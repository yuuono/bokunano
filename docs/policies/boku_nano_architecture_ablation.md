# 既存1M・5Mを基準とする構造ablation study

## 目的と比較方法

既存1M・5Mをそれぞれ基準にし、head数だけ、またはlayer数だけを変更して結果を比較する。各規模内ではd_modelとd_ffを固定する。全条件をランダム初期値から同じデータ・学習条件で学習する。

- head比較: layer数・d_model・d_ffを固定し、n_headsを基準4の半分2、基準4、倍の8にする。head_dimはd_model/n_headsとして連動し、総parameter数は変わらない。
- layer比較: head数・d_model・d_ffを固定し、n_layersを基準−1、基準、基準＋1にする。head_dimは変わらず、総parameter数は変わる。
- 各規模の基準構成は両比較で共用する。各5構成×2規模×1 seedで計10学習。

以前の `fixed_heads` / `fixed_layers` は、15Mから同じparameter予算に縮小するため幅・layer数・head数・FFN幅を複数変更していた。この比較で測れるのは構成全体の差で、head数やlayer数の変更による差を切り分けられないため、今回の実験から外す。名前も「何を変更するか」が分かるものに変更する。

## 実験表

1M・5Mは**基準モデルの名前**を示す。layer変更後のモデルを厳密な1M・5M予算に戻す調整は行わない。比較はそれぞれの `existing` を対照とし、1Mと5Mの間の差から単独の要因を推定しない。

|基準|条件名|変更点|d_model|layers|heads|head_dim|d_ff|実parameter数|
|---|---|---|---:|---:|---:|---:|---:|---:|
|15M|参考|既存15Mの設定|384|8|6|64|1024|15,735,168|
|1M|existing|基準|128|3|4|32|256|1,016,704|
|1M|heads_2|head数4→2|128|3|2|64|256|1,016,704|
|1M|heads_8|head数4→8|128|3|8|16|256|1,016,704|
|1M|layers_minus_1|layer数3→2|128|2|4|32|256|852,608|
|1M|layers_plus_1|layer数3→4|128|4|4|32|256|1,180,800|
|5M|existing|基準|256|5|4|64|704|5,065,472|
|5M|heads_2|head数4→2|256|5|2|128|704|5,065,472|
|5M|heads_8|head数4→8|256|5|8|32|704|5,065,472|
|5M|layers_minus_1|layer数5→4|256|4|4|64|704|4,262,144|
|5M|layers_plus_1|layer数5→6|256|6|4|64|704|5,868,800|

15Mの設定元は [`config/boku_nano_bpe_2048_1epoch.yaml`](../../config/boku_nano_bpe_2048_1epoch.yaml)。表に参考として残すが、今回の比較の対照でもrunnerの実行対象でもない。既存1M・5Mの設定元はそれぞれ [`config/boku_nano_1m_bpe_2048_1epoch.yaml`](../../config/boku_nano_1m_bpe_2048_1epoch.yaml)、[`config/boku_nano_5m_bpe_2048_1epoch.yaml`](../../config/boku_nano_5m_bpe_2048_1epoch.yaml)。

1Mの `heads_2` は、以前の「head_dim=64追加候補」と同一構成で、今回からrunnerの対象に含む。削除した「1M・8 layers・head_dim=64」構成は含めない。

15Mを含めた残りのmodel設定は次の通り。

|設定|共通値|
|---|---|
|vocab_size|2048|
|context_length|256|
|dropout|0.0|
|rope_base|10000.0|
|rms_norm_eps|1.0e-5|
|tie_word_embeddings|false（入力embeddingと出力層は非共有）|

語彙V=2048、幅d、layer数L、FFN幅fについて、総parameter数は `2Vd + L(4d² + 3df + 2d) + d`。現行実装ではこの式にhead数が入らない。runnerは実モデルを生成し、この式との一致を検査する。layerを1つ増減したときの差は1M基準で164,096、5M基準で803,328 parameters。

## 候補値の根拠と文献

以前の「幅24〜384」「FFNは8刻み」「2 ≤ d_ff/d_model ≤ 4」「予算差1%以内」は、予算合わせのために作成者が置いた探索条件であり、特定の論文から採用した範囲ではない。今回の設計には不要なので、自動探索と予算差による足切りを削除する。残る構造制約は実装上の正整数条件、d_modelがhead数で割り切れること、RoPE用のhead_dimが偶数であること等である。

