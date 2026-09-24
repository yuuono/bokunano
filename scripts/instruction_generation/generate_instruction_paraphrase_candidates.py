"""ルール生成指示の一部をQwen3で言い換える。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse
# 遅延生成されるバッチ結果の型注釈に使う
from collections.abc import Iterator
# 人間確認用CSVを書き出すために使う
import csv
# 教師生成日時をUTCで記録するために使う
from datetime import datetime, timezone
# 設定と候補をJSONで読み書きするために使う
import json
# 入出力ファイルのパスを扱うために使う
from pathlib import Path
# プロジェクト内モジュールのimport経路を設定するために使う
import sys
# 設定辞書と候補レコードの型注釈に使う
from typing import Any, Mapping


# このファイルから二階層上をプロジェクトルートとして取得する
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 直接実行時にプロジェクト内モジュールを読み込めるか確認する
if str(PROJECT_ROOT) not in sys.path:
    # プロジェクトルートをimport検索パスの先頭へ追加する
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.instruction_generation.qwen_teacher import (  # noqa: E402
    # 次の値または処理を現在の構造へ組み込む
    QwenTeacher,
    # 次の値または処理を現在の構造へ組み込む
    canonical_json,
    # 次の値または処理を現在の構造へ組み込む
    parse_json_string_list,
    # 次の値または処理を現在の構造へ組み込む
    prompt_hash,
    # 次の値または処理を現在の構造へ組み込む
    render_prompt,
    # 次の値または処理を現在の構造へ組み込む
    sha256_text,
    # 次の値または処理を現在の構造へ組み込む
    validate_model_config,
    # 次の値または処理を現在の構造へ組み込む
    validate_sampling_config,
)


# 出力へ記録する全文言い換え生成器のバージョンを定義する
GENERATOR_VERSION = "2"


# この工程を担当する関数を定義する
def parse_args() -> argparse.Namespace:
    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        # descriptionへこの工程で使用する値を設定する
        description="ルール生成済み日本語指示の一部をQwen3で言い換えます。"
    )
    # 全文言い換えの生成条件を持つ設定JSONを受け取る
    parser.add_argument("--config", required=True, type=Path)
    # clone先でローカルモデルの配置場所だけを差し替えられるようにする
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--model-path",
        # typeへこの工程で使用する値を設定する
        type=Path,
        # helpへこの工程で使用する値を設定する
        help=(
            "設定JSONのmodel.model_pathを今回の実行だけ上書きする"
            "ローカルQwenモデルのディレクトリです。"
        ),
    )
    # モデルを読み込まず設定と入力だけを確認するオプションを追加する
    parser.add_argument("--validate-config", action="store_true")
    # 既存出力を明示的に置き換えるオプションを追加する
    parser.add_argument("--overwrite", action="store_true")
    # コマンドラインを解析して返す
    return parser.parse_args()


# この工程を担当する関数を定義する
def main() -> None:
    # コマンドライン引数を取得する
    args = parse_args()
    # 設定JSONを辞書と元文字列の両方で読み込む
    config, config_text = _load_json_object(args.config.resolve())
    # clone先固有のモデル配置場所が指定された場合だけ設定値を差し替える
    config = _override_model_path(config, args.model_path)
    # 設定値を検査し、パスを絶対パスへ変換する
    settings = _validate_config(config)
    # 24操作の正準意味と厳守事項を意味ASTから引ける形で読み込む
    definitions = _load_operation_definitions(settings["operation_definitions"])
    # ルールベース生成済みの指示レコードを読み込む
    source_records = _read_jsonl(settings["input"])
    # 全件ではなく設定割合だけを決定的に選ぶ
    selected = _select_sources(
        # 次の値または処理を現在の構造へ組み込む
        source_records,
        # splitへこの工程で使用する値を設定する
        split=settings["source_split"],
        # dictionaryへこの工程で使用する値を設定する
        dictionary=settings["source_dictionary"],
        # per_astへこの工程で使用する値を設定する
        per_ast=settings["source_instructions_per_ast"],
        # seedへこの工程で使用する値を設定する
        seed=settings["generator_seed"],
    )
    # 選抜後の意味AST数を数える
    selected_ast_count = len({record["spec_id"] for record in selected})
    # 意味AST数が設定した期待値と一致することを確認する
    if selected_ast_count != settings["expected_source_ast_count"]:
        # 入力または選抜条件のずれを通知する
        raise ValueError(f"選抜元の意味AST数が不一致です: {selected_ast_count}")
    # 選抜指示数が設定した期待値と一致することを確認する
    if len(selected) != settings["expected_selected_source_count"]:
        # 各意味ASTから10件を得られていない状態を通知する
        raise ValueError(f"言い換え元の選抜件数が不一致です: {len(selected)}")

    # 設定検査だけの場合はモデルを読み込まない
    if args.validate_config:
        # 入力件数と言い換え対象件数を表示する
        print(
            # 次の値または処理を現在の構造へ組み込む
            f"設定は有効です: input={len(source_records)}, "
            f"asts={selected_ast_count}, selected={len(selected)}"
        )
        # 教師生成へ進まず終了する
        return
    # 抽出結果が0件なら設定ミスの可能性があるため停止する
    if not selected:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("言い換え対象が0件です。split、dictionary、入力を確認してください")

    # この実行で作成する4つの出力パスをまとめる
    output_paths = [
        # 次の値または処理を現在の構造へ組み込む
        settings["output"],
        # 次の値または処理を現在の構造へ組み込む
        settings["raw_responses"],
        # 次の値または処理を現在の構造へ組み込む
        settings["review_csv"],
        # 次の値または処理を現在の構造へ組み込む
        settings["stats"],
    ]
    # すでに存在する出力パスだけを抽出する
    existing = [str(path) for path in output_paths if path.exists()]
    # 上書き指定なしで既存出力があれば誤消去を防ぐため停止する
    if existing and not args.overwrite:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(
            "既存出力があります。置き換える場合は--overwriteを指定してください: "
            # 次の値または処理を現在の構造へ組み込む
            + ", ".join(existing)
        )

    # 全文言い換え用のsystem promptを読み込む
    system_prompt = settings["system_prompt"].read_text(encoding="utf-8").strip()
    # Qwen3モデルとtokenizerを一度だけ読み込む
    teacher = QwenTeacher(settings["model"])
    # 中断時にも完了済み情報を残せるようJSONL出力を空の状態で作る
    _write_jsonl(settings["output"], [])
    # 生応答も各バッチ後に追記できる空のJSONLとして作る
    _write_jsonl(settings["raw_responses"], [])
    # 人間確認前の言い換え候補を格納する配列を作る
    candidates: list[dict[str, Any]] = []
    # Qwenへ渡したプロンプトと生出力を格納する配列を作る
    raw_records: list[dict[str, Any]] = []
    # JSON解析失敗などを記録する配列を作る
    failures: list[dict[str, str]] = []

    # 選ばれた指示をバッチ生成し、結果を元の順番で一件ずつ処理する
    for generated_item in _generate_selected(
        # 選抜済み元指示を渡す
        selected=selected,
        # 意味ASTごとの正準定義を渡す
        definitions=definitions,
        # 検査済み生成設定を渡す
        settings=settings,
        # 読み込み済み教師モデルを渡す
        teacher=teacher,
        # 全件共通のsystem promptを渡す
        system_prompt=system_prompt,
    ):
        # 後続の保存処理で使う生成情報を取り出す
        source = generated_item["source"]
        # 実際に使用したuser promptを取り出す
        user_prompt = generated_item["user_prompt"]
        # system/user promptの組に対応するハッシュを取り出す
        current_prompt_hash = generated_item["prompt_hash"]
        # バッチsamplingへ使ったseedを取り出す
        seed = generated_item["seed"]
        # 教師モデルを呼び出したUTC日時を取り出す
        generated_at = generated_item["generated_at"]
        # 一件分の教師モデル生成結果を取り出す
        result = generated_item["result"]
        # バッチ先頭の全体位置を取り出す
        batch_start = generated_item["batch_start"]
        # バッチ内の位置を取り出す
        batch_position = generated_item["batch_position"]
        # 元指示を一意に識別するIDを取得する
        instruction_id = _required_string(source, "instruction_id")
        # Qwenへ渡す元の日本語指示を取得する
        instruction = _required_string(source, "instruction_ja")
        # 元指示が表す意味ASTを取得する
        semantic_ast = source.get("semantic_ast")
        # 解析成否にかかわらず保存する生出力レコードを作る
        raw_record: dict[str, Any] = {
            # 出力レコードの項目と値を設定する
            "source_instruction_id": instruction_id,
            # 出力レコードの項目と値を設定する
            "seed": seed,
            # 固定選択順におけるバッチ先頭位置を記録する
            "batch_start": batch_start,
            # バッチ内の0始まり位置を記録する
            "batch_position": batch_position,
            # 出力レコードの項目と値を設定する
            "prompt_hash": current_prompt_hash,
            # 出力レコードの項目と値を設定する
            "system_prompt": system_prompt,
            # 出力レコードの項目と値を設定する
            "user_prompt": user_prompt,
            # 出力レコードの項目と値を設定する
            "raw_response": result.text,
            # 出力レコードの項目と値を設定する
            "generated_at": generated_at,
            # 出力レコードの項目と値を設定する
            "parsed_ok": False,
            # 既知の閉じ引用符補正を適用したかの初期値を記録する
            "parse_repaired": False,
            # 出力レコードの項目と値を設定する
            "parse_error": None,
        }
        # Qwen出力をparaphrases文字列配列として解析する
        try:
            # 厳密JSONまたは記録対象の既知末尾崩れとして解析する
            paraphrases, parse_repaired = _parse_paraphrase_response(result.text)
        # JSON形式が不正な場合も生出力と原因を保存して次へ進む
        except ValueError as error:
            # 解析エラーを生出力レコードへ記録する
            raw_record["parse_error"] = str(error)
            # 失敗した応答も監査用に保存する
            raw_records.append(raw_record)
            # 中断時にもこの生応答が残るよう直ちにJSONLへ追記する
            _append_jsonl(settings["raw_responses"], [raw_record])
            # 元指示IDと失敗理由を集計へ追加する
            failures.append(
                # 次の値または処理を現在の構造へ組み込む
                {"source_instruction_id": instruction_id, "reason": str(error)}
            )
            # 次の元指示へ進む
            continue
        # JSON解析に成功したことを記録する
        raw_record["parsed_ok"] = True
        # 既知の閉じ引用符だけを補正したかを監査用に記録する
        raw_record["parse_repaired"] = parse_repaired
        # 成功した生出力も保存対象へ追加する
        raw_records.append(raw_record)
        # 中断時にもこの生応答が残るよう直ちにJSONLへ追記する
        _append_jsonl(settings["raw_responses"], [raw_record])

        # 元文と異なる固有候補だけを格納する配列を作る
        unique_paraphrases: list[str] = []
        # Qwenが返した各言い換え候補を順番に検査する
        for paraphrase in paraphrases:
            # 元文と完全一致する候補や同一応答内の重複を除外する
            if paraphrase == instruction or paraphrase in unique_paraphrases:
                # 現在の対象を終えて次の対象へ進む
                continue
            # thinkingタグまたはコードフェンスが混入した候補を除外する
            if "<think>" in paraphrase or "```" in paraphrase:
                # 現在の対象を終えて次の対象へ進む
                continue
            # 形式検査を通過した言い換え候補を追加する
            unique_paraphrases.append(paraphrase)
            # 設定件数に達したら余分な候補は採用しない
            if len(unique_paraphrases) >= settings["paraphrases_per_instruction"]:
                # 条件を満たしたため繰り返しを終了する
                break
        # 固有候補を一件も得られなかった場合を失敗として記録する
        if not unique_paraphrases:
            # 次の値または処理を現在の構造へ組み込む
            failures.append(
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "source_instruction_id": instruction_id,
                    # 出力レコードの項目と値を設定する
                    "reason": "固有の言い換え候補を取得できませんでした",
                }
            )
            # 次の元指示へ進む
            continue

        # 形式検査を通過した各候補を人間確認用レコードへ変換する
        for paraphrase in unique_paraphrases:
            # 元指示IDと候補本文から一意な候補IDを作る
            candidate_id = "instruction-teacher-candidate-" + sha256_text(
                # 次の値または処理を現在の構造へ組み込む
                instruction_id + "\0" + paraphrase
            )
            # 元文、AST、モデル情報を含む候補レコードを追加する
            candidates.append(
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "instruction_id": candidate_id,
                    # 出力レコードの項目と値を設定する
                    "source_instruction_id": instruction_id,
                    # 出力レコードの項目と値を設定する
                    "spec_id": source.get("spec_id"),
                    # 出力レコードの項目と値を設定する
                    "semantic_ast": semantic_ast,
                    # 出力レコードの項目と値を設定する
                    "source_instruction_ja": instruction,
                    # 出力レコードの項目と値を設定する
                    "instruction_ja": paraphrase,
                    # 出力レコードの項目と値を設定する
                    "instruction_source": "teacher",
                    # 出力レコードの項目と値を設定する
                    "dictionary": source.get("dictionary"),
                    # 出力レコードの項目と値を設定する
                    "review_status": "pending",
                    # 出力レコードの項目と値を設定する
                    "teacher_model": settings["model"]["model_id"],
                    # 出力レコードの項目と値を設定する
                    "teacher_revision": result.resolved_revision,
                    # 出力レコードの項目と値を設定する
                    "teacher_quantization": "AWQ 4-bit",
                    # 出力レコードの項目と値を設定する
                    "teacher_library": "transformers",
                    # 出力レコードの項目と値を設定する
                    "teacher_library_version": result.transformers_version,
                    # 出力レコードの項目と値を設定する
                    "teacher_torch_version": result.torch_version,
                    # 出力レコードの項目と値を設定する
                    "teacher_seed": seed,
                    # 同一seedを共有したバッチ先頭位置を保存する
                    "teacher_batch_start": batch_start,
                    # 同一バッチ内の0始まり位置を保存する
                    "teacher_batch_position": batch_position,
                    # 出力レコードの項目と値を設定する
                    "teacher_sampling": settings["sampling"],
                    # 出力レコードの項目と値を設定する
                    "teacher_generated_at": generated_at,
                    # 出力レコードの項目と値を設定する
                    "prompt_hash": current_prompt_hash,
                    # 出力レコードの項目と値を設定する
                    "text_hash": sha256_text(paraphrase),
                }
            )
        # この元指示から得た候補を中断耐性のあるJSONLへ直ちに追記する
        _append_jsonl(settings["output"], candidates[-len(unique_paraphrases):])

    # 人間確認前の言い換え候補をJSONLへ保存する
    _write_jsonl(settings["output"], candidates)
    # 実際のプロンプトとQwen生出力をJSONLへ保存する
    _write_jsonl(settings["raw_responses"], raw_records)
    # 元文と候補を横並びにした人間確認用CSVを保存する
    _write_review_csv(settings["review_csv"], candidates)
    # 実行条件、件数、失敗内容を持つ集計レコードを作る
    stats = {
        # 出力レコードの項目と値を設定する
        "phase": "instruction_paraphrase_candidates",
        # 出力レコードの項目と値を設定する
        "input_count": len(source_records),
        # 出力レコードの項目と値を設定する
        "selected_source_count": len(selected),
        # 出力レコードの項目と値を設定する
        "candidate_count": len(candidates),
        # 出力レコードの項目と値を設定する
        "failure_count": len(failures),
        # 出力レコードの項目と値を設定する
        "failures": failures,
        # 出力レコードの項目と値を設定する
        "source_split": settings["source_split"],
        # 出力レコードの項目と値を設定する
        "source_dictionary": settings["source_dictionary"],
        # 出力レコードの項目と値を設定する
        "source_instructions_per_ast": settings["source_instructions_per_ast"],
        # 出力レコードの項目と値を設定する
        "selected_source_ast_count": selected_ast_count,
        # 出力レコードの項目と値を設定する
        "model_id": settings["model"]["model_id"],
        # 出力レコードの項目と値を設定する
        "model_path": teacher.model_path,
        # 出力レコードの項目と値を設定する
        "requested_revision": settings["model"]["revision"],
        # 出力レコードの項目と値を設定する
        "resolved_revision": teacher.resolved_revision,
        # 出力レコードの項目と値を設定する
        "enable_thinking": False,
        # 出力レコードの項目と値を設定する
        "sampling": settings["sampling"],
        # 出力レコードの項目と値を設定する
        "generator_version": GENERATOR_VERSION,
        # 出力レコードの項目と値を設定する
        "generator_seed": settings["generator_seed"],
        # 一回のmodel.generateへ渡した最大件数を記録する
        "batch_size": settings["batch_size"],
        # 出力レコードの項目と値を設定する
        "config_hash": sha256_text(config_text),
        # 出力レコードの項目と値を設定する
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    # 集計レコードを整形JSONとして保存する
    _write_json(settings["stats"], stats)
    # 対象件数、候補件数、失敗件数を表示する
    print(
        # 次の値または処理を現在の構造へ組み込む
        f"言い換え候補生成完了: selected={len(selected)}, "
        # 次の値または処理を現在の構造へ組み込む
        f"candidates={len(candidates)}, failures={len(failures)}"
    )
    # 作成者本人が次に開く確認用CSVの場所を表示する
    print(f"確認用CSV: {settings['review_csv']}")


# この工程を担当する関数を定義する
def _generate_selected(
    # 選抜済み元指示を受け取る
    *,
    # 選抜済み元指示を受け取る
    selected: list[dict[str, Any]],
    # 意味ASTから正準定義を引く辞書を受け取る
    definitions: Mapping[str, dict[str, str]],
    # 検査済み設定を受け取る
    settings: Mapping[str, Any],
    # 読み込み済み教師モデルを受け取る
    teacher: QwenTeacher,
    # 全件共通のsystem promptを受け取る
    system_prompt: str,
# 一件ずつ後続処理へ渡すiteratorを返す
) -> Iterator[dict[str, Any]]:
    """promptを組み立て、設定件数ごとにQwenへまとめて渡す。"""

    # 一回のmodel.generateへ渡す件数を設定から取得する
    batch_size = settings["batch_size"]
    # 全対象を固定した並びのままバッチ先頭位置ごとに処理する
    for batch_start in range(0, len(selected), batch_size):
        # 今回のバッチへ含める元指示を切り出す
        batch_sources = selected[batch_start : batch_start + batch_size]
        # Qwenへ渡すuser promptを入力順に格納する配列を作る
        user_prompts: list[str] = []
        # 各promptと一緒に保存するメタデータ配列を作る
        prepared: list[dict[str, Any]] = []
        # 今回の元指示を順番にpromptへ変換する
        for batch_position, source in enumerate(batch_sources):
            # 元指示を一意に識別するIDを取得する
            instruction_id = _required_string(source, "instruction_id")
            # Qwenへ渡す元の日本語指示を取得する
            instruction = _required_string(source, "instruction_ja")
            # 元指示が表す意味ASTを取得する
            semantic_ast = source.get("semantic_ast")
            # 単独操作とsequence形式を同じ操作配列へ正規化する
            sequence = _normalize_sequence(semantic_ast)
            # Qwenへ示す操作の正準意味を順番に格納する配列を作る
            operation_details: list[str] = []
            # Qwenが保持すべき注意事項を順番に格納する配列を作る
            preserve_details: list[str] = []
            # 意味ASTの各操作を元の実行順どおりに処理する
            for position, operation in enumerate(sequence, start=1):
                # 操作の意味ASTから対応する正準定義を取得する
                definition = definitions.get(canonical_json(operation))
                # 未定義操作があれば誤った言い換えを防ぐため停止する
                if definition is None:
                    # 不正な状態を例外として通知して処理を停止する
                    raise ValueError(
                        # どの元指示に未定義操作があったかを含める
                        f"操作定義にない意味ASTです: {instruction_id}: {operation!r}"
                    )
                # 操作位置と正準意味をprompt用一覧へ追加する
                operation_details.append(
                    # 操作順が変わらないよう番号付きで記述する
                    f"{position}. {definition['canonical_meaning_ja']}"
                )
                # 操作位置と厳守事項をprompt用一覧へ追加する
                preserve_details.append(
                    # 操作ごとの禁止変更事項を番号付きで記述する
                    f"{position}. {definition['must_preserve_ja']}"
                )
            # AST、操作順、厳守事項、元文をuser promptへ埋め込む
            user_prompt = render_prompt(
                # 設定で指定したuser promptテンプレートを使う
                settings["user_prompt"],
                # テンプレート変数へ今回の意味情報を渡す
                {
                    # 元文一件から要求する候補数を設定する
                    "count": settings["paraphrases_per_instruction"],
                    # 意味ASTを決定的JSON文字列として設定する
                    "semantic_ast": canonical_json(semantic_ast),
                    # 操作順を改行区切りで設定する
                    "operation_sequence": "\n".join(operation_details),
                    # 保持事項を改行区切りで設定する
                    "must_preserve_ja": "\n".join(preserve_details),
                    # 実際に言い換える元指示を設定する
                    "source_instruction": instruction,
                },
            # promptファイル末尾由来の余分な空白を除く
            ).strip()
            # バッチ生成へ渡すprompt配列へ追加する
            user_prompts.append(user_prompt)
            # 保存処理で必要な元レコードとprompt情報を保持する
            prepared.append(
                # 一件分の生成前メタデータをまとめる
                {
                    # 元の指示レコードを保持する
                    "source": source,
                    # 実際に使用するuser promptを保持する
                    "user_prompt": user_prompt,
                    # system/user promptの組からハッシュを計算する
                    "prompt_hash": prompt_hash(system_prompt, user_prompt),
                    # バッチ内の0始まり位置を保持する
                    "batch_position": batch_position,
                }
            )
        # 固定選択順のバッチ先頭位置からsampling seedを決める
        batch_seed = settings["generator_seed"] + batch_start
        # このQwenバッチ呼び出しのUTC日時を記録する
        generated_at = datetime.now(timezone.utc).isoformat()
        # Qwen3を非thinkingモードでバッチ実行する
        results = teacher.generate_batch(
            # 全件共通のsystem promptを渡す
            system_prompt=system_prompt,
            # 今回のuser prompt配列を渡す
            user_prompts=user_prompts,
            # temperatureなどのsampling設定を渡す
            sampling=settings["sampling"],
            # 今回のバッチ全体で使うseedを渡す
            seed=batch_seed,
        )
        # モデルが入力件数と異なる結果数を返した場合は保存前に停止する
        if len(results) != len(prepared):
            # 入出力件数の不一致を例外として通知する
            raise RuntimeError("Qwenのバッチ入力数と生成結果数が一致しません")
        # 入力順を保ったまま一件ずつ後続処理へ渡す
        for item, result in zip(prepared, results, strict=True):
            # バッチ共通情報と一件分の結果をメタデータへ追加する
            yield {
                # 元指示を後続へ渡す
                **item,
                # 今回のバッチ先頭位置を保持する
                "batch_start": batch_start,
                # 今回のバッチ全体で使ったseedを保持する
                "seed": batch_seed,
                # バッチ呼び出し日時を保持する
                "generated_at": generated_at,
                # 一件分の生成結果を保持する
                "result": result,
            }
        # 長時間実行の進捗をバッチ単位で標準出力へ表示する
        print(
            # 完了件数と全対象件数を同じ行へ表示する
            f"言い換え生成進捗: {min(batch_start + len(batch_sources), len(selected))}"
            f"/{len(selected)}"
        )


# この工程を担当する関数を定義する
def _parse_paraphrase_response(text: str) -> tuple[list[str], bool]:
    """厳密JSONを読み、Qwenの既知の閉じ引用符崩れだけを補正する。"""

    # まず通常の厳密JSONとして解析する
    try:
        # 補正不要だったことと一緒に候補配列を返す
        return parse_json_string_list(text, "paraphrases"), False
    # 厳密JSONでなかった場合だけ既知パターンを確認する
    except ValueError as original_error:
        # 前後空白を除いて末尾を正確に比較できるようにする
        stripped = text.strip()
        # JSON文字列の閉じ二重引用符だけが単一引用符になった形に限定する
        if stripped.startswith('{"paraphrases":["') and stripped.endswith("']}"):
            # 最後の単一引用符、配列終端、object終端を正しいJSON末尾へ置き換える
            repaired = stripped[:-3] + '"]}'
            # 補正後も厳密な所定schemaを満たす場合だけ候補として返す
            return parse_json_string_list(repaired, "paraphrases"), True
        # 対象外の崩れは従来どおり失敗として呼び出し元へ返す
        raise original_error


# この工程を担当する関数を定義する
def _override_model_path(
    # 次の値または処理を現在の構造へ組み込む
    config: dict[str, Any], model_path: Path | None
# 次の値または処理を現在の構造へ組み込む
) -> dict[str, Any]:
    """CLI指定がある場合だけローカルモデルの配置場所を上書きする。"""

    # 条件を満たす場合だけ次の処理を行う
    if model_path is None:
        # 処理結果を呼び出し元へ返す
        return config
    # modelへこの工程で使用する値を設定する
    model = config.get("model")
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(model, dict):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("設定のmodelはobjectにしてください")
    # overriddenへこの工程で使用する値を設定する
    overridden = dict(config)
    # 次の値または処理を現在の構造へ組み込む
    overridden["model"] = dict(model)
    # 次の値または処理を現在の構造へ組み込む
    overridden["model"]["model_path"] = str(model_path.resolve())
    # 処理結果を呼び出し元へ返す
    return overridden


# この工程を担当する関数を定義する
def _validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    # 設定JSONに必要なキーを厳密に列挙する
    expected = {
        # この処理で扱う文字列を一覧へ加える
        "config_version",
        # この処理で扱う文字列を一覧へ加える
        "phase",
        # この処理で扱う文字列を一覧へ加える
        "input",
        # この処理で扱う文字列を一覧へ加える
        "operation_definitions",
        # この処理で扱う文字列を一覧へ加える
        "output",
        # この処理で扱う文字列を一覧へ加える
        "raw_responses",
        # この処理で扱う文字列を一覧へ加える
        "review_csv",
        # この処理で扱う文字列を一覧へ加える
        "stats",
        # この処理で扱う文字列を一覧へ加える
        "prompts",
        # この処理で扱う文字列を一覧へ加える
        "source_split",
        # この処理で扱う文字列を一覧へ加える
        "source_dictionary",
        # この処理で扱う文字列を一覧へ加える
        "source_instructions_per_ast",
        # この処理で扱う文字列を一覧へ加える
        "expected_source_ast_count",
        # この処理で扱う文字列を一覧へ加える
        "expected_selected_source_count",
        # この処理で扱う文字列を一覧へ加える
        "paraphrases_per_instruction",
        # この処理で扱う文字列を一覧へ加える
        "generator_version",
        # この処理で扱う文字列を一覧へ加える
        "generator_seed",
        # この処理で扱う文字列を一覧へ加える
        "batch_size",
        # この処理で扱う文字列を一覧へ加える
        "model",
        # この処理で扱う文字列を一覧へ加える
        "sampling",
    }
    # 設定キーが過不足なく一致することを確認する
    if set(config) != expected:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("言い換え生成設定の項目が不正です")
    # 対応する設定形式のバージョンを確認する
    if config["config_version"] != 1:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("config_versionは1にしてください")
    # このスクリプト用の処理段階名であることを確認する
    if config["phase"] != "instruction_paraphrase_candidates":
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("phaseが不正です")
    # 設定と実装の生成器バージョンが一致することを確認する
    if config["generator_version"] != GENERATOR_VERSION:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("generator_versionが実装と一致しません")
    # promptファイル設定を辞書として取得する
    prompts = _required_mapping(config, "prompts")
    # systemとuser以外のpromptキーを許可しない
    if set(prompts) != {"system", "user"}:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("promptsにはsystemとuserだけを指定してください")
    # モデル設定をモデル読込前に検査する
    model = validate_model_config(_required_mapping(config, "model"))

    # 元設定を壊さないよう解決済み設定用のコピーを作る
    settings = dict(config)
    # 入出力に使う各パスを順番に絶対パスへ変換する
    for key in (
        # この処理で扱う文字列を一覧へ加える
        "input",
        # この処理で扱う文字列を一覧へ加える
        "operation_definitions",
        # この処理で扱う文字列を一覧へ加える
        "output",
        # この処理で扱う文字列を一覧へ加える
        "raw_responses",
        # この処理で扱う文字列を一覧へ加える
        "review_csv",
        # この処理で扱う文字列を一覧へ加える
        "stats",
    # 次の値または処理を現在の構造へ組み込む
    ):
        # パス設定を文字列として検査してプロジェクト基準へ変換する
        settings[key] = _project_path(_required_string(config, key))
    # system promptのパスをプロジェクト基準へ変換する
    settings["system_prompt"] = _project_path(_required_string(prompts, "system"))
    # user promptのパスをプロジェクト基準へ変換する
    settings["user_prompt"] = _project_path(_required_string(prompts, "user"))
    # 検査済みモデル設定を解決済み設定へ格納する
    settings["model"] = model
    # sampling設定を検査して解決済み設定へ格納する
    settings["sampling"] = validate_sampling_config(
        # 次の値または処理を現在の構造へ組み込む
        _required_mapping(config, "sampling")
    )
    # 生成開始前から必要な入力ファイルを順番に確認する
    for key in ("input", "operation_definitions", "system_prompt", "user_prompt"):
        # 入力ファイルがなければモデルを読み込む前に停止する
        if not settings[key].is_file():
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"入力ファイルが見つかりません: {settings[key]}")
    # 言い換え対象のsplitを取得する
    settings["source_split"] = _required_string(config, "source_split")
    # 言い換え対象の辞書区分を取得する
    settings["source_dictionary"] = _required_string(config, "source_dictionary")
    # 意味ASTごとに選ぶ元指示数を確認する
    _required_int(config, "source_instructions_per_ast")
    # 対象となる意味ASTの期待数を確認する
    _required_int(config, "expected_source_ast_count")
    # 選抜後の元指示の期待数を確認する
    _required_int(config, "expected_selected_source_count")
    # 意味AST数とASTごとの件数の積が全選抜数になることを確認する
    if (
        config["source_instructions_per_ast"] * config["expected_source_ast_count"]
        != config["expected_selected_source_count"]
    ):
        # 設定内の件数不整合を通知する
        raise ValueError("意味AST数、ASTごとの選抜数、全選抜数が不一致です")
    # 一つの元指示から作る候補数を確認する
    _required_int(config, "paraphrases_per_instruction")
    # 選択と生成に使う基準seedを確認する
    _required_int(config, "generator_seed", allow_zero=True)
    # 一回のmodel.generateへ渡す件数を確認する
    _required_int(config, "batch_size")
    # 検査とパス解決が終わった設定を返す
    return settings


# この工程を担当する関数を定義する
def _load_operation_definitions(path: Path) -> dict[str, dict[str, str]]:
    # 24操作の日本語定義JSONを読み込む
    value, _ = _load_json_object(path)
    # 操作定義の配列を取り出す
    operations = value.get("operations")
    # 設定バージョンと配列形式を確認する
    if value.get("config_version") != 1 or not isinstance(operations, list):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("操作定義が不正です")
    # 意味ASTから日本語定義を引ける辞書を作る
    result: dict[str, dict[str, str]] = {}
    # 各操作定義を順番に検査する
    for operation in operations:
        # 各操作定義がJSONオブジェクトであることを確認する
        if not isinstance(operation, dict):
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("操作定義の各要素はオブジェクトにしてください")
        # 意味ASTを決定的JSONにして検索キーを作る
        key = canonical_json(operation.get("semantic_ast"))
        # 正準意味と厳守事項を検索辞書へ登録する
        result[key] = {
            # 出力レコードの項目と値を設定する
            "canonical_meaning_ja": _required_string(
                # 次の値または処理を現在の構造へ組み込む
                operation, "canonical_meaning_ja"
            ),
            # 出力レコードの項目と値を設定する
            "must_preserve_ja": _required_string(operation, "must_preserve_ja"),
        }
    # 重複のない24操作が登録されたことを確認する
    if len(result) != 24:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("操作定義には重複のない24操作が必要です")
    # 意味ASTをキーとする操作定義辞書を返す
    return result


# この工程を担当する関数を定義する
def _normalize_sequence(semantic_ast: object) -> list[object]:
    # 意味ASTがJSONオブジェクトであることを確認する
    if not isinstance(semantic_ast, dict):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("semantic_astはオブジェクトにしてください")
    # sequenceだけを持つ意味ASTは複数操作として扱う
    if set(semantic_ast) == {"sequence"}:
        # sequence配列を取得する
        sequence = semantic_ast["sequence"]
        # 課題範囲である1〜3操作の配列か確認する
        if not isinstance(sequence, list) or not 1 <= len(sequence) <= 3:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("sequenceには1〜3操作が必要です")
        # 呼び出し元で変更されても元ASTを壊さないようコピーして返す
        return list(sequence)
    # 単独操作は一要素の配列へ包んで返す
    return [semantic_ast]


# この工程を担当する関数を定義する
def _select_sources(
    # 次の値または処理を現在の構造へ組み込む
    records: list[dict[str, Any]],
    # 次の値または処理を現在の構造へ組み込む
    *,
    # 次の値または処理を現在の構造へ組み込む
    split: str,
    # 次の値または処理を現在の構造へ組み込む
    dictionary: str,
    # 次の値または処理を現在の構造へ組み込む
    per_ast: int,
    # 次の値または処理を現在の構造へ組み込む
    seed: int,
# 次の値または処理を現在の構造へ組み込む
) -> list[dict[str, Any]]:
    # 意味ASTごとにハッシュ順位とレコードの組を格納する辞書を作る
    ranked_by_spec: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    # 入力指示を一件ずつ対象区分へ絞り込む
    for record in records:
        # 設定したsplit以外は教師言い換え対象にしない
        if record.get("split") != split:
            # 次の入力指示へ進む
            continue
        # 設定した辞書区分以外は教師言い換え対象にしない
        if record.get("dictionary") != dictionary:
            # 次の入力指示へ進む
            continue
        # 意味ASTを識別するIDを取得する
        spec_id = _required_string(record, "spec_id")
        # 選択単位となる指示IDを取得する
        instruction_id = _required_string(record, "instruction_id")
        # seed、意味AST ID、指示IDからランダム順位用ハッシュを作る
        digest = sha256_text(f"{seed}\0{spec_id}\0{instruction_id}")
        # 現在意味ASTの候補配列へハッシュとレコードを保存する
        ranked_by_spec.setdefault(spec_id, []).append((digest, record))
    # 選抜したレコードを意味AST順に格納する配列を作る
    selected: list[dict[str, Any]] = []
    # 意味AST ID順に各候補群を処理する
    for spec_id in sorted(ranked_by_spec):
        # 現在意味ASTの候補を固定seed由来のハッシュ昇順に並べる
        ranked = sorted(ranked_by_spec[spec_id], key=lambda item: item[0])
        # 10件未満など設定数に届かない意味ASTがあれば停止する
        if len(ranked) < per_ast:
            # 不足している意味ASTと実件数を通知する
            raise ValueError(
                f"意味ASTの言い換え元が{per_ast}件未満です: {spec_id}: {len(ranked)}"
            )
        # 固定ランダム順位の先頭から設定件数だけを採用する
        selected.extend(record for _, record in ranked[:per_ast])
    # 意味ASTごとに同数選んだ全レコードを返す
    return selected


# この工程を担当する関数を定義する
def _write_review_csv(path: Path, records: list[dict[str, Any]]) -> None:
    # 保存先ディレクトリがなければ作成する
    path.parent.mkdir(parents=True, exist_ok=True)
    # 元文と教師候補を比較するためのCSV列を定義する
    fieldnames = [
        # この処理で扱う文字列を一覧へ加える
        "instruction_id",
        # この処理で扱う文字列を一覧へ加える
        "source_instruction_id",
        # この処理で扱う文字列を一覧へ加える
        "semantic_ast",
        # この処理で扱う文字列を一覧へ加える
        "source_instruction_ja",
        # この処理で扱う文字列を一覧へ加える
        "instruction_ja",
        # この処理で扱う文字列を一覧へ加える
        "review_status",
        # この処理で扱う文字列を一覧へ加える
        "edited_instruction_ja",
        # この処理で扱う文字列を一覧へ加える
        "reviewer",
        # この処理で扱う文字列を一覧へ加える
        "reviewed_at",
    ]
    # 確認用CSVをUTF-8で新規作成する
    with path.open("w", encoding="utf-8", newline="") as handle:
        # 辞書を指定列順で書くCSV writerを作る
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        # 最初の行へ列名を書き込む
        writer.writeheader()
        # 各言い換え候補を一行ずつ書き込む
        for record in records:
            # 元文と候補を埋め、確認者入力欄は空欄で出力する
            writer.writerow(
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "instruction_id": record["instruction_id"],
                    # 出力レコードの項目と値を設定する
                    "source_instruction_id": record["source_instruction_id"],
                    # 出力レコードの項目と値を設定する
                    "semantic_ast": canonical_json(record["semantic_ast"]),
                    # 出力レコードの項目と値を設定する
                    "source_instruction_ja": record["source_instruction_ja"],
                    # 出力レコードの項目と値を設定する
                    "instruction_ja": record["instruction_ja"],
                    # 出力レコードの項目と値を設定する
                    "review_status": "",
                    # 出力レコードの項目と値を設定する
                    "edited_instruction_ja": "",
                    # 出力レコードの項目と値を設定する
                    "reviewer": "",
                    # 出力レコードの項目と値を設定する
                    "reviewed_at": "",
                }
            )


# この工程を担当する関数を定義する
def _load_json_object(path: Path) -> tuple[dict[str, Any], str]:
    # JSONファイルを文字列として読み、辞書へ解析する
    try:
        # ハッシュ記録用に元文字列を保持する
        text = path.read_text(encoding="utf-8")
        # JSON文字列をPython値へ変換する
        value = json.loads(text)
    # ファイルが存在しない場合は対象パスを示して停止する
    except FileNotFoundError as error:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"JSONファイルが見つかりません: {path}") from error
    # JSON構文が不正な場合は対象パスを示して停止する
    except json.JSONDecodeError as error:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"JSONファイルが不正です: {path}") from error
    # JSONのルートがオブジェクトであることを確認する
    if not isinstance(value, dict):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("JSONのルートはオブジェクトにしてください")
    # 解析済み辞書と元文字列を返す
    return value, text


# この工程を担当する関数を定義する
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    # 読み込んだルール生成指示を格納する配列を作る
    records: list[dict[str, Any]] = []
    # 入力JSONLをUTF-8で開く
    with path.open(encoding="utf-8") as handle:
        # エラー位置を示せるよう行番号付きで読む
        for line_number, line in enumerate(handle, start=1):
            # 空行は読み飛ばす
            if not line.strip():
                # 現在の対象を終えて次の対象へ進む
                continue
            # 一行をJSONとして解析する
            try:
                # valueへこの工程で使用する値を設定する
                value = json.loads(line)
            # JSON構文エラーへファイル名と行番号を付ける
            except json.JSONDecodeError as error:
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"JSONLが不正です: {path}:{line_number}") from error
            # 各レコードがJSONオブジェクトであることを確認する
            if not isinstance(value, dict):
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(f"JSONLレコードが不正です: {path}:{line_number}")
            # 検査済みレコードを追加する
            records.append(value)
    # 全ルール生成指示を返す
    return records


# この工程を担当する関数を定義する
def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    # 保存先ディレクトリがなければ作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 出力JSONLをUTF-8で新規作成する
    with path.open("w", encoding="utf-8") as handle:
        # 各レコードを一件ずつ書く
        for record in records:
            # 日本語を保った一行JSONへ変換して書く
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            # JSONLのレコード区切りとなる改行を書く
            handle.write("\n")


# この工程を担当する関数を定義する
def _append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """長時間生成の完了済みレコードを既存JSONLへ追記する。"""

    # 追記先ディレクトリがなければ作成する
    path.parent.mkdir(parents=True, exist_ok=True)
    # 既存内容を保持したままUTF-8でファイル末尾を開く
    with path.open("a", encoding="utf-8") as handle:
        # 今回完了した各レコードを順番に書く
        for record in records:
            # 日本語を保った一行JSONへ変換して書く
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            # JSONLのレコード区切りとなる改行を書く
            handle.write("\n")


# この工程を担当する関数を定義する
def _write_json(path: Path, value: object) -> None:
    # 保存先ディレクトリがなければ作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 集計値を人間が読める整形JSONで保存する
    path.write_text(
        # 次の値または処理を現在の構造へ組み込む
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        # encodingへこの工程で使用する値を設定する
        encoding="utf-8",
    )


# この工程を担当する関数を定義する
def _project_path(value: str) -> Path:
    # 設定文字列をPathへ変換する
    path = Path(value)
    # 相対パスだけをプロジェクトルート基準へ変換して返す
    return path if path.is_absolute() else PROJECT_ROOT / path


# この工程を担当する関数を定義する
def _required_mapping(values: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    # 指定キーの値を取得する
    value = values.get(key)
    # JSONオブジェクトに対応する辞書以外は拒否する
    if not isinstance(value, dict):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}はオブジェクトにしてください")
    # 検査済み辞書を返す
    return value


# この工程を担当する関数を定義する
def _required_string(values: Mapping[str, Any], key: str) -> str:
    # 指定キーの値を取得する
    value = values.get(key)
    # 空でない文字列以外は拒否する
    if not isinstance(value, str) or not value:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は空でない文字列にしてください")
    # 検査済み文字列を返す
    return value


# この工程を担当する関数を定義する
def _required_int(
    # 次の値または処理を現在の構造へ組み込む
    values: Mapping[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    key: str,
    # 次の値または処理を現在の構造へ組み込む
    *,
    # allow_zeroへこの工程で使用する値を設定する
    allow_zero: bool = False,
# 次の値または処理を現在の構造へ組み込む
) -> int:
    # 指定キーの値を取得する
    value = values.get(key)
    # 0を許可する設定かどうかに応じて下限を決める
    minimum = 0 if allow_zero else 1
    # boolを含まない整数で、下限以上であることを確認する
    if type(value) is not int or value < minimum:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は{minimum}以上の整数にしてください")
    # 検査済み整数を返す
    return value


# importされたときはQwenを実行せず、直接実行時だけmainを呼ぶ
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    main()
