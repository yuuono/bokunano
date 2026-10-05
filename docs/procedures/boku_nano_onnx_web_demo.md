> 2026年10月5日更新: 白背景のチャット内に入力欄を置き、最新のやり取りを下へ追加する。操作検索・選択とPythonの色分けに対応。モデル・温度・CNLの編集は設定欄に置く。以下の過去の試験結果は当時の条件を維持して記載している。

# Boku1-nano ONNX Webデモ手順書

## 目的

GitHub Pages上のブラウザだけで、自由な日本語からPythonコードまでを次の順で処理する。

1. Qwen3-0.6Bが自由な日本語をControlled Natural Language（CNL）へ翻訳する。
2. JavaScriptがQwenの操作名を検査し、24種類・最大4操作のCNLへ整形して再検査する。
3. ユーザーがCNLと操作順を確認する。
4. 1M・5M・15Mの学習済み10モデルから選んだBoku1-nanoが、検査済みCNLからコードを生成する。

生成時に検査済みの操作列をデータセット互換の意味ASTとして保存し、コードごとの実行比較に使用する。操作ボタンと入力例は自然な日本語の下書きを入力欄へ挿入し、自由に編集して送信できる。チャットの指示はすべてQwenへ渡す。JavaScriptはQwenの出力について、番号なし・箇条書き・全角・連番の欠け・既知の日本語表現・正規CNLを受け付け、操作の順序と重複を保持してCNL化する。不明な操作、否定、5操作以上は黙って捨てず再試行対象にする。Qwenのk行は任意の補助情報とし、kを使わない処理では破棄する。不正なk表記や矛盾する補助値だけでは操作を拒否せず、値が確定しなければ関数の引数として扱う。操作文や既知の入力で明示された数値を補助情報より優先する。操作ボタン・入力例の明示的な選択は下書きと対応づけて保持し、Qwenの出力がずれた場合は補正を表示して選択内容からCNLを確定する。自由に編集した時点で保持した選択は無効にし、Qwenに解釈させる。変換失敗時は現在のCNLと操作一覧を空にし、過去の結果は会話履歴だけに残す。コードはBoku1-nanoが生成する。

詳細方針は[`browser_cnl_normalization_policy.md`](../policies/browser_cnl_normalization_policy.md)を参照する。

## 構成

- `web/cnl.js`: 24操作、CNL文法、検査器、Qwen用prompt
- `web/qwen-worker.js`: Qwenの読込、最大2回のCNL生成、モデル解放
- `web/qwen-manifest.json`: Qwenモデル、revision、成果物hash、Transformers.js version
- `web/demo.js`: UI状態管理、CNL検査、Boku1-nano ONNX推論
- `scripts/model/export_boku_nano_onnx.py`: 学習済み学生モデル10種のONNX変換、モデル別tokenizer配置、PyTorch比較
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
| 1M・3エポック | 既存BPE | [boku-nano-1m-3epoch.onnx](../../web/models/boku-nano-1m-3epoch.onnx) |
| 1M・3エポック | 短いpiece版BPE | [boku-nano-1m-short-3epoch.onnx](../../web/models/boku-nano-1m-short-3epoch.onnx) |

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

各モデルディレクトリへ`model.onnx`と`onnx_manifest.json`を保存する。manifestには元のsafetensors、トークナイザー、ONNXのSHA-256、ファイルサイズ、logits比較、greedy生成一致の結果を記録する。Pagesでは全10モデルを`web/models/`へ配置し、[Webモデルmanifest](../../web/model-manifest.json)でモデルと2種類のtokenizerの対応を固定している。全保存先は[学習済みモデル一覧](../results/trained_model_inventory.md)を参照する。

## ローカル表示

```bash
uv run --group onnx-export python -m http.server 8000 --directory web
```

デスクトップ版ChromeまたはEdgeで`http://127.0.0.1:8000/`を開く。Qwen翻訳にはWebGPUが必要である。Boku1-nanoはWebGPUを優先し、初期化できない場合だけWASMを使用する。自由文とCNLは外部APIへ送信しないが、モデルとJavaScriptの取得通信は発生する。

