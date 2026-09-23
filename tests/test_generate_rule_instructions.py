"""ルールベース全文指示生成の選択と結合を検証する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# 一時ファイル用ディレクトリを作るために使う
import tempfile

# 単体テストの枠組みを使う
import unittest

# ファイルのパスを扱う
from pathlib import Path

# ZIP内容のハッシュを比較するために使う
import hashlib

# 検証対象の生成関数を読み込む
from scripts.instruction_generation.generate_rule_instructions import (
    # 直積を一巡する選択パラメータを作る
    _affine_permutation_parameters,
    # 一つの意味ASTから全文指示を作る
    _generate_for_ast,
    # 固定メタデータのZIPを作る
    _write_deterministic_zip,
)


# 関連する検査をまとめるクラスを定義する
class RuleInstructionGenerationTests(unittest.TestCase):
    """表現組の選択、接続、ZIP再現性を確認する。"""

    # この工程を担当するテストを定義する
    def test_affine_parameters_visit_every_combination_once(self) -> None:
        """アフィン置換が直積インデックスを重複なく一巡する。"""

        # 12通りの直積に対する開始位置と歩幅を得る
        offset, step = _affine_permutation_parameters(7, "spec-1", "{}", 12)
        # 12回の巡回結果を集合にする
        visited = {(offset + index * step) % 12 for index in range(12)}
        # 0から11までを一度ずつ訪れることを確認する
        self.assertEqual(visited, set(range(12)))

    # この工程を担当するテストを定義する
    def test_repeated_operation_keeps_unique_text_and_correct_forms(self) -> None:
        """同一操作の反復でも接続形と終止形を使い分けて重複を除く。"""

        # 二つの辞書レコードが同じ終止形と異なる接続形を持つ例を作る
        expressions = {
            "atomic-000001": [
                {
                    "expression_id": "expr-a",
                    "operation_id": "atomic-000001",
                    "operation_ast": {"filter": ["even"]},
                    "expression_ja": "偶数を残す",
                    "connective_expression_ja": "偶数を残し",
                },
                {
                    "expression_id": "expr-b",
                    "operation_id": "atomic-000001",
                    "operation_ast": {"filter": ["even"]},
                    "expression_ja": "偶数を残す",
                    "connective_expression_ja": "偶数を選んで",
                },
            ]
        }
        # 同じ操作を二回適用する意味ASTを作る
        source = {
            "spec_id": "repetition-test",
            "semantic_ast": {"sequence": [{"filter": ["even"]}, {"filter": ["even"]}]},
            "resolved_split": "test",
            "test_suite": "repetition",
        }
        # テスト用の固定設定を作る
        settings = {
            "maximum_instructions_per_ast": 20,
            "generator_seed": 7,
            "generator_version": "1",
            "sentence_templates": {
                "without_k": {
                    "template_id": "without-k",
                    "text": "整数リストxsから{operations}solve関数を書いてください。",
                },
                "with_k": {
                    "template_id": "with-k",
                    "text": "整数リストxsと整数kを受け取り、{operations}solve関数を書いてください。",
                },
            },
        }
        # 反復ASTの全文指示を生成する
        records = _generate_for_ast(source, expressions, "dictionary-v1", settings)
        # 接続形2種類と終止形1種類から固有全文が2件になることを確認する
        self.assertEqual(len(records), 2)
        # 全文が互いに異なることを確認する
        self.assertEqual(len({record["instruction_ja"] for record in records}), 2)
        # 末尾操作が終止形になることを確認する
        self.assertTrue(
            all(
                "、偶数を残すsolve関数" in record["instruction_ja"]
                for record in records
            )
        )
        # test_onlyではなくtrain辞書として記録されることを確認する
        self.assertTrue(all(record["dictionary"] == "train" for record in records))

    # この工程を担当するテストを定義する
    def test_zip_output_is_deterministic(self) -> None:
        """同じJSONLから作るZIPのバイト列が毎回一致する。"""

        # 一時ディレクトリを自動的に後片付けする
        with tempfile.TemporaryDirectory() as directory:
            # 一時ディレクトリをPathへ変換する
            root = Path(directory)
            # 小さな入力JSONLを作る
            source = root / "input.jsonl"
            # UTF-8の日本語を含む一行を書き込む
            source.write_text('{"instruction_ja":"偶数を残す"}\n', encoding="utf-8")
            # 同じ入力から二つのZIPを作る
            first = root / "first.zip"
            # 比較対象となる二つ目のZIPパスを作る
            second = root / "second.zip"
            # 一つ目の決定的ZIPを生成する
            _write_deterministic_zip(source, first, "data/input.jsonl")
            # 二つ目の決定的ZIPを生成する
            _write_deterministic_zip(source, second, "data/input.jsonl")
            # 二つのZIPのSHA-256が同じことを確認する
            self.assertEqual(
                hashlib.sha256(first.read_bytes()).hexdigest(),
                hashlib.sha256(second.read_bytes()).hexdigest(),
            )


# 直接実行された場合だけ単体テストを開始する
if __name__ == "__main__":
    # unittest標準のテストランナーを呼び出す
    unittest.main()
