"""Fixed common executable scoring for the browser benchmark (no code repairs)."""
from __future__ import annotations
import argparse, ast, builtins, hashlib, json, multiprocessing, queue, re, resource, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from reference_interpreter import interpret
from generated_code_verifier import build_verification_cases

CALLS={'abs','list','reversed','sorted','range','len','enumerate','min','max','sum','int'}
METHODS={'append','extend','sort','reverse','copy'}
NODES=(ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Return,ast.Assign,ast.AnnAssign,ast.For,ast.If,ast.AugAssign,ast.Name,ast.Load,ast.Store,ast.ListComp,ast.comprehension,ast.BinOp,ast.UnaryOp,ast.Compare,ast.Call,ast.Subscript,ast.Slice,ast.List,ast.Tuple,ast.Constant,ast.keyword,ast.Add,ast.Sub,ast.Mult,ast.Pow,ast.Mod,ast.FloorDiv,ast.Div,ast.USub,ast.UAdd,ast.Eq,ast.NotEq,ast.Gt,ast.GtE,ast.Lt,ast.LtE,ast.BoolOp,ast.And,ast.Or,ast.Not,ast.IfExp,ast.Attribute,ast.Expr,ast.Break,ast.Continue,ast.Pass)

def extract_code(raw):
    fences=re.findall(r'```[^\n]*\n([\s\S]*?)```',raw)
    if '```' in raw:
        if len(fences)!=1 or raw.count('```')!=2: raise ValueError('single_code_block_required')
        return fences[0].strip()+'\n'
    return raw.strip()+'\n'

def validate(source):
    if len(source)>12000: raise ValueError('source_length_limit')
    tree=ast.parse(source)
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef): raise ValueError('one_solve_function_required')
    fn=tree.body[0];a=fn.args
    if fn.name!='solve' or fn.decorator_list or a.posonlyargs or a.vararg or a.kwonlyargs or a.kwarg or len(a.args)!=2 or [x.arg for x in a.args]!=['xs','k'] or a.defaults:
        raise ValueError('solve_xs_k_signature_required')
    bound={'xs','k'}|{n.id for n in ast.walk(fn) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
    calls={id(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)}
    for n in ast.walk(tree):
        if not isinstance(n,NODES): raise ValueError(f'unsupported_syntax:{type(n).__name__}')
        if isinstance(n,ast.FunctionDef) and n is not fn: raise ValueError('nested_function')
        if isinstance(n,ast.Name) and (n.id.startswith('__') or n.id not in bound|CALLS|{'int','list'}): raise ValueError(f'unsupported_name:{n.id}')
        if isinstance(n,ast.Attribute) and (id(n) not in calls or n.attr not in METHODS): raise ValueError('unsupported_attribute')
        if isinstance(n,ast.Call):
            if isinstance(n.func,ast.Name):
                if n.func.id not in CALLS: raise ValueError('unsupported_call')
            elif not isinstance(n.func,ast.Attribute) or n.func.attr not in METHODS: raise ValueError('unsupported_call')
        if isinstance(n,ast.Constant) and not isinstance(n.value,(int,str,type(None),bool)): raise ValueError('unsupported_constant')
    return tree

def all_cases():
    cases=build_verification_cases(2026100501,128)
    for k in range(1,11):
        for xs in ([k-1,k,k+1,-k,0,2*k,-2*k], [3,-2,0,8,1,8,-7], list(range(-10,10)), [k]*5):
            cases.append((list(xs),k))
    return cases

def _worker(source,semantic_ast,cases,out):
    try:
        resource.setrlimit(resource.RLIMIT_CPU,(2,2))
        ns={'__builtins__':{name:getattr(builtins,name) for name in CALLS}}
        exec(compile(source,'<benchmark>','exec',flags=__import__('__future__').annotations.compiler_flag),ns)
        for i,(original,k) in enumerate(cases):
            xs=list(original);expected=interpret(semantic_ast,list(xs),k)
            try: actual=ns['solve'](xs,k)
            except BaseException as e:
                out.put({'passed':False,'reason':'runtime_error','error':f'{type(e).__name__}: {e}','test_index':i,'xs':original,'k':k,'expected':expected});return
            if xs!=original or not isinstance(actual,list) or any(type(x) is not int for x in actual) or actual!=expected:
                out.put({'passed':False,'reason':'input_mutation' if xs!=original else 'output_mismatch','test_index':i,'xs':original,'k':k,'expected':expected,'actual':repr(actual)[:3000]});return
        out.put({'passed':True,'reason':'pass','tests_passed':len(cases)})
    except BaseException as e: out.put({'passed':False,'reason':'runtime_error','error':f'{type(e).__name__}: {e}'})

def verify(source,semantic_ast,cases):
    try: validate(source)
    except SyntaxError as e: return {'passed':False,'reason':'syntax_error','error':str(e)}
    except ValueError as e: return {'passed':False,'reason':'contract_or_allowed_syntax','error':str(e)}
    ctx=multiprocessing.get_context('spawn');out=ctx.Queue();p=ctx.Process(target=_worker,args=(source,semantic_ast,cases,out));p.start()
    try: result=out.get(timeout=3)
    except queue.Empty: result={'passed':False,'reason':'timeout_or_process_exit','exitcode':p.exitcode}
    finally:
        if p.is_alive(): p.terminate()
        p.join();out.close()
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--questions',type=Path,required=True);parser.add_argument('--run',type=Path,required=True);args=parser.parse_args()
    qs={q['question_id']:q for q in map(json.loads,args.questions.read_text().splitlines())}
    records=[json.loads(x) for x in (args.run/'raw_inference.jsonl').read_text().splitlines()]
    cases=all_cases()
    for q in qs.values():
        witness=q.get('order_sensitivity_witness')
        if witness and (witness['xs'],witness['k']) not in cases:cases.append((witness['xs'],witness['k']))
    (args.run/'test_cases.json').write_text(json.dumps([{'xs':xs,'k':k} for xs,k in cases],indent=2)+'\n')
    results=[];seen=set()
    for r in records:
        if r['kind']!='inference' or r['condition']=='C-normalize':continue
        key=(r['model'],r['condition'],r['question_id'])
        if key in seen:raise ValueError(f'Duplicate inference: {key}')
        seen.add(key);q=qs[r['question_id']]
        try: code=extract_code(r['raw_output'])
        except ValueError as e: code='';result={'passed':False,'reason':'code_extraction','error':str(e)}
        else:
            result=verify(code,q['semantic_ast'],cases) if not r.get('error') else {'passed':False,'reason':r['error']}
        results.append({**{k:r[k] for k in ['model','condition','question_id','category_id']},'code':code,**result})
    (args.run/'scored.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in results))
    summary={}
    for m,c in sorted({(r['model'],r['condition']) for r in results}):
        subset=[r for r in results if r['model']==m and r['condition']==c]
        summary[f'{m}/{c}']={'passed':sum(r['passed'] for r in subset),'total':len(subset),'categories':{cat:sum(r['passed'] for r in subset if r['category_id']==cat) for cat in sorted({q['category_id'] for q in qs.values()})}}
    (args.run/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
