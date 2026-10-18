#!/usr/bin/env python3
"""Looped Boku-nanoの周回・物理層別attentionを比較可視化する。"""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
import sys
from typing import Any

import torch
from tokenizers import Tokenizer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.model.evaluate_boku_nano import PROMPT_TEMPLATE  # noqa: E402
from scripts.model.visualize_boku_nano_kv import load_model, project_path  # noqa: E402


DEFAULT_INSTRUCTION = (
    "整数リストxsと整数kを受け取り、"
    "k以下の値だけを残すsolve関数を書いてください。"
)
EOS_ID = 2
DEFAULT_VARIANTS = ("u3", "u3_r2", "u3_r3")
LABELS = {
    "u3": "通常 3層×1周",
    "u3_r2": "元2周版",
    "u3_r3": "3層×3周",
    "u3_slow": "通常版・遅い減衰",
    "u3_r2_slow": "候補1・遅い減衰",
    "u3_r2_scaled": "候補2・残差0.5倍",
    "u3_r2_add": "候補3・入力再注入",
    "u3_middle4": "候補4・中間層4回",
    "u3_middle4_scaled025": "中間層4回・反復残差0.25倍",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, default=Path("data/tokenizers/bpe_2048/tokenizer.json"))
    parser.add_argument("--instruction", default=DEFAULT_INSTRUCTION)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--variants", nargs="+", default=list(DEFAULT_VARIANTS))
    return parser.parse_args()


def capture_attention(model: Any, token_ids: list[int]) -> tuple[torch.Tensor, torch.Tensor]:
    """1 forwardの全周回・全物理層について最終queryのattentionを返す。"""
    calls: list[tuple[int, torch.Tensor, torch.Tensor]] = []
    hooks = []
    for layer_index, block in enumerate(model.blocks):
        attention = block.attention

        def hook(
            _module: torch.nn.Module,
            _inputs: tuple[torch.Tensor, ...],
            output: torch.Tensor,
            index: int = layer_index,
            attention_module: Any = attention,
        ) -> None:
            query, key, _value = output.detach().chunk(3, dim=-1)
            length = query.size(1)
            shape = (1, length, attention_module.n_heads, attention_module.head_dim)
            query = query.view(shape).transpose(1, 2)
            key = key.view(shape).transpose(1, 2)
            query, key = attention_module.rope(query, key)
            calls.append((index, query[0].float().cpu(), key[0].float().cpu()))

        hooks.append(attention.qkv_proj.register_forward_hook(hook))
    try:
        with torch.inference_mode():
            logits = model(torch.tensor([token_ids], dtype=torch.long)).logits[0, -1].cpu()
    finally:
        for registered in hooks:
            registered.remove()
    effective = []
    for _layer_index, query, key in calls:
        scores = torch.einsum("hd,htd->ht", query[:, -1], key) / math.sqrt(key.size(-1))
        effective.append(torch.softmax(scores, dim=-1))
    if len(effective) != model.config.effective_layers:
        raise ValueError(
            f"block適用回数が設定と一致しません: {len(effective)} != "
            f"{model.config.effective_layers}"
        )
    return torch.stack(effective), logits


def effective_layer_labels(config: Any) -> list[str]:
    """実際のblock適用順に周回・物理層ラベルを返す。"""
    if config.loop_pattern == "middle":
        labels = ["前段 / L1"]
        for repeat in range(config.n_loops):
            labels.extend(
                f"中間{repeat + 1} / L{layer + 1}"
                for layer in range(1, config.n_layers - 1)
            )
        labels.append(f"後段 / L{config.n_layers}")
        return labels
    return [
        f"周回{loop + 1} / L{layer + 1}"
        for loop in range(config.n_loops)
        for layer in range(config.n_layers)
    ]


def generate_records(model: Any, prompt_ids: list[int], max_new_tokens: int) -> tuple[list[int], list[torch.Tensor], bool]:
    current = prompt_ids.copy()
    generated: list[int] = []
    records: list[torch.Tensor] = []
    reached_eos = False
    for _ in range(min(max_new_tokens, model.config.context_length - len(current))):
        attention, logits = capture_attention(model, current)
        predicted = int(torch.argmax(logits))
        if predicted == EOS_ID:
            reached_eos = True
            break
        records.append(attention)
        generated.append(predicted)
        current.append(predicted)
    return generated, records, reached_eos


