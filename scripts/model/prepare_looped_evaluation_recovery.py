"""報告と保存重みから小型loopの評価専用設定を復元する。学習manifestは作らない。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REPORT = ROOT / "docs/results/boku_nano_looped_all_sizes_20261015.md"
REPORT_SHA256 = "8cecdb3a180d730dc34e77925bc65c336036fe02a507e5953b06fc633903f4df"
BASE_CONFIG = ROOT / "config/boku_nano_looped_lt1_3epoch.yaml"
RUNNER = ROOT / "scripts/model/run_boku_nano_looped_experiment.py"
MODEL_CODE = ROOT / "scripts/model/boku_nano.py"
WEIGHTS_ROOT = ROOT / "data/models/looped_all_sizes_20261015"
TOKENIZER = ROOT / "data/tokenizers/bpe_2048/tokenizer.json"
TOKENIZER_SHA256 = "6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293"
# Values are transcribed from the frozen report, not inferred from tensor shapes.
VARIANTS = {
    "lt1": (128, 256, 4, 426368, "34266e64bcc100975f804f6d7b80c3061227911c381afd0f85d4f17bec36f704"),
    "f128": (128, 128, 4, 377216, "c8a7a3a0f7761a7a2ceceab408c70f5f0ba375821a9a4aaff60671c7dfbdd485"),
    "w96": (96, 192, 3, 289056, "a8723af569667ef9b5b1bbbaa46d4102b95513e04be416c4abe3b79e4b2b52ed"),
    "w64": (64, 128, 2, 172224, "0f0c290cf8875e6a0d2949732684b306a40012de939a1a49fed6eaf84a87b193"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def prepare(output_root: Path, variants: list[str]) -> list[dict]:
    """全モデルの検証後に新規JSONだけを保存し、既存ファイルへの書込みを拒否する。"""
    import torch
    import yaml
    from safetensors.torch import load_file
    from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM
    from scripts.model.run_boku_nano_looped_experiment import architecture, parameter_count

    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"出力先は既に存在します。未使用の場所を指定してください: {output_root}")
    if not variants or len(variants) != len(set(variants)) or any(v not in VARIANTS for v in variants):
        raise ValueError("lt1/f128/w96/w64から重複なしで選んでください")
    if sha256(REPORT) != REPORT_SHA256:
        raise ValueError("復元根拠の報告書hashが変わっています。内容を再確認してください")
    if sha256(TOKENIZER) != TOKENIZER_SHA256:
        raise ValueError("標準BPEのtokenizer hashが一致しません")
    base = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    sources = {display_path(p): sha256(p) for p in (REPORT, BASE_CONFIG, RUNNER, MODEL_CODE)}
    created_at = datetime.now(timezone.utc).isoformat()
    prepared = []
    for variant in variants:
        d_model, d_ff, n_heads, expected_count, expected_sha = VARIANTS[variant]
        source_directory = WEIGHTS_ROOT / f"{variant}_seed20260925" / "model"
        weights = source_directory / "model.safetensors"
        original_manifest = source_directory / "training_manifest.json"
        original_config = source_directory / "model_config.json"
        if original_manifest.exists() or original_config.exists():
            raise ValueError(f"元設定または学習manifestがあります。復元せず正本を確認してください: {source_directory}")
        actual_sha = sha256(weights)
        if actual_sha != expected_sha:
            raise ValueError(f"報告と保存重みのhashが一致しません: {variant}")
        expected_architecture = dict(d_model=d_model, d_ff=d_ff, n_heads=n_heads,
                                     n_layers=1, n_loops=3, tie_word_embeddings=True,
                                     loop_input_mode="none")
        if architecture(variant) != expected_architecture:
            raise ValueError(f"既存runnerと報告の構造が一致しません: {variant}")
        values = dict(base["model"], **expected_architecture)
        # These later-added defaults preserve the original full-loop forward.
        values.update(loop_pattern="full", residual_scale=1.0, recurrent_residual_scale=1.0)
        config = BokuNanoConfig.from_dict(values)
        expected_common = {"vocab_size": 2048, "context_length": 256, "dropout": 0.0,
                           "rope_base": 10000.0, "rms_norm_eps": 1e-5}
        if any(config.to_dict()[key] != value for key, value in expected_common.items()):
            raise ValueError("元のLT1設定の共通項目が変更されています")
        model = BokuNanoForCausalLM(config)
        state = load_file(str(weights), device="cpu")
        model.load_state_dict(state, strict=True)
        actual_count = model.parameter_count()
        if actual_count != expected_count or parameter_count(config) != expected_count:
            raise ValueError(f"報告と復元モデルのparameter数が一致しません: {variant}")
        if model.lm_head.weight is not model.token_embedding.weight:
            raise ValueError(f"embedding/head共有が復元されていません: {variant}")
        if not all(torch.isfinite(tensor).all().item() for tensor in state.values()):
            raise ValueError(f"非有限の重みがあります: {variant}")
        if sha256(weights) != actual_sha:
            raise ValueError(f"検証中に重みが変更されました: {variant}")
        model_config = config.to_dict()
        config_payload = json_bytes(model_config)
        config_path = output_root / variant / "model_config.json"
        manifest = {
            "format_version": 1,
            "status": "recovered_for_evaluation",
            "created_at": created_at,
            "variant": variant,
            "description": "Evaluation-only reconstruction from a frozen report, existing runner, and exact checkpoint bytes. This is not an original training manifest or a new training run.",
            "weights_path": display_path(weights),
            "weights_sha256": actual_sha,
            "expected_weights_sha256": expected_sha,
            "model_config_path": display_path(config_path),
            "model_config_sha256": hashlib.sha256(config_payload).hexdigest(),
            "model_config": model_config,
            "tokenizer_path": display_path(TOKENIZER),
            "tokenizer_sha256": TOKENIZER_SHA256,
            "parameter_count": actual_count,
            "expected_parameter_count": expected_count,
            "source_report": {"path": display_path(REPORT), "sha256": REPORT_SHA256},
            "configuration_sources": sources,
            "configuration_basis": {
                "report_and_runner": ["d_model", "d_ff", "n_heads", "n_layers", "n_loops", "tie_word_embeddings", "loop_input_mode"],
                "base_lt1_config": list(expected_common),
                "backward_compatible_defaults": {"loop_pattern": "full", "residual_scale": 1.0, "recurrent_residual_scale": 1.0},
                "limitation": "Tensor shapes alone cannot establish loop count, attention head count, or forward semantics. These values are reconstructed from the named sources.",
            },
            "original_training_manifest_path": display_path(original_manifest),
            "original_training_manifest_present": False,
            "original_model_config_present": False,
            "reported_training": {
                "seed": 20260925,
                "epochs": 3,
                "source": display_path(REPORT),
                "provenance": "Reported historical values; no original training manifest/log was recovered or newly generated.",
            },
            "validation": {
                "strict_load": True,
                "parameter_count_verified": True,
                "tied_embeddings_verified": True,
                "finite_weights_verified": True,
                "source_weights_unchanged": True,
                "device": "cpu",
                "inference_performed": False,
                "training_performed": False,
            },
        }
        prepared.append((variant, config_payload, manifest))
        del model, state

    # Validate every checkpoint before creating any output directory.
    output_root.mkdir(parents=True, exist_ok=False)
    results = []
    for variant, config_payload, manifest in prepared:
        directory = output_root / variant
        directory.mkdir()
        with (directory / "model_config.json").open("xb") as stream:
            stream.write(config_payload)
        with (directory / "recovery_manifest.json").open("xb") as stream:
            stream.write(json_bytes(manifest))
        results.append({"variant": variant, "directory": display_path(directory),
                        "weights_path": manifest["weights_path"],
                        "parameter_count": manifest["parameter_count"],
                        "status": manifest["status"]})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True,
                        help="未使用の評価専用復元ディレクトリ。重みは複製しない")
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    args = parser.parse_args()
    for result in prepare(args.output_root, args.variants):
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
