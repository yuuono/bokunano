"""人間が確認したCSVから承認済み表現辞書を作成する。"""

from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse
# 操作別・辞書別の件数を数えるために使う
from collections import Counter
# 人間が記入した確認CSVを読むために使う
import csv
# 設定と辞書レコードをJSONで読み書きするために使う
import json
# 入出力ファイルのパスを扱うために使う
from pathlib import Path
# プロジェクト内モジュールのimport経路を設定するために使う
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
    canonical_json,
    sha256_text,
)


def parse_args() -> argparse.Namespace:
    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        description="確認済みCSVから承認済み日本語表現辞書を作ります。"
    )
    # 辞書作成条件を持つ設定JSONを必須引数として受け取る
    parser.add_argument("--config", required=True, type=Path)
    # 入力と設定だけを検査するオプションを追加する
    parser.add_argument("--validate-config", action="store_true")
    # 既存出力を明示的に置き換えるオプションを追加する
    parser.add_argument("--overwrite", action="store_true")
    # コマンドラインを解析して返す
    return parser.parse_args()


def main() -> None:
    # コマンドライン引数を取得する
    args = parse_args()
    # 設定JSONを絶対パスから読み込む
    config = _load_json(args.config.resolve())
    # 設定値と入力ファイルを検査する
    settings = _validate_config(config)
    # Qwenが生成した未承認候補JSONLを読み込む
    candidates = _read_jsonl(settings["candidates"])
    # 候補をexpression_idから即座に取得できる辞書へ変換する
    candidate_by_id = {
        _required_string(record, "expression_id"): record for record in candidates
    }
    # 辞書化で件数が減った場合は候補IDが重複しているため停止する
    if len(candidate_by_id) != len(candidates):
        raise ValueError("候補JSONLのexpression_idが重複しています")

    # 作成者本人が記入した確認CSVを読み込む
    review_rows = _read_review_csv(settings["review_csv"])
    # 設定検査だけの場合は件数を表示して辞書を書かずに終了する
    if args.validate_config:
        # 候補件数と確認CSV行数を表示する
        print(
            f"設定は有効です: candidates={len(candidates)}, "
            f"review_rows={len(review_rows)}"
        )
        # 承認済み辞書の作成へ進まず終了する
        return

    # 承認済み辞書と集計の出力先を順番に確認する
    for path in (settings["output"], settings["stats"]):
        # 上書き指定なしで既存出力があれば誤消去を防ぐため停止する
        if path.exists() and not args.overwrite:
            raise ValueError(
                f"既存出力があります。置き換える場合は--overwriteを指定してください: {path}"
            )

    # 承認済み表現レコードを格納する配列を作る
    approved: list[dict[str, Any]] = []
    # 確認CSV内の候補ID重複を検出する集合を作る
    seen_review_ids: set[str] = set()
    # 同じ操作・辞書・表現の重複を検出する集合を作る
    seen_dictionary_entries: set[tuple[str, str, str]] = set()
    # ヘッダーを除く実際のCSV行番号付きで各確認結果を処理する
    for row_number, row in enumerate(review_rows, start=2):
        # 元候補を示すexpression_idを取得する
        source_id = row["expression_id"].strip()
        # 同じ候補IDがCSV内に二度現れた場合は停止する
        if source_id in seen_review_ids:
            raise ValueError(f"確認CSVのexpression_idが重複しています: 行{row_number}")
        # 候補IDを確認済み集合へ追加する
        seen_review_ids.add(source_id)
        # 候補JSONLから対応する元レコードを取得する
        candidate = candidate_by_id.get(source_id)
        # 候補JSONLに存在しないIDが書かれていれば停止する
        if candidate is None:
            raise ValueError(f"候補にないexpression_idです: 行{row_number}: {source_id}")

        # 確認者が記入した状態を小文字へ統一して取得する
        status = row["review_status"].strip().lower()
        # 空欄またはunusedの行は承認済み辞書へ入れない
        if status in ("", "unused"):
            continue
        # approved以外の未知状態が指定されていれば入力ミスとして停止する
        if status != "approved":
            raise ValueError(
                f"review_statusはapproved、unused、空欄のいずれかにしてください: 行{row_number}"
            )
        # 承認表現を入れる辞書区分を取得する
        dictionary = row["dictionary"].strip()
        # 訓練用または言い換えテスト専用だけを許可する
        if dictionary not in ("train", "test_only"):
            raise ValueError(
                f"承認行のdictionaryはtrainまたはtest_onlyにしてください: 行{row_number}"
            )
        # 承認した確認者名を取得する
        reviewer = row["reviewer"].strip()
        # 承認日時を取得する
        reviewed_at = row["reviewed_at"].strip()
        # 誰がいつ承認したか不明な行は採用しない
        if not reviewer or not reviewed_at:
            raise ValueError(
                f"承認行にはreviewerとreviewed_atが必要です: 行{row_number}"
            )
        # 確認者が修正した表現があれば取得する
        edited = row["edited_expression_ja"].strip()
        # 修正版があれば優先し、なければQwenの元候補を使う
        expression = edited or _required_string(candidate, "expression_ja")
        # 単純操作辞書の表現は一行だけに制限する
        if "\n" in expression or "\r" in expression:
            raise ValueError(f"承認表現は1行にしてください: 行{row_number}")

        # 元候補から対象操作IDを取得する
        operation_id = _required_string(candidate, "operation_id")
        # 操作・辞書・本文を組にして重複確認キーを作る
        duplicate_key = (operation_id, dictionary, expression)
        # 同じ辞書エントリがすでにあれば停止する
        if duplicate_key in seen_dictionary_entries:
            raise ValueError(f"同じ承認表現が重複しています: 行{row_number}")
        # 新しい辞書エントリを重複確認集合へ追加する
        seen_dictionary_entries.add(duplicate_key)
        # 操作・辞書・本文から承認済み表現の一意IDを作る
        expression_id = "expr-" + sha256_text(
            operation_id + "\0" + dictionary + "\0" + expression
        )
        # 承認情報とQwen生成元を追跡できるレコードを追加する
        approved.append(
            {
                "expression_id": expression_id,
                "operation_id": operation_id,
                "operation_ast": candidate["operation_ast"],
                "expression_ja": expression,
                "dictionary": dictionary,
                "approved_by": reviewer,
                "approved_at": reviewed_at,
                "source_candidate_id": source_id,
                "source_expression_ja": candidate["expression_ja"],
                "human_edited": bool(edited),
                "teacher_model": candidate.get("teacher_model"),
                "teacher_revision": candidate.get("teacher_revision"),
                "prompt_hash": candidate.get("prompt_hash"),
            }
        )

    # 24操作ごとの承認済み表現数を集計する
    counts = Counter(record["operation_id"] for record in approved)
    # 操作と辞書区分の組ごとの承認数を集計する
    dictionary_counts = Counter(
        (record["operation_id"], record["dictionary"]) for record in approved
    )
    # 候補JSONLに含まれる全操作IDを安定した順番で取得する
    operation_ids = sorted(
        {_required_string(record, "operation_id") for record in candidates}
    )
    # 各操作に必要な承認数の下限を取得する
    minimum = settings["minimum_approved_per_operation"]
    # 各操作に許可する承認数の上限を取得する
    maximum = settings["maximum_approved_per_operation"]
    # 各操作の承認数と辞書分離を一件ずつ確認する
    for operation_id in operation_ids:
        # 現在操作の総承認数を取得する
        count = counts[operation_id]
        # 承認数が設定範囲外なら辞書を作らず停止する
        if not minimum <= count <= maximum:
            raise ValueError(
                f"{operation_id}の承認数は{minimum}〜{maximum}件にしてください: {count}"
            )
        # 訓練用表現が一件もない操作を許可しない
        if dictionary_counts[(operation_id, "train")] == 0:
            raise ValueError(f"{operation_id}にtrain表現がありません")
        # 言い換えテスト専用表現が一件もない操作を許可しない
        if dictionary_counts[(operation_id, "test_only")] == 0:
            raise ValueError(f"{operation_id}にtest_only表現がありません")

    # 出力順を操作IDと表現IDで固定する
    approved.sort(key=lambda record: (record["operation_id"], record["expression_id"]))
    # 辞書内容全体から再現性確認用のバージョンハッシュを作る
    dictionary_hash = sha256_text(
        "\n".join(canonical_json(record) for record in approved) + "\n"
    )
    # すべての承認済み表現へ同じ辞書バージョンを付ける
    for record in approved:
        record["dictionary_version"] = dictionary_hash

    # 承認済み表現辞書をJSONLへ保存する
    _write_jsonl(settings["output"], approved)
    # 全体件数と操作別件数を持つ集計レコードを作る
    stats = {
        "approved_count": len(approved),
        "dictionary_version": dictionary_hash,
        "counts_by_operation": dict(sorted(counts.items())),
        "counts_by_operation_and_dictionary": {
            f"{operation_id}:{dictionary}": count
            for (operation_id, dictionary), count in sorted(dictionary_counts.items())
        },
    }
    # 集計レコードを整形JSONへ保存する
    _write_json(settings["stats"], stats)
    # 作成した承認済み表現数を表示する
    print(f"承認済み辞書を作成しました: {len(approved)}件")
    # 後続生成器が使用する辞書バージョンを表示する
    print(f"dictionary_version={dictionary_hash}")


