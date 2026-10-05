# 自己回帰生成と温度の説明スライド作成方針

作成日: 2026年10月5日

状態: 説明内容と資料追加の計画。発表資料と生成実装は未変更。

> 2026年10月5日追記: 後続のWeb UI改修で、ブラウザにも温度samplingを実装した。以下の「現在のWebはgreedy」は改修前の調査結果を指す。スライド実作成時は`web/sampling.js`と更新後の`web/demo.js`も出典に加え、T=0がgreedy、T>0がsamplingと説明する。発表資料は未変更。

## 1. 目的

Boku1-nanoがPythonコードを作る過程を、実際の生成コードに対応させて説明する。聞き手が次の内容を理解できることを目標とする。

1. モデルは指示と生成済みのトークンを読み、次の1トークンの候補を計算する。
2. 選んだトークンを入力列へ追加して同じ処理を繰り返すことが自己回帰生成である。
3. 温度は候補のロジットをTで割り、softmaxへ渡すことで選択確率を変える。
4. greedyによる最大候補の選択と、確率に従うサンプリングは異なる。

既存のloss・attentionの説明を保ち、その前に「実際に何を繰り返してコードを生成するのか」を補う。

## 2. 対象資料と追加位置

- 対象PPTX: [boku1_nano_presentation_loss_attention_marp.pptx](../report/boku1_nano_presentation_loss_attention_marp.pptx)
- 対応する原稿: [boku1_nano_presentation_loss_attention_marp.md](../report/boku1_nano_presentation_loss_attention_marp.md)
- 追加位置: 現在の12枚目「三つの大きさを、1 epochで比較する」の後。
- 追加枚数: 本編2枚。「自己回帰によるコード生成」「温度と次トークンの選択」を予定。

既存の配色、余白、文字サイズを基準にする。コードが小さくなりすぎる場合は抜粋を短くし、補足を発表者ノートへ移す。スライド数を増やすより、1枚につき一つの説明に絞る。

PPTXとMarkdownには編集順などの差がある可能性があるため、更新開始時に対応を確認する。原稿から再出力する場合も、指定PPTXの既存34枚を維持できていることを比較する。別名の旧原稿を誤って編集しない。

## 3. 実装上の事実

| 実装 | 生成方式 | 説明に使用する部分 |
| --- | --- | --- |
| [evaluate_boku_nano.py](../../scripts/model/evaluate_boku_nano.py) | greedy | 最後の位置のlogits、argmax、EOS、系列追加 |
| [web/demo.js](../../web/demo.js) | greedy | ONNX実行、argmax、配列追加、途中表示 |
| [evaluate_boku_nano_comparison.py](../../scripts/model/evaluate_boku_nano_comparison.py) | 温度とtop-pを使うsampling | 温度除算、softmax、候補制限、multinomial |
| [boku_nano.py](../../scripts/model/boku_nano.py) | モデル本体 | 語彙ごとのlogits、因果的attention |

確認時点で、通常評価の主な処理は484行付近、Web生成は341行付近、samplingは207行付近にある。行番号は改修で変わるため、資料へ掲載する際は関数と内容を再確認する。

現在のWeb版は温度を使う生成ではない。別の比較評価スクリプトに温度samplingが存在する。この区別をスライドか発表者ノートに明記する。

## 4. 1枚目「自己回帰によるコード生成」

### 伝える順番

1. 日本語指示をtokenizerでID列へ変換する。
2. 入力列をモデルに渡す。
3. 最後の位置の出力から、次のトークン候補のlogitsを取り出す。
4. 次のトークンを一つ選ぶ。
5. EOSなら終了し、それ以外は生成済み列と次回の入力へ加える。
6. 同じ処理をEOSまたは長さ上限まで繰り返す。

「1トークンは1文字や1単語とは限らない」ことも一言補足する。実演のトークン境界は実際のBPE出力から取得し、`def`や`solve`が必ず独立tokenになるような図は作らない。

### 掲載する実コードの候補

Web側は実際に動くループが短いため、次の部分を抜粋候補とする。前後のTensor作成や状態表示はノートへ回す。

```javascript
const outputs = await runtime.session.run({ input_ids: input });
const tokenId = argmax(outputs.logits.data);
if (tokenId === state.manifest.special_token_ids.eos) break;
generatedIds.push(tokenId);
currentIds.push(tokenId);
elements.output.textContent = tokenizer.decode(generatedIds);
```

