"""既存の12,720件から組合せ汎化テスト用の意味ASTを670件抽出する。"""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "semantic_asts"
ATOMIC_PATH = DATA_DIR / "atomic_semantic_asts.jsonl"
COMBINED_PATH = DATA_DIR / "combined_semantic_asts.jsonl"
OUTPUT_PATH = DATA_DIR / "compositional_semantic_asts.jsonl"

# 方針文書で確定した、互いに単独操作を共有しない5ペア
PAIR_ATOMIC_IDS = {
    "pair-01": ("atomic-000001", "atomic-000020"),
    "pair-02": ("atomic-000002", "atomic-000011"),
    "pair-03": ("atomic-000004", "atomic-000023"),
    "pair-04": ("atomic-000014", "atomic-000021"),
    "pair-05": ("atomic-000017", "atomic-000024"),
}

EXPECTED_COMBINED_COUNT = 12_720
EXPECTED_COUNTS_PER_PAIR = {2: 2, 3: 132}
EXPECTED_TOTAL_COUNTS = {2: 10, 3: 660}


def canonical_json(value: object) -> str:
    """JSON値を比較に使える決定的な文字列へ変換する。"""

    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def load_jsonl(path: Path) -> list[dict]:
    """空行を無視してJSONLを読み込む。"""

    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def load_pair_operation_keys(path: Path) -> dict[str, frozenset[str]]:
    """atomic IDで指定された5ペアを意味ASTの比較キーへ変換する。"""

    atomic_records = load_jsonl(path)
    if len(atomic_records) != 24:
        raise ValueError(f"単独操作は24件必要です: {len(atomic_records)}件")

    operation_by_id = {}
    for record in atomic_records:
        spec_id = record.get("spec_id")
        operation = record.get("semantic_ast")
        if not isinstance(spec_id, str):
            raise ValueError(f"単独操作のspec_idが不正です: {record!r}")
        if not isinstance(operation, dict) or len(operation) != 1:
            raise ValueError(f"単独操作の意味ASTが不正です: {record!r}")
        if spec_id in operation_by_id:
            raise ValueError(f"単独操作のspec_idが重複しています: {spec_id}")
        operation_by_id[spec_id] = canonical_json(operation)

    pair_operation_keys = {}
    used_atomic_ids = []
    for pair_id, atomic_ids in PAIR_ATOMIC_IDS.items():
        missing = [atomic_id for atomic_id in atomic_ids if atomic_id not in operation_by_id]
        if missing:
            raise ValueError(f"{pair_id}の単独操作が見つかりません: {missing}")

        pair_operation_keys[pair_id] = frozenset(
            operation_by_id[atomic_id] for atomic_id in atomic_ids
        )
        used_atomic_ids.extend(atomic_ids)

    if len(used_atomic_ids) != len(set(used_atomic_ids)):
        raise ValueError("5ペアの間で単独操作が重複しています")

    return pair_operation_keys


def matching_pair_ids(
    semantic_ast: dict,
    pair_operation_keys: dict[str, frozenset[str]],
) -> list[str]:
    """意味ASTが両方の操作を含むペアIDを返す。"""

    if not isinstance(semantic_ast, dict) or set(semantic_ast) != {"sequence"}:
        raise ValueError(f"意味ASTの形式が不正です: {semantic_ast!r}")

    sequence = semantic_ast["sequence"]
    if not isinstance(sequence, list) or not 1 <= len(sequence) <= 3:
        raise ValueError(f"sequenceの形式が不正です: {sequence!r}")

    operation_keys = [canonical_json(operation) for operation in sequence]
    if len(operation_keys) != len(set(operation_keys)):
        raise ValueError(f"既存12,720件に反復操作が含まれています: {semantic_ast!r}")

    operation_key_set = set(operation_keys)
    return [
        pair_id
        for pair_id, pair_keys in pair_operation_keys.items()
        if pair_keys <= operation_key_set
    ]


