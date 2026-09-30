"""生成stepごとのQuery、attention、K/V類似度を解析してSVGへ出力する。"""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Any
from xml.sax.saxutils import escape

import torch
import torch.nn.functional as F
from tokenizers import Tokenizer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.model.evaluate_boku_nano import PROMPT_TEMPLATE  # noqa: E402
from scripts.model.visualize_boku_nano_kv import (  # noqa: E402
    DEFAULT_INSTRUCTION,
    DEFAULT_MODEL,
    DEFAULT_TOKENIZER,
    load_model,
    project_path,
)

FIGURE_DIR = PROJECT_ROOT / "docs/results/figures"
METRICS_PATH = PROJECT_ROOT / "docs/results/boku_nano_attention_analysis.json"


def label(tokenizer: Tokenizer, token_id: int) -> str:
    value = tokenizer.decode([token_id], skip_special_tokens=False)
    return (value or f"id:{token_id}").replace(" ", "␠").replace("\n", "↵")


def capture_qkv(
    model: Any, token_ids: list[int]
) -> tuple[
    list[torch.Tensor],
    list[torch.Tensor],
    list[torch.Tensor],
    list[torch.Tensor],
    torch.Tensor,
]:
    """各層のRoPE適用後Q/K、V、fused attention出力を取得する。"""
    captured: dict[int, tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = {}
    fused_contexts: dict[int, torch.Tensor] = {}
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
            query, key, value = output.detach().chunk(3, dim=-1)
            sequence_length = query.size(1)
            shape = (1, sequence_length, attention_module.n_heads, attention_module.head_dim)
            query = query.view(shape).transpose(1, 2)
            key = key.view(shape).transpose(1, 2)
            value = value.view(shape).transpose(1, 2)
            query, key = attention_module.rope(query, key)
            captured[index] = (query[0].float().cpu(), key[0].float().cpu(), value[0].float().cpu())

        def capture_fused_context(
            _module: torch.nn.Module,
            inputs: tuple[torch.Tensor, ...],
            index: int = layer_index,
            attention_module: Any = attention,
        ) -> None:
            attended = inputs[0].detach()[0, -1]
            fused_contexts[index] = attended.view(
                attention_module.n_heads, attention_module.head_dim
            ).float().cpu()

        hooks.append(attention.qkv_proj.register_forward_hook(hook))
        hooks.append(attention.out_proj.register_forward_pre_hook(capture_fused_context))
    try:
        with torch.inference_mode():
            logits = model(torch.tensor([token_ids], dtype=torch.long)).logits[0, -1].cpu()
    finally:
        for registered in hooks:
            registered.remove()
    ordered = [captured[index] for index in range(model.config.n_layers)]
    contexts = [fused_contexts[index] for index in range(model.config.n_layers)]
    return (
        [item[0] for item in ordered],
        [item[1] for item in ordered],
        [item[2] for item in ordered],
        contexts,
        logits,
    )


def generate(model: Any, prompt_ids: list[int], eos_id: int = 2, max_new_tokens: int = 64) -> tuple[list[int], list[dict[str, Any]], bool]:
    current = prompt_ids.copy()
    generated: list[int] = []
    records: list[dict[str, Any]] = []
    reached_eos = False
    limit = min(max_new_tokens, model.config.context_length - len(current))
    for _ in range(limit):
        queries, keys, values, fused_contexts, logits = capture_qkv(model, current)
        predicted_id = int(torch.argmax(logits).item())
        if predicted_id == eos_id:
            reached_eos = True
            break
        attention = []
        validation = []
        for query, key, value, fused_context in zip(
            queries, keys, values, fused_contexts, strict=True
        ):
            score = torch.einsum("hd,htd->ht", query[:, -1], key) / math.sqrt(key.size(-1))
            weights = torch.softmax(score, dim=-1)
            attention.append(weights)
            reconstructed = torch.einsum("ht,htd->hd", weights, value)
            difference = reconstructed - fused_context
            validation.append({
                "maximum_absolute_error": float(difference.abs().max()),
                "mean_absolute_error": float(difference.abs().mean()),
                "cosine_similarity": float(F.cosine_similarity(
                    reconstructed.flatten(), fused_context.flatten(), dim=0
                )),
            })
        records.append({
            "source_ids": current.copy(),
            "predicted_id": predicted_id,
            "last_query": torch.stack([query[:, -1] for query in queries]),
            "attention": torch.stack(attention),
            "attention_output_validation": validation,
        })
        generated.append(predicted_id)
        current.append(predicted_id)
    return generated, records, reached_eos


def full_states(model: Any, token_ids: list[int]) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
    _queries, keys, values, _contexts, _logits = capture_qkv(model, token_ids)
    return keys, values


def cosine_matrix(states: list[torch.Tensor]) -> torch.Tensor:
    matrices = []
    for state in states:
        normalized = F.normalize(state, dim=-1)
        matrices.append(torch.einsum("htd,hsd->hts", normalized, normalized))
    return torch.stack(matrices).mean(dim=(0, 1))


def blue(value: float, maximum: float) -> str:
    ratio = min(1.0, max(0.0, value / maximum if maximum else 0.0))
    start, end = (240, 244, 247), (24, 73, 111)
    rgb = [round(a + (b - a) * ratio) for a, b in zip(start, end, strict=True)]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def diverging(value: float) -> str:
    value = min(1.0, max(-1.0, value))
    low, mid, high = (49, 105, 151), (248, 248, 246), (179, 54, 44)
    if value < 0:
        start, end, ratio = low, mid, value + 1
    else:
        start, end, ratio = mid, high, value
    rgb = [round(a + (b - a) * ratio) for a, b in zip(start, end, strict=True)]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def svg_header(width: int, height: int, title: str, description: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f'<title>{escape(title)}</title>',
        f'<desc>{escape(description)}</desc>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#17212b;font-size:12px}.small{font-size:10px;fill:#52606d}.title{font-size:20px;font-weight:500}.label{font-size:13px;font-weight:500}</style>',
        f'<text x="24" y="30" class="title">{escape(title)}</text>',
        f'<text x="24" y="52" class="small">{escape(description)}</text>',
    ]


def attention_grid(
    records: list[dict[str, Any]], prompt_length: int, destination: Path
) -> None:
    layers, heads = records[0]["attention"].shape[:2]
    positions = max(len(record["source_ids"]) for record in records)
    steps = len(records)
    panel_w, panel_h, gap_x, gap_y = 132, 82, 24, 24
    left, top = 58, 82
    width = left + heads * (panel_w + gap_x) + 24
    height = top + layers * (panel_h + gap_y) + 46
    all_values = torch.cat([record["attention"].flatten() for record in records])
    maximum = float(torch.quantile(all_values, 0.98))
    parts = svg_header(
        width,
        height,
        "生成step × 参照token位置のattention",
        "8層 × 6 head。各行は生成step、各列は過去token位置。赤線より右が生成済みコード。",
    )
    for layer in range(layers):
        for head in range(heads):
            x0 = left + head * (panel_w + gap_x)
            y0 = top + layer * (panel_h + gap_y)
            parts.append(f'<text x="{x0}" y="{y0 - 6}" class="small">L{layer + 1} / H{head + 1}</text>')
            for step, record in enumerate(records):
                row = record["attention"][layer, head]
                for position in range(positions):
                    fill = "#edf0f2" if position >= len(row) else blue(float(row[position]), maximum)
                    x = x0 + position * panel_w / positions
                    y = y0 + step * panel_h / steps
                    parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{panel_w / positions + .15:.2f}" height="{panel_h / steps + .15:.2f}" fill="{fill}"/>')
            boundary = x0 + prompt_length * panel_w / positions
            parts.append(
                f'<line x1="{boundary:.2f}" y1="{y0}" x2="{boundary:.2f}" '
                f'y2="{y0 + panel_h}" stroke="#c43b2f" stroke-width="1.5"/>'
            )
    parts.append(f'<text x="{width / 2}" y="{height - 16}" text-anchor="middle" class="small">横: 参照token位置　縦: 生成step（上から下）　赤線: コード生成開始位置</text>')
    parts.append('</svg>')
    destination.write_text("\n".join(parts), encoding="utf-8")


def regions_from_offsets(prompt: str, instruction: str, offsets: list[tuple[int, int]]) -> list[str]:
    start, end = prompt.index(instruction), prompt.index(instruction) + len(instruction)
    return ["instruction" if offset_end > start and offset_start < end else "control" for offset_start, offset_end in offsets]


def analyze(
    records: list[dict[str, Any]], prompt_regions: list[str], full_ids: list[int], tokenizer: Tokenizer
) -> tuple[list[dict[str, Any]], list[dict[str, float]], list[dict[str, Any]], list[dict[str, Any]]]:
    token_count = len(full_ids)
    sums = [0.0] * token_count
    opportunities = [0] * token_count
    hits = [0] * token_count
    layer_heads = [set() for _ in range(token_count)]
    steps_seen = [set() for _ in range(token_count)]
    top_rows, region_rows = [], []
    query_count = records[0]["attention"].size(0) * records[0]["attention"].size(1)
    for step, record in enumerate(records):
        attention = record["attention"]
        mean_attention = attention.mean(dim=(0, 1))
        top_positions = torch.topk(mean_attention, min(5, len(mean_attention))).indices.tolist()
        top_rows.append({
            "step": step + 1,
            "generated_token": label(tokenizer, record["predicted_id"]),
            "references": [{
                "position": position,
                "token": label(tokenizer, record["source_ids"][position]),
                "attention": float(mean_attention[position]),
            } for position in top_positions],
        })
        row = {"control": 0.0, "instruction": 0.0, "generated_code": 0.0}
        for position, value in enumerate(mean_attention.tolist()):
            category = prompt_regions[position] if position < len(prompt_regions) else "generated_code"
            row[category] += value
            sums[position] += value
            opportunities[position] += 1
        row["beginning_4"] = float(mean_attention[:4].sum())
        row["recent_4"] = float(mean_attention[-4:].sum())
        region_rows.append(row)
        for layer in range(attention.size(0)):
            for head in range(attention.size(1)):
                for position in torch.topk(attention[layer, head], min(5, attention.size(-1))).indices.tolist():
                    hits[position] += 1
                    layer_heads[position].add((layer, head))
                    steps_seen[position].add(step)
    usage = []
    for position, token_id in enumerate(full_ids):
        if not opportunities[position]:
            continue
        usage.append({
            "position": position,
            "token": label(tokenizer, token_id),
            "available_steps": opportunities[position],
            "mean_attention": sums[position] / opportunities[position],
            "top5_hits": hits[position],
            "top5_hit_rate": hits[position] / (opportunities[position] * query_count),
            "distinct_layer_heads": len(layer_heads[position]),
            "referenced_steps": len(steps_seen[position]),
        })
    repeated = sorted(usage, key=lambda item: (-item["top5_hit_rate"], -item["mean_attention"]))[:8]
    eligible = [item for item in usage if item["available_steps"] >= 3]
    barely = sorted(eligible, key=lambda item: (item["mean_attention"], item["top5_hit_rate"]))[:8]
    return top_rows, region_rows, repeated, barely


def summarize_region_attention(
    records: list[dict[str, Any]], prompt_regions: list[str]
) -> dict[str, Any]:
    """token数の違いを補正し、日本語指示が一様分布より強いかを集計する。"""
    control_positions = [
        index for index, category in enumerate(prompt_regions) if category == "control"
    ]
    instruction_positions = [
        index for index, category in enumerate(prompt_regions) if category == "instruction"
    ]
    per_step = []
    instruction_by_layer_head = []
    for step, record in enumerate(records):
        attention = record["attention"]
        mean_attention = attention.mean(dim=(0, 1))
        generated_positions = list(range(len(prompt_regions), len(record["source_ids"])))
        position_groups = {
            "control": control_positions,
            "instruction": instruction_positions,
            "generated_code": generated_positions,
        }
        row: dict[str, Any] = {"step": step + 1}
        for category, positions in position_groups.items():
            mass = float(mean_attention[positions].sum()) if positions else 0.0
            expected = len(positions) / len(record["source_ids"])
            row[category] = {
                "token_count": len(positions),
                "attention_mass": mass,
                "attention_per_token": mass / len(positions) if positions else None,
                "uniform_expected_mass": expected,
                "relative_to_uniform": mass / expected if expected else None,
            }
        per_step.append(row)
        instruction_by_layer_head.append(attention[:, :, instruction_positions].sum(dim=-1))

    categories: dict[str, Any] = {}
    for category in ("control", "instruction", "generated_code"):
        available = [row[category] for row in per_step if row[category]["token_count"]]
        categories[category] = {
            "mean_attention_mass": sum(row[category]["attention_mass"] for row in per_step) / len(per_step),
            "mean_attention_per_token_when_available": sum(
                row["attention_per_token"] for row in available
            ) / len(available),
            "mean_uniform_expected_mass": sum(
                row[category]["uniform_expected_mass"] for row in per_step
            ) / len(per_step),
            "mean_relative_to_uniform_when_available": sum(
                row["relative_to_uniform"] for row in available
            ) / len(available),
        }
    instruction_matrix = torch.stack(instruction_by_layer_head).mean(dim=0)
    ranked = []
    for layer in range(instruction_matrix.size(0)):
        for head in range(instruction_matrix.size(1)):
            ranked.append({
                "layer": layer + 1,
                "head": head + 1,
                "mean_instruction_attention": float(instruction_matrix[layer, head]),
            })
    ranked.sort(key=lambda row: -row["mean_instruction_attention"])
    return {
        "prompt_region_token_counts": {
            "control": len(control_positions),
            "instruction": len(instruction_positions),
        },
        "categories": categories,
        "instruction_attention_by_layer_head": instruction_matrix.tolist(),
        "highest_instruction_attention_heads": ranked[:5],
        "lowest_instruction_attention_heads": list(reversed(ranked[-5:])),
        "per_step": per_step,
    }


def region_chart(rows: list[dict[str, float]], destination: Path) -> None:
    width, height = 940, 520
    left, top, plot_w, panel_h = 76, 82, 820, 155
    palette = {"control": "#9fb8c9", "instruction": "#3d7591", "generated_code": "#d08a55"}
    parts = svg_header(width, height, "生成中にどの領域を参照したか", "上は排他的な領域内訳。下は冒頭4 tokenと直近4 tokenへのattentionで、上の領域とは重複する。")
    bar_w = plot_w / len(rows) * .72
    for index, row in enumerate(rows):
        x = left + (index + .5) * plot_w / len(rows) - bar_w / 2
        y = top + panel_h
        for key in ("control", "instruction", "generated_code"):
            block = row[key] * panel_h
            y -= block
            parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{block:.2f}" fill="{palette[key]}"/>')
        parts.append(f'<text x="{x + bar_w / 2:.2f}" y="{top + panel_h + 18}" text-anchor="middle" class="small">{index + 1}</text>')
    legend_x = left
    for key, text in (("control", "制御token"), ("instruction", "日本語指示"), ("generated_code", "生成済みコード")):
        parts.append(f'<rect x="{legend_x}" y="{top + panel_h + 34}" width="12" height="12" fill="{palette[key]}"/>')
        parts.append(f'<text x="{legend_x + 17}" y="{top + panel_h + 44}" class="small">{text}</text>')
        legend_x += 140
    lower_top = 330
    for tick in range(6):
        y = lower_top + panel_h - tick / 5 * panel_h
        parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#e5e8eb"/>')
        parts.append(f'<text x="{left - 9}" y="{y + 4:.2f}" text-anchor="end" class="small">{tick * 20}%</text>')
    for key, stroke, text in (("beginning_4", "#704c7d", "冒頭4 token"), ("recent_4", "#2f7d61", "直近4 token")):
        points = []
        for index, row in enumerate(rows):
            x = left + (index + .5) * plot_w / len(rows)
            y = lower_top + panel_h - row[key] * panel_h
            points.append(f"{x:.2f},{y:.2f}")
        parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{stroke}" stroke-width="3"/>')
        parts.append(f'<text x="{left + plot_w - 4}" y="{lower_top + (18 if key == "beginning_4" else 36)}" text-anchor="end" class="small">{text}</text>')
    parts.append(f'<text x="{width / 2}" y="{height - 12}" text-anchor="middle" class="small">生成step</text>')
    parts.append('</svg>')
    destination.write_text("\n".join(parts), encoding="utf-8")


def cosine_chart(key_matrix: torch.Tensor, value_matrix: torch.Tensor, destination: Path) -> None:
    count = key_matrix.size(0)
    width, height, top, size, gap, left = 980, 510, 88, 390, 76, 68
    parts = svg_header(width, height, "Key／Valueのtoken間コサイン類似度", "最終token列を8層・6 headで平均。対角は同じtokenなので1.0。青は負、赤は正の類似。")
    for title, matrix, x0 in (("Key（RoPE後）", key_matrix, left), ("Value", value_matrix, left + size + gap)):
        parts.append(f'<text x="{x0}" y="{top - 12}" class="label">{title}</text>')
        cell = size / count
        for row in range(count):
            for column in range(count):
                parts.append(f'<rect x="{x0 + column * cell:.2f}" y="{top + row * cell:.2f}" width="{cell + .15:.2f}" height="{cell + .15:.2f}" fill="{diverging(float(matrix[row, column]))}"/>')
        for tick in range(0, count, 5):
            parts.append(f'<text x="{x0 + (tick + .5) * cell:.2f}" y="{top + size + 17}" text-anchor="middle" class="small">{tick}</text>')
            parts.append(f'<text x="{x0 - 7}" y="{top + (tick + .7) * cell:.2f}" text-anchor="end" class="small">{tick}</text>')
    parts.append(f'<text x="{width / 2}" y="{height - 18}" text-anchor="middle" class="small">横・縦: token位置　　青 -1 ← 0 → +1 赤</text>')
    parts.append('</svg>')
    destination.write_text("\n".join(parts), encoding="utf-8")


def utilization_chart(repeated: list[dict[str, Any]], barely: list[dict[str, Any]], destination: Path) -> None:
    width, height = 980, 540
    parts = svg_header(width, height, "繰り返し参照されたtoken／参照の少ないtoken", "左は全層・全headでtop 5に入った率。右は参照可能なstepでの平均attention。いずれも出現機会で正規化。")
    panels = (("top 5へ繰り返し入ったtoken", repeated, "top5_hit_rate", "#356f8a"), ("平均attentionが小さいtoken", barely, "mean_attention", "#a96745"))
    for panel_index, (title, rows, metric, fill) in enumerate(panels):
        x0, y0, plot_w, row_h = 34 + panel_index * 486, 90, 430, 46
        maximum = max(float(row[metric]) for row in rows) or 1
        parts.append(f'<text x="{x0}" y="{y0 - 12}" class="label">{title}</text>')
        for index, row in enumerate(rows):
            y = y0 + index * row_h
            text = f'{row["position"]}: {row["token"]}'
            value = float(row[metric])
            parts.append(f'<text x="{x0}" y="{y + 13}" class="small">{escape(text[:24])}</text>')
            parts.append(f'<rect x="{x0}" y="{y + 19}" width="{plot_w}" height="14" fill="#edf0f2"/>')
            parts.append(f'<rect x="{x0}" y="{y + 19}" width="{plot_w * value / maximum:.2f}" height="14" fill="{fill}"/>')
            parts.append(f'<text x="{x0 + plot_w}" y="{y + 13}" text-anchor="end" class="small">{value * 100:.2f}%</text>')
    parts.append('</svg>')
    destination.write_text("\n".join(parts), encoding="utf-8")


def cosine_summary(matrix: torch.Tensor, ids: list[int], tokenizer: Tokenizer) -> dict[str, Any]:
    count = matrix.size(0)
    mask = ~torch.eye(count, dtype=torch.bool)
    off = matrix[mask]
    ranked = matrix.clone()
    ranked.fill_diagonal_(-2)
    flat = int(torch.argmax(ranked))
    first, second = divmod(flat, count)
    return {
        "mean_off_diagonal": float(off.mean()),
        "mean_absolute_off_diagonal": float(off.abs().mean()),
        "maximum_off_diagonal": float(ranked[first, second]),
        "maximum_pair": [
            {"position": first, "token": label(tokenizer, ids[first])},
            {"position": second, "token": label(tokenizer, ids[second])},
        ],
    }


def rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item) for item in value]
    return value


