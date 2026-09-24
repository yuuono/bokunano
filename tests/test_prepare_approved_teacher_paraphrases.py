"""教師言い換えの一括承認成果物を検証する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# JSONLと集計JSONを検査するために使う
import json
# 一時入出力パスを作るために使う
from pathlib import Path
# テスト後に自動削除される一時ディレクトリを作るために使う
import tempfile
# 標準ライブラリだけで単体テストを実行するために使う
import unittest
# ZIP内の承認済みJSONLを検査するために使う
import zipfile

# 一括承認処理をテスト対象として読み込む
from scripts.instruction_generation.prepare_approved_teacher_paraphrases import (
    # 全候補を承認済み成果物へ変換する関数を読み込む
    prepare_approved_paraphrases,
)


# 関連する状態と処理をまとめるクラスを定義する
class PrepareApprovedTeacherParaphrasesTests(unittest.TestCase):
    # この工程を担当する関数を定義する
    def test_approve_all_preserves_candidate_and_adds_audit_fields(self) -> None:
        # テスト終了時に自動削除されるディレクトリを作る
        with tempfile.TemporaryDirectory() as directory:
            # 一時ディレクトリをPathへ変換する
            root = Path(directory)
            # 候補JSONLのパスを作る
            candidates = root / "candidates.jsonl"
            # 承認済みJSONLのパスを作る
            output = root / "approved.jsonl"
            # ZIPのパスを作る
            archive = root / "approved.zip"
            # 集計JSONのパスを作る
            stats = root / "stats.json"
            # 元候補の全項目を保持できるテストレコードを作る
            candidate = self._candidate("candidate-1", "source-1")
            # 候補JSONLへ一件を書き込む
            candidates.write_text(
                # 日本語を保った一行JSONLを作る
                json.dumps(candidate, ensure_ascii=False) + "\n",
                # UTF-8で保存する
                encoding="utf-8",
            )
            # 明示的一括承認を実行する
            result = prepare_approved_paraphrases(
                # 候補JSONLを渡す
                candidate_jsonl=candidates,
                # 承認済みJSONLの保存先を渡す
                output_jsonl=output,
                # ZIP保存先を渡す
                archive=archive,
                # 集計JSON保存先を渡す
                stats=stats,
                # 承認者を渡す
                reviewer="ono_yusuke",
                # 固定した承認日時を渡す
                approved_at="2026-09-24T20:51:52+09:00",
                # 一件を期待する
                expected_count=1,
                # 一括承認を明示する
                approve_all=True,
                # 新規作成なので上書きしない
                overwrite=False,
            )
            # 承認済み件数が一件であることを確認する
            self.assertEqual(result["approved_count"], 1)
            # 承認済みJSONLの一件を読み込む
            approved = json.loads(output.read_text(encoding="utf-8"))
            # 元候補の意味ASTがそのまま保持されることを確認する
            self.assertEqual(approved["semantic_ast"], candidate["semantic_ast"])
            # 元指示IDがそのまま保持されることを確認する
            self.assertEqual(approved["source_instruction_id"], "source-1")
            # 元のpending状態が別項目に保持されることを確認する
            self.assertEqual(approved["candidate_review_status"], "pending")
            # 利用可能な承認済み状態になったことを確認する
            self.assertEqual(approved["review_status"], "approved")
            # 承認者が保存されたことを確認する
            self.assertEqual(approved["approved_by"], "ono_yusuke")
            # 明示的一括承認方式が保存されたことを確認する
            self.assertEqual(approved["approval_mode"], "blanket_all_candidates")
            # ZIP内JSONLが承認済みJSONLと同じバイト列であることを確認する
            with zipfile.ZipFile(archive) as zip_handle:
                # 固定メンバー名から内容を読み込む
                archived = zip_handle.read("approved_teacher_paraphrases.jsonl")
            # ZIP展開内容とJSONL本体が一致することを確認する
            self.assertEqual(archived, output.read_bytes())
            # 集計JSONにも承認件数が保存されることを確認する
            self.assertEqual(
                # 集計JSONを読み込んで件数を取得する
                json.loads(stats.read_text(encoding="utf-8"))["approved_count"],
                # 期待する件数を設定する
                1,
            )

    # この工程を担当する関数を定義する
    def test_requires_explicit_approve_all(self) -> None:
        # テスト終了時に自動削除されるディレクトリを作る
        with tempfile.TemporaryDirectory() as directory:
            # 一時ディレクトリをPathへ変換する
            root = Path(directory)
            # 入力候補JSONLを一件で作る
            candidates = root / "candidates.jsonl"
            # 候補レコードを一行JSONLとして保存する
            candidates.write_text(
                # テスト候補をJSON文字列へ変換する
                json.dumps(self._candidate("candidate-1", "source-1")) + "\n",
                # UTF-8で保存する
                encoding="utf-8",
            )
            # 明示フラグがない場合に停止することを確認する
            with self.assertRaisesRegex(ValueError, "--approve-all"):
                # 一括承認を明示せず処理を呼び出す
                prepare_approved_paraphrases(
                    # 候補JSONLを渡す
                    candidate_jsonl=candidates,
                    # 承認済みJSONLの保存先を渡す
                    output_jsonl=root / "approved.jsonl",
                    # ZIP保存先を渡す
                    archive=root / "approved.zip",
                    # 集計JSON保存先を渡す
                    stats=root / "stats.json",
                    # 承認者を渡す
                    reviewer="ono_yusuke",
                    # タイムゾーン付き日時を渡す
                    approved_at="2026-09-24T20:51:52+09:00",
                    # 一件を期待する
                    expected_count=1,
                    # 一括承認を明示しない
                    approve_all=False,
                    # 新規作成なので上書きしない
                    overwrite=False,
                )

    # 直後の定義へデコレータを適用する
    @staticmethod
    # この工程を担当する関数を定義する
    def _candidate(instruction_id: str, source_instruction_id: str) -> dict[str, object]:
        """承認処理に必要な最小候補レコードを作る。"""

        # 必須来歴を持つ候補レコードを返す
        return {
            # 教師候補IDを設定する
            "instruction_id": instruction_id,
            # 元指示IDを設定する
            "source_instruction_id": source_instruction_id,
            # 意味AST IDを設定する
            "spec_id": "combined-000001",
            # 意味ASTを設定する
            "semantic_ast": {"sequence": [{"filter": ["even"]}]},
            # 元指示文を設定する
            "source_instruction_ja": "偶数を残してください。",
            # 言い換え文を設定する
            "instruction_ja": "偶数だけを抽出してください。",
            # 教師生成区分を設定する
            "instruction_source": "teacher",
            # 訓練辞書区分を設定する
            "dictionary": "train",
            # 承認前状態を設定する
            "review_status": "pending",
            # 教師モデルIDを設定する
            "teacher_model": "Qwen/Qwen3-4B-AWQ",
            # 教師モデルrevisionを設定する
            "teacher_revision": "a" * 40,
            # sampling seedを設定する
            "teacher_seed": 1,
            # sampling設定を設定する
            "teacher_sampling": {"temperature": 0.9},
            # prompt hashを設定する
            "prompt_hash": "b" * 64,
            # 本文hashを設定する
            "text_hash": "c" * 64,
        }


# 直接実行された場合だけテストを開始する
if __name__ == "__main__":
    # unittestの標準runnerを起動する
    unittest.main()
