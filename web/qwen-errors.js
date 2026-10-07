// Runtime failures happen before or during inference, not during CNL validation.
export function qwenRuntimeFailure(message, phase = "runtime", label = "Qwen") {
  if (/bad_alloc|out of memory|memory allocation|cannot allocate/i.test(String(message))) {
    return `${label}の実行に必要なメモリを確保できませんでした。設定で小さいモデルを選ぶか、他のタブを閉じて再試行してください。`;
  }
  if (phase === "loading") {
    return `${label}を読み込めませんでした。通信状況を確認して再試行してください。詳しい原因は「処理の詳細」に表示しています。`;
  }
  return `${label}の実行中にエラーが発生しました。もう一度送信してください。詳しい原因は「処理の詳細」に表示しています。`;
}
