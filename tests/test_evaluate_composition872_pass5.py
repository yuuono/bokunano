"""pass@5の候補対応・既存greedy保持・途中再開を、GPU/実コード実行なしで検証する。"""
from __future__ import annotations

import copy
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.model import evaluate_composition872_pass5 as runner


class FakeTokenizer:
    def token_to_id(self, token):
        return {"<|pad|>": 0, "<|bos|>": 1, "<|eos|>": 2, "<|unk|>": 3, "<|task|>": 4, "<|code|>": 5}[token]

    def encode(self, text, add_special_tokens=False):
        return SimpleNamespace(ids=[1, 4, 7, 5])

    def decode(self, ids, skip_special_tokens=True):
        return " ".join(str(value) for value in ids)


def fixture():
    questions = [{"question_id": f"q{index}", "suite": "general_4op", "category_id": f"c{index}",
                  "ast_id": f"ast{index}", "instruction_ja": f"指示{index}"} for index in range(2)]
    prompts = [[1, 4, 7, 5] for _ in questions]
    raw = [{"kind": "inference", "model": "custom", "condition": "A", "question_id": q["question_id"],
            "suite": q["suite"], "category_id": q["category_id"], "instruction": q["instruction_ja"],
            "prompt": runner.greedy.PROMPT_TEMPLATE.format(instruction_ja=q["instruction_ja"]),
            "prompt_ids": prompt, "output_ids": [8], "termination": "eos", "raw_output": "8"}
           for q, prompt in zip(questions, prompts)]
    scores = [{key: row[key] for key in ("model", "condition", "question_id", "suite", "category_id", "termination")}
              | {"ast_id": q["ast_id"], "code": "8", "passed": index == 1,
                 "reason": "pass" if index == 1 else "output_mismatch", "tests_passed": 2 if index == 1 else None}
              for index, (row, q) in enumerate(zip(raw, questions))]
    spec = {"name": "custom", "directory": "/unused", "model_config": {}, "parameter_count": 1,
            "epochs": 1, "weight_sha256": "a" * 64, "tokenizer_sha256": runner.greedy.TOKENIZER_SHA256,
            "tokenizer_path": "/unused/tokenizer.json", "source_hashes": {}}
    item = {"spec": spec, "run_root": "/unused/greedy", "greedy_artifact_hashes": {},
            "greedy_raw": raw, "greedy_scored": scores}
    sampler = lambda batch: [[{"generated_token_ids": [9], "termination": "eos"} for _ in range(4)] for _ in batch]
    candidates = runner.generate_candidates(questions, prompts, FakeTokenizer(), raw, "custom", 1, sampler)
    config = {"source_hashes": {}, "models": [spec], "question_batch_size": 1, "score_workers": 1}
    cases = [{"xs": [], "k": 1}, {"xs": [1], "k": 1}]
    return questions, prompts, item, candidates, config, cases


def fake_score(item):
    row, question, cases = item
    passed = row["candidate_index"] == 2 and row["question_id"] == "q0"
    return ({key: row[key] for key in ("model", "condition", "question_id", "suite", "category_id", "termination")}
            | {"ast_id": question["ast_id"], "code": row["raw_output"], "passed": passed,
               "reason": "pass" if passed else "output_mismatch", "tests_passed": len(cases) if passed else None})


