"""Qwen3で24操作の日本語表現候補を生成する。"""

from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse
# 人間確認用CSVを書き出すために使う
import csv
# 生成日時をUTCで記録するために使う
from datetime import datetime, timezone
# 設定と生成結果をJSONで読み書きするために使う
import json
# 入出力ファイルのパスを扱うために使う
from pathlib import Path
# 外国語の英字混入を検出するために使う
import re
# プロジェクトルートをimport検索パスへ追加するために使う
import sys
# 設定辞書とレコードの型注釈に使う
from typing import Any, Mapping


# このファイルから二階層上をプロジェクトルートとして取得する
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 直接実行時にプロジェクト内モジュールを読み込めるか確認する
if str(PROJECT_ROOT) not in sys.path:
    # プロジェクトルートをimport検索パスの先頭へ追加する
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.instruction_generation.qwen_teacher import (  # noqa: E402
    QwenTeacher,
    canonical_json,
    parse_json_string_object_list,
    prompt_hash,
    render_prompt,
    sha256_text,
    validate_model_config,
    validate_sampling_config,
)


# 出力へ記録する表現生成器のバージョンを定義する
GENERATOR_VERSION = "8"
# 7と8はCLI機能の追加なので、従来の6・7設定も互換入力として扱う
SUPPORTED_GENERATOR_VERSIONS = {"6", "7", GENERATOR_VERSION}

# 変数名k以外の英字は外国語混入として拒否する
NON_K_ASCII_LETTER_PATTERN = re.compile(r"[a-jl-zA-JL-Z]")
# 日本語の動詞基本形が取り得る末尾の仮名を定義する
DICTIONARY_FORM_VERB_ENDINGS = frozenset("うくぐすつぬぶむる")
# 後続操作へ自然につなげる接続形として認める語尾を定義する
CONNECTIVE_VERB_ENDINGS = (
    "して",
    "いて",
    "いで",
    "って",
    "んで",
    "し",
    "き",
    "ぎ",
    "ち",
    "び",
    "み",
    "り",
    "て",
    "で",
    "い",
    "え",
    "け",
    "げ",
    "せ",
    "べ",
)


def parse_args() -> argparse.Namespace:
    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        description="Qwen3で単純操作ごとの日本語表現候補を生成します。"
    )
    # 正式な生成条件を持つ設定JSONを必須引数として受け取る
    parser.add_argument("--config", required=True, type=Path)
    # clone先でローカルモデルの配置場所だけを差し替えられるようにする
    parser.add_argument(
        "--model-path",
        type=Path,
        help=(
            "設定JSONのmodel.model_pathを今回の実行だけ上書きする"
            "ローカルQwenモデルのディレクトリです。"
        ),
    )
    # モデルを読み込まず設定だけを検査するオプションを追加する
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="設定と入力だけを検査し、モデルを読み込まず終了します。",
    )
    # 既存出力を明示的に置き換えるオプションを追加する
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="既存の出力ファイルを置き換えます。",
    )
    # 未達操作だけを既存候補へ追加生成するオプションを追加する
    parser.add_argument(
        "--resume",
        action="store_true",
        help="既存候補を保持し、目標未達の操作だけを追加生成します。",
    )
    # 特定の操作だけを独立した出力先へ生成できるよう操作IDを複数回受け取る
    parser.add_argument(
        "--operation-id",
        action="append",
        dest="operation_ids",
        help=(
            "指定した操作IDだけを生成します（例: atomic-000024）。"
            "複数操作を指定する場合はこのoptionを繰り返します。"
        ),
    )
    # 設定JSONの最大試行回数を今回の実行だけ上書きできるようにする
    parser.add_argument(
        "--max-attempts-per-operation",
        type=int,
        help=(
            "操作ごとの最大生成試行回数を今回の実行だけ上書きします。"
            "1以上を指定してください。"
        ),
    )
    # 既存の確認CSVにある表現を再生成しないため任意の除外元として受け取る
    parser.add_argument(
        "--existing-review-csv",
        type=Path,
        help=(
            "既存表現としてプロンプトと重複判定へ加える確認CSVです。"
            "既存表現は新規候補の目標件数には含めません。"
        ),
    )
    # 既存表現を機械的な重複判定には使いつつpromptへ見せない指定を追加する
    parser.add_argument(
        "--omit-existing-expressions-from-prompt",
        action="store_true",
        help=(
            "既存確認CSVの表現を重複判定だけに使い、promptには載せません。"
            "今回の実行で採用した候補は再試行時のpromptへ載せます。"
        ),
    )
    # 別操作の承認例を表現構造の参考として対象操作へ渡せるよう対応表を受け取る
    parser.add_argument(
        "--reference-operation",
        action="append",
        default=[],
        dest="reference_operations",
        metavar="TARGET=SOURCE",
        help=(
            "SOURCE操作の既存表現をTARGET操作の参考例へ加えます。"
            "複数の対応はこのoptionを繰り返します。"
        ),
    )
    # 一つの参照元操作からプロンプトへ載せる承認例数を受け取る
    parser.add_argument(
        "--reference-examples-per-operation",
        type=int,
        default=3,
        help="一つの参照元操作から使う例数です。1〜20を指定してください。",
    )
    # 承認済み表現を終止形で一件ずつ指定し、意図した参考例だけを渡せるようにする
    parser.add_argument(
        "--reference-expression",
        action="append",
        default=[],
        dest="reference_expressions",
        metavar="TARGET=SOURCE=EXPRESSION",
        help=(
            "SOURCE操作の承認済み終止形EXPRESSIONをTARGET操作の参考例へ加えます。"
            "複数指定する場合はこのoptionを繰り返します。"
        ),
    )
    # コマンドラインを解析して返す
    return parser.parse_args()


