"""意味ASTのJSONLから検証済みPythonコード候補のJSONLを生成する。

正式生成では設定JSONを読み、予備確認では同じ項目をコマンド引数で指定できる。
このスクリプトをimportしただけでは生成処理を開始しない。
"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# この処理で使う標準または外部モジュールを読み込む
import argparse
# 必要な定義を対象モジュールから読み込む
from collections import Counter
# この処理で使う標準または外部モジュールを読み込む
import json
# 必要な定義を対象モジュールから読み込む
from pathlib import Path
# この処理で使う標準または外部モジュールを読み込む
import platform
# この処理で使う標準または外部モジュールを読み込む
import sys
# この処理で使う標準または外部モジュールを読み込む
import tempfile
# 必要な定義を対象モジュールから読み込む
from typing import Any, Iterable, Mapping


# PROJECT_ROOTへこの工程で使用する値を設定する
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 条件を満たす場合だけ次の処理を行う
if str(PROJECT_ROOT) not in sys.path:
    # 次の値または処理を現在の構造へ組み込む
    sys.path.insert(0, str(PROJECT_ROOT))

from generated_code_verifier import (  # noqa: E402
    # 次の値または処理を現在の構造へ組み込む
    GeneratedCodeVerifierSession,
    # 次の値または処理を現在の構造へ組み込む
    build_verification_cases,
)
from python_code_generator import (  # noqa: E402
    # 次の値または処理を現在の構造へ組み込む
    GENERATOR_VERSION,
    # 次の値または処理を現在の構造へ組み込む
    GeneratorConfig,
    # 次の値または処理を現在の構造へ組み込む
    generate_python_code,
    # 次の値または処理を現在の構造へ組み込む
    make_code_candidate_record,
    # 次の値または処理を現在の構造へ組み込む
    sha256_text,
)
from structural_variant_generator import StructuralVariantGenerator  # noqa: E402


# この工程を担当する関数を定義する
def parse_args() -> argparse.Namespace:
    # parserへこの工程で使用する値を設定する
    parser = argparse.ArgumentParser(
        # descriptionへこの工程で使用する値を設定する
        description="意味ASTごとに構造的変種を作り、実行検証後のコードだけを保存します。"
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--config",
        # typeへこの工程で使用する値を設定する
        type=Path,
        # helpへこの工程で使用する値を設定する
        help="正式生成の設定JSON。指定時は生成条件をJSONから読みます。",
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--validate-config",
        # actionへこの工程で使用する値を設定する
        action="store_true",
        # helpへこの工程で使用する値を設定する
        help="設定JSONを検査し、コードを生成せず終了します。",
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--input", type=Path, help="意味ASTの入力JSONL")
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--output", type=Path, help="コード候補の出力JSONL")
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--rejections",
        # typeへこの工程で使用する値を設定する
        type=Path,
        # helpへこの工程で使用する値を設定する
        help="不採用候補と理由を保存するJSONL",
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--stats",
        # typeへこの工程で使用する値を設定する
        type=Path,
        # helpへこの工程で使用する値を設定する
        help="件数集計を保存するJSON",
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--element-names",
        # helpへこの工程で使用する値を設定する
        help="承認済み要素変数名。カンマ区切りで指定します。",
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--result-names",
        # helpへこの工程で使用する値を設定する
        help="承認済み結果変数名。カンマ区切りで2つ以上指定します。",
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--target-verified-per-ast",
        # typeへこの工程で使用する値を設定する
        type=int,
        # helpへこの工程で使用する値を設定する
        help="1意味ASTから確保する、完全重複除外後の検証済みコード目標数。",
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--single-operation-only",
        # actionへこの工程で使用する値を設定する
        action="store_true",
        # helpへこの工程で使用する値を設定する
        help="最初の確認用。1操作AST以外が入力された場合は停止します。",
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--operation-count",
        # typeへこの工程で使用する値を設定する
        type=int,
        # choicesへこの工程で使用する値を設定する
        choices=(1, 2, 3),
        # helpへこの工程で使用する値を設定する
        help="指定した操作数の意味ASTだけを入力JSONLから選びます。",
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--seed", type=int)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--random-test-seed", type=int)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--max-source-chars", type=int)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--random-test-count", type=int)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--timeout-seconds", type=float)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--exclude-code-jsonl",
        # typeへこの工程で使用する値を設定する
        type=Path,
        # actionへこの工程で使用する値を設定する
        action="append",
        # defaultへこの工程で使用する値を設定する
        default=None,
        # helpへこの工程で使用する値を設定する
        help="完全一致を除外する既存コードレコード。複数回指定できます。",
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--overwrite",
        # actionへこの工程で使用する値を設定する
        action="store_true",
        # helpへこの工程で使用する値を設定する
        help="既存出力を置き換える場合だけ指定します。",
    )
    # argsへこの工程で使用する値を設定する
    args = parser.parse_args()
    # 処理結果を呼び出し元へ返す
    return _resolve_settings(args)


# この工程を担当する関数を定義する
def _resolve_settings(args: argparse.Namespace) -> argparse.Namespace:
    """コマンド引数または正式設定JSONから実行条件を確定する。"""

    # 条件を満たす場合だけ次の処理を行う
    if args.validate_config and args.config is None:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("--validate-configには--configが必要です")

    # 条件を満たす場合だけ次の処理を行う
    if args.config is not None:
        # conflictsへこの工程で使用する値を設定する
        conflicts = [
            # 次の値または処理を現在の構造へ組み込む
            option
            # 対象を一件ずつ取り出して処理する
            for option, value in (
                # 次の値または処理を現在の構造へ組み込む
                ("--input", args.input),
                # 次の値または処理を現在の構造へ組み込む
                ("--output", args.output),
                # 次の値または処理を現在の構造へ組み込む
                ("--rejections", args.rejections),
                # 次の値または処理を現在の構造へ組み込む
                ("--stats", args.stats),
                # 次の値または処理を現在の構造へ組み込む
                ("--element-names", args.element_names),
                # 次の値または処理を現在の構造へ組み込む
                ("--result-names", args.result_names),
                # 次の値または処理を現在の構造へ組み込む
                ("--target-verified-per-ast", args.target_verified_per_ast),
                # 次の値または処理を現在の構造へ組み込む
                ("--operation-count", args.operation_count),
                # 次の値または処理を現在の構造へ組み込む
                ("--seed", args.seed),
                # 次の値または処理を現在の構造へ組み込む
                ("--random-test-seed", args.random_test_seed),
                # 次の値または処理を現在の構造へ組み込む
                ("--max-source-chars", args.max_source_chars),
                # 次の値または処理を現在の構造へ組み込む
                ("--random-test-count", args.random_test_count),
                # 次の値または処理を現在の構造へ組み込む
                ("--timeout-seconds", args.timeout_seconds),
                # 次の値または処理を現在の構造へ組み込む
                ("--exclude-code-jsonl", args.exclude_code_jsonl),
            )
            # 条件を満たす場合だけ次の処理を行う
            if value is not None
        ]
        # 条件を満たす場合だけ次の処理を行う
        if args.single_operation_only:
            # 次の値または処理を現在の構造へ組み込む
            conflicts.append("--single-operation-only")
        # 条件を満たす場合だけ次の処理を行う
        if conflicts:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                "--configと生成条件の個別指定は併用できません: "
                # 次の値または処理を現在の構造へ組み込む
                + ", ".join(conflicts)
            )
        # 次の値または処理を現在の構造へ組み込む
        _apply_config_file(args)
        # 処理結果を呼び出し元へ返す
        return args

    # requiredへこの工程で使用する値を設定する
    required = {
        # 出力レコードの項目と値を設定する
        "--input": args.input,
        # 出力レコードの項目と値を設定する
        "--output": args.output,
        # 出力レコードの項目と値を設定する
        "--rejections": args.rejections,
        # 出力レコードの項目と値を設定する
        "--stats": args.stats,
        # 出力レコードの項目と値を設定する
        "--element-names": args.element_names,
        # 出力レコードの項目と値を設定する
        "--result-names": args.result_names,
        # 出力レコードの項目と値を設定する
        "--target-verified-per-ast": args.target_verified_per_ast,
    }
    # missingへこの工程で使用する値を設定する
    missing = [option for option, value in required.items() if value is None]
    # 条件を満たす場合だけ次の処理を行う
    if missing:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("必須引数がありません: " + ", ".join(missing))

    # args.seedへこの工程で使用する値を設定する
    args.seed = 0 if args.seed is None else args.seed
    # args.random_test_seedへこの工程で使用する値を設定する
    args.random_test_seed = (
        # 次の値または処理を現在の構造へ組み込む
        args.seed if args.random_test_seed is None else args.random_test_seed
    )
    # args.max_source_charsへこの工程で使用する値を設定する
    args.max_source_chars = 4_096 if args.max_source_chars is None else args.max_source_chars
    # args.random_test_countへこの工程で使用する値を設定する
    args.random_test_count = 32 if args.random_test_count is None else args.random_test_count
    # args.timeout_secondsへこの工程で使用する値を設定する
    args.timeout_seconds = 2.0 if args.timeout_seconds is None else args.timeout_seconds
    # args.exclude_code_jsonlへこの工程で使用する値を設定する
    args.exclude_code_jsonl = args.exclude_code_jsonl or []
    # args.config_hashへこの工程で使用する値を設定する
    args.config_hash = None
    # 処理結果を呼び出し元へ返す
    return args


# この工程を担当する関数を定義する
def _apply_config_file(args: argparse.Namespace) -> None:
    # config_pathへこの工程で使用する値を設定する
    config_path = args.config.resolve()
    # 失敗する可能性がある処理を開始する
    try:
        # config_textへこの工程で使用する値を設定する
        config_text = config_path.read_text(encoding="utf-8")
        # rawへこの工程で使用する値を設定する
        raw = json.loads(config_text)
    # 発生した例外を受け取り、安全に処理する
    except FileNotFoundError as error:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"設定JSONが見つかりません: {config_path}") from error
    # 発生した例外を受け取り、安全に処理する
    except json.JSONDecodeError as error:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"設定JSONが不正です: {config_path}") from error
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(raw, dict):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("設定JSONのルートは辞書にしてください")

    # expected_keysへこの工程で使用する値を設定する
    expected_keys = {
        # この処理で扱う文字列を一覧へ加える
        "config_version",
        # この処理で扱う文字列を一覧へ加える
        "phase",
        # この処理で扱う文字列を一覧へ加える
        "input",
        # この処理で扱う文字列を一覧へ加える
        "output",
        # この処理で扱う文字列を一覧へ加える
        "rejections",
        # この処理で扱う文字列を一覧へ加える
        "stats",
        # この処理で扱う文字列を一覧へ加える
        "operation_count_filter",
        # この処理で扱う文字列を一覧へ加える
        "target_verified_per_ast",
        # この処理で扱う文字列を一覧へ加える
        "generator_version",
        # この処理で扱う文字列を一覧へ加える
        "generator_seed",
        # この処理で扱う文字列を一覧へ加える
        "element_names",
        # この処理で扱う文字列を一覧へ加える
        "result_names",
        # この処理で扱う文字列を一覧へ加える
        "max_source_chars",
        # この処理で扱う文字列を一覧へ加える
        "verification",
        # この処理で扱う文字列を一覧へ加える
        "exact_duplicate_check",
        # この処理で扱う文字列を一覧へ加える
        "exclude_code_jsonl",
        # この処理で扱う文字列を一覧へ加える
        "python",
    }
    # 条件を満たす場合だけ次の処理を行う
    if set(raw) != expected_keys:
        # missingへこの工程で使用する値を設定する
        missing = sorted(expected_keys - set(raw))
        # extraへこの工程で使用する値を設定する
        extra = sorted(set(raw) - expected_keys)
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"設定JSONの項目が不正です: 不足={missing}, 余分={extra}")
    # 条件を満たす場合だけ次の処理を行う
    if raw["config_version"] != 1:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("config_versionは1にしてください")
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(raw["phase"], str) or not raw["phase"]:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("phaseは空でない文字列にしてください")
    # 条件を満たす場合だけ次の処理を行う
    if raw["generator_version"] != GENERATOR_VERSION:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"generator_versionが実装と一致しません: "
            # 次の値または処理を現在の構造へ組み込む
            f"{raw['generator_version']!r} != {GENERATOR_VERSION!r}"
        )

    # args.inputへこの工程で使用する値を設定する
    args.input = _project_path(_config_string(raw, "input"))
    # args.outputへこの工程で使用する値を設定する
    args.output = _project_path(_config_string(raw, "output"))
    # args.rejectionsへこの工程で使用する値を設定する
    args.rejections = _project_path(_config_string(raw, "rejections"))
    # args.statsへこの工程で使用する値を設定する
    args.stats = _project_path(_config_string(raw, "stats"))
    # 条件を満たす場合だけ次の処理を行う
    if not args.input.is_file():
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"入力JSONLが見つかりません: {args.input}")

    # operation_countへこの工程で使用する値を設定する
    operation_count = raw["operation_count_filter"]
    # 条件を満たす場合だけ次の処理を行う
    if type(operation_count) is not int or operation_count not in {1, 2, 3}:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("operation_count_filterは1、2、3のいずれかにしてください")
    # args.operation_countへこの工程で使用する値を設定する
    args.operation_count = operation_count
    # args.target_verified_per_astへこの工程で使用する値を設定する
    args.target_verified_per_ast = _positive_int(raw, "target_verified_per_ast")
    # args.seedへこの工程で使用する値を設定する
    args.seed = _integer(raw, "generator_seed")
    # args.element_namesへこの工程で使用する値を設定する
    args.element_names = ",".join(_name_list(raw, "element_names"))
    # args.result_namesへこの工程で使用する値を設定する
    args.result_names = ",".join(_name_list(raw, "result_names"))
    # args.max_source_charsへこの工程で使用する値を設定する
    args.max_source_chars = _positive_int(raw, "max_source_chars")
    # args.single_operation_onlyへこの工程で使用する値を設定する
    args.single_operation_only = False

    # verificationへこの工程で使用する値を設定する
    verification = _mapping(raw, "verification")
    # expected_verification_keysへこの工程で使用する値を設定する
    expected_verification_keys = {
        # この処理で扱う文字列を一覧へ加える
        "reference",
        # この処理で扱う文字列を一覧へ加える
        "boundary_case_count",
        # この処理で扱う文字列を一覧へ加える
        "random_case_count",
        # この処理で扱う文字列を一覧へ加える
        "random_seed",
        # この処理で扱う文字列を一覧へ加える
        "timeout_seconds",
        # この処理で扱う文字列を一覧へ加える
        "require_input_unchanged",
    }
    # 次の値または処理を現在の構造へ組み込む
    _require_exact_keys(verification, expected_verification_keys, "verification")
    # reference_pathへこの工程で使用する値を設定する
    reference_path = _project_path(_config_string(verification, "reference"))
    # 条件を満たす場合だけ次の処理を行う
    if not reference_path.is_file():
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"参照インタプリタが見つかりません: {reference_path}")
    # args.random_test_countへこの工程で使用する値を設定する
    args.random_test_count = _nonnegative_int(verification, "random_case_count")
    # args.random_test_seedへこの工程で使用する値を設定する
    args.random_test_seed = _integer(verification, "random_seed")
    # boundary_countへこの工程で使用する値を設定する
    boundary_count = _nonnegative_int(verification, "boundary_case_count")
    # actual_boundary_countへこの工程で使用する値を設定する
    actual_boundary_count = len(build_verification_cases(args.random_test_seed, 0))
    # 条件を満たす場合だけ次の処理を行う
    if boundary_count != actual_boundary_count:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"boundary_case_countが実装と一致しません: "
            # 次の値または処理を現在の構造へ組み込む
            f"{boundary_count} != {actual_boundary_count}"
        )
    # timeout_secondsへこの工程で使用する値を設定する
    timeout_seconds = verification["timeout_seconds"]
    # 条件を満たす場合だけ次の処理を行う
    if type(timeout_seconds) not in {int, float} or timeout_seconds <= 0:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("timeout_secondsは正の数にしてください")
    # args.timeout_secondsへこの工程で使用する値を設定する
    args.timeout_seconds = float(timeout_seconds)
    # 条件を満たす場合だけ次の処理を行う
    if verification["require_input_unchanged"] is not True:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("require_input_unchangedはtrueにしてください")

    # duplicate_checkへこの工程で使用する値を設定する
    duplicate_check = _mapping(raw, "exact_duplicate_check")
    # 次の値または処理を現在の構造へ組み込む
    _require_exact_keys(
        # 次の値または処理を現在の構造へ組み込む
        duplicate_check,
        # 次の値または処理を現在の構造へ組み込む
        {"lookup", "final_comparison"},
        # この処理で扱う文字列を一覧へ加える
        "exact_duplicate_check",
    )
    # 条件を満たす場合だけ次の処理を行う
    if duplicate_check != {
        # 出力レコードの項目と値を設定する
        "lookup": "sha256",
        # 出力レコードの項目と値を設定する
        "final_comparison": "full_reference_code",
    # 次の値または処理を現在の構造へ組み込む
    }:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("完全重複判定はSHA-256検索後の全文比較にしてください")

    # excludedへこの工程で使用する値を設定する
    excluded = raw["exclude_code_jsonl"]
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(excluded, list) or any(
        # 次の値または処理を現在の構造へ組み込む
        not isinstance(path, str) or not path for path in excluded
    # 次の値または処理を現在の構造へ組み込む
    ):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("exclude_code_jsonlはパス文字列のリストにしてください")
    # args.exclude_code_jsonlへこの工程で使用する値を設定する
    args.exclude_code_jsonl = [_project_path(path) for path in excluded]
    # missing_exclusionsへこの工程で使用する値を設定する
    missing_exclusions = [str(path) for path in args.exclude_code_jsonl if not path.is_file()]
    # 条件を満たす場合だけ次の処理を行う
    if missing_exclusions:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("除外用JSONLが見つかりません: " + ", ".join(missing_exclusions))

    # python_settingsへこの工程で使用する値を設定する
    python_settings = _mapping(raw, "python")
    # 次の値または処理を現在の構造へ組み込む
    _require_exact_keys(python_settings, {"version", "lockfile"}, "python")
    # requested_pythonへこの工程で使用する値を設定する
    requested_python = _config_string(python_settings, "version")
    # actual_pythonへこの工程で使用する値を設定する
    actual_python = ".".join(platform.python_version().split(".")[:2])
    # 条件を満たす場合だけ次の処理を行う
    if requested_python != actual_python:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            # 次の値または処理を現在の構造へ組み込む
            f"Pythonバージョンが設定と一致しません: "
            # 次の値または処理を現在の構造へ組み込む
            f"{requested_python} != {actual_python}"
        )
    # lockfileへこの工程で使用する値を設定する
    lockfile = _project_path(_config_string(python_settings, "lockfile"))
    # 条件を満たす場合だけ次の処理を行う
    if not lockfile.is_file():
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"ロックファイルが見つかりません: {lockfile}")

    # args.configへこの工程で使用する値を設定する
    args.config = config_path
    # args.config_hashへこの工程で使用する値を設定する
    args.config_hash = sha256_text(config_text)


# この工程を担当する関数を定義する
def _project_path(value: str) -> Path:
    # pathへこの工程で使用する値を設定する
    path = Path(value)
    # 処理結果を呼び出し元へ返す
    return path if path.is_absolute() else PROJECT_ROOT / path


# この工程を担当する関数を定義する
def _mapping(record: Mapping[str, Any], key: str) -> dict[str, Any]:
    # valueへこの工程で使用する値を設定する
    value = record.get(key)
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(value, dict):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は辞書にしてください")
    # 処理結果を呼び出し元へ返す
    return value


# この工程を担当する関数を定義する
def _config_string(record: Mapping[str, Any], key: str) -> str:
    # valueへこの工程で使用する値を設定する
    value = record.get(key)
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(value, str) or not value:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は空でない文字列にしてください")
    # 処理結果を呼び出し元へ返す
    return value


# この工程を担当する関数を定義する
def _integer(record: Mapping[str, Any], key: str) -> int:
    # valueへこの工程で使用する値を設定する
    value = record.get(key)
    # 条件を満たす場合だけ次の処理を行う
    if type(value) is not int:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は整数にしてください")
    # 処理結果を呼び出し元へ返す
    return value


# この工程を担当する関数を定義する
def _positive_int(record: Mapping[str, Any], key: str) -> int:
    # valueへこの工程で使用する値を設定する
    value = _integer(record, key)
    # 条件を満たす場合だけ次の処理を行う
    if value <= 0:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は正の整数にしてください")
    # 処理結果を呼び出し元へ返す
    return value


# この工程を担当する関数を定義する
def _nonnegative_int(record: Mapping[str, Any], key: str) -> int:
    # valueへこの工程で使用する値を設定する
    value = _integer(record, key)
    # 条件を満たす場合だけ次の処理を行う
    if value < 0:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は0以上の整数にしてください")
    # 処理結果を呼び出し元へ返す
    return value


# この工程を担当する関数を定義する
def _name_list(record: Mapping[str, Any], key: str) -> list[str]:
    # valueへこの工程で使用する値を設定する
    value = record.get(key)
    # 条件を満たす場合だけ次の処理を行う
    if (
        # 次の値または処理を現在の構造へ組み込む
        not isinstance(value, list)
        # 次の値または処理を現在の構造へ組み込む
        or not value
        # 次の値または処理を現在の構造へ組み込む
        or any(not isinstance(name, str) or not name for name in value)
        # 次の値または処理を現在の構造へ組み込む
        or len(value) != len(set(value))
    # 次の値または処理を現在の構造へ組み込む
    ):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は重複のない文字列リストにしてください")
    # 処理結果を呼び出し元へ返す
    return value


# この工程を担当する関数を定義する
def _require_exact_keys(
    # 次の値または処理を現在の構造へ組み込む
    record: Mapping[str, Any], expected: set[str], label: str
# 次の値または処理を現在の構造へ組み込む
) -> None:
    # 条件を満たす場合だけ次の処理を行う
    if set(record) != expected:
        # missingへこの工程で使用する値を設定する
        missing = sorted(expected - set(record))
        # extraへこの工程で使用する値を設定する
        extra = sorted(set(record) - expected)
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{label}の項目が不正です: 不足={missing}, 余分={extra}")


# この工程を担当する関数を定義する
def main() -> None:
    # argsへこの工程で使用する値を設定する
    args = parse_args()
    # 条件を満たす場合だけ次の処理を行う
    if args.target_verified_per_ast <= 0:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("target-verified-per-astは正の整数にしてください")

    # configへこの工程で使用する値を設定する
    config = GeneratorConfig(
        # element_namesへこの工程で使用する値を設定する
        element_names=_parse_names(args.element_names, "element-names"),
        # result_namesへこの工程で使用する値を設定する
        result_names=_parse_names(args.result_names, "result-names"),
        # max_source_charsへこの工程で使用する値を設定する
        max_source_chars=args.max_source_chars,
    )
    # 条件を満たす場合だけ次の処理を行う
    if args.validate_config:
        # 次の値または処理を現在の構造へ組み込む
        _check_paths(
            # input_pathへこの工程で使用する値を設定する
            input_path=args.input,
            # excluded_pathsへこの工程で使用する値を設定する
            excluded_paths=args.exclude_code_jsonl,
            # output_pathsへこの工程で使用する値を設定する
            output_paths=(args.output, args.rejections, args.stats),
            # overwriteへこの工程で使用する値を設定する
            overwrite=True,
        )
        # 処理結果を利用者へ表示する
        print(f"設定JSONは有効です: {args.config}")
        # 処理結果を呼び出し元へ返す
        return

    # 次の値または処理を現在の構造へ組み込む
    _check_paths(
        # input_pathへこの工程で使用する値を設定する
        input_path=args.input,
        # excluded_pathsへこの工程で使用する値を設定する
        excluded_paths=args.exclude_code_jsonl,
        # output_pathsへこの工程で使用する値を設定する
        output_paths=(args.output, args.rejections, args.stats),
        # overwriteへこの工程で使用する値を設定する
        overwrite=args.overwrite,
    )
    # variant_generatorへこの工程で使用する値を設定する
    variant_generator = StructuralVariantGenerator(config, seed=args.seed)
    # casesへこの工程で使用する値を設定する
    cases = build_verification_cases(args.random_test_seed, args.random_test_count)
    # excluded_codesへこの工程で使用する値を設定する
    excluded_codes = _load_excluded_codes(args.exclude_code_jsonl)

    # countersへこの工程で使用する値を設定する
    counters: Counter[str] = Counter()
    # per_specへこの工程で使用する値を設定する
    per_spec: dict[str, Counter[str]] = {}
    # seen_codesへこの工程で使用する値を設定する
    seen_codes: dict[str, tuple[str, str | None]] = dict(excluded_codes)
    # shortfall_specsへこの工程で使用する値を設定する
    shortfall_specs: list[dict[str, Any]] = []

    # 使用するリソースの開始と終了をこの範囲で管理する
    with (
        # 次の値または処理を現在の構造へ組み込む
        GeneratedCodeVerifierSession(
            # 次の値または処理を現在の構造へ組み込む
            cases,
            # 次の値または処理を現在の構造へ組み込む
            args.timeout_seconds,
            # 次の値または処理を現在の構造へ組み込む
            config.max_source_chars,
        # 次の値または処理を現在の構造へ組み込む
        ) as verifier,
        # 次の値または処理を現在の構造へ組み込む
        _atomic_text_writer(args.output) as output_file,
        # 次の値または処理を現在の構造へ組み込む
        _atomic_text_writer(args.rejections) as rejection_file,
    # 次の値または処理を現在の構造へ組み込む
    ):
        # 対象を一件ずつ取り出して処理する
        for input_record in _read_jsonl(args.input):
            # spec_idへこの工程で使用する値を設定する
            spec_id = _required_string(input_record, "spec_id")
            # semantic_astへこの工程で使用する値を設定する
            semantic_ast = input_record.get("semantic_ast")
            # 条件を満たす場合だけ次の処理を行う
            if not isinstance(semantic_ast, Mapping):
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"{spec_id}: semantic_astがありません")
            # operation_countへこの工程で使用する値を設定する
            operation_count = _operation_count(semantic_ast)
            # 条件を満たす場合だけ次の処理を行う
            if (
                # 次の値または処理を現在の構造へ組み込む
                args.operation_count is not None
                # 次の値または処理を現在の構造へ組み込む
                and operation_count != args.operation_count
            # 次の値または処理を現在の構造へ組み込む
            ):
                # 次の値または処理を現在の構造へ組み込む
                counters["skipped_input_count"] += 1
                # 現在の対象を終えて次の対象へ進む
                continue
            # 条件を満たす場合だけ次の処理を行う
            if args.single_operation_only and operation_count != 1:
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"{spec_id}: 最初の確認では1操作ASTだけを入力してください")

            # spec_countsへこの工程で使用する値を設定する
            spec_counts: Counter[str] = Counter()
            # variantsへこの工程で使用する値を設定する
            variants = variant_generator.enumerate(semantic_ast)
            # 次の値または処理を現在の構造へ組み込む
            spec_counts["available_style_count"] = len(variants)
            # 次の値または処理を現在の構造へ組み込む
            counters["available_style_count"] += len(variants)

            # 対象を一件ずつ取り出して処理する
            for variant in variants:
                # 条件を満たす場合だけ次の処理を行う
                if spec_counts["deduplicated_count"] >= args.target_verified_per_ast:
                    # 条件を満たしたため繰り返しを終了する
                    break
                # 次の値または処理を現在の構造へ組み込む
                spec_counts["candidate_count"] += 1
                # 次の値または処理を現在の構造へ組み込む
                counters["candidate_count"] += 1
                # 失敗する可能性がある処理を開始する
                try:
                    # generatedへこの工程で使用する値を設定する
                    generated = generate_python_code(semantic_ast, variant, config)
                # 発生した例外を受け取り、安全に処理する
                except Exception as error:
                    # 次の値または処理を現在の構造へ組み込む
                    _write_jsonl(
                        # 次の値または処理を現在の構造へ組み込む
                        rejection_file,
                        # 次の値または処理を現在の構造へ組み込む
                        {
                            # 出力レコードの項目と値を設定する
                            "spec_id": spec_id,
                            # 出力レコードの項目と値を設定する
                            "style_spec": variant,
                            # 出力レコードの項目と値を設定する
                            "reason": "generation_or_static_validation_failed",
                            # 出力レコードの項目と値を設定する
                            "error": f"{type(error).__name__}: {error}",
                        },
                    )
                    # 次の値または処理を現在の構造へ組み込む
                    spec_counts["static_rejected_count"] += 1
                    # 次の値または処理を現在の構造へ組み込む
                    counters["static_rejected_count"] += 1
                    # 現在の対象を終えて次の対象へ進む
                    continue

                # verificationへこの工程で使用する値を設定する
                verification = verifier.verify(
                    # 次の値または処理を現在の構造へ組み込む
                    generated.reference_code,
                    # 次の値または処理を現在の構造へ組み込む
                    semantic_ast,
                )
                # 条件を満たす場合だけ次の処理を行う
                if not verification.tests_passed:
                    # 次の値または処理を現在の構造へ組み込む
                    _write_jsonl(
                        # 次の値または処理を現在の構造へ組み込む
                        rejection_file,
                        # 次の値または処理を現在の構造へ組み込む
                        {
                            # 出力レコードの項目と値を設定する
                            "spec_id": spec_id,
                            # 出力レコードの項目と値を設定する
                            "style_id": generated.style_id,
                            # 出力レコードの項目と値を設定する
                            "code_hash": generated.code_hash,
                            # 出力レコードの項目と値を設定する
                            "reason": "execution_verification_failed",
                            # 出力レコードの項目と値を設定する
                            "verification": verification.to_record(),
                        },
                    )
                    # 次の値または処理を現在の構造へ組み込む
                    spec_counts["verification_rejected_count"] += 1
                    # 次の値または処理を現在の構造へ組み込む
                    counters["verification_rejected_count"] += 1
                    # 現在の対象を終えて次の対象へ進む
                    continue

                # 次の値または処理を現在の構造へ組み込む
                spec_counts["verified_count"] += 1
                # 次の値または処理を現在の構造へ組み込む
                counters["verified_count"] += 1
                # candidate_recordへこの工程で使用する値を設定する
                candidate_record = make_code_candidate_record(
                    # 次の値または処理を現在の構造へ組み込む
                    input_record,
                    # 次の値または処理を現在の構造へ組み込む
                    generated,
                    # 次の値または処理を現在の構造へ組み込む
                    args.seed,
                    # 次の値または処理を現在の構造へ組み込む
                    verification.to_record(),
                )
                # matchedへこの工程で使用する値を設定する
                matched = seen_codes.get(generated.code_hash)
                # 条件を満たす場合だけ次の処理を行う
                if matched is not None:
                    # 次の値または処理を現在の構造へ組み込む
                    matched_source, matched_code_id = matched
                    # 条件を満たす場合だけ次の処理を行う
                    if matched_source != generated.reference_code:
                        # 不正な状態を例外として通知して処理を停止する
                        raise RuntimeError(f"SHA-256衝突を検出しました: {generated.code_hash}")
                    # 次の値または処理を現在の構造へ組み込む
                    _write_jsonl(
                        # 次の値または処理を現在の構造へ組み込む
                        rejection_file,
                        # 次の値または処理を現在の構造へ組み込む
                        {
                            # 出力レコードの項目と値を設定する
                            "spec_id": spec_id,
                            # 出力レコードの項目と値を設定する
                            "style_id": generated.style_id,
                            # 出力レコードの項目と値を設定する
                            "code_hash": generated.code_hash,
                            # 出力レコードの項目と値を設定する
                            "matched_code_id": matched_code_id,
                            # 出力レコードの項目と値を設定する
                            "reason": "exact_duplicate_code",
                        },
                    )
                    # 次の値または処理を現在の構造へ組み込む
                    spec_counts["duplicate_count"] += 1
                    # 次の値または処理を現在の構造へ組み込む
                    counters["duplicate_count"] += 1
                    # 現在の対象を終えて次の対象へ進む
                    continue

                # seen_codes[generated.code_hash]へこの工程で使用する値を設定する
                seen_codes[generated.code_hash] = (
                    # 次の値または処理を現在の構造へ組み込む
                    generated.reference_code,
                    # 次の値または処理を現在の構造へ組み込む
                    str(candidate_record["code_id"]),
                )
                # 次の値または処理を現在の構造へ組み込む
                _write_jsonl(output_file, candidate_record)
                # 次の値または処理を現在の構造へ組み込む
                spec_counts["deduplicated_count"] += 1
                # 次の値または処理を現在の構造へ組み込む
                counters["deduplicated_count"] += 1

            # 条件を満たす場合だけ次の処理を行う
            if spec_counts["deduplicated_count"] < args.target_verified_per_ast:
                # shortfallへこの工程で使用する値を設定する
                shortfall = {
                    # 出力レコードの項目と値を設定する
                    "spec_id": spec_id,
                    # 出力レコードの項目と値を設定する
                    "operation_count": operation_count,
                    # 出力レコードの項目と値を設定する
                    "target": args.target_verified_per_ast,
                    # 出力レコードの項目と値を設定する
                    "accepted": spec_counts["deduplicated_count"],
                    # 出力レコードの項目と値を設定する
                    "available_style_count": spec_counts["available_style_count"],
                }
                # 次の値または処理を現在の構造へ組み込む
                shortfall_specs.append(shortfall)
                # 次の値または処理を現在の構造へ組み込む
                _write_jsonl(
                    # 次の値または処理を現在の構造へ組み込む
                    rejection_file,
                    # 次の値または処理を現在の構造へ組み込む
                    {**shortfall, "reason": "verified_code_target_shortfall"},
                )
                # 次の値または処理を現在の構造へ組み込む
                spec_counts["target_shortfall"] = 1
                # 次の値または処理を現在の構造へ組み込む
                counters["target_shortfall"] += 1

            # per_spec[spec_id]へこの工程で使用する値を設定する
            per_spec[spec_id] = spec_counts

    # statsへこの工程で使用する値を設定する
    stats = {
        # 出力レコードの項目と値を設定する
        "input": str(args.input),
        # 出力レコードの項目と値を設定する
        "output": str(args.output),
        # 出力レコードの項目と値を設定する
        "config": str(args.config) if args.config is not None else None,
        # 出力レコードの項目と値を設定する
        "config_hash": args.config_hash,
        # 出力レコードの項目と値を設定する
        "generator_seed": args.seed,
        # 出力レコードの項目と値を設定する
        "target_verified_per_ast": args.target_verified_per_ast,
        # 出力レコードの項目と値を設定する
        "single_operation_only": args.single_operation_only,
        # 出力レコードの項目と値を設定する
        "operation_count_filter": args.operation_count,
        # 出力レコードの項目と値を設定する
        "element_names": list(config.element_names),
        # 出力レコードの項目と値を設定する
        "result_names": list(config.result_names),
        # 出力レコードの項目と値を設定する
        "max_source_chars": config.max_source_chars,
        # 出力レコードの項目と値を設定する
        "boundary_test_count": len(cases) - args.random_test_count,
        # 出力レコードの項目と値を設定する
        "random_test_count": args.random_test_count,
        # 出力レコードの項目と値を設定する
        "random_test_seed": args.random_test_seed,
        # 出力レコードの項目と値を設定する
        "verification_case_count": len(cases),
        # 出力レコードの項目と値を設定する
        "timeout_seconds": args.timeout_seconds,
        # 出力レコードの項目と値を設定する
        "python_version": platform.python_version(),
        # 出力レコードの項目と値を設定する
        "shortfall_specs": shortfall_specs,
        # 出力レコードの項目と値を設定する
        "totals": dict(sorted(counters.items())),
        # 出力レコードの項目と値を設定する
        "per_spec": {
            # 次の値または処理を現在の構造へ組み込む
            spec_id: dict(sorted(counts.items()))
            # 対象を一件ずつ取り出して処理する
            for spec_id, counts in sorted(per_spec.items())
        },
    }
    # 次の値または処理を現在の構造へ組み込む
    _write_json_file_atomic(args.stats, stats)
    # 条件を満たす場合だけ次の処理を行う
    if shortfall_specs:
        # 不正な状態を例外として通知して処理を停止する
        raise RuntimeError(
            # 次の値または処理を現在の構造へ組み込む
            f"検証済み固有コードが目標へ届かない意味ASTが{len(shortfall_specs)}件あります"
        )


# この工程を担当する関数を定義する
def _parse_names(raw: str, option_name: str) -> tuple[str, ...]:
    # namesへこの工程で使用する値を設定する
    names = tuple(item.strip() for item in raw.split(",") if item.strip())
    # 条件を満たす場合だけ次の処理を行う
    if not names:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{option_name}を1つ以上指定してください")
    # 条件を満たす場合だけ次の処理を行う
    if len(names) != len(set(names)):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{option_name}に重複があります")
    # 処理結果を呼び出し元へ返す
    return names


# この工程を担当する関数を定義する
def _required_string(record: Mapping[str, Any], key: str) -> str:
    # valueへこの工程で使用する値を設定する
    value = record.get(key)
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(value, str) or not value:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"空でない{key}が必要です")
    # 処理結果を呼び出し元へ返す
    return value


# この工程を担当する関数を定義する
def _operation_count(semantic_ast: Mapping[str, Any]) -> int:
    # 条件を満たす場合だけ次の処理を行う
    if set(semantic_ast) == {"sequence"}:
        # sequenceへこの工程で使用する値を設定する
        sequence = semantic_ast["sequence"]
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(sequence, list):
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("semantic_ast.sequenceはリストにしてください")
        # 処理結果を呼び出し元へ返す
        return len(sequence)
    # 処理結果を呼び出し元へ返す
    return 1


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
            # 失敗する可能性がある処理を開始する
            try:
                # recordへこの工程で使用する値を設定する
                record = json.loads(line)
            # 発生した例外を受け取り、安全に処理する
            except json.JSONDecodeError as error:
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"{path}:{line_number}: JSONが不正です") from error
            # 条件を満たす場合だけ次の処理を行う
            if not isinstance(record, dict):
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"{path}:{line_number}: レコードは辞書にしてください")
            # 生成した値を呼び出し元へ一件ずつ返す
            yield record


# この工程を担当する関数を定義する
def _load_excluded_codes(paths: Iterable[Path]) -> dict[str, tuple[str, str | None]]:
    # excludedへこの工程で使用する値を設定する
    excluded: dict[str, tuple[str, str | None]] = {}
    # 対象を一件ずつ取り出して処理する
    for path in paths:
        # 対象を一件ずつ取り出して処理する
        for record in _read_jsonl(path):
            # code_hashへこの工程で使用する値を設定する
            code_hash = _required_string(record, "code_hash")
            # sourceへこの工程で使用する値を設定する
            source = _required_string(record, "reference_code")
            # code_id_valueへこの工程で使用する値を設定する
            code_id_value = record.get("code_id")
            # 条件を満たす場合だけ次の処理を行う
            if code_id_value is not None and not isinstance(code_id_value, str):
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"{path}: code_idは文字列またはnullにしてください")
            # previousへこの工程で使用する値を設定する
            previous = excluded.get(code_hash)
            # 条件を満たす場合だけ次の処理を行う
            if previous is not None and previous[0] != source:
                # 不正な状態を例外として通知して処理を停止する
                raise RuntimeError(f"SHA-256衝突を検出しました: {code_hash}")
            # excluded[code_hash]へこの工程で使用する値を設定する
            excluded[code_hash] = (source, code_id_value)
    # 処理結果を呼び出し元へ返す
    return excluded


# この工程を担当する関数を定義する
def _write_jsonl(destination: Any, record: Mapping[str, Any]) -> None:
    # 次の値または処理を現在の構造へ組み込む
    destination.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


# 関連する状態と処理をまとめるクラスを定義する
class _atomic_text_writer:
    # この工程を担当する関数を定義する
    def __init__(self, destination: Path) -> None:
        # self.destinationへこの工程で使用する値を設定する
        self.destination = destination
        # self.temporary_pathへこの工程で使用する値を設定する
        self.temporary_path: Path | None = None
        # self.handleへこの工程で使用する値を設定する
        self.handle: Any = None

    # この工程を担当する関数を定義する
    def __enter__(self) -> Any:
        # 次の値または処理を現在の構造へ組み込む
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        # temporaryへこの工程で使用する値を設定する
        temporary = tempfile.NamedTemporaryFile(
            # modeへこの工程で使用する値を設定する
            mode="w",
            # encodingへこの工程で使用する値を設定する
            encoding="utf-8",
            # newlineへこの工程で使用する値を設定する
            newline="\n",
            # dirへこの工程で使用する値を設定する
            dir=self.destination.parent,
            # prefixへこの工程で使用する値を設定する
            prefix=f".{self.destination.name}.",
            # suffixへこの工程で使用する値を設定する
            suffix=".tmp",
            # deleteへこの工程で使用する値を設定する
            delete=False,
        )
        # self.temporary_pathへこの工程で使用する値を設定する
        self.temporary_path = Path(temporary.name)
        # self.handleへこの工程で使用する値を設定する
        self.handle = temporary
        # 処理結果を呼び出し元へ返す
        return temporary

    # この工程を担当する関数を定義する
    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        # 条件を満たす場合だけ次の処理を行う
        if self.handle is not None:
            # 次の値または処理を現在の構造へ組み込む
            self.handle.close()
        # 条件を満たす場合だけ次の処理を行う
        if self.temporary_path is None:
            # 処理結果を呼び出し元へ返す
            return
        # 条件を満たす場合だけ次の処理を行う
        if exc_type is None:
            # 次の値または処理を現在の構造へ組み込む
            self.temporary_path.replace(self.destination)
        # 前の条件に該当せず、この条件を満たす場合を処理する
        elif self.temporary_path.exists():
            # 次の値または処理を現在の構造へ組み込む
            self.temporary_path.unlink()


# この工程を担当する関数を定義する
def _write_json_file_atomic(path: Path, value: Mapping[str, Any]) -> None:
    # 使用するリソースの開始と終了をこの範囲で管理する
    with _atomic_text_writer(path) as destination:
        # 次の値または処理を現在の構造へ組み込む
        json.dump(value, destination, ensure_ascii=False, indent=2, sort_keys=True)
        # 次の値または処理を現在の構造へ組み込む
        destination.write("\n")


# この工程を担当する関数を定義する
def _check_paths(
    # 次の値または処理を現在の構造へ組み込む
    input_path: Path,
    # 次の値または処理を現在の構造へ組み込む
    excluded_paths: Iterable[Path],
    # 次の値または処理を現在の構造へ組み込む
    output_paths: Iterable[Path],
    # 次の値または処理を現在の構造へ組み込む
    overwrite: bool,
# 次の値または処理を現在の構造へ組み込む
) -> None:
    # outputsへこの工程で使用する値を設定する
    outputs = tuple(output_paths)
    # duplicatesへこの工程で使用する値を設定する
    duplicates = [str(path.resolve()) for path in outputs]
    # 条件を満たす場合だけ次の処理を行う
    if len(duplicates) != len(set(duplicates)):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("output、rejections、statsには別々のパスを指定してください")
    # protectedへこの工程で使用する値を設定する
    protected = {input_path.resolve(), *(path.resolve() for path in excluded_paths)}
    # overlappingへこの工程で使用する値を設定する
    overlapping = [str(path) for path in outputs if path.resolve() in protected]
    # 条件を満たす場合だけ次の処理を行う
    if overlapping:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("入力ファイルを出力先に指定できません: " + ", ".join(overlapping))
    # existingへこの工程で使用する値を設定する
    existing = [str(path) for path in outputs if path.exists()]
    # 条件を満たす場合だけ次の処理を行う
    if existing and not overwrite:
        # 不正な状態を例外として通知して処理を停止する
        raise FileExistsError(
            "既存ファイルがあります。置換する場合だけ--overwriteを指定してください: "
            # 次の値または処理を現在の構造へ組み込む
            + ", ".join(existing)
        )


# 条件を満たす場合だけ次の処理を行う
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    main()
