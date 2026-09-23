"""承認済み表現を整理し、GitHub公開用のCSVと来歴JSONLを作る。"""

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


# REVIEW_FIELDSへこの工程で使用する値を設定する
REVIEW_FIELDS = [
    # この処理で扱う文字列を一覧へ加える
    "expression_id",
    # この処理で扱う文字列を一覧へ加える
    "operation_id",
    # この処理で扱う文字列を一覧へ加える
    "operation_ast",
    # この処理で扱う文字列を一覧へ加える
    "canonical_meaning_ja",
    # この処理で扱う文字列を一覧へ加える
    "must_preserve_ja",
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
    # この処理で扱う文字列を一覧へ加える
    "dictionary",
    # この処理で扱う文字列を一覧へ加える
    "reviewer",
    # この処理で扱う文字列を一覧へ加える
    "reviewed_at",
]
# RELEASE_FIELDSへこの工程で使用する値を設定する
RELEASE_FIELDS = [
    # この処理で扱う文字列を一覧へ加える
    "expression_id",
    # この処理で扱う文字列を一覧へ加える
    "operation_id",
    # この処理で扱う文字列を一覧へ加える
    "operation_ast",
    # この処理で扱う文字列を一覧へ加える
    "canonical_meaning_ja",
    # この処理で扱う文字列を一覧へ加える
    "must_preserve_ja",
    # この処理で扱う文字列を一覧へ加える
    "expression_ja",
    # この処理で扱う文字列を一覧へ加える
    "connective_expression_ja",
]
# RELEASE_CSV_NAMEへこの工程で使用する値を設定する
RELEASE_CSV_NAME = "japanese_atomic_expressions.csv"
# RELEASE_JSONL_NAMEへこの工程で使用する値を設定する
RELEASE_JSONL_NAME = "japanese_atomic_expression_provenance.jsonl"


# この工程を担当する関数を定義する
def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""

    # parserへこの工程で使用する値を設定する
    parser = argparse.ArgumentParser(
        # descriptionへこの工程で使用する値を設定する
        description=(
            "承認済み表現と生成来歴を検証し、公開専用ディレクトリへ出力します。"
        )
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--review-csv", required=True, type=Path)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--candidate-jsonl", required=True, type=Path)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--release-directory", required=True, type=Path)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--prune-unused",
        # actionへこの工程で使用する値を設定する
        action="store_true",
        # helpへこの工程で使用する値を設定する
        help=(
            "review_status=unusedの行を承認CSVと承認候補JSONLから除き、"
            "承認CSVの余分な先頭行も除去します。"
        ),
    )
    # 処理結果を呼び出し元へ返す
    return parser.parse_args()


# この工程を担当する関数を定義する
def main() -> None:
    """承認済みマスターを整理し、公開成果物を作る。"""

    # argsへこの工程で使用する値を設定する
    args = parse_args()
    # resultへこの工程で使用する値を設定する
    result = prepare_release(
        # review_csvへこの工程で使用する値を設定する
        review_csv=args.review_csv,
        # candidate_jsonlへこの工程で使用する値を設定する
        candidate_jsonl=args.candidate_jsonl,
        # release_directoryへこの工程で使用する値を設定する
        release_directory=args.release_directory,
        # prune_unusedへこの工程で使用する値を設定する
        prune_unused=args.prune_unused,
    )
    # 処理結果を利用者へ表示する
    print(
        # 次の値または処理を現在の構造へ組み込む
        f"公開用辞書を作成しました: approved={result['approved']}, "
        # 次の値または処理を現在の構造へ組み込む
        f"removed_unused={result['removed_unused']}, "
        # 次の値または処理を現在の構造へ組み込む
        f"human_edited={result['human_edited']}"
    )


