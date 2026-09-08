"""同一操作が隣接する反復汎化テスト用の意味ASTを1,152件生成する。"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "data" / "atomic_semantic_asts.jsonl"
OUTPUT_PATH = PROJECT_ROOT / "data" / "repetition_semantic_asts.jsonl"
EXPECTED_COUNTS = {
    "A → A": 24,
    "A → A → B": 552,
    "B → A → A": 552,
    "A → A → A": 24,
}


def canonical_operation(operation: dict) -> str:
    """操作を重複確認に使える決定的な文字列へ変換する。"""

    return json.dumps(
        operation,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def load_atomic_operations(path: Path) -> list[dict]:
    """24個の単独操作を読み込み、形式と重複を検証する。"""

    with path.open(encoding="utf-8") as source:
        records = [json.loads(line) for line in source if line.strip()]

    if len(records) != 24:
        raise ValueError(f"単独操作は24件必要です: {len(records)}件")

    operations = []
    for record in records:
        operation = record.get("semantic_ast")
        if not isinstance(operation, dict) or len(operation) != 1:
            raise ValueError(f"単独操作の形式が不正です: {record!r}")
        operations.append(operation)

    operation_keys = [canonical_operation(operation) for operation in operations]
    if len(operation_keys) != len(set(operation_keys)):
        raise ValueError("単独操作の意味ASTが重複しています")

    return operations


def make_record(record_number: int, operations: list[dict]) -> dict:
    """反復汎化テスト用の1レコードを作る。"""

    return {
        "spec_id": f"repetition-{record_number:06d}",
        "semantic_ast": {"sequence": operations},
        "test_suite": "repetition",
    }


def generate_records(atomic_operations: list[dict]) -> list[dict]:
    """方針文書で定めた4形式を決定的な順序で列挙する。"""

    records = []

    # 2操作: A → A
    for operation_a in atomic_operations:
        records.append(make_record(len(records) + 1, [operation_a, operation_a]))

    # 3操作: A → A → B と B → A → A（AとBは異なる）
    for operation_a in atomic_operations:
        for operation_b in atomic_operations:
            if operation_a == operation_b:
                continue
            records.append(
                make_record(
                    len(records) + 1,
                    [operation_a, operation_a, operation_b],
                )
            )
            records.append(
                make_record(
                    len(records) + 1,
                    [operation_b, operation_a, operation_a],
                )
            )

    # 3操作: A → A → A
    for operation_a in atomic_operations:
        records.append(
            make_record(
                len(records) + 1,
                [operation_a, operation_a, operation_a],
            )
        )

    return records


def classify_sequence(sequence: list[dict]) -> str:
    """操作列が方針で許可されたどの形式かを返す。"""

    operation_keys = [canonical_operation(operation) for operation in sequence]

    if len(operation_keys) == 2 and operation_keys[0] == operation_keys[1]:
        return "A → A"

    if len(operation_keys) == 3:
        first, second, third = operation_keys
        if first == second == third:
            return "A → A → A"
        if first == second and second != third:
            return "A → A → B"
        if first != second and second == third:
            return "B → A → A"

    raise ValueError(f"反復汎化テストの対象外形式です: {sequence!r}")


def validate_records(records: list[dict]) -> None:
    """件数、ID、意味AST、対象形式を保存前に検証する。"""

    expected_total = sum(EXPECTED_COUNTS.values())
    if len(records) != expected_total:
        raise ValueError(
            f"生成件数が不正です: 期待={expected_total}件, 実際={len(records)}件"
        )

    expected_spec_ids = [
        f"repetition-{record_number:06d}"
        for record_number in range(1, expected_total + 1)
    ]
    actual_spec_ids = [record.get("spec_id") for record in records]
    if actual_spec_ids != expected_spec_ids:
        raise ValueError("spec_idがrepetition-000001からの連番になっていません")

    semantic_asts = [
        json.dumps(
            record.get("semantic_ast"),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for record in records
    ]
    if len(semantic_asts) != len(set(semantic_asts)):
        raise ValueError("生成した意味ASTが重複しています")

    actual_counts = {name: 0 for name in EXPECTED_COUNTS}
    for record in records:
        if record.get("test_suite") != "repetition":
            raise ValueError(f"test_suiteが不正です: {record!r}")

        semantic_ast = record.get("semantic_ast")
        if not isinstance(semantic_ast, dict) or set(semantic_ast) != {"sequence"}:
            raise ValueError(f"意味ASTの形式が不正です: {record!r}")

        category = classify_sequence(semantic_ast["sequence"])
        actual_counts[category] += 1

    if actual_counts != EXPECTED_COUNTS:
        raise ValueError(
            f"形式別件数が不正です: 期待={EXPECTED_COUNTS}, 実際={actual_counts}"
        )


def save_jsonl(records: list[dict], path: Path) -> None:
    """検証済みレコードをUTF-8のJSONLとして保存する。"""

    with path.open("w", encoding="utf-8", newline="\n") as destination:
        for record in records:
            destination.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )


def main() -> None:
    atomic_operations = load_atomic_operations(INPUT_PATH)
    records = generate_records(atomic_operations)
    validate_records(records)
    save_jsonl(records, OUTPUT_PATH)

    counts = ", ".join(
        f"{category}={count}件" for category, count in EXPECTED_COUNTS.items()
    )
    print(f"{OUTPUT_PATH} に {len(records)}件保存しました（{counts}）")


if __name__ == "__main__":
    main()
