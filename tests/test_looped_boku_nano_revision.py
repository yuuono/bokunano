"""修正4候補の計算・比較条件・日程保存の契約を検証する。"""
from copy import deepcopy
from array import array
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import torch
import yaml

from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM, model_from_checkpoint
from scripts.model.run_boku_nano_looped_experiment import (
    ROOT, REVISION_CANDIDATES, REVISION_COMPARISON, SLOW_SCHEDULE, build_configs, write_comparison,
)
from scripts.model.train_boku_nano import (
    learning_rate_for_step, resolve_learning_rate_schedule, validate_resume_schedule,
    save_training_checkpoint,
    TokenizedCodeDataset, train,
)


class RevisionModelTest(unittest.TestCase):
    def test_manual_unroll_gradients_causality_and_checkpoint(self):
        # 実装のblock.forwardを使わず、枝の倍率と順序を独立に展開する
        ids = torch.tensor([[1, 4, 8, 9, 2]])
        for changes in ({"n_loops": 2, "residual_scale": 0.5},
                        {"n_loops": 2, "loop_input_mode": "add"},
                        {"n_loops": 4, "loop_pattern": "middle"}):
            with self.subTest(changes=changes):
                config = BokuNanoConfig(vocab_size=32, d_model=16, n_layers=3,
                                       n_heads=2, d_ff=32, context_length=16, **changes)
                model = BokuNanoForCausalLM(config)
                reference = deepcopy(model)
                order = [0, 1, 1, 1, 1, 2] if config.loop_pattern == "middle" else [0, 1, 2] * 2
                embedding = reference.token_embedding(ids)
                hidden = embedding
                for position, index in enumerate(order):
                    if position == 3 and config.loop_input_mode == "add":
                        hidden = hidden + embedding
                    block = reference.blocks[index]
                    hidden = hidden + config.residual_scale * block.attention(block.attention_norm(hidden))
                    hidden = hidden + config.residual_scale * block.feed_forward(block.ffn_norm(hidden))
                expected = reference.lm_head(reference.final_norm(hidden)).float()
                actual = model(ids).logits
                torch.testing.assert_close(actual, expected)
                actual.square().sum().backward()
                expected.square().sum().backward()
                for name, param in model.named_parameters():
                    torch.testing.assert_close(param.grad, dict(reference.named_parameters())[name].grad)
                changed = ids.clone()
                changed[:, 3:] = 12
                torch.testing.assert_close(model(ids).logits[:, :3], model(changed).logits[:, :3])
                calls = []
                hooks = [b.register_forward_hook(lambda m, i, o, j=j: calls.append(j))
                         for j, b in enumerate(model.blocks)]
                model(ids)
                for hook in hooks:
                    hook.remove()
                self.assertEqual(calls, order)
                self.assertEqual(config.effective_layers, 6)
                restored = model_from_checkpoint({"model_config": config.to_dict(),
                                                  "model_state_dict": model.state_dict()})
                torch.testing.assert_close(restored(ids).logits, actual)

    def test_invalid_model_options(self):
        config = BokuNanoConfig(n_layers=3)
        for scale in [0, -1, float("nan"), float("inf"), True, "0.5"]:
            with self.subTest(scale=scale), self.assertRaises(ValueError):
                replace(config, residual_scale=scale).validate()
        for changes in ({"loop_pattern": "bad"}, {"loop_pattern": "middle", "n_layers": 2},
                        {"loop_pattern": "middle", "loop_input_mode": "add"}):
            with self.assertRaises(ValueError):
                replace(config, **changes).validate()


