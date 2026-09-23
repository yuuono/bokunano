"""組合せ汎化用670件を除いた意味ASTを案Bのハッシュ順で分割する。"""

# この処理で使う標準または外部モジュールを読み込む
import hashlib
# この処理で使う標準または外部モジュールを読み込む
import json
# 必要な定義を対象モジュールから読み込む
from collections import Counter
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
# COMPOSITIONAL_PATHへこの工程で使用する値を設定する
COMPOSITIONAL_PATH = DATA_DIR / "compositional_semantic_asts.jsonl"
# OUTPUT_PATHSへこの工程で使用する値を設定する
OUTPUT_PATHS = {
    # 出力レコードの項目と値を設定する
    "train": DATA_DIR / "train_semantic_asts.jsonl",
    # 出力レコードの項目と値を設定する
    "val": DATA_DIR / "val_semantic_asts.jsonl",
    # 出力レコードの項目と値を設定する
    "normal": DATA_DIR / "normal_semantic_asts.jsonl",
}

# EXPECTED_COMBINED_COUNTへこの工程で使用する値を設定する
EXPECTED_COMBINED_COUNT = 12_720
# EXPECTED_COMPOSITIONAL_COUNTへこの工程で使用する値を設定する
EXPECTED_COMPOSITIONAL_COUNT = 670
# EXPECTED_REMAINING_COUNTSへこの工程で使用する値を設定する
EXPECTED_REMAINING_COUNTS = {1: 24, 2: 542, 3: 11_484}
# EXPECTED_SPLIT_COUNTSへこの工程で使用する値を設定する
EXPECTED_SPLIT_COUNTS = {
    # 次の値または処理を現在の構造へ組み込む
    1: {"train": 24, "val": 0, "normal": 0},
    # 次の値または処理を現在の構造へ組み込む
    2: {"train": 434, "val": 54, "normal": 54},
    # 次の値または処理を現在の構造へ組み込む
    3: {"train": 9_188, "val": 1_148, "normal": 1_148},
}


# この工程を担当する関数を定義する
def canonical_json(value: object) -> str:
    """JSON値をハッシュと完全一致確認に使う正規形へ変換する。"""

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
def ast_key(semantic_ast: dict) -> str:
    """意味ASTだけを正規化する。"""

    # 処理結果を呼び出し元へ返す
    return canonical_json(semantic_ast)


# この工程を担当する関数を定義する
def ast_hash(semantic_ast: dict) -> str:
    """正規化した意味ASTのSHA-256を16進文字列で返す。"""

    # normalizedへこの工程で使用する値を設定する
    normalized = ast_key(semantic_ast).encode("utf-8")
    # 処理結果を呼び出し元へ返す
    return hashlib.sha256(normalized).hexdigest()


# この工程を担当する関数を定義する
def load_jsonl(path: Path) -> list[dict]:
    """空行を無視してJSONLを読み込む。"""

    # 使用するリソースの開始と終了をこの範囲で管理する
    with path.open(encoding="utf-8") as source:
        # 処理結果を呼び出し元へ返す
        return [json.loads(line) for line in source if line.strip()]


# この工程を担当する関数を定義する
def operation_count(record: dict) -> int:
    """レコードを検証し、sequence内の操作数を返す。"""

    # semantic_astへこの工程で使用する値を設定する
    semantic_ast = record.get("semantic_ast")
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(semantic_ast, dict) or set(semantic_ast) != {"sequence"}:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"意味ASTの形式が不正です: {record!r}")

    # sequenceへこの工程で使用する値を設定する
    sequence = semantic_ast["sequence"]
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(sequence, list) or not 1 <= len(sequence) <= 3:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"sequenceの形式が不正です: {record!r}")
    # 条件を満たす場合だけ次の処理を行う
    if any(not isinstance(operation, dict) or len(operation) != 1 for operation in sequence):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"単独操作の形式が不正です: {record!r}")

    # 処理結果を呼び出し元へ返す
    return len(sequence)


