"""言い換えテスト用32表現の分離と単独操作対応を検証する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# CSV形式の公開表現を読むために使う
import csv

# 設定とJSONLを読むために使う
import json

# 操作ごとの表現数を数えるために使う
from collections import Counter

# リポジトリ内ファイルのパスを扱う
from pathlib import Path

# 単体テストの枠組みを使う
import unittest


# このテストファイルから一階層上をプロジェクトルートとして取得する
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# 関連する検査をまとめるクラスを定義する
class ParaphraseTestPolicyTests(unittest.TestCase):
    """承認済み23件と人手追加9件が安全な32件になることを確認する。"""

    # この工程を担当するテストを定義する
    def test_32_test_only_expressions_cover_all_operations(self) -> None:
        """32件がtrainと重複せず、24個の単独操作ASTを覆う。"""

        # 公開済みの承認表現CSVを読む
        with (
            PROJECT_ROOT
            / "data/instruction_dictionaries/release/japanese_atomic_expressions.csv"
        ).open(encoding="utf-8", newline="") as handle:
            # CSVヘッダーを使って全表現を辞書化する
            approved_rows = list(csv.DictReader(handle))
        # 人手選定した23件のIDを持つ設定を読む
        split_config = json.loads(
            (
                PROJECT_ROOT / "config/build_approved_expression_dictionary.json"
            ).read_text(encoding="utf-8")
        )
        # test_only IDを高速に照合できる集合へ変換する
        selected_ids = set(split_config["test_only_expression_ids"])
        # 承認済み545件からtest_only 23件を抽出する
        selected_rows = [
            # 現在の承認表現を結果へ入れる
            row
            # 全承認表現を順番に処理する
            for row in approved_rows
            # 人手選定IDだけを残す
            if row["expression_id"] in selected_ids
        ]
        # 人手追加9件のJSONLを読む
        external_path = (
            PROJECT_ROOT
            / "data/instruction_dictionaries/release/paraphrase_test_external_expressions.jsonl"
        )
        # 空行を除いて各行をJSONオブジェクトへ変換する
        external_rows = [
            # 現在行をJSONとして解析する
            json.loads(line)
            # UTF-8のJSONLを一行ずつ処理する
            for line in external_path.read_text(encoding="utf-8").splitlines()
            # 空行は読み飛ばす
            if line.strip()
        ]
        # 承認済み側が23件であることを確認する
        self.assertEqual(len(selected_rows), 23)
        # 人手追加側が9件であることを確認する
        self.assertEqual(len(external_rows), 9)
        # 二つを合わせて32件になることを確認する
        test_rows = selected_rows + external_rows
        # 合計件数を確認する
        self.assertEqual(len(test_rows), 32)
        # 24操作すべてを覆うことを確認する
        self.assertEqual(len({row["operation_id"] for row in test_rows}), 24)
        # 人手追加9件の区分と出所が固定値であることを確認する
        self.assertTrue(
            # 全行がtest_onlyかつ人手作成なら成功とする
            all(
                row["dictionary"] == "test_only"
                and row["source"] == "human_authored_out_of_dictionary"
                for row in external_rows
            )
        )
        # train側の終止形・接続形組を集合にする
        train_pairs = {
            # 終止形と接続形を組にする
            (row["expression_ja"], row["connective_expression_ja"])
            # 全承認表現を順番に処理する
            for row in approved_rows
            # test_onlyに選ばれなかった522件だけを対象にする
            if row["expression_id"] not in selected_ids
        }
        # 32件の表現組がtrain側と完全一致しないことを確認する
        self.assertTrue(
            all(
                (row["expression_ja"], row["connective_expression_ja"])
                not in train_pairs
                for row in test_rows
            )
        )
        # 操作IDごとのtest_only表現数を数える
        counts = Counter(row["operation_id"] for row in test_rows)
        # 正式な操作定義を読む
        operation_config = json.loads(
            (PROJECT_ROOT / "config/japanese_atomic_operations.json").read_text(
                encoding="utf-8"
            )
        )
        # 操作IDから正式な単独操作ASTを引く対応表を作る
        operation_ast_by_id = {
            # 現在操作のIDと意味ASTを対応付ける
            item["operation_id"]: item["semantic_ast"]
            # 24操作の定義を順番に処理する
            for item in operation_config["operations"]
        }
        # 32件を一件ずつ処理する
        for row in test_rows:
            # CSV側だけJSON文字列になっている操作ASTを辞書へ戻す
            operation_ast = row["operation_ast"]
            # 文字列ならJSONとして解析する
            if isinstance(operation_ast, str):
                # 単独操作ASTの辞書を得る
                operation_ast = json.loads(operation_ast)
            # 各表現が対応する正式な単独操作ASTと一致することを確認する
            self.assertEqual(operation_ast, operation_ast_by_id[row["operation_id"]])
            # 複数操作を表すsequence形式が混ざっていないことを確認する
            self.assertNotIn("sequence", operation_ast)
        # 操作別の表現数が人手で確定した分布と一致することを確認する
        self.assertEqual(
            counts,
            Counter(
                {
                    "atomic-000001": 3,
                    "atomic-000002": 3,
                    "atomic-000003": 2,
                    "atomic-000013": 2,
                    "atomic-000014": 2,
                    "atomic-000015": 2,
                    **{
                        operation_id: 1
                        for operation_id in operation_ast_by_id
                        if operation_id
                        not in {
                            "atomic-000001",
                            "atomic-000002",
                            "atomic-000003",
                            "atomic-000013",
                            "atomic-000014",
                            "atomic-000015",
                        }
                    },
                }
            ),
        )
        # 表現一件につき一文なので、予定する評価指示数が32件になる
        self.assertEqual(sum(counts.values()), 32)


# 直接実行された場合だけ単体テストを開始する
if __name__ == "__main__":
    # unittest標準のテストランナーを呼び出す
    unittest.main()
