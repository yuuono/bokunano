"""確認済み表現を承認CSVへ追加し、候補JSONLの生成履歴を永続化する。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


REQUIRED_REVIEW_FIELDS = {
    "expression_id",
    "operation_id",
    "expression_ja",
    "connective_expression_ja",
    "review_status",
    "edited_expression_ja",
    "edited_connective_expression_ja",
}


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""

    parser = argparse.ArgumentParser(
        description=(
            "review_status=approvedの表現だけを承認CSVへ追加し、"
            "対応する候補JSONLを別ファイルへ保存します。"
        )
    )
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--candidate-jsonl", required=True, type=Path)
    parser.add_argument("--approved-review-csv", required=True, type=Path)
    parser.add_argument("--approved-candidates-jsonl", required=True, type=Path)
    parser.add_argument(
        "--provenance-jsonl",
        action="append",
        default=[],
        type=Path,
        help="既存承認IDの候補情報を探すJSONLです。複数回指定できます。",
    )
    return parser.parse_args()


def main() -> None:
    """承認行と候補生成履歴を検証して同時に更新する。"""

    args = parse_args()
    review_fields, review_rows = _read_review_csv(args.review_csv)
    approved_fields, approved_rows = _read_review_csv(args.approved_review_csv)
    if review_fields != approved_fields:
        raise ValueError("確認CSVと承認CSVのヘッダーが一致しません")

    reviewed_candidates = _read_candidate_jsonl(args.candidate_jsonl)
    approved_ids = {row["expression_id"].strip() for row in approved_rows}
    approved_pairs = {
        _effective_pair(row)
        for row in approved_rows
    }

    added_rows: list[dict[str, str]] = []
    duplicate_pair_count = 0
    direct_edit_count = 0
    selected_count = 0
    for row_number, row in enumerate(review_rows, start=2):
        status = row["review_status"].strip().lower()
        if status in ("", "unused"):
            continue
        if status != "approved":
            raise ValueError(
                f"review_statusが不正です: 行{row_number}: {status!r}"
            )
        selected_count += 1
        expression_id = row["expression_id"].strip()
        candidate = reviewed_candidates.get(expression_id)
        if candidate is None:
            raise ValueError(
                f"approved行に対応する候補JSONLがありません: {expression_id}"
            )
        _validate_review_candidate(row, candidate, row_number=row_number)
        expression = (
            row["edited_expression_ja"].strip() or row["expression_ja"].strip()
        )
        connective = (
            row["edited_connective_expression_ja"].strip()
            or row["connective_expression_ja"].strip()
        )
        if (
            row["expression_ja"].strip() != candidate["expression_ja"]
            or row["connective_expression_ja"].strip()
            != candidate["connective_expression_ja"]
        ):
            direct_edit_count += 1
        pair = (row["operation_id"].strip(), expression, connective)
        if expression_id in approved_ids:
            continue
        if pair in approved_pairs:
            duplicate_pair_count += 1
            continue
        normalized = dict(row)
        normalized["expression_ja"] = candidate["expression_ja"]
        normalized["connective_expression_ja"] = candidate[
            "connective_expression_ja"
        ]
        normalized["review_status"] = "approved"
        normalized["edited_expression_ja"] = (
            expression if expression != candidate["expression_ja"] else ""
        )
        normalized["edited_connective_expression_ja"] = (
            connective
            if connective != candidate["connective_expression_ja"]
            else ""
        )
        approved_rows.append(normalized)
        added_rows.append(normalized)
        approved_ids.add(expression_id)
        approved_pairs.add(pair)

    provenance: dict[str, dict[str, Any]] = {}
    if args.approved_candidates_jsonl.is_file():
        provenance.update(
            _read_candidate_jsonl(args.approved_candidates_jsonl)
        )
    for path in args.provenance_jsonl:
        for expression_id, record in _read_candidate_jsonl(path).items():
            provenance.setdefault(expression_id, record)
    for row in added_rows:
        expression_id = row["expression_id"].strip()
        provenance[expression_id] = reviewed_candidates[expression_id]

    missing_ids = sorted(approved_ids - set(provenance))
    if missing_ids:
        raise ValueError(
            "承認済みIDに対応する候補生成履歴がありません: "
            + ", ".join(missing_ids)
        )
    # atomic番号順へ安定整列し、同じ操作内では従来の確認順を維持する
    approved_rows.sort(key=lambda row: row["operation_id"].strip())
    # CSVとJSONLを同じexpression_id順へ揃えて一行単位でも対応確認できるようにする
    ordered_candidates = [
        provenance[row["expression_id"].strip()] for row in approved_rows
    ]
    _write_review_csv(args.approved_review_csv, approved_fields, approved_rows)
    _write_candidate_jsonl(
        args.approved_candidates_jsonl,
        ordered_candidates,
    )
    print(
        f"統合完了: reviewed_approved={selected_count}, "
        f"added={len(added_rows)}, duplicate_pairs={duplicate_pair_count}, "
        f"direct_edits={direct_edit_count}, "
        f"approved_total={len(approved_rows)}, "
        f"provenance_total={len(ordered_candidates)}"
    )


def _read_review_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Excel由来の余分な先頭行も許容して確認CSVを読む。"""

    with path.open(encoding="utf-8-sig", newline="") as handle:
        matrix = list(csv.reader(handle))
    header_index = next(
        (
            index
            for index, values in enumerate(matrix)
            if REQUIRED_REVIEW_FIELDS.issubset(values)
        ),
        None,
    )
    if header_index is None:
        raise ValueError(f"確認CSVの実ヘッダーが見つかりません: {path}")
    fields = matrix[header_index]
    if len(fields) != len(set(fields)):
        raise ValueError(f"確認CSVのヘッダーが重複しています: {path}")
    rows: list[dict[str, str]] = []
    for row_number, values in enumerate(
        matrix[header_index + 1 :],
        start=header_index + 2,
    ):
        if not values or not any(value.strip() for value in values):
            continue
        if len(values) > len(fields):
            raise ValueError(f"確認CSVの列数が不正です: {path}: 行{row_number}")
        padded = values + [""] * (len(fields) - len(values))
        rows.append(dict(zip(fields, padded)))
    return fields, rows