# この工程を担当する関数を定義する
def validate_unique_records(records: list[dict], source_name: str) -> None:
    """spec_idと意味ASTが重複していないことを確認する。"""

    # spec_idsへこの工程で使用する値を設定する
    spec_ids = [record.get("spec_id") for record in records]
    # 条件を満たす場合だけ次の処理を行う
    if any(not isinstance(spec_id, str) for spec_id in spec_ids):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{source_name}に不正なspec_idがあります")
    # 条件を満たす場合だけ次の処理を行う
    if len(spec_ids) != len(set(spec_ids)):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{source_name}のspec_idが重複しています")

    # ast_keysへこの工程で使用する値を設定する
    ast_keys = [ast_key(record.get("semantic_ast")) for record in records]
    # 条件を満たす場合だけ次の処理を行う
    if len(ast_keys) != len(set(ast_keys)):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{source_name}の意味ASTが重複しています")


# この工程を担当する関数を定義する
def load_and_validate_inputs() -> tuple[list[dict], list[dict], list[dict]]:
    """3入力を読み、件数、重複、包含関係を検証する。"""

    # atomic_recordsへこの工程で使用する値を設定する
    atomic_records = load_jsonl(ATOMIC_PATH)
    # combined_recordsへこの工程で使用する値を設定する
    combined_records = load_jsonl(COMBINED_PATH)
    # compositional_recordsへこの工程で使用する値を設定する
    compositional_records = load_jsonl(COMPOSITIONAL_PATH)

    # 条件を満たす場合だけ次の処理を行う
    if len(atomic_records) != 24:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"単独操作は24件必要です: {len(atomic_records)}件")
    # 条件を満たす場合だけ次の処理を行う
    if len(combined_records) != EXPECTED_COMBINED_COUNT:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"組み合わせASTは{EXPECTED_COMBINED_COUNT}件必要です: "
            # 次の値または処理を現在の構造へ組み込む
            f"{len(combined_records)}件"
        )
    # 条件を満たす場合だけ次の処理を行う
    if len(compositional_records) != EXPECTED_COMPOSITIONAL_COUNT:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"組合せ汎化ASTは{EXPECTED_COMPOSITIONAL_COUNT}件必要です: "
            # 次の値または処理を現在の構造へ組み込む
            f"{len(compositional_records)}件"
        )

    # 次の値または処理を現在の構造へ組み込む
    validate_unique_records(atomic_records, "単独操作")
    # 次の値または処理を現在の構造へ組み込む
    validate_unique_records(combined_records, "組み合わせAST")
    # 次の値または処理を現在の構造へ組み込む
    validate_unique_records(compositional_records, "組合せ汎化AST")

    # combined_by_idへこの工程で使用する値を設定する
    combined_by_id = {
        # 次の値または処理を現在の構造へ組み込む
        record["spec_id"]: ast_key(record["semantic_ast"])
        # 対象を一件ずつ取り出して処理する
        for record in combined_records
    }
    # 対象を一件ずつ取り出して処理する
    for record in compositional_records:
        # spec_idへこの工程で使用する値を設定する
        spec_id = record["spec_id"]
        # 条件を満たす場合だけ次の処理を行う
        if combined_by_id.get(spec_id) != ast_key(record["semantic_ast"]):
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                # 次の値または処理を現在の構造へ組み込む
                f"組合せ汎化ASTが抽出元と一致しません: {spec_id}"
            )
        # 条件を満たす場合だけ次の処理を行う
        if record.get("test_suite") != "compositional":
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"compositionalのtest_suiteが不正です: {record!r}")

    # 処理結果を呼び出し元へ返す
    return atomic_records, combined_records, compositional_records


