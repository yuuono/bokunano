#!/usr/bin/env python3
"""中間層4回・3epochの2条件についてlossと評価結果をSVG化する。"""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any

VARIANTS = ("u3_middle4", "u3_middle4_scaled025")
LABELS = {
    "u3_middle4": "反復残差 1.0",
    "u3_middle4_scaled025": "反復残差 0.25",
}
COLORS = {"u3_middle4": "#2563eb", "u3_middle4_scaled025": "#e11d48"}


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def loss_svg(root: Path) -> tuple[str, dict[str, Any]]:
    values = {}
    for variant in VARIANTS:
        rows = jsonl(root / f"{variant}_seed20260925/model/training_metrics.jsonl")
        train = [(int(row["global_step"]), float(row["loss"])) for row in rows if "loss" in row]
        validation = [row for row in rows if row.get("event") == "validation"]
        values[variant] = {
            "train": train,
            "final_train_loss": train[-1][1],
            "validation_loss": float(validation[-1]["validation_loss"]),
            "validation_perplexity": float(validation[-1]["validation_perplexity"]),
        }
    width, height = 1080, 620
    left, right, top, bottom = 90, 34, 82, 100
    plot_w, plot_h = width - left - right, height - top - bottom
    all_losses = [loss for item in values.values() for _, loss in item["train"]]
    all_losses += [item["validation_loss"] for item in values.values()]
    max_step = max(step for item in values.values() for step, _ in item["train"])
    log_min, log_max = math.log(min(all_losses) * .9), math.log(max(all_losses) * 1.1)

    def x(step: int) -> float:
        return left + step / max_step * plot_w

    def y(loss: float) -> float:
        return top + (1 - (math.log(loss) - log_min) / (log_max - log_min)) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<title>中間層4回反復・3 epochのloss</title>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#172033}.title{font-size:22px;font-weight:650}.sub{font-size:12px;fill:#5b6577}.axis{font-size:11px}.grid{stroke:#dce3ec;stroke-width:1}</style>',
        '<text x="540" y="32" text-anchor="middle" class="title">中間層4回反復：3 epoch loss</text>',
        '<text x="540" y="54" text-anchor="middle" class="sub">線: 20 optimizer step区間のtrain loss　四角: 最終validation loss</text>',
    ]
    for step in (0, 200, 400, 600, 800, 1000, max_step):
        px = x(step)
        parts += [f'<line x1="{px:.1f}" y1="{top}" x2="{px:.1f}" y2="{top + plot_h}" class="grid"/>',
                  f'<text x="{px:.1f}" y="{top + plot_h + 23}" text-anchor="middle" class="axis">{step}</text>']
    for tick in (.4, .5, 1, 2, 5, 10):
        if math.exp(log_min) <= tick <= math.exp(log_max):
            py = y(tick)
            parts += [f'<line x1="{left}" y1="{py:.1f}" x2="{left + plot_w}" y2="{py:.1f}" class="grid"/>',
                      f'<text x="{left - 11}" y="{py + 4:.1f}" text-anchor="end" class="axis">{tick:g}</text>']
    for index, variant in enumerate(VARIANTS):
        points = " ".join(f"{x(step):.1f},{y(loss):.1f}" for step, loss in values[variant]["train"])
        color = COLORS[variant]
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.4"/>')
        vy = y(values[variant]["validation_loss"])
        parts.append(f'<rect x="{x(max_step) - 5:.1f}" y="{vy - 5:.1f}" width="10" height="10" fill="{color}" stroke="#fff"/>')
        lx = 330 + index * 300
        parts += [f'<line x1="{lx}" y1="{height - 39}" x2="{lx + 34}" y2="{height - 39}" stroke="{color}" stroke-width="3"/>',
                  f'<text x="{lx + 43}" y="{height - 35}" class="axis">{LABELS[variant]}</text>']
    parts += [f'<text x="{width / 2}" y="{top + plot_h + 50}" text-anchor="middle" class="axis">Optimizer step</text>',
              f'<text x="22" y="{top + plot_h / 2}" text-anchor="middle" class="axis" transform="rotate(-90 22 {top + plot_h / 2})">Loss（対数目盛）</text>', '</svg>']
    return "\n".join(parts) + "\n", values


