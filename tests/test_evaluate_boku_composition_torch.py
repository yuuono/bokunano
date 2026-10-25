"""CUDA評価runnerの制御を検証する。実モデル・実推論・GPUは使用しない。"""
from __future__ import annotations

import builtins
from contextlib import nullcontext
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.model import evaluate_boku_composition_torch as runner


class FakeTokenizer:
    def token_to_id(self, token):
        return {"<|pad|>": 0, "<|bos|>": 1, "<|eos|>": 2,
                "<|unk|>": 3, "<|task|>": 4, "<|code|>": 5}[token]

    def encode(self, text, add_special_tokens):
        assert add_special_tokens is False
        return SimpleNamespace(ids=[1, 4, 7, 5])

    def decode(self, tokens, skip_special_tokens):
        assert skip_special_tokens is True
        return " ".join(map(str, tokens))


class FrozenTorchRunnerTests(unittest.TestCase):
    def test_equal_length_groups_are_bounded_and_lossless(self):
        prompts = [[1], [2, 3], [4], [5], [6, 7]]
        self.assertEqual(runner.grouped_batches(prompts, 2), [[0, 2], [3], [1, 4]])
        with self.assertRaises(ValueError):
            runner.grouped_batches(prompts, 0)

    def test_eos_is_excluded_and_does_not_stop_other_rows(self):
        calls = []

        def predict(rows):
            calls.append(copy.deepcopy(rows))
            return [2, 9] if len(rows[0]) == 2 else [8, 2]

        result = runner.greedy_equal_length([[1, 4], [1, 5]], predict, context_length=6)
        self.assertEqual(result, [{"output_ids": [], "termination": "eos"},
                                  {"output_ids": [9], "termination": "eos"}])
        self.assertEqual(calls[1], [[1, 4, 2], [1, 5, 9]])

    def test_total_context_limit_and_eos_at_last_step(self):
        result = runner.greedy_equal_length([[1, 4, 5]], lambda rows: [7], context_length=5)
        self.assertEqual(result, [{"output_ids": [7, 7], "termination": "max_context"}])
        result = runner.greedy_equal_length([[1, 4, 5]], lambda rows: [2], context_length=4)
        self.assertEqual(result, [{"output_ids": [], "termination": "eos"}])
        for prompts in ([], [[]], [[1], [1, 2]], [[1] * 5]):
            with self.assertRaises(ValueError):
                runner.greedy_equal_length(prompts, lambda rows: [2], context_length=5)
        with self.assertRaises(ValueError):
            runner.greedy_equal_length([[1]], lambda rows: [])

    def test_original_question_order_survives_grouping(self):
        questions = [{"question_id": f"q{i}", "suite": "general_4op", "category_id": f"c{i}",
                      "instruction_ja": f"指示{i}"} for i in range(4)]
        prompts = [[1, 7], [1, 9, 9], [1, 8], [1, 6, 6]]

        def predict(rows):
            return [2 if row[-1] == 10 else 10 for row in rows]

        rows = runner.generate_records(questions, prompts, FakeTokenizer(), "test", 2, predict)
        self.assertEqual([row["question_id"] for row in rows], ["q0", "q1", "q2", "q3"])
        self.assertEqual([row["batch_id"] for row in rows], [0, 1, 0, 1])
        self.assertEqual([row["prompt_ids"] for row in rows], prompts)
        self.assertTrue(all(row["output_ids"] == [10] and row["termination"] == "eos" for row in rows))
        self.assertTrue(all(row["batch_size"] == 2 for row in rows))
        runner.validate_record_identity(rows, questions, "test")
        with self.assertRaises(ValueError):
            runner.validate_record_identity(rows[:-1] + [rows[0]], questions, "test")

    def test_prompt_format_and_unknown_or_oversized_rejected(self):
        questions = [{"question_id": "q", "instruction_ja": "条件"}]
        self.assertEqual(runner.encode_prompts(questions, FakeTokenizer()), [[1, 4, 7, 5]])
        for ids in ([1, 3, 5], [1] * 256, [], [4, 5]):
            tokenizer = FakeTokenizer()
            tokenizer.encode = lambda *args, **kwargs: SimpleNamespace(ids=ids)
            with self.assertRaises(ValueError):
                runner.encode_prompts(questions, tokenizer)

    def test_model_selection_and_output_guards(self):
        self.assertEqual(list(runner.select_models(None, [])), runner.DEFAULT_SELECTION)
        self.assertEqual(list(runner.select_models(None, ["custom=data/models/custom"])), ["custom"])
        self.assertEqual(list(runner.select_models(["boku-15m-1epoch"], ["custom=data/models/custom"])),
                         ["boku-15m-1epoch", "custom"])
        for specification in ("../escape=/tmp", "bad", "name=", "=path", "bad/name=/tmp"):
            with self.assertRaises(ValueError):
                runner.select_models(None, [specification])
        with self.assertRaises(ValueError):
            runner.select_models(None, ["custom=a", "custom=b"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner.require_new_output(root / "new")
            with self.assertRaises(FileExistsError):
                runner.require_new_output(root)
            (root / "dangling").symlink_to(root / "missing")
            with self.assertRaises(FileExistsError):
                runner.require_new_output(root / "dangling")

    def test_main_rejects_dangling_output_symlink_before_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            link = root / "results"
            link.symlink_to(root / "missing-target")
            with patch.object(runner, "validate_dataset") as validation:
                with self.assertRaises(FileExistsError):
                    runner.main(["--output-root", str(link), "--validate-only"])
                validation.assert_not_called()
            self.assertTrue(link.is_symlink())
            self.assertFalse((root / "missing-target").exists())

    def test_compare_records_counts_token_and_pass_changes_separately(self):
        old = [{"question_id": "q", "prompt_ids": [1], "output_ids": [8], "raw_output": "8", "termination": "eos"}]
        current = [{**old[0], "output_ids": [9], "raw_output": "9"}]
        comparison = runner.compare_records(current, old, [{"question_id": "q", "passed": True}],
                                             [{"question_id": "q", "passed": False}])
        self.assertEqual(comparison["different_generation_count"], 1)
        self.assertEqual(comparison["pass_change_count"], 1)
        with self.assertRaises(ValueError):
            runner.compare_records(current, [])

    def test_reference_rejects_missing_root_wrong_hash_and_wrong_ast(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec = {"name": "custom", "weight_sha256": "original-safetensors"}
            question = {"question_id": "q", "instruction_ja": "指示", "suite": "general_4op",
                        "category_id": "c", "ast_id": "original-ast"}
            prompts = [[1, 4, 7, 5]]
            with self.assertRaises(FileNotFoundError):
                runner.load_reference(root / "missing", spec, [question], prompts)
            self.assertIsNone(runner.load_reference(root, spec, [question], prompts))
            directory = root / "custom"
            directory.mkdir()
            config = {"questions_sha256": runner.QUESTIONS_SHA256, "tokenizer_sha256": runner.TOKENIZER_SHA256,
                      "catalog_entry": {"source_weight_sha256": "original-safetensors"},
                      "prompt_template": runner.PROMPT_TEMPLATE, "context_length": 256,
                      "temperature": 0, "history": False, "repair": False}
            raw_row = {"kind": "inference", "model": "custom", "condition": "A", "question_id": "q",
                       "suite": "general_4op", "category_id": "c", "instruction": "指示",
                       "prompt": runner.PROMPT_TEMPLATE.format(instruction_ja="指示"), "prompt_ids": prompts[0]}
            scored = [{**raw_row, "ast_id": "original-ast", "passed": True}]
            runner.write_json(directory / "config.json", config)
            runner.write_jsonl(directory / "raw_inference.jsonl", [raw_row, {"kind": "complete"}])
            runner.write_jsonl(directory / "scored.jsonl", scored)
            runner.write_json(directory / "summary.json", runner.summarize(scored))
            runner.write_json(directory / "scoring_provenance.json", {
                "questions_sha256": runner.QUESTIONS_SHA256, "test_cases_sha256": runner.TEST_CASES_SHA256,
                "scorer_sha256": runner.SCORING_HASHES["scripts/model/score_composition_suite.py"],
                "common_sha256": runner.SCORING_HASHES["scripts/model/composition_suite_common.py"],
                "raw_inference_sha256": runner.sha(directory / "raw_inference.jsonl")})
            reference = runner.load_reference(root, spec, [question], prompts)
            self.assertEqual(reference["scored"], scored)
            scored[0]["ast_id"] = "different-ast"
            (directory / "scored.jsonl").write_text(json.dumps(scored[0]) + "\n")
            with self.assertRaisesRegex(ValueError, "AST"):
                runner.load_reference(root, spec, [question], prompts)
            config["questions_sha256"] = "wrong-dataset"
            runner.write_json(directory / "config.json", config)
            with self.assertRaisesRegex(ValueError, "hash"):
                runner.load_reference(root, spec, [question], prompts)

    def test_frozen_dataset_protocol_hash_cannot_be_self_declared(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner.write_json(root / "protocol.json", {"questions_sha256": "tampered"})
            with self.assertRaisesRegex(ValueError, "protocol"):
                runner.validate_dataset(root)

    def test_validate_model_uses_only_metadata_and_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = {"context_length": 256, "vocab_size": 2048}
            (root / "model.safetensors").write_bytes(b"mock-not-weights")
            (root / "tokenizer.json").write_text("{}")
            runner.write_json(root / "model_config.json", config)
            manifest = {"status": "completed", "model_config": config, "model_sha256": "weight",
                        "tokenizer_path": str(root / "tokenizer.json"), "tokenizer_sha256": runner.TOKENIZER_SHA256}
            runner.write_json(root / "training_manifest.json", manifest)
            fake_hash = lambda path: runner.TOKENIZER_SHA256 if path.name == "tokenizer.json" else "weight"
            with patch.object(runner, "sha", side_effect=fake_hash):
                result = runner.validate_model("custom", root)
                self.assertEqual(result["weight_sha256"], "weight")
                with self.assertRaisesRegex(ValueError, "固定checkpoint"):
                    runner.validate_model("boku-15m-1epoch", root)
                manifest["status"] = "running"
                runner.write_json(root / "training_manifest.json", manifest)
                with self.assertRaises(ValueError):
                    runner.validate_model("custom", root)

    def test_same_baseline_weights_with_changed_loop_config_require_another_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = "boku-1m-3epoch"
            config = {"context_length": 256, "vocab_size": 2048, "n_loops": 2}
            (root / "model.safetensors").write_bytes(b"mock-not-weights")
            (root / "tokenizer.json").write_text("{}")
            runner.write_json(root / "model_config.json", config)
            manifest = {"status": "completed", "model_config": config,
                        "model_sha256": runner.BASELINE_WEIGHTS[baseline],
                        "tokenizer_path": str(root / "tokenizer.json"), "tokenizer_sha256": runner.TOKENIZER_SHA256}
            runner.write_json(root / "training_manifest.json", manifest)
            original_sha = runner.sha

            def fake_artifact_hash(path):
                if path.name == "model.safetensors":
                    return runner.BASELINE_WEIGHTS[baseline]
                if path.name == "tokenizer.json":
                    return runner.TOKENIZER_SHA256
                return original_sha(path)

            with patch.object(runner, "sha", side_effect=fake_artifact_hash):
                with self.assertRaisesRegex(ValueError, "固定model_config"):
                    runner.validate_model(baseline, root)
                spec = runner.validate_model("custom-two-loops", root)
                self.assertEqual(spec["model_config"]["n_loops"], 2)
                self.assertEqual(spec["weight_sha256"], runner.BASELINE_WEIGHTS[baseline])

    def test_validate_only_cannot_import_torch_or_load_weights_or_create_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "results"
            spec = {"name": "custom", "tokenizer_path": "fake.json", "source_hashes": {}}
            questions = [{"question_id": "q", "instruction_ja": "指示"}]
            fake_tokenizers = SimpleNamespace(Tokenizer=SimpleNamespace(from_file=lambda path: FakeTokenizer()))
            original_import = builtins.__import__

            def guarded_import(name, *args, **kwargs):
                if name.startswith(("torch", "safetensors")) or name.endswith("boku_nano"):
                    self.fail("validate-only must not import model/torch/weight loaders")
                return original_import(name, *args, **kwargs)

            with patch.object(runner, "validate_dataset", return_value=(questions, [], {})), \
                    patch.object(runner, "validate_model", return_value=spec), \
                    patch.object(runner, "sha", return_value="mockhash"), \
                    patch.dict(sys.modules, {"tokenizers": fake_tokenizers}), \
                    patch("builtins.__import__", side_effect=guarded_import), patch("builtins.print"):
                runner.main(["--model", "custom=/unused", "--output-root", str(output), "--validate-only"])
            self.assertFalse(output.exists())

    def test_mock_run_writes_complete_artifacts_and_calls_original_score_entry(self):
        """モデル・torch・旧採点関数を全てfake化し、実推論やコード実行を起こさない。"""
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "results"
            spec = {"name": "custom", "directory": "/unused", "model_config": {}, "parameter_count": 1,
                    "epochs": 1, "tokenizer_path": "fake.json", "source_hashes": {}, "weight_sha256": "fake"}
            question = {"question_id": "q", "instruction_ja": "指示", "suite": "general_4op", "category_id": "c"}
            cases = [{"xs": [], "k": 1}]

            class FakeLogits:
                def __getitem__(self, key):
                    return self

                def argmax(self, dim):
                    return self

                def tolist(self):
                    return [2]

            class FakeModel:
                def __init__(self, config):
                    pass

                def load_state_dict(self, state, strict):
                    assert strict is True and state == {}

                def parameter_count(self):
                    return 1

                def to(self, **kwargs):
                    return self

                def eval(self):
                    return self

                def __call__(self, value):
                    return SimpleNamespace(logits=FakeLogits())

            cuda = SimpleNamespace(is_available=lambda: True, get_device_name=lambda device: "FAKE",
                                   reset_peak_memory_stats=lambda device: None, synchronize=lambda device: None,
                                   max_memory_allocated=lambda device: 0, empty_cache=lambda: None)
            fake_torch = SimpleNamespace(cuda=cuda, version=SimpleNamespace(cuda="fake", hip=None), __version__="fake",
                                         set_float32_matmul_precision=lambda value: None,
                                         backends=SimpleNamespace(cuda=SimpleNamespace(matmul=SimpleNamespace()), cudnn=SimpleNamespace()),
                                         device=lambda name: name, inference_mode=nullcontext, tensor=lambda value, **kwargs: value,
                                         long="long", float32="float32")
            fake_tokenizers = SimpleNamespace(Tokenizer=SimpleNamespace(from_file=lambda path: FakeTokenizer()))

            def fake_score(item):
                row, q, actual_cases = item
                self.assertIs(q, question)
                self.assertIs(actual_cases, cases)
                return {key: row[key] for key in ("model", "condition", "question_id", "suite", "category_id")} | {"passed": True}

            score_mock = Mock(side_effect=fake_score)
            modules = {"torch": fake_torch,
                       "torch.nn.attention": SimpleNamespace(SDPBackend=SimpleNamespace(MATH="math"), sdpa_kernel=lambda backend: nullcontext()),
                       "safetensors.torch": SimpleNamespace(load_file=lambda *args, **kwargs: {}),
                       "scripts.model.boku_nano": SimpleNamespace(BokuNanoConfig=SimpleNamespace(from_dict=lambda value: value), BokuNanoForCausalLM=FakeModel),
                       "scripts.model.score_composition_suite": SimpleNamespace(score_one=score_mock),
                       "tokenizers": fake_tokenizers}
            with patch.object(runner, "validate_dataset", return_value=([question], cases, {})), \
                    patch.object(runner, "validate_model", return_value=spec), patch.dict(sys.modules, modules), \
                    patch("builtins.print"):
                runner.main(["--model", "custom=/unused", "--output-root", str(output), "--check-batch-size-one"])
            self.assertEqual(score_mock.call_count, 2)
            comparison = runner.read_json(output / "comparison.json")
            self.assertEqual(comparison["status"], "completed")
            self.assertEqual(comparison["models"][0]["passed"], 1)
            self.assertEqual(comparison["models"][0]["batch_size_one_comparison"]["pass_change_count"], 0)
            raw = runner.read_jsonl(output / "custom/raw_inference.jsonl")
            self.assertEqual([row["kind"] for row in raw], ["environment", "inference", "complete"])
            for filename in ("config.json", "source_hashes.json", "scored.jsonl", "summary.json", "scoring_provenance.json",
                             "run_metrics.json", "batch_size_one_raw.jsonl", "batch_size_one_scored.jsonl", "batch_size_comparison.json"):
                self.assertTrue((output / "custom" / filename).exists(), filename)


if __name__ == "__main__":
    unittest.main()