def extract_records(
    combined_records: list[dict],
    pair_operation_keys: dict[str, frozenset[str]],
) -> list[dict]:
    """5ペアのいずれかを含む2操作・3操作ASTを抽出する。"""

    extracted = []
    for record in combined_records:
        semantic_ast = record.get("semantic_ast")
        matched_pair_ids = matching_pair_ids(semantic_ast, pair_operation_keys)
        if not matched_pair_ids:
            continue
        if len(matched_pair_ids) != 1:
            raise ValueError(
                f"1件の意味ASTが複数ペアに一致しました: "
                f"{record.get('spec_id')}, {matched_pair_ids}"
            )

        extracted.append(
            {
                "spec_id": record["spec_id"],
                "semantic_ast": semantic_ast,
                "test_suite": "compositional",
            }
        )

    return extracted


def validate_records(
    combined_records: list[dict],
    extracted_records: list[dict],
    pair_operation_keys: dict[str, frozenset[str]],
) -> None:
    """入力件数、抽出件数、ペア別内訳、重複を検証する。"""

    if len(combined_records) != EXPECTED_COMBINED_COUNT:
        raise ValueError(
            f"既存の組み合わせASTは{EXPECTED_COMBINED_COUNT}件必要です: "
            f"{len(combined_records)}件"
        )

    expected_total = sum(EXPECTED_TOTAL_COUNTS.values())
    if len(extracted_records) != expected_total:
        raise ValueError(
            f"抽出件数が不正です: 期待={expected_total}件, "
            f"実際={len(extracted_records)}件"
        )

    spec_ids = [record.get("spec_id") for record in extracted_records]
    if len(spec_ids) != len(set(spec_ids)):
        raise ValueError("抽出後のspec_idが重複しています")

    semantic_asts = [canonical_json(record.get("semantic_ast")) for record in extracted_records]
    if len(semantic_asts) != len(set(semantic_asts)):
        raise ValueError("抽出後の意味ASTが重複しています")

    total_counts = {2: 0, 3: 0}
    pair_counts = {
        pair_id: {2: 0, 3: 0}
        for pair_id in PAIR_ATOMIC_IDS
    }

    for record in extracted_records:
        if record.get("test_suite") != "compositional":
            raise ValueError(f"test_suiteが不正です: {record!r}")

        semantic_ast = record["semantic_ast"]
        operation_count = len(semantic_ast["sequence"])
        if operation_count not in (2, 3):
            raise ValueError(f"操作数が不正です: {record!r}")

        matched_pair_ids = matching_pair_ids(semantic_ast, pair_operation_keys)
        if len(matched_pair_ids) != 1:
            raise ValueError(f"ペア一致数が不正です: {record!r}")

        total_counts[operation_count] += 1
        pair_counts[matched_pair_ids[0]][operation_count] += 1

    if total_counts != EXPECTED_TOTAL_COUNTS:
        raise ValueError(
            f"操作数別件数が不正です: 期待={EXPECTED_TOTAL_COUNTS}, "
            f"実際={total_counts}"
        )

    for pair_id, counts in pair_counts.items():
        if counts != EXPECTED_COUNTS_PER_PAIR:
            raise ValueError(
                f"{pair_id}の件数が不正です: "
                f"期待={EXPECTED_COUNTS_PER_PAIR}, 実際={counts}"
            )


def save_jsonl(records: list[dict], path: Path) -> None:
    """抽出済みレコードを元ファイルと同じ順序で保存する。"""

    with path.open("w", encoding="utf-8", newline="\n") as destination:
        for record in records:
            destination.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )


def main() -> None:
    pair_operation_keys = load_pair_operation_keys(ATOMIC_PATH)
    combined_records = load_jsonl(COMBINED_PATH)
    extracted_records = extract_records(combined_records, pair_operation_keys)
    validate_records(combined_records, extracted_records, pair_operation_keys)
    save_jsonl(extracted_records, OUTPUT_PATH)

    print(
        f"{OUTPUT_PATH} に{len(extracted_records)}件保存しました"
        f"（2操作={EXPECTED_TOTAL_COUNTS[2]}件, "
        f"3操作={EXPECTED_TOTAL_COUNTS[3]}件, "
        f"各ペア=134件）"
    )


if __name__ == "__main__":
    main()
