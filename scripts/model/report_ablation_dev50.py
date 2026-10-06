"""Validate five browser ablation runs and append the condition-A comparison."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from report_qwen_17b_mac_benchmark import ALL_LABELS, ALL_ORDER, data
from report_browser_100_benchmark import ROOT, OUT, RUN, CATEGORIES, jsonl

MODELS = {
    'existing': ('15M再学習・8 layers / 6 heads', 'existing'),
    'heads4': ('約9.5M・8 layers / 4 heads', 'heads_4_dim64'),
    'layers2': ('約5M・2 layers / 6 heads', 'layers_2'),
    'layers4': ('約8.7M・4 layers / 6 heads', 'layers_4'),
    'layers6': ('約12.2M・6 layers / 6 heads', 'layers_6'),
}
FILENAME = 'dev50_20261006_architecture_ablation.md'
MARKER = '<!-- architecture-ablation-dev50-20261006 -->'
END = '<!-- /architecture-ablation-dev50-20261006 -->'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    qs, old_scores, *_ = data()
    prior = {r['question_id']: r for r in jsonl(RUN/'raw_inference.jsonl')
             if r['kind']=='inference' and r['model']=='boku' and r['condition']=='A'}
    old_hashes = json.loads((RUN/'source_hashes.json').read_text())
    measured = {}
    lines = ['# 条件A・dev50：構造ablationの追加5モデル', '', '実施日: 2026年10月6日。固定50問・各1候補。条件B/Cと正式84,550件評価は実施していない。', '']
    metadata = {}
    for key, (label, strategy) in MODELS.items():
        folder = ROOT/f'data/benchmarks/browser_100/runs/dev50-20261006-ablation-{key}'
        config = json.loads((folder/'config.json').read_text())
        raw = jsonl(folder/'raw_inference.jsonl')
        scored = jsonl(folder/'scored.jsonl')
        assert len(scored)==50 and len({r['question_id'] for r in scored})==50
        inf = [r for r in raw if r['kind']=='inference']
        assert len(inf)==50 and raw[-1]['kind']=='complete' and raw[-1]['records']==50
        assert not any(r['kind']=='infrastructure_error' for r in raw)
        assert config['conditions']==['A'] and config['models']==['boku']
        assert config['temperature']==0 and not config['history']
        assert config['questions_sha256']==sha(ROOT/'data/benchmarks/browser_100/dev50.jsonl')
        assert (folder/'test_cases.json').read_bytes()==(RUN/'test_cases.json').read_bytes()
        hashes=json.loads((folder/'source_hashes.json').read_text())
        for source in ['scripts/model/score_browser_100_benchmark.py','web/tokenizer.js','web/sampling.js']:
            assert hashes[source]==old_hashes[source],source
        previous_runner=json.loads((RUN.with_name('dev50-20261005-5m-1epoch')/'source_hashes.json').read_text())
        assert hashes['scripts/model/browser_benchmark/runner.js']==previous_runner['scripts/model/browser_benchmark/runner.js']
        for r in inf:
            assert not r.get('error') and r['backend']=='webgpu' and r['condition']=='A'
            assert r['model_id']==f'ablation-{key}'
            assert r['prompt']==prior[r['question_id']]['prompt']
            assert r['prompt_ids']==prior[r['question_id']]['prompt_ids']
        model_dir=ROOT/f'data/models/architecture_ablation_run_20261006/15m_{strategy}_seed20260925/model'
        training=json.loads((model_dir/'training_manifest.json').read_text())
        assert training['status']=='completed' and training['epochs']==1 and training['seed']==20260925
        env=next(r for r in raw if r['kind']=='environment')
        entry=next(m for m in env['manifest']['models'] if m['id']==f'ablation-{key}')
        assert entry['source_sha256']==training['model_sha256']==sha(model_dir/'model.safetensors')
        assert entry['sha256']==sha(ROOT/'web'/entry['path'])
        tokenizer=env['manifest']['tokenizers'][entry['tokenizer_id']]
        assert tokenizer['sha256']==training['tokenizer_sha256']==sha(ROOT/'web'/tokenizer['path'])
        assert entry['parameter_count']==training['parameter_count']
        val=jsonl(model_dir/'training_metrics.jsonl')[-1]['validation_loss']
        measured[key]={r['question_id']:r for r in scored}
        metadata[key]={'label':label,'training':training,'entry':entry,'validation_loss':val,
                       'terminations':dict(Counter(r['termination'] for r in inf)),
                       'elapsed_seconds':sum(r['elapsed_seconds'] for r in inf),
                       'environment':env,'run':str(folder.relative_to(ROOT))}
    comparison=['| モデル | 合格 / 50問 | 正答率 | 実行方式 |','| --- | ---: | ---: | --- |']
    for key in ALL_ORDER:
        passed=sum(old_scores[key,q['question_id']]['passed'] for q in qs)
        backend='Mac・Python/MPS' if key.startswith('qwen3-') else 'ブラウザ・WebGPU'
        comparison.append(f'| {ALL_LABELS[key]}（既存結果） | {passed}/50 | {passed*2}% | {backend} |')
    for key,(label,_) in MODELS.items():
        passed=sum(r['passed'] for r in measured[key].values())
        comparison.append(f'| {label}（今回追加） | {passed}/50 | {passed*2}% | ブラウザ・WebGPU |')
    lines += ['## 既存モデルを含む比較', '', *comparison, '',
              '既存6モデルの得点は再掲。今回の5モデルはすべて1 epoch・seed 20260925・既存BPE。旧15Mと今回の再学習15Mは区別する。Qwenは重み形式・実行基盤も異なるため、モデル規模だけの効果とは解釈しない。', '',
              '## 追加モデルの構成とvalidation loss', '',
              '| モデル | 幅 | layers | heads | head_dim | FFN | parameters | validation loss |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for key,(label,_) in MODELS.items():
        m=metadata[key];t=m['training'];c=t['model_config']
        lines.append(f"| {label} | {c['d_model']} | {c['n_layers']} | {c['n_heads']} | {c['d_model']//c['n_heads']} | {c['d_ff']} | {t['parameter_count']:,} | {m['validation_loss']:.6f} |")
    lines += ['', '## 分類別の合格数（各5問）', '', '| 分類 | 15M再学習 | 約9.5M | 2 layers | 4 layers | 6 layers |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for i,category in enumerate(CATEGORIES,1):
        nums=[sum(r['passed'] for r in measured[k].values() if r['category_id']==f'C{i:02}') for k in MODELS]
        lines.append(f'| C{i:02} {category} | '+' | '.join(map(str,nums))+' |')
    lines += ['', '## 失敗内訳と実行確認', '']
    for key,(label,_) in MODELS.items():
        reasons=Counter(r['reason'] for r in measured[key].values() if not r['passed'])
        lines.append(f"- {label}: {dict(reasons)}。終了理由: {metadata[key]['terminations']}。")
    lines += ['', 'ブラウザ推論は各モデルを順番に実行し、終了後に解放した。全250問でプロンプト全文・入力token列が既存Boku条件Aと一致。問題hash・採点器・tokenizerと179テスト入力が既存評価と一致することを検査した。ブラウザ生成処理は既存5M追加評価時のrunnerと同一hashで、今回の変更は別モデルmanifestを読み込むサーバー側だけ。モデル出力の修正・再生成・問題の選び直しは行っていない。', '',
              'greedy・T=0・会話履歴なし・系列長上限256（入力＋出力）。ONNX変換後にPyTorchとのlogitsと2つの確認プロンプトの生成token一致を検証した。得点に基づく構成調整は行っていない。単一seed・開発用50問であり、未知問題全般での順位や有意差は主張しない。', '',
              '## 再現情報', '', '各runのraw_inference.jsonlに実プロンプト・生成コード・環境、scored.jsonlに採点・失敗反例を保存。重みとONNXのhashも照合済み。', '']
    for key,(label,_) in MODELS.items():
        m=metadata[key]
        lines += [f"- {label}: [run](../../../{m['run']}/summary.json)、[全生成](../../../{m['run']}/raw_inference.jsonl)、[採点](../../../{m['run']}/scored.jsonl)。重みSHA-256: `{m['training']['model_sha256']}`。"]
    lines += ['', '## 問題別の合否', '', '| 問題 | 日本語指示 | 15M再学習 | 約9.5M | 2 layers | 4 layers | 6 layers |','| --- | --- | --- | --- | --- | --- | --- |']
    for q in qs:
        cells=['○' if measured[k][q['question_id']]['passed'] else '×' for k in MODELS]
        lines.append('| '+q['question_id']+' | '+q['instruction_ja'].replace('|','\\|')+' | '+' | '.join(cells)+' |')
    (OUT/FILENAME).write_text('\n'.join(lines)+'\n')
    addition='\n'.join([MARKER,'','## 追記：2026年10月6日 構造ablation追加5モデル','',*comparison,'',
        '追加5モデルは同じ条件A・dev50をブラウザWebGPUで評価。全モデル1 epoch・1 seed。既存6モデルの結果は再掲。', '',f'[構成・分類別得点・問題別合否・再現情報]({FILENAME})','',END])
    target=OUT/'dev50_20261005_results.md'
    text=target.read_text()
    if MARKER in text:
        start=text.index(MARKER);end=text.index(END,start)+len(END)
        text=text[:start]+addition+text[end:]
    else:
        text=text.rstrip()+'\n\n'+addition+'\n'
    target.write_text(text)
    print('\n'.join(comparison))


if __name__=='__main__':
    main()