def heatmap_svg(
    label: str, source_labels: list[str], attention: torch.Tensor, row_labels: list[str]
) -> str:
    # [effective layer, head, source]をhead平均し、周回と物理層を縦に並べる。
    matrix = attention.mean(dim=1)
    rows, columns = matrix.shape
    width = max(1000, 190 + columns * 28)
    height = 105 + rows * 34 + 105
    left, top, cell_h = 155, 76, 29
    plot_w = width - left - 26
    cell_w = plot_w / columns
    maximum = float(torch.quantile(matrix.flatten(), 0.98)) or 1.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f'<title>{html.escape(label)}の周回・物理層別attention</title>',
        '<desc>最終生成stepにおけるhead平均attention。濃いほど参照比率が高い。</desc>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#172033}.title{font-size:21px;font-weight:600}.sub{font-size:12px;fill:#5b6577}.axis{font-size:10px}</style>',
        f'<text x="{width / 2}" y="31" text-anchor="middle" class="title">{html.escape(label)}：周回・物理層別attention</text>',
        f'<text x="{width / 2}" y="52" text-anchor="middle" class="sub">最終生成step・4 head平均（行和=100%）</text>',
    ]
    for row in range(rows):
        y = top + row * cell_h
        parts.append(f'<text x="{left - 10}" y="{y + cell_h * .68:.1f}" text-anchor="end" class="axis">{html.escape(row_labels[row])}</text>')
        for column in range(columns):
            ratio = min(1.0, float(matrix[row, column]) / maximum)
            # 白から青への連続色。SVG単体で再現できるよう数値化する。
            start, end = (239, 246, 255), (29, 78, 216)
            rgb = tuple(round(a + (b - a) * ratio) for a, b in zip(start, end, strict=True))
            color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            parts.append(f'<rect x="{left + column * cell_w:.2f}" y="{y:.2f}" width="{cell_w + .2:.2f}" height="{cell_h - 2}" fill="{color}"/>')
    baseline = top + rows * cell_h + 7
    for column, token in enumerate(source_labels):
        x = left + (column + .5) * cell_w
        short = token if len(token) <= 8 else token[:7] + "…"
        parts.append(f'<text x="{x:.2f}" y="{baseline}" class="axis" transform="rotate(60 {x:.2f} {baseline})">{html.escape(short)}</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def region_svg(rows: list[dict[str, Any]]) -> str:
    width = 920
    height = 128 + len(rows) * 62
    left, top, plot_w, bar_h = 205, 76, 660, 39
    colors = {"control": "#64748b", "instruction": "#2563eb", "generated": "#f97316"}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<title>loop回数別の参照領域</title>',
        '<desc>全生成step、全実効層、全headで平均したattention領域比率。</desc>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#172033}.title{font-size:21px;font-weight:600}.sub{font-size:12px;fill:#5b6577}.axis{font-size:12px}</style>',
        '<text x="460" y="31" text-anchor="middle" class="title">loop回数別の参照領域</text>',
        '<text x="460" y="52" text-anchor="middle" class="sub">全生成step・全head平均。attention配置の記述であり、因果的重要度ではない。</text>',
    ]
    for index, row in enumerate(rows):
        y = top + index * 62
        parts.append(f'<text x="{left - 12}" y="{y + 25}" text-anchor="end" class="axis">{html.escape(row["label"])}</text>')
        cursor = left
        for region in ("control", "instruction", "generated"):
            value = float(row["region_attention"][region])
            width_part = value * plot_w
            parts.append(f'<rect x="{cursor:.2f}" y="{y}" width="{width_part:.2f}" height="{bar_h}" fill="{colors[region]}"/>')
            if value >= .08:
                parts.append(f'<text x="{cursor + width_part / 2:.2f}" y="{y + 25}" text-anchor="middle" fill="#fff" class="axis">{100 * value:.1f}%</text>')
            cursor += width_part
    for index, (region, label) in enumerate((("control", "制御token"), ("instruction", "日本語指示"), ("generated", "生成済みコード"))):
        x = left + index * 185
        parts += [f'<rect x="{x}" y="{height - 37}" width="14" height="14" fill="{colors[region]}"/>',
                  f'<text x="{x + 22}" y="{height - 25}" class="axis">{label}</text>']
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def main() -> None:
    args = parse_args()
    tokenizer = Tokenizer.from_file(str(args.tokenizer))
    prompt = PROMPT_TEMPLATE.format(instruction_ja=args.instruction)
    encoding = tokenizer.encode(prompt)
    prompt_ids = encoding.ids
    instruction_start = prompt.index(args.instruction)
    instruction_end = instruction_start + len(args.instruction)
    prompt_regions = [
        "instruction" if end > instruction_start and start < instruction_end else "control"
        for start, end in encoding.offsets
    ]
    args.output_directory.mkdir(parents=True, exist_ok=True)
    summaries = []
    for variant in args.variants:
        label = LABELS.get(variant, variant)
        directory = args.run_directory / f"{variant}_seed20260925/model"
        model, config = load_model(directory)
        generated, records, reached_eos = generate_records(model, prompt_ids, args.max_new_tokens)
        if not records:
            raise ValueError(f"attentionを記録できませんでした: {variant}")
        source_ids = prompt_ids + generated[:-1]
        source_labels = [
            (tokenizer.decode([token_id], skip_special_tokens=False) or f"id:{token_id}")
            .replace(" ", "␠").replace("\n", "↵")
            for token_id in source_ids
        ]
        final_attention = records[-1]
        figure = args.output_directory / f"{variant}_attention_heatmap.svg"
        figure.write_text(
            heatmap_svg(label, source_labels, final_attention, effective_layer_labels(config)),
            encoding="utf-8",
        )
        region_sums = {"control": 0.0, "instruction": 0.0, "generated": 0.0}
        observations = 0
        for step, attention in enumerate(records):
            mean = attention.mean(dim=(0, 1))
            regions = prompt_regions + ["generated"] * step
            for position, region in enumerate(regions):
                region_sums[region] += float(mean[position])
            observations += 1
        region_attention = {key: value / observations for key, value in region_sums.items()}
        summaries.append({
            "variant": variant,
            "label": label,
            "model_directory": project_path(directory),
            "n_layers": config.n_layers,
            "n_loops": config.n_loops,
            "effective_layers": config.effective_layers,
            "generated_text": tokenizer.decode(generated),
            "generated_token_count": len(generated),
            "reached_eos": reached_eos,
            "region_attention": region_attention,
            "figure": project_path(figure),
        })
    (args.output_directory / "attention_regions.svg").write_text(region_svg(summaries), encoding="utf-8")
    payload = {"instruction": args.instruction, "prompt": prompt, "models": summaries}
    (args.output_directory / "attention_metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote attention analysis to {args.output_directory}")


if __name__ == "__main__":
    main()
