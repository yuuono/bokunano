"""採用したテスト専用表現から単独操作の言い換え評価指示を生成する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse

# 操作別の生成件数を数えるために使う
from collections import Counter

# SHA-256ハッシュを計算するために使う
import hashlib

# 設定とJSONLを読み書きするために使う
import json

# 入出力ファイルのパスを扱うために使う
from pathlib import Path

# 大きなJSONLをZIPへコピーするために使う
import shutil

# 設定辞書とレコードの型注釈に使う
from typing import Any, Mapping

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
        description="採用したテスト専用表現から1操作1文の評価指示を生成します。"
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
    """設定と入力を検査し、1操作1文のJSONL、集計、ZIPを作る。"""

    # コマンドライン引数を取得する
    args = parse_args()
    # 設定JSONを読み込んで型とパスを検査する
    settings = _validate_config(
        # UTF-8の設定ファイルをJSONとして解析する
        json.loads(args.config.resolve().read_text(encoding="utf-8"))
    )
    # 承認済み辞書の採用分と辞書外9件を読み込む
    expressions, approved_dictionary_version = _load_test_expressions(settings)
    # 24個の単独操作ASTを訓練分割から読み込む
    single_asts = _load_single_operation_asts(settings["single_operation_asts"])
    # 採用表現を1操作1文へ変換する
    records, paraphrase_dictionary_version = _build_records(
        # テスト専用表現を渡す
        expressions,
        # 単独操作ASTを渡す
        single_asts,
        # 承認済み辞書の版を渡す
        approved_dictionary_version,
        # 検査済み設定を渡す
        settings,
    )
    # 入力検査だけの場合は件数を表示して終了する
    if args.validate_config:
        # 検査済みの表現数、操作数、指示数を表示する
        print(
            f"設定は有効です: expressions={len(expressions)}, "
            f"operations={len(single_asts)}, instructions={len(records)}"
        )
        # ファイル生成へ進まず終了する
        return

    # この実行で作る三つの出力パスをまとめる
    output_paths = (
        # 生JSONLの出力先を含める
        settings["output"],
        # 集計JSONの出力先を含める
        settings["stats"],
        # ZIPの出力先を含める
        settings["archive"]["path"],
    )
    # すでに存在する出力だけを抽出する
    existing = [str(path) for path in output_paths if path.exists()]
    # 上書き指定なしで既存出力があれば停止する
    if existing and not args.overwrite:
        # 誤消去を防ぐため対象パスを列挙して通知する
        raise ValueError(
            "既存出力があります。置き換える場合は--overwriteを指定してください: "
            + ", ".join(existing)
        )

    # 各出力の親ディレクトリを作る
    for path in output_paths:
        # 存在済みでも失敗しないよう再帰的に作る
        path.parent.mkdir(parents=True, exist_ok=True)
    # 全レコードを固定キー順の一行JSONとして保存する
    output_text = "".join(
        # 日本語をエスケープせず改行付きJSONLへ変換する
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        # 操作ID順のレコードを一件ずつ処理する
        for record in records
    )
    # 生JSONLをUTF-8で保存する
    settings["output"].write_text(output_text, encoding="utf-8")
    # 生JSONLを固定メタデータのZIPへ格納する
    _write_deterministic_zip(
        # 圧縮元のJSONLを渡す
        settings["output"],
        # ZIP出力先を渡す
        settings["archive"]["path"],
        # ZIP内部の相対パスを渡す
        settings["archive"]["member"],
    )
    # 操作IDごとの指示数を数える
    counts_by_operation = Counter(
        # 各レコードが持つ唯一の操作IDを数える
        record["operation_ids"][0]
        # 全生成レコードを処理する
        for record in records
    )
    # 実行結果を確認できる集計オブジェクトを作る
    stats = {
        # 生成器の版を保存する
        "generator_version": settings["generator_version"],
        # 承認済み545件の辞書版を保存する
        "approved_dictionary_version": approved_dictionary_version,
        # 言い換え評価採用表現の内容ハッシュを保存する
        "paraphrase_dictionary_version": paraphrase_dictionary_version,
        # 承認済み辞書内のtest_only総数を保存する
        "dictionary_test_only_count": settings[
            "expected_dictionary_test_only_count"
        ],
        # 指定により評価から除いた承認済み表現IDを保存する
        "excluded_approved_expression_ids": settings[
            "excluded_approved_expression_ids"
        ],
        # 承認済み辞書から選んだ件数を保存する
        "approved_expression_count": settings[
            "expected_approved_expression_count"
        ],
        # 人手追加した辞書外表現の件数を保存する
        "external_expression_count": settings[
            "expected_external_expression_count"
        ],
        # 生成した全文指示数を保存する
        "instruction_count": len(records),
        # 覆った操作数を保存する
        "operation_count": len(counts_by_operation),
        # 操作別の生成件数を保存する
        "counts_by_operation": dict(sorted(counts_by_operation.items())),
        # 生JSONLのパスを保存する
        "output": _relative_project_path(settings["output"]),
        # 生JSONLのサイズを保存する
        "output_bytes": settings["output"].stat().st_size,
        # 生JSONLのSHA-256を保存する
        "output_sha256": _sha256_file(settings["output"]),
        # ZIP情報をまとめて保存する
        "archive": {
            # ZIPのパスを保存する
            "path": _relative_project_path(settings["archive"]["path"]),
            # ZIP内のJSONLパスを保存する
            "member": settings["archive"]["member"],
            # ZIP内レコード数を保存する
            "record_count": len(records),
            # ZIPサイズを保存する
            "bytes": settings["archive"]["path"].stat().st_size,
            # ZIPのSHA-256を保存する
            "sha256": _sha256_file(settings["archive"]["path"]),
        },
    }
    # 集計JSONを可読形式と末尾改行付きで保存する
    settings["stats"].write_text(
        # 日本語を保持したインデント付きJSONへ変換する
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
        # UTF-8で保存する
        encoding="utf-8",
    )
    # 完了件数と出力先を表示する
    print(
        f"言い換え評価指示を作成しました: instructions={len(records)}, "
        f"operations={len(counts_by_operation)}"
    )
    # 生JSONLの再現性確認用ハッシュを表示する
    print(f"output_sha256={stats['output_sha256']}")
    # ZIPのパス、件数、サイズを表示する
    print(
        f"archive={stats['archive']['path']} "
        f"records={stats['archive']['record_count']} "
        f"bytes={stats['archive']['bytes']}"
    )


# この工程を担当する関数を定義する
def _validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """設定のキー、型、パス、テンプレートを検査する。"""

    # 設定JSONに必要なキーを厳密に列挙する
    expected_keys = {
        "config_version",
        "phase",
        "approved_dictionary",
        "external_expressions",
        "single_operation_asts",
        "output",
        "stats",
        "archive",
        "expected_dictionary_test_only_count",
        "excluded_approved_expression_ids",
        "expected_approved_expression_count",
        "expected_external_expression_count",
        "expected_instruction_count",
        "expected_operation_count",
        "generator_version",
        "sentence_templates",
    }
    # 設定キーに過不足があれば停止する
    if set(config) != expected_keys:
        # 設定形式の取り違えとして通知する
        raise ValueError("言い換え評価指示生成設定の項目が不正です")
    # 対応する設定形式の版を確認する
    if config["config_version"] != 1:
        # 未対応の設定版を拒否する
        raise ValueError("config_versionは1にしてください")
    # 工程名が想定値と一致することを確認する
    if config["phase"] != "paraphrase_test_instructions":
        # 別工程の設定ファイルを拒否する
        raise ValueError("phaseはparaphrase_test_instructionsにしてください")
    # 元の設定を壊さないようコピーする
    settings = dict(config)
    # 入出力の単独パスをプロジェクトルート基準へ変換する
    for key in (
        "approved_dictionary",
        "external_expressions",
        "single_operation_asts",
        "output",
        "stats",
    ):
        # 空でない文字列をPathへ変換する
        settings[key] = _project_path(_required_string(config, key))
    # 三つの入力ファイルが存在することを確認する
    for key in ("approved_dictionary", "external_expressions", "single_operation_asts"):
        # 不足入力があれば対象名とパスを通知する
        if not settings[key].is_file():
            # 再生成すべき入力を明示して停止する
            raise ValueError(f"{key}が見つかりません: {settings[key]}")
    # 件数設定を0以上の整数として検査する
    for key in (
        "expected_dictionary_test_only_count",
        "expected_approved_expression_count",
        "expected_external_expression_count",
        "expected_instruction_count",
        "expected_operation_count",
    ):
        # boolを整数として誤認しないよう型を確認する
        if isinstance(config[key], bool) or not isinstance(config[key], int):
            # 不正な件数キーを通知する
            raise ValueError(f"{key}は0以上の整数にしてください")
        # 負の件数を拒否する
        if config[key] < 0:
            # 不正な件数キーを通知する
            raise ValueError(f"{key}は0以上の整数にしてください")
    # 二つの表現入力の合計が全文予定数と一致することを確認する
    if (
        config["expected_approved_expression_count"]
        + config["expected_external_expression_count"]
        != config["expected_instruction_count"]
    ):
        # 表現一件につき一文という規則違反を通知する
        raise ValueError("表現入力件数の合計とexpected_instruction_countが不一致です")
    # 評価から除外する承認済み表現ID配列を取得する
    excluded_ids = config["excluded_approved_expression_ids"]
    # 空文字列や重複を含まない文字列配列であることを確認する
    if (
        not isinstance(excluded_ids, list)
        or any(not isinstance(value, str) or not value for value in excluded_ids)
        or len(set(excluded_ids)) != len(excluded_ids)
    ):
        # 不正な除外ID設定を拒否する
        raise ValueError("excluded_approved_expression_idsが不正です")
    # test_only総数から除外数を引いた件数が採用件数になることを確認する
    if (
        config["expected_dictionary_test_only_count"] - len(excluded_ids)
        != config["expected_approved_expression_count"]
    ):
        # 評価採用件数との不整合を通知する
        raise ValueError("test_only総数、除外数、承認済み採用数が不一致です")
    # 検査済みの除外IDを設定へ保存する
    settings["excluded_approved_expression_ids"] = excluded_ids
    # 生成器の版を空でない文字列として取得する
    settings["generator_version"] = _required_string(config, "generator_version")
    # ZIP設定が三つの必要項目だけを持つことを確認する
    archive = config["archive"]
    # 不正なZIP設定を拒否する
    if not isinstance(archive, dict) or set(archive) != {"path", "member"}:
        # 設定位置を通知して停止する
        raise ValueError("archiveはpathとmemberを指定してください")
    # ZIP出力先をプロジェクトルート基準へ変換する
    archive_path = _project_path(_required_string(archive, "path"))
    # ZIP内部の相対パスを取得する
    archive_member = _required_string(archive, "member")
    # ZIP内パスが絶対パスまたは親参照を含む場合は拒否する
    if Path(archive_member).is_absolute() or ".." in Path(archive_member).parts:
        # 安全でないメンバー名を通知する
        raise ValueError("archive.memberは安全な相対パスにしてください")
    # 検査済みのZIP設定を保存する
    settings["archive"] = {"path": archive_path, "member": archive_member}
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
            raise ValueError(f"sentence_templates.{key}.textが不正です")
        # 検査済みのIDと本文を保存する
        templates[key] = {"template_id": template_id, "text": text}
    # 二つのテンプレートIDが異なることを確認する
    if templates["without_k"]["template_id"] == templates["with_k"]["template_id"]:
        # 追跡不能な重複IDを拒否する
        raise ValueError("sentence template IDは重複させないでください")
    # 検査済みテンプレートを返す
    return templates


# この工程を担当する関数を定義する
def _load_test_expressions(
    settings: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    """承認済み採用表現と辞書外9件を読み、来歴付きで返す。"""

    # 承認済み辞書の全レコードを読む
    approved_records = _read_jsonl(settings["approved_dictionary"])
    # 承認済み辞書の版を集める
    approved_versions = {
        # 各行の辞書版を取得する
        _required_string(record, "dictionary_version")
        # 全545件を順番に処理する
        for record in approved_records
    }
    # 承認済み辞書の版が一つでなければ停止する
    if len(approved_versions) != 1:
        # 入力辞書の混在を通知する
        raise ValueError("approved_dictionaryのdictionary_versionが不一致です")
    # 訓練表現の終止形・接続形組を集合にする
    train_pairs = {
        # 完全な表現組を重複検査用に保存する
        (record["expression_ja"], record["connective_expression_ja"])
        # 全承認済み表現を処理する
        for record in approved_records
        # train区分だけを対象にする
        if record.get("dictionary") == "train"
    }
    # 承認済み辞書のtest_only全件を抽出する
    selected_all = [
        # 元レコードへ来歴区分を追加する
        {**record, "expression_origin": "approved_dictionary"}
        # 全承認済み表現を処理する
        for record in approved_records
        # test_only区分だけを採用する
        if record.get("dictionary") == "test_only"
    ]
    # test_only総数が設定値と一致することを確認する
    if len(selected_all) != settings["expected_dictionary_test_only_count"]:
        # 実件数を通知して停止する
        raise ValueError(f"approved test_only件数が不一致です: {len(selected_all)}")
    # 設定した評価除外IDを集合にする
    excluded_ids = set(settings["excluded_approved_expression_ids"])
    # 除外IDがすべてtest_only内に存在することを確認する
    selected_all_ids = {record["expression_id"] for record in selected_all}
    # 不明なIDがあれば停止する
    if not excluded_ids <= selected_all_ids:
        # 見つからないIDを通知する
        raise ValueError(
            f"評価除外IDがtest_onlyにありません: {sorted(excluded_ids - selected_all_ids)}"
        )
    # 指定された2件を除いて評価へ採用する
    selected = [
        # 除外対象でない元レコードを採用する
        record
        # test_only全件を入力順に処理する
        for record in selected_all
        # 設定した除外IDは評価へ入れない
        if record["expression_id"] not in excluded_ids
    ]
    # 承認済み側の評価採用件数が設定値と一致することを確認する
    if len(selected) != settings["expected_approved_expression_count"]:
        # 実件数を通知して停止する
        raise ValueError(f"approved評価採用件数が不一致です: {len(selected)}")
    # 人手追加した辞書外9件を読む
    external = _read_jsonl(settings["external_expressions"])
    # 辞書外側の件数が設定値と一致することを確認する
    if len(external) != settings["expected_external_expression_count"]:
        # 実件数を通知して停止する
        raise ValueError(f"external表現件数が不一致です: {len(external)}")
    # 辞書外9件を順番に検査する
    for record in external:
        # test_onlyかつ人手作成という来歴を必須にする
        if (
            record.get("dictionary") != "test_only"
            or record.get("source") != "human_authored_out_of_dictionary"
        ):
            # 不正な表現IDを通知する
            raise ValueError(f"external表現の来歴が不正です: {record.get('expression_id')}")
    # 辞書外レコードにも統一した来歴区分を追加する
    external_with_origin = [
        # 元レコードへ来歴区分を追加する
        {**record, "expression_origin": "human_authored_out_of_dictionary"}
        # 辞書外9件を入力順に処理する
        for record in external
    ]
    # 承認済み採用分と辞書外9件を結合する
    expressions = selected + external_with_origin
    # 表現IDの重複がないことを確認する
    expression_ids = [
        # 各レコードの必須IDを取得する
        _required_string(record, "expression_id")
        # 評価採用表現を順番に処理する
        for record in expressions
    ]
    # 表現IDの件数が採用表現数と一致しなければ停止する
    if len(set(expression_ids)) != len(expression_ids):
        # 重複IDの混入を通知する
        raise ValueError("言い換え評価表現のexpression_idが重複しています")
    # 評価採用表現組がtrain 522件と完全一致しないことを確認する
    for record in expressions:
        # 現在表現の終止形・接続形組を作る
        pair = (record["expression_ja"], record["connective_expression_ja"])
        # 訓練表現との完全一致があれば停止する
        if pair in train_pairs:
            # 漏洩した表現IDを通知する
            raise ValueError(f"trainと重複するtest_only表現です: {record['expression_id']}")
    # 操作ID順、承認済み側優先、元入力順へ安定整列する
    expressions.sort(
        # 操作IDと来歴だけで同一来歴内の入力順を保つ
        key=lambda record: (
            record["operation_id"],
            record["expression_origin"] != "approved_dictionary",
        )
    )
    # 評価採用表現と唯一の承認済み辞書版を返す
    return expressions, approved_versions.pop()


# この工程を担当する関数を定義する
def _load_single_operation_asts(path: Path) -> dict[str, dict[str, Any]]:
    """訓練分割から24個の単独操作ASTを操作AST別に読む。"""

    # 操作ASTから元の意味ASTレコードを引く辞書を作る
    single_asts: dict[str, dict[str, Any]] = {}
    # 訓練意味ASTを一件ずつ処理する
    for record in _read_jsonl(path):
        # 意味AST本体を取得する
        semantic_ast = record.get("semantic_ast")
        # 標準形式の操作列を取得する
        sequence = semantic_ast.get("sequence") if isinstance(semantic_ast, dict) else None
        # 単独操作でなければ次のレコードへ進む
        if not isinstance(sequence, list) or len(sequence) != 1:
            # 2・3操作ASTを読み飛ばす
            continue
        # 唯一の操作ASTを正規化してキーにする
        operation_key = _canonical_json(sequence[0])
        # 同じ単独操作が複数あれば停止する
        if operation_key in single_asts:
            # 重複した元spec_idを通知する
            raise ValueError(f"単独操作ASTが重複しています: {record.get('spec_id')}")
        # 元のspec_idと標準意味ASTを保持する
        single_asts[operation_key] = {
            "spec_id": _required_string(record, "spec_id"),
            "semantic_ast": semantic_ast,
        }
    # 24個すべての単独操作を取得できたことを確認する
    if len(single_asts) != 24:
        # 実件数を通知して停止する
        raise ValueError(f"単独操作ASTが24件ではありません: {len(single_asts)}")
    # 操作AST別の元レコードを返す
    return single_asts


# この工程を担当する関数を定義する
def _build_records(
    expressions: list[dict[str, Any]],
    single_asts: Mapping[str, dict[str, Any]],
    approved_dictionary_version: str,
    settings: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    """評価採用表現を各1件の単独操作全文指示へ変換する。"""

    # 言い換え専用辞書版の計算対象を表現ID順に作る
    dictionary_payload = [
        # 意味と本文と来歴に必要な項目だけを固定する
        {
            "expression_id": record["expression_id"],
            "operation_id": record["operation_id"],
            "operation_ast": record["operation_ast"],
            "expression_ja": record["expression_ja"],
            "connective_expression_ja": record["connective_expression_ja"],
            "expression_origin": record["expression_origin"],
        }
        # ID順なら入力ファイル順に依存しない
        for record in sorted(expressions, key=lambda item: item["expression_id"])
    ]
    # 評価採用表現の正規JSONから辞書版ハッシュを計算する
    paraphrase_dictionary_version = _sha256_text(_canonical_json(dictionary_payload))
    # 生成した全文指示レコードを格納する
    records: list[dict[str, Any]] = []
    # 全文の完全重複を検査する集合を作る
    seen_texts: set[str] = set()
    # 評価採用表現を操作ID順に処理する
    for expression in expressions:
        # 操作IDを必須文字列として取得する
        operation_id = _required_string(expression, "operation_id")
        # 操作ASTが辞書であることを確認する
        operation_ast = expression.get("operation_ast")
        # 不正な操作ASTを拒否する
        if not isinstance(operation_ast, dict):
            # 対象表現IDを通知する
            raise ValueError(f"operation_astが不正です: {expression['expression_id']}")
        # 操作ASTを単独操作元レコードのキーへ変換する
        operation_key = _canonical_json(operation_ast)
        # 対応する単独操作ASTがなければ停止する
        if operation_key not in single_asts:
            # 解決不能な操作IDを通知する
            raise ValueError(f"単独操作ASTが見つかりません: {operation_id}")
        # k有無に応じて外側文テンプレートを選ぶ
        template = settings["sentence_templates"][
            "with_k" if operation_id in K_OPERATION_IDS else "without_k"
        ]
        # 終止形を外側文テンプレートへ埋め込む
        instruction = template["text"].format(
            operations=_required_string(expression, "expression_ja")
        )
        # 完成全文が別表現と完全一致した場合は停止する
        if instruction in seen_texts:
            # 重複本文を通知する
            raise ValueError(f"言い換え評価指示が重複しています: {instruction}")
        # 新しい全文を確認済み集合へ追加する
        seen_texts.add(instruction)
        # 対応する標準単独操作ASTレコードを取得する
        ast_record = single_asts[operation_key]
        # 指示IDの安定した入力文字列を作る
        id_source = "\0".join(
            [
                ast_record["spec_id"],
                template["template_id"],
                expression["expression_id"],
                "paraphrase",
            ]
        )
        # 1操作1表現の評価指示レコードを追加する
        records.append(
            {
                "instruction_id": "instruction-paraphrase-" + _sha256_text(id_source),
                "spec_id": ast_record["spec_id"],
                "semantic_ast": ast_record["semantic_ast"],
                "operation_ids": [operation_id],
                "split": "test",
                "test_suite": "paraphrase",
                "instruction_ja": instruction,
                "instruction_source": "rule",
                "dictionary": "test_only",
                "dictionary_version": paraphrase_dictionary_version,
                "approved_dictionary_version": approved_dictionary_version,
                "expression_ids": [expression["expression_id"]],
                "expression_origin": expression["expression_origin"],
                "sentence_template_id": template["template_id"],
                "generator_version": settings["generator_version"],
                "generator_seed": None,
                "teacher_model": None,
                "teacher_revision": None,
                "prompt_hash": None,
                "text_hash": _sha256_text(instruction),
            }
        )
    # 生成件数が設定値と一致することを確認する
    if len(records) != settings["expected_instruction_count"]:
        # 実件数を通知して停止する
        raise ValueError(f"生成指示数が不一致です: {len(records)}")
    # 覆った操作ID集合を作る
    operation_ids = {
        # 各レコードの唯一の操作IDを取得する
        record["operation_ids"][0]
        # 全生成レコードを処理する
        for record in records
    }
    # 操作数が設定値と一致することを確認する
    if len(operation_ids) != settings["expected_operation_count"]:
        # 実操作数を通知して停止する
        raise ValueError(f"被覆操作数が不一致です: {len(operation_ids)}")
    # すべてのレコードが1操作・1表現であることを確認する
    if any(
        len(record["semantic_ast"]["sequence"]) != 1
        or len(record["expression_ids"]) != 1
        for record in records
    ):
        # 2・3操作または複数表現の混入を通知する
        raise ValueError("1操作1文の規則に違反するレコードがあります")
    # 生成レコードと言い換え専用辞書版を返す
    return records, paraphrase_dictionary_version


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
                # 1 MiBの固定バッファで末尾までコピーする
                shutil.copyfileobj(source_handle, archive_handle, length=1024 * 1024)


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
def _sha256_file(path: Path) -> str:
    """ファイルを逐次読み込みSHA-256を返す。"""

    # SHA-256計算器を初期化する
    hasher = hashlib.sha256()
    # 対象ファイルをバイナリで開く
    with path.open("rb") as handle:
        # 1 MiBずつ末尾まで読む
        while chunk := handle.read(1024 * 1024):
            # 現在のバイト列をハッシュへ加える
            hasher.update(chunk)
    # 16進文字列のSHA-256を返す
    return hasher.hexdigest()


# この工程を担当する関数を定義する
def _required_string(record: Mapping[str, Any], key: str) -> str:
    """指定キーから空でない文字列を取得する。"""

    # 指定キーの値を取得する
    value = record.get(key)
    # 空文字列と文字列以外を拒否する
    if not isinstance(value, str) or not value:
        # 不正なキーを通知する
        raise ValueError(f"{key}は空でない文字列にしてください")
    # 検査済み文字列を返す
    return value


# この工程を担当する関数を定義する
def _project_path(value: str) -> Path:
    """プロジェクト相対または絶対パスを解決する。"""

    # 入力文字列をPathへ変換する
    path = Path(value)
    # 絶対パスならそのまま正規化する
    if path.is_absolute():
        # 絶対パスを解決して返す
        return path.resolve()
    # 相対パスをプロジェクトルート基準で解決する
    return (PROJECT_ROOT / path).resolve()


# この工程を担当する関数を定義する
def _relative_project_path(path: Path) -> str:
    """プロジェクトルートからのPOSIX相対パスを返す。"""

    # 追跡しやすいスラッシュ区切り相対パスへ変換する
    return path.relative_to(PROJECT_ROOT).as_posix()


# 直接実行された場合だけ生成処理を開始する
if __name__ == "__main__":
    # コマンドライン入口を呼び出す
    main()
