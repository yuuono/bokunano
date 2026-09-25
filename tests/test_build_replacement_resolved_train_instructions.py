"""教師言い換えを元指示へ一対一置換する処理を検証する。"""

# JSONとJSONLのテスト入力を作るために使う
import json
# 一時ディレクトリを作るために使う
from pathlib import Path
# 一時ディレクトリを安全に削除するために使う
import tempfile
# 標準ライブラリだけでテストを自動検出するために使う
import unittest
# ZIP内JSONLを検査するために使う
import zipfile

# テスト対象の置換処理と本文ハッシュ関数を読み込む
from scripts.instruction_generation.build_replacement_resolved_train_instructions import (
    ARCHIVE_MEMBER,
    build_replacement_resolved_instructions,
    text_sha256,
)


# 置換処理をまとめて検証するクラスを定義する
class ReplacementResolvedInstructionsTest(unittest.TestCase):
    """元入力保持、教師置換、元文維持を確認する。"""

    # 一対一置換と元文維持の全経路を検証する
    def test_builds_replacement_resolved_jsonl_without_changing_inputs(self) -> None:
        """教師成功、教師失敗、非選抜を合計件数を変えず出力する。"""

        # テスト専用一時ディレクトリを作る
        with tempfile.TemporaryDirectory() as temporary_directory:
            # 一時パスをPathへ変換する
            root = Path(temporary_directory)
            # 元ルール生成指示JSONLのパスを作る
            rule_path = root / "rule.jsonl"
            # 承認済み教師言い換えJSONLのパスを作る
            approved_path = root / "approved.jsonl"
            # 教師生成集計JSONのパスを作る
            generation_stats_path = root / "generation_stats.json"
            # 置換済みJSONLのパスを作る
            output_path = root / "resolved.jsonl"
            # ZIPのパスを作る
            archive_path = root / "resolved.zip"
            # 出力集計JSONのパスを作る
            stats_path = root / "resolved_stats.json"
            # 教師置換対象の元指示を作る
            source_replaced = _rule_record("rule-1", "spec-1", "偶数を残してください。")
            # 教師生成失敗で維持する元指示を作る
            source_failure = _rule_record("rule-2", "spec-2", "奇数を残してください。")
            # 教師非選抜で維持する元指示を作る
            source_unselected = _rule_record("rule-3", "spec-3", "値を二倍してください。")
            # 評価用で出力対象外の指示を作る
            source_evaluation = _rule_record(
                "rule-4", "spec-4", "昇順にしてください。", split="val"
            )
            # 元ルール生成JSONLを保存する
            _write_jsonl(
                rule_path,
                [source_replaced, source_failure, source_unselected, source_evaluation],
            )
            # 教師置換レコードを作る
            teacher = _teacher_record(source_replaced, "偶数だけを抽出してください。")
            # 承認済み教師JSONLを保存する
            _write_jsonl(approved_path, [teacher])
            # 教師生成集計JSONを保存する
            generation_stats_path.write_text(
                # 成功1件と失敗1件の集計をJSON化する
                json.dumps(
                    {
                        "selected_source_count": 2,
                        "candidate_count": 1,
                        "failure_count": 1,
                        "failures": [
                            {
                                "source_instruction_id": "rule-2",
                                "reason": "固有の言い換え候補を取得できませんでした",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                # UTF-8で保存する
                encoding="utf-8",
            )
            # 処理前の元入力バイト列を保存する
            rule_bytes_before = rule_path.read_bytes()
            # 処理前の教師入力バイト列を保存する
            approved_bytes_before = approved_path.read_bytes()
            # 置換済み訓練指示を生成する
            result = build_replacement_resolved_instructions(
                # 元ルール生成指示を渡す
                rule_instructions=rule_path,
                # 承認済み教師言い換えを渡す
                approved_paraphrases=approved_path,
                # 教師生成集計を渡す
                paraphrase_generation_stats=generation_stats_path,
                # 置換済みJSONLの保存先を渡す
                output_jsonl=output_path,
                # ZIPの保存先を渡す
                archive=archive_path,
                # 集計JSONの保存先を渡す
                stats=stats_path,
                # 訓練用3件を期待する
                expected_output_count=3,
                # 教師置換1件を期待する
                expected_replacement_count=1,
                # 新規出力なので上書きを無効にする
                overwrite=False,
            )
            # 処理後も元ルール生成JSONLが同じであることを確認する
            self.assertEqual(rule_path.read_bytes(), rule_bytes_before)
            # 処理後も承認済み教師JSONLが同じであることを確認する
            self.assertEqual(approved_path.read_bytes(), approved_bytes_before)
            # 置換済み3レコードを読み込む
            records = _read_jsonl(output_path)
            # 評価用を除く3件だけが出力されたことを確認する
            self.assertEqual(len(records), 3)
            # 元順序が維持されていることを確認する
            self.assertEqual([record["spec_id"] for record in records], ["spec-1", "spec-2", "spec-3"])
            # 教師置換された先頭レコードを取得する
            replaced = records[0]
            # 教師文へ置き換わったことを確認する
            self.assertEqual(replaced["instruction_ja"], "偶数だけを抽出してください。")
            # 元指示IDが保存されたことを確認する
            self.assertEqual(replaced["source_instruction_id"], "rule-1")
            # 元文が保存されたことを確認する
            self.assertEqual(replaced["source_instruction_ja"], "偶数を残してください。")
            # 元文ハッシュが保存されたことを確認する
            self.assertEqual(replaced["source_text_hash"], source_replaced["text_hash"])
            # 元の表現IDが保持されたことを確認する
            self.assertEqual(replaced["expression_ids"], ["expr-rule-1"])
            # 教師モデル来歴が保持されたことを確認する
            self.assertEqual(replaced["teacher_model"], "teacher-model")
            # 教師失敗レコードが元文維持になったことを確認する
            self.assertEqual(records[1]["replacement_status"], "rule_retained")
            # 教師失敗理由が保存されたことを確認する
            self.assertEqual(records[1]["retention_reason"], "teacher_paraphrase_unavailable")
            # 非選抜レコードが元文維持になったことを確認する
            self.assertEqual(records[2]["replacement_status"], "rule_retained")
            # 非選抜理由が保存されたことを確認する
            self.assertEqual(
                records[2]["retention_reason"], "not_selected_for_teacher_paraphrase"
            )
            # 集計上の教師置換数を確認する
            self.assertEqual(result["teacher_replaced_count"], 1)
            # 集計上の元文維持数を確認する
            self.assertEqual(result["rule_retained_count"], 2)
            # 入力未変更の検証結果を確認する
            self.assertTrue(result["source_inputs_unchanged"])
            # ZIPを開く
            with zipfile.ZipFile(archive_path) as archive:
                # ZIP内メンバーが固定名一件だけであることを確認する
                self.assertEqual(archive.namelist(), [ARCHIVE_MEMBER])
                # ZIP内JSONLがローカル出力と同一であることを確認する
                self.assertEqual(archive.read(ARCHIVE_MEMBER), output_path.read_bytes())

    # 教師候補の意味ASTが元指示と異なる場合に停止することを検証する
    def test_rejects_teacher_with_different_semantic_ast(self) -> None:
        """spec_idだけが同じでも意味AST本体が違う置換を許可しない。"""

        # テスト専用一時ディレクトリを作る
        with tempfile.TemporaryDirectory() as temporary_directory:
            # 一時パスをPathへ変換する
            root = Path(temporary_directory)
            # 元ルール生成指示を作る
            source = _rule_record("rule-1", "spec-1", "偶数を残してください。")
            # 教師置換レコードを作る
            teacher = _teacher_record(source, "偶数だけを抽出してください。")
            # 教師側の意味ASTだけを別操作へ変更する
            teacher["semantic_ast"] = {"sequence": [{"filter": ["odd"]}]}
            # 元指示JSONLを保存する
            _write_jsonl(root / "rule.jsonl", [source])
            # 不正な教師JSONLを保存する
            _write_jsonl(root / "approved.jsonl", [teacher])
            # 失敗なしの教師生成集計を保存する
            (root / "generation_stats.json").write_text(
                # 必要な集計をJSON化する
                json.dumps(
                    {
                        "selected_source_count": 1,
                        "candidate_count": 1,
                        "failure_count": 0,
                        "failures": [],
                    }
                ),
                # UTF-8で保存する
                encoding="utf-8",
            )
            # 意味AST不一致エラーを期待する
            with self.assertRaisesRegex(ValueError, "semantic_astが一致しません"):
                # 不正な置換を実行する
                build_replacement_resolved_instructions(
                    # 元ルール生成指示を渡す
                    rule_instructions=root / "rule.jsonl",
                    # 不正な教師言い換えを渡す
                    approved_paraphrases=root / "approved.jsonl",
                    # 教師生成集計を渡す
                    paraphrase_generation_stats=root / "generation_stats.json",
                    # 出力JSONLのパスを渡す
                    output_jsonl=root / "resolved.jsonl",
                    # ZIPのパスを渡す
                    archive=root / "resolved.zip",
                    # 集計JSONのパスを渡す
                    stats=root / "resolved_stats.json",
                    # 一件出力を期待する
                    expected_output_count=1,
                    # 一件置換を期待する
                    expected_replacement_count=1,
                    # 新規出力なので上書きを無効にする
                    overwrite=False,
                )


# テスト用ルール生成指示を作る関数を定義する
def _rule_record(
    # 指示IDを受け取る
    instruction_id: str,
    # 意味AST IDを受け取る
    spec_id: str,
    # 日本語指示を受け取る
    instruction_ja: str,
    # 分割を受け取る
    split: str = "train",
) -> dict[str, object]:
    """実データの必須来歴を持つルール生成指示を返す。"""

    # 意味AST内の操作名をIDから作る
    operation_name = f"operation-{spec_id}"
    # ルール生成指示を返す
    return {
        "instruction_id": instruction_id,
        "spec_id": spec_id,
        "semantic_ast": {"sequence": [{"map": [operation_name]}]},
        "split": split,
        "test_suite": None,
        "instruction_ja": instruction_ja,
        "instruction_source": "rule",
        "dictionary": "train",
        "dictionary_version": "dictionary-version",
        "expression_ids": [f"expr-{instruction_id}"],
        "sentence_template_id": "sentence-template",
        "generator_version": "1",
        "generator_seed": 20260924,
        "teacher_model": None,
        "teacher_revision": None,
        "prompt_hash": None,
        "text_hash": text_sha256(instruction_ja),
    }


# テスト用承認済み教師言い換えを作る関数を定義する
def _teacher_record(
    # 元のルール生成指示を受け取る
    source: dict[str, object],
    # 言い換え本文を受け取る
    instruction_ja: str,
) -> dict[str, object]:
    """実データの必須来歴を持つ教師言い換えを返す。"""

    # 承認済み教師言い換えを返す
    return {
        "instruction_id": f"teacher-{source['instruction_id']}",
        "source_instruction_id": source["instruction_id"],
        "spec_id": source["spec_id"],
        "semantic_ast": source["semantic_ast"],
        "source_instruction_ja": source["instruction_ja"],
        "instruction_ja": instruction_ja,
        "instruction_source": "teacher",
        "dictionary": "train",
        "review_status": "approved",
        "teacher_model": "teacher-model",
        "teacher_revision": "teacher-revision",
        "teacher_seed": 1,
        "teacher_sampling": {"temperature": 0.9},
        "prompt_hash": "prompt-hash",
        "text_hash": text_sha256(instruction_ja),
        "candidate_review_status": "pending",
        "approved_by": "reviewer",
        "approved_at": "2026-09-25T00:00:00+09:00",
        "approval_mode": "blanket_all_candidates",
    }


# JSON object列をJSONLへ保存する関数を定義する
def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    """テストレコードを決定的な一行JSONとして保存する。"""

    # 全レコードを一行ずつJSONへ変換して保存する
    path.write_text(
        # 各レコードをコンパクトJSONと改行へ変換する
        "".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            for record in records
        ),
        # UTF-8で保存する
        encoding="utf-8",
    )


# JSONLをテスト用配列へ読み込む関数を定義する
def _read_jsonl(path: Path) -> list[dict[str, object]]:
    """空行を無視してJSONLを読み込む。"""

    # UTF-8で開く
    with path.open(encoding="utf-8") as handle:
        # 各非空行をJSON objectへ変換して返す
        return [json.loads(line) for line in handle if line.strip()]
