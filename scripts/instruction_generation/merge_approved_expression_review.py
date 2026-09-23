"""確認済み表現を承認CSVへ追加し、候補JSONLの生成履歴を永続化する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# この処理で使う標準または外部モジュールを読み込む
import argparse
# この処理で使う標準または外部モジュールを読み込む
import csv
# この処理で使う標準または外部モジュールを読み込む
import json
# 必要な定義を対象モジュールから読み込む
from pathlib import Path
# 必要な定義を対象モジュールから読み込む
from typing import Any


# REQUIRED_REVIEW_FIELDSへこの工程で使用する値を設定する
REQUIRED_REVIEW_FIELDS = {
    # この処理で扱う文字列を一覧へ加える
    "expression_id",
    # この処理で扱う文字列を一覧へ加える
    "operation_id",
    # この処理で扱う文字列を一覧へ加える
    "expression_ja",
    # この処理で扱う文字列を一覧へ加える
    "connective_expression_ja",
    # この処理で扱う文字列を一覧へ加える
    "review_status",
    # この処理で扱う文字列を一覧へ加える
    "edited_expression_ja",
    # この処理で扱う文字列を一覧へ加える
    "edited_connective_expression_ja",
}


# この工程を担当する関数を定義する
def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""

    # parserへこの工程で使用する値を設定する
    parser = argparse.ArgumentParser(
        # descriptionへこの工程で使用する値を設定する
        description=(
            "review_status=approvedの表現だけを承認CSVへ追加し、"
            "対応する候補JSONLを別ファイルへ保存します。"
        )
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--review-csv", required=True, type=Path)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--candidate-jsonl", required=True, type=Path)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--approved-review-csv", required=True, type=Path)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--approved-candidates-jsonl", required=True, type=Path)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--provenance-jsonl",
        # actionへこの工程で使用する値を設定する
        action="append",
        # defaultへこの工程で使用する値を設定する
        default=[],
        # typeへこの工程で使用する値を設定する
        type=Path,
        # helpへこの工程で使用する値を設定する
        help="既存承認IDの候補情報を探すJSONLです。複数回指定できます。",
    )
    # 処理結果を呼び出し元へ返す
    return parser.parse_args()


# この工程を担当する関数を定義する
def main() -> None:
    """承認行と候補生成履歴を検証して同時に更新する。"""

    # argsへこの工程で使用する値を設定する
    args = parse_args()
    # 次の値または処理を現在の構造へ組み込む
    review_fields, review_rows = _read_review_csv(args.review_csv)
    # 次の値または処理を現在の構造へ組み込む
    approved_fields, approved_rows = _read_review_csv(args.approved_review_csv)
    # 条件を満たす場合だけ次の処理を行う
    if review_fields != approved_fields:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("確認CSVと承認CSVのヘッダーが一致しません")

    # reviewed_candidatesへこの工程で使用する値を設定する
    reviewed_candidates = _read_candidate_jsonl(args.candidate_jsonl)
    # approved_idsへこの工程で使用する値を設定する
    approved_ids = {row["expression_id"].strip() for row in approved_rows}
    # approved_pairsへこの工程で使用する値を設定する
    approved_pairs = {
        # 次の値または処理を現在の構造へ組み込む
        _effective_pair(row)
        # 対象を一件ずつ取り出して処理する
        for row in approved_rows
    }

    # added_rowsへこの工程で使用する値を設定する
    added_rows: list[dict[str, str]] = []
    # duplicate_pair_countへこの工程で使用する値を設定する
    duplicate_pair_count = 0
    # direct_edit_countへこの工程で使用する値を設定する
    direct_edit_count = 0
    # selected_countへこの工程で使用する値を設定する
    selected_count = 0
    # 対象を一件ずつ取り出して処理する
    for row_number, row in enumerate(review_rows, start=2):
        # statusへこの工程で使用する値を設定する
        status = row["review_status"].strip().lower()
        # 条件を満たす場合だけ次の処理を行う
        if status in ("", "unused"):
            # 現在の対象を終えて次の対象へ進む
            continue
        # 条件を満たす場合だけ次の処理を行う
        if status != "approved":
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                # 次の値または処理を現在の構造へ組み込む
                f"review_statusが不正です: 行{row_number}: {status!r}"
            )
        # 次の値または処理を現在の構造へ組み込む
        selected_count += 1
        # expression_idへこの工程で使用する値を設定する
        expression_id = row["expression_id"].strip()
        # candidateへこの工程で使用する値を設定する
        candidate = reviewed_candidates.get(expression_id)
        # 条件を満たす場合だけ次の処理を行う
        if candidate is None:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                # 次の値または処理を現在の構造へ組み込む
                f"approved行に対応する候補JSONLがありません: {expression_id}"
            )
        # 次の値または処理を現在の構造へ組み込む
        _validate_review_candidate(row, candidate, row_number=row_number)
        # expressionへこの工程で使用する値を設定する
        expression = (
            # 次の値または処理を現在の構造へ組み込む
            row["edited_expression_ja"].strip() or row["expression_ja"].strip()
        )
        # connectiveへこの工程で使用する値を設定する
        connective = (
            # 次の値または処理を現在の構造へ組み込む
            row["edited_connective_expression_ja"].strip()
            # 次の値または処理を現在の構造へ組み込む
            or row["connective_expression_ja"].strip()
        )
        # 条件を満たす場合だけ次の処理を行う
        if (
            # 次の値または処理を現在の構造へ組み込む
            row["expression_ja"].strip() != candidate["expression_ja"]
            # 次の値または処理を現在の構造へ組み込む
            or row["connective_expression_ja"].strip()
            # 次の値または処理を現在の構造へ組み込む
            != candidate["connective_expression_ja"]
        # 次の値または処理を現在の構造へ組み込む
        ):
            # 次の値または処理を現在の構造へ組み込む
            direct_edit_count += 1
        # pairへこの工程で使用する値を設定する
        pair = (row["operation_id"].strip(), expression, connective)
        # 条件を満たす場合だけ次の処理を行う
        if expression_id in approved_ids:
            # 現在の対象を終えて次の対象へ進む
            continue
        # 条件を満たす場合だけ次の処理を行う
        if pair in approved_pairs:
            # 次の値または処理を現在の構造へ組み込む
            duplicate_pair_count += 1
            # 現在の対象を終えて次の対象へ進む
            continue
        # normalizedへこの工程で使用する値を設定する
        normalized = dict(row)
        # 次の値または処理を現在の構造へ組み込む
        normalized["expression_ja"] = candidate["expression_ja"]
        # 次の値または処理を現在の構造へ組み込む
        normalized["connective_expression_ja"] = candidate[
            "connective_expression_ja"
        ]
        # 次の値または処理を現在の構造へ組み込む
        normalized["review_status"] = "approved"
        # 次の値または処理を現在の構造へ組み込む
        normalized["edited_expression_ja"] = (
            # 次の値または処理を現在の構造へ組み込む
            expression if expression != candidate["expression_ja"] else ""
        )
        # 次の値または処理を現在の構造へ組み込む
        normalized["edited_connective_expression_ja"] = (
            # 次の値または処理を現在の構造へ組み込む
            connective
            # 条件を満たす場合だけ次の処理を行う
            if connective != candidate["connective_expression_ja"]
            # それまでの条件に該当しない場合を処理する
            else ""
        )
        # 次の値または処理を現在の構造へ組み込む
        approved_rows.append(normalized)
        # 次の値または処理を現在の構造へ組み込む
        added_rows.append(normalized)
        # 次の値または処理を現在の構造へ組み込む
        approved_ids.add(expression_id)
        # 次の値または処理を現在の構造へ組み込む
        approved_pairs.add(pair)

    # provenanceへこの工程で使用する値を設定する
    provenance: dict[str, dict[str, Any]] = {}
    # 条件を満たす場合だけ次の処理を行う
    if args.approved_candidates_jsonl.is_file():
        # 次の値または処理を現在の構造へ組み込む
        provenance.update(
            # 次の値または処理を現在の構造へ組み込む
            _read_candidate_jsonl(args.approved_candidates_jsonl)
        )
    # 対象を一件ずつ取り出して処理する
    for path in args.provenance_jsonl:
        # 対象を一件ずつ取り出して処理する
        for expression_id, record in _read_candidate_jsonl(path).items():
            # 次の値または処理を現在の構造へ組み込む
            provenance.setdefault(expression_id, record)
    # 対象を一件ずつ取り出して処理する
    for row in added_rows:
        # expression_idへこの工程で使用する値を設定する
        expression_id = row["expression_id"].strip()
        # provenance[expression_id]へこの工程で使用する値を設定する
        provenance[expression_id] = reviewed_candidates[expression_id]

    # missing_idsへこの工程で使用する値を設定する
    missing_ids = sorted(approved_ids - set(provenance))
    # 条件を満たす場合だけ次の処理を行う
    if missing_ids:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            "承認済みIDに対応する候補生成履歴がありません: "
            # 次の値または処理を現在の構造へ組み込む
            + ", ".join(missing_ids)
        )
    # atomic番号順へ安定整列し、同じ操作内では従来の確認順を維持する
    approved_rows.sort(key=lambda row: row["operation_id"].strip())
    # CSVとJSONLを同じexpression_id順へ揃えて一行単位でも対応確認できるようにする
    ordered_candidates = [
        # 次の値または処理を現在の構造へ組み込む
        provenance[row["expression_id"].strip()] for row in approved_rows
    ]
    # 次の値または処理を現在の構造へ組み込む
    _write_review_csv(args.approved_review_csv, approved_fields, approved_rows)
    # 次の値または処理を現在の構造へ組み込む
    _write_candidate_jsonl(
        # 次の値または処理を現在の構造へ組み込む
        args.approved_candidates_jsonl,
        # 次の値または処理を現在の構造へ組み込む
        ordered_candidates,
    )
    # 処理結果を利用者へ表示する
    print(
        # 次の値または処理を現在の構造へ組み込む
        f"統合完了: reviewed_approved={selected_count}, "
        # 次の値または処理を現在の構造へ組み込む
        f"added={len(added_rows)}, duplicate_pairs={duplicate_pair_count}, "
        # 次の値または処理を現在の構造へ組み込む
        f"direct_edits={direct_edit_count}, "
        # 次の値または処理を現在の構造へ組み込む
        f"approved_total={len(approved_rows)}, "
        # 次の値または処理を現在の構造へ組み込む
        f"provenance_total={len(ordered_candidates)}"
    )


# この工程を担当する関数を定義する
def _read_review_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Excel由来の余分な先頭行も許容して確認CSVを読む。"""

    # 使用するリソースの開始と終了をこの範囲で管理する
    with path.open(encoding="utf-8-sig", newline="") as handle:
        # matrixへこの工程で使用する値を設定する
        matrix = list(csv.reader(handle))
    # header_indexへこの工程で使用する値を設定する
    header_index = next(
        # 次の値または処理を現在の構造へ組み込む
        (
            # 次の値または処理を現在の構造へ組み込む
            index
            # 対象を一件ずつ取り出して処理する
            for index, values in enumerate(matrix)
            # 条件を満たす場合だけ次の処理を行う
            if REQUIRED_REVIEW_FIELDS.issubset(values)
        ),
        # 次の値または処理を現在の構造へ組み込む
        None,
    )
    # 条件を満たす場合だけ次の処理を行う
    if header_index is None:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"確認CSVの実ヘッダーが見つかりません: {path}")
    # fieldsへこの工程で使用する値を設定する
    fields = matrix[header_index]
    # 条件を満たす場合だけ次の処理を行う
    if len(fields) != len(set(fields)):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"確認CSVのヘッダーが重複しています: {path}")
    # rowsへこの工程で使用する値を設定する
    rows: list[dict[str, str]] = []
    # 対象を一件ずつ取り出して処理する
    for row_number, values in enumerate(
        # 次の値または処理を現在の構造へ組み込む
        matrix[header_index + 1 :],
        # startへこの工程で使用する値を設定する
        start=header_index + 2,
    # 次の値または処理を現在の構造へ組み込む
    ):
        # 条件を満たす場合だけ次の処理を行う
        if not values or not any(value.strip() for value in values):
            # 現在の対象を終えて次の対象へ進む
            continue
        # 条件を満たす場合だけ次の処理を行う
        if len(values) > len(fields):
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"確認CSVの列数が不正です: {path}: 行{row_number}")
        # paddedへこの工程で使用する値を設定する
        padded = values + [""] * (len(fields) - len(values))
        # 次の値または処理を現在の構造へ組み込む
        rows.append(dict(zip(fields, padded)))
    # 処理結果を呼び出し元へ返す
    return fields, rows


