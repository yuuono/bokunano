"""生成コードを隔離した子プロセスで実行し、参照結果と比較する。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import multiprocessing
import queue
import random
from typing import Any, Mapping, Sequence

from python_code_generator import validate_generated_code
from reference_interpreter import interpret


@dataclass(frozen=True)
class VerificationResult:
    syntax_ok: bool
    ast_safe: bool
    signature_ok: bool
    tests_passed: bool
    input_unchanged: bool
    timeout: bool
    error: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


class GeneratedCodeVerifierSession:
    """隔離プロセスを再利用し、複数の生成コードを1件ずつ検証する。"""

    def __init__(
        self,
        cases: Sequence[tuple[list[int], int]],
        timeout_seconds: float,
        max_source_chars: int,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_secondsは正の値にしてください")
        self.cases = [(list(xs), k) for xs, k in cases]
        self.timeout_seconds = timeout_seconds
        self.max_source_chars = max_source_chars
        self.context = multiprocessing.get_context("spawn")
        self.task_queue: multiprocessing.Queue | None = None
        self.result_queue: multiprocessing.Queue | None = None
        self.process: multiprocessing.Process | None = None
        self.request_id = 0

    def __enter__(self) -> GeneratedCodeVerifierSession:
        self._start_worker()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def verify(
        self,
        source: str,
        semantic_ast: Mapping[str, Any],
    ) -> VerificationResult:
        """静的検査後、隔離プロセスで1件を参照結果と照合する。"""

        try:
            validate_generated_code(source, self.max_source_chars)
        except Exception as error:
            return VerificationResult(False, False, False, False, False, False, str(error))

        self._ensure_worker()
        assert self.task_queue is not None
        assert self.result_queue is not None
        self.request_id += 1
        current_request = self.request_id
        self.task_queue.put((current_request, source, dict(semantic_ast)))
        try:
            returned_request, payload = self.result_queue.get(
                timeout=self.timeout_seconds
            )
        except queue.Empty:
            self._stop_worker()
            return VerificationResult(True, True, True, False, False, True, "timeout")
        if returned_request != current_request:
            self._stop_worker()
            return VerificationResult(
                True,
                True,
                True,
                False,
                False,
                False,
                "検証プロセスから異なるリクエストの結果が返されました",
            )
        return VerificationResult(**payload)

    def close(self) -> None:
        """検証プロセスと通信用キューを終了する。"""

        if self.process is not None and self.process.is_alive():
            assert self.task_queue is not None
            self.task_queue.put(None)
            self.process.join(timeout=1.0)
        self._stop_worker()

    def _ensure_worker(self) -> None:
        if self.process is None or not self.process.is_alive():
            self._stop_worker()
            self._start_worker()

    def _start_worker(self) -> None:
        self.task_queue = self.context.Queue(maxsize=1)
        self.result_queue = self.context.Queue(maxsize=1)
        self.process = self.context.Process(
            target=_verification_session_worker,
            args=(self.cases, self.task_queue, self.result_queue),
        )
        self.process.start()

    def _stop_worker(self) -> None:
        if self.process is not None and self.process.is_alive():
            self.process.terminate()
            self.process.join()
        if self.task_queue is not None:
            self.task_queue.close()
            self.task_queue.join_thread()
        if self.result_queue is not None:
            self.result_queue.close()
            self.result_queue.join_thread()
        self.process = None
        self.task_queue = None
        self.result_queue = None


def build_verification_cases(seed: int, random_case_count: int) -> list[tuple[list[int], int]]:
    """境界値と決定的なランダム入力を作る。"""

    if random_case_count < 0:
        raise ValueError("random_case_countは0以上にしてください")
    cases = [
        ([], 1),
        ([0], 1),
        ([1], 1),
        ([-1], 10),
        ([0, 0, 0], 3),
        ([-5, -1, 0, 1, 5], 2),
        ([5, 4, 3, 2, 1], 5),
        ([1, 1, 2, 2, 3, 3], 10),
        ([-100, 100], 1),
    ]
    generator = random.Random(seed)
    for _ in range(random_case_count):
        length = generator.randint(0, 20)
        xs = [generator.randint(-100, 100) for _ in range(length)]
        cases.append((xs, generator.randint(1, 10)))
    return cases


def verify_generated_code(
    source: str,
    semantic_ast: Mapping[str, Any],
    cases: Sequence[tuple[list[int], int]],
    timeout_seconds: float,
    max_source_chars: int,
) -> VerificationResult:
    """静的検査後、子プロセスで全入力を参照インタプリタと照合する。"""

    with GeneratedCodeVerifierSession(
        cases,
        timeout_seconds,
        max_source_chars,
    ) as verifier:
        return verifier.verify(source, semantic_ast)


def _verification_session_worker(
    cases: list[tuple[list[int], int]],
    task_queue: multiprocessing.Queue,
    result_queue: multiprocessing.Queue,
) -> None:
    """親プロセスから受け取ったコードを、同じ隔離プロセス内で順番に検証する。"""

    while True:
        task = task_queue.get()
        if task is None:
            return
        request_id, source, semantic_ast = task
        payload = _run_verification(source, semantic_ast, cases)
        result_queue.put((request_id, payload))


def _verification_worker(
    source: str,
    semantic_ast: dict[str, Any],
    cases: list[tuple[list[int], int]],
    result_queue: multiprocessing.Queue,
) -> None:
    result_queue.put(_run_verification(source, semantic_ast, cases))


def _run_verification(
    source: str,
    semantic_ast: dict[str, Any],
    cases: list[tuple[list[int], int]],
) -> dict[str, Any]:
    try:
        namespace: dict[str, Any] = {
            "__builtins__": {
                "abs": abs,
                "int": int,
                "list": list,
                "reversed": reversed,
                "sorted": sorted,
            }
        }
        exec(compile(source, "<generated>", "exec"), namespace)
        solve = namespace["solve"]
        for original_xs, k in cases:
            expected = interpret(semantic_ast, list(original_xs), k)
            first_input = list(original_xs)
            first = solve(first_input, k)
            input_unchanged = first_input == original_xs
            valid_type = isinstance(first, list) and all(type(value) is int for value in first)
            if not input_unchanged or not valid_type or first != expected:
                return asdict(
                    VerificationResult(
                        True,
                        True,
                        True,
                        False,
                        input_unchanged,
                        False,
                        f"不一致: xs={original_xs!r}, k={k}, expected={expected!r}, actual={first!r}",
                    )
                )
        return asdict(VerificationResult(True, True, True, True, True, False, None))
    except BaseException as error:
        return asdict(
            VerificationResult(
                True,
                True,
                True,
                False,
                False,
                False,
                f"{type(error).__name__}: {error}",
            )
        )
