# Boku1-nano

## Demo

[デモはこちらです](https://yuuono.github.io/bokunano/)

Boku1-nanoは、CNLから`solve(xs, k)`形式のPythonコードを生成する小規模なDecoder-only Transformerです。トークナイザとモデルをランダム初期値から学習しています。ブラウザ版は、チャット内で指示を送り、Qwen3-0.6Bによる日本語の整理とBoku1-nanoのコード生成を続けて確認するベージュ基調のUIです。先頭には1〜4操作の文章例を表示し、入力した日本語をQwenで整理します。番号や箇条書きの形式差は吸収し、操作内容と順序を検査してCNLへ整形します。掲載例の操作列はQwenの出力検査にだけ使い、欠落・順序・数値が違えば理由を返して1回再試行します。2回とも失敗した場合はCNLを確定せず、アプリによる操作の補完は行いません。各回の実際のプロンプト・出力・検査結果を確認できます。既定は5M・1エポック・既存BPEで、設定ボタンから1M・3エポックの2種類を含む10モデルと温度を選べます。

両モデルの温度を独立して調整でき、0はgreedy、正の値はsamplingです。24種類・最大4操作に対応し、4操作は学習範囲（最大3操作）を超える実験として扱います。参照インタプリタによる実行・比較は公開デモから外しています。実行方式は[説明資料](docs/procedures/browser_reference_interpreter.md)に記録しています。

- [課題仕様](boku1-nano.md)
- [全ドキュメント](docs/README.md)
- [3エポックモデル評価結果](docs/results/boku_nano_3epoch_evaluation_results.md)
