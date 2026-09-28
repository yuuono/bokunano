import {
  UNSUPPORTED_CNL,
  buildNormalizerSystemPrompt,
  buildNormalizerUserPrompt,
  validateCnl,
} from "./cnl.js";

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

async function generateCnl(messages) {
  const prompt = generator.tokenizer.apply_chat_template(messages, {
    tokenize: false,
    add_generation_prompt: true,
    enable_thinking: false,
  });
  const result = await generator(prompt, {
    max_new_tokens: 96,
    do_sample: false,
    repetition_penalty: 1.05,
    return_full_text: false,
  });
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
  const { instruction, manifest } = event.data;
  const startedAt = performance.now();
  let candidate = "";
  let validation = null;
  try {
    await loadGenerator(manifest);
    const messages = [
      { role: "system", content: buildNormalizerSystemPrompt() },
      { role: "user", content: buildNormalizerUserPrompt(instruction) },
    ];
    for (let attempt = 1; attempt <= 2; attempt += 1) {
      send("phase", { message: `QwenがCNLへ翻訳しています… (${attempt}/2)` });
      candidate = await generateCnl(messages);
      if (candidate === UNSUPPORTED_CNL) {
        send("result", {
          supported: false,
          cnl: candidate,
          attempts: attempt,
          elapsed_seconds: (performance.now() - startedAt) / 1000,
        });
        return;
      }
      validation = validateCnl(candidate);
      if (validation.valid) {
        send("result", {
          supported: true,
          cnl: validation.cnl,
          operations: validation.operations,
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
      cnl: candidate,
      error: validation?.error ?? "CNL検査に失敗しました。",
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
