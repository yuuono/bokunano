"""2・3操作のコード候補について、件数、検証記録、完全重複を確認する。"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GROUPS = (
    {
        "name": "compositional_two_operation",
        "path": PROJECT_ROOT
        / "data/code_candidates/compositional/two_operation/python_code_candidates.jsonl",
        "operation_count": 2,
        "spec_count": 10,
        "split": "test",
        "test_suite": "compositional",
        "side": "compositional",
    },
    {
        "name": "compositional_three_operation",
        "path": PROJECT_ROOT
        / "data/code_candidates/compositional/three_operation/python_code_candidates.jsonl",
        "operation_count": 3,
        "spec_count": 660,
        "split": "test",
        "test_suite": "compositional",
        "side": "compositional",
    },
    {
        "name": "train_two_operation",
        "path": PROJECT_ROOT
        / "data/code_candidates/train/two_operation/python_code_candidates.jsonl",
        "operation_count": 2,
        "spec_count": 434,
        "split": "train",
        "test_suite": None,
        "side": "train",
    },
    {
        "name": "train_three_operation",
        "path": PROJECT_ROOT
        / "data/code_candidates/train/three_operation/python_code_candidates.jsonl",
        "operation_count": 3,
        "spec_count": 9_188,
        "split": "train",
        "test_suite": None,
        "side": "train",
    },
)

SINGLE_OPERATION_PATH = (
    PROJECT_ROOT
    / "data/code_candidates/single_operation/python_code_candidates.jsonl"
)
EXPECTED_PER_SPEC = 20


def main() -> None:
    summaries: dict[str, dict[str, int]] = {}
    side_codes: dict[str, dict[str, tuple[str, str]]] = {
        "train": {},
        "compositional": {},
    }
    all_code_ids: set[str] = set()

    _add_existing_train_codes(side_codes["train"], all_code_ids)
    for group in GROUPS:
        summaries[str(group["name"])] = _verify_group(
            group,
            side_codes[str(group["side"])],
            all_code_ids,
        )

    exact_overlap = 0
    hash_collisions = 0
    for code_hash, (evaluation_source, evaluation_code_id) in side_codes[
        "compositional"
    ].items():
        train_match = side_codes["train"].get(code_hash)
        if train_match is None:
            continue
        train_source, train_code_id = train_match
        if train_source == evaluation_source:
            exact_overlap += 1
            raise ValueError(
                "訓練側と組合せ汎化側に完全重複があります: "
                f"{train_code_id}, {evaluation_code_id}"
            )
        hash_collisions += 1
        raise ValueError(f"SHA-256衝突があります: {code_hash}")

    result = {
        "groups": summaries,
        "train_code_count_including_single_operation": len(side_codes["train"]),
        "compositional_code_count": len(side_codes["compositional"]),
        "train_compositional_exact_overlap": exact_overlap,
        "sha256_collision_count": hash_collisions,
        "all_checks_passed": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def _verify_group(
    group: dict[str, Any],
    side_codes: dict[str, tuple[str, str]],
    all_code_ids: set[str],
) -> dict[str, int]:
    counts_by_spec: Counter[str] = Counter()
    record_count = 0
    for record in _read_jsonl(group["path"]):
        record_count += 1
        spec_id = _required_string(record, "spec_id")
        code_id = _required_string(record, "code_id")
        code_hash = _required_string(record, "code_hash")
        source = _required_string(record, "reference_code")

        if code_id in all_code_ids:
            raise ValueError(f"code_idが重複しています: {code_id}")
        all_code_ids.add(code_id)
        if _sha256_text(source) != code_hash:
            raise ValueError(f"code_hashが本文と一致しません: {code_id}")
        if record.get("split") != group["split"]:
            raise ValueError(f"splitが不正です: {code_id}")
        if record.get("test_suite") != group["test_suite"]:
            raise ValueError(f"test_suiteが不正です: {code_id}")
        semantic_ast = record.get("semantic_ast")
        if not isinstance(semantic_ast, dict):
            raise ValueError(f"semantic_astがありません: {code_id}")
        sequence = semantic_ast.get("sequence")
        if not isinstance(sequence, list) or len(sequence) != group["operation_count"]:
            raise ValueError(f"操作数が不正です: {code_id}")
        _verify_stored_result(record, code_id)
        _add_unique_code(side_codes, code_hash, source, code_id, str(group["side"]))
        counts_by_spec[spec_id] += 1

    expected_records = int(group["spec_count"]) * EXPECTED_PER_SPEC
    if record_count != expected_records:
        raise ValueError(
            f"{group['name']}: レコード数が不正です: "
            f"{record_count} != {expected_records}"
        )
    if len(counts_by_spec) != group["spec_count"]:
        raise ValueError(f"{group['name']}: 意味AST数が不正です")
    shortfalls = {
        spec_id: count
        for spec_id, count in counts_by_spec.items()
        if count != EXPECTED_PER_SPEC
    }
    if shortfalls:
        raise ValueError(f"{group['name']}: 20件でない意味ASTがあります: {shortfalls}")
    return {
        "operation_count": int(group["operation_count"]),
        "semantic_ast_count": len(counts_by_spec),
        "records_per_semantic_ast": EXPECTED_PER_SPEC,
        "record_count": record_count,
    }


def _add_existing_train_codes(
    train_codes: dict[str, tuple[str, str]],
    all_code_ids: set[str],
) -> None:
    for record in _read_jsonl(SINGLE_OPERATION_PATH):
        code_id = _required_string(record, "code_id")
        code_hash = _required_string(record, "code_hash")
        source = _required_string(record, "reference_code")
        if _sha256_text(source) != code_hash:
            raise ValueError(f"code_hashが本文と一致しません: {code_id}")
        if code_id in all_code_ids:
            raise ValueError(f"code_idが重複しています: {code_id}")
        all_code_ids.add(code_id)
        _verify_stored_result(record, code_id)
        _add_unique_code(train_codes, code_hash, source, code_id, "train")


def _verify_stored_result(record: dict[str, Any], code_id: str) -> None:
    verification = record.get("verification")
    expected = {
        "syntax_ok": True,
        "ast_safe": True,
        "signature_ok": True,
        "tests_passed": True,
        "input_unchanged": True,
        "timeout": False,
        "error": None,
    }
    if verification != expected:
        raise ValueError(f"検証結果が合格状態ではありません: {code_id}")


def _add_unique_code(
    codes: dict[str, tuple[str, str]],
    code_hash: str,
    source: str,
    code_id: str,
    side: str,
) -> None:
    previous = codes.get(code_hash)
    if previous is None:
        codes[code_hash] = (source, code_id)
        return
    previous_source, previous_code_id = previous
    if previous_source == source:
        raise ValueError(
            f"{side}内に完全重複があります: {previous_code_id}, {code_id}"
        )
    raise ValueError(f"SHA-256衝突があります: {code_hash}")


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: レコードは辞書にしてください")
            yield record


def _required_string(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"空でない{key}が必要です")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
