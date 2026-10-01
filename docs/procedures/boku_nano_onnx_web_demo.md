# Boku1-nano ONNX Webデモ手順書

## 目的

GitHub Pages上のブラウザだけで、自由な日本語からPythonコードまでを次の順で処理する。

1. Qwen3-0.6Bが自由な日本語をControlled Natural Language（CNL）へ翻訳する。
2. JavaScriptがCNLを24種類・最大3操作の規則に照らして検査する。
3. ユーザーがCNLと操作順を確認する。
4. 1M・5M・15Mの学習済み8モデルから選んだBoku1-nanoが、検査済みCNLからコードを生成する。

内部の意味ASTはブラウザ経路に設けない。JavaScriptは自由文の意味解釈やCNL生成を行わず、Qwenの出力を検査するだけである。入力例は自由文欄へ文章を設定するだけで、CNLやコードを固定で返す分岐を持たない。

詳細方針は[`browser_cnl_normalization_policy.md`](../policies/browser_cnl_normalization_policy.md)を参照する。

## 構成

- `web/cnl.js`: 24操作、CNL文法、検査器、Qwen用few-shot prompt
- `web/qwen-worker.js`: Qwenの読込、最大2回のCNL生成、モデル解放
- `web/qwen-manifest.json`: Qwenモデル、revision、成果物hash、Transformers.js version
- `web/demo.js`: UI状態管理、CNL検査、Boku1-nano ONNX推論
- `scripts/model/export_boku_nano_onnx.py`: 学習済み学生モデル8種のONNX変換、モデル別tokenizer配置、PyTorch比較
- `scripts/model/test_boku_nano_web.py`: FirefoxによるCNL検査と学生モデルのスモークテスト
- `.github/workflows/pages.yml`: `main`更新時のPages公開

| 表示名 | tokenizer | Pages用ONNX |
| --- | --- | --- |
| 15M・3エポック | 既存BPE | [boku-nano-3epoch.onnx](../../web/models/boku-nano-3epoch.onnx) |
| 15M・10エポック | 既存BPE | [boku-nano-10epoch.onnx](../../web/models/boku-nano-10epoch.onnx) |
| 15M・1エポック | 既存BPE | [boku-nano-15m-1epoch.onnx](../../web/models/boku-nano-15m-1epoch.onnx) |
| 15M・1エポック | 短いpiece版BPE | [boku-nano-15m-short-1epoch.onnx](../../web/models/boku-nano-15m-short-1epoch.onnx) |
| 5M・1エポック | 既存BPE | [boku-nano-5m-1epoch.onnx](../../web/models/boku-nano-5m-1epoch.onnx) |
| 5M・1エポック | 短いpiece版BPE | [boku-nano-5m-short-1epoch.onnx](../../web/models/boku-nano-5m-short-1epoch.onnx) |
| 1M・1エポック | 既存BPE | [boku-nano-1m-1epoch.onnx](../../web/models/boku-nano-1m-1epoch.onnx) |
| 1M・1エポック | 短いpiece版BPE | [boku-nano-1m-short-1epoch.onnx](../../web/models/boku-nano-1m-short-1epoch.onnx) |

Qwen3-0.6B q4f16は569,789,750 bytesである。Pages成果物へ複製せず、初回翻訳時に固定したHugging Face revisionから取得してブラウザキャッシュへ保存する。Boku1-nanoのONNXは1M級約4.0 MiB、5M級約19.6 MiB、15M級約60.4 MiBで、選択モデルだけを初回生成時にPagesから取得する。モデル切替時は直前のONNXセッションを解放し、複数モデルのメモリ常駐を避ける。

## ONNXの再生成

```bash
uv sync --group onnx-export
uv run --group onnx-export python scripts/model/export_boku_nano_onnx.py
```

変換時に、ONNX形式検査、2プロンプトのlogits比較、greedy生成token列の完全一致、単一ファイルサイズ、各成果物のSHA-256記録を自動実行する。

## 学習済みモデルごとのONNX生成

各モデルディレクトリにもONNXを保存する場合は、[ONNX変換スクリプト](../../scripts/model/export_boku_nano_onnx.py)の`--in-place`を使う。トークナイザーは各`training_manifest.json`から自動選択されるため、既存BPEと短いpiece用BPEを取り違えない。

```bash
uv run --group onnx-export python scripts/model/export_boku_nano_onnx.py \
  --in-place \
  --model <識別名>=data/models/<モデルディレクトリ>
```

各モデルディレクトリへ`model.onnx`と`onnx_manifest.json`を保存する。manifestには元のsafetensors、トークナイザー、ONNXのSHA-256、ファイルサイズ、logits比較、greedy生成一致の結果を記録する。Pagesでは全8モデルを`web/models/`へ配置し、[Webモデルmanifest](../../web/model-manifest.json)でモデルと2種類のtokenizerの対応を固定している。全保存先は[学習済みモデル一覧](../results/trained_model_inventory.md)を参照する。

## ローカル表示

```bash
uv run --group onnx-export python -m http.server 8000 --directory web
```

デスクトップ版ChromeまたはEdgeで`http://127.0.0.1:8000/`を開く。Qwen翻訳にはWebGPUが必要である。Boku1-nanoはWebGPUを優先し、初期化できない場合だけWASMを使用する。自由文とCNLは外部APIへ送信しないが、モデルとJavaScriptの取得通信は発生する。

## 操作手順

