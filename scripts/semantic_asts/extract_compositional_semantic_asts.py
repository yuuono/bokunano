"""既存の12,720件から組合せ汎化テスト用の意味ASTを670件抽出する。"""

# この処理で使う標準または外部モジュールを読み込む
import json
# 必要な定義を対象モジュールから読み込む
from pathlib import Path


# PROJECT_ROOTへこの工程で使用する値を設定する
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# DATA_DIRへこの工程で使用する値を設定する
DATA_DIR = PROJECT_ROOT / "data" / "semantic_asts"
# ATOMIC_PATHへこの工程で使用する値を設定する
ATOMIC_PATH = DATA_DIR / "atomic_semantic_asts.jsonl"
# COMBINED_PATHへこの工程で使用する値を設定する
COMBINED_PATH = DATA_DIR / "combined_semantic_asts.jsonl"
# OUTPUT_PATHへこの工程で使用する値を設定する
OUTPUT_PATH = DATA_DIR / "compositional_semantic_asts.jsonl"

# 方針文書で確定した、互いに単独操作を共有しない5ペア
PAIR_ATOMIC_IDS = {
    # 出力レコードの項目と値を設定する
    "pair-01": ("atomic-000001", "atomic-000020"),
    # 出力レコードの項目と値を設定する
    "pair-02": ("atomic-000002", "atomic-000011"),
    # 出力レコードの項目と値を設定する
    "pair-03": ("atomic-000004", "atomic-000023"),
    # 出力レコードの項目と値を設定する
    "pair-04": ("atomic-000014", "atomic-000021"),
    # 出力レコードの項目と値を設定する
    "pair-05": ("atomic-000017", "atomic-000024"),
}

# EXPECTED_COMBINED_COUNTへこの工程で使用する値を設定する
EXPECTED_COMBINED_COUNT = 12_720
# EXPECTED_COUNTS_PER_PAIRへこの工程で使用する値を設定する
EXPECTED_COUNTS_PER_PAIR = {2: 2, 3: 132}
# EXPECTED_TOTAL_COUNTSへこの工程で使用する値を設定する
EXPECTED_TOTAL_COUNTS = {2: 10, 3: 660}


# この工程を担当する関数を定義する
def canonical_json(value: object) -> str:
    """JSON値を比較に使える決定的な文字列へ変換する。"""

    # 処理結果を呼び出し元へ返す
    return json.dumps(
        # 次の値または処理を現在の構造へ組み込む
        value,
        # sort_keysへこの工程で使用する値を設定する
        sort_keys=True,
        # ensure_asciiへこの工程で使用する値を設定する
        ensure_ascii=False,
        # separatorsへこの工程で使用する値を設定する
        separators=(",", ":"),
    )


# この工程を担当する関数を定義する
def load_jsonl(path: Path) -> list[dict]:
    """空行を無視してJSONLを読み込む。"""

    # 使用するリソースの開始と終了をこの範囲で管理する
    with path.open(encoding="utf-8") as source:
        # 処理結果を呼び出し元へ返す
        return [json.loads(line) for line in source if line.strip()]


# この工程を担当する関数を定義する
def load_pair_operation_keys(path: Path) -> dict[str, frozenset[str]]:
    """atomic IDで指定された5ペアを意味ASTの比較キーへ変換する。"""

    # atomic_recordsへこの工程で使用する値を設定する
    atomic_records = load_jsonl(path)
    # 条件を満たす場合だけ次の処理を行う
    if len(atomic_records) != 24:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"単独操作は24件必要です: {len(atomic_records)}件")

    # operation_by_idへこの工程で使用する値を設定する
    operation_by_id = {}
    # 対象を一件ずつ取り出して処理する
    for record in atomic_records:
        # spec_idへこの工程で使用する値を設定する
        spec_id = record.get("spec_id")
        # operationへこの工程で使用する値を設定する
        operation = record.get("semantic_ast")
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(spec_id, str):
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"単独操作のspec_idが不正です: {record!r}")
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(operation, dict) or len(operation) != 1:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"単独操作の意味ASTが不正です: {record!r}")
        # 条件を満たす場合だけ次の処理を行う
        if spec_id in operation_by_id:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"単独操作のspec_idが重複しています: {spec_id}")
        # operation_by_id[spec_id]へこの工程で使用する値を設定する
        operation_by_id[spec_id] = canonical_json(operation)

    # pair_operation_keysへこの工程で使用する値を設定する
    pair_operation_keys = {}
    # used_atomic_idsへこの工程で使用する値を設定する
    used_atomic_ids = []
    # 対象を一件ずつ取り出して処理する
    for pair_id, atomic_ids in PAIR_ATOMIC_IDS.items():
        # missingへこの工程で使用する値を設定する
        missing = [atomic_id for atomic_id in atomic_ids if atomic_id not in operation_by_id]
        # 条件を満たす場合だけ次の処理を行う
        if missing:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"{pair_id}の単独操作が見つかりません: {missing}")

        # pair_operation_keys[pair_id]へこの工程で使用する値を設定する
        pair_operation_keys[pair_id] = frozenset(
            # 次の値または処理を現在の構造へ組み込む
            operation_by_id[atomic_id] for atomic_id in atomic_ids
        )
        # 次の値または処理を現在の構造へ組み込む
        used_atomic_ids.extend(atomic_ids)

    # 条件を満たす場合だけ次の処理を行う
    if len(used_atomic_ids) != len(set(used_atomic_ids)):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("5ペアの間で単独操作が重複しています")

    # 処理結果を呼び出し元へ返す
    return pair_operation_keys


