"""複数prompt・norm・rollout・ablationでBoku1-nanoのattentionを解析する。"""

from __future__ import annotations

from contextlib import contextmanager
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterator
from xml.sax.saxutils import escape

import torch
import torch.nn.functional as F
from tokenizers import Tokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from generated_code_verifier import (  # noqa: E402
    build_verification_cases,
    verify_generated_code,
)
from scripts.model.analyze_boku_nano_attention import (  # noqa: E402
    capture_qkv,
    label,
    regions_from_offsets,
)
from scripts.model.evaluate_boku_nano import PROMPT_TEMPLATE  # noqa: E402
from scripts.model.visualize_boku_nano_kv import (  # noqa: E402
    DEFAULT_MODEL,
    DEFAULT_TOKENIZER,
    load_model,
    project_path,
)


OPERATIONS_PATH = PROJECT_ROOT / "config/japanese_atomic_operations.json"
FIGURE_DIR = PROJECT_ROOT / "docs/results/figures"
METRICS_PATH = (
    PROJECT_ROOT / "docs/results/boku_nano_attention_interpretability_analysis.json"
)
EOS_ID = 2


def canonical_instruction(canonical_meaning: str) -> str:
    """24操作を同じ外形の日本語指示へ変換する。"""

    return f"整数リストxsに対して、{canonical_meaning}solve関数を書いてください。"


def load_diagnostics() -> list[dict[str, Any]]:
    """24種類の単独操作をhead比較用の固定promptとして読み込む。"""

    payload = json.loads(OPERATIONS_PATH.read_text(encoding="utf-8"))
    diagnostics = []
    for operation in payload["operations"]:
        diagnostics.append(
            {
                "operation_id": operation["operation_id"],
                "instruction": canonical_instruction(operation["canonical_meaning_ja"]),
                "semantic_ast": {"sequence": [operation["semantic_ast"]]},
            }
        )
    if len(diagnostics) != 24:
        raise ValueError(f"単独操作は24件である必要があります: {len(diagnostics)}")
    return diagnostics


def greedy_generate(
    model: Any, prompt_ids: list[int], max_new_tokens: int = 64
) -> tuple[list[int], bool]:
    """greedy decodingを行い、EOS自体は生成列へ含めない。"""

    current = prompt_ids.copy()
    generated: list[int] = []
    limit = min(max_new_tokens, model.config.context_length - len(current))
    with torch.inference_mode():
        for _ in range(limit):
            logits = model(torch.tensor([current], dtype=torch.long)).logits[0, -1]
            token_id = int(torch.argmax(logits))
            if token_id == EOS_ID:
                return generated, True
            generated.append(token_id)
            current.append(token_id)
    return generated, False


def full_attention(
    queries: list[torch.Tensor], keys: list[torch.Tensor]
) -> torch.Tensor:
    """全query位置についてcausal attentionを復元する。"""

    layers = []
    for query, key in zip(queries, keys, strict=True):
        score = torch.einsum("hid,hjd->hij", query, key) / math.sqrt(key.size(-1))
        mask = torch.ones(score.size(-2), score.size(-1), dtype=torch.bool).triu(1)
        score = score.masked_fill(mask.unsqueeze(0), float("-inf"))
        layers.append(torch.softmax(score, dim=-1))
    return torch.stack(layers)


def attention_rollout(attention: torch.Tensor) -> torch.Tensor:
    """head平均attentionへ残差を加え、層方向にrolloutする。"""

    head_mean = attention.mean(dim=1)
    sequence_length = head_mean.size(-1)
    identity = torch.eye(sequence_length)
    joint = identity
    for layer_attention in head_mean:
        augmented = layer_attention + identity
        augmented = augmented / augmented.sum(dim=-1, keepdim=True)
        joint = augmented @ joint
    return joint


@contextmanager
def ablate_head(model: Any, layer: int, head: int) -> Iterator[None]:
    """指定headのattention出力をout projection前で0にする。"""

    attention = model.blocks[layer].attention
    head_dim = attention.head_dim

    def hook(_module: torch.nn.Module, inputs: tuple[torch.Tensor, ...]) -> tuple[torch.Tensor]:
        attended = inputs[0].clone()
        start = head * head_dim
        attended[..., start : start + head_dim] = 0
        return (attended,)

    registered = attention.out_proj.register_forward_pre_hook(hook)
    try:
        yield
    finally:
        registered.remove()


