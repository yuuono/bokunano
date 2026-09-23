from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from scripts.instruction_generation.prepare_approved_expression_release import (
    RELEASE_CSV_NAME,
    RELEASE_JSONL_NAME,
    REVIEW_FIELDS,
    prepare_release,
)


class PrepareApprovedExpressionReleaseTests(unittest.TestCase):
    def test_prunes_unused_and_preserves_generation_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review_csv = root / "approved.csv"
            candidate_jsonl = root / "approved.jsonl"
            release_directory = root / "release"
            rows = [
                self._review_row(
                    expression_id="expr-approved",
                    status="approved",
                    edited_expression="偶数だけを残す",
                ),
                self._review_row(
                    expression_id="expr-unused",
                    status="unused",
                    expression="偶数のみを検索する",
                ),
            ]
            self._write_review(review_csv, rows, extra_header=True)
            candidates = [
                self._candidate("expr-approved", "偶数を残す"),
                self._candidate("expr-unused", "偶数のみを検索する"),
            ]
            self._write_jsonl(candidate_jsonl, candidates)

            result = prepare_release(
                review_csv=review_csv,
                candidate_jsonl=candidate_jsonl,
                release_directory=release_directory,
                prune_unused=True,
            )

            self.assertEqual(result["approved"], 1)
            self.assertEqual(result["removed_unused"], 1)
            self.assertEqual(result["human_edited"], 1)
            with review_csv.open(encoding="utf-8", newline="") as handle:
                master_rows = list(csv.DictReader(handle))
            self.assertEqual([row["expression_id"] for row in master_rows], ["expr-approved"])
            master_candidates = self._read_jsonl(candidate_jsonl)
            self.assertEqual(
                [record["expression_id"] for record in master_candidates],
                ["expr-approved"],
            )

            with (release_directory / RELEASE_CSV_NAME).open(
                encoding="utf-8", newline=""
            ) as handle:
                release_rows = list(csv.DictReader(handle))
            self.assertEqual(release_rows[0]["expression_ja"], "偶数だけを残す")
            self.assertNotIn("review_status", release_rows[0])

            provenance = self._read_jsonl(
                release_directory / RELEASE_JSONL_NAME
            )
            self.assertEqual(provenance[0]["approved_expression_ja"], "偶数だけを残す")
            self.assertTrue(provenance[0]["human_edited"])
            self.assertEqual(
                provenance[0]["generation_record"]["expression_ja"],
                "偶数を残す",
            )

    def test_refuses_unused_without_explicit_prune(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review_csv = root / "approved.csv"
            candidate_jsonl = root / "approved.jsonl"
            self._write_review(
                review_csv,
                [self._review_row(expression_id="expr-unused", status="unused")],
            )
            self._write_jsonl(
                candidate_jsonl,
                [self._candidate("expr-unused", "偶数を残す")],
            )

            with self.assertRaisesRegex(ValueError, "--prune-unused"):
                prepare_release(
                    review_csv=review_csv,
                    candidate_jsonl=candidate_jsonl,
                    release_directory=root / "release",
                    prune_unused=False,
                )

    @staticmethod
    def _review_row(
        *,
        expression_id: str,
        status: str,
        expression: str = "偶数を残す",
        edited_expression: str = "",
    ) -> dict[str, str]:
        row = {field: "" for field in REVIEW_FIELDS}
        row.update(
            {
                "expression_id": expression_id,
                "operation_id": "atomic-000001",
                "operation_ast": '{"filter":["even"]}',
                "canonical_meaning_ja": "偶数だけを残す",
                "must_preserve_ja": "偶数だけを選ぶ。",
                "expression_ja": expression,
                "connective_expression_ja": "偶数を残して",
                "review_status": status,
                "edited_expression_ja": edited_expression,
            }
        )
        return row

    @staticmethod
    def _candidate(expression_id: str, expression: str) -> dict[str, object]:
        return {
            "expression_id": expression_id,
            "operation_id": "atomic-000001",
            "expression_ja": expression,
            "connective_expression_ja": "偶数を残して",
            "teacher_seed": 1,
        }

    @staticmethod
    def _write_review(
        path: Path,
        rows: list[dict[str, str]],
        *,
        extra_header: bool = False,
    ) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            if extra_header:
                handle.write(",".join(f"Column{index}" for index in range(1, 14)))
                handle.write("\n")
            writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, object]]:
        with path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


if __name__ == "__main__":
    unittest.main()
