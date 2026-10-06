"""Report Qwen3-1.7B condition A and append the six-model comparison."""
from collections import Counter
import hashlib
import json
import statistics
from report_browser_100_benchmark import ROOT, OUT, RUN, CATEGORIES, block, jsonl
from report_browser_additional_models import ORDER, LABELS
from report_qwen_awq_mac_benchmark import data as awq_data

NEW_RUN = RUN.with_name('dev50-20261006-qwen3-1.7b-mps')
FILENAME = 'dev50_20261006_qwen3_1_7b.md'
MODEL = 'qwen3-1.7b'
MARKER = '<!-- qwen3-1.7b-mps-addition -->'
ALL_ORDER = [*ORDER, MODEL, 'qwen3-4b-awq']
ALL_LABELS = {**LABELS, MODEL: 'Qwen3-1.7B（非量子化・FP16）', 'qwen3-4b-awq': 'Qwen3-4B-AWQ（FP16展開）'}
FAILURE_NOTES = {
    "dev-C01-02": "奇数だけを抽出する代わりに、奇数の値をkへ置き換え、偶数も残す。",
    "dev-C01-04": "負の値だけを抽出する代わりに、負の値をkへ置き換え、0や正数も残す。",
    "dev-C02-01": "kを超える条件をx <= kへ逆転している。",
    "dev-C02-04": "k以下の条件をx >= kへ逆転している。",
    "dev-C03-04": "符号反転を1回ではなくk回実行する。kが偶数なら元の符号へ戻ってしまう。",
    "dev-C03-05": "二乗をk乗へ置き換えている。kは指数として指定されていない。",
    "dev-C04-02": "降順ソートを行わず、添字がkの要素を除く処理になっている。",
    "dev-C04-04": "昇順ソートを行わず、k個右の値で前半を書き換える。末尾の値が重複する。",
    "dev-C04-05": "反転を1回ではなくk回実行する。kが偶数なら元の順序へ戻る。",
    "dev-C05-03": "1個おき（添字間隔2）の指示を、添字間隔kの取り出しへ変えている。",
    "dev-C05-04": "先頭k個を取り出す代わりに、先頭k個を除いた残りを返す。",
    "dev-C05-05": "末尾k個を取り出す代わりに、末尾k個を除いた残りを返す。",
    "dev-C06-02": "負の値の絶対値は取るが、負の値だけの抽出を行わず0や正数も返す。",
    "dev-C06-03": "末尾k個を反転して返す代わりに、末尾k個を先頭へ移動した全体を返す。",
    "dev-C06-05": "二乗を省略し、取り出す間隔も2ではなくk+1としている。",
    "dev-C07-01": "奇数抽出・3倍・ソートという処理の構成は指示に沿うが、tripledをtripedと誤記して未定義変数になった。静的検査で停止しており、意味理解の誤りと一括りにしない。",
    "dev-C07-03": "絶対値で条件を判定するが、リストへ追加するのは絶対値化前のxなので負数が残る。",
    "dev-C07-05": "偶数添字の値だけ2倍するが、間の要素も残し、最後のkを超える条件を適用しない。",
    "dev-C08-01": "2倍を2回（4倍）の指示に対して、2倍を1回だけ行う。",
    "dev-C08-02": "kを加算する操作を3回ではなく1回だけ行う。",
    "dev-C08-03": "kを減算する操作を2回ではなく1回だけ行う。",
    "dev-C08-04": "3倍を3回の指示を、3倍をk回へ置き換える。",
    "dev-C08-05": "許可外のwhileを使用して静的検査で拒否。コード読解でも間隔がkで、1個おきの操作を2回行う内容ではない。実行による反例は測定していない。",
    "dev-C09-02": "二乗値で条件判定するが、返すのは二乗前のxとなっている。",
    "dev-C09-05": "負数を正数へ変換する一方で、除くべき元の0や正数も残す。結果として全要素の絶対値に相当する。",
    "dev-C10-02": "0からの距離abs(x)ではなく、kからの距離abs(x-k)を計算する。",
    "dev-C10-04": "先頭k個ではなく、それ以降の要素を返す。"
}


def data():
    qs, baseline, _, _, awq_scores, _ = awq_data()
    scores = dict(baseline)
    scores.update({('qwen3-4b-awq', qid): s for qid, s in awq_scores.items()})
    raw = jsonl(NEW_RUN/'raw_inference.jsonl')
    measured = jsonl(NEW_RUN/'scored.jsonl')
    config = json.loads((NEW_RUN/'config.json').read_text())
    records = {r['question_id']: r for r in raw if r['kind'] == 'inference'}
    assert len(raw) == 52 and raw[-1]['kind'] == 'complete' and raw[-1]['records'] == 50
    assert len(records) == len(measured) == 50
    assert len({s['question_id'] for s in measured}) == 50
    assert (NEW_RUN/'test_cases.json').read_bytes() == (RUN/'test_cases.json').read_bytes()
    hashes = json.loads((NEW_RUN/'source_hashes.json').read_text())
    old_hashes = json.loads((RUN/'source_hashes.json').read_text())
    assert hashes['scripts/model/score_browser_100_benchmark.py'] == old_hashes['scripts/model/score_browser_100_benchmark.py']
    assert config['questions_sha256'] == hashlib.sha256((ROOT/'data/benchmarks/browser_100/dev50.jsonl').read_bytes()).hexdigest()
    prior = {r['question_id']: r for r in jsonl(RUN/'raw_inference.jsonl') if r['kind']=='inference' and r['model']=='qwen' and r['condition']=='A'}
    for q in qs:
        qid=q['question_id'];r=records[qid]
        assert r['condition']=='A' and r['model']==MODEL and r['backend']=='pytorch-mps'
        assert r['prompt']==prior[qid]['prompt'] and r['messages']==prior[qid]['messages']
        assert r['instruction']==q['instruction_ja']
    for s in measured:
        assert s['model']==MODEL and s['condition']=='A'
        scores[MODEL,s['question_id']]=s
    assert len(scores)==300
    return qs,scores,raw,records,config


