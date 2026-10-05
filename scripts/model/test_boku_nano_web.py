"""静的WebデモをFirefoxで開き、CNL検査と10個のONNXモデルを確認する。"""

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
TOKENIZER_PATHS = {
    "bpe-2048-minfreq5-maxlen24": PROJECT_ROOT
    / "data/tokenizers/bpe_2048/tokenizer.json",
    "bpe-2048-minfreq2-maxlen8": PROJECT_ROOT
    / "data/tokenizers/bpe_2048_minfreq2_maxlen8/tokenizer.json",
}
EXPECTED_MODEL_IDS = {
    "1m-3epoch",
    "1m-short-3epoch",
    "1m-1epoch",
    "1m-short-1epoch",
    "5m-1epoch",
    "5m-short-1epoch",
    "15m-1epoch",
    "15m-short-1epoch",
    "3epoch",
    "10epoch",
}
TWO_OPERATION_CNL = (
    "整数リストxsから各要素の絶対値を取り、"
    "値を降順に並べるsolve関数を書いてください。"
)
THREE_OPERATION_CNL = (
    "整数リストxsと整数kを受け取り、各要素を3倍し、"
    "各要素の符号を反転し、kより小さい値だけを残すsolve関数を書いてください。"
)


class QuietHandler(SimpleHTTPRequestHandler):
    """成功したHTTPアクセスログを抑制する。"""

    def log_message(self, format: str, *args: Any) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Boku1-nano Webデモを実ブラウザで確認します。")
    parser.add_argument("--geckodriver", type=Path, help="geckodriverのパス")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    return parser.parse_args()


def verify_prompt_disclosure(driver: webdriver.Firefox) -> None:
    details = driver.find_element("css selector", ".prompt-details")
    details.find_element("css selector", "summary").click()
    WebDriverWait(driver, 5).until(
        lambda current: current.find_element(
            "css selector", ".prompt-details"
        ).get_attribute("open")
        is not None
    )
    system_prompt = driver.find_element("id", "normalizer-system-prompt").text
    initial_prompt = driver.find_element("id", "normalizer-initial-prompt").text
    retry_prompt = driver.find_element("id", "normalizer-retry-prompt").text
    if "整数リスト処理の手順を選ぶ" not in system_prompt:
        raise AssertionError("system messageがデモに表示されていません。")
    if (
        "次の24操作から1～4操作" not in system_prompt
        or "入力: 偶数を残して" not in system_prompt
    ):
        raise AssertionError("24操作の規則またはfew-shot例が表示されていません。")
    if initial_prompt != "入力: {ユーザー入力}\n出力:":
        raise AssertionError(f"初回user messageの表示が異なります: {initial_prompt!r}")
    if "前回の出力: {検査に失敗したQwen出力}" not in retry_prompt:
        raise AssertionError("再生成messageがデモに表示されていません。")


def verify_cnl_validator(driver: webdriver.Firefox) -> None:
    actual = driver.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        import('./cnl.js').then(({CNL_OPERATIONS, validateCnl}) => {
          done({
            operationCount: CNL_OPERATIONS.length,
            two: validateCnl(arguments[0]),
            three: validateCnl(arguments[1]),
            four: validateCnl(
              '整数リストxsから偶数だけを残し、各要素を2倍し、' +
              '各要素を3倍し、値を昇順に並べるsolve関数を書いてください。'
            ),
            five: validateCnl(
              '整数リストxsから偶数だけを残し、各要素を2倍し、' +
              '各要素を3倍し、値を昇順に並べ、現在の要素順を反転するsolve関数を書いてください。'
            ),
            unknown: validateCnl(
              '整数リストxsから合計値を求めるsolve関数を書いてください。'
            ),
          });
        }).catch(error => done({error: String(error)}));
        """,
        TWO_OPERATION_CNL,
        THREE_OPERATION_CNL,
    )
    if actual.get("error"):
        raise AssertionError(f"CNL検査モジュールの読込に失敗しました: {actual['error']}")
    if actual["operationCount"] != 24:
        raise AssertionError(f"許可操作数が24ではありません: {actual['operationCount']}")
    if not actual["two"]["valid"] or len(actual["two"]["operations"]) != 2:
        raise AssertionError(f"2操作CNLを受理できませんでした: {actual['two']}")
    if not actual["three"]["valid"] or len(actual["three"]["operations"]) != 3:
        raise AssertionError(f"3操作CNLを受理できませんでした: {actual['three']}")
    if not actual["four"]["valid"] or not actual["four"]["experimental"]:
        raise AssertionError("4操作CNLを実験として受理できませんでした。")
    if actual["five"]["valid"]:
        raise AssertionError("5操作CNLを誤って受理しました。")
    if actual["unknown"]["valid"]:
        raise AssertionError("許可外操作を誤って受理しました。")


def verify_tokenizers(driver: webdriver.Firefox) -> None:
    for tokenizer_id, tokenizer_path in TOKENIZER_PATHS.items():
        browser_path = f"./tokenizers/{tokenizer_id}.json"
        actual = driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            import('./tokenizer.js').then(async ({BokuNanoTokenizer}) => {
              const tokenizer = await BokuNanoTokenizer.load(arguments[0]);
              done(tokenizer.encodePrompt(arguments[1]));
            }).catch(error => done({error: String(error)}));
            """,
            browser_path,
            TWO_OPERATION_CNL,
        )
        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        expected = tokenizer.encode(
            f"<|bos|><|task|>\n{TWO_OPERATION_CNL}\n<|code|>\n",
            add_special_tokens=False,
        ).ids
        if actual != expected:
            raise AssertionError(
                f"{tokenizer_id}のブラウザとPythonのtoken IDが一致しません: "
                f"{actual} != {expected}"
            )


