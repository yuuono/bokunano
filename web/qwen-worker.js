import { translateWithRetry } from "./qwen-translation.js?v=25";
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
  let phase = "loading";
  try {
    await loadGenerator(manifest);
    phase = "generation";
    const result = await translateWithRetry({
      instruction, contextCnl, contextK, selection,
      generate: async (messages, attempt) => {
        send("phase", { message: `Qwenが指示の操作を整理しています… (${attempt}/2)` });
        return generatePlan(messages, temperature, attempt);
      },
      onAttempt: detail => send("attempt-result", detail),
    });
    send("result", { ...result, elapsed_seconds: (performance.now() - startedAt) / 1000 });
  } catch (error) {
    send("error", { phase, message: error instanceof Error ? error.message : String(error) });
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
