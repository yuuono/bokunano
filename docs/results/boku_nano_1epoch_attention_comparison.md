# Boku Nano 1epochモデルのattention可視化・因果評価（学習時準拠文型）

## 結論

1M・5M・15Mの各1epochモデルについて、既存BPE（`min_frequency=5`、`max_token_length=24`）と短いpiece用BPE（`min_frequency=2`、`max_token_length=8`）の計6構成を同じ方法で解析した。各モデルで24種類の単独操作を、学習時の1操作文と同じ「整数リストxsから」または「整数リストxsと整数kを受け取り、」へ埋め込んでgreedy生成し、attentionの役割候補、BOSへの集中、Valueノルム、attention rollout、head単位とtoken位置単位の因果的ablationを評価した。

| モデル | パラメータ数 | 層×head | 診断合格 | 教師強制NLL | 日本語Value=0 | BOS Value=0 |
|---|---:|---:|---:|---:|---:|---:|
| 1M・既存BPE | 1,016,704 | 3×4 | 3 / 24 | 1.1743 | 0 / 24 | 5 / 24 |
| 1M・短いpiece | 1,016,704 | 3×4 | 1 / 24 | 0.4210 | 0 / 24 | 0 / 24 |
| 5M・既存BPE | 5,065,472 | 5×4 | 22 / 24 | 0.4760 | 0 / 24 | 7 / 24 |
| 5M・短いpiece | 5,065,472 | 5×4 | 23 / 24 | 0.1219 | 0 / 24 | 2 / 24 |
| 15M・既存BPE | 15,735,168 | 8×6 | 22 / 24 | 0.4321 | 2 / 24 | 18 / 24 |
| 15M・短いpiece | 15,735,168 | 8×6 | 24 / 24 | 0.1117 | 0 / 24 | 5 / 24 |

主な観察は次のとおりである。

- 学習時準拠文型では、5M既存BPEが22件、5M短いpiece版が23件、15M既存BPEが22件、15M短いpiece版が24件すべてに合格した。1Mは既存BPEで3件、短いpiece版で1件だった。
- 旧「整数リストxsに対して、」文型からの変化は、1M既存BPE `1→3`、1M短いpiece `0→1`、5M既存BPE `1→22`、5M短いpiece `10→23`、15M既存BPE `21→22`、15M短いpiece `24→24`だった。特に5Mでは文型が診断合格数を大きく左右した。
- 日本語指示位置のValueを全層で0にすると、5M既存BPEは22件から0件、5M短いpiece版は23件から0件、15M既存BPEは22件から2件、15M短いpiece版は24件から0件へ低下した。診断性能がある4構成で、日本語指示のValueが操作選択に必要であることを強く支持する。
- BOS Valueを消すと、5M既存BPEは22件から7件、5M短いpiece版は23件から2件、15M既存BPEは22件から18件、15M短いpiece版は24件から5件へ変化した。BOSへのattentionは単なる無意味なsinkとはいえず、影響の大きさはモデルとトークナイザーで異なる。
- 全head内で「日本語指示へのattention」とhead無効化時のNLL増加を比べると、Spearman相関は6構成すべて正で、0.371〜0.874だった。ただし、attention値だけで個々の出力の因果的重要度を断定はできない。

## 結果の種類ごとに6モデルの図を見る

次の各Markdownでは、SVGへの単独リンクではなく、6モデルの図を本文へ直接表示する。

| 結果の種類 | 一覧ページ |
|---|---|
| head別の記述的役割 | [6モデルの図を表示](attention_1epoch_by_result/attention_head_roles.md) |
| BOS sinkとValueノルム | [6モデルの図を表示](attention_1epoch_by_result/attention_sink_contribution.md) |
| 因果的ablation | [6モデルの図を表示](attention_1epoch_by_result/attention_causal_ablation.md) |
| attention rollout | [6モデルの図を表示](attention_1epoch_by_result/attention_rollout.md) |
| 生成step×参照token位置 | [6モデルの図を表示](attention_1epoch_by_result/attention_by_layer_head.md) |
| 領域別attention | [6モデルの図を表示](attention_1epoch_by_result/attention_regions.md) |
| K/Vのコサイン類似度 | [6モデルの図を表示](attention_1epoch_by_result/kv_cosine_similarity.md) |
| token利用状況 | [6モデルの図を表示](attention_1epoch_by_result/token_utilization.md) |

