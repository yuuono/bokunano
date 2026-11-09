#!/usr/bin/env python3
"""旧872問のgreedyを保持し、4 sampling候補を追加してpass@1/pass@5を測定する。"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# spawn採点子processからもimportされるため、torch/tokenizers/sampling実装はここで読まない。
from scripts.model import evaluate_boku_composition_torch as greedy  # noqa: E402
from scripts.model import report_composition872_cuda as report  # noqa: E402

TEMPERATURE = 0.8
TOP_P = 0.95
SAMPLING_SEED = 2026092607
SAMPLING_CANDIDATES = 4
CANDIDATE_COUNT = 5
SCORE_CHUNK_SIZE = 128
ARTIFACT_NAMES = ("raw_inference.jsonl", "scored.jsonl", "question_results.jsonl", "summary.json",
                  "generation_manifest.json", "scoring_progress.json")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest_json(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def atomic_json(path: Path, value) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def atomic_jsonl(path: Path, rows: list[dict]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(path)


def verify_hashes(hashes: dict[str, str]) -> None:
    for path, expected in hashes.items():
        require(greedy.sha(greedy.resolve_path(path)) == expected, f"参照ファイルhashが変わっています: {path}")


def source_hashes() -> dict[str, str]:
    paths = [Path(__file__), ROOT / "scripts/model/evaluate_boku_composition_torch.py",
             ROOT / "scripts/model/report_composition872_cuda.py",
             ROOT / "scripts/model/evaluate_boku_nano_comparison.py", ROOT / "scripts/model/evaluate_boku_nano.py",
             ROOT / "scripts/model/train_boku_nano.py", ROOT / "scripts/model/boku_nano.py",
             *[ROOT / path for path in greedy.SCORING_HASHES],
             *[greedy.DATASET / name for name in ("questions.jsonl", "test_cases.json", "protocol.json")]]
    return {greedy.display_path(path): greedy.sha(path) for path in paths}


def load_inputs(run_roots: list[Path], names: list[str] | None, expected_count: int) -> tuple[list[dict], list[dict], list[dict], dict]:
    """旧runを再集計検証し、現存する学習済みartifactのhashも再検証する。"""
    questions, cases, _ = greedy.validate_dataset()
    values = report.collect(run_roots, expected_count)
    available = {row["model"]: row for row in values["models"]}
    selected = names if names is not None else list(available)
    require(bool(selected) and len(selected) == len(set(selected)) and set(selected) <= set(available),
            "--modelsに未知・重複・空のモデル選択があります")
    model_inputs = []
    for name in selected:
        row = available[name]
        spec = row["metadata"]
        if spec.get("artifact_provenance") == "recovered_for_evaluation":
            current = greedy.validate_recovered_model(name, greedy.resolve_path(spec["recovery_manifest_path"]),
                                                       tokenizer_sha256=spec["tokenizer_sha256"])
        else:
            current = greedy.validate_model(name, greedy.resolve_path(spec["directory"]),
                                             tokenizer_sha256=spec["tokenizer_sha256"])
        require(current == spec, f"現在の重み・設定・tokenizerとgreedy評価時metadataが一致しません: {name}")
        folder = greedy.resolve_path(row["run_root"]) / name
        raw = [r for r in greedy.read_jsonl(folder / "raw_inference.jsonl") if r.get("kind") == "inference"]
        scored = greedy.read_jsonl(folder / "scored.jsonl")
        raw_map, score_map = ({r["question_id"]: r for r in records} for records in (raw, scored))
        model_inputs.append({"spec": spec, "run_root": row["run_root"],
                             "greedy_artifact_hashes": row["artifact_hashes"],
                             "greedy_raw": [raw_map[q["question_id"]] for q in questions],
                             "greedy_scored": [score_map[q["question_id"]] for q in questions]})
    return questions, cases, model_inputs, {run["run_root"]: run["artifact_hashes"] for run in values["runs"]}


def sampling_batches(prompts: list[list[int]], question_batch_size: int) -> list[list[int]]:
    """prompt長昇順、同じ長さでは元問題順。batch条件も再現条件に含める。"""
    batches = greedy.grouped_batches(prompts, question_batch_size)
    return sorted(batches, key=lambda indices: (len(prompts[indices[0]]), indices[0]))


def generate_candidates(questions: list[dict], prompts: list[list[int]], tokenizer,
                        greedy_rows: list[dict], name: str, question_batch_size: int,
                        sample_batch, progress=None) -> list[dict]:
    require(len(questions) == len(prompts) == len(greedy_rows), "問題・prompt・greedy件数が一致しません")
    by_question = {}
    for batch_id, indices in enumerate(sampling_batches(prompts, question_batch_size)):
        candidates = sample_batch([prompts[index] for index in indices])
        require(len(candidates) == len(indices) and all(len(items) == SAMPLING_CANDIDATES for items in candidates),
                "sampling候補数が4ではありません")
        for index, outputs in zip(indices, candidates, strict=True):
            q = questions[index]
            rows = [{**greedy_rows[index], "candidate_index": 1, "decoding": "greedy",
                     "candidate_origin": "existing_greedy"}]
            for candidate_index, candidate in enumerate(outputs, start=2):
                ids = candidate["generated_token_ids"]
                rows.append({"kind": "inference", "model": name, "condition": "A", "question_id": q["question_id"],
                             "suite": q["suite"], "category_id": q["category_id"], "instruction": q["instruction_ja"],
                             "prompt": greedy.PROMPT_TEMPLATE.format(instruction_ja=q["instruction_ja"]),
                             "prompt_ids": prompts[index], "candidate_index": candidate_index, "decoding": "top_p",
                             "candidate_origin": "new_sampling", "sampling_seed": SAMPLING_SEED,
                             "temperature": TEMPERATURE, "top_p": TOP_P, "sampling_batch_id": batch_id,
                             "question_batch_size": len(indices), "effective_candidate_batch_size": len(indices) * 4,
                             "output_ids": ids, "termination": candidate["termination"],
                             "raw_output": tokenizer.decode(ids, skip_special_tokens=True)})
            by_question[q["question_id"]] = rows
        if progress is not None:
            progress(f"{name}: sampling {len(by_question)}/{len(questions)} questions")
    return [row for q in questions for row in by_question[q["question_id"]]]


def validate_raw(rows: list[dict], questions: list[dict], prompts: list[list[int]], tokenizer,
                 model_input: dict) -> None:
    require(len(rows) == len(questions) * CANDIDATE_COUNT, "raw候補数が一致しません")
    name = model_input["spec"]["name"]
    for index, q in enumerate(questions):
        for offset, row in enumerate(rows[index * 5:(index + 1) * 5]):
            candidate_index = offset + 1
            require(row.get("question_id") == q["question_id"] and row.get("candidate_index") == candidate_index
                    and row.get("model") == name and row.get("condition") == "A"
                    and row.get("suite") == q["suite"] and row.get("category_id") == q["category_id"]
                    and row.get("instruction") == q["instruction_ja"]
                    and row.get("prompt") == greedy.PROMPT_TEMPLATE.format(instruction_ja=q["instruction_ja"])
                    and row.get("prompt_ids") == prompts[index], "rawの問題・候補・prompt対応が一致しません")
            require(row.get("decoding") == ("greedy" if candidate_index == 1 else "top_p"), "候補のdecodingが不正です")
            ids = row.get("output_ids")
            require(isinstance(ids, list) and all(type(v) is int and 0 <= v < 2048 for v in ids)
                    and len(ids) <= greedy.CONTEXT_LENGTH - len(prompts[index])
                    and row.get("termination") in ("eos", "max_context")
                    and tokenizer.decode(ids, skip_special_tokens=True) == row.get("raw_output"), "rawのtoken・decodeが不正です")
            if candidate_index == 1:
                original = {k: v for k, v in row.items() if k not in ("candidate_index", "decoding", "candidate_origin")}
                require(original == model_input["greedy_raw"][index], "既存greedy候補が変更されています")
            else:
                require(row.get("sampling_seed") == SAMPLING_SEED and row.get("temperature") == TEMPERATURE
                        and row.get("top_p") == TOP_P and row.get("candidate_origin") == "new_sampling",
                        "sampling条件が一致しません")


def validate_scores(scored: list[dict], raw: list[dict], question_map: dict, test_count: int) -> None:
    require(len(scored) == len(raw), "採点候補数が一致しません")
    for score, candidate in zip(scored, raw, strict=True):
        q = question_map[candidate["question_id"]]
        require(all(score.get(k) == candidate.get(k) for k in
                    ("model", "condition", "question_id", "suite", "category_id", "candidate_index", "decoding", "termination"))
                and score.get("ast_id") == q["ast_id"] and type(score.get("passed")) is bool,
                "採点の候補・問題・合否対応が一致しません")
        require(not score["passed"] or score.get("tests_passed") == test_count, "合格候補が全hidden入力を通過していません")


def question_results(questions: list[dict], scored: list[dict], greedy_scored: list[dict]) -> list[dict]:
    require(len(scored) == len(questions) * 5 and len(greedy_scored) == len(questions), "問題集計の候補件数が不正です")
    results = []
    for index, q in enumerate(questions):
        candidates = scored[index * 5:(index + 1) * 5]
        require([r.get("candidate_index") for r in candidates] == [1, 2, 3, 4, 5]
                and all(r.get("question_id") == q["question_id"] and type(r.get("passed")) is bool for r in candidates),
                "5候補の識別情報が不正です")
        first = {k: v for k, v in candidates[0].items() if k not in ("candidate_index", "decoding")}
        require(first == greedy_scored[index], "pass@1の採点が既存greedyと一致しません")
        outcomes = [{key: row.get(key) for key in
                     ("candidate_index", "decoding", "passed", "reason", "tests_passed", "termination")} for row in candidates]
        results.append({"model": candidates[0]["model"], "question_id": q["question_id"], "suite": q["suite"],
                        "category_id": q["category_id"], "ast_id": q["ast_id"],
                        "pass_at_1": outcomes[0]["passed"], "pass_at_5": any(r["passed"] for r in outcomes),
                        "passed_count": sum(r["passed"] for r in outcomes), "candidates": outcomes})
    return results


def summarize_questions(rows: list[dict], name: str) -> dict:
    def counts(items):
        total = len(items)
        one, five = sum(r["pass_at_1"] for r in items), sum(r["pass_at_5"] for r in items)
        return {"total": total, "pass_at_1_count": one, "pass_at_5_count": five,
                "pass_at_1": one / total if total else 0.0, "pass_at_5": five / total if total else 0.0,
                "sampling_rescued_count": five - one}
    return {"model": name, **counts(rows), "suites": {
        suite: counts([row for row in rows if row["suite"] == suite]) for suite in report.PRESENTATION_SUITE_ORDER}}


def score_sampling(folder: Path, raw: list[dict], questions: list[dict], cases: list[dict],
                   config_sha: str, raw_sha: str, score_one, workers: int, progress=None) -> list[dict]:
    """128候補ごとのatomic shardをcommitし、再開時はhashと候補対応を検証する。"""
    candidates = [row for row in raw if row["candidate_index"] > 1]
    question_map = {q["question_id"]: q for q in questions}
    shards_dir = folder / "scoring_batches"
    shards_dir.mkdir(exist_ok=True)
    manifest_path = folder / "scoring_progress.json"
    identity = {"format_version": 1, "config_sha256": config_sha, "raw_inference_sha256": raw_sha,
                "chunk_size": SCORE_CHUNK_SIZE, "sampling_candidate_count": len(candidates)}
    manifest = greedy.read_json(manifest_path) if manifest_path.exists() else {**identity, "status": "in_progress", "shards": []}
    require(all(manifest.get(k) == v for k, v in identity.items())
            and manifest.get("status") in ("in_progress", "completed"), "採点再開条件が一致しません")
    total_chunks = (len(candidates) + SCORE_CHUNK_SIZE - 1) // SCORE_CHUNK_SIZE
    require(len(manifest["shards"]) <= total_chunks, "採点shard数が過剰です")
    if manifest["status"] == "completed":
        require(len(manifest["shards"]) == total_chunks, "完了採点に欠落shardがあります")
    sampled_scores = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for chunk_index, start in enumerate(range(0, len(candidates), SCORE_CHUNK_SIZE)):
            batch = candidates[start:start + SCORE_CHUNK_SIZE]
            filename = f"batch_{chunk_index:04d}.json"
            path = shards_dir / filename
            keys = [[r["question_id"], r["candidate_index"]] for r in batch]
            if chunk_index < len(manifest["shards"]):
                entry = manifest["shards"][chunk_index]
                require(entry.get("file") == filename and entry.get("sha256") == greedy.sha(path),
                        f"採点shard hashが一致しません: {path}")
                shard = greedy.read_json(path)
                require(shard.get("config_sha256") == config_sha and shard.get("raw_inference_sha256") == raw_sha
                        and shard.get("candidate_keys") == keys, f"採点shard条件が一致しません: {path}")
                scores = shard["scored"]
            else:
                scores = list(pool.map(score_one, [(row, question_map[row["question_id"]], cases) for row in batch]))
                scores = [{**score, "candidate_index": row["candidate_index"], "decoding": "top_p"}
                          for score, row in zip(scores, batch, strict=True)]
                validate_scores(scores, batch, question_map, len(cases))
                shard = {"config_sha256": config_sha, "raw_inference_sha256": raw_sha,
                         "candidate_keys": keys, "scored": scores}
                atomic_json(path, shard)
                manifest["shards"].append({"file": filename, "sha256": greedy.sha(path), "count": len(scores)})
                atomic_json(manifest_path, manifest)
            validate_scores(scores, batch, question_map, len(cases))
            sampled_scores.extend(scores)
            if progress is not None:
                progress(f"{folder.name}: scored {len(sampled_scores)}/{len(candidates)} sampling candidates")
    manifest["status"] = "completed"
    atomic_json(manifest_path, manifest)
    return sampled_scores


def complete_scores(model_input: dict, raw: list[dict], sampled: list[dict]) -> list[dict]:
    mapping = {(r["question_id"], r["candidate_index"]): r for r in sampled}
    require(len(mapping) == len(sampled), "sampling採点に重複があります")
    original = {r["question_id"]: r for r in model_input["greedy_scored"]}
    return [{**original[r["question_id"]], "candidate_index": 1, "decoding": "greedy"}
            if r["candidate_index"] == 1 else mapping[(r["question_id"], r["candidate_index"])] for r in raw]


def model_configuration(configuration: dict, model_input: dict) -> dict:
    spec = model_input["spec"]
    return {**{k: v for k, v in configuration.items() if k != "models"}, "model": spec["name"],
            "model_metadata": spec, "weight_sha256": spec["weight_sha256"], "tokenizer_sha256": spec["tokenizer_sha256"],
            "greedy_run_root": model_input["run_root"], "greedy_artifact_hashes": model_input["greedy_artifact_hashes"]}


def validate_completed(folder: Path, config: dict, model_input: dict, questions: list[dict],
                       prompts: list[list[int]], tokenizer, cases: list[dict]) -> dict:
    provenance = greedy.read_json(folder / "provenance.json")
    require(provenance.get("status") == "completed" and greedy.read_json(folder / "config.json") == config
            and provenance.get("config_sha256") == greedy.sha(folder / "config.json")
            and provenance.get("questions_sha256") == greedy.QUESTIONS_SHA256
            and provenance.get("test_cases_sha256") == greedy.TEST_CASES_SHA256
            and provenance.get("greedy_artifact_hashes") == model_input["greedy_artifact_hashes"]
            and provenance.get("source_hashes") == {**config["source_hashes"], **model_input["spec"]["source_hashes"]},
            f"完了モデルの再開条件が一致しません: {folder}")
    require(set(provenance.get("artifact_hashes", {})) == set(ARTIFACT_NAMES), "完了成果物一覧が不正です")
    for name, expected in provenance["artifact_hashes"].items():
        require(greedy.sha(folder / name) == expected, f"完了成果物hash不一致: {folder / name}")
    raw, scored = (greedy.read_jsonl(folder / name) for name in ("raw_inference.jsonl", "scored.jsonl"))
    validate_raw(raw, questions, prompts, tokenizer, model_input)
    validate_scores(scored, raw, {q["question_id"]: q for q in questions}, len(cases))
    results = question_results(questions, scored, model_input["greedy_scored"])
    summary = summarize_questions(results, model_input["spec"]["name"])
    require(greedy.read_jsonl(folder / "question_results.jsonl") == results
            and greedy.read_json(folder / "summary.json") == summary, "完了結果の再集計が一致しません")
    return summary


def generate_model_raw(model_input: dict, questions: list[dict], prompts: list[list[int]], tokenizer,
                       question_batch_size: int, device, torch) -> tuple[list[dict], dict]:
    # sampling既存関数と重い依存は親processのこの関数内だけでimportする。
    from safetensors.torch import load_file
    from torch.nn.attention import SDPBackend, sdpa_kernel
    from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM
    from scripts.model.evaluate_boku_nano_comparison import sample_generate_equal_length
    spec = model_input["spec"]
    model = BokuNanoForCausalLM(BokuNanoConfig.from_dict(spec["model_config"]))
    model.load_state_dict(load_file(str(greedy.resolve_path(spec["directory"]) / "model.safetensors"), device="cpu"), strict=True)
    require(model.parameter_count() == spec["parameter_count"], f"parameter数不一致: {spec['name']}")
    model.to(device=device, dtype=torch.float32).eval()
    generator = torch.Generator(device=device)
    generator.manual_seed(SAMPLING_SEED)

    def sample_batch(prompt_ids):
        return sample_generate_equal_length(model, prompt_ids, SAMPLING_CANDIDATES, 2, 0,
                                             greedy.CONTEXT_LENGTH, greedy.CONTEXT_LENGTH, TEMPERATURE, TOP_P,
                                             device, generator)

    torch.cuda.reset_peak_memory_stats(device)
    torch.cuda.synchronize(device)
    started = time.perf_counter()
    with torch.inference_mode(), sdpa_kernel(SDPBackend.MATH):
        rows = generate_candidates(questions, prompts, tokenizer, model_input["greedy_raw"], spec["name"],
                                   question_batch_size, sample_batch, progress=lambda message: print(message, flush=True))
    torch.cuda.synchronize(device)
    metrics = {"sampling_seconds": time.perf_counter() - started,
               "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
               "sampling_candidates": len(questions) * 4,
               "generator_state_sha256_after_sampling": hashlib.sha256(bytes(generator.get_state().cpu().tolist())).hexdigest()}
    del model, generator
    torch.cuda.empty_cache()
    return rows, metrics


def run_model(output: Path, configuration: dict, model_input: dict, questions: list[dict], cases: list[dict],
              tokenizer, prompts: list[list[int]], device, torch, score_one, resume: bool) -> dict:
    spec = model_input["spec"]
    folder = output / spec["name"]
    config = model_configuration(configuration, model_input)
    if folder.exists():
        require(resume and greedy.read_json(folder / "config.json") == config, f"モデル再開設定が一致しません: {folder}")
    else:
        folder.mkdir()
        atomic_json(folder / "config.json", config)
    if (folder / "provenance.json").exists():
        return validate_completed(folder, config, model_input, questions, prompts, tokenizer, cases)
    config_sha = greedy.sha(folder / "config.json")
    generation_path = folder / "generation_manifest.json"
    if generation_path.exists():
        generation = greedy.read_json(generation_path)
        require(generation.get("status") == "completed" and generation.get("config_sha256") == config_sha
                and generation.get("raw_inference_sha256") == greedy.sha(folder / "raw_inference.jsonl")
                and generation.get("candidate_count") == len(questions) * 5,
                f"保存済み生成の再開条件が一致しません: {folder}")
        raw = greedy.read_jsonl(folder / "raw_inference.jsonl")
    else:
        require(not (folder / "scoring_progress.json").exists(), "採点が存在するのに生成manifestがありません")
        raw, metrics = generate_model_raw(model_input, questions, prompts, tokenizer,
                                          configuration["question_batch_size"], device, torch)
        validate_raw(raw, questions, prompts, tokenizer, model_input)
        atomic_jsonl(folder / "raw_inference.jsonl", raw)
        generation = {"status": "completed", "config_sha256": config_sha,
                      "raw_inference_sha256": greedy.sha(folder / "raw_inference.jsonl"),
                      "candidate_count": len(raw), **metrics}
        atomic_json(generation_path, generation)
    validate_raw(raw, questions, prompts, tokenizer, model_input)
    sampled = score_sampling(folder, raw, questions, cases, config_sha, generation["raw_inference_sha256"],
                              score_one, configuration["score_workers"], progress=lambda message: print(message, flush=True))
    scored = complete_scores(model_input, raw, sampled)
    validate_scores(scored, raw, {q["question_id"]: q for q in questions}, len(cases))
    results = question_results(questions, scored, model_input["greedy_scored"])
    summary = summarize_questions(results, spec["name"])
    atomic_jsonl(folder / "scored.jsonl", scored)
    atomic_jsonl(folder / "question_results.jsonl", results)
    atomic_json(folder / "summary.json", summary)
    sources = {**configuration["source_hashes"], **spec["source_hashes"]}
    verify_hashes({**sources, **model_input["greedy_artifact_hashes"]})
    provenance = {"status": "completed", "questions_sha256": greedy.QUESTIONS_SHA256,
                  "test_cases_sha256": greedy.TEST_CASES_SHA256,
                  "scorer_sha256": greedy.SCORING_HASHES["scripts/model/score_composition_suite.py"],
                  "common_sha256": greedy.SCORING_HASHES["scripts/model/composition_suite_common.py"],
                  "config_sha256": config_sha,
                  "artifact_hashes": {name: greedy.sha(folder / name) for name in ARTIFACT_NAMES},
                  "source_hashes": sources, "greedy_artifact_hashes": model_input["greedy_artifact_hashes"]}
    atomic_json(folder / "provenance.json", provenance)
    return validate_completed(folder, config, model_input, questions, prompts, tokenizer, cases)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--greedy-run-roots", nargs="+", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--models", nargs="+", help="省略時は全固有モデル")
    parser.add_argument("--expected-model-count", type=int, default=18, help="入力greedyの固有モデル数。既定18")
    parser.add_argument("--question-batch-size", type=int, default=8, help="samplingは指定問数×4候補のbatch")
    parser.add_argument("--score-workers", type=int, default=4)
    parser.add_argument("--resume", action="store_true", help="設定・hash一致を検証し、完了モデル/生成/採点shardを再利用")
    parser.add_argument("--validate-only", action="store_true", help="入力・hash・prompt検査のみ。CUDA呼出・出力作成なし")
    args = parser.parse_args(argv)
    if min(args.expected_model_count, args.question_batch_size, args.score_workers) < 1:
        parser.error("件数・batch・worker数は正整数にしてください")
    return args


def main(argv=None) -> None:
    args = parse_args(argv)
    require(not args.output_root.is_symlink(), "出力先symlinkは使用できません")
    output = args.output_root.resolve()
    if output.exists():
        require(args.resume and output.is_dir(), "既存出力には--resumeが必要です。上書きはしません")
    else:
        require(not args.resume, "--resumeには既存出力が必要です")
    run_roots = [greedy.resolve_path(p) for p in args.greedy_run_roots]
    require(output not in run_roots and all(output not in root.parents and root not in output.parents for root in run_roots),
            "出力先を元greedy runの内部・親ディレクトリには置けません")
    questions, cases, model_inputs, greedy_run_hashes = load_inputs(run_roots, args.models, args.expected_model_count)
    from tokenizers import Tokenizer
    prepared = {}
    for item in model_inputs:
        spec = item["spec"]
        tokenizer = Tokenizer.from_file(str(greedy.resolve_path(spec["tokenizer_path"])))
        prompts = greedy.encode_prompts(questions, tokenizer)
        require([row["prompt_ids"] for row in item["greedy_raw"]] == prompts, f"greedyとsamplingのpromptが一致しません: {spec['name']}")
        prepared[spec["name"]] = (tokenizer, prompts)
    configuration = {"format_version": 1, "questions_sha256": greedy.QUESTIONS_SHA256,
                     "test_cases_sha256": greedy.TEST_CASES_SHA256, "protocol_sha256": greedy.PROTOCOL_SHA256,
                     "question_count": len(questions), "test_case_count": len(cases),
                     "candidate_count": CANDIDATE_COUNT, "sampling_candidates": SAMPLING_CANDIDATES,
                     "pass_at_1_definition": "existing_greedy", "pass_at_5_definition": "any_of_greedy_1_and_top_p_4",
                     "temperature": TEMPERATURE, "top_p": TOP_P, "sampling_seed": SAMPLING_SEED,
                     "seed_policy": "reset_same_seed_for_each_model", "candidate_order": "greedy_then_four_sampling_draws_no_deduplication",
                     "sampling_order": "prompt_length_ascending_then_question_source_order",
                     "question_batch_size": args.question_batch_size, "effective_candidate_batch_size": args.question_batch_size * 4,
                     "score_workers": args.score_workers, "score_chunk_size": SCORE_CHUNK_SIZE,
                     "context_length": greedy.CONTEXT_LENGTH, "max_new_tokens": greedy.CONTEXT_LENGTH,
                     "prompt_template": greedy.PROMPT_TEMPLATE, "condition": "A", "history": False, "repair": False,
                     "decode_skip_special_tokens": True, "dtype": "float32", "tf32": False, "autocast": False,
                     "sdpa_backend": "math", "kv_cache": False,
                     "greedy_run_roots": [greedy.display_path(p) for p in run_roots], "greedy_run_hashes": greedy_run_hashes,
                     "models": [item["spec"] for item in model_inputs], "source_hashes": source_hashes()}
    if output.exists():
        require(greedy.read_json(output / "config.json") == configuration, "root再開設定・入力・ソースhashが一致しません")
    if args.validate_only:
        print(json.dumps({"status": "validated_without_inference", **configuration}, ensure_ascii=False, indent=2))
        return
    import torch
    from scripts.model.score_composition_suite import score_one
    require(torch.cuda.is_available() and torch.version.cuda is not None and torch.version.hip is None,
            "NVIDIA CUDA版PyTorchとGPUが必要です")
    torch.set_float32_matmul_precision("highest")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    device = torch.device("cuda:0")
    runtime = {"python": platform.python_version(), "platform": platform.platform(), "torch": torch.__version__,
               "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(device), "device": str(device)}
    if output.exists():
        old_runtime = greedy.read_json(output / "environment.json")
        require(all(old_runtime.get(k) == v for k, v in runtime.items()), "再開環境のPython/PyTorch/CUDA/GPUが一致しません")
    else:
        output.mkdir(parents=True)
        atomic_json(output / "config.json", configuration)
        atomic_json(output / "environment.json", {**runtime, "started_at": datetime.now(timezone.utc).isoformat()})
    completed = []
    comparison_base = {"questions_sha256": greedy.QUESTIONS_SHA256, "test_cases_sha256": greedy.TEST_CASES_SHA256,
                       "config_sha256": greedy.sha(output / "config.json")}
    for item in model_inputs:
        tokenizer, prompts = prepared[item["spec"]["name"]]
        summary = run_model(output, configuration, item, questions, cases, tokenizer, prompts,
                            device, torch, score_one, args.resume)
        completed.append(summary)
        atomic_json(output / "comparison.json", {**comparison_base, "status": "in_progress", "models": completed})
        print(f"{summary['model']}: pass@1={summary['pass_at_1_count']}/{summary['total']} "
              f"pass@5={summary['pass_at_5_count']}/{summary['total']}", flush=True)
    verify_hashes(configuration["source_hashes"])
    for hashes in greedy_run_hashes.values():
        verify_hashes(hashes)
    atomic_json(output / "comparison.json", {**comparison_base, "status": "completed", "models": completed,
                                              "completed_at": datetime.now(timezone.utc).isoformat()})
    print(f"pass@1/pass@5評価完了: {output}", flush=True)


if __name__ == "__main__":
    main()
