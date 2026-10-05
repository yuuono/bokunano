"""Serve the browser benchmark and append its actual inference records locally."""
from __future__ import annotations
import argparse
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--questions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--boku-model', default='15m-1epoch')
    parser.add_argument('--models', nargs='+', choices=['boku', 'qwen'], default=['boku', 'qwen'])
    parser.add_argument('--conditions', nargs='+', choices=['A', 'B', 'C'], default=['A', 'B'])
    args = parser.parse_args()
    manifest = json.loads((ROOT/'web/model-manifest.json').read_text())
    if args.boku_model not in {m['id'] for m in manifest['models']}:
        parser.error('Unknown Boku model')
    if 'C' in args.conditions and set(args.models) != {'boku', 'qwen'}:
        parser.error('Condition C requires both models')
    questions = [json.loads(line) for line in args.questions.read_text().splitlines() if line.strip()]
    args.output.mkdir(parents=True, exist_ok=True)
    config = {'run_id': args.run_id, 'boku_model': args.boku_model, 'models': args.models, 'question_count': len(questions), 'questions_sha256': hashlib.sha256(args.questions.read_bytes()).hexdigest(), 'conditions': args.conditions, 'qwen_max_new_tokens': 512, 'qwen_normalizer_max_new_tokens': 192, 'qwen_direct_repetition_penalty': 1, 'temperature': 0, 'normalizer_max_attempts': 2, 'history': False}
    config_path=args.output/'config.json'
    if config_path.exists() and json.loads(config_path.read_text())!=config:
        raise ValueError('Existing run has different configuration')
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n')
    sources={}
    for p in [Path(__file__).resolve(), args.questions, *sorted((ROOT/'scripts/model/browser_benchmark').glob('*')), ROOT/'web/model-manifest.json', ROOT/'web/qwen-manifest.json', ROOT/'web/tokenizer.js', ROOT/'web/qwen-translation.js', ROOT/'web/cnl.js', ROOT/'web/sampling.js', ROOT/'web/chat-utils.js', ROOT/'web/semantic-ast.js', ROOT/'scripts/model/score_browser_100_benchmark.py']:
        sources[str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    (args.output/'source_hashes.json').write_text(json.dumps(sources, indent=2)+'\n')
    lock=threading.Lock()
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT),**kw)
        def json_response(self,data):
            body=json.dumps(data,ensure_ascii=False).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            path=urlparse(self.path).path
            if path=='/api/questions': return self.json_response([{k:q[k] for k in ['question_id','category_id','instruction_ja','canonical_cnl']} for q in questions])
            if path=='/api/config': return self.json_response(config)
            if path=='/api/state':
                p=args.output/'raw_inference.jsonl'
                return self.json_response([json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else [])
            if path.startswith('/web/') or path.startswith('/scripts/model/browser_benchmark/'): return super().do_GET()
            self.send_error(404)
        def do_POST(self):
            if self.path!='/api/record': return self.send_error(404)
            origin=self.headers.get('Origin','')
            if origin and origin!=f'http://127.0.0.1:{args.port}': return self.send_error(403)
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<2_000_000: return self.send_error(413)
            record=json.loads(self.rfile.read(size))
            record['run_id']=args.run_id
            with lock, (args.output/'raw_inference.jsonl').open('a') as f:
                f.write(json.dumps(record,ensure_ascii=False)+'\n');f.flush()
            self.json_response({'saved':True})
        def log_message(self,*a): pass
    print(f'http://127.0.0.1:{args.port}/scripts/model/browser_benchmark/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
if __name__=='__main__': main()