def main() -> None:
    # コマンドライン引数を取得する
    args = parse_args()
    # 設定JSONを辞書と元文字列の両方で読み込む
    config, config_text = _load_json_object(args.config)
    # clone先固有のモデル配置場所が指定された場合だけ設定値を差し替える
    config = _override_model_path(config, args.model_path)
    # 設定値を検査し、パスを絶対パスへ変換する
    settings = _validate_and_resolve_config(config)
    # CLI指定があれば設定JSONより優先して今回の最大試行回数へ反映する
    settings["max_attempts_per_operation"] = _resolve_max_attempts(
        settings["max_attempts_per_operation"],
        args.max_attempts_per_operation,
    )
    # 24操作の意味定義と入力ASTが一致することを確認する
    all_operations = _load_and_validate_operations(settings)
    # 操作別seedを従来と同じ定義順で計算するため元の位置を保持する
    operation_indexes = {
        operation["operation_id"]: index
        for index, operation in enumerate(all_operations)
    }
    # 操作IDが指定された場合は、その操作群だけを生成対象に絞る
    if args.operation_ids is None:
        operations = all_operations
    else:
        # 同じIDの重複指定は一度だけ扱う
        requested_operation_ids = set(args.operation_ids)
        # 未知のIDをモデル読込前に検出する
        unknown_operation_ids = sorted(
            requested_operation_ids - set(operation_indexes)
        )
        if unknown_operation_ids:
            raise ValueError(
                "未知のoperation_idです: " + ", ".join(unknown_operation_ids)
            )
        # 正式な24操作の定義順を保ったまま指定操作だけを選ぶ
        operations = [
            operation
            for operation in all_operations
            if operation["operation_id"] in requested_operation_ids
        ]

    # 参照元と対象操作の対応を検査し、CLI記載順を保った辞書へ変換する
    reference_sources_by_target = _parse_reference_operations(
        args.reference_operations,
        valid_operation_ids=set(operation_indexes),
        selected_operation_ids={
            operation["operation_id"] for operation in operations
        },
    )
    # 一つの参照元操作からプロンプトへ載せる最大例数を検査する
    reference_examples_per_operation = (
        _resolve_reference_examples_per_operation(
            args.reference_examples_per_operation
        )
    )
    # 参考例を終止形で明示した指定を検査し、対象操作別に整理する
    selected_references_by_target = _parse_reference_expressions(
        args.reference_expressions,
        valid_operation_ids=set(operation_indexes),
        selected_operation_ids={
            operation["operation_id"] for operation in operations
        },
    )
    # 操作単位の自動選択と表現単位の明示選択を混ぜる曖昧な指定は拒否する
    if reference_sources_by_target and selected_references_by_target:
        raise ValueError(
            "--reference-operationと--reference-expressionは同時に指定できません"
        )

    # 任意指定された既存確認CSVを操作ID別の表現一覧として読み込む
    existing_review_csv = (
        args.existing_review_csv.resolve()
        if args.existing_review_csv is not None
        else None
    )
    existing_by_operation = (
        _read_existing_review_csv(existing_review_csv)
        if existing_review_csv is not None
        else {}
    )
    # 参照操作を指定した場合は承認済み例の入力CSVを必須にする
    if (
        reference_sources_by_target or selected_references_by_target
    ) and existing_review_csv is None:
        raise ValueError(
            "参考例指定には--existing-review-csvが必要です"
        )
    # 長時間の生成中に元CSVが変わっても実行後の内容を誤記録しないよう先に固定する
    existing_review_csv_hash = (
        sha256_text(existing_review_csv.read_text(encoding="utf-8-sig"))
        if existing_review_csv is not None
        else None
    )
    # CSV内の操作IDが正式な24操作以外を指していれば入力ミスとして停止する
    unknown_existing_ids = sorted(
        set(existing_by_operation) - set(operation_indexes)
    )
    if unknown_existing_ids:
        raise ValueError(
            "既存確認CSVに未知のoperation_idがあります: "
            + ", ".join(unknown_existing_ids)
        )
    # 今回の生成対象に対応する既存表現数を再現可能な集計として保持する
    existing_counts = {
        operation["operation_id"]: len(
            existing_by_operation.get(operation["operation_id"], [])
        )
        for operation in operations
    }
    # 対象操作ごとにプロンプトへ載せる別操作の参考例を構築する
    if selected_references_by_target:
        reference_groups_by_target = _build_selected_reference_groups(
            selected_references_by_target=selected_references_by_target,
            existing_by_operation=existing_by_operation,
            all_operations=all_operations,
        )
    else:
        reference_groups_by_target = _build_reference_groups(
            reference_sources_by_target=reference_sources_by_target,
            existing_by_operation=existing_by_operation,
            all_operations=all_operations,
            examples_per_operation=reference_examples_per_operation,
        )
    # statsには明示選択の場合も参照元操作を入力順に残す
    effective_reference_sources_by_target = (
        {
            target: list(dict.fromkeys(source for source, _ in selections))
            for target, selections in selected_references_by_target.items()
        }
        if selected_references_by_target
        else reference_sources_by_target
    )
    # 集計へ残すため対象操作ごとの参考例総数を数える
    reference_counts = {
        operation["operation_id"]: sum(
            len(group["expressions"])
            for group in reference_groups_by_target.get(
                operation["operation_id"], []
            )
        )
        for operation in operations
    }

    # 設定検査だけを指定された場合はモデルを読み込まない
    if args.validate_config:
        # 確認した操作数と操作ごとの目標件数を表示する
        print(
            f"設定は有効です: operations={len(operations)}, "
            f"target={settings['target_candidates_per_operation']}, "
            f"existing_examples={sum(existing_counts.values())}, "
            f"reference_examples={sum(reference_counts.values())}"
        )
        # 生成処理へ進まず終了する
        return

    # この実行で作成する4つの出力パスをまとめる
    output_paths = [
        settings["output"],
        settings["raw_responses"],
        settings["review_csv"],
        settings["stats"],
    ]
    # 上書きと再開を同時指定する曖昧な実行を拒否する
    if args.overwrite and args.resume:
        raise ValueError("--overwriteと--resumeは同時に指定できません")
    # すでに存在する出力だけを抽出する
    existing = [str(path) for path in output_paths if path.exists()]
    # 再開時は前回の4出力がすべて存在することを必須にする
    if args.resume and len(existing) != len(output_paths):
        raise ValueError("--resumeには前回の4出力がすべて必要です")
    # 上書き・再開指定なしで既存出力がある場合は誤消去を防ぐため停止する
    if existing and not args.overwrite and not args.resume:
        raise ValueError(
            "既存出力があります。置き換える場合は--overwriteを指定してください: "
            + ", ".join(existing)
        )

    # 単純操作表現生成用のsystem promptを読み込む
    system_prompt = settings["system_prompt"].read_text(encoding="utf-8").strip()
    # Qwen3モデルとtokenizerを一度だけ読み込む
    teacher = QwenTeacher(settings["model"])
    # 各操作から確保する固有候補数を取得する
    target = settings["target_candidates_per_operation"]
    # 目標未達時に再生成できる最大回数を取得する
    max_attempts = settings["max_attempts_per_operation"]
    # 操作別seedの基準値を取得する
    base_seed = settings["generator_seed"]

    # 再開時は前回候補を保持し、それ以外は空の候補一覧から始める
    candidate_records = (
        _read_jsonl(settings["output"]) if args.resume else []
    )
    # 再開時は前回生出力も保持し、それ以外は空の一覧から始める
    raw_records = (
        _read_jsonl(settings["raw_responses"]) if args.resume else []
    )
    # 目標件数へ届かなかった操作を格納する配列を作る
    failures: list[dict[str, Any]] = []

    # 24操作を定義順に処理する
    for operation in operations:
        # 単独生成でも24操作を一括生成した場合と同じseed系列を使う
        operation_index = operation_indexes[operation["operation_id"]]
        # 再開時は現在操作の採用済み候補だけを取り出す
        operation_records = [
            record
            for record in candidate_records
            if record.get("operation_id") == operation["operation_id"]
        ]
        # 現在の操作で採用した終止形・接続形の組を格納する
        expression_pairs = [
            {
                "expression_ja": _required_string(record, "expression_ja"),
                "connective_expression_ja": _required_string(
                    record,
                    "connective_expression_ja",
                ),
            }
            for record in operation_records
        ]
        # 確認CSVの既存例と今回候補を重複判定用の一覧へまとめる
        dedup_expression_pairs = _unique_expression_pairs(
            existing_by_operation.get(operation["operation_id"], [])
            + expression_pairs
        )
        # 指定時は従来表現をpromptから外し、今回候補だけを再試行へ示す
        prompt_expression_pairs = _unique_expression_pairs(
            expression_pairs
            if args.omit_existing_expressions_from_prompt
            else dedup_expression_pairs
        )
        # 目標を超える既存候補は設定不整合として停止する
        if len(expression_pairs) > target:
            raise ValueError(
                f"既存候補が目標件数を超えています: {operation['operation_id']}"
            )
        # 同じ操作内の組と終止形の重複を高速に判定する集合を作る
        seen_pairs: set[tuple[str, str]] = set()
        seen_final_expressions: set[str] = set()
        # promptへ見せない場合も既存例は生成後の重複確認集合へ登録する
        for expression_pair in dedup_expression_pairs:
            seen_pairs.add(
                (
                    expression_pair["expression_ja"],
                    expression_pair["connective_expression_ja"],
                )
            )
            seen_final_expressions.add(expression_pair["expression_ja"])
        # 再開時に同じseedを使わないよう現在操作の試行済み回数を取得する
        previous_attempts = max(
            (
                int(record.get("attempt", 0))
                for record in raw_records
                if record.get("operation_id") == operation["operation_id"]
            ),
            default=0,
        )
        # 目標件数に達するまで設定回数内でQwen生成を試す
        for attempt_offset in range(max_attempts):
            # すでに目標件数へ到達していれば再生成を打ち切る
            if len(expression_pairs) >= target:
                break
            # 再試行でも十分な候補数を要求し、既存候補との重複を避けやすくする
            count = target
            # 操作と試行ごとに衝突しない決定的seedを計算する
            attempt = previous_attempts + attempt_offset + 1
            seed = base_seed + operation_index * 1_000 + attempt - 1
            # 再生成時に同じ候補を避けさせるため既存表現をJSON化する
            existing_expressions = (
                canonical_json(prompt_expression_pairs)
                if prompt_expression_pairs
                else "（なし）"
            )
            # 別操作の承認例は意味ではなく語彙・構文の参考としてJSON化する
            reference_groups = reference_groups_by_target.get(
                operation["operation_id"], []
            )
            reference_expressions = (
                canonical_json(reference_groups)
                if reference_groups
                else "（なし）"
            )
            # 操作固有の意味、注意事項、件数をuser promptへ埋め込む
            user_prompt = render_prompt(
                settings["user_prompt"],
                {
                    "count": count,
                    "operation_id": operation["operation_id"],
                    "semantic_ast": canonical_json(operation["semantic_ast"]),
                    "canonical_meaning_ja": operation["canonical_meaning_ja"],
                    "must_preserve_ja": operation["must_preserve_ja"],
                    "existing_expressions": existing_expressions,
                    "reference_expressions": reference_expressions,
                },
            ).strip()
            # 実際にQwenへ渡す二つのプロンプトからハッシュを計算する
            current_prompt_hash = prompt_hash(system_prompt, user_prompt)
            # この生成呼び出しのUTC日時を記録する
            generated_at = datetime.now(timezone.utc).isoformat()
            # 非thinkingモードのQwen3で候補JSONを生成する
            result = teacher.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                sampling=settings["sampling"],
                seed=seed,
            )
            # 解析の成否にかかわらず保存する生出力レコードを作る
            raw_record: dict[str, Any] = {
                "operation_id": operation["operation_id"],
                "attempt": attempt,
                "seed": seed,
                "prompt_hash": current_prompt_hash,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "raw_response": result.text,
                "generated_at": generated_at,
                "parsed_ok": False,
                "parse_error": None,
            }
            # Qwen出力を終止形・接続形を持つexpressions配列として解析する
            try:
                generated_expressions = parse_json_string_object_list(
                    result.text,
                    "expressions",
                    {"expression_ja", "connective_expression_ja"},
                )
            # JSON形式が不正な場合も原因と生出力を残して次の試行へ進む
            except ValueError as error:
                # 解析エラーの内容を生出力レコードへ記録する
                raw_record["parse_error"] = str(error)
                # 失敗した応答も監査できるよう保存対象へ追加する
                raw_records.append(raw_record)
                # 同じ操作の次の試行へ進む
                continue

            # JSON解析に成功したことを記録する
            raw_record["parsed_ok"] = True
            # 成功した生出力も保存対象へ追加する
            raw_records.append(raw_record)
            # Qwenが返した終止形・接続形の組を順番に確認する
            for generated_expression in generated_expressions:
                # 終止形と接続形をそれぞれ取得する
                expression = generated_expression["expression_ja"]
                connective_expression = generated_expression[
                    "connective_expression_ja"
                ]
                # 改行、長さ、禁止文字列、終止形語尾の検査に落ちた組は使わない
                if not _valid_expression(
                    expression,
                    max_chars=settings["max_expression_chars"],
                ):
                    continue
                # 接続形として不自然な語尾や禁止文字を含む組は使わない
                if not _valid_connective_expression(
                    connective_expression,
                    max_chars=settings["max_expression_chars"],
                ):
                    continue
                # 二つの形が同一なら接続形を作れていないため採用しない
                if expression == connective_expression:
                    continue
                # 同じ終止形または同じ組を重複採用しない
                pair = (expression, connective_expression)
                if pair in seen_pairs or expression in seen_final_expressions:
                    continue
                # 新しい表現の組を重複確認集合へ登録する
                seen_pairs.add(pair)
                seen_final_expressions.add(expression)
                # 現在操作の採用済み表現一覧へ追加する
                expression_pairs.append(generated_expression)
                # 次の試行でQwenへ示す既存表現一覧にも同じ組を追加する
                prompt_expression_pairs.append(generated_expression)
                # 人間確認用の候補レコードを作って全体一覧へ追加する
                candidate_records.append(
                    _make_candidate_record(
                        operation=operation,
                        expression=expression,
                        connective_expression=connective_expression,
                        attempt=attempt,
                        seed=seed,
                        prompt_hash_value=current_prompt_hash,
                        generated_at=generated_at,
                        result=result,
                        model_id=teacher.model_id,
                        sampling=settings["sampling"],
                    )
                )
                # 目標件数に達したら今回の出力の残りは採用しない
                if len(expression_pairs) >= target:
                    break

        # 最大試行後も目標件数へ届かなかったかを確認する
        if len(expression_pairs) < target:
            # 操作ID、実件数、目標件数を失敗一覧へ記録する
            failures.append(
                {
                    "operation_id": operation["operation_id"],
                    "generated": len(expression_pairs),
                    "target": target,
                }
            )

    # 実行に使用した設定JSON全文のハッシュを計算する
    config_hash = sha256_text(config_text)
    # 再開で追加した候補も操作順と試行順にまとまるよう出力順を整える
    candidate_records.sort(
        key=lambda record: (
            record["operation_id"],
            int(record.get("generation_attempt", 0)),
            int(record.get("teacher_seed", 0)),
            record["expression_id"],
        )
    )
    # 生応答も操作順と試行順へ整列して監査しやすくする
    raw_records.sort(
        key=lambda record: (
            record["operation_id"],
            int(record.get("attempt", 0)),
        )
    )
    # 人間確認前の候補をJSONLへ保存する
    _write_jsonl(settings["output"], candidate_records)
    # プロンプトとQwen生出力をJSONLへ保存する
    _write_jsonl(settings["raw_responses"], raw_records)
    # 作成者本人が確認しやすいCSVを保存する
    _write_review_csv(settings["review_csv"], candidate_records)
    # 実行条件と生成件数をまとめた集計レコードを作る
    stats = {
        "phase": "atomic_expression_candidates",
        "complete": not failures,
        "operation_count": len(operations),
        "selected_operation_id": (
            args.operation_ids[0]
            if args.operation_ids is not None and len(args.operation_ids) == 1
            else None
        ),
        "selected_operation_ids": (
            [operation["operation_id"] for operation in operations]
            if args.operation_ids is not None
            else None
        ),
        "existing_review_csv": (
            str(existing_review_csv) if existing_review_csv is not None else None
        ),
        "existing_review_csv_hash": existing_review_csv_hash,
        "existing_expression_counts_by_operation": existing_counts,
        "existing_expression_count": sum(existing_counts.values()),
        "existing_expressions_in_prompt": (
            not args.omit_existing_expressions_from_prompt
        ),
        "reference_operation_ids_by_target": (
            effective_reference_sources_by_target
        ),
        "selected_reference_expressions_by_target": {
            target: [
                {"operation_id": source, "expression_ja": expression}
                for source, expression in selections
            ]
            for target, selections in selected_references_by_target.items()
        },
        "reference_examples_per_operation": reference_examples_per_operation,
        "reference_expression_counts_by_target": reference_counts,
        "reference_expression_count": sum(reference_counts.values()),
        "target_candidates_per_operation": target,
        "max_attempts_per_operation": max_attempts,
        "candidate_count": len(candidate_records),
        "raw_response_count": len(raw_records),
        "failures": failures,
        "model_id": settings["model"]["model_id"],
        "model_path": teacher.model_path,
        "requested_revision": settings["model"]["revision"],
        "resolved_revision": teacher.resolved_revision,
        "enable_thinking": False,
        "sampling": settings["sampling"],
        "generator_version": GENERATOR_VERSION,
        "generator_seed": base_seed,
        "config_hash": config_hash,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    # 集計レコードを整形JSONとして保存する
    _write_json(settings["stats"], stats)

    # 生成した候補数、操作数、未達操作数を標準出力へ表示する
    print(
        f"生成完了: candidates={len(candidate_records)}, "
        f"operations={len(operations)}, failures={len(failures)}"
    )
    # 人間が次に開く確認用CSVの場所を表示する
    print(f"確認用CSV: {settings['review_csv']}")
    # 1操作でも目標未達があれば終了コードを成功にしない
    if failures:
        raise RuntimeError(
            "目標件数に届かなかった操作があります。raw responseとstatsを確認してください。"
        )


def _load_json_object(path: Path) -> tuple[dict[str, Any], str]:
    # 相対パスを現在位置に依存しない絶対パスへ変換する
    resolved = path.resolve()
    # JSONファイルを文字列として読み、辞書へ解析する
    try:
        # ハッシュ記録用に元の文字列を保持する
        text = resolved.read_text(encoding="utf-8")
        # JSON文字列をPython値へ変換する
        value = json.loads(text)
    # ファイルが存在しない場合は対象パスを含む設定エラーへ変換する
    except FileNotFoundError as error:
        raise ValueError(f"JSONファイルが見つかりません: {resolved}") from error
    # JSON構文が不正な場合は対象パスを含む設定エラーへ変換する
    except json.JSONDecodeError as error:
        raise ValueError(f"JSONファイルが不正です: {resolved}") from error
    # 設定や操作定義のルートがJSONオブジェクトであることを確認する
    if not isinstance(value, dict):
        raise ValueError(f"JSONのルートはオブジェクトにしてください: {resolved}")
    # 解析済み辞書とハッシュ用の元文字列を返す
    return value, text


def _override_model_path(
    config: dict[str, Any], model_path: Path | None
) -> dict[str, Any]:
    """CLI指定がある場合だけローカルモデルの配置場所を上書きする。"""

    if model_path is None:
        return config
    model = config.get("model")
    if not isinstance(model, dict):
        raise ValueError("設定のmodelはobjectにしてください")
    overridden = dict(config)
    overridden["model"] = dict(model)
    overridden["model"]["model_path"] = str(model_path.resolve())
    return overridden


def _validate_and_resolve_config(config: Mapping[str, Any]) -> dict[str, Any]:
    # 設定JSONに必要なキーを厳密に列挙する
    required_keys = {
        "config_version",
        "phase",
        "input",
        "operation_definitions",
        "output",
        "raw_responses",
        "review_csv",
        "stats",
        "prompts",
        "target_candidates_per_operation",
        "max_attempts_per_operation",
        "generator_version",
        "generator_seed",
        "max_expression_chars",
        "model",
        "sampling",
    }
    # 設定キーの不足や余分なキーがある場合は停止する
    if set(config) != required_keys:
        # 不足しているキーを並べる
        missing = sorted(required_keys - set(config))
        # 余分に指定されたキーを並べる
        extra = sorted(set(config) - required_keys)
        raise ValueError(f"設定項目が不正です: 不足={missing}, 余分={extra}")
    # 対応している設定形式のバージョンを確認する
    if config["config_version"] != 1:
        raise ValueError("config_versionは1にしてください")
    # このスクリプト用の処理段階名であることを確認する
    if config["phase"] != "atomic_expression_candidates":
        raise ValueError("phaseはatomic_expression_candidatesにしてください")
    # 参考例機能を使わない従来設定も同じ生成ロジックで再実行できるようにする
    if config["generator_version"] not in SUPPORTED_GENERATOR_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_GENERATOR_VERSIONS))
        raise ValueError(
            f"generator_versionは対応版を指定してください: {supported}"
        )

    # promptファイル設定を辞書として取得する
    prompts = _required_mapping(config, "prompts")
    # systemとuser以外のpromptキーを許可しない
    if set(prompts) != {"system", "user"}:
        raise ValueError("promptsにはsystemとuserだけを指定してください")
    # モデル設定をモデル読込前に検査する
    model = validate_model_config(_required_mapping(config, "model"))
    # sampling設定をモデル読込前に検査する
    sampling = validate_sampling_config(_required_mapping(config, "sampling"))

    # 元の設定を壊さないよう解決済み設定用のコピーを作る
    settings = dict(config)
    # 入出力に使う各パス設定を順番に絶対パスへ変換する
    for key in (
        "input",
        "operation_definitions",
        "output",
        "raw_responses",
        "review_csv",
        "stats",
    ):
        # 設定値を文字列として検査してプロジェクト基準のパスへ変換する
        settings[key] = _project_path(_required_string(config, key))
    # system promptのパスをプロジェクト基準へ変換する
    settings["system_prompt"] = _project_path(_required_string(prompts, "system"))
    # user promptのパスをプロジェクト基準へ変換する
    settings["user_prompt"] = _project_path(_required_string(prompts, "user"))
    # 検査済みモデル設定を解決済み設定へ格納する
    settings["model"] = model
    # 検査済みsampling設定を解決済み設定へ格納する
    settings["sampling"] = sampling

    # 生成開始前から存在すべき入力ファイルを順番に確認する
    for key in ("input", "operation_definitions", "system_prompt", "user_prompt"):
        # 入力ファイルがなければモデルを読み込む前に停止する
        if not settings[key].is_file():
            raise ValueError(f"入力ファイルが見つかりません: {settings[key]}")
    # 操作ごとの候補目標数を正の整数として取得する
    target = _required_int(config, "target_candidates_per_operation")
    # 標準生成30件に加え、特定操作の追加候補生成では最大100件まで許可する
    if not 10 <= target <= 100:
        raise ValueError("target_candidates_per_operationは10〜100にしてください")
    # 最大再試行回数が正の整数であることを確認する
    _required_int(config, "max_attempts_per_operation")
    # seedが0以上の整数であることを確認する
    _required_int(config, "generator_seed", allow_zero=True)
    # 表現の最大文字数が正の整数であることを確認する
    _required_int(config, "max_expression_chars")
    # 検査とパス解決が終わった設定を返す
    return settings


