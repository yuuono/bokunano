# Looped Transformer 全4サイズ：3 epoch学習・固定5集合評価

実行日: 2026-10-15

## 結論

設計書の小型化候補4サイズ（LT1、F128、W96、W64）を、すべてランダム初期値から3 epoch学習した。全モデルで各epoch後に24,040件のvalidation lossを測定し、`epoch_01.pt`、`epoch_02.pt`、`epoch_03.pt`を保存した。学習と成果物検査はすべて正常終了している。

固定5集合84,550件の実行評価では、最大のLT1（426,368 parameters）が18,483件、pass@1 21.8604%で最良だった。F128は11.3601%、W96は1.1674%、W64は0.1549%で、サイズ縮小に伴って大きく低下した。既存の通常3層1Mモデルは同じ固定5集合で99.5517%であり、今回の4候補はいずれも代替水準に達していない。

したがって、この結果だけからlooped transformerによる小型化成功とは判断しない。1物理層を3周させる構成は、今回のデータ量・optimizer・3 epoch条件では、3つの独立層を持つ1Mモデルの実行能力を回復できなかった。

## 対象と固定条件

「全モデルサイズ」は、[Looped Transformer導入方針](../policies/boku_nano_looped_transformer_plan.md)の初版小型化表にある、embedding/head共有・1物理層×3周の4サイズを指す。通常1層対照や反復回数2/6、入力再注入`add`は別の構造比較であり、今回のサイズ系列には含めていない。

| ID | hidden / FFN | heads | 物理層×周回 | parameters | 既存1Mからの削減 |
|---|---:|---:|---:|---:|---:|
| LT1 | 128 / 256 | 4 | 1×3 | 426,368 | 58.0637% |
| F128 | 128 / 128 | 4 | 1×3 | 377,216 | 62.8981% |
| W96 | 96 / 192 | 3 | 1×3 | 289,056 | 71.5693% |
| W64 | 64 / 128 | 2 | 1×3 | 172,224 | 83.0606% |

共通条件は標準BPE 2,048語彙、context 256、embedding/head共有、`loop_input_mode=none`、訓練192,900件、validation 24,040件、seed `20260925`、AdamW、実効batch 512、CUDA bfloat16である。各モデルは1 epochあたり377 optimizer steps、合計1,131 stepsを実行した。学習対象はcode＋EOS tokenのみで、3 epochの対象token数は11,238,201だった。

## Epoch別validation loss

validation lossは各epoch終了時に、固定24,040件・468,381教師tokenの加重平均として測定した。

| Model | Epoch 1 | Epoch 2 | Epoch 3 | Epoch 3 perplexity |
|---|---:|---:|---:|---:|
| LT1 | 1.306877 | 0.869333 | **0.761235** | 2.140918 |
| F128 | 1.369272 | 0.949107 | **0.837467** | 2.310506 |
| W96 | 1.626059 | 1.193968 | **1.087412** | 2.966586 |
| W64 | 2.373558 | 1.570373 | **1.460476** | 4.308011 |

![Epoch別validation loss](figures/looped_all_sizes/validation_loss_by_epoch.svg)

全モデルでepochごとにlossは低下し、parameter数が大きいほど最終lossも低かった。NaN/Infによる停止はなく、4モデルとも`status=completed`で終了した。

## 学習成果物

| Model | 学習時間 | checkpoint | 最終重みSHA-256 |
|---|---:|---:|---|
| LT1 | 44.081秒 | 3 / 3 | `34266e64bcc100975f804f6d7b80c3061227911c381afd0f85d4f17bec36f704` |
| F128 | 43.957秒 | 3 / 3 | `c8a7a3a0f7761a7a2ceceab408c70f5f0ba375821a9a4aaff60671c7dfbdd485` |
| W96 | 43.312秒 | 3 / 3 | `a8723af569667ef9b5b1bbbaa46d4102b95513e04be416c4abe3b79e4b2b52ed` |
| W64 | 43.052秒 | 3 / 3 | `0f0c290cf8875e6a0d2949732684b306a40012de939a1a49fed6eaf84a87b193` |

