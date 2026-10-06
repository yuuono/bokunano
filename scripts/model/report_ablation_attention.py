"""Summarize completed attention analyses and link the five model figure galleries."""
from pathlib import Path
import argparse
import hashlib
import json
import statistics
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/results/attention_ablation_20261006'
MODELS={
    'existing':('15M基準','existing'),
    'heads_4_dim64':('約9.5M・4 heads','heads4'),
    'layers_2':('約5M・2 layers','layers2'),
    'layers_4':('約8.7M・4 layers','layers4'),
    'layers_6':('約12.2M・6 layers','layers6'),
}
FIGURES={
    'attention_head_roles.svg':('head別の参照傾向','24操作の生成位置を集計。日本語指示・BOS・直近token・entropy等を比較する。記述的傾向であり、役割を断定する分類ではない。'),
    'attention_sink_contribution.svg':('BOS attentionとValue寄与','横軸はBOSへの生attention、縦軸はattentionで重み付けしたprojected Valueノルムの構成比。方向間の相殺を表現しないため、最終出力への厳密な寄与率ではない。'),
    'attention_causal_ablation.svg':('head・Valueの無効化','上段は各head無効化時の自己生成列に対するΔNLL。下段は選んだheadおよびBOS・日本語位置Valueを0化して再生成した24操作の合格率。'),
    'attention_rollout.svg':('attention rollout','固定操作の生成列でhead平均と残差を加えたrollout、生attention、projected Valueノルムを比較。生成列・表示query位置はモデルごとに異なり、近似的な情報経路として読む。'),
    'attention_by_layer_head.svg':('生成step×参照位置','共通の単一プロンプトに対する全層・全headのattention。横軸はtoken位置、縦軸は生成step。生成内容・長さはモデルごとに異なる。'),
    'attention_regions.svg':('領域別attention','単一プロンプトで日本語・制御token・生成済みコードへのattentionを集計。領域のtoken数にも依存する。'),
    'kv_cosine_similarity.svg':('K/Vコサイン類似度','単一プロンプトで得たK/Vのtoken間類似度。類似しているだけで同じ機能や因果的重要度を意味しない。'),
    'token_utilization.svg':('tokenの参照頻度','単一プロンプトで繰り返し参照された位置と参照が少ない位置を表示。参照が少ないことだけで不要とは判断しない。'),
}


