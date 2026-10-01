#!/usr/bin/env python3
"""Boku Nanoのtraining_metrics.jsonlから20 stepごとのloss図を生成する。"""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path


WIDTH = 1120
HEIGHT = 620
LEFT = 92
RIGHT = 34
TOP = 104
BOTTOM = 82
PLOT_WIDTH = WIDTH - LEFT - RIGHT
PLOT_HEIGHT = HEIGHT - TOP - BOTTOM


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--title", required=True)
    return parser.parse_args()


def load_metrics(path: Path) -> tuple[list[tuple[int, float]], list[tuple[int, float, int]]]:
    train: list[tuple[int, float]] = []
    validation: list[tuple[int, float, int]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if "loss" in record and "global_step" in record:
            train.append((int(record["global_step"]), float(record["loss"])))
        elif record.get("event") == "validation":
            validation.append(
                (
                    int(record["global_step"]),
                    float(record["validation_loss"]),
                    int(record["epoch"]),
                )
            )
        elif "event" not in record:
            raise ValueError(f"{path}:{line_number}: lossまたはeventがありません")
    if not train:
        raise ValueError(f"train lossが見つかりません: {path}")
    if not validation:
        raise ValueError(f"validation lossが見つかりません: {path}")
    return train, validation


def choose_x_ticks(max_step: int) -> list[int]:
    rough_interval = max_step / 6
    magnitude = 10 ** math.floor(math.log10(max(rough_interval, 1)))
    interval = min((1, 2, 5, 10), key=lambda value: abs(value * magnitude - rough_interval)) * magnitude
    ticks = list(range(0, max_step + 1, int(interval)))
    if max_step not in ticks:
        ticks.append(max_step)
    return ticks


def render_svg(
    title: str,
    train: list[tuple[int, float]],
    validation: list[tuple[int, float, int]],
) -> str:
    max_step = max(max(step for step, _ in train), max(step for step, _, _ in validation))
    all_losses = [loss for _, loss in train] + [loss for _, loss, _ in validation]
    if any(loss <= 0 for loss in all_losses):
        raise ValueError("対数軸へ描画できない0以下のlossが含まれています")

    standard_ticks = [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
    data_min = min(all_losses)
    data_max = max(all_losses)
    visible_ticks = [tick for tick in standard_ticks if data_min * 0.75 <= tick <= data_max * 1.35]
    if len(visible_ticks) < 2:
        visible_ticks = [min(standard_ticks, key=lambda tick: abs(math.log(tick / data_min))), max(standard_ticks)]
    y_min = min(visible_ticks)
    y_max = max(visible_ticks)
    if y_min >= data_min:
        smaller = [tick for tick in standard_ticks if tick < y_min]
        y_min = max(smaller) if smaller else data_min * 0.8
    if y_max <= data_max:
        larger = [tick for tick in standard_ticks if tick > y_max]
        y_max = min(larger) if larger else data_max * 1.2

    log_min = math.log10(y_min)
    log_max = math.log10(y_max)

    def x(step: int) -> float:
        return LEFT + (step / max_step) * PLOT_WIDTH

    def y(loss: float) -> float:
        ratio = (math.log10(loss) - log_min) / (log_max - log_min)
        return TOP + (1 - ratio) * PLOT_HEIGHT

    train_points = " ".join(f"{x(step):.2f},{y(loss):.2f}" for step, loss in train)
    x_ticks = choose_x_ticks(max_step)
    shown_y_ticks = [tick for tick in standard_ticks if y_min <= tick <= y_max]
    subtitle = (
        f"train: 20 optimizer stepごとの区間平均（最終区間を含む） / "
        f"validation: 各epoch終了時 / train {len(train)}点・validation {len(validation)}点"
    )

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        f"<title>{html.escape(title)}：20 stepごとのloss推移</title>",
        f"<desc>{html.escape(subtitle)}</desc>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        "<style>",
        'text{font-family:system-ui,-apple-system,"Segoe UI","Noto Sans JP",sans-serif;fill:#172033}',
        ".title{font-size:22px;font-weight:650}.subtitle{font-size:13px;fill:#526079}",
        ".label{font-size:13px}.small{font-size:12px;fill:#526079}.grid{stroke:#dce3ec;stroke-width:1}",
        ".axis{stroke:#667085;stroke-width:1.4}.epoch{stroke:#98a2b3;stroke-width:1.2;stroke-dasharray:5 5}",
        "</style>",
        f'<text x="{WIDTH / 2:.0f}" y="35" text-anchor="middle" class="title">{html.escape(title)}</text>',
        f'<text x="{WIDTH / 2:.0f}" y="61" text-anchor="middle" class="subtitle">{html.escape(subtitle)}</text>',
    ]

    for tick in shown_y_ticks:
        py = y(tick)
        label = f"{tick:g}"
        lines.extend(
            [
                f'<line x1="{LEFT}" y1="{py:.2f}" x2="{WIDTH - RIGHT}" y2="{py:.2f}" class="grid"/>',
                f'<text x="{LEFT - 13}" y="{py + 5:.2f}" text-anchor="end" class="label">{label}</text>',
            ]
        )

    for tick in x_ticks:
        px = x(tick)
        lines.extend(
            [
                f'<line x1="{px:.2f}" y1="{TOP}" x2="{px:.2f}" y2="{TOP + PLOT_HEIGHT}" class="grid"/>',
                f'<text x="{px:.2f}" y="{TOP + PLOT_HEIGHT + 27}" text-anchor="middle" class="label">{tick:,}</text>',
            ]
        )

    for step, _, epoch in validation[:-1]:
        px = x(step)
        lines.extend(
            [
                f'<line x1="{px:.2f}" y1="{TOP}" x2="{px:.2f}" y2="{TOP + PLOT_HEIGHT}" class="epoch"/>',
                f'<text x="{px + 6:.2f}" y="{TOP + 17}" class="small">Epoch {epoch}終了</text>',
            ]
        )

    lines.extend(
        [
            f'<line x1="{LEFT}" y1="{TOP + PLOT_HEIGHT}" x2="{WIDTH - RIGHT}" y2="{TOP + PLOT_HEIGHT}" class="axis"/>',
            f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" y2="{TOP + PLOT_HEIGHT}" class="axis"/>',
            f'<polyline points="{train_points}" fill="none" stroke="#1463d6" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>',
        ]
    )
    for step, loss in train:
        lines.append(f'<circle cx="{x(step):.2f}" cy="{y(loss):.2f}" r="3.0" fill="#1463d6"/>')
    for step, loss, epoch in validation:
        px = x(step)
        py = y(loss)
        lines.extend(
            [
                f'<rect x="{px - 5:.2f}" y="{py - 5:.2f}" width="10" height="10" rx="1" fill="#d65a12" stroke="#ffffff" stroke-width="1.5"/>',
                f'<text x="{px - 8:.2f}" y="{py - 10:.2f}" text-anchor="end" class="small">E{epoch}: {loss:.4f}</text>',
            ]
        )

    legend_y = HEIGHT - 25
    lines.extend(
        [
            f'<line x1="{LEFT}" y1="{legend_y}" x2="{LEFT + 31}" y2="{legend_y}" stroke="#1463d6" stroke-width="2.4"/>',
            f'<circle cx="{LEFT + 16}" cy="{legend_y}" r="3" fill="#1463d6"/>',
            f'<text x="{LEFT + 40}" y="{legend_y + 5}" class="label">Train loss</text>',
            f'<rect x="{LEFT + 162}" y="{legend_y - 5}" width="10" height="10" rx="1" fill="#d65a12"/>',
            f'<text x="{LEFT + 181}" y="{legend_y + 5}" class="label">Validation loss</text>',
            f'<text x="{WIDTH / 2:.0f}" y="{HEIGHT - 47}" text-anchor="middle" class="label">Optimizer step</text>',
            f'<text x="24" y="{TOP + PLOT_HEIGHT / 2:.0f}" text-anchor="middle" class="label" transform="rotate(-90 24 {TOP + PLOT_HEIGHT / 2:.0f})">Loss（対数目盛）</text>',
            "</svg>",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    train, validation = load_metrics(args.metrics)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_svg(args.title, train, validation), encoding="utf-8")
    print(f"wrote {args.output} (train={len(train)}, validation={len(validation)})")


if __name__ == "__main__":
    main()