def _resolve_max_attempts(configured: int, override: int | None) -> int:
    """CLI指定を優先して操作ごとの最大試行回数を確定する。"""

    # CLI指定がなければ検査済みの設定値をそのまま使う
    if override is None:
        return configured
    # ゼロ以下では一度も生成せず終了するため入力ミスとして拒否する
    if override < 1:
        raise ValueError("--max-attempts-per-operationは1以上にしてください")
    # 正のCLI指定を今回の実効値として返す
    return override


def _parse_reference_operations(
    values: list[str],
    *,
    valid_operation_ids: set[str],
    selected_operation_ids: set[str],
) -> dict[str, list[str]]:
    """TARGET=SOURCE形式の参考操作指定を対象操作別に整理する。"""

    references: dict[str, list[str]] = {}
    for value in values:
        if value.count("=") != 1:
            raise ValueError(
                "--reference-operationはTARGET=SOURCE形式にしてください: "
                f"{value!r}"
            )
        target, source = (part.strip() for part in value.split("=", 1))
        if target not in valid_operation_ids or source not in valid_operation_ids:
            raise ValueError(f"参考操作指定に未知のoperation_idがあります: {value}")
        if target not in selected_operation_ids:
            raise ValueError(f"参考例の対象操作が生成対象外です: {target}")
        if target == source:
            raise ValueError(f"対象操作自身は参考操作へ指定できません: {target}")
        target_sources = references.setdefault(target, [])
        if source in target_sources:
            raise ValueError(f"参考操作指定が重複しています: {value}")
        target_sources.append(source)
    return references


