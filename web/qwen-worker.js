import { resolveSelection, reconcileSelection } from "./chat-utils.js?v=10";
import {
  UNSUPPORTED_CNL,
  buildConversationMessages,
  buildNormalizerUserPrompt,
  validateOperationPlan,
} from "./cnl.js?v=12";
import { qwenSamplingOptions } from "./sampling.js";

let generator = null;

function send(type, payload = {}) {
  self.postMessage({ type, ...payload });
}

function extractGeneratedText(result) {
  const generated = result?.[0]?.generated_text;
  if (typeof generated === "string") return generated.trim();
  if (Array.isArray(generated)) {
    const assistant = [...generated].reverse().find((item) => item?.role === "assistant");
    if (typeof assistant?.content === "string") return assistant.content.trim();
  }
  throw new Error("Qwenの生成結果を文字列として取得できませんでした。");
}

function formatProgress(progress) {
  const percentage = Number(progress?.progress);
  return {
    status: progress?.status ?? "loading",
    file: progress?.file ?? "",
    percentage: Number.isFinite(percentage) ? Math.round(percentage) : null,
    loaded: Number(progress?.loaded) || null,
    total: Number(progress?.total) || null,
  };
}

async function loadGenerator(manifest) {
  send("phase", { message: "Qwen実行環境を読み込んでいます…" });
  const { env, pipeline } = await import(manifest.transformers_js_url);
  env.allowLocalModels = false;
  env.allowRemoteModels = true;
  env.useBrowserCache = true;
  generator = await pipeline("text-generation", manifest.model_id, {
    revision: manifest.revision,
    dtype: manifest.dtype,
    device: manifest.device,
    progress_callback: (progress) => send("progress", formatProgress(progress)),
  });
}

async function generatePlan(messages, temperature, attempt) {
  const prompt = generator.tokenizer.apply_chat_template(messages, {
    tokenize: false,
    add_generation_prompt: true,
    enable_thinking: false,
  });
  const options = {
    max_new_tokens: 192,
    ...qwenSamplingOptions(temperature),
    repetition_penalty: 1.05,
    return_full_text: false,
  };
  send("prompt", { attempt, messages, prompt, options });
  const result = await generator(prompt, options);
  return extractGeneratedText(result);
}

async function disposeGenerator() {
  if (generator && typeof generator.dispose === "function") {
    await generator.dispose();
  }
  generator = null;
}

self.addEventListener("message", async (event) => {
  if (event.data?.type !== "translate") return;
  const { instruction, manifest, contextCnl = "", contextK = null, temperature = 0, selection = null } = event.data;
  const startedAt = performance.now();
  let candidate = "";
  let validation = null;
  try {
    await loadGenerator(manifest);
    const selected = resolveSelection(instruction, selection);
    const messages = buildConversationMessages(instruction, contextCnl, contextK, Boolean(selected));
    if (selected) {
      messages[0].content = `利用者が選んだ操作を、日本語の操作名として確認してください。説明は不要です。
次の${selected.operations.length}操作をこの順番で全て出力してください。他の操作は追加しません。
${selected.operations.map(op => op.label).join("\n")}
${selected.usesK && selected.kValue !== null ? `数値: k=${selected.kValue}` : "数値の補足は不要です。"}`;
    }
    const maxAttempts = selected ? 1 : 2;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      send("phase", { message: `Qwenが指示の操作を整理しています… (${attempt}/${maxAttempts})` });
      candidate = await generatePlan(messages, temperature, attempt);
      if (!selected && candidate === UNSUPPORTED_CNL) {
        send("result", {
          supported: false,
          cnl: candidate,
          attempts: attempt,
          elapsed_seconds: (performance.now() - startedAt) / 1000,
        });
        return;
      }
      validation = validateOperationPlan(candidate);
      // Qwen always runs. Explicit UI choices remain authoritative if it drifts.
      validation = reconcileSelection(validation, selected);
      if (validation.valid) {
        send("result", {
          supported: true,
          cnl: validation.cnl,
          operations: validation.operations,
          kValue: validation.kValue,
          plan: candidate,
          selectionRecovered: validation.selectionRecovered,
          attempts: attempt,
          elapsed_seconds: (performance.now() - startedAt) / 1000,
        });
        return;
      }
      messages.push({ role: "assistant", content: candidate });
      messages.push({
        role: "user",
        content: buildNormalizerUserPrompt(instruction, candidate, validation.error),
      });
    }
    send("result", {
      supported: false,
      cnl: "",
      plan: candidate,
      error: "Qwenが指示を整理できませんでした。表現を変えるか、操作を選んで再送信してください。",
      diagnostic: validation?.error,
      attempts: 2,
      elapsed_seconds: (performance.now() - startedAt) / 1000,
    });
  } catch (error) {
    send("error", { message: error instanceof Error ? error.message : String(error) });
  } finally {
    try {
      await disposeGenerator();
    } catch (error) {
      console.warn("Qwenの解放中にエラーが発生しました", error);
    }
    send("released");
    self.close();
  }
});
