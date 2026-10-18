"""looped attentionの周回別捕捉を検証する。"""

import unittest

from scripts.model.analyze_looped_attention import capture_attention, effective_layer_labels
from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM


class LoopedAttentionTest(unittest.TestCase):
    def test_capture_returns_every_loop_and_physical_layer(self) -> None:
        config = BokuNanoConfig(
            vocab_size=32,
            d_model=16,
            n_layers=3,
            n_heads=4,
            d_ff=32,
            context_length=16,
            n_loops=3,
        )
        model = BokuNanoForCausalLM(config).eval()
        attention, logits = capture_attention(model, [1, 2, 3, 4])

        self.assertEqual(tuple(attention.shape), (9, 4, 4))
        self.assertEqual(tuple(logits.shape), (32,))
        self.assertTrue(attention.sum(dim=-1).allclose(attention.new_ones(9, 4)))

    def test_capture_supports_middle_looping_order(self) -> None:
        config = BokuNanoConfig(
            vocab_size=32,
            d_model=16,
            n_layers=3,
            n_heads=4,
            d_ff=32,
            context_length=16,
            n_loops=4,
            loop_pattern="middle",
        )
        model = BokuNanoForCausalLM(config).eval()
        attention, _logits = capture_attention(model, [1, 2, 3, 4])

        self.assertEqual(tuple(attention.shape), (6, 4, 4))
        self.assertEqual(
            effective_layer_labels(config),
            ["前段 / L1", "中間1 / L2", "中間2 / L2", "中間3 / L2", "中間4 / L2", "後段 / L3"],
        )


if __name__ == "__main__":
    unittest.main()
