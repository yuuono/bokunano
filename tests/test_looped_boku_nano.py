"""共有反復の勾配・因果性・保存互換性と比較設定を検証する。"""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import torch
from safetensors.torch import load_file
import yaml

from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM, model_from_checkpoint
from scripts.model.train_boku_nano import save_final_weights, save_training_checkpoint
from scripts.model.run_boku_nano_looped_experiment import (
    ROOT, VARIANTS, build_configs, parameter_count,
)


class LoopedModelTest(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(7)
        self.config = BokuNanoConfig(vocab_size=32, d_model=16, n_layers=2,
                                    n_heads=2, d_ff=32, context_length=16, n_loops=3)
        self.ids = torch.tensor([[1, 4, 8, 9, 2], [1, 4, 7, 10, 2]])

    def test_legacy_config_and_single_loop(self):
        values = self.config.to_dict()
        values.pop("n_loops")
        values.pop("loop_input_mode")
        config = BokuNanoConfig.from_dict(values)
        self.assertEqual(config.n_loops, 1)
        model = BokuNanoForCausalLM(config)
        hidden = model.token_embedding(self.ids)
        for block in model.blocks:
            hidden = block(hidden)
        expected = model.lm_head(model.final_norm(hidden)).float()
        torch.testing.assert_close(model(self.ids).logits, expected, rtol=0, atol=0)
        restored = model_from_checkpoint({"model_config": values, "model_state_dict": model.state_dict()})
        torch.testing.assert_close(restored(self.ids).logits, expected, rtol=0, atol=0)
        add = BokuNanoForCausalLM(replace(config, loop_input_mode="add"))
        add.load_state_dict(model.state_dict())
        torch.testing.assert_close(add(self.ids).logits, expected, rtol=0, atol=0)

    def test_config_validation(self):
        for value in [0, -1, True, 1.5, "3"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(self.config, n_loops=value).validate()
        with self.assertRaises(ValueError):
            replace(self.config, loop_input_mode="bad").validate()

    def test_unrolled_reference_outputs_and_summed_gradients(self):
        # 独立した展開位置の勾配の和と共有Parameterの勾配を照合する
        for mode in ("none", "add"):
            with self.subTest(mode=mode):
                model = BokuNanoForCausalLM(replace(self.config, loop_input_mode=mode))
                embedding = deepcopy(model.token_embedding)
                norm, head = deepcopy(model.final_norm), deepcopy(model.lm_head)
                blocks = [[deepcopy(block) for block in model.blocks] for _ in range(3)]
                inputs = embedding(self.ids)
                hidden = inputs
                for index, stack in enumerate(blocks):
                    if index > 0 and mode == "add":
                        hidden = hidden + inputs
                    for block in stack:
                        hidden = block(hidden)
                reference = head(norm(hidden)).float()
                actual = model(self.ids).logits
                torch.testing.assert_close(actual, reference)
                reference.square().sum().backward()
                actual.square().sum().backward()
                for block_index, block in enumerate(model.blocks):
                    for name, param in block.named_parameters():
                        expected = sum(dict(stack[block_index].named_parameters())[name].grad
                                       for stack in blocks)
                        torch.testing.assert_close(param.grad, expected, atol=2e-6, rtol=2e-5)
                torch.testing.assert_close(model.token_embedding.weight.grad, embedding.weight.grad)

    def test_causality_and_loss_mask(self):
        for mode in ("none", "add"):
            model = BokuNanoForCausalLM(replace(self.config, loop_input_mode=mode))
            changed = self.ids.clone()
            changed[:, 3:] = 12
            torch.testing.assert_close(model(self.ids).logits[:, :3], model(changed).logits[:, :3])
            labels = self.ids.clone()
            labels[:, :3] = -100
            output = model(self.ids, labels)
            expected = torch.nn.functional.cross_entropy(
                output.logits[:, 2:4].reshape(-1, 32), self.ids[:, 3:5].reshape(-1))
            torch.testing.assert_close(output.loss, expected)

    def test_shared_count_and_call_order(self):
        model = BokuNanoForCausalLM(self.config)
        shallow = BokuNanoForCausalLM(replace(self.config, n_loops=1))
        self.assertEqual(model.parameter_count(), shallow.parameter_count())
        self.assertEqual(list(model.state_dict()), list(shallow.state_dict()))
        calls = []
        hooks = [block.register_forward_hook(lambda m, i, o, index=j: calls.append(index))
                 for j, block in enumerate(model.blocks)]
        try:
            model(self.ids)
        finally:
            for hook in hooks:
                hook.remove()
        self.assertEqual(calls, [0, 1, 0, 1, 0, 1])

    def test_tied_save_load_and_optimizer_checkpoint(self):
        config = replace(self.config, tie_word_embeddings=True)
        model = BokuNanoForCausalLM(config)
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)
        model(self.ids, self.ids).loss.backward()
        optimizer.step()
        optimizer.zero_grad()
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "model.safetensors"
            save_final_weights(weights, model)
            state = load_file(weights)
            self.assertNotIn("lm_head.weight", state)
            for assign in (False, True):
                restored = BokuNanoForCausalLM(config)
                restored.load_state_dict(state, strict=True, assign=assign)
                self.assertIs(restored.lm_head.weight, restored.token_embedding.weight)
                torch.testing.assert_close(restored(self.ids).logits, model(self.ids).logits)
            checkpoint = Path(directory) / "epoch.pt"
            save_training_checkpoint(checkpoint, model, optimizer, 1, 1, 10, 8)
            saved = torch.load(checkpoint, weights_only=True)
            restored = model_from_checkpoint(saved)
            restored_optimizer = torch.optim.AdamW(restored.parameters(), lr=0.001)
            restored_optimizer.load_state_dict(saved["optimizer_state_dict"])
            for current, opt in ((model, optimizer), (restored, restored_optimizer)):
                current(self.ids, self.ids).loss.backward()
                opt.step()
            torch.testing.assert_close(restored(self.ids).logits, model(self.ids).logits)
        # 従来の両キー形式は許容するが矛盾する値は拒否する
        restored.load_state_dict(model.state_dict(), strict=True)
        bad = dict(model.state_dict())
        bad["lm_head.weight"] = bad["lm_head.weight"] + 1
        with self.assertRaises(ValueError):
            restored.load_state_dict(bad)


class LoopedRunnerTest(unittest.TestCase):
    def test_configs_counts_and_three_epochs(self):
        base = yaml.safe_load((ROOT / "config/boku_nano_1m_bpe_2048_1epoch.yaml").read_text())
        evaluation = yaml.safe_load((ROOT / "config/boku_nano_1m_bpe_2048_1epoch_evaluation.yaml").read_text())
        expected = {"u3": 1016704, "u1": 688512, "l1": 688512, "t3": 754560,
                    "lt1": 426368, "lt2": 590464, "f128": 377216,
                    "w96": 289056, "w64": 172224}
        for name in VARIANTS:
            config, ev = build_configs(base, evaluation, name, Path("/tmp/test-loop") / name, 7, 3)
            model_config = BokuNanoConfig.from_dict(config["model"])
            self.assertEqual(config["training"]["epochs"], 3)
            self.assertEqual(config["model_validation"]["expected_parameter_count"], parameter_count(model_config))
            self.assertEqual(ev["model"]["expected_parameter_count"], parameter_count(model_config))
            self.assertEqual(config["data"], base["data"])
            if name in expected:
                self.assertEqual(parameter_count(model_config), expected[name])
        self.assertNotIn("n_loops", base["model"])

    def test_cli_generates_without_training_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plan"
            command = [sys.executable, str(ROOT / "scripts/model/run_boku_nano_looped_experiment.py"),
                       "--output-root", str(output), "--variants", "lt1", "w64"]
            subprocess.run(command, check=True, capture_output=True)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["epochs"], 3)
            self.assertFalse((output / "lt1_seed20260925/model").exists())
            result = subprocess.run(command, capture_output=True)
            self.assertNotEqual(result.returncode, 0)


