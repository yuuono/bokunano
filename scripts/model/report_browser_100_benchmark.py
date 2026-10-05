"""Write the measured summary and exhaustive prompt/output Markdown appendix."""
from __future__ import annotations
from collections import Counter
import hashlib, json, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'data/benchmarks/browser_100/runs/dev50-20261005'
OUT=ROOT/'docs/results/browser_100'
CATEGORIES=['基本的な抽出','kを使う条件','値の変換','順序の変更','切り出し','2操作の合成','3操作の合成','同じ操作の反復','順序を取り違えやすい合成','未学習の言い回し']
def jsonl(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def block(s,language='text'):
    fence='`'*max(4,max((len(x) for x in __import__('re').findall(r'`+',s)),default=0)+1)
    return f'{fence}{language}\n{s.rstrip()}\n{fence}\n'
def norm(ast):return ast.get('sequence',[ast]) if ast else None

def main():
    qs=jsonl(ROOT/'data/benchmarks/browser_100/dev50.jsonl');raw=jsonl(RUN/'raw_inference.jsonl');scored=jsonl(RUN/'scored.jsonl')
    records={(r['model'],r['condition'],r['question_id']):r for r in raw if r['kind']=='inference'}
    scores={(r['model'],r['condition'],r['question_id']):r for r in scored}
    assert len(records)==300 and len(scores)==250 and any(r['kind']=='complete' for r in raw)
    summary=json.loads((RUN/'summary.json').read_text());pre=json.loads((RUN/'preflight_review.json').read_text());overlap=json.loads((ROOT/'data/benchmarks/browser_100/authoring/overlap_summary.json').read_text());env=next(r for r in raw if r['kind']=='environment');complete=next(r for r in raw if r['kind']=='complete')
    OUT.mkdir(parents=True,exist_ok=True)
    lines=['# ブラウザ版QwenとBoku1-nano：開発用50問の実測結果','', '実施日: 2026年10月5日（日本時間）。10分類×5問。100問本番ではなく、初回の開発用評価。報告対象は条件A・B。保存済みの実行記録は変更せず、不要になった条件Cは本報告・付録から除外した。','', '## 1. 結果','', '| 条件 | Boku1-nano | Qwen3-0.6B |','| --- | ---: | ---: |']
    def score(m,c):
        r=summary[f'{m}/{c}'];return f"{r['passed']}/50（{r['passed']*2}%）"
    lines += [f'| A：同じ日本語から直接コード生成（主比較） | {score("boku","A")} | {score("qwen","A")} |',f'| B：同じ正解CNLから直接コード生成 | {score("boku","B")} | {score("qwen","B")} |','', '1問1点、50点満点。括弧内は正答率であり、100問の実測点ではない。各問は全179ケース一致・整数リスト返却・入力非破壊で合格とした。得点が70点相当になるような問題選別や再生成は行っていない。','', '### 分類別（各5問）','', '| 分類 | Boku A | Qwen A | Boku B | Qwen B |','| --- | ---: | ---: | ---: | ---: |']
    for i,name in enumerate(CATEGORIES,1):
        cat=f'C{i:02}';lines.append('| '+cat+' '+name+' | '+' | '.join(str(summary[f'{m}/{c}']['categories'][cat]) for m,c in [('boku','A'),('qwen','A'),('boku','B'),('qwen','B')])+' |')
    lines+=['','### 不合格の内訳','','| モデル・条件 | 不合格理由と件数 |','| --- | --- |']
    for m,c in [('boku','A'),('qwen','A'),('boku','B'),('qwen','B')]:
        counts=Counter(r['reason'] for r in scored if r['model']==m and r['condition']==c and not r['passed']);lines.append(f'| {m}/{c} | '+('、'.join(f'{k}: {v}' for k,v in counts.items()) or 'なし')+' |')
    lines += ['', '## 2. 作問・重複・レビュー', '', '- 作問: Astra（実際のsubagent指定 `gpt-6-astra`、reasoning effort `high`）。依頼全文と追加修正指示を保存。', '- 承認済み辞書545件からtrain522件を抽出して参照。77操作出現の内訳は、原文使用67・改変5・新規5。意味ASTは42種類、24操作を網羅。', f'- 実訓練192,900件との全文完全一致は {overlap["full_text_known_question_count"]}問。最初の候補で一致した12問は推論前に外側文型だけを変更した。ASTは {overlap["ast_known_question_count"]}問が既知。操作表現は67/77が訓練中に存在するため、全問が未学習の意味・表現ではない。', '- C10の5問は全文・操作表現の完全一致0。語彙全体が未知であることや、Qwenの事前学習データに存在しないことは主張しない。', '- 自然言語問題文への既存テスト専用23件・人手追加9件の混入は検査上0。CNLの文法語句や実装を通じた既存表現への接触はあるため、作問の厳密な盲検とは扱わない。', '- 親AIが50問の日本語とASTを確認し、参照コードは全179入力で検証した。人間による各問題の最終承認は未実施で、今回の結果は開発用候補の評価として扱う。', f'- 推論前固定: `{pre["frozen_at"]}`。問題SHA-256: `{pre["questions_sha256"]}`。', '', '## 3. モデルと実行条件', '', '| 項目 | 設定 |','| --- | --- |', '| Boku | `15m-1epoch`、15,735,168 parameters、既存BPE 2048、ONNX、WebGPU |', '| Qwen | `onnx-community/Qwen3-0.6B-ONNX`、q4f16、WebGPU |', '| Qwen revision | `da1453100cf3ff33ef56d17983fc7a8648706db6` |', '| ライブラリ | Transformers.js 4.3.0、Bokuはリポジトリ同梱ONNX Runtime Web |', '| 生成 | 全条件greedy、T=0、各コード1候補、会話履歴なし |', '| Qwen直接生成 | 最大512新規tokens、repetition_penalty=1、thinking無効 |',  '| Boku上限 | 入力＋出力で最大256 tokens。EOSで終了 |',  '', '生成はブラウザ内で実行し、Pythonによる採点は同じ端末のローカル子プロセスで実行した。モデルはQwenを解放してからBokuをロードした。既存Web UIの標準モデル5Mではなく、方針書で指定した15Mを使用した。', '', '実行ブラウザ・GPUの実測情報:',block(json.dumps({k:env[k] for k in ['user_agent','gpu','started_at']},ensure_ascii=False,indent=2),'json'),f'完了時刻（UTC）: `{complete["completed_at"]}`。再実行時の端末条件を合わせるため、生記録のenvironmentも参照する。', '', '### 生成時間（モデルの初回読込を除く各呼出し）','','| モデル・条件 | 合計秒 | 中央値秒 |','| --- | ---: | ---: |']
    for m,c in [('qwen','A'),('qwen','B'),('boku','A'),('boku','B')]:
        ts=[r['elapsed_seconds'] for r in records.values() if r['model']==m and r['condition']==c and 'elapsed_seconds' in r];lines.append(f'| {m}/{c} | {sum(ts):.2f} | {statistics.median(ts):.2f} |')

    lines += ['', '速度は同一端末上の観測値で、厳密な速度ベンチマーク用の反復測定ではない。Bokuの時間には入力token化を含み、Qwenはテンプレート適用後の生成呼出しを計測する。Qwenの出力token数は生テキストの再token化による推定値。終了理由はpipeline完了／上限到達の疑いとして記録し、厳密なEOS観測とは区別する。', '', '## 4. 実際のプロンプト', '', '### A：元の日本語をそのままコード生成へ渡す', '', 'Bokuには以下の専用形式を使用する。語句のCNL補正は行わない。',block(records['boku','A',qs[0]['question_id']]['prompt']), 'Qwenは同じ日本語をuser messageに置き、共通の関数契約をsystem messageとして加える。両者はモデル固有のテンプレートが異なるため、完全に同一のtoken列を渡す比較ではない。Qwenにのみ正解コードや正解操作を与えることはしていない。', '', 'Qwenのsystem message（全問・A/Bで共通）:',block(records['qwen','A',qs[0]['question_id']]['messages'][0]['content']), '1問目で実際に渡したチャットテンプレート適用後の全文:',block(records['qwen','A',qs[0]['question_id']]['prompt']), '', '### B：正解CNLを入力', '', 'Aと同じ生成設定で、user指示だけを各問のcanonical_cnlへ置換する。Qwenが作ったCNLではなく、事前に検証した正解CNLを両モデルに渡す。',block(qs[0]['canonical_cnl']), '', '## 5. 採点方法と読み方', '', '- 共通179入力: 既存の境界9、固定seedによるランダム128、k=1〜10の条件別40、C09の順序差を検出する不足分2。xsの長さ0〜20、値−100〜100、k=1〜10。', '- 正解は意味ASTを参照インタプリタで実行した値。参考コードとの文字列一致は使わない。', '- 各コードはASTの許可検査後、独立した子プロセスで実行。CPU上限2秒、待機上限3秒、入力非破壊、戻り値の型・値・順番を検査。', '- Qwenの正しい別解を型注釈やappendだけで落とさないよう、既存検証器を変更せず、この評価専用の共通採点器を用意した。型注釈は任意、許可する組み込みとリスト操作はQwenのsystem messageに明示している。importや外部入出力・再帰・任意属性参照は許可しない。', '- 1つのMarkdownコードフェンスのみ除去可能。生成関数の修理、正しい候補の選び直し、採点後の再生成はしない。許可外構文は意味不一致とは別理由に記録する。', '- 最初の失敗入力と期待値・実際値または例外を保存。179ケース一致は有限テストへの合格であり、全入力での正しさの証明ではない。', '', '## 6. 全50問の一覧', '', '| ID | 日本語 | Boku A | Qwen A | Boku B | Qwen B |', '| --- | --- | --- | --- | --- | --- |']
    for q in qs:
        qid=q['question_id'];anchor=qid.lower();marks=['○' if scores[m,c,qid]['passed'] else '×' for m,c in [('boku','A'),('qwen','A'),('boku','B'),('qwen','B')]]
        lines.append(f'| [{qid}](dev50_20261005_details.md#{anchor}) | {q["instruction_ja"]} | '+' | '.join(marks)+' |')
    lines += ['', '## 7. 再現用成果物', '', '- [全50問：条件A・Bの実プロンプト・生出力・採点詳細](dev50_20261005_details.md)', '- [固定した問題JSONL](../../../data/benchmarks/browser_100/dev50.jsonl)', '- [Astraへの実依頼文](../../../data/benchmarks/browser_100/authoring/request_ja.txt)', '- [辞書参照・作問来歴](../../../data/benchmarks/browser_100/authoring/source_snapshot.json)', '- [重複検査](../../../data/benchmarks/browser_100/authoring/overlap_summary.json)', '- [推論前レビュー](../../../data/benchmarks/browser_100/runs/dev50-20261005/preflight_review.json)', '- [実プロンプト・生出力JSONL](../../../data/benchmarks/browser_100/runs/dev50-20261005/raw_inference.jsonl)', '- [採点JSONL](../../../data/benchmarks/browser_100/runs/dev50-20261005/scored.jsonl)', '- [固定テスト入力](../../../data/benchmarks/browser_100/runs/dev50-20261005/test_cases.json)', '- [推論コード・設定等のSHA-256](../../../data/benchmarks/browser_100/runs/dev50-20261005/source_hashes.json)', '', '採点とレポートの再生成:', block('.venv/bin/python scripts/model/score_browser_100_benchmark.py --questions data/benchmarks/browser_100/dev50.jsonl --run data/benchmarks/browser_100/runs/dev50-20261005\n.venv/bin/python scripts/model/report_browser_100_benchmark.py','bash'), '採点対象外の1問による経路確認は `runs/smoke-20261005/` に別保存し、上記50問の成績へ含めていない。']
    analysis = [
        '### 結果の解釈と具体例', '',
        '主比較ではBokuが11問上回った。両者合格10問、Bokuのみ合格20問、Qwenのみ合格9問、両者不合格11問。この開発集合・生成条件での結果であり、汎用コード生成全体の優位性を示すものではない。', '',
        'Bokuは日本語直接入力60%から正解CNL入力94%へ上がった。特にC10は直接入力0/5で、新しい言い回しへの弱さが残る。正解CNLでも、符号反転で未定義変数を使用、反復を1回に省略、絶対値の後に二乗を追加、という3件の誤りがあった。', '',
        '**例1：3操作（dev-C07-01）**',
        block(next(q['instruction_ja'] for q in qs if q['question_id']=='dev-C07-01')),
        'Bokuの出力（条件A、合格）:', block(records['boku','A','dev-C07-01']['raw_output'],'python'),
        'Qwenの生出力（条件A、不合格）:', block(records['qwen','A','dev-C07-01']['raw_output']),
        'Qwenのコメントには「三倍」「小さい順」とあるが、実装は3倍を行わず降順にしている。xs=[1], k=1で期待[3]に対し実際[1]となった。', '',
        '**契約・許可構文による減点**', '',
        'Qwen条件Aの8件は契約または許可構文で不合格だった。dev-C04-03とdev-C04-05は反転処理自体は正しくてもsolve(xs)という1引数のため不合格。dev-C10-03もinsertで反転するが、固定した許可呼出しにinsertがなく不合格だった。これらをすべて意味理解の失敗とは説明しない。主得点は事前の採点契約を維持し、コードと判定理由を付録に残す。', '',
        '[条件Aの全不合格例と両モデルの比較](dev50_20261005_condition_a_failures.md)に、指示・出力・反例・原因をまとめた。', '',
    ]
    at = lines.index('## 2. 作問・重複・レビュー')
    lines[at:at] = analysis
    (OUT/'dev50_20261005_results.md').write_text('\n'.join(lines)+'\n')
    details=['# 開発用50問：実プロンプト・生出力・採点詳細','', '[集計と実行条件](dev50_20261005_results.md)に戻る。以下のコードはモデルの生出力であり、誤答も修正せず掲載する。条件A・Bを掲載。','']
    for q in qs:
        qid=q['question_id'];details += [f'## {qid}', '', f'分類: {q["category_id"]} {CATEGORIES[int(q["category_id"][1:])-1]}', '', '日本語:',block(q['instruction_ja']), '正解CNL:',block(q['canonical_cnl']), '期待する意味AST:',block(json.dumps(q['semantic_ast'],ensure_ascii=False),'json')]
        for m,c in [('boku','A'),('qwen','A'),('boku','B'),('qwen','B')]:
            r=records[m,c,qid];s=scores[m,c,qid];details += [f'### {m} / 条件{c}', '', '実プロンプト:',block(r['prompt']), '生の生成出力:',block(r['raw_output']), '採点:',block(json.dumps({k:v for k,v in s.items() if k!='code'},ensure_ascii=False,indent=2),'json'),f'生成時間: {r.get("elapsed_seconds",0):.3f}秒。終了記録: `{r.get("termination")}`。','']
    (OUT/'dev50_20261005_details.md').write_text('\n'.join(details)+'\n')
    print('Wrote summary and full 50-question Markdown appendix.')
if __name__=='__main__':main()