説明を含む入口は[結果種類別一覧](attention_1epoch_by_result/README.md)にまとめた。

## 新旧文型の比較

| モデル | 旧「に対して」文型 | 学習時準拠文型 | 差 |
|---|---:|---:|---:|
| 1M・既存BPE | 1 / 24 | 3 / 24 | +2 |
| 1M・短いpiece | 0 / 24 | 1 / 24 | +1 |
| 5M・既存BPE | 1 / 24 | 22 / 24 | +21 |
| 5M・短いpiece | 10 / 24 | 23 / 24 | +13 |
| 15M・既存BPE | 21 / 24 | 22 / 24 | +1 |
| 15M・短いpiece | 24 / 24 | 24 / 24 | 0 |

旧診断では、24操作すべてを「整数リストxsに対して、{操作}solve関数を書いてください。」へ埋め込んでいた。この24文は訓練指示との完全一致が0件で、訓練中の「整数リストxsに対して、」で始まる84件は2操作1件・3操作83件だった。5Mで大幅に改善したことから、旧結果にはこの文型と複数操作の学習上の結び付きが強く影響していたと考えられる。旧結果と図は[旧「に対して」文型の報告書](boku_nano_1epoch_attention_comparison_legacy_taishite_prompt.md)へ分離した。

### 診断基準で残った不合格

| モデル | 合格または不合格操作 | 内容 |
|---|---|---|
| 1M・既存BPE | 合格は`k以下`、`kの倍数`、`先頭k個`の3操作 | 残る21操作では未定義変数、構文不正、意味不一致が発生 |
| 1M・短いpiece | 合格は`k以下`の1操作 | 残る23操作では未定義変数、timeout、意味不一致が発生 |
| 5M・既存BPE | 不合格は`2倍`、`符号反転` | `2倍`を3倍として生成し、`符号反転`は値を変更しなかった |
| 5M・短いpiece | 不合格は`正の値` | `result`を定義しないコードを生成し、静的検査で不合格 |
| 15M・既存BPE | 不合格は`符号反転`、`絶対値` | `符号反転`は未初期化変数、`絶対値`は二乗を生成 |
| 15M・短いpiece | 不合格なし | 24操作すべてで33 / 33入力に合格 |

各指示、生成コード、最初の不一致入力はモデル別の`analysis.json`に保存している。

## 評価条件

| 項目 | 条件 |
|---|---|
| 対象 | 1M・5M・15M、各1epoch、2トークナイザー、計6モデル |
| prompt | kなしは「整数リストxsから」、kありは「整数リストxsと整数kを受け取り、」に24単独操作を埋め込んだ固定診断 |
| テンプレートID | `single-operation-training-aligned-v1` |
| decoding | greedy、最大64 token |
| 機能判定 | 各promptにつき固定33ケース。構文、安全AST、signature、出力値を検証 |
| head役割 | BOS、日本語指示、制御token、生成済みコード、直前token、直近4 token、copy-like、induction-like、entropy |
| head ablation | attention出力の対象headを`out_proj`直前で0化 |
| 位置ablation | 対象位置のKとattention weightは保ち、全層でValueだけを0化 |
| 因果指標 | 教師強制NLL差、KL divergence、argmax変化率、再生成後の機能合格数 |
| 乱数seed | 20260930 |

24操作の因果評価は[attention解釈性解析スクリプト](../../scripts/model/analyze_boku_nano_attention_interpretability.py)、単一promptの復元検証は[Query・attention解析スクリプト](../../scripts/model/analyze_boku_nano_attention.py)にある。解析JSONにはテンプレートID、kあり・なしの全文テンプレート、kを使う10操作IDも保存した。1Mの3層×4head、5Mの5層×4head、15Mの8層×6headを同じコードで処理した。

この24操作診断は、既存報告書の固定84,550件評価とは別物である。固定評価は主に2・3操作を含むが、この診断はheadの比較を目的に単独操作だけを学習時準拠の外側文へ埋め込んで問う。したがって、ここでの合格数を通常評価の合格率として扱わない。

## 診断生成とattentionの全head平均

