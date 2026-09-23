"""承認済み表現を整理し、GitHub公開用のCSVと来歴JSONLを作る。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


REVIEW_FIELDS = [
    "expression_id",
    "operation_id",
    "operation_ast",
    "canonical_meaning_ja",
    "must_preserve_ja",
    "expression_ja",
    "connective_expression_ja",
    "review_status",
    "edited_expression_ja",
    "edited_connective_expression_ja",
    "dictionary",
    "reviewer",
    "reviewed_at",
]
RELEASE_FIELDS = [
    "expression_id",
    "operation_id",
    "operation_ast",
    "canonical_meaning_ja",
    "must_preserve_ja",
    "expression_ja",
    "connective_expression_ja",
]
RELEASE_CSV_NAME = "japanese_atomic_expressions.csv"
RELEASE_JSONL_NAME = "japanese_atomic_expression_provenance.jsonl"


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""

    parser = argparse.ArgumentParser(
        description=(
            "承認済み表現と生成来歴を検証し、公開専用ディレクトリへ出力します。"
        )
    )
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--candidate-jsonl", required=True, type=Path)
    parser.add_argument("--release-directory", required=True, type=Path)
    parser.add_argument(
        "--prune-unused",
        action="store_true",
        help=(
            "review_status=unusedの行を承認CSVと承認候補JSONLから除き、"
            "承認CSVの余分な先頭行も除去します。"
        ),
    )
    return parser.parse_args()


def main() -> None:
    """承認済みマスターを整理し、公開成果物を作る。"""

    args = parse_args()
    result = prepare_release(
        review_csv=args.review_csv,
        candidate_jsonl=args.candidate_jsonl,
        release_directory=args.release_directory,
        prune_unused=args.prune_unused,
    )
    print(
        f"公開用辞書を作成しました: approved={result['approved']}, "
        f"removed_unused={result['removed_unused']}, "
        f"human_edited={result['human_edited']}"
    )


def prepare_release(
    *,
    review_csv: Path,
    candidate_jsonl: Path,
    release_directory: Path,
    prune_unused: bool,
) -> dict[str, int]:
    """入力を相互検証し、承認済みマスターと公開成果物を同時に整える。"""

    fields, rows = _read_review_csv(review_csv)
    missing_fields = [field for field in REVIEW_FIELDS if field not in fields]
    if missing_fields:
        raise ValueError(
            "承認CSVに必須列がありません: " + ", ".join(missing_fields)
        )

    candidates = _read_jsonl_by_id(candidate_jsonl)
    approved_rows: list[dict[str, str]] = []
    unused_rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str, str]] = set()
    human_edited = 0

    for row_number, row in enumerate(rows, start=2):
        expression_id = row["expression_id"].strip()
        if not expression_id:
            raise ValueError(f"expression_idが空です: 行{row_number}")
        if expression_id in seen_ids:
            raise ValueError(f"expression_idが重複しています: {expression_id}")
        seen_ids.add(expression_id)

        status = row["review_status"].strip().lower()
        if status == "unused":
            unused_rows.append(row)
            continue
        if status != "approved":
            raise ValueError(
                f"review_statusはapprovedまたはunusedが必要です: "
                f"行{row_number}: {status!r}"
            )

        candidate = candidates.get(expression_id)
        if candidate is None:
            raise ValueError(
                f"承認行に対応する候補JSONLがありません: {expression_id}"
            )
        operation_id = row["operation_id"].strip()
        if candidate.get("operation_id") != operation_id:
            raise ValueError(
                f"CSVとJSONLのoperation_idが一致しません: {expression_id}"
            )
        expression, connective = _effective_expressions(row)
        if not expression or not connective:
            raise ValueError(f"最終表現が空です: {expression_id}")
        pair = (operation_id, expression, connective)
        if pair in seen_pairs:
            raise ValueError(
                "同じ操作の最終表現が重複しています: "
                f"{operation_id}: {expression!r}, {connective!r}"
            )
        seen_pairs.add(pair)
        if row["edited_expression_ja"].strip() or row[
            "edited_connective_expression_ja"
        ].strip():
            human_edited += 1
        approved_rows.append(row)

    if unused_rows and not prune_unused:
        raise ValueError(
            f"unusedが{len(unused_rows)}件あります。削除する場合は"
            "--prune-unusedを指定してください"
        )

    approved_rows.sort(key=lambda row: row["operation_id"].strip())
    approved_ids = [row["expression_id"].strip() for row in approved_rows]
    approved_candidates = [candidates[expression_id] for expression_id in approved_ids]

    release_rows = [_release_row(row) for row in approved_rows]
    release_records = [
        _release_provenance(row, candidate)
        for row, candidate in zip(approved_rows, approved_candidates, strict=True)
    ]

    if prune_unused:
        _write_csv(review_csv, fields, approved_rows)
        _write_jsonl(candidate_jsonl, approved_candidates)

    release_directory.mkdir(parents=True, exist_ok=True)
    _write_csv(
        release_directory / RELEASE_CSV_NAME,
        RELEASE_FIELDS,
        release_rows,
    )
    _write_jsonl(
        release_directory / RELEASE_JSONL_NAME,
        release_records,
    )
    return {
        "approved": len(approved_rows),
        "removed_unused": len(unused_rows),
        "human_edited": human_edited,
    }


def _read_review_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Excel由来の余分な先頭行を許容してレビューCSVを読む。"""

    with path.open(encoding="utf-8-sig", newline="") as handle:
        matrix = list(csv.reader(handle))
    header_index = next(
        (
            index
            for index, values in enumerate(matrix)
            if {"expression_id", "review_status"}.issubset(values)
        ),
        None,
    )
    if header_index is None:
        raise ValueError(f"承認CSVの実ヘッダーが見つかりません: {path}")
    fields = matrix[header_index]
    rows: list[dict[str, str]] = []
    for row_number, values in enumerate(
        matrix[header_index + 1 :], start=header_index + 2
    ):
        if not values or not any(value.strip() for value in values):
            continue
        if len(values) > len(fields):
            raise ValueError(f"承認CSVの列数が不正です: {path}: 行{row_number}")
        padded = values + [""] * (len(fields) - len(values))
        rows.append(dict(zip(fields, padded, strict=True)))
    return fields, rows