# この工程を担当する関数を定義する
def matching_pair_ids(
    # 次の値または処理を現在の構造へ組み込む
    semantic_ast: dict,
    # 次の値または処理を現在の構造へ組み込む
    pair_operation_keys: dict[str, frozenset[str]],
# 次の値または処理を現在の構造へ組み込む
) -> list[str]:
    """意味ASTが両方の操作を含むペアIDを返す。"""

    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(semantic_ast, dict) or set(semantic_ast) != {"sequence"}:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"意味ASTの形式が不正です: {semantic_ast!r}")

    # sequenceへこの工程で使用する値を設定する
    sequence = semantic_ast["sequence"]
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(sequence, list) or not 1 <= len(sequence) <= 3:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"sequenceの形式が不正です: {sequence!r}")

    # operation_keysへこの工程で使用する値を設定する
    operation_keys = [canonical_json(operation) for operation in sequence]
    # 条件を満たす場合だけ次の処理を行う
    if len(operation_keys) != len(set(operation_keys)):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"既存12,720件に反復操作が含まれています: {semantic_ast!r}")

    # operation_key_setへこの工程で使用する値を設定する
    operation_key_set = set(operation_keys)
    # 処理結果を呼び出し元へ返す
    return [
        # 次の値または処理を現在の構造へ組み込む
        pair_id
        # 対象を一件ずつ取り出して処理する
        for pair_id, pair_keys in pair_operation_keys.items()
        # 条件を満たす場合だけ次の処理を行う
        if pair_keys <= operation_key_set
    ]


# この工程を担当する関数を定義する
def extract_records(
    # 次の値または処理を現在の構造へ組み込む
    combined_records: list[dict],
    # 次の値または処理を現在の構造へ組み込む
    pair_operation_keys: dict[str, frozenset[str]],
# 次の値または処理を現在の構造へ組み込む
) -> list[dict]:
    """5ペアのいずれかを含む2操作・3操作ASTを抽出する。"""

    # extractedへこの工程で使用する値を設定する
    extracted = []
    # 対象を一件ずつ取り出して処理する
    for record in combined_records:
        # semantic_astへこの工程で使用する値を設定する
        semantic_ast = record.get("semantic_ast")
        # matched_pair_idsへこの工程で使用する値を設定する
        matched_pair_ids = matching_pair_ids(semantic_ast, pair_operation_keys)
        # 条件を満たす場合だけ次の処理を行う
        if not matched_pair_ids:
            # 現在の対象を終えて次の対象へ進む
            continue
        # 条件を満たす場合だけ次の処理を行う
        if len(matched_pair_ids) != 1:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                # 次の値または処理を現在の構造へ組み込む
                f"1件の意味ASTが複数ペアに一致しました: "
                # 次の値または処理を現在の構造へ組み込む
                f"{record.get('spec_id')}, {matched_pair_ids}"
            )

        # 次の値または処理を現在の構造へ組み込む
        extracted.append(
            # 次の値または処理を現在の構造へ組み込む
            {
                # 出力レコードの項目と値を設定する
                "spec_id": record["spec_id"],
                # 出力レコードの項目と値を設定する
                "semantic_ast": semantic_ast,
                # 出力レコードの項目と値を設定する
                "test_suite": "compositional",
            }
        )

    # 処理結果を呼び出し元へ返す
    return extracted