class PassFiveTests(unittest.TestCase):
    def test_top_level_import_does_not_load_gpu_or_sampling_dependencies(self):
        command = [sys.executable, "-c", "import sys; import scripts.model.evaluate_composition872_pass5; "
                   "assert 'torch' not in sys.modules; assert 'tokenizers' not in sys.modules; "
                   "assert 'scripts.model.evaluate_boku_nano_comparison' not in sys.modules"]
        result = subprocess.run(command, cwd=runner.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_candidate_order_duplicate_draws_and_greedy_are_preserved(self):
        questions, prompts, item, raw, _, _ = fixture()
        self.assertEqual(len(raw), 10)
        self.assertEqual([r["candidate_index"] for r in raw], [1, 2, 3, 4, 5] * 2)
        self.assertEqual([r["output_ids"] for r in raw[1:5]], [[9]] * 4)
        runner.validate_raw(raw, questions, prompts, FakeTokenizer(), item)
        changed = copy.deepcopy(raw)
        changed[0]["raw_output"] = "altered"
        with self.assertRaises(ValueError):
            runner.validate_raw(changed, questions, prompts, FakeTokenizer(), item)
        changed = copy.deepcopy(raw)
        changed[1]["sampling_seed"] += 1
        with self.assertRaisesRegex(ValueError, "sampling条件"):
            runner.validate_raw(changed, questions, prompts, FakeTokenizer(), item)

    def test_sampling_order_is_length_then_source_order_with_four_rows_per_question(self):
        prompts = [[1, 2, 3], [1], [2, 3, 4], [2], [5, 6]]
        self.assertEqual(runner.sampling_batches(prompts, 1), [[1], [3], [4], [0], [2]])
        self.assertEqual(runner.sampling_batches(prompts, 2), [[1, 3], [4], [0, 2]])

    def test_scoring_shards_resume_without_rescoring_and_reject_tampering(self):
        questions, _, _, raw, _, cases = fixture()
        scorer = Mock(side_effect=fake_score)
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "SCORE_CHUNK_SIZE", 3):
            folder = Path(temporary)
            first = runner.score_sampling(folder, raw, questions, cases, "config", "raw", scorer, 1)
            self.assertEqual(scorer.call_count, 8)
            second = runner.score_sampling(folder, raw, questions, cases, "config", "raw", scorer, 1)
            self.assertEqual(first, second)
            self.assertEqual(scorer.call_count, 8)
            with self.assertRaisesRegex(ValueError, "再開条件"):
                runner.score_sampling(folder, raw, questions, cases, "other-config", "raw", scorer, 1)
            path = folder / "scoring_batches/batch_0000.json"
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "shard hash"):
                runner.score_sampling(folder, raw, questions, cases, "config", "raw", scorer, 1)

    def test_pass_five_is_any_complete_candidate_and_reuses_exact_greedy(self):
        questions, _, item, raw, _, cases = fixture()
        sampled = [{**fake_score((r, questions[int(r["question_id"][1:])], cases)),
                    "candidate_index": r["candidate_index"], "decoding": "top_p"}
                   for r in raw if r["candidate_index"] > 1]
        scored = runner.complete_scores(item, raw, sampled)
        runner.validate_scores(scored, raw, {q["question_id"]: q for q in questions}, 2)
        results = runner.question_results(questions, scored, item["greedy_scored"])
        self.assertEqual([r["pass_at_1"] for r in results], [False, True])
        self.assertEqual([r["pass_at_5"] for r in results], [True, True])
        self.assertEqual([r["passed_count"] for r in results], [1, 1])
        summary = runner.summarize_questions(results, "custom")
        self.assertEqual((summary["pass_at_1_count"], summary["pass_at_5_count"]), (1, 2))
        self.assertEqual(summary["suites"]["general_4op"]["sampling_rescued_count"], 1)
        scored[1]["tests_passed"] = 1
        with self.assertRaisesRegex(ValueError, "全hidden"):
            runner.validate_scores(scored, raw, {q["question_id"]: q for q in questions}, 2)
        scored[0]["passed"] = True
        with self.assertRaisesRegex(ValueError, "既存greedy"):
            runner.question_results(questions, scored, item["greedy_scored"])

    def test_complete_model_artifacts_and_strict_resume(self):
        questions, prompts, item, raw, config, cases = fixture()
        generator = Mock(return_value=(raw, {"sampling_seconds": 1.0}))
        scorer = Mock(side_effect=fake_score)
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "generate_model_raw", generator):
            output = Path(temporary)
            summary = runner.run_model(output, config, item, questions, cases, FakeTokenizer(), prompts,
                                       None, None, scorer, False)
            self.assertEqual(summary["pass_at_5_count"], 2)
            self.assertEqual(generator.call_count, 1)
            self.assertEqual(scorer.call_count, 8)
            folder = output / "custom"
            provenance = runner.greedy.read_json(folder / "provenance.json")
            self.assertEqual(set(provenance["artifact_hashes"]), set(runner.ARTIFACT_NAMES))
            again = runner.run_model(output, config, item, questions, cases, FakeTokenizer(), prompts,
                                     None, None, scorer, True)
            self.assertEqual(summary, again)
            self.assertEqual((generator.call_count, scorer.call_count), (1, 8))
            (folder / "question_results.jsonl").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "hash不一致"):
                runner.run_model(output, config, item, questions, cases, FakeTokenizer(), prompts,
                                 None, None, scorer, True)

    def test_partial_score_resume_keeps_generation_and_committed_shards(self):
        questions, prompts, item, raw, config, cases = fixture()
        generator = Mock(return_value=(raw, {"sampling_seconds": 1.0}))
        count = 0

        def interrupted_score(arg):
            nonlocal count
            count += 1
            if count > 2:
                raise RuntimeError("simulated interruption")
            return fake_score(arg)

        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "generate_model_raw", generator), \
                patch.object(runner, "SCORE_CHUNK_SIZE", 2):
            output = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, "interruption"):
                runner.run_model(output, config, item, questions, cases, FakeTokenizer(), prompts,
                                 None, None, interrupted_score, False)
            progress = runner.greedy.read_json(output / "custom/scoring_progress.json")
            self.assertEqual(len(progress["shards"]), 1)
            scorer = Mock(side_effect=fake_score)
            summary = runner.run_model(output, config, item, questions, cases, FakeTokenizer(), prompts,
                                       None, None, scorer, True)
            self.assertEqual((generator.call_count, scorer.call_count), (1, 6))
            self.assertEqual(summary["pass_at_5_count"], 2)

    def test_validate_only_never_imports_torch_or_creates_output(self):
        questions, _, item, _, _, cases = fixture()
        fake_tokenizers = SimpleNamespace(Tokenizer=SimpleNamespace(from_file=lambda path: FakeTokenizer()))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "new-output"
            with patch.object(runner, "load_inputs", return_value=(questions, cases, [item], {})), \
                    patch.dict(sys.modules, {"tokenizers": fake_tokenizers, "torch": None}), patch("builtins.print"):
                runner.main(["--greedy-run-roots", "/unused/greedy", "--output-root", str(output), "--validate-only"])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
