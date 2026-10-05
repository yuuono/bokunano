// One worker per run: no state leaks between code cards, and terminate() always stops a run.
self.onmessage = async ({ data }) => {
  try {
    self.postMessage({ type: "phase", message: "Python実行環境を準備しています（初回はダウンロードします）…" });
    const { loadPyodide } = await import("https://cdn.jsdelivr.net/pyodide/v0.29.2/full/pyodide.mjs");
    const python = await loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.29.2/full/" });
    for (const name of ["reference_interpreter.py", "verification_runtime.py"]) {
      const response = await fetch(new URL(`./${name}?v=11`, import.meta.url));
      if (!response.ok) throw new Error(`検証用ファイルを取得できません: ${name}`);
      python.FS.writeFile(name, await response.text());
    }
    python.runPython("from verification_runtime import verify_json");
    python.globals.set("request_json", JSON.stringify(data));
    self.postMessage({ type: "running" });
    const result = JSON.parse(python.runPython("verify_json(request_json)"));
    self.postMessage({ type: "result", result });
  } catch (error) {
    self.postMessage({ type: "error", message: String(error.message || error) });
  }
};