# この工程を担当する関数を定義する
def validate_records(
    # 次の値または処理を現在の構造へ組み込む
    combined_records: list[dict],
    # 次の値または処理を現在の構造へ組み込む
    extracted_records: list[dict],
    # 次の値または処理を現在の構造へ組み込む
    pair_operation_keys: dict[str, frozenset[str]],
# 次の値または処理を現在の構造へ組み込む
) -> None:
    """入力件数、抽出件数、ペア別内訳、重複を検証する。"""

    # 条件を満たす場合だけ次の処理を行う
    if len(combined_records) != EXPECTED_COMBINED_COUNT:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"既存の組み合わせASTは{EXPECTED_COMBINED_COUNT}件必要です: "
            # 次の値または処理を現在の構造へ組み込む
            f"{len(combined_records)}件"
        )

    # expected_totalへこの工程で使用する値を設定する
    expected_total = sum(EXPECTED_TOTAL_COUNTS.values())
    # 条件を満たす場合だけ次の処理を行う
    if len(extracted_records) != expected_total:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"抽出件数が不正です: 期待={expected_total}件, "
            # 次の値または処理を現在の構造へ組み込む
            f"実際={len(extracted_records)}件"
        )

    # spec_idsへこの工程で使用する値を設定する
    spec_ids = [record.get("spec_id") for record in extracted_records]
    # 条件を満たす場合だけ次の処理を行う
    if len(spec_ids) != len(set(spec_ids)):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("抽出後のspec_idが重複しています")

    # semantic_astsへこの工程で使用する値を設定する
    semantic_asts = [canonical_json(record.get("semantic_ast")) for record in extracted_records]
    # 条件を満たす場合だけ次の処理を行う
    if len(semantic_asts) != len(set(semantic_asts)):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("抽出後の意味ASTが重複しています")

    # total_countsへこの工程で使用する値を設定する
    total_counts = {2: 0, 3: 0}
    # pair_countsへこの工程で使用する値を設定する
    pair_counts = {
        # 次の値または処理を現在の構造へ組み込む
        pair_id: {2: 0, 3: 0}
        # 対象を一件ずつ取り出して処理する
        for pair_id in PAIR_ATOMIC_IDS
    }

    # 対象を一件ずつ取り出して処理する
    for record in extracted_records:
        # 条件を満たす場合だけ次の処理を行う
        if record.get("test_suite") != "compositional":
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"test_suiteが不正です: {record!r}")

        # semantic_astへこの工程で使用する値を設定する
        semantic_ast = record["semantic_ast"]
        # operation_countへこの工程で使用する値を設定する
        operation_count = len(semantic_ast["sequence"])
        # 条件を満たす場合だけ次の処理を行う
        if operation_count not in (2, 3):
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"操作数が不正です: {record!r}")

        # matched_pair_idsへこの工程で使用する値を設定する
        matched_pair_ids = matching_pair_ids(semantic_ast, pair_operation_keys)
        # 条件を満たす場合だけ次の処理を行う
        if len(matched_pair_ids) != 1:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"ペア一致数が不正です: {record!r}")

        # 次の値または処理を現在の構造へ組み込む
        total_counts[operation_count] += 1
        # 次の値または処理を現在の構造へ組み込む
        pair_counts[matched_pair_ids[0]][operation_count] += 1

    # 条件を満たす場合だけ次の処理を行う
    if total_counts != EXPECTED_TOTAL_COUNTS:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"操作数別件数が不正です: 期待={EXPECTED_TOTAL_COUNTS}, "
            # 次の値または処理を現在の構造へ組み込む
            f"実際={total_counts}"
        )

    # 対象を一件ずつ取り出して処理する
    for pair_id, counts in pair_counts.items():
        # 条件を満たす場合だけ次の処理を行う
        if counts != EXPECTED_COUNTS_PER_PAIR:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                # 次の値または処理を現在の構造へ組み込む
                f"{pair_id}の件数が不正です: "
                # 次の値または処理を現在の構造へ組み込む
                f"期待={EXPECTED_COUNTS_PER_PAIR}, 実際={counts}"
            )


# この工程を担当する関数を定義する
def save_jsonl(records: list[dict], path: Path) -> None:
    """抽出済みレコードを元ファイルと同じ順序で保存する。"""

    # 使用するリソースの開始と終了をこの範囲で管理する
    with path.open("w", encoding="utf-8", newline="\n") as destination:
        # 対象を一件ずつ取り出して処理する
        for record in records:
            # 次の値または処理を現在の構造へ組み込む
            destination.write(
                # 次の値または処理を現在の構造へ組み込む
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )


# この工程を担当する関数を定義する
def main() -> None:
    # pair_operation_keysへこの工程で使用する値を設定する
    pair_operation_keys = load_pair_operation_keys(ATOMIC_PATH)
    # combined_recordsへこの工程で使用する値を設定する
    combined_records = load_jsonl(COMBINED_PATH)
    # extracted_recordsへこの工程で使用する値を設定する
    extracted_records = extract_records(combined_records, pair_operation_keys)
    # 次の値または処理を現在の構造へ組み込む
    validate_records(combined_records, extracted_records, pair_operation_keys)
    # 次の値または処理を現在の構造へ組み込む
    save_jsonl(extracted_records, OUTPUT_PATH)

    # 処理結果を利用者へ表示する
    print(
        # 次の値または処理を現在の構造へ組み込む
        f"{OUTPUT_PATH} に{len(extracted_records)}件保存しました"
        # 次の値または処理を現在の構造へ組み込む
        f"（2操作={EXPECTED_TOTAL_COUNTS[2]}件, "
        # 次の値または処理を現在の構造へ組み込む
        f"3操作={EXPECTED_TOTAL_COUNTS[3]}件, "
        # 次の値または処理を現在の構造へ組み込む
        f"各ペア=134件）"
    )


# 条件を満たす場合だけ次の処理を行う
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    main()