各modelディレクトリには最終`model.safetensors`、`model_config.json`、解決済み`training_config.yaml`、`training_manifest.json`、`training_metrics.jsonl`と、3個のepoch checkpointがある。

## 固定5集合の実行評価

greedy生成、最大160 token、CUDA bfloat16、1コード5秒timeoutで評価した。参照コードとの文字列一致ではなく、構文・安全AST・`solve(xs, k)`のsignature・入力非変更・固定hidden testをすべて満たした場合を合格とした。

### Suite別pass@1

| Model | 通常 24,040 | 組合せ 13,400 | 言い換え 30 | 反復 23,040 | 境界 24,040 | 合計 84,550 |
|---|---:|---:|---:|---:|---:|---:|
| 既存1M通常3層 | 99.6256% | 99.3358% | 50.0000% | 99.5877% | 99.6256% | **99.5517%** |
| LT1 | 4,707 (19.5799%) | 2,109 (15.7388%) | 3 (10.0000%) | 6,990 (30.3385%) | 4,674 (19.4426%) | **18,483 (21.8604%)** |
| F128 | 2,404 (10.0000%) | 918 (6.8507%) | 3 (10.0000%) | 3,883 (16.8533%) | 2,397 (9.9709%) | **9,605 (11.3601%)** |
| W96 | 254 (1.0566%) | 40 (0.2985%) | 1 (3.3333%) | 451 (1.9575%) | 241 (1.0025%) | **987 (1.1674%)** |
| W64 | 19 (0.0790%) | 0 (0.0000%) | 0 (0.0000%) | 92 (0.3993%) | 20 (0.0832%) | **131 (0.1549%)** |

![固定5集合の実行正解率](figures/looped_all_sizes/fixed_evaluation_pass_rate.svg)

既存1M通常3層の値は[既存BPE・3 epoch評価](boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch_results.md)から引用した。同じseed、tokenizer、訓練・評価集合を使うが、保存済み既存runとの比較であり、今回同時に再学習した対照ではない。

### 組合せ汎化ベンチマーク

訓練から隔離した固定13,400問の組合せ汎化集合を、通常・言い換え等と同じ正式評価で実行した。左図は既存モデルを含む全体比較、右図は今回のlooped 4モデルを2操作200問と3操作13,200問に分けた結果である。

![組合せ汎化ベンチマーク](figures/looped_all_sizes/compositional_generalization.svg)

| Model | 2操作 | 3操作 | 合計 |
|---|---:|---:|---:|
| LT1 | 67 / 200 (33.5000%) | 2,042 / 13,200 (15.4697%) | **2,109 / 13,400 (15.7388%)** |
| F128 | 24 / 200 (12.0000%) | 894 / 13,200 (6.7727%) | **918 / 13,400 (6.8507%)** |
| W96 | 0 / 200 (0.0000%) | 40 / 13,200 (0.3030%) | **40 / 13,400 (0.2985%)** |
| W64 | 0 / 200 (0.0000%) | 0 / 13,200 (0.0000%) | **0 / 13,400 (0.0000%)** |

既存の[9カテゴリ・872問の図](../report/figure/composition_benchmark/plot.svg)は、生成済み画像と集計値だけが現checkoutにあり、元の`questions`、`test_cases`、モデル別`scored.jsonl`、作図スクリプトは含まれていない。異なる13,400問の値を同じ棒へ混ぜると誤比較になるため、今回は実際に4モデルすべてを評価した固定組合せ汎化集合を、同じ横棒比較の見せ方で別図にした。元の872問を4モデルへ追加するには、`questions_sha256=aa119f...`と`test_cases_sha256=0090a3...`に対応する入力成果物が必要である。

### 生成の健全性

