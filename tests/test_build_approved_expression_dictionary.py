"""人手選定した日本語表現辞書の分割設定を検証する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# 操作別・辞書別の件数確認に使う
from collections import Counter

# リポジトリ内ファイルのパスを扱う
from pathlib import Path

# 単体テストの枠組みを使う
import unittest

# 分割実装の読込・検査関数を使う
from scripts.instruction_generation.build_approved_expression_dictionary import (
    # 公開CSVと来歴JSONLを結合して読む
    _load_release_records,
    # 設定JSONを読む
    _load_json,
    # 設定の型と件数を検査する
    _validate_config,
    # 人手選定IDの存在と操作別配分を検査する
    _validate_selection,
)


# このテストファイルから一階層上をプロジェクトルートとして取得する
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# 関連する検査をまとめるクラスを定義する
class ApprovedExpressionDictionaryTests(unittest.TestCase):
    """公開済み545件と固定した23件の整合性を確認する。"""

    # この工程を担当するテストを定義する
    def test_human_reviewed_split_is_522_train_and_23_test_only(self) -> None:
        """人手選定IDが確定済みの件数と操作範囲を保つ。"""

        # リポジトリで管理する分割設定を読み検査する
        settings = _validate_config(
            # 設定JSONを絶対パスから読み込む
            _load_json(
                PROJECT_ROOT / "config/build_approved_expression_dictionary.json"
            )
        )
        # 公開CSVと来歴JSONLを結合する
        records = _load_release_records(
            # 公開CSVパスを渡す
            settings["expressions_csv"],
            # 来歴JSONLパスを渡す
            settings["provenance_jsonl"],
        )
        # 人手選定IDが公開物と一致することを検査する
        _validate_selection(records, settings)
        # 選定IDを高速に照合できる集合へ変換する
        selected_ids = set(settings["test_only_expression_ids"])
        # test_onlyだけのレコードを抽出する
        selected = [
            # 現在の公開レコードを結果へ入れる
            record
            # 公開レコードを順番に確認する
            for record in records
            # 人手選定IDと一致するレコードだけを残す
            if record["expression_id"] in selected_ids
        ]
        # 公開表現の総数を確認する
        self.assertEqual(len(records), 545)
        # 選定されたtest_only件数を確認する
        self.assertEqual(len(selected), 23)
        # 残りのtrain件数を確認する
        self.assertEqual(len(records) - len(selected), 522)
        # 選定された操作数が22であることを確認する
        self.assertEqual(len({record["operation_id"] for record in selected}), 22)
        # atomic-000003だけが2件であることを確認する
        self.assertEqual(
            # 操作別件数を集計する
            Counter(record["operation_id"] for record in selected)["atomic-000003"],
            # 人手確定した期待件数と比べる
            2,
        )
        # 全公開レコードが生成時のJSONL情報を保持することを確認する
        self.assertTrue(
            # すべてのgeneration_recordがオブジェクトなら成功とする
            all(isinstance(record["generation_record"], dict) for record in records)
        )


# 直接実行された場合だけ単体テストを開始する
if __name__ == "__main__":
    # unittest標準のテストランナーを呼び出す
    unittest.main()
