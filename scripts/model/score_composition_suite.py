"""Score raw generated code with fixed 179 inputs and four-operation semantics."""
from pathlib import Path
import argparse
import builtins
import concurrent.futures
import json
import multiprocessing
import queue
import resource
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.model.composition_suite_common import BASE,interpret,read_jsonl,sha
from scripts.model.score_browser_100_benchmark import CALLS,extract_code,validate

def worker(source,ast,cases,out):
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(2,2))
        ns={'__builtins__':{name:getattr(builtins,name) for name in CALLS}}
        exec(compile(source,'<benchmark>','exec',flags=__import__('__future__').annotations.compiler_flag),ns)
        for i,c in enumerate(cases):
            xs=list(c['xs']);k=c['k'];expected=interpret(ast,xs,k)
            try:actual=ns['solve'](xs,k)
            except BaseException as e:
                out.put({'passed':False,'reason':'runtime_error','error':f'{type(e).__name__}: {e}','test_index':i,**c,'expected':expected});return
            if xs!=c['xs'] or not isinstance(actual,list) or any(type(v) is not int for v in actual) or actual!=expected:
                out.put({'passed':False,'reason':'input_mutation' if xs!=c['xs'] else 'output_mismatch','test_index':i,**c,'expected':expected,'actual':repr(actual)[:3000]});return
        out.put({'passed':True,'reason':'pass','tests_passed':len(cases)})
    except BaseException as e:out.put({'passed':False,'reason':'runtime_error','error':f'{type(e).__name__}: {e}'})

def score_one(item):
    r,q,cases=item
    try:code=extract_code(r['raw_output']);validate(code)
    except SyntaxError as e:code=r['raw_output'];result={'passed':False,'reason':'syntax_error','error':str(e)}
    except ValueError as e:code=r['raw_output'];result={'passed':False,'reason':'contract_or_code_extraction','error':str(e)}
    else:
        ctx=multiprocessing.get_context('spawn');out=ctx.Queue();p=ctx.Process(target=worker,args=(code,q['semantic_ast'],cases,out));p.start()
        try:result=out.get(timeout=5)
        except queue.Empty:result={'passed':False,'reason':'timeout_or_process_exit','exitcode':p.exitcode}
        finally:
            if p.is_alive():p.terminate()
            p.join();out.close()
    return {k:r[k] for k in ('model','condition','question_id','suite','category_id')}|{'ast_id':q['ast_id'],'code':code,'termination':r['termination'],**result}

def main(args):
    protocol=json.loads((BASE/'protocol.json').read_text());assert sha(BASE/'questions.jsonl')==protocol['questions_sha256'];assert sha(BASE/'test_cases.json')==protocol['test_cases_sha256']
    questions={q['question_id']:q for q in read_jsonl(BASE/'questions.jsonl')};cases=json.loads((BASE/'test_cases.json').read_text());run=BASE/'runs'/args.model
    raw=read_jsonl(run/'raw_inference.jsonl');assert raw[-1]['kind']=='complete';rs=[r for r in raw if r['kind']=='inference'];assert len(rs)==len(questions) and {r['question_id'] for r in rs}==set(questions)
    output=run/'scored.jsonl';results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool, output.open('w') as f:
        for r in pool.map(score_one,[(r,questions[r['question_id']],cases) for r in rs]):
            results.append(r);f.write(json.dumps(r,ensure_ascii=False)+'\n')
    summary={suite:{'passed':sum(r['passed'] for r in results if r['suite']==suite),'total':sum(r['suite']==suite for r in results)} for suite in protocol['suites']}
    (run/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (run/'scoring_provenance.json').write_text(json.dumps({'scorer_sha256':sha(Path(__file__)),'common_sha256':sha(ROOT/'scripts/model/composition_suite_common.py'),'raw_inference_sha256':sha(run/'raw_inference.jsonl'),'questions_sha256':sha(BASE/'questions.jsonl'),'test_cases_sha256':sha(BASE/'test_cases.json')},indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--model',required=True);main(parser.parse_args())
