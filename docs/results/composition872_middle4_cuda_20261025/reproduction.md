# 1M・3 epochのmiddle4 2モデル：CUDA評価の再現手順

2026-10-25、`origin/main`の`2cefb4a`を取り込み、同コミットに追加された最終重み・構造設定・学習完了manifestを使用。既存のローカル変更は保持した。

## 今回新しく評価するモデル

| 評価ID | 保存variant | parameters | epoch |
|---|---|---:|---:|
| `middle4-1m-3epoch` | `u3_middle4` | 1,016,704 | 3 |
| `middle4-scaled025-1m-3epoch` | `u3_middle4_scaled025` | 1,016,704 | 3 |

既存通常モデル・小型loopは検証済みの保存結果を再利用する。ユーザー指定により1M・1 epochは再実行せず、新しい比較図からも除外する。

## Greedy：pass@1

リポジトリのルートで、CUDA版PyTorchを導入した環境を使う。

```bash
.venv/bin/python scripts/model/evaluate_boku_composition_torch.py \
  --models middle4-1m-3epoch middle4-scaled025-1m-3epoch \
  --output-root data/evaluations/composition872_cuda_20261025_middle4 \
  --batch-size 32 \
  --score-workers 4
```

実行前のhash・設定確認のみなら`--validate-only`を付ける。実行時は新規出力先が必要。

## 追加4候補：pass@5

```bash
.venv/bin/python scripts/model/evaluate_composition872_pass5.py \
  --greedy-run-roots data/evaluations/composition872_cuda_20261025_middle4 \
  --expected-model-count 2 \
  --output-root data/evaluations/composition872_pass5_cuda_20261025_middle4 \
  --question-batch-size 8 \
  --score-workers 4
```

事前確認は`--validate-only`、中断した追加候補の評価は`--resume`で再開する。既存の18モデル評価を再実行する必要はない。

前報と同じ固定872問・9カテゴリ・179検査入力、旧採点器、PyTorch FP32、TF32無効、SDPA math、context合計256 token。samplingはtemperature 0.8、top-p 0.95、seed 2026092607、8問×4候補の同長バッチ。pass@5はgreedy 1候補とsampling 4候補のうち1つ以上が全179入力を通過した割合。

## モデルの同定

- `u3_middle4`の重みSHA-256：`2fd1210f240f7f128b4f2219b7f6e4a8eb245fd39478935b5c5258ed4110b89e`
- `u3_middle4_scaled025`の重みSHA-256：`9dae44c77216f40f43a0d6fd6c08aa11565497b3669a5ab5611975646de4e587`

各modelディレクトリの元`training_manifest.json`で、完了状態、3 epoch・1,131更新、seed 20260925、重みhashを照合する。構造は3物理層・幅128・FFN256・4 heads・embedding非共有・中間層4回であり、反復部分の残差倍率のみ1.0と0.25。今回の2モデルには構造設定の復元は必要ない。

## 既存結果との統合・作図

```bash
.venv/bin/python scripts/model/report_composition872_pass5_extended.py
```

既存18モデルのsampling runと今回の2モデルrunを、それぞれ元greedy runへ照合してから統合する。推論は行わない。標準/短いBPEの1M・1 epochは元記録を保持したまま表示から除外し、18モデルを`docs/results/figures/composition872_pass5_cuda_20261025_with_middle4/`へ出力する。既存出力先は上書きしない。

主要図は`categories_1m_3epoch`で、通常1M・3 epochと今回の2モデルを9カテゴリ別に比較する。旧分類関数が同じ幅の小型LT1とmiddle4を混同しないよう、統合表示側でmiddle構造・残差倍率・学習完了記録を検証して表示名を付ける。評価本体と旧作図スクリプトは変更しない。

```bash
.venv/bin/python -m unittest \
  tests.test_evaluate_boku_composition_torch \
  tests.test_evaluate_composition872_pass5 \
  tests.test_report_composition872_pass5_extended
```
