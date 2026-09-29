#!/usr/bin/env bash

# 未定義変数、途中失敗、pipeline失敗を見逃さない。
set -euo pipefail

# script位置からclone先に依存しないリポジトリルートを求める。
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repository_root}"

# 短いpiece用BPEによる1 epoch実験を、既存モデルから分離して保存する。
experiment_name="boku_nano_bpe_2048_minfreq2_maxlen8_1epoch"
output_dir="data/models/${experiment_name}"
log_path="data/models/${experiment_name}_console.log"
pid_path="data/models/${experiment_name}.pid"
config_path="config/boku_nano_bpe_2048_minfreq2_maxlen8_1epoch.yaml"

mkdir -p data/models

# 保存済みPIDが実行中なら二重起動を拒否する。
if [[ -f "${pid_path}" ]] && kill -0 "$(<"${pid_path}")" 2>/dev/null; then
  echo "1 epoch学習は既に実行中です: PID $(<"${pid_path}")" >&2
  exit 1
fi

# 既存成果物を暗黙に上書きしない。
if [[ -d "${output_dir}" ]] && [[ -n "$(find "${output_dir}" -mindepth 1 -print -quit)" ]]; then
  echo "出力先が空ではありません: ${output_dir}" >&2
  echo "既存結果を退避するか、内容を確認してから削除してください。" >&2
  exit 1
fi

# 専用YAMLに固定した1 epoch scheduleで、ランダム初期値からbackground学習する。
nohup uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config "${config_path}" \
  >"${log_path}" 2>&1 &

training_pid=$!
printf '%s\n' "${training_pid}" >"${pid_path}"

echo "短いpiece用BPEの1 epoch学習を開始しました: PID ${training_pid}"
echo "出力: ${output_dir}"
echo "ログ: ${log_path}"
echo "確認: tail -f ${log_path}"