## 操作手順

1. チャット下部の白いメッセージ欄へ日本語を入力し、「送信」を押す。自由文の変換はQwenを使い、初回は約543 MiBを取得する。
2. 「操作を追加」で24種類を検索・クリックして入力できる。Enterで検索結果の先頭を追加でき、選択した操作は日本語の下書きになり、入力欄で自由に編集できる。
3. 入力例も自由入力もQwenで整理する。「4操作を試す」は4操作を保持した変換を検査し、実験として受理する。5操作は拒否する。
4. 会話内の操作順とCNLを確認し、「この内容でコードを生成」を押す。同じやり取りの下に色分けしたPythonコードが追加される。コピー時のコード文字列は色分け前と同一。
5. 左の設定欄で10モデル・両温度・CNLを編集できる。900px以下の画面では上部の「設定」から開く。初期モデルは15M・3 epoch・既存BPE、温度は0。
6. 「前の指示を変更」を選ぶと、直前のCNLと数値をQwenに渡して変更できる。通常は「新しい指示」で以前の処理を引き継がない。
7. 最新の会話は末尾に追加され、下端にいるときだけ出力に追従する。過去を読んでいる間は位置を保ち、「最新の返信へ」で戻れる。入力欄は画面下部に残る。
8. 生成停止・コピー・実プロンプト表示・新しい会話による初期化に対応する。数値はチャットから受け取り、独立したk入力欄は設けない。

各回答の「実際のプロンプトを見る」をクリックすると、その実行で使った入力を確認できる。Qwenはsystem/user/assistantのメッセージとテンプレート適用後の文字列、Bokuは特殊トークン付きのプロンプトと入力トークンIDを表示する。Qwenの再生成は試行ごとに記録する。

5操作以上や許可外操作は受理しない。CNL文法合格は意味の正しさや生成コードの正しさを保証しない。生成コードは自動実行しない。コード下の「実行して参照結果と比較」を押すと、指定したxsとkでブラウザ内実行し、保存した意味ASTの参照結果と照合する。

## 自動ブラウザ試験

```bash
uv run --group onnx-export python scripts/model/test_boku_nano_web.py \
  --geckodriver /snap/bin/geckodriver
```

この試験は次を確認する。

- CNL定義が24操作である。
- 正しい2操作・3操作CNLを受理する。
- 4操作を実験として受理し、5操作と許可外操作を拒否する。
- 旧BPE・短いpiece版BPEの両方で、ブラウザ版とPython版のtoken ID列が一致する。
- 選択欄に学習済み10モデルが表示される。
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
- CNLは許可された24種類の操作を1～4個含められる。4操作は学習範囲外の実験。
- Boku1-nanoの最大系列長は入力と生成を合わせて256 tokenである。
- Boku1-nanoはT=0なら既存評価と同じgreedy、T>0ならsampling。生成長は系列長256 tokenの残りまでで、打ち切りを表示する。
- Boku1-nanoにはKV cacheがなく、生成tokenごとに現在の系列全体を再計算する。
- 画面はコードを表示するだけで、生成コードを自動実行しない。
- Qwenの処理終了後にWorkerを閉じてモデルを解放してから、Boku1-nanoを読み込む。

2026-10-05の全24単独操作の実機確認は[検証結果](../results/chat_v10_single_operation_browser.md)を参照。

## v11：コードを入力値で検証する

1. 通常どおり指示を送信し、Pythonコードを生成する。
2. コードカードの下の「入力を試して、結果を検証」で、xsを`[3, -1, 2]`のようなJSONリストで入力し、kを指定する。既定例や「別の入力例」も使用できる。
3. 「実行して参照結果と比較」を押す。初回はPython実行環境の準備が必要。
4. 参照インタプリタと生成Pythonの結果、一致・不一致・エラーを確認する。「検証に使う意味ASTを見る」で、生成時点に保存した比較対象も確認できる。
5. xsまたはkを変えて再実行する。以前のコードも、それぞれのカードから検証できる。

