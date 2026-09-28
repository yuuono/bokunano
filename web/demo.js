import { BokuNanoTokenizer } from "./tokenizer.js";
import {
  buildNormalizerSystemPrompt,
  buildNormalizerUserPrompt,
  validateCnl,
} from "./cnl.js";

const elements = {
  model: document.querySelector("#model"),
  prompt: document.querySelector("#prompt"),
  translate: document.querySelector("#translate"),
  cancelTranslation: document.querySelector("#cancel-translation"),
  translationStatus: document.querySelector("#translation-status"),
  translationMetrics: document.querySelector("#translation-metrics"),
  cnl: document.querySelector("#cnl"),
  validateCnl: document.querySelector("#validate-cnl"),
  cnlStatus: document.querySelector("#cnl-status"),
  operationList: document.querySelector("#operation-list"),
  generate: document.querySelector("#generate"),
  stop: document.querySelector("#stop"),
  output: document.querySelector("#output"),
  status: document.querySelector("#status"),
  metrics: document.querySelector("#metrics"),
  exampleButtons: document.querySelectorAll("[data-example-prompt]"),
  normalizerSystemPrompt: document.querySelector("#normalizer-system-prompt"),
  normalizerInitialPrompt: document.querySelector("#normalizer-initial-prompt"),
  normalizerRetryPrompt: document.querySelector("#normalizer-retry-prompt"),
};

elements.normalizerSystemPrompt.textContent = buildNormalizerSystemPrompt();
elements.normalizerInitialPrompt.textContent = buildNormalizerUserPrompt("{ユーザー入力}");
elements.normalizerRetryPrompt.textContent = buildNormalizerUserPrompt(
  "{元のユーザー入力}",
  "{検査に失敗したQwen出力}",
  "{JavaScript検査器が返した理由}",
);

const state = {
  manifest: null,
  qwenManifest: null,
  tokenizer: null,
  sessions: new Map(),
  qwenWorker: null,
  translationBusy: false,
  generationBusy: false,
  cancelled: false,
  cnlValidation: null,
};

function setMessage(element, message, kind = "normal") {
  element.textContent = message;
  element.dataset.kind = kind;
}