def main() -> None:
    model, config = load_model(DEFAULT_MODEL)
    tokenizer = Tokenizer.from_file(str(DEFAULT_TOKENIZER))
    instruction = DEFAULT_INSTRUCTION
    prompt = PROMPT_TEMPLATE.format(instruction_ja=instruction)
    encoding = tokenizer.encode(prompt, add_special_tokens=False)
    generated, records, reached_eos = generate(model, encoding.ids)
    full_ids = encoding.ids + generated
    keys, values = full_states(model, full_ids)
    key_cosine, value_cosine = cosine_matrix(keys), cosine_matrix(values)
    prompt_regions = regions_from_offsets(prompt, instruction, encoding.offsets)
    top_rows, region_rows, repeated, barely = analyze(records, prompt_regions, full_ids, tokenizer)
    region_summary = summarize_region_attention(records, prompt_regions)

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    figures = {
        "attention_by_layer_head": FIGURE_DIR / "boku_nano_attention_by_layer_head.svg",
        "attention_regions": FIGURE_DIR / "boku_nano_attention_regions.svg",
        "kv_cosine": FIGURE_DIR / "boku_nano_kv_cosine_similarity.svg",
        "token_utilization": FIGURE_DIR / "boku_nano_token_utilization.svg",
    }
    attention_grid(records, len(encoding.ids), figures["attention_by_layer_head"])
    region_chart(region_rows, figures["attention_regions"])
    cosine_chart(key_cosine, value_cosine, figures["kv_cosine"])
    utilization_chart(repeated, barely, figures["token_utilization"])

    row_sums = [float(row.sum()) for record in records for row in record["attention"].reshape(-1, record["attention"].size(-1))]
    output_checks = [
        check
        for record in records
        for check in record["attention_output_validation"]
    ]
    output_validation = {
        "comparison": "reconstructed attention weights @ V versus fused attention output before out_proj",
        "comparison_count": len(output_checks),
        "maximum_absolute_error": max(check["maximum_absolute_error"] for check in output_checks),
        "mean_absolute_error": sum(check["mean_absolute_error"] for check in output_checks) / len(output_checks),
        "minimum_cosine_similarity": min(check["cosine_similarity"] for check in output_checks),
        "by_step_and_layer": [
            record["attention_output_validation"] for record in records
        ],
    }
    metrics = {
        "model_directory": project_path(DEFAULT_MODEL),
        "instruction": instruction,
        "model_config": {
            "layers": config.n_layers,
            "heads": config.n_heads,
            "head_dimension": config.d_model // config.n_heads,
        },
        "prompt_token_count": len(encoding.ids),
        "generated_token_count": len(generated),
        "reached_eos": reached_eos,
        "generated_code": tokenizer.decode(generated, skip_special_tokens=True),
        "token_labels": [label(tokenizer, token_id) for token_id in full_ids],
        "attention": {
            "formula": "softmax(Q_last @ K_transpose / sqrt(head_dim))",
            "shape_by_step": [[config.n_layers, config.n_heads, len(record["source_ids"])] for record in records],
            "row_sum_min": min(row_sums),
            "row_sum_max": max(row_sums),
            "last_query_shape_by_step": [list(record["last_query"].shape) for record in records],
            "last_query_by_step_layer_head_dimension": [record["last_query"].tolist() for record in records],
            "fused_attention_output_validation": output_validation,
        },
        "top5_references_by_generated_token": top_rows,
        "attention_region_ratios_by_step": region_rows,
        "attention_region_token_normalized": region_summary,
        "repeatedly_referenced_tokens": repeated,
        "barely_referenced_tokens": barely,
        "cosine_similarity": {
            "key": cosine_summary(key_cosine, full_ids, tokenizer),
            "value": cosine_summary(value_cosine, full_ids, tokenizer),
            "key_matrix": key_cosine.tolist(),
            "value_matrix": value_cosine.tolist(),
        },
        "figures": {name: project_path(path) for name, path in figures.items()},
    }
    METRICS_PATH.write_text(json.dumps(rounded(metrics), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "generated_code": metrics["generated_code"],
        "row_sum_range": [min(row_sums), max(row_sums)],
        "fused_attention_output_validation": output_validation,
        "region_token_normalized": region_summary["categories"],
        "highest_instruction_attention_heads": region_summary["highest_instruction_attention_heads"],
        "key": metrics["cosine_similarity"]["key"],
        "value": metrics["cosine_similarity"]["value"],
        "repeated": repeated,
        "barely": barely,
        "metrics": str(METRICS_PATH),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
