"""Report the separately identified AWQ-to-FP16 Apple MPS evaluation."""
from collections import Counter
import json
import statistics
from report_browser_100_benchmark import ROOT, OUT, RUN, CATEGORIES, block, jsonl
from report_browser_additional_models import load, ORDER, LABELS

AWQ_RUN = RUN.with_name('dev50-20261006-qwen3-4b-awq-mps')
FILENAME = 'dev50_20261006_qwen3_4b_awq.md'
MODEL = 'qwen3-4b-awq'
LABEL = 'Qwen3-4B-AWQ（FP16展開・MPS）'
MARKER = '<!-- qwen3-4b-awq-mps-addition -->'


FAILURE_NOTES = {'C02-01': 'kを超える値（x > k）を残す指示に対して、x <= kを残す。条件が逆。', 'C02-02': '抽出条件>=kは正しいが、指示にない昇順ソートを追加し、元の要素順を変える。', 'C02-04': 'x <= kではなくabs(x) <= kを使い、大きな負数を落とす。', 'C03-04': '全要素ではなく先頭k個だけ符号反転する。空入力で添字範囲外になる。', 'C05-03': '先頭から1個おきという指示を、k番目からk個ごとに取り出す処理へ変えている。', 'C05-04': '先頭k個を返す代わりに、先頭k個を除いた残りを返す。', 'C05-05': '末尾k個を返す代わりに、末尾k個を除いた残りを返す。', 'C06-02': '負の値だけの抽出を省略し、全要素の絶対値を返す。', 'C06-03': '末尾k個を反転する処理はあるが、除くべき前半を付け戻している。', 'C06-05': '二乗後の間引きをk % len(squared)個の先頭取得へ取り違える。空入力でゼロ除算。', 'C07-05': '間引きと2倍は行うが、最後のkを超える条件を<=kへ逆転している。', 'C08-01': '2倍を2回（4倍）の指示に対して、2倍を1回しか行わない。', 'C08-02': 'k加算3回の指示に対して、1回しか加算しない。', 'C08-03': 'k減算2回の指示に対して、1回しか減算しない。', 'C08-04': '3倍を3回（27倍）ではなく、3のk乗倍を行う。kは反復回数ではない。', 'C08-05': '許可していないwhileで静的検査により拒否。コード読解でも間隔をkとし、1個おきを2回という指示を実装していない。実行検証は行っていない。', 'C09-05': '符号反転後に正数を選ぶのではなく、全要素を非正の値へ変換する。抽出も行わない。', 'C10-03': '全要素の反転ではなく末尾からk個だけ取る。空入力で添字範囲外になる。'}

def data():
    qs, baseline, _ = load()
    raw = jsonl(AWQ_RUN/'raw_inference.jsonl')
    scored = jsonl(AWQ_RUN/'scored.jsonl')
    config = json.loads((AWQ_RUN/'config.json').read_text())
    assert raw[-1]['kind'] == 'complete' and raw[-1]['records'] == 50
    records = {r['question_id']: r for r in raw if r['kind'] == 'inference'}
    scores = {s['question_id']: s for s in scored}
    assert len(records) == len(scores) == len(scored) == 50
    assert {qid.removeprefix('dev-') for qid, score in scores.items() if not score['passed']} == set(FAILURE_NOTES)
    old_raw = {r['question_id']: r for r in jsonl(RUN/'raw_inference.jsonl') if r['kind'] == 'inference' and r['condition'] == 'A' and r['model'] == 'qwen'}
    assert (AWQ_RUN/'test_cases.json').read_bytes() == (RUN/'test_cases.json').read_bytes()
    hashes = json.loads((AWQ_RUN/'source_hashes.json').read_text())
    old_hashes = json.loads((RUN/'source_hashes.json').read_text())
    assert hashes['scripts/model/score_browser_100_benchmark.py'] == old_hashes['scripts/model/score_browser_100_benchmark.py']
    for q in qs:
        qid = q['question_id']; r = records[qid]
        assert r['condition'] == 'A' and r['model'] == MODEL and r['prompt'] == old_raw[qid]['prompt']
        assert r['messages'] == old_raw[qid]['messages'] and r['instruction'] == q['instruction_ja']
    assert config['questions_sha256'] == json.loads((RUN/'config.json').read_text())['questions_sha256']
    return qs, baseline, raw, records, scores, config


