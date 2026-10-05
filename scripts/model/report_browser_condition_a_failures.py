"""Report every condition-A failure from frozen dev50 results; no new inference."""
from collections import Counter
from report_browser_100_benchmark import ROOT, RUN, OUT, CATEGORIES, block, jsonl

NAMES = {'boku': 'Boku1-nano', 'qwen': 'Qwen3-0.6B'}
REASONS = {
    'output_mismatch': '実行結果の不一致',
    'contract_or_allowed_syntax': '関数契約・許可構文の検査で拒否',
    'syntax_error': 'Python構文エラー',
    'runtime_error': '実行時例外',
    'input_mutation': '入力リストを変更',
}
# Code-reading explanations are separate from the unchanged measured verdicts.
NOTES = {
 'boku': {
  'C01-03': '正の値を選ぶ代わりに、k未満を抽出してからk以上を抽出する。両立しない条件なので空になる。',
  'C02-02': '最初の抽出がk < xで、kと等しい要素を落とす。後段の>=では取り戻せない。',
  'C02-03': 'k未満という指示に対して、kより大きい値を抽出する。大小が逆。',
  'C02-04': 'kより大きい値を抽出した後、k以下を抽出するため空になる。',
  'C02-05': '倍数判定の前に、指示にない「kより大きい値だけ残す」を加える。0や負の倍数を落とす。',
  'C03-01': '加算前に、指示にない「kより大きい値だけ残す」を加える。',
  'C03-02': '減算前に、指示にない「kより大きい値だけ残す」を加える。',
  'C03-04': '符号を反転した後に、指示にない二乗を行う。',
  'C05-01': '先頭k個の取り出し前に、指示にないkより大きい値の抽出を行う。',
  'C05-03': '1個おきの取り出しを2回行う。要求はxs[::2]だが、実質xs[::4]になる。',
  'C05-04': '先頭k個という指示に対して、kより大きい値の抽出・反転・2倍を生成する。',
  'C05-05': '末尾k個の取り出し前に、指示にないkより大きい値の抽出を行う。',
  'C06-05': '二乗後の1個おきの取り出しを、要求より1回多く行う。',
  'C07-05': '内包表記の変数はvalueなのに、条件式で未定義のxを参照する。静的検査で停止した。',
  'C08-05': '1個おきの取り出し2回という指示を、反転→1個おき1回へ変更する。',
  'C10-01': '閉じ角括弧が不足して構文エラー。出力には、指示にないk未満の抽出・間引き・3倍も含まれる。',
  'C10-02': '「0からの距離」（絶対値）を、負の値だけ抽出して2倍する処理へ取り違える。',
  'C10-03': '未定義のresultを反復しており、さらに指示にない3倍が入る。静的検査で停止した。',
  'C10-04': '未定義のresultを反復する。先頭k個ではなく、kとの比較と間引きを生成する。',
  'C10-05': 'kを引く前に、指示にない3倍を行う。',
 },
 'qwen': {
  'C01-03': '正の値という条件に、指示にないnum <= kを追加して大きな正数を落とす。',
  'C02-01': '許可外のremoveで拒否。コードを読むと、残すべきkより大きい値を逆に削除し、入力自体も変更している。後者は実測判定ではなくコード読解。',
  'C02-02': 'k以上をkより大きいに取り違え、等しい値を落とす。',
  'C02-03': 'kより大きい値だけを除外するため、kと等しい値が残る。「未満」と「以下」の混同。',
  'C02-04': 'k以下の比較を行わず、num > 0 and k > 0で正数を選ぶ。',
  'C04-01': '許可外のlambdaで拒否。コード読解でも、kをソート方式の選択番号として扱い、常に昇順という指示に従っていない。',
  'C04-02': '許可外のinsertで拒否。コード読解では元の順番を反転するだけで、降順ソートにはなっていない。',
  'C04-03': '反転処理xs[::-1]自体は正しい。solve(xs)という1引数で、要求されたsolve(xs, k)の契約を満たさない。意味理解の失敗と断定しない。',
  'C04-04': '許可外のlambdaで拒否。kをソート方式の選択番号として扱う処理も指示にない。',
  'C04-05': 'list(reversed(xs))という反転処理自体は正しいが、solve(xs)という1引数で契約不一致。意味理解の失敗と断定しない。',
  'C05-02': '末尾k個という指示に対して、先頭k個xs[:k]を返す。',
  'C05-03': '1引数で契約不一致。コード読解でも間引かず、全要素をコピーしている。',
  'C05-05': '末尾k個という指示に対して、先頭k個xs[:k]を返す。',
  'C06-03': '要求は末尾k個の反転だが、先頭k個を反転し、不要な残りxs[k:]を付け戻している。',
  'C06-05': '二乗して1個おきに取る代わりに、先頭k個を二乗する。空入力への添字参照でIndexError。',
  'C07-01': '3倍を省略し、昇順を降順に変更する。コメントの「三倍」「小さい順」と実装が一致しない。',
  'C07-02': '正の値の抽出とk加算を省略し、末尾k個ではなく先頭k個を返す。',
  'C07-03': 'kを用いる条件をx >= 0へ変更し、要求された処理を省略して昇順にする。',
  'C07-04': '反転→先頭k個→k減算の指示を、先頭k個→反転へ変更する。空入力でxs[0]へアクセスしてIndexError。',
  'C07-05': '間引きを省略し、条件を満たす場合は2倍する前の値、満たさない場合は2倍した値を残す。抽出になっていない。',
  'C08-01': '2倍を2回（4倍）という指示を、k倍1回へ置き換える。',
  'C08-02': 'k加算3回のうち1回しか実行しない。',
  'C08-03': 'xs[num]へ代入して入力を変更する。減算も1回だけで、要素の値を添字に使う問題もある。採点は最初の入力変更で停止した。',
  'C08-04': '3倍を3回（27倍）という指示を、k倍1回へ置き換える。',
  'C08-05': '1個おき2回を先頭k個の取得に取り違える。空入力でIndexError。',
  'C09-02': '二乗後に条件を満たす値を抽出せず、条件成立時に元の値、不成立時に二乗値を残す。',
  'C09-03': '要素数がk未満のとき、ソートせず元のリストを返してしまう。',
  'C09-04': 'ソートを行わず、分割したxsの前半と後半を再結合し、元のリスト全体を返す。',
  'C09-05': '符号反転を省略し、元の値が正かどうかだけで選ぶ。',
  'C10-02': '「0からの距離」（絶対値）をk倍へ取り違える。',
  'C10-03': 'insert(0, ...)で順序を反転するアルゴリズム自体は正しい。固定した許可呼出しにinsertがなく拒否された採点上の制約であり、反転ができない証拠にはしない。',
 },
}