@contextmanager
def zero_value_positions(model: Any, positions: list[int]) -> Iterator[None]:
    """全層で指定位置のValueだけを0にし、attention weight自体は保つ。"""

    hooks = []
    model_dimension = model.config.d_model
    fixed_positions = sorted(set(positions))

    def hook(
        _module: torch.nn.Module,
        _inputs: tuple[torch.Tensor, ...],
        output: torch.Tensor,
    ) -> torch.Tensor:
        modified = output.clone()
        valid = [position for position in fixed_positions if position < modified.size(1)]
        if valid:
            modified[:, valid, 2 * model_dimension : 3 * model_dimension] = 0
        return modified

    for block in model.blocks:
        hooks.append(block.attention.qkv_proj.register_forward_hook(hook))
    try:
        yield
    finally:
        for registered in hooks:
            registered.remove()


def verify(
    tokenizer: Tokenizer,
    generated_ids: list[int],
    semantic_ast: dict[str, Any],
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    code = tokenizer.decode(generated_ids, skip_special_tokens=True)
    result = verify_generated_code(
        code,
        semantic_ast,
        cases,
        timeout_seconds=5.0,
        max_source_chars=4096,
    )
    return {
        "code": code,
        "syntax_ok": result.syntax_ok,
        "ast_safe": result.ast_safe,
        "signature_ok": result.signature_ok,
        "tests_passed": result.tests_passed,
        "error": result.error,
    }


def teacher_logits(model: Any, prompt_ids: list[int], generated_ids: list[int]) -> torch.Tensor:
    """baseline生成tokenを教師強制した位置のlogitsを返す。"""

    source = prompt_ids + generated_ids[:-1]
    with torch.inference_mode():
        logits = model(torch.tensor([source], dtype=torch.long)).logits[0]
    start = len(prompt_ids) - 1
    return logits[start : start + len(generated_ids)].cpu()


def rankdata(values: list[float]) -> list[float]:
    """tieへ平均順位を与える小規模Spearman用rankを返す。"""

    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + end - 1) / 2
        for offset in range(cursor, end):
            ranks[order[offset]] = rank
        cursor = end
    return ranks


def pearson(left: list[float], right: list[float]) -> float:
    left_tensor = torch.tensor(left, dtype=torch.float64)
    right_tensor = torch.tensor(right, dtype=torch.float64)
    left_tensor -= left_tensor.mean()
    right_tensor -= right_tensor.mean()
    denominator = left_tensor.norm() * right_tensor.norm()
    return float((left_tensor @ right_tensor) / denominator) if denominator else 0.0


def spearman(left: list[float], right: list[float]) -> float:
    return pearson(rankdata(left), rankdata(right))


def rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 8)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item) for item in value]
    return value


def svg_header(width: int, height: int, title: str, description: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f"<title>{escape(title)}</title>",
        f"<desc>{escape(description)}</desc>",
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#17212b;font-size:12px}.small{font-size:10px;fill:#52606d}.title{font-size:20px;font-weight:500}.label{font-size:13px;font-weight:500}</style>',
        f'<text x="24" y="30" class="title">{escape(title)}</text>',
        f'<text x="24" y="52" class="small">{escape(description)}</text>',
    ]


def color(value: float, minimum: float, maximum: float) -> str:
    ratio = 0.5 if maximum <= minimum else (value - minimum) / (maximum - minimum)
    ratio = min(1.0, max(0.0, ratio))
    start, end = (238, 242, 245), (31, 93, 128)
    channels = [round(a + (b - a) * ratio) for a, b in zip(start, end, strict=True)]
    return f"#{channels[0]:02x}{channels[1]:02x}{channels[2]:02x}"