def verify_model_options(driver: webdriver.Firefox) -> None:
    actual = {
        option.get_attribute("value")
        for option in Select(driver.find_element("id", "model")).options
    }
    if actual != EXPECTED_MODEL_IDS:
        raise AssertionError(f"モデル選択肢が一致しません: {actual} != {EXPECTED_MODEL_IDS}")


def set_cnl(driver: webdriver.Firefox, cnl: str) -> None:
    driver.execute_script(
        """
        const field = document.querySelector('#cnl');
        field.value = arguments[0];
        field.dispatchEvent(new Event('input', {bubbles: true}));
        """,
        cnl,
    )
    WebDriverWait(driver, 5).until(
        lambda current: not current.find_element("id", "generate").get_attribute("disabled")
    )


def run_model(
    driver: webdriver.Firefox,
    model_id: str,
    cnl: str,
    operation_count: int,
    timeout: float,
) -> dict[str, str]:
    driver.find_element("css selector", f'input[name="boku-model"][value="{model_id}"]').click()
    set_cnl(driver, cnl)
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
    if operation_count == 2 and ("abs(" not in output or "sorted(" not in output):
        raise AssertionError(
            f"{model_id}が指定した2操作を生成しませんでした: {output!r}"
        )
    has_negation = "-x" in output or "-value" in output
    if operation_count == 3 and (
        "* 3" not in output
        or not has_negation
        or ("if k >" not in output and "< k" not in output)
    ):
        raise AssertionError(
            f"{model_id}が指定した3操作を生成しませんでした: {output!r}"
        )
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
        verify_prompt_disclosure(driver)
        print("prompt disclosure: system・初回・再生成messageの表示を確認")
        verify_cnl_validator(driver)
        print("CNL validator: 24操作・最大4操作・5操作と許可外の拒否を確認")
        verify_tokenizers(driver)
        print("tokenizer: 旧BPE・短いpiece版ともPython版と一致")
        verify_model_options(driver)
        print("model selector: 学習済み10モデルを確認")
        cases = ((2, TWO_OPERATION_CNL), (3, THREE_OPERATION_CNL))
        for model_id in ("3epoch", "10epoch"):
            for operation_count, cnl in cases:
                result = run_model(
                    driver,
                    model_id,
                    cnl,
                    operation_count,
                    args.timeout_seconds,
                )
                label = f"{model_id}/{operation_count}操作"
                print(f"{label}: {result['status']}")
                print(f"{label}: {result['metrics']}")
                print(f"{label}: {result['output']}")
        for model_id in sorted(EXPECTED_MODEL_IDS - {"3epoch", "10epoch"}):
            result = run_model(
                driver,
                model_id,
                TWO_OPERATION_CNL,
                0,
                args.timeout_seconds,
            )
            print(f"{model_id}/smoke: {result['status']}")
            print(f"{model_id}/smoke: {result['metrics']}")
    finally:
        driver.quit()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
