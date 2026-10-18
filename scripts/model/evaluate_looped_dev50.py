#!/usr/bin/env python3
"""Looped Boku-nanoを自然な日本語の固定dev50でgreedy評価する。"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.model.evaluate_boku_nano import (  # noqa: E402
    PROMPT_TEMPLATE,
    encode_prompt,
    greedy_generate_equal_length,
    load_model,
)

VARIANTS = ("u3_middle4", "u3_middle4_scaled025")
SPECIAL_IDS = {"pad": 0, "bos": 1, "eos": 2, "unk": 3, "task": 4, "code": 5}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--questions", type=Path,
                        default=Path("data/benchmarks/browser_100/dev50.jsonl"))
    parser.add_argument("--tokenizer", type=Path,
                        default=Path("data/tokenizers/bpe_2048/tokenizer.json"))
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", choices=("float32", "bfloat16"), default="bfloat16")
    parser.add_argument("--max-new-tokens", type=int, default=160)
    args = parser.parse_args()
    if args.output_directory.exists():
        parser.error(f"既存の出力先を上書きしません: {args.output_directory}")
    questions = [json.loads(line) for line in args.questions.read_text(encoding="utf-8").splitlines()
                 if line]
    tokenizer = Tokenizer.from_file(str(args.tokenizer))
    args.output_directory.mkdir(parents=True)
    for variant in args.variants:
        started = time.perf_counter()
        output = args.output_directory / variant
        output.mkdir()
        model_directory = args.run_directory / f"{variant}_seed20260925/model"
        model, device = load_model(model_directory, "model_config.json", "model.safetensors",
                                   args.device, args.dtype)
        prompts = [encode_prompt(tokenizer, row["instruction_ja"], SPECIAL_IDS,
                                 model.config.context_length) for row in questions]
        grouped: dict[int, list[int]] = defaultdict(list)
        for index, prompt_ids in enumerate(prompts):
            grouped[len(prompt_ids)].append(index)
        generated: list[dict | None] = [None] * len(questions)
        for indices in grouped.values():
            batch = greedy_generate_equal_length(
                model,
                [prompts[index] for index in indices],
                eos_token_id=SPECIAL_IDS["eos"],
                pad_token_id=SPECIAL_IDS["pad"],
                max_new_tokens=args.max_new_tokens,
                context_length=model.config.context_length,
                device=device,
            )
            for index, result in zip(indices, batch, strict=True):
                generated[index] = result
        elapsed = time.perf_counter() - started
        records = []
        for question, prompt_ids, result in zip(questions, prompts, generated, strict=True):
            assert result is not None
            output_ids = result["generated_token_ids"]
            records.append({
                "kind": "inference",
                "run_id": f"middle4-3epoch-{variant}-dev50",
                "question_id": question["question_id"],
                "category_id": question["category_id"],
                "model": "boku",
                "model_id": variant,
                "condition": "A",
                "instruction": question["instruction_ja"],
                "backend": device.type,
                "temperature": 0,
                "prompt": PROMPT_TEMPLATE.format(instruction_ja=question["instruction_ja"]),
                "prompt_ids": prompt_ids,
                "output_ids": output_ids,
                "raw_output": tokenizer.decode(output_ids, skip_special_tokens=True),
                "termination": result["termination"],
            })
        (output / "raw_inference.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
            encoding="utf-8",
        )
        config = {
            "run_id": f"middle4-3epoch-{variant}-dev50",
            "variant": variant,
            "question_count": len(questions),
            "questions_sha256": hashlib.sha256(args.questions.read_bytes()).hexdigest(),
            "decoding": "greedy",
            "max_new_tokens": args.max_new_tokens,
            "elapsed_seconds": elapsed,
        }
        (output / "config.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        subprocess.run([
            sys.executable,
            str(ROOT / "scripts/model/score_browser_100_benchmark.py"),
            "--questions", str(args.questions),
            "--run", str(output),
        ], check=True)


if __name__ == "__main__":
    main()
