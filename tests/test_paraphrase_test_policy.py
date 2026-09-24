"""言い換え評価用30表現の分離と単独操作対応を検証する。"""

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

# ZIP内の生成済みJSONLを読むために使う
import zipfile


# このテストファイルから一階層上をプロジェクトルートとして取得する
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# 関連する検査をまとめるクラスを定義する
class ParaphraseTestPolicyTests(unittest.TestCase):
    """候補32件から指定2件を除き、安全な30件になることを確認する。"""

    # この工程を担当するテストを定義する
    def test_30_test_only_expressions_cover_all_operations(self) -> None:
        """採用30件がtrainと重複せず、24個の単独操作ASTを覆う。"""

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
        # 二つを合わせた候補が32件になることを確認する
        candidate_rows = selected_rows + external_rows
        # 候補総数を確認する
        self.assertEqual(len(candidate_rows), 32)
        # 言い換え評価指示の生成設定を読む
        generation_config = json.loads(
            (
                PROJECT_ROOT / "config/paraphrase_test_instruction_generation.json"
            ).read_text(encoding="utf-8")
        )
        # 指定により評価から除外する承認済み2件のIDを集合にする
        excluded_ids = set(generation_config["excluded_approved_expression_ids"])
        # 除外IDが2件であることを確認する
        self.assertEqual(len(excluded_ids), 2)
        # 除外後の評価採用30件を作る
        test_rows = [
            # 除外されていない候補を採用する
            row
            # 候補32件を順番に処理する
            for row in candidate_rows
            # 指定された2件を除く
            if row["expression_id"] not in excluded_ids
        ]
        # 評価採用件数を確認する
        self.assertEqual(len(test_rows), 30)
        # 除外した本文が指定と異なる2表現であることを確認する
        self.assertEqual(
            {
                row["expression_ja"]
                for row in candidate_rows
                if row["expression_id"] in excluded_ids
            },
            {"各要素を2倍にする", "全部を三倍する"},
        )
        # 指定どおり残す2表現が評価対象に存在することを確認する
        self.assertTrue(
            {"各要素を二倍にする", "全部を3倍する"}
            <= {row["expression_ja"] for row in test_rows}
        )
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
        # 候補32件の表現組がtrain側と完全一致しないことを確認する
        self.assertTrue(
            all(
                (row["expression_ja"], row["connective_expression_ja"])
                not in train_pairs
                for row in candidate_rows
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
        # 評価採用30件を一件ずつ処理する
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
                    **{
                        operation_id: 1
                        for operation_id in operation_ast_by_id
                        if operation_id
                        not in {
                            "atomic-000001",
                            "atomic-000002",
                            "atomic-000003",
                            "atomic-000013",
                        }
                    },
                }
            ),
        )
        # 表現一件につき一文なので、予定する評価指示数が30件になる
        self.assertEqual(sum(counts.values()), 30)
        # Git管理する言い換え評価ZIPのパスを作る
        archive_path = (
            PROJECT_ROOT
            / "data/archives/paraphrase_test_instructions_2026-09-24.zip"
        )
        # ZIP内の固定JSONLパスを定義する
        archive_member = "data/instructions/paraphrase_test_instructions.jsonl"
        # ZIPを読み取り専用で開く
        with zipfile.ZipFile(archive_path) as archive:
            # ZIP内JSONLをUTF-8文字列へ戻す
            archived_text = archive.read(archive_member).decode("utf-8")
        # 空行を除いて生成済みレコードを解析する
        instruction_rows = [
            # 現在行をJSONオブジェクトへ変換する
            json.loads(line)
            # JSONLを一行ずつ処理する
            for line in archived_text.splitlines()
            # 空行は読み飛ばす
            if line.strip()
        ]
        # ZIPが30件の評価指示を含むことを確認する
        self.assertEqual(len(instruction_rows), 30)
        # 表現IDから元のテスト専用表現を引く対応表を作る
        expression_by_id = {
            # 表現IDをキーに元レコードを保存する
            row["expression_id"]: row
            # 評価採用30表現を処理する
            for row in test_rows
        }
        # kを明示的な入力に持つ操作ID集合を定義する
        k_operation_ids = {
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
        # 生成済み30レコードを一件ずつ検査する
        for record in instruction_rows:
            # 各文がテスト用の単独操作レコードであることを確認する
            self.assertEqual(record["split"], "test")
            # テスト集合が言い換え評価であることを確認する
            self.assertEqual(record["test_suite"], "paraphrase")
            # 辞書区分がtest_onlyであることを確認する
            self.assertEqual(record["dictionary"], "test_only")
            # 一つの表現IDだけが使われることを確認する
            self.assertEqual(len(record["expression_ids"]), 1)
            # 一つの操作IDだけが使われることを確認する
            self.assertEqual(len(record["operation_ids"]), 1)
            # 意味ASTの操作列長が1であることを確認する
            self.assertEqual(len(record["semantic_ast"]["sequence"]), 1)
            # 使用表現IDに対応する元表現を取得する
            source_expression = expression_by_id[record["expression_ids"][0]]
            # 使用操作IDが元表現の操作IDと一致することを確認する
            self.assertEqual(
                record["operation_ids"][0], source_expression["operation_id"]
            )
            # CSV側だけ文字列になっている操作ASTを辞書へ戻す
            expected_operation_ast = source_expression["operation_ast"]
            # 文字列ならJSONとして解析する
            if isinstance(expected_operation_ast, str):
                # 比較可能な操作AST辞書にする
                expected_operation_ast = json.loads(expected_operation_ast)
            # 意味ASTが元表現の単独操作だけを含むことを確認する
            self.assertEqual(
                record["semantic_ast"]["sequence"], [expected_operation_ast]
            )
            # kを使う操作かどうかを判定する
            requires_k = source_expression["operation_id"] in k_operation_ids
            # k有無に対応する外側テンプレートで期待全文を作る
            expected_instruction = (
                "整数リストxsと整数kを受け取り、"
                if requires_k
                else "整数リストxsから"
            ) + source_expression["expression_ja"] + "solve関数を書いてください。"
            # 完成全文が終止形を一度だけ使う期待文と一致することを確認する
            self.assertEqual(record["instruction_ja"], expected_instruction)
        # 30個の表現IDがZIP内で一度ずつ使われることを確認する
        self.assertEqual(
            {record["expression_ids"][0] for record in instruction_rows},
            set(expression_by_id),
        )


# 直接実行された場合だけ単体テストを開始する
if __name__ == "__main__":
    # unittest標準のテストランナーを呼び出す
    unittest.main()
