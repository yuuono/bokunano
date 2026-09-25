"""validation・hidden・boundary評価入力の生成処理を検証する。"""

# JSONとJSONLのテスト入力を作るために使う
import json
# 一時ディレクトリ内のパスを扱うために使う
from pathlib import Path
# 一時ディレクトリを安全に作成・削除するために使う
import tempfile
# 標準ライブラリだけでテストを自動検出するために使う
import unittest

# 評価入力生成処理と補助関数を読み込む
from scripts.validation.generate_evaluation_input_sets import (
    build_targeted_filter_case,
    case_key,
    generate_evaluation_input_sets,
    generate_random_cases,
)


# 評価入力生成の振舞いをまとめて検証するクラスを定義する
class EvaluationInputGenerationTest(unittest.TestCase):
    """決定性、集合分離、境界条件、入力不変を確認する。"""

    # 同じseedから同じケースが得られることを検証する
    def test_random_cases_are_deterministic_and_disjoint(self) -> None:
        """build除外集合を避けながら再現可能な入力を作る。"""

        # build入力に相当する除外ケースを作る
        excluded = {case_key([], 1), case_key([0], 1)}
        # 一回目のケースを生成する
        first = generate_random_cases(
            name="normal", seed=1234, count=16, forbidden_keys=set(excluded)
        )
        # 二回目も同じ初期条件で生成する
        second = generate_random_cases(
            name="normal", seed=1234, count=16, forbidden_keys=set(excluded)
        )
        # 全内容が一致することを確認する
        self.assertEqual(first, second)
        # 集合内に完全重複がないことを確認する
        keys = {case_key(case["xs"], case["k"]) for case in first}
        # 16件すべてが固有であることを確認する
        self.assertEqual(len(keys), 16)
        # build除外ケースと重ならないことを確認する
        self.assertTrue(keys.isdisjoint(excluded))

    # 先行変換後のfilterでも全要素不合格ケースを作れることを検証する
    def test_builds_targeted_all_rejected_case_after_map(self) -> None:
        """最初のfilterが2操作目でもfilter直前非空・直後空を満たす。"""

        # 二乗後に負数だけを残す意味ASTを作る
        semantic_ast = {
            "sequence": [
                {"map": ["square"]},
                {"filter": ["negative"]},
            ]
        }
        # AST固有境界ケースを生成する
        case = build_targeted_filter_case(
            spec_id="spec-map-filter",
            semantic_ast=semantic_ast,
            forbidden_keys=set(),
        )
        # filterを含むのでケースが作られたことを確認する
        self.assertIsNotNone(case)
        # 型検査器と実行時の双方へNoneでないことを示す
        assert case is not None
        # 対象位置が2操作目であることを確認する
        self.assertEqual(case["target_operation_index"], 1)
        # 対象filter名を確認する
        self.assertEqual(case["target_filter"], "negative")

    # 前段操作によりfilterが必ず通過する場合を検証する
    def test_reports_unreachable_all_rejected_condition(self) -> None:
        """有効な全singletonが通過するASTでは不可能なケースを捏造しない。"""

        # 二乗、符号反転後の値は常に0以下なのでk未満を必ず通過する
        semantic_ast = {
            "sequence": [
                {"map": ["square"]},
                {"map": ["negate"]},
                {"filter": ["lt_k"]},
            ]
        }
        # 全要素不合格ケースを探索する
        case = build_targeted_filter_case(
            spec_id="spec-unreachable",
            semantic_ast=semantic_ast,
            forbidden_keys=set(),
        )
        # 仕様内では作れないためNoneになることを確認する
        self.assertIsNone(case)

    # 小さな6集合を最後まで生成する統合経路を検証する
    def test_generates_six_manifests_and_stats(self) -> None:
        """5ランダム集合とboundary集合を生成して全ASTで参照実行する。"""

        # テスト専用一時ディレクトリを作る
        with tempfile.TemporaryDirectory() as temporary_directory:
            # 一時パスをPathへ変換する
            root = Path(temporary_directory)
            # filterありとfilterなしの2意味ASTを作る
            semantic_records = [
                {
                    "spec_id": "spec-even",
                    "semantic_ast": {"sequence": [{"filter": ["even"]}]},
                },
                {
                    "spec_id": "spec-add",
                    "semantic_ast": {"sequence": [{"map": ["add_k"]}]},
                },
            ]
            # 全集合で使う小さな意味AST JSONLを保存する
            semantic_path = root / "semantic.jsonl"
            # 一行JSONとして保存する
            semantic_path.write_text(
                "".join(json.dumps(record) + "\n" for record in semantic_records),
                encoding="utf-8",
            )
            # build入力manifestを保存する
            build_path = root / "build.json"
            # 一件だけのbuildケースを保存する
            build_path.write_text(
                json.dumps({"cases": [{"case_id": "build-1", "xs": [], "k": 1}]}),
                encoding="utf-8",
            )
            # 5ランダム集合設定を作る
            random_sets = []
            # 固定された5集合名を順番に処理する
            for index, name in enumerate(
                ["validation", "normal", "compositional", "paraphrase", "repetition"],
                start=1,
            ):
                # 集合設定を追加する
                random_sets.append(
                    {
                        "name": name,
                        "test_set_id": f"{name}-set",
                        "semantic_asts": str(semantic_path),
                        "expected_semantic_ast_count": 2,
                        "output": str(root / f"{name}.json"),
                        "split": "val" if name == "validation" else "test",
                        "test_suite": None if name == "validation" else name,
                        "input_set": "build" if name == "validation" else "hidden",
                        "random_seed": 1000 + index,
                        "case_count": 8,
                    }
                )
            # 全体設定を作る
            config = {
                "config_version": 1,
                "generator_version": "1",
                "reference": "reference_interpreter.py",
                "exclude_build_test_set": str(build_path),
                "stats": str(root / "stats.json"),
                "random_sets": random_sets,
                "boundary_set": {
                    "name": "boundary",
                    "test_set_id": "boundary-set",
                    "semantic_asts": str(semantic_path),
                    "expected_semantic_ast_count": 2,
                    "output": str(root / "boundary.json"),
                    "split": "test",
                    "test_suite": "boundary",
                    "input_set": "boundary",
                    "shared_cases": [
                        {"xs": [], "k": 10, "tags": ["empty"]},
                        {"xs": [0], "k": 10, "tags": ["singleton", "zero"]},
                    ],
                },
            }
            # 設定JSONを保存する
            config_path = root / "config.json"
            # 読みやすいJSONとして保存する
            config_path.write_text(json.dumps(config), encoding="utf-8")
            # 6入力集合を生成する
            result = generate_evaluation_input_sets(config_path=config_path, overwrite=False)
            # 6集合の集計が存在することを確認する
            self.assertEqual(set(result["sets"]), {
                "validation",
                "normal",
                "compositional",
                "paraphrase",
                "repetition",
                "boundary",
            })
            # 5ランダム集合が各8件であることを確認する
            self.assertEqual(result["random_evaluation_case_count"], 40)
            # boundaryにfilter AST固有ケースが一件あることを確認する
            self.assertEqual(result["sets"]["boundary"]["targeted_filter_case_count"], 1)
            # build入力との重複が0であることを確認する
            self.assertEqual(result["random_case_overlap_with_build"], 0)
            # 集計JSONが保存されたことを確認する
            self.assertTrue((root / "stats.json").is_file())


# このファイルを直接実行した場合だけテストを開始する
if __name__ == "__main__":
    # unittestの標準runnerを起動する
    unittest.main()
