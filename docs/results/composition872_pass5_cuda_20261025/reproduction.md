# カテゴリ別pass@1 / pass@5の再現手順

対象は発表資料の固定872問・9カテゴリ・179検査入力。モデル、tokenizer、問題、採点器のhashを検証してから実行する。旧greedy評価を候補1として再利用し、各問にsampling 4候補を追加する。学習・修復・候補の引き直しは行わない。

## 評価

リポジトリのルートで、CUDA対応PyTorchを導入済みの環境を使う。

```bash
.venv/bin/python scripts/model/evaluate_composition872_pass5.py \
  --greedy-run-roots \
    data/evaluations/composition872_cuda_20261025_baselines \
    data/evaluations/composition872_cuda_20261025_standard_extra \
    data/evaluations/composition872_cuda_20261025_short_bpe \
    data/evaluations/composition872_cuda_20261025_small_loops \
  --output-root data/evaluations/composition872_pass5_cuda_20261025 \
  --question-batch-size 8 \
  --score-workers 4
```

事前確認は同じ引数へ`--validate-only`を追加する。中断後は`--resume`を追加し、保存済みの生成・採点記録を検証して再開する。モデル名や生成条件を変えて同じ結果ディレクトリを使い回さない。

samplingはtemperature=0.8、top-p=0.95、seed=2026092607。各モデルの開始時にseedを設定し、prompt長ごと・元の問題順で8問×4候補を生成する。同じseedでもbatch形状、実装、環境が変われば同一の出力は保証されない。FP32、TF32無効、SDPA math、promptを含むcontext上限256 tokenを固定する。

pass@1はgreedyの1候補の合否。pass@5はそのgreedyを含む5候補のうち、**1候補以上が同じ179検査入力をすべて通過**した問題の割合。本リポジトリの既存定義を使っており、5候補すべてを同一sampling分布から抽選した推定量ではない。

## 保存物

各モデルの`raw_inference.jsonl`と`scored.jsonl`に候補別結果、`question_results.jsonl`に問題別pass@1/pass@5、`summary.json`にカテゴリ別集計を保存する。設定・実行環境・出典のhashも同じrunへ保存する。元のgreedy runは変更しない。

元greedy評価の復元手順と、生結果の保存場所は[greedy評価報告](../composition872_cuda_20261025/README.md)を参照。小型loop 4モデルの設定復元・middle4重み欠損に関する制約も引き継ぐ。

## 作図

全18モデルの評価完了後に実行する。未完了run、候補欠損、モデルや元greedyとの不一致、hash不一致は拒否する。

```bash
.venv/bin/python scripts/model/report_composition872_pass5.py
```

既定の出力先は`docs/results/figures/composition872_pass5_cuda_20261025/`。4系列のカテゴリ棒グラフと全18モデルのヒートマップをPNG・SVG・PDFで保存し、問題別合否を含む`values.json`とカテゴリ別の数値表`summary.md`を作成する。

## 検証

```bash
.venv/bin/python -m unittest \
  tests.test_evaluate_composition872_pass5 \
  tests.test_evaluate_boku_composition_torch \
  tests.test_evaluate_boku_composition_recovery
```

候補の順序と重複の保持、greedyの保存結果との一致、5候補の集計、採点再開とhash改変の拒否、軽量な採点子プロセス、元評価器・復元設定の検証を対象とする。