def main():
    qs = jsonl(ROOT / 'data/benchmarks/browser_100/dev50.jsonl')
    scores = {(s['model'], s['question_id']): s for s in jsonl(RUN / 'scored.jsonl') if s['condition'] == 'A'}
    assert len(qs) == 50 and len(scores) == 100
    for m in NAMES:
        assert set(NOTES[m]) == {qid.removeprefix('dev-') for (model, qid), s in scores.items() if model == m and not s['passed']}
    groups = [
        ('Boku1-nanoだけが不合格', False, True, 9),
        ('Qwen3-0.6Bだけが不合格', True, False, 20),
        ('両モデルとも不合格', False, False, 11),
    ]
    lines = ['# 条件A：Boku1-nanoとQwen3-0.6Bが失敗した例', '',
        '2026年10月5日の保存済み実測を整理。条件Aは、同じ自然な日本語から両モデルがそれぞれ直接Pythonコードを生成する比較。CNL変換・補正は挟まない。本書は条件Aだけを扱う。モデルの再生成や採点条件の変更は行っていない。', '',
        'Boku1-nanoは15M・1 epoch（15,735,168 parameters）、Qwen3-0.6BはONNX q4f16。両者ともWebGPU・greedy・T=0・1問1候補・会話履歴なし。Webデモ既定の5Mモデルの成績ではない。', '',
        '## 1. 結果の見取り図', '',
        '| 結果 | 問題数 |', '| --- | ---: |',
        '| 両モデルとも合格 | 10 |', '| Boku1-nanoだけが不合格 | 9 |',
        '| Qwen3-0.6Bだけが不合格 | 20 |', '| 両モデルとも不合格 | 11 |', '',
        '**Boku1-nanoは30/50合格・20問不合格、Qwen3-0.6Bは19/50合格・31問不合格。** 少なくとも片方が不合格の全40問を以下に掲載する。同じ11問で両方が不合格なので、モデル別不合格件数の合計は51件となる。', '',
        '「不合格」は、固定した関数契約・許可構文・全179入力の検査を通らなかったという意味。別のプロンプトでも絶対に解けないという主張ではない。Qwenの3例（C04-03、C04-05、C10-03）は反転処理自体が正しく、引数契約や採点器の制限による不合格として区別する。', '',
        '### モデルごとに目立った誤り', '',
        '- **Boku1-nano:** 指示にないkによる抽出を加える、操作を余分に繰り返す、新しい言い回しから別操作を生成する。C10の言い換え5問はすべて不合格だった。',
        '- **Qwen3-0.6B:** 複数操作の省略、反復回数の無視、先頭と末尾の混同。3操作と反復は各5問とも不合格。一方、基本的な値の変換は5問とも合格した。',
        '- **両モデル共通:** k以上／未満／以下の境界や、絶対値を「0からの距離」と表した問題で失敗した。', '',
        'これらは生成コードから観察した傾向であり、学習過程などの内部原因を特定したものではない。', '',
        '### すぐ確認できる代表例', '',
        '| 指示の要点 | Boku1-nano | Qwen3-0.6B | 詳細 |', '| --- | --- | --- | --- |',
        '| 各要素にkを足す | 先にkより大きい値を抽出してしまう | 合格 | [C03-01](#dev-c03-01) |',
        '| 符号を反転する | 反転した後に二乗してしまう | 合格 | [C03-04](#dev-c03-04) |',
        '| 奇数抽出→3倍→昇順 | 合格 | 3倍を省略し降順にする | [C07-01](#dev-c07-01) |',
        '| kを足す操作を3回 | 合格 | 1回しか足さない | [C08-02](#dev-c08-02) |',
        '| k以上を残す | kと等しい値を落とす | kと等しい値を落とす | [C02-02](#dev-c02-02) |',
        '| 0からの距離に置き換える | 負の値だけ残して2倍 | k倍 | [C10-02](#dev-c10-02) |',
        '| 今の順序を反転する | 合格 | 処理は正しいがk引数を欠く | [C04-03](#dev-c04-03) |', '',
        '### 不合格理由（最初に検出された理由で集計）', '',
        '| 理由 | Boku1-nano | Qwen3-0.6B |', '| --- | ---: | ---: |']
    counts = {m: Counter(s['reason'] for (model, _), s in scores.items() if model == m and not s['passed']) for m in NAMES}
    for reason, label in REASONS.items():
        lines.append(f'| {label} | {counts["boku"][reason]} | {counts["qwen"][reason]} |')
    lines += ['', 'Bokuの「関数契約・許可構文」3件は未定義変数の検出。Qwenの同分類8件は引数不足3件、許可外の呼出し3件、lambda使用2件。許可外と判定されたコードには意味誤りも含まれ得るが、実行しなかったものに実測出力は付けない。', '',
        '### 分類別の不合格数（各5問）', '', '| 分類 | Boku1-nano | Qwen3-0.6B |', '| --- | ---: | ---: |']
    for i, name in enumerate(CATEGORIES, 1):
        nums = [sum(not s['passed'] for (model, _), s in scores.items() if model == m and s['category_id'] == f'C{i:02}') for m in NAMES]
        lines.append(f'| C{i:02} {name} | {nums[0]} | {nums[1]} |')
    lines += ['', '## 2. プロンプトと採点の読み方', '',
        '各問題の「日本語指示」は両モデルへ渡した共通部分。Bokuには専用の入出力形式、Qwenにはsolve(xs, k)・入力非破壊・許可構文などを指示するsystem messageとチャットテンプレートが付く。完全に同じ文字列のプロンプトではない。[実際の共通プロンプトと生成設定](dev50_20261005_results.md#4-実際のプロンプト)および各問のリンク先で、テンプレート適用後の全文を確認できる。', '',
        '正解は保存済みの意味ASTを参照インタプリタで実行した値。各問179入力（境界・固定seedランダム・k条件・順序検査）を使用し、すべて一致した場合に合格とした。コードの文字列一致では採点していない。', '',
        '以下の生成コードは採点対象として抽出したコード（単一のMarkdownフェンスを除去したもの）。修理や意味の補正はしていない。「読み取り」はコード読解による説明、「実測」は採点記録からの転記を表す。失敗入力は最初に検出されたものなので、両モデルで異なる場合がある。静的検査で止まった例には実測反例がない。', '']
    included = []
    for n, (label, bp, qp, expected_count) in enumerate(groups, 3):
        selected = [q for q in qs if scores['boku', q['question_id']]['passed'] == bp and scores['qwen', q['question_id']]['passed'] == qp]
        assert len(selected) == expected_count
        lines += [f'## {n}. {label}：{len(selected)}問', '', '| 問題 | 指示 |', '| --- | --- |']
        for q in selected:
            qid = q['question_id']
            lines.append(f'| [{qid}](#{qid.lower()}) | {q["instruction_ja"]} |')
        lines.append('')
        for q in selected:
            qid = q['question_id']; included.append(qid)
            lines += [f'### {qid}', '', '**日本語指示（原文）**', '', block(q['instruction_ja']),
                '**期待する処理（正解CNL。条件Aのモデル入力には渡していない）**', '', block(q['canonical_cnl']),
                f'[この問題の実プロンプト全文・生出力](dev50_20261005_details.md#{qid.lower()})', '']
            for m, name in NAMES.items():
                s = scores[m, qid]
                lines += [f'#### {name}：' + ('合格' if s['passed'] else '不合格'), '', block(s['code'], 'python')]
                if s['passed']:
                    lines += ['実測: 全179入力で一致し、関数契約・型・入力非破壊の検査も通過。', '']
                    continue
                lines += [f'判定: **{REASONS[s["reason"]]}**（`{s["reason"]}`）。', '', '読み取り: ' + NOTES[m][qid.removeprefix('dev-')], '']
                if 'xs' in s:
                    lines += [f'- 実測入力: `xs={s["xs"]}`, `k={s["k"]}`', f'- 期待値: `{s["expected"]}`']
                    if 'actual' in s:
                        lines.append(f'- 実際値: `{s["actual"]}`')
                    if 'error' in s:
                        lines.append(f'- 実際の例外: `{s["error"]}`')
                    if s['reason'] == 'input_mutation':
                        lines.append('- 入力リストの変更を検出したため不合格。')
                    lines.append('')
                else:
                    lines += [f'検査エラー: `{s["error"]}`。実行前に拒否されたため、実測の入力・返却値はない。', '']
    assert len(included) == len(set(included)) == 40
    lines += ['## 6. 元データと再生成', '',
        '- [全体集計（条件A・B）](dev50_20261005_results.md)',
        '- [全50問の実プロンプト・生出力（条件A・B）](dev50_20261005_details.md)',
        '- [固定問題JSONL](../../../data/benchmarks/browser_100/dev50.jsonl)',
        '- [採点記録JSONL](../../../data/benchmarks/browser_100/runs/dev50-20261005/scored.jsonl)',
        '- [生の推論記録JSONL](../../../data/benchmarks/browser_100/runs/dev50-20261005/raw_inference.jsonl)', '',
        '過去の実行記録は追跡可能性のためそのまま保存。本書はcondition=Aの100件だけを抽出して作成した。', '',
        block('.venv/bin/python scripts/model/report_browser_condition_a_failures.py', 'bash')]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'dev50_20261005_condition_a_failures.md'
    path.write_text('\n'.join(lines) + '\n')
    print(f'Wrote {path}: 40 questions, 20 Boku failures, 31 Qwen failures.')


if __name__ == '__main__':
    main()
