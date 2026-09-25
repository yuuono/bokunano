"""評価用最終レコードのID、参照、決定的ZIPを検証する。"""

# JSONL確認用にJSONを読み込む
import json
# 一時ディレクトリ内のパスを扱う
from pathlib import Path
# 一時ディレクトリを安全に作成・削除する
import tempfile
# 標準ライブラリだけでテストを自動検出する
import unittest
# 評価成果物ZIPの内容を検査する
import zipfile

# 評価最終結合の対象関数と共通ハッシュ関数を読み込む
from scripts.instruction_generation.build_final_evaluation_records import (
    OUTPUT_FILENAMES,
    make_evaluation_record,
    validate_evaluation_record,
    write_deterministic_archive,
)
# 意味・本文ハッシュ作成に使う共通関数を読み込む
from scripts.instruction_generation.build_final_train_records import (
    canonical_json,
    text_sha256,
)


# 評価最終結合の小さな単体テストをまとめる
class FinalEvaluationRecordsTest(unittest.TestCase):
    """レコード生成とZIP再現性を確認する。"""

    # 一件のnormalレコードが追跡可能な形で作られることを検証する
    def test_makes_traceable_normal_record(self) -> None:
        """指示とコードを結合し、テスト参照とIDを再検査できる。"""

        # 一操作の意味ASTを作る
        semantic_ast = {"sequence": [{"filter": ["even"]}]}
        # 評価指示を作る
        instruction = _instruction(semantic_ast)
        # 対応する検証済みコードを作る
        code = _code(semantic_ast)
        # normal最終レコードを作る
        record = make_evaluation_record(
            instruction=instruction,
            code=code,
            split="test",
            test_suite="normal",
            dictionary="train",
            input_set="hidden",
            test_set_id="normal-hidden-v1",
            pairing_seed=20260925,
            pairing_strategy="source_order_one_to_one_within_semantic_ast",
        )
        # 作成レコードを本番と同じ検査へ通す
        validate_evaluation_record(
            record,
            split="test",
            test_suite="normal",
            dictionary="train",
            input_set="hidden",
            test_set_id="normal-hidden-v1",
        )
        # 評価入力はID参照だけであることを確認する
        self.assertEqual(record["tests"], ["normal-hidden-v1"])
        # 指示とコードの元IDが維持されることを確認する
        self.assertEqual(record["instruction_id"], "instruction-1")
        # コードIDも維持されることを確認する
        self.assertEqual(record["code_id"], "code-1")
        # コード検証結果が最終レコードへ残ることを確認する
        self.assertTrue(record["verification"]["tests_passed"])

    # 同じ6ファイルから同じバイト列のZIPが作られることを検証する
    def test_writes_deterministic_six_member_archive(self) -> None:
        """メンバー順・内容・ZIPバイト列を固定する。"""

        # テスト専用一時ディレクトリを作る
        with tempfile.TemporaryDirectory() as temporary_directory:
            # 一時パスをPathへ変換する
            root = Path(temporary_directory)
            # 6集合の入力パス対応を作る
            output_paths = {}
            # 公開順に小さなJSONLを作る
            for suite_name, filename in OUTPUT_FILENAMES.items():
                # 集合別パスを作る
                path = root / filename
                # 一行のJSONLを書き込む
                path.write_text(
                    json.dumps({"suite": suite_name}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                # 対応表へ追加する
                output_paths[suite_name] = path
            # 同じ入力から二つのZIPを作る
            first_archive = root / "first.zip"
            # 二つ目のZIPパスを作る
            second_archive = root / "second.zip"
            # 一つ目を生成する
            write_deterministic_archive(output_paths, first_archive)
            # 二つ目も生成する
            write_deterministic_archive(output_paths, second_archive)
            # ZIP全体のバイト列が同一であることを確認する
            self.assertEqual(first_archive.read_bytes(), second_archive.read_bytes())
            # ZIPのメンバー順と内容を確認する
            with zipfile.ZipFile(first_archive) as archive:
                # メンバー順を公開順と照合する
                self.assertEqual(archive.namelist(), list(OUTPUT_FILENAMES.values()))
                # CRC検査を通ることを確認する
                self.assertIsNone(archive.testzip())
                # 各メンバーが元JSONLと一致することを確認する
                for suite_name, filename in OUTPUT_FILENAMES.items():
                    # 展開内容を元ファイルと照合する
                    self.assertEqual(archive.read(filename), output_paths[suite_name].read_bytes())


# テスト用評価指示を作る
def _instruction(semantic_ast: dict[str, object]) -> dict[str, object]:
    """normalのルール生成指示に必要な項目を返す。"""

    # 日本語本文を固定する
    instruction_ja = "偶数だけを残してください。"
    # 指示レコードを返す
    return {
        "instruction_id": "instruction-1",
        "spec_id": "combined-000001",
        "semantic_ast": semantic_ast,
        "instruction_ja": instruction_ja,
        "text_hash": text_sha256(instruction_ja),
        "split": "test",
        "test_suite": "normal",
        "dictionary": "train",
        "instruction_source": "rule",
        "teacher_model": None,
        "teacher_revision": None,
        "prompt_hash": None,
        "generator_version": "1",
        "generator_seed": 7,
    }


# テスト用検証済みコードを作る
def _code(semantic_ast: dict[str, object]) -> dict[str, object]:
    """normalコード候補に必要な項目を返す。"""

    # コード本文を固定する
    reference_code = "def solve(xs, k):\n    return [x for x in xs if x % 2 == 0]\n"
    # 検証済みコードレコードを返す
    return {
        "code_id": "code-1",
        "spec_id": "combined-000001",
        "semantic_ast": semantic_ast,
        "semantic_hash": text_sha256(canonical_json(semantic_ast)),
        "reference_code": reference_code,
        "code_hash": text_sha256(reference_code),
        "code_style": "expression_comprehension",
        "style_id": "style-1",
        "style_spec": {"form": "comprehension"},
        "rewrite_id": None,
        "split": "test",
        "test_suite": "normal",
        "generator_version": "1",
        "generator_seed": 9,
        "verification": {
            "syntax_ok": True,
            "ast_safe": True,
            "signature_ok": True,
            "tests_passed": True,
            "input_unchanged": True,
            "timeout": False,
        },
    }


# 直接実行時もテストを走らせる
if __name__ == "__main__":
    # unittestの標準実行を開始する
    unittest.main()
