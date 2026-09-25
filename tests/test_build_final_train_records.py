"""日本語指示と検証済みコードの最終結合を検証する。"""

# JSONとJSONLのテスト入力を作るために使う
import json
# 一時ディレクトリ内のパスを扱うために使う
from pathlib import Path
# 一時ディレクトリを安全に作成・削除するために使う
import tempfile
# 標準ライブラリだけでテストを自動検出するために使う
import unittest
# 2・3操作コード候補と最終成果物のZIPを扱うために使う
import zipfile

# 最終結合処理と共通ハッシュ関数を読み込む
from scripts.instruction_generation.build_final_train_records import (
    ARCHIVE_MEMBER,
    THREE_OPERATION_MEMBER,
    TWO_OPERATION_MEMBER,
    build_final_train_records,
    canonical_json,
    text_sha256,
)


# 最終結合の振舞いをまとめて検証するクラスを定義する
class FinalTrainRecordsTest(unittest.TestCase):
    """一対一結合、不足コード分離、ZIP、入力不変を確認する。"""

    # 通常ASTと指示不足ASTを含む小さな結合を検証する
    def test_builds_final_records_and_preserves_rejected_code_provenance(self) -> None:
        """全指示を使い、余るコードだけを完全な来歴付きで分離する。"""

        # テスト専用一時ディレクトリを作る
        with tempfile.TemporaryDirectory() as temporary_directory:
            # 一時パスをPathへ変換する
            root = Path(temporary_directory)
            # 各入出力パスを作る
            instructions_path = root / "instructions.jsonl"
            # 1操作コード入力パスを作る
            single_codes_path = root / "single.jsonl"
            # 空の2・3操作メンバーを持つZIPパスを作る
            multi_archive_path = root / "multi.zip"
            # 最終JSONLパスを作る
            output_path = root / "final.jsonl"
            # 最終ZIPパスを作る
            archive_path = root / "final.zip"
            # 不採用コードJSONLパスを作る
            rejected_path = root / "rejected.jsonl"
            # テスト集合manifestパスを作る
            manifest_path = root / "tests.json"
            # 集計JSONパスを作る
            stats_path = root / "stats.json"
            # 一件目の意味ASTを作る
            first_ast = {"sequence": [{"filter": ["even"]}]}
            # 二件目の意味ASTを作る
            second_ast = {"sequence": [{"map": ["add_k"]}]}
            # 指示3件を同一spec_id連続で作る
            instructions = [
                _instruction("instruction-1", "spec-1", first_ast, "偶数だけ残してください。"),
                _instruction("instruction-2", "spec-1", first_ast, "偶数を抽出してください。"),
                _instruction("instruction-3", "spec-2", second_ast, "各値にkを足してください。"),
            ]
            # コード4件を同一spec_id連続で作る
            codes = [
                _code("code-1", "spec-1", first_ast, "expression_comprehension", "return [x for x in xs if x % 2 == 0]"),
                _code("code-2", "spec-1", first_ast, "staged_loop", "return list(filter(lambda x: x % 2 == 0, xs))"),
                _code("code-3", "spec-2", second_ast, "expression_comprehension", "return [x + k for x in xs]"),
                _code("code-4", "spec-2", second_ast, "staged_loop", "return list(map(lambda x: x + k, xs))"),
            ]
            # 指示JSONLを保存する
            _write_jsonl(instructions_path, instructions)
            # 1操作コードJSONLを保存する
            _write_jsonl(single_codes_path, codes)
            # 必須2・3操作メンバーを空で保存する
            with zipfile.ZipFile(multi_archive_path, mode="w") as multi_archive:
                # 2操作メンバーを追加する
                multi_archive.writestr(TWO_OPERATION_MEMBER, "")
                # 3操作メンバーを追加する
                multi_archive.writestr(THREE_OPERATION_MEMBER, "")
            # 処理前の入力バイト列を保存する
            input_bytes_before = (
                instructions_path.read_bytes(),
                single_codes_path.read_bytes(),
                multi_archive_path.read_bytes(),
            )
            # 小さな最終訓練集合を生成する
            result = build_final_train_records(
                instructions=instructions_path,
                single_operation_codes=single_codes_path,
                multi_operation_code_archive=multi_archive_path,
                output_jsonl=output_path,
                archive=archive_path,
                rejected_codes=rejected_path,
                test_set_manifest=manifest_path,
                stats=stats_path,
                expected_record_count=3,
                expected_code_count=4,
                pairing_seed=20260925,
                overwrite=False,
            )
            # 元入力が処理後も同一であることを確認する
            self.assertEqual(
                (
                    instructions_path.read_bytes(),
                    single_codes_path.read_bytes(),
                    multi_archive_path.read_bytes(),
                ),
                input_bytes_before,
            )
            # 最終3件を読み込む
            final_records = _read_jsonl(output_path)
            # 全指示が一度ずつ出力されたことを確認する
            self.assertEqual(
                [record["instruction_id"] for record in final_records],
                ["instruction-1", "instruction-2", "instruction-3"],
            )
            # 最終レコードにコードと指示の追跡IDがあることを確認する
            self.assertTrue(all(record["record_id"].startswith("record-") for record in final_records))
            # 最終レコードに共有テスト集合参照があることを確認する
            self.assertTrue(all(len(record["tests"]) == 1 for record in final_records))
            # 指示不足specから一件だけが不採用になったことを確認する
            rejected_records = _read_jsonl(rejected_path)
            # 不採用件数を確認する
            self.assertEqual(len(rejected_records), 1)
            # 不採用理由を確認する
            self.assertEqual(rejected_records[0]["reason"], "instruction_shortfall")
            # 元コード本文が不採用記録にも残ることを確認する
            self.assertIn("reference_code", rejected_records[0])
            # 元style_specが不採用記録にも残ることを確認する
            self.assertIn("style_spec", rejected_records[0])
            # 検証入力が境界9件とランダム32件であることを確認する
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            # 合計41件を確認する
            self.assertEqual(manifest["case_count"], 41)
            # ZIP内JSONLがローカルJSONLと同一であることを確認する
            with zipfile.ZipFile(archive_path) as final_archive:
                # 固定名一件だけが格納されていることを確認する
                self.assertEqual(final_archive.namelist(), [ARCHIVE_MEMBER])
                # ZIP展開内容を照合する
                self.assertEqual(final_archive.read(ARCHIVE_MEMBER), output_path.read_bytes())
            # 集計が3採用・1不採用を示すことを確認する
            self.assertEqual(result["selected_code_count"], 3)
            # 不採用件数も確認する
            self.assertEqual(result["rejected_code_count"], 1)
            # 入力不変検証結果を確認する
            self.assertTrue(result["source_inputs_unchanged"])

    # 意味ASTが異なる指示とコードを拒否することを検証する
    def test_rejects_semantic_ast_mismatch(self) -> None:
        """spec_idだけが同じでも意味ASTが異なる結合を許可しない。"""

        # テスト専用一時ディレクトリを作る
        with tempfile.TemporaryDirectory() as temporary_directory:
            # 一時パスをPathへ変換する
            root = Path(temporary_directory)
            # 指示側ASTを作る
            instruction_ast = {"sequence": [{"filter": ["even"]}]}
            # コード側ASTを別操作で作る
            code_ast = {"sequence": [{"filter": ["odd"]}]}
            # 指示JSONLを保存する
            _write_jsonl(
                root / "instructions.jsonl",
                [_instruction("instruction-1", "spec-1", instruction_ast, "偶数を残してください。")],
            )
            # コードJSONLを保存する
            _write_jsonl(
                root / "single.jsonl",
                [_code("code-1", "spec-1", code_ast, "staged_loop", "return xs")],
            )
            # 空の複数操作コードZIPを作る
            with zipfile.ZipFile(root / "multi.zip", mode="w") as multi_archive:
                # 2操作メンバーを追加する
                multi_archive.writestr(TWO_OPERATION_MEMBER, "")
                # 3操作メンバーを追加する
                multi_archive.writestr(THREE_OPERATION_MEMBER, "")
            # 意味AST不一致エラーを期待する
            with self.assertRaisesRegex(ValueError, "semantic_astが不一致"):
                # 不正な入力を結合する
                build_final_train_records(
                    instructions=root / "instructions.jsonl",
                    single_operation_codes=root / "single.jsonl",
                    multi_operation_code_archive=root / "multi.zip",
                    output_jsonl=root / "final.jsonl",
                    archive=root / "final.zip",
                    rejected_codes=root / "rejected.jsonl",
                    test_set_manifest=root / "tests.json",
                    stats=root / "stats.json",
                    expected_record_count=1,
                    expected_code_count=1,
                    pairing_seed=20260925,
                    overwrite=False,
                )


