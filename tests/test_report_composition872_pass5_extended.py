"""既存評価の非破壊統合、middle分類、明示的な表示除外を検証する。"""
from copy import deepcopy
import unittest

from scripts.model import report_composition872_pass5_extended as report


class ExtendedPass5ReportTests(unittest.TestCase):
    def setUp(self):
        def model(name, group="standard", epochs=3, *, middle_scale=None, small=False):
            config = {"d_model": 128, "d_ff": 256, "n_layers": 1 if small else 3, "n_heads": 4,
                      "n_loops": 3 if small else 1, "loop_pattern": "full", "loop_input_mode": "none",
                      "residual_scale": 1.0, "recurrent_residual_scale": 1.0,
                      "tie_word_embeddings": small}
            if middle_scale is not None:
                config.update(n_loops=4, loop_pattern="middle", recurrent_residual_scale=middle_scale)
                group = "looped"  # The frozen old classifier calls all repeated models small loops.
            count = 426368 if small else 1016704
            metadata = {"name": name, "model_config": deepcopy(config), "parameter_count": count, "epochs": epochs}
            return {"model": name, "model_config": config, "parameter_count": count, "epochs": epochs,
                    "metadata": metadata, "group": group, "group_label": "original group", "label": "LT1" if group == "looped" else name,
                    "weight_sha256": name, "artifact_hashes": {}, "greedy_run_root": "greedy/" + name,
                    "pass5_run_root": "sampling/" + name, "pass_at_1_count": 10, "pass_at_5_count": 20,
                    "configuration_recovered": small}
        first = [model(report.MAIN_MODELS[0]), model(report.EXCLUDED_MODELS[0], epochs=1),
                 model(report.EXCLUDED_MODELS[1], "short", epochs=1), model("loop-lt1-3epoch", "looped", small=True)]
        second = [model(report.MAIN_MODELS[1], middle_scale=1.0), model(report.MAIN_MODELS[2], middle_scale=.25)]
        shared = {"dataset": "fixture", "questions_sha256": "questions", "test_cases_sha256": "cases",
                  "protocol_sha256": "protocol", "question_count": 872, "test_case_count": 179,
                  "suite_order": report.SUITES, "suite_counts": report.COUNTS, "suite_labels": report.LABELS}
        self.baseline = {**shared, "models": deepcopy(first + second), "runs": []}
        self.reports = [{**shared, "models": models, "sampling_conditions": {"sampling_seed": 1},
                         "metric_note": "fixture", "pass5_run_root": f"sampling/{i}",
                         "sampling_config": {}, "completed_at": "fixture", "source_hashes": {}}
                        for i, models in enumerate((first, second))]

    def merge(self):
        return report.merge_reports(self.reports, self.baseline, report.EXCLUDED_MODELS, expected_count=4)

    def test_only_requested_one_epoch_models_are_hidden_without_changing_sources(self):
        before = deepcopy((self.reports, self.baseline))
        values = self.merge()
        self.assertEqual((values["input_model_count"], values["model_count"]), (6, 4))
        self.assertEqual({r["model"] for r in values["display_exclusions"]}, set(report.EXCLUDED_MODELS))
        self.assertTrue(set(report.MAIN_MODELS) <= {r["model"] for r in values["models"]})
        self.assertEqual((self.reports, self.baseline), before)

    def test_middle_models_are_separate_from_lt1_with_same_width_and_ffn(self):
        values = self.merge()
        rows = {r["model"]: r for r in values["models"]}
        for name in report.MAIN_MODELS[1:]:
            self.assertEqual(rows[name]["group"], "middle")
            self.assertIn("中間層×4", rows[name]["label"])
            self.assertNotIn("LT1", rows[name]["label"])
            self.assertFalse(rows[name]["configuration_recovered"])
        self.assertEqual(rows["loop-lt1-3epoch"]["group"], "looped")
        self.assertTrue(rows["loop-lt1-3epoch"]["configuration_recovered"])

    def test_middle_name_cannot_hide_wrong_scale_or_full_loop(self):
        original = self.reports[1]["models"][0]
        for change in ({"recurrent_residual_scale": .25}, {"loop_pattern": "full"}):
            with self.subTest(change=change):
                row = deepcopy(original)
                row["model_config"].update(change)
                with self.assertRaises(ValueError):
                    report.display_metadata(row)

    def test_duplicate_model_across_sampling_runs_is_not_pooled(self):
        self.reports[1]["models"].append(deepcopy(self.reports[0]["models"][0]))
        with self.assertRaisesRegex(ValueError, "複数sampling run"):
            self.merge()

    def test_different_sampling_seed_is_not_silently_combined(self):
        self.reports[1]["sampling_conditions"]["sampling_seed"] = 2
        with self.assertRaisesRegex(ValueError, "sampling条件またはseed"):
            self.merge()

    def test_sampling_metadata_must_match_global_greedy_identity(self):
        self.reports[1]["models"][0]["metadata"]["parameter_count"] = 426368
        with self.assertRaisesRegex(ValueError, "重み・構造・tokenizer"):
            self.merge()


if __name__ == "__main__":
    unittest.main()