参考文献は Vaswani et al. (2017), [Attention Is All You Need](https://papers.neurips.cc/paper/7181-attention-isall-you-need.pdf), §3.2.2・§6.2・Table 3。Table 3(A)ではhead数と各headのkey/value次元を連動させ、計算量を固定して比較している。Table 3(C)には他の設定を基準に揃えたlayer数の比較もある。本実験はこの「基準から変更項目を限定して比較する」考え方を参考にする。

今回のhead数2/4/8は既存head数4の半分・そのまま・倍、layer数は既存値の前後1層という、本リポジトリ用の局所比較である。論文がこの候補値を推奨したという意味ではなく、最適値探索でもない。論文のencoder-decoder Transformerと本モデルのdecoder-only・SwiGLU・RoPE構成は異なるため、論文の性能結果を本モデルへ直接適用しない。

## 統制条件と解釈

1 epoch、seed=20260925の1回に統一する。複数seedの反復は行わない。既存1Mの学習YAMLを複製し、表のmodel設定、期待parameter数、seed、epochs、出力先だけを変更する。基準1M・5Mについても同じ実行で再学習し、過去の別条件の重みと混ぜない。

tokenizerとtrain/validationの固定hash、語彙2048、context 256、非共有embedding、code+EOS loss、batch 512、AdamW、学習率・scheduler・dropout等を揃える。デフォルトtokenizerは `bpe_2048_minfreq5_maxlen24`。短いpiece版は `bpe_2048_minfreq2_maxlen8` を指定して全10条件を別出力先へ実行する。3 epochを調べる場合も全条件を揃える。

同じseedでデータ順序を揃えるが、構造の異なるモデルの初期重みが同じになることは保証しない。計算時間を固定する実験ではなく、データ提示量を揃える。head比較はhead_dimも連動するので「head分割」の比較と解釈する。layer比較では層数とともに容量・計算量も変わるため、それらを除いた深さだけの効果とは解釈しない。単一seedなのでseedに対する安定性・分散は評価しない。

## 実行

リポジトリルートから設定生成のみ（学習しない）:

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_architecture_ablation.py \
  --output-root data/models/architecture_ablation_plan
```

固定入力のhash・件数等も検証する場合は `--validate` を付ける。全条件を検証した後に順次学習する場合:

```bash
uv run --group model-training --python 3.12.12 python \
  scripts/model/run_boku_nano_architecture_ablation.py \
  --output-root data/models/architecture_ablation_run \
  --epochs 1 --seed 20260925 --run
```

`--sizes 5m --strategies existing heads_2 heads_8` で5Mのhead比較だけを実行できる。layer比較は `--strategies existing layers_minus_1 layers_plus_1` を使う。以前の `fixed_heads` / `fixed_layers` と複数値を受け取る `--seeds` は廃止する。旧方針の設定を使わず、新しく生成する。

出力先は毎回新規パスを指定する。既存ディレクトリは拒否し、失敗時は後続条件を停止する。途中再開・自動スキップは行わず、ログを確認して新しい出力先で条件を限定して再実行する。

出力は全条件の `manifest.json`、各条件の `config.yaml`、学習時の `console.log` と `model/` 以下の既存trainer成果物。manifestには実parameter数・構造・実行コマンドが残る。生成設定・重み・ログはpush対象に含めない。

## 評価と報告

全条件の最終epoch validation lossとperplexityを比較する。主指標は既存 `evaluate_boku_nano.py` による固定5集合（normal/compositional/paraphrase/repetition/boundary）の実行正解率。各model出力を指定し、生成条件・入力・件数・実行制限を揃える。runnerの自動化範囲は設定生成・入力検証・学習までで、生成評価は別途実行する。

各条件の単一seedの実測値と、同じ規模のexistingからの差を報告する。seed間の平均・標準偏差は計算しない。正解率は集合別、総正解数/総件数のmicro平均、5集合のmacro平均を区別する。parameter数、学習時間、生成速度、peak memoryも同一hardware・dtypeで記録する。

testの結果を見て候補値を調整しない。追加調整はvalidationだけを使用し、別実験として扱う。
