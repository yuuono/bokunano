"""Boku Nanoの追加指標と学習前ランダムモデル比較を測定する。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import heapq
import json
from pathlib import Path
import platform
import sys
import time
from typing import Any, Mapping, Sequence

import torch
from tokenizers import Tokenizer
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM  # noqa: E402
from scripts.model.evaluate_boku_nano import (  # noqa: E402
    SUPPORTED_SUITES,
    SuiteVerifier,
    cases_for_record,
    configured_path,
    encode_prompt,
    file_sha256,
    greedy_generate_equal_length,
    iter_suite_records,
    load_config as load_evaluation_config,
    load_model,
    validate_configuration,
    write_json_atomic,
)
from scripts.model.train_boku_nano import (  # noqa: E402
    build_training_dataset,
    evaluate_validation_loss,
    load_config as load_training_config,
    seed_everything,
    validate_source_archive,
    validate_tokenizer,
)


COMPARISON_VERSION = "1"


def parse_args() -> argparse.Namespace:
    """比較評価のCLI引数を読む。"""

    parser = argparse.ArgumentParser(
        description="学習済みモデルと学習前ランダムモデルを固定部分集合で比較します。"
    )
    parser.add_argument("--config", type=Path, required=True, help="比較評価設定YAML")
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="設定と比較集合だけを検証し、推論せず終了します。",
    )
    parser.add_argument(
        "--max-records-per-suite",
        type=int,
        help="smoke test時だけ各テストの比較件数を上書きします。",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        help="設定内の出力先を実行時だけ差し替えます。",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="既存の比較結果がある場合に置き換えます。",
    )
    return parser.parse_args()


def load_comparison_config(path: Path) -> dict[str, Any]:
    """比較設定の必須構造と値を検査する。"""

    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("version") != 1:
        raise ValueError("比較評価設定versionは1にしてください")
    for section in ("comparison", "output"):
        if not isinstance(config.get(section), dict):
            raise ValueError(f"比較評価設定の{section}がobjectではありません")
    comparison = config["comparison"]
    for key in (
        "selection_seed",
        "records_per_suite",
        "candidate_count",
        "sampling_seed",
        "random_model_seed",
    ):
        if int(comparison.get(key, 0)) <= 0:
            raise ValueError(f"comparison.{key}は正の整数にしてください")
    if int(comparison["candidate_count"]) < 2:
        raise ValueError("candidate_countは2以上にしてください")
    if float(comparison.get("temperature", 0.0)) <= 0.0:
        raise ValueError("temperatureは正の値にしてください")
    top_p = float(comparison.get("top_p", 0.0))
    if not 0.0 < top_p <= 1.0:
        raise ValueError("top_pは0より大きく1以下にしてください")
    return config


def selection_score(record_id: str, seed: int) -> str:
    """record IDと固定seedから部分集合選択用hashを返す。"""

    payload = f"{seed}\0{record_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def select_records(
    archive_path: Path,
    suite_name: str,
    suite_config: Mapping[str, Any],
    count: int,
    seed: int,
) -> list[dict[str, Any]]:
    """集合全体からhash順で固定件数を選ぶ。"""

    expected = int(suite_config["expected_record_count"])
    selected_count = min(count, expected)
    selected = heapq.nsmallest(
        selected_count,
        iter_suite_records(archive_path, suite_name, suite_config),
        key=lambda record: selection_score(record["record_id"], seed),
    )
    selected.sort(key=lambda record: record["source_index"])
    if len(selected) != selected_count:
        raise ValueError(f"比較集合件数が不足しています: {suite_name}")
    return selected


def validate_hidden_case_counts(
    evaluation_config: Mapping[str, Any],
    selected: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, dict[str, int]]:
    """各問題が20件以上の分離済みhidden入力を持つことを確認する。"""

    result: dict[str, dict[str, int]] = {}
    for suite_name, records in selected.items():
        suite_config = evaluation_config["evaluation_data"]["suites"][suite_name]
        input_manifest = json.loads(
            configured_path(suite_config["inputs"]).read_text(encoding="utf-8")
        )
        counts = [
            len(cases_for_record(input_manifest, suite_name, record["spec_id"]))
            for record in records
        ]
        minimum = min(counts)
        maximum = max(counts)
        if minimum < 20:
            raise ValueError(f"hidden testが20件未満です: {suite_name}: {minimum}")
        result[suite_name] = {
            "maximum_cases_per_record": maximum,
            "minimum_cases_per_record": minimum,
            "record_count": len(records),
        }
    return result


def sample_generate_equal_length(
    model: BokuNanoForCausalLM,
    prompt_token_ids: Sequence[Sequence[int]],
    candidates_per_prompt: int,
    eos_token_id: int,
    pad_token_id: int,
    max_new_tokens: int,
    context_length: int,
    temperature: float,
    top_p: float,
    device: torch.device,
    generator: torch.Generator,
) -> list[list[dict[str, Any]]]:
    """同長promptごとにtop-p samplingで複数候補を生成する。"""

    if not prompt_token_ids:
        raise ValueError("sampling生成batchが空です")
    if candidates_per_prompt <= 0:
        raise ValueError("candidates_per_promptは正の整数にしてください")
    prompt_length = len(prompt_token_ids[0])
    if any(len(values) != prompt_length for values in prompt_token_ids):
        raise ValueError("sampling生成batchのprompt長が一致していません")
    expanded = [
        list(prompt)
        for prompt in prompt_token_ids
        for _ in range(candidates_per_prompt)
    ]
    generation_limit = min(max_new_tokens, context_length - prompt_length)
    input_ids = torch.tensor(expanded, dtype=torch.long, device=device)
    generated: list[list[int]] = [[] for _ in expanded]
    finished = [False for _ in expanded]
    limit_reason = (
        "max_context"
        if context_length - prompt_length <= max_new_tokens
        else "max_new_tokens"
    )
    termination = [limit_reason for _ in expanded]
    with torch.inference_mode():
        for _ in range(generation_limit):
            logits = model(input_ids).logits[:, -1, :] / temperature
            sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
            sorted_probabilities = torch.softmax(sorted_logits, dim=-1)
            cumulative = torch.cumsum(sorted_probabilities, dim=-1)
            remove = cumulative - sorted_probabilities >= top_p
            sorted_probabilities = sorted_probabilities.masked_fill(remove, 0.0)
            sorted_probabilities /= sorted_probabilities.sum(dim=-1, keepdim=True)
            sampled_positions = torch.multinomial(
                sorted_probabilities,
                num_samples=1,
                generator=generator,
            )
            next_ids = sorted_indices.gather(1, sampled_positions).squeeze(1)
            next_values = next_ids.tolist()
            append_values: list[int] = []
            for index, token_id in enumerate(next_values):
                if finished[index]:
                    append_values.append(pad_token_id)
                    continue
                if token_id == eos_token_id:
                    finished[index] = True
                    termination[index] = "eos"
                    append_values.append(pad_token_id)
                    continue
                generated[index].append(int(token_id))
                append_values.append(int(token_id))
            if all(finished):
                break
            appended = torch.tensor(append_values, dtype=torch.long, device=device)
            input_ids = torch.cat((input_ids, appended[:, None]), dim=1)
    grouped: list[list[dict[str, Any]]] = []
    for prompt_index in range(len(prompt_token_ids)):
        start = prompt_index * candidates_per_prompt
        grouped.append(
            [
                {
                    "generated_token_ids": generated[index],
                    "termination": termination[index],
                }
                for index in range(start, start + candidates_per_prompt)
            ]
        )
    return grouped


def synchronize(device: torch.device) -> None:
    """CUDA計時時だけ未完了kernelを同期する。"""

    if device.type == "cuda":
        torch.cuda.synchronize(device)


def is_executable(verification: Mapping[str, Any]) -> bool:
    """静的検査後に例外・timeoutなく全hidden入力を実行できたか返す。"""

    if not bool(verification["signature_ok"]) or bool(verification["timeout"]):
        return False
    error = verification.get("error")
    return error is None or str(error).startswith("不一致:")


def run_suite(
    suite_name: str,
    records: Sequence[dict[str, Any]],
    evaluation_config: Mapping[str, Any],
    model: BokuNanoForCausalLM,
    tokenizer: Tokenizer,
    special_ids: Mapping[str, int],
    device: torch.device,
    candidate_count: int,
    sampling_seed: int,
    temperature: float,
    top_p: float,
    output_path: Path,
) -> tuple[dict[str, Any], dict[str, float]]:
    """一テストのpass@1とpass@5を生成・実行評価する。"""

    suite_config = evaluation_config["evaluation_data"]["suites"][suite_name]
    input_manifest = json.loads(
        configured_path(suite_config["inputs"]).read_text(encoding="utf-8")
    )
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        prompt_ids = encode_prompt(
            tokenizer,
            record["instruction_ja"],
            special_ids,
            model.config.context_length,
        )
        grouped[len(prompt_ids)].append({**record, "prompt_token_ids": prompt_ids})
    generated_by_index: dict[int, dict[str, Any]] = {}
    batch_size = int(evaluation_config["generation"]["batch_size"])
    generator = torch.Generator(device=device)
    generator.manual_seed(sampling_seed)
    greedy_seconds = 0.0
    sampled_seconds = 0.0
    greedy_tokens = 0
    sampled_tokens = 0
    for prompt_length in sorted(grouped):
        group = grouped[prompt_length]
        for start in range(0, len(group), batch_size):
            batch = group[start : start + batch_size]
            prompt_ids = [item["prompt_token_ids"] for item in batch]
            synchronize(device)
            started = time.perf_counter()
            greedy_outputs = greedy_generate_equal_length(
                model,
                prompt_ids,
                int(special_ids["eos"]),
                int(special_ids["pad"]),
                int(evaluation_config["generation"]["max_new_tokens"]),
                model.config.context_length,
                device,
            )
            synchronize(device)
            greedy_seconds += time.perf_counter() - started
            synchronize(device)
            started = time.perf_counter()
            sampled_outputs = sample_generate_equal_length(
                model,
                prompt_ids,
                candidate_count - 1,
                int(special_ids["eos"]),
                int(special_ids["pad"]),
                int(evaluation_config["generation"]["max_new_tokens"]),
                model.config.context_length,
                temperature,
                top_p,
                device,
                generator,
            )
            synchronize(device)
            sampled_seconds += time.perf_counter() - started
            for item, greedy, sampled in zip(
                batch, greedy_outputs, sampled_outputs, strict=True
            ):
                candidates = [greedy, *sampled]
                for candidate in candidates:
                    candidate["generated_code"] = tokenizer.decode(
                        candidate["generated_token_ids"],
                        skip_special_tokens=False,
                    )
                greedy_tokens += len(greedy["generated_token_ids"])
                sampled_tokens += sum(
                    len(candidate["generated_token_ids"])
                    for candidate in sampled
                )
                generated_by_index[item["source_index"]] = {
                    **item,
                    "candidates": candidates,
                }
    counters: Counter[str] = Counter()
    termination_counts: Counter[str] = Counter()
    operation_counts: dict[int, Counter[str]] = defaultdict(Counter)
    with output_path.open("w", encoding="utf-8") as output_handle:
        with SuiteVerifier(
            suite_name,
            input_manifest,
            float(evaluation_config["verification"]["timeout_seconds"]),
            int(evaluation_config["verification"]["max_source_chars"]),
        ) as verifier:
            for source_index in sorted(generated_by_index):
                item = generated_by_index[source_index]
                candidate_records: list[dict[str, Any]] = []
                for candidate_index, candidate in enumerate(item["candidates"], start=1):
                    verification = verifier.verify(
                        candidate["generated_code"],
                        item["semantic_ast"],
                        item["spec_id"],
                    )
                    candidate_records.append(
                        {
                            "candidate_index": candidate_index,
                            "decoding": "greedy" if candidate_index == 1 else "top_p",
                            "generated_code": candidate["generated_code"],
                            "generated_token_count": len(candidate["generated_token_ids"]),
                            "passed": bool(verification["tests_passed"]),
                            "termination": candidate["termination"],
                            "verification": verification,
                        }
                    )
                primary = candidate_records[0]
                pass_at_1 = bool(primary["passed"])
                pass_at_5 = any(bool(candidate["passed"]) for candidate in candidate_records)
                verification = primary["verification"]
                counters["total"] += 1
                counters["syntax_valid"] += int(bool(verification["syntax_ok"]))
                counters["safe_ast"] += int(bool(verification["ast_safe"]))
                counters["signature_valid"] += int(bool(verification["signature_ok"]))
                counters["executable"] += int(is_executable(verification))
                counters["pass_at_1"] += int(pass_at_1)
                counters["pass_at_5"] += int(pass_at_5)
                counters["timeout"] += int(bool(verification["timeout"]))
                termination_counts[str(primary["termination"])] += 1
                operation_count = int(item["operation_count"])
                operation_counts[operation_count]["total"] += 1
                operation_counts[operation_count]["pass_at_1"] += int(pass_at_1)
                operation_counts[operation_count]["pass_at_5"] += int(pass_at_5)
                output_handle.write(
                    json.dumps(
                        {
                            "candidates": candidate_records,
                            "instruction_id": item["instruction_id"],
                            "operation_count": operation_count,
                            "pass_at_1": pass_at_1,
                            "pass_at_5": pass_at_5,
                            "record_id": item["record_id"],
                            "source_index": source_index,
                            "spec_id": item["spec_id"],
                            "suite": suite_name,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
    total = counters["total"]
    summary = {
        "by_operation_count": {
            str(operation_count): {
                "pass_at_1": values["pass_at_1"] / values["total"],
                "pass_at_1_count": values["pass_at_1"],
                "pass_at_5": values["pass_at_5"] / values["total"],
                "pass_at_5_count": values["pass_at_5"],
                "total": values["total"],
            }
            for operation_count, values in sorted(operation_counts.items())
        },
        "executable_count": counters["executable"],
        "executable_rate": counters["executable"] / total,
        "pass_at_1": counters["pass_at_1"] / total,
        "pass_at_1_count": counters["pass_at_1"],
        "pass_at_5": counters["pass_at_5"] / total,
        "pass_at_5_count": counters["pass_at_5"],
        "record_count": total,
        "safe_ast_count": counters["safe_ast"],
        "safe_ast_rate": counters["safe_ast"] / total,
        "signature_valid_count": counters["signature_valid"],
        "signature_valid_rate": counters["signature_valid"] / total,
        "suite": suite_name,
        "syntax_valid_count": counters["syntax_valid"],
        "syntax_valid_rate": counters["syntax_valid"] / total,
        "termination_counts": dict(sorted(termination_counts.items())),
        "timeout_count": counters["timeout"],
    }
    timing = {
        "greedy_generation_seconds": greedy_seconds,
        "greedy_generated_tokens": float(greedy_tokens),
        "sampled_generation_seconds": sampled_seconds,
        "sampled_generated_tokens": float(sampled_tokens),
    }
    return summary, timing


def aggregate_summaries(summaries: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """集合別件数を比較集合全体へ合算する。"""

    total = sum(int(summary["record_count"]) for summary in summaries.values())
    result: dict[str, Any] = {"record_count": total}
    for name in (
        "syntax_valid",
        "safe_ast",
        "signature_valid",
        "executable",
        "pass_at_1",
        "pass_at_5",
    ):
        count = sum(int(summary[f"{name}_count"]) for summary in summaries.values())
        result[f"{name}_count"] = count
        result[f"{name}_rate" if name not in {"pass_at_1", "pass_at_5"} else name] = (
            count / total
        )
    result["timeout_count"] = sum(
        int(summary["timeout_count"]) for summary in summaries.values()
    )
    return result


def aggregate_existing_full_results(directory: Path) -> dict[str, Any]:
    """既存の正式pass@1結果から段階別指標を再集計する。"""

    counters: Counter[str] = Counter()
    by_suite: dict[str, Any] = {}
    for suite_name in SUPPORTED_SUITES:
        suite_counters: Counter[str] = Counter()
        path = directory / f"{suite_name}_results.jsonl"
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                verification = record["verification"]
                suite_counters["total"] += 1
                suite_counters["syntax_valid"] += int(bool(verification["syntax_ok"]))
                suite_counters["safe_ast"] += int(bool(verification["ast_safe"]))
                suite_counters["signature_valid"] += int(bool(verification["signature_ok"]))
                suite_counters["executable"] += int(is_executable(verification))
                suite_counters["pass_at_1"] += int(bool(record["passed"]))
        counters.update(suite_counters)
        total = suite_counters["total"]
        by_suite[suite_name] = {
            "executable_count": suite_counters["executable"],
            "executable_rate": suite_counters["executable"] / total,
            "pass_at_1": suite_counters["pass_at_1"] / total,
            "pass_at_1_count": suite_counters["pass_at_1"],
            "record_count": total,
            "safe_ast_count": suite_counters["safe_ast"],
            "safe_ast_rate": suite_counters["safe_ast"] / total,
            "signature_valid_count": suite_counters["signature_valid"],
            "signature_valid_rate": suite_counters["signature_valid"] / total,
            "syntax_valid_count": suite_counters["syntax_valid"],
            "syntax_valid_rate": suite_counters["syntax_valid"] / total,
        }
    total = counters["total"]
    return {
        "by_suite": by_suite,
        "executable_count": counters["executable"],
        "executable_rate": counters["executable"] / total,
        "pass_at_1": counters["pass_at_1"] / total,
        "pass_at_1_count": counters["pass_at_1"],
        "record_count": total,
        "safe_ast_count": counters["safe_ast"],
        "safe_ast_rate": counters["safe_ast"] / total,
        "signature_valid_count": counters["signature_valid"],
        "signature_valid_rate": counters["signature_valid"] / total,
        "syntax_valid_count": counters["syntax_valid"],
        "syntax_valid_rate": counters["syntax_valid"] / total,
    }


def initial_state_sha256(model: BokuNanoForCausalLM) -> str:
    """CPU上のランダム初期parameterを順序固定でhash化する。"""

    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        value = tensor.detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(str(tuple(value.shape)).encode("ascii"))
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def load_random_model(
    model_config_path: Path,
    seed: int,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[BokuNanoForCausalLM, str]:
    """学習開始時と同じseed・構造で未学習モデルを再現する。"""

    seed_everything(seed)
    values = json.loads(model_config_path.read_text(encoding="utf-8"))
    model = BokuNanoForCausalLM(BokuNanoConfig.from_dict(values))
    state_sha256 = initial_state_sha256(model)
    model.to(device=device, dtype=dtype)
    model.eval()
    return model, state_sha256


def build_validation_dataset_for_comparison(
    training_config_path: Path,
) -> tuple[Any, dict[str, Any], dict[str, int], int]:
    """訓練時と同じvalidation集合を一度だけ構築する。"""

    config = load_training_config(training_config_path)
    model_config = BokuNanoConfig.from_dict(config["model"])
    tokenizer, special_ids, _ = validate_tokenizer(config, model_config)
    validation_view = dict(config)
    validation_view["data"] = config["validation_data"]
    validation_view["training"] = dict(config["training"], epochs=1)
    archive_path, archive_sha256 = validate_source_archive(validation_view)
    dataset, stats = build_training_dataset(
        validation_view,
        tokenizer,
        special_ids,
        archive_path,
        archive_sha256,
    )
    return dataset, stats, special_ids, int(config["training"]["validation_batch_size"])


def evaluate_model(
    model_name: str,
    model: BokuNanoForCausalLM,
    model_sha256: str,
    selected: Mapping[str, Sequence[dict[str, Any]]],
    evaluation_config: Mapping[str, Any],
    comparison_config: Mapping[str, Any],
    tokenizer: Tokenizer,
    special_ids: Mapping[str, int],
    device: torch.device,
    validation_dataset: Any,
    validation_batch_size: int,
    output_directory: Path,
) -> dict[str, Any]:
    """一モデルのvalidation lossと比較集合指標を測る。"""

    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    validation_started = time.perf_counter()
    validation = evaluate_validation_loss(
        model,
        validation_dataset,
        validation_batch_size,
        int(special_ids["pad"]),
        device,
        torch.bfloat16 if str(evaluation_config["generation"]["dtype"]) == "bfloat16" else torch.float32,
    )
    synchronize(device)
    validation_seconds = time.perf_counter() - validation_started
    model.eval()
    suite_summaries: dict[str, Any] = {}
    timings: Counter[str] = Counter()
    for suite_index, suite_name in enumerate(SUPPORTED_SUITES):
        summary, timing = run_suite(
            suite_name,
            selected[suite_name],
            evaluation_config,
            model,
            tokenizer,
            special_ids,
            device,
            int(comparison_config["candidate_count"]),
            int(comparison_config["sampling_seed"]) + suite_index,
            float(comparison_config["temperature"]),
            float(comparison_config["top_p"]),
            output_directory / f"{model_name}_{suite_name}_results.jsonl",
        )
        suite_summaries[suite_name] = summary
        timings.update(timing)
    aggregate = aggregate_summaries(suite_summaries)
    greedy_seconds = float(timings["greedy_generation_seconds"])
    sampled_seconds = float(timings["sampled_generation_seconds"])
    greedy_tokens = int(timings["greedy_generated_tokens"])
    sampled_tokens = int(timings["sampled_generated_tokens"])
    efficiency = {
        "all_candidates_generated_tokens": greedy_tokens + sampled_tokens,
        "all_candidates_generation_seconds": greedy_seconds + sampled_seconds,
        "all_candidates_tokens_per_second": (
            (greedy_tokens + sampled_tokens) / (greedy_seconds + sampled_seconds)
        ),
        "greedy_generated_tokens": greedy_tokens,
        "greedy_generation_seconds": greedy_seconds,
        "greedy_tokens_per_second": greedy_tokens / greedy_seconds,
        "sampled_generated_tokens": sampled_tokens,
        "sampled_generation_seconds": sampled_seconds,
        "sampled_tokens_per_second": sampled_tokens / sampled_seconds,
    }
    peak_memory = (
        int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else None
    )
    return {
        "aggregate": aggregate,
        "efficiency": efficiency,
        "maximum_gpu_memory_allocated_bytes": peak_memory,
        "model": model_name,
        "model_sha256": model_sha256,
        "suites": suite_summaries,
        "validation": {
            **validation,
            "elapsed_seconds": validation_seconds,
        },
    }


def validate_and_select(
    config_path: Path,
    records_per_suite_override: int | None,
    output_directory_override: Path | None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, list[dict[str, Any]]],
    Path,
    dict[str, Any],
]:
    """全設定を検証し、固定比較集合を返す。"""

    comparison_root = load_comparison_config(config_path)
    base_path = configured_path(comparison_root["base_evaluation_config"])
    validation = validate_configuration(base_path)
    evaluation_config = load_evaluation_config(base_path)
    comparison = dict(comparison_root["comparison"])
    if records_per_suite_override is not None:
        if records_per_suite_override <= 0:
            raise ValueError("--max-records-per-suiteは正の整数にしてください")
        comparison["records_per_suite"] = records_per_suite_override
    archive_path = configured_path(evaluation_config["evaluation_data"]["archive"])
    selected = {
        suite_name: select_records(
            archive_path,
            suite_name,
            evaluation_config["evaluation_data"]["suites"][suite_name],
            int(comparison["records_per_suite"]),
            int(comparison["selection_seed"]),
        )
        for suite_name in SUPPORTED_SUITES
    }
    case_counts = validate_hidden_case_counts(evaluation_config, selected)
    output_directory = (
        output_directory_override.resolve()
        if output_directory_override is not None
        else configured_path(comparison_root["output"]["directory"])
    )
    preflight = {
        "case_counts": case_counts,
        "comparison_config_sha256": file_sha256(config_path),
        "evaluation_config_sha256": validation["config_sha256"],
        "record_ids_sha256": hashlib.sha256(
            "\n".join(
                record["record_id"]
                for suite_name in SUPPORTED_SUITES
                for record in selected[suite_name]
            ).encode("utf-8")
        ).hexdigest(),
        "selected_record_count": sum(len(records) for records in selected.values()),
    }
    return comparison_root, evaluation_config, comparison, selected, output_directory, preflight


def main() -> None:
    """比較評価を検証または実行する。"""

    args = parse_args()
    (
        comparison_root,
        evaluation_config,
        comparison,
        selected,
        output_directory,
        preflight,
    ) = validate_and_select(
        args.config.resolve(),
        args.max_records_per_suite,
        args.output_directory,
    )
    if args.validate_config:
        print(json.dumps(preflight, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if output_directory.exists() and any(output_directory.iterdir()) and not args.overwrite:
        raise FileExistsError(
            f"比較評価結果が既にあります: {output_directory}. --overwriteを指定してください"
        )
    output_directory.mkdir(parents=True, exist_ok=True)
    for path in output_directory.glob("*"):
        if args.overwrite and path.is_file():
            path.unlink()
    tokenizer = Tokenizer.from_file(
        str(configured_path(evaluation_config["tokenizer"]["path"]))
    )
    special_ids = {
        name: int(value)
        for name, value in evaluation_config["tokenizer"]["special_token_ids"].items()
    }
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = (
        torch.bfloat16
        if str(evaluation_config["generation"]["dtype"]) == "bfloat16"
        else torch.float32
    )
    training_config_path = configured_path(comparison_root["training_config"])
    validation_dataset, validation_stats, _, validation_batch_size = (
        build_validation_dataset_for_comparison(training_config_path)
    )
    model_directory = configured_path(evaluation_config["model"]["directory"])
    started = time.monotonic()
    trained_model, _ = load_model(
        model_directory,
        str(evaluation_config["model"]["config"]),
        str(evaluation_config["model"]["weights"]),
        str(device),
        str(evaluation_config["generation"]["dtype"]),
    )
    trained = evaluate_model(
        "trained_3epoch",
        trained_model,
        file_sha256(model_directory / str(evaluation_config["model"]["weights"])),
        selected,
        evaluation_config,
        comparison,
        tokenizer,
        special_ids,
        device,
        validation_dataset,
        validation_batch_size,
        output_directory,
    )
    del trained_model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    random_model, random_sha256 = load_random_model(
        model_directory / str(evaluation_config["model"]["config"]),
        int(comparison["random_model_seed"]),
        device,
        dtype,
    )
    random_result = evaluate_model(
        "random_init",
        random_model,
        random_sha256,
        selected,
        evaluation_config,
        comparison,
        tokenizer,
        special_ids,
        device,
        validation_dataset,
        validation_batch_size,
        output_directory,
    )
    del random_model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    full_trained = aggregate_existing_full_results(
        configured_path(comparison_root["full_trained_results"])
    )
    manifest = {
        "comparison": comparison,
        "comparison_version": COMPARISON_VERSION,
        "elapsed_seconds": time.monotonic() - started,
        "full_trained_pass_at_1": full_trained,
        "platform": platform.platform(),
        "preflight": preflight,
        "python": platform.python_version(),
        "random_init": random_result,
        "torch": torch.__version__,
        "trained_3epoch": trained,
        "validation_dataset": validation_stats,
    }
    write_json_atomic(output_directory / "comparison_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
