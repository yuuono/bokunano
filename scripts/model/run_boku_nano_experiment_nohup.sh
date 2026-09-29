#!/usr/bin/env bash

# 未定義変数、途中失敗、pipeline失敗を見逃さない。
set -euo pipefail

# script位置からclone先に依存しないリポジトリルートを求める。
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${script_dir}/../.." && pwd)"

# どの作業ディレクトリから呼ばれてもリポジトリルートで実行する。
cd "${repository_root}"

# 全モデルで共通する明示的なオプションと候補値を表示する。
show_usage() {
  # 必須オプションの並びを表示する。
  printf '%s\n' "使い方: $0 --model-size <1m|5m|15m> --epochs <正の整数> --tokenizer <名前>"
  # 旧BPEの省略しない識別子を表示する。
  printf '%s\n' "  --tokenizer bpe_2048_minfreq5_maxlen24"
  # 短いpiece版BPEの省略しない識別子を表示する。
  printf '%s\n' "  --tokenizer bpe_2048_minfreq2_maxlen8"
}

# 必須値が指定されたかを後で検査できるよう空で初期化する。
model_size=""
epochs=""
tokenizer_name=""

# 名前付きオプションを順番に解析する。
while [[ $# -gt 0 ]]; do
  # 現在のオプション名に応じて値を保存する。
  case "$1" in
    # モデル規模を受け取る。
    --model-size)
      # 値が欠けている場合は後続参照前に拒否する。
      if [[ $# -lt 2 ]]; then
        # 欠落したオプション名を表示する。
        echo "--model-sizeの値がありません" >&2
        # コマンドラインの使い方の誤りとして終了する。
        exit 2
      fi
      # モデル規模を保存する。
      model_size="$2"
      # 読み終えたオプション名と値を除く。
      shift 2
      ;;
    # 学習epoch数を受け取る。
    --epochs)
      # 値が欠けている場合は後続参照前に拒否する。
      if [[ $# -lt 2 ]]; then
        # 欠落したオプション名を表示する。
        echo "--epochsの値がありません" >&2
        # コマンドラインの使い方の誤りとして終了する。
        exit 2
      fi
      # epoch数を保存する。
      epochs="$2"
      # 読み終えたオプション名と値を除く。
      shift 2
      ;;
    # tokenizer名を受け取る。
    --tokenizer)
      # 値が欠けている場合は後続参照前に拒否する。
      if [[ $# -lt 2 ]]; then
        # 欠落したオプション名を表示する。
        echo "--tokenizerの値がありません" >&2
        # コマンドラインの使い方の誤りとして終了する。
        exit 2
      fi
      # tokenizer名を保存する。
      tokenizer_name="$2"
      # 読み終えたオプション名と値を除く。
      shift 2
      ;;
    # help指定では学習せず使い方だけを表示する。
    -h|--help)
      # 標準出力へ使い方を表示する。
      show_usage
      # 正常終了として返す。
      exit 0
      ;;
    # 未対応オプションや位置引数を拒否する。
    *)
      # 不明な値を標準エラーへ表示する。
      printf '未対応のオプションです: %s\n' "$1" >&2
      # 正しい使い方も続けて表示する。
      show_usage >&2
      # コマンドラインの使い方の誤りとして終了する。
      exit 2
      ;;
  esac
done

# 三つの必須オプションがすべて指定されたことを確認する。
if [[ -z "${model_size}" || -z "${epochs}" || -z "${tokenizer_name}" ]]; then
  # 不足時は正しい使い方を標準エラーへ表示する。
  show_usage >&2
  # コマンドラインの使い方の誤りとして終了する。
  exit 2
fi

# epoch数を1以上の10進整数に限定する。
if [[ ! "${epochs}" =~ ^[1-9][0-9]*$ ]]; then
  # 不正な値を標準エラーへ表示する。
  printf -- '--epochsは正の整数にしてください: %s\n' "${epochs}" >&2
  # コマンドラインの使い方の誤りとして終了する。
  exit 2
fi

# モデル規模ごとに設定ファイルと表示情報を定義する。
case "${model_size}" in
  # 約1M parameterモデルを選ぶ。
  1m)
    # 旧BPE用設定を指定する。
    old_config="config/boku_nano_1m_bpe_2048_1epoch.yaml"
    # 短いpiece版BPE用設定を指定する。
    short_config="config/boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch.yaml"
    # tokenizerより前に付ける成果物名を指定する。
    experiment_prefix="boku_nano_1m"
    # 検証対象の実parameter数を表示用に保存する。
    parameter_count="1,016,704"
    ;;
  # 約5M parameterモデルを選ぶ。
  5m)
    # 旧BPE用設定を指定する。
    old_config="config/boku_nano_5m_bpe_2048_1epoch.yaml"
    # 短いpiece版BPE用設定を指定する。
    short_config="config/boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch.yaml"
    # tokenizerより前に付ける成果物名を指定する。
    experiment_prefix="boku_nano_5m"
    # 検証対象の実parameter数を表示用に保存する。
    parameter_count="5,065,472"
    ;;
  # 現行の約15M parameterモデルを選ぶ。
  15m)
    # 旧BPE用設定を指定する。
    old_config="config/boku_nano_bpe_2048.yaml"
    # 短いpiece版BPE用設定を指定する。
    short_config="config/boku_nano_bpe_2048_minfreq2_maxlen8_1epoch.yaml"
    # 既存成果物名との互換性を保つprefixを指定する。
    experiment_prefix="boku_nano"
    # 検証対象の実parameter数を表示用に保存する。
    parameter_count="15,735,168"
    ;;
  # 未対応のモデル規模を拒否する。
  *)
    # 不正な値を標準エラーへ表示する。
    printf '未対応のモデル規模です: %s\n' "${model_size}" >&2
    # 正しい候補も続けて表示する。
    show_usage >&2
    # コマンドラインの使い方の誤りとして終了する。
    exit 2
    ;;