# この工程を担当する関数を定義する
def remaining_by_operation_count(
    # 次の値または処理を現在の構造へ組み込む
    combined_records: list[dict],
    # 次の値または処理を現在の構造へ組み込む
    compositional_records: list[dict],
# 次の値または処理を現在の構造へ組み込む
) -> dict[int, list[dict]]:
    """670件を除き、残りを操作数別にまとめる。"""

    # compositional_idsへこの工程で使用する値を設定する
    compositional_ids = {record["spec_id"] for record in compositional_records}
    # remainingへこの工程で使用する値を設定する
    remaining = {1: [], 2: [], 3: []}
    # 対象を一件ずつ取り出して処理する
    for record in combined_records:
        # 条件を満たす場合だけ次の処理を行う
        if record["spec_id"] in compositional_ids:
            # 現在の対象を終えて次の対象へ進む
            continue
        # 次の値または処理を現在の構造へ組み込む
        remaining[operation_count(record)].append(record)

    # actual_countsへこの工程で使用する値を設定する
    actual_counts = {count: len(records) for count, records in remaining.items()}
    # 条件を満たす場合だけ次の処理を行う
    if actual_counts != EXPECTED_REMAINING_COUNTS:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"組合せ汎化AST除外後の件数が不正です: "
            # 次の値または処理を現在の構造へ組み込む
            f"期待={EXPECTED_REMAINING_COUNTS}, 実際={actual_counts}"
        )

    # 処理結果を呼び出し元へ返す
    return remaining


# この工程を担当する関数を定義する
def make_output_record(record: dict, split_name: str) -> dict:
    """元IDと意味ASTを保持し、分割情報を加える。"""

    # 処理結果を呼び出し元へ返す
    return {
        # 出力レコードの項目と値を設定する
        "spec_id": record["spec_id"],
        # 出力レコードの項目と値を設定する
        "semantic_ast": record["semantic_ast"],
        # 出力レコードの項目と値を設定する
        "split": "test" if split_name == "normal" else split_name,
        # 出力レコードの項目と値を設定する
        "test_suite": "normal" if split_name == "normal" else None,
    }


# この工程を担当する関数を定義する
def split_records(remaining: dict[int, list[dict]]) -> dict[str, list[dict]]:
    """操作数ごとにSHA-256順で並べ、指定件数で切り分ける。"""

    # resultへこの工程で使用する値を設定する
    result = {"train": [], "val": [], "normal": []}
    # 対象を一件ずつ取り出して処理する
    for count in (1, 2, 3):
        # orderedへこの工程で使用する値を設定する
        ordered = sorted(
            # 次の値または処理を現在の構造へ組み込む
            remaining[count],
            # keyへこの工程で使用する値を設定する
            key=lambda record: (
                # 次の値または処理を現在の構造へ組み込む
                ast_hash(record["semantic_ast"]),
                # 次の値または処理を現在の構造へ組み込む
                ast_key(record["semantic_ast"]),
            ),
        )
        # allocationへこの工程で使用する値を設定する
        allocation = EXPECTED_SPLIT_COUNTS[count]
        # train_endへこの工程で使用する値を設定する
        train_end = allocation["train"]
        # val_endへこの工程で使用する値を設定する
        val_end = train_end + allocation["val"]

        # piecesへこの工程で使用する値を設定する
        pieces = {
            # 出力レコードの項目と値を設定する
            "train": ordered[:train_end],
            # 出力レコードの項目と値を設定する
            "val": ordered[train_end:val_end],
            # 出力レコードの項目と値を設定する
            "normal": ordered[val_end:],
        }
        # 対象を一件ずつ取り出して処理する
        for split_name, records in pieces.items():
            # expectedへこの工程で使用する値を設定する
            expected = allocation[split_name]
            # 条件を満たす場合だけ次の処理を行う
            if len(records) != expected:
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(
                    # 次の値または処理を現在の構造へ組み込む
                    f"{count}操作の{split_name}件数が不正です: "
                    # 次の値または処理を現在の構造へ組み込む
                    f"期待={expected}, 実際={len(records)}"
                )
            # 次の値または処理を現在の構造へ組み込む
            result[split_name].extend(
                # 次の値または処理を現在の構造へ組み込む
                make_output_record(record, split_name) for record in records
            )

    # 処理結果を呼び出し元へ返す
    return result


