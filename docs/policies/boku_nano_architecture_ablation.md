# head_dim=64を固定したhead数・layer数の縮小比較

## 目的と比較方法

既存15Mを共通の起点にし、head_dim=64を固定してhead数を減らす構成と、layer数だけを減らす構成を比較する。d_ff=1024を全条件で固定する。head数を減らす場合は `d_model = n_heads × 64` として幅を連動させる。既存5Mは15Mから幅・layer数・head数・FFN幅を同時に変えた構成なので、この比較の対照には使わない。

- `existing`: 15Mの基準構成。
- `heads_4_dim64`: layer数8・head_dim64・FFN1024を固定し、head数6→4、幅384→256とする。総parameter数は9,441,536（約9.5M）になる。
- `layers_2`: head数6・幅384・FFN1024を固定し、layer数だけ8→2にする。head_dim=64を維持して5,113,728 parametersの約5Mを作る。

- `layers_4` / `layers_6`: head数6・幅384・FFN1024を固定し、layer数だけ8→4または8→6にする。

1 seedで計5学習。全条件をランダム初期値から同じデータ・学習条件で学習する。既存重みのpruningではない。

## 実験表

|条件名|d_model|layers|heads|head_dim|d_ff|実parameter数|
|---|---:|---:|---:|---:|---:|---:|
|existing（15M）|384|8|6|64|1024|15,735,168|
|heads_4_dim64（約9.5M）|256|8|4|64|1024|9,441,536|
|layers_2（約5M）|384|2|6|64|1024|5,113,728|
|layers_4（約8.7M）|384|4|6|64|1024|8,654,208|
|layers_6（約12.2M）|384|6|6|64|1024|12,194,688|

設定元は [`config/boku_nano_bpe_2048_1epoch.yaml`](../../config/boku_nano_bpe_2048_1epoch.yaml)。各変更行を同じ表の `existing` と比較する。head数とlayer数を同時に変更する行は設けない。

今回のhead縮小はhead_dimを64に固定するため、幅も縮小し、projection・embedding等の重みが減る。以前の「幅384を固定してhead数だけ6→4にする」構成とは異なる。head数4の構成名には「約9.5M」を用い、正確なparameter数は表の9,441,536を参照する。予算を合わせるためのlayer数やFFN幅の追加調整は行わない。

この固定条件では約1Mには届かない。head縮小は1 head・幅64まで減らしても1,967,168 parameters、layer縮小は1 layerまで減らしても3,343,488 parametersになる。1Mは幅やFFN等の変更を要する別実験として扱い、まず上の5構成を比較する。削除済みの「1M・8 layers・head_dim=64」候補は復活させない。

15Mを含めた残りのmodel設定は次の通り。

|設定|共通値|
|---|---|
|vocab_size|2048|
|context_length|256|
|dropout|0.0|
|rope_base|10000.0|
|rms_norm_eps|1.0e-5|
|tie_word_embeddings|false（入力embeddingと出力層は非共有）|

語彙V=2048、幅d、layer数L、FFN幅fについて、総parameter数は `2Vd + L(4d² + 3df + 2d) + d`。head数はこの式に直接は入らないが、今回は幅d=64×head数として連動するため、head数を減らすとparameter数も減る。runnerは実モデルを生成し、この式との一致を検査する。15Mでは1 layerあたり1,770,240 parametersで、8→2 layersにすると5,113,728 parametersになる。

## 候補値の根拠と文献

以前の「幅24〜384」「FFNは8刻み」「2 ≤ d_ff/d_model ≤ 4」「予算差1%以内」は、予算合わせのために作成者が置いた探索条件であり、特定の論文から採用した範囲ではない。今回の設計には不要なので、自動探索と予算差による足切りを削除する。残る構造制約は実装上の正整数条件、d_modelがhead数で割り切れること、RoPE用のhead_dimが偶数であること等である。