| Model | Syntax / Safe-AST / Signature valid | Exact code match | Timeout |
|---|---:|---:|---:|
| LT1 | 82,764 / 84,550 (97.8876%) | 18 | 0 |
| F128 | 72,781 / 84,550 (86.0804%) | 4 | 0 |
| W96 | 53,546 / 84,550 (63.3306%) | 1 | 464 |
| W64 | 79,408 / 84,550 (93.9184%) | 0 | 111 |

W64は構文・安全性・signatureを満たす生成が93.9%ある一方、実行正解は0.1549%だった。単なる構文崩壊だけではなく、意味的な操作選択・合成能力が失われている。W96は意味的不正解に加えて構文不正とtimeoutも多い。全モデル・全suiteで期待件数を評価し、各evaluation manifestのsuite statusはすべて`completed`である。

## 評価

1. **4候補内ではLT1が明確に最良。** 最終validation loss 0.761235、固定評価21.8604%で、parameter数と性能はこの範囲では単調だった。
2. **ただしLT1も採用不可。** 既存1M通常3層との差は77.6913 percentage pointsあり、58.1%のparameter削減と引き換えに実行能力の大半を失った。
3. **FFN・hidden幅の追加削減は急激に効く。** LT1からF128へのFFN縮小だけで総合pass@1は10.5003 points低下し、W96以下はほぼ実用能力を失った。
4. **validation lossだけでは採用判断できない。** 全モデルでlossは安定して低下したが、最終loss 0.761〜1.460の差以上に実行正解率の差が大きい。固定生成・実行評価を必須にする方針は妥当だった。
5. **loopの寄与自体はこの4サイズだけでは分離できない。** 同parameter数の通常1層対照（T1、F128-plain、W96-plain、W64-plain）を学習していないため、「反復が無い場合より良いか」は未判定である。次に構造効果を調べるなら、同容量の通常1層対照と入力再注入`add`を優先し、epoch追加は3 epoch主比較と分けて扱う。

## 成果物

- [実験manifest](../../data/models/looped_all_sizes_20261015/manifest.json)
- [図の元データ](figures/looped_all_sizes/values.json) / [再生成スクリプト](../../scripts/model/plot_looped_all_sizes_results.py)
- LT1: [学習manifest](../../data/models/looped_all_sizes_20261015/lt1_seed20260925/model/training_manifest.json) / [評価manifest](../../data/models/looped_all_sizes_20261015/lt1_seed20260925/evaluation/evaluation_manifest.json)
- F128: [学習manifest](../../data/models/looped_all_sizes_20261015/f128_seed20260925/model/training_manifest.json) / [評価manifest](../../data/models/looped_all_sizes_20261015/f128_seed20260925/evaluation/evaluation_manifest.json)
- W96: [学習manifest](../../data/models/looped_all_sizes_20261015/w96_seed20260925/model/training_manifest.json) / [評価manifest](../../data/models/looped_all_sizes_20261015/w96_seed20260925/evaluation/evaluation_manifest.json)
- W64: [学習manifest](../../data/models/looped_all_sizes_20261015/w64_seed20260925/model/training_manifest.json) / [評価manifest](../../data/models/looped_all_sizes_20261015/w64_seed20260925/evaluation/evaluation_manifest.json)

## 再現コマンド

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_looped_experiment.py \
  --output-root data/models/looped_all_sizes_20261015 \
  --variants lt1 f128 w96 w64 \
  --epochs 3 --seed 20260925 \
  --device cuda --dtype bfloat16 \
  --micro-batch-size 512 --gradient-accumulation-steps 1 \
  --run

uv run --group model-training --python 3.12.12 python \
  scripts/model/evaluate_boku_nano.py \
  --config data/models/looped_all_sizes_20261015/lt1_seed20260925/evaluation.yaml
```

F128、W96、W64も各ディレクトリの`evaluation.yaml`を同じ評価スクリプトへ渡した。W96とW64はsuite単位に並列実行してから`--resume`で全5 suiteのmanifestを再構築した。suiteごとの入力、greedy生成、timeout、検証条件は逐次実行と同一である。