def _resolve_reference_examples_per_operation(value: int) -> int:
    """一つの参照元操作から使う例数を検査する。"""

    if not 1 <= value <= 20:
        raise ValueError(
            "--reference-examples-per-operationは1〜20にしてください"
        )
    return value


def _parse_reference_expressions(
    values: list[str],
    *,
    valid_operation_ids: set[str],
    selected_operation_ids: set[str],
) -> dict[str, list[tuple[str, str]]]:
    """TARGET=SOURCE=EXPRESSION形式の参考表現指定を整理する。"""

    references: dict[str, list[tuple[str, str]]] = {}
    for value in values:
        if value.count("=") != 2:
            raise ValueError(
                "--reference-expressionはTARGET=SOURCE=EXPRESSION形式に"
                f"してください: {value!r}"
            )
        target, source, expression = (
            part.strip() for part in value.split("=", 2)
        )
        if target not in valid_operation_ids or source not in valid_operation_ids:
            raise ValueError(f"参考表現指定に未知のoperation_idがあります: {value}")
        if target not in selected_operation_ids:
            raise ValueError(f"参考表現の対象操作が生成対象外です: {target}")
        if target == source:
            raise ValueError(f"対象操作自身の表現は参考例へ指定できません: {target}")
        if not expression:
            raise ValueError(f"参考表現の終止形が空です: {value}")
        selection = (source, expression)
        target_references = references.setdefault(target, [])
        if selection in target_references:
            raise ValueError(f"参考表現指定が重複しています: {value}")
        target_references.append(selection)
    return references


