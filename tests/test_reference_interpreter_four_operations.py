import unittest

from reference_interpreter import interpret


class ReferenceInterpreterFourOperationTests(unittest.TestCase):
    def test_four_operations_are_applied_in_order(self) -> None:
        semantic_ast = {
            "sequence": [
                {"map": ["abs"]},
                {"filter": ["even"]},
                {"order": "descending"},
                {"slice": ["take_first_k"]},
            ]
        }
        self.assertEqual(interpret(semantic_ast, [-3, 2, -8, 4, 1], 2), [8, 4])

    def test_five_operations_remain_out_of_scope(self) -> None:
        semantic_ast = {"sequence": [{"map": ["abs"]}] * 5}
        with self.assertRaisesRegex(ValueError, "1〜4"):
            interpret(semantic_ast, [-1], 1)


if __name__ == "__main__":
    unittest.main()