esac

# tokenizer名から固定設定と説明表示を選ぶ。
case "${tokenizer_name}" in
  # 既存のBPE 2,048語彙を選ぶ。
  bpe_2048_minfreq5_maxlen24)
    # 旧BPE用の固定設定を使う。
    config_path="${old_config}"
    # 既存成果物との互換性を保つ保存名を設定する。
    artifact_tokenizer_name="bpe_2048"
    # 実行時の確認表示を設定する。
    tokenizer_label="既存のBPE 2,048語彙"
    # tokenizer訓練時の主要parameterを表示用に設定する。
    tokenizer_parameter_summary="vocab_size=2,048, min_frequency=5, max_token_length=24"
    ;;
  # 最小頻度2・最大piece長8のBPEを選ぶ。
  bpe_2048_minfreq2_maxlen8)
    # 短いpiece版BPE用の固定設定を使う。
    config_path="${short_config}"
    # tokenizer設定を含む保存名を設定する。
    artifact_tokenizer_name="bpe_2048_minfreq2_maxlen8"
    # 実行時の確認表示を設定する。
    tokenizer_label="最小頻度2・最大piece長8のBPE 2,048語彙"
    # tokenizer訓練時の主要parameterを表示用に設定する。
    tokenizer_parameter_summary="vocab_size=2,048, min_frequency=2, max_token_length=8"
    ;;
  # 省略名を含む未対応tokenizerを拒否する。
  *)
    # 不正な値を標準エラーへ表示する。
    printf '未対応のtokenizerです: %s\n' "${tokenizer_name}" >&2
    # 省略しない候補名を続けて表示する。
    show_usage >&2
    # コマンドラインの使い方の誤りとして終了する。
    exit 2
    ;;
esac

# モデル規模、tokenizer、epoch数を含む一意な実験名を作る。
experiment_name="${experiment_prefix}_${artifact_tokenizer_name}_${epochs}epoch"
# 実験名から出力先を作る。
output_dir="data/models/${experiment_name}"
# 実験名からconsole logの保存先を作る。
log_path="data/models/${experiment_name}_console.log"
# 実験名からPIDの保存先を作る。
pid_path="data/models/${experiment_name}.pid"

# Git管理外のmodel成果物ディレクトリを作る。
mkdir -p data/models

# 保存済みPIDのprocessが動作中なら同じ実験の二重起動を拒否する。
if [[ -f "${pid_path}" ]] && kill -0 "$(<"${pid_path}")" 2>/dev/null; then
  # 動作中のPIDを表示する。
  echo "学習は既に実行中です: PID $(<"${pid_path}")" >&2
  # 既存processを維持したまま終了する。
  exit 1
fi

# 既存成果物を暗黙に上書きせず、実験結果を保護する。
if [[ -d "${output_dir}" ]] && [[ -n "$(find "${output_dir}" -mindepth 1 -print -quit)" ]]; then
  # 空でない出力先を表示する。
  echo "出力先が空ではありません: ${output_dir}" >&2
  # 利用者が既存結果を確認するよう促す。
  echo "既存結果を退避するか、内容を確認してから削除してください。" >&2
  # 上書きせず終了する。
  exit 1
fi

# 選択したtokenizer、入力ZIP、モデルparameter数を学習開始前に検査する。
uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config "${config_path}" \
  --epochs "${epochs}" \
  --output-dir "${output_dir}" \
  --validate-config

# 選択した条件でランダム初期値からbackground学習する。
nohup uv run --group model-training --python 3.12.12 python \
  scripts/model/train_boku_nano.py \
  --config "${config_path}" \
  --epochs "${epochs}" \
  --output-dir "${output_dir}" \
  >"${log_path}" 2>&1 &

# 起動したuv processのPIDを監視用に保存する。
training_pid=$!
# PIDを一行のテキストとして書き込む。
printf '%s\n' "${training_pid}" >"${pid_path}"

# 利用者へ選択内容、成果物、監視先を表示する。
echo "${model_size}級・${epochs} epoch学習を開始しました: PID ${training_pid}"
echo "parameter数: ${parameter_count}"
echo "tokenizer: ${tokenizer_label}"
echo "tokenizer parameter: ${tokenizer_parameter_summary}"
echo "出力: ${output_dir}"
echo "ログ: ${log_path}"
echo "確認: tail -f ${log_path}"
