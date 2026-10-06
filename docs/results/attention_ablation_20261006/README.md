# 構造ablation 5モデルのattention可視化・因果診断

実施日: 2026年10月6日。全モデル1 epoch・学習seed 20260925・既存BPE・head_dim=64。追加5モデルの学習済み重みを同じ分析コードで解析した。

## 結果一覧

| モデル／図一覧 | parameters | 層×head | dev50 | 24操作診断 | BOS Value=0 | 日本語Value=0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [15M基準](existing/README.md) | 15,735,168 | 8×6 | 30/50 | 22/24 | 18/24 | 2/24 |
| [約9.5M・4 heads](heads_4_dim64/README.md) | 9,441,536 | 8×4 | 29/50 | 22/24 | 12/24 | 0/24 |
| [約5M・2 layers](layers_2/README.md) | 5,113,728 | 2×6 | 25/50 | 20/24 | 2/24 | 1/24 |
| [約8.7M・4 layers](layers_4/README.md) | 8,654,208 | 4×6 | 30/50 | 22/24 | 2/24 | 1/24 |
| [約12.2M・6 layers](layers_6/README.md) | 12,194,688 | 6×6 | 28/50 | 22/24 | 8/24 | 0/24 |

24操作の通常生成は20–22/24、日本語指示位置のValueを全層で無効化すると0–2/24だった。今回の診断では、全モデルで指示位置のValueが機能正解に強く関わっている。

BOS Value無効化の影響は構成によって異なる。BOSへのattentionが小さい／大きいという観察だけでは、その機能上の必要性を判断できない。

dev50は自然な日本語の開発用50問、24操作は学習時準拠文型の単独操作診断で、別の評価集合である。両者の得点を混ぜない。既存Qwen等との比較は[条件Aレポート](../browser_100/dev50_20261006_architecture_ablation.md)を参照。

## 指示参照とhead介入

| モデル | 日本語attention平均 | BOS attention平均 | 日本語attention最大head | ΔNLL最大head | ΔNLL | 同head除去後 | Spearman |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |
| 15M基準 | 29.08% | 8.67% | L3H5 | L1H5 | +0.138623 | 11/24 | 0.498 |
| 約9.5M・4 heads | 31.94% | 7.46% | L3H1 | L1H4 | +0.245706 | 11/24 | 0.542 |
| 約5M・2 layers | 25.98% | 8.50% | L2H3 | L1H1 | +0.122271 | 10/24 | 0.797 |
| 約8.7M・4 layers | 25.61% | 6.59% | L2H5 | L1H3 | +0.170581 | 15/24 | 0.723 |
| 約12.2M・6 layers | 28.37% | 8.04% | L2H1 | L1H4 | +0.243919 | 13/24 | 0.629 |

ΔNLLは各モデルが介入前に生成したtoken列を固定して教師強制したときの変化で、正解コードに対するNLLではない。EOSは対象外。モデルごとに生成列が異なるので、このNLLをモデル間の品質ランキングに用いない。Spearmanは同一モデル内の日本語attentionとhead除去ΔNLLの順位相関。最大headは同じ24操作で選択しているため、独立した汎化評価ではない。

日本語attention最大headとΔNLL最大headは必ずしも一致しない。参照量だけで重要度を判断せず、介入後の生成・実行結果も確認する。日本語Valueを0にする操作では各層の当該attention計算でKを直接変更しないが、下流層の状態や以後の生成は介入により変化する。

## Attention復元の数値検証

| モデル | attention行和 min–max | attention×Vと実出力の最大絶対誤差 |
| --- | --- | ---: |
| 15M基準 | 0.9999998–1.0000002 | 8.00e-07 |
| 約9.5M・4 heads | 0.9999999–1.0000001 | 4.20e-07 |
| 約5M・2 layers | 0.9999999–1.0000001 | 3.60e-07 |
| 約8.7M・4 layers | 0.9999998–1.0000001 | 3.60e-07 |
| 約12.2M・6 layers | 0.9999999–1.0000002 | 5.70e-07 |

## 方法・範囲

- 既存の `analyze_boku_nano_attention.py` と `analyze_boku_nano_attention_interpretability.py` を使用。解析はCPU・float32、各プロセス1 thread。学習は追加していない。
- 24操作は `single-operation-training-aligned-v1`。kなし／ありで外側文型を使い分け、固定33入力で機能判定。greedy、最大64 token。診断seedは20260930。訓練から独立した未見24問とは主張しない。
- 全headを1つずつout_proj直前で0化してNLL差・KL・argmax変化を測定。ΔNLL上位3 headと絶対変化の小さい3 headは、各々24操作を再生成して機能判定。
- BOSおよび日本語指示位置のValueを全層で0化し、24操作を再生成。BOSのattentionが大きいだけで無意味なsinkとは扱わない。
- 各モデル8図: head別参照傾向、BOS/Valueノルム、因果的ablation、rollout、step×位置、領域別attention、K/V類似度、token参照頻度。全40図を各モデルのMarkdownに直接表示。
- 単一プロンプトは全モデル同じ「xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。」。モデルごとの生成列が異なるため、図の同じ位置が同じtokenとは限らない。
- head数減では幅も連動し、layer数減では容量・計算量も変わる。単一seedの結果であり、サイズ以外の影響を排除した因果比較や統計的有意差は主張しない。

## 再実行

```bash
.venv/bin/python scripts/model/run_ablation_attention.py --output-root docs/results/attention_ablation_new_run
.venv/bin/python scripts/model/report_ablation_attention.py --output-root docs/results/attention_ablation_new_run
```

解析runnerは既存のモデル別出力先を上書きしない。reportスクリプトにも同じ出力先を指定する。各モデルのmanifest.jsonに重み・tokenizer・実行ソースのhash、実行コマンド、完了状態を保存した。