def _build_reference_groups(
    *,
    reference_sources_by_target: Mapping[str, list[str]],
    existing_by_operation: Mapping[str, list[dict[str, str]]],
    all_operations: list[dict[str, Any]],
    examples_per_operation: int,
) -> dict[str, list[dict[str, Any]]]:
    """別操作の承認例を意味情報付きのプロンプト用配列へ変換する。"""

    operations_by_id = {
        operation["operation_id"]: operation for operation in all_operations
    }
    groups_by_target: dict[str, list[dict[str, Any]]] = {}
    for target, sources in reference_sources_by_target.items():
        groups: list[dict[str, Any]] = []
        for source in sources:
            pairs = _unique_expression_pairs(
                list(existing_by_operation.get(source, []))
            )
            if not pairs:
                raise ValueError(f"参考操作に既存表現がありません: {source}")
            source_operation = operations_by_id[source]
            groups.append(
                {
                    "operation_id": source,
                    "semantic_ast": source_operation["semantic_ast"],
                    "canonical_meaning_ja": source_operation[
                        "canonical_meaning_ja"
                    ],
                    "expressions": pairs[:examples_per_operation],
                }
            )
        groups_by_target[target] = groups
    return groups_by_target


def _build_selected_reference_groups(
    *,
    selected_references_by_target: Mapping[str, list[tuple[str, str]]],
    existing_by_operation: Mapping[str, list[dict[str, str]]],
    all_operations: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """明示された承認済み終止形だけを意味情報付き参考例へ変換する。"""

    operations_by_id = {
        operation["operation_id"]: operation for operation in all_operations
    }
    groups_by_target: dict[str, list[dict[str, Any]]] = {}
    for target, selections in selected_references_by_target.items():
        groups_by_source: dict[str, dict[str, Any]] = {}
        for source, expression in selections:
            matches = [
                pair
                for pair in existing_by_operation.get(source, [])
                if pair["expression_ja"] == expression
            ]
            if not matches:
                raise ValueError(
                    "承認済みCSVに参考表現がありません: "
                    f"{source}={expression}"
                )
            unique_matches = _unique_expression_pairs(matches)
            if len(unique_matches) != 1:
                raise ValueError(
                    "参考表現の接続形を一意に決められません: "
                    f"{source}={expression}"
                )
            if source not in groups_by_source:
                source_operation = operations_by_id[source]
                groups_by_source[source] = {
                    "operation_id": source,
                    "semantic_ast": source_operation["semantic_ast"],
                    "canonical_meaning_ja": source_operation[
                        "canonical_meaning_ja"
                    ],
                    "expressions": [],
                }
            groups_by_source[source]["expressions"].append(unique_matches[0])
        groups_by_target[target] = list(groups_by_source.values())
    return groups_by_target


def _load_and_validate_operations(settings: Mapping[str, Any]) -> list[dict[str, Any]]:
    # 正式な24操作の意味ASTレコードを読み込む
    input_records = _read_jsonl(settings["input"])
    # 日本語の正準意味と厳守事項を持つ操作定義を読み込む
    definitions, _ = _load_json_object(settings["operation_definitions"])
    # 操作定義ファイルの形式バージョンを確認する
    if definitions.get("config_version") != 1:
        raise ValueError("操作定義のconfig_versionは1にしてください")
    # 操作定義の配列を取り出す
    operations = definitions.get("operations")
    # 24操作が過不足なく定義されていることを確認する
    if not isinstance(operations, list) or len(operations) != 24:
        raise ValueError("操作定義には24操作を指定してください")

    # 正式入力を操作IDから意味ASTへ引ける辞書へ変換する
    input_by_id: dict[str, object] = {}
    # 正式入力の各レコードを順番に読む
    for record in input_records:
        # spec_idを操作IDとして取得する
        operation_id = _required_string(record, "spec_id")
        # 操作IDに対応する意味ASTを辞書へ登録する
        input_by_id[operation_id] = record.get("semantic_ast")
    # 操作IDの重複または不足がないことを件数で確認する
    if len(input_by_id) != 24:
        raise ValueError("意味AST入力には重複のない24操作が必要です")

    # 検査済み操作定義を格納する配列を作る
    validated: list[dict[str, Any]] = []
    # 操作IDの重複確認用集合を作る
    seen_ids: set[str] = set()
    # 意味ASTの重複確認用集合を作る
    seen_asts: set[str] = set()
    # 操作定義を一件ずつ検査する
    for value in operations:
        # 各操作定義がJSONオブジェクトであることを確認する
        if not isinstance(value, dict):
            raise ValueError("各操作定義はオブジェクトにしてください")
        # 操作IDを取得する
        operation_id = _required_string(value, "operation_id")
        # 人間とQwenへ示す正準な意味を取得する
        canonical_meaning = _required_string(value, "canonical_meaning_ja")
        # Qwenが変えてはいけない意味上の注意事項を取得する
        must_preserve = _required_string(value, "must_preserve_ja")
        # 操作定義に保存された意味ASTを取得する
        semantic_ast = value.get("semantic_ast")
        # 正式入力と操作定義の意味ASTが完全一致することを確認する
        if input_by_id.get(operation_id) != semantic_ast:
            raise ValueError(f"操作定義と入力ASTが一致しません: {operation_id}")
        # 意味ASTを決定的JSONにして重複確認キーを作る
        ast_key = canonical_json(semantic_ast)
        # 操作IDまたは意味ASTが既出なら重複として停止する
        if operation_id in seen_ids or ast_key in seen_asts:
            raise ValueError(f"操作定義が重複しています: {operation_id}")
        # 操作IDを確認済み集合へ追加する
        seen_ids.add(operation_id)
        # 意味ASTを確認済み集合へ追加する
        seen_asts.add(ast_key)
        # 必要な項目だけを検査済み操作一覧へ追加する
        validated.append(
            {
                "operation_id": operation_id,
                "semantic_ast": semantic_ast,
                "canonical_meaning_ja": canonical_meaning,
                "must_preserve_ja": must_preserve,
            }
        )
    # 正式入力と操作定義の操作ID集合が完全一致することを確認する
    if seen_ids != set(input_by_id):
        raise ValueError("操作定義と意味AST入力の操作ID集合が一致しません")
    # 検査済みの24操作を返す
    return validated


def _make_candidate_record(
    *,
    operation: Mapping[str, Any],
    expression: str,
    connective_expression: str,
    attempt: int,
    seed: int,
    prompt_hash_value: str,
    generated_at: str,
    result: Any,
    model_id: str,
    sampling: Mapping[str, Any],
) -> dict[str, Any]:
    # 操作IDと二つの表現本文から候補を一意に表すIDを作る
    expression_id = "expr-candidate-" + sha256_text(
        operation["operation_id"]
        + "\0"
        + expression
        + "\0"
        + connective_expression
    )
    # 人間確認と再現に必要な情報を一つの候補レコードへまとめる
    return {
        "expression_id": expression_id,
        "operation_id": operation["operation_id"],
        "operation_ast": operation["semantic_ast"],
        "canonical_meaning_ja": operation["canonical_meaning_ja"],
        "must_preserve_ja": operation["must_preserve_ja"],
        "expression_ja": expression,
        "connective_expression_ja": connective_expression,
        "source": "teacher_atomic",
        "review_status": "pending",
        "teacher_model": model_id,
        "teacher_revision": result.resolved_revision,
        "teacher_quantization": "AWQ 4-bit",
        "teacher_library": "transformers",
        "teacher_library_version": result.transformers_version,
        "teacher_torch_version": result.torch_version,
        "teacher_seed": seed,
        "teacher_sampling": dict(sampling),
        "teacher_generated_at": generated_at,
        "generation_attempt": attempt,
        "prompt_hash": prompt_hash_value,
    }


def _valid_expression_text(expression: str, *, max_chars: int) -> bool:
    """終止形と接続形に共通する日本語表現の形式を検査する。"""

    # 単純操作表現は空でない一行だけに制限する
    if not expression:
        return False
    if "\n" in expression or "\r" in expression:
        return False
    # 確認しづらい過長な表現を除外する
    if len(expression) > max_chars:
        return False
    # コード、thinking、コードフェンスの混入を判定する語を定義する
    forbidden = ("```", "def solve", "<think>", "</think>")
    # 禁止文字列を一つでも含む候補は拒否する
    if any(token in expression for token in forbidden):
        return False
    # 変数名k以外の英字があれば外国語の混入として拒否する
    if NON_K_ASCII_LETTER_PATTERN.search(expression):
        return False
    # 丁寧語や依頼形は短い原子表現として採用しない
    if expression.endswith(("ます", "です", "ください")):
        return False
    # CSVや一文結合時に不要な句読点を表現本文へ含めない
    if expression.endswith(("、", "。", ",", ".")):
        return False
    return True


def _valid_expression(expression: str, *, max_chars: int) -> bool:
    """最終操作に使う動詞基本形の表現を検査する。"""

    # 共通形式検査に落ちる表現は拒否する
    if not _valid_expression_text(expression, max_chars=max_chars):
        return False
    # 原則を生成結果でも保証するため、動詞基本形に現れる仮名だけを末尾に許す
    return expression[-1] in DICTIONARY_FORM_VERB_ENDINGS


def _valid_connective_expression(expression: str, *, max_chars: int) -> bool:
    """後続操作へつなぐ連用形・て形の表現を検査する。"""

    # 共通形式検査に落ちる表現は拒否する
    if not _valid_expression_text(expression, max_chars=max_chars):
        return False
    # 動詞基本形のままではなく、連用形またはて形に見える語尾だけを認める
    return expression.endswith(CONNECTIVE_VERB_ENDINGS)


def _write_review_csv(path: Path, records: list[dict[str, Any]]) -> None:
    # 保存先ディレクトリがなければ作成する
    path.parent.mkdir(parents=True, exist_ok=True)
    # 作成者本人が確認・編集するCSV列を順番どおり定義する
    fieldnames = [
        "expression_id",
        "operation_id",
        "operation_ast",
        "canonical_meaning_ja",
        "must_preserve_ja",
        "expression_ja",
        "connective_expression_ja",
        "review_status",
        "edited_expression_ja",
        "edited_connective_expression_ja",
        "dictionary",
        "reviewer",
        "reviewed_at",
    ]
    # Excel等でも扱えるUTF-8のCSVを新規作成する
    with path.open("w", encoding="utf-8", newline="") as handle:
        # 辞書を指定列順で書くCSV writerを作る
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        # 最初の行へ列名を書き込む
        writer.writeheader()
        # 各候補を一行ずつ確認用CSVへ書き込む
        for record in records:
            # 機械生成項目を埋め、確認者入力欄は空欄で出力する
            writer.writerow(
                {
                    "expression_id": record["expression_id"],
                    "operation_id": record["operation_id"],
                    "operation_ast": canonical_json(record["operation_ast"]),
                    "canonical_meaning_ja": record["canonical_meaning_ja"],
                    "must_preserve_ja": record["must_preserve_ja"],
                    "expression_ja": record["expression_ja"],
                    "connective_expression_ja": record[
                        "connective_expression_ja"
                    ],
                    "review_status": "",
                    "edited_expression_ja": "",
                    "edited_connective_expression_ja": "",
                    "dictionary": "",
                    "reviewer": "",
                    "reviewed_at": "",
                }
            )


def _read_existing_review_csv(path: Path) -> dict[str, list[dict[str, str]]]:
    """確認CSVから操作別の既存終止形・接続形を読み込む。"""

    # 最低限必要な列だけを定義し、追加の確認列はそのまま許可する
    required_fields = {
        "operation_id",
        "expression_ja",
        "connective_expression_ja",
    }
    # 存在しない除外元を指定したままモデルを読み込まないよう先に停止する
    if not path.is_file():
        raise ValueError(f"既存確認CSVが見つかりません: {path}")
    # Excel由来のBOMと先頭のColumn1行を扱えるよう行配列として読む
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))

    # 必須列を含む実ヘッダーを先頭から探す
    header_index: int | None = None
    fieldnames: list[str] | None = None
    for index, row in enumerate(rows):
        if required_fields.issubset(row):
            header_index = index
            fieldnames = row
            break
    if header_index is None or fieldnames is None:
        raise ValueError(
            "既存確認CSVにoperation_id、expression_ja、"
            "connective_expression_jaのヘッダーがありません"
        )
    # 同名列があるとどの値を使うか曖昧になるため拒否する
    if len(fieldnames) != len(set(fieldnames)):
        raise ValueError("既存確認CSVのヘッダー名が重複しています")

    # 操作IDごとにCSV記載順の既存表現を格納する
    by_operation: dict[str, list[dict[str, str]]] = {}
    for row_number, values in enumerate(rows[header_index + 1 :], start=header_index + 2):
        # 完全な空行は読み飛ばす
        if not values or not any(value.strip() for value in values):
            continue
        # ヘッダーより列が多い行は位置ずれを黙認せず停止する
        if len(values) > len(fieldnames):
            raise ValueError(f"既存確認CSVの列数が不正です: 行{row_number}")
        # 末尾空欄が省略されたCSVも列名で参照できるよう不足分を補う
        padded = values + [""] * (len(fieldnames) - len(values))
        record = dict(zip(fieldnames, padded))
        operation_id = record["operation_id"].strip()
        expression = record["expression_ja"].strip()
        connective = record["connective_expression_ja"].strip()
        # 既存例として使う三項目の欠落は入力ミスとして行番号付きで停止する
        if not operation_id or not expression or not connective:
            raise ValueError(
                "既存確認CSVのoperation_id、expression_ja、"
                f"connective_expression_jaは必須です: 行{row_number}"
            )
        pairs = by_operation.setdefault(operation_id, [])
        # 元候補はreview_statusに関係なく、再生成防止用の既存例へ加える
        pairs.append(
            {
                "expression_ja": expression,
                "connective_expression_ja": connective,
            }
        )

        # 人間修正版がある場合は、元候補に加えて実際の採用形も既存例へ加える
        edited_expression = record.get("edited_expression_ja", "").strip()
        edited_connective = record.get(
            "edited_connective_expression_ja", ""
        ).strip()
        if edited_expression or edited_connective:
            pairs.append(
                {
                    "expression_ja": edited_expression or expression,
                    "connective_expression_ja": edited_connective or connective,
                }
            )

    # 同一組がCSV内に複数あってもプロンプトへは一度だけ載せる
    return {
        operation_id: _unique_expression_pairs(pairs)
        for operation_id, pairs in by_operation.items()
    }


