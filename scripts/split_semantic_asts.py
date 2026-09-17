"""組合せ汎化用670件を除いた意味ASTを案Bのハッシュ順で分割する。"""

import hashlib
import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ATOMIC_PATH = PROJECT_ROOT / "data" / "atomic_semantic_asts.jsonl"
COMBINED_PATH = PROJECT_ROOT / "data" / "combined_semantic_asts.jsonl"
COMPOSITIONAL_PATH = PROJECT_ROOT / "data" / "compositional_semantic_asts.jsonl"
OUTPUT_PATHS = {
    "train": PROJECT_ROOT / "data" / "train_semantic_asts.jsonl",
    "val": PROJECT_ROOT / "data" / "val_semantic_asts.jsonl",
    "normal": PROJECT_ROOT / "data" / "normal_semantic_asts.jsonl",
}

EXPECTED_COMBINED_COUNT = 12_720
EXPECTED_COMPOSITIONAL_COUNT = 670
EXPECTED_REMAINING_COUNTS = {1: 24, 2: 542, 3: 11_484}
EXPECTED_SPLIT_COUNTS = {
    1: {"train": 24, "val": 0, "normal": 0},
    2: {"train": 434, "val": 54, "normal": 54},
    3: {"train": 9_188, "val": 1_148, "normal": 1_148},
}


def canonical_json(value: object) -> str:
    """JSON値をハッシュと完全一致確認に使う正規形へ変換する。"""

    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def ast_key(semantic_ast: dict) -> str:
    """意味ASTだけを正規化する。"""

    return canonical_json(semantic_ast)


def ast_hash(semantic_ast: dict) -> str:
    """正規化した意味ASTのSHA-256を16進文字列で返す。"""

    normalized = ast_key(semantic_ast).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    """空行を無視してJSONLを読み込む。"""

    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def operation_count(record: dict) -> int:
    """レコードを検証し、sequence内の操作数を返す。"""

    semantic_ast = record.get("semantic_ast")
    if not isinstance(semantic_ast, dict) or set(semantic_ast) != {"sequence"}:
        raise ValueError(f"意味ASTの形式が不正です: {record!r}")

    sequence = semantic_ast["sequence"]
    if not isinstance(sequence, list) or not 1 <= len(sequence) <= 3:
        raise ValueError(f"sequenceの形式が不正です: {record!r}")
    if any(not isinstance(operation, dict) or len(operation) != 1 for operation in sequence):
        raise ValueError(f"単独操作の形式が不正です: {record!r}")

    return len(sequence)


def validate_unique_records(records: list[dict], source_name: str) -> None:
    """spec_idと意味ASTが重複していないことを確認する。"""

    spec_ids = [record.get("spec_id") for record in records]
    if any(not isinstance(spec_id, str) for spec_id in spec_ids):
        raise ValueError(f"{source_name}に不正なspec_idがあります")
    if len(spec_ids) != len(set(spec_ids)):
        raise ValueError(f"{source_name}のspec_idが重複しています")

    ast_keys = [ast_key(record.get("semantic_ast")) for record in records]
    if len(ast_keys) != len(set(ast_keys)):
        raise ValueError(f"{source_name}の意味ASTが重複しています")


def load_and_validate_inputs() -> tuple[list[dict], list[dict], list[dict]]:
    """3入力を読み、件数、重複、包含関係を検証する。"""

    atomic_records = load_jsonl(ATOMIC_PATH)
    combined_records = load_jsonl(COMBINED_PATH)
    compositional_records = load_jsonl(COMPOSITIONAL_PATH)

    if len(atomic_records) != 24:
        raise ValueError(f"単独操作は24件必要です: {len(atomic_records)}件")
    if len(combined_records) != EXPECTED_COMBINED_COUNT:
        raise ValueError(
            f"組み合わせASTは{EXPECTED_COMBINED_COUNT}件必要です: "
            f"{len(combined_records)}件"
        )
    if len(compositional_records) != EXPECTED_COMPOSITIONAL_COUNT:
        raise ValueError(
            f"組合せ汎化ASTは{EXPECTED_COMPOSITIONAL_COUNT}件必要です: "
            f"{len(compositional_records)}件"
        )

    validate_unique_records(atomic_records, "単独操作")
    validate_unique_records(combined_records, "組み合わせAST")
    validate_unique_records(compositional_records, "組合せ汎化AST")

    combined_by_id = {
        record["spec_id"]: ast_key(record["semantic_ast"])
        for record in combined_records
    }
    for record in compositional_records:
        spec_id = record["spec_id"]
        if combined_by_id.get(spec_id) != ast_key(record["semantic_ast"]):
            raise ValueError(
                f"組合せ汎化ASTが抽出元と一致しません: {spec_id}"
            )
        if record.get("test_suite") != "compositional":
            raise ValueError(f"compositionalのtest_suiteが不正です: {record!r}")

    return atomic_records, combined_records, compositional_records


def remaining_by_operation_count(
    combined_records: list[dict],
    compositional_records: list[dict],
) -> dict[int, list[dict]]:
    """670件を除き、残りを操作数別にまとめる。"""

    compositional_ids = {record["spec_id"] for record in compositional_records}
    remaining = {1: [], 2: [], 3: []}
    for record in combined_records:
        if record["spec_id"] in compositional_ids:
            continue
        remaining[operation_count(record)].append(record)

    actual_counts = {count: len(records) for count, records in remaining.items()}
    if actual_counts != EXPECTED_REMAINING_COUNTS:
        raise ValueError(
            f"組合せ汎化AST除外後の件数が不正です: "
            f"期待={EXPECTED_REMAINING_COUNTS}, 実際={actual_counts}"
        )

    return remaining