# この工程を担当する関数を定義する
def compositional_pair_keys(compositional_records: list[dict]) -> set[frozenset[str]]:
    """compositionalの2操作10件から、対象の5ペアを復元する。"""

    # pair_occurrencesへこの工程で使用する値を設定する
    pair_occurrences = Counter()
    # 対象を一件ずつ取り出して処理する
    for record in compositional_records:
        # sequenceへこの工程で使用する値を設定する
        sequence = record["semantic_ast"]["sequence"]
        # 条件を満たす場合だけ次の処理を行う
        if len(sequence) != 2:
            # 現在の対象を終えて次の対象へ進む
            continue
        # pairへこの工程で使用する値を設定する
        pair = frozenset(canonical_json(operation) for operation in sequence)
        # 条件を満たす場合だけ次の処理を行う
        if len(pair) != 2:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"組合せ汎化の2操作ASTが不正です: {record!r}")
        # 次の値または処理を現在の構造へ組み込む
        pair_occurrences[pair] += 1

    # 条件を満たす場合だけ次の処理を行う
    if len(pair_occurrences) != 5 or set(pair_occurrences.values()) != {2}:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            "組合せ汎化の2操作ASTから5ペア×2順序を確認できません"
        )
    # 処理結果を呼び出し元へ返す
    return set(pair_occurrences)


# この工程を担当する関数を定義する
def validate_splits(
    # 次の値または処理を現在の構造へ組み込む
    split_records_by_name: dict[str, list[dict]],
    # 次の値または処理を現在の構造へ組み込む
    remaining: dict[int, list[dict]],
    # 次の値または処理を現在の構造へ組み込む
    atomic_records: list[dict],
    # 次の値または処理を現在の構造へ組み込む
    compositional_records: list[dict],
# 次の値または処理を現在の構造へ組み込む
) -> None:
    """件数、排他性、網羅性、組合せ汎化条件を検証する。"""

    # expected_totalsへこの工程で使用する値を設定する
    expected_totals = {
        # 次の値または処理を現在の構造へ組み込む
        split_name: sum(
            # 次の値または処理を現在の構造へ組み込む
            allocation[split_name]
            # 対象を一件ずつ取り出して処理する
            for allocation in EXPECTED_SPLIT_COUNTS.values()
        )
        # 対象を一件ずつ取り出して処理する
        for split_name in ("train", "val", "normal")
    }
    # actual_totalsへこの工程で使用する値を設定する
    actual_totals = {
        # 次の値または処理を現在の構造へ組み込む
        split_name: len(records)
        # 対象を一件ずつ取り出して処理する
        for split_name, records in split_records_by_name.items()
    }
    # 条件を満たす場合だけ次の処理を行う
    if actual_totals != expected_totals:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"分割後の総件数が不正です: 期待={expected_totals}, "
            # 次の値または処理を現在の構造へ組み込む
            f"実際={actual_totals}"
        )

    # split_keysへこの工程で使用する値を設定する
    split_keys = {}
    # 対象を一件ずつ取り出して処理する
    for split_name, records in split_records_by_name.items():
        # 次の値または処理を現在の構造へ組み込む
        validate_unique_records(records, split_name)
        # split_keys[split_name]へこの工程で使用する値を設定する
        split_keys[split_name] = {
            # 次の値または処理を現在の構造へ組み込む
            ast_key(record["semantic_ast"]) for record in records
        }
        # 対象を一件ずつ取り出して処理する
        for record in records:
            # expected_splitへこの工程で使用する値を設定する
            expected_split = "test" if split_name == "normal" else split_name
            # expected_suiteへこの工程で使用する値を設定する
            expected_suite = "normal" if split_name == "normal" else None
            # 条件を満たす場合だけ次の処理を行う
            if record.get("split") != expected_split:
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"splitが不正です: {record!r}")
            # 条件を満たす場合だけ次の処理を行う
            if record.get("test_suite") != expected_suite:
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"test_suiteが不正です: {record!r}")

    # 条件を満たす場合だけ次の処理を行う
    if split_keys["train"] & split_keys["val"]:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("trainとvalの意味ASTが重複しています")
    # 条件を満たす場合だけ次の処理を行う
    if split_keys["train"] & split_keys["normal"]:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("trainとnormalの意味ASTが重複しています")
    # 条件を満たす場合だけ次の処理を行う
    if split_keys["val"] & split_keys["normal"]:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("valとnormalの意味ASTが重複しています")

    # expected_remaining_keysへこの工程で使用する値を設定する
    expected_remaining_keys = {
        # 次の値または処理を現在の構造へ組み込む
        ast_key(record["semantic_ast"])
        # 対象を一件ずつ取り出して処理する
        for records in remaining.values()
        # 対象を一件ずつ取り出して処理する
        for record in records
    }
    # actual_keysへこの工程で使用する値を設定する
    actual_keys = set().union(*split_keys.values())
    # 条件を満たす場合だけ次の処理を行う
    if actual_keys != expected_remaining_keys:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("分割結果が残り12,050件を過不足なく網羅していません")

    # atomic_keysへこの工程で使用する値を設定する
    atomic_keys = {
        # 次の値または処理を現在の構造へ組み込む
        ast_key({"sequence": [record["semantic_ast"]]})
        # 対象を一件ずつ取り出して処理する
        for record in atomic_records
    }
    # 条件を満たす場合だけ次の処理を行う
    if not atomic_keys <= split_keys["train"]:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("24個の単独操作がすべてtrainに入っていません")

    # target_pairsへこの工程で使用する値を設定する
    target_pairs = compositional_pair_keys(compositional_records)
    # 対象を一件ずつ取り出して処理する
    for record in split_records_by_name["train"]:
        # operation_keysへこの工程で使用する値を設定する
        operation_keys = {
            # 次の値または処理を現在の構造へ組み込む
            canonical_json(operation)
            # 対象を一件ずつ取り出して処理する
            for operation in record["semantic_ast"]["sequence"]
        }
        # 条件を満たす場合だけ次の処理を行う
        if any(pair <= operation_keys for pair in target_pairs):
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                # 次の値または処理を現在の構造へ組み込む
                f"train内で組合せ汎化用ペアが共起しています: {record!r}"
            )


