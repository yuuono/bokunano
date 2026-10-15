# Boku-nanoへのLooped Transformer導入方針：1M未満への小型化

調査日: 2026-10-15。コード確認時のHEAD: `bf6db12`。未コミットの既存文書・評価結果も参照した。

**モデルと訓練スクリプトを実装済み。** 固定反復、入力再注入、embedding共有、保存・復元、比較設定生成、ONNX書き出しに対応した。互換性等の22テストと実データ2更新のCPU学習を確認済み。3epochの小型モデルの生成性能評価は未実施である。[実行手順](../procedures/boku_nano_looped_training.md)を参照。周回別のattention解析、因子分解embedding、可変反復、KV cacheは後段の課題として残す。

## 1. 採用する方針

**比較起点を、すでに学習済みの1,016,704パラメータ・3層・3epochモデルに置く。目標は、その実行能力を維持する最小構成を探すこと。** 主候補は幅128・FFN256の**1物理層×3周＋入力/出力embedding共有、426,368パラメータ（約0.426M）**とする。1Mから約58.1%小さく、幅と層適用回数は既存1Mと同じである。

変更の効果を切り分けるため、embedding非共有の**1層×3周・688,512パラメータ**を先に比較する。さらに幅96の**289,056**、幅64の**172,224**まで段階的に縮める。通常1層や通常2層だけで目的を満たす可能性も評価する。loop版が同容量の通常1層に勝たなければ、単純な通常1層を選ぶ。

「1層×3周」は、同一のTransformer blockを3回適用する意味である。新しい独立層を3個作らない。2物理層を使う候補では、層群の順序を保って反復する。

```text
既存1M:   embedding → B0 → B1 → B2 → norm → head
1層×3周:  embedding → B0 → B0 → B0 → norm → head
                     1周目 2周目 3周目
                      └─ 同じ重み ─┘
主候補では、embeddingとheadも同じパラメータを参照する。
```

初版の決定は次のとおり。

| 項目 | 決定 | 決定した理由 |
| --- | --- | --- |
| 共有範囲 | block全体を周回間で共有。異なる物理block間は非共有 | 容量削減を明確にし、attentionだけ共有する等の別要因を避ける |
| ループの入力 | 前の周回の出力をそのまま次へ渡す | 現行コードの変更が小さく、共有・反復の効果を切り分けやすい。単純反復の先例は文献[2][3] |
| 入力の再注入 | `add`方式を必須の比較条件として用意する。初期既定は`none` | Looped GPT-BERTとの重要な差を明示し、再注入が必要かをbokunanoで判定する |
| 反復回数 | モデルごとに固定。主候補は3周、必要時に2・6周を比較 | 既存3層との主要な演算数を揃え、ONNX推論の構造も固定する |
| 学習 | **全候補3epoch**、ランダム初期化、全周回を逆伝播、最終周回のcode＋EOS loss | 成功済みの1M・3epochと同じデータ提示量で比較する |
| embedding/head | 非共有対照と共有候補を両方学習。主候補は共有 | 1Mでは入力/出力行列だけで524,288パラメータを使うため |
| 維持する構造 | causal mask、RoPE、pre-norm RMSNorm、SwiGLU、語彙2048・context256 | 語彙変更による系列長変化を小型化実験へ混ぜない |
| 後段へ回す機能 | 可変回数学習、適応停止、周回ID embedding、補助loss、KV cache | それぞれ独立した効果・実装上の検証を必要とする |

これは**未学習の候補構成**であり、0.426Mや0.172Mで既存能力を達成済みという意味ではない。まず0.689Mでloopだけの効果、0.426Mでembedding共有との組み合わせを調べる。0.289M・0.172Mは能力維持の下限を探す候補とする。

## 2. 文献から何を採用し、何をそのまま移さないか

### 2.1 指定されたLooped GPT-BERTの位置づけ

