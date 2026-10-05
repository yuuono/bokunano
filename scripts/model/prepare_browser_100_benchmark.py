"""Validate and freeze the development questions before inference."""
from collections import Counter
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path
from scripts.model.score_browser_100_benchmark import all_cases, verify
from reference_interpreter import interpret

def main():
    root=Path(__file__).resolve().parents[2]
    path=root/'data/benchmarks/browser_100/dev50.jsonl'
    qs=[json.loads(x) for x in path.read_text().splitlines()]
    assert len(qs)==50 and len({q['question_id'] for q in qs})==50
    assert Counter(q['category_id'] for q in qs)=={f'C{i:02}':5 for i in range(1,11)}
    cases=all_cases()
    for q in qs:
        w=q.get('order_sensitivity_witness')
        if w and (w['xs'],w['k']) not in cases:cases.append((w['xs'],w['k']))
    for q in qs:
        r=verify(q['reference_code'],q['semantic_ast'],cases)
        assert r['passed'],(q['question_id'],r)
        w=q.get('order_sensitivity_witness')
        if w:
            assert interpret(q['semantic_ast'],w['xs'],w['k'])==w['expected']
            assert w['expected']!=w['reversed_order_expected']
    manifest=json.loads((root/'web/model-manifest.json').read_text())
    model=next(x for x in manifest['models'] if x['id']=='15m-1epoch')
    tokenizer=manifest['tokenizers'][model['tokenizer_id']]
    for artifact in [model,tokenizer]:
        assert hashlib.sha256((root/'web'/artifact['path']).read_bytes()).hexdigest()==artifact['sha256']
    out=root/'data/benchmarks/browser_100/runs/dev50-20261005'
    out.mkdir(parents=True,exist_ok=True)
    (out/'test_cases.json').write_text(json.dumps([{'xs':x,'k':k} for x,k in cases],indent=2)+'\n')
    review={'questions_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'frozen_at':datetime.now(timezone.utc).isoformat(),'question_count':50,'tests_per_question':len(cases),'reference_tests_passed':50*len(cases),'reviewer':'parent coding agent (AI)','human_approval':False,'meaning_review':'all 50 Japanese instructions read against ordered semantic AST; no changes to meanings','reference_comparison':'all reference implementations pass shared boundary/random/order-witness tests','local_model_and_tokenizer_hashes':'verified','score_seen_before_freeze':False,'scoring_timeout_seconds':3,'cpu_limit_seconds':2,'source_chars_limit':12000,'case_seed':2026100501,'random_cases':128}
    (out/'preflight_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n');print(json.dumps(review,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
