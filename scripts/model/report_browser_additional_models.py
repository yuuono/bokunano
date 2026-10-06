"""Append the measured 5M/1M condition-A runs to the original dev50 reports."""
from collections import Counter
import hashlib
import json
import statistics
from pathlib import Path
from report_browser_100_benchmark import ROOT, RUN, OUT, CATEGORIES, block, jsonl

NEW_MODELS = ['5m-1epoch', '1m-3epoch']
LABELS = {'15m-1epoch': 'Boku1-nano 15M・1epoch', '5m-1epoch': 'Boku1-nano 5M・1epoch',
          '1m-3epoch': 'Boku1-nano 1M・3epoch', 'qwen': 'Qwen3-0.6B'}
ORDER = list(LABELS)
DETAILS = 'dev50_20261005_additional_models.md'
MARKER = '<!-- additional-condition-a-models -->'
END = '<!-- /additional-condition-a-models -->'


def load():
    questions_path = ROOT / 'data/benchmarks/browser_100/dev50.jsonl'
    qs = jsonl(questions_path)
    base_scores = jsonl(RUN / 'scored.jsonl')
    scores = {(('15m-1epoch' if r['model'] == 'boku' else 'qwen'), r['question_id']): r
              for r in base_scores if r['condition'] == 'A'}
    runs = {}
    old_hashes = json.loads((RUN / 'source_hashes.json').read_text())
    old_raw = {(r['model'], r.get('question_id')): r for r in jsonl(RUN / 'raw_inference.jsonl')
               if r['kind'] == 'inference' and r['condition'] == 'A'}
    for model in NEW_MODELS:
        path = RUN.with_name(RUN.name + '-' + model)
        config = json.loads((path / 'config.json').read_text())
        assert config['conditions'] == ['A'] and config['models'] == ['boku'] and config['boku_model'] == model
        assert config['temperature'] == 0 and not config['history']
        assert config['questions_sha256'] == hashlib.sha256(questions_path.read_bytes()).hexdigest()
        assert (path / 'test_cases.json').read_bytes() == (RUN / 'test_cases.json').read_bytes()
        hashes = json.loads((path / 'source_hashes.json').read_text())
        for source in ['scripts/model/score_browser_100_benchmark.py', 'web/tokenizer.js', 'web/sampling.js']:
            assert hashes[source] == old_hashes[source]
        raw = jsonl(path / 'raw_inference.jsonl')
        inference = {r['question_id']: r for r in raw if r['kind'] == 'inference'}
        assert len(inference) == 50 and len([r for r in raw if r['kind'] == 'inference']) == 50
        assert raw[-1]['kind'] == 'complete' and raw[-1]['records'] == 50
        assert not any(r['kind'] == 'infrastructure_error' for r in raw)
        for q in qs:
            r = inference[q['question_id']]
            assert r['model_id'] == model and r['condition'] == 'A' and not r.get('error')
            assert r['backend'] == 'webgpu' and r['temperature'] == 0
            assert r['instruction'] == q['instruction_ja']
            assert r['prompt'] == old_raw['boku', q['question_id']]['prompt']
            assert r['prompt_ids'] == old_raw['boku', q['question_id']]['prompt_ids']
        measured = jsonl(path / 'scored.jsonl')
        assert len(measured) == 50 and {s['question_id'] for s in measured} == set(inference)
        scores.update({(model, s['question_id']): s for s in measured})
        env = next(r for r in raw if r['kind'] == 'environment')
        entry = next(m for m in env['manifest']['models'] if m['id'] == model)
        tokenizer = env['manifest']['tokenizers'][entry['tokenizer_id']]
        for asset in [entry, tokenizer]:
            assert hashlib.sha256((ROOT / 'web' / asset['path']).read_bytes()).hexdigest() == asset['sha256']
        runs[model] = {'path': path, 'config': config, 'raw': inference, 'env': env,
                       'complete': raw[-1], 'entry': entry, 'tokenizer': tokenizer}
    assert len(scores) == 200
    return qs, scores, runs


