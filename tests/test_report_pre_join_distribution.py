"""結合前分布レポートの置換件数計算を検証する。"""

# 標準ライブラリだけでテストを自動検出するために使う
import unittest

# テスト対象を読み込むために使う
from scripts.instruction_generation.report_pre_join_distribution import build_summary


# テスト用の意味AST別集計を作る関数を定義する
def make_spec(
    # 意味AST IDを受け取る
    spec_id: str,
    # 置換前指示数を受け取る
    rule_count: int,
    # 教師置換成功数を受け取る
    replacement_count: int,
    # 教師置換失敗数を受け取る
    failure_count: int,
    # 検証済みコード数を受け取る
    code_count: int = 20,
# 意味AST別集計を返す
) -> dict[str, object]:
    """実データと同じ必須項目を持つテスト集計を返す。"""

    # 単一操作の意味ASTを作る
    semantic_ast = {"sequence": [{"filter": ["even"]}]}
    # テスト対象へ渡す集計を返す
    return {
        # 意味AST IDを保存する
        "spec_id": spec_id,
        # 意味AST本体を保存する
        "semantic_ast": semantic_ast,
        # 比較用文字列を保存する
        "semantic_key": '{"sequence":[{"filter":["even"]}]}',
        # 操作数を保存する
        "operation_count": 1,
        # 置換前指示数を保存する
        "rule_instruction_count": rule_count,
        # 教師置換成功数を保存する
        "teacher_replacement_count": replacement_count,
        # 教師置換失敗数を保存する
        "teacher_failure_count": failure_count,
        # コード数を保存する
        "code_count": code_count,
    }


# 結合前分布計算をまとめて検証するクラスを定義する
class PreJoinDistributionTest(unittest.TestCase):
    """教師置換とコード分布の検査を確認する。"""

    # 教師言い換えを追加せず置換として数えることを検証する
    def test_build_summary_keeps_instruction_count_after_replacement(self) -> None:
        """置換成功数を足して最終指示数を増やさない。"""

        # 20件のうち10件を置換した意味ASTを作る
        specs = {"spec-1": make_spec("spec-1", 20, 10, 0)}
        # 教師生成全体件数を作る
        teacher_stats = {
            # 選抜した元指示数を保存する
            "selected_source_count": 10,
            # 承認済み候補数を保存する
            "candidate_count": 10,
            # 失敗数を保存する
            "failure_count": 0,
            # 対象意味AST数を保存する
            "selected_source_ast_count": 1,
            # 意味AST当たり選抜数を保存する
            "source_instructions_per_ast": 10,
        }
        # 分布を集計する
        summary = build_summary(specs, teacher_stats, 20, "2026-09-25")
        # 置換後も指示総数が20件であることを確認する
        self.assertEqual(summary["final_instruction_count_after_replacement"], 20)
        # 教師言い換えが10件であることを確認する
        self.assertEqual(summary["teacher_replacement_count"], 10)
        # 元のルール生成指示が10件残ることを確認する
        self.assertEqual(summary["retained_rule_instruction_count"], 10)
        # 指示数とコード数が一致することを確認する
        self.assertEqual(summary["instruction_minus_code"], 0)

    # コード数が意味AST当たり20件でない入力を拒否することを検証する
    def test_build_summary_rejects_non_twenty_code_count(self) -> None:
        """結合前提と異なるコード分布を見逃さない。"""

        # 19コードしかない不正な意味ASTを作る
        specs = {"spec-1": make_spec("spec-1", 20, 10, 0, code_count=19)}
        # 教師生成全体件数を作る
        teacher_stats = {
            # 選抜した元指示数を保存する
            "selected_source_count": 10,
            # 承認済み候補数を保存する
            "candidate_count": 10,
            # 失敗数を保存する
            "failure_count": 0,
            # 対象意味AST数を保存する
            "selected_source_ast_count": 1,
            # 意味AST当たり選抜数を保存する
            "source_instructions_per_ast": 10,
        }
        # 期待する検査エラーを確認する
        with self.assertRaisesRegex(ValueError, "コード数が20件ではありません"):
            # 不正なコード数で集計を実行する
            build_summary(specs, teacher_stats, 19, "2026-09-25")