1. 自由な日本語を入力し、`QwenでCNLに翻訳`を押す。
2. 初回は約543 MiBのQwenを取得するため、進捗表示が完了するまで待つ。
3. 表示されたCNLと操作順が意図どおりか確認する。
4. 誤りがあれば自由文を変えて再翻訳するか、CNL欄を直接修正して`CNLを再検査`を押す。
5. 検査合格後、1M・5M・15Mの8モデルから比較したいモデルを選び、`このCNLでコードを生成`を押す。

Qwenが`対応できません。`を返した場合、または2回の生成がどちらも検査に失敗した場合、学生モデルの生成ボタンは有効にならない。

## 自動ブラウザ試験

```bash
uv run --group onnx-export python scripts/model/test_boku_nano_web.py \
  --geckodriver /snap/bin/geckodriver
```

この試験は次を確認する。

- CNL定義が24操作である。
- 正しい2操作・3操作CNLを受理する。
- 4操作と許可外操作を拒否する。
- 旧BPE・短いpiece版BPEの両方で、ブラウザ版とPython版のtoken ID列が一致する。
- 選択欄に学習済み8モデルが表示される。
- 3エポック・10エポックモデルが、検査済み2操作・3操作CNLから期待する処理を生成する。
- 追加した1M・5M・15Mの1エポック6モデルが、対応tokenizerでブラウザ推論を完了する。

2026年10月1日のFirefox headless試験では、CNL検査、2種類のBPE一致、8モデルの選択肢、全モデルのWASM推論を確認した。3・10エポック版は2操作・3操作の期待処理まで検査し、追加6モデルは対応tokenizerによる生成完了と`solve`関数出力をsmoke testした。速度は実行機によって変わる。

| モデル | 検査 | 入力token | 生成token | 速度 | 結果 |
| --- | --- | ---: | ---: | ---: | --- |
| 15M・3ep・既存BPE | 2操作 | 13 | 11 | 20.4 tokens/s | 絶対値化、降順ソートを生成 |
| 15M・3ep・既存BPE | 3操作 | 17 | 19 | 49.2 tokens/s | 3倍、符号反転、k未満抽出を生成 |
| 15M・10ep・既存BPE | 2操作 | 13 | 13 | 31.9 tokens/s | 絶対値化、降順ソートを生成 |
| 15M・10ep・既存BPE | 3操作 | 17 | 24 | 47.3 tokens/s | 3倍、符号反転、k未満抽出を生成 |
| 15M・1ep・既存BPE | smoke | 13 | 15 | 32.5 tokens/s | 推論完了、`solve`生成 |
| 15M・1ep・短いpiece | smoke | 28 | 47 | 24.8 tokens/s | 推論完了、`solve`生成 |
| 5M・1ep・既存BPE | smoke | 13 | 14 | 63.3 tokens/s | 推論完了、`solve`生成 |
| 5M・1ep・短いpiece | smoke | 28 | 47 | 72.5 tokens/s | 推論完了、`solve`生成 |
| 1M・1ep・既存BPE | smoke | 13 | 15 | 93.2 tokens/s | 推論完了、`solve`生成 |
| 1M・1ep・短いpiece | smoke | 28 | 61 | 111.5 tokens/s | 推論完了、`solve`生成 |

Firefox headlessではWebGPU Qwenを起動せず、CNLを直接入力して検査器からBoku1-nanoまでを確認した。この実行環境にはChrome系ブラウザがないため、Qwenの実推論は未確認であり、次のChrome手動試験で確認する。

## Qwen翻訳の初回検証

追加学習なしの成立性は、既存の24操作で表現できる自由文を使って確認する。最低限、1操作・2操作・3操作を含む入力群について次を記録する。

- 自由文
- 期待CNL
- Qwen出力
- 文法検査の成否
- 操作種別と操作順の完全一致
- 1回目または再生成のどちらで合格したか
- 初回モデル読込時間、キャッシュ後読込時間、生成時間
- Boku1-nanoのコードとhidden test結果

操作数1・2・3の評価件数は同数を前提にせず、各区分の件数を明記した上で区分別の成功率を報告する。0.6Bの採否はCNL構文合格率だけでなく、期待した操作列の完全一致率と端末上の速度で判断する。

## Chrome手動確認

1. DevToolsのConsoleとNetworkを開く。
2. WebGPUが有効なChromeまたはEdgeでページを開く。
3. 入力例と独自の言い換えをそれぞれ翻訳する。
4. NetworkでQwenが固定revision、Transformers.jsが4.3.0から取得されることを確認する。
5. CNL、操作順、所要時間を記録する。
6. 不正なCNLへ編集し、学生モデルへ渡らないことを確認する。
7. 正しいCNLへ直し、必要な8モデルを切り替えてコード生成する。

## GitHub Pages公開

1. リポジトリのSettingsからPagesを開く。
2. SourceにGitHub Actionsを選ぶ。
3. `main`へpushするか、`GitHub PagesへONNXデモを公開` workflowを手動実行する。
4. workflowが`web/`全体をPages artifactとして公開する。

## 制約

- QwenのCNL文法合格は、自由文の意味を正しく翻訳した保証ではない。
- Qwen翻訳はWebGPUを必須とし、WASMへ自動切替しない。
- CNLは許可された24種類の操作を1～3個だけ含められる。
- Boku1-nanoの最大系列長は入力と生成を合わせて256 tokenである。
- Boku1-nanoの生成方式は評価条件と同じgreedy decodingである。
- Boku1-nanoにはKV cacheがなく、生成tokenごとに現在の系列全体を再計算する。
- 画面はコードを表示するだけで、生成コードを自動実行しない。
- Qwenの処理終了後にWorkerを閉じてモデルを解放してから、Boku1-nanoを読み込む。
