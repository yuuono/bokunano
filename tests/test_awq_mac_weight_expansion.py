"""Guard AWQ nibble ordering and the Linear weight orientation used on Mac."""
import unittest
from scripts.model.run_qwen_awq_mac_benchmark import dequantize, validate_decoder


class AwqMacWeightExpansionTests(unittest.TestCase):
    def test_every_nibble_group_and_signed_packed_word(self):
        self.assertEqual(validate_decoder()['synthetic_all_nibbles_groups_signed_words'], 'exact_match')

    def test_known_packed_word_and_group_zero_points(self):
        import torch
        # AWQ packing stores columns in the order 0,2,4,6,1,3,5,7.
        packed = torch.tensor([[0x75316420], [0x75316420]], dtype=torch.int32)
        zeros = torch.tensor([[0x11111111], [0x22222222]], dtype=torch.int32)
        scales = torch.tensor([[0.5] * 8, [2.0] * 8], dtype=torch.float16)
        result = dequantize(packed, zeros, scales, group_size=1)
        expected = torch.stack([(torch.arange(8)-1)*0.5, (torch.arange(8)-2)*2.0], dim=1).half()
        self.assertEqual(result.shape, (8, 2))
        self.assertEqual(result.dtype, torch.float16)
        self.assertTrue(torch.equal(result, expected))


if __name__ == '__main__':
    unittest.main()
