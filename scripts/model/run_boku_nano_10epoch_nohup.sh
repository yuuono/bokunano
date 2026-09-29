#!/usr/bin/env bash

# 未定義変数、途中失敗、pipeline失敗を見逃さない。
set -euo pipefail

# script位置から共通ランナーの絶対パスを求める。
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# help指定ではこのscriptに必要なtokenizerオプションを表示する。
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  # 省略しないtokenizer名を使った実行形式を表示する。
  echo "使い方: $0 --tokenizer <bpe_2048_minfreq5_maxlen24|bpe_2048_minfreq2_maxlen8>"
  # 学習を開始せず正常終了する。
  exit 0
fi

# 現行15M級・10 epochを固定し、tokenizerオプションを共通ランナーへ渡す。
exec "${script_dir}/run_boku_nano_experiment_nohup.sh" \
  "$@" \
  --model-size 15m \
  --epochs 10
