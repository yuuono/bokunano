"""長いコード一致検査の字句正規化と一致判定を確認する。"""

import unittest

from scripts.validation.check_long_code_matches import ngrams, source_tokens


class LongCodeMatchTest(unittest.TestCase):
    def test_comments_and_layout_do_not_change_tokens(self) -> None:
        left = "def solve(xs, k):\n    # comment\n    return xs[:k]\n"
        right = "def solve(xs,k): return xs[:k]"
        self.assertEqual(source_tokens(left), source_tokens(right))

    def test_ngram_uses_exact_consecutive_tokens(self) -> None:
        values = ("a", "b", "c", "d")
        self.assertEqual(list(ngrams(values, 3)), [("a", "b", "c"), ("b", "c", "d")])


if __name__ == "__main__":
    unittest.main()