# この工程を担当する関数を定義する
def _read_candidate_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    """候補JSONLをIDで引けるように読み、重複IDを拒否する。"""

    # recordsへこの工程で使用する値を設定する
    records: dict[str, dict[str, Any]] = {}
    # 使用するリソースの開始と終了をこの範囲で管理する
    with path.open(encoding="utf-8") as handle:
        # 対象を一件ずつ取り出して処理する
        for line_number, line in enumerate(handle, start=1):
            # 条件を満たす場合だけ次の処理を行う
            if not line.strip():
                # 現在の対象を終えて次の対象へ進む
                continue
            # valueへこの工程で使用する値を設定する
            value = json.loads(line)
            # 条件を満たす場合だけ次の処理を行う
            if not isinstance(value, dict):
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"候補JSONLの行がobjectではありません: {path}")
            # expression_idへこの工程で使用する値を設定する
            expression_id = value.get("expression_id")
            # 条件を満たす場合だけ次の処理を行う
            if not isinstance(expression_id, str) or not expression_id:
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(
                    # 次の値または処理を現在の構造へ組み込む
                    f"候補JSONLにexpression_idがありません: {path}: 行{line_number}"
                )
            # 条件を満たす場合だけ次の処理を行う
            if expression_id in records:
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(
                    # 次の値または処理を現在の構造へ組み込む
                    f"候補JSONLのexpression_idが重複しています: {expression_id}"
                )
            # records[expression_id]へこの工程で使用する値を設定する
            records[expression_id] = value
    # 処理結果を呼び出し元へ返す
    return records