def _validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    # 設定JSONに必要なキーを厳密に列挙する
    expected = {
        "config_version",
        "candidates",
        "review_csv",
        "output",
        "stats",
        "minimum_approved_per_operation",
        "maximum_approved_per_operation",
    }
    # 設定キーが過不足なく一致することを確認する
    if set(config) != expected:
        raise ValueError("承認済み辞書設定の項目が不正です")
    # 対応している設定形式のバージョンを確認する
    if config["config_version"] != 1:
        raise ValueError("config_versionは1にしてください")
    # 元設定を壊さないよう解決済み設定用のコピーを作る
    settings = dict(config)
    # 入出力パスを順番にプロジェクトルート基準へ変換する
    for key in ("candidates", "review_csv", "output", "stats"):
        # パス設定を文字列として検査してPathへ変換する
        settings[key] = _project_path(_required_string(config, key))
    # 辞書作成前に存在すべき二つの入力ファイルを確認する
    for key in ("candidates", "review_csv"):
        # 入力ファイルがなければ停止する
        if not settings[key].is_file():
            raise ValueError(f"入力ファイルが見つかりません: {settings[key]}")
    # 操作ごとの承認数下限を取得する
    minimum = _required_int(config, "minimum_approved_per_operation")
    # 操作ごとの承認数上限を取得する
    maximum = _required_int(config, "maximum_approved_per_operation")
    # 下限が上限を超える矛盾した設定を拒否する
    if minimum > maximum:
        raise ValueError("承認数の最小値が最大値を超えています")
    # 検査とパス解決が終わった設定を返す
    return settings


