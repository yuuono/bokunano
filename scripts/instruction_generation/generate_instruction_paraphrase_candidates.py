# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "accelerate>=1.6.0",
#   "autoawq>=0.2.9",
#   "torch>=2.6.0",
#   "transformers>=4.51.0,<5",
# ]
# ///
"""ルール生成指示の一部をQwen3で言い換える。"""

from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse
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
    QwenTeacher,
    canonical_json,
    parse_json_string_list,
    prompt_hash,
    render_prompt,
    sha256_text,
    validate_model_config,
    validate_sampling_config,
)


# 出力へ記録する全文言い換え生成器のバージョンを定義する
GENERATOR_VERSION = "1"


def parse_args() -> argparse.Namespace:
    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        description="ルール生成済み日本語指示の一部をQwen3で言い換えます。"
    )
    # 全文言い換えの生成条件を持つ設定JSONを受け取る
    parser.add_argument("--config", required=True, type=Path)
    # モデルを読み込まず設定と入力だけを確認するオプションを追加する
    parser.add_argument("--validate-config", action="store_true")
    # 既存出力を明示的に置き換えるオプションを追加する
    parser.add_argument("--overwrite", action="store_true")
    # コマンドラインを解析して返す
    return parser.parse_args()


def main() -> None:
    # コマンドライン引数を取得する
    args = parse_args()
    # 設定JSONを辞書と元文字列の両方で読み込む
    config, config_text = _load_json_object(args.config.resolve())
    # 設定値を検査し、パスを絶対パスへ変換する
    settings = _validate_config(config)
    # 24操作の正準意味と厳守事項を意味ASTから引ける形で読み込む
    definitions = _load_operation_definitions(settings["operation_definitions"])
    # ルールベース生成済みの指示レコードを読み込む
    source_records = _read_jsonl(settings["input"])
    # 全件ではなく設定割合だけを決定的に選ぶ
    selected = _select_sources(
        source_records,
        rate=settings["selection_rate"],
        maximum=settings["maximum_source_instructions"],
        seed=settings["generator_seed"],
    )

    # 設定検査だけの場合はモデルを読み込まない
    if args.validate_config:
        # 入力件数と言い換え対象件数を表示する
        print(
            f"設定は有効です: input={len(source_records)}, selected={len(selected)}"
        )
        # 教師生成へ進まず終了する
        return
    # 抽出結果が0件なら設定ミスの可能性があるため停止する
    if not selected:
        raise ValueError("言い換え対象が0件です。selection_rateまたは入力を確認してください")

    # この実行で作成する4つの出力パスをまとめる
    output_paths = [
        settings["output"],
        settings["raw_responses"],
        settings["review_csv"],
        settings["stats"],
    ]
    # すでに存在する出力パスだけを抽出する
    existing = [str(path) for path in output_paths if path.exists()]
    # 上書き指定なしで既存出力があれば誤消去を防ぐため停止する
    if existing and not args.overwrite:
        raise ValueError(
            "既存出力があります。置き換える場合は--overwriteを指定してください: "
            + ", ".join(existing)
        )

    # 全文言い換え用のsystem promptを読み込む
    system_prompt = settings["system_prompt"].read_text(encoding="utf-8").strip()
    # Qwen3モデルとtokenizerを一度だけ読み込む
    teacher = QwenTeacher(settings["model"])
    # 人間確認前の言い換え候補を格納する配列を作る
    candidates: list[dict[str, Any]] = []
    # Qwenへ渡したプロンプトと生出力を格納する配列を作る
    raw_records: list[dict[str, Any]] = []
    # JSON解析失敗などを記録する配列を作る
    failures: list[dict[str, str]] = []

    # 選ばれたルール生成指示を一件ずつ言い換える
    for index, source in enumerate(selected):
        # 元指示を一意に識別するIDを取得する
        instruction_id = _required_string(source, "instruction_id")
        # Qwenへ渡す元の日本語指示を取得する
        instruction = _required_string(source, "instruction_ja")
        # 元指示が表す意味ASTを取得する
        semantic_ast = source.get("semantic_ast")
        # 単独操作とsequence形式を同じ操作配列へ正規化する
        sequence = _normalize_sequence(semantic_ast)
        # Qwenへ示す操作の正準意味を順番に格納する配列を作る
        operation_details = []
        # Qwenが保持すべき注意事項を順番に格納する配列を作る
        preserve_details = []
        # 意味ASTの各操作を元の実行順どおりに処理する
        for position, operation in enumerate(sequence, start=1):
            # 操作の意味ASTから対応する正準定義を取得する
            definition = definitions.get(canonical_json(operation))
            # 未定義操作があれば誤った言い換えを防ぐため停止する
            if definition is None:
                raise ValueError(
                    f"操作定義にない意味ASTです: {instruction_id}: {operation!r}"
                )
            # 操作位置と正準意味をプロンプト用一覧へ追加する
            operation_details.append(
                f"{position}. {definition['canonical_meaning_ja']}"
            )
            # 操作位置と厳守事項をプロンプト用一覧へ追加する
            preserve_details.append(
                f"{position}. {definition['must_preserve_ja']}"
            )

        # AST、操作順、厳守事項、元文をuser promptへ埋め込む
        user_prompt = render_prompt(
            settings["user_prompt"],
            {
                "count": settings["paraphrases_per_instruction"],
                "semantic_ast": canonical_json(semantic_ast),
                "operation_sequence": "\n".join(operation_details),
                "must_preserve_ja": "\n".join(preserve_details),
                "source_instruction": instruction,
            },
        ).strip()
        # 実際に使用するsystem/user promptからハッシュを計算する
        current_prompt_hash = prompt_hash(system_prompt, user_prompt)
        # 対象指示ごとに異なる決定的seedを計算する
        seed = settings["generator_seed"] + index
        # このQwen呼び出しのUTC日時を記録する
        generated_at = datetime.now(timezone.utc).isoformat()
        # Qwen3を非thinkingモードで実行して言い換え候補を得る
        result = teacher.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            sampling=settings["sampling"],
            seed=seed,
        )
        # 解析成否にかかわらず保存する生出力レコードを作る
        raw_record: dict[str, Any] = {
            "source_instruction_id": instruction_id,
            "seed": seed,
            "prompt_hash": current_prompt_hash,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "raw_response": result.text,
            "generated_at": generated_at,
            "parsed_ok": False,
            "parse_error": None,
        }
        # Qwen出力をparaphrases文字列配列として解析する
        try:
            paraphrases = parse_json_string_list(result.text, "paraphrases")
        # JSON形式が不正な場合も生出力と原因を保存して次へ進む
        except ValueError as error:
            # 解析エラーを生出力レコードへ記録する
            raw_record["parse_error"] = str(error)
            # 失敗した応答も監査用に保存する
            raw_records.append(raw_record)
            # 元指示IDと失敗理由を集計へ追加する
            failures.append(
                {"source_instruction_id": instruction_id, "reason": str(error)}
            )
            # 次の元指示へ進む
            continue
        # JSON解析に成功したことを記録する
        raw_record["parsed_ok"] = True
        # 成功した生出力も保存対象へ追加する
        raw_records.append(raw_record)

        # 元文と異なる固有候補だけを格納する配列を作る
        unique_paraphrases: list[str] = []
        # Qwenが返した各言い換え候補を順番に検査する
        for paraphrase in paraphrases:
            # 元文と完全一致する候補や同一応答内の重複を除外する
            if paraphrase == instruction or paraphrase in unique_paraphrases:
                continue
            # thinkingタグまたはコードフェンスが混入した候補を除外する
            if "<think>" in paraphrase or "```" in paraphrase:
                continue
            # 形式検査を通過した言い換え候補を追加する
            unique_paraphrases.append(paraphrase)
            # 設定件数に達したら余分な候補は採用しない
            if len(unique_paraphrases) >= settings["paraphrases_per_instruction"]:
                break
        # 固有候補を一件も得られなかった場合を失敗として記録する
        if not unique_paraphrases:
            failures.append(
                {
                    "source_instruction_id": instruction_id,
                    "reason": "固有の言い換え候補を取得できませんでした",
                }
            )
            # 次の元指示へ進む
            continue

        # 形式検査を通過した各候補を人間確認用レコードへ変換する
        for paraphrase in unique_paraphrases:
            # 元指示IDと候補本文から一意な候補IDを作る
            candidate_id = "instruction-teacher-candidate-" + sha256_text(
                instruction_id + "\0" + paraphrase
            )
            # 元文、AST、モデル情報を含む候補レコードを追加する
            candidates.append(
                {
                    "instruction_id": candidate_id,
                    "source_instruction_id": instruction_id,
                    "spec_id": source.get("spec_id"),
                    "semantic_ast": semantic_ast,
                    "source_instruction_ja": instruction,
                    "instruction_ja": paraphrase,
                    "instruction_source": "teacher",
                    "dictionary": source.get("dictionary"),
                    "review_status": "pending",
                    "teacher_model": settings["model"]["model_id"],
                    "teacher_revision": result.resolved_revision,
                    "teacher_quantization": "AWQ 4-bit",
                    "teacher_library": "transformers",
                    "teacher_library_version": result.transformers_version,
                    "teacher_torch_version": result.torch_version,
                    "teacher_seed": seed,
                    "teacher_sampling": settings["sampling"],
                    "teacher_generated_at": generated_at,
                    "prompt_hash": current_prompt_hash,
                    "text_hash": sha256_text(paraphrase),
                }
            )

    # 人間確認前の言い換え候補をJSONLへ保存する
    _write_jsonl(settings["output"], candidates)
    # 実際のプロンプトとQwen生出力をJSONLへ保存する
    _write_jsonl(settings["raw_responses"], raw_records)
    # 元文と候補を横並びにした人間確認用CSVを保存する
    _write_review_csv(settings["review_csv"], candidates)
    # 実行条件、件数、失敗内容を持つ集計レコードを作る
    stats = {
        "phase": "instruction_paraphrase_candidates",
        "input_count": len(source_records),
        "selected_source_count": len(selected),
        "candidate_count": len(candidates),
        "failure_count": len(failures),
        "failures": failures,
        "selection_rate": settings["selection_rate"],
        "maximum_source_instructions": settings["maximum_source_instructions"],
        "model_id": settings["model"]["model_id"],
        "requested_revision": settings["model"]["revision"],
        "resolved_revision": teacher.resolved_revision,
        "enable_thinking": False,
        "sampling": settings["sampling"],
        "generator_version": GENERATOR_VERSION,
        "generator_seed": settings["generator_seed"],
        "config_hash": sha256_text(config_text),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    # 集計レコードを整形JSONとして保存する
    _write_json(settings["stats"], stats)
    # 対象件数、候補件数、失敗件数を表示する
    print(
        f"言い換え候補生成完了: selected={len(selected)}, "
        f"candidates={len(candidates)}, failures={len(failures)}"
    )
    # 作成者本人が次に開く確認用CSVの場所を表示する
    print(f"確認用CSV: {settings['review_csv']}")


def _validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    # 設定JSONに必要なキーを厳密に列挙する
    expected = {
        "config_version",
        "phase",
        "input",
        "operation_definitions",
        "output",
        "raw_responses",
        "review_csv",
        "stats",
        "prompts",
        "selection_rate",
        "maximum_source_instructions",
        "paraphrases_per_instruction",
        "generator_version",
        "generator_seed",
        "model",
        "sampling",
    }
    # 設定キーが過不足なく一致することを確認する
    if set(config) != expected:
        raise ValueError("言い換え生成設定の項目が不正です")
    # 対応する設定形式のバージョンを確認する
    if config["config_version"] != 1:
        raise ValueError("config_versionは1にしてください")
    # このスクリプト用の処理段階名であることを確認する
    if config["phase"] != "instruction_paraphrase_candidates":
        raise ValueError("phaseが不正です")
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

    # 元設定を壊さないよう解決済み設定用のコピーを作る
    settings = dict(config)
    # 入出力に使う各パスを順番に絶対パスへ変換する
    for key in (
        "input",
        "operation_definitions",
        "output",
        "raw_responses",
        "review_csv",
        "stats",
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
        _required_mapping(config, "sampling")
    )
    # 生成開始前から必要な入力ファイルを順番に確認する
    for key in ("input", "operation_definitions", "system_prompt", "user_prompt"):
        # 入力ファイルがなければモデルを読み込む前に停止する
        if not settings[key].is_file():
            raise ValueError(f"入力ファイルが見つかりません: {settings[key]}")
    # 全ルール生成指示から選ぶ割合を取得する
    rate = config["selection_rate"]
    # 選択割合を0より大きく1以下の数へ制限する
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 < rate <= 1:
        raise ValueError("selection_rateは0より大きく1以下にしてください")
    # 言い換える元指示数の上限を確認する
    _required_int(config, "maximum_source_instructions")
    # 一つの元指示から作る候補数を確認する
    _required_int(config, "paraphrases_per_instruction")
    # 選択と生成に使う基準seedを確認する
    _required_int(config, "generator_seed", allow_zero=True)
    # 検査とパス解決が終わった設定を返す
    return settings


def _load_operation_definitions(path: Path) -> dict[str, dict[str, str]]:
    # 24操作の日本語定義JSONを読み込む
    value, _ = _load_json_object(path)
    # 操作定義の配列を取り出す
    operations = value.get("operations")
    # 設定バージョンと配列形式を確認する
    if value.get("config_version") != 1 or not isinstance(operations, list):
        raise ValueError("操作定義が不正です")
    # 意味ASTから日本語定義を引ける辞書を作る
    result: dict[str, dict[str, str]] = {}
    # 各操作定義を順番に検査する
    for operation in operations:
        # 各操作定義がJSONオブジェクトであることを確認する
        if not isinstance(operation, dict):
            raise ValueError("操作定義の各要素はオブジェクトにしてください")
        # 意味ASTを決定的JSONにして検索キーを作る
        key = canonical_json(operation.get("semantic_ast"))
        # 正準意味と厳守事項を検索辞書へ登録する
        result[key] = {
            "canonical_meaning_ja": _required_string(
                operation, "canonical_meaning_ja"
            ),
            "must_preserve_ja": _required_string(operation, "must_preserve_ja"),
        }
    # 重複のない24操作が登録されたことを確認する
    if len(result) != 24:
        raise ValueError("操作定義には重複のない24操作が必要です")
    # 意味ASTをキーとする操作定義辞書を返す
    return result


def _normalize_sequence(semantic_ast: object) -> list[object]:
    # 意味ASTがJSONオブジェクトであることを確認する
    if not isinstance(semantic_ast, dict):
        raise ValueError("semantic_astはオブジェクトにしてください")
    # sequenceだけを持つ意味ASTは複数操作として扱う
    if set(semantic_ast) == {"sequence"}:
        # sequence配列を取得する
        sequence = semantic_ast["sequence"]
        # 課題範囲である1〜3操作の配列か確認する
        if not isinstance(sequence, list) or not 1 <= len(sequence) <= 3:
            raise ValueError("sequenceには1〜3操作が必要です")
        # 呼び出し元で変更されても元ASTを壊さないようコピーして返す
        return list(sequence)
    # 単独操作は一要素の配列へ包んで返す
    return [semantic_ast]


def _select_sources(
    records: list[dict[str, Any]],
    *,
    rate: float,
    maximum: int,
    seed: int,
) -> list[dict[str, Any]]:
    # ハッシュ順位とレコードの組を格納する配列を作る
    ranked: list[tuple[str, dict[str, Any]]] = []
    # 256-bitハッシュ空間に対する選択割合の閾値を計算する
    threshold = int(rate * (2**256 - 1))
    # 入力指示を一件ずつ決定的に選抜する
    for record in records:
        # 選択単位となる指示IDを取得する
        instruction_id = _required_string(record, "instruction_id")
        # seedと指示IDから選択用ハッシュを作る
        digest = sha256_text(f"{seed}\0{instruction_id}")
        # ハッシュ値が割合閾値以下の指示だけを候補にする
        if int(digest, 16) <= threshold:
            # 後で決定的に並べられるようハッシュとレコードを保存する
            ranked.append((digest, record))
    # 選択されたレコードをハッシュ昇順に並べる
    ranked.sort(key=lambda item: item[0])
    # 最大件数までのレコード本体だけを返す
    return [record for _, record in ranked[:maximum]]


def _write_review_csv(path: Path, records: list[dict[str, Any]]) -> None:
    # 保存先ディレクトリがなければ作成する
    path.parent.mkdir(parents=True, exist_ok=True)
    # 元文と教師候補を比較するためのCSV列を定義する
    fieldnames = [
        "instruction_id",
        "source_instruction_id",
        "semantic_ast",
        "source_instruction_ja",
        "instruction_ja",
        "review_status",
        "edited_instruction_ja",
        "reviewer",
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
                {
                    "instruction_id": record["instruction_id"],
                    "source_instruction_id": record["source_instruction_id"],
                    "semantic_ast": canonical_json(record["semantic_ast"]),
                    "source_instruction_ja": record["source_instruction_ja"],
                    "instruction_ja": record["instruction_ja"],
                    "review_status": "",
                    "edited_instruction_ja": "",
                    "reviewer": "",
                    "reviewed_at": "",
                }
            )


def _load_json_object(path: Path) -> tuple[dict[str, Any], str]:
    # JSONファイルを文字列として読み、辞書へ解析する
    try:
        # ハッシュ記録用に元文字列を保持する
        text = path.read_text(encoding="utf-8")
        # JSON文字列をPython値へ変換する
        value = json.loads(text)
    # ファイルが存在しない場合は対象パスを示して停止する
    except FileNotFoundError as error:
        raise ValueError(f"JSONファイルが見つかりません: {path}") from error
    # JSON構文が不正な場合は対象パスを示して停止する
    except json.JSONDecodeError as error:
        raise ValueError(f"JSONファイルが不正です: {path}") from error
    # JSONのルートがオブジェクトであることを確認する
    if not isinstance(value, dict):
        raise ValueError("JSONのルートはオブジェクトにしてください")
    # 解析済み辞書と元文字列を返す
    return value, text


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    # 読み込んだルール生成指示を格納する配列を作る
    records: list[dict[str, Any]] = []
    # 入力JSONLをUTF-8で開く
    with path.open(encoding="utf-8") as handle:
        # エラー位置を示せるよう行番号付きで読む
        for line_number, line in enumerate(handle, start=1):
            # 空行は読み飛ばす
            if not line.strip():
                continue
            # 一行をJSONとして解析する
            try:
                value = json.loads(line)
            # JSON構文エラーへファイル名と行番号を付ける
            except json.JSONDecodeError as error:
                raise ValueError(f"JSONLが不正です: {path}:{line_number}") from error
            # 各レコードがJSONオブジェクトであることを確認する
            if not isinstance(value, dict):
                raise ValueError(f"JSONLレコードが不正です: {path}:{line_number}")
            # 検査済みレコードを追加する
            records.append(value)
    # 全ルール生成指示を返す
    return records


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


def _write_json(path: Path, value: object) -> None:
    # 保存先ディレクトリがなければ作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 集計値を人間が読める整形JSONで保存する
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _project_path(value: str) -> Path:
    # 設定文字列をPathへ変換する
    path = Path(value)
    # 相対パスだけをプロジェクトルート基準へ変換して返す
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
        raise ValueError(f"{key}は{minimum}以上の整数にしてください")
    # 検査済み整数を返す
    return value


# importされたときはQwenを実行せず、直接実行時だけmainを呼ぶ
if __name__ == "__main__":
    main()