このコードは`web/demo.js`の生成ループ内の抜粋であり、単独で動くプログラムではない。入力の`input`は各周回で`currentIds`から作り直される点を説明する。

Python側との対応もノートに載せる。

```python
next_logits = model(input_ids).logits[:, -1, :]
next_ids = torch.argmax(next_logits, dim=-1)
```

`[:, -1, :]`は「各入力について最後の位置にある、語彙全体の候補」を表す。選んだIDを次の入力へ加える処理は同じ関数の`torch.cat`に対応する。バッチ内の終了済み系列にはpaddingを入れるが、本編では一つの系列に絞って説明する。

### 図または表示例

同じ実行記録から、生成開始時、1トークン追加後、数トークン追加後の3時点を表示する。毎回「日本語指示＋生成済みコード」が次の入力になることを示す。

コードの表示単位とモデルが選んだtoken IDを対応させる。説明のために表示を省略する場合は省略記号を付け、実際のtoken列を組み替えない。

## 5. 2枚目「温度と次トークンの選択」

### 基本式

候補iのlogitをz_i、温度をTとすると、T > 0で選択確率を次のように計算する。

```text
p_i = exp(z_i / T) / Σ_j exp(z_j / T)
```

計算順序は「各候補のlogitをTで割る」「softmaxで合計1の確率へ変える」「確率に従って1候補を選ぶ」とする。logit自体を確率と説明しない。

### 既存コードを根拠にする

既存の`sample_generate_equal_length`には、以下の処理がある。

```python
logits = model(input_ids).logits[:, -1, :] / temperature
sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
sorted_probabilities = torch.softmax(sorted_logits, dim=-1)
```

この後にtop-pによる候補制限と再正規化があり、次の処理で候補位置を抽選する。

```python
sampled_positions = torch.multinomial(
    sorted_probabilities,
    num_samples=1,
    generator=generator,
)
```

上記2つは既存実装の離れた箇所からの抜粋である。間に処理があることを省略表示や注釈で示す。抽選した位置を`sorted_indices`で元の語彙IDへ戻す処理はノートで補足する。

### 温度だけを見る最小例

以下は説明用に簡略化した例で、既存実装の全文や未変更の引用ではない。本編に用いる場合は「説明用の簡略例」と明記する。

```python
if temperature == 0:
    next_id = logits.argmax(dim=-1, keepdim=True)
else:
    probabilities = torch.softmax(logits / temperature, dim=-1)
    next_id = torch.multinomial(probabilities, num_samples=1)
```

この例は事前にtemperatureが有限かつ0以上であることを検査する想定である。T=0では割り算せず、greedyへ分岐する。実際のsampling関数へT=0をそのまま渡してよい、という説明にはしない。

## 6. 温度の数値例

説明用に3候補のlogitsを`[2, 1, 0]`と仮定し、温度だけを変える。以下はモデルから測定した値ではなく、数式から求めた例である。

| 温度T | 候補A | 候補B | 候補C | 見せる変化 |
| --- | ---: | ---: | ---: | --- |
| 0.5 | 約86.7% | 約11.7% | 約1.6% | 最大候補へ集中 |
| 1.0 | 約66.5% | 約24.5% | 約9.0% | 元のlogitsのsoftmax |
| 2.0 | 約50.6% | 約30.7% | 約18.6% | 確率が平らになる |

丸めのため、表の合計が100.0%と一致しない場合がある。正のTを変えても候補の順位は変わらない。greedyで常に最大候補を取るなら、この例はどのTでも候補Aになる。

高い温度は多様性を増やしうるが、正確さを保証するものではない。コード生成の正解率が上がるという主張には使わない。

### 数値計算上の補足

手計算や独自のsoftmax実装を説明する場合は、最大値を引いてから指数を計算すると数値が大きくなりすぎるのを抑えられることをノートへ置く。

```text
u_i = z_i / T
m = max_j u_j
p_i = exp(u_i - m) / Σ_j exp(u_j - m)
```

本編ではTによる除算とsoftmaxを優先し、数値安定化の詳細で説明を中断しない。

## 7. top-p、attention、学習との区別

### top-p

温度は確率の集中度を変える。top-pは確率の高い順に候補を残す範囲を決める。既存実装は温度を適用した確率に対してtop-pを処理し、残った確率を再正規化してから抽選する。