# テスト用指示レコードを作る関数を定義する
def _instruction(
    instruction_id: str,
    spec_id: str,
    semantic_ast: dict[str, object],
    instruction_ja: str,
) -> dict[str, object]:
    """実データで必要な訓練指示項目を持つレコードを返す。"""

    # ルール生成指示レコードを返す
    return {
        "instruction_id": instruction_id,
        "spec_id": spec_id,
        "semantic_ast": semantic_ast,
        "split": "train",
        "test_suite": None,
        "instruction_ja": instruction_ja,
        "instruction_source": "rule",
        "dictionary": "train",
        "dictionary_version": "dictionary-version",
        "expression_ids": [f"expr-{instruction_id}"],
        "sentence_template_id": "sentence-template",
        "generator_version": "1",
        "generator_seed": 0,
        "teacher_model": None,
        "teacher_revision": None,
        "prompt_hash": None,
        "text_hash": text_sha256(instruction_ja),
        "replacement_status": "rule_retained",
        "retention_reason": "not_selected_for_teacher_paraphrase",
        "source_instruction_id": None,
        "source_instruction_ja": None,
        "source_text_hash": None,
        "replacement_mode": "retain_rule_instruction",
    }


# テスト用コード候補レコードを作る関数を定義する
def _code(
    code_id: str,
    spec_id: str,
    semantic_ast: dict[str, object],
    code_style: str,
    body: str,
) -> dict[str, object]:
    """実データと同じハッシュ・検証項目を持つコード候補を返す。"""

    # solve関数本文を作る
    reference_code = f"def solve(xs: list[int], k: int) -> list[int]:\n    {body}\n"
    # コード候補レコードを返す
    return {
        "code_id": code_id,
        "spec_id": spec_id,
        "semantic_ast": semantic_ast,
        "reference_code": reference_code,
        "code_style": code_style,
        "style_id": f"style-{code_id}",
        "style_spec": {"code_style": code_style},
        "rewrite_id": None,
        "split": "train",
        "test_suite": None,
        "semantic_hash": text_sha256(canonical_json(semantic_ast)),
        "code_hash": text_sha256(reference_code),
        "generator_version": "1",
        "generator_seed": 0,
        "verification": {
            "syntax_ok": True,
            "ast_safe": True,
            "signature_ok": True,
            "tests_passed": True,
            "input_unchanged": True,
            "timeout": False,
            "error": None,
        },
    }


# JSONLを書き出すテスト補助関数を定義する
def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    """レコード一覧を決定的な一行JSONとして保存する。"""

    # 一行JSONを改行で結合して保存する
    path.write_text(
        "".join(canonical_json(record) + "\n" for record in records),
        encoding="utf-8",
    )


# JSONLを読み込むテスト補助関数を定義する
def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """テスト成果物の非空行をJSON object一覧として返す。"""

    # 非空行だけを解析して返す
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


# このファイルを直接実行した場合だけテストを開始する
if __name__ == "__main__":
    # unittestの標準runnerを起動する
    unittest.main()
