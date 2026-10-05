import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'web'))
from verification_runtime import verify


def run(code, semantic_ast=None, xs=None, k=3):
    return verify(dict(code=code, semanticAst=semantic_ast or {'order':'reverse'}, xs=xs if xs is not None else [3,-1,2,0,-4,5,2], k=k))


class VerificationTests(unittest.TestCase):
    def test_match_mismatch_and_exceptions(self):
        self.assertEqual(run('def solve(xs, k):\n return xs[::-1]')['status'], 'match')
        wrong = run('def solve(xs, k):\n return sorted(xs)')
        self.assertEqual(wrong['status'], 'mismatch')
        self.assertNotEqual(wrong['expected'], wrong['actual'])
        for code in ['def solve(', 'def solve(xs, k):\n return output', 'def solve(xs, k):\n return 1 // 0', 'def solve(xs, k):\n return True']:
            result = run(code)
            self.assertEqual(result['status'], 'code_error')
            self.assertIn('expected', result)

    def test_no_external_access_or_recursion(self):
        for code in ['import js\ndef solve(xs, k):\n return xs', 'def solve(xs, k):\n return xs.__class__', 'def solve(xs, k):\n return open("x")', 'def solve(xs, k):\n return solve(xs, k)', 'def solve(xs, k):\n return [2 ** 999999]']:
            self.assertEqual(run(code)['status'], 'code_error')

    def test_time_budget_and_fresh_inputs(self):
        expensive = 'def solve(xs, k):\n total = 0\n for x in range(1000):\n  for y in range(1000):\n   total += y\n return xs'
        result = run(expensive)
        self.assertEqual(result['status'], 'code_error')
        self.assertIn('TimeoutError', result['error'])
        self.assertEqual(run('def solve(xs, k):\n xs[0] = 999\n return xs')['status'], 'mismatch')
        self.assertEqual(run('def solve(xs, k):\n return xs[::-1]')['status'], 'match')

    def test_four_steps_and_repeated_squaring_keep_python_integers(self):
        meaning = {'sequence':[{'map':['add_k']},{'filter':['even']},{'map':['add_k']},{'order':'reverse'}]}
        code = 'def solve(xs, k):\n return [x + k for x in [v + k for v in xs] if x % 2 == 0][::-1]'
        self.assertEqual(run(code, meaning)['status'], 'match')
        square = {'sequence':[{'map':['square']}] * 4}
        result = run('def solve(xs, k):\n for i in range(4):\n  xs = [x ** 2 for x in xs]\n return xs', square, [100])
        self.assertEqual(result['status'], 'match')
        self.assertEqual(result['actual'], '[' + str(100 ** 16) + ']')

    def test_explicit_k_overrides_function_default(self):
        meaning = {'map':['add_k']}
        result = run('def solve(xs: list[int], k: int = 3) -> list[int]:\n return [x + k for x in xs]', meaning, [1], 7)
        self.assertEqual(result['actual'], '[8]')
        self.assertEqual(result['status'], 'match')
        for xs, k in [([True],3), ([101],3), ([],0), ([],11)]:
            self.assertEqual(run('def solve(xs,k):\n return xs', meaning, xs, k)['status'], 'reference_error')


if __name__ == '__main__':
    unittest.main()
