# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "accelerate>=1.6.0",
#   "autoawq>=0.2.9",
#   "torch>=2.6.0",
#   "transformers>=4.51.0,<5",
# ]
# ///
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
    parse_json_string_list,
    prompt_hash,
    render_prompt,
    sha256_text,
    validate_model_config,
    validate_sampling_config,
)


# 出力へ記録する表現生成器のバージョンを定義する
GENERATOR_VERSION = "1"


def parse_args() -> argparse.Namespace:
    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        description="Qwen3で単純操作ごとの日本語表現候補を生成します。"
    )
    # 正式な生成条件を持つ設定JSONを必須引数として受け取る
    parser.add_argument("--config", required=True, type=Path)
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
    # コマンドラインを解析して返す
    return parser.parse_args()


def main() -> None:
    # コマンドライン引数を取得する
    args = parse_args()
    # 設定JSONを辞書と元文字列の両方で読み込む
    config, config_text = _load_json_object(args.config)
    # 設定値を検査し、パスを絶対パスへ変換する
    settings = _validate_and_resolve_config(config)
    # 24操作の意味定義と入力ASTが一致することを確認する
    operations = _load_and_validate_operations(settings)

    # 設定検査だけを指定された場合はモデルを読み込まない
    if args.validate_config:
        # 確認した操作数と操作ごとの目標件数を表示する
        print(
            f"設定は有効です: operations={len(operations)}, "
            f"target={settings['target_candidates_per_operation']}"
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
    # すでに存在する出力だけを抽出する
    existing = [str(path) for path in output_paths if path.exists()]
    # 上書き指定なしで既存出力がある場合は誤消去を防ぐため停止する
    if existing and not args.overwrite:
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

    # 人間確認へ渡す候補レコードを格納する配列を作る
    candidate_records: list[dict[str, Any]] = []
    # Qwenの生出力と実際のプロンプトを格納する配列を作る
    raw_records: list[dict[str, Any]] = []
    # 目標件数へ届かなかった操作を格納する配列を作る
    failures: list[dict[str, Any]] = []

    # 24操作を定義順に処理する
    for operation_index, operation in enumerate(operations):
        # 現在の操作で採用した表現を格納する
        expressions: list[str] = []
        # 同じ操作内の完全重複を高速に判定する集合を作る
        seen: set[str] = set()
        # 目標件数に達するまで設定回数内でQwen生成を試す
        for attempt in range(max_attempts):
            # すでに目標件数へ到達していれば再生成を打ち切る
            if len(expressions) >= target:
                break
            # 今回の呼び出しで追加生成してほしい件数を計算する
            count = target - len(expressions)
            # 操作と試行ごとに衝突しない決定的seedを計算する
            seed = base_seed + operation_index * 1_000 + attempt
            # 再生成時に同じ候補を避けさせるため既存表現をJSON化する
            existing_expressions = (
                canonical_json(expressions) if expressions else "（なし）"
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
                "attempt": attempt + 1,
                "seed": seed,
                "prompt_hash": current_prompt_hash,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "raw_response": result.text,
                "generated_at": generated_at,
                "parsed_ok": False,
                "parse_error": None,
            }
            # Qwen出力をexpressions文字列配列として解析する
            try:
                generated_expressions = parse_json_string_list(
                    result.text,
                    "expressions",
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
            # Qwenが返した表現を順番に確認する
            for expression in generated_expressions:
                # 改行、長さ、禁止文字列の形式検査に落ちた表現は使わない
                if not _valid_expression(
                    expression,
                    max_chars=settings["max_expression_chars"],
                ):
                    continue
                # 同じ操作ですでに得た完全一致表現は重複採用しない
                if expression in seen:
                    continue
                # 新しい表現を重複確認集合へ登録する
                seen.add(expression)
                # 現在操作の採用済み表現一覧へ追加する
                expressions.append(expression)
                # 人間確認用の候補レコードを作って全体一覧へ追加する
                candidate_records.append(
                    _make_candidate_record(
                        operation=operation,
                        expression=expression,
                        attempt=attempt + 1,
                        seed=seed,
                        prompt_hash_value=current_prompt_hash,
                        generated_at=generated_at,
                        result=result,
                        model_id=teacher.model_id,
                        sampling=settings["sampling"],
                    )
                )
                # 目標件数に達したら今回の出力の残りは採用しない
                if len(expressions) >= target:
                    break

        # 最大試行後も目標件数へ届かなかったかを確認する
        if len(expressions) < target:
            # 操作ID、実件数、目標件数を失敗一覧へ記録する
            failures.append(
                {
                    "operation_id": operation["operation_id"],
                    "generated": len(expressions),
                    "target": target,
                }
            )

    # 実行に使用した設定JSON全文のハッシュを計算する
    config_hash = sha256_text(config_text)
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
        "target_candidates_per_operation": target,
        "candidate_count": len(candidate_records),
        "raw_response_count": len(raw_records),
        "failures": failures,
        "model_id": settings["model"]["model_id"],
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
    # 設定と実装の生成器バージョンが一致することを確認する
    if config["generator_version"] != GENERATOR_VERSION:
        raise ValueError("generator_versionが実装と一致しません")

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
    # 課題指定に合わせて目標数を10〜30件へ制限する
    if not 10 <= target <= 30:
        raise ValueError("target_candidates_per_operationは10〜30にしてください")
    # 最大再試行回数が正の整数であることを確認する
    _required_int(config, "max_attempts_per_operation")
    # seedが0以上の整数であることを確認する
    _required_int(config, "generator_seed", allow_zero=True)
    # 表現の最大文字数が正の整数であることを確認する
    _required_int(config, "max_expression_chars")
    # 検査とパス解決が終わった設定を返す
    return settings


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
    attempt: int,
    seed: int,
    prompt_hash_value: str,
    generated_at: str,
    result: Any,
    model_id: str,
    sampling: Mapping[str, Any],
) -> dict[str, Any]:
    # 操作IDと表現本文から候補を一意に表すIDを作る
    expression_id = "expr-candidate-" + sha256_text(
        operation["operation_id"] + "\0" + expression
    )
    # 人間確認と再現に必要な情報を一つの候補レコードへまとめる
    return {
        "expression_id": expression_id,
        "operation_id": operation["operation_id"],
        "operation_ast": operation["semantic_ast"],
        "canonical_meaning_ja": operation["canonical_meaning_ja"],
        "must_preserve_ja": operation["must_preserve_ja"],
        "expression_ja": expression,
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


def _valid_expression(expression: str, *, max_chars: int) -> bool:
    # 単純操作表現は一行だけに制限する
    if "\n" in expression or "\r" in expression:
        return False
    # 確認しづらい過長な表現を除外する
    if len(expression) > max_chars:
        return False
    # コード、thinking、コードフェンスの混入を判定する語を定義する
    forbidden = ("```", "def solve", "<think>", "</think>")
    # 禁止文字列を一つも含まない場合だけ有効とする
    return not any(token in expression for token in forbidden)


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
        "review_status",
        "edited_expression_ja",
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
                    "review_status": "",
                    "edited_expression_ja": "",
                    "dictionary": "",
                    "reviewer": "",
                    "reviewed_at": "",
                }
            )


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
