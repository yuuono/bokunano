#!/usr/bin/env bash

# 未定義変数、途中失敗、pipeline失敗を見逃さない。
set -euo pipefail

# script位置からclone先に依存しないリポジトリルートを求める。
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${script_dir}/../.." && pwd)"

# どの作業ディレクトリから呼ばれてもリポジトリルートで実行する。
cd "${repository_root}"

# 5M級1 epoch実験を既存の15M級モデルから分離して保存する。
experiment_name="boku_nano_5m_bpe_2048_1epoch"
config_path="config/${experiment_name}.yaml"
output_dir="data/models/${experiment_name}"
log_path="data/models/${experiment_name}_console.log"
pid_path="data/models/${experiment_name}.pid"

# Git管理外のmodel成果物ディレクトリを作る。
mkdir -p data/models

# 保存済みPIDのprocessが動作中なら二重起動を拒否する。
if [[ -f "${pid_path}" ]] && kill -0 "$(<"${pid_path}")" 2>/dev/null; then
  echo "5M級1 epoch学習は既に実行中です: PID $(<"${pid_path}")" >&2
  exit 1
fi

# 既存成果物を暗黙に上書きせず、別実験として保護する。
if [[ -d "${output_dir}" ]] && [[ -n "$(find "${output_dir}" -mindepth 1 -print -quit)" ]]; then
  echo "出力先が空ではありません: ${output_dir}" >&2
  echo "既存結果を退避するか、内容を確認してから削除してください。" >&2
  exit 1
fi

# tokenizer、入力ZIP、5,065,472 parameter構成を学習開始前に検査する。
uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config "${config_path}" \
  --validate-config

# 旧BPE 2,048語彙を使い、ランダム初期値からbackground学習する。
nohup uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config "${config_path}" \
  >"${log_path}" 2>&1 &

# 起動したuv processのPIDを監視用に保存する。
training_pid=$!
printf '%s\n' "${training_pid}" >"${pid_path}"

# 利用者へ成果物と監視先を表示する。
echo "5M級1 epoch学習を開始しました: PID ${training_pid}"
echo "出力: ${output_dir}"
echo "ログ: ${log_path}"
echo "確認: tail -f ${log_path}"