参照仕様の入力範囲はxsの要素−100〜100、最大20個、kは1〜10。kを使わない操作でも同じ関数形式で実行する。関数にkの初期値が書かれていても、検証欄のkを明示的に渡す。一致はその入力についての確認であり、任意の入力や元の自由文の解釈の正しさを保証しない。

Web側の参照ファイルはルートのreference_interpreter.pyの複製。更新時は両方を同期し、`node --test tests/web/*.test.mjs`で一致確認と比較処理のテストを実行する。4操作だけはWebアダプタで同じハンドラを4回適用する。生成Pythonはブラウザ内の独立したWorkerで実行し、停止可能。読み込み60秒・実行5秒で時間切れとし、許可されない構文や実行エラーは結果に表示する。

### v11の実機確認（2026-10-05）

- 15M・3エポックの「各要素に3を足す」をQwen経由で生成し、xs=`[3,-1,2,0,-4,5,2]`、k=3で両方が`[6,2,5,3,-1,8,5]`となることを確認。
- 同じコードでxs=`[1,2,-3]`、k=7へ変更し、関数の初期値3より入力したkを優先して、両方が`[8,9,4]`となることを確認。
- 15M・1エポックの絶対値の誤生成を実行。参照`[3,1,2,0,4,5,2]`に対し生成コード`[9,1,4,0,16,25,4]`となり、不一致を表示。
- 同モデルの符号反転の誤生成でUnboundLocalErrorを表示。参照の`[-3,1,-2,0,4,-5,-2]`は表示したまま。
- 4操作「偶数→2倍→昇順→逆順」のASTを保持して参照実行。参照`[4,4,0,-8]`と、最後の逆順を落とした生成結果`[-8,0,4,4]`の不一致を表示。
- 別のCNL・モデルで生成した後、最初の加算コードを再検証して`[8,9,4]`が維持されることを確認。現在のCNLや別カードのASTを流用していない。
- 実行環境の準備中に停止し、入力欄と再実行ボタンが使用可能に戻ることを確認。
- Nodeテスト31件合格。24操作のASTをデータセットと照合し、過去に記録した両モデル48件の生成コードを新しい実行器で比較。既知の不一致と実行エラーも区別できた。Python側では4操作・反復二乗の大整数・実行回数制限・構文拒否・入力の独立性も確認。

## v12の操作画面

「操作を追加」は一度開けば続けて選べる。「完了」で入力欄に戻る。例は1〜4操作の4ボタンから選択する。設定上部でモデル・温度を選び、その下にCNLの直接編集と生成を配置した。

変更モードの選択は不要。同じ入力欄から「kを5に変えて」などを送信する。選択肢や例で新しく手順を作った場合は前の手順を混ぜない。Qwenの生出力、整形したCNL、Boku1-nanoのPython出力を別の見出しで表示する。アプリによる番号付きの確認説明は削除した。

v12の実ブラウザ確認：一覧を閉じずに偶数・2倍・昇順・逆順を順に選択でき、4操作で追加ボタンが無効になることを確認。全4個の例ボタンが対応する下書きを入れること、「各要素に3を足す」に続けて「kを5に変えて」でk=5へ変更され、そのコードと検証欄が生成されることを確認した。その後「2操作」の例を送信すると、以前の加算やk=5を引き継がず絶対値→降順となった。モード切り替えと重複確認文は表示されず、設定欄の見出し順はモデルと温度→内容確認となっている。

## v13の現在の公開構成

既定モデルは5M・1エポック・既存BPE。設定ボタンを押したときだけ「モデル・詳細」が開く。画面はベージュ系に変更し、操作追加・例ボタンを撤去した。チャット先頭に1〜4操作の文章例を表示する。

v11で追加した実行・比較欄はPagesから外した。実装はリポジトリに保持し、公開workflowがcode-verification.js、verification-worker.js、verification_runtime.py、reference_interpreter.pyを配信成果物から除外する。実行方式は[専用の説明](browser_reference_interpreter.md)を参照。上記v11・v12の手順と記録は当時の仕様である。
