"""生成コードを隔離した子プロセスで実行し、参照結果と比較する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# 必要な定義を対象モジュールから読み込む
from dataclasses import asdict, dataclass
# この処理で使う標準または外部モジュールを読み込む
import multiprocessing
# この処理で使う標準または外部モジュールを読み込む
import queue
# この処理で使う標準または外部モジュールを読み込む
import random
# 必要な定義を対象モジュールから読み込む
from typing import Any, Mapping, Sequence

# 必要な定義を対象モジュールから読み込む
from python_code_generator import validate_generated_code
# 必要な定義を対象モジュールから読み込む
from reference_interpreter import interpret


# 直後の定義へデコレータを適用する
@dataclass(frozen=True)
# 関連する状態と処理をまとめるクラスを定義する
class VerificationResult:
    # 次の値または処理を現在の構造へ組み込む
    syntax_ok: bool
    # 次の値または処理を現在の構造へ組み込む
    ast_safe: bool
    # 次の値または処理を現在の構造へ組み込む
    signature_ok: bool
    # 次の値または処理を現在の構造へ組み込む
    tests_passed: bool
    # 次の値または処理を現在の構造へ組み込む
    input_unchanged: bool
    # 次の値または処理を現在の構造へ組み込む
    timeout: bool
    # errorへこの工程で使用する値を設定する
    error: str | None = None

    # この工程を担当する関数を定義する
    def to_record(self) -> dict[str, Any]:
        # 処理結果を呼び出し元へ返す
        return asdict(self)


# 関連する状態と処理をまとめるクラスを定義する
class GeneratedCodeVerifierSession:
    """隔離プロセスを再利用し、複数の生成コードを1件ずつ検証する。"""

    # この工程を担当する関数を定義する
    def __init__(
        # 次の値または処理を現在の構造へ組み込む
        self,
        # 次の値または処理を現在の構造へ組み込む
        cases: Sequence[tuple[list[int], int]],
        # 次の値または処理を現在の構造へ組み込む
        timeout_seconds: float,
        # 次の値または処理を現在の構造へ組み込む
        max_source_chars: int,
    # 次の値または処理を現在の構造へ組み込む
    ) -> None:
        # 条件を満たす場合だけ次の処理を行う
        if timeout_seconds <= 0:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("timeout_secondsは正の値にしてください")
        # self.casesへこの工程で使用する値を設定する
        self.cases = [(list(xs), k) for xs, k in cases]
        # self.timeout_secondsへこの工程で使用する値を設定する
        self.timeout_seconds = timeout_seconds
        # self.max_source_charsへこの工程で使用する値を設定する
        self.max_source_chars = max_source_chars
        # self.contextへこの工程で使用する値を設定する
        self.context = multiprocessing.get_context("spawn")
        # self.task_queueへこの工程で使用する値を設定する
        self.task_queue: multiprocessing.Queue | None = None
        # self.result_queueへこの工程で使用する値を設定する
        self.result_queue: multiprocessing.Queue | None = None
        # self.processへこの工程で使用する値を設定する
        self.process: multiprocessing.Process | None = None
        # self.request_idへこの工程で使用する値を設定する
        self.request_id = 0

    # この工程を担当する関数を定義する
    def __enter__(self) -> GeneratedCodeVerifierSession:
        # 次の値または処理を現在の構造へ組み込む
        self._start_worker()
        # 処理結果を呼び出し元へ返す
        return self

    # この工程を担当する関数を定義する
    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        # 次の値または処理を現在の構造へ組み込む
        self.close()

    # この工程を担当する関数を定義する
    def verify(
        # 次の値または処理を現在の構造へ組み込む
        self,
        # 次の値または処理を現在の構造へ組み込む
        source: str,
        # 次の値または処理を現在の構造へ組み込む
        semantic_ast: Mapping[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    ) -> VerificationResult:
        """静的検査後、隔離プロセスで1件を参照結果と照合する。"""

        # 失敗する可能性がある処理を開始する
        try:
            # 次の値または処理を現在の構造へ組み込む
            validate_generated_code(source, self.max_source_chars)
        # 発生した例外を受け取り、安全に処理する
        except Exception as error:
            # 処理結果を呼び出し元へ返す
            return VerificationResult(False, False, False, False, False, False, str(error))

        # 次の値または処理を現在の構造へ組み込む
        self._ensure_worker()
        # 後続処理が前提とする状態を確認する
        assert self.task_queue is not None
        # 後続処理が前提とする状態を確認する
        assert self.result_queue is not None
        # 次の値または処理を現在の構造へ組み込む
        self.request_id += 1
        # current_requestへこの工程で使用する値を設定する
        current_request = self.request_id
        # 次の値または処理を現在の構造へ組み込む
        self.task_queue.put((current_request, source, dict(semantic_ast)))
        # 失敗する可能性がある処理を開始する
        try:
            # 処理結果を呼び出し元へ返す
            returned_request, payload = self.result_queue.get(
                # timeoutへこの工程で使用する値を設定する
                timeout=self.timeout_seconds
            )
        # 発生した例外を受け取り、安全に処理する
        except queue.Empty:
            # 次の値または処理を現在の構造へ組み込む
            self._stop_worker()
            # 処理結果を呼び出し元へ返す
            return VerificationResult(True, True, True, False, False, True, "timeout")
        # 条件を満たす場合だけ次の処理を行う
        if returned_request != current_request:
            # 次の値または処理を現在の構造へ組み込む
            self._stop_worker()
            # 処理結果を呼び出し元へ返す
            return VerificationResult(
                # 次の値または処理を現在の構造へ組み込む
                True,
                # 次の値または処理を現在の構造へ組み込む
                True,
                # 次の値または処理を現在の構造へ組み込む
                True,
                # 次の値または処理を現在の構造へ組み込む
                False,
                # 次の値または処理を現在の構造へ組み込む
                False,
                # 次の値または処理を現在の構造へ組み込む
                False,
                # この処理で扱う文字列を一覧へ加える
                "検証プロセスから異なるリクエストの結果が返されました",
            )
        # 処理結果を呼び出し元へ返す
        return VerificationResult(**payload)

    # この工程を担当する関数を定義する
    def close(self) -> None:
        """検証プロセスと通信用キューを終了する。"""

        # 条件を満たす場合だけ次の処理を行う
        if self.process is not None and self.process.is_alive():
            # 後続処理が前提とする状態を確認する
            assert self.task_queue is not None
            # 次の値または処理を現在の構造へ組み込む
            self.task_queue.put(None)
            # 次の値または処理を現在の構造へ組み込む
            self.process.join(timeout=1.0)
        # 次の値または処理を現在の構造へ組み込む
        self._stop_worker()

    # この工程を担当する関数を定義する
    def _ensure_worker(self) -> None:
        # 条件を満たす場合だけ次の処理を行う
        if self.process is None or not self.process.is_alive():
            # 次の値または処理を現在の構造へ組み込む
            self._stop_worker()
            # 次の値または処理を現在の構造へ組み込む
            self._start_worker()

    # この工程を担当する関数を定義する
    def _start_worker(self) -> None:
        # self.task_queueへこの工程で使用する値を設定する
        self.task_queue = self.context.Queue(maxsize=1)
        # self.result_queueへこの工程で使用する値を設定する
        self.result_queue = self.context.Queue(maxsize=1)
        # self.processへこの工程で使用する値を設定する
        self.process = self.context.Process(
            # targetへこの工程で使用する値を設定する
            target=_verification_session_worker,
            # argsへこの工程で使用する値を設定する
            args=(self.cases, self.task_queue, self.result_queue),
        )
        # 次の値または処理を現在の構造へ組み込む
        self.process.start()

    # この工程を担当する関数を定義する
    def _stop_worker(self) -> None:
        # 条件を満たす場合だけ次の処理を行う
        if self.process is not None and self.process.is_alive():
            # 次の値または処理を現在の構造へ組み込む
            self.process.terminate()
            # 次の値または処理を現在の構造へ組み込む
            self.process.join()
        # 条件を満たす場合だけ次の処理を行う
        if self.task_queue is not None:
            # 次の値または処理を現在の構造へ組み込む
            self.task_queue.close()
            # 次の値または処理を現在の構造へ組み込む
            self.task_queue.join_thread()
        # 条件を満たす場合だけ次の処理を行う
        if self.result_queue is not None:
            # 次の値または処理を現在の構造へ組み込む
            self.result_queue.close()
            # 次の値または処理を現在の構造へ組み込む
            self.result_queue.join_thread()
        # self.processへこの工程で使用する値を設定する
        self.process = None
        # self.task_queueへこの工程で使用する値を設定する
        self.task_queue = None
        # self.result_queueへこの工程で使用する値を設定する
        self.result_queue = None


# この工程を担当する関数を定義する
def build_verification_cases(seed: int, random_case_count: int) -> list[tuple[list[int], int]]:
    """境界値と決定的なランダム入力を作る。"""

    # 条件を満たす場合だけ次の処理を行う
    if random_case_count < 0:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("random_case_countは0以上にしてください")
    # casesへこの工程で使用する値を設定する
    cases = [
        # 次の値または処理を現在の構造へ組み込む
        ([], 1),
        # 次の値または処理を現在の構造へ組み込む
        ([0], 1),
        # 次の値または処理を現在の構造へ組み込む
        ([1], 1),
        # 次の値または処理を現在の構造へ組み込む
        ([-1], 10),
        # 次の値または処理を現在の構造へ組み込む
        ([0, 0, 0], 3),
        # 次の値または処理を現在の構造へ組み込む
        ([-5, -1, 0, 1, 5], 2),
        # 次の値または処理を現在の構造へ組み込む
        ([5, 4, 3, 2, 1], 5),
        # 次の値または処理を現在の構造へ組み込む
        ([1, 1, 2, 2, 3, 3], 10),
        # 次の値または処理を現在の構造へ組み込む
        ([-100, 100], 1),
    ]
    # generatorへこの工程で使用する値を設定する
    generator = random.Random(seed)
    # 対象を一件ずつ取り出して処理する
    for _ in range(random_case_count):
        # lengthへこの工程で使用する値を設定する
        length = generator.randint(0, 20)
        # xsへこの工程で使用する値を設定する
        xs = [generator.randint(-100, 100) for _ in range(length)]
        # 次の値または処理を現在の構造へ組み込む
        cases.append((xs, generator.randint(1, 10)))
    # 処理結果を呼び出し元へ返す
    return cases


# この工程を担当する関数を定義する
def verify_generated_code(
    # 次の値または処理を現在の構造へ組み込む
    source: str,
    # 次の値または処理を現在の構造へ組み込む
    semantic_ast: Mapping[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    cases: Sequence[tuple[list[int], int]],
    # 次の値または処理を現在の構造へ組み込む
    timeout_seconds: float,
    # 次の値または処理を現在の構造へ組み込む
    max_source_chars: int,
# 次の値または処理を現在の構造へ組み込む
) -> VerificationResult:
    """静的検査後、子プロセスで全入力を参照インタプリタと照合する。"""

    # 使用するリソースの開始と終了をこの範囲で管理する
    with GeneratedCodeVerifierSession(
        # 次の値または処理を現在の構造へ組み込む
        cases,
        # 次の値または処理を現在の構造へ組み込む
        timeout_seconds,
        # 次の値または処理を現在の構造へ組み込む
        max_source_chars,
    # 次の値または処理を現在の構造へ組み込む
    ) as verifier:
        # 処理結果を呼び出し元へ返す
        return verifier.verify(source, semantic_ast)


# この工程を担当する関数を定義する
def _verification_session_worker(
    # 次の値または処理を現在の構造へ組み込む
    cases: list[tuple[list[int], int]],
    # 次の値または処理を現在の構造へ組み込む
    task_queue: multiprocessing.Queue,
    # 次の値または処理を現在の構造へ組み込む
    result_queue: multiprocessing.Queue,
# 次の値または処理を現在の構造へ組み込む
) -> None:
    """親プロセスから受け取ったコードを、同じ隔離プロセス内で順番に検証する。"""

    # 条件を満たす間は処理を繰り返す
    while True:
        # taskへこの工程で使用する値を設定する
        task = task_queue.get()
        # 条件を満たす場合だけ次の処理を行う
        if task is None:
            # 処理結果を呼び出し元へ返す
            return
        # 次の値または処理を現在の構造へ組み込む
        request_id, source, semantic_ast = task
        # payloadへこの工程で使用する値を設定する
        payload = _run_verification(source, semantic_ast, cases)
        # 次の値または処理を現在の構造へ組み込む
        result_queue.put((request_id, payload))


# この工程を担当する関数を定義する
def _verification_worker(
    # 次の値または処理を現在の構造へ組み込む
    source: str,
    # 次の値または処理を現在の構造へ組み込む
    semantic_ast: dict[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    cases: list[tuple[list[int], int]],
    # 次の値または処理を現在の構造へ組み込む
    result_queue: multiprocessing.Queue,
# 次の値または処理を現在の構造へ組み込む
) -> None:
    # 次の値または処理を現在の構造へ組み込む
    result_queue.put(_run_verification(source, semantic_ast, cases))


# この工程を担当する関数を定義する
def _run_verification(
    # 次の値または処理を現在の構造へ組み込む
    source: str,
    # 次の値または処理を現在の構造へ組み込む
    semantic_ast: dict[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    cases: list[tuple[list[int], int]],
# 次の値または処理を現在の構造へ組み込む
) -> dict[str, Any]:
    # 失敗する可能性がある処理を開始する
    try:
        # namespaceへこの工程で使用する値を設定する
        namespace: dict[str, Any] = {
            # 出力レコードの項目と値を設定する
            "__builtins__": {
                # 出力レコードの項目と値を設定する
                "abs": abs,
                # 出力レコードの項目と値を設定する
                "int": int,
                # 出力レコードの項目と値を設定する
                "list": list,
                # 出力レコードの項目と値を設定する
                "reversed": reversed,
                # 出力レコードの項目と値を設定する
                "sorted": sorted,
            }
        }
        # 次の値または処理を現在の構造へ組み込む
        exec(compile(source, "<generated>", "exec"), namespace)
        # solveへこの工程で使用する値を設定する
        solve = namespace["solve"]
        # 対象を一件ずつ取り出して処理する
        for original_xs, k in cases:
            # expectedへこの工程で使用する値を設定する
            expected = interpret(semantic_ast, list(original_xs), k)
            # first_inputへこの工程で使用する値を設定する
            first_input = list(original_xs)
            # firstへこの工程で使用する値を設定する
            first = solve(first_input, k)
            # input_unchangedへこの工程で使用する値を設定する
            input_unchanged = first_input == original_xs
            # valid_typeへこの工程で使用する値を設定する
            valid_type = isinstance(first, list) and all(type(value) is int for value in first)
            # 条件を満たす場合だけ次の処理を行う
            if not input_unchanged or not valid_type or first != expected:
                # 処理結果を呼び出し元へ返す
                return asdict(
                    # 次の値または処理を現在の構造へ組み込む
                    VerificationResult(
                        # 次の値または処理を現在の構造へ組み込む
                        True,
                        # 次の値または処理を現在の構造へ組み込む
                        True,
                        # 次の値または処理を現在の構造へ組み込む
                        True,
                        # 次の値または処理を現在の構造へ組み込む
                        False,
                        # 次の値または処理を現在の構造へ組み込む
                        input_unchanged,
                        # 次の値または処理を現在の構造へ組み込む
                        False,
                        # 次の値または処理を現在の構造へ組み込む
                        f"不一致: xs={original_xs!r}, k={k}, expected={expected!r}, actual={first!r}",
                    )
                )
        # 処理結果を呼び出し元へ返す
        return asdict(VerificationResult(True, True, True, True, True, False, None))
    # 発生した例外を受け取り、安全に処理する
    except BaseException as error:
        # 処理結果を呼び出し元へ返す
        return asdict(
            # 次の値または処理を現在の構造へ組み込む
            VerificationResult(
                # 次の値または処理を現在の構造へ組み込む
                True,
                # 次の値または処理を現在の構造へ組み込む
                True,
                # 次の値または処理を現在の構造へ組み込む
                True,
                # 次の値または処理を現在の構造へ組み込む
                False,
                # 次の値または処理を現在の構造へ組み込む
                False,
                # 次の値または処理を現在の構造へ組み込む
                False,
                # 次の値または処理を現在の構造へ組み込む
                f"{type(error).__name__}: {error}",
            )
        )