@unittest.skipUnless(importlib.util.find_spec("onnx") and importlib.util.find_spec("onnxruntime"),
                     "ONNX export dependencies are optional")
class LoopedOnnxTest(unittest.TestCase):
    def test_dynamic_lengths_and_shared_initializer(self):
        import numpy as np
        import onnx
        import onnxruntime as ort
        from scripts.model.export_boku_nano_onnx import export_model
        config = BokuNanoConfig(vocab_size=32, d_model=16, n_layers=1, n_heads=2,
                                d_ff=32, context_length=16, n_loops=3, tie_word_embeddings=True)
        for mode in ("none", "add"):
            model = BokuNanoForCausalLM(replace(config, loop_input_mode=mode)).eval()
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "model.onnx"
                export_model(model, output, 4, 18)
                graph = onnx.load(output)
                tables = [value for value in graph.graph.initializer if list(value.dims) in ([32, 16], [16, 32])]
                # FFNの行列も同shapeなので、名前で語彙行列を照合する
                vocabulary = [value for value in tables if "token_embedding" in value.name or "lm_head" in value.name]
                self.assertEqual(len(vocabulary), 1)
                session = ort.InferenceSession(str(output), providers=["CPUExecutionProvider"])
                for length in (1, 7, 16):
                    ids = torch.arange(length)[None, :] % 32
                    actual = session.run(None, {"input_ids": ids.numpy()})[0]
                    with torch.inference_mode():
                        expected = model(ids).logits[:, -1].numpy()
                    np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=2e-5)


if __name__ == "__main__":
    unittest.main()