def _read_jsonl_by_id(path: Path) -> dict[str, dict[str, Any]]:
    """JSONLをexpression_idで索引し、重複IDを拒否する。"""

    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"JSONLの行がobjectではありません: 行{line_number}")
            expression_id = record.get("expression_id")
            if not isinstance(expression_id, str) or not expression_id:
                raise ValueError(f"JSONLにexpression_idがありません: 行{line_number}")
            if expression_id in records:
                raise ValueError(f"JSONLのIDが重複しています: {expression_id}")
            records[expression_id] = record
    return records


def _effective_expressions(row: dict[str, str]) -> tuple[str, str]:
    """人間修正版を優先した終止形と接続形を返す。"""

    expression = row["edited_expression_ja"].strip() or row[
        "expression_ja"
    ].strip()
    connective = row["edited_connective_expression_ja"].strip() or row[
        "connective_expression_ja"
    ].strip()
    return expression, connective


def _release_row(row: dict[str, str]) -> dict[str, str]:
    """レビュー列を除き、人間修正を反映した公開CSV行を作る。"""

    expression, connective = _effective_expressions(row)
    released = {field: row[field].strip() for field in RELEASE_FIELDS}
    released["expression_ja"] = expression
    released["connective_expression_ja"] = connective
    return released


def _release_provenance(
    row: dict[str, str], candidate: dict[str, Any]
) -> dict[str, Any]:
    """最終表現と変更前の生成レコードを分離した公開来歴を作る。"""

    expression, connective = _effective_expressions(row)
    return {
        "expression_id": row["expression_id"].strip(),
        "operation_id": row["operation_id"].strip(),
        "approved_expression_ja": expression,
        "approved_connective_expression_ja": connective,
        "human_edited": bool(
            row["edited_expression_ja"].strip()
            or row["edited_connective_expression_ja"].strip()
        ),
        "generation_record": candidate,
    }


def _write_csv(
    path: Path, fields: list[str], rows: list[dict[str, str]]
) -> None:
    """CSVを一時ファイル経由で置き換える。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """JSONLを一時ファイル経由で置き換える。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                + "\n"
            )
    temporary.replace(path)


if __name__ == "__main__":
    main()
