"""意味ASTのJSONLから検証済みPythonコード候補のJSONLを生成する。

正式生成では設定JSONを読み、予備確認では同じ項目をコマンド引数で指定できる。
このスクリプトをimportしただけでは生成処理を開始しない。
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import sys
import tempfile
from typing import Any, Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from generated_code_verifier import (  # noqa: E402
    build_verification_cases,
    verify_generated_code,
)
from python_code_generator import (  # noqa: E402
    GENERATOR_VERSION,
    GeneratorConfig,
    generate_python_code,
    make_code_candidate_record,
    sha256_text,
)
from structural_variant_generator import StructuralVariantGenerator  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="意味ASTごとに構造的変種を作り、実行検証後のコードだけを保存します。"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="正式生成の設定JSON。指定時は生成条件をJSONから読みます。",
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="設定JSONを検査し、コードを生成せず終了します。",
    )
    parser.add_argument("--input", type=Path, help="意味ASTの入力JSONL")
    parser.add_argument("--output", type=Path, help="コード候補の出力JSONL")
    parser.add_argument(
        "--rejections",
        type=Path,
        help="不採用候補と理由を保存するJSONL",
    )
    parser.add_argument(
        "--stats",
        type=Path,
        help="件数集計を保存するJSON",
    )
    parser.add_argument(
        "--element-names",
        help="承認済み要素変数名。カンマ区切りで指定します。",
    )
    parser.add_argument(
        "--result-names",
        help="承認済み結果変数名。カンマ区切りで2つ以上指定します。",
    )
    parser.add_argument(
        "--target-verified-per-ast",
        type=int,
        help="1意味ASTから確保する、完全重複除外後の検証済みコード目標数。",
    )
    parser.add_argument(
        "--single-operation-only",
        action="store_true",
        help="最初の確認用。1操作AST以外が入力された場合は停止します。",
    )
    parser.add_argument(
        "--operation-count",
        type=int,
        choices=(1, 2, 3),
        help="指定した操作数の意味ASTだけを入力JSONLから選びます。",
    )
    parser.add_argument("--seed", type=int)
    parser.add_argument("--random-test-seed", type=int)
    parser.add_argument("--max-source-chars", type=int)
    parser.add_argument("--random-test-count", type=int)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument(
        "--exclude-code-jsonl",
        type=Path,
        action="append",
        default=None,
        help="完全一致を除外する既存コードレコード。複数回指定できます。",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="既存出力を置き換える場合だけ指定します。",
    )
    args = parser.parse_args()
    return _resolve_settings(args)


def _resolve_settings(args: argparse.Namespace) -> argparse.Namespace:
    """コマンド引数または正式設定JSONから実行条件を確定する。"""

    if args.validate_config and args.config is None:
        raise ValueError("--validate-configには--configが必要です")

    if args.config is not None:
        conflicts = [
            option
            for option, value in (
                ("--input", args.input),
                ("--output", args.output),
                ("--rejections", args.rejections),
                ("--stats", args.stats),
                ("--element-names", args.element_names),
                ("--result-names", args.result_names),
                ("--target-verified-per-ast", args.target_verified_per_ast),
                ("--operation-count", args.operation_count),
                ("--seed", args.seed),
                ("--random-test-seed", args.random_test_seed),
                ("--max-source-chars", args.max_source_chars),
                ("--random-test-count", args.random_test_count),
                ("--timeout-seconds", args.timeout_seconds),
                ("--exclude-code-jsonl", args.exclude_code_jsonl),
            )
            if value is not None
        ]
        if args.single_operation_only:
            conflicts.append("--single-operation-only")
        if conflicts:
            raise ValueError(
                "--configと生成条件の個別指定は併用できません: "
                + ", ".join(conflicts)
            )
        _apply_config_file(args)
        return args

    required = {
        "--input": args.input,
        "--output": args.output,
        "--rejections": args.rejections,
        "--stats": args.stats,
        "--element-names": args.element_names,
        "--result-names": args.result_names,
        "--target-verified-per-ast": args.target_verified_per_ast,
    }
    missing = [option for option, value in required.items() if value is None]
    if missing:
        raise ValueError("必須引数がありません: " + ", ".join(missing))

    args.seed = 0 if args.seed is None else args.seed
    args.random_test_seed = (
        args.seed if args.random_test_seed is None else args.random_test_seed
    )
    args.max_source_chars = 4_096 if args.max_source_chars is None else args.max_source_chars
    args.random_test_count = 32 if args.random_test_count is None else args.random_test_count
    args.timeout_seconds = 2.0 if args.timeout_seconds is None else args.timeout_seconds
    args.exclude_code_jsonl = args.exclude_code_jsonl or []
    args.config_hash = None
    return args


def _apply_config_file(args: argparse.Namespace) -> None:
    config_path = args.config.resolve()
    try:
        config_text = config_path.read_text(encoding="utf-8")
        raw = json.loads(config_text)
    except FileNotFoundError as error:
        raise ValueError(f"設定JSONが見つかりません: {config_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"設定JSONが不正です: {config_path}") from error
    if not isinstance(raw, dict):
        raise ValueError("設定JSONのルートは辞書にしてください")

    expected_keys = {
        "config_version",
        "phase",
        "input",
        "output",
        "rejections",
        "stats",
        "operation_count_filter",
        "target_verified_per_ast",
        "generator_version",
        "generator_seed",
        "element_names",
        "result_names",
        "max_source_chars",
        "verification",
        "exact_duplicate_check",
        "exclude_code_jsonl",
        "python",
    }
    if set(raw) != expected_keys:
        missing = sorted(expected_keys - set(raw))
        extra = sorted(set(raw) - expected_keys)
        raise ValueError(f"設定JSONの項目が不正です: 不足={missing}, 余分={extra}")
    if raw["config_version"] != 1:
        raise ValueError("config_versionは1にしてください")
    if not isinstance(raw["phase"], str) or not raw["phase"]:
        raise ValueError("phaseは空でない文字列にしてください")
    if raw["generator_version"] != GENERATOR_VERSION:
        raise ValueError(
            f"generator_versionが実装と一致しません: "
            f"{raw['generator_version']!r} != {GENERATOR_VERSION!r}"
        )

    args.input = _project_path(_config_string(raw, "input"))
    args.output = _project_path(_config_string(raw, "output"))
    args.rejections = _project_path(_config_string(raw, "rejections"))
    args.stats = _project_path(_config_string(raw, "stats"))
    if not args.input.is_file():
        raise ValueError(f"入力JSONLが見つかりません: {args.input}")

    operation_count = raw["operation_count_filter"]
    if type(operation_count) is not int or operation_count not in {1, 2, 3}:
        raise ValueError("operation_count_filterは1、2、3のいずれかにしてください")
    args.operation_count = operation_count
    args.target_verified_per_ast = _positive_int(raw, "target_verified_per_ast")
    args.seed = _integer(raw, "generator_seed")
    args.element_names = ",".join(_name_list(raw, "element_names"))
    args.result_names = ",".join(_name_list(raw, "result_names"))
    args.max_source_chars = _positive_int(raw, "max_source_chars")
    args.single_operation_only = False

    verification = _mapping(raw, "verification")
    expected_verification_keys = {
        "reference",
        "boundary_case_count",
        "random_case_count",
        "random_seed",
        "timeout_seconds",
        "require_input_unchanged",
    }
    _require_exact_keys(verification, expected_verification_keys, "verification")
    reference_path = _project_path(_config_string(verification, "reference"))
    if not reference_path.is_file():
        raise ValueError(f"参照インタプリタが見つかりません: {reference_path}")
    args.random_test_count = _nonnegative_int(verification, "random_case_count")
    args.random_test_seed = _integer(verification, "random_seed")
    boundary_count = _nonnegative_int(verification, "boundary_case_count")
    actual_boundary_count = len(build_verification_cases(args.random_test_seed, 0))
    if boundary_count != actual_boundary_count:
        raise ValueError(
            f"boundary_case_countが実装と一致しません: "
            f"{boundary_count} != {actual_boundary_count}"
        )
    timeout_seconds = verification["timeout_seconds"]
    if type(timeout_seconds) not in {int, float} or timeout_seconds <= 0:
        raise ValueError("timeout_secondsは正の数にしてください")
    args.timeout_seconds = float(timeout_seconds)
    if verification["require_input_unchanged"] is not True:
        raise ValueError("require_input_unchangedはtrueにしてください")

    duplicate_check = _mapping(raw, "exact_duplicate_check")
    _require_exact_keys(
        duplicate_check,
        {"lookup", "final_comparison"},
        "exact_duplicate_check",
    )
    if duplicate_check != {
        "lookup": "sha256",
        "final_comparison": "full_reference_code",
    }:
        raise ValueError("完全重複判定はSHA-256検索後の全文比較にしてください")

    excluded = raw["exclude_code_jsonl"]
    if not isinstance(excluded, list) or any(
        not isinstance(path, str) or not path for path in excluded
    ):
        raise ValueError("exclude_code_jsonlはパス文字列のリストにしてください")
    args.exclude_code_jsonl = [_project_path(path) for path in excluded]
    missing_exclusions = [str(path) for path in args.exclude_code_jsonl if not path.is_file()]
    if missing_exclusions:
        raise ValueError("除外用JSONLが見つかりません: " + ", ".join(missing_exclusions))

    python_settings = _mapping(raw, "python")
    _require_exact_keys(python_settings, {"version", "lockfile"}, "python")
    requested_python = _config_string(python_settings, "version")
    actual_python = ".".join(platform.python_version().split(".")[:2])
    if requested_python != actual_python:
        raise ValueError(
            f"Pythonバージョンが設定と一致しません: "
            f"{requested_python} != {actual_python}"
        )
    lockfile = _project_path(_config_string(python_settings, "lockfile"))
    if not lockfile.is_file():
        raise ValueError(f"ロックファイルが見つかりません: {lockfile}")

    args.config = config_path
    args.config_hash = sha256_text(config_text)


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _mapping(record: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key}は辞書にしてください")
    return value


def _config_string(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key}は空でない文字列にしてください")
    return value


def _integer(record: Mapping[str, Any], key: str) -> int:
    value = record.get(key)
    if type(value) is not int:
        raise ValueError(f"{key}は整数にしてください")
    return value


def _positive_int(record: Mapping[str, Any], key: str) -> int:
    value = _integer(record, key)
    if value <= 0:
        raise ValueError(f"{key}は正の整数にしてください")
    return value


def _nonnegative_int(record: Mapping[str, Any], key: str) -> int:
    value = _integer(record, key)
    if value < 0:
        raise ValueError(f"{key}は0以上の整数にしてください")
    return value


def _name_list(record: Mapping[str, Any], key: str) -> list[str]:
    value = record.get(key)
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(name, str) or not name for name in value)
        or len(value) != len(set(value))
    ):
        raise ValueError(f"{key}は重複のない文字列リストにしてください")
    return value


def _require_exact_keys(
    record: Mapping[str, Any], expected: set[str], label: str
) -> None:
    if set(record) != expected:
        missing = sorted(expected - set(record))
        extra = sorted(set(record) - expected)
        raise ValueError(f"{label}の項目が不正です: 不足={missing}, 余分={extra}")


def main() -> None:
    args = parse_args()
    if args.target_verified_per_ast <= 0:
        raise ValueError("target-verified-per-astは正の整数にしてください")

    config = GeneratorConfig(
        element_names=_parse_names(args.element_names, "element-names"),
        result_names=_parse_names(args.result_names, "result-names"),
        max_source_chars=args.max_source_chars,
    )
    if args.validate_config:
        _check_paths(
            input_path=args.input,
            excluded_paths=args.exclude_code_jsonl,
            output_paths=(args.output, args.rejections, args.stats),
            overwrite=True,
        )
        print(f"設定JSONは有効です: {args.config}")
        return

    _check_paths(
        input_path=args.input,
        excluded_paths=args.exclude_code_jsonl,
        output_paths=(args.output, args.rejections, args.stats),
        overwrite=args.overwrite,
    )
    variant_generator = StructuralVariantGenerator(config, seed=args.seed)
    cases = build_verification_cases(args.random_test_seed, args.random_test_count)
    excluded_codes = _load_excluded_codes(args.exclude_code_jsonl)

    counters: Counter[str] = Counter()
    per_spec: dict[str, Counter[str]] = {}
    seen_codes: dict[str, tuple[str, str | None]] = dict(excluded_codes)
    shortfall_specs: list[dict[str, Any]] = []

    with _atomic_text_writer(args.output) as output_file, _atomic_text_writer(
        args.rejections
    ) as rejection_file:
        for input_record in _read_jsonl(args.input):
            spec_id = _required_string(input_record, "spec_id")
            semantic_ast = input_record.get("semantic_ast")
            if not isinstance(semantic_ast, Mapping):
                raise ValueError(f"{spec_id}: semantic_astがありません")
            operation_count = _operation_count(semantic_ast)
            if (
                args.operation_count is not None
                and operation_count != args.operation_count
            ):
                counters["skipped_input_count"] += 1
                continue
            if args.single_operation_only and operation_count != 1:
                raise ValueError(f"{spec_id}: 最初の確認では1操作ASTだけを入力してください")

            spec_counts: Counter[str] = Counter()
            variants = variant_generator.enumerate(semantic_ast)
            spec_counts["available_style_count"] = len(variants)
            counters["available_style_count"] += len(variants)

            for variant in variants:
                if spec_counts["deduplicated_count"] >= args.target_verified_per_ast:
                    break
                spec_counts["candidate_count"] += 1
                counters["candidate_count"] += 1
                try:
                    generated = generate_python_code(semantic_ast, variant, config)
                except Exception as error:
                    _write_jsonl(
                        rejection_file,
                        {
                            "spec_id": spec_id,
                            "style_spec": variant,
                            "reason": "generation_or_static_validation_failed",
                            "error": f"{type(error).__name__}: {error}",
                        },
                    )
                    spec_counts["static_rejected_count"] += 1
                    counters["static_rejected_count"] += 1
                    continue

                verification = verify_generated_code(
                    generated.reference_code,
                    semantic_ast,
                    cases,
                    timeout_seconds=args.timeout_seconds,
                    max_source_chars=config.max_source_chars,
                )
                if not verification.tests_passed:
                    _write_jsonl(
                        rejection_file,
                        {
                            "spec_id": spec_id,
                            "style_id": generated.style_id,
                            "code_hash": generated.code_hash,
                            "reason": "execution_verification_failed",
                            "verification": verification.to_record(),
                        },
                    )
                    spec_counts["verification_rejected_count"] += 1
                    counters["verification_rejected_count"] += 1
                    continue

                spec_counts["verified_count"] += 1
                counters["verified_count"] += 1
                candidate_record = make_code_candidate_record(
                    input_record,
                    generated,
                    args.seed,
                    verification.to_record(),
                )
                matched = seen_codes.get(generated.code_hash)
                if matched is not None:
                    matched_source, matched_code_id = matched
                    if matched_source != generated.reference_code:
                        raise RuntimeError(f"SHA-256衝突を検出しました: {generated.code_hash}")
                    _write_jsonl(
                        rejection_file,
                        {
                            "spec_id": spec_id,
                            "style_id": generated.style_id,
                            "code_hash": generated.code_hash,
                            "matched_code_id": matched_code_id,
                            "reason": "exact_duplicate_code",
                        },
                    )
                    spec_counts["duplicate_count"] += 1
                    counters["duplicate_count"] += 1
                    continue

                seen_codes[generated.code_hash] = (
                    generated.reference_code,
                    str(candidate_record["code_id"]),
                )
                _write_jsonl(output_file, candidate_record)
                spec_counts["deduplicated_count"] += 1
                counters["deduplicated_count"] += 1

            if spec_counts["deduplicated_count"] < args.target_verified_per_ast:
                shortfall = {
                    "spec_id": spec_id,
                    "operation_count": operation_count,
                    "target": args.target_verified_per_ast,
                    "accepted": spec_counts["deduplicated_count"],
                    "available_style_count": spec_counts["available_style_count"],
                }
                shortfall_specs.append(shortfall)
                _write_jsonl(
                    rejection_file,
                    {**shortfall, "reason": "verified_code_target_shortfall"},
                )
                spec_counts["target_shortfall"] = 1
                counters["target_shortfall"] += 1

            per_spec[spec_id] = spec_counts

    stats = {
        "input": str(args.input),
        "output": str(args.output),
        "config": str(args.config) if args.config is not None else None,
        "config_hash": args.config_hash,
        "generator_seed": args.seed,
        "target_verified_per_ast": args.target_verified_per_ast,
        "single_operation_only": args.single_operation_only,
        "operation_count_filter": args.operation_count,
        "element_names": list(config.element_names),
        "result_names": list(config.result_names),
        "max_source_chars": config.max_source_chars,
        "boundary_test_count": len(cases) - args.random_test_count,
        "random_test_count": args.random_test_count,
        "random_test_seed": args.random_test_seed,
        "verification_case_count": len(cases),
        "timeout_seconds": args.timeout_seconds,
        "python_version": platform.python_version(),
        "shortfall_specs": shortfall_specs,
        "totals": dict(sorted(counters.items())),
        "per_spec": {
            spec_id: dict(sorted(counts.items()))
            for spec_id, counts in sorted(per_spec.items())
        },
    }
    _write_json_file_atomic(args.stats, stats)
    if shortfall_specs:
        raise RuntimeError(
            f"検証済み固有コードが目標へ届かない意味ASTが{len(shortfall_specs)}件あります"
        )


def _parse_names(raw: str, option_name: str) -> tuple[str, ...]:
    names = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not names:
        raise ValueError(f"{option_name}を1つ以上指定してください")
    if len(names) != len(set(names)):
        raise ValueError(f"{option_name}に重複があります")
    return names


def _required_string(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"空でない{key}が必要です")
    return value


def _operation_count(semantic_ast: Mapping[str, Any]) -> int:
    if set(semantic_ast) == {"sequence"}:
        sequence = semantic_ast["sequence"]
        if not isinstance(sequence, list):
            raise ValueError("semantic_ast.sequenceはリストにしてください")
        return len(sequence)
    return 1


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: JSONが不正です") from error
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: レコードは辞書にしてください")
            yield record


def _load_excluded_codes(paths: Iterable[Path]) -> dict[str, tuple[str, str | None]]:
    excluded: dict[str, tuple[str, str | None]] = {}
    for path in paths:
        for record in _read_jsonl(path):
            code_hash = _required_string(record, "code_hash")
            source = _required_string(record, "reference_code")
            code_id_value = record.get("code_id")
            if code_id_value is not None and not isinstance(code_id_value, str):
                raise ValueError(f"{path}: code_idは文字列またはnullにしてください")
            previous = excluded.get(code_hash)
            if previous is not None and previous[0] != source:
                raise RuntimeError(f"SHA-256衝突を検出しました: {code_hash}")
            excluded[code_hash] = (source, code_id_value)
    return excluded


def _write_jsonl(destination: Any, record: Mapping[str, Any]) -> None:
    destination.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


class _atomic_text_writer:
    def __init__(self, destination: Path) -> None:
        self.destination = destination
        self.temporary_path: Path | None = None
        self.handle: Any = None

    def __enter__(self) -> Any:
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=self.destination.parent,
            prefix=f".{self.destination.name}.",
            suffix=".tmp",
            delete=False,
        )
        self.temporary_path = Path(temporary.name)
        self.handle = temporary
        return temporary

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.handle is not None:
            self.handle.close()
        if self.temporary_path is None:
            return
        if exc_type is None:
            self.temporary_path.replace(self.destination)
        elif self.temporary_path.exists():
            self.temporary_path.unlink()


def _write_json_file_atomic(path: Path, value: Mapping[str, Any]) -> None:
    with _atomic_text_writer(path) as destination:
        json.dump(value, destination, ensure_ascii=False, indent=2, sort_keys=True)
        destination.write("\n")


def _check_paths(
    input_path: Path,
    excluded_paths: Iterable[Path],
    output_paths: Iterable[Path],
    overwrite: bool,
) -> None:
    outputs = tuple(output_paths)
    duplicates = [str(path.resolve()) for path in outputs]
    if len(duplicates) != len(set(duplicates)):
        raise ValueError("output、rejections、statsには別々のパスを指定してください")
    protected = {input_path.resolve(), *(path.resolve() for path in excluded_paths)}
    overlapping = [str(path) for path in outputs if path.resolve() in protected]
    if overlapping:
        raise ValueError("入力ファイルを出力先に指定できません: " + ", ".join(overlapping))
    existing = [str(path) for path in outputs if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "既存ファイルがあります。置換する場合だけ--overwriteを指定してください: "
            + ", ".join(existing)
        )


if __name__ == "__main__":
    main()