def summary_lines(qs, scores):
    lines = ['| モデル | 合格 / 50問 | 正答率 | 不合格 |', '| --- | ---: | ---: | ---: |']
    for model in ORDER:
        passed = sum(scores[model, q['question_id']]['passed'] for q in qs)
        lines.append(f'| {LABELS[model]} | {passed}/50 | {passed * 2}% | {50-passed} |')
    lines += ['', '15MとQwenは前回の条件Aの実測を再掲し、5M・1epochと1M・3epochだけを追加実行した。条件Bは追加評価していない。50問の固定集合・各1候補での結果であり、1Mのほうが5Mより一般に優れるとは結論しない。サイズに加えて学習epoch数も異なる。', '',
              '### 分類別の合格数（各5問）', '',
              '| 分類 | 15M・1epoch | 5M・1epoch | 1M・3epoch | Qwen3-0.6B |',
              '| --- | ---: | ---: | ---: | ---: |']
    for i, label in enumerate(CATEGORIES, 1):
        nums = [sum(scores[m, q['question_id']]['passed'] for q in qs if q['category_id'] == f'C{i:02}') for m in ORDER]
        lines.append(f'| C{i:02} {label} | ' + ' | '.join(map(str, nums)) + ' |')
    lines += ['', '5M・1MともにC07（3操作）は5/5で、15Mが落としたC07-05も合格した。一方、C10（新しい言い回し）は両モデル0/5。5MはC05（切り出し）0/5、1Mは同分類1/5だった。', '',
              '### 追加モデルの不合格理由', '', '| 理由 | 5M・1epoch | 1M・3epoch |', '| --- | ---: | ---: |']
    counts = {m: Counter(scores[m, q['question_id']]['reason'] for q in qs if not scores[m, q['question_id']]['passed']) for m in NEW_MODELS}
    for reason, label in [('output_mismatch', '実行結果の不一致'), ('contract_or_allowed_syntax', '契約・許可構文の検査で拒否'), ('syntax_error', 'Python構文エラー'), ('runtime_error', '実行時例外')]:
        lines.append(f'| {label} | {counts[NEW_MODELS[0]][reason]} | {counts[NEW_MODELS[1]][reason]} |')
    lines += ['', '関数契約・許可構文の不合格は、5Mの2件が未定義変数、1Mの1件が空出力（C10-03、関数なし）を静的に検出したもの。全100生成はEOSで終了し、生成上限到達や基盤エラーはなかった。Qwenの契約・許可構文による不合格を意味誤りと区別する扱いは前回のまま維持する。', '',
              '### 追加モデルが失敗した問題', '']
    for model in NEW_MODELS:
        failed = [q['question_id'] for q in qs if not scores[model, q['question_id']]['passed']]
        lines += [f'**{LABELS[model]}：{len(failed)}問**', '',
                  '、'.join(f'[{qid.removeprefix("dev-")}]({DETAILS}#{qid.lower()})' for qid in failed), '']
    lines += ['### 具体的な違い', '',
              '- **C03-01「各要素にkを足す」:** 5Mは加算後に不要な3倍を追加。`xs=[0], k=1`で期待`[1]`に対し`[3]`。1Mは符号反転→偶数抽出へ取り違え、同じ入力で`[0]`。',
              '- **C05-03「先頭から1個おき」:** 5Mは取り出した値をさらに2倍し、`xs=[1], k=1`で期待`[1]`に対し`[2]`。1Mは閉じ角括弧不足で構文エラー。',
              '- **C07-05「1個おき→2倍→kより大きい値」:** 追加した両モデルは全179ケースで合格。15Mは未定義の`x`を参照し不合格だった。', '',
              f'[全50問×追加2モデルの実プロンプト・生出力・採点・実測反例]({DETAILS})', '']
    return lines


def append_existing():
    if not all((RUN.with_name(RUN.name + '-' + m) / 'scored.jsonl').exists() for m in NEW_MODELS):
        return
    qs, scores, _ = load()
    for filename in ['dev50_20261005_results.md', 'dev50_20261005_condition_a_failures.md', 'dev50_20261005_details.md']:
        path = OUT / filename
        if not path.exists():
            continue
        original = path.read_text()
        original = original.split(MARKER)[0].rstrip()
        if filename.endswith('_details.md'):
            section = [f'[5M・1epochと1M・3epochの条件A・全50問の追記]({DETAILS})', '']
        else:
            section = summary_lines(qs, scores)
        path.write_text(original + '\n\n' + MARKER + '\n\n## 追記：5M・1epochと1M・3epochの条件A評価\n\n' + '\n'.join(section) + '\n' + END + '\n')

    from report_qwen_awq_mac_benchmark import append_existing as append_awq
    append_awq()

