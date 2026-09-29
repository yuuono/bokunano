# Boku NanoのChinchilla則によるモデル規模・訓練トークン概算

## 1. 結論

Boku Nanoと同じ語彙数2,048、文脈長256、RoPE、RMSNorm、SwiGLU、入力embeddingと出力headを非共有とする実装で、約5M・15M・35Mの3構成を比較する。

| 呼称 | 実parameter数 | d_model | block数 | head数 | head次元 | d_ff | 推奨訓練token | 概算範囲 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 5M級 | 5,065,472 | 256 | 5 | 4 | 64 | 704 | 約100M | 約70M〜105M |
| 15M級（現行） | 15,735,168 | 384 | 8 | 6 | 64 | 1,024 | 約320M | 約285M〜320M |
| 35M級 | 34,220,544 | 512 | 10 | 8 | 64 | 1,408 | 約700M | 約690M〜735M |

推奨訓練tokenは、Chinchilla論文のApproach 1から得られる約20.2 token/parameterを計画の中心値として丸めた値である。概算範囲は、Approach 1と論文のparametric loss fit（Approach 3）の両方を今回の実parameter数へ適用した幅であり、統計的な信頼区間ではない。

今回の用途で最初に比較するなら、現行15M級を基準に5M級を追加する。35M級は約700Mの十分に多様な訓練tokenを用意できる場合に検討する。現在の固定訓練コーパスは1 epoch当たり6,939,466非padding tokenであり、同じデータを単純に何十回も反復することは、Chinchilla論文が想定するデータ増加と同等ではない。

## 2. Chinchilla論文から使用する式

