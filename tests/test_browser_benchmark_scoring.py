import unittest
from scripts.model.score_browser_100_benchmark import extract_code, validate, verify

class BrowserScoringTests(unittest.TestCase):
    def test_qwen_style_append_without_annotations(self):
        source='def solve(xs, k):\n    out = []\n    for x in xs:\n        if x % 2 == 0:\n            out.append(x)\n    return out\n'
        self.assertTrue(verify(source,{'filter':['even']},[([1,2,-4],2),([],1)])['passed'])
    def test_wrong_order_has_counterexample(self):
        source='def solve(xs, k):\n    return sorted(xs[:k])\n'
        r=verify(source,{'sequence':[{'order':'ascending'},{'slice':['take_first_k']}]},[([9,1,2],2)])
        self.assertEqual(r['reason'],'output_mismatch');self.assertEqual(r['expected'],[1,2])
    def test_mutation_is_rejected(self):
        r=verify('def solve(xs, k):\n    xs.sort()\n    return xs\n',{'order':'ascending'},[([2,1],1)])
        self.assertEqual(r['reason'],'input_mutation')
    def test_imports_and_introspection_are_rejected(self):
        for source in ['import os\ndef solve(xs,k): return xs', 'def solve(xs,k): return xs.__class__', 'def solve(xs,k): return open("file")']:
            with self.assertRaises(ValueError):validate(source)
    def test_code_extraction_is_not_code_repair(self):
        self.assertEqual(extract_code('```python\ndef solve(xs,k): return xs\n```'),'def solve(xs,k): return xs\n')
        with self.assertRaises(ValueError):extract_code('```python\nx\n```\n```python\ny\n```')
        with self.assertRaises(SyntaxError):validate(extract_code('Here is code:\ndef solve(xs,k): return xs'))
if __name__=='__main__':unittest.main()
