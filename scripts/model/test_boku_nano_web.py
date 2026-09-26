"""静的WebデモをFirefoxで開き、両ONNXモデルの生成を確認する。"""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from typing import Any

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait
from tokenizers import Tokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PROJECT_ROOT / "web"
TOKENIZER_PATH = PROJECT_ROOT / "data/tokenizers/bpe_2048/tokenizer.json"
INSTRUCTION = "整数リストxsから偶数だけを残すsolve関数を書いてください。"


class QuietHandler(SimpleHTTPRequestHandler):
    """成功したHTTPアクセスログを抑制する。"""

    def log_message(self, format: str, *args: Any) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Boku1-nano Webデモを実ブラウザで確認します。")
    parser.add_argument("--geckodriver", type=Path, help="geckodriverのパス")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    return parser.parse_args()


def verify_tokenizer(driver: webdriver.Firefox) -> None:
    actual = driver.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        import('./tokenizer.js').then(async ({BokuNanoTokenizer}) => {
          const tokenizer = await BokuNanoTokenizer.load('./tokenizer.json');
          done(tokenizer.encodePrompt(arguments[0]));
        }).catch(error => done({error: String(error)}));
        """,
        INSTRUCTION,
    )
    tokenizer = Tokenizer.from_file(str(TOKENIZER_PATH))
    expected = tokenizer.encode(
        f"<|bos|><|task|>\n{INSTRUCTION}\n<|code|>\n",
        add_special_tokens=False,
    ).ids
    if actual != expected:
        raise AssertionError(f"ブラウザとPythonのtoken IDが一致しません: {actual} != {expected}")


def run_model(driver: webdriver.Firefox, model_id: str, timeout: float) -> dict[str, str]:
    Select(driver.find_element("id", "model")).select_by_value(model_id)
    driver.find_element("id", "generate").click()
    WebDriverWait(driver, timeout).until(
        lambda current: "完了しました" in current.find_element("id", "status").text
        or current.find_element("id", "status").get_attribute("data-kind") == "error"
    )
    status = driver.find_element("id", "status")
    output = driver.find_element("id", "output").text
    if status.get_attribute("data-kind") == "error":
        raise AssertionError(f"{model_id}のブラウザ推論に失敗しました: {status.text}")
    if "def solve(" not in output:
        raise AssertionError(f"{model_id}がsolve関数を生成しませんでした: {output!r}")
    return {
        "status": status.text,
        "metrics": driver.find_element("id", "metrics").text,
        "output": output,
    }


def main() -> None:
    args = parse_args()
    handler = partial(QuietHandler, directory=str(WEB_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    options = Options()
    options.add_argument("-headless")
    service = Service(str(args.geckodriver)) if args.geckodriver else Service()
    driver = webdriver.Firefox(service=service, options=options)
    try:
        driver.get(f"http://127.0.0.1:{server.server_port}/")
        WebDriverWait(driver, 60).until(
            lambda current: current.execute_script("return window.__bokuNanoReady === true")
        )
        verify_tokenizer(driver)
        print("tokenizer: Python版と一致")
        for model_id in ("3epoch", "10epoch"):
            result = run_model(driver, model_id, args.timeout_seconds)
            print(f"{model_id}: {result['status']}")
            print(f"{model_id}: {result['metrics']}")
            print(f"{model_id}: {result['output']}")
    finally:
        driver.quit()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