def _unique_expression_pairs(
    pairs: list[dict[str, str]],
) -> list[dict[str, str]]:
    """終止形・接続形の組を入力順のまま一意化する。"""

    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for pair in pairs:
        expression = pair["expression_ja"]
        connective = pair["connective_expression_ja"]
        key = (expression, connective)
        if key in seen:
            continue
        seen.add(key)
        unique.append(
            {
                "expression_ja": expression,
                "connective_expression_ja": connective,
            }
        )
    return unique


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    # 読み込んだJSONオブジェクトを格納する配列を作る
    records: list[dict[str, Any]] = []
    # 入力JSONLをUTF-8で開く
    with path.open(encoding="utf-8") as handle:
        # エラー位置を示せるよう行番号付きで一行ずつ読む
        for line_number, line in enumerate(handle, start=1):
            # 空行はレコードとして扱わず読み飛ばす
            if not line.strip():
                continue
            # 一行をJSONとして解析する
            try:
                value = json.loads(line)
            # JSON構文エラーにはファイル名と行番号を付ける
            except json.JSONDecodeError as error:
                raise ValueError(f"JSONLが不正です: {path}:{line_number}") from error
            # 各レコードがJSONオブジェクトであることを確認する
            if not isinstance(value, dict):
                raise ValueError(f"JSONLレコードはオブジェクトにしてください: {path}:{line_number}")
            # 検査済みレコードを配列へ追加する
            records.append(value)
    # 全レコードを読み込み順で返す
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    # 保存先ディレクトリがなければ作成する
    path.parent.mkdir(parents=True, exist_ok=True)
    # 出力JSONLをUTF-8で新規作成する
    with path.open("w", encoding="utf-8") as handle:
        # 各レコードを入力順に一件ずつ書く
        for record in records:
            # 日本語をエスケープせず、一行のJSONへ変換して書く
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            # JSONLのレコード区切りとなる改行を書く
            handle.write("\n")