# この工程を担当する関数を定義する
def prepare_release(
    # 次の値または処理を現在の構造へ組み込む
    *,
    # 次の値または処理を現在の構造へ組み込む
    review_csv: Path,
    # 次の値または処理を現在の構造へ組み込む
    candidate_jsonl: Path,
    # 次の値または処理を現在の構造へ組み込む
    release_directory: Path,
    # 次の値または処理を現在の構造へ組み込む
    prune_unused: bool,
# 次の値または処理を現在の構造へ組み込む
) -> dict[str, int]:
    """入力を相互検証し、承認済みマスターと公開成果物を同時に整える。"""

    # 次の値または処理を現在の構造へ組み込む
    fields, rows = _read_review_csv(review_csv)
    # missing_fieldsへこの工程で使用する値を設定する
    missing_fields = [field for field in REVIEW_FIELDS if field not in fields]
    # 条件を満たす場合だけ次の処理を行う
    if missing_fields:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 出力レコードの項目と値を設定する
            "承認CSVに必須列がありません: " + ", ".join(missing_fields)
        )

    # candidatesへこの工程で使用する値を設定する
    candidates = _read_jsonl_by_id(candidate_jsonl)
    # approved_rowsへこの工程で使用する値を設定する
    approved_rows: list[dict[str, str]] = []
    # unused_rowsへこの工程で使用する値を設定する
    unused_rows: list[dict[str, str]] = []
    # seen_idsへこの工程で使用する値を設定する
    seen_ids: set[str] = set()
    # seen_pairsへこの工程で使用する値を設定する
    seen_pairs: set[tuple[str, str, str]] = set()
    # human_editedへこの工程で使用する値を設定する
    human_edited = 0

    # 対象を一件ずつ取り出して処理する
    for row_number, row in enumerate(rows, start=2):
        # expression_idへこの工程で使用する値を設定する
        expression_id = row["expression_id"].strip()
        # 条件を満たす場合だけ次の処理を行う
        if not expression_id:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"expression_idが空です: 行{row_number}")
        # 条件を満たす場合だけ次の処理を行う
        if expression_id in seen_ids:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"expression_idが重複しています: {expression_id}")
        # 次の値または処理を現在の構造へ組み込む
        seen_ids.add(expression_id)

        # statusへこの工程で使用する値を設定する
        status = row["review_status"].strip().lower()
        # 条件を満たす場合だけ次の処理を行う
        if status == "unused":
            # 次の値または処理を現在の構造へ組み込む
            unused_rows.append(row)
            # 現在の対象を終えて次の対象へ進む
            continue
        # 条件を満たす場合だけ次の処理を行う
        if status != "approved":
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                # 次の値または処理を現在の構造へ組み込む
                f"review_statusはapprovedまたはunusedが必要です: "
                # 次の値または処理を現在の構造へ組み込む
                f"行{row_number}: {status!r}"
            )

        # candidateへこの工程で使用する値を設定する
        candidate = candidates.get(expression_id)
        # 条件を満たす場合だけ次の処理を行う
        if candidate is None:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                # 次の値または処理を現在の構造へ組み込む
                f"承認行に対応する候補JSONLがありません: {expression_id}"
            )
        # operation_idへこの工程で使用する値を設定する
        operation_id = row["operation_id"].strip()
        # 条件を満たす場合だけ次の処理を行う
        if candidate.get("operation_id") != operation_id:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                # 次の値または処理を現在の構造へ組み込む
                f"CSVとJSONLのoperation_idが一致しません: {expression_id}"
            )
        # 次の値または処理を現在の構造へ組み込む
        expression, connective = _effective_expressions(row)
        # 条件を満たす場合だけ次の処理を行う
        if not expression or not connective:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"最終表現が空です: {expression_id}")
        # pairへこの工程で使用する値を設定する
        pair = (operation_id, expression, connective)
        # 条件を満たす場合だけ次の処理を行う
        if pair in seen_pairs:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                "同じ操作の最終表現が重複しています: "
                # 次の値または処理を現在の構造へ組み込む
                f"{operation_id}: {expression!r}, {connective!r}"
            )
        # 次の値または処理を現在の構造へ組み込む
        seen_pairs.add(pair)
        # 条件を満たす場合だけ次の処理を行う
        if row["edited_expression_ja"].strip() or row[
            "edited_connective_expression_ja"
        # 次の値または処理を現在の構造へ組み込む
        ].strip():
            # 次の値または処理を現在の構造へ組み込む
            human_edited += 1
        # 次の値または処理を現在の構造へ組み込む
        approved_rows.append(row)

    # 条件を満たす場合だけ次の処理を行う
    if unused_rows and not prune_unused:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"unusedが{len(unused_rows)}件あります。削除する場合は"
            "--prune-unusedを指定してください"
        )

    # 次の値または処理を現在の構造へ組み込む
    approved_rows.sort(key=lambda row: row["operation_id"].strip())
    # approved_idsへこの工程で使用する値を設定する
    approved_ids = [row["expression_id"].strip() for row in approved_rows]
    # approved_candidatesへこの工程で使用する値を設定する
    approved_candidates = [candidates[expression_id] for expression_id in approved_ids]

    # release_rowsへこの工程で使用する値を設定する
    release_rows = [_release_row(row) for row in approved_rows]
    # release_recordsへこの工程で使用する値を設定する
    release_records = [
        # 次の値または処理を現在の構造へ組み込む
        _release_provenance(row, candidate)
        # 対象を一件ずつ取り出して処理する
        for row, candidate in zip(approved_rows, approved_candidates, strict=True)
    ]

    # 条件を満たす場合だけ次の処理を行う
    if prune_unused:
        # 次の値または処理を現在の構造へ組み込む
        _write_csv(review_csv, fields, approved_rows)
        # 次の値または処理を現在の構造へ組み込む
        _write_jsonl(candidate_jsonl, approved_candidates)

    # 次の値または処理を現在の構造へ組み込む
    release_directory.mkdir(parents=True, exist_ok=True)
    # 次の値または処理を現在の構造へ組み込む
    _write_csv(
        # 次の値または処理を現在の構造へ組み込む
        release_directory / RELEASE_CSV_NAME,
        # 次の値または処理を現在の構造へ組み込む
        RELEASE_FIELDS,
        # 次の値または処理を現在の構造へ組み込む
        release_rows,
    )
    # 次の値または処理を現在の構造へ組み込む
    _write_jsonl(
        # 次の値または処理を現在の構造へ組み込む
        release_directory / RELEASE_JSONL_NAME,
        # 次の値または処理を現在の構造へ組み込む
        release_records,
    )
    # 処理結果を呼び出し元へ返す
    return {
        # 出力レコードの項目と値を設定する
        "approved": len(approved_rows),
        # 出力レコードの項目と値を設定する
        "removed_unused": len(unused_rows),
        # 出力レコードの項目と値を設定する
        "human_edited": human_edited,
    }