def read(path):return json.loads(path.read_text())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=OUT)
    args=parser.parse_args()
    output=args.output_root.resolve()
    records={}
    for name,(label,run) in MODELS.items():
        folder=output/name
        manifest=read(folder/'manifest.json')
        assert manifest['status']=='completed'
        a=read(folder/'attention.json');b=read(folder/'interpretability.json')
        assert b['diagnostic_design']['prompt_count']==b['baseline']['total']==24
        assert b['diagnostic_design']['hidden_tests_per_prompt']==33
        cfg=b['model_config']
        assert len(b['head_ablation'])==len(b['head_roles'])==cfg['layers']*cfg['heads']
        assert cfg['head_dimension']==64
        assert a['attention']['fused_attention_output_validation']['maximum_absolute_error']<1e-4
        assert abs(a['attention']['row_sum_min']-1)<1e-5 and abs(a['attention']['row_sum_max']-1)<1e-5
        for filename in FIGURES:
            ET.parse(folder/'figures'/filename)
        training=read(ROOT/b['model_directory']/'training_manifest.json')
        assert manifest['model_sha256']==training['model_sha256']
        assert hashlib.sha256((ROOT/b['model_directory']/'model.safetensors').read_bytes()).hexdigest()==manifest['model_sha256']
        dev=read(ROOT/f'data/benchmarks/browser_100/runs/dev50-20261006-ablation-{run}/summary.json')['boku/A']['passed']
        conditions={r['name']:r for r in b['causal_generation_results']}
        assert all(c['total']==24 and len(c['results'])==24 for c in conditions.values())
        records[name]=(a,b,conditions,dev)
        top=b['most_causally_influential_heads'][0]
        lines=[f'# {label}：attention可視化・診断', '', '[5モデル比較へ戻る](../README.md)', '',
               f"構成: 幅{cfg['hidden_size']}、{cfg['layers']} layers、{cfg['heads']} heads、head_dim=64、FFN {cfg['ffn_size']}、{cfg['parameter_count']:,} parameters。", '',
               f"dev50: {dev}/50。24操作診断: {b['baseline']['passed']}/24。BOS Value=0: {conditions['zero_bos_values']['passed']}/24、日本語Value=0: {conditions['zero_instruction_values']['passed']}/24。", '',
               f"ΔNLL最大head: {top['id']}（{top['delta_nll']:+.6f}）。このheadを無効化して再生成した合格数は{conditions['ablate_'+top['id']]['passed']}/24。", '',
               '## 単一プロンプトの生成', '', a['instruction'], '', '```python',a['generated_code'].rstrip(),'```','',
               'この単一プロンプトのコードは可視化対象であり、ここでは機能正解を保証しない。機能評価は別の24操作診断・dev50を参照。', '',
               '## 図', '']
        for filename,(title,description) in FIGURES.items():
            lines += [f'### {title}', '', description, '', f'![{title}](figures/{filename})','']
        lines += ['## 24操作の結果', '', '| 操作ID | 指示 | 合否 | 診断 |','| --- | --- | --- | --- |']
        for sample in b['samples']:
            v=sample['verification'];error=str(v['error'] or '').replace('|','\\|').replace('\n',' ')
            lines.append(f"| {sample['operation_id']} | {sample['instruction']} | {'○' if v['tests_passed'] else '×'} | {error} |")
        lines += ['', '## 再現情報', '', '[全headの数値・生成コード・介入結果](interpretability.json)、[単一プロンプトのQ/K/V解析](attention.json)、[重み・tokenizer・ソースhashと実行コマンド](manifest.json)。']
        (folder/'README.md').write_text('\n'.join(lines)+'\n')
    lines=['# 構造ablation 5モデルのattention可視化・因果診断', '',
           '実施日: 2026年10月6日。全モデル1 epoch・学習seed 20260925・既存BPE・head_dim=64。追加5モデルの学習済み重みを同じ分析コードで解析した。', '',
           '## 結果一覧', '',
           '| モデル／図一覧 | parameters | 層×head | dev50 | 24操作診断 | BOS Value=0 | 日本語Value=0 |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name,(label,_) in MODELS.items():
        a,b,c,dev=records[name];cfg=b['model_config']
        lines.append(f"| [{label}]({name}/README.md) | {cfg['parameter_count']:,} | {cfg['layers']}×{cfg['heads']} | {dev}/50 | {b['baseline']['passed']}/24 | {c['zero_bos_values']['passed']}/24 | {c['zero_instruction_values']['passed']}/24 |")
    base_scores=[r[1]['baseline']['passed'] for r in records.values()]
    jp_scores=[r[2]['zero_instruction_values']['passed'] for r in records.values()]
    lines += ['', f'24操作の通常生成は{min(base_scores)}–{max(base_scores)}/24、日本語指示位置のValueを全層で無効化すると{min(jp_scores)}–{max(jp_scores)}/24だった。今回の診断では、全モデルで指示位置のValueが機能正解に強く関わっている。', '',
              'BOS Value無効化の影響は構成によって異なる。BOSへのattentionが小さい／大きいという観察だけでは、その機能上の必要性を判断できない。']
    lines += ['', 'dev50は自然な日本語の開発用50問、24操作は学習時準拠文型の単独操作診断で、別の評価集合である。両者の得点を混ぜない。既存Qwen等との比較は[条件Aレポート](../browser_100/dev50_20261006_architecture_ablation.md)を参照。', '',
              '## 指示参照とhead介入', '',
              '| モデル | 日本語attention平均 | BOS attention平均 | 日本語attention最大head | ΔNLL最大head | ΔNLL | 同head除去後 | Spearman |',
              '| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |']
    for name,(label,_) in MODELS.items():
        a,b,c,_=records[name];roles=b['head_roles'];top=b['most_causally_influential_heads'][0]
        instr=max(roles,key=lambda r:r['instruction_attention'])
        lines.append(f"| {label} | {statistics.mean(r['instruction_attention'] for r in roles):.2%} | {statistics.mean(r['bos_attention'] for r in roles):.2%} | {instr['id']} | {top['id']} | {top['delta_nll']:+.6f} | {c['ablate_'+top['id']]['passed']}/24 | {b['attention_causal_correlations']['instruction_attention']['spearman']:.3f} |")
    lines += ['', 'ΔNLLは各モデルが介入前に生成したtoken列を固定して教師強制したときの変化で、正解コードに対するNLLではない。EOSは対象外。モデルごとに生成列が異なるので、このNLLをモデル間の品質ランキングに用いない。Spearmanは同一モデル内の日本語attentionとhead除去ΔNLLの順位相関。最大headは同じ24操作で選択しているため、独立した汎化評価ではない。', '',
              '日本語attention最大headとΔNLL最大headは必ずしも一致しない。参照量だけで重要度を判断せず、介入後の生成・実行結果も確認する。日本語Valueを0にする操作では各層の当該attention計算でKを直接変更しないが、下流層の状態や以後の生成は介入により変化する。', '',
              '## Attention復元の数値検証', '',
              '| モデル | attention行和 min–max | attention×Vと実出力の最大絶対誤差 |',
              '| --- | --- | ---: |']
    for name,(label,_) in MODELS.items():
        a,b,c,_=records[name];att=a['attention']
        lines.append(f"| {label} | {att['row_sum_min']:.7f}–{att['row_sum_max']:.7f} | {att['fused_attention_output_validation']['maximum_absolute_error']:.2e} |")
    lines += ['', '## 方法・範囲', '',
              '- 既存の `analyze_boku_nano_attention.py` と `analyze_boku_nano_attention_interpretability.py` を使用。解析はCPU・float32、各プロセス1 thread。学習は追加していない。',
              '- 24操作は `single-operation-training-aligned-v1`。kなし／ありで外側文型を使い分け、固定33入力で機能判定。greedy、最大64 token。診断seedは20260930。訓練から独立した未見24問とは主張しない。',
              '- 全headを1つずつout_proj直前で0化してNLL差・KL・argmax変化を測定。ΔNLL上位3 headと絶対変化の小さい3 headは、各々24操作を再生成して機能判定。',
              '- BOSおよび日本語指示位置のValueを全層で0化し、24操作を再生成。BOSのattentionが大きいだけで無意味なsinkとは扱わない。',
              '- 各モデル8図: head別参照傾向、BOS/Valueノルム、因果的ablation、rollout、step×位置、領域別attention、K/V類似度、token参照頻度。全40図を各モデルのMarkdownに直接表示。',
              '- 単一プロンプトは全モデル同じ「xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。」。モデルごとの生成列が異なるため、図の同じ位置が同じtokenとは限らない。',
              '- head数減では幅も連動し、layer数減では容量・計算量も変わる。単一seedの結果であり、サイズ以外の影響を排除した因果比較や統計的有意差は主張しない。', '',
              '## 再実行', '', '```bash', '.venv/bin/python scripts/model/run_ablation_attention.py --output-root docs/results/attention_ablation_new_run', '.venv/bin/python scripts/model/report_ablation_attention.py --output-root docs/results/attention_ablation_new_run', '```', '',
              '解析runnerは既存のモデル別出力先を上書きしない。reportスクリプトにも同じ出力先を指定する。各モデルのmanifest.jsonに重み・tokenizer・実行ソースのhash、実行コマンド、完了状態を保存した。']
    (output/'README.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines[:20]))


if __name__=='__main__':main()