| モデル | 平均prompt token | 平均生成token | 日本語指示attention | BOS attention | 生成済みコードattention | 直近4 token | entropy |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1M・既存BPE | 11.17 | 13.88 | 26.39% | 5.50% | 40.20% | 27.96% | 0.9757 |
| 1M・短いpiece | 23.46 | 39.12 | 40.59% | 2.37% | 46.09% | 12.94% | 0.9790 |
| 5M・既存BPE | 11.17 | 8.71 | 26.97% | 7.87% | 33.75% | 34.23% | 0.9436 |
| 5M・短いpiece | 23.46 | 31.33 | 41.91% | 3.07% | 42.33% | 14.70% | 0.9628 |
| 15M・既存BPE | 11.17 | 8.92 | 29.08% | 8.67% | 30.71% | 30.22% | 0.9197 |
| 15M・短いpiece | 23.46 | 31.25 | 41.12% | 3.19% | 41.89% | 14.17% | 0.9531 |

attentionは24操作の生成位置を集計し、全層・全headで平均した。短いpiece版は日本語指示がより多くのtokenに分割されるため、日本語領域のattention総量が高く、BOS 1 tokenの比率が低くなりやすい。領域内のtoken数が異なるので、この表だけからトークナイザーの優劣や日本語理解の強さを結論づけない。entropyは参照可能token数で正規化した0〜1の値で、大きいほどattentionが平坦である。

また、教師強制NLLはtoken単位であり、分割単位が異なる2トークナイザー間では直接比較しない。同じモデル内のablation前後差に使う。

## 日本語指示を参照するhead

| モデル | 日本語attention最大head | attention | NLL影響最大head | ΔNLL | argmax変化率 | 日本語attentionとΔNLLの相関（Pearson / Spearman） |
|---|---|---:|---|---:|---:|---:|
| 1M・既存BPE | L1H2 | 29.09% | L1H3 | +0.0881 | 14.41% | 0.448 / 0.371 |
| 1M・短いpiece | L1H2 | 42.74% | L1H2 | +0.2027 | 12.78% | 0.767 / 0.874 |
| 5M・既存BPE | L2H3 | 38.77% | L1H2 | +0.5550 | 23.44% | 0.602 / 0.690 |
| 5M・短いpiece | L3H1 | 50.57% | L1H1 | +0.0660 | 4.92% | 0.544 / 0.617 |
| 15M・既存BPE | L3H5 | 61.43% | L1H5 | +0.1386 | 13.08% | 0.247 / 0.498 |
| 15M・短いpiece | L3H4 | 62.79% | L3H4 | +0.0185 | 1.47% | 0.332 / 0.541 |

1M短いpieceと15M短いpieceでは、日本語attention最大headとNLL影響最大headが一致した。その他の4構成では一致しないため、「日本語を強く見るhead」が常に最重要headとは限らない。相関はhead集合全体の傾向であり、個別headの因果性はablationで判断する。

## 因果的ablation

### Value位置の除去

| モデル | 診断基準 | BOS Value=0 | 基準と同じコード | 日本語Value=0 | 基準と同じコード |
|---|---:|---:|---:|---:|---:|
| 1M・既存BPE | 3 / 24 | 5 / 24 | 1 / 24 | 0 / 24 | 0 / 24 |
| 1M・短いpiece | 1 / 24 | 0 / 24 | 0 / 24 | 0 / 24 | 0 / 24 |
| 5M・既存BPE | 22 / 24 | 7 / 24 | 3 / 24 | 0 / 24 | 0 / 24 |
| 5M・短いpiece | 23 / 24 | 2 / 24 | 1 / 24 | 0 / 24 | 0 / 24 |
| 15M・既存BPE | 22 / 24 | 18 / 24 | 3 / 24 | 2 / 24 | 0 / 24 |
| 15M・短いpiece | 24 / 24 | 5 / 24 | 0 / 24 | 0 / 24 | 0 / 24 |

日本語Value=0は日本語token自体を削除する実験ではない。日本語位置のKeyは残るため、attention weightは維持される一方、そこから取り出すValueだけが0になる。この条件で診断性能がある4構成のうち3構成が0件、15M既存BPEも2件まで落ちたことは、日本語指示へのattentionが見かけだけではなく、Value経由で操作選択へ寄与していることを示す。

BOS Valueの影響はモデルにより異なる。生attentionと`attention × projected Value norm`も同一ではないため、BOS attentionが大きいことだけを根拠にsinkまたは不要tokenとは判断しない。

### NLL影響最大headの除去

