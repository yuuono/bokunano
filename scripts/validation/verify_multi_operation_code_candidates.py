"""2・3操作のコード候補について、件数、検証記録、完全重複を確認する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# 必要な定義を対象モジュールから読み込む
from collections import Counter
# この処理で使う標準または外部モジュールを読み込む
import hashlib
# 必要な定義を対象モジュールから読み込む
from itertools import combinations
# この処理で使う標準または外部モジュールを読み込む
import json
# 必要な定義を対象モジュールから読み込む
from pathlib import Path
# 必要な定義を対象モジュールから読み込む
from typing import Any, Iterable


# PROJECT_ROOTへこの工程で使用する値を設定する
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# GROUPSへこの工程で使用する値を設定する
GROUPS = (
    # 次の値または処理を現在の構造へ組み込む
    {
        # 出力レコードの項目と値を設定する
        "name": "compositional_two_operation",
        # 出力レコードの項目と値を設定する
        "path": PROJECT_ROOT
        # 次の値または処理を現在の構造へ組み込む
        / "data/code_candidates/compositional/two_operation/python_code_candidates.jsonl",
        # 出力レコードの項目と値を設定する
        "operation_count": 2,
        # 出力レコードの項目と値を設定する
        "spec_count": 10,
        # 出力レコードの項目と値を設定する
        "split": "test",
        # 出力レコードの項目と値を設定する
        "test_suite": "compositional",
        # 出力レコードの項目と値を設定する
        "side": "compositional",
    },
    # 次の値または処理を現在の構造へ組み込む
    {
        # 出力レコードの項目と値を設定する
        "name": "compositional_three_operation",
        # 出力レコードの項目と値を設定する
        "path": PROJECT_ROOT
        # 次の値または処理を現在の構造へ組み込む
        / "data/code_candidates/compositional/three_operation/python_code_candidates.jsonl",
        # 出力レコードの項目と値を設定する
        "operation_count": 3,
        # 出力レコードの項目と値を設定する
        "spec_count": 660,
        # 出力レコードの項目と値を設定する
        "split": "test",
        # 出力レコードの項目と値を設定する
        "test_suite": "compositional",
        # 出力レコードの項目と値を設定する
        "side": "compositional",
    },
    # 次の値または処理を現在の構造へ組み込む
    {
        # 出力レコードの項目と値を設定する
        "name": "train_two_operation",
        # 出力レコードの項目と値を設定する
        "path": PROJECT_ROOT
        # 次の値または処理を現在の構造へ組み込む
        / "data/code_candidates/train/two_operation/python_code_candidates.jsonl",
        # 出力レコードの項目と値を設定する
        "operation_count": 2,
        # 出力レコードの項目と値を設定する
        "spec_count": 434,
        # 出力レコードの項目と値を設定する
        "split": "train",
        # 出力レコードの項目と値を設定する
        "test_suite": None,
        # 出力レコードの項目と値を設定する
        "side": "train",
    },
    # 次の値または処理を現在の構造へ組み込む
    {
        # 出力レコードの項目と値を設定する
        "name": "train_three_operation",
        # 出力レコードの項目と値を設定する
        "path": PROJECT_ROOT
        # 次の値または処理を現在の構造へ組み込む
        / "data/code_candidates/train/three_operation/python_code_candidates.jsonl",
        # 出力レコードの項目と値を設定する
        "operation_count": 3,
        # 出力レコードの項目と値を設定する
        "spec_count": 9_188,
        # 出力レコードの項目と値を設定する
        "split": "train",
        # 出力レコードの項目と値を設定する
        "test_suite": None,
        # 出力レコードの項目と値を設定する
        "side": "train",
    },
    # 次の値または処理を現在の構造へ組み込む
    {
        # 出力レコードの項目と値を設定する
        "name": "validation_two_operation",
        # 出力レコードの項目と値を設定する
        "path": PROJECT_ROOT
        # 次の値または処理を現在の構造へ組み込む
        / "data/code_candidates/validation/two_operation/python_code_candidates.jsonl",
        # 出力レコードの項目と値を設定する
        "operation_count": 2,
        # 出力レコードの項目と値を設定する
        "spec_count": 54,
        # 出力レコードの項目と値を設定する
        "split": "val",
        # 出力レコードの項目と値を設定する
        "test_suite": None,
        # 出力レコードの項目と値を設定する
        "side": "validation",
    },
    # 次の値または処理を現在の構造へ組み込む
    {
        # 出力レコードの項目と値を設定する
        "name": "validation_three_operation",
        # 出力レコードの項目と値を設定する
        "path": PROJECT_ROOT
        # 次の値または処理を現在の構造へ組み込む
        / "data/code_candidates/validation/three_operation/python_code_candidates.jsonl",
        # 出力レコードの項目と値を設定する
        "operation_count": 3,
        # 出力レコードの項目と値を設定する
        "spec_count": 1_148,
        # 出力レコードの項目と値を設定する
        "split": "val",
        # 出力レコードの項目と値を設定する
        "test_suite": None,
        # 出力レコードの項目と値を設定する
        "side": "validation",
    },
    # 次の値または処理を現在の構造へ組み込む
    {
        # 出力レコードの項目と値を設定する
        "name": "normal_two_operation",
        # 出力レコードの項目と値を設定する
        "path": PROJECT_ROOT
        # 次の値または処理を現在の構造へ組み込む
        / "data/code_candidates/normal/two_operation/python_code_candidates.jsonl",
        # 出力レコードの項目と値を設定する
        "operation_count": 2,
        # 出力レコードの項目と値を設定する
        "spec_count": 54,
        # 出力レコードの項目と値を設定する
        "split": "test",
        # 出力レコードの項目と値を設定する
        "test_suite": "normal",
        # 出力レコードの項目と値を設定する
        "side": "normal",
    },
    # 次の値または処理を現在の構造へ組み込む
    {
        # 出力レコードの項目と値を設定する
        "name": "normal_three_operation",
        # 出力レコードの項目と値を設定する
        "path": PROJECT_ROOT
        # 次の値または処理を現在の構造へ組み込む
        / "data/code_candidates/normal/three_operation/python_code_candidates.jsonl",
        # 出力レコードの項目と値を設定する
        "operation_count": 3,
        # 出力レコードの項目と値を設定する
        "spec_count": 1_148,
        # 出力レコードの項目と値を設定する
        "split": "test",
        # 出力レコードの項目と値を設定する
        "test_suite": "normal",
        # 出力レコードの項目と値を設定する
        "side": "normal",
    },
    # 次の値または処理を現在の構造へ組み込む
    {
        # 出力レコードの項目と値を設定する
        "name": "repetition_two_operation",
        # 出力レコードの項目と値を設定する
        "path": PROJECT_ROOT
        # 次の値または処理を現在の構造へ組み込む
        / "data/code_candidates/repetition/two_operation/python_code_candidates.jsonl",
        # 出力レコードの項目と値を設定する
        "operation_count": 2,
        # 出力レコードの項目と値を設定する
        "spec_count": 24,
        # 出力レコードの項目と値を設定する
        "split": "test",
        # 出力レコードの項目と値を設定する
        "test_suite": "repetition",
        # 出力レコードの項目と値を設定する
        "side": "repetition",
    },
    # 次の値または処理を現在の構造へ組み込む
    {
        # 出力レコードの項目と値を設定する
        "name": "repetition_three_operation",
        # 出力レコードの項目と値を設定する
        "path": PROJECT_ROOT
        # 次の値または処理を現在の構造へ組み込む
        / "data/code_candidates/repetition/three_operation/python_code_candidates.jsonl",
        # 出力レコードの項目と値を設定する
        "operation_count": 3,
        # 出力レコードの項目と値を設定する
        "spec_count": 1_128,
        # 出力レコードの項目と値を設定する
        "split": "test",
        # 出力レコードの項目と値を設定する
        "test_suite": "repetition",
        # 出力レコードの項目と値を設定する
        "side": "repetition",
    },
)

# SINGLE_OPERATION_PATHへこの工程で使用する値を設定する
SINGLE_OPERATION_PATH = (
    # 次の値または処理を現在の構造へ組み込む
    PROJECT_ROOT
    # 次の値または処理を現在の構造へ組み込む
    / "data/code_candidates/single_operation/python_code_candidates.jsonl"
)
# EXPECTED_PER_SPECへこの工程で使用する値を設定する
EXPECTED_PER_SPEC = 20


# この工程を担当する関数を定義する
def main() -> None:
    # summariesへこの工程で使用する値を設定する
    summaries: dict[str, dict[str, int]] = {}
    # side_codesへこの工程で使用する値を設定する
    side_codes: dict[str, dict[str, tuple[str, str]]] = {
        # 出力レコードの項目と値を設定する
        "train": {},
        # 出力レコードの項目と値を設定する
        "compositional": {},
        # 出力レコードの項目と値を設定する
        "validation": {},
        # 出力レコードの項目と値を設定する
        "normal": {},
        # 出力レコードの項目と値を設定する
        "repetition": {},
    }
    # all_code_idsへこの工程で使用する値を設定する
    all_code_ids: set[str] = set()

    # 次の値または処理を現在の構造へ組み込む
    _add_existing_train_codes(side_codes["train"], all_code_ids)
    # 対象を一件ずつ取り出して処理する
    for group in GROUPS:
        # 次の値または処理を現在の構造へ組み込む
        summaries[str(group["name"])] = _verify_group(
            # 次の値または処理を現在の構造へ組み込む
            group,
            # 次の値または処理を現在の構造へ組み込む
            side_codes[str(group["side"])],
            # 次の値または処理を現在の構造へ組み込む
            all_code_ids,
        )

    # exact_overlap_by_pairへこの工程で使用する値を設定する
    exact_overlap_by_pair: dict[str, int] = {}
    # hash_collisionsへこの工程で使用する値を設定する
    hash_collisions = 0
    # 対象を一件ずつ取り出して処理する
    for left, right in combinations(side_codes, 2):
        # overlap_countへこの工程で使用する値を設定する
        overlap_count = 0
        # 対象を一件ずつ取り出して処理する
        for code_hash, (right_source, right_code_id) in side_codes[right].items():
            # left_matchへこの工程で使用する値を設定する
            left_match = side_codes[left].get(code_hash)
            # 条件を満たす場合だけ次の処理を行う
            if left_match is None:
                # 現在の対象を終えて次の対象へ進む
                continue
            # 次の値または処理を現在の構造へ組み込む
            left_source, left_code_id = left_match
            # 条件を満たす場合だけ次の処理を行う
            if left_source == right_source:
                # 次の値または処理を現在の構造へ組み込む
                overlap_count += 1
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(
                    # 次の値または処理を現在の構造へ組み込む
                    f"{left}と{right}に完全重複があります: "
                    # 次の値または処理を現在の構造へ組み込む
                    f"{left_code_id}, {right_code_id}"
                )
            # 次の値または処理を現在の構造へ組み込む
            hash_collisions += 1
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"SHA-256衝突があります: {code_hash}")
        # 次の値または処理を現在の構造へ組み込む
        exact_overlap_by_pair[f"{left}__{right}"] = overlap_count

    # resultへこの工程で使用する値を設定する
    result = {
        # 出力レコードの項目と値を設定する
        "groups": summaries,
        # 出力レコードの項目と値を設定する
        "code_count_by_set": {
            # 次の値または処理を現在の構造へ組み込む
            side: len(codes) for side, codes in side_codes.items()
        },
        # 出力レコードの項目と値を設定する
        "all_code_count": sum(len(codes) for codes in side_codes.values()),
        # 出力レコードの項目と値を設定する
        "exact_overlap_by_pair": exact_overlap_by_pair,
        # 出力レコードの項目と値を設定する
        "sha256_collision_count": hash_collisions,
        # 出力レコードの項目と値を設定する
        "all_checks_passed": True,
    }
    # 処理結果を利用者へ表示する
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


# この工程を担当する関数を定義する
def _verify_group(
    # 次の値または処理を現在の構造へ組み込む
    group: dict[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    side_codes: dict[str, tuple[str, str]],
    # 次の値または処理を現在の構造へ組み込む
    all_code_ids: set[str],
# 次の値または処理を現在の構造へ組み込む
) -> dict[str, int]:
    # counts_by_specへこの工程で使用する値を設定する
    counts_by_spec: Counter[str] = Counter()
    # record_countへこの工程で使用する値を設定する
    record_count = 0
    # 対象を一件ずつ取り出して処理する
    for record in _read_jsonl(group["path"]):
        # 次の値または処理を現在の構造へ組み込む
        record_count += 1
        # spec_idへこの工程で使用する値を設定する
        spec_id = _required_string(record, "spec_id")
        # code_idへこの工程で使用する値を設定する
        code_id = _required_string(record, "code_id")
        # code_hashへこの工程で使用する値を設定する
        code_hash = _required_string(record, "code_hash")
        # sourceへこの工程で使用する値を設定する
        source = _required_string(record, "reference_code")

        # 条件を満たす場合だけ次の処理を行う
        if code_id in all_code_ids:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"code_idが重複しています: {code_id}")
        # 次の値または処理を現在の構造へ組み込む
        all_code_ids.add(code_id)
        # 条件を満たす場合だけ次の処理を行う
        if _sha256_text(source) != code_hash:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"code_hashが本文と一致しません: {code_id}")
        # 条件を満たす場合だけ次の処理を行う
        if record.get("split") != group["split"]:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"splitが不正です: {code_id}")
        # 条件を満たす場合だけ次の処理を行う
        if record.get("test_suite") != group["test_suite"]:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"test_suiteが不正です: {code_id}")
        # semantic_astへこの工程で使用する値を設定する
        semantic_ast = record.get("semantic_ast")
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(semantic_ast, dict):
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"semantic_astがありません: {code_id}")
        # sequenceへこの工程で使用する値を設定する
        sequence = semantic_ast.get("sequence")
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(sequence, list) or len(sequence) != group["operation_count"]:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"操作数が不正です: {code_id}")
        # 次の値または処理を現在の構造へ組み込む
        _verify_stored_result(record, code_id)
        # 次の値または処理を現在の構造へ組み込む
        _add_unique_code(side_codes, code_hash, source, code_id, str(group["side"]))
        # 次の値または処理を現在の構造へ組み込む
        counts_by_spec[spec_id] += 1

    # expected_recordsへこの工程で使用する値を設定する
    expected_records = int(group["spec_count"]) * EXPECTED_PER_SPEC
    # 条件を満たす場合だけ次の処理を行う
    if record_count != expected_records:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"{group['name']}: レコード数が不正です: "
            # 次の値または処理を現在の構造へ組み込む
            f"{record_count} != {expected_records}"
        )
    # 条件を満たす場合だけ次の処理を行う
    if len(counts_by_spec) != group["spec_count"]:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{group['name']}: 意味AST数が不正です")
    # shortfallsへこの工程で使用する値を設定する
    shortfalls = {
        # 次の値または処理を現在の構造へ組み込む
        spec_id: count
        # 対象を一件ずつ取り出して処理する
        for spec_id, count in counts_by_spec.items()
        # 条件を満たす場合だけ次の処理を行う
        if count != EXPECTED_PER_SPEC
    }
    # 条件を満たす場合だけ次の処理を行う
    if shortfalls:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{group['name']}: 20件でない意味ASTがあります: {shortfalls}")
    # 処理結果を呼び出し元へ返す
    return {
        # 出力レコードの項目と値を設定する
        "operation_count": int(group["operation_count"]),
        # 出力レコードの項目と値を設定する
        "semantic_ast_count": len(counts_by_spec),
        # 出力レコードの項目と値を設定する
        "records_per_semantic_ast": EXPECTED_PER_SPEC,
        # 出力レコードの項目と値を設定する
        "record_count": record_count,
    }


# この工程を担当する関数を定義する
def _add_existing_train_codes(
    # 次の値または処理を現在の構造へ組み込む
    train_codes: dict[str, tuple[str, str]],
    # 次の値または処理を現在の構造へ組み込む
    all_code_ids: set[str],
# 次の値または処理を現在の構造へ組み込む
) -> None:
    # 対象を一件ずつ取り出して処理する
    for record in _read_jsonl(SINGLE_OPERATION_PATH):
        # code_idへこの工程で使用する値を設定する
        code_id = _required_string(record, "code_id")
        # code_hashへこの工程で使用する値を設定する
        code_hash = _required_string(record, "code_hash")
        # sourceへこの工程で使用する値を設定する
        source = _required_string(record, "reference_code")
        # 条件を満たす場合だけ次の処理を行う
        if _sha256_text(source) != code_hash:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"code_hashが本文と一致しません: {code_id}")
        # 条件を満たす場合だけ次の処理を行う
        if code_id in all_code_ids:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"code_idが重複しています: {code_id}")
        # 次の値または処理を現在の構造へ組み込む
        all_code_ids.add(code_id)
        # 次の値または処理を現在の構造へ組み込む
        _verify_stored_result(record, code_id)
        # 次の値または処理を現在の構造へ組み込む
        _add_unique_code(train_codes, code_hash, source, code_id, "train")


# この工程を担当する関数を定義する
def _verify_stored_result(record: dict[str, Any], code_id: str) -> None:
    # verificationへこの工程で使用する値を設定する
    verification = record.get("verification")
    # expectedへこの工程で使用する値を設定する
    expected = {
        # 出力レコードの項目と値を設定する
        "syntax_ok": True,
        # 出力レコードの項目と値を設定する
        "ast_safe": True,
        # 出力レコードの項目と値を設定する
        "signature_ok": True,
        # 出力レコードの項目と値を設定する
        "tests_passed": True,
        # 出力レコードの項目と値を設定する
        "input_unchanged": True,
        # 出力レコードの項目と値を設定する
        "timeout": False,
        # 出力レコードの項目と値を設定する
        "error": None,
    }
    # 条件を満たす場合だけ次の処理を行う
    if verification != expected:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"検証結果が合格状態ではありません: {code_id}")


# この工程を担当する関数を定義する
def _add_unique_code(
    # 次の値または処理を現在の構造へ組み込む
    codes: dict[str, tuple[str, str]],
    # 次の値または処理を現在の構造へ組み込む
    code_hash: str,
    # 次の値または処理を現在の構造へ組み込む
    source: str,
    # 次の値または処理を現在の構造へ組み込む
    code_id: str,
    # 次の値または処理を現在の構造へ組み込む
    side: str,
# 次の値または処理を現在の構造へ組み込む
) -> None:
    # previousへこの工程で使用する値を設定する
    previous = codes.get(code_hash)
    # 条件を満たす場合だけ次の処理を行う
    if previous is None:
        # codes[code_hash]へこの工程で使用する値を設定する
        codes[code_hash] = (source, code_id)
        # 処理結果を呼び出し元へ返す
        return
    # 次の値または処理を現在の構造へ組み込む
    previous_source, previous_code_id = previous
    # 条件を満たす場合だけ次の処理を行う
    if previous_source == source:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"{side}内に完全重複があります: {previous_code_id}, {code_id}"
        )
    # 不正な状態を例外として通知して処理を停止する
    raise ValueError(f"SHA-256衝突があります: {code_hash}")


# この工程を担当する関数を定義する
def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    # 使用するリソースの開始と終了をこの範囲で管理する
    with path.open(encoding="utf-8") as source:
        # 対象を一件ずつ取り出して処理する
        for line_number, line in enumerate(source, start=1):
            # 条件を満たす場合だけ次の処理を行う
            if not line.strip():
                # 現在の対象を終えて次の対象へ進む
                continue
            # recordへこの工程で使用する値を設定する
            record = json.loads(line)
            # 条件を満たす場合だけ次の処理を行う
            if not isinstance(record, dict):
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"{path}:{line_number}: レコードは辞書にしてください")
            # 生成した値を呼び出し元へ一件ずつ返す
            yield record


# この工程を担当する関数を定義する
def _required_string(record: dict[str, Any], key: str) -> str:
    # valueへこの工程で使用する値を設定する
    value = record.get(key)
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(value, str) or not value:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"空でない{key}が必要です")
    # 処理結果を呼び出し元へ返す
    return value


# この工程を担当する関数を定義する
def _sha256_text(value: str) -> str:
    # 処理結果を呼び出し元へ返す
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# 条件を満たす場合だけ次の処理を行う
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    main()