def benchmark_svg(comparison: dict[str, Any], dev50_root: Path) -> tuple[str, dict[str, Any]]:
    rows = {row["variant"]: row for row in comparison["models"]}
    metrics = ("compositional", "paraphrase", "dev50", "dev50_c10", "all")
    metric_labels = ("組合せ汎化\n13,400問", "未学習言い換え\n30問", "自然文dev50\n50問", "dev50新表現\nC10・5問", "正式5集合\n84,550問")
    values: dict[str, dict[str, float]] = {}
    dev_summaries = {}
    for variant in VARIANTS:
        dev = json.loads((dev50_root / variant / "summary.json").read_text(encoding="utf-8"))["boku/A"]
        dev_summaries[variant] = dev
        suite = rows[variant]["suites"]
        values[variant] = {
            "compositional": 100 * suite["compositional"]["passed_record_count"] / suite["compositional"]["evaluated_record_count"],
            "paraphrase": 100 * suite["paraphrase"]["passed_record_count"] / suite["paraphrase"]["evaluated_record_count"],
            "dev50": 100 * dev["passed"] / dev["total"],
            "dev50_c10": 100 * dev["categories"]["C10"] / 5,
            "all": 100 * rows[variant]["pass_rate"],
        }
    width, height = 1080, 590
    left, top, plot_w, plot_h = 92, 92, 940, 400
    group_w = plot_w / len(metrics)
    bar_w = 54
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<title>組合せ汎化・言い換えベンチマーク</title>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#172033}.title{font-size:22px;font-weight:650}.sub{font-size:12px;fill:#5b6577}.axis{font-size:11px}.value{font-size:11px;font-weight:650}.grid{stroke:#dce3ec;stroke-width:1}</style>',
        '<text x="540" y="32" text-anchor="middle" class="title">組合せ汎化・言い換えベンチマーク</text>',
        '<text x="540" y="54" text-anchor="middle" class="sub">実行正解率。集合サイズが異なるため列間ではなく、各列内で2条件を比較。</text>',
    ]
    for tick in range(0, 101, 20):
        py = top + (100 - tick) / 100 * plot_h
        parts += [f'<line x1="{left}" y1="{py:.1f}" x2="{left + plot_w}" y2="{py:.1f}" class="grid"/>',
                  f'<text x="{left - 10}" y="{py + 4:.1f}" text-anchor="end" class="axis">{tick}%</text>']
    for column, (metric, label) in enumerate(zip(metrics, metric_labels, strict=True)):
        center = left + (column + .5) * group_w
        for index, variant in enumerate(VARIANTS):
            value = values[variant][metric]
            x = center + (index - .5) * (bar_w + 9) - bar_w / 2
            y = top + (100 - value) / 100 * plot_h
            parts += [f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{top + plot_h - y:.1f}" fill="{COLORS[variant]}"/>',
                      f'<text x="{x + bar_w / 2:.1f}" y="{max(top + 13, y - 7):.1f}" text-anchor="middle" class="value">{value:.2f}%</text>']
        first, second = label.split("\n")
        parts += [f'<text x="{center:.1f}" y="{top + plot_h + 25}" text-anchor="middle" class="axis">{html.escape(first)}</text>',
                  f'<text x="{center:.1f}" y="{top + plot_h + 41}" text-anchor="middle" class="axis">{html.escape(second)}</text>']
    for index, variant in enumerate(VARIANTS):
        x = 350 + index * 300
        parts += [f'<rect x="{x}" y="{height - 35}" width="16" height="16" fill="{COLORS[variant]}"/>',
                  f'<text x="{x + 24}" y="{height - 22}" class="axis">{LABELS[variant]}</text>']
    parts.append('</svg>')
    return "\n".join(parts) + "\n", {"rates": values, "dev50": dev_summaries}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--dev50-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    loss, loss_values = loss_svg(args.run_directory)
    comparison = json.loads((args.run_directory / "comparison.json").read_text(encoding="utf-8"))
    benchmark, benchmark_values = benchmark_svg(comparison, args.dev50_directory)
    (args.output_directory / "training_loss.svg").write_text(loss, encoding="utf-8")
    (args.output_directory / "benchmark.svg").write_text(benchmark, encoding="utf-8")
    (args.output_directory / "values.json").write_text(
        json.dumps({"losses": loss_values, "evaluation": comparison, **benchmark_values},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
