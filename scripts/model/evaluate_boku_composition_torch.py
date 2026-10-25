#!/usr/bin/env python3
"""発表資料の旧872問を固定し、NVIDIA CUDAのPyTorchバッチ推論で新規評価する。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import time
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATASET = ROOT / "data/benchmarks/composition_suite_20261008"
QUESTIONS_SHA256 = "aa119fa2a9e8507136ad14a54b9d3d2e9043fd81af9e48251ef7f5c49c20f97f"
TEST_CASES_SHA256 = "0090a38d255848a813876ce3b64a8029603aa14e4181b453a89801b41ac67fc2"
PROTOCOL_SHA256 = "6af76f37503d99590e88307c107f8529aebac79f6c3593eb0016ab4ae766c22d"
TOKENIZER_SHA256 = "6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293"
PROMPT_TEMPLATE = "<|bos|><|task|>\n{instruction_ja}\n<|code|>\n"
CONTEXT_LENGTH = 256
EOS_ID = 2
SUITE_COUNTS = {"transfer_1op": 96, "composition_2op": 100, "repeat_2": 96,
                "transfer_3to2": 88, "composition_3op": 100, "repeat_3": 96,
                "repeat_4": 96, "general_4op": 100, "repeat_abab": 100}
# 旧採点器は変更せず、呼び出す実ファイルと依存する意味解釈を固定する。
SCORING_HASHES = {
    "scripts/model/score_composition_suite.py": "e4d86b978fb968040371ce12ee0c8903f056ae2a303426c4b4bebe0b3e4ab8e1",
    "scripts/model/composition_suite_common.py": "a38d66004952c7e896824fe6c9af36ea2f45d4848897f2ced877926deaa1da72",
    "scripts/model/score_browser_100_benchmark.py": "b001cf8c414310606b2a213b0f5ad0993dc9c83ef06dbe9319c645307c4fc559",
    "reference_interpreter.py": "4b7254b1ff0c9b4d21b693e6a5169a9c2490ca2f16d8004e57c77460210fa7b9",
    "generated_code_verifier.py": "3ec6c53baab408ba265e5e1e2f2d4edf7b1e4c0db3c87038593aa063d7644c29",
    "python_code_generator.py": "98fc8fb25118418de354fe15356df1aa2a6df85ba9c44c4223e9adb4f6a4742c",
}
DEFAULT_MODELS = {
    "boku-15m-1epoch": "data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch",
    "boku-5m-1epoch": "data/models/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch",
    "boku-1m-3epoch": "data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch",
    "middle4-1m-3epoch": "data/models/middle4_1m_3epoch_20261018/u3_middle4_seed20260925/model",
    "middle4-scaled025-1m-3epoch": "data/models/middle4_1m_3epoch_20261018/u3_middle4_scaled025_seed20260925/model",
}
DEFAULT_SELECTION = ["boku-15m-1epoch", "boku-5m-1epoch", "boku-1m-3epoch"]
BASELINE_WEIGHTS = {
    "boku-15m-1epoch": "1a0002e1b50aeae59805d8087fbaa16be1b6e2716d78a085230f2cc35edbf68f",
    "boku-5m-1epoch": "027fe1b64c4495dd39322f0ade7824e085b7315543c840b031742e42f4a4c0c6",
    "boku-1m-3epoch": "e9eafad8c5195b501414c4456b04918258cc1a3a6ef799d5d77f3ea69cd17533",
}
BASELINE_MODEL_CONFIG_HASHES = {
    "boku-15m-1epoch": "15d303c16af19f7b43a45ccf0c489f42a37fb773cd773fecf4fc2e1e55b88596",
    "boku-5m-1epoch": "819b7f5a5caecdbbf1b09eafd99a1937e6d790ca43ddd0b99460700151aa2a0e",
    "boku-1m-3epoch": "8be0e71c236252ae3a8d09e5ecd7a02ec639599a0189b01635564c19984b3a9d",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[dict]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def validate_dataset(dataset: Path = DATASET) -> tuple[list[dict], list[dict], dict]:
    """データ自身が宣言するhashだけに依存せず、旧872問のhashへ固定する。"""
    if sha(dataset / "protocol.json") != PROTOCOL_SHA256:
        raise ValueError("旧872問のprotocol.json固定hashと不一致です")
    protocol = read_json(dataset / "protocol.json")
    for filename, expected, key in (
        ("questions.jsonl", QUESTIONS_SHA256, "questions_sha256"),
        ("test_cases.json", TEST_CASES_SHA256, "test_cases_sha256"),
    ):
        if sha(dataset / filename) != expected or protocol.get(key) != expected:
            raise ValueError(f"旧872問の固定hashと不一致です: {filename}")
    questions = read_jsonl(dataset / "questions.jsonl")
    cases = read_json(dataset / "test_cases.json")
    if (len(questions) != 872 or len({q["question_id"] for q in questions}) != 872
            or Counter(q["suite"] for q in questions) != SUITE_COUNTS
            or len(cases) != 179 or protocol.get("suites") != SUITE_COUNTS):
        raise ValueError("旧872問・9集合・179検査入力の構成と一致しません")
    for relative, expected in SCORING_HASHES.items():
        if sha(ROOT / relative) != expected:
            raise ValueError(f"旧採点コードが変更されています: {relative}")
    return questions, cases, protocol


def select_models(names: list[str] | None, overrides: list[str]) -> dict[str, Path]:
    selected = {name: resolve_path(DEFAULT_MODELS[name]) for name in
                (names if names is not None else ([] if overrides else DEFAULT_SELECTION))}
    override_names = set()
    for specification in overrides:
        name, separator, path = specification.partition("=")
        if not separator or not path or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
            raise ValueError("--modelには安全な名前=学習済みモデルディレクトリを指定してください")
        if name in override_names:
            raise ValueError(f"--modelの名前が重複しています: {name}")
        override_names.add(name)
        selected[name] = resolve_path(path)
    if not selected:
        raise ValueError("評価モデルを1個以上選択してください")
    return selected


def validate_model(name: str, directory: Path) -> dict:
    """JSONとファイルhashだけを読む。重みの復元・モデル初期化・CUDA呼出はしない。"""
    paths = {"weights": directory / "model.safetensors", "model_config": directory / "model_config.json",
             "training_manifest": directory / "training_manifest.json"}
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(f"必要な学習済みartifactがありません: {path}")
    manifest = read_json(paths["training_manifest"])
    config = read_json(paths["model_config"])
    if manifest.get("status") != "completed" or manifest.get("model_config") != config:
        raise ValueError(f"学習完了manifestとmodel_configが一致しません: {name}")
    if config.get("context_length") != CONTEXT_LENGTH or config.get("vocab_size") != 2048:
        raise ValueError(f"旧評価と同じ256文脈長・2048語彙が必要です: {name}")
    weights_sha = sha(paths["weights"])
    if weights_sha != manifest.get("model_sha256"):
        raise ValueError(f"重みと学習manifestのhashが一致しません: {name}")
    if name in BASELINE_WEIGHTS and weights_sha != BASELINE_WEIGHTS[name]:
        raise ValueError(f"発表資料の固定checkpointと異なります。別名で評価してください: {name}")
    # 同じ重みでもloop設定を変えると別モデルになるため、基準名の構造も固定する。
    if name in BASELINE_MODEL_CONFIG_HASHES and sha(paths["model_config"]) != BASELINE_MODEL_CONFIG_HASHES[name]:
        raise ValueError(f"発表資料の固定model_configと異なります。別名で評価してください: {name}")
    if name.startswith("middle4") and name in DEFAULT_MODELS:
        scale = 0.25 if "scaled025" in name else 1.0
        if (config.get("loop_pattern") != "middle" or config.get("n_loops") != 4
                or config.get("n_layers") != 3 or config.get("d_model") != 128
                or config.get("recurrent_residual_scale", 1.0) != scale or manifest.get("epochs") != 3):
            raise ValueError(f"既定middle4候補と異なります。別名で評価してください: {name}")
    tokenizer_path = resolve_path(manifest["tokenizer_path"])
    if manifest.get("tokenizer_sha256") != TOKENIZER_SHA256 or sha(tokenizer_path) != TOKENIZER_SHA256:
        raise ValueError(f"発表資料と同じtokenizerが必要です: {name}")
    paths["tokenizer"] = tokenizer_path
    return {"name": name, "directory": display_path(directory), "model_config": config,
            "parameter_count": manifest.get("parameter_count"), "epochs": manifest.get("epochs"),
            "weight_sha256": weights_sha, "tokenizer_sha256": TOKENIZER_SHA256,
            "tokenizer_path": display_path(tokenizer_path),
            "source_hashes": {display_path(path): sha(path) for path in paths.values()}}


def encode_prompts(questions: Sequence[dict], tokenizer) -> list[list[int]]:
    expected_tokens = {"<|pad|>": 0, "<|bos|>": 1, "<|eos|>": 2,
                       "<|unk|>": 3, "<|task|>": 4, "<|code|>": 5}
    if any(tokenizer.token_to_id(token) != ident for token, ident in expected_tokens.items()):
        raise ValueError("特殊token IDが旧評価と一致しません")
    encoded = []
    for question in questions:
        prompt = PROMPT_TEMPLATE.format(instruction_ja=question["instruction_ja"])
        ids = tokenizer.encode(prompt, add_special_tokens=False).ids
        if not ids or ids[0] != 1 or 3 in ids or len(ids) >= CONTEXT_LENGTH:
            raise ValueError(f"使用できないpromptです: {question['question_id']}")
        encoded.append(ids)
    return encoded


def grouped_batches(prompts: Sequence[Sequence[int]], batch_size: int) -> list[list[int]]:
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_sizeは正整数にしてください")
    groups = defaultdict(list)
    for index, prompt in enumerate(prompts):
        groups[len(prompt)].append(index)
    return [indices[start:start + batch_size] for indices in groups.values()
            for start in range(0, len(indices), batch_size)]


def greedy_equal_length(prompts: Sequence[Sequence[int]],
                        predict_next: Callable[[list[list[int]]], list[int]],
                        context_length: int = CONTEXT_LENGTH) -> list[dict]:
    """純粋な生成制御。callbackをmockに替え、実モデルなしで停止条件を検査できる。"""
    if not prompts or len({len(prompt) for prompt in prompts}) != 1:
        raise ValueError("空でない同長promptのbatchが必要です")
    if not prompts[0] or len(prompts[0]) >= context_length:
        raise ValueError("promptはcontext_length未満にしてください")
    sequences = [list(prompt) for prompt in prompts]
    results = [{"output_ids": [], "termination": "max_context"} for _ in prompts]
    finished = [False] * len(prompts)
    while len(sequences[0]) < context_length:
        next_ids = predict_next(sequences)
        if len(next_ids) != len(prompts) or any(type(token) is not int for token in next_ids):
            raise ValueError("予測tokenの件数・型がbatchと一致しません")
        for index, token in enumerate(next_ids):
            if not finished[index]:
                if token == EOS_ID:
                    finished[index] = True
                    results[index]["termination"] = "eos"
                else:
                    results[index]["output_ids"].append(token)
            # EOS後は同長維持用にEOSを追加する。保存出力にはEOSを含めない。
            sequences[index].append(EOS_ID if finished[index] else token)
        if all(finished):
            break
    return results


def generate_records(questions: Sequence[dict], prompts: Sequence[Sequence[int]], tokenizer,
                     name: str, batch_size: int, predict_next, progress=None) -> list[dict]:
    if len(questions) != len(prompts):
        raise ValueError("問題数とprompt数が一致しません")
    records = [None] * len(questions)
    done = 0
    for batch_id, indices in enumerate(grouped_batches(prompts, batch_size)):
        started = time.perf_counter()
        results = greedy_equal_length([prompts[index] for index in indices], predict_next)
        elapsed = time.perf_counter() - started
        for index, result in zip(indices, results):
            question = questions[index]
            records[index] = {"kind": "inference", "model": name, "condition": "A",
                              "question_id": question["question_id"], "suite": question["suite"],
                              "category_id": question["category_id"], "instruction": question["instruction_ja"],
                              "prompt": PROMPT_TEMPLATE.format(instruction_ja=question["instruction_ja"]),
                              "prompt_ids": list(prompts[index]), "batch_size": len(indices),
                              "batch_id": batch_id, "batch_elapsed_seconds": elapsed, **result,
                              "raw_output": tokenizer.decode(result["output_ids"], skip_special_tokens=True)}
        done += len(indices)
        if progress is not None:
            progress(f"{name}: {done}/{len(questions)} batch={len(indices)} {elapsed:.2f}s")
    return records


def summarize(scored: Sequence[dict]) -> dict:
    return {suite: {"passed": sum(row["passed"] for row in scored if row["suite"] == suite),
                    "total": sum(row["suite"] == suite for row in scored)} for suite in SUITE_COUNTS}


def validate_record_identity(rows: Sequence[dict], questions: Sequence[dict], name: str) -> None:
    if (len(rows) != len(questions) or len({row["question_id"] for row in rows}) != len(questions)
            or {row["question_id"] for row in rows} != {q["question_id"] for q in questions}):
        raise ValueError(f"保存結果に欠落・重複・別問題があります: {name}")
    mapping = {q["question_id"]: q for q in questions}
    for row in rows:
        question = mapping[row["question_id"]]
        if (row["model"] != name or row["condition"] != "A" or row["suite"] != question["suite"]
                or row["category_id"] != question["category_id"]):
            raise ValueError(f"保存結果のモデル・問題の対応が一致しません: {name}")


def load_reference(root: Path | None, spec: dict, questions: Sequence[dict], prompts) -> dict | None:
    if root is not None and not root.is_dir():
        raise FileNotFoundError(f"比較対象のrunsディレクトリがありません: {root}")
    if root is None or not (root / spec["name"]).exists():
        return None
    directory = root / spec["name"]
    config = read_json(directory / "config.json")
    provenance = read_json(directory / "scoring_provenance.json")
    source_weight = config.get("catalog_entry", {}).get("source_weight_sha256", config.get("weight_sha256"))
    if (config.get("questions_sha256") != QUESTIONS_SHA256
            or config.get("tokenizer_sha256") != TOKENIZER_SHA256
            or source_weight != spec["weight_sha256"]
            or config.get("prompt_template") != PROMPT_TEMPLATE
            or config.get("context_length") != CONTEXT_LENGTH
            or config.get("temperature") != 0 or config.get("history") is not False
            or config.get("repair") is not False
            or provenance.get("questions_sha256") != QUESTIONS_SHA256
            or provenance.get("test_cases_sha256") != TEST_CASES_SHA256
            or provenance.get("scorer_sha256") != SCORING_HASHES["scripts/model/score_composition_suite.py"]
            or provenance.get("common_sha256") != SCORING_HASHES["scripts/model/composition_suite_common.py"]
            or provenance.get("raw_inference_sha256") != sha(directory / "raw_inference.jsonl")):
        raise ValueError(f"比較対象の条件・hashが一致しません: {directory}")
    raw = read_jsonl(directory / "raw_inference.jsonl")
    if not raw or raw[-1].get("kind") != "complete":
        raise ValueError(f"比較対象が完了していません: {directory}")
    rows = [row for row in raw if row.get("kind") == "inference"]
    scored = read_jsonl(directory / "scored.jsonl")
    validate_record_identity(rows, questions, spec["name"])
    validate_record_identity(scored, questions, spec["name"])
    prompt_map = {q["question_id"]: (q, prompt) for q, prompt in zip(questions, prompts)}
    for row in scored:
        question, _ = prompt_map[row["question_id"]]
        if row.get("ast_id") != question["ast_id"] or type(row.get("passed")) is not bool:
            raise ValueError("比較対象の採点AST ID・合否型が一致しません")
    for row in rows:
        question, prompt = prompt_map[row["question_id"]]
        if (row.get("prompt_ids") != prompt or row.get("instruction") != question["instruction_ja"]
                or row.get("prompt") != PROMPT_TEMPLATE.format(instruction_ja=question["instruction_ja"])):
            raise ValueError("比較対象の実promptが一致しません")
    if read_json(directory / "summary.json") != summarize(scored):
        raise ValueError("比較対象のsummaryが問題別採点と一致しません")
    return {"rows": rows, "scored": scored, "source_hashes": {
        display_path(directory / filename): sha(directory / filename) for filename in
        ("config.json", "raw_inference.jsonl", "scored.jsonl", "summary.json", "scoring_provenance.json")}}


def compare_records(current: Sequence[dict], previous: Sequence[dict],
                    current_scored: Sequence[dict] | None = None,
                    previous_scored: Sequence[dict] | None = None) -> dict:
    old = {row["question_id"]: row for row in previous}
    if len(old) != len(previous) or set(old) != {row["question_id"] for row in current}:
        raise ValueError("比較する問題IDが一致しません")
    differences = []
    for row in current:
        before = old[row["question_id"]]
        fields = [key for key in ("prompt_ids", "output_ids", "termination", "raw_output") if row[key] != before[key]]
        if fields:
            differences.append({"question_id": row["question_id"], "fields": fields,
                                "previous_output_ids": before["output_ids"], "current_output_ids": row["output_ids"],
                                "previous_raw_output": before["raw_output"], "current_raw_output": row["raw_output"]})
    result = {"question_count": len(current), "different_generation_count": len(differences),
              "generation_differences": differences}
    if current_scored is not None and previous_scored is not None:
        old_scores = {row["question_id"]: row for row in previous_scored}
        result["pass_changes"] = [{"question_id": row["question_id"], "previous_passed": old_scores[row["question_id"]]["passed"],
                                   "current_passed": row["passed"]} for row in current_scored
                                  if row["passed"] != old_scores[row["question_id"]]["passed"]]
        result["pass_change_count"] = len(result["pass_changes"])
    return result


def require_new_output(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"既存出力は再利用・上書きしません。新しい--output-rootを指定してください: {path}")


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, help="新規の結果ディレクトリ。既存パスは禁止")
    parser.add_argument("--models", nargs="+", choices=list(DEFAULT_MODELS), help="省略時は基準3個。middle4候補2個は明示指定")
    parser.add_argument("--model", action="append", default=[], metavar="NAME=DIRECTORY",
                        help="学習済みartifactの追加・配置変更。これだけ指定した場合は指定モデルのみ")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--score-workers", type=int, default=4)
    parser.add_argument("--reference-root", type=Path, help="旧runsを指定すると同条件の保存出力・合否と照合")
    parser.add_argument("--check-batch-size-one", action="store_true", help="同じCUDAモデルでbatch=1も生成し、全872問の差を保存")
    parser.add_argument("--validate-only", action="store_true", help="ファイル・hash・promptだけ検査。重み読込・CUDA呼出・評価・出力作成なし")
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args(argv)
    if not args.list_models and args.output_root is None:
        parser.error("--output-rootが必要です")
    if args.batch_size <= 0 or args.score_workers <= 0:
        parser.error("--batch-sizeと--score-workersは正整数にしてください")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.list_models:
        print(json.dumps(DEFAULT_MODELS, ensure_ascii=False, indent=2))
        return
    # resolve前に末端symlinkも検査し、存在しないリンク先への迂回を許可しない。
    require_new_output(args.output_root)
    output = args.output_root.resolve()
    require_new_output(output)
    questions, cases, protocol = validate_dataset()
    selected = select_models(args.models, args.model)
    specs = [validate_model(name, path) for name, path in selected.items()]
    # validate-onlyでもprompt検査を行うが、torchやsafetensorsはimportしない。
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(resolve_path(specs[0]["tokenizer_path"])))
    prompts = encode_prompts(questions, tokenizer)
    references = {spec["name"]: load_reference(args.reference_root.resolve() if args.reference_root else None,
                                              spec, questions, prompts) for spec in specs}
    script_paths = [Path(__file__), ROOT / "scripts/model/boku_nano.py",
                    *[ROOT / relative for relative in SCORING_HASHES]]
    source_hashes = {display_path(path): sha(path) for path in
                     [*script_paths, *[DATASET / name for name in ("questions.jsonl", "test_cases.json", "protocol.json")]]}
    configuration = {"format_version": 1, "dataset": display_path(DATASET), "question_count": 872,
                     "test_case_count": 179, "questions_sha256": QUESTIONS_SHA256, "test_cases_sha256": TEST_CASES_SHA256,
                     "prompt_template": PROMPT_TEMPLATE, "context_length": CONTEXT_LENGTH, "condition": "A",
                     "decoding": "greedy", "temperature": 0, "history": False, "repair": False,
                     "batch_size": args.batch_size, "batching": "equal_prompt_length_no_padding",
                     "dtype": "float32", "tf32": False, "autocast": False, "sdpa_backend": "math",
                     "kv_cache": False, "score_workers": args.score_workers,
                     "check_batch_size_one": args.check_batch_size_one, "models": specs,
                     "source_hashes": source_hashes}
    if args.validate_only:
        print(json.dumps({"status": "validated_without_inference", **configuration}, ensure_ascii=False, indent=2))
        return

    import torch
    from torch.nn.attention import SDPBackend, sdpa_kernel
    from safetensors.torch import load_file
    from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM
    from scripts.model.score_composition_suite import score_one
    if not torch.cuda.is_available() or torch.version.cuda is None or torch.version.hip is not None:
        raise RuntimeError("NVIDIA CUDA版PyTorchと利用可能なGPUが必要です。CPU/MPSへはfallbackしません")
    torch.set_float32_matmul_precision("highest")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    device = torch.device("cuda:0")
    environment = {"python": platform.python_version(), "platform": platform.platform(), "torch": torch.__version__,
                   "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(device),
                   "device": str(device), "started_at": datetime.now(timezone.utc).isoformat()}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "config.json", configuration)
    write_json(output / "environment.json", environment)
    write_json(output / "protocol.json", protocol)
    comparisons = []
    for spec in specs:
        name = spec["name"]
        directory = output / name
        directory.mkdir()
        conf = {key: value for key, value in configuration.items() if key != "models"}
        conf.update(model=name, weight_sha256=spec["weight_sha256"], tokenizer_sha256=TOKENIZER_SHA256, model_metadata=spec)
        write_json(directory / "config.json", conf)
        write_json(directory / "source_hashes.json", {**source_hashes, **spec["source_hashes"]})
        model = BokuNanoForCausalLM(BokuNanoConfig.from_dict(spec["model_config"]))
        model.load_state_dict(load_file(str(resolve_path(spec["directory"]) / "model.safetensors"), device="cpu"), strict=True)
        if model.parameter_count() != spec["parameter_count"]:
            raise ValueError(f"parameter数が学習manifestと一致しません: {name}")
        model.to(device=device, dtype=torch.float32).eval()

        def predict_next(sequences):
            input_ids = torch.tensor(sequences, dtype=torch.long, device=device)
            return model(input_ids).logits[:, -1, :].argmax(dim=-1).tolist()

        torch.cuda.reset_peak_memory_stats(device)
        started = time.perf_counter()
        with torch.inference_mode(), sdpa_kernel(SDPBackend.MATH):
            rows = generate_records(questions, prompts, tokenizer, name, args.batch_size, predict_next,
                                    progress=lambda message: print(message, flush=True))
        torch.cuda.synchronize(device)
        inference_seconds = time.perf_counter() - started
        peak_bytes = torch.cuda.max_memory_allocated(device)
        raw = [{"kind": "environment", "config": conf, **environment}, *rows,
               {"kind": "complete", "records": len(rows), "completed_at": datetime.now(timezone.utc).isoformat()}]
        write_jsonl(directory / "raw_inference.jsonl", raw)
        batch_check = None
        if args.check_batch_size_one:
            started = time.perf_counter()
            with torch.inference_mode(), sdpa_kernel(SDPBackend.MATH):
                single_rows = generate_records(questions, prompts, tokenizer, name, 1, predict_next,
                                               progress=lambda message: print("batch=1 " + message, flush=True))
            torch.cuda.synchronize(device)
            single_seconds = time.perf_counter() - started
            write_jsonl(directory / "batch_size_one_raw.jsonl", single_rows)
            batch_check = compare_records(rows, single_rows)
            batch_check.update(batch_one_seconds=single_seconds, batch_seconds=inference_seconds)
        del model
        torch.cuda.empty_cache()
        # 旧score_oneを直接利用し、179入力・構文・入力変更・時間制限を保つ。
        with ThreadPoolExecutor(max_workers=args.score_workers) as pool:
            scored = list(pool.map(score_one, [(row, question, cases) for row, question in zip(rows, questions)]))
            if batch_check is not None:
                single_scored = list(pool.map(score_one, [(row, question, cases) for row, question in zip(single_rows, questions)]))
                batch_check.update(compare_records(rows, single_rows, scored, single_scored))
                write_jsonl(directory / "batch_size_one_scored.jsonl", single_scored)
                write_json(directory / "batch_size_comparison.json", batch_check)
        write_jsonl(directory / "scored.jsonl", scored)
        summary = summarize(scored)
        write_json(directory / "summary.json", summary)
        provenance = {"scorer_sha256": SCORING_HASHES["scripts/model/score_composition_suite.py"],
                      "common_sha256": SCORING_HASHES["scripts/model/composition_suite_common.py"],
                      "questions_sha256": QUESTIONS_SHA256, "test_cases_sha256": TEST_CASES_SHA256,
                      "raw_inference_sha256": sha(directory / "raw_inference.jsonl"),
                      "scored_sha256": sha(directory / "scored.jsonl"), "summary_sha256": sha(directory / "summary.json"),
                      "source_hashes": {**source_hashes, **spec["source_hashes"]}}
        write_json(directory / "scoring_provenance.json", provenance)
        reference = references[name]
        reference_comparison = None
        if reference is not None:
            reference_comparison = compare_records(rows, reference["rows"], scored, reference["scored"])
            reference_comparison["source_hashes"] = reference["source_hashes"]
            write_json(directory / "reference_comparison.json", reference_comparison)
        result = {"model": name, "parameter_count": spec["parameter_count"], "epochs": spec["epochs"],
                  "suites": summary, "passed": sum(row["passed"] for row in scored), "total": len(scored),
                  "inference_seconds": inference_seconds, "questions_per_second": len(rows) / inference_seconds,
                  "peak_cuda_allocated_bytes": peak_bytes,
                  "reference_comparison": None if reference is None else {
                      key: reference_comparison[key] for key in ("different_generation_count", "pass_change_count")},
                  "reference_status": "compared" if reference else "not_supplied_or_model_absent",
                  "batch_size_one_comparison": None if batch_check is None else {
                      key: batch_check[key] for key in ("different_generation_count", "pass_change_count", "batch_one_seconds", "batch_seconds")}}
        write_json(directory / "run_metrics.json", result)
        comparisons.append(result)
        write_json(output / "comparison.json", {"status": "in_progress", "questions_sha256": QUESTIONS_SHA256, "models": comparisons})
    # 実行中に参照ファイルが変更された場合も完了扱いにしない。
    for path, expected in {**source_hashes, **{key: value for spec in specs for key, value in spec["source_hashes"].items()}}.items():
        if sha(resolve_path(path)) != expected:
            raise ValueError(f"評価中に参照ファイルが変更されました: {path}")
    write_json(output / "comparison.json", {"status": "completed", "questions_sha256": QUESTIONS_SHA256,
                                            "test_cases_sha256": TEST_CASES_SHA256, "models": comparisons,
                                            "completed_at": datetime.now(timezone.utc).isoformat()})
    print(f"評価完了: {output}", flush=True)


if __name__ == "__main__":
    main()
