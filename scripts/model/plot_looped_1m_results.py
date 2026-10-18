#!/usr/bin/env python3
"""1M通常版とloop版のloss・固定評価を比較するSVGを生成する。"""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any


VARIANTS = ("u3", "u3_r2", "u3_r3")
LABELS = {"u3": "通常 3層×1周", "u3_r2": "3層×2周", "u3_r3": "3層×3周"}
COLORS = {"u3": "#2563eb", "u3_r2": "#ea580c", "u3_r3": "#16a34a"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_losses(run_directory: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for variant in VARIANTS:
        path = run_directory / f"{variant}_seed20260925/model/training_metrics.jsonl"
        rows = load_jsonl(path)
        train = [(int(r["global_step"]), float(r["loss"])) for r in rows if "loss" in r]
        validation = [r for r in rows if r.get("event") == "validation"]
        if not train or len(validation) != 1:
            raise ValueError(f"1epochのtrain/validation lossが揃っていません: {path}")
        result[variant] = {
            "train": train,
            "validation_loss": float(validation[0]["validation_loss"]),
            "validation_tokens": int(validation[0]["validation_supervised_tokens"]),
        }
    return result


def loss_svg(values: dict[str, dict[str, Any]]) -> str:
    width, height = 1120, 650
    left, right, top, bottom = 86, 32, 90, 90
    plot_w, plot_h = width - left - right, height - top - bottom
    all_points = [point for value in values.values() for point in value["train"]]
    max_step = max(step for step, _ in all_points)
    all_losses = [loss for _, loss in all_points] + [
        value["validation_loss"] for value in values.values()
    ]
    y_min = min(all_losses) * 0.8
    y_max = max(all_losses) * 1.2
    log_min, log_max = math.log(y_min), math.log(y_max)

    def x(step: int) -> float:
        return left + step / max_step * plot_w

    def y(loss: float) -> float:
        return top + (1 - (math.log(loss) - log_min) / (log_max - log_min)) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<title>1M通常版とloop版の1epoch train loss</title>',
        '<desc>同じ初期値、データ、optimizerで、3層を1周、2周、3周するモデルを比較。</desc>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#172033}.title{font-size:22px;font-weight:600}.sub{font-size:12px;fill:#5b6577}.axis{font-size:12px}.grid{stroke:#dce3ec;stroke-width:1}</style>',
        '<text x="560" y="34" text-anchor="middle" class="title">同じ1M構造でloop回数だけを増やした学習loss</text>',
        '<text x="560" y="57" text-anchor="middle" class="sub">線は20 optimizer step区間のtrain平均、右端の四角は固定validation。全条件1 epoch・377更新。</text>',
    ]
    for step in (0, 50, 100, 150, 200, 250, 300, 350, max_step):
        px = x(step)
        parts += [f'<line x1="{px:.1f}" y1="{top}" x2="{px:.1f}" y2="{top + plot_h}" class="grid"/>',
                  f'<text x="{px:.1f}" y="{top + plot_h + 24}" text-anchor="middle" class="axis">{step}</text>']
    for tick in (0.1, 0.2, 0.5, 1, 2, 5, 10):
        if y_min <= tick <= y_max:
            py = y(tick)
            parts += [f'<line x1="{left}" y1="{py:.1f}" x2="{left + plot_w}" y2="{py:.1f}" class="grid"/>',
                      f'<text x="{left - 12}" y="{py + 4:.1f}" text-anchor="end" class="axis">{tick:g}</text>']
    for index, variant in enumerate(VARIANTS):
        points = " ".join(f"{x(s):.1f},{y(v):.1f}" for s, v in values[variant]["train"])
        color = COLORS[variant]
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>')
        validation_loss = float(values[variant]["validation_loss"])
        vy = y(validation_loss)
        parts.append(
            f'<rect x="{x(max_step) - 5:.1f}" y="{vy - 5:.1f}" width="10" height="10" '
            f'fill="{color}" stroke="#fff" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{x(max_step) - 11:.1f}" y="{vy - 8 - index * 15:.1f}" '
            f'text-anchor="end" class="axis">val {validation_loss:.4f}</text>'
        )
        lx = left + index * 230
        parts += [f'<line x1="{lx}" y1="{height - 29}" x2="{lx + 28}" y2="{height - 29}" stroke="{color}" stroke-width="3"/>',
                  f'<text x="{lx + 36}" y="{height - 24}" class="axis">{html.escape(LABELS[variant])}</text>']
    parts += [f'<text x="{width / 2}" y="{height - 55}" text-anchor="middle" class="axis">Optimizer step</text>',
              f'<text x="22" y="{top + plot_h / 2}" text-anchor="middle" class="axis" transform="rotate(-90 22 {top + plot_h / 2})">Train loss（対数目盛）</text>',
              '</svg>']
    return "\n".join(parts) + "\n"


def evaluation_svg(comparison: dict[str, Any]) -> str:
    width, height = 1120, 620
    left, right, top, bottom = 92, 30, 88, 115
    plot_w, plot_h = width - left - right, height - top - bottom
    rows = {row["variant"]: row for row in comparison["models"]}
    suite_names = list(rows["u3"]["suites"])
    groups = [*suite_names, "all"]
    group_labels = {name: name.replace("_", " ") for name in suite_names} | {"all": "5集合合計"}

    def rate(variant: str, group: str) -> float:
        row = rows[variant]
        if group == "all":
            return 100 * float(row["pass_rate"])
        suite = row["suites"][group]
        return 100 * int(suite["passed_record_count"]) / int(suite["evaluated_record_count"])

    maximum = max(rate(v, g) for v in VARIANTS for g in groups)
    y_max = max(10.0, math.ceil(maximum / 10) * 10)

    def y(value: float) -> float:
        return top + (1 - value / y_max) * plot_h

    group_w = plot_w / len(groups)
    bar_w = min(34, group_w / 4.2)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<title>1M通常版とloop版の固定5集合実行評価</title>',
        '<desc>生成したPythonコードを実行して正解した割合。</desc>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#172033}.title{font-size:22px;font-weight:600}.sub{font-size:12px;fill:#5b6577}.axis{font-size:11px}.value{font-size:10px}.grid{stroke:#dce3ec;stroke-width:1}</style>',
        '<text x="560" y="34" text-anchor="middle" class="title">固定5集合の実行正解率</text>',
        '<text x="560" y="57" text-anchor="middle" class="sub">高いほど良い。通常3層とloop版は同じパラメータ数・学習データ量。</text>',
    ]
    for tick in range(0, int(y_max) + 1, 10):
        py = y(tick)
        parts += [f'<line x1="{left}" y1="{py:.1f}" x2="{left + plot_w}" y2="{py:.1f}" class="grid"/>',
                  f'<text x="{left - 10}" y="{py + 4:.1f}" text-anchor="end" class="axis">{tick}%</text>']
    for gi, group in enumerate(groups):
        center = left + (gi + 0.5) * group_w
        for vi, variant in enumerate(VARIANTS):
            value = rate(variant, group)
            px = center + (vi - 1) * (bar_w + 5) - bar_w / 2
            py = y(value)
            parts += [f'<rect x="{px:.1f}" y="{py:.1f}" width="{bar_w:.1f}" height="{top + plot_h - py:.1f}" fill="{COLORS[variant]}"/>',
                      f'<text x="{px + bar_w / 2:.1f}" y="{py - 5:.1f}" text-anchor="middle" class="value">{value:.2f}</text>']
        parts.append(f'<text x="{center:.1f}" y="{top + plot_h + 25}" text-anchor="middle" class="axis">{html.escape(group_labels[group])}</text>')
    for index, variant in enumerate(VARIANTS):
        lx = left + index * 230
        parts += [f'<rect x="{lx}" y="{height - 30}" width="13" height="13" fill="{COLORS[variant]}"/>',
                  f'<text x="{lx + 21}" y="{height - 19}" class="axis">{html.escape(LABELS[variant])}</text>']
    parts += [f'<text x="22" y="{top + plot_h / 2}" text-anchor="middle" class="axis" transform="rotate(-90 22 {top + plot_h / 2})">Pass@1（実行正解率）</text>', '</svg>']
    return "\n".join(parts) + "\n"


def main() -> None:
    args = parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    losses = load_losses(args.run_directory)
    comparison = json.loads((args.run_directory / "comparison.json").read_text(encoding="utf-8"))
    (args.output_directory / "training_loss.svg").write_text(loss_svg(losses), encoding="utf-8")
    (args.output_directory / "evaluation_pass_rate.svg").write_text(
        evaluation_svg(comparison), encoding="utf-8"
    )
    summary = {"losses": losses, "evaluation": comparison}
    (args.output_directory / "values.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote figures and values to {args.output_directory}")


if __name__ == "__main__":
    main()
