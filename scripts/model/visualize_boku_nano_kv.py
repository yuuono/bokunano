"""Boku1-nanoの一時K/V状態と、KV cacheを導入した場合の容量を可視化する。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys
from typing import Any
from xml.sax.saxutils import escape

import torch
from safetensors.torch import load_file as load_safetensors
from tokenizers import Tokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM  # noqa: E402
from scripts.model.evaluate_boku_nano import PROMPT_TEMPLATE  # noqa: E402
from generated_code_verifier import build_verification_cases, verify_generated_code  # noqa: E402


DEFAULT_INSTRUCTION = "xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。"
DEFAULT_MODEL = PROJECT_ROOT / "data/models/boku_nano_bpe_2048"
DEFAULT_TOKENIZER = PROJECT_ROOT / "data/tokenizers/bpe_2048/tokenizer.json"
DEFAULT_FIGURE_DIRECTORY = PROJECT_ROOT / "docs/results/figures"
DEFAULT_METRICS = PROJECT_ROOT / "docs/results/boku_nano_kv_visualization_metrics.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Boku1-nanoのK/V内部状態とKV cache容量をSVGへ出力します。"
    )
    parser.add_argument("--model-directory", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--tokenizer", type=Path, default=DEFAULT_TOKENIZER)
    parser.add_argument("--instruction", default=DEFAULT_INSTRUCTION)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--figure-directory", type=Path, default=DEFAULT_FIGURE_DIRECTORY)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    return parser.parse_args()


def project_path(path: Path) -> str:
    """プロジェクト内の成果物は環境非依存の相対pathで記録する。"""

    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def load_model(directory: Path) -> tuple[BokuNanoForCausalLM, BokuNanoConfig]:
    config = BokuNanoConfig.from_dict(
        json.loads((directory / "model_config.json").read_text(encoding="utf-8"))
    )
    model = BokuNanoForCausalLM(config)
    model.load_state_dict(
        load_safetensors(str(directory / "model.safetensors"), device="cpu"),
        strict=True,
    )
    model.eval()
    return model, config


def greedy_generate(
    model: BokuNanoForCausalLM,
    prompt_ids: list[int],
    eos_token_id: int,
    max_new_tokens: int,
) -> tuple[list[int], int, bool]:
    current = prompt_ids.copy()
    generated: list[int] = []
    inference_calls = 0
    reached_eos = False
    limit = min(max_new_tokens, model.config.context_length - len(current))
    with torch.inference_mode():
        for _ in range(limit):
            logits = model(torch.tensor([current], dtype=torch.long)).logits[0, -1]
            inference_calls += 1
            token_id = int(torch.argmax(logits).item())
            if token_id == eos_token_id:
                reached_eos = True
                break
            generated.append(token_id)
            current.append(token_id)
    return generated, inference_calls, reached_eos


def capture_kv_rms(
    model: BokuNanoForCausalLM, token_ids: list[int]
) -> tuple[list[list[float]], list[list[float]], list[list[float]], list[list[float]]]:
    layer_keys: dict[int, torch.Tensor] = {}
    layer_values: dict[int, torch.Tensor] = {}
    hooks: list[Any] = []

    for layer_index, block in enumerate(model.blocks):
        attention = block.attention

        def capture(
            _module: torch.nn.Module,
            _inputs: tuple[torch.Tensor, ...],
            output: torch.Tensor,
            index: int = layer_index,
            attention_module: Any = attention,
        ) -> None:
            _, key, value = output.detach().chunk(3, dim=-1)
            sequence_length = key.size(1)
            key = key.view(1, sequence_length, attention_module.n_heads, attention_module.head_dim)
            key = key.transpose(1, 2)
            value = value.view(
                1, sequence_length, attention_module.n_heads, attention_module.head_dim
            ).transpose(1, 2)
            dummy_query = torch.zeros_like(key)
            _, rotated_key = attention_module.rope(dummy_query, key)
            layer_keys[index] = rotated_key.cpu()
            layer_values[index] = value.cpu()

        hooks.append(attention.qkv_proj.register_forward_hook(capture))

    try:
        with torch.inference_mode():
            model(torch.tensor([token_ids], dtype=torch.long))
    finally:
        for hook in hooks:
            hook.remove()

    key_token_rms: list[list[float]] = []
    value_token_rms: list[list[float]] = []
    key_head_rms: list[list[float]] = []
    value_head_rms: list[list[float]] = []
    for index in range(model.config.n_layers):
        key = layer_keys[index].float()[0]
        value = layer_values[index].float()[0]
        key_token_rms.append(key.pow(2).mean(dim=(0, 2)).sqrt().tolist())
        value_token_rms.append(value.pow(2).mean(dim=(0, 2)).sqrt().tolist())
        key_head_rms.append(key.pow(2).mean(dim=(1, 2)).sqrt().tolist())
        value_head_rms.append(value.pow(2).mean(dim=(1, 2)).sqrt().tolist())
    return key_token_rms, value_token_rms, key_head_rms, value_head_rms


def color(value: float, minimum: float, maximum: float) -> str:
    ratio = 0.5 if maximum <= minimum else (value - minimum) / (maximum - minimum)
    ratio = min(1.0, max(0.0, ratio))
    start = (232, 240, 247)
    end = (31, 78, 121)
    red = round(start[0] + (end[0] - start[0]) * ratio)
    green = round(start[1] + (end[1] - start[1]) * ratio)
    blue = round(start[2] + (end[2] - start[2]) * ratio)
    return f"#{red:02x}{green:02x}{blue:02x}"


def heatmap_svg(
    keys: list[list[float]],
    values: list[list[float]],
    prompt_length: int,
    destination: Path,
) -> None:
    token_count = len(keys[0])
    width = 1040
    left = 82
    right = 58
    plot_width = width - left - right
    cell_width = plot_width / token_count
    cell_height = 25
    panel_height = 8 * cell_height
    top = 86
    gap = 78
    height = top + panel_height * 2 + gap + 88
    all_values = [number for matrix in (keys, values) for row in matrix for number in row]
    minimum = min(all_values)
    maximum = max(all_values)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#17212b;font-size:13px}.small{font-size:11px;fill:#4b5967}.title{font-size:20px;font-weight:500}.label{font-size:14px;font-weight:500}</style>',
        '<text x="24" y="32" class="title">Boku1-nanoの一時K/V状態</text>',
        '<text x="24" y="56" class="small">各セルは6 head × 64次元のRMS。現在の実装では生成stepをまたいで保持しない。</text>',
    ]
    panels = [("Key（RoPE適用後）", keys, top), ("Value", values, top + panel_height + gap)]
    for title, matrix, y0 in panels:
        parts.append(f'<text x="{left}" y="{y0 - 14}" class="label">{escape(title)}</text>')
        for layer, row in enumerate(matrix):
            y = y0 + layer * cell_height
            parts.append(f'<text x="{left - 12}" y="{y + 17}" text-anchor="end" class="small">L{layer + 1}</text>')
            for token_index, number in enumerate(row):
                x = left + token_index * cell_width
                parts.append(
                    f'<rect x="{x:.2f}" y="{y}" width="{cell_width + 0.2:.2f}" height="{cell_height}" fill="{color(number, minimum, maximum)}"/>'
                )
        boundary = left + prompt_length * cell_width
        parts.append(
            f'<line x1="{boundary:.2f}" y1="{y0}" x2="{boundary:.2f}" y2="{y0 + panel_height}" stroke="#c33d2e" stroke-width="2"/>'
        )
        parts.append(
            f'<text x="{boundary + 5:.2f}" y="{y0 + 14}" class="small">生成開始</text>'
        )
        tick_step = max(1, math.ceil(token_count / 18))
        for token_index in range(0, token_count, tick_step):
            x = left + (token_index + 0.5) * cell_width
            parts.append(
                f'<text x="{x:.2f}" y="{y0 + panel_height + 18}" text-anchor="middle" class="small">{token_index}</text>'
            )
        parts.append(
            f'<text x="{left + plot_width / 2:.2f}" y="{y0 + panel_height + 39}" text-anchor="middle" class="small">token位置</text>'
        )
    legend_x = width - 230
    legend_y = height - 39
    for index in range(100):
        parts.append(
            f'<rect x="{legend_x + index * 1.5:.1f}" y="{legend_y}" width="1.6" height="13" fill="{color(minimum + (maximum - minimum) * index / 99, minimum, maximum)}"/>'
        )
    parts.extend(
        [
            f'<text x="{legend_x - 8}" y="{legend_y + 11}" text-anchor="end" class="small">{minimum:.3f}</text>',
            f'<text x="{legend_x + 158}" y="{legend_y + 11}" class="small">{maximum:.3f} RMS</text>',
            '</svg>',
        ]
    )
    destination.write_text("\n".join(parts), encoding="utf-8")


def memory_svg(config: BokuNanoConfig, destination: Path) -> None:
    width, height = 900, 440
    left, top, plot_width, plot_height = 82, 74, 750, 280
    context = config.context_length

    def cache_mib(tokens: int, bytes_per_value: int) -> float:
        elements = config.n_layers * 2 * config.n_heads * (config.d_model // config.n_heads) * tokens
        return elements * bytes_per_value / (1024 * 1024)

    maximum = cache_mib(context, 4)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#17212b;font-size:13px}.small{font-size:11px;fill:#4b5967}.title{font-size:20px;font-weight:500}.label{font-size:13px;font-weight:500}</style>',
        '<text x="24" y="32" class="title">KV cacheを導入した場合の容量上限</text>',
        '<text x="24" y="54" class="small">8層・6 KV head・head次元64・batch 1。現行実装の永続KV cache使用量は0 MiB。</text>',
    ]
    for tick in range(0, 7):
        y = top + plot_height - (tick / maximum) * plot_height
        parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#e3e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" class="small">{tick}</text>')
    for token in (0, 64, 128, 192, 256):
        x = left + token / context * plot_width
        parts.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_height}" stroke="#eef1f3" stroke-width="1"/>')
        parts.append(f'<text x="{x:.2f}" y="{top + plot_height + 22}" text-anchor="middle" class="small">{token}</text>')
    for bytes_per_value, stroke, label in ((2, "#246b8e", "BF16/FP16"), (4, "#b44c35", "FP32")):
        points=[]
        for token in range(context + 1):
            x=left + token/context*plot_width
            y=top + plot_height - cache_mib(token, bytes_per_value)/maximum*plot_height
            points.append(f"{x:.2f},{y:.2f}")
        parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{stroke}" stroke-width="3"/>')
        end_y=top + plot_height - cache_mib(context, bytes_per_value)/maximum*plot_height
        parts.append(f'<text x="{left + plot_width - 8}" y="{end_y - 8:.2f}" text-anchor="end" class="label" fill="{stroke}">{label}: {cache_mib(context, bytes_per_value):.1f} MiB</text>')
    parts.extend(
        [
            f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#66717d" stroke-width="1.5"/>',
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#66717d" stroke-width="1.5"/>',
            f'<text x="{left + plot_width / 2}" y="{height - 32}" text-anchor="middle">保持token数</text>',
            f'<text x="18" y="{top + plot_height / 2}" text-anchor="middle" transform="rotate(-90 18 {top + plot_height / 2})">KV容量（MiB）</text>',
            '</svg>',
        ]
    )
    destination.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.max_new_tokens <= 0:
        raise ValueError("max-new-tokensは正の整数にしてください")
    model, config = load_model(args.model_directory.resolve())
    tokenizer = Tokenizer.from_file(str(args.tokenizer.resolve()))
    prompt = PROMPT_TEMPLATE.format(instruction_ja=args.instruction)
    prompt_ids = tokenizer.encode(prompt, add_special_tokens=False).ids
    generated_ids, inference_calls, reached_eos = greedy_generate(
        model, prompt_ids, eos_token_id=2, max_new_tokens=args.max_new_tokens
    )
    full_ids = prompt_ids + generated_ids
    keys, values, key_heads, value_heads = capture_kv_rms(model, full_ids)
    generated_code = tokenizer.decode(generated_ids, skip_special_tokens=True)
    verification_cases = build_verification_cases(seed=20260929, random_case_count=55)
    verification = verify_generated_code(
        generated_code,
        {"sequence": [{"map": ["abs"]}, {"order": "descending"}]},
        verification_cases,
        timeout_seconds=5.0,
        max_source_chars=4096,
    )
    if not verification.tests_passed:
        raise AssertionError(f"可視化用生成コードの実行検証に失敗しました: {verification.error}")

    figure_directory = args.figure_directory.resolve()
    figure_directory.mkdir(parents=True, exist_ok=True)
    heatmap_path = figure_directory / "boku_nano_kv_state_heatmap.svg"
    memory_path = figure_directory / "boku_nano_kv_cache_memory.svg"
    heatmap_svg(keys, values, len(prompt_ids), heatmap_path)
    memory_svg(config, memory_path)

    prefix_lengths = [len(prompt_ids) + index for index in range(inference_calls)]
    current_projected_positions = sum(prefix_lengths)
    cached_projected_positions = len(prompt_ids) + max(0, inference_calls - 1)
    head_dim = config.d_model // config.n_heads
    elements_per_token = config.n_layers * 2 * config.n_heads * head_dim
    metrics = {
        "model_directory": project_path(args.model_directory),
        "model_config": asdict(config),
        "instruction": args.instruction,
        "prompt_token_count": len(prompt_ids),
        "generated_token_count": len(generated_ids),
        "inference_call_count": inference_calls,
        "reached_eos": reached_eos,
        "generated_code": generated_code,
        "execution_verification": {
            "semantic_ast": {"sequence": [{"map": ["abs"]}, {"order": "descending"}]},
            "case_count": len(verification_cases),
            **verification.to_record(),
        },
        "visualized_token_count": len(full_ids),
        "kv_shape_per_layer": [1, config.n_heads, len(full_ids), head_dim],
        "persistent_kv_cache_implemented": False,
        "hypothetical_cache": {
            "elements_per_token": elements_per_token,
            "bytes_per_token_bfloat16_or_float16": elements_per_token * 2,
            "bytes_per_token_float32": elements_per_token * 4,
            "max_mib_bfloat16_or_float16": elements_per_token * config.context_length * 2 / (1024 * 1024),
            "max_mib_float32": elements_per_token * config.context_length * 4 / (1024 * 1024),
        },
        "generation_projection_positions": {
            "current_full_prefix_recompute": current_projected_positions,
            "hypothetical_kv_cache": cached_projected_positions,
            "ratio": current_projected_positions / cached_projected_positions,
        },
        "key_rms_by_layer_and_token": keys,
        "value_rms_by_layer_and_token": values,
        "key_rms_by_layer_and_head": key_heads,
        "value_rms_by_layer_and_head": value_heads,
        "figures": [project_path(heatmap_path), project_path(memory_path)],
    }
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "prompt_tokens": len(prompt_ids),
        "generated_tokens": len(generated_ids),
        "inference_calls": inference_calls,
        "current_projection_positions": current_projected_positions,
        "cached_projection_positions": cached_projected_positions,
        "projection_ratio": metrics["generation_projection_positions"]["ratio"],
        "generated_code": metrics["generated_code"],
        "heatmap": str(heatmap_path),
        "memory": str(memory_path),
        "metrics": str(args.metrics),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