def _write_json(path: Path, value: object) -> None:
    # 保存先ディレクトリがなければ作成する
    path.parent.mkdir(parents=True, exist_ok=True)
    # 集計値を人間が読めるインデント付きJSONで保存する
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _project_path(value: str) -> Path:
    # 設定文字列をPathへ変換する
    path = Path(value)
    # 絶対パスはそのまま、相対パスはプロジェクトルート基準で返す
    return path if path.is_absolute() else PROJECT_ROOT / path


def _required_mapping(values: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    # 指定キーの値を取得する
    value = values.get(key)
    # JSONオブジェクトに対応する辞書以外は拒否する
    if not isinstance(value, dict):
        raise ValueError(f"{key}はオブジェクトにしてください")
    # 検査済み辞書を返す
    return value


def _required_string(values: Mapping[str, Any], key: str) -> str:
    # 指定キーの値を取得する
    value = values.get(key)
    # 空でない文字列以外は拒否する
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key}は空でない文字列にしてください")
    # 検査済み文字列を返す
    return value


def _required_int(
    values: Mapping[str, Any],
    key: str,
    *,
    allow_zero: bool = False,
) -> int:
    # 指定キーの値を取得する
    value = values.get(key)
    # 0を許可する設定かどうかに応じて下限を決める
    minimum = 0 if allow_zero else 1
    # boolを含まない整数で、下限以上であることを確認する
    if type(value) is not int or value < minimum:
        # エラーメッセージへ表示する下限表現を作る
        relation = "0以上" if allow_zero else "正"
        raise ValueError(f"{key}は{relation}の整数にしてください")
    # 検査済み整数を返す
    return value


# importされたときは生成せず、直接実行された場合だけmainを呼ぶ
if __name__ == "__main__":
    main()
