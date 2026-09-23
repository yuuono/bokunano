# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# この処理で使う標準または外部モジュールを読み込む
import csv
# この処理で使う標準または外部モジュールを読み込む
import json
# 必要な定義を対象モジュールから読み込む
from pathlib import Path
# この処理で使う標準または外部モジュールを読み込む
import tempfile
# この処理で使う標準または外部モジュールを読み込む
import unittest

# 必要な定義を対象モジュールから読み込む
from scripts.instruction_generation.prepare_approved_expression_release import (
    # 次の値または処理を現在の構造へ組み込む
    RELEASE_CSV_NAME,
    # 次の値または処理を現在の構造へ組み込む
    RELEASE_JSONL_NAME,
    # 次の値または処理を現在の構造へ組み込む
    REVIEW_FIELDS,
    # 次の値または処理を現在の構造へ組み込む
    prepare_release,
)


# 関連する状態と処理をまとめるクラスを定義する
class PrepareApprovedExpressionReleaseTests(unittest.TestCase):
    # この工程を担当する関数を定義する
    def test_prunes_unused_and_preserves_generation_record(self) -> None:
        # 使用するリソースの開始と終了をこの範囲で管理する
        with tempfile.TemporaryDirectory() as directory:
            # rootへこの工程で使用する値を設定する
            root = Path(directory)
            # review_csvへこの工程で使用する値を設定する
            review_csv = root / "approved.csv"
            # candidate_jsonlへこの工程で使用する値を設定する
            candidate_jsonl = root / "approved.jsonl"
            # release_directoryへこの工程で使用する値を設定する
            release_directory = root / "release"
            # rowsへこの工程で使用する値を設定する
            rows = [
                # 次の値または処理を現在の構造へ組み込む
                self._review_row(
                    # expression_idへこの工程で使用する値を設定する
                    expression_id="expr-approved",
                    # statusへこの工程で使用する値を設定する
                    status="approved",
                    # edited_expressionへこの工程で使用する値を設定する
                    edited_expression="偶数だけを残す",
                ),
                # 次の値または処理を現在の構造へ組み込む
                self._review_row(
                    # expression_idへこの工程で使用する値を設定する
                    expression_id="expr-unused",
                    # statusへこの工程で使用する値を設定する
                    status="unused",
                    # expressionへこの工程で使用する値を設定する
                    expression="偶数のみを検索する",
                ),
            ]
            # 次の値または処理を現在の構造へ組み込む
            self._write_review(review_csv, rows, extra_header=True)
            # candidatesへこの工程で使用する値を設定する
            candidates = [
                # 次の値または処理を現在の構造へ組み込む
                self._candidate("expr-approved", "偶数を残す"),
                # 次の値または処理を現在の構造へ組み込む
                self._candidate("expr-unused", "偶数のみを検索する"),
            ]
            # 次の値または処理を現在の構造へ組み込む
            self._write_jsonl(candidate_jsonl, candidates)

            # resultへこの工程で使用する値を設定する
            result = prepare_release(
                # review_csvへこの工程で使用する値を設定する
                review_csv=review_csv,
                # candidate_jsonlへこの工程で使用する値を設定する
                candidate_jsonl=candidate_jsonl,
                # release_directoryへこの工程で使用する値を設定する
                release_directory=release_directory,
                # prune_unusedへこの工程で使用する値を設定する
                prune_unused=True,
            )

            # 次の値または処理を現在の構造へ組み込む
            self.assertEqual(result["approved"], 1)
            # 次の値または処理を現在の構造へ組み込む
            self.assertEqual(result["removed_unused"], 1)
            # 次の値または処理を現在の構造へ組み込む
            self.assertEqual(result["human_edited"], 1)
            # 使用するリソースの開始と終了をこの範囲で管理する
            with review_csv.open(encoding="utf-8", newline="") as handle:
                # master_rowsへこの工程で使用する値を設定する
                master_rows = list(csv.DictReader(handle))
            # 次の値または処理を現在の構造へ組み込む
            self.assertEqual([row["expression_id"] for row in master_rows], ["expr-approved"])
            # master_candidatesへこの工程で使用する値を設定する
            master_candidates = self._read_jsonl(candidate_jsonl)
            # 次の値または処理を現在の構造へ組み込む
            self.assertEqual(
                # 次の値または処理を現在の構造へ組み込む
                [record["expression_id"] for record in master_candidates],
                # 次の値または処理を現在の構造へ組み込む
                ["expr-approved"],
            )

            # 使用するリソースの開始と終了をこの範囲で管理する
            with (release_directory / RELEASE_CSV_NAME).open(
                # encodingへこの工程で使用する値を設定する
                encoding="utf-8", newline=""
            # 次の値または処理を現在の構造へ組み込む
            ) as handle:
                # release_rowsへこの工程で使用する値を設定する
                release_rows = list(csv.DictReader(handle))
            # 次の値または処理を現在の構造へ組み込む
            self.assertEqual(release_rows[0]["expression_ja"], "偶数だけを残す")
            # 次の値または処理を現在の構造へ組み込む
            self.assertNotIn("review_status", release_rows[0])

            # provenanceへこの工程で使用する値を設定する
            provenance = self._read_jsonl(
                # 次の値または処理を現在の構造へ組み込む
                release_directory / RELEASE_JSONL_NAME
            )
            # 次の値または処理を現在の構造へ組み込む
            self.assertEqual(provenance[0]["approved_expression_ja"], "偶数だけを残す")
            # 次の値または処理を現在の構造へ組み込む
            self.assertTrue(provenance[0]["human_edited"])
            # 次の値または処理を現在の構造へ組み込む
            self.assertEqual(
                # 次の値または処理を現在の構造へ組み込む
                provenance[0]["generation_record"]["expression_ja"],
                # この処理で扱う文字列を一覧へ加える
                "偶数を残す",
            )

    # この工程を担当する関数を定義する
    def test_refuses_unused_without_explicit_prune(self) -> None:
        # 使用するリソースの開始と終了をこの範囲で管理する
        with tempfile.TemporaryDirectory() as directory:
            # rootへこの工程で使用する値を設定する
            root = Path(directory)
            # review_csvへこの工程で使用する値を設定する
            review_csv = root / "approved.csv"
            # candidate_jsonlへこの工程で使用する値を設定する
            candidate_jsonl = root / "approved.jsonl"
            # 次の値または処理を現在の構造へ組み込む
            self._write_review(
                # 次の値または処理を現在の構造へ組み込む
                review_csv,
                # 次の値または処理を現在の構造へ組み込む
                [self._review_row(expression_id="expr-unused", status="unused")],
            )
            # 次の値または処理を現在の構造へ組み込む
            self._write_jsonl(
                # 次の値または処理を現在の構造へ組み込む
                candidate_jsonl,
                # 次の値または処理を現在の構造へ組み込む
                [self._candidate("expr-unused", "偶数を残す")],
            )

            # 使用するリソースの開始と終了をこの範囲で管理する
            with self.assertRaisesRegex(ValueError, "--prune-unused"):
                # 次の値または処理を現在の構造へ組み込む
                prepare_release(
                    # review_csvへこの工程で使用する値を設定する
                    review_csv=review_csv,
                    # candidate_jsonlへこの工程で使用する値を設定する
                    candidate_jsonl=candidate_jsonl,
                    # release_directoryへこの工程で使用する値を設定する
                    release_directory=root / "release",
                    # prune_unusedへこの工程で使用する値を設定する
                    prune_unused=False,
                )

    # 直後の定義へデコレータを適用する
    @staticmethod
    # この工程を担当する関数を定義する
    def _review_row(
        # 次の値または処理を現在の構造へ組み込む
        *,
        # 次の値または処理を現在の構造へ組み込む
        expression_id: str,
        # 次の値または処理を現在の構造へ組み込む
        status: str,
        # expressionへこの工程で使用する値を設定する
        expression: str = "偶数を残す",
        # edited_expressionへこの工程で使用する値を設定する
        edited_expression: str = "",
    # 次の値または処理を現在の構造へ組み込む
    ) -> dict[str, str]:
        # rowへこの工程で使用する値を設定する
        row = {field: "" for field in REVIEW_FIELDS}
        # 次の値または処理を現在の構造へ組み込む
        row.update(
            # 次の値または処理を現在の構造へ組み込む
            {
                # 出力レコードの項目と値を設定する
                "expression_id": expression_id,
                # 出力レコードの項目と値を設定する
                "operation_id": "atomic-000001",
                # 出力レコードの項目と値を設定する
                "operation_ast": '{"filter":["even"]}',
                # 出力レコードの項目と値を設定する
                "canonical_meaning_ja": "偶数だけを残す",
                # 出力レコードの項目と値を設定する
                "must_preserve_ja": "偶数だけを選ぶ。",
                # 出力レコードの項目と値を設定する
                "expression_ja": expression,
                # 出力レコードの項目と値を設定する
                "connective_expression_ja": "偶数を残して",
                # 出力レコードの項目と値を設定する
                "review_status": status,
                # 出力レコードの項目と値を設定する
                "edited_expression_ja": edited_expression,
            }
        )
        # 処理結果を呼び出し元へ返す
        return row

    # 直後の定義へデコレータを適用する
    @staticmethod
    # この工程を担当する関数を定義する
    def _candidate(expression_id: str, expression: str) -> dict[str, object]:
        # 処理結果を呼び出し元へ返す
        return {
            # 出力レコードの項目と値を設定する
            "expression_id": expression_id,
            # 出力レコードの項目と値を設定する
            "operation_id": "atomic-000001",
            # 出力レコードの項目と値を設定する
            "expression_ja": expression,
            # 出力レコードの項目と値を設定する
            "connective_expression_ja": "偶数を残して",
            # 出力レコードの項目と値を設定する
            "teacher_seed": 1,
        }

    # 直後の定義へデコレータを適用する
    @staticmethod
    # この工程を担当する関数を定義する
    def _write_review(
        # 次の値または処理を現在の構造へ組み込む
        path: Path,
        # 次の値または処理を現在の構造へ組み込む
        rows: list[dict[str, str]],
        # 次の値または処理を現在の構造へ組み込む
        *,
        # extra_headerへこの工程で使用する値を設定する
        extra_header: bool = False,
    # 次の値または処理を現在の構造へ組み込む
    ) -> None:
        # 使用するリソースの開始と終了をこの範囲で管理する
        with path.open("w", encoding="utf-8", newline="") as handle:
            # 条件を満たす場合だけ次の処理を行う
            if extra_header:
                # 次の値または処理を現在の構造へ組み込む
                handle.write(",".join(f"Column{index}" for index in range(1, 14)))
                # 次の値または処理を現在の構造へ組み込む
                handle.write("\n")
            # writerへこの工程で使用する値を設定する
            writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
            # 次の値または処理を現在の構造へ組み込む
            writer.writeheader()
            # 次の値または処理を現在の構造へ組み込む
            writer.writerows(rows)

    # 直後の定義へデコレータを適用する
    @staticmethod
    # この工程を担当する関数を定義する
    def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
        # 使用するリソースの開始と終了をこの範囲で管理する
        with path.open("w", encoding="utf-8") as handle:
            # 対象を一件ずつ取り出して処理する
            for record in records:
                # 次の値または処理を現在の構造へ組み込む
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 直後の定義へデコレータを適用する
    @staticmethod
    # この工程を担当する関数を定義する
    def _read_jsonl(path: Path) -> list[dict[str, object]]:
        # 使用するリソースの開始と終了をこの範囲で管理する
        with path.open(encoding="utf-8") as handle:
            # 処理結果を呼び出し元へ返す
            return [json.loads(line) for line in handle if line.strip()]


# 条件を満たす場合だけ次の処理を行う
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    unittest.main()