def _read_candidate_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    """候補JSONLをIDで引けるように読み、重複IDを拒否する。"""

    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"候補JSONLの行がobjectではありません: {path}")
            expression_id = value.get("expression_id")
            if not isinstance(expression_id, str) or not expression_id:
                raise ValueError(
                    f"候補JSONLにexpression_idがありません: {path}: 行{line_number}"
                )
            if expression_id in records:
                raise ValueError(
                    f"候補JSONLのexpression_idが重複しています: {expression_id}"
                )
            records[expression_id] = value
    return records


def _validate_review_candidate(
    row: dict[str, str],
    candidate: dict[str, Any],
    *,
    row_number: int,
) -> None:
    """レビュー行と候補JSONLが同じ操作を指すことを確認する。"""

    if row["operation_id"].strip() != candidate.get("operation_id"):
        raise ValueError(
            f"確認CSVと候補JSONLのoperation_idが一致しません: 行{row_number}"
        )
    for key in ("expression_ja", "connective_expression_ja"):
        if not row[key].strip():
            raise ValueError(f"確認CSVの{key}が空です: 行{row_number}")


def _effective_pair(row: dict[str, str]) -> tuple[str, str, str]:
    """人間修正版を優先した操作ID・終止形・接続形を返す。"""

    expression = row["edited_expression_ja"].strip() or row[
        "expression_ja"
    ].strip()
    connective = row["edited_connective_expression_ja"].strip() or row[
        "connective_expression_ja"
    ].strip()
    return row["operation_id"].strip(), expression, connective


def _write_review_csv(
    path: Path,
    fields: list[str],
    rows: list[dict[str, str]],
) -> None:
    """承認CSVを一時ファイル経由で置き換える。"""

    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _write_candidate_jsonl(
    path: Path,
    records: list[dict[str, Any]],
) -> None:
    """承認候補JSONLを一時ファイル経由で置き換える。"""

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