def head_role_figure(rows: list[dict[str, Any]], destination: Path) -> None:
    metrics = [
        ("bos_attention", "BOS attention", "percent"),
        ("instruction_attention", "日本語指示attention", "percent"),
        ("previous_token_attention", "直前token attention", "percent"),
        ("recent4_attention", "直近4 token attention", "percent"),
        ("induction_like_relative", "induction-like（一様比）", "ratio"),
        ("normalized_entropy", "attention entropy", "decimal"),
    ]
    width, height = 1080, 590
    parts = svg_header(
        width,
        height,
        "24操作で見たattention headの記述的な役割",
        "各セルに24操作の平均値を表示。列がhead、行がlayer。色はパネル内の大小で、因果的重要度ではない。",
    )
    panel_w, panel_h = 288, 184
    for metric_index, (metric, title, display) in enumerate(metrics):
        column, row = metric_index % 3, metric_index // 3
        x0, y0 = 62 + column * 344, 94 + row * 238
        values = [float(item[metric]) for item in rows]
        minimum, maximum = min(values), max(values)
        parts.append(f'<text x="{x0}" y="{y0 - 12}" class="label">{escape(title)}</text>')
        for item in rows:
            value = float(item[metric])
            ratio = 0.5 if maximum <= minimum else (value - minimum) / (maximum - minimum)
            ratio = min(1.0, max(0.0, ratio))
            x = x0 + (item["head"] - 1) * panel_w / 6
            y = y0 + (item["layer"] - 1) * panel_h / 8
            if display == "percent":
                shown = f"{value * 100:.1f}%"
            elif display == "ratio":
                shown = f"{value:.2f}x"
            else:
                shown = f"{value:.3f}"
            text_color = "#ffffff" if ratio >= 0.53 else "#15202b"
            parts.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{panel_w / 6 + .2:.2f}" '
                f'height="{panel_h / 8 + .2:.2f}" fill="{color(value, minimum, maximum)}" '
                f'stroke="#ffffff" stroke-width="0.7"/>'
            )
            parts.append(
                f'<text x="{x + panel_w / 12:.2f}" y="{y + panel_h / 16 + 3.5:.2f}" '
                f'text-anchor="middle" fill="{text_color}" style="font-size:9px;font-weight:500">'
                f'{shown}</text>'
            )
        for head in range(6):
            parts.append(
                f'<text x="{x0 + (head + .5) * panel_w / 6:.2f}" y="{y0 + panel_h + 15}" '
                f'text-anchor="middle" class="small">H{head + 1}</text>'
            )
        for layer in range(8):
            parts.append(
                f'<text x="{x0 - 6}" y="{y0 + (layer + .7) * panel_h / 8:.2f}" '
                f'text-anchor="end" class="small">L{layer + 1}</text>'
            )
        parts.append(
            f'<text x="{x0 + panel_w}" y="{y0 - 12}" text-anchor="end" class="small">'
            "薄い＝小、濃い＝大</text>"
        )
    parts.append("</svg>")
    destination.write_text("\n".join(parts), encoding="utf-8")

def sink_figure(rows: list[dict[str, Any]], destination: Path) -> None:
    width, height = 820, 600
    left, top, plot_w, plot_h = 88, 88, 660, 430
    maximum = max(
        max(float(row["bos_attention"]), float(row["bos_projected_norm_share"]))
        for row in rows
    ) * 1.08
    ranked = sorted(rows, key=lambda row: -float(row["bos_attention"]))[:6]
    marked = {(row["layer"], row["head"]) for row in ranked}
    parts = svg_header(
        width,
        height,
        "BOSへのattentionと出力ベクトル寄与",
        "横は生attention、縦はattention×out_proj後Valueノルムの構成比。破線上なら両者が同率。",
    )
    for tick in range(6):
        value = maximum * tick / 5
        x = left + value / maximum * plot_w
        y = top + plot_h - value / maximum * plot_h
        parts.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_h}" stroke="#e5e8eb"/>')
        parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#e5e8eb"/>')
        parts.append(f'<text x="{x:.2f}" y="{top + plot_h + 20}" text-anchor="middle" class="small">{value * 100:.0f}%</text>')
        parts.append(f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" class="small">{value * 100:.0f}%</text>')
    parts.append(
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top}" '
        'stroke="#8b949d" stroke-dasharray="5 5"/>'
    )
    for row in rows:
        x = left + float(row["bos_attention"]) / maximum * plot_w
        y = top + plot_h - float(row["bos_projected_norm_share"]) / maximum * plot_h
        selected = (row["layer"], row["head"]) in marked
        radius = 5 if selected else 3
        fill = "#b35438" if selected else "#356f8a"
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{fill}"/>')
        if selected:
            parts.append(
                f'<text x="{x + 7:.2f}" y="{y - 6:.2f}" class="small">'
                f'L{row["layer"]}H{row["head"]}</text>'
            )
    parts.extend(
        [
            f'<text x="{left + plot_w / 2}" y="{height - 28}" text-anchor="middle">BOSへの生attention</text>',
            f'<text x="22" y="{top + plot_h / 2}" text-anchor="middle" transform="rotate(-90 22 {top + plot_h / 2})">BOSのprojected Valueノルム構成比</text>',
            "</svg>",
        ]
    )
    destination.write_text("\n".join(parts), encoding="utf-8")


