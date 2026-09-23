# 単純操作の日本語表現候補生成結果

## 実行内容

2026年9月21日に、ローカルの`/home/ono_yusuke/Qwen3-4B-AWQ`を教師モデルとして使用し、24種類の単純操作ごとに30件、合計720件の日本語表現候補を生成した。各候補は、文末に置く`expression_ja`と、後続操作へつなぐ`connective_expression_ja`の組である。30件は各操作で最終的に20件以上を人間承認するための候補母数であり、全30件を採用するための生成ではない。

```bash
uv run --python 3.12.12 scripts/instruction_generation/generate_atomic_expression_candidates.py \
  --config config/qwen_atomic_expression_generation.json \
  --overwrite
```

モデルは`local_files_only=true`で読み込み、Hubへのモデル取得は行っていない。途中で残っていた旧条件の生成だけは利用者の指示で停止したが、それ以外の実行中スクリプトやプロセスには停止シグナルを送っていない。

実行時の環境は、現在`pyproject.toml`の`instruction-generation` dependency group、`uv.lock`、`.python-version`へ固定している。別環境では`uv sync --python 3.12.12 --group instruction-generation`で同じ直接依存・推移依存とPython 3.12.12を復元し、`uv run --group instruction-generation --python 3.12.12 python ...`で実行する。

## 候補の形式

一つの候補は次の二つを持つ。

```json
{
  "expression_ja": "偶数だけを残す",
  "connective_expression_ja": "偶数だけを残し"
}
```

- `expression_ja`: 最終操作として使う終止形。基本的に動詞の基本形で終える
- `connective_expression_ja`: 後続操作へつなぐ連用形またはて形。読点は含めない

プロンプトには「中国語の漢字や中国語表現を使わない」と記載した。個別の禁止文字は列挙しておらず、生成器にも中国語の禁止文字集合は持たせていない。生成後の日本語・意味・中国語混入の内容検査は行わず、720件を未承認候補として人間確認へ渡す。

## 実行環境

| 項目 | 値 |
|---|---|
| GPU | NVIDIA GeForce RTX 5090 |
| Python | 3.12.12（uv管理版） |
| PyTorch | 2.13.0 |
| Transformers | 4.51.3 |
| AutoAWQ | 0.2.9 |
| Accelerate | 1.15.0 |
| Triton | 3.7.1 |
| `model_id` | `Qwen/Qwen3-4B-AWQ` |
| `model_path` | `/home/ono_yusuke/Qwen3-4B-AWQ` |
| revision | `74d4bd2bd4bff9cafc9345221320bffb08b406a3` |
| 量子化 | AWQ 4-bit |
| `device_map` | `auto` |
| Attention実装 | `sdpa` |
| `trust_remote_code` | `false` |
| `local_files_only` | `true` |
| CUDA必須 | `true` |
| thinking | 無効（`enable_thinking=false`） |

AutoAWQ 0.2.9との互換性のためTransformersは4.51.3へ固定した。RTX 5090の`sm_120`に対応するためPyTorch 2.13.0を使用し、Tritonの実行時コンパイルに必要な`Python.h`を含むuv管理Python 3.12.12で実行した。

## 生成設定

| 項目 | 値 |
|---|---:|
| generator version | 3 |
| 1操作当たりの目標候補数 | 30組 |
| 1操作当たりの最大試行数 | 20 |
| 表現の最大文字数 | 80 |
| seed | 20260923 |
| `max_new_tokens` | 2048 |
| `temperature` | 0.9 |
| `top_p` | 0.95 |
| `top_k` | 50 |
| `repetition_penalty` | 1.1 |

- 設定SHA-256: `5f26325e1716a22a8f04abde97fca77101c86dd6a4aa29beeebb19b795712835`
- system prompt SHA-256: `a90f13a9a12ed4fd01709a24a74289f202a46970814c7b54bbc2bad75bc248c1`
- user prompt SHA-256: `a1a52c13541a7822745e1a2b5300cc78819b182175ac632f33ab47f3c6bb938c`

## 結果

- 対象操作: 24件
- 1操作当たりの候補: 30組
- 候補総数: 720件
- Qwen呼び出し回数: 150回
- 目標未達: 0操作
- 確認用CSV: ヘッダーを除いて720行
- 集計結果: `complete=true`、`failures=[]`

最初の実行では`atomic-000019`だけが21件で止まり、全体711件だった。候補本文を選別せず、`--resume`で既存711件を保持したまま不足9件だけを追加生成し、720件へ到達した。上記のQwen呼び出し回数150回は、最初の149回と追加生成1回の合計である。

内容の正しさをこちらでは検査していない。件数は生成器の完了表示と集計ファイルに記録された値である。

## 旧方式で人間確認から見つかった問題

接続形を持たない旧生成では、人間確認によって次の問題が見つかった。この記録は今回の720件を検査した結果ではなく、今回も人間確認が必要な理由を残すための履歴である。

- `k`以上に対して「`k`以下の値を除外する」とし、比較境界の意味が変わった
- `偶数だけを筛除する`、`每个数值减去k`など、中国語・簡体字が混入した
- `先端からk个取り出す`のように一部だけ簡体字が混入した
- 日本語以外の語や不自然な日本語が混入した

今回の候補は個別文字による自動除外をしていない。`expression_review.csv`で、意味の一致、日本語の自然さ、中国語の混入、終止形と接続形の対応を人が判断する。

## 出力ファイル

| ファイル | 内容 |
|---|---|
| `data/instruction_dictionaries/expression_candidates.jsonl` | 未承認の終止形・接続形候補720件 |
| `data/instruction_dictionaries/atomic_expression_raw_responses.jsonl` | 実際のプロンプトとQwen生応答100件 |
| `data/instruction_dictionaries/expression_review.csv` | 720件の人間確認用CSV |
| `data/instruction_dictionaries/atomic_expression_generation_stats.json` | モデル、sampling、seed、件数、生成日時 |

## 次の作業

[`expression_review.csv`](../../data/instruction_dictionaries/expression_review.csv)の各行について、`expression_ja`と`connective_expression_ja`の両方を確認する。必要なら`edited_expression_ja`と`edited_connective_expression_ja`へ修正案を記入し、`review_status`、`dictionary`、`reviewer`、`reviewed_at`を記録する。
