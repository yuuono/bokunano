import { BokuNanoTokenizer, formatBokuPrompt } from "./tokenizer.js?v=3";
import { CNL_OPERATIONS, MAX_OPERATIONS, validateOperationPlan, buildNormalizerSystemPrompt, buildNormalizerUserPrompt, validateCnl, parseK, bindKDefault } from "./cnl.js?v=12";
import { selectToken, validateTemperature } from "./sampling.js";

import { appendOperationToDraft, nearBottom, captureSelection } from "./chat-utils.js?v=10";
import { highlightPython } from "./python-highlight.js?v=7";
import { captureSemanticAst } from "./semantic-ast.js?v=11";
import { appendCodeVerification, cancelVerification } from "./code-verification.js?v=11";

const $ = (id) => document.getElementById(id);
const state = {
  manifest: null,
  qwenManifest: null,
  tokenizers: new Map(),
  activeSession: null,
  job: null,
  ready: false,
  candidate: null,
  contextCnl: "",
  contextK: null,
  parameterK: null,
  confirmedReply: null,
  draftSelection: null,
};
const errorText = (error) => error instanceof Error ? error.message : String(error);
const formatBytes = (bytes) => `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
const current = (job) => state.job === job && !job.cancelled;

function setMessage(element, message, kind = "normal") {
  element.textContent = message;
  element.dataset.kind = kind;
}

function updateControls() {
  const busy = Boolean(state.job);
  for (const id of ["model", "qwen-temperature", "boku-temperature", "prompt", "cnl", "validate-cnl", "new-chat", "new-chat-top"]) {
    $(id).disabled = !state.ready || busy;
  }
  $("translate").disabled = !state.ready || busy;
  $("generate").disabled = !state.ready || busy || !state.candidate?.valid;
  $("cancel-translation").hidden = state.job?.kind !== "qwen";
  $("stop").hidden = state.job?.kind !== "boku";
  for (const input of document.querySelectorAll('[name="boku-model"]')) {
    input.disabled = !state.ready || busy;
  }
  const draft = validateOperationPlan($("prompt").value);
  const count = draft.valid ? draft.operations.length : 0;
  for (const button of document.querySelectorAll('[data-operation-id]')) {
    button.disabled = !state.ready || busy || count >= MAX_OPERATIONS;
    const selected = draft.valid ? draft.operations.filter(op => op.id === button.dataset.operationId).length : 0;
    button.dataset.selected = String(selected > 0);
    button.querySelector('small').textContent = selected ? `${selected}回選択中` : "＋追加";
  }
  for (const button of document.querySelectorAll('#operation-list button')) button.disabled = !state.ready || busy || button.dataset.unavailable === "true";
  for (const button of document.querySelectorAll("[data-generate-confirmation]")) button.disabled = !state.ready || busy;
  for (const button of document.querySelectorAll("[data-example-prompt]")) button.disabled = !state.ready || busy;
  for (const kind of ["qwen", "boku"]) {
    const running = state.job?.kind === kind;
    $(`${kind}-state`).textContent = running ? (state.job.cancelled ? "停止中" : "処理中") : "待機中";
    $(`${kind}-state`).dataset.busy = String(running);
  }
}

function updateScrollButton() {
  $("latest-message").hidden = nearBottom($("conversation"));
}

function followScroll(element, change, force = false) {
  const follow = force || nearBottom(element);
  change();
  if (follow) element.scrollTop = element.scrollHeight;
  updateScrollButton();
}

function resizeComposer() {
  const conversation = $("conversation");
  const follow = nearBottom(conversation);
  $("prompt").style.height = "58px";
  $("prompt").style.height = `${Math.min(110, $("prompt").scrollHeight)}px`;
  if (follow) conversation.scrollTop = conversation.scrollHeight;
  updateScrollButton();
}

function confirmReply(reply, validation, selectionRecovered = false) {
  followScroll($("conversation"), () => {
    reply.message.dataset.selectionRecovered = String(selectionRecovered);
    if (selectionRecovered) {
      const note = document.createElement("p");
      note.className = "selection-recovery";
      note.textContent = "Qwenの出力を選択内容に合わせて補正しました。";
      reply.message.append(note);
    }
    const result = document.createElement("div");
    result.className = "cnl-result";
    const label = document.createElement("strong");
    label.textContent = "Boku1-nanoへの入力（整形後のCNL）";
    const content = document.createElement("p");
    content.textContent = validation.cnl + (validation.kValue != null ? `\nk=${validation.kValue}` : "");
    result.append(label, content);
    reply.message.append(result);
    if (validation.experimental) {
      const note = document.createElement("p");
      note.className = "experimental-note";
      note.textContent = "4操作は実験です。学習範囲は最大3操作のため、生成コードの内容を確認してください。";
      reply.message.append(note);
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "confirm-generate";
    button.dataset.generateConfirmation = "true";
    button.textContent = "この内容でコードを生成";
    button.addEventListener("click", () => {
      if (state.job) return;
      $("cnl").value = validation.cnl;
      state.parameterK = validation.kValue;
      state.confirmedReply = { message: reply.message, cnl: validation.cnl, kValue: validation.kValue };
      checkCnl();
      generateCode();
    });
    reply.message.append(button);
    state.confirmedReply = { message: reply.message, cnl: validation.cnl, kValue: validation.kValue };
  });
  updateControls();
}

function addMessage(role, text, kind = "normal") {
  const message = document.createElement("article");
  message.className = `message ${role}`;
  message.dataset.kind = kind;
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "あなた" : "Qwen3-0.6B · 処理中";
  const body = document.createElement("p");
  body.textContent = text;
  message.append(label, body);
  $("welcome").hidden = true;
  followScroll($("conversation"), () => {
    let turn = $("conversation").querySelector(".chat-turn:last-child");
    if (role === "user" || !turn) {
      turn = document.createElement("section");
      turn.className = "chat-turn";
      $("conversation").append(turn);
    }
    turn.append(message);
  }, role === "user");
  return { message, body };
}

function checkCnl() {
  const validation = validateCnl($("cnl").value);
  if (validation.valid && validation.usesK) {
    try { validation.kValue = parseK(state.parameterK); }
    catch (error) { validation.valid = false; validation.error = errorText(error); }
  } else if (validation.valid) {
    validation.kValue = null;
    state.parameterK = null;
  }
  state.candidate = validation;
  $("operation-list").replaceChildren();
  if (validation.valid) {
    state.contextCnl = validation.cnl;
    state.contextK = validation.kValue ?? null;
    for (const [index, operation] of validation.operations.entries()) {
      const item = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = operation.label;
      item.append(label);
      for (const [symbol, title, offset] of [["↑", "前へ", -1], ["↓", "後ろへ", 1], ["×", "削除", 0]]) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = symbol;
        button.setAttribute("aria-label", `${index + 1}番目の操作を${title}`);
        button.disabled = offset !== 0 && (index + offset < 0 || index + offset >= validation.operations.length);
        button.dataset.unavailable = String(button.disabled);
        button.addEventListener("click", () => {
          const operations = [...validation.operations];
          if (!offset) operations.splice(index, 1);
          else [operations[index], operations[index + offset]] = [operations[index + offset], operations[index]];
          setOperations(operations);
        });
        item.append(button);
      }
      $("operation-list").append(item);
    }
    $("experimental-note").hidden = !validation.experimental;
    setMessage($("cnl-status"), `${validation.operations.length}操作 / 検査済み${validation.experimental ? "・実験" : ""}`, "success");
  } else {
    $("experimental-note").hidden = true;
    setMessage($("cnl-status"), validation.error, $("cnl").value ? "error" : "normal");
  }
  setMessage($("selection-status"), `${validation.operations.length} / ${MAX_OPERATIONS}操作を選択中${validation.operations.length === MAX_OPERATIONS ? "。追加するには選択済みの操作を削除してください。" : ""}`);
  updateControls();
  return validation;
}

function setOperations(operations) {
  if (state.job) return;
  if (!operations.length) {
    $("cnl").value = "";
    state.parameterK = null;
    state.contextCnl = "";
    state.contextK = null;
  } else {
    const result = validateOperationPlan(operations.map((op, i) => `${i + 1}. ${op.label}`).join("\n"));
    if (!result.valid) { setMessage($("selection-status"), result.error, "error"); return; }
    $("cnl").value = result.cnl;
  }
  checkCnl();
  setMessage($("translation-status"), "操作の選択からCNLを更新しました。内容を確認して生成してください。");
}

function promptDetails(parent, title, text) {
  const details = document.createElement("details");
  details.className = "actual-prompt";
  const summary = document.createElement("summary");
  summary.textContent = title;
  const pre = document.createElement("pre");
  pre.textContent = text;
  details.append(summary, pre);
  followScroll($("conversation"), () => parent.append(details));
  return details;
}

function finish(job) {
  if (state.job !== job) return;
  state.job = null;
  updateControls();
}

async function releaseActiveSession() {
  const active = state.activeSession;
  state.activeSession = null;
  if (active) await active.session.release();
}

async function translateInstruction(event) {
  event?.preventDefault();
  if (!state.ready || state.job) return;
  const instruction = $("prompt").value.trim();
  if (!instruction) { $("prompt").focus(); return; }
  setMessage($("status"), "");
  $("metrics").textContent = "";
  if (!("gpu" in navigator)) {
    setMessage($("translation-status"), "QwenにはWebGPU対応のChrome / Edgeが必要です。入力側のCNL欄へ直接入力することもできます。", "error");
    return;
  }
  const temperature = validateTemperature($("qwen-temperature").value);
  const previousCnl = state.candidate?.valid ? state.candidate.cnl : state.contextCnl;
  const previousK = state.candidate?.valid ? state.candidate.kValue : state.contextK;
  const contextCnl = previousCnl;
  const contextK = previousK;
  const selection = state.draftSelection;
  $("operation-picker").open = false;
  state.draftSelection = null;
  // An earlier answer remains in chat history, never as the current candidate.
  $("cnl").value = "";
  state.parameterK = null;
  state.confirmedReply = null;
  checkCnl();
  setMessage($("cnl-status"), "今回の指示を確認しています…");
  addMessage("user", instruction);
  $("prompt").value = "";
  resizeComposer();
  $("translation-metrics").textContent = "";
  const reply = addMessage("assistant", "指示を読み取っています…");
  const job = { kind: "qwen", cancelled: false, worker: null, reply };
  state.job = job;
  updateControls();
  setMessage($("translation-status"), "Qwenを準備しています…");
  const fail = (message) => {
    if (!current(job)) return;
    $("cnl").value = "";
    state.parameterK = null;
    checkCnl();
    state.contextCnl = previousCnl;
    state.contextK = previousK;
    const explanation = message;
    reply.message.querySelector(".message-label").textContent = "指示の処理結果（エラー）";
    setMessage($("cnl-status"), "今回の指示は未確定です。再送信してください。");
    followScroll($("conversation"), () => { reply.body.textContent = explanation; });
    reply.message.dataset.kind = "error";
    setMessage($("translation-status"), explanation, "error");
  };
  try {
    await releaseActiveSession();
    if (!current(job)) return;
    const worker = new Worker(new URL("./qwen-worker.js?v=12", import.meta.url), { type: "module" });
    job.worker = worker;
    worker.addEventListener("message", ({ data: message }) => {
      if (!current(job)) return;
      if (message.type === "phase") setMessage($("translation-status"), message.message);
      if (message.type === "prompt") {
        promptDetails(reply.message, `Qwenの実際のプロンプトを見る（${message.attempt}回目）`,
          `モデル: ${state.qwenManifest.model_id}\n\n生成条件:\n${JSON.stringify(message.options, null, 2)}\n\nメッセージ:\n${message.messages.map(item => `[${item.role}]\n${item.content}`).join("\n\n")}\n\nモデルに渡した文字列（チャットテンプレート適用後）:\n${message.prompt}`);
      }
      if (message.type === "progress") {
        const progress = message.percentage === null ? "" : ` ${message.percentage}%`;
        const size = message.loaded ? ` (${formatBytes(message.loaded)})` : "";
        setMessage($("translation-status"), `Qwenを読み込んでいます…${progress}${size}`);
      }
      if (message.type === "result") {
        $("translation-metrics").textContent = `Qwen3-0.6B · T=${temperature.toFixed(1)} · ${message.elapsed_seconds.toFixed(1)}秒 · ${message.attempts}回生成`;
        if (message.plan && !message.supported) {
          const details = document.createElement("details");
          details.className = "plan-details";
          const summary = document.createElement("summary");
          summary.textContent = "Qwenの出力を見る";
          const content = document.createElement("pre");
          content.textContent = message.plan;
          details.append(summary, content);
          followScroll($("conversation"), () => reply.message.append(details));
        }
        $("cnl").value = message.cnl || "";
        state.parameterK = message.kValue ?? null;
        const validation = checkCnl();
        if (!message.supported || !validation.valid) {
          state.contextCnl = previousCnl;
          state.contextK = previousK;
          fail(message.error || "この指示を解釈できませんでした。操作を具体的に伝えるか、CNLを直接編集してください。対応は24種類・最大4操作です。");
        } else {
          reply.message.querySelector(".message-label").textContent = "Qwen3-0.6B の出力";
          reply.body.textContent = message.plan || "（出力なし）";
          reply.body.className = "model-output";
          confirmReply(reply, validation, message.selectionRecovered);
          setMessage($("translation-status"), "解釈ができました。チャット内で確認して生成してください。", "success");
        }
      }
      if (message.type === "error") fail(message.message);
      if (message.type === "released") { worker.terminate(); finish(job); }
    });
    worker.addEventListener("error", (event) => {
      fail(event.message || "Qwenの実行に失敗しました。もう一度送信してください。");
      worker.terminate();
      finish(job);
    });
    worker.postMessage({ type: "translate", instruction, contextCnl, contextK, temperature, selection, manifest: state.qwenManifest });
  } catch (error) {
    fail(errorText(error));
    job.worker?.terminate();
    finish(job);
  }
}

function stopJob() {
  const job = state.job;
  if (!job) return;
  job.cancelled = true;
  if (job.kind === "qwen") {
    job.worker?.terminate();
    job.reply.message.querySelector(".message-label").textContent = "Qwenの処理を中止";
    job.reply.body.textContent = "解釈を中止しました。入力し直すか、前の指示から続けてください。";
    checkCnl();
    setMessage($("translation-status"), "Qwenの処理を中止しました。");
    finish(job);
  } else {
    job.controller.abort();
    setMessage($("status"), "生成を停止しています…");
    updateControls();
  }
}

async function fetchBytesWithProgress(model, job) {
  const response = await fetch(model.path, { signal: job.controller.signal });
  if (!response.ok) throw new Error(`モデルを取得できませんでした: ${response.status}`);
  if (!response.body) return new Uint8Array(await response.arrayBuffer());
  const total = Number(response.headers.get("content-length")) || model.size_bytes;
  const reader = response.body.getReader();
  const chunks = [];
  let received = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    if (current(job)) setMessage($("status"), `モデルを読み込んでいます… ${Math.min(100, Math.round(received / total * 100))}% (${formatBytes(received)})`);
  }
  const result = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.length; }
  return result;
}

function selectedModel() { return state.manifest.models.find(model => model.id === $("model").value); }

async function tokenizerForModel(model) {
  const id = model.tokenizer_id;
  if (!state.tokenizers.has(id)) {
    const definition = state.manifest.tokenizers[id];
    if (!definition) throw new Error(`tokenizer設定がありません: ${id}`);
    state.tokenizers.set(id, await BokuNanoTokenizer.load(`./${definition.path}`));
  }
  return state.tokenizers.get(id);
}

function renderModelSummary() {
  const model = selectedModel();
  for (const input of document.querySelectorAll('[name="boku-model"]')) input.checked = input.value === model.id;
  $("generation-selection").textContent = `使用モデル: ${model.label}`;
  $("model-summary").textContent = `${(model.parameter_count / 1e6).toFixed(1)}M parameters · ${formatBytes(model.size_bytes)} · 最大${model.context_length} tokens`;
}

async function createSession(model, job) {
  if (state.activeSession?.modelId === model.id) return state.activeSession;
  await releaseActiveSession();
  if (!current(job)) return null;
  const bytes = await fetchBytesWithProgress(model, job);
  if (!current(job)) return null;
  let session;
  let backend = "WebGPU";
  if ("gpu" in navigator) {
    try { session = await ort.InferenceSession.create(bytes, { executionProviders: ["webgpu"] }); }
    catch (error) { console.warn("WASMへ切り替えます", error); }
  }
  if (!current(job)) { await session?.release(); return null; }
  if (!session) {
    backend = "WASM";
    session = await ort.InferenceSession.create(bytes, { executionProviders: ["wasm"] });
  }
  if (!current(job)) { await session.release(); return null; }
  state.activeSession = { modelId: model.id, session, backend };
  return state.activeSession;
}

function newCodeCard(model, validation, temperature) {
  const confirmed = state.confirmedReply;
  const lastTurn = $("conversation").querySelector(".chat-turn:last-child");
  const sameTurn = confirmed?.message.parentElement === lastTurn && confirmed.cnl === validation.cnl && confirmed.kValue === validation.kValue;
  const turn = sameTurn ? lastTurn : addMessage("user", validation.cnl + (validation.kValue !== null ? `\n使う数値: k=${validation.kValue}` : "")).message.parentElement;
  // Keep stable IDs for the latest result, without duplicating IDs in history.
  $("output")?.removeAttribute("id");
  const card = document.createElement("article");
  card.className = "code-card";
  const header = document.createElement("div");
  header.className = "code-card-header";
  const label = document.createElement("span");
  label.textContent = `Boku1-nano の出力（Python） · ${model.label} · T=${temperature.toFixed(1)}`;
  const copy = document.createElement("button");
  copy.type = "button";
  copy.textContent = "コピー";
  copy.disabled = true;
  header.append(label, copy);
  const instruction = document.createElement("p");
  instruction.className = "code-instruction";
  instruction.textContent = validation.operations.map(item => item.label).join(" → ") + (validation.kValue !== null ? ` / k=${validation.kValue}` : "") + (validation.experimental ? " / 4操作・実験" : "");
  const pre = document.createElement("pre");
  const code = document.createElement("code");
  code.id = "output";
  code.textContent = "モデルを準備しています…";
  pre.append(code);
  const meta = document.createElement("div");
  meta.className = "code-card-meta";
  meta.textContent = "準備中";
  card.append(header, instruction, pre, meta);
  const inputCnl = document.createElement("p");
  inputCnl.className = "code-instruction";
  inputCnl.textContent = `使用したCNL: ${validation.cnl}`;
  card.insertBefore(inputCnl, pre);
  followScroll($("conversation"), () => turn.append(card), true);
  copy.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(code.textContent); copy.textContent = "コピーしました"; }
    catch { copy.textContent = "コピーできませんでした"; }
    setTimeout(() => { copy.textContent = "コピー"; }, 1800);
  });
  return { card, code, meta, copy };
}

async function generateCode() {
  if (!state.ready || state.job) return;
  const validation = checkCnl();
  if (!validation.valid) return;
  const semanticAst = captureSemanticAst(validation);
  const model = selectedModel();
  const temperature = validateTemperature($("boku-temperature").value);
  const job = { kind: "boku", cancelled: false, controller: new AbortController() };
  state.job = job;
  state.contextCnl = validation.cnl;
  const view = newCodeCard(model, validation, temperature);
  $("metrics").textContent = "";
  setMessage($("status"), "Boku1-nanoを準備しています…");
  updateControls();
  const startedAt = performance.now();
  let generatedCount = 0;
  try {
    const tokenizer = await tokenizerForModel(model);
    const promptIds = tokenizer.encodePrompt(validation.cnl);
    if (promptIds.includes(state.manifest.special_token_ids.unk)) throw new Error("この指示にはモデルが扱えない文字が含まれています。CNLを修正してください。");
    if (promptIds.length >= model.context_length) throw new Error(`指示が長すぎます (${promptIds.length}/${model.context_length} tokens)。短くしてください。`);
    const runtime = await createSession(model, job);
    if (!runtime || !current(job)) return;
    promptDetails(view.card, "Boku1-nanoの実際のプロンプトを見る",
      `モデル: ${model.id}\n温度: ${temperature}\n\n${formatBokuPrompt(validation.cnl)}\n入力トークンID:\n${JSON.stringify(promptIds)}${validation.kValue !== null ? `\n\nk=${validation.kValue} は生成後に関数の初期値として設定します。上記プロンプトには含めません。` : ""}`);
    const currentIds = [...promptIds];
    const generatedIds = [];
    const limit = model.context_length - promptIds.length;
    let ended = false;
    const inferenceStarted = performance.now();
    view.code.textContent = "";
    setMessage($("status"), `${runtime.backend}でコードを生成しています…`);
    for (let step = 0; step < limit && current(job); step += 1) {
      const input = new ort.Tensor("int64", BigInt64Array.from(currentIds, BigInt), [1, currentIds.length]);
      let outputs;
      try {
        outputs = await runtime.session.run({ input_ids: input });
        if (!current(job)) break;
        const tokenId = selectToken(outputs.logits.data, temperature);
        if (tokenId === state.manifest.special_token_ids.eos) { ended = true; break; }
        currentIds.push(tokenId);
        generatedIds.push(tokenId);
        generatedCount = generatedIds.length;
        followScroll($("conversation"), () => highlightPython(view.code, tokenizer.decode(generatedIds)));
        view.copy.disabled = validation.kValue !== null;
        if (step % 2 === 0) await new Promise(requestAnimationFrame);
      } finally {
        input.dispose();
        for (const tensor of Object.values(outputs || {})) tensor.dispose();
      }
    }
    const seconds = (performance.now() - inferenceStarted) / 1000;
    if (ended && validation.kValue !== null) {
      const rawCode = tokenizer.decode(generatedIds);
      followScroll($("conversation"), () => highlightPython(view.code, bindKDefault(rawCode, validation.kValue)));
      view.copy.disabled = false;
      const details = document.createElement("details");
      details.className = "plan-details code-instruction";
      const summary = document.createElement("summary");
      summary.textContent = `k=${validation.kValue} を初期値に設定済み · モデルの元の出力を見る`;
      const pre = document.createElement("pre");
      pre.textContent = rawCode;
      details.append(summary, pre);
      followScroll($("conversation"), () => view.card.append(details));
    }
    const totalSeconds = (performance.now() - startedAt) / 1000;
    const result = job.cancelled ? "中止・未完了" : ended ? "生成完了" : "長さ上限・未完了";
    view.card.dataset.termination = job.cancelled ? "cancelled" : ended ? "eos" : "max_context";
    followScroll($("conversation"), () => { view.meta.textContent = `${result} · ${runtime.backend} · ${generatedIds.length} tokens · 生成 ${seconds.toFixed(1)}秒 · 合計 ${totalSeconds.toFixed(1)}秒`; });
    $("metrics").textContent = `入力 ${promptIds.length} / 生成 ${generatedIds.length} tokens · T=${temperature.toFixed(1)} · ${(generatedIds.length / Math.max(seconds, .001)).toFixed(1)} tokens/s`;
    setMessage($("status"), job.cancelled ? "生成を中止しました。" : ended ? "コードの生成が完了しました。" : "系列長の上限に達しました。コードは未完了の可能性があります。", ended ? "success" : "normal");
    if (!generatedCount) view.code.textContent = "コードは生成されませんでした。指示やモデルを変えて再試行してください。";
  } catch (error) {
    if (!job.cancelled) {
      setMessage($("status"), errorText(error), "error");
      view.meta.textContent = `エラー: ${errorText(error)}`;
      view.card.dataset.termination = "error";
      if (!generatedCount) view.code.textContent = "生成できませんでした。下の状態表示を確認してください。";
    }
  } finally {
    if (job.cancelled) {
      view.meta.textContent = "中止・未完了";
      view.card.dataset.termination = "cancelled";
      if (!generatedCount) view.code.textContent = "生成を中止しました。";
      setMessage($("status"), "生成を中止しました。");
    }
    if (generatedCount && view.code.textContent) {
      followScroll($("conversation"), () => appendCodeVerification(view.card, {
        code: view.code.textContent, semanticAst, kValue: validation.kValue,
      }, {
        incomplete: view.card.dataset.termination !== "eos",
        onChange: change => followScroll($("conversation"), change),
      }));
    }
    finish(job);
  }
}

function newConversation() {
  if (state.job) return;
  cancelVerification();
  state.candidate = null;
  state.confirmedReply = null;
  state.draftSelection = null;
  state.contextCnl = "";
  state.contextK = null;
  state.parameterK = null;
  $("conversation").querySelectorAll(".chat-turn").forEach(item => item.remove());
  $("welcome").hidden = false;
  $("cnl").value = "";
  $("prompt").value = "";
  resizeComposer();
  $("translation-metrics").textContent = "";
  $("metrics").textContent = "";
  checkCnl();
  setMessage($("translation-status"), "新しい指示を入力してください。");
  setMessage($("status"), "指示を確認するとコードを生成できます。");
  resizeComposer();
  $("operation-picker").open = false;
  $("prompt").focus();
}

async function initialize() {
  ort.env.wasm.wasmPaths = new URL("./vendor/", window.location.href).href;
  ort.env.wasm.numThreads = 1;
  const responses = await Promise.all([fetch("./model-manifest.json?v=4"), fetch("./qwen-manifest.json")]);
  if (responses.some(response => !response.ok)) throw new Error("モデル設定を取得できませんでした。ページを再読み込みしてください。");
  [state.manifest, state.qwenManifest] = await Promise.all(responses.map(response => response.json()));
  const groups = new Map();
  for (const model of state.manifest.models) {
    const groupName = model.group || "その他";
    if (!groups.has(groupName)) {
      const group = document.createElement("optgroup");
      group.label = `${groupName}モデル`;
      $("model").append(group);
      groups.set(groupName, group);
    }
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = model.label;
    groups.get(groupName).append(option);
  }
  $("model").value = state.manifest.default_model_id;
  for (const model of state.manifest.models) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "boku-model";
    input.value = model.id;
    input.checked = model.id === $("model").value;
    const name = document.createElement("span");
    name.textContent = model.label;
    label.append(input, name);
    input.addEventListener("change", () => { $("model").value = input.value; renderModelSummary(); });
    $("model-options").append(label);
  }
  for (const operation of CNL_OPERATIONS) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.operationId = operation.id;
    const name = document.createElement("span");
    name.textContent = operation.label;
    button.append(name, document.createElement("small"));
    button.addEventListener("click", () => {
      try {
        $("prompt").value = appendOperationToDraft($("prompt").value, operation.id);
        state.draftSelection = captureSelection($("prompt").value);
        updateDraft();
        // Keep the menu and keyboard focus in place for consecutive choices.
      } catch (error) { setMessage($("selection-status"), errorText(error), "error"); }
    });
    $("operation-catalog").append(button);
  }
  renderModelSummary();
  await tokenizerForModel(selectedModel());
  $("normalizer-system-prompt").textContent = buildNormalizerSystemPrompt();
  $("normalizer-initial-prompt").textContent = buildNormalizerUserPrompt("{ユーザー入力}");
  $("normalizer-retry-prompt").textContent = buildNormalizerUserPrompt("{元のユーザー入力}", "{検査に失敗したQwen出力}", "{検査エラー}");
  state.ready = true;
  setMessage($("translation-status"), "日本語で指示を送ってください。Qwenが内容を整理します。");
  checkCnl();
  updateDraft();
  window.__bokuNanoReady = true;
}

$("composer").addEventListener("submit", translateInstruction);
$("prompt").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault();
    translateInstruction();
  }
});
$("cnl").addEventListener("input", checkCnl);
$("validate-cnl").addEventListener("click", checkCnl);
$("generate").addEventListener("click", generateCode);
$("cancel-translation").addEventListener("click", stopJob);
$("stop").addEventListener("click", stopJob);
$("new-chat").addEventListener("click", newConversation);
$("new-chat-top").addEventListener("click", newConversation);
$("model").addEventListener("change", renderModelSummary);
for (const kind of ["qwen", "boku"]) {
  $(`${kind}-temperature`).addEventListener("input", () => {
    const value = validateTemperature($(`${kind}-temperature`).value);
    $(`${kind}-temperature-value`).textContent = value.toFixed(1);
    $(`${kind}-temperature-mode`).textContent = value === 0 ? "Greedy" : "Sampling";
  });
}
for (const button of document.querySelectorAll("[data-example-prompt]")) {
  button.addEventListener("click", () => {
    $("prompt").value = button.dataset.examplePrompt;
    state.draftSelection = captureSelection($("prompt").value);
    updateDraft();
    $("prompt").focus({ preventScroll: true });
  });
}
function updateDraft() {
  if (state.draftSelection?.text !== $("prompt").value.trim()) state.draftSelection = null;
  const plan = validateOperationPlan($("prompt").value);
  setMessage($("selection-status"), plan.valid ? `${plan.operations.length} / 4操作を入力中。クリックで追加できます。` : "操作を選ぶと日本語の指示になります。自由に書き換えて送信できます。");
  resizeComposer();
  updateControls();
}
$("prompt").addEventListener("input", updateDraft);
$("conversation").addEventListener("scroll", updateScrollButton, { passive: true });
$("latest-message").addEventListener("click", () => followScroll($("conversation"), () => {}, true));
const aliases = { map_add_k: "足す 加算", map_sub_k: "引く 減算", map_mul_k: "掛け算 かける", order_reverse: "逆順", order_ascending: "小さい順", order_descending: "大きい順", map_abs: "プラス 絶対値" };
$("operation-search").addEventListener("input", () => {
  const query = $("operation-search").value.normalize("NFKC").trim().toLowerCase();
  let visible = 0;
  for (const button of document.querySelectorAll('[data-operation-id]')) {
    const text = `${button.textContent} ${aliases[button.dataset.operationId] || ""}`.normalize("NFKC").toLowerCase();
    button.hidden = !text.includes(query);
    if (!button.hidden) visible += 1;
  }
  setMessage($("selection-status"), visible ? `${visible}種類の操作` : "一致する操作がありません。別の言葉で検索してください。");
});
$("operation-search").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.isComposing) {
    event.preventDefault();
    document.querySelector('[data-operation-id]:not([hidden]):not(:disabled)')?.click();
  }
});
$("close-operation-picker").addEventListener("click", () => {
  $("operation-picker").open = false;
  $("prompt").focus({ preventScroll: true });
});
$("operation-picker").addEventListener("toggle", () => {
  if ($("operation-picker").open) $("operation-search").focus({ preventScroll: true });
});
document.addEventListener("click", event => {
  if (!$("operation-picker").contains(event.target)) $("operation-picker").open = false;
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    if ($("operation-picker").open) { $("operation-picker").open = false; $("prompt").focus({ preventScroll: true }); }
    setSettingsOpen(false);
  }
});
function setSettingsOpen(open) {
  $("settings-panel").dataset.open = String(open);
  $("toggle-settings").setAttribute("aria-expanded", String(open));
}
$("toggle-settings").addEventListener("click", () => setSettingsOpen($("settings-panel").dataset.open !== "true"));
$("close-settings").addEventListener("click", () => { setSettingsOpen(false); $("toggle-settings").focus(); });
window.addEventListener("resize", updateScrollButton);
initialize().catch(error => {
  console.error(error);
  setMessage($("translation-status"), errorText(error), "error");
  setMessage($("status"), errorText(error), "error");
});
