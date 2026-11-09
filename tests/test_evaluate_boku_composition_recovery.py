"""評価専用の復元来歴を検証する。実重み・GPU・保存済み評価結果には依存しない。"""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.model import evaluate_boku_composition_torch as runner
from scripts.model import prepare_looped_evaluation_recovery as recovery


class RecoveredCompositionModelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.original = self.root / "original"
        self.recovered = self.root / "recovered"
        self.original.mkdir()
        self.recovered.mkdir()
        self.weights = self.original / "model.safetensors"
        self.weights.write_bytes(b"fixture checkpoint bytes; deliberately not a loadable tensor file")
        self.tokenizer = self.root / "tokenizer.json"
        self.tokenizer.write_text('{"fixture": "tokenizer"}\n', encoding="utf-8")
        self.report = self.root / "report.md"
        self.report.write_text("# Fixture report\n1 block x 3 loops; 3 epochs.\n", encoding="utf-8")
        self.config_path = self.recovered / "model_config.json"
        self.manifest_path = self.recovered / "recovery_manifest.json"
        self.config = dict(vocab_size=2048, d_model=128, n_layers=1, n_heads=4,
                           d_ff=256, context_length=256, dropout=0.0, rope_base=10000.0,
                           rms_norm_eps=1e-5, tie_word_embeddings=True, n_loops=3,
                           loop_input_mode="none", loop_pattern="full", residual_scale=1.0,
                           recurrent_residual_scale=1.0)
        runner.write_json(self.config_path, self.config)
        self.weight_sha = runner.sha(self.weights)
        self.report_sha = runner.sha(self.report)
        self.tokenizer_sha = runner.sha(self.tokenizer)
        for obj, name, value in (
            (recovery, "VARIANTS", {"lt1": (128, 256, 4, 426368, self.weight_sha)}),
            (recovery, "REPORT", self.report),
            (recovery, "REPORT_SHA256", self.report_sha),
            (runner, "TOKENIZER_SHA256", self.tokenizer_sha),
        ):
            patcher = patch.object(obj, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.manifest = {
            "status": "recovered_for_evaluation", "variant": "lt1",
            "original_training_manifest_present": False,
            "weights_path": str(self.weights), "weights_sha256": self.weight_sha,
            "expected_weights_sha256": self.weight_sha,
            "model_config_path": str(self.config_path), "model_config": copy.deepcopy(self.config),
            "model_config_sha256": runner.sha(self.config_path),
            "parameter_count": 426368, "expected_parameter_count": 426368,
            "tokenizer_path": str(self.tokenizer), "tokenizer_sha256": self.tokenizer_sha,
            "reported_training": {"epochs": 3, "seed": 20260925, "source": str(self.report)},
            "source_report": {"path": str(self.report), "sha256": self.report_sha},
            "configuration_sources": {str(self.report): self.report_sha},
        }
        self.save_manifest()

    def save_manifest(self):
        runner.write_json(self.manifest_path, self.manifest)

    def validate(self, name="recovered-lt1"):
        return runner.validate_recovered_model(name, self.manifest_path,
                                               tokenizer_sha256=self.tokenizer_sha)

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_recovery_is_read_only_and_does_not_claim_original_training_provenance(self):
        before = self.snapshot()
        result = self.validate()
        self.assertEqual(result["artifact_provenance"], "recovered_for_evaluation")
        self.assertIs(result["original_training_manifest_present"], False)
        self.assertEqual(result["directory"], str(self.original))
        self.assertEqual(result["weight_sha256"], self.weight_sha)
        self.assertEqual(result["parameter_count"], 426368)
        self.assertEqual(result["epochs"], 3)
        self.assertIn(str(self.report), result["source_hashes"])
        self.assertIn(str(self.manifest_path), result["source_hashes"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.root.rglob("training_manifest.json")), [])

    def test_recovery_cannot_reuse_any_frozen_default_model_name(self):
        for name in runner.DEFAULT_MODELS:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "既定モデル"):
                self.validate(name)

    def test_recovery_requires_explicit_status_and_missing_original_manifest(self):
        original = copy.deepcopy(self.manifest)
        for changes in ({"status": "completed"}, {"original_training_manifest_present": True},
                        {"original_training_manifest_present": None}):
            with self.subTest(changes=changes):
                self.manifest = {**original, **changes}
                self.save_manifest()
                with self.assertRaisesRegex(ValueError, "評価用復元manifest"):
                    self.validate()

    def test_rehashed_loop_count_change_cannot_redefine_historical_checkpoint(self):
        self.config["n_loops"] = 2
        runner.write_json(self.config_path, self.config)
        self.manifest["model_config"] = copy.deepcopy(self.config)
        self.manifest["model_config_sha256"] = runner.sha(self.config_path)
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "報告条件と復元設定"):
            self.validate()

    def test_changed_checkpoint_bytes_are_rejected(self):
        self.weights.write_bytes(b"different checkpoint")
        with self.assertRaisesRegex(ValueError, "artifactのhash"):
            self.validate()

    def test_self_declared_new_checkpoint_hash_is_not_trusted(self):
        self.weights.write_bytes(b"different checkpoint")
        self.manifest["weights_sha256"] = runner.sha(self.weights)
        self.manifest["expected_weights_sha256"] = runner.sha(self.weights)
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "報告条件と復元設定"):
            self.validate()

    def test_changed_report_bytes_are_rejected(self):
        self.report.write_text("A different report.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "復元根拠またはartifactのhash"):
            self.validate()

    def test_self_declared_new_report_hash_is_not_trusted(self):
        self.report.write_text("A different report.\n", encoding="utf-8")
        self.manifest["source_report"]["sha256"] = runner.sha(self.report)
        self.manifest["configuration_sources"][str(self.report)] = runner.sha(self.report)
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "復元根拠の報告書"):
            self.validate()


if __name__ == "__main__":
    unittest.main()