温度の比較例ではtop-p=1相当として候補制限を無効にする。Tとtop-pを同時に変えて、変化を温度だけの効果として説明しない。

### attention

生成時の温度は出力語彙のlogitsへ適用する。attention内部のスコア計算や次元によるスケーリングとは別である。既存のattention可視化スライドは「どこから情報を読むか」、今回の温度説明は「出力候補からどれを選ぶか」としてつなぐ。

### 学習と推論

自己回帰の説明は生成時のループについて行う。学習時には正解の前のtokenを入力し、因果マスクによって未来を見ない条件で複数位置の損失をまとめて計算できる。生成時の逐次処理と学習時の計算を混同しない。

現在のBoku1-nanoにはKV cacheがなく、各生成stepで現在の系列全体を再計算する。これは現実装の特徴であり、自己回帰モデルが一般に毎回全系列を再計算する必要がある、とは説明しない。

## 8. 実演の方針

本編2枚の説明は、Web UIへの温度機能追加を前提にしない。以下の記録を説明用に用意する。

1. 15M・1 epoch・既存BPEを明示して一つの入力を選ぶ。
2. モデルを評価モードにし、勾配計算を無効にしてgreedy生成する。
3. 各stepの入力長、選んだtoken ID、復号結果、終了理由を保存する。
4. 温度の説明用に、固定した同じlogitsの確率を複数のTで計算する。
5. 実際のsampling例を見せる場合は、温度以外の設定と乱数seedを記録する。

生成列が一度分岐すると次のlogitsも変わる。そのため、温度の直接効果は同じstepの同じlogitsで比較し、全文の違いは別の実演として扱う。

将来Webへ温度設定を付ける場合は「学習用モード」として別途実装する。100問比較の主評価はgreedyのまま固定し、利用者が画面で変更した温度によって評価条件が変わらないようにする。

## 9. 成果物と作業順

成果物:

- 既存の発表資料へ追加する2枚。
- 出典ファイル名・関数名・説明上の省略を記した発表者ノート。
- tokenごとの生成記録と、温度の確率表を再計算できる説明用データ。
- 必要に応じて実演用の短いスクリプト。保存先候補は`scripts/report/`、記録先候補は`docs/report/`配下とする。

作業順:

1. 指定PPTXと対応原稿の内容・順序を確認する。
2. 掲載する実コードの抜粋と出典を確定する。
3. 実モデルで自己回帰の記録を取得する。
4. 温度の数値例を再計算し、必要な実演記録を保存する。
5. 既存デザインに合わせて2枚を追加する。
6. コードの読みやすさ、文字切れ、図との対応を出力後に確認する。
7. 資料中のページ番号や参照番号を更新し、既存結果の数値が変わっていないことを確認する。

## 10. 検証項目

- logitsの取り出しが「最後の位置・語彙全体」になっている。
- 選択したtokenが次の入力へ追加されることを示している。
- EOSと長さ上限による終了を区別している。
- token境界と復号表示が実際のtokenizerに基づいている。
- 温度はsoftmaxの前に適用している。
- 確率の総和、数値例の丸め、低温・高温の傾向を確認している。
- T=0で除算せず、負値や非有限値の扱いが明確になっている。
- samplingの乱数とtop-pの条件が記録されている。
- 既存コードの抜粋と説明用の簡略例を区別している。
- 現在のWebがgreedyであることと矛盾していない。

## 11. 完了条件

- [ ] 実際のコードを指しながら、次tokenの計算・選択・追加・反復を説明できる。
- [ ] 「logitsをTで割る→softmax→抽選」の順序がコードと一致する。
- [ ] greedyとsamplingの違い、T=0の扱いが明確。
- [ ] 温度の表が再計算でき、仮定した例であると明示されている。
- [ ] top-pとattentionの役割を温度と混同していない。
- [ ] 既存の実験結果を変えず、2枚の追加で説明が成立する。
- [ ] 出力した資料のコードが発表時に読めるサイズで表示される。
- [ ] 発表者ノートから出典と実演条件を追跡できる。

## 12. 関連する作成方針

- [100問ベンチマーク作成方針](boku_nano_benchmark_100_plan.md)
- [チャットUI刷新方針](boku_nano_chat_ui_plan.md)