def _read_review_csv(path: Path) -> list[dict[str, str]]:
    # 生成スクリプトが出力する確認CSVの列を定義する
    required_fields = {
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
    }
    # 確認CSVをUTF-8で開く
    with path.open(encoding="utf-8", newline="") as handle:
        # ヘッダーをキーとして各行を辞書化するreaderを作る
        reader = csv.DictReader(handle)
        # 列の削除や追加があれば誤った確認ファイルとして停止する
        if set(reader.fieldnames or []) != required_fields:
            raise ValueError("確認CSVの列が生成時から変更されています")
        # CSV各行を通常の辞書へ変換して返す
        return [dict(row) for row in reader]


def _load_json(path: Path) -> dict[str, Any]:
    # 設定ファイルを読み込みJSONとして解析する
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    # ファイルが存在しない場合は対象パスを示して停止する
    except FileNotFoundError as error:
        raise ValueError(f"設定が見つかりません: {path}") from error
    # JSON構文が不正な場合は対象パスを示して停止する
    except json.JSONDecodeError as error:
        raise ValueError(f"設定JSONが不正です: {path}") from error
    # 設定のルートがJSONオブジェクトであることを確認する
    if not isinstance(value, dict):
        raise ValueError("設定JSONのルートはオブジェクトにしてください")
    # 検査済み設定辞書を返す
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    # 読み込んだ候補レコードを格納する配列を作る
    records: list[dict[str, Any]] = []
    # 候補JSONLをUTF-8で開く
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
    # 全候補レコードを返す
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    # 保存先ディレクトリがなければ作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 承認済み辞書JSONLをUTF-8で新規作成する
    with path.open("w", encoding="utf-8") as handle:
        # 承認済み表現を一件ずつ書く
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


def _required_string(values: Mapping[str, Any], key: str) -> str:
    # 指定キーの値を取得する
    value = values.get(key)
    # 空でない文字列以外は拒否する
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key}は空でない文字列にしてください")
    # 検査済み文字列を返す
    return value


def _required_int(values: Mapping[str, Any], key: str) -> int:
    # 指定キーの値を取得する
    value = values.get(key)
    # boolを含まない正の整数だけを許可する
    if type(value) is not int or value <= 0:
        raise ValueError(f"{key}は正の整数にしてください")
    # 検査済み整数を返す
    return value


# importされたときは辞書を作らず、直接実行時だけmainを呼ぶ
if __name__ == "__main__":
    main()
