import { captureSemanticAst } from '/web/semantic-ast.js?v=11';
import { translateWithRetry } from '/web/qwen-translation.js?v=18';
let generator;
const send = (type, data={}) => self.postMessage({type,...data});
const SYSTEM = '整数リストの処理をPythonで実装してください。出力はsolve(xs: list[int], k: int) -> list[int]関数1つのコードだけにしてください。xsは長さ0〜20、各要素は-100〜100の整数、kは1〜10の整数です。指定された操作を順番どおりに適用し、整数リストを返してください。xs自体は変更しないでください。import、外部入出力、再帰は不要です。組み込みのabs、list、reversed、sorted、range、len、enumerate、min、max、sum、int、リスト内包表記、スライス、for、if、リストのappend/extend/sort/reverse/copyを使用できます。説明や実行例は出力しないでください。';
function extract(result) {
 const generated=result?.[0]?.generated_text;
 if(typeof generated==='string') return generated;
 if(Array.isArray(generated)) return [...generated].reverse().find(x=>x.role==='assistant')?.content ?? '';
 throw Error('Unexpected generation result');
}
async function generate(messages, maxTokens, penalty) {
 const prompt=generator.tokenizer.apply_chat_template(messages,{tokenize:false,add_generation_prompt:true,enable_thinking:false});
 const options={max_new_tokens:maxTokens,do_sample:false,repetition_penalty:penalty,return_full_text:false};
 const start=performance.now();
 const raw_output=extract(await generator(prompt,options));
 const output_tokens_estimate=generator.tokenizer.encode(raw_output,{add_special_tokens:false}).length;
 return {messages:JSON.parse(JSON.stringify(messages)),prompt,options,raw_output,output_tokens_estimate,elapsed_seconds:(performance.now()-start)/1000,termination:output_tokens_estimate>=maxTokens?'possible_token_limit':'pipeline_completed'};
}
self.onmessage=async({data})=>{
 try {
  if(data.type==='load') {
   const {env,pipeline}=await import(data.manifest.transformers_js_url);
   env.allowLocalModels=false;env.allowRemoteModels=true;env.useBrowserCache=true;
   generator=await pipeline('text-generation',data.manifest.model_id,{revision:data.manifest.revision,dtype:data.manifest.dtype,device:'webgpu',progress_callback:p=>{if(p.status==='progress')send('progress',{message:`Qwen読込 ${Math.round(p.progress)}%`});}});
   send('loaded');
  } else if(data.type==='direct') {
   send('result',{record:await generate([{role:'system',content:SYSTEM},{role:'user',content:data.instruction}],512,1)});
  } else if(data.type==='translate') {
   const attempts=[];
   const translated=await translateWithRetry({instruction:data.instruction,contextCnl:'',contextK:null,selection:null,generate:async(messages,attempt)=>{const r=await generate(messages,192,1.05);attempts.push({attempt,...r});return r.raw_output;},onAttempt:r=>Object.assign(attempts[attempts.length-1],r)});
   send('result',{record:{...translated,translated_semantic_ast:translated.supported?captureSemanticAst({valid:true,operations:translated.operations}):null,attempt_records:attempts}});
  } else if(data.type==='dispose') {await generator?.dispose();generator=null;send('disposed');self.close();}
 }catch(e){send('error',{message:e.stack||String(e)});}
};