参考文献は Vaswani et al. (2017), [Attention Is All You Need](https://papers.neurips.cc/paper/7181-attention-isall-you-need.pdf), §3.2.2・§6.2・Table 3。Table 3(A)ではhead数と各headのkey/value次元を連動させ、計算量を固定して比較している。Table 3(C)には他の設定を基準に揃えたlayer数の比較もある。今回のhead縮小はhead_dimを固定して幅と計算量も減らすため、Table 3(A)の再現ではない。比較方法の関連文献として引用し、今回の固定条件を論文由来のものとは扱わない。

今回のhead数4は元の6から減らす比較候補として選び、ユーザー指定のhead_dim=64を維持する。幅256は4×64から決まる。layer数2は幅・FFN・head数を変えず約5Mになる整数層数として選ぶ。layer数4・6はユーザー指定の比較例として追加し、幅・FFN・head数は同様に固定する。論文がこの候補値を推奨したという意味ではなく、最適値探索でもない。論文のencoder-decoder Transformerと本モデルのdecoder-only・SwiGLU・RoPE構成は異なるため、論文の性能結果を本モデルへ直接適用しない。

## 統制条件と解釈

1 epoch、seed=20260925の1回に統一する。複数seedの反復は行わない。既存15Mの学習YAMLを複製し、表のmodel設定、期待parameter数、seed、epochs、出力先だけを変更する。基準15Mについても同じ実行で再学習し、過去の別条件の重みと混ぜない。

tokenizerとtrain/validationの固定hash、語彙2048、context 256、非共有embedding、code+EOS loss、batch 512、AdamW、学習率・scheduler・dropout等を揃える。デフォルトtokenizerは `bpe_2048_minfreq5_maxlen24`。短いpiece版は `bpe_2048_minfreq2_maxlen8` を指定して全5条件を別出力先へ実行する。3 epochを調べる場合も全条件を揃える。

同じseedでデータ順序を揃えるが、構造の異なるモデルの初期重みが同じになることは保証しない。計算時間を固定する実験ではなく、データ提示量を揃える。head比較はhead_dimを固定し、head数と幅が連動する縮小方針の比較と解釈する。幅や総容量を一定に保ったhead分割だけの効果とは解釈しない。layer比較では層数とともに容量・計算量も変わるため、それらを除いた深さだけの効果とは解釈しない。単一seedなのでseedに対する安定性・分散は評価しない。

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

約5Mのlayer変更構成だけを生成・学習する場合は `--strategies layers_2` を付ける。4・6 layersの例だけなら `--strategies layers_4 layers_6`、基準も含むlayer比較なら `--strategies existing layers_2 layers_4 layers_6` を使う。head_dim=64固定のhead縮小は `--strategies heads_4_dim64`、基準を含めたhead比較は `--strategies existing heads_4_dim64` を使う。`--sizes` は起点を表す `15m` のみを受け付ける。以前の1M・5M基準の条件と複数seed指定は対象外とし、旧方針の設定を使わず新しく生成する。旧条件名 `heads_4` は廃止し、幅384・head_dim96の旧成果物との混同を避ける。

出力先は毎回新規パスを指定する。既存ディレクトリは拒否し、失敗時は後続条件を停止する。途中再開・自動スキップは行わず、ログを確認して新しい出力先で条件を限定して再実行する。

出力は全条件の `manifest.json`、各条件の `config.yaml`、学習時の `console.log` と `model/` 以下の既存trainer成果物。manifestには実parameter数・構造・実行コマンドが残る。生成設定・重み・ログはpush対象に含めない。

## 評価と報告

全条件の最終epoch validation lossとperplexityを比較する。主指標は既存 `evaluate_boku_nano.py` による固定5集合（normal/compositional/paraphrase/repetition/boundary）の実行正解率。各model出力を指定し、生成条件・入力・件数・実行制限を揃える。runnerの自動化範囲は設定生成・入力検証・学習までで、生成評価は別途実行する。

各条件の単一seedの実測値と、15Mのexistingからの差を報告する。seed間の平均・標準偏差は計算しない。正解率は集合別、総正解数/総件数のmicro平均、5集合のmacro平均を区別する。parameter数、学習時間、生成速度、peak memoryも同一hardware・dtypeで記録する。

testの結果を見て候補値を調整しない。追加調整はvalidationだけを使用し、別実験として扱う。