# この工程を担当する関数を定義する
def _validate_review_candidate(
    # 次の値または処理を現在の構造へ組み込む
    row: dict[str, str],
    # 次の値または処理を現在の構造へ組み込む
    candidate: dict[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    *,
    # 次の値または処理を現在の構造へ組み込む
    row_number: int,
# 次の値または処理を現在の構造へ組み込む
) -> None:
    """レビュー行と候補JSONLが同じ操作を指すことを確認する。"""

    # 条件を満たす場合だけ次の処理を行う
    if row["operation_id"].strip() != candidate.get("operation_id"):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"確認CSVと候補JSONLのoperation_idが一致しません: 行{row_number}"
        )
    # 対象を一件ずつ取り出して処理する
    for key in ("expression_ja", "connective_expression_ja"):
        # 条件を満たす場合だけ次の処理を行う
        if not row[key].strip():
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"確認CSVの{key}が空です: 行{row_number}")


# この工程を担当する関数を定義する
def _effective_pair(row: dict[str, str]) -> tuple[str, str, str]:
    """人間修正版を優先した操作ID・終止形・接続形を返す。"""

    # expressionへこの工程で使用する値を設定する
    expression = row["edited_expression_ja"].strip() or row[
        "expression_ja"
    # 次の値または処理を現在の構造へ組み込む
    ].strip()
    # connectiveへこの工程で使用する値を設定する
    connective = row["edited_connective_expression_ja"].strip() or row[
        "connective_expression_ja"
    # 次の値または処理を現在の構造へ組み込む
    ].strip()
    # 処理結果を呼び出し元へ返す
    return row["operation_id"].strip(), expression, connective


