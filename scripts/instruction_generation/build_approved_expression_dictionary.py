"""公開済み承認表現を人手選定結果に従ってtrainとtest_onlyへ分ける。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse

# 操作別・辞書別の件数を数えるために使う
from collections import Counter

# 公開済み表現CSVを読むために使う
import csv

# 設定とJSONLを読み書きするために使う
import json

# 入出力ファイルのパスを扱うために使う
from pathlib import Path

# 設定辞書とレコードの型注釈に使う
from typing import Any, Mapping


# このファイルから二階層上をプロジェクトルートとして取得する
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# この工程を担当する関数を定義する
def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""

    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        # 実行内容をヘルプへ表示する
        description="公開済み承認表現をtrainとtest_onlyへ決定的に分割します。"
    )
    # 分割条件を持つ設定JSONを必須引数として受け取る
    parser.add_argument("--config", required=True, type=Path)
    # 入力と設定だけを検査するオプションを追加する
    parser.add_argument("--validate-config", action="store_true")
    # 既存出力を明示的に置き換えるオプションを追加する
    parser.add_argument("--overwrite", action="store_true")
    # コマンドラインを解析して返す
    return parser.parse_args()


# この工程を担当する関数を定義する
def main() -> None:
    """設定を読み、承認済み辞書と集計を出力する。"""

    # コマンドライン引数を取得する
    args = parse_args()
    # 設定JSONを読み込んで検査する
    settings = _validate_config(_load_json(args.config.resolve()))
    # 公開CSVと来歴JSONLを対応付けて読む
    source_records = _load_release_records(
        # 公開CSVのパスを渡す
        settings["expressions_csv"],
        # 来歴JSONLのパスを渡す
        settings["provenance_jsonl"],
    )
    # 入力内容と人手選定IDを検査する
    _validate_selection(source_records, settings)
    # 設定検査だけの場合は出力せず終了する
    if args.validate_config:
        # 検査済み件数を表示する
        print(
            # 全件数と分割件数を一行にまとめる
            f"設定は有効です: total={len(source_records)}, "
            # train件数を表示へ加える
            f"train={settings['expected_train_count']}, "
            # test_only件数を表示へ加える
            f"test_only={settings['expected_test_only_count']}"
        )
        # ファイル生成へ進まず終了する
        return

    # 出力先を順番に確認する
    for path in (settings["output"], settings["stats"]):
        # 上書き指定なしで既存出力があれば停止する
        if path.exists() and not args.overwrite:
            # 誤消去を防ぐため対象パス付きで例外を送る
            raise ValueError(
                f"既存出力があります。置き換える場合は--overwriteを指定してください: {path}"
            )

    # 人手選定したtest_only IDを集合へ変換する
    test_only_ids = set(settings["test_only_expression_ids"])
    # 出力する承認済みレコードを格納する
    approved: list[dict[str, Any]] = []
    # 公開順の各表現へ辞書区分を付ける
    for source in source_records:
        # 現在表現の一意IDを取得する
        expression_id = _required_string(source, "expression_id")
        # 人手選定IDだけをtest_onlyとし、それ以外をtrainにする
        dictionary = "test_only" if expression_id in test_only_ids else "train"
        # 分割後も生成時の完全な来歴を保持したレコードを追加する
        approved.append(
            {
                # 公開CSVと共通の一意IDを保存する
                "expression_id": expression_id,
                # 対象の単純操作IDを保存する
                "operation_id": source["operation_id"],
                # 機械処理用の操作ASTを保存する
                "operation_ast": source["operation_ast"],
                # 人間向けの正準意味を保存する
                "canonical_meaning_ja": source["canonical_meaning_ja"],
                # 言い換え時に保持すべき条件を保存する
                "must_preserve_ja": source["must_preserve_ja"],
                # 承認済み終止形を保存する
                "expression_ja": source["expression_ja"],
                # 承認済み接続形を保存する
                "connective_expression_ja": source["connective_expression_ja"],
                # 訓練用か言い換えテスト専用かを保存する
                "dictionary": dictionary,
                # 分割を人手で決めたことを保存する
                "dictionary_selection_method": settings["selection_method"],
                # 承認時に表現が修正されたかを保存する
                "human_edited": source["human_edited"],
                # Qwen候補生成時の完全なJSONLレコードを失わず保存する
                "generation_record": source["generation_record"],
            }
        )

    # 辞書バージョン付与前の内容から再現性確認用ハッシュを作る
    dictionary_version = _sha256_records(approved)
    # 全レコードへ共通の辞書バージョンを付ける
    for record in approved:
        # 分割内容を識別するハッシュを保存する
        record["dictionary_version"] = dictionary_version

    # 分割後の辞書区分ごとの件数を集計する
    counts_by_dictionary = Counter(record["dictionary"] for record in approved)
    # 操作と辞書区分の組ごとの件数を集計する
    counts_by_operation_and_dictionary = Counter(
        # 現在レコードの操作IDと辞書区分を集計キーにする
        (record["operation_id"], record["dictionary"])
        for record in approved
    )
    # 承認済み表現辞書をJSONLへ保存する
    _write_jsonl(settings["output"], approved)
    # 分割結果を確認できる集計オブジェクトを作る
    stats = {
        # 入力した承認済み表現の総数を保存する
        "approved_count": len(approved),
        # 分割方法が人手選定であることを保存する
        "selection_method": settings["selection_method"],
        # 再現性確認用の辞書バージョンを保存する
        "dictionary_version": dictionary_version,
        # 辞書区分ごとの件数を保存する
        "counts_by_dictionary": dict(sorted(counts_by_dictionary.items())),
        # 操作・辞書区分ごとの件数を保存する
        "counts_by_operation_and_dictionary": {
            # 二つの区分名をコロンで結んだキーへ件数を割り当てる
            f"{operation_id}:{dictionary}": count
            # 集計キーを安定した順番で処理する
            for (operation_id, dictionary), count in sorted(
                counts_by_operation_and_dictionary.items()
            )
        },
        # 人手選定したIDを設定と同じ順番で保存する
        "test_only_expression_ids": settings["test_only_expression_ids"],
    }
    # 集計JSONを保存する
    _write_json(settings["stats"], stats)
    # 実行結果の件数を標準出力へ表示する
    print(
        # 総数と二つの辞書区分の件数を一行にまとめる
        f"承認済み辞書を作成しました: total={len(approved)}, "
        # train件数を表示へ加える
        f"train={counts_by_dictionary['train']}, "
        # test_only件数を表示へ加える
        f"test_only={counts_by_dictionary['test_only']}"
    )
    # 後続生成器が記録する辞書バージョンを表示する
    print(f"dictionary_version={dictionary_version}")


# この工程を担当する関数を定義する
def _validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """設定のキー、型、入力パスを検査して返す。"""

    # 設定JSONに必要なキーを厳密に列挙する
    expected = {
        "config_version",
        "expressions_csv",
        "provenance_jsonl",
        "output",
        "stats",
        "selection_method",
        "test_only_expression_ids",
        "expected_total_count",
        "expected_train_count",
        "expected_test_only_count",
    }
    # 設定キーに過不足があれば停止する
    if set(config) != expected:
        # 設定形式の取り違えとして通知する
        raise ValueError("承認済み辞書設定の項目が不正です")
    # 対応する設定形式の版を確認する
    if config["config_version"] != 3:
        # 古い候補・レビュー入力方式を誤用しないよう停止する
        raise ValueError("config_versionは3にしてください")
    # 元の設定を壊さないようコピーする
    settings = dict(config)
    # 入出力パスをプロジェクトルート基準へ変換する
    for key in ("expressions_csv", "provenance_jsonl", "output", "stats"):
        # パス文字列を検査してPathへ変換する
        settings[key] = _project_path(_required_string(config, key))
    # 二つの公開入力ファイルが存在することを確認する
    for key in ("expressions_csv", "provenance_jsonl"):
        # 入力が通常ファイルでなければ停止する
        if not settings[key].is_file():
            # 不足している入力パスを通知する
            raise ValueError(f"入力ファイルが見つかりません: {settings[key]}")
    # 分割方法が人手選定であることを固定する
    if config["selection_method"] != "human_reviewed":
        # 自動抽出と誤解される値を拒否する
        raise ValueError("selection_methodはhuman_reviewedにしてください")
    # test_only ID配列を取得する
    selected_ids = config["test_only_expression_ids"]
    # 配列でない場合や空の場合は停止する
    if not isinstance(selected_ids, list) or not selected_ids:
        # 人手選定結果がない設定を拒否する
        raise ValueError("test_only_expression_idsは空でない配列にしてください")
    # 全IDが空でない文字列であることを確認する
    if any(not isinstance(value, str) or not value for value in selected_ids):
        # 不正なID型を通知する
        raise ValueError("test_only_expression_idsは空でない文字列にしてください")
    # 選定IDに重複がないことを確認する
    if len(set(selected_ids)) != len(selected_ids):
        # 同じ表現を二重に選ぶ設定を拒否する
        raise ValueError("test_only_expression_idsが重複しています")
    # 期待件数を整数として順番に検査する
    for key in (
        "expected_total_count",
        "expected_train_count",
        "expected_test_only_count",
    ):
        # boolを除く正の整数だけを許可する
        if (
            isinstance(config[key], bool)
            or not isinstance(config[key], int)
            or config[key] < 0
        ):
            # 不正な期待件数のキーを通知する
            raise ValueError(f"{key}は0以上の整数にしてください")
    # trainとtest_onlyの期待件数が総数に一致するか確認する
    if (
        config["expected_train_count"] + config["expected_test_only_count"]
        != config["expected_total_count"]
    ):
        # 矛盾した件数設定を拒否する
        raise ValueError("trainとtest_onlyの期待件数の和が総数と一致しません")
    # test_only ID数が期待件数と一致するか確認する
    if len(selected_ids) != config["expected_test_only_count"]:
        # 人手選定リストの不足や過剰を通知する
        raise ValueError("test_only_expression_idsの数が期待件数と一致しません")
    # 検査済み設定を返す
    return settings


# この工程を担当する関数を定義する
def _load_release_records(
    csv_path: Path, provenance_path: Path
) -> list[dict[str, Any]]:
    """公開CSVと同順の来歴JSONLを検査して結合する。"""

    # 公開CSVを辞書行として読む
    with csv_path.open(encoding="utf-8", newline="") as handle:
        # ヘッダーを使って全行を辞書化する
        csv_rows = list(csv.DictReader(handle))
    # 来歴JSONLを全件読む
    provenance_rows = _read_jsonl(provenance_path)
    # 二つの公開物の件数が違えば停止する
    if len(csv_rows) != len(provenance_rows):
        # 対応関係が壊れていることを通知する
        raise ValueError("公開CSVと来歴JSONLの件数が一致しません")
    # 結合済みレコードを格納する
    records: list[dict[str, Any]] = []
    # 同一行番号のCSVと来歴を対応付ける
    for line_number, (csv_row, provenance) in enumerate(
        # 1始まりの行番号を付けて二つの列を同時に処理する
        zip(csv_rows, provenance_rows, strict=True),
        # CSVヘッダーの次を2行目として数える
        start=2,
    ):
        # CSV側のIDを取得する
        expression_id = _required_string(csv_row, "expression_id")
        # 来歴側のIDと行単位で一致することを確認する
        if expression_id != _required_string(provenance, "expression_id"):
            # 対応が崩れた行番号を通知する
            raise ValueError(
                f"公開CSVと来歴JSONLのIDが一致しません: CSV行{line_number}"
            )
        # 操作IDも両ファイルで一致することを確認する
        if csv_row["operation_id"] != provenance.get("operation_id"):
            # 操作の取り違えを通知する
            raise ValueError(
                f"公開CSVと来歴JSONLの操作IDが一致しません: CSV行{line_number}"
            )
        # 承認済み終止形が両ファイルで一致することを確認する
        if csv_row["expression_ja"] != provenance.get("approved_expression_ja"):
            # 最終表現の取り違えを通知する
            raise ValueError(
                f"公開CSVと来歴JSONLの終止形が一致しません: CSV行{line_number}"
            )
        # 承認済み接続形が両ファイルで一致することを確認する
        if csv_row["connective_expression_ja"] != provenance.get(
            "approved_connective_expression_ja"
        ):
            # 最終表現の取り違えを通知する
            raise ValueError(
                f"公開CSVと来歴JSONLの接続形が一致しません: CSV行{line_number}"
            )
        # 生成元の完全なレコードを来歴から取得する
        generation_record = provenance.get("generation_record")
        # 来歴が欠落した公開レコードを拒否する
        if not isinstance(generation_record, dict):
            # 欠落した行番号を通知する
            raise ValueError(f"generation_recordがありません: JSONL行{line_number - 1}")
        # CSV文字列の操作ASTをJSONオブジェクトへ戻す
        operation_ast = json.loads(csv_row["operation_ast"])
        # 分割に必要な公開情報と完全な来歴を一つにまとめる
        records.append(
            {
                # 公開表現IDを保存する
                "expression_id": expression_id,
                # 操作IDを保存する
                "operation_id": csv_row["operation_id"],
                # 解析済み操作ASTを保存する
                "operation_ast": operation_ast,
                # 正準意味を保存する
                "canonical_meaning_ja": csv_row["canonical_meaning_ja"],
                # 保持条件を保存する
                "must_preserve_ja": csv_row["must_preserve_ja"],
                # 承認済み終止形を保存する
                "expression_ja": csv_row["expression_ja"],
                # 承認済み接続形を保存する
                "connective_expression_ja": csv_row["connective_expression_ja"],
                # 人手修正の有無を来歴から保存する
                "human_edited": provenance.get("human_edited", False),
                # 生成元の完全なレコードを保存する
                "generation_record": generation_record,
            }
        )
    # 公開順の結合済みレコードを返す
    return records


# この工程を担当する関数を定義する
def _validate_selection(
    records: list[dict[str, Any]], settings: Mapping[str, Any]
) -> None:
    """公開表現と人手選定IDの件数・存在・操作対応を検査する。"""

    # 公開表現IDを順番に取り出す
    all_ids = [_required_string(record, "expression_id") for record in records]
    # 公開表現IDの重複を拒否する
    if len(set(all_ids)) != len(all_ids):
        # 分割不能な重複を通知する
        raise ValueError("公開CSVのexpression_idが重複しています")
    # 入力総数が確定済み件数と一致するか確認する
    if len(records) != settings["expected_total_count"]:
        # 意図しない辞書更新を通知する
        raise ValueError(f"承認済み表現の総数が期待値と一致しません: {len(records)}")
    # 人手選定IDを集合にする
    selected_ids = set(settings["test_only_expression_ids"])
    # 公開辞書に存在しない選定IDを抽出する
    missing = sorted(selected_ids - set(all_ids))
    # 不明なIDが一つでもあれば停止する
    if missing:
        # 最初の不明IDを通知する
        raise ValueError(f"公開CSVにないtest_only IDです: {missing[0]}")
    # 分割後の実際のtrain件数を求める
    train_count = len(records) - len(selected_ids)
    # train件数が期待値と一致するか確認する
    if train_count != settings["expected_train_count"]:
        # 分割設定の矛盾を通知する
        raise ValueError(f"train件数が期待値と一致しません: {train_count}")
    # 選定済み表現の操作ごとの件数を数える
    selected_by_operation = Counter(
        # test_onlyに選ばれたレコードの操作IDを数える
        record["operation_id"]
        # 公開表現を順番に処理する
        for record in records
        # 人手選定IDに含まれるレコードだけを対象にする
        if record["expression_id"] in selected_ids
    )
    # 選定結果が22操作を覆うことを確認する
    if len(selected_by_operation) != 22:
        # 想定外の操作範囲を通知する
        raise ValueError("test_onlyの23件は22操作を覆う必要があります")
    # k超過操作だけが2件選定されていることを確認する
    if selected_by_operation != Counter(
        # atomic-000003だけ2件、ほかの選定操作は1件にする
        {
            **{
                f"atomic-{index:06d}": 1
                for index in range(1, 25)
                if index not in (18, 21)
            },
            "atomic-000003": 2,
        }
    ):
        # 人手確定した操作別配分の変更を拒否する
        raise ValueError("test_onlyの操作別件数が人手選定結果と一致しません")


# この工程を担当する関数を定義する
def _sha256_records(records: list[dict[str, Any]]) -> str:
    """JSONL相当の正規化内容からSHA-256を返す。"""

    # ハッシュ計算に使う標準モジュールを読み込む
    import hashlib

    # キー順を固定した一行JSONを改行で結合する
    text = (
        "\n".join(
            # 日本語を保持しつつJSONキーを整列する
            json.dumps(
                record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            # 全レコードを公開順に処理する
            for record in records
        )
        + "\n"
    )
    # UTF-8バイト列のSHA-256を16進文字列で返す
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# この工程を担当する関数を定義する
def _load_json(path: Path) -> dict[str, Any]:
    """JSONオブジェクトを読み込む。"""

    # 設定ファイルをUTF-8で読みJSONとして解析する
    value = json.loads(path.read_text(encoding="utf-8"))
    # 設定のルートがオブジェクトであることを確認する
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
def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """レコードを一行一JSONで保存する。"""

    # 保存先ディレクトリがなければ作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 出力JSONLをUTF-8で新規作成する
    with path.open("w", encoding="utf-8") as handle:
        # レコードを公開順に一件ずつ書く
        for record in records:
            # 日本語を保持した一行JSONへ変換する
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            # JSONLの区切りとなる改行を書く
            handle.write("\n")


# この工程を担当する関数を定義する
def _write_json(path: Path, value: object) -> None:
    """集計値を可読なJSONで保存する。"""

    # 保存先ディレクトリがなければ作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 日本語を保持した整形JSONを末尾改行付きで保存する
    path.write_text(
        # 集計オブジェクトを2空白インデントで整形する
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        # UTF-8で保存する
        encoding="utf-8",
    )


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


# 直接実行された場合だけ主処理を呼び出す
if __name__ == "__main__":
    # 辞書分割処理を開始する
    main()
