# Boku1-nano

## Demo

[デモはこちらです](https://yuuono.github.io/bokunano/)

Boku1-nanoは、CNLから`solve(xs, k)`形式のPythonコードを生成する小規模なDecoder-only Transformerです。トークナイザとモデルをランダム初期値から学習しています。ブラウザ版は、左のQwen3-0.6Bが日本語から操作列を選び、検査・整形したCNLを右のBoku1-nanoへ渡すチャットUIです。既定は15M・1エポックで、8モデルから選べます。

両モデルの温度を独立して調整でき、0はgreedy、正の値はsamplingです。24種類・最大4操作に対応し、4操作は学習範囲（最大3操作）を超える実験として扱います。生成コードの正しさは確認が必要です。

- [課題仕様](boku1-nano.md)
- [全ドキュメント](docs/README.md)
- [3エポックモデル評価結果](docs/results/boku_nano_3epoch_evaluation_results.md)