def summary(qs, baseline, scores):
    passed = sum(s['passed'] for s in scores.values())
    lines = ['| モデル | 合格 / 50問 | 正答率 | 実行方式 |', '| --- | ---: | ---: | --- |']
    for m in ORDER:
        count = sum(baseline[m, q['question_id']]['passed'] for q in qs)
        lines.append(f'| {LABELS[m]} | {count}/50 | {count*2}% | ブラウザ・WebGPU |')
    lines += [f'| **{LABEL}** | **{passed}/50** | **{passed*2}%** | **このMacのPython・Apple GPU** |', '',
              '追加分も条件Aの同じ50問・同じ179テスト入力・同じ採点器。Qwen3-0.6Bとsystem/userメッセージおよびテンプレート適用後の全文が一致する。greedy、T=0、thinking無効、最大512新規tokens、反復ペナルティ1、会話履歴なし。旧4モデルの数値は前回実測を再掲した。', '',
              '**実行方式の違い:** 公式`Qwen/Qwen3-4B-AWQ`の4bit量子化済み重みをFP16へ展開してMPSで実行した。元の非量子化4BやMLX版への置換・再量子化はしていない。AWQのCUDAカーネルでの実行とは浮動小数点演算が異なり、出力の完全一致は保証しない。WebGPUの0.6Bとはモデルサイズだけでなく量子化・実行基盤も違うため、速度やサイズ単独の効果を断定する比較には使わない。', '',
              '### 分類別の合格数（各5問）', '',
              '| 分類 | 15M・1epoch | 5M・1epoch | 1M・3epoch | Qwen 0.6B | Qwen 4B-AWQ |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for i, category in enumerate(CATEGORIES, 1):
        ids = [q['question_id'] for q in qs if q['category_id'] == f'C{i:02}']
        counts = [sum(baseline[m, qid]['passed'] for qid in ids) for m in ORDER]
        counts.append(sum(scores[qid]['passed'] for qid in ids))
        lines.append(f'| C{i:02} {category} | ' + ' | '.join(map(str, counts)) + ' |')
    failures = Counter(s['reason'] for s in scores.values() if not s['passed'])
    lines += ['', f'追加モデルの不合格は{50-passed}問。理由別: '+ ('、'.join(f'`{k}` {v}件' for k, v in failures.items()) or 'なし')+'。', '',
              '0.6Bの19問から4Bは32問へ増えた。基本抽出と順序変更は5/5、新しい言い回しは4/5。一方、同一操作の反復は0/5で、kの比較方向や取り出す部分の誤りも残った。Boku 15M（30問）との差は2問であり、この50問から一般的な優劣は断定しない。', '',
              '**例:** 「kを足す」を3回要求しても`x + k`しか生成せず、`xs=[0], k=1`で期待`[3]`に対し`[1]`となった。「k以上を残す」では不要なソートを追加し、`xs=[53,-28,35,-66,-69,-14,-23], k=1`で期待`[53,35]`に対し`[35,53]`となった。', '',
              f'[追加50問の実プロンプト・生出力・採点・反例]({FILENAME})', '']
    return lines


def append_existing():
    if not (AWQ_RUN/'scored.jsonl').exists():
        return
    qs, baseline, _, _, scores, _ = data()
    section = '\n'.join(summary(qs, baseline, scores))
    for name in ['dev50_20261005_results.md', 'dev50_20261005_condition_a_failures.md', 'dev50_20261005_additional_models.md', 'dev50_20261005_details.md']:
        path = OUT/name
        if not path.exists():
            continue
        text = path.read_text().split(MARKER)[0].rstrip()
        content = f'[Qwen3-4B-AWQの全50問の追記]({FILENAME})' if name.endswith('_details.md') else section
        path.write_text(text+'\n\n'+MARKER+'\n\n## 追記：2026年10月6日 Qwen3-4B-AWQの条件A評価\n\n'+content+'\n')


def main():
    qs, baseline, raw, records, scores, config = data()
    lines = ['# 条件Aの追加評価：Qwen3-4B-AWQをMacで実行', '',
             '実施日: 2026年10月6日。公式AWQ重みをFP16に展開し、このMacのApple GPU（PyTorch MPS）で生成した。前回と同じ50問を各1回実行し、生成コードの補修・正解選別・採点後の再生成は行っていない。', '',
             '## 1. 結果', ''] + summary(qs, baseline, scores)
    lines += ['## 2. モデルと実行条件', '',
              'Qwen3のDenseモデルは0.6B、1.7B、4B、8B、14B、32B。したがって0.6Bのすぐ次は1.7Bであり、今回は指定された4BのAWQ版を使用した。[Qwen公式発表](https://qwenlm.github.io/zh/blog/qwen3/)', '',
              '[公式モデル](https://huggingface.co/Qwen/Qwen3-4B-AWQ)のrevisionを固定し、重みのSHA-256を保存した。AWQは重みの量子化形式で、モデルサイズとは別の条件。[AWQの公式ライブラリ実装](https://github.com/casper-hansen/AutoAWQ/blob/main/awq/utils/packing_utils.py)に基づき、4bit整数の並び順を戻し、`(整数重み − zero_point) × scale`をFP16で計算する。新しい量子化や元のFP16重みの取得は行わない。', '',
              '作問資料の来歴: 承認済み日本語表現辞書545件の生成記録は、このQwen3-4B-AWQと同じrevisionを教師モデルとして記録している。今回の50問はAstraが作成し、辞書のtrain区分を参考にしたもの。これはQwenの学習データへの混入を示す証拠ではないが、比較対象モデルと問題表現の作成過程が完全に独立した評価ではない。[辞書の生成来歴](../../../data/instruction_dictionaries/release/japanese_atomic_expression_provenance.jsonl)', '',
              '展開処理は全16値・符号付きpacked word・複数groupの独立テストで確認した。実モデルの252個の量子化Linear層でも計1,008箇所をスカラー計算と完全一致で確認し、全パラメータの読み込みはstrictで検証した。これはCUDA版全体とのlogit同一性を保証する検証ではない。', '',
              '実設定:', '', block(json.dumps(config, ensure_ascii=False, indent=2), 'json'),
              '実行環境と生成設定:', '', block(json.dumps(next(r for r in raw if r['kind']=='environment'), ensure_ascii=False, indent=2), 'json'),
              '読み込み検証:', '', block((AWQ_RUN/'loading_validation.json').read_text(), 'json')]
    times = [r['elapsed_seconds'] for r in records.values()]
    lines += [f'完了UTC: `{raw[-1]["completed_at"]}`。生成時間合計{sum(times):.2f}秒、中央値{statistics.median(times):.2f}秒。重み取得・展開・読み込みは含まない。速度比較用の反復測定はしていない。', '',
              '終了理由: '+json.dumps(dict(Counter(r['termination'] for r in records.values())), ensure_ascii=False)+'。', '',
              '## 3. 全50問の結果', '',
              '| 問題 | 指示 | 15M | 5M | 1M | Qwen 0.6B | Qwen 4B-AWQ |', '| --- | --- | --- | --- | --- | --- | --- |']
    for q in qs:
        qid=q['question_id'];marks=['○' if baseline[m,qid]['passed'] else '×' for m in ORDER]+['○' if scores[qid]['passed'] else '×']
        lines.append(f'| [{qid}](#{qid.lower()}) | {q["instruction_ja"]} | '+' | '.join(marks)+' |')
    lines += ['', '## 4. 不合格例', '',
              '意味の誤りと、引数・許可構文による不合格を区別する。採点器や許可構文を4B向けに緩めて再採点することはしていない。', '']
    failures = [q for q in qs if not scores[q['question_id']]['passed']]
    for q in failures:
        qid=q['question_id'];score=scores[qid]
        lines += [f'### 不合格 {qid}', '', block(q['instruction_ja']), '読み取り: '+FAILURE_NOTES[qid.removeprefix('dev-')], '', block(score['code'], 'python'),
                  block(json.dumps({k:v for k,v in score.items() if k!='code'}, ensure_ascii=False, indent=2), 'json')]
    if not failures:
        lines.append('全50問が固定した179ケースと関数契約の検査に合格。有限テストの結果であり、全入力での正しさの証明ではない。')
    lines += ['', '## 5. 実プロンプト・生出力・採点の全件記録', '',
              '誤答も修正せず掲載する。合格は全179ケース一致。採点JSONの反例は最初に失敗した入力で、静的検査で拒否した出力には実測反例がない。', '']
    for q in qs:
        qid=q['question_id'];r=records[qid];s=scores[qid]
        lines += [f'### {qid}', '', f'結果: **{"合格" if s["passed"] else "不合格"}**', '',
                  '日本語指示:', '', block(q['instruction_ja']), '期待するCNL（モデルには渡さない）:', '', block(q['canonical_cnl']),
                  '実プロンプト全文:', '', block(r['prompt']), '生の生成出力:', '', block(r['raw_output']),
                  '採点:', '', block(json.dumps({k:v for k,v in s.items() if k!='code'}, ensure_ascii=False, indent=2), 'json'),
                  f'生成時間: {r["elapsed_seconds"]:.3f}秒。終了: `{r["termination"]}`。新規token数（EOS含む）: {len(r["output_ids"])}。', '']
    lines += ['## 6. 元データと再生成', '']
    for name in ['config.json','source_hashes.json','loading_validation.json','model_provenance.json','raw_inference.jsonl','scored.jsonl','summary.json','test_cases.json']:
        lines.append(f'- [{name}](../../../data/benchmarks/browser_100/runs/{AWQ_RUN.name}/{name})')
    lines += ['', '実行時は既存環境を変更しない専用venvへtorch 2.13.0、transformers 4.51.3、accelerate 1.15.0、safetensors 0.8.0を用意した。公式revisionの取得後、次のコマンドで別runへ生成・採点できる。', '',
              block('python scripts/model/run_qwen_awq_mac_benchmark.py --model-path /PATH/TO/OFFICIAL-AWQ-SNAPSHOT --run data/benchmarks/browser_100/runs/NEW-RUN-ID\npython scripts/model/score_browser_100_benchmark.py --questions data/benchmarks/browser_100/dev50.jsonl --run data/benchmarks/browser_100/runs/NEW-RUN-ID', 'bash'),
              'この保存済み結果のレポート再生成:', '', block('.venv/bin/python scripts/model/report_qwen_awq_mac_benchmark.py', 'bash')]
    (OUT/FILENAME).write_text('\n'.join(lines)+'\n')
    append_existing()
    print('Wrote Qwen3-4B-AWQ detailed report and appended prior reports.')


if __name__ == '__main__':
    main()
