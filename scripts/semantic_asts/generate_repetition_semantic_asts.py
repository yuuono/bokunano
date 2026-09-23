"""同一操作が隣接する反復汎化テスト用の意味ASTを1,152件生成する。"""

# この処理で使う標準または外部モジュールを読み込む
import json
# 必要な定義を対象モジュールから読み込む
from pathlib import Path


# PROJECT_ROOTへこの工程で使用する値を設定する
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# DATA_DIRへこの工程で使用する値を設定する
DATA_DIR = PROJECT_ROOT / "data" / "semantic_asts"
# INPUT_PATHへこの工程で使用する値を設定する
INPUT_PATH = DATA_DIR / "atomic_semantic_asts.jsonl"
# OUTPUT_PATHへこの工程で使用する値を設定する
OUTPUT_PATH = DATA_DIR / "repetition_semantic_asts.jsonl"
# EXPECTED_COUNTSへこの工程で使用する値を設定する
EXPECTED_COUNTS = {
    # 出力レコードの項目と値を設定する
    "A → A": 24,
    # 出力レコードの項目と値を設定する
    "A → A → B": 552,
    # 出力レコードの項目と値を設定する
    "B → A → A": 552,
    # 出力レコードの項目と値を設定する
    "A → A → A": 24,
}


# この工程を担当する関数を定義する
def canonical_operation(operation: dict) -> str:
    """操作を重複確認に使える決定的な文字列へ変換する。"""

    # 処理結果を呼び出し元へ返す
    return json.dumps(
        # 次の値または処理を現在の構造へ組み込む
        operation,
        # sort_keysへこの工程で使用する値を設定する
        sort_keys=True,
        # ensure_asciiへこの工程で使用する値を設定する
        ensure_ascii=False,
        # separatorsへこの工程で使用する値を設定する
        separators=(",", ":"),
    )


# この工程を担当する関数を定義する
def load_atomic_operations(path: Path) -> list[dict]:
    """24個の単独操作を読み込み、形式と重複を検証する。"""

    # 使用するリソースの開始と終了をこの範囲で管理する
    with path.open(encoding="utf-8") as source:
        # recordsへこの工程で使用する値を設定する
        records = [json.loads(line) for line in source if line.strip()]

    # 条件を満たす場合だけ次の処理を行う
    if len(records) != 24:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"単独操作は24件必要です: {len(records)}件")

    # operationsへこの工程で使用する値を設定する
    operations = []
    # 対象を一件ずつ取り出して処理する
    for record in records:
        # operationへこの工程で使用する値を設定する
        operation = record.get("semantic_ast")
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(operation, dict) or len(operation) != 1:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"単独操作の形式が不正です: {record!r}")
        # 次の値または処理を現在の構造へ組み込む
        operations.append(operation)

    # operation_keysへこの工程で使用する値を設定する
    operation_keys = [canonical_operation(operation) for operation in operations]
    # 条件を満たす場合だけ次の処理を行う
    if len(operation_keys) != len(set(operation_keys)):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("単独操作の意味ASTが重複しています")

    # 処理結果を呼び出し元へ返す
    return operations


# この工程を担当する関数を定義する
def make_record(record_number: int, operations: list[dict]) -> dict:
    """反復汎化テスト用の1レコードを作る。"""

    # 処理結果を呼び出し元へ返す
    return {
        # 出力レコードの項目と値を設定する
        "spec_id": f"repetition-{record_number:06d}",
        # 出力レコードの項目と値を設定する
        "semantic_ast": {"sequence": operations},
        # 出力レコードの項目と値を設定する
        "test_suite": "repetition",
    }


# この工程を担当する関数を定義する
def generate_records(atomic_operations: list[dict]) -> list[dict]:
    """方針文書で定めた4形式を決定的な順序で列挙する。"""

    # recordsへこの工程で使用する値を設定する
    records = []

    # 2操作: A → A
    for operation_a in atomic_operations:
        # 次の値または処理を現在の構造へ組み込む
        records.append(make_record(len(records) + 1, [operation_a, operation_a]))

    # 3操作: A → A → B と B → A → A（AとBは異なる）
    for operation_a in atomic_operations:
        # 対象を一件ずつ取り出して処理する
        for operation_b in atomic_operations:
            # 条件を満たす場合だけ次の処理を行う
            if operation_a == operation_b:
                # 現在の対象を終えて次の対象へ進む
                continue
            # 次の値または処理を現在の構造へ組み込む
            records.append(
                # 次の値または処理を現在の構造へ組み込む
                make_record(
                    # 次の値または処理を現在の構造へ組み込む
                    len(records) + 1,
                    # 次の値または処理を現在の構造へ組み込む
                    [operation_a, operation_a, operation_b],
                )
            )
            # 次の値または処理を現在の構造へ組み込む
            records.append(
                # 次の値または処理を現在の構造へ組み込む
                make_record(
                    # 次の値または処理を現在の構造へ組み込む
                    len(records) + 1,
                    # 次の値または処理を現在の構造へ組み込む
                    [operation_b, operation_a, operation_a],
                )
            )

    # 3操作: A → A → A
    for operation_a in atomic_operations:
        # 次の値または処理を現在の構造へ組み込む
        records.append(
            # 次の値または処理を現在の構造へ組み込む
            make_record(
                # 次の値または処理を現在の構造へ組み込む
                len(records) + 1,
                # 次の値または処理を現在の構造へ組み込む
                [operation_a, operation_a, operation_a],
            )
        )

    # 処理結果を呼び出し元へ返す
    return records