def ablation_figure(
    head_rows: list[dict[str, Any]], conditions: list[dict[str, Any]], destination: Path
) -> None:
    width, height = 1040, 650
    parts = svg_header(
        width,
        height,
        "attention headとValue位置の因果的ablation",
        "上段は各headを0にしたときの教師強制NLL変化。下段はgreedy生成をhidden testで再評価した合格率。",
    )
    left, top, plot_w, plot_h = 72, 88, 920, 240
    values = [float(row["delta_nll"]) for row in head_rows]
    lower, upper = min(min(values), 0.0), max(max(values), 0.0)
    padding = max(upper - lower, 0.001) * 0.08
    lower, upper = lower - padding, upper + padding
    zero_y = top + (upper / (upper - lower)) * plot_h
    parts.append(f'<line x1="{left}" y1="{zero_y:.2f}" x2="{left + plot_w}" y2="{zero_y:.2f}" stroke="#66717d"/>')
    bar_w = plot_w / len(head_rows) * .72
    top_heads = {row["id"] for row in sorted(head_rows, key=lambda row: -row["delta_nll"])[:3]}
    for index, row in enumerate(head_rows):
        x = left + (index + .5) * plot_w / len(head_rows) - bar_w / 2
        value_y = top + (upper - float(row["delta_nll"])) / (upper - lower) * plot_h
        y, h = min(value_y, zero_y), abs(value_y - zero_y)
        fill = "#b35438" if row["id"] in top_heads else "#4f7f96"
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{max(h, .7):.2f}" fill="{fill}"/>')
        if index % 6 == 2:
            parts.append(f'<text x="{x + bar_w / 2:.2f}" y="{top + plot_h + 17}" text-anchor="middle" class="small">L{row["layer"]}</text>')
    parts.append(f'<text x="20" y="{top + plot_h / 2}" text-anchor="middle" transform="rotate(-90 20 {top + plot_h / 2})">NLL差（無効化後−基準、nat/token）</text>')

    lower_top, lower_h = 410, 160
    count = len(conditions)
    lower_bar_w = plot_w / max(count, 1) * .58
    for tick in range(6):
        y = lower_top + lower_h - tick / 5 * lower_h
        parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#e5e8eb"/>')
        parts.append(f'<text x="{left - 9}" y="{y + 4:.2f}" text-anchor="end" class="small">{tick * 20}%</text>')
    for index, condition in enumerate(conditions):
        x = left + (index + .5) * plot_w / count
        rate = float(condition["pass_rate"])
        h = rate * lower_h
        fill = "#356f8a" if condition["name"] == "baseline" else "#a76b49"
        parts.append(f'<rect x="{x - lower_bar_w / 2:.2f}" y="{lower_top + lower_h - h:.2f}" width="{lower_bar_w:.2f}" height="{h:.2f}" fill="{fill}"/>')
        parts.append(f'<text x="{x:.2f}" y="{lower_top + lower_h - h - 7:.2f}" text-anchor="middle" class="small">{rate * 100:.1f}%</text>')
        name = str(condition["label"])
        parts.append(f'<text x="{x:.2f}" y="{lower_top + lower_h + 18}" text-anchor="middle" class="small">{escape(name)}</text>')
    parts.append("</svg>")
    destination.write_text("\n".join(parts), encoding="utf-8")


