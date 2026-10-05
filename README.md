# Boku1-nano

## Demo

[デモはこちらです](https://yuuono.github.io/bokunano/)

Boku1-nanoは、CNLから`solve(xs, k)`形式のPythonコードを生成する小規模なDecoder-only Transformerです。トークナイザとモデルをランダム初期値から学習しています。ブラウザ版は、チャット内で指示を送り、Qwen3-0.6Bによる日本語の整理とBoku1-nanoのコード生成を続けて確認する白背景のUIです。操作を検索・選択して入力することもでき、確定した操作列はQwenで再変換せずCNLへ整形します。既定は15M・1エポックで、1M・3エポックの2種類を含む10モデルから選べます。

両モデルの温度を独立して調整でき、0はgreedy、正の値はsamplingです。24種類・最大4操作に対応し、4操作は学習範囲（最大3操作）を超える実験として扱います。生成コードの正しさは確認が必要です。

- [課題仕様](boku1-nano.md)
- [全ドキュメント](docs/README.md)
- [3エポックモデル評価結果](docs/results/boku_nano_3epoch_evaluation_results.md)
