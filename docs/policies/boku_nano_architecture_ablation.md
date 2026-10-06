# 1M・5M構造縮小方針のablation study

## 目的と比較の意味

現行15M（d_model=384、8 layers、6 heads、d_ff=1024、15,735,168 parameters）を共通の設計上の起点とし、約1M・約5Mへ縮小する際の制約を比較する。既存重みのpruningや追加学習ではなく、全条件をランダム初期値から学習する。

- `fixed_heads`: 6 headsを維持。1Mは3 layers、5Mは5 layersとし、幅とFFNを縮小する。
- `fixed_layers`: 8 layersを維持。1Mは2 heads、5Mは4 headsとし、幅とFFNを縮小する。
- `existing`: 現行1M・5M構成を同じ学習条件で再学習する対照群。

この実装のQKV・出力projectionはd_modelで決まるため、head数だけを減らしても総parameter数は減らない。15Mの幅384を維持すると非共有embeddingだけで1,572,864 parametersあり、layer数だけの削減では1Mに到達できない。したがって、これは「縮小方針」の比較であり、head数・layer数単独の因果効果を測る実験ではない。head_dimとFFN比率も変化する。

## 実験表

|規模|方針|d_model|layers|heads|head_dim|d_ff|実parameter数|
|---|---|---:|---:|---:|---:|---:|---:|
|1M|existing|128|3|4|32|256|1,016,704|
|1M|fixed_heads|120|3|6|20|328|1,019,400|
|1M|fixed_layers|88|8|2|44|192|1,015,256|
|5M|existing|256|5|4|64|704|5,065,472|
|5M|fixed_heads|228|5|6|38|904|5,067,756|
|5M|fixed_layers|192|8|4|48|672|5,065,920|

予算は既存構成の実数に合わせる。候補は幅24〜384、偶数head_dim、FFNは8刻み、2 ≤ d_ff/d_model ≤ 4。予算との絶対差を最優先し、同率ではFFN比率8/3への近さ、その後は幅・head数・FFN幅の昇順で決定する。性能評価を使って構造を選ばない。予算差1%超は実行前に拒否する。

語彙V=2048、幅d、layer数L、FFN幅fについて、総数は `2Vd + L(4d² + 3df + 2d) + d`。スクリプトは実モデルを生成し、この式との一致も検査する。

## 統制条件

既存1MのYAMLを複製し、model、期待parameter数、seed、epochs、出力先だけを変更する。tokenizerとtrain/validationの固定hash、語彙2048、context 256、非共有embedding、code+EOS loss、batch 512、AdamW、学習率・scheduler・dropout等は全構成で揃える。

主実験は1 epoch、seed=20260925/20260926/20260927の3反復、2規模×3方針×3 seed=18学習。比較単位は同一tokenizer・同一epoch数・同一seed。初期化で消費する乱数は構造で異なるため、同じseedでも同じ重みにはならない。固定データ順序を同じseedで比較する。計算時間を揃える実験ではなく、データ提示量を揃える実験とする。

デフォルトtokenizerは `bpe_2048_minfreq5_maxlen24`。短いpiece版を調べる場合は `bpe_2048_minfreq2_maxlen8` で全18条件を別の出力先に実行し、tokenizer間の結果を混ぜない。3 epochを調べる場合も全条件を揃え、既存1Mの3 epochと5Mの1 epochを直接比較しない。

## 実行

リポジトリルートから、設定生成のみ（学習しない）:

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
  --epochs 1 --seeds 20260925 20260926 20260927 --run
```

`--sizes 1m`、`--strategies fixed_heads fixed_layers` で部分実行できる。出力先は毎回新規パスを指定する。既存ディレクトリは拒否し、学習失敗時は後続条件を停止する。途中再開・完了条件の自動スキップは行わない。失敗した条件はログを確認し、新しい出力先で条件を限定して再実行する。

出力は全条件の `manifest.json`、各条件の `config.yaml`、学習時の `console.log` と `model/` 以下の既存trainer成果物。manifestには実parameter数・構造・実行コマンド、trainer成果物には固定入力hash・環境・metricsが残る。出力先が異なるrunの混同を避けるため、集計ではtokenizer・epochs・seedも確認する。生成設定・重み・ログは今回のpush対象に含めない。

## 評価と報告

まず全条件の最終epoch validation lossとperplexityを比較する。主指標は既存 `evaluate_boku_nano.py` による固定5集合（normal/compositional/paraphrase/repetition/boundary）の実行正解率。既存評価設定を各model出力へ合わせ、生成条件・入力・件数・実行制限を揃えて評価する。今回のrunnerの自動化範囲は設定生成・入力検証・学習までで、生成評価は別途実行する。

各規模・方針ごとに3 seedの個別値、平均、標本標準偏差を報告し、同じseedでの方針間差も示す。正解率は集合別に加え、総正解数/総件数のmicro平均と5集合のmacro平均を区別する。parameter数、学習時間、生成速度、peak memoryも同一hardware・dtypeで記録する。少数seedの小差を優劣と断定しない。

testの結果を見てFFN幅・学習率等を調整しない。追加調整はvalidationだけを使用し、別実験として扱う。15Mは設計上の起点であり、学習済み15Mとの数値比較を行う場合は同じtokenizer・epochs・seedで改めて統制する。
