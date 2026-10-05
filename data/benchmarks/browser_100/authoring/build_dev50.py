"""Materialize the author's fixed choices; no inference, model scoring, or score selection."""
import collections, datetime, hashlib, json, pathlib, re, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from python_code_generator import GeneratorConfig, generate_python_code
from structural_variant_generator import StructuralVariantGenerator
from reference_interpreter import interpret
BASE=ROOT/'data/benchmarks/browser_100'; A=BASE/'authoring'
def dump(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def hashfile(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
train=[json.loads(line) for line in (A/'train_reference.jsonl').open()]
byop=collections.defaultdict(list)
for r in train: byop[int(r['operation_id'].split('-')[-1])].append(r)
# Author-selected indices in the frozen train-only reference, not model-generated rankings.
def item(op,index=0):return byop[op][index]
cnltext=(ROOT/'web/cnl.js').read_text()
cnls=re.findall(r'\{ id: "([^"]+)", label: "([^"]+)", connective: "([^"]+)", final: "([^"]+)", requiresK: (true|false) \}',cnltext)
assert len(cnls)==24
cnl={i+1:dict(zip(['id','label','connective','final','requiresK'],row)) for i,row in enumerate(cnls)}
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
paths=['docs/policies/boku_nano_benchmark_100_plan.md','docs/specifications/atomic_semantic_asts.md','reference_interpreter.py','python_code_generator.py','structural_variant_generator.py','web/cnl.js','data/instruction_dictionaries/release/japanese_atomic_expressions.csv','data/instruction_dictionaries/release/japanese_atomic_expression_provenance.jsonl','config/build_approved_expression_dictionary.json','data/benchmarks/browser_100/authoring/train_reference.jsonl','data/benchmarks/browser_100/authoring/request_ja.txt','data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/training_manifest.json','data/final/final_train_dataset_stats.json','data/instructions/replacement_resolved_train_instruction_stats.json']
snapshot={p:{'path':p,'sha256':hashfile(ROOT/p),'git_commit':commit} for p in paths}
dump(A/'source_snapshot.json',{'created_at':now,'git_commit':commit,'references':list(snapshot.values()),'reference_roles':{'authoring_examples':'Only train_reference.jsonl; final approved fields only.','source_dictionary':'CSV read programmatically for extraction; first four rows also visible in initial inspection and confirmed train. CNL implementation inspection also displayed UI aliases overlapping some held-out wording; these were not used as authoring examples. Do not claim blind authoring.','split_config':'Read to exclude held-out IDs, never included in author prompt.','provenance':'Final approved fields checked; generation_record not used.','training_data':'Post-generation checks only; manifest and aggregate stats inspected before generation.'}})
# Select all questions before inspecting held-out expression texts or training instructions.
specs=[]
def add(cat,seq,overrides=None,instruction=None,tags=None):
 specs.append((cat,seq,overrides or {},instruction,tags or []))
for op in [1,2,8,9,10]:add('C01',[(op,0)])
for op in [3,4,5,6,7]:add('C02',[(op,0)])
for op,i in [(11,13),(12,0),(13,0),(16,3),(18,1)]:add('C03',[(op,i)])
for op,i in [(19,0),(20,1),(21,19),(19,2),(21,2)]:add('C04',[(op,i)])
for op,i in [(22,0),(23,1),(24,17),(22,2),(23,0)]:
 ov={0:('先頭の要素から始めて隔番で取り出す','adapted')} if op==24 else {}
 add('C05',[(op,i)],ov)
for seq in [[(1,0),(14,0)],[(9,0),(17,10)],[(23,1),(21,19)],[(13,0),(20,0)],[(18,1),(24,17)]]:
 ov={1:('先頭の要素から始めて隔番で取り出す','adapted')} if seq[-1][0]==24 else {}
 add('C06',seq,ov)
for seq in [[(2,1),(15,7),(19,0)],[(8,0),(11,13),(23,1)],[(17,10),(4,0),(20,1)],[(21,19),(22,0),(12,0)],[(24,17),(14,0),(3,0)]]:
 ov={0:('先頭の要素から始めて隔番で取り出して','adapted')} if seq[0][0]==24 else {}
 add('C07',seq,ov)
for seq in [[(14,0)]*2,[(11,13)]*3,[(12,1)]*2,[(15,7)]*3,[(24,17)]*2]:
 ov={i:('その時点の先頭の要素から始めて隔番で取り出して' if i<len(seq)-1 else 'その時点の先頭の要素から始めて隔番で取り出す','adapted') for i in range(len(seq))} if seq[0][0]==24 else {}
 add('C08',seq,ov,tags=['explicit_repetition'])
for seq in [[(1,0),(11,13)],[(18,1),(3,0)],[(22,0),(19,0)],[(19,0),(23,1)],[(16,3),(8,0)]]:add('C09',seq,tags=['order_sensitive'])
new=[
 (1,0,'値を2で割った余りが0になる要素だけを、出てきた順のまま選び出す'),
 (17,10,'各要素を数直線上での0からの距離に置き換える'),
 (21,19,'今の末尾を最初にして、要素を末尾側から一つずつたどった並びにする'),
 (22,0,'左端から数えてk番目までにある要素を、今の順番で取り出す。要素がk個に満たなければ全部を取り出す'),
 (12,0,'どの要素についても、その値から同じ整数kを差し引いた値に置き換える')]
for op,i,phrase in new:
 instruction='整数リストxsを処理するsolve(xs, k)を作ってください。'+phrase+'処理を行い、結果のリストを返してください。'
 if op==22:instruction='solve(xs, k)をお願いします。整数リストxsについて、'+phrase+'。結果をリストで返してください。'
 add('C10',[(op,i)],{0:(phrase,'new')},instruction,['new_operation_wording_candidate'])
assert len(specs)==50
config=GeneratorConfig(element_names=('x',),result_names=('result','next_result'))
generator=StructuralVariantGenerator(config,seed=20261005)
counts=collections.Counter();rows=[]
for cat,seq,overrides,instruction,tags in specs:
 counts[cat]+=1;qid=f'dev-{cat}-{counts[cat]:02d}'
 operations=[item(op,i)['operation_ast'] for op,i in seq]
 semantic={'sequence':operations}
 sources=[];phrases=[]
 for n,(op,i) in enumerate(seq):
  r=item(op,i);form='final' if n==len(seq)-1 else 'connective'
  field='expression_ja' if form=='final' else 'connective_expression_ja'
  phrase,status=overrides.get(n,(r[field],'verbatim'));phrases.append(phrase)
  sources.append({'operation_index':n,'operation_id':r['operation_id'],'operation_ast':r['operation_ast'],'reference_expression_ids':[r['expression_id']],'used_expression_ja':phrase,'form':form,'usage':status,'dictionary_split':'train','used_expression_id':r['expression_id'] if status=='verbatim' else None,'reference_expression_ja':r[field],'must_preserve_ja':r['must_preserve_ja'],'expression_approval':'approved_dictionary_text' if status=='verbatim' else 'candidate'})
 usesk=any(cnl[op]['requiresK']=='true' for op,i in seq)
 prefix='整数リストxsと整数kを受け取り、' if usesk else '整数リストxsから'
 canonical=prefix+'、'.join(cnl[op]['final' if n==len(seq)-1 else 'connective'] for n,(op,i) in enumerate(seq))+'solve関数を書いてください。'
 instruction=instruction or prefix+'、'.join(phrases)+'solve関数を書いてください。'
 style=generator.enumerate(semantic,limit=1)[0]
 code=generate_python_code(semantic,style,config).reference_code
 scope={};exec(code,scope)
 test_inputs=[([],1),([0],1),([-100,-3,-2,-1,0,1,2,3,100],3),([7,2,9,-4,2,0,1],2),([1,2,3,4,5,6,7,8,9,10],4),([0,0,-1,-1,2,2],10)]
 for xs,k in test_inputs:assert scope['solve'](xs.copy(),k)==interpret(semantic,xs,k),qid
 notes=['関数契約: solve(xs, k)。xsは長さ0〜20、各値-100〜100の整数。kは1〜10。','操作は記載順に前段の結果へ適用する。抽出と切り出しでは残る要素の相対順序を保持する。']
 if cat=='C08':notes.append('同じ操作をASTの回数だけ適用する。短縮・回数の読み落としを検査する。')
 if cat=='C10':notes.append('新規提案の日本語。未学習性・意味の人手レビュー前であり、承認済みや未学習と断定しない。')
 row={'question_id':qid,'split':'dev','category_id':cat,'instruction_ja':instruction,'canonical_cnl':canonical,'semantic_ast':semantic,'operation_count':len(seq),'difficulty':'easy' if cat in ['C01','C02','C03','C04','C05'] else 'hard' if cat in ['C07','C09','C10'] else 'medium','tags':tags+['dictionary_train_reference'],'reference_code':code,'test_case_set_id':f'{qid}-hidden-v1','expression_sources':sources,'dictionary_snapshot':{p:snapshot[p] for p in paths if p.endswith('.csv') or 'provenance.jsonl' in p or p.endswith('build_approved_expression_dictionary.json') or p.endswith('train_reference.jsonl')},'overlap_checks':{'status':'pending_post_generation'},'review':{'status':'candidate','author_semantic_check':'passed','independent_human_review':'pending','reference_code_check':{'status':'passed','cases':len(test_inputs),'method':'generated Python versus reference_interpreter.interpret'}},'scoring_notes':notes,'provenance':{'author_role':'question_author_subagent','author_model':'gpt-6-astra','reasoning_effort':'high','model_routing_evidence':'Parent confirmed actual spawn_agent arguments: model gpt-6-astra; high; fork_turns none','authored_at':now,'request_path':'data/benchmarks/browser_100/authoring/request_ja.txt','reference_snapshot_path':'data/benchmarks/browser_100/authoring/source_snapshot.json','method':'Actual author-selected wording and operation combinations, materialized with build_dev50.py. No scores or model inference used to select questions.','revision_history':[]}}
 if cat=='C09':
  reverse={'sequence':operations[::-1]}
  for xs,k in test_inputs:
   expected=interpret(semantic,xs,k);wrong=interpret(reverse,xs,k)
   if expected!=wrong:
    row['order_sensitivity_witness']={'xs':xs,'k':k,'expected':expected,'reversed_order_expected':wrong};break
  else:raise ValueError('No order witness '+qid)
 rows.append(row)
assert all(n==5 for n in counts.values())
assert len({r['instruction_ja'] for r in rows})==50
(BASE/'dev50.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
dump(A/'generation_summary.json',{'created_at':now,'question_count':50,'categories':dict(counts),'operations_covered':sorted({s['operation_id'] for r in rows for s in r['expression_sources']}),'usage':dict(collections.Counter(s['usage'] for r in rows for s in r['expression_sources'])),'semantic_ast_unique':len({json.dumps(r['semantic_ast'],sort_keys=True) for r in rows}),'reference_code_verified':50,'status':'candidate','dev50_initial_sha256':hashfile(BASE/'dev50.jsonl')})
print('Created 50 questions; reference codes verified. Held-out and training text inspection can begin now.')
