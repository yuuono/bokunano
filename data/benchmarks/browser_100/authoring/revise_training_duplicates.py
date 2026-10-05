"""Revise only known full-text duplicates following the saved parent instruction."""
import datetime,hashlib,json,pathlib
BASE=pathlib.Path(__file__).resolve().parents[1];A=BASE/'authoring'
p=BASE/'dev50.jsonl';rows=list(map(json.loads,p.open()));changes=[]
for row in rows:
 if row['overlap_checks']['boku_training']['full_text_exact_record_count']==0:continue
 before=row['instruction_ja']
 phrases=[s['used_expression_ja'] for s in row['expression_sources']]
 usesk=row['canonical_cnl'].startswith('整数リストxsと整数k')
 intro='整数リストxsと整数kが与えられます。' if usesk else '整数リストxsが与えられます。'
 after=intro+'、'.join(phrases)+'処理をするsolve(xs, k)を作成し、結果をリストで返してください。'
 row['instruction_ja']=after
 change={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'change':'Parent requested removal of exact training full-text duplicates before inference results; only outer sentence template changed. Operation wording, category, CNL, AST and reference code unchanged.','before_instruction_ja':before,'after_instruction_ja':after,'reason':'full_text_training_overlap','score_informed':False}
 row['provenance']['revision_history'].append(change)
 row['overlap_checks']['status']='pending_post_revision_recheck'
 row['review']['parent_ai_semantic_review']='passed_before_outer_template_revision; user approval remains pending'
 changes.append({'question_id':row['question_id'],**change})
assert len(changes)==12,len(changes)
p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
(A/'full_text_revisions.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
print('Revised 12 outer sentence templates, preserved all operation wording and semantics.')
