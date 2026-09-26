"""Boku-nano評価のprompt、greedy生成、固定設定を検証する。"""

from pathlib import Path
from types import SimpleNamespace
import unittest

import torch
from tokenizers import Tokenizer

from scripts.model.evaluate_boku_nano import (
    SUPPORTED_SUITES,
    cases_for_record,
    encode_prompt,
    greedy_generate_equal_length,
    validate_configuration,
)
from scripts.model.evaluate_boku_nano_comparison import (
    is_executable,
    sample_generate_equal_length,
    selection_score,
)


class FakeGreedyModel:
    """batch別の次token IDを順番に返す。"""

    def __init__(self, step_token_ids: list[list[int]], vocab_size: int = 16) -> None:
        self.step_token_ids = step_token_ids
        self.vocab_size = vocab_size
        self.step = 0

    def __call__(self, input_ids: torch.Tensor) -> SimpleNamespace:
        token_ids = self.step_token_ids[self.step]
        if len(token_ids) != input_ids.size(0):
            raise ValueError("fake token IDsのbatch数が一致しません")
        logits = torch.full(
            (input_ids.size(0), input_ids.size(1), self.vocab_size),
            -1000.0,
            device=input_ids.device,
        )
        for index, token_id in enumerate(token_ids):
            logits[index, -1, token_id] = 1000.0
        self.step += 1
        return SimpleNamespace(logits=logits)


class BokuNanoEvaluationTest(unittest.TestCase):
    """固定prompt、終了条件、case選択、artifact整合性を確認する。"""

    def test_prompt_encoding_matches_training_template(self) -> None:
        """promptはBOS、task、codeを各1個含みEOSを含まない。"""

        tokenizer = Tokenizer.from_file("data/tokenizers/bpe_2048/tokenizer.json")
        special_ids = {"pad": 0, "bos": 1, "eos": 2, "unk": 3, "task": 4, "code": 5}
        token_ids = encode_prompt(
            tokenizer,
            "整数リストxsから偶数を残すsolve関数を書いてください。",
            special_ids,
            context_length=256,
        )
        self.assertEqual(token_ids[0], special_ids["bos"])
        self.assertEqual(token_ids.count(special_ids["task"]), 1)
        self.assertEqual(token_ids.count(special_ids["code"]), 1)
        self.assertNotIn(special_ids["eos"], token_ids)
        self.assertNotIn(special_ids["unk"], token_ids)

    def test_greedy_generation_stops_each_sequence_at_eos(self) -> None:
        """終了済み系列をpaddingしながら他系列だけを継続する。"""

        model = FakeGreedyModel([[6, 2], [2, 7]])
        outputs = greedy_generate_equal_length(
            model,  # type: ignore[arg-type]
            [[1, 4, 5], [1, 4, 5]],
            eos_token_id=2,
            pad_token_id=0,
            max_new_tokens=4,
            context_length=8,
            device=torch.device("cpu"),
        )
        self.assertEqual(outputs[0]["generated_token_ids"], [6])
        self.assertEqual(outputs[1]["generated_token_ids"], [])
        self.assertEqual([item["termination"] for item in outputs], ["eos", "eos"])

    def test_boundary_cases_include_only_matching_target(self) -> None:
        """共通caseへ対象specのfilter caseだけを追加する。"""

        manifest = {
            "shared_cases": [{"xs": [], "k": 1}],
            "targeted_filter_cases": [
                {"spec_id": "spec-a", "xs": [1], "k": 2},
                {"spec_id": "spec-b", "xs": [3], "k": 4},
            ],
        }
        cases = cases_for_record(manifest, "boundary", "spec-b")
        self.assertEqual(cases, [([], 1), ([3], 4)])

    def test_comparison_selection_score_is_seeded_and_deterministic(self) -> None:
        """比較集合のhash順はrecord IDとseedだけで決まる。"""

        first = selection_score("record-a", 123)
        self.assertEqual(first, selection_score("record-a", 123))
        self.assertNotEqual(first, selection_score("record-a", 124))
        self.assertNotEqual(first, selection_score("record-b", 123))

    def test_sample_generation_returns_candidates_per_prompt(self) -> None:
        """top-p生成はpromptごとに指定数の候補を返しEOSで止まる。"""

        model = FakeGreedyModel([[6, 6, 2, 2], [2, 2, 7, 7]])
        generator = torch.Generator(device="cpu")
        generator.manual_seed(123)
        outputs = sample_generate_equal_length(
            model,  # type: ignore[arg-type]
            [[1, 4, 5], [1, 4, 5]],
            candidates_per_prompt=2,
            eos_token_id=2,
            pad_token_id=0,
            max_new_tokens=4,
            context_length=8,
            temperature=1.0,
            top_p=0.01,
            device=torch.device("cpu"),
            generator=generator,
        )
        self.assertEqual(len(outputs), 2)
        self.assertEqual([len(candidates) for candidates in outputs], [2, 2])
        self.assertEqual(
            [candidate["generated_token_ids"] for candidate in outputs[0]],
            [[6], [6]],
        )
        self.assertEqual(
            [candidate["generated_token_ids"] for candidate in outputs[1]],
            [[], []],
        )

    def test_executable_allows_functional_mismatch_only(self) -> None:
        """実行結果不一致は実行可能、例外とtimeoutは実行不能とする。"""

        base = {
            "signature_ok": True,
            "timeout": False,
            "error": "不一致: expected=[1], actual=[2]",
        }
        self.assertTrue(is_executable(base))
        self.assertFalse(is_executable({**base, "error": "NameError: x"}))
        self.assertFalse(is_executable({**base, "timeout": True}))
        self.assertFalse(is_executable({**base, "signature_ok": False}))

    def test_production_evaluation_configuration_is_consistent(self) -> None:
        """モデル、tokenizer、評価ZIP、5入力manifestのhashを照合する。"""

        summary = validate_configuration(Path("config/boku_nano_evaluation.yaml"))
        self.assertEqual(set(summary["suites"]), set(SUPPORTED_SUITES))
        self.assertEqual(summary["parameter_count"], 15_735_168)
        self.assertEqual(
            sum(item["expected_record_count"] for item in summary["suites"].values()),
            84_550,
        )


if __name__ == "__main__":
    unittest.main()