Fan et al. (2026)の[Looped GPT-BERT](https://arxiv.org/html/2609.09691v1)は、4物理層×12周、計48回の層適用、12.18Mパラメータのモデルを報告している。29.9Mは同論文内の非ループ12層対照であり、公開GPT-BERT基準の31Mとは別である。§3.3では、毎周回に固定入力を加える再帰とDWAを使用する。学習目的はMNTPとcausal LMの混合である。

採用上重要なのは、**少ない重みで一部の能力を維持できる可能性と、追加計算の限界の両方**である。Table 8の1:3条件では、BLiMPは通常モデル70.54に対し4×3で71.21。一方、Entity Trackingは4×6の28.66から4×12の15.78へ低下する。単一seedかつ4×12は計算量を揃えた比較ではない。したがって「12周が最適」「重み削減だけで高速化」「状態保持も改善」とは解釈しない。出典: [§3.3、§4.4、Limitations](https://arxiv.org/html/2609.09691v1)。

今回のタスクは日本語指示からPythonを生成する条件付きcausal LMである。英語の一般事前学習の設定値を移植するより、既存のloss・tokenizer・optimizerを固定して共有構造を比較する。DWAやMNTPを導入しない以上、成果物は「Looped GPT-BERTの再現」ではなく「文献を参考にしたBoku-nanoのlooped decoder」と呼ぶ。

### 2.2 関連研究と実装判断の対応

| 文献 | 一次資料から確認した点 | 今回への適用と限界 |
| --- | --- | --- |
| [2. Saunshi et al., 2025](https://arxiv.org/html/2502.17416v1) | 単純な層群の反復を、同パラメータ・同実効深さの通常モデルと比較。言語モデルでは推論課題とperplexity・記憶の傾向が異なる（§2–3） | 対照モデルを2種類置く。lossだけで採用しない。理論上のCoT模倣を、bokunanoの各周回が特定の操作を実行する証拠とは扱わない |
| [3. Kohli et al., 2026](https://arxiv.org/html/2604.07822v2) | 入力再注入なしのdecoder層群反復を使用（§4）。過剰反復による性能低下も報告（§6.3） | 単純反復を初版にする直接の先例。ただし合成知識グラフの回答token予測であり、長いコード生成への効果は未確認 |
| [4. Yang et al., ICLR 2024](https://arxiv.org/html/2311.12424) | 入力再注入と反復末尾の学習窓を用いる。再注入なしで学習時以上の反復が不安定になる実験がある（§4–4.1） | `add`比較を置く理由。主対象は回帰等のin-context learningなので、短い固定ループにも必須とは断定しない |
| [5. Geiping et al., 2025](https://arxiv.org/html/2502.05171) | prelude/core/coda、入力再注入、反復数のランダム化、最後の8反復の逆伝播を組み合わせる。step条件付けは外挿に悪影響の報告（§3） | 大規模・多数反復向けの発展案。少反復の初版はfull BPTTとし、周回embeddingを追加しない |
| [6. Dehghani et al., ICLR 2019](https://arxiv.org/html/1807.03819) | 深さ方向の共有に位置・反復時刻の信号を組み合わせ、tokenごとの適応停止も検討（§2） | 共有と適応停止は分けて実装できる。ACTまで一度に導入する根拠にはしない |
| [7. Lan et al., ICLR 2020](https://arxiv.org/html/1909.11942) | cross-layer sharingで容量を削減するが、共有範囲によって精度が変わる（§3.1、§4.5） | 全共有で失敗した場合にFFN非共有などを試す根拠。BERT系の結果をコード生成の保証に使わない |
| [8. Press & Wolf, EACL 2017](https://aclanthology.org/E17-2025/) | 入力embeddingと出力embeddingのweight tyingを検討し、パラメータ削減とLM・翻訳での効果を報告 | 0.426M案で語彙行列を共有する根拠。ただし日本語入力とPython出力での語彙の役割は異なるため、非共有対照を残す |

各行の番号は末尾の本文リンク付き参考文献に対応する。共通する示唆は「容量と計算の深さを分けて設計できる」であり、万能な圧縮や汎化改善ではない。

1物理層・3周や幅96/64という数値は論文がbokunano向けに推奨した値ではない。既存1Mの3層・幅128を起点に、層適用回数を揃えること、head次元32を維持すること、実際の重み内訳から削減箇所を選ぶことに基づく設計値である。周回数を増やしても失った独立変換や表現幅が必ず回復するわけではない。

## 3. 現在のbokunanoとの接続

### 3.1 コードから確認した構造

[モデル本体](../../scripts/model/boku_nano.py)の`BokuNanoForCausalLM`は、embedding、`ModuleList`内のblock、最終RMSNorm、出力headの順で計算する。blockはpre-normのcausal attentionとSwiGLUで構成され、線形層にbiasはない。今回`n_loops`と`loop_input_mode`を追加し、旧設定は各blockを1回ずつ適用する動作を維持した。

| 項目 | 比較起点の既存1M |
| --- | ---: |
| 語彙 | 2,048 |
| 幅 | 128 |
| 物理層 | 3 |
| heads / head次元 | 4 / 32 |
| FFN幅 | 256 |
| context | 256 |
| embedding/head | 非共有 |
| 重み数 | 1,016,704 |
| 学習期間 | 3epoch |

根拠: [保存済み1M・3epoch設定](../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/training_config.yaml)、[モデル設定](../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/model_config.json)。元の[1M設定ファイル](../../config/boku_nano_1m_bpe_2048_1epoch.yaml)はファイル名どおり1epochなので、比較実験では保存済み3epoch設定を起点にする。

**研究・小型化の基準は1M・3epoch**とする。現行Web既定が5Mであることは配備上の比較にだけ使い、より大きなモデルから縮めた事実を1M未満での成果として扱わない。既存の15M起点の構造比較とは別実験であり、head次元もその実験の64ではなく、1Mの32に合わせる。

### 3.2 何の改善を狙うか

[1M・標準BPE・3epochの実績](../results/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch_results.md)は、固定5集合で84,171/84,550、99.5517%。通常99.6256%、組合せ99.3358%、反復99.5877%、境界99.6256%を達成している。ただし日本語言い換えは15/30であり、巨大な集合のmicro平均に隠れるため別指標とする。

[現行872問の診断](../results/composition_suite_20261008/report.md)でも同モデルは未学習2操作99/100、3操作100/100、一般4操作43/100、ABAB78/100を達成している。[短いBPE版](../results/boku_nano_1m_bpe_2048_minfreq2_maxlen8_3epoch_results.md)は言い換え22/30という別の強みを持つが、token量も変わるので別系統として比較する。

そこで、次の2仮説を分ける。

1. **圧縮仮説**: 物理層・語彙行列の共有により、**0.426M以下で1M・3epochに近い実行正解率**を維持できる。loopだけの寄与は0.689Mの対照で分離する。
2. **構成汎化仮説**: 同じ変換を繰り返す構造が、既知の操作を長い列へ組み合わせる学習に役立つ。

後者は未検証の仮説である。潜在表現のループ数と、生成Pythonの操作数・`for`文の反復回数は別物であり、「4周すれば4操作を解ける」とは設計しない。

## 4. モデルの実装仕様

### 4.1 設定と共有の定義

`BokuNanoConfig`へ次の2項目を追加した。

```yaml
# 実装済みモデル設定の抜粋。完全な学習設定はconfig/boku_nano_looped_lt1_3epoch.yaml。
model:
  vocab_size: 2048
  d_model: 128
  n_layers: 1          # K: 固有の物理block数。既存キーの意味を変えない
  n_loops: 3           # R: 層群全体を通る回数。省略時は1
  loop_input_mode: none  # none / add。省略時はnone
  n_heads: 4
  d_ff: 256
  context_length: 256
  dropout: 0.0
  tie_word_embeddings: true  # 既存キー。非共有対照ではfalse
```

`n_loops`はboolを除く正の整数、`loop_input_mode`は列挙値に限定する。実効深さ`K * R`は派生値としてmanifestへ記録し、`n_layers`へ書き戻さない。

blockはK個だけ作る。attentionのQ/K/Vと出力射影、FFNの3射影、block内RMSNormを、同じ物理blockの全周回で共有する。最終normとheadは全周回後に1回適用する。`deepcopy`したK×R個の層を作ったり、周回ごとに別のnormやadapterを追加したりしない。

### 4.2 forwardの定義

`E`をtoken embedding、`F`をK個のblockの順次適用とする。既定の単純反復は`h₀=E; hᵣ₊₁=F(hᵣ)`である。再注入比較は`z₀=0; zᵣ₊₁=F(E+zᵣ)`とする。後者の入力経路は[1][4]を参考にするが、内部blockはbokunanoのままとする。

```python
# forward内の概念図。lossとshape検査は現行のものを維持する。
embedded = self.token_embedding(input_ids)
hidden = embedded
for loop_index in range(self.config.n_loops):
    if loop_index > 0 and self.config.loop_input_mode == "add":
        hidden = hidden + embedded
    for block in self.blocks:
        hidden = block(hidden)
logits = self.lm_head(self.final_norm(hidden)).float()
```

この書き方なら1周目にembeddingを二重加算せず、`R=1`で既存forwardと同じ計算になる。`none`と`add`はR=1では同じモデルである。

毎周回の各attentionで、現在の表現からQ/K/Vを計算し、同じtoken位置のRoPEを適用する。周回番号をtoken位置へ加算しない。既に回転したKを再回転して使い回さない。causal maskと右paddingの扱いを維持するため、ループを増やしても未来tokenを参照できない。

周回の間で`detach()`や`no_grad()`を挟まず、全周回を通して勾配を伝える。最終周回だけで既存のshifted causal lossを計算し、prompt・paddingは`-100`、code＋EOSを教師対象とする。途中周回の出力を別の正解として監督する補助loss、周回ごとのoptimizer更新、lossをRで割る処理は加えない。

### 4.3 初期化と学習安定性

初版は現行の切断正規初期化と、`_scale_residual_projections()`の`1/sqrt(2K)`を維持する。**Kを黙ってK×Rへ置き換えない。** 同じKの通常版とloop版で初期重みを揃えられ、Rだけを変える比較が明確になるためである。

一方、通常3層と1層×3周ではKが異なり、残差射影の初期スケールが√3倍異なる。同じ初期化規則でも同じ数値の初期化ではない。この比較を「共有以外は完全に同一」と説明せず、必要なら実効深さ3で揃えた初期化を別途比較する。

ただし、この初期化の安定性が共有反復で保証されるわけではない。少量の訓練データで、周回別hidden RMS、相対更新量、勾配norm、NaN/Inf、clip発生率を確認してから全件学習へ進む。`add`方式はembeddingの繰り返し加算によるスケール変化も記録する。

不安定なら、同じ小規模検証条件で次の初期化を別アブレーションする。

- attention出力とFFN down projectionを`1/sqrt(2KR)`で縮小する案。ただし共有重みの更新は相関するため、独立層の分散計算をそのまま保証には使わない。
- それらの出力射影のゼロ初期化。[3] §4に先例があるが、現行モデルからの追加変更として扱う。

初期化を変更した結果は初期版と分け、対照にも同じ規則を適用する。安定しなかった構成を隠して、成功した条件だけの比較にしない。

### 4.4 既存成果物との互換性

古い設定は`n_loops=1, loop_input_mode=none`で読み込む。`blocks.0...`等のstate dict名と既存層の形を保ち、旧重みをstrictにロードする。新しいモデルを古いローダーが誤って1周として実行しないよう、新キーの未知キー拒否は維持する。

注意点は[trainerのresume処理](../../scripts/model/train_boku_nano.py)である。実装前は保存済み`checkpoint["model_config"]`と`model_config.to_dict()`を生の辞書で比較していた。新しい既定値を加えただけでは、旧checkpointにキーがないため再開に失敗する。実装では`BokuNanoConfig.from_dict(...)`で保存済み設定を正規化し、現在の設定オブジェクトと比較する。R・再注入方式等の実質的な不一致は引き続き拒否する。

新実験は全条件をランダム初期化から学習する。既存3層重みの1層だけの流用や複数層の平均は初版に含めない。既存checkpointの読込互換性と、通常モデルからloopモデルへの変換は別の課題である。

### 4.5 embedding共有の保存・復元

現行モデルはすでに`tie_word_embeddings`を持ち、trueなら`lm_head.weight`が`token_embedding.weight`と同じParameterを参照する。新しい共有演算を作る必要はない。ただし、学習可能parameterの共有と、保存形式での重複排除は別である。

実装前の`save_final_weights()`はstate dictの全項目をCPUへ移してsafetensorsへ渡していた。共有した2つの名前は、CPU上では同一storageによる保存エラーを起こし得る一方、別deviceから個別にCPUへコピーされると重複保存になり得る。**小型化版では語彙行列を1回だけ保存する形式を実装した。** token embeddingを正本とし、共有設定のときだけheadの別名をモデルの`load_state_dict()`で復元してstrict loadする。旧形式で両方がある場合は値の整合性を検証するため、既存の評価・export・解析loaderも同じ規則を利用できる。

optimizerが同一Parameterを二重登録しないこと、load後の同一storage、両方の経路からの勾配、safetensorsの総bytes、ONNXで語彙行列が複製されないことを確認する。学習前の共有により条件が変わるため、非共有学習済みheadを読込時だけ捨てて圧縮できたとは扱わない。

## 5. 重み・計算量・メモリの見積もり

現行構造で語彙V、幅d、FFN幅f、固有block数Kの場合、パラメータ数は以下になる。embedding/headの共有とblockの周回間共有は独立した2種類の共有である。

```text
P_block = 4d² + 3df + 2d
P_untied = 2Vd + K × P_block + d
P_tied  =  Vd + K × P_block + d
D_effective = K × R
```

### 5.1 まず幅128のまま、共有の効果を分ける

幅128・FFN256では1 blockが164,096、非共有のembedding/headが524,288、最終normが128。**既存1Mの約51.6%がembedding/headにある。** blockだけを1個まで減らしても688,512となり、同じ幅・語彙・非共有行列のまま0.5M未満へは届かない。周回数を減らしてもこの重み数は減らない。

| ID | 構成 | K×R | embedding/head | 重み数 | 1M基準からの削減 | 用途 |
| --- | --- | --- | --- | ---: | ---: | --- |
| U3 | 通常3層 | 3×1 | 非共有 | 1,016,704 | — | 成功済み基準を再学習 |
| U2 | 通常2層 | 2×1 | 非共有 | 852,608 | 16.1% | 単に1層削るだけで十分か |
| U1 | 通常1層 | 1×1 | 非共有 | 688,512 | 32.3% | loopなしの同容量対照 |
| L1 | 1層×3周 | 1×3 | 非共有 | 688,512 | 32.3% | loopだけによる圧縮 |
| T3 | 通常3層 | 3×1 | 共有 | 754,560 | 25.8% | embedding共有だけの効果 |
| T1 | 通常1層 | 1×1 | 共有 | 426,368 | 58.1% | 主候補と同容量の浅い対照 |
| LT1 | **1層×3周** | **1×3** | **共有** | **426,368** | **58.1%** | **本命の小型loopモデル** |
| LT2 | 2層×2周 | 2×2 | 共有 | 590,464 | 41.9% | 1種類のblockで能力が不足した場合の候補 |

U3→L1が深さ方向の共有、U3→T3が語彙行列の共有、T3→LT1が共有embedding条件でのloop化に対応する。U1→L1とT1→LT1が、同じ重みへ反復計算を追加する価値を測る。LT2は4回適用なので、3回のLT1と同計算量とは呼ばない。実験する場合は通常2層tied版590,464も対照に加える。

### 5.2 さらに0.4M、0.3M、0.2M未満を調べる

以下は全て1物理層×3周、embedding/head共有、語彙2048、context256。数値は既存blockの式とモデル生成による固有パラメータ数の照合済み。**生成能力は未検証**である。

| ID | 幅d | FFN幅f | heads / head次元 | 重み数 | 1M基準からの削減 | 判断した理由 |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| LT1 | 128 | 256 | 4 / 32 | 426,368 | 58.1% | 表現幅を保つ主候補 |
| F128 | 128 | 128 | 4 / 32 | 377,216 | 62.9% | 状態の幅を維持し、FFNだけを削る |
| W96 | 96 | 192 | 3 / 32 | 289,056 | 71.6% | 幅を3/4にし、FFN比2とhead次元を維持 |
| W64 | 64 | 128 | 2 / 32 | 172,224 | 83.1% | 幅を半分にする最小側の探索候補 |

各候補に同じ幅・FFN・共有条件の通常1層を対照として置く。これにより、狭いモデルでloop自体が役立つか判定する。F128/W96/W64は容量と計算量の両方が変わるため、loopだけの効果としてU3と比べない。head数だけを減らして幅を固定しても現行dense projectionの重み数は減らないので、head数を節約の根拠にはしない。

F128はW96より大きいが幅128を保つため、2つを大小順だけで一方に決めない。devで選び、必要なら両方を残す。W64で失敗したら、学習時からR=6のW64を別条件として試せるが、反復による計算増と、幅の不足が残る可能性を明示する。

### 5.3 埋め込みをさらに分解する発展案

0.172Mでも大きい場合や、幅を保ちながら語彙行列を小さくしたい場合は、[ALBERT §3.1](https://arxiv.org/html/1909.11942)の低次元embeddingを参考にする。語彙行列`E[V,e]`を入出力で共有し、入力射影`A[e,d]`と出力射影`B[d,e]`は別のbiasなし行列にする設計なら、`P = Ve + 2ed + K×P_block + d`となる。これはALBERTそのものの再現ではなく、bokunano向けの追加設計である。

| 発展候補 | d / f / e | K×R | 重み数 | 目的 |
| --- | --- | --- | ---: | --- |
| Factor128 | 128 / 256 / 32 | 1×3 | 237,952 | 状態幅128を保って語彙行列を縮める |
| Factor64 | 64 / 128 / 32 | 1×3 | 110,784 | 約0.11Mの探索候補 |

低次元の入出力経路が新たなボトルネックになるため、初版の必須条件にはしない。tokenizer縮小は別の選択肢だが、系列長・context超過・教師token数が変わるので後段へ回す。量子化はbytes削減であり、ここで数える固有パラメータの削減とは別に報告する。

### 5.4 計算量とメモリ

固定幅・固定系列長で、block部分の主要なforward演算は概ねK×Rに比例する。通常3層と同幅の1層×3周は主要な演算数を揃える対照になるが、optimizer更新量、カーネル実行、メモリアクセスは異なる。**同じ実効深さを「学習時間も同じ」「厳密な総FLOPs一致」とは呼ばない。** 同一token量での演算見積もりと実測時間を併記する。

embedding tyingは出力logitsの行列積を省略する方法ではない。同じ1層の1周と3周では重み数が同じでもblock計算が増える。重み・勾配・optimizer stateは固有parameter数に依存する一方、full BPTTの中間activationは層適用回数にも依存する。したがって、重み58.1%削減から学習peak memory58.1%削減は導けない。必要になった場合のactivation checkpointingは、勾配を切る方法とは区別して追加する。

現行PyTorch生成・Web推論はKV cacheを持たず、生成のたびに全prefixを再計算する。初版はこの条件で比較する。将来厳密な通常decode cacheを導入する場合、重みが共通でも各周回の状態は異なるため、**cacheは原則`(loop_index, block_index)`ごとに持つ**。MHAでbatch B、prefix長T、要素bytes sなら容量概算は`2 × B × K × R × T × d × s`。K個へまとめて上書きするのは別の近似方式である。

## 6. 比較実験と学習条件

### 6.1 実施順と比較の意味

| 段階 | 条件 | 確かめること |
| --- | --- | --- |
| A・基礎比較 | U3、U2、U1、L1、T3、T1、LT1 | 全て3epoch。層を削るだけ、loop、embedding共有の寄与を分ける |
| A・再注入比較 | L1とLT1について、それぞれ同条件の`add`版を追加 | `none`との対応比較。小型・単一blockでも入力再注入が必要か |
| B・小型化 | F128、W96、W64と、それぞれの通常1層対照 | 全て3epoch。幅・FFN縮小時の精度とloopの価値 |
| B・容量救済 | LT2と通常2層tied。必要なら最小候補のR=2/6 | 1種類のblockで不足する場合と、周回数の不足を別々に調べる |
| C・確認 | 開発基準を満たす最小候補、対応する浅い対照、U3 | 複数seed、ONNX・実ブラウザ検証 |
| D・発展 | Factor128/Factor64と対応する通常版 | 埋め込み因子分解を追加し、0.24M/0.11M級を検討 |

段階A/Bの標準は`none`とし、Aの`add`比較で良ければBでも同一構成の`add`比較を事前追加する。候補ごとに方式を選んだ結果を、方式が揃った比較と混ぜない。初期実装の確認はU3/U1/L1の3条件から始め、性能を判断する学習は3epochまで行う。全候補で同じ学習token量を揃え、通常モデルも今回の実験で再学習する。

### 6.2 固定する条件

[保存済み1M・3epoch設定](../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/training_config.yaml)を起点にする。

- 192,900訓練レコード、既存train/validation archiveとtokenizerのSHA-256、系列テンプレート、code＋EOSのみのlossを固定する。
- 標準BPE 2,048語彙（minfreq5/maxlen24）、context 256、dropout 0を使用する。embedding共有は表の比較因子としてのみ変更する。短いpiece版は全条件を揃えた別実験とする。
- **主比較は最初から全条件3epoch**、seed `20260925`。AdamW、LR `3e-4`→`3e-5`、warmup 5%、weight decay 0.1、gradient clip 1.0を維持する。
- 論文[1]のLAMBや学習率を移植しない。optimizerや教師token密度も異なるので、同じ数値で安定する根拠がない。
- 実効batch 512を維持する。OOMでmicro batchを下げる場合は勾配蓄積で合わせ、**全ての比較対象を同じmicro batch・蓄積回数に揃えて再学習する**。現trainerは各micro batchの平均CEを平均するため、教師token数が異なる場合は512件一括のtoken平均と一般に一致しない。実効batch数だけを合わせて同じ学習条件とは扱わない。最終端の不完全batchを含め、実際の更新数・token数を記録する。
- データの並べ替えは、既存trainerの独立した`torch.Generator`と`seed + epoch`を維持し、サンプル順を検証する。同じseedだけで異なる構造の初期重みまで同一とは主張しない。同じKのR比較では初期stateのhash一致を確認する。
- 学習率や初期化の探索は同じ候補数・開発用評価条件で通常版にも行い、探索予算を記録する。

1Mは1epoch時点では十分に習得していないため、1epochの正解率で小型候補を足切りしない。3epoch scheduleの途中checkpointと、最初から1epoch scheduleで学習した過去モデルも同一視しない。標準BPEでは3epochで非padding系列token20,818,398、教師token11,238,201、1,131更新を既存再現の照合値にする。短いBPEは系列token51,845,985で約2.49倍異なる。

3epochで不足して6epoch等を試すなら、比較対象の通常版にも同じ追加予算を与える別実験として登録する。正式確認の複数seedは、例えば`20260925/20260926/20260927`を事前固定する。初期値やembedding共有の有無で初期学習の立ち上がりは変わり得るため、最終精度と収束の速さを分けて報告する。

固定学習量に加え、必要なら同じ総学習FLOPsまたは同じ実時間予算の実験を別に設ける。その場合は各モデルが見たtoken数の違いも報告する。単純にパラメータ数だけを使う`6ND`等の概算では、反復した重みの演算を数え落とすので、共有blockの適用回数を数える。

## 7. 評価と採用判断

### 7.1 指標

主指標はgreedy生成1回・修復なしの**実行正解率**とする。validation loss/perplexityは学習監視に使い、採用を単独で決めない。

| 評価 | 用途 |
| --- | --- |
| 既存の固定5集合: normal/compositional/paraphrase/repetition/boundary | 従来の生成能力と境界条件の回帰確認 |
| 2026-10-08改訂の9カテゴリ・872問 | 2・3操作、一般4操作、ABAB、反復、表現転用の診断。カテゴリ別に比較 |
| 順序を区別できる入力・反復回数を区別できる部分集合 | 交換可能な操作や冪等操作による見かけの成功を分離 |
| 構文・契約・実行失敗の分類 | 操作欠落、順序違い、前段結果の不使用、未初期化変数、不要操作、早期EOS、context上限を区別 |

Boku間では同じtokenizer、プロンプト、context、生成上限、停止条件を使う。Qwenの前処理・修復は介在させない。既存872問は全179入力と同じ契約検査を維持し、意味的に正しいコードの簡約を「操作行数が少ない」という理由で失格にしない。

計測は同一hardware・dtype・runtimeで、warmup後のprefill時間、固定prefix長ごとの次token推論時間、tokens/s、実タスクの生成完了時間、peak memory、保存重みbytes、ONNX bytesを記録する。生成長が短いだけで速く見えないよう、固定系列長の計測とEOSまでの実生成を分ける。端末・ブラウザ・実行backend・反復測定回数・中央値とp95を残す。

### 7.2 既存テストを未使用の盲検と扱わない

872問は既に結果を確認した診断セットである。固定5集合も過去に利用済みなので、今回の候補数・学習期間・checkpoint・生成条件を事前固定した再測定と位置づける。これらの得点を見て選び直した場合は開発利用として明記し、独立した最終性能とは呼ばない。

特に[改訂報告](../results/composition_suite_20261008/report.md)と[既存の未学習組合せ評価方針](boku_nano_unseen_composition_benchmark_plan.md)を踏まえ、次を守る。

- 2操作100問は10 ASTの表現違いであり、100独立アルゴリズムではない。文単位の得点に加え、AST・操作対単位で対応差を見る。
- 3→2転用88問の順序は全て3操作訓練内に既出で、固定入力で順序を判別できるのは48問。厳密な初見逆順の評価と呼ばない。
- より強い汎化主張には、操作対・意味AST・機能等価群でtrain/dev/finalを分ける新実験を設ける。厳密な逆順の保留を含めるなら、通常モデルも含めて再分割・再学習する。
- 新しい確認用評価では、機能重複の選別用入力と最終採点用入力を分離する。既存872問の再測定は179入力を維持する。有限入力での一致は全入力での数学的等価性を保証しない。

調整には既存validationを使う。構成汎化を見て調整する必要がある場合は、専用devと最終セットの分割・凍結を先に行う。初版の比較を終えるために、既存訓練データを途中で変更しない。

### 7.3 採用の基準

次は文献の保証値ではなく、**本提案の暫定的な工学基準**である。実験開始前に固定してmanifestへ保存する。

1. **実装の成立**: R=1互換性、因果性、共有勾配、embedding/headの共有復元、PyTorch/ONNXの一致を満たす。
2. **圧縮の成立**: まず0.689M、主目標0.426M、さらに0.289M/0.172Mで、書き出し後の配布bytesも減る。条件を満たす最小構成を選ぶ。
3. **固定5集合の能力維持**: 再測定したU3・3epochに対し、micro正解率低下を**0.05 percentage points以内**、通常・組合せ・反復・境界それぞれを**0.10 points以内**とする。報告済み84,171/84,550を再現した場合、microの追加失敗は42件までに相当する。99.55%の基準に対して2ポイントの劣化を許すと失敗が約5.5倍になり得るため、許容幅を狭くする。
4. **小さな評価集合**: 言い換え30件は正解件数を減らさない（標準BPEの既存値は15/30）。1件が3.33ポイントなので、大集合と同じ小数点の閾値を当てない。新しく解けた問題・解けなくなった問題を併記する。
5. **872問の能力維持**: 全9カテゴリを報告し、候補判定では各カテゴリの正解数をU3から減らさない。特に一般4操作43/100、ABAB78/100、4回反復70/96という既存水準を別掲する。小差で判定が変わる候補は複数seedで再確認し、未達でも圧縮率と失敗の代償を残す。
6. **反復の価値**: 同じ容量・同じembedding共有条件の通常1層との対応差を確認する。通常1層でも能力維持でき、loopで改善がなければ、速い通常1層を選ぶ。loop方式自体を採用の必須条件にしない。
7. **確認段階**: 上の閾値は採用候補の実務上の判定であり、統計的同等性の証明ではない。複数seed、AST/操作対を単位とする対応評価と不確実性を報告する。非劣性を主張するなら、Δ＝候補の正解率−U3の正解率、許容低下δ＞0と定義し、事前に定めた評価でΔの下側信頼限界が−δを上回ることを要する。標本不足なら「未確定」とする。
8. **Webへの採用**: まず1Mとの能力・配信容量・生成時間を比較し、現行Web既定5Mとの比較も併記する。容量が小さくてもR増加で遅くなる場合は、その代償を表示して実験モデルとして提供する。

各閾値は今回の性能維持目標に基づく暫定設計値であり、文献由来でもユーザー指定値でもない。実験前に固定し、得点を見て広げない。通常・境界等の重複や同一ASTの表現違いを独立標本と見なさず、順序・回数を識別できる部分集合も別掲する。新しい分割による正式汎化実験は、その分割で評価手続きを再登録する。

## 8. コード変更箇所と検証

| 対象 | 実装時に行う変更 |
| --- | --- |
| [boku_nano.py](../../scripts/model/boku_nano.py) | configの2項目・検証・派生深さ、共有stackの反復、再注入比較、既存embedding tyingの利用。既存block構造・lossを維持 |
| [train_boku_nano.py](../../scripts/model/train_boku_nano.py) | 旧configを正規化するresume比較、tied重みの保存、R等の記録、既存の独立shuffle generatorの維持、安定性ログ |
| [config/](../../config/) | 新しいloop用YAMLを別名で追加。学習・評価双方の`expected_parameter_count`を更新し、既存学習設定・出力先を上書きしない |
| [loop比較runner](../../scripts/model/run_boku_nano_looped_experiment.py) | 既存のhead/layer比較を維持し、独立したloop比較runnerを追加済み |
| [evaluate_boku_nano.py](../../scripts/model/evaluate_boku_nano.py)・[composition_model_catalog.py](../../scripts/model/composition_model_catalog.py) | tied重み読込、新モデルIDとK/R/方式/幅/FFN/tyingを記録し、生成・採点条件を維持 |
| [export_boku_nano_onnx.py](../../scripts/model/export_boku_nano_onnx.py) | tied重み読込、固定Rの書き出し、constant foldingによる転置head重複への対応。metadata・数値一致を検査 |
| [web/demo.js](../../web/demo.js)・[web/app.js](../../web/app.js)とWeb側モデル定義 | 現行`index.html`の入口は`demo.js`。評価通過後に別モデルとして登録し、初版は全prefix推論を継続 |
| [attention解析](../../scripts/model/analyze_boku_nano_attention.py)・[KV可視化](../../scripts/model/visualize_boku_nano_kv.py) | 初版はloopモデルを明示的に拒否し、上書きによる誤解析を防ぐ。将来は捕捉キーを`(loop, block)`へ拡張 |
| [head介入解析](../../scripts/model/analyze_boku_nano_attention_interpretability.py) | 初版はloopモデルを拒否。将来、全周回の共有head介入と特定周回への介入を区別 |
| [既存モデルテスト](../../tests/test_train_boku_nano.py)と新規loopテスト | 下記の実装契約を検証。実性能は別の学習・生成評価で確認 |

ONNXはRを固定して展開する方針とし、初版で動的`Loop`演算子による可変反復は狙わない。ただし、共有Python moduleが自動的に最小容量のONNXになると決めつけない。initializerの数・総bytes・実ファイルサイズを調べ、重複があればexporter側を修正してから配備する。CPUのONNX Runtimeだけで終わらず、対象ブラウザbackendで全prefix推論を確認する。

小規模検証では、LT1相当の未学習1層×3周・float32・opset18で、現行の`do_constant_folding=True`だとembeddingと転置headが別initializerになり、initializer合計2,753,024 bytes、ファイル2,910,803 bytesとなった。`False`ではそれぞれ1,704,448 bytes、1,870,758 bytesに減った。入力長1/7/23でCPU ONNX RuntimeとPyTorchのlogits最大誤差は両条件とも約5.36e-7以下だった。環境はtorch2.13.0、onnx1.23.0、onnxruntime1.30.0。**これは重み格納の検証であり、学習済み性能・ブラウザ速度の確認ではない。** exporter側のfolding制御を候補とし、ブラウザで数値・速度・実行時メモリを検証して採用する。

必要な検証は次のとおり。

- 旧config・旧state dictでR=1のlogits/loss/greedy生成が旧実装と一致し、旧checkpointのresumeも通る。
- K固定でRを変えてもparameter数とstate dictの固有重みが増えず、各blockの呼出し数はRになる。
- 微小モデルの独立した展開参照で、loop版のlogitsと共有重みの勾配を比較する。各展開位置の勾配の和が共有側に一致し、途中detachがないことを確かめる。
- `none`/`add`はR=1で一致し、R>1の`add`が初回二重加算を起こさない。
- 未来tokenを変更しても、それ以前のlogitsは変わらない。prompt/paddingのloss除外とEOS監督を維持する。
- 保存・読込でR/方式を復元し、実質的に異なる設定へのresumeを拒否する。
- embedding共有を保存・読込後も復元し、optimizerへの二重登録と配布ファイル上の語彙行列の重複を検査する。評価・解析の全loaderを対象にする。
- PyTorch/ONNXを短文・長文・EOS・context境界で比較する。dtypeに応じた許容誤差を先に定め、argmaxが異なる例を検査する。
- attention等の捕捉数がK×Rになり、周回別の出力が上書きされない。解析でいう「層」が物理層か適用位置かを表示する。

## 9. 初版の後に検討するもの

| 条件・観測 | 次に試す変更 | 別実験にする理由 |
| --- | --- | --- |
| `none`より`add`が安定して良い | 再注入を新しい既定にする | 入力経路の寄与を確認してから採用する |
| 初段・最終段の役割が共有で壊れる | 前後に非共有blockを置くmiddle looping | [2] §3.3、[5]の設計を参考にする。固有容量・計算量も変わる |
| 共有FFNで容量不足が疑われる | attentionのみ共有、または少数の非共有FFN | [7]を参考に、物理容量を増やす効果として比較する |
| 語彙行列の占有がさらに問題になる | §5.3の因子分解、次いでtokenizer縮小 | 前者は入出力の表現力、後者は系列長・教師token量も変える |
| 固定Rで成果が出て、可変計算を求める | 学習時Rを分布から選び、推論時Rの曲線を測る | 初めて推論回数の外挿を主題にする。R_trainとR_evalを必ず別記 |
| 高Rで速度負担が大きい | 適応停止・途中出力の学習 | 停止指標の収束だけでは正しさを保証できない。追加lossと停止失敗を評価する |
| ブラウザ推論が遅い | 正確な周回別KV cache | 重み共有とは別の高速化。RoPE offset・cacheあり/なしの一致も必要 |

学習済みRを推論時だけ増やす実験は診断として行えても、改善を前提にUIへ「考える回数」の可変設定を追加しない。通常の採点では学習時と同じRを使用する。

## 10. 参考文献

全て一次資料。閲覧日は2026-10-15。節番号はリンク先の版に従う。

1. Fan, T. et al. (2026). **Looped GPT-BERT: Trading Parameters for Computation in Small Language Modeling**. arXiv:2609.09691v1. [本文](https://arxiv.org/html/2609.09691v1)。主に§3.3、§4.4–4.5、Limitations。
2. Saunshi, N. et al. (2025). **Reasoning with Latent Thoughts: On the Power of Looped Transformers**. ICLR 2025, arXiv:2502.17416. [本文v1](https://arxiv.org/html/2502.17416v1) / [会議版](https://openreview.net/pdf?id=din0lGfZFd)。主に§2、§3.1–3.3。
3. Kohli, H. et al. (2026). **Loop, Think, & Generalize: Implicit Reasoning in Recurrent-Depth Transformers**. arXiv:2604.07822v2. [本文](https://arxiv.org/html/2604.07822v2)。主に§4–6、Appendix F。
4. Yang, L. et al. (2024). **Looped Transformers are Better at Learning Learning Algorithms**. ICLR 2024, arXiv:2311.12424. [本文](https://arxiv.org/html/2311.12424)。主に§4–4.1、§6。
5. Geiping, J. et al. (2025). **Scaling up Test-Time Compute with Latent Reasoning: A Recurrent Depth Approach**. arXiv:2502.05171. [書誌](https://arxiv.org/abs/2502.05171) / [本文](https://arxiv.org/html/2502.05171)。主に§3、§4.3。HTML見出しには別表題「Scaling by Thinking in Continuous Space」が表示されるため、ここでは書誌ページの表題を使用。
6. Dehghani, M. et al. (2019). **Universal Transformers**. ICLR 2019, arXiv:1807.03819. [本文](https://arxiv.org/html/1807.03819)。主に§2.1–2.2。
7. Lan, Z. et al. (2020). **ALBERT: A Lite BERT for Self-supervised Learning of Language Representations**. ICLR 2020, arXiv:1909.11942. [本文](https://arxiv.org/html/1909.11942)。主に§3.1、§4.5。
8. Press, O. and Wolf, L. (2017). **Using the Output Embedding to Improve Language Models**. EACL 2017, pp.157–163. [ACL Anthology](https://aclanthology.org/E17-2025/) / [arXiv](https://arxiv.org/abs/1608.05859)。入力/出力embeddingのweight tying。

実験結果の再利用・データの意味は、[構造比較方針](boku_nano_architecture_ablation.md)、[モデル評価方針](boku_nano_model_evaluation_policy.md)、[872問改訂報告](../results/composition_suite_20261008/report.md)、[未学習組合せ評価方針](boku_nano_unseen_composition_benchmark_plan.md)を併せて参照する。

## 11. 実行方法

本命の0.426Mを3epoch学習するコマンド:

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_looped_experiment.py \
  --output-root data/models/looped_lt1_run --variants lt1 --run
```

`--run`なしなら設定生成のみ。`--variants`を省くと通常モデルを含む9条件を生成する。小型候補は`--variants lt1 w96 w64`、対応する通常1層対照は`--variants t1 w96_plain w64_plain`で指定できる。全て3epochが既定。

依存関係、固定YAMLでの直接学習、CPU動作確認、メモリ調整、再開、生成評価、ONNX、自動テストは[実行手順](../procedures/boku_nano_looped_training.md)に記載した。
