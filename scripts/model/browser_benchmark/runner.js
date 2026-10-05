import { BokuNanoTokenizer, formatBokuPrompt } from '/web/tokenizer.js?v=3';
import { selectToken } from '/web/sampling.js';
const $=id=>document.getElementById(id);
function status(text){$('status').textContent=text;}
async function save(record){const r=await fetch('/api/record',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(record)});if(!r.ok)throw Error(await r.text());}
function request(worker,type,payload={}){return new Promise((resolve,reject)=>{const handler=({data})=>{if(data.type==='progress'){status(data.message);return;}worker.removeEventListener('message',handler);data.type==='error'?reject(Error(data.message)):resolve(data);};worker.addEventListener('message',handler);worker.postMessage({type,...payload});});}
async function run(){
 $('run').disabled=true;
 const questions=await(await fetch('/api/questions')).json();
 const config=await(await fetch('/api/config')).json();
 const manifest=await(await fetch('/web/model-manifest.json')).json();
 const qmanifest=await(await fetch('/web/qwen-manifest.json')).json();
 const adapter=await navigator.gpu.requestAdapter();if(!adapter)throw Error('WebGPU unavailable');
 await save({kind:'environment',run_id:config.run_id,user_agent:navigator.userAgent,gpu:adapter.info?{vendor:adapter.info.vendor,architecture:adapter.info.architecture,device:adapter.info.device,description:adapter.info.description}:null,started_at:new Date().toISOString(),manifest,qwen_manifest:qmanifest});
 const previous=await(await fetch('/api/state')).json();
 const done=new Map(previous.filter(r=>r.kind==='inference').map(r=>[`${r.model}/${r.condition}/${r.question_id}`,r]));
 let count=done.size;
 const models=config.models??['boku','qwen'];
 const qconditions=config.conditions.filter(c=>c!=='C');
 if(config.conditions.includes('C'))qconditions.push('C-normalize');
 const total=questions.length*((models.includes('qwen')?qconditions.length:0)+(models.includes('boku')?config.conditions.length:0));
 $('progress').max=total;
 $('progress').value=count;
 const completed=record=>{count++;$('progress').value=count;$('log').textContent=`保存済み ${count}/${total}\n${record.model} ${record.condition} ${record.question_id}\n${(record.raw_output||record.cnl||record.error||'').slice(0,1200)}`;};
 const translations=new Map(previous.filter(r=>r.kind==='inference'&&r.condition==='C-normalize').map(r=>[r.question_id,r]));
 if(models.includes('qwen')){
 const worker=new Worker(new URL('./worker.js',import.meta.url),{type:'module'});
 status('Qwenを準備しています');
 await request(worker,'load',{manifest:qmanifest});
 for(const condition of qconditions){
  for(const q of questions){
   if(done.has(`qwen/${condition}/${q.question_id}`))continue;
   status(`Qwen ${condition} ${q.question_id} (${count+1}/${total})`);
   const instruction=condition==='B'?q.canonical_cnl:q.instruction_ja;
   const result=(await request(worker,condition==='C-normalize'?'translate':'direct',{instruction})).record;
   const record={kind:'inference',run_id:config.run_id,question_id:q.question_id,category_id:q.category_id,model:'qwen',condition,instruction,...result};
   await save(record);completed(record);
   if(condition==='C-normalize')translations.set(q.question_id,result);
  }
 }
 await request(worker,'dispose');worker.terminate();
 }
 if(models.includes('boku')){
 const model=manifest.models.find(m=>m.id===config.boku_model);
 ort.env.wasm.wasmPaths=new URL('/web/vendor/',location.href).href;ort.env.wasm.numThreads=1;
 status('Boku1-nanoを準備しています');
 const session=await ort.InferenceSession.create(`/web/${model.path}`,{executionProviders:['webgpu']});
 const tokenizer=await BokuNanoTokenizer.load(`/web/${manifest.tokenizers[model.tokenizer_id].path}`);
 for(const condition of config.conditions){
  for(const q of questions){
   if(done.has(`boku/${condition}/${q.question_id}`))continue;
   const translation=translations.get(q.question_id);
   const instruction=condition==='A'?q.instruction_ja:condition==='B'?q.canonical_cnl:translation.cnl;
   const base={kind:'inference',run_id:config.run_id,question_id:q.question_id,category_id:q.category_id,model:'boku',model_id:model.id,condition,instruction,backend:'webgpu',temperature:0};
   status(`Boku ${condition} ${q.question_id} (${count+1}/${total})`);
   if(condition==='C'&&!translation.supported){const r={...base,error:'normalization_failed',raw_output:'',termination:'normalization_failed'};await save(r);completed(r);continue;}
   const start=performance.now();let record;
   try{
    const prompt_ids=tokenizer.encodePrompt(instruction),ids=[...prompt_ids],output_ids=[];
    if(prompt_ids.includes(manifest.special_token_ids.unk))throw Error('unknown_token');
    if(ids.length>=model.context_length)throw Error('input_context_limit');
    let termination='max_context';
    for(let i=ids.length;i<model.context_length;i++){
     const input=new ort.Tensor('int64',BigInt64Array.from(ids,BigInt),[1,ids.length]);let outputs;
     try{outputs=await session.run({input_ids:input});const token=selectToken(outputs.logits.data,0);if(token===manifest.special_token_ids.eos){termination='eos';break;}ids.push(token);output_ids.push(token);}finally{input.dispose();for(const t of Object.values(outputs||{}))t.dispose();}
     if(output_ids.length%4===0)await new Promise(requestAnimationFrame);
    }
    record={...base,prompt:formatBokuPrompt(instruction),prompt_ids,output_ids,raw_output:tokenizer.decode(output_ids),termination,elapsed_seconds:(performance.now()-start)/1000};
   }catch(e){record={...base,prompt:formatBokuPrompt(instruction),raw_output:'',error:String(e),termination:'error',elapsed_seconds:(performance.now()-start)/1000};}
   await save(record);completed(record);
  }
 }
 await session.release();
 }
 await save({kind:'complete',run_id:config.run_id,completed_at:new Date().toISOString(),records:count});status(`評価完了：${count}件を保存しました`);
}
$('run').onclick=()=>run().catch(async e=>{status(`実行停止：${e.message}`);console.error(e);await save({kind:'infrastructure_error',error:e.stack||String(e)});});