| モデル | 対象head | ΔNLL | 診断基準 | 無効化後合格 | 同じコード |
|---|---|---:|---:|---:|---:|
| 1M・既存BPE | L1H3 | +0.0881 | 3 / 24 | 0 / 24 | 2 / 24 |
| 1M・短いpiece | L1H2 | +0.2027 | 1 / 24 | 0 / 24 | 0 / 24 |
| 5M・既存BPE | L1H2 | +0.5550 | 22 / 24 | 3 / 24 | 0 / 24 |
| 5M・短いpiece | L1H1 | +0.0660 | 23 / 24 | 16 / 24 | 3 / 24 |
| 15M・既存BPE | L1H5 | +0.1386 | 22 / 24 | 11 / 24 | 7 / 24 |
| 15M・短いpiece | L3H4 | +0.0185 | 24 / 24 | 22 / 24 | 15 / 24 |

NLL影響最大headは、5M既存BPEで19件、5M短いpiece版で7件、15M既存BPEで11件、15M短いpiece版で2件の機能合格を失わせた。文型を学習時準拠にしたことで5Mにも十分な診断性能が得られ、head無効化の機能差を解釈できるようになった。教師強制NLL、token列一致、機能的正しさは別の指標として読む必要がある。

低NLL影響headでも生成tokenが完全に不変とは限らない。たとえば15M短いpiece版のL7H2はΔNLLが-0.000063で、24件中23件が同じコード、全24件が機能合格だった。これは単独の診断では低影響だったことを示すだけで、複数headの同時削除や未知promptに対する安全なpruningを保証しない。

## 単一promptでのattention復元検証

既存の可視化例と同じ「xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。」を使い、生成stepごとの最後のQueryと全Keyから `softmax(QK^T / sqrt(head_dim))` を再計算した。復元した `attention @ V` を、モデル本体のfused attentionが `out_proj` へ渡す直前の出力と比較した。

| モデル | prompt token | 生成token | 行和範囲 | 最大絶対誤差 | 最小cos類似度 |
|---|---:|---:|---:|---:|---:|
| 1M・既存BPE | 16 | 13 | 0.99999982〜1.00000012 | 1.2 × 10^-7 | 0.99999988 |
| 1M・短いpiece | 24 | 45 | 0.99999988〜1.00000024 | 2.4 × 10^-7 | 0.99999982 |
| 5M・既存BPE | 16 | 14 | 0.99999982〜1.00000024 | 1.8 × 10^-7 | 0.99999988 |
| 5M・短いpiece | 24 | 31 | 0.99999976〜1.00000024 | 3.0 × 10^-7 | 0.99999976 |
| 15M・既存BPE | 16 | 16 | 0.99999976〜1.00000024 | 8.6 × 10^-7 | 0.99999982 |
| 15M・短いpiece | 24 | 33 | 0.99999976〜1.00000024 | 3.6 × 10^-7 | 0.99999982 |

全構成で行和が1と整合し、さらにfused attention出力もfloat32の丸め誤差程度で再現した。したがって、保存したheatmapは少なくともこのCPU推論でモデル本体のattention計算と数値的に一致している。

### 単一promptの生成結果

生成コードは、24操作診断と同じ33ケースおよび「絶対値化→降順化」の意味ASTで機能判定した。

| モデル | 判定 | 主な失敗理由 |
|---|---|---|
| 1M・既存BPE | 不合格 | 代入前の `result` を参照し、実行時例外 |
| 1M・短いpiece | 不合格 | 反復中のlistへ追加し続け、timeout |
| 5M・既存BPE | 不合格 | `abs(value + k)` となり、要求と意味不一致 |
| 5M・短いpiece | 不合格 | 絶対値・降順ではなく二乗を生成 |
| 15M・既存BPE | **合格** | 33 / 33ケースで期待値と一致 |
| 15M・短いpiece | 不合格 | `value * 3result` を生成し、構文不正 |

15M短いpiece版は学習時準拠の24操作診断では24 / 24だったが、この2操作表現では構文不正になった。モデル規模だけでなく、指示表現とトークナイザーによって生成が変わるため、1 promptのheatmapをモデル全体の能力説明には使わない。

### 領域attentionとK/V類似度