# この工程を担当する関数を定義する
def _write_review_csv(
    # 次の値または処理を現在の構造へ組み込む
    path: Path,
    # 次の値または処理を現在の構造へ組み込む
    fields: list[str],
    # 次の値または処理を現在の構造へ組み込む
    rows: list[dict[str, str]],
# 次の値または処理を現在の構造へ組み込む
) -> None:
    """承認CSVを一時ファイル経由で置き換える。"""

    # temporaryへこの工程で使用する値を設定する
    temporary = path.with_suffix(path.suffix + ".tmp")
    # 使用するリソースの開始と終了をこの範囲で管理する
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        # writerへこの工程で使用する値を設定する
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        # 次の値または処理を現在の構造へ組み込む
        writer.writeheader()
        # 次の値または処理を現在の構造へ組み込む
        writer.writerows(rows)
    # 次の値または処理を現在の構造へ組み込む
    temporary.replace(path)


# この工程を担当する関数を定義する
def _write_candidate_jsonl(
    # 次の値または処理を現在の構造へ組み込む
    path: Path,
    # 次の値または処理を現在の構造へ組み込む
    records: list[dict[str, Any]],
# 次の値または処理を現在の構造へ組み込む
) -> None:
    """承認候補JSONLを一時ファイル経由で置き換える。"""

    # 次の値または処理を現在の構造へ組み込む
    path.parent.mkdir(parents=True, exist_ok=True)
    # temporaryへこの工程で使用する値を設定する
    temporary = path.with_suffix(path.suffix + ".tmp")
    # 使用するリソースの開始と終了をこの範囲で管理する
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        # 対象を一件ずつ取り出して処理する
        for record in records:
            # 次の値または処理を現在の構造へ組み込む
            handle.write(
                # 次の値または処理を現在の構造へ組み込む
                json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                # 次の値または処理を現在の構造へ組み込む
                + "\n"
            )
    # 次の値または処理を現在の構造へ組み込む
    temporary.replace(path)


# 条件を満たす場合だけ次の処理を行う
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    main()