def rollout_figure(
    token_labels: list[str], raw: list[float], norm: list[float], rollout: list[float], destination: Path
) -> None:
    visible = min(len(raw), 28)
    width, height = 1080, 560
    left, top, plot_w, plot_h = 72, 92, 950, 350
    maximum = max(max(raw[:visible]), max(norm[:visible]), max(rollout[:visible])) * 1.12
    parts = svg_header(
        width,
        height,
        "最終生成stepのtoken別参照量",
        "生attention、Valueノルムを含む構成比、8層attention rolloutを同じtoken位置で比較。",
    )
    palette = ["#356f8a", "#b06b45", "#6c5b8e"]
    names = ["生attention", "attention×projected Value norm", "attention rollout"]
    group_w = plot_w / visible
    bar_w = group_w * .22
    for tick in range(6):
        value = maximum * tick / 5
        y = top + plot_h - value / maximum * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="#e5e8eb"/>')
        parts.append(f'<text x="{left - 9}" y="{y + 4:.2f}" text-anchor="end" class="small">{value * 100:.0f}%</text>')
    for index in range(visible):
        x0 = left + index * group_w + group_w * .14
        for series_index, series in enumerate((raw, norm, rollout)):
            value = series[index]
            h = value / maximum * plot_h
            x = x0 + series_index * bar_w
            parts.append(f'<rect x="{x:.2f}" y="{top + plot_h - h:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{palette[series_index]}"/>')
        token = token_labels[index].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        token = token[:9]
        x = left + (index + .5) * group_w
        parts.append(f'<text x="{x:.2f}" y="{top + plot_h + 13}" transform="rotate(60 {x:.2f} {top + plot_h + 13})" class="small">{token}</text>')
    legend_x = left
    for name, fill in zip(names, palette, strict=True):
        parts.append(f'<rect x="{legend_x}" y="{height - 32}" width="12" height="12" fill="{fill}"/>')
        parts.append(f'<text x="{legend_x + 17}" y="{height - 22}" class="small">{escape(name)}</text>')
        legend_x += 260
    parts.append("</svg>")
    destination.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    torch.manual_seed(20260930)
    torch.set_num_threads(1)
    model, config = load_model(DEFAULT_MODEL)
    tokenizer = Tokenizer.from_file(str(DEFAULT_TOKENIZER))
    cases = build_verification_cases(seed=20260930, random_case_count=24)
    diagnostics = load_diagnostics()

    samples: list[dict[str, Any]] = []
    metric_names = [
        "bos_attention",
        "instruction_attention",
        "control_attention",
        "generated_code_attention",
        "previous_token_attention",
        "self_attention",
        "recent4_attention",
        "normalized_entropy",
        "bos_value_norm_share",
        "bos_projected_norm_share",
        "copy_relative",
        "induction_like_relative",
    ]
    sums = {name: torch.zeros(config.n_layers, config.n_heads) for name in metric_names}
    counts = {name: torch.zeros(config.n_layers, config.n_heads) for name in metric_names}
    example_rollout: dict[str, Any] | None = None

    for diagnostic_index, diagnostic in enumerate(diagnostics):
        prompt = PROMPT_TEMPLATE.format(instruction_ja=diagnostic["instruction"])
        encoding = tokenizer.encode(prompt, add_special_tokens=False)
        generated, reached_eos = greedy_generate(model, encoding.ids)
        verification = verify(tokenizer, generated, diagnostic["semantic_ast"], cases)
        full_ids = encoding.ids + generated
        queries, keys, values, _contexts, _logits = capture_qkv(model, full_ids)
        attention = full_attention(queries, keys)
        prompt_regions = regions_from_offsets(prompt, diagnostic["instruction"], encoding.offsets)
        instruction_positions = [
            index for index, region in enumerate(prompt_regions) if region == "instruction"
        ]
        control_positions = [
            index for index, region in enumerate(prompt_regions) if region == "control"
        ]
        query_positions = list(
            range(len(encoding.ids) - 1, len(encoding.ids) + len(generated) - 1)
        )

        for query_position in query_positions:
            row = attention[:, :, query_position, : query_position + 1]
            groups = {
                "instruction_attention": [p for p in instruction_positions if p <= query_position],
                "control_attention": [p for p in control_positions if p <= query_position],
                "generated_code_attention": list(
                    range(len(encoding.ids), query_position + 1)
                ),
                "recent4_attention": list(range(max(0, query_position - 3), query_position + 1)),
            }
            sums["bos_attention"] += row[:, :, 0]
            counts["bos_attention"] += 1
            for name, positions in groups.items():
                if positions:
                    sums[name] += row[:, :, positions].sum(dim=-1)
                    counts[name] += 1
            if query_position > 0:
                sums["previous_token_attention"] += row[:, :, query_position - 1]
                counts["previous_token_attention"] += 1
            sums["self_attention"] += row[:, :, query_position]
            counts["self_attention"] += 1
            entropy = -(row.clamp_min(1e-12) * row.clamp_min(1e-12).log()).sum(dim=-1)
            entropy /= math.log(query_position + 1) if query_position else 1.0
            sums["normalized_entropy"] += entropy
            counts["normalized_entropy"] += 1

            current_ids = full_ids[: query_position + 1]
            copy_positions = [
                position
                for position in range(query_position)
                if current_ids[position] == current_ids[query_position]
            ]
            induction_positions = [
                position
                for position in range(1, query_position + 1)
                if current_ids[position - 1] == current_ids[query_position]
            ]
            for name, positions in (
                ("copy_relative", copy_positions),
                ("induction_like_relative", induction_positions),
            ):
                if positions:
                    observed = row[:, :, positions].sum(dim=-1)
                    expected = len(positions) / (query_position + 1)
                    sums[name] += observed / expected
                    counts[name] += 1

            for layer in range(config.n_layers):
                output_weight = model.blocks[layer].attention.out_proj.weight.detach().cpu()
                for head in range(config.n_heads):
                    weights = row[layer, head]
                    current_values = values[layer][head, : query_position + 1]
                    value_norms = current_values.norm(dim=-1)
                    weighted_value_norm = weights * value_norms
                    sums["bos_value_norm_share"][layer, head] += (
                        weighted_value_norm[0] / weighted_value_norm.sum().clamp_min(1e-12)
                    )
                    counts["bos_value_norm_share"][layer, head] += 1

                    start = head * model.blocks[layer].attention.head_dim
                    head_weight = output_weight[:, start : start + model.blocks[layer].attention.head_dim]
                    projected = current_values @ head_weight.T
                    projected_norm = projected.norm(dim=-1)
                    weighted_projected_norm = weights * projected_norm
                    sums["bos_projected_norm_share"][layer, head] += (
                        weighted_projected_norm[0]
                        / weighted_projected_norm.sum().clamp_min(1e-12)
                    )
                    counts["bos_projected_norm_share"][layer, head] += 1

        if diagnostic_index == 16:
            query_position = query_positions[-1]
            row = attention[:, :, query_position, : query_position + 1]
            raw = row.mean(dim=(0, 1))
            norm_rows = []
            for layer in range(config.n_layers):
                output_weight = model.blocks[layer].attention.out_proj.weight.detach().cpu()
                for head in range(config.n_heads):
                    weights = row[layer, head]
                    start = head * model.blocks[layer].attention.head_dim
                    head_weight = output_weight[:, start : start + model.blocks[layer].attention.head_dim]
                    projected = values[layer][head, : query_position + 1] @ head_weight.T
                    contribution = weights * projected.norm(dim=-1)
                    norm_rows.append(contribution / contribution.sum().clamp_min(1e-12))
            norm_contribution = torch.stack(norm_rows).mean(dim=0)
            rollout = attention_rollout(attention)[query_position, : query_position + 1]
            example_rollout = {
                "operation_id": diagnostic["operation_id"],
                "instruction": diagnostic["instruction"],
                "query_position": query_position,
                "tokens": [label(tokenizer, token_id) for token_id in full_ids[: query_position + 1]],
                "raw_attention": raw.tolist(),
                "projected_value_norm_share": norm_contribution.tolist(),
                "attention_rollout": rollout.tolist(),
            }

        samples.append(
            {
                **diagnostic,
                "prompt": prompt,
                "prompt_ids": encoding.ids,
                "instruction_positions": instruction_positions,
                "generated_ids": generated,
                "reached_eos": reached_eos,
                "verification": verification,
            }
        )

    means = {
        name: sums[name] / counts[name].clamp_min(1)
        for name in metric_names
    }
    head_roles = []
    for layer in range(config.n_layers):
        for head in range(config.n_heads):
            row: dict[str, Any] = {
                "id": f"L{layer + 1}H{head + 1}",
                "layer": layer + 1,
                "head": head + 1,
            }
            for name in metric_names:
                row[name] = float(means[name][layer, head])
                row[f"{name}_observations"] = int(counts[name][layer, head])
            head_roles.append(row)

    baseline_teacher = []
    total_targets = sum(len(sample["generated_ids"]) for sample in samples)
    for sample in samples:
        logits = teacher_logits(model, sample["prompt_ids"], sample["generated_ids"])
        targets = torch.tensor(sample["generated_ids"], dtype=torch.long)
        baseline_teacher.append(
            {
                "logits": logits,
                "targets": targets,
                "nll_sum": float(F.cross_entropy(logits, targets, reduction="sum")),
            }
        )
    baseline_nll = sum(item["nll_sum"] for item in baseline_teacher) / total_targets

    head_ablation = []
    for layer in range(config.n_layers):
        for head in range(config.n_heads):
            nll_sum = 0.0
            kl_sum = 0.0
            changed = 0
            with ablate_head(model, layer, head):
                for sample, baseline in zip(samples, baseline_teacher, strict=True):
                    logits = teacher_logits(model, sample["prompt_ids"], sample["generated_ids"])
                    targets = baseline["targets"]
                    nll_sum += float(F.cross_entropy(logits, targets, reduction="sum"))
                    baseline_log_probs = F.log_softmax(baseline["logits"], dim=-1)
                    ablated_log_probs = F.log_softmax(logits, dim=-1)
                    baseline_probs = baseline_log_probs.exp()
                    kl_sum += float(
                        (baseline_probs * (baseline_log_probs - ablated_log_probs)).sum()
                    )
                    changed += int(
                        (logits.argmax(dim=-1) != baseline["logits"].argmax(dim=-1)).sum()
                    )
            ablated_nll = nll_sum / total_targets
            head_ablation.append(
                {
                    "id": f"L{layer + 1}H{head + 1}",
                    "layer": layer + 1,
                    "head": head + 1,
                    "baseline_nll": baseline_nll,
                    "ablated_nll": ablated_nll,
                    "delta_nll": ablated_nll - baseline_nll,
                    "mean_kl_divergence": kl_sum / total_targets,
                    "argmax_changed_tokens": changed,
                    "argmax_changed_rate": changed / total_targets,
                }
            )

    role_by_id = {row["id"]: row for row in head_roles}
    ablation_by_id = {row["id"]: row for row in head_ablation}
    attention_causal_correlations = {}
    for metric in (
        "bos_attention",
        "instruction_attention",
        "previous_token_attention",
        "recent4_attention",
        "induction_like_relative",
    ):
        attention_values = [role_by_id[row["id"]][metric] for row in head_ablation]
        causal_values = [row["delta_nll"] for row in head_ablation]
        attention_causal_correlations[metric] = {
            "pearson": pearson(attention_values, causal_values),
            "spearman": spearman(attention_values, causal_values),
        }

    top_heads = sorted(head_ablation, key=lambda row: -row["delta_nll"])[:3]
    low_heads = sorted(
        head_ablation,
        key=lambda row: (abs(row["delta_nll"]), row["argmax_changed_rate"]),
    )[:3]
    causal_conditions = [
        {
            "name": "baseline",
            "label": "baseline",
            "kind": "baseline",
        },
        {
            "name": "zero_bos_values",
            "label": "BOS Value=0",
            "kind": "values",
            "positions": "bos",
        },
        {
            "name": "zero_instruction_values",
            "label": "日本語 Value=0",
            "kind": "values",
            "positions": "instruction",
        },
    ]
    for row in top_heads:
        causal_conditions.append(
            {
                "name": f'ablate_{row["id"]}',
                "label": f'{row["id"]}=0',
                "kind": "head",
                "layer": row["layer"] - 1,
                "head": row["head"] - 1,
                "selection": "top_delta_nll",
            }
        )
    for row in low_heads:
        causal_conditions.append(
            {
                "name": f'ablate_{row["id"]}',
                "label": f'{row["id"]}=0',
                "kind": "head",
                "layer": row["layer"] - 1,
                "head": row["head"] - 1,
                "selection": "lowest_absolute_delta_nll",
            }
        )

    causal_results = []
    for condition in causal_conditions:
        results = []
        for sample in samples:
            if condition["kind"] == "baseline":
                generated = sample["generated_ids"]
                reached_eos = sample["reached_eos"]
            elif condition["kind"] == "head":
                with ablate_head(model, condition["layer"], condition["head"]):
                    generated, reached_eos = greedy_generate(model, sample["prompt_ids"])
            else:
                positions = (
                    [0]
                    if condition["positions"] == "bos"
                    else sample["instruction_positions"]
                )
                with zero_value_positions(model, positions):
                    generated, reached_eos = greedy_generate(model, sample["prompt_ids"])
            verification = verify(tokenizer, generated, sample["semantic_ast"], cases)
            results.append(
                {
                    "operation_id": sample["operation_id"],
                    "reached_eos": reached_eos,
                    "same_code_as_baseline": generated == sample["generated_ids"],
                    **verification,
                }
            )
        passed = sum(result["tests_passed"] for result in results)
        causal_results.append(
            {
                **condition,
                "passed": passed,
                "total": len(results),
                "pass_rate": passed / len(results),
                "same_code_count": sum(result["same_code_as_baseline"] for result in results),
                "syntax_valid": sum(result["syntax_ok"] for result in results),
                "results": results,
            }
        )

    if example_rollout is None:
        raise AssertionError("rollout例を作成できませんでした")

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    figures = {
        "head_roles": FIGURE_DIR / "boku_nano_attention_head_roles.svg",
        "attention_sink": FIGURE_DIR / "boku_nano_attention_sink_contribution.svg",
        "causal_ablation": FIGURE_DIR / "boku_nano_attention_causal_ablation.svg",
        "rollout": FIGURE_DIR / "boku_nano_attention_rollout.svg",
    }
    head_role_figure(head_roles, figures["head_roles"])
    sink_figure(head_roles, figures["attention_sink"])
    ablation_figure(head_ablation, causal_results, figures["causal_ablation"])
    rollout_figure(
        example_rollout["tokens"],
        example_rollout["raw_attention"],
        example_rollout["projected_value_norm_share"],
        example_rollout["attention_rollout"],
        figures["rollout"],
    )

    metrics = {
        "model_directory": project_path(DEFAULT_MODEL),
        "tokenizer": project_path(DEFAULT_TOKENIZER),
        "diagnostic_design": {
            "prompt_count": len(samples),
            "coverage": "24 atomic operations, one canonical instruction per operation",
            "hidden_tests_per_prompt": len(cases),
            "generation": "greedy",
            "ablation": "head output is zeroed before out_proj; token-position experiment zeros V but preserves K and attention weights",
        },
        "baseline": {
            "passed": sum(sample["verification"]["tests_passed"] for sample in samples),
            "total": len(samples),
            "teacher_forced_nll": baseline_nll,
            "generated_token_count": total_targets,
        },
        "head_roles": head_roles,
        "role_rankings": {
            metric: sorted(
                (
                    {"id": row["id"], "value": row[metric]}
                    for row in head_roles
                ),
                key=lambda row: -row["value"],
            )[:6]
            for metric in metric_names
        },
        "head_ablation": head_ablation,
        "most_causally_influential_heads": top_heads,
        "least_causally_influential_heads": low_heads,
        "attention_causal_correlations": attention_causal_correlations,
        "causal_generation_results": causal_results,
        "rollout_example": example_rollout,
        "samples": [
            {
                "operation_id": sample["operation_id"],
                "instruction": sample["instruction"],
                "semantic_ast": sample["semantic_ast"],
                "prompt_token_count": len(sample["prompt_ids"]),
                "generated_token_count": len(sample["generated_ids"]),
                "reached_eos": sample["reached_eos"],
                "verification": sample["verification"],
            }
            for sample in samples
        ],
        "figures": {name: project_path(path) for name, path in figures.items()},
    }
    METRICS_PATH.write_text(
        json.dumps(rounded(metrics), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            rounded(
                {
                    "baseline": metrics["baseline"],
                    "top_role_rankings": {
                        key: value[:3] for key, value in metrics["role_rankings"].items()
                    },
                    "top_head_ablation": top_heads,
                    "low_head_ablation": low_heads,
                    "correlations": attention_causal_correlations,
                    "causal_generation": [
                        {
                            "name": row["name"],
                            "passed": row["passed"],
                            "total": row["total"],
                            "same_code_count": row["same_code_count"],
                        }
                        for row in causal_results
                    ],
                    "metrics": project_path(METRICS_PATH),
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