# この工程を担当する関数を定義する
def _read_review_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Excel由来の余分な先頭行を許容してレビューCSVを読む。"""

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
            if {"expression_id", "review_status"}.issubset(values)
        ),
        # 次の値または処理を現在の構造へ組み込む
        None,
    )
    # 条件を満たす場合だけ次の処理を行う
    if header_index is None:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"承認CSVの実ヘッダーが見つかりません: {path}")
    # fieldsへこの工程で使用する値を設定する
    fields = matrix[header_index]
    # rowsへこの工程で使用する値を設定する
    rows: list[dict[str, str]] = []
    # 対象を一件ずつ取り出して処理する
    for row_number, values in enumerate(
        # 次の値または処理を現在の構造へ組み込む
        matrix[header_index + 1 :], start=header_index + 2
    # 次の値または処理を現在の構造へ組み込む
    ):
        # 条件を満たす場合だけ次の処理を行う
        if not values or not any(value.strip() for value in values):
            # 現在の対象を終えて次の対象へ進む
            continue
        # 条件を満たす場合だけ次の処理を行う
        if len(values) > len(fields):
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"承認CSVの列数が不正です: {path}: 行{row_number}")
        # paddedへこの工程で使用する値を設定する
        padded = values + [""] * (len(fields) - len(values))
        # 次の値または処理を現在の構造へ組み込む
        rows.append(dict(zip(fields, padded, strict=True)))
    # 処理結果を呼び出し元へ返す
    return fields, rows


# この工程を担当する関数を定義する
def _read_jsonl_by_id(path: Path) -> dict[str, dict[str, Any]]:
    """JSONLをexpression_idで索引し、重複IDを拒否する。"""

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
            # recordへこの工程で使用する値を設定する
            record = json.loads(line)
            # 条件を満たす場合だけ次の処理を行う
            if not isinstance(record, dict):
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"JSONLの行がobjectではありません: 行{line_number}")
            # expression_idへこの工程で使用する値を設定する
            expression_id = record.get("expression_id")
            # 条件を満たす場合だけ次の処理を行う
            if not isinstance(expression_id, str) or not expression_id:
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"JSONLにexpression_idがありません: 行{line_number}")
            # 条件を満たす場合だけ次の処理を行う
            if expression_id in records:
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"JSONLのIDが重複しています: {expression_id}")
            # records[expression_id]へこの工程で使用する値を設定する
            records[expression_id] = record
    # 処理結果を呼び出し元へ返す
    return records


# この工程を担当する関数を定義する
def _effective_expressions(row: dict[str, str]) -> tuple[str, str]:
    """人間修正版を優先した終止形と接続形を返す。"""

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
    return expression, connective


# この工程を担当する関数を定義する
def _release_row(row: dict[str, str]) -> dict[str, str]:
    """レビュー列を除き、人間修正を反映した公開CSV行を作る。"""

    # 次の値または処理を現在の構造へ組み込む
    expression, connective = _effective_expressions(row)
    # releasedへこの工程で使用する値を設定する
    released = {field: row[field].strip() for field in RELEASE_FIELDS}
    # 次の値または処理を現在の構造へ組み込む
    released["expression_ja"] = expression
    # 次の値または処理を現在の構造へ組み込む
    released["connective_expression_ja"] = connective
    # 処理結果を呼び出し元へ返す
    return released


# この工程を担当する関数を定義する
def _release_provenance(
    # 次の値または処理を現在の構造へ組み込む
    row: dict[str, str], candidate: dict[str, Any]
# 次の値または処理を現在の構造へ組み込む
) -> dict[str, Any]:
    """最終表現と変更前の生成レコードを分離した公開来歴を作る。"""

    # 次の値または処理を現在の構造へ組み込む
    expression, connective = _effective_expressions(row)
    # 処理結果を呼び出し元へ返す
    return {
        # 出力レコードの項目と値を設定する
        "expression_id": row["expression_id"].strip(),
        # 出力レコードの項目と値を設定する
        "operation_id": row["operation_id"].strip(),
        # 出力レコードの項目と値を設定する
        "approved_expression_ja": expression,
        # 出力レコードの項目と値を設定する
        "approved_connective_expression_ja": connective,
        # 出力レコードの項目と値を設定する
        "human_edited": bool(
            # 次の値または処理を現在の構造へ組み込む
            row["edited_expression_ja"].strip()
            # 次の値または処理を現在の構造へ組み込む
            or row["edited_connective_expression_ja"].strip()
        ),
        # 出力レコードの項目と値を設定する
        "generation_record": candidate,
    }


# この工程を担当する関数を定義する
def _write_csv(
    # 次の値または処理を現在の構造へ組み込む
    path: Path, fields: list[str], rows: list[dict[str, str]]
# 次の値または処理を現在の構造へ組み込む
) -> None:
    """CSVを一時ファイル経由で置き換える。"""

    # 次の値または処理を現在の構造へ組み込む
    path.parent.mkdir(parents=True, exist_ok=True)
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
def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """JSONLを一時ファイル経由で置き換える。"""

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
