"""Boku-nanoの学習済み重みをブラウザ向けONNXへ変換して検証する。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import numpy as np
import onnx
import onnxruntime as ort
from safetensors.torch import load_file as load_safetensors
import torch
from tokenizers import Tokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM  # noqa: E402
from scripts.model.evaluate_boku_nano import PROMPT_TEMPLATE  # noqa: E402


DEFAULT_MODELS = {
    "3epoch": PROJECT_ROOT / "data/models/boku_nano_bpe_2048",
    "10epoch": PROJECT_ROOT / "data/models/boku_nano_bpe_2048_10epoch",
}
DEFAULT_TOKENIZER = PROJECT_ROOT / "data/tokenizers/bpe_2048/tokenizer.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "web/models"


class LastTokenLogits(torch.nn.Module):
    """ブラウザの自己回帰生成に必要な末尾位置logitsだけを返す。"""

    def __init__(self, model: BokuNanoForCausalLM) -> None:
        super().__init__()
        self.model = model

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        return self.model(input_ids).logits[:, -1, :]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="3/10エポックのBoku-nanoをONNXへ変換しPyTorch出力と比較します。"
    )
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tokenizer", type=Path, default=DEFAULT_TOKENIZER)
    parser.add_argument(
        "--model",
        action="append",
        metavar="NAME=DIR",
        help="変換対象。省略時は3epochと10epochの両方。",
    )
    parser.add_argument("--opset", type=int, default=18)
    parser.add_argument("--sample-sequence-length", type=int, default=32)
    parser.add_argument("--atol", type=float, default=2.0e-4)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--skip-generation-check", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_models(values: list[str] | None) -> dict[str, Path]:
    if not values:
        return DEFAULT_MODELS.copy()
    result: dict[str, Path] = {}
    for value in values:
        name, separator, directory = value.partition("=")
        if not separator or not name or not directory:
            raise ValueError("--modelはNAME=DIR形式で指定してください")
        if name in result:
            raise ValueError(f"モデル名が重複しています: {name}")
        result[name] = Path(directory).resolve()
    return result


def load_model(directory: Path) -> tuple[BokuNanoForCausalLM, BokuNanoConfig, Path]:
    config_path = directory / "model_config.json"
    weights_path = directory / "model.safetensors"
    if not config_path.is_file() or not weights_path.is_file():
        raise FileNotFoundError(f"モデル成果物が不足しています: {directory}")
    config = BokuNanoConfig.from_dict(
        json.loads(config_path.read_text(encoding="utf-8"))
    )
    model = BokuNanoForCausalLM(config)
    model.load_state_dict(load_safetensors(str(weights_path), device="cpu"), strict=True)
    model.eval()
    return model, config, weights_path


def export_model(
    model: BokuNanoForCausalLM,
    output_path: Path,
    sample_sequence_length: int,
    opset: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample = torch.arange(sample_sequence_length, dtype=torch.long)[None, :]
    sample %= model.config.vocab_size
    wrapper = LastTokenLogits(model).eval()
    with torch.inference_mode():
        torch.onnx.export(
            wrapper,
            (sample,),
            str(output_path),
            input_names=["input_ids"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "sequence"},
                "logits": {0: "batch"},
            },
            opset_version=opset,
            do_constant_folding=True,
            dynamo=False,
        )
    checked = onnx.load(str(output_path), load_external_data=True)
    onnx.checker.check_model(checked)
    if output_path.stat().st_size >= 100 * 1024 * 1024:
        raise ValueError(f"GitHubの単一ファイル上限を超えています: {output_path}")


def compare_logits(
    model: BokuNanoForCausalLM,
    session: ort.InferenceSession,
    input_ids: list[int],
    atol: float,
) -> dict[str, float]:
    values = np.asarray([input_ids], dtype=np.int64)
    with torch.inference_mode():
        expected = model(torch.from_numpy(values)).logits[:, -1, :].numpy()
    actual = session.run(["logits"], {"input_ids": values})[0]
    maximum = float(np.max(np.abs(expected - actual)))
    mean = float(np.mean(np.abs(expected - actual)))
    if not np.allclose(expected, actual, atol=atol, rtol=1.0e-4):
        raise AssertionError(f"PyTorchとONNXのlogitsが不一致です: max_abs_diff={maximum}")
    return {"max_abs_diff": maximum, "mean_abs_diff": mean}


def generate_with_pytorch(
    model: BokuNanoForCausalLM,
    prompt_ids: list[int],
    eos_token_id: int,
    max_new_tokens: int,
) -> list[int]:
    current = prompt_ids.copy()
    generated: list[int] = []
    with torch.inference_mode():
        for _ in range(min(max_new_tokens, model.config.context_length - len(current))):
            values = torch.tensor([current], dtype=torch.long)
            token_id = int(torch.argmax(model(values).logits[0, -1]).item())
            if token_id == eos_token_id:
                break
            generated.append(token_id)
            current.append(token_id)
    return generated


def generate_with_onnx(
    session: ort.InferenceSession,
    prompt_ids: list[int],
    eos_token_id: int,
    context_length: int,
    max_new_tokens: int,
) -> list[int]:
    current = prompt_ids.copy()
    generated: list[int] = []
    for _ in range(min(max_new_tokens, context_length - len(current))):
        values = np.asarray([current], dtype=np.int64)
        logits = session.run(["logits"], {"input_ids": values})[0][0]
        token_id = int(np.argmax(logits))
        if token_id == eos_token_id:
            break
        generated.append(token_id)
        current.append(token_id)
    return generated


def verify_model(
    model: BokuNanoForCausalLM,
    onnx_path: Path,
    tokenizer: Tokenizer,
    atol: float,
    max_new_tokens: int,
    check_generation: bool,
) -> dict[str, Any]:
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    prompts = [
        "整数リストxsから偶数だけを残すsolve関数を書いてください。",
        "xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。",
    ]
    comparisons: list[dict[str, Any]] = []
    for instruction in prompts:
        prompt = PROMPT_TEMPLATE.format(instruction_ja=instruction)
        prompt_ids = tokenizer.encode(prompt, add_special_tokens=False).ids
        result: dict[str, Any] = {
            "instruction": instruction,
            "prompt_tokens": len(prompt_ids),
            **compare_logits(model, session, prompt_ids, atol),
        }
        if check_generation:
            expected = generate_with_pytorch(model, prompt_ids, 2, max_new_tokens)
            actual = generate_with_onnx(
                session,
                prompt_ids,
                2,
                model.config.context_length,
                max_new_tokens,
            )
            if expected != actual:
                raise AssertionError("PyTorchとONNXのgreedy生成token列が一致しません")
            result["generated_tokens"] = len(actual)
            result["generated_code"] = tokenizer.decode(actual, skip_special_tokens=True)
        comparisons.append(result)
    return {
        "providers": session.get_providers(),
        "comparisons": comparisons,
    }


def main() -> None:
    args = parse_args()
    if args.sample_sequence_length <= 0:
        raise ValueError("--sample-sequence-lengthは正の整数にしてください")
    tokenizer = Tokenizer.from_file(str(args.tokenizer))
    output_directory = args.output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    web_root = output_directory.parent
    tokenizer_output = web_root / "tokenizer.json"
    shutil.copyfile(args.tokenizer.resolve(), tokenizer_output)

    manifest: dict[str, Any] = {
        "format_version": 1,
        "tokenizer": {
            "path": "tokenizer.json",
            "sha256": sha256(tokenizer_output),
        },
        "prompt_template": PROMPT_TEMPLATE,
        "special_token_ids": {"pad": 0, "bos": 1, "eos": 2, "unk": 3, "task": 4, "code": 5},
        "models": [],
    }
    for name, directory in selected_models(args.model).items():
        print(f"[{name}] 読み込み: {directory}", flush=True)
        model, config, weights_path = load_model(directory)
        onnx_path = output_directory / f"boku-nano-{name}.onnx"
        print(f"[{name}] ONNX変換: {onnx_path}", flush=True)
        export_model(model, onnx_path, args.sample_sequence_length, args.opset)
        print(f"[{name}] PyTorchとの比較", flush=True)
        verification = verify_model(
            model,
            onnx_path,
            tokenizer,
            args.atol,
            args.max_new_tokens,
            not args.skip_generation_check,
        )
        manifest["models"].append(
            {
                "id": name,
                "label": "3エポックモデル" if name == "3epoch" else "10エポックモデル",
                "path": f"models/{onnx_path.name}",
                "sha256": sha256(onnx_path),
                "size_bytes": onnx_path.stat().st_size,
                "source_sha256": sha256(weights_path),
                "parameter_count": model.parameter_count(),
                "context_length": config.context_length,
                "vocab_size": config.vocab_size,
                "verification": verification,
            }
        )
        print(
            f"[{name}] 完了: {onnx_path.stat().st_size / 1024 / 1024:.1f} MiB",
            flush=True,
        )
    manifest_path = web_root / "model-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"manifest: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