# この工程を担当する関数を定義する
def save_jsonl(records: list[dict], path: Path) -> None:
    """検証済みレコードをUTF-8、LFのJSONLで保存する。"""

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
    # 次の値または処理を現在の構造へ組み込む
    atomic_records, combined_records, compositional_records = load_and_validate_inputs()
    # remainingへこの工程で使用する値を設定する
    remaining = remaining_by_operation_count(combined_records, compositional_records)
    # split_records_by_nameへこの工程で使用する値を設定する
    split_records_by_name = split_records(remaining)
    # 次の値または処理を現在の構造へ組み込む
    validate_splits(
        # 次の値または処理を現在の構造へ組み込む
        split_records_by_name,
        # 次の値または処理を現在の構造へ組み込む
        remaining,
        # 次の値または処理を現在の構造へ組み込む
        atomic_records,
        # 次の値または処理を現在の構造へ組み込む
        compositional_records,
    )

    # 対象を一件ずつ取り出して処理する
    for split_name, path in OUTPUT_PATHS.items():
        # 次の値または処理を現在の構造へ組み込む
        save_jsonl(split_records_by_name[split_name], path)

    # countsへこの工程で使用する値を設定する
    counts = ", ".join(
        # 次の値または処理を現在の構造へ組み込む
        f"{split_name}={len(records):,}件"
        # 対象を一件ずつ取り出して処理する
        for split_name, records in split_records_by_name.items()
    )
    # 処理結果を利用者へ表示する
    print(f"案BのSHA-256順で分割しました（{counts}）")


# 条件を満たす場合だけ次の処理を行う
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    main()
