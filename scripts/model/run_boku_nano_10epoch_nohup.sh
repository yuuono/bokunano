#!/usr/bin/env bash

# 未定義変数、途中失敗、pipeline失敗を見逃さない。
set -euo pipefail

# script位置からclone先に依存しないリポジトリルートを求める。
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${script_dir}/../.." && pwd)"

# どの作業ディレクトリから呼ばれてもリポジトリルートで実行する。
cd "${repository_root}"

# 3 epoch正式結果と混在しない10 epoch専用出力を定義する。
output_dir="data/models/boku_nano_bpe_2048_10epoch"
log_path="data/models/boku_nano_bpe_2048_10epoch_console.log"
pid_path="data/models/boku_nano_bpe_2048_10epoch.pid"

# Git管理外のmodel成果物ディレクトリを作る。
mkdir -p data/models

# 同じscriptから起動したprocessが動作中なら二重起動を拒否する。
if [[ -f "${pid_path}" ]] && kill -0 "$(<"${pid_path}")" 2>/dev/null; then
  echo "10 epoch学習は既に実行中です: PID $(<"${pid_path}")" >&2
  exit 1
fi

# 既存成果物を暗黙に上書きせず、別実験として保護する。
if [[ -d "${output_dir}" ]] && [[ -n "$(find "${output_dir}" -mindepth 1 -print -quit)" ]]; then
  echo "出力先が空ではありません: ${output_dir}" >&2
  echo "既存結果を退避するか、内容を確認してから削除してください。" >&2
  exit 1
fi

# 全10 epoch用scheduleを最初から組み、nohupでbackground実行する。
nohup uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config config/boku_nano_bpe_2048.yaml \
  --epochs 10 \
  --output-dir "${output_dir}" \
  >"${log_path}" 2>&1 &

# 起動したuv processのPIDを監視用に保存する。
training_pid=$!
printf '%s\n' "${training_pid}" >"${pid_path}"

# 利用者へ監視先を表示する。
echo "10 epoch学習を開始しました: PID ${training_pid}"
echo "ログ: ${log_path}"
echo "確認: tail -f ${log_path}"
