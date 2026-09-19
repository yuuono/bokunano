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

    if timeout_seconds <= 0:
        raise ValueError("timeout_secondsは正の値にしてください")
    try:
        validate_generated_code(source, max_source_chars)
    except Exception as error:
        return VerificationResult(False, False, False, False, False, False, str(error))

    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_verification_worker,
        args=(source, dict(semantic_ast), list(cases), result_queue),
    )
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        return VerificationResult(True, True, True, False, False, True, "timeout")

    try:
        payload = result_queue.get(timeout=0.2)
    except queue.Empty:
        return VerificationResult(
            True,
            True,
            True,
            False,
            False,
            False,
            f"検証プロセスが結果を返しませんでした: exitcode={process.exitcode}",
        )
    return VerificationResult(**payload)


def _verification_worker(
    source: str,
    semantic_ast: dict[str, Any],
    cases: list[tuple[list[int], int]],
    result_queue: multiprocessing.Queue,
) -> None:
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
                result_queue.put(
                    asdict(
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
                )
                return
        result_queue.put(
            asdict(VerificationResult(True, True, True, True, True, False, None))
        )
    except BaseException as error:
        result_queue.put(
            asdict(
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
        )