function formatBytes(bytes) {
  return `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
}

function updateControls() {
  const ready = Boolean(state.manifest && state.tokenizer);
  elements.translate.disabled = !ready || !state.qwenManifest || state.translationBusy || state.generationBusy;
  elements.cancelTranslation.hidden = !state.translationBusy;
  elements.prompt.disabled = state.translationBusy || state.generationBusy;
  elements.cnl.disabled = state.translationBusy || state.generationBusy;
  elements.validateCnl.disabled = state.translationBusy || state.generationBusy;
  elements.model.disabled = !ready || state.translationBusy || state.generationBusy;
  elements.generate.disabled =
    !ready ||
    state.translationBusy ||
    state.generationBusy ||
    !state.cnlValidation?.valid;
  elements.stop.hidden = !state.generationBusy;
  for (const button of elements.exampleButtons) {
    button.disabled = state.translationBusy || state.generationBusy;
  }
}

function renderOperations(operations) {
  elements.operationList.replaceChildren();
  for (const [index, operation] of operations.entries()) {
    const item = document.createElement("li");
    item.textContent = `${index + 1}. ${operation.label}`;
    elements.operationList.append(item);
  }
}

function checkCnl() {
  const validation = validateCnl(elements.cnl.value);
  state.cnlValidation = validation;
  if (validation.valid) {
    elements.cnl.value = validation.cnl;
    renderOperations(validation.operations);
    setMessage(
      elements.cnlStatus,
      `${validation.operations.length}操作のCNLとして検査に合格しました。`,
      "success",
    );
  } else {
    renderOperations([]);
    setMessage(elements.cnlStatus, validation.error, "error");
  }
  updateControls();
  return validation;
}

function formatQwenProgress(message) {
  const parts = [message.file || "Qwenモデル"];
  if (message.percentage !== null) parts.push(`${message.percentage}%`);
  if (message.loaded && message.total) {
    parts.push(`${formatBytes(message.loaded)} / ${formatBytes(message.total)}`);
  }
  return `${parts.join(" / ")} を読み込んでいます…`;
}

async function translateInstruction() {
  const instruction = elements.prompt.value.trim();
  if (!instruction) {
    setMessage(elements.translationStatus, "自由な日本語を入力してください。", "error");
    elements.prompt.focus();
    return;
  }
  if (!("gpu" in navigator)) {
    setMessage(
      elements.translationStatus,
      "WebGPUを利用できません。デスクトップ版ChromeまたはEdgeを使うか、CNLを直接入力してください。",
      "error",
    );
    return;
  }

  if (state.qwenWorker) state.qwenWorker.terminate();
  state.translationBusy = true;
  state.cnlValidation = null;
  elements.cnl.value = "";
  elements.translationMetrics.textContent = "";
  renderOperations([]);
  setMessage(elements.cnlStatus, "Qwenの翻訳結果を待っています。");
  setMessage(elements.translationStatus, "Qwenを準備しています…");
  updateControls();

  const worker = new Worker(new URL("./qwen-worker.js", import.meta.url), { type: "module" });
  state.qwenWorker = worker;
  worker.addEventListener("message", (event) => {
    const message = event.data;
    if (message.type === "progress") {
      setMessage(elements.translationStatus, formatQwenProgress(message));
      return;
    }
    if (message.type === "phase") {
      setMessage(elements.translationStatus, message.message);
      return;
    }
    if (message.type === "result") {
      elements.translationMetrics.textContent = [
        "Qwen3-0.6B q4f16",
        `${message.elapsed_seconds.toFixed(2)}秒`,
        `${message.attempts}回生成`,
      ].join(" / ");
      elements.cnl.value = message.cnl || "";
      if (!message.supported) {
        checkCnl();
        setMessage(
          elements.translationStatus,
          message.error || "対応可能なCNLへ変換できませんでした。CNLを直接編集するか、表現を変えて再試行してください。",
          "error",
        );
        return;
      }
      const validation = checkCnl();
      setMessage(
        elements.translationStatus,
        validation.valid
          ? "QwenによるCNL翻訳が完了しました。解釈を確認してください。"
          : validation.error,
        validation.valid ? "success" : "error",
      );
      return;
    }
    if (message.type === "error") {
      setMessage(elements.translationStatus, message.message, "error");
      return;
    }
    if (message.type === "released") {
      state.translationBusy = false;
      state.qwenWorker = null;
      updateControls();
    }
  });
  worker.addEventListener("error", (event) => {
    state.translationBusy = false;
    state.qwenWorker = null;
    setMessage(elements.translationStatus, event.message || "Qwen Workerでエラーが発生しました。", "error");
    updateControls();
  });
  worker.postMessage({ type: "translate", instruction, manifest: state.qwenManifest });
}

function cancelTranslation() {
  if (state.qwenWorker) state.qwenWorker.terminate();
  state.qwenWorker = null;
  state.translationBusy = false;
  setMessage(elements.translationStatus, "CNL翻訳を中止しました。");
  updateControls();
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
    const percentage = total ? Math.min(100, Math.round((received / expectedSize) * 100)) : 0;
    setMessage(elements.status, `Boku1-nanoを読み込んでいます… ${percentage}% (${formatBytes(received)})`);
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
  if ("gpu" in navigator) {
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

async function generateCode() {
  const validation = checkCnl();
  if (!validation.valid) return;
  const model = state.manifest.models.find((item) => item.id === elements.model.value);
  state.cancelled = false;
  state.generationBusy = true;
  elements.output.textContent = "";
  elements.metrics.textContent = "";
  const startedAt = performance.now();
  updateControls();
  try {
    const promptIds = state.tokenizer.encodePrompt(validation.cnl);
    if (promptIds.includes(state.manifest.special_token_ids.unk)) {
      throw new Error("CNLにtokenizerで表現できない文字が含まれています。");
    }
    if (promptIds.length >= model.context_length) {
      throw new Error(`CNLが長すぎます（${promptIds.length}/${model.context_length}トークン）。`);
    }
    const runtime = await createSession(model);
    const currentIds = [...promptIds];
    const generatedIds = [];
    const limit = Math.min(96, model.context_length - promptIds.length);
    setMessage(elements.status, `${model.label}が${runtime.backend}で生成しています…`);
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
    setMessage(
      elements.status,
      state.cancelled ? "生成を中止しました。" : `${model.label}による生成が完了しました。`,
      state.cancelled ? "normal" : "success",
    );
  } catch (error) {
    console.error(error);
    setMessage(elements.status, error instanceof Error ? error.message : String(error), "error");
  } finally {
    state.generationBusy = false;
    updateControls();
  }
}

async function initialize() {
  ort.env.wasm.wasmPaths = new URL("./vendor/", window.location.href).href;
  ort.env.wasm.numThreads = 1;
  const [modelResponse, qwenResponse] = await Promise.all([
    fetch("./model-manifest.json"),
    fetch("./qwen-manifest.json"),
  ]);
  if (!modelResponse.ok) throw new Error("Boku1-nanoのモデル一覧を取得できませんでした。");
  if (!qwenResponse.ok) throw new Error("Qwenの設定を取得できませんでした。");
  state.manifest = await modelResponse.json();
  state.qwenManifest = await qwenResponse.json();
  state.tokenizer = await BokuNanoTokenizer.load(`./${state.manifest.tokenizer.path}`);
  for (const model of state.manifest.models) {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = `${model.label} (${formatBytes(model.size_bytes)})`;
    if (model.id === "10epoch") option.selected = true;
    elements.model.append(option);
  }
  setMessage(
    elements.translationStatus,
    "自由な日本語を入力し、QwenでCNLへ翻訳できます。初回は約543 MiBを取得します。",
  );
  setMessage(elements.status, "検査済みCNLからコードを生成できます。");
  checkCnl();
  window.__bokuNanoReady = true;
}

elements.translate.addEventListener("click", translateInstruction);
elements.cancelTranslation.addEventListener("click", cancelTranslation);
elements.validateCnl.addEventListener("click", checkCnl);
elements.cnl.addEventListener("input", checkCnl);
elements.generate.addEventListener("click", generateCode);
elements.stop.addEventListener("click", () => {
  state.cancelled = true;
});
for (const button of elements.exampleButtons) {
  button.addEventListener("click", () => {
    elements.prompt.value = button.dataset.examplePrompt;
    elements.prompt.focus();
  });
}

initialize().catch((error) => {
  console.error(error);
  setMessage(elements.translationStatus, error instanceof Error ? error.message : String(error), "error");
  setMessage(elements.status, error instanceof Error ? error.message : String(error), "error");
});
