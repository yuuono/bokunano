"""意味ASTとtrain表現辞書から全文の日本語指示をルール生成する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse

# 操作別・集合別・表現別の件数を数えるために使う
from collections import Counter, defaultdict

# SHA-256ハッシュを計算するために使う
import hashlib

# 設定とJSONLを読み書きするために使う
import json

# 直積の大きさと最大公約数を計算するために使う
import math

# 大きなJSONLをZIPへコピーするために使う
import shutil

# 入出力ファイルのパスを扱うために使う
from pathlib import Path

# 設定辞書とレコードの型注釈に使う
from typing import Any, BinaryIO, Mapping

# 決定的なZIPアーカイブを作るために使う
import zipfile


# このファイルから二階層上をプロジェクトルートとして取得する
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# kを入力として明示する必要がある操作IDを固定する
K_OPERATION_IDS = {
    "atomic-000003",
    "atomic-000004",
    "atomic-000005",
    "atomic-000006",
    "atomic-000007",
    "atomic-000011",
    "atomic-000012",
    "atomic-000013",
    "atomic-000022",
    "atomic-000023",
}

# ZIPメタデータを実行日時に依存させない固定日時を定義する
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


# この工程を担当する関数を定義する
def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""

    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        # 実行内容をヘルプへ表示する
        description="意味ASTとtrain表現辞書から全文の日本語指示を生成します。"
    )
    # 生成条件を持つ設定JSONを必須引数として受け取る
    parser.add_argument("--config", required=True, type=Path)
    # 入力と設定だけを検査するオプションを追加する
    parser.add_argument("--validate-config", action="store_true")
    # 既存出力を明示的に置き換えるオプションを追加する
    parser.add_argument("--overwrite", action="store_true")
    # コマンドラインを解析して返す
    return parser.parse_args()


# この工程を担当する関数を定義する
def main() -> None:
    """設定を読み、全文指示JSONL、集計JSON、ZIPを作る。"""

    # コマンドライン引数を取得する
    args = parse_args()
    # 設定JSONを読み込んで型とパスを検査する
    settings = _validate_config(_load_json(args.config.resolve()))
    # train表現だけを操作別に読み込む
    expressions_by_operation, dictionary_version = _load_train_expressions(
        settings["dictionary"]
    )
    # 5集合の意味ASTを重複検査しながら読み込む
    semantic_records = _load_semantic_records(settings["semantic_ast_inputs"])
    # すべての意味AST操作が辞書で解決できることを検査する
    _validate_semantic_operations(semantic_records, expressions_by_operation)
    # 読み込んだ意味AST総数が期待値と一致することを確認する
    if len(semantic_records) != settings["expected_ast_count"]:
        # 意図しない入力更新を件数付きで通知する
        raise ValueError(f"意味AST総数が期待値と一致しません: {len(semantic_records)}")
    # 設定検査だけの場合は生成予定件数を表示して終了する
    if args.validate_config:
        # 実際の辞書件数から生成予定件数を計算する
        expected = _count_expected_instructions(
            # 全意味ASTレコードを渡す
            semantic_records,
            # 操作別のtrain表現を渡す
            expressions_by_operation,
            # ASTごとの上限件数を渡す
            settings["maximum_instructions_per_ast"],
        )
        # 設定に固定した期待件数と一致するか確認する
        if expected != settings["expected_instruction_count"]:
            # 辞書または入力ASTの変更を通知する
            raise ValueError(f"生成予定件数が期待値と一致しません: {expected}")
        # 検査済みの入力件数と生成予定件数を表示する
        print(f"設定は有効です: asts={len(semantic_records)}, instructions={expected}")
        # ファイル生成へ進まず終了する
        return

    # この実行で作る出力パスをまとめる
    output_paths = (settings["output"], settings["stats"], settings["archive"])
    # すでに存在する出力だけを抽出する
    existing = [str(path) for path in output_paths if path.exists()]
    # 上書き指定なしで既存出力があれば停止する
    if existing and not args.overwrite:
        # 誤消去を防ぐため対象パスを列挙して通知する
        raise ValueError(
            "既存出力があります。置き換える場合は--overwriteを指定してください: "
            + ", ".join(existing)
        )

    # 出力先ディレクトリがなければ作る
    settings["output"].parent.mkdir(parents=True, exist_ok=True)
    # 集計先ディレクトリがなければ作る
    settings["stats"].parent.mkdir(parents=True, exist_ok=True)
    # アーカイブ先ディレクトリがなければ作る
    settings["archive"].parent.mkdir(parents=True, exist_ok=True)

    # 集合別の生成指示数を数える
    counts_by_source = Counter()
    # 操作数別の生成指示数を数える
    counts_by_operation_count = Counter()
    # 辞書表現ごとの使用回数を数える
    expression_usage = Counter()
    # 同一AST内の指示ID重複を検査する集合を作る
    seen_instruction_ids: set[str] = set()
    # 全指示本文の完全重複を検査する集合を作る
    seen_instruction_texts: set[str] = set()
    # JSONL全体のSHA-256を逐次計算する
    output_hasher = hashlib.sha256()
    # 生成した指示の総数を初期化する
    instruction_count = 0

    # 大きな出力をメモリへ保持せず一行ずつ保存する
    with settings["output"].open("w", encoding="utf-8") as handle:
        # 5集合の意味ASTを設定順・入力順に処理する
        for source in semantic_records:
            # 現在ASTに対応する指示レコード群を決定的に生成する
            records = _generate_for_ast(
                # 意味ASTレコードを渡す
                source,
                # 操作別のtrain表現を渡す
                expressions_by_operation,
                # 辞書バージョンを渡す
                dictionary_version,
                # 検査済み設定を渡す
                settings,
            )
            # 現在ASTから得た各指示を保存する
            for record in records:
                # 指示IDを取得する
                instruction_id = record["instruction_id"]
                # 同じ指示IDが二度生成された場合は停止する
                if instruction_id in seen_instruction_ids:
                    # 衝突したIDを通知する
                    raise ValueError(
                        f"instruction_idが重複しています: {instruction_id}"
                    )
                # 新しい指示IDを確認済み集合へ追加する
                seen_instruction_ids.add(instruction_id)
                # 指示本文を取得する
                instruction_text = record["instruction_ja"]
                # 異なるレコード間で本文が完全一致した場合は停止する
                if instruction_text in seen_instruction_texts:
                    # 意味追跡が曖昧になる本文を通知する
                    raise ValueError(f"指示本文が重複しています: {instruction_text}")
                # 新しい指示本文を確認済み集合へ追加する
                seen_instruction_texts.add(instruction_text)
                # 一行JSONへ変換する
                line = (
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
                # JSONLへ一行を書き込む
                handle.write(line)
                # 同じUTF-8バイト列を出力ハッシュへ加える
                output_hasher.update(line.encode("utf-8"))
                # 集合別件数を更新する
                counts_by_source[source["source_name"]] += 1
                # 操作数別件数を更新する
                counts_by_operation_count[len(record["expression_ids"])] += 1
                # 使用した各表現IDの回数を更新する
                expression_usage.update(record["expression_ids"])
                # 総生成件数を1増やす
                instruction_count += 1

    # 実生成件数が設定の期待値と一致することを確認する
    if instruction_count != settings["expected_instruction_count"]:
        # 不完全な生成を件数付きで通知する
        raise ValueError(f"生成件数が期待値と一致しません: {instruction_count}")
    # 522件のtrain表現が少なくとも一度は使われたことを確認する
    train_expression_ids = {
        # 各表現の一意IDを集合へ入れる
        expression["expression_id"]
        # 全操作の表現配列を順番に処理する
        for expressions in expressions_by_operation.values()
        # 各操作内の表現を順番に処理する
        for expression in expressions
    }
    # 一度も使われなかったtrain表現IDを抽出する
    unused_train_ids = sorted(train_expression_ids - set(expression_usage))
    # 未使用のtrain表現があれば停止する
    if unused_train_ids:
        # 最初の未使用IDを通知する
        raise ValueError(f"未使用のtrain表現があります: {unused_train_ids[0]}")

    # JSONL内容のSHA-256を16進文字列で確定する
    output_sha256 = output_hasher.hexdigest()
    # 操作ごとの表現使用回数の偏りを集計する
    usage_by_operation = _summarize_expression_usage(
        expressions_by_operation, expression_usage
    )
    # 実行結果を確認できる集計オブジェクトを作る
    stats = {
        # 生成器の版を保存する
        "generator_version": settings["generator_version"],
        # 決定的選択に使ったseedを保存する
        "generator_seed": settings["generator_seed"],
        # 入力辞書の内容ハッシュを保存する
        "dictionary_version": dictionary_version,
        # 入力した意味ASTの総数を保存する
        "semantic_ast_count": len(semantic_records),
        # 生成した指示の総数を保存する
        "instruction_count": instruction_count,
        # ASTごとの生成上限を保存する
        "maximum_instructions_per_ast": settings["maximum_instructions_per_ast"],
        # 集合別の生成件数を保存する
        "counts_by_source": dict(sorted(counts_by_source.items())),
        # 操作数別の生成件数を保存する
        "counts_by_operation_count": {
            # 数値キーをJSON用文字列へ変換する
            str(key): value
            # 操作数順に件数を処理する
            for key, value in sorted(counts_by_operation_count.items())
        },
        # 全train表現が使われた件数を保存する
        "used_train_expression_count": len(expression_usage),
        # 操作別の使用回数分布を保存する
        "expression_usage_by_operation": usage_by_operation,
        # 生JSONLの再現性確認用ハッシュを保存する
        "output_sha256": output_sha256,
        # 生JSONLのバイト数を保存する
        "output_bytes": settings["output"].stat().st_size,
        # ZIP内で使用するパスを保存する
        "archive_member": settings["archive_member"],
    }
    # 集計JSONを可読形式で保存する
    _write_json(settings["stats"], stats)
    # 固定メタデータを使って生JSONLをZIPへ圧縮する
    _write_deterministic_zip(
        # 生JSONLのパスを渡す
        settings["output"],
        # ZIPの出力パスを渡す
        settings["archive"],
        # ZIP内の相対パスを渡す
        settings["archive_member"],
    )
    # 完了件数と出力先を表示する
    print(
        f"ルール生成指示を作成しました: asts={len(semantic_records)}, "
        f"instructions={instruction_count}"
    )
    # 再現性確認用の出力ハッシュを表示する
    print(f"output_sha256={output_sha256}")
    # 作成したZIPのパスとサイズを表示する
    print(f"archive={settings['archive']} bytes={settings['archive'].stat().st_size}")


# この工程を担当する関数を定義する
def _validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """設定のキー、型、パス、テンプレートを検査する。"""

    # 設定JSONに必要なキーを厳密に列挙する
    expected = {
        "config_version",
        "phase",
        "dictionary",
        "semantic_ast_inputs",
        "output",
        "stats",
        "archive",
        "archive_member",
        "maximum_instructions_per_ast",
        "expected_ast_count",
        "expected_instruction_count",
        "generator_version",
        "generator_seed",
        "sentence_templates",
    }
    # 設定キーに過不足があれば停止する
    if set(config) != expected:
        # 設定形式の取り違えとして通知する
        raise ValueError("ルール指示生成設定の項目が不正です")
    # 対応する設定形式の版を確認する
    if config["config_version"] != 1:
        # 未対応の設定版を拒否する
        raise ValueError("config_versionは1にしてください")
    # 工程名が想定値と一致することを確認する
    if config["phase"] != "rule_generated_instructions":
        # 別工程の設定ファイルを拒否する
        raise ValueError("phaseはrule_generated_instructionsにしてください")
    # 元の設定を壊さないようコピーする
    settings = dict(config)
    # 単独の入出力パスをプロジェクトルート基準へ変換する
    for key in ("dictionary", "output", "stats", "archive"):
        # 空でない文字列をPathへ変換する
        settings[key] = _project_path(_required_string(config, key))
    # 承認済み辞書が存在することを確認する
    if not settings["dictionary"].is_file():
        # 先に辞書分割を実行するよう対象パスを通知する
        raise ValueError(f"承認済み辞書が見つかりません: {settings['dictionary']}")
    # 意味AST入力の配列を取得する
    semantic_inputs = config["semantic_ast_inputs"]
    # 空でない配列であることを確認する
    if not isinstance(semantic_inputs, list) or not semantic_inputs:
        # 入力集合がない設定を拒否する
        raise ValueError("semantic_ast_inputsは空でない配列にしてください")
    # 検査済みの意味AST入力設定を格納する
    resolved_inputs: list[dict[str, Any]] = []
    # 各入力集合を順番に検査する
    for index, item in enumerate(semantic_inputs):
        # 各項目が3キーだけを持つオブジェクトか確認する
        if not isinstance(item, dict) or set(item) != {
            "name",
            "path",
            "expected_count",
        }:
            # 不正な配列位置を通知する
            raise ValueError(f"semantic_ast_inputs[{index}]が不正です")
        # 集合名を空でない文字列として取得する
        name = _required_string(item, "name")
        # 入力パスをプロジェクトルート基準へ解決する
        path = _project_path(_required_string(item, "path"))
        # 入力ファイルが存在することを確認する
        if not path.is_file():
            # 不足している入力パスを通知する
            raise ValueError(f"意味AST入力が見つかりません: {path}")
        # 期待件数を0以上の整数として取得する
        expected_count = _required_nonnegative_int(item, "expected_count")
        # 解決済み入力設定を追加する
        resolved_inputs.append(
            {"name": name, "path": path, "expected_count": expected_count}
        )
    # 集合名の重複を拒否する
    if len({item["name"] for item in resolved_inputs}) != len(resolved_inputs):
        # 重複した設定を通知する
        raise ValueError("semantic_ast_inputsのnameが重複しています")
    # 解決済み入力配列を設定へ戻す
    settings["semantic_ast_inputs"] = resolved_inputs
    # 件数とseedを整数として順番に検査する
    for key in (
        "maximum_instructions_per_ast",
        "expected_ast_count",
        "expected_instruction_count",
        "generator_seed",
    ):
        # 0以上の整数を取得する
        settings[key] = _required_nonnegative_int(config, key)
    # ASTごとの生成上限が1以上であることを確認する
    if settings["maximum_instructions_per_ast"] < 1:
        # 生成不能な上限を拒否する
        raise ValueError("maximum_instructions_per_astは1以上にしてください")
    # 生成器の版を空でない文字列として取得する
    settings["generator_version"] = _required_string(config, "generator_version")
    # ZIP内パスを空でない相対パスとして取得する
    settings["archive_member"] = _required_string(config, "archive_member")
    # ZIP内パスが絶対パスなら拒否する
    if Path(settings["archive_member"]).is_absolute():
        # 安全でないアーカイブメンバー名を通知する
        raise ValueError("archive_memberは相対パスにしてください")
    # 外側文テンプレートを検査する
    settings["sentence_templates"] = _validate_sentence_templates(
        config["sentence_templates"]
    )
    # 検査済み設定を返す
    return settings


# この工程を担当する関数を定義する
def _validate_sentence_templates(value: Any) -> dict[str, dict[str, str]]:
    """k有無の外側文テンプレートを検査する。"""

    # k有無の二種類だけがあることを確認する
    if not isinstance(value, dict) or set(value) != {"without_k", "with_k"}:
        # 不正なテンプレート区分を拒否する
        raise ValueError("sentence_templatesはwithout_kとwith_kを指定してください")
    # 検査済みテンプレートを格納する
    templates: dict[str, dict[str, str]] = {}
    # 二つのテンプレート区分を順番に処理する
    for key in ("without_k", "with_k"):
        # 現在区分の設定を取得する
        item = value[key]
        # IDと本文だけを持つオブジェクトか確認する
        if not isinstance(item, dict) or set(item) != {"template_id", "text"}:
            # 不正な区分名を通知する
            raise ValueError(f"sentence_templates.{key}が不正です")
        # テンプレートIDを取得する
        template_id = _required_string(item, "template_id")
        # テンプレート本文を取得する
        text = _required_string(item, "text")
        # 操作本文の置換位置が一つだけあることを確認する
        if text.count("{operations}") != 1:
            # 誤った外側文を拒否する
            raise ValueError(f"sentence_templates.{key}.textに{{operations}}が必要です")
        # 検査済みのIDと本文を保存する
        templates[key] = {"template_id": template_id, "text": text}
    # 二つのテンプレートIDが異なることを確認する
    if templates["without_k"]["template_id"] == templates["with_k"]["template_id"]:
        # 追跡不能な重複IDを拒否する
        raise ValueError("sentence template IDは重複させないでください")
    # 検査済みテンプレートを返す
    return templates


# この工程を担当する関数を定義する
def _load_train_expressions(
    path: Path,
) -> tuple[dict[str, list[dict[str, Any]]], str]:
    """承認済み辞書からtrain表現だけを操作別に読む。"""

    # 操作別のtrain表現を格納する
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    # 辞書バージョンの一意値を集める
    dictionary_versions: set[str] = set()
    # 全表現IDの重複を検査する
    seen_ids: set[str] = set()
    # 承認済み辞書を一件ずつ処理する
    for line_number, record in enumerate(_read_jsonl(path), start=1):
        # 表現IDを取得する
        expression_id = _required_string(record, "expression_id")
        # 表現IDの重複を拒否する
        if expression_id in seen_ids:
            # 重複した行を通知する
            raise ValueError(f"辞書のexpression_idが重複しています: 行{line_number}")
        # 新しい表現IDを確認済み集合へ追加する
        seen_ids.add(expression_id)
        # 辞書バージョンを集合へ追加する
        dictionary_versions.add(_required_string(record, "dictionary_version"))
        # test_only表現はルール生成対象から完全に除外する
        if record.get("dictionary") == "test_only":
            # 次の辞書レコードへ進む
            continue
        # train以外の未知区分を拒否する
        if record.get("dictionary") != "train":
            # 不正な区分と行を通知する
            raise ValueError(f"辞書区分が不正です: 行{line_number}")
        # 操作IDを取得する
        operation_id = _required_string(record, "operation_id")
        # 生成に必要な項目だけを操作別配列へ追加する
        grouped[operation_id].append(
            {
                "expression_id": expression_id,
                "operation_id": operation_id,
                "operation_ast": record.get("operation_ast"),
                "expression_ja": _required_string(record, "expression_ja"),
                "connective_expression_ja": _required_string(
                    record, "connective_expression_ja"
                ),
            }
        )
    # 全レコードで辞書バージョンが一つに揃っていることを確認する
    if len(dictionary_versions) != 1:
        # 入力辞書の混在を通知する
        raise ValueError("dictionary_versionが一つに揃っていません")
    # 24操作すべてにtrain表現があることを確認する
    if set(grouped) != {f"atomic-{index:06d}" for index in range(1, 25)}:
        # 不足または未知の操作を通知する
        raise ValueError("train表現辞書が24操作を覆っていません")
    # 操作内の表現順をID昇順へ固定する
    for expressions in grouped.values():
        # expression_idの辞書順で整列する
        expressions.sort(key=lambda record: record["expression_id"])
    # 操作別表現と唯一の辞書バージョンを返す
    return dict(grouped), dictionary_versions.pop()


# この工程を担当する関数を定義する
def _load_semantic_records(
    input_settings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """設定順に意味AST集合を読み、集合間重複を検査する。"""

    # 全集合の意味ASTレコードを格納する
    records: list[dict[str, Any]] = []
    # 全集合でspec_idの重複を検査する
    seen_spec_ids: set[str] = set()
    # 全集合で意味ASTの重複を検査する
    seen_semantic_asts: set[str] = set()
    # 設定した入力集合を順番に処理する
    for input_setting in input_settings:
        # 現在ファイルのJSONLレコードを読む
        source_records = _read_jsonl(input_setting["path"])
        # 実件数が設定値と一致することを確認する
        if len(source_records) != input_setting["expected_count"]:
            # 集合名と実件数を通知する
            raise ValueError(
                f"{input_setting['name']}の意味AST件数が期待値と一致しません: "
                f"{len(source_records)}"
            )
        # 現在集合の各意味ASTを入力順に処理する
        for record in source_records:
            # 意味ASTを識別するspec_idを取得する
            spec_id = _required_string(record, "spec_id")
            # 意味AST本体を取得する
            semantic_ast = record.get("semantic_ast")
            # 意味ASTがオブジェクトであることを確認する
            if not isinstance(semantic_ast, dict):
                # 不正なspec_idを通知する
                raise ValueError(f"semantic_astが不正です: {spec_id}")
            # 意味ASTを比較可能な正規JSONへ変換する
            semantic_key = _canonical_json(semantic_ast)
            # spec_idが集合間で重複していないことを確認する
            if spec_id in seen_spec_ids:
                # 重複IDを通知する
                raise ValueError(f"spec_idが集合間で重複しています: {spec_id}")
            # 意味ASTが集合間で重複していないことを確認する
            if semantic_key in seen_semantic_asts:
                # 重複した意味ASTを通知する
                raise ValueError(f"意味ASTが集合間で重複しています: {spec_id}")
            # 新しいspec_idを確認済み集合へ追加する
            seen_spec_ids.add(spec_id)
            # 新しい意味ASTを確認済み集合へ追加する
            seen_semantic_asts.add(semantic_key)
            # 元レコードを壊さず生成用メタデータを追加する
            enriched = dict(record)
            # 入力集合名を保存する
            enriched["source_name"] = input_setting["name"]
            # split省略の評価集合にはtestを補う
            enriched["resolved_split"] = record.get("split") or "test"
            # 生成対象配列へ追加する
            records.append(enriched)
    # 設定順・入力順の全レコードを返す
    return records


# この工程を担当する関数を定義する
def _validate_semantic_operations(
    records: list[dict[str, Any]],
    expressions_by_operation: Mapping[str, list[dict[str, Any]]],
) -> None:
    """全AST操作が辞書内の操作ASTと一意に対応するか確認する。"""

    # 操作ASTから操作IDを逆引きする辞書を作る
    operation_id_by_ast: dict[str, str] = {}
    # 24操作の各表現群を処理する
    for operation_id, expressions in expressions_by_operation.items():
        # 同じ操作内の全表現が同じ操作ASTを持つことを確認する
        ast_keys = {_canonical_json(item["operation_ast"]) for item in expressions}
        # 操作ASTが一つに揃っていなければ停止する
        if len(ast_keys) != 1:
            # 不整合のある操作IDを通知する
            raise ValueError(f"辞書内のoperation_astが一致しません: {operation_id}")
        # 唯一の操作ASTを取得する
        ast_key = ast_keys.pop()
        # 異なる操作IDが同じ操作ASTを持つ場合は停止する
        if ast_key in operation_id_by_ast:
            # 曖昧な操作ASTを通知する
            raise ValueError(f"辞書内のoperation_astが重複しています: {ast_key}")
        # 操作ASTから操作IDへの対応を保存する
        operation_id_by_ast[ast_key] = operation_id
    # 全意味ASTレコードを処理する
    for record in records:
        # 操作列を正規化して取得する
        sequence = _normalize_sequence(record["semantic_ast"])
        # 各操作を順番に確認する
        for operation in sequence:
            # 辞書で解決できない操作を拒否する
            if _canonical_json(operation) not in operation_id_by_ast:
                # 対象spec_idと操作を通知する
                raise ValueError(
                    f"辞書にない操作です: {record['spec_id']}: {operation!r}"
                )


# この工程を担当する関数を定義する
def _generate_for_ast(
    source: Mapping[str, Any],
    expressions_by_operation: Mapping[str, list[dict[str, Any]]],
    dictionary_version: str,
    settings: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """一つの意味ASTから上限まで固有の全文指示を生成する。"""

    # 意味AST本体を取得する
    semantic_ast = source["semantic_ast"]
    # 意味ASTの操作列を元の順序で取得する
    sequence = _normalize_sequence(semantic_ast)
    # 操作ASTから操作IDを引く対応表を作る
    operation_id_by_ast = {
        # 各操作の先頭表現が持つ操作ASTをキーにする
        _canonical_json(expressions[0]["operation_ast"]): operation_id
        # 操作別表現辞書を処理する
        for operation_id, expressions in expressions_by_operation.items()
    }
    # 操作列を操作ID列へ変換する
    operation_ids = [
        # 現在操作の正規JSONから操作IDを得る
        operation_id_by_ast[_canonical_json(operation)]
        # 意味ASTの操作を順番に処理する
        for operation in sequence
    ]
    # 各操作位置で使用できる表現配列を取得する
    expression_options = [
        # 現在操作IDに対応するtrain表現配列を取得する
        expressions_by_operation[operation_id]
        # 操作ID列を順番に処理する
        for operation_id in operation_ids
    ]
    # 各位置の候補数を直積の基数として取得する
    radices = [len(options) for options in expression_options]
    # 使用可能な表現組合せの総数を計算する
    combination_count = math.prod(radices)
    # 各位置で実際に使う形の固有文字列数を取得する
    unique_phrase_counts = [
        # 最終位置は終止形、それ以外は接続形の種類数を数える
        len(
            {
                expression[
                    "expression_ja"
                    if position == len(expression_options) - 1
                    else "connective_expression_ja"
                ]
                for expression in options
            }
        )
        # 各操作位置の候補配列を順番に処理する
        for position, options in enumerate(expression_options)
    ]
    # ASTごとの上限と固有全文組合せ数の小さい方を生成件数にする
    target_count = min(
        settings["maximum_instructions_per_ast"], math.prod(unique_phrase_counts)
    )
    # 固定seed、spec_id、意味ASTから直積巡回の開始位置と歩幅を得る
    offset, step = _affine_permutation_parameters(
        # 生成器seedを渡す
        settings["generator_seed"],
        # 意味ASTの一意IDを渡す
        source["spec_id"],
        # 正規化した意味ASTを渡す
        _canonical_json(semantic_ast),
        # 直積の総数を渡す
        combination_count,
    )
    # kを使う操作が一つでもあるか確認する
    requires_k = any(operation_id in K_OPERATION_IDS for operation_id in operation_ids)
    # k有無に対応する外側文テンプレートを選ぶ
    template = settings["sentence_templates"]["with_k" if requires_k else "without_k"]
    # 現在ASTから生成する指示レコードを格納する
    records: list[dict[str, Any]] = []
    # 現在AST内の全文重複を検査する集合を作る
    seen_texts: set[str] = set()
    # 表現IDの直積を重複しない順序で巡回する
    for candidate_index in range(combination_count):
        # アフィン置換で重複しない直積インデックスを得る
        linear_index = (offset + candidate_index * step) % combination_count
        # 一次元インデックスを各操作位置の候補番号へ分解する
        option_indices = _decode_mixed_radix(linear_index, radices)
        # 各位置で選ばれた表現レコードを取得する
        selected = [
            # 現在位置の候補番号に対応する表現を取得する
            options[index]
            # 表現配列と候補番号を位置ごとに組み合わせる
            for options, index in zip(expression_options, option_indices, strict=True)
        ]
        # 最後以外は接続形、最後は終止形を使う操作句配列を作る
        operation_phrases = [
            # 最終位置だけ終止形を使い、それ以外は接続形を使う
            expression[
                "expression_ja"
                if position == len(selected) - 1
                else "connective_expression_ja"
            ]
            # 選定表現を位置付きで処理する
            for position, expression in enumerate(selected)
        ]
        # 操作句を読点で元の操作順に結合する
        operations_text = "、".join(operation_phrases)
        # 外側文テンプレートへ操作句を埋め込む
        instruction = template["text"].format(operations=operations_text)
        # 同じAST内で全文が重複する表現ID組は採用しない
        if instruction in seen_texts:
            # 次の表現ID組へ進む
            continue
        # 新しい全文を現在ASTの確認済み集合へ追加する
        seen_texts.add(instruction)
        # 使用した表現IDを意味AST順に取り出す
        expression_ids = [expression["expression_id"] for expression in selected]
        # ID計算用の安定した入力文字列を作る
        id_source = "\0".join(
            [
                source["spec_id"],
                template["template_id"],
                *expression_ids,
            ]
        )
        # 意味ASTと表現組を一意に識別する指示IDを作る
        instruction_id = "instruction-rule-" + _sha256_text(id_source)
        # 全文指示レコードを追加する
        records.append(
            {
                "instruction_id": instruction_id,
                "spec_id": source["spec_id"],
                "semantic_ast": semantic_ast,
                "split": source["resolved_split"],
                "test_suite": source.get("test_suite"),
                "instruction_ja": instruction,
                "instruction_source": "rule",
                "dictionary": "train",
                "dictionary_version": dictionary_version,
                "expression_ids": expression_ids,
                "sentence_template_id": template["template_id"],
                "generator_version": settings["generator_version"],
                "generator_seed": settings["generator_seed"],
                "teacher_model": None,
                "teacher_revision": None,
                "prompt_hash": None,
                "text_hash": _sha256_text(instruction),
            }
        )
        # 固有全文が目標件数へ達したら直積巡回を終了する
        if len(records) >= target_count:
            # 現在ASTの生成を終了する
            break
    # 固有全文を計算した目標件数まで得られたことを確認する
    if len(records) != target_count:
        # 辞書内の形式重複または生成処理の不整合を通知する
        raise ValueError(
            f"固有指示数が目標へ届きません: {source['spec_id']}: "
            f"{len(records)}/{target_count}"
        )
    # 現在ASTの固有指示レコードを返す
    return records


# この工程を担当する関数を定義する
def _affine_permutation_parameters(
    seed: int, spec_id: str, semantic_key: str, size: int
) -> tuple[int, int]:
    """直積全体を一巡する開始位置と歩幅を決定的に返す。"""

    # seed、ID、意味ASTを区切り付き文字列へまとめる
    source = f"{seed}\0{spec_id}\0{semantic_key}".encode("utf-8")
    # 選択パラメータ用のSHA-256を計算する
    digest = hashlib.sha256(source).digest()
    # 前半8バイトから開始位置を得る
    offset = int.from_bytes(digest[:8], "big") % size
    # 後半8バイトから1以上の歩幅候補を得る
    step = int.from_bytes(digest[8:16], "big") % size or 1
    # 直積サイズと互いに素になるまで歩幅を増やす
    while math.gcd(step, size) != 1:
        # サイズ内で次の1以上の値へ進める
        step = step % size + 1
    # 重複せず全直積を巡回できる開始位置と歩幅を返す
    return offset, step


# この工程を担当する関数を定義する
def _decode_mixed_radix(index: int, radices: list[int]) -> list[int]:
    """直積の一次元インデックスを位置ごとの候補番号へ分解する。"""

    # 各位置の候補番号を0で初期化する
    digits = [0] * len(radices)
    # 末尾位置から基数ごとに剰余を取り出す
    for position in range(len(radices) - 1, -1, -1):
        # 現在位置の候補番号を剰余として保存する
        digits[position] = index % radices[position]
        # 次の上位位置へ進むため商へ更新する
        index //= radices[position]
    # 意味AST順の候補番号を返す
    return digits


# この工程を担当する関数を定義する
def _count_expected_instructions(
    records: list[dict[str, Any]],
    expressions_by_operation: Mapping[str, list[dict[str, Any]]],
    maximum: int,
) -> int:
    """全意味ASTから生成する指示件数を計算する。"""

    # 操作ASTからtrain表現配列を引く対応表を作る
    expressions_by_ast = {
        # 各操作の先頭表現が持つ操作ASTをキーにする
        _canonical_json(expressions[0]["operation_ast"]): expressions
        # 操作別表現辞書を処理する
        for expressions in expressions_by_operation.values()
    }
    # 全ASTの生成可能件数を合計して返す
    return sum(
        # AST上限と表現直積数の小さい方を足す
        min(
            maximum,
            math.prod(
                # 現在位置で使う形の固有文字列数を数える
                len(
                    {
                        expression[
                            "expression_ja"
                            if position == len(sequence) - 1
                            else "connective_expression_ja"
                        ]
                        for expression in expressions_by_ast[_canonical_json(operation)]
                    }
                )
                # 操作列を位置付きで処理する
                for position, operation in enumerate(sequence)
            ),
        )
        # 全意味ASTレコードを処理する
        for record in records
        # 現在レコードの操作列を一度だけ取得する
        for sequence in [_normalize_sequence(record["semantic_ast"])]
    )


# この工程を担当する関数を定義する
def _summarize_expression_usage(
    expressions_by_operation: Mapping[str, list[dict[str, Any]]],
    usage: Counter[str],
) -> dict[str, dict[str, float | int]]:
    """操作ごとのtrain表現使用回数の最小・最大・平均を返す。"""

    # 操作別集計を格納する
    summary: dict[str, dict[str, float | int]] = {}
    # 操作ID順に表現群を処理する
    for operation_id, expressions in sorted(expressions_by_operation.items()):
        # 現在操作の各表現使用回数を取得する
        counts = [usage[expression["expression_id"]] for expression in expressions]
        # 最小・最大・平均と表現数を保存する
        summary[operation_id] = {
            "expression_count": len(counts),
            "minimum_usage": min(counts),
            "maximum_usage": max(counts),
            "mean_usage": sum(counts) / len(counts),
        }
    # 操作別集計を返す
    return summary


# この工程を担当する関数を定義する
def _write_deterministic_zip(source: Path, archive_path: Path, member: str) -> None:
    """固定メタデータと圧縮設定で単一JSONLのZIPを作る。"""

    # ZIP内ファイルの固定メタデータを作る
    info = zipfile.ZipInfo(member, date_time=ZIP_TIMESTAMP)
    # Unix上の通常ファイル権限644を固定する
    info.external_attr = 0o100644 << 16
    # deflate圧縮を指定する
    info.compress_type = zipfile.ZIP_DEFLATED
    # UTF-8ファイル名フラグを有効にする
    info.flag_bits |= 0x800
    # 既存ZIPを置き換えて新規作成する
    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        # 生JSONLをバイナリで開く
        with source.open("rb") as source_handle:
            # ZIPメンバーを書き込み用に開く
            with archive.open(info, "w", force_zip64=True) as archive_handle:
                # 大きなファイルを1 MiBずつコピーする
                _copy_binary(source_handle, archive_handle)


# この工程を担当する関数を定義する
def _copy_binary(source: BinaryIO, destination: BinaryIO) -> None:
    """バイナリストリームを固定バッファサイズでコピーする。"""

    # 1 MiBのバッファで末尾までコピーする
    shutil.copyfileobj(source, destination, length=1024 * 1024)


# この工程を担当する関数を定義する
def _normalize_sequence(semantic_ast: Any) -> list[dict[str, Any]]:
    """意味ASTから1〜3操作の配列を取得する。"""

    # 意味ASTがオブジェクトであることを確認する
    if not isinstance(semantic_ast, dict):
        # 不正な意味ASTを拒否する
        raise ValueError("semantic_astはオブジェクトにしてください")
    # sequence形式の場合はその値を取得する
    sequence = semantic_ast.get("sequence")
    # 1〜3件の配列であることを確認する
    if not isinstance(sequence, list) or not 1 <= len(sequence) <= 3:
        # 対象外の操作数を拒否する
        raise ValueError("semantic_ast.sequenceは1〜3操作にしてください")
    # 全操作がオブジェクトであることを確認する
    if any(not isinstance(operation, dict) for operation in sequence):
        # 不正な操作要素を拒否する
        raise ValueError("semantic_ast.sequenceの各操作はオブジェクトにしてください")
    # 型検査済みの操作列を返す
    return sequence


# この工程を担当する関数を定義する
def _load_json(path: Path) -> dict[str, Any]:
    """JSONオブジェクトを読み込む。"""

    # UTF-8テキストをJSONとして解析する
    value = json.loads(path.read_text(encoding="utf-8"))
    # ルートがオブジェクトであることを確認する
    if not isinstance(value, dict):
        # 配列などの誤った設定形式を拒否する
        raise ValueError("設定JSONのルートはオブジェクトにしてください")
    # 型検査済みの設定を返す
    return value


# この工程を担当する関数を定義する
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """JSONLをオブジェクト配列として読む。"""

    # 読み込んだレコードを格納する
    records: list[dict[str, Any]] = []
    # 対象JSONLをUTF-8で開く
    with path.open(encoding="utf-8") as handle:
        # エラー位置を示せるよう行番号付きで読む
        for line_number, line in enumerate(handle, start=1):
            # 空行は無視する
            if not line.strip():
                # 次の行へ進む
                continue
            # 一行をJSONとして解析する
            value = json.loads(line)
            # 各行がオブジェクトであることを確認する
            if not isinstance(value, dict):
                # 不正な行番号を通知する
                raise ValueError(f"JSONLレコードが不正です: {path}:{line_number}")
            # 検査済みレコードを追加する
            records.append(value)
    # 全レコードを返す
    return records


# この工程を担当する関数を定義する
def _write_json(path: Path, value: object) -> None:
    """集計値を可読なJSONで保存する。"""

    # 日本語を保持した整形JSONを末尾改行付きで保存する
    path.write_text(
        # 2空白インデントでJSONへ変換する
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        # UTF-8で保存する
        encoding="utf-8",
    )


# この工程を担当する関数を定義する
def _canonical_json(value: Any) -> str:
    """ハッシュと比較用の正規JSON文字列を返す。"""

    # キー順と区切りを固定し、日本語をそのまま保持する
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# この工程を担当する関数を定義する
def _sha256_text(value: str) -> str:
    """文字列のSHA-256を16進文字列で返す。"""

    # UTF-8バイト列のSHA-256を計算して返す
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# この工程を担当する関数を定義する
def _project_path(value: str) -> Path:
    """相対パスをプロジェクトルート基準へ変換する。"""

    # 設定文字列をPathへ変換する
    path = Path(value)
    # 絶対パスはそのまま、相対パスはプロジェクトルートへ結合する
    return path if path.is_absolute() else PROJECT_ROOT / path


# この工程を担当する関数を定義する
def _required_string(record: Mapping[str, Any], key: str) -> str:
    """必須の空でない文字列を取得する。"""

    # 指定キーの値を取得する
    value = record.get(key)
    # 空でない文字列か確認する
    if not isinstance(value, str) or not value:
        # 不正な項目名を通知する
        raise ValueError(f"{key}は空でない文字列にしてください")
    # 検査済み文字列を返す
    return value


# この工程を担当する関数を定義する
def _required_nonnegative_int(record: Mapping[str, Any], key: str) -> int:
    """必須の0以上の整数を取得する。"""

    # 指定キーの値を取得する
    value = record.get(key)
    # boolを除く0以上の整数か確認する
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        # 不正な項目名を通知する
        raise ValueError(f"{key}は0以上の整数にしてください")
    # 検査済み整数を返す
    return value


# 直接実行された場合だけ主処理を呼び出す
if __name__ == "__main__":
    # 全文指示生成を開始する
    main()