def summary(qs,scores):
    lines=['| モデル | 合格 / 50問 | 正答率 | 実行方式 |','| --- | ---: | ---: | --- |']
    for m in ALL_ORDER:
        passed=sum(scores[m,q['question_id']]['passed'] for q in qs)
        backend='MacのPython・MPS' if m in [MODEL,'qwen3-4b-awq'] else 'ブラウザ・WebGPU'
        lines.append(f'| {ALL_LABELS[m]} | {passed}/50 | {passed*2}% | {backend} |')
    lines+=['','今回追加したのはQwen3-1.7Bだけ。既存5モデルは過去の実測値を再掲した。条件Aの同じ50問、同じ179入力、同じ採点器を使用し、Qwenの実プロンプト全文・system/userメッセージも一致する。greedy、T=0、thinking無効、最大512新規tokens、反復ペナルティ1、会話履歴なし。','',
            '**重み形式:** 1.7Bは公式の非量子化BF16重みをFP16へ変換してMPSで実行。0.6BはONNX q4f16、4BはAWQ重みをFP16へ展開した別条件。量子化・実行基盤がそろっていないため、得点差をモデルサイズだけの効果とは断定しない。','',
            '### 分類別の合格数（各5問）','','| 分類 | 15M | 5M | 1M | Qwen 0.6B | Qwen 1.7B | Qwen 4B-AWQ |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for i,category in enumerate(CATEGORIES,1):
        ids=[q['question_id'] for q in qs if q['category_id']==f'C{i:02}']
        nums=[sum(scores[m,qid]['passed'] for qid in ids) for m in ALL_ORDER]
        lines.append(f'| C{i:02} {category} | '+' | '.join(map(str,nums))+' |')
    failures=Counter(scores[MODEL,q['question_id']]['reason'] for q in qs if not scores[MODEL,q['question_id']]['passed'])
    lines+=['','1.7Bの不合格理由: '+('、'.join(f'`{k}` {v}件' for k,v in failures.items()) or 'なし')+'。','',
            '1.7Bは23/50（46%）で、0.6Bの19問より4問多く、4B-AWQの32問より9問少なかった。同じ操作の反復は0/5。Boku 15M・1epochの30問との差は7問。これはこの固定集合と生成条件での結果。', '',
            '**代表例:** 「二乗」を`x ** k`へ変更、「0からの距離」を`abs(x-k)`へ変更するなど、指示にないkの使用が見られた。「kを足す」を3回指示しても1回しか実行せず、`xs=[0], k=1`で期待`[3]`に対し`[1]`。不合格27件は結果不一致25件、未定義変数1件、許可外while 1件で、静的検査の2件は実行結果の不一致と区別する。', '',
            f'[Qwen3-1.7Bの全50問の実プロンプト・生成コード・採点・反例]({FILENAME})','']
    return lines


def append_existing():
    if not (NEW_RUN/'scored.jsonl').exists():
        return
    qs,scores,_,_,_=data()
    for name in ['dev50_20261005_results.md','dev50_20261005_condition_a_failures.md','dev50_20261005_additional_models.md','dev50_20261005_details.md','dev50_20261006_qwen3_4b_awq.md']:
        path=OUT/name
        if not path.exists():continue
        original=path.read_text().split(MARKER)[0].rstrip()
        section=f'[Qwen3-1.7Bの全50問の追記]({FILENAME})' if name.endswith('_details.md') else '\n'.join(summary(qs,scores))
        path.write_text(original+'\n\n'+MARKER+'\n\n## 追記：2026年10月6日 Qwen3-1.7Bの条件A評価\n\n'+section+'\n')


def main():
    qs,scores,raw,records,config=data()
    lines=['# 条件Aの追加評価：Qwen3-1.7BをMacで実行','','実施日: 2026年10月6日。公式`Qwen/Qwen3-1.7B`の非量子化重みを使い、このMacのGPUで50問を各1回生成した。指示・コードの補正、得点に応じた問題選別、採点後の再生成は行っていない。','','## 1. 結果','']+summary(qs,scores)
    lines+=['## 2. 実行条件と来歴','',
            f'[公式モデルの固定revision](https://huggingface.co/Qwen/Qwen3-1.7B/tree/{config["revision"]})を取得。各重みファイルのSHA-256をダウンロード記録と照合し、全パラメータをstrictで読み込んだ。入力テンプレートと推論設定は前回のQwen比較と一致させた。4Bとの入力token ID列も全50問で一致を確認した。','',
            '元の重みはBF16、実行時はFP16。AWQ化や4bit再量子化は行っていない。生成はPython＋PyTorch MPSで行い、生成コードの採点は独立したローカルPython子プロセスで行った。許可構文をこのモデルのために変更していない。','',
            '各問題の意味ASTから参照値を計算し、179入力すべてで値・順序・整数リストの型・入力非破壊を検査する。正解コードとの文字列一致による採点ではない。静的検査で拒否した出力には実測反例を付けない。','',
            '実設定:',block(json.dumps(config,ensure_ascii=False,indent=2),'json'),
            '読み込み検証:',block((NEW_RUN/'loading_validation.json').read_text(),'json'),
            '実行環境:',block(json.dumps(next(r for r in raw if r['kind']=='environment'),ensure_ascii=False,indent=2),'json')]
    times=[r['elapsed_seconds'] for r in records.values()]
    lines += [f'完了UTC: `{raw[-1]["completed_at"]}`。生成合計{sum(times):.2f}秒、中央値{statistics.median(times):.2f}秒（重み取得・読込を除く単回の観測。厳密な速度比較ではない）。','',
              '終了理由: '+json.dumps(dict(Counter(r['termination'] for r in records.values())),ensure_ascii=False)+'。','','## 3. 全50問・6モデルの結果','','| 問題 | 指示 | 15M | 5M | 1M | Qwen 0.6B | Qwen 1.7B | Qwen 4B-AWQ |','| --- | --- | --- | --- | --- | --- | --- | --- |']
    for q in qs:
        qid=q['question_id'];marks=['○' if scores[m,qid]['passed'] else '×' for m in ALL_ORDER]
        lines.append(f'| [{qid}](#{qid.lower()}) | {q["instruction_ja"]} | '+' | '.join(marks)+' |')
    lines+=['','## 4. 1.7Bの不合格例','']
    failures=[q for q in qs if not scores[MODEL,q['question_id']]['passed']]
    assert set(FAILURE_NOTES)=={q['question_id'] for q in failures}
    for q in failures:
        qid=q['question_id'];s=scores[MODEL,qid]
        lines+=[f'### 不合格 {qid}','',block(q['instruction_ja']),'読み取り: '+FAILURE_NOTES[qid],'',block(s['code'],'python'),
                block(json.dumps({k:v for k,v in s.items() if k!='code'},ensure_ascii=False,indent=2),'json')]
    if not failures:lines+=['全50問が固定した検査に合格。有限テストでの結果であり、全入力での正しさの証明ではない。','']
    lines+=['## 5. 全問の実プロンプト・生出力・採点','']
    for q in qs:
        qid=q['question_id'];r=records[qid];s=scores[MODEL,qid]
        lines+=[f'### {qid}','',f'結果: **{"合格" if s["passed"] else "不合格"}**','','日本語指示:',block(q['instruction_ja']),
                '正解CNL（モデルには渡さない）:',block(q['canonical_cnl']),
                '実プロンプト全文:',block(r['prompt']),'生出力（修正なし）:',block(r['raw_output']),
                '採点:',block(json.dumps({k:v for k,v in s.items() if k!='code'},ensure_ascii=False,indent=2),'json'),
                f'生成時間: {r["elapsed_seconds"]:.3f}秒。終了: `{r["termination"]}`。新規token数（EOS含む）: {len(r["output_ids"])}。','']
    lines+=['## 6. 元データと再現','']
    for name in ['config.json','source_hashes.json','model_provenance.json','loading_validation.json','raw_inference.jsonl','scored.jsonl','summary.json','test_cases.json']:
        lines.append(f'- [{name}](../../../data/benchmarks/browser_100/runs/{NEW_RUN.name}/{name})')
    lines+=['','既存環境を変更しない専用venvで、torch 2.13.0、transformers 4.51.3、accelerate 1.15.0、safetensors 0.8.0を使用した。指定revisionの公式モデルを取得後、既存記録と重複しないrunへ生成・採点する。','',
            block('python scripts/model/run_qwen_dense_mac_benchmark.py --model-path /PATH/TO/OFFICIAL-QWEN3-1.7B-SNAPSHOT --run data/benchmarks/browser_100/runs/NEW-RUN-ID\npython scripts/model/score_browser_100_benchmark.py --questions data/benchmarks/browser_100/dev50.jsonl --run data/benchmarks/browser_100/runs/NEW-RUN-ID','bash'),
            'この保存済み結果からレポートを再生成:',block('.venv/bin/python scripts/model/report_qwen_17b_mac_benchmark.py','bash')]
    (OUT/FILENAME).write_text('\n'.join(lines)+'\n')
    append_existing()
    print('Wrote 1.7B details and appended six-model comparison.')


if __name__=='__main__':main()
