#!/usr/bin/env python3
"""固定872問の組合せ汎化ベンチマークを構築・評価・可視化する。"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import html
import json
from pathlib import Path
import random
import re
import sys
import time
from typing import Any, Iterable
import zipfile

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generated_code_verifier import GeneratedCodeVerifierSession  # noqa: E402
from scripts.model.evaluate_boku_nano import (  # noqa: E402
    encode_prompt,
    greedy_generate_equal_length,
    load_model,
)

DEFAULT_DATASET = ROOT / "data/benchmarks/composition_suite_872_v2_20261018"
DEFAULT_RUNS = ROOT / "data/models/composition_suite_872_v2_20261018"
DEFAULT_OUTPUT = ROOT / "docs/results/figures/composition_suite_872_v2_20261018"
EVALUATION_ARCHIVE = ROOT / "data/archives/final_evaluation_dataset_records_2026-09-25.zip"
TRAIN_ARCHIVE = ROOT / "data/archives/replacement_resolved_train_instructions_2026-09-25.zip"
EXPRESSIONS_CSV = ROOT / "data/instruction_dictionaries/release/japanese_atomic_expressions.csv"
SPLIT_CONFIG = ROOT / "config/build_approved_expression_dictionary.json"
ATOMIC_ASTS = ROOT / "data/semantic_asts/atomic_semantic_asts.jsonl"
TOKENIZER = ROOT / "data/tokenizers/bpe_2048/tokenizer.json"
TEST_CASE_SOURCE = ROOT / "data/benchmarks/browser_100/runs/dev50-20261005/test_cases.json"

SPECIAL_IDS = {"pad": 0, "bos": 1, "eos": 2, "unk": 3, "task": 4, "code": 5}
CATEGORIES = (
    "transfer_1op",
    "composition_2op",
    "transfer_3to2",
    "repeat_2",
    "composition_3op",
    "repeat_3",
    "general_4op",
    "repeat_abab",
    "repeat_4",
)
CATEGORY_LABELS = {
    "transfer_1op": "複合→単独",
    "composition_2op": "未学習2操作",
    "transfer_3to2": "3操作→2操作",
    "repeat_2": "同一操作×2",
    "composition_3op": "未学習3操作",
    "repeat_3": "同一操作×3",
    "general_4op": "異なる4操作",
    "repeat_abab": "ABAB",
    "repeat_4": "同一操作×4",
}
EXPECTED_COUNTS = {
    "transfer_1op": 96,
    "composition_2op": 100,
    "transfer_3to2": 88,
    "repeat_2": 96,
    "composition_3op": 100,
    "repeat_3": 96,
    "general_4op": 100,
    "repeat_abab": 100,
    "repeat_4": 96,
}
MODEL_REGISTRY = {
    "boku-15m-1epoch": (
        "Boku 15M / 1ep",
        ROOT / "data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch",
    ),
    "boku-5m-1epoch": (
        "Boku 5M / 1ep",
        ROOT / "data/models/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch",
    ),
    "boku-1m-3epoch": (
        "Boku 1M / 3ep",
        ROOT / "data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch",
    ),
    "middle4-1m-3epoch": (
        "中間層×4 / 3ep",
        ROOT / "data/models/middle4_1m_3epoch_20261018/u3_middle4_seed20260925/model",
    ),
    "middle4-scaled025-1m-3epoch": (
        "中間層×4・残差0.25 / 3ep",
        ROOT / "data/models/middle4_1m_3epoch_20261018/u3_middle4_scaled025_seed20260925/model",
    ),
}
COLORS = ("#2563eb", "#0891b2", "#7c3aed", "#e11d48", "#ea580c", "#16a34a")
CANONICAL_FINALS = (
    "偶数だけを残す", "奇数だけを残す", "kより大きい値だけを残す", "k以上の値だけを残す",
    "kより小さい値を残す", "k以下の値だけを残す", "kの倍数だけを残す", "正の値だけを残す",
    "負の値だけを残す", "ゼロだけを残す", "各要素にkを加える", "各要素からkを引く",
    "すべての要素をk倍する", "すべての値を2倍する", "各要素を三倍する", "値の符号を反転する",
    "各要素の絶対値を取る", "各要素を二乗する", "値を昇順に並べる", "値を降順に並べ替える",
    "順序を反転する", "先頭からk個を取る", "末尾からk個を取る", "隔番で取る",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def ast_key(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sequence(value: dict[str, Any]) -> list[dict[str, Any]]:
    return list(value.get("sequence", [value]))


def uses_k(operations: Iterable[dict[str, Any]]) -> bool:
    return any("_k" in ast_key(operation) for operation in operations)


def instruction_for(
    operations: list[dict[str, Any]], expression_rows: list[dict[str, str]]
) -> str:
    prefix = "整数リストxsと整数kを受け取り、" if uses_k(operations) else "整数リストxsから"
    phrases = [row["connective_expression_ja"] for row in expression_rows[:-1]]
    phrases.append(expression_rows[-1]["expression_ja"])
    return prefix + "、".join(phrases) + "solve関数を書いてください。"


def read_archive_member(archive: Path, member: str) -> Iterable[dict[str, Any]]:
    with zipfile.ZipFile(archive) as zipped:
        with zipped.open(member) as handle:
            for line in handle:
                yield json.loads(line)


def make_question(
    category: str,
    index: int,
    semantic_ast: dict[str, Any],
    instruction: str,
    expression_ids: list[str],
    source: str,
) -> dict[str, Any]:
    return {
        "question_id": f"{category}-{index:03d}",
        "category_id": category,
        "instruction_ja": instruction,
        "semantic_ast": semantic_ast,
        "operation_count": len(sequence(semantic_ast)),
        "expression_ids": expression_ids,
        "source": source,
    }


def build_dataset(dataset: Path) -> dict[str, Any]:
    """保存済み一次資料から、決定的な872問と共通179入力を作る。"""

    dataset.mkdir(parents=True, exist_ok=True)
    split = json.loads(SPLIT_CONFIG.read_text(encoding="utf-8"))
    test_only = set(split["test_only_expression_ids"])
    expressions = list(csv.DictReader(EXPRESSIONS_CSV.open(encoding="utf-8")))
    expression_by_id = {row["expression_id"]: row for row in expressions}
    atomic_rows = jsonl(ATOMIC_ASTS)
    atomic_operations = [row["semantic_ast"] for row in atomic_rows]
    operation_id_by_ast = {ast_key(row["semantic_ast"]): row["spec_id"] for row in atomic_rows}

    train_by_operation: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in expressions:
        if row["expression_id"] not in test_only:
            train_by_operation[row["operation_id"]].append(row)

    multi_expression_ids: set[str] = set()
    train_texts: set[str] = set()
    transfer_rows: list[dict[str, Any]] = []
    transfer_seen: set[str] = set()
    for row in read_archive_member(TRAIN_ARCHIVE, "replacement_resolved_train_instructions.jsonl"):
        train_texts.add(row["instruction_ja"])
        operations = sequence(row["semantic_ast"])
        if len(operations) >= 2:
            multi_expression_ids.update(row["expression_ids"])
        if len(operations) == 3 and len(transfer_rows) < 88:
            pair_ast = {"sequence": operations[:2]}
            key = ast_key(pair_ast)
            if key not in transfer_seen:
                transfer_seen.add(key)
                ids = list(row["expression_ids"][:2])
                transfer_rows.append({
                    "semantic_ast": pair_ast,
                    "expression_ids": ids,
                    "instruction_ja": instruction_for(
                        operations[:2], [expression_by_id[value] for value in ids]
                    ),
                    "record_id": row["instruction_id"],
                })

    questions: list[dict[str, Any]] = []
    for operation, atomic_row in zip(atomic_operations, atomic_rows, strict=True):
        candidates = [
            row for row in train_by_operation[atomic_row["spec_id"]]
            if row["expression_id"] in multi_expression_ids
        ][:4]
        if len(candidates) != 4:
            raise ValueError(f"複数操作で使用済みの表現が4件ありません: {atomic_row['spec_id']}")
        for candidate in candidates:
            instruction = instruction_for([operation], [candidate])
            if instruction in train_texts:
                instruction = instruction.removesuffix(
                    "solve関数を書いてください。"
                ) + "関数solveを実装してください。"
            questions.append(make_question(
                "transfer_1op",
                1 + sum(q["category_id"] == "transfer_1op" for q in questions),
                {"sequence": [operation]},
                instruction,
                [candidate["expression_id"]],
                "training expression observed in a multi-operation instruction",
            ))

    compositional_rows = list(read_archive_member(
        EVALUATION_ARCHIVE, "compositional_test_dataset_records.jsonl"
    ))
    grouped_composition_2: dict[str, list[dict[str, Any]]] = defaultdict(list)
    first_composition_3: list[dict[str, Any]] = []
    seen_composition_3: set[str] = set()
    for row in compositional_rows:
        operations = sequence(row["semantic_ast"])
        key = ast_key(row["semantic_ast"])
        if len(operations) == 2 and len(grouped_composition_2[key]) < 10:
            grouped_composition_2[key].append(row)
        if len(operations) == 3 and key not in seen_composition_3 and len(first_composition_3) < 100:
            seen_composition_3.add(key)
            first_composition_3.append(row)
    selected_2 = [row for rows in grouped_composition_2.values() for row in rows]
    for category, rows in (("composition_2op", selected_2), ("composition_3op", first_composition_3)):
        for index, row in enumerate(rows, 1):
            questions.append(make_question(
                category, index, row["semantic_ast"], row["instruction_ja"],
                list(row["expression_ids"]), row["record_id"],
            ))

    for index, row in enumerate(transfer_rows, 1):
        questions.append(make_question(
            "transfer_3to2", index, row["semantic_ast"], row["instruction_ja"],
            row["expression_ids"], row["record_id"],
        ))

    repetition_rows = read_archive_member(
        EVALUATION_ARCHIVE, "repetition_test_dataset_records.jsonl"
    )
    grouped_repetition: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in repetition_rows:
        operations = sequence(row["semantic_ast"])
        if len(operations) not in (2, 3) or any(operation != operations[0] for operation in operations):
            continue
        operation_id = operation_id_by_ast[ast_key(operations[0])]
        key = (len(operations), operation_id)
        if len(grouped_repetition[key]) < 4:
            grouped_repetition[key].append(row)
    for count, category in ((2, "repeat_2"), (3, "repeat_3")):
        index = 0
        for atomic_row in atomic_rows:
            rows = grouped_repetition[(count, atomic_row["spec_id"])]
            if len(rows) != 4:
                raise ValueError(f"反復表現が4件ありません: {count=} {atomic_row['spec_id']}")
            for row in rows:
                index += 1
                questions.append(make_question(
                    category, index, row["semantic_ast"], row["instruction_ja"],
                    list(row["expression_ids"]), row["record_id"],
                ))

    primary_expression = {}
    for atomic_row, canonical_final in zip(atomic_rows, CANONICAL_FINALS, strict=True):
        primary_expression[atomic_row["spec_id"]] = next(
            item for item in train_by_operation[atomic_row["spec_id"]]
            if item["expression_ja"] == canonical_final
        )
    rng = random.Random(20261008)
    distinct_four_set: set[tuple[int, ...]] = set()
    while len(distinct_four_set) < 100:
        distinct_four_set.add(tuple(rng.sample(range(24), 4)))
    distinct_four = sorted(distinct_four_set)
    ordered_pairs = [(left, right) for left in range(24) for right in range(24) if left != right]
    abab_pairs = rng.sample(ordered_pairs, 100)
    for category, index_sequences in (
        ("general_4op", distinct_four),
        ("repeat_abab", [(left, right, left, right) for left, right in abab_pairs]),
    ):
        for index, indices in enumerate(index_sequences, 1):
            operations = [atomic_operations[value] for value in indices]
            rows = [primary_expression[atomic_rows[value]["spec_id"]] for value in indices]
            questions.append(make_question(
                category, index, {"sequence": operations}, instruction_for(operations, rows),
                [row["expression_id"] for row in rows], "deterministic 20261008 construction",
            ))

    index = 0
    for atomic_row, operation in zip(atomic_rows, atomic_operations, strict=True):
        candidates = [
            row for row in train_by_operation[atomic_row["spec_id"]]
            if row["expression_id"] in multi_expression_ids
        ][:4]
        for candidate in candidates:
            index += 1
            operations = [operation] * 4
            rows = [candidate] * 4
            questions.append(make_question(
                "repeat_4", index, {"sequence": operations}, instruction_for(operations, rows),
                [candidate["expression_id"]] * 4, "fourfold extension of a learned expression",
            ))

    for question in questions:
        if question["instruction_ja"] not in train_texts:
            continue
        stem = question["instruction_ja"].removesuffix("solve関数を書いてください。")
        for suffix in ("関数solveを実装してください。", "solve関数を実装してください。"):
            candidate = stem + suffix
            if candidate not in train_texts:
                question["instruction_ja"] = candidate
                break
        else:
            raise ValueError(f"訓練全文一致を除けません: {question['question_id']}")

    order = {category: index for index, category in enumerate(CATEGORIES)}
    questions.sort(key=lambda row: (order[row["category_id"]], row["question_id"]))
    counts = {category: sum(row["category_id"] == category for row in questions) for category in CATEGORIES}
    if counts != EXPECTED_COUNTS or len(questions) != 872:
        raise ValueError(f"872問の内訳が不正です: {counts}")
    question_path = dataset / "questions.jsonl"
    question_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in questions),
        encoding="utf-8",
    )
    test_cases = json.loads(TEST_CASE_SOURCE.read_text(encoding="utf-8"))
    if len(test_cases) != 179 or sha256(TEST_CASE_SOURCE) != "0090a38d255848a813876ce3b64a8029603aa14e4181b453a89801b41ac67fc2":
        raise ValueError("共通179入力の固定artifactが一致しません")
    (dataset / "test_cases.json").write_text(
        json.dumps(test_cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    protocol = {
        "version": 2,
        "status": "reconstructed because the 20261008 questions artifact is absent",
        "question_count": 872,
        "category_counts": counts,
        "test_case_count": 179,
        "decoding": "greedy pass@1; no repair",
        "passing_rule": "all 179 cases, contract, safe syntax, and input immutability",
        "questions_sha256": sha256(question_path),
        "test_cases_sha256": sha256(dataset / "test_cases.json"),
        "legacy_questions_sha256": "aa119fa2a9e8507136ad14a54b9d3d2e9043fd81af9e48251ef7f5c49c20f97f",
        "sources": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (EVALUATION_ARCHIVE, TRAIN_ARCHIVE, EXPRESSIONS_CSV, SPLIT_CONFIG, ATOMIC_ASTS)
        },
    }
    (dataset / "protocol.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return protocol


def extract_code(raw: str) -> str:
    fences = re.findall(r"```[^\n]*\n([\s\S]*?)```", raw)
    if "```" in raw:
        if len(fences) != 1 or raw.count("```") != 2:
            raise ValueError("single_code_block_required")
        raw = fences[0]
    return raw.strip() + "\n"


def evaluate_model(
    model_id: str,
    dataset: Path,
    runs: Path,
    device: str,
    dtype: str,
    max_new_tokens: int,
) -> dict[str, Any]:
    label, model_directory = MODEL_REGISTRY[model_id]
    questions = jsonl(dataset / "questions.jsonl")
    tokenizer = Tokenizer.from_file(str(TOKENIZER))
    model, resolved_device = load_model(
        model_directory, "model_config.json", "model.safetensors", device, dtype
    )
    prompts = [
        encode_prompt(tokenizer, row["instruction_ja"], SPECIAL_IDS, model.config.context_length)
        for row in questions
    ]
    grouped: dict[int, list[int]] = defaultdict(list)
    for index, prompt in enumerate(prompts):
        grouped[len(prompt)].append(index)
    generated: list[dict[str, Any] | None] = [None] * len(questions)
    started = time.perf_counter()
    for indices in grouped.values():
        results = greedy_generate_equal_length(
            model, [prompts[index] for index in indices], SPECIAL_IDS["eos"], SPECIAL_IDS["pad"],
            max_new_tokens, model.config.context_length, resolved_device,
        )
        for index, result in zip(indices, results, strict=True):
            generated[index] = result
    generation_seconds = time.perf_counter() - started
    output = runs / model_id
    output.mkdir(parents=True, exist_ok=True)
    raw_records = []
    for question, prompt, result in zip(questions, prompts, generated, strict=True):
        assert result is not None
        output_ids = result["generated_token_ids"]
        raw_records.append({
            "question_id": question["question_id"],
            "category_id": question["category_id"],
            "prompt_ids": prompt,
            "output_ids": output_ids,
            "raw_output": tokenizer.decode(output_ids, skip_special_tokens=True),
            "termination": result["termination"],
        })
    (output / "raw_inference.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in raw_records), encoding="utf-8"
    )
    test_cases_json = json.loads((dataset / "test_cases.json").read_text(encoding="utf-8"))
    cases = [(list(row["xs"]), int(row["k"])) for row in test_cases_json]
    scored = []
    with GeneratedCodeVerifierSession(cases, timeout_seconds=3.0, max_source_chars=12000) as verifier:
        for question, raw in zip(questions, raw_records, strict=True):
            try:
                code = extract_code(raw["raw_output"])
                verification = verifier.verify(code, question["semantic_ast"]).to_record()
            except ValueError as error:
                code = ""
                verification = {"tests_passed": False, "error": str(error)}
            scored.append({
                "question_id": question["question_id"],
                "category_id": question["category_id"],
                "code": code,
                **verification,
            })
    (output / "scored.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in scored), encoding="utf-8"
    )
    categories = {}
    for category in CATEGORIES:
        subset = [row for row in scored if row["category_id"] == category]
        passed = sum(bool(row.get("tests_passed")) for row in subset)
        categories[category] = {"passed": passed, "total": len(subset), "percentage": 100 * passed / len(subset)}
    passed = sum(bool(row.get("tests_passed")) for row in scored)
    summary = {
        "model_id": model_id,
        "label": label,
        "model_directory": str(model_directory.relative_to(ROOT)),
        "model_sha256": sha256(model_directory / "model.safetensors"),
        "questions_sha256": sha256(dataset / "questions.jsonl"),
        "test_cases_sha256": sha256(dataset / "test_cases.json"),
        "passed": passed,
        "total": len(scored),
        "percentage": 100 * passed / len(scored),
        "categories": categories,
        "generation_seconds": generation_seconds,
        "device": resolved_device.type,
        "dtype": dtype,
        "decoding": "greedy",
        "max_new_tokens": max_new_tokens,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def plot(models: list[str], dataset: Path, runs: Path, output: Path) -> dict[str, Any]:
    summaries = [json.loads((runs / model / "summary.json").read_text(encoding="utf-8")) for model in models]
    width, height = 1800, 760
    left, right, top, bottom = 78, 28, 92, 150
    plot_width, plot_height = width - left - right, height - top - bottom
    group_width = plot_width / len(CATEGORIES)
    bar_width = min(27, group_width / (len(models) + 1))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<title>872問・組合せ汎化ベンチマーク</title>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:"Noto Sans CJK JP",sans-serif;fill:#172033}.title{font-size:25px;font-weight:700}.sub{font-size:13px;fill:#5b6577}.axis{font-size:12px}.value{font-size:10px;font-weight:650}.grid{stroke:#dce3ec;stroke-width:1}</style>',
        '<text x="900" y="34" text-anchor="middle" class="title">872問・組合せ汎化ベンチマーク</text>',
        '<text x="900" y="59" text-anchor="middle" class="sub">各問で179入力すべてに合格した割合（greedy pass@1、修復なし）</text>',
    ]
    for tick in range(0, 101, 20):
        y = top + (100 - tick) / 100 * plot_height
        parts.extend((
            f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid"/>',
            f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" class="axis">{tick}%</text>',
        ))
    for category_index, category in enumerate(CATEGORIES):
        center = left + (category_index + 0.5) * group_width
        for model_index, summary in enumerate(summaries):
            value = summary["categories"][category]["percentage"]
            x = center + (model_index - (len(models) - 1) / 2) * (bar_width + 3) - bar_width / 2
            y = top + (100 - value) / 100 * plot_height
            parts.extend((
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{top+plot_height-y:.1f}" fill="{COLORS[model_index]}"/>',
                f'<text x="{x+bar_width/2:.1f}" y="{max(top+11,y-5):.1f}" text-anchor="middle" class="value">{value:.0f}</text>',
            ))
        parts.append(
            f'<text x="{center:.1f}" y="{top+plot_height+27}" text-anchor="middle" class="axis">{html.escape(CATEGORY_LABELS[category])}</text>'
        )
        parts.append(
            f'<text x="{center:.1f}" y="{top+plot_height+46}" text-anchor="middle" class="sub">n={EXPECTED_COUNTS[category]}</text>'
        )
    legend_y = height - 48
    legend_width = 290
    legend_start = (width - legend_width * len(models)) / 2
    for index, summary in enumerate(summaries):
        x = legend_start + index * legend_width
        parts.extend((
            f'<rect x="{x:.1f}" y="{legend_y-12}" width="16" height="16" fill="{COLORS[index]}"/>',
            f'<text x="{x+23:.1f}" y="{legend_y+1}" class="axis">{html.escape(summary["label"])} ({summary["passed"]}/{summary["total"]})</text>',
        ))
    parts.append("</svg>")
    output.mkdir(parents=True, exist_ok=True)
    (output / "plot.svg").write_text("\n".join(parts) + "\n", encoding="utf-8")
    values = {
        "dataset": str(dataset.relative_to(ROOT)),
        "questions_sha256": sha256(dataset / "questions.jsonl"),
        "test_cases_sha256": sha256(dataset / "test_cases.json"),
        "models": summaries,
    }
    (output / "values.json").write_text(
        json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = ["# 872問・組合せ汎化ベンチマーク", "", "各欄は合格数／問題数（正答率）。", ""]
    lines.append("| カテゴリ | " + " | ".join(item["label"] for item in summaries) + " |")
    lines.append("| --- | " + " | ".join("---:" for _ in summaries) + " |")
    for category in CATEGORIES:
        cells = []
        for summary in summaries:
            value = summary["categories"][category]
            cells.append(f'{value["passed"]}/{value["total"]} ({value["percentage"]:.1f}%)')
        lines.append(f'| {CATEGORY_LABELS[category]} | ' + " | ".join(cells) + " |")
    lines.extend(("", f'質問SHA-256: `{values["questions_sha256"]}`', f'入力SHA-256: `{values["test_cases_sha256"]}`', ""))
    (output / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "evaluate", "plot", "all"))
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--models", nargs="+", choices=tuple(MODEL_REGISTRY), default=list(MODEL_REGISTRY))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", choices=("float32", "bfloat16"), default="float32")
    parser.add_argument("--max-new-tokens", type=int, default=160)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = args.dataset.resolve()
    runs = args.runs.resolve()
    output = args.output.resolve()
    if args.action in ("build", "all"):
        print(json.dumps(build_dataset(dataset), ensure_ascii=False, indent=2))
    if args.action in ("evaluate", "all"):
        if not (dataset / "questions.jsonl").is_file():
            raise FileNotFoundError("先にbuildを実行してください")
        for model_id in args.models:
            summary = evaluate_model(
                model_id, dataset, runs, args.device, args.dtype, args.max_new_tokens
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.action in ("plot", "all"):
        print(json.dumps(plot(args.models, dataset, runs, output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