一次資料はHoffmann et al., [Training Compute-Optimal Large Language Models](https://arxiv.org/abs/2203.15556)である。著者らは400超のモデルを比較し、モデルparameter数と訓練token数を、計算量の増加に対してほぼ同じ割合で増やすという結果を報告している。Google DeepMindの[研究紹介](https://deepmind.google/blog/an-empirical-analysis-of-compute-optimal-large-language-model-training/)でも、70B parameterのChinchillaを約1.4T tokenで学習した検証結果が説明されている。

記号を次のように置く。

- N: embeddingを含むモデルparameter総数
- D: 訓練token数
- C: 訓練計算量の近似値（FLOPs）

論文ではTransformerの訓練計算量を次で近似する。

~~~text
C ≈ 6 N D
~~~

### 2.1 Approach 1を使う中心値

論文Table 3では、400M parameterに8.0B token、1B parameterに20.2B tokenなどが割り当てられている。今回の規模では、計画用の中心値を次の単純な式で求める。

~~~text
D_approach1 ≈ 20.2 N
~~~

### 2.2 Approach 3を使う別推定

論文は最終lossを次の関数としてfitしている。

~~~text
L(N, D) = E + A / N^α + B / D^β

E = 1.69
A = 406.4
B = 410.7
α = 0.34
β = 0.28
~~~

C ≈ 6NDを固定してlossを最小化すると、parameter数を指定した場合のtoken数は次になる。

~~~text
D_approach3 = (βB / αA)^(1/β) N^(α/β)
            ≈ 0.5190 N^1.2143
~~~

本書では、Approach 1とApproach 3の小さい方から大きい方までを概算範囲として示す。Approach 2のIsoFLOP推定も論文Table A3では概ね20 token/parameter付近であり、中心値を20.2倍とする判断を大きく変えない。

### 2.3 外挿上の注意

論文の実験モデルは70M〜16B超、訓練量は5B〜500B tokenである。今回の5M〜35Mは実験範囲より小さいため、この計算は外挿である。また、論文はC4とGitHub codeでも、原則として1 epochを超えない条件で同様の傾向を確認している。したがって、次の点に注意する。

- 約20 token/parameterは保証値ではなく、初期の計画値として使う。
- 同じ少量データの反復だけでDを満たしたとみなさず、できるだけ固有で多様なデータを増やす。
- 汎用言語モデルのloss最適点と、狭いコード生成課題の実行成功率の最適点は一致するとは限らない。
- 最終的な停止位置はvalidation lossと5評価集合の実行成功率で決める。

## 3. Boku Nanoのparameter計算式

現行の[モデル実装](../../scripts/model/boku_nano.py)では、linear層にbiasを持たず、通常のMulti-Head AttentionとSwiGLUを使用する。[現行設定](../../config/boku_nano_bpe_2048.yaml)と同じく入力embeddingとLM output headは共有しない。

次の記号を使う。

- V: 語彙数
- d: d_model
- L: Transformer block数
- f: SwiGLUのd_ff

1 blockのparameter数は次になる。

~~~text
attention = QKV projection + output projection
          = 3d² + d²
          = 4d²

SwiGLU    = gate projection + up projection + down projection
          = df + df + fd
          = 3df

RMSNorm   = 2d

block     = 4d² + 3df + 2d
~~~

モデル全体は次になる。

~~~text
N = token embedding + L × block + final RMSNorm + LM output head
  = Vd + L(4d² + 3df + 2d) + d + Vd
  = 2Vd + L(4d² + 3df + 2d) + d
~~~

RoPEとdropoutは学習parameterを持たない。head数はprojection行列の総形状を変えないため、dがheadへ分割可能である限りparameter総数には影響しない。ただし、今回の3構成は比較を単純にするためhead次元をすべて64に固定する。

## 4. 具体的な3モデル

全構成で語彙数2,048、文脈長256、通常のMulti-Head Attention、SwiGLU、RoPE、pre-norm RMSNorm、biasなし、embedding非共有、dropout 0.0を固定する。

| 呼称 | d_model | block数 | head数 | head次元 | d_ff | 実parameter数 |
|---|---:|---:|---:|---:|---:|---:|
| 5M級 | 256 | 5 | 4 | 64 | 704 | 5,065,472 |
| 15M級（現行） | 384 | 8 | 6 | 64 | 1,024 | 15,735,168 |
| 35M級 | 512 | 10 | 8 | 64 | 1,408 | 34,220,544 |

### 4.1 5M級

~~~yaml
model:
  vocab_size: 2048
  d_model: 256
  n_layers: 5
  n_heads: 4
  d_ff: 704
  context_length: 256
  tie_word_embeddings: false
~~~

~~~text
embedding + output head = 2 × 2,048 × 256               = 1,048,576
1 block                = 4 × 256² + 3 × 256 × 704 + 512 =   803,328
5 blocks               = 5 × 803,328                    = 4,016,640
final RMSNorm          =                                      256
合計                   =                                5,065,472
~~~

### 4.2 15M級（現行モデル）

~~~yaml
model:
  vocab_size: 2048
  d_model: 384
  n_layers: 8
  n_heads: 6
  d_ff: 1024
  context_length: 256
  tie_word_embeddings: false
~~~

~~~text
embedding + output head = 2 × 2,048 × 384                  =  1,572,864
1 block                = 4 × 384² + 3 × 384 × 1,024 + 768 =  1,770,240
8 blocks               = 8 × 1,770,240                    = 14,161,920
final RMSNorm          =                                         384
合計                   =                                  15,735,168
~~~

これは現在の[Boku Nano本学習方針](boku_nano_training_policy.md#2-固定モデル仕様)と同じ構成である。

### 4.3 35M級

~~~yaml
model:
  vocab_size: 2048
  d_model: 512
  n_layers: 10
  n_heads: 8
  d_ff: 1408
  context_length: 256
  tie_word_embeddings: false
~~~

~~~text
embedding + output head = 2 × 2,048 × 512                   =  2,097,152
1 block                = 4 × 512² + 3 × 512 × 1,408 + 1,024 =  3,212,288
10 blocks              = 10 × 3,212,288                    = 32,122,880
final RMSNorm          =                                            512
合計                   =                                     34,220,544
~~~

3構成とも、実際にBokuNanoForCausalLMを生成してparameter_count()を実行し、上記の式と一致することを確認した。

## 5. 訓練token量の計算結果

| 呼称 | 実parameter数 N | Approach 1: 20.2N | Approach 3 | 計画用の範囲 | 採用する目安 | C ≈ 6ND |
|---|---:|---:|---:|---:|---:|---:|
| 5M級 | 5,065,472 | 102.3M | 71.9M | 70M〜105M | 100M | 約3.1e15 FLOPs |
| 15M級 | 15,735,168 | 317.9M | 284.6M | 285M〜320M | 320M | 約3.0e16 FLOPs |
| 35M級 | 34,220,544 | 691.3M | 731.1M | 690M〜735M | 700M | 約1.4e17 FLOPs |

FLOPs列はApproach 1の未丸めtoken数を使用した理論近似である。実際の処理量は系列padding、optimizer、validation、checkpoint、kernel実装などで増減する。

## 6. 現在の訓練量との比較

[3 epoch学習結果](../results/boku_nano_three_epoch_training_results.md#学習条件と完了状態)では、1 epoch当たり次のtoken数を使用している。

| 数え方 | 1 epoch | 3 epoch | 10 epoch |
|---|---:|---:|---:|
| モデルが読む非padding系列token | 6,939,466 | 20,818,398 | 69,394,660 |
| loss対象のcode・EOS token | 3,746,067 | 11,238,201 | 37,460,670 |

現行15M級モデルのChinchilla概算範囲は約285M〜320M tokenである。実parameter数で割ると約18.1〜20.2 token/parameterになる。

| 学習量 | 全系列token / parameter | loss対象token / parameter | 320M目安に対する全系列token比 |
|---|---:|---:|---:|
| 3 epoch | 1.32 | 0.71 | 6.5% |
| 10 epoch | 4.41 | 2.38 | 21.7% |
| Chinchilla計画値 | 約20.2 | 約20.2 | 100% |

ChinchillaのDは通常のcausal language modellingでlossを計算する訓練tokenを指す。一方、Boku Nanoは日本語promptをcontextとして読むが、その部分をloss対象にしない。このため、全系列tokenとloss対象tokenのどちらも完全には同じ定義にならない。計算量を見積もるときは全系列token、学習信号の量を比較するときはloss対象tokenを併記する。

現在と同じコーパスを反復するだけで目安へ到達させる場合、全系列token基準では約14.4、46.1、100.9 epoch、loss対象token基準では約26.7、85.4、186.9 epochが必要になる。しかし、これは必要量をepochへ機械的に換算した値にすぎず、推奨epoch数ではない。Chinchilla則へ近づけるには、反復回数より固有データ量を増やすことを優先する。

## 7. 今回のモデルに対する判断

### 5M級

- 現在の約15.7Mモデルより訓練・推論が軽く、データ量との不均衡も小さくなる。
- 約100Mの多様な訓練tokenを確保できれば、Chinchilla中心値に近づけやすい。
- 現行モデルとのparameter効率比較に最初に追加する候補とする。

### 15M級

- 現行の15,735,168 parameter構成をそのまま使用できる。
- Chinchilla中心値は約318M tokenであり、計画上は約320Mを目安にする。
- 現在の3 epochまたは10 epoch結果を、320M token学習済みと表現してはいけない。

### 35M級

- 15M級より容量は増えるが、目安となる訓練量も約700M tokenへ増える。
- 現在の固有コーパス規模のままparameterだけ35Mへ増やすと、データ不足がさらに大きくなる。
- 先にデータ拡張と5M対15Mの比較を行い、validation lossと実行成功率が容量不足を示した場合に進む。

## 8. 推奨する実験順

1. 5M級と現行15M級を、同じtokenizer、同じデータ順、同じtoken budgetで比較する。
2. validation lossだけでなく、通常・組合せ汎化・言い換え・反復・境界値の実行成功率を比較する。
3. token budgetを増やす場合は、同一レコードの反復率と固有token数を分けて記録する。
4. 約100M、320M、700Mを最終到達必須値ではなく、early stoppingを判断する上限側の計画値として扱う。
5. 35M級は、15M級が十分なデータでも明確に容量不足であることを確認してから学習する。

この順序により、Chinchilla則を参考にしつつ、今回の狭い日本語命令からPythonコードを生成する課題で必要以上にモデルだけを大きくすることを避けられる。
