"""Verify the pinned Qwen3-1.7B split ONNX against its original weights."""
from pathlib import Path
import argparse
import hashlib,json,onnx

def sha_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--original', type=Path, required=True)
parser.add_argument('--graph', type=Path, required=True)
parser.add_argument('--weights', type=Path, required=True)
parser.add_argument('--original-tokenizer', type=Path, required=True)
parser.add_argument('--split-tokenizer', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args=parser.parse_args()
original=args.original;weights=args.weights
assert original.stat().st_size==1426069098
assert weights.stat().st_size==1425786880
assert sha_file(original)=='fb85b44defdf43ace50c7a4937127e889b9f8a0483eb87a6c4151a815c5da3b5'
assert sha_file(weights)=='70c82eb223466746db1e98c62cef90b18a49748f8568d17997450d36cace64ed'
a=onnx.load(original,load_external_data=False);b=onnx.load(args.graph,load_external_data=False)
assert len(a.graph.initializer)==len(b.graph.initializer)
count=0
with open(weights,'rb') as f:
 for x,y in zip(a.graph.initializer,b.graph.initializer):
  assert x.name==y.name and x.data_type==y.data_type and x.dims==y.dims
  if y.external_data:
   meta={d.key:d.value for d in y.external_data};assert len(x.raw_data)==int(meta['length'])
   h=hashlib.sha256();f.seek(int(meta['offset']));remaining=int(meta['length'])
   while remaining:
    block=f.read(min(8*1024*1024,remaining));assert block;h.update(block);remaining-=len(block)
   assert hashlib.sha256(x.raw_data).digest()==h.digest(),x.name
   y.ClearField('external_data');y.ClearField('data_location');x.ClearField('data_location');x.ClearField('raw_data');count+=1
  assert x==y,x.name
assert a==b,'Graph/model metadata differs beyond external weight storage'
result={'all_model_fields_equal_after_externalizing_weights':True,'initializer_count':len(a.graph.initializer),'external_tensors_compared':count,'graph_nodes':len(a.graph.node),'tokenizer_semantic_equality':json.loads(args.original_tokenizer.read_text())==json.loads(args.split_tokenizer.read_text()),'original_model_sha256':sha_file(original),'external_graph_sha256':sha_file(args.graph),'external_weights_sha256':sha_file(weights)}
args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
