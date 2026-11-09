#!/usr/bin/env python3
"""固定872問の代表81 prefixでCPU/ONNX/CUDAのlogitsを比較する補助診断。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.model import evaluate_boku_composition_torch as evaluation  # noqa: E402

DEFAULT_RUN = ROOT / "data/evaluations/composition872_cuda_20261025_baselines"
ORT_VERSION = "1.30.0"
BACKENDS = ("pytorch_cpu_math", "onnxruntime_cpu", "pytorch_cuda_math")
PAIRS = ((BACKENDS[0], BACKENDS[1]), (BACKENDS[0], BACKENDS[2]), (BACKENDS[1], BACKENDS[2]))


def sample_prefixes(questions: list[dict], rows: list[dict]) -> list[dict]:
    """問題ファイル順の各suite先頭を固定し、生成開始/中間/EOS直前を選ぶ。"""
    first = {}
    for question in questions:
        first.setdefault(question["suite"], question)
    by_id = {row["question_id"]: row for row in rows}
    samples = []
    for suite in evaluation.SUITE_COUNTS:
        question = first[suite]
        row = by_id[question["question_id"]]
        tokens = row["output_ids"]
        if row["termination"] != "eos" or len(tokens) < 2:
            raise ValueError("固定代表問題に3個の異なるEOS終了prefixを作れません")
        for position, offset in (("generation_start", 0), ("generation_middle", len(tokens) // 2),
                                 ("before_eos", len(tokens))):
            prefix = row["prompt_ids"] + tokens[:offset]
            if not 0 < len(prefix) < evaluation.CONTEXT_LENGTH:
                raise ValueError("代表prefixの長さが生成条件と一致しません")
            samples.append({"question_id": question["question_id"], "suite": suite,
                            "position": position, "generated_token_offset": offset,
                            "prompt_token_count": len(row["prompt_ids"]),
                            "prefix_token_count": len(prefix), "prefix_ids": prefix,
                            "stored_next_token_id": tokens[offset] if offset < len(tokens) else evaluation.EOS_ID})
    return samples


def prepare(run_root: Path, reference_root: Path, model_names: list[str]) -> tuple[list[dict], dict]:
    """GPU/torch/ONNXを呼ばず、学習済み重み・保存生成・元ONNXの由来を検証する。"""
    from tokenizers import Tokenizer

    questions, _, _ = evaluation.validate_dataset()
    completed = evaluation.read_json(run_root / "comparison.json")
    if (completed.get("status") != "completed"
            or completed.get("questions_sha256") != evaluation.QUESTIONS_SHA256
            or completed.get("test_cases_sha256") != evaluation.TEST_CASES_SHA256):
        raise ValueError("固定872問のCUDA評価が完了したディレクトリを指定してください")
    source_paths = [Path(__file__), Path(evaluation.__file__), ROOT / "scripts/model/boku_nano.py",
                    run_root / "comparison.json", run_root / "environment.json",
                    *[evaluation.DATASET / filename for filename in
                      ("questions.jsonl", "test_cases.json", "protocol.json")]]
    source_hashes = {evaluation.display_path(path): evaluation.sha(path) for path in source_paths}
    plans = []
    for name in model_names:
        spec = evaluation.validate_model(name, evaluation.resolve_path(evaluation.DEFAULT_MODELS[name]))
        tokenizer = Tokenizer.from_file(str(evaluation.resolve_path(spec["tokenizer_path"])))
        prompts = evaluation.encode_prompts(questions, tokenizer)
        current = evaluation.load_reference(run_root, spec, questions, prompts)
        previous = evaluation.load_reference(reference_root, spec, questions, prompts)
        if current is None or previous is None:
            raise ValueError(f"新旧の保存済み生成が必要です: {name}")
        comparison = evaluation.compare_records(current["rows"], previous["rows"],
                                                current["scored"], previous["scored"])
        if comparison["different_generation_count"] or comparison["pass_change_count"]:
            raise ValueError(f"新旧全872問の生成・採点が一致しません: {name}")
        config = evaluation.read_json(run_root / name / "config.json")
        if (config.get("dtype") != "float32" or config.get("tf32") is not False
                or config.get("autocast") is not False or config.get("sdpa_backend") != "math"
                or config.get("kv_cache") is not False):
            raise ValueError(f"保存CUDAの数値条件が診断前提と違います: {name}")
        single_path = run_root / name / "batch_size_one_raw.jsonl"
        single = evaluation.read_jsonl(single_path)
        evaluation.validate_record_identity(single, questions, name)
        if evaluation.compare_records(current["rows"], single)["different_generation_count"]:
            raise ValueError(f"保存CUDA batch1/batch32の生成が一致しません: {name}")
        old_config = evaluation.read_json(reference_root / name / "config.json")
        catalog = old_config["catalog_entry"]
        onnx_path = evaluation.resolve_path(catalog["model_path"])
        onnx_sha = evaluation.sha(onnx_path)
        export_path = evaluation.resolve_path(spec["directory"]) / "onnx_manifest.json"
        export = evaluation.read_json(export_path)
        if (onnx_sha != old_config["weight_sha256"] or onnx_sha != catalog["weight_sha256"]
                or onnx_sha != export["onnx"]["sha256"]
                or export["model"]["sha256"] != spec["weight_sha256"]
                or catalog["source_weight_sha256"] != spec["weight_sha256"]
                or catalog["model_config"] != spec["model_config"]
                or old_config.get("onnxruntime") != ORT_VERSION):
            raise ValueError(f"旧ONNXの実体・元重み・設定・runtime由来が一致しません: {name}")
        source_hashes.update(spec["source_hashes"])
        source_hashes.update(current["source_hashes"])
        source_hashes.update(previous["source_hashes"])
        for path in (single_path, onnx_path, export_path):
            source_hashes[evaluation.display_path(path)] = evaluation.sha(path)
        plans.append({"model": name, "spec": spec, "onnx_path": evaluation.display_path(onnx_path),
                      "onnx_sha256": onnx_sha, "verified_saved_generation_count": len(current["rows"]),
                      "samples": sample_prefixes(questions, current["rows"])})
    return plans, source_hashes


def logit_metrics(vectors: dict, expected: int) -> dict:
    """有限なfloat32語彙logitsの値・順位・差を記録し、差を原因と決めつけない。"""
    import numpy as np

    backends = {}
    for name, logits in vectors.items():
        if logits.shape != (2048,) or logits.dtype != np.float32 or not np.isfinite(logits).all():
            raise ValueError(f"診断logitsが有限なfloat32/2048語彙ではありません: {name}")
        ranked = np.argsort(-logits, kind="stable")[:5]
        top = int(np.argmax(logits))
        backends[name] = {"top1_token_id": top, "matches_stored_next_token": top == expected,
                          "top1_top2_margin": float(logits[ranked[0]]) - float(logits[ranked[1]]),
                          "stored_next_token_logit": float(logits[expected]),
                          "top5": [{"token_id": int(i), "logit": float(logits[i])} for i in ranked],
                          "float32_logits_sha256": hashlib.sha256(logits.tobytes()).hexdigest()}
    pairs = {}
    for left, right in PAIRS:
        difference = vectors[left].astype(np.float64) - vectors[right].astype(np.float64)
        pairs[f"{left}__vs__{right}"] = {
            "max_abs_diff": float(np.abs(difference).max()),
            "mean_abs_diff": float(np.abs(difference).mean()),
            "rms_diff": float(np.sqrt(np.square(difference).mean())),
            "top1_equal": backends[left]["top1_token_id"] == backends[right]["top1_token_id"],
            "bitwise_equal": vectors[left].tobytes() == vectors[right].tobytes(),
        }
    return {"backends": backends, "pairwise": pairs}


def summarize(rows: list[dict]) -> dict:
    return {"prefix_count": len(rows),
            "backends": {name: {
                "matches_stored_next_token_count": sum(row["backends"][name]["matches_stored_next_token"] for row in rows),
                "min_top1_top2_margin": min(row["backends"][name]["top1_top2_margin"] for row in rows),
            } for name in BACKENDS},
            "pairwise": {f"{left}__vs__{right}": {
                "max_abs_diff": max(row["pairwise"][f"{left}__vs__{right}"]["max_abs_diff"] for row in rows),
                "top1_equal_count": sum(row["pairwise"][f"{left}__vs__{right}"]["top1_equal"] for row in rows),
                "bitwise_equal_count": sum(row["pairwise"][f"{left}__vs__{right}"]["bitwise_equal"] for row in rows),
            } for left, right in PAIRS}}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--reference-root", type=Path, default=evaluation.DATASET / "runs")
    parser.add_argument("--models", nargs="+", choices=evaluation.DEFAULT_SELECTION,
                        default=evaluation.DEFAULT_SELECTION)
    parser.add_argument("--output", type=Path, required=True, help="新規JSON。既存ファイルは拒否")
    parser.add_argument("--validate-only", action="store_true", help="hashとprefixを検証。推論・出力作成なし")
    args = parser.parse_args(argv)
    if len(set(args.models)) != len(args.models):
        parser.error("モデル名の重複は指定できません")
    evaluation.require_new_output(args.output)
    output = args.output.resolve()
    evaluation.require_new_output(output)
    plans, source_hashes = prepare(args.run_root.resolve(), args.reference_root.resolve(), args.models)
    configuration = {
        "questions_sha256": evaluation.QUESTIONS_SHA256, "tokenizer_sha256": evaluation.TOKENIZER_SHA256,
        "selection": "first_question_in_file_order_per_suite; generated offsets 0, floor(n/2), n",
        "prefix_origin": "saved CUDA generation, verified equal to old ONNX and saved CUDA batch1 on all 872 questions",
        "scope": "Representative prefix diagnostic only; not all 872 questions or all decoding positions. No rescoring or training.",
        "run_root": evaluation.display_path(args.run_root), "reference_root": evaluation.display_path(args.reference_root),
        "models": args.models, "prefix_count": sum(len(plan["samples"]) for plan in plans),
        "batch_size": 1, "dtype": "float32", "tf32": False, "autocast": False, "sdpa_backend": "math",
        "onnxruntime_version_required": ORT_VERSION, "onnx_provider": "CPUExecutionProvider",
        "onnx_graph_optimizations": "ORT_ENABLE_ALL (same as old runner default)",
        "cpu_intra_threads": 4, "cpu_inter_threads": 1,
    }
    if args.validate_only:
        print(json.dumps({"status": "validated_without_inference", **configuration,
                          "samples": {plan["model"]: plan["samples"] for plan in plans}}, ensure_ascii=False, indent=2))
        return

    import numpy as np
    import onnxruntime as ort
    import torch
    from safetensors.torch import load_file
    from torch.nn.attention import SDPBackend, sdpa_kernel
    from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM

    if ort.__version__ != ORT_VERSION:
        raise RuntimeError(f"旧評価と同じonnxruntime=={ORT_VERSION}が必要です。実際: {ort.__version__}")
    if not torch.cuda.is_available() or torch.version.cuda is None or torch.version.hip is not None:
        raise RuntimeError("NVIDIA CUDAを利用できる環境で実行してください")
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.set_float32_matmul_precision("highest")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    environment = {"python": platform.python_version(), "platform": platform.platform(),
                   "torch": torch.__version__, "numpy": np.__version__, "onnxruntime": ort.__version__,
                   "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0),
                   "started_at": datetime.now(timezone.utc).isoformat()}
    results = []
    for plan in plans:
        spec = plan["spec"]
        weights = load_file(str(evaluation.resolve_path(spec["directory"]) / "model.safetensors"), device="cpu")
        cpu = BokuNanoForCausalLM(BokuNanoConfig.from_dict(spec["model_config"]))
        cpu.load_state_dict(weights, strict=True)
        cpu.to(device="cpu", dtype=torch.float32).eval()
        gpu = BokuNanoForCausalLM(BokuNanoConfig.from_dict(spec["model_config"]))
        gpu.load_state_dict(weights, strict=True)
        gpu.to(device="cuda:0", dtype=torch.float32).eval()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session = ort.InferenceSession(str(evaluation.resolve_path(plan["onnx_path"])), sess_options=options,
                                       providers=["CPUExecutionProvider"])
        rows = []
        with torch.inference_mode(), sdpa_kernel(SDPBackend.MATH):
            for sample in plan["samples"]:
                values = np.asarray([sample["prefix_ids"]], dtype=np.int64)
                cpu_logits = cpu(torch.from_numpy(values)).logits[0, -1].numpy().copy()
                onnx_logits = session.run(["logits"], {"input_ids": values})[0][0].copy()
                cuda_logits = gpu(torch.from_numpy(values).to("cuda:0")).logits[0, -1].cpu().numpy().copy()
                vectors = dict(zip(BACKENDS, (cpu_logits, onnx_logits, cuda_logits)))
                rows.append({**sample, **logit_metrics(vectors, sample["stored_next_token_id"])})
        results.append({"model": plan["model"], "weight_sha256": spec["weight_sha256"],
                        "onnx_sha256": plan["onnx_sha256"],
                        "verified_saved_generation_count": plan["verified_saved_generation_count"],
                        "summary": summarize(rows), "prefixes": rows})
        del gpu, cpu, session, weights
        torch.cuda.empty_cache()
        print(f"{plan['model']}: {len(rows)} representative prefixes compared", flush=True)
    for path, expected in source_hashes.items():
        if evaluation.sha(evaluation.resolve_path(path)) != expected:
            raise ValueError(f"診断中に参照ファイルが変更されました: {path}")
    payload = {"status": "completed", "configuration": configuration, "environment": environment,
               "summary": summarize([row for model in results for row in model["prefixes"]]),
               "models": results, "source_hashes": source_hashes,
               "completed_at": datetime.now(timezone.utc).isoformat()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(f"診断保存: {output}", flush=True)


if __name__ == "__main__":
    main()
