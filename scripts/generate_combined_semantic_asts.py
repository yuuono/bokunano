"""24個の単独操作から、順序付きの意味ASTを1〜3操作で生成する。"""

import itertools
import json
from pathlib import Path


INPUT_PATH = Path("data/atomic_semantic_asts.jsonl")
OUTPUT_PATH = Path("data/combined_semantic_asts.jsonl")
MIN_OPERATIONS = 1
MAX_OPERATIONS = 3


def load_atomic_asts(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as source:
        records = [json.loads(line) for line in source if line.strip()]

    if len(records) != 24:
        raise ValueError(f"単独操作は24件必要です: {len(records)}件")

    spec_ids = [record["spec_id"] for record in records]
    if len(spec_ids) != len(set(spec_ids)):
        raise ValueError("単独操作のspec_idが重複しています")

    return records


def generate_records(atomic_records: list[dict]):
    record_number = 1

    for operation_count in range(MIN_OPERATIONS, MAX_OPERATIONS + 1):
        for selected in itertools.permutations(atomic_records, operation_count):
            yield {
                "spec_id": f"combined-{record_number:06d}",
                "semantic_ast": {
                    "sequence": [record["semantic_ast"] for record in selected]
                },
            }
            record_number += 1


def save_jsonl(records, path: Path) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as destination:
        for record in records:
            destination.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
            count += 1
    return count


def main() -> None:
    atomic_records = load_atomic_asts(INPUT_PATH)
    count = save_jsonl(generate_records(atomic_records), OUTPUT_PATH)

    expected_count = 24 + 24 * 23 + 24 * 23 * 22
    if count != expected_count:
        raise RuntimeError(f"生成件数が不正です: {count}件")

    print(f"{OUTPUT_PATH} に {count} 件保存しました")


if __name__ == "__main__":
    main()