# この工程を担当する関数を定義する
def classify_sequence(sequence: list[dict]) -> str:
    """操作列が方針で許可されたどの形式かを返す。"""

    # operation_keysへこの工程で使用する値を設定する
    operation_keys = [canonical_operation(operation) for operation in sequence]

    # 条件を満たす場合だけ次の処理を行う
    if len(operation_keys) == 2 and operation_keys[0] == operation_keys[1]:
        # 処理結果を呼び出し元へ返す
        return "A → A"

    # 条件を満たす場合だけ次の処理を行う
    if len(operation_keys) == 3:
        # 次の値または処理を現在の構造へ組み込む
        first, second, third = operation_keys
        # 条件を満たす場合だけ次の処理を行う
        if first == second == third:
            # 処理結果を呼び出し元へ返す
            return "A → A → A"
        # 条件を満たす場合だけ次の処理を行う
        if first == second and second != third:
            # 処理結果を呼び出し元へ返す
            return "A → A → B"
        # 条件を満たす場合だけ次の処理を行う
        if first != second and second == third:
            # 処理結果を呼び出し元へ返す
            return "B → A → A"

    # 不正な状態を例外として通知して処理を停止する
    raise ValueError(f"反復汎化テストの対象外形式です: {sequence!r}")


# この工程を担当する関数を定義する
def validate_records(records: list[dict]) -> None:
    """件数、ID、意味AST、対象形式を保存前に検証する。"""

    # expected_totalへこの工程で使用する値を設定する
    expected_total = sum(EXPECTED_COUNTS.values())
    # 条件を満たす場合だけ次の処理を行う
    if len(records) != expected_total:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"生成件数が不正です: 期待={expected_total}件, 実際={len(records)}件"
        )

    # expected_spec_idsへこの工程で使用する値を設定する
    expected_spec_ids = [
        # 次の値または処理を現在の構造へ組み込む
        f"repetition-{record_number:06d}"
        # 対象を一件ずつ取り出して処理する
        for record_number in range(1, expected_total + 1)
    ]
    # actual_spec_idsへこの工程で使用する値を設定する
    actual_spec_ids = [record.get("spec_id") for record in records]
    # 条件を満たす場合だけ次の処理を行う
    if actual_spec_ids != expected_spec_ids:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("spec_idがrepetition-000001からの連番になっていません")

    # semantic_astsへこの工程で使用する値を設定する
    semantic_asts = [
        # 次の値または処理を現在の構造へ組み込む
        json.dumps(
            # 次の値または処理を現在の構造へ組み込む
            record.get("semantic_ast"),
            # sort_keysへこの工程で使用する値を設定する
            sort_keys=True,
            # ensure_asciiへこの工程で使用する値を設定する
            ensure_ascii=False,
            # separatorsへこの工程で使用する値を設定する
            separators=(",", ":"),
        )
        # 対象を一件ずつ取り出して処理する
        for record in records
    ]
    # 条件を満たす場合だけ次の処理を行う
    if len(semantic_asts) != len(set(semantic_asts)):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("生成した意味ASTが重複しています")

    # actual_countsへこの工程で使用する値を設定する
    actual_counts = {name: 0 for name in EXPECTED_COUNTS}
    # 対象を一件ずつ取り出して処理する
    for record in records:
        # 条件を満たす場合だけ次の処理を行う
        if record.get("test_suite") != "repetition":
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"test_suiteが不正です: {record!r}")

        # semantic_astへこの工程で使用する値を設定する
        semantic_ast = record.get("semantic_ast")
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(semantic_ast, dict) or set(semantic_ast) != {"sequence"}:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"意味ASTの形式が不正です: {record!r}")

        # categoryへこの工程で使用する値を設定する
        category = classify_sequence(semantic_ast["sequence"])
        # 次の値または処理を現在の構造へ組み込む
        actual_counts[category] += 1

    # 条件を満たす場合だけ次の処理を行う
    if actual_counts != EXPECTED_COUNTS:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"形式別件数が不正です: 期待={EXPECTED_COUNTS}, 実際={actual_counts}"
        )


# この工程を担当する関数を定義する
def save_jsonl(records: list[dict], path: Path) -> None:
    """検証済みレコードをUTF-8のJSONLとして保存する。"""

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
    # atomic_operationsへこの工程で使用する値を設定する
    atomic_operations = load_atomic_operations(INPUT_PATH)
    # recordsへこの工程で使用する値を設定する
    records = generate_records(atomic_operations)
    # 次の値または処理を現在の構造へ組み込む
    validate_records(records)
    # 次の値または処理を現在の構造へ組み込む
    save_jsonl(records, OUTPUT_PATH)

    # countsへこの工程で使用する値を設定する
    counts = ", ".join(
        # 次の値または処理を現在の構造へ組み込む
        f"{category}={count}件" for category, count in EXPECTED_COUNTS.items()
    )
    # 処理結果を利用者へ表示する
    print(f"{OUTPUT_PATH} に {len(records)}件保存しました（{counts}）")


# 条件を満たす場合だけ次の処理を行う
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    main()
