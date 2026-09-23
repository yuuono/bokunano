# 2操作・3操作のPythonコード候補生成結果

2026年9月20日に、訓練用意味ASTと組合せ汎化テスト用意味ASTから、1意味AST当たり20件の検証済み固有コードを生成した。日本語指示はまだ生成していない。

## 生成件数

| 対象 | 操作数 | 意味AST | 1 AST当たり | 生成コード |
|---|---:|---:|---:|---:|
| 訓練 | 2 | 434 | 20 | 8,680 |
| 訓練 | 3 | 9,188 | 20 | 183,760 |
| 組合せ汎化テスト | 2 | 10 | 20 | 200 |
| 組合せ汎化テスト | 3 | 660 | 20 | 13,200 |
| 合計 |  | 10,292 |  | 205,840 |

全10,292件の意味ASTが20件へ到達した。不足した意味ASTは0件、不採用コードは0件だった。

## 参照インタプリタとの確認

各生成コードについて、境界値入力9件と固定seed 0のランダム入力32件、合計41件を実行した。同じ意味AST、`xs`、`k`で参照インタプリタを実行し、戻り値が完全一致することを確認した。

- 検証した生成コード: 205,840件
- 1コード当たりの入力: 41件
- 入出力比較: 8,439,440回
- 不一致: 0件
- 時間超過: 0件
- 入力リストを変更したコード: 0件
- 構文、安全性、関数シグネチャの不合格: 0件

検証は生成コードを隔離した別プロセス内で実行した。処理量が大きいため隔離プロセス自体は生成実行中に再利用したが、コードごとに新しい名前空間を使用し、コードごとの制限時間は従来どおり適用した。

## 完全重複の確認

各`code_hash`が`reference_code`のUTF-8バイト列に対するSHA-256と一致することを確認した。完全重複の判定では、ハッシュが一致する場合にコード全文も比較する。

| 確認範囲 | コード数 | 完全重複 |
|---|---:|---:|
| 訓練内（既存の1操作480件を含む） | 192,920 | 0 |
| 組合せ汎化テスト内 | 13,400 | 0 |
| 訓練と組合せ汎化テストの間 |  | 0 |

SHA-256衝突も0件だった。したがって、生成済みコードについて、訓練側と組合せ汎化テスト側のコード全文の積集合は空である。

再確認には次を使用する。

```bash
uv run --python 3.12.12 python scripts/validation/verify_multi_operation_code_candidates.py
```

## 設定

| 対象 | 設定JSON | SHA-256 |
|---|---|---|
| 組合せ汎化・2操作 | [`config/python_code_generation_compositional_two_operation.json`](../../config/python_code_generation_compositional_two_operation.json) | `1a58bc64af386da6275603c78223f0abbe354ef51a429d615497023ec95e28da` |
| 組合せ汎化・3操作 | [`config/python_code_generation_compositional_three_operation.json`](../../config/python_code_generation_compositional_three_operation.json) | `5678c36bea49eea637cce7b6926d7ca14c31b5d7b3552f7a64685a8700b191c5` |
| 訓練・2操作 | [`config/python_code_generation_train_two_operation.json`](../../config/python_code_generation_train_two_operation.json) | `b88956049fd13ce571242c9670fc3186c76bb924a2d61753504e4ed2bdf1e42f` |
| 訓練・3操作 | [`config/python_code_generation_train_three_operation.json`](../../config/python_code_generation_train_three_operation.json) | `e1273d62e6305c88bb37c3d47e644d2beb69706d88b7a7b83b07481546a83d8d` |

## 保存先

各ディレクトリに、採用コード`python_code_candidates.jsonl`、不採用記録`rejected_python_codes.jsonl`、件数と設定の記録`python_code_generation_stats.json`を保存した。

- `data/code_candidates/train/two_operation/`
- `data/code_candidates/train/three_operation/`
- `data/code_candidates/compositional/two_operation/`
- `data/code_candidates/compositional/three_operation/`

この20件は今回のコード生成目標であり、日本語指示を結合した最終訓練データの1意味AST当たりの採用上限ではない。

## Gitで管理するZIP

4つの`python_code_candidates.jsonl`は、次の1ファイルにまとめてGitで管理する。展開済みJSONLは`.gitignore`でGit管理対象から除外する。

| ZIP | 収録ファイル | 展開後の合計 | ZIPの大きさ | SHA-256 |
|---|---:|---:|---:|---|
| `data/archives/multi_operation_python_code_candidates_2026-09-20.zip` | 4 | 360,705,893バイト | 約32 MB | `369fb2175c715f15c6c7aeccd6d3ce96191404dac4537da8d72774e52d862a8e` |

収録件数は訓練192,440件、組合せ汎化テスト13,400件、合計205,840件である。展開方法は[`data/README.md`](../../data/README.md#2操作3操作コード候補のzip)に記載する。
