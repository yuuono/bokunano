"""Frozen benchmark semantics for up to four operations; no training-code changes."""
from pathlib import Path
import hashlib
import json
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from reference_interpreter import _apply_operation, _validate_inputs
BASE = ROOT / 'data/benchmarks/composition_suite_20261007'
SEED = 2026100703
key = lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while block := f.read(8 * 1024 * 1024): h.update(block)
    return h.hexdigest()
def read_jsonl(path): return [json.loads(line) for line in Path(path).read_text().splitlines()]
def interpret(ast, xs, k):
    _validate_inputs(xs, k)
    seq = ast.get('sequence', [ast])
    if not isinstance(seq, list) or not 1 <= len(seq) <= 4: raise ValueError('Expected 1–4 operations')
    result = list(xs)
    for op in seq: result = _apply_operation(op, result, k)
    return result

def reference_code(ast):
    filters = {'even':'x % 2 == 0', 'odd':'x % 2 != 0', 'gt_k':'x > k', 'ge_k':'x >= k', 'lt_k':'x < k', 'le_k':'x <= k', 'multiple_of_k':'x % k == 0', 'positive':'x > 0', 'negative':'x < 0', 'zero':'x == 0'}
    maps = {'add_k':'x + k', 'sub_k':'x - k', 'mul_k':'x * k', 'negate':'-x', 'abs':'abs(x)', 'square':'x ** 2'}
    lines = ['def solve(xs: list[int], k: int) -> list[int]:', '    result = list(xs)']
    for op in ast['sequence']:
        kind, arg = next(iter(op.items()))
        if kind == 'filter': expr = f'[x for x in result if {filters[arg[0]]}]'
        elif kind == 'map': expr = '[%s for x in result]' % (f'x * {arg[1]}' if arg[0] == 'mul_const' else maps[arg[0]])
        elif kind == 'order': expr = {'ascending':'sorted(result)', 'descending':'sorted(result, reverse=True)', 'reverse':'result[::-1]'}[arg]
        else: expr = {'take_first_k':'result[:k]', 'take_last_k':'result[-k:]', 'every_other':'result[::2]'}[arg[0]]
        lines.append('    result = ' + expr)
    return '\n'.join(lines + ['    return result', ''])

SUITES = {
    'transfer_1op': '複合→単独への表現の転用',
    'composition_original': '未学習の組み合わせ・既存50問',
    'composition_3op': '未学習の組み合わせ・追加3操作50問',
    'repeat_2': '同一操作の2回反復',
    'repeat_3': '同一操作の3回反復',
    'repeat_4': '同一操作の4回反復',
    'general_4op': '一般の4操作',
    'transfer_3to2': '既知の操作列の短い構成への汎化（3操作→2操作）',
    'repeat_abab': '2操作の組の2回反復（ABAB）',
}