def make_output_record(record: dict, split_name: str) -> dict:
    """元IDと意味ASTを保持し、分割情報を加える。"""

    return {
        "spec_id": record["spec_id"],
        "semantic_ast": record["semantic_ast"],
        "split": "test" if split_name == "normal" else split_name,
        "test_suite": "normal" if split_name == "normal" else None,
    }


def split_records(remaining: dict[int, list[dict]]) -> dict[str, list[dict]]:
    """操作数ごとにSHA-256順で並べ、指定件数で切り分ける。"""

    result = {"train": [], "val": [], "normal": []}
    for count in (1, 2, 3):
        ordered = sorted(
            remaining[count],
            key=lambda record: (
                ast_hash(record["semantic_ast"]),
                ast_key(record["semantic_ast"]),
            ),
        )
        allocation = EXPECTED_SPLIT_COUNTS[count]
        train_end = allocation["train"]
        val_end = train_end + allocation["val"]

        pieces = {
            "train": ordered[:train_end],
            "val": ordered[train_end:val_end],
            "normal": ordered[val_end:],
        }
        for split_name, records in pieces.items():
            expected = allocation[split_name]
            if len(records) != expected:
                raise ValueError(
                    f"{count}操作の{split_name}件数が不正です: "
                    f"期待={expected}, 実際={len(records)}"
                )
            result[split_name].extend(
                make_output_record(record, split_name) for record in records
            )

    return result


def compositional_pair_keys(compositional_records: list[dict]) -> set[frozenset[str]]:
    """compositionalの2操作10件から、対象の5ペアを復元する。"""

    pair_occurrences = Counter()
    for record in compositional_records:
        sequence = record["semantic_ast"]["sequence"]
        if len(sequence) != 2:
            continue
        pair = frozenset(canonical_json(operation) for operation in sequence)
        if len(pair) != 2:
            raise ValueError(f"組合せ汎化の2操作ASTが不正です: {record!r}")
        pair_occurrences[pair] += 1

    if len(pair_occurrences) != 5 or set(pair_occurrences.values()) != {2}:
        raise ValueError(
            "組合せ汎化の2操作ASTから5ペア×2順序を確認できません"
        )
    return set(pair_occurrences)


def validate_splits(
    split_records_by_name: dict[str, list[dict]],
    remaining: dict[int, list[dict]],
    atomic_records: list[dict],
    compositional_records: list[dict],
) -> None:
    """件数、排他性、網羅性、組合せ汎化条件を検証する。"""

    expected_totals = {
        split_name: sum(
            allocation[split_name]
            for allocation in EXPECTED_SPLIT_COUNTS.values()
        )
        for split_name in ("train", "val", "normal")
    }
    actual_totals = {
        split_name: len(records)
        for split_name, records in split_records_by_name.items()
    }
    if actual_totals != expected_totals:
        raise ValueError(
            f"分割後の総件数が不正です: 期待={expected_totals}, "
            f"実際={actual_totals}"
        )

    split_keys = {}
    for split_name, records in split_records_by_name.items():
        validate_unique_records(records, split_name)
        split_keys[split_name] = {
            ast_key(record["semantic_ast"]) for record in records
        }
        for record in records:
            expected_split = "test" if split_name == "normal" else split_name
            expected_suite = "normal" if split_name == "normal" else None
            if record.get("split") != expected_split:
                raise ValueError(f"splitが不正です: {record!r}")
            if record.get("test_suite") != expected_suite:
                raise ValueError(f"test_suiteが不正です: {record!r}")

    if split_keys["train"] & split_keys["val"]:
        raise ValueError("trainとvalの意味ASTが重複しています")
    if split_keys["train"] & split_keys["normal"]:
        raise ValueError("trainとnormalの意味ASTが重複しています")
    if split_keys["val"] & split_keys["normal"]:
        raise ValueError("valとnormalの意味ASTが重複しています")

    expected_remaining_keys = {
        ast_key(record["semantic_ast"])
        for records in remaining.values()
        for record in records
    }
    actual_keys = set().union(*split_keys.values())
    if actual_keys != expected_remaining_keys:
        raise ValueError("分割結果が残り12,050件を過不足なく網羅していません")

    atomic_keys = {
        ast_key({"sequence": [record["semantic_ast"]]})
        for record in atomic_records
    }
    if not atomic_keys <= split_keys["train"]:
        raise ValueError("24個の単独操作がすべてtrainに入っていません")

    target_pairs = compositional_pair_keys(compositional_records)
    for record in split_records_by_name["train"]:
        operation_keys = {
            canonical_json(operation)
            for operation in record["semantic_ast"]["sequence"]
        }
        if any(pair <= operation_keys for pair in target_pairs):
            raise ValueError(
                f"train内で組合せ汎化用ペアが共起しています: {record!r}"
            )


def save_jsonl(records: list[dict], path: Path) -> None:
    """検証済みレコードをUTF-8、LFのJSONLで保存する。"""

    with path.open("w", encoding="utf-8", newline="\n") as destination:
        for record in records:
            destination.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )


def main() -> None:
    atomic_records, combined_records, compositional_records = load_and_validate_inputs()
    remaining = remaining_by_operation_count(combined_records, compositional_records)
    split_records_by_name = split_records(remaining)
    validate_splits(
        split_records_by_name,
        remaining,
        atomic_records,
        compositional_records,
    )

    for split_name, path in OUTPUT_PATHS.items():
        save_jsonl(split_records_by_name[split_name], path)

    counts = ", ".join(
        f"{split_name}={len(records):,}件"
        for split_name, records in split_records_by_name.items()
    )
    print(f"案BのSHA-256順で分割しました（{counts}）")


if __name__ == "__main__":
    main()
