"""Post-generation overlap checks; does not author or select questions by score."""
import collections,csv,datetime,difflib,hashlib,json,pathlib,unicodedata,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[4];BASE=ROOT/'data/benchmarks/browser_100';A=BASE/'authoring'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def hashfile(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def astkey(x):return json.dumps(x if 'sequence' in x else {'sequence':[x]},sort_keys=True)
def norm(x):return ''.join(unicodedata.normalize('NFKC',x).split())
rows=[json.loads(x) for x in (BASE/'dev50.jsonl').open()]
config=json.loads((ROOT/'config/build_approved_expression_dictionary.json').read_text())
csvrows=list(csv.DictReader((ROOT/config['expressions_csv']).open()))
prov={x['expression_id']:x for x in map(json.loads,(ROOT/config['provenance_jsonl']).open())}
assert len(csvrows)==545 and len(prov)==545
for r in csvrows:
 p=prov[r['expression_id']]
 assert r['expression_ja']==p['approved_expression_ja'] and r['connective_expression_ja']==p['approved_connective_expression_ja']
excluded=[r for r in csvrows if r['expression_id'] in config['test_only_expression_ids']]
external=list(map(json.loads,(ROOT/'data/instruction_dictionaries/release/paraphrase_test_external_expressions.jsonl').open()))
assert len(excluded)==23 and len(external)==9
for r in rows:
 matches=[]
 for p in excluded+external:
  for field in ['expression_ja','connective_expression_ja']:
   if norm(p[field]) in norm(r['instruction_ja']):matches.append({'expression_id':p['expression_id'],'form':field})
 r['overlap_checks']={'held_out_expressions':{'status':'passed' if not matches else 'overlap_found','dictionary_test_only_count':23,'external_count':9,'method':'NFKC/whitespace-normalized substring match against natural-language instruction; canonical CNL is a fixed specification and separately excluded from this wording check.','matches':matches},'development_full_text_duplicates':[],'production_full_text':'not_available_no_production_set_created','near_expression_semantic_overlap':'Not established by string matching; independent semantic review still required.'}
 assert not matches,(r['question_id'],matches)
manifestpath=ROOT/'data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/training_manifest.json'
manifest=json.loads(manifestpath.read_text());archive=ROOT/manifest['source_archive']
archivehash=hashfile(archive);assert archivehash==manifest['source_archive_sha256']
phrases={s['used_expression_ja'] for r in rows for s in r['expression_sources']};phrasecounts=collections.Counter();alltexts=collections.Counter();astcounts=collections.Counter();sameast=collections.defaultdict(set)
wantedast={astkey(r['semantic_ast']) for r in rows};seen_records=0;sourcecounts=collections.Counter()
with zipfile.ZipFile(archive) as z:
 with z.open('final_dataset_records.jsonl') as f:
  for line in f:
   t=json.loads(line);seen_records+=1;txt=t['instruction_ja'];alltexts[txt]+=1
   key=astkey(t['semantic_ast']);astcounts[key]+=1
   if key in wantedast:sameast[key].add(txt)
   sourcecounts[t['instruction_source']]+=1
# Operation wording presence is literal substring presence, independent of the AST of the containing instruction.
for phrase in phrases:
 phrasecounts[phrase]=sum(c for txt,c in alltexts.items() if phrase in txt)
for r in rows:
 txt=r['instruction_ja'];key=astkey(r['semantic_ast']);matches=sameast[key]
 nearest=max(matches,key=lambda t:difflib.SequenceMatcher(None,txt,t,autojunk=False).ratio()) if matches else None
 r['overlap_checks']['boku_training']={'status':'checked','model_manifest_path':str(manifestpath.relative_to(ROOT)),'archive_path':str(archive.relative_to(ROOT)),'archive_sha256':archivehash,'manifest_hash_matches':True,'record_count':seen_records,'actual_instruction_field':'instruction_ja (teacher replacements included; source_instruction_ja is not substituted)','full_text_exact_record_count':alltexts[txt],'semantic_ast_record_count':astcounts[key],'operation_wording':[{'operation_index':s['operation_index'],'used_expression_ja':s['used_expression_ja'],'substring_record_count':phrasecounts[s['used_expression_ja']],'status':'known_exact_wording' if phrasecounts[s['used_expression_ja']] else 'no_exact_wording_found'} for s in r['expression_sources']],'nearest_full_text_same_ast':{'text':nearest,'sequence_matcher_ratio':round(difflib.SequenceMatcher(None,txt,nearest,autojunk=False).ratio(),4)} if nearest else None,'limitations':'Exact/substring wording checks do not prove absence of semantic paraphrases or every morphological variant. Nearest text searched only among matching ASTs. Qwen pretraining was not examined.'}
 r['provenance']['author_model']='gpt-6-astra'
 r['provenance']['reasoning_effort']='high'
 r['provenance']['model_routing_evidence']='Parent confirmed actual spawn_agent(model="gpt-6-astra", reasoning_effort="high", fork_turns="none").'
 r['provenance']['revision_history'].append({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'change':'Post-generation overlap metadata and actual model routing recorded; question wording and AST unchanged.'})
(BASE/'dev50.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
summary={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'dictionary_consistency':{'csv_count':545,'provenance_count':545,'final_fields_match':True,'train_count':522},'held_out_natural_language_overlaps':0,'train_archive':{'path':str(archive.relative_to(ROOT)),'sha256':archivehash,'record_count':seen_records,'sources':dict(sourcecounts)},'full_text_known_question_count':sum(bool(alltexts[r['instruction_ja']]) for r in rows),'ast_known_question_count':sum(bool(astcounts[astkey(r['semantic_ast'])]) for r in rows),'operation_occurrences_with_known_wording':sum(bool(phrasecounts[s['used_expression_ja']]) for r in rows for s in r['expression_sources']),'operation_occurrences_total':sum(r['operation_count'] for r in rows),'C10_exact_full_text_matches':sum(bool(alltexts[r['instruction_ja']]) for r in rows if r['category_id']=='C10'),'C10_exact_operation_wording_matches':sum(bool(phrasecounts[s['used_expression_ja']]) for r in rows if r['category_id']=='C10' for s in r['expression_sources']),'dev50_sha256':hashfile(BASE/'dev50.jsonl'),'question_review_status':'candidate; independent meaning review pending','post_generation_only_references':[{'path':p,'sha256':hashfile(ROOT/p)} for p in ['docs/policies/japanese_paraphrase_test_policy.md','data/instruction_dictionaries/release/paraphrase_test_external_expressions.jsonl']]}
dump(A/'overlap_summary.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
