# 検証・通常テスト・反復汎化のPythonコード候補生成結果

2026年9月20日に、検証、通常テスト、反復汎化の2操作・3操作ASTから、1意味AST当たり20件の検証済み固有コードを生成した。日本語指示と実行評価用のhidden入力はまだ生成していない。

## 生成件数

| 対象 | 操作数 | 意味AST | 1 AST当たり | 生成コード |
|---|---:|---:|---:|---:|
| 検証 | 2 | 54 | 20 | 1,080 |
| 検証 | 3 | 1,148 | 20 | 22,960 |
| 通常テスト | 2 | 54 | 20 | 1,080 |
| 通常テスト | 3 | 1,148 | 20 | 22,960 |
| 反復汎化 | 2 | 24 | 20 | 480 |
| 反復汎化 | 3 | 1,128 | 20 | 22,560 |
| 合計 |  | 3,556 |  | 71,120 |

全3,556件の意味ASTが20件へ到達した。不足した意味ASTは0件、不採用コードは0件だった。言い換えテストと境界値テストは通常テストと同じ意味ASTと正解コードを使うため、別のPythonコード候補は生成しない。

## 参照インタプリタとの確認

各生成コードについて、境界値入力9件と固定seed 0のランダム入力32件、合計41件を実行した。同じ意味AST、`xs`、`k`で参照インタプリタを実行し、戻り値が完全一致することを確認した。

- 今回検証したコード: 71,120件
- 今回の入出力比較: 2,915,920回
- 不一致: 0件
- 時間超過: 0件
- 入力リストを変更したコード: 0件
- 構文、安全性、関数シグネチャの不合格: 0件

## 全コード候補の完全重複確認

既存の訓練、組合せ汎化、単一操作を含む全277,440件について、`code_hash`を再計算し、ハッシュが一致する場合はコード全文を比較した。

| 集合 | コード数 | 集合内の完全重複 |
|---|---:|---:|
| 訓練（1操作を含む） | 192,920 | 0 |
| 検証 | 24,040 | 0 |
| 通常テスト | 24,040 | 0 |
| 組合せ汎化 | 13,400 | 0 |
| 反復汎化 | 23,040 | 0 |
| 合計 | 277,440 | 0 |

5集合の組み合わせ10通りをすべて比較し、集合間の完全一致も0件である。SHA-256衝突も0件だった。

再確認には次を使用する。

```bash
uv run python scripts/validation/verify_multi_operation_code_candidates.py
```

## 設定JSON

| 対象 | 操作数 | 設定JSON | SHA-256 |
|---|---:|---|---|
| 検証 | 2 | `config/python_code_generation_validation_two_operation.json` | `afffab3618775eae44992c04f833d2a3c752ce7d8cbd47384846f54cdafd1c25` |
| 検証 | 3 | `config/python_code_generation_validation_three_operation.json` | `29e2134486aa1b5ed197fca454553dc0140e30b034aeee6132c03bb6065b2dec` |
| 通常テスト | 2 | `config/python_code_generation_normal_two_operation.json` | `619efbc2653c2e9a3c6b39e035d2e6018d8b1d6499226a8bd6ba33cbada698dd` |
| 通常テスト | 3 | `config/python_code_generation_normal_three_operation.json` | `d82b908aa1fa25b8bcc0caeac1c0828124d306e0fee2affff5d4fa8ec8dda44c` |
| 反復汎化 | 2 | `config/python_code_generation_repetition_two_operation.json` | `e13fd663fb9b4ce50621df6b305d14c3805b1a03c4beb9dd4d488eca56c4e9d5` |
| 反復汎化 | 3 | `config/python_code_generation_repetition_three_operation.json` | `05b010ce81bf726bcebc3d6e5dc3c17c9a0c5379b3075e48f7703009f2cae6ea` |

## コード候補JSONL

| 対象 | 操作数 | SHA-256 |
|---|---:|---|
| 検証 | 2 | `6d8b36be75d7e4010f2b8fce7cc52c5ce0ad48cc7c4d0470ef83da831a6f38ca` |
| 検証 | 3 | `e7ac4974113c5f36b5eeb864c918a397c7744dfd538c040c0ba25eec8b7da379` |
| 通常テスト | 2 | `3a8dcefcd3652a2804caedb5db6801e2f67197a2b7ba27e68a2e54857a915aa8` |
| 通常テスト | 3 | `7a8da92106041a7eb542c5700b6351aedccb67f64b9faa8d46a3f4122c6567b3` |
| 反復汎化 | 2 | `79b775a8b8615ff3c5e1583fefcf990529bd6260740e507cb4613d52f1091828` |
| 反復汎化 | 3 | `3545e458038066ad8cf869cb2fcc38e7b545ee7c5e8c74ab9edd5bd0c15b4fce` |

各保存先には、コード候補`python_code_candidates.jsonl`、不採用記録`rejected_python_codes.jsonl`、件数と実行条件`python_code_generation_stats.json`を保存した。

- `data/code_candidates/validation/{two_operation,three_operation}/`
- `data/code_candidates/normal/{two_operation,three_operation}/`
- `data/code_candidates/repetition/{two_operation,three_operation}/`

今回の20件はコード生成目標であり、日本語指示を結合した最終データの1意味AST当たりの採用上限ではない。

## Gitで管理するZIP

6つの`python_code_candidates.jsonl`は、次の1ファイルにまとめてGitで管理する。展開済みJSONLは`.gitignore`でGit管理対象から除外する。

| ZIP | 収録ファイル | 展開後の合計 | ZIPの大きさ | SHA-256 |
|---|---:|---:|---:|---|
| `data/archives/evaluation_python_code_candidates_2026-09-20.zip` | 6 | 124,962,411バイト | 約11 MB | `5fcab861bcc6d69fb12758fb62325e02a00ab00e5da55db25c7b2e03134821d4` |

収録件数は検証24,040件、通常テスト24,040件、反復汎化23,040件、合計71,120件である。展開方法は[`data/README.md`](../../data/README.md#コード候補のzip)に記載する。