def main():
    qs, scores, runs = load()
    lines = ['# 条件Aの追加評価：5M・1epoch／1M・3epoch', '',
             '実施日: 2026年10月5日。同じ開発用50問で追加評価し、既存の15M・Qwenと比較する。問題や生成コードの補正、得点に合わせた問題選別、失敗後の再生成は行っていない。', '',
             '[既存の失敗例一覧へ戻る](dev50_20261005_condition_a_failures.md)', '', '## 1. 結果', '']
    lines += summary_lines(qs, scores)
    lines += ['## 2. 比較条件と実行来歴', '',
              '- 条件Aのみ。自然な日本語をBoku専用プロンプトへ直接入力。正解CNL・意味ASTをモデルへ渡さない。',
              '- greedy、T=0、会話履歴なし、1問1候補、系列長上限256（入力＋出力）。既存BPEの同じtokenizerを使用。',
              '- 15Mの条件Aと、全50問のプロンプト全文・入力token ID列が一致することを確認。変更はモデルの重み・構成・epoch数。',
              '- 問題SHA-256、採点器SHA-256、全179テスト入力ファイルの一致を確認。採点器の変更なし。',
              '- ブラウザ推論は追加2モデルを順番に実行し、各モデルの終了後に解放。採点は同端末のPython子プロセス。',
              '- 実行器にはモデル・条件を選択する設定を追加。Bokuのtoken生成処理は前回と同じ。実行時のソースhashを別runに保存。',
              '- 50問は15Mを対象に作成した同一開発集合。5M・1Mそれぞれの実学習指示との重複検査は今回追加実施しておらず、全問が未学習とは主張しない。', '',
              f'問題SHA-256: `{next(iter(runs.values()))["config"]["questions_sha256"]}`', '']
    for model, run in runs.items():
        entry = run['entry']; env = run['env']; times = [r['elapsed_seconds'] for r in run['raw'].values()]
        lines += [f'### {LABELS[model]}', '',
                  f'- model_id: `{model}`、{entry["parameter_count"]:,} parameters、ONNX {entry["size_bytes"]:,} bytes。',
                  f'- モデルSHA-256: `{entry["sha256"]}`',
                  f'- tokenizer SHA-256: `{run["tokenizer"]["sha256"]}`',
                  f'- 開始UTC: `{env["started_at"]}`、完了UTC: `{run["complete"]["completed_at"]}`',
                  f'- 生成時間合計: {sum(times):.2f}秒、中央値: {statistics.median(times):.3f}秒（初回ロード除外）。',
                  '- 速度は単回の観測値。負荷・キャッシュ状態などを統制した速度比較ではない。', '',
                  block(json.dumps({'user_agent': env['user_agent'], 'gpu': env['gpu']}, ensure_ascii=False, indent=2), 'json')]
    lines += ['## 3. 全50問・4モデルの合否', '',
              '| 問題 | 日本語指示 | 15M・1epoch | 5M・1epoch | 1M・3epoch | Qwen3-0.6B |', '| --- | --- | --- | --- | --- | --- |']
    for q in qs:
        qid = q['question_id']; marks = ['○' if scores[m, qid]['passed'] else '×' for m in ORDER]
        lines.append(f'| [{qid}](#{qid.lower()}) | {q["instruction_ja"]} | ' + ' | '.join(marks) + ' |')
    lines += ['', '## 4. 追加2モデルの全プロンプト・生成結果', '',
              '「生出力」は修正せず掲載。「採点」には最初に失敗した入力・期待値・実際値または例外を掲載する。静的検査で拒否したものには実測反例がない。合格は179ケースでの一致であり、全入力での正しさの証明ではない。', '']
    for q in qs:
        qid = q['question_id']
        lines += [f'### {qid}', '', '**日本語指示:**', '', block(q['instruction_ja']),
                  '**期待する処理（モデルに渡していない正解CNL）:**', '', block(q['canonical_cnl']),
                  f'[15MとQwenの元のプロンプト・結果](dev50_20261005_details.md#{qid.lower()})', '']
        for model in NEW_MODELS:
            raw = runs[model]['raw'][qid]; score = scores[model, qid]
            lines += [f'#### {LABELS[model]}：' + ('合格' if score['passed'] else '不合格'), '',
                      '実プロンプト:', '', block(raw['prompt']), '生出力:', '', block(raw['raw_output'], 'python'),
                      '採点:', '', block(json.dumps({k: v for k, v in score.items() if k != 'code'}, ensure_ascii=False, indent=2), 'json'),
                      f'終了: `{raw["termination"]}`。生成時間: {raw["elapsed_seconds"]:.3f}秒。', '']
    lines += ['## 5. 元データと再現', '']
    for model, run in runs.items():
        prefix = '../../../' + str(run['path'].relative_to(ROOT))
        lines += [f'**{LABELS[model]}**', '']
        for filename in ['config.json', 'raw_inference.jsonl', 'scored.jsonl', 'summary.json', 'test_cases.json', 'source_hashes.json']:
            lines.append(f'- [{filename}]({prefix}/{filename})')
        lines.append('')
    lines += ['追加推論の再実行例（既存の測定を上書きしないよう、新しい出力先を指定）:', '',
              block('.venv/bin/python scripts/model/run_browser_100_benchmark.py --questions data/benchmarks/browser_100/dev50.jsonl --output data/benchmarks/browser_100/runs/NEW-RUN-ID --run-id NEW-RUN-ID --boku-model 5m-1epoch --models boku --conditions A', 'bash'),
              '`--boku-model 1m-3epoch`で1M版を実行できる。サーバーが表示したURLをWebGPU対応ブラウザで開き「評価を開始」を押す。', '',
              '保存済み結果からこの追記を再生成:', '', block('.venv/bin/python scripts/model/report_browser_additional_models.py', 'bash')]
    (OUT / DETAILS).write_text('\n'.join(lines) + '\n')
    append_existing()
    print('Wrote additional-model details and appended all three existing reports.')


if __name__ == '__main__':
    main()
