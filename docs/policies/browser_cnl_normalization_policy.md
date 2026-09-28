# ブラウザ内QwenによるCNL翻訳方針

## 1. 目的

GitHub Pages上で自由な日本語を受け取り、ブラウザ内のQwenがControlled Natural Language（CNL）へ翻訳し、検査済みCNLからBoku1-nanoがPythonコードを生成する。

役割は次のように分離する。

- Qwen: 自由な日本語からCNLへの翻訳
- JavaScript: Qwenが出したCNLの文法検査
- Boku1-nano: 検査済みCNLから`solve(xs, k)`コードの生成

JavaScriptは入力の意味を解釈してCNLを作らない。入力例にもコードやCNLを固定対応させず、自由入力と同じQwen・Boku1-nanoの推論経路を通す。

## 2. 追加学習を行わない条件

Qwenには追加学習を行わない。既存のQwen3-0.6Bへ、許可する24操作、CNL文法、少数の日本語からCNLへの変換例をsystem promptとして与える。

形式上正しいCNLでも意味翻訳が正しいとは限らない。そのため、生成後のCNLと抽出した操作順を画面に表示し、ユーザーが確認してからBoku1-nanoを実行する。

## 3. 使用モデルと固定条件

| 項目 | 値 |
| --- | --- |
| model | `onnx-community/Qwen3-0.6B-ONNX` |
| upstream | `Qwen/Qwen3-0.6B` |
| revision | `da1453100cf3ff33ef56d17983fc7a8648706db6` |
| dtype | `q4f16` |
| backend | WebGPU |
| model file | `onnx/model_q4f16.onnx` |
| model file size | 569,789,750 bytes |
| model file SHA-256 | `9e33a5911974174761d0dfdcc0bec975d9c45af0eae5e9eb647b8ba9442a8f91` |
| Transformers.js | 4.3.0 |
| Qwen生成上限 | 96 token |
| sampling | greedy |
| 最大試行回数 | 2 |

固定値は`web/qwen-manifest.json`に保存する。Qwen成果物は約543 MiBあるためGitHub Pages成果物へ複製せず、固定revisionのHugging Faceリポジトリからブラウザキャッシュを利用して取得する。

## 4. CNL文法

CNLは、Boku1-nanoの訓練データを作成した外側テンプレートと同じ形式にする。

`k`を使わない場合:

```text
整数リストxsから{操作列}solve関数を書いてください。
```

`k`を使う場合:

```text
整数リストxsと整数kを受け取り、{操作列}solve関数を書いてください。
```

操作列には[`atomic_semantic_asts.md`](../specifications/atomic_semantic_asts.md)の24操作だけを使用する。操作数は1～3とし、最後以外は接続形、最後は終止形を使用して読点で連結する。

例:

```text
整数リストxsから各要素の絶対値を取り、値を降順に並べるsolve関数を書いてください。
```

正式な24操作と接続形・終止形は`web/cnl.js`を正とする。

## 5. 検査

JavaScriptはQwenの出力に対して次を確認する。

1. 出力が1行だけである。
2. 外側テンプレートが完全一致する。
3. 操作数が1～3である。
4. 各操作が許可された24種類の接続形または終止形と完全一致する。
5. 最後以外が接続形、最後が終止形である。
6. `k`を使う操作と外側テンプレートの入力契約が一致する。
7. 説明、Markdown、JSON、Pythonコードが混入していない。

検査失敗時は、検査エラーと前回出力をQwenへ渡して一度だけ再生成する。2回とも失敗した場合はBoku1-nanoへ渡さず、Qwenの出力と検査エラーを表示する。ユーザーは自由文を変更して再試行するか、CNL欄を直接編集できる。

`対応できません。`は明示的な拒否として扱い、再生成せずBoku1-nanoを実行しない。

## 6. ブラウザ実行順

1. GitHub Pagesを開く。
2. ユーザーが自由な日本語を入力する。
3. Qwen専用module Workerを起動する。
4. Qwen3-0.6B q4f16をWebGPUへ読み込む。
5. CNLを最大2回生成・検査する。
6. Qwenをdisposeし、Workerを終了する。
7. 検査済みCNLと操作順を画面へ表示する。
8. ユーザーが解釈を確認する。
9. 選択中のBoku1-nano ONNXを読み込む。
10. CNLからコードをgreedy生成する。

QwenとBoku1-nanoを順番に読み込むことで、両モデルのGPUメモリ同時保持を避ける。Boku1-nanoの読み込みは従来どおり初回生成時だけ行い、同じページ内では再利用する。

## 7. 対応環境とフォールバック

Qwen翻訳はWebGPUを必須とし、デスクトップ版ChromeまたはEdgeを主対象にする。WebGPUを利用できない場合、QwenをWASMへ自動切替しない。画面に非対応を表示し、CNL直接入力だけを利用可能にする。

Boku1-nanoは従来どおりWebGPUを優先し、利用できない場合はWASMへ切り替える。

## 8. 初回検証

追加学習なしの成立性は、既存の選択肢で表現できる処理を自由な日本語へ言い換え、Qwenが期待するCNLを生成できるかで確認する。

最低限、次を記録する。

- 自由文
- 期待CNL
- Qwen出力
- CNL文法検査の成否
- 操作列完全一致
- 1回目・2回目のどちらで合格したか
- Qwenの初回読込み時間とキャッシュ後時間
- Boku1-nanoの生成結果とhidden test結果

0.6Bの採否はCNLの構文合格率だけでなく、操作種別と操作順の完全一致率で判断する。精度不足の場合は追加学習ではなく、system prompt、少数例、0.6Bから1.7Bへのモデル変更を比較する。

## 9. 制約

- CNLの文法検査は意味の正しさを保証しない。
- 自由な日本語が曖昧な場合、Qwenが誤った許可操作を選ぶ可能性がある。
- 初回は約543 MiBのQwenモデル取得が必要である。
- WebGPU端末、ブラウザ、GPUドライバによって実行可否と速度が異なる。
- Qwen変換に成功しても、Boku1-nanoのコードがhidden testへ合格するとは限らない。
- 本構成はQwenとBoku1-nanoのカスケードであり、Boku1-nano単体が自由な日本語を理解していることを示すものではない。
