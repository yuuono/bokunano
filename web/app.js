import { BokuNanoTokenizer } from "./tokenizer.js";

const elements = {
  model: document.querySelector("#model"),
  example: document.querySelector("#example"),
  prompt: document.querySelector("#prompt"),
  generate: document.querySelector("#generate"),
  stop: document.querySelector("#stop"),
  output: document.querySelector("#output"),
  status: document.querySelector("#status"),
  metrics: document.querySelector("#metrics"),
};

const state = {
  manifest: null,
  tokenizer: null,
  sessions: new Map(),
  cancelled: false,
};

function setStatus(message, kind = "normal") {
  elements.status.textContent = message;
  elements.status.dataset.kind = kind;
}

function setBusy(busy) {
  elements.generate.disabled = busy;
  elements.model.disabled = busy;
  elements.example.disabled = busy;
  elements.prompt.disabled = busy;
  elements.stop.hidden = !busy;
}

function formatBytes(bytes) {
  return `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
}

async function fetchBytesWithProgress(path, expectedSize) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`モデルを取得できませんでした: ${response.status}`);
  if (!response.body) return new Uint8Array(await response.arrayBuffer());
  const total = Number(response.headers.get("content-length")) || expectedSize;
  const reader = response.body.getReader();
  const chunks = [];
  let received = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    const percentage = total ? Math.round((received / total) * 100) : 0;
    setStatus(`モデルを読み込んでいます… ${percentage}% (${formatBytes(received)})`);
  }
  const result = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}

async function createSession(model) {
  if (state.sessions.has(model.id)) return state.sessions.get(model.id);
  const bytes = await fetchBytesWithProgress(model.path, model.size_bytes);
  const canUseWebGpu = "gpu" in navigator;
  if (canUseWebGpu) {
    try {
      const session = await ort.InferenceSession.create(bytes, { executionProviders: ["webgpu"] });
      const result = { session, backend: "WebGPU" };
      state.sessions.set(model.id, result);
      return result;
    } catch (error) {
      console.warn("WebGPU初期化に失敗したためWASMへ切り替えます", error);
    }
  }
  const session = await ort.InferenceSession.create(bytes, { executionProviders: ["wasm"] });
  const result = { session, backend: "WASM" };
  state.sessions.set(model.id, result);
  return result;
}

function argmax(values) {
  let selectedIndex = 0;
  let selectedValue = values[0];
  for (let index = 1; index < values.length; index += 1) {
    if (values[index] > selectedValue) {
      selectedValue = values[index];
      selectedIndex = index;
    }
  }
  return selectedIndex;
}

async function generate() {
  const instruction = elements.prompt.value.trim();
  if (!instruction) {
    setStatus("日本語の指示を入力してください。", "error");
    elements.prompt.focus();
    return;
  }
  const model = state.manifest.models.find((item) => item.id === elements.model.value);
  state.cancelled = false;
  setBusy(true);
  elements.output.textContent = "";
  elements.metrics.textContent = "";
  const startedAt = performance.now();
  try {
    const promptIds = state.tokenizer.encodePrompt(instruction);
    if (promptIds.includes(state.manifest.special_token_ids.unk)) {
      throw new Error("入力にtokenizerで表現できない文字が含まれています。表現を変えてください。");
    }
    if (promptIds.length >= model.context_length) {
      throw new Error(`入力が長すぎます（${promptIds.length}/${model.context_length}トークン）。`);
    }
    const runtime = await createSession(model);
    const currentIds = [...promptIds];
    const generatedIds = [];
    const limit = Math.min(96, model.context_length - promptIds.length);
    setStatus(`${model.label}が${runtime.backend}で生成しています…`);
    for (let step = 0; step < limit && !state.cancelled; step += 1) {
      const input = new ort.Tensor(
        "int64",
        BigInt64Array.from(currentIds, (value) => BigInt(value)),
        [1, currentIds.length],
      );
      const outputs = await runtime.session.run({ input_ids: input });
      const tokenId = argmax(outputs.logits.data);
      if (tokenId === state.manifest.special_token_ids.eos) break;
      generatedIds.push(tokenId);
      currentIds.push(tokenId);
      elements.output.textContent = state.tokenizer.decode(generatedIds);
      if (step % 2 === 0) await new Promise(requestAnimationFrame);
    }
    const elapsedSeconds = (performance.now() - startedAt) / 1000;
    const rate = generatedIds.length / Math.max(elapsedSeconds, 0.001);
    elements.metrics.textContent = [
      runtime.backend,
      `入力 ${promptIds.length} tokens`,
      `生成 ${generatedIds.length} tokens`,
      `${elapsedSeconds.toFixed(2)}秒`,
      `${rate.toFixed(1)} tokens/s`,
    ].join(" / ");
    setStatus(
      state.cancelled ? "生成を中止しました。" : `${model.label}による生成が完了しました。`,
      state.cancelled ? "normal" : "success",
    );
  } catch (error) {
    console.error(error);
    setStatus(error instanceof Error ? error.message : String(error), "error");
  } finally {
    setBusy(false);
  }
}

async function initialize() {
  ort.env.wasm.wasmPaths = new URL("./vendor/", window.location.href).href;
  ort.env.wasm.numThreads = 1;
  const response = await fetch("./model-manifest.json");
  if (!response.ok) throw new Error("モデル一覧を取得できませんでした。");
  state.manifest = await response.json();
  state.tokenizer = await BokuNanoTokenizer.load(`./${state.manifest.tokenizer.path}`);
  for (const model of state.manifest.models) {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = `${model.label} (${formatBytes(model.size_bytes)})`;
    if (model.id === "10epoch") option.selected = true;
    elements.model.append(option);
  }
  elements.generate.disabled = false;
  elements.model.disabled = false;
  setStatus("モデルを選び、日本語の指示からコードを生成できます。", "success");
  window.__bokuNanoReady = true;
}

elements.generate.addEventListener("click", generate);
elements.stop.addEventListener("click", () => {
  state.cancelled = true;
});
elements.example.addEventListener("change", () => {
  if (elements.example.value) {
    elements.prompt.value = elements.example.value;
    elements.prompt.focus();
  }
});

initialize().catch((error) => {
  console.error(error);
  setStatus(error instanceof Error ? error.message : String(error), "error");
});
