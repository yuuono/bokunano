import { parseVerificationInputs } from "./semantic-ast.js?v=11";

let activeCancel = null;
export function cancelVerification() { activeCancel?.(); }

function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text) node.textContent = text;
  return node;
}

export function appendCodeVerification(card, snapshot, { incomplete = false, onChange = fn => fn() } = {}) {
  // Own both code and meaning; subsequent edits to the current CNL cannot change this check.
  const code = snapshot.code;
  const semanticAst = structuredClone(snapshot.semanticAst);
  const section = element("section", "code-verification");
  section.setAttribute("aria-label", "参照インタプリタとの検証");
  section.append(element("h3", "", "入力を試して、結果を検証"));
  section.append(element("p", "verification-help", incomplete
    ? "このコードは未完了です。実行エラーになる可能性があります。"
    : "生成コードと、保存した意味ASTの参照実行結果を比較します。"));
  const form = element("form", "verification-form");
  const xsLabel = element("label", "verification-xs", "入力リスト xs");
  const xs = element("input", "");
  xs.type = "text";
  xs.value = "[3, -1, 2, 0, -4, 5, 2]";
  xs.maxLength = 200;
  xs.required = true;
  xsLabel.append(xs);
  const kLabel = element("label", "verification-k", "k");
  const k = element("input", "");
  k.type = "number";
  k.min = "1"; k.max = "10"; k.step = "1"; k.required = true;
  k.value = String(snapshot.kValue ?? 3);
  kLabel.append(k);
  const buttons = element("div", "verification-actions");
  const run = element("button", "verify-run", "実行して参照結果と比較");
  run.type = "submit";
  const sample = element("button", "", "別の入力例");
  sample.type = "button";
  const stop = element("button", "", "検証を停止");
  stop.type = "button"; stop.hidden = true;
  buttons.append(run, sample, stop);
  form.append(xsLabel, kLabel, buttons);
  section.append(form);
  section.append(element("p", "verification-help", "xs：−100〜100の整数を最大20個 ／ k：1〜10。kを使わない操作では値は結果に影響しません。"));
  const status = element("p", "verification-status", "入力値を変えて何度でも試せます。実行はブラウザ内で行います。");
  status.setAttribute("role", "status");
  const results = element("div", "verification-results");
  results.hidden = true;
  const expected = element("pre", "");
  const actual = element("pre", "");
  for (const [label, output] of [["参照インタプリタ", expected], ["生成したPython", actual]]) {
    const row = element("div", "verification-result");
    row.append(element("strong", "", label), output);
    results.append(row);
  }
  const detail = element("details", "verification-ast");
  detail.append(element("summary", "", "検証に使う意味ASTを見る"), element("pre", "", JSON.stringify(semanticAst, null, 2)));
  section.append(status, results, detail);
  card.append(section);

  function display(text, kind = "normal") {
    onChange(() => { status.textContent = text; section.dataset.result = kind; });
  }
  function clearResult() {
    results.hidden = true;
    expected.textContent = ""; actual.textContent = "";
    display("入力を変更しました。もう一度実行すると、この値で比較できます。");
  }
  xs.addEventListener("input", clearResult);
  k.addEventListener("input", clearResult);
  let sampleIndex = 0;
  const samples = ["[]", "[0, 0, 0]", "[-10, -3, -1, 1, 3, 10]", "[8, 3, 8, -2, 0, 1]", "[3, -1, 2, 0, -4, 5, 2]"];
  sample.addEventListener("click", () => { xs.value = samples[sampleIndex++ % samples.length]; clearResult(); });
  form.addEventListener("submit", event => {
    event.preventDefault();
    let inputs;
    try { inputs = parseVerificationInputs(xs.value, k.value); }
    catch (error) { results.hidden = true; display(error.message, "error"); return; }
    cancelVerification();
    results.hidden = true;
    let worker;
    let timer;
    let done = false;
    function finish() {
      if (done) return;
      done = true;
      clearTimeout(timer);
      worker?.terminate();
      for (const control of [xs, k, run, sample]) control.disabled = false;
      stop.hidden = true;
      if (activeCancel === cancel) activeCancel = null;
    }
    function cancel() { finish(); display("検証を中止しました。入力を変えて再実行できます。"); }
    function timeout(message) { finish(); display(message, "error"); }
    activeCancel = cancel;
    stop.onclick = cancel;
    for (const control of [xs, k, run, sample]) control.disabled = true;
    stop.hidden = false;
    display("実行環境を準備しています…");
    // Loading can take longer than evaluation; neither may leave the UI stuck.
    timer = setTimeout(() => timeout("実行環境の読み込みが時間切れになりました。通信状態を確認して再実行してください。"), 60000);
    try {
      worker = new Worker(new URL("./verification-worker.js?v=11", import.meta.url), { type: "module" });
      worker.onmessage = ({ data }) => {
        if (done) return;
        if (data.type === "phase") display(data.message);
        if (data.type === "running") {
          clearTimeout(timer);
          timer = setTimeout(() => timeout("実行時間の上限（5秒）を超えたため停止しました。"), 5000);
          display("コードと参照インタプリタを実行しています…");
        }
        if (data.type === "error") { finish(); display(`実行環境のエラー: ${data.message}`, "error"); }
        if (data.type === "result") {
          finish();
          const result = data.result;
          onChange(() => {
            results.hidden = false;
            expected.textContent = result.expected ?? result.error;
            actual.textContent = result.actual ?? (result.status === "reference_error" ? "未実行" : result.error);
          });
          const messages = {
            match: "一致しました。この入力で生成コードと参照結果が一致しています。",
            mismatch: "不一致です。生成コードの結果が参照結果と異なります。",
            code_error: "生成コードの実行エラーです。参照結果とエラーの内容を確認してください。",
            reference_error: "参照インタプリタで実行できませんでした。入力と意味ASTを確認してください。",
          };
          display(messages[result.status] || "検証結果を取得できませんでした。", result.status);
        }
      };
      worker.onerror = () => { finish(); display("実行環境を読み込めませんでした。再実行してください。", "error"); };
      worker.postMessage({ code, semanticAst, ...inputs });
    } catch (error) { finish(); display(error.message, "error"); }
  });
}