class RevisionRunnerTest(unittest.TestCase):
    def setUp(self):
        self.base = yaml.safe_load((ROOT / "config/boku_nano_1m_bpe_2048_1epoch.yaml").read_text())
        self.ev = yaml.safe_load((ROOT / "config/boku_nano_1m_bpe_2048_1epoch_evaluation.yaml").read_text())

    def test_one_factor_same_initial_weights_and_one_epoch(self):
        torch.manual_seed(7)
        original = BokuNanoForCausalLM(BokuNanoConfig.from_dict(self.base["model"]))
        for variant in REVISION_COMPARISON:
            config, _ = build_configs(self.base, self.ev, variant, Path("/tmp/test") / variant, 7, 1)
            self.assertEqual(config["training"]["epochs"], 1)
            for key in ("data", "validation_data", "tokenizer", "runtime"):
                self.assertEqual(config[key], self.base[key])
            expected_optimizer = dict(self.base["optimizer"])
            if variant in ("u3_slow", "u3_r2_slow"):
                expected_optimizer.update(SLOW_SCHEDULE)
            self.assertEqual(config["optimizer"], expected_optimizer)
            torch.manual_seed(7)
            model = BokuNanoForCausalLM(BokuNanoConfig.from_dict(config["model"]))
            self.assertEqual(model.parameter_count(), 1016704)
            for key, value in original.state_dict().items():
                torch.testing.assert_close(model.state_dict()[key], value, rtol=0, atol=0)
            if variant in REVISION_CANDIDATES:
                self.assertEqual(model.config.effective_layers, 6)
                with self.assertRaises(ValueError):
                    build_configs(self.base, self.ev, variant, Path("/tmp/test"), 7, 3)

    def test_schedule_preserves_warmup_and_legacy_resume(self):
        optimizer = self.base["optimizer"]
        old = resolve_learning_rate_schedule(optimizer, 377)
        slow_optimizer = dict(optimizer, **SLOW_SCHEDULE)
        slow = resolve_learning_rate_schedule(slow_optimizer, 377)
        self.assertEqual(old["warmup_steps"], 19)
        self.assertEqual(slow["warmup_steps"], 19)
        self.assertEqual(slow["schedule_steps"], 1131)
        def lr(step, config):
            return learning_rate_for_step(step, config["schedule_steps"], config["warmup_steps"],
                                          config["maximum_learning_rate"], config["minimum_learning_rate"])
        for step in range(1, 20):
            self.assertEqual(lr(step, old), lr(step, slow))
        self.assertAlmostEqual(lr(377, old), 3e-5)
        self.assertGreater(lr(377, slow), 2e-4)
        three = resolve_learning_rate_schedule(optimizer, 1131)
        self.assertEqual(three["warmup_steps"], 57)
        self.assertAlmostEqual(lr(377, three), 0.00024505220633160025)
        validate_resume_schedule({}, old, optimizer)
        validate_resume_schedule({"learning_rate_schedule": slow}, slow, slow_optimizer)
        with self.assertRaises(ValueError):
            validate_resume_schedule({}, slow, slow_optimizer)
        with self.assertRaises(ValueError):
            validate_resume_schedule({"learning_rate_schedule": old}, slow, slow_optimizer)
        for changes in ({"learning_rate_schedule_steps": True}, {"warmup_steps": -1},
                        {"warmup_steps": 378}, {"minimum_learning_rate": 1}, {"warmup_ratio": float("nan")}):
            with self.assertRaises(ValueError):
                resolve_learning_rate_schedule(dict(optimizer, **changes), 377)
        with tempfile.TemporaryDirectory() as directory:
            model = BokuNanoForCausalLM(BokuNanoConfig(vocab_size=32, d_model=16, n_heads=2,
                                                      n_layers=3, d_ff=32))
            path = Path(directory) / "epoch.pt"
            save_training_checkpoint(path, model, torch.optim.AdamW(model.parameters()), 1, 377,
                                     10, 8, learning_rate_schedule=slow)
            self.assertEqual(torch.load(path, weights_only=True)["learning_rate_schedule"], slow)

    def test_cli_defaults_and_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plan"
            command = [sys.executable, str(ROOT / "scripts/model/run_boku_nano_looped_revision_experiment.py"),
                       "--output-root", str(output)]
            subprocess.run(command, check=True, capture_output=True)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual([j["variant"] for j in manifest["jobs"]], REVISION_COMPARISON)
            self.assertEqual([j["effective_layers"] for j in manifest["jobs"]], [3, 6, 3, 6, 6, 6, 6])
            self.assertEqual(manifest["epochs"], 1)
            self.assertFalse(manifest["smoke_test"])
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            jobs = []
            for i, variant in enumerate(REVISION_COMPARISON):
                folder = output / f"{variant}_seed20260925"
                (folder / "evaluation").mkdir()
                suite = {"normal": {"status": "completed", "evaluated_record_count": 10,
                                    "passed_record_count": i}}
                (folder / "evaluation/evaluation_manifest.json").write_text(json.dumps({"suites": suite}))
                ev = {"evaluation_data": {"suites": {"normal": {"expected_record_count": 10}}}}
                jobs.append((folder, {}, ev, {"variant": variant, "parameter_count": 1016704,
                                              "effective_layers": 6}))
            result = write_comparison(output, jobs)
            slow = result["models"][3]
            self.assertEqual(slow["control_variant"], "u3_r2")
            self.assertEqual(slow["matched_nonloop_variant"], "u3_slow")
            self.assertAlmostEqual(slow["delta_vs_control_percentage_points"], 20)
            self.assertAlmostEqual(slow["delta_vs_matched_nonloop_percentage_points"], 10)
            result = write_comparison(output, jobs[3:])
            self.assertIsNone(result["models"][0]["delta_vs_control_percentage_points"])
            self.assertIsNone(result["models"][0]["delta_vs_matched_nonloop_percentage_points"])

    def test_training_completion_uses_epoch_not_schedule_horizon(self):
        # 入力だけを2例のfixtureにし、実trainerで1epoch完了と保存を検証する
        dataset = TokenizedCodeDataset([(array("H", [1, 4, 8, 5, 9, 2]), 4),
                                        (array("H", [1, 4, 7, 5, 10, 2]), 4)])
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            config, _ = build_configs(self.base, self.ev, "u3_r2_slow", folder, 7, 1)
            config["runtime"].update(device="cpu", dtype="float32")
            config["training"].update(micro_batch_size=2, gradient_accumulation_steps=1)
            path = folder / "config.yaml"
            path.write_text(yaml.safe_dump(config))
            with patch("scripts.model.train_boku_nano.build_training_dataset",
                       return_value=(dataset, {"fixture": True})):
                manifest = train(path, None, False, None, None, None)
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["global_step"], 1)
            self.assertEqual(manifest["configured_optimizer_steps"], 1)
            self.assertEqual(manifest["learning_rate_schedule"]["schedule_steps"], 1131)
            saved = torch.load(folder / "model/checkpoints/epoch_01.pt", weights_only=True)
            self.assertEqual(saved["learning_rate_schedule"], manifest["learning_rate_schedule"])
            self.assertTrue((folder / "model/model.safetensors").exists())


@unittest.skipUnless(importlib.util.find_spec("onnx") and importlib.util.find_spec("onnxruntime"),
                     "ONNX dependencies are optional")
class RevisionOnnxTest(unittest.TestCase):
    def test_scaled_add_and_middle_dynamic_prefix(self):
        import numpy as np
        import onnxruntime as ort
        from scripts.model.export_boku_nano_onnx import export_model
        for changes in ({"n_loops": 2, "residual_scale": 0.5},
                        {"n_loops": 2, "loop_input_mode": "add"},
                        {"n_loops": 4, "loop_pattern": "middle"}):
            model = BokuNanoForCausalLM(BokuNanoConfig(vocab_size=32, d_model=16, n_layers=3,
                                       n_heads=2, d_ff=32, context_length=16, **changes)).eval()
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "model.onnx"
                export_model(model, path, 4, 18)
                session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
                for length in (1, 7, 16):
                    ids = torch.arange(length)[None, :]
                    with torch.inference_mode():
                        expected = model(ids).logits[:, -1].numpy()
                    actual = session.run(None, {"input_ids": ids.numpy()})[0]
                    np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=2e-5)


if __name__ == "__main__":
    unittest.main()
