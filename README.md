# Boku1-nano

## Demo

[デモはこちらです](https://yuuono.github.io/bokunano/)

Boku1-nanoは、CNLから`solve(xs, k)`形式のPythonコードを生成する小規模なDecoder-only Transformerです。トークナイザとモデルをランダム初期値から学習しています。ブラウザ版では、追加学習していないQwen3-0.6Bが自由な日本語をCNLへ翻訳し、検査済みCNLを3エポックまたは10エポックのBoku1-nanoへ渡します。

- [課題仕様](boku1-nano.md)
- [全ドキュメント](docs/README.md)
- [3エポックモデル評価結果](docs/results/boku_nano_3epoch_evaluation_results.md)