| モデル | 日本語指示attention | 一様分布比 | Key最大非対角cos | Value最大非対角cos |
|---|---:|---:|---:|---:|
| 1M・既存BPE | 43.40% | 0.926倍 | 0.8672 | 0.9989 |
| 1M・短いpiece | 39.77% | 0.916倍 | 0.8287 | 0.9996 |
| 5M・既存BPE | 36.32% | 0.772倍 | 0.8028 | 0.9984 |
| 5M・短いpiece | 42.28% | 0.846倍 | 0.8328 | 0.9992 |
| 15M・既存BPE | 32.58% | 0.719倍 | 0.8216 | 0.9977 |
| 15M・短いpiece | 47.55% | 0.988倍 | 0.8152 | 0.9977 |

一様分布比は、指示領域のtoken数と各生成stepの参照可能token数を補正した値である。全構成で1未満だったため、この1 promptでは日本語指示領域への総attentionはtoken数比例の一様分布より弱い。Value最大非対角cosはすべて0.997以上だが、高類似の位置は改行や反復するコード断片を含む。類似度が高いこと自体はtokenの重要度を意味しない。

詳細値と図は次のとおりである。

| モデル | step×token | 領域比率 | K/V類似度 | token利用 | 全数値JSON |
|---|---|---|---|---|---|
| 1M・既存BPE | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_by_layer_head.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_regions.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/kv_cosine_similarity.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/token_utilization.svg) | [JSON](attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/detail_analysis.json) |
| 1M・短いpiece | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_by_layer_head.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_regions.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/kv_cosine_similarity.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/token_utilization.svg) | [JSON](attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/detail_analysis.json) |
| 5M・既存BPE | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_by_layer_head.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_regions.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/kv_cosine_similarity.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/token_utilization.svg) | [JSON](attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/detail_analysis.json) |
| 5M・短いpiece | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_by_layer_head.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_regions.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/kv_cosine_similarity.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/token_utilization.svg) | [JSON](attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/detail_analysis.json) |
| 15M・既存BPE | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_by_layer_head.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_regions.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/kv_cosine_similarity.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/token_utilization.svg) | [JSON](attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/detail_analysis.json) |
| 15M・短いpiece | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_by_layer_head.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_regions.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/kv_cosine_similarity.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/token_utilization.svg) | [JSON](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/detail_analysis.json) |

## モデル別の可視化と生データ

各モデルに4種類のSVGを保存した。head役割図は生attentionの記述的パターン、sink図はBOSの生attentionとprojected Valueノルム構成比、ablation図はNLL差と機能合格率、rollout図は層をまたぐ参照経路を表す。rolloutは因果的重要度ではなく、残差込みの経路可視化である。

| モデル | head役割 | BOS sink | 因果的ablation | rollout | 全数値JSON |
|---|---|---|---|---|---|
| 1M・既存BPE | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_head_roles.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_sink_contribution.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_causal_ablation.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_rollout.svg) | [JSON](attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/analysis.json) |
| 1M・短いpiece | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_head_roles.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_sink_contribution.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_causal_ablation.svg) | [SVG](attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_rollout.svg) | [JSON](attention_1epoch/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch/analysis.json) |
| 5M・既存BPE | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_head_roles.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_sink_contribution.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_causal_ablation.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_rollout.svg) | [JSON](attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/analysis.json) |
| 5M・短いpiece | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_head_roles.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_sink_contribution.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_causal_ablation.svg) | [SVG](attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_rollout.svg) | [JSON](attention_1epoch/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch/analysis.json) |
| 15M・既存BPE | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_head_roles.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_sink_contribution.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_causal_ablation.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_rollout.svg) | [JSON](attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/analysis.json) |
| 15M・短いpiece | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_head_roles.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_sink_contribution.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_causal_ablation.svg) | [SVG](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_rollout.svg) | [JSON](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/analysis.json) |

### 15M・短いpiece版の代表図

![15M短いpiece版のhead別attention役割](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_head_roles.svg)

![15M短いpiece版の因果的ablation](attention_1epoch/boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch/figures/attention_causal_ablation.svg)

## 解釈上の注意

- attention weightは参照の観測値であり、出力根拠そのものではない。
- `attention × projected Value norm`は各加算項の大きさであり、ベクトル相殺、残差、FFN、後続層を完全には表さない。
- head ablationは1 headずつの局所実験であり、複数headを同時に削除した場合の相互作用は測っていない。
- Value位置ablationはKを残すため、token削除やattention maskとは異なる。
- 24操作は限定自然言語SLMの内部比較用診断であり、一般的な言語理解や説明可能性を示す評価ではない。
