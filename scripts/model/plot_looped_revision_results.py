#!/usr/bin/env python3
"""1M loop修正4候補と3対照のloss・固定評価をSVGへまとめる。"""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any


VARIANTS = (
    "u3", "u3_r2", "u3_slow", "u3_r2_slow",
    "u3_r2_scaled", "u3_r2_add", "u3_middle4",
)
LABELS = {
    "u3": "通常版",
    "u3_r2": "元2周版",
    "u3_slow": "通常・遅い減衰",
    "u3_r2_slow": "候補1・遅い減衰",
    "u3_r2_scaled": "候補2・残差0.5倍",
    "u3_r2_add": "候補3・入力再注入",
    "u3_middle4": "候補4・中間層4回",
}
COLORS = {
    "u3": "#2563eb",
    "u3_r2": "#64748b",
    "u3_slow": "#06b6d4",
    "u3_r2_slow": "#7c3aed",
    "u3_r2_scaled": "#16a34a",
    "u3_r2_add": "#ea580c",
    "u3_middle4": "#db2777",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_losses(root: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for variant in VARIANTS:
        rows = jsonl(root / f"{variant}_seed20260925/model/training_metrics.jsonl")
        train = [(int(row["global_step"]), float(row["loss"])) for row in rows if "loss" in row]
        validation = [row for row in rows if row.get("event") == "validation"]
        if not train or len(validation) != 1:
            raise ValueError(f"lossが揃っていません: {variant}")
        result[variant] = {
            "train": train,
            "final_train_loss": train[-1][1],
            "validation_loss": float(validation[0]["validation_loss"]),
            "validation_perplexity": float(validation[0]["validation_perplexity"]),
        }
    return result


def loss_svg(values: dict[str, dict[str, Any]]) -> str:
    width, height = 1180, 720
    left, right, top, bottom = 88, 36, 92, 142
    plot_w, plot_h = width - left - right, height - top - bottom
    points = [point for item in values.values() for point in item["train"]]
    losses = [loss for _, loss in points] + [item["validation_loss"] for item in values.values()]
    max_step = max(step for step, _ in points)
    log_min, log_max = math.log(min(losses) * .8), math.log(max(losses) * 1.2)

    def x(step: int) -> float:
        return left + step / max_step * plot_w

    def y(loss: float) -> float:
        return top + (1 - (math.log(loss) - log_min) / (log_max - log_min)) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<title>1M loop修正4候補と対照の1 epoch loss</title>',
        '<desc>線は20 optimizer step区間のtrain loss、右端の四角はvalidation loss。</desc>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#172033}.title{font-size:22px;font-weight:600}.sub{font-size:12px;fill:#5b6577}.axis{font-size:11px}.grid{stroke:#dce3ec;stroke-width:1}</style>',
        '<text x="590" y="34" text-anchor="middle" class="title">1M loop修正4候補：1 epoch loss</text>',
        '<text x="590" y="57" text-anchor="middle" class="sub">線: train区間平均　四角: epoch終了時validation　全条件377更新</text>',
    ]
    for step in (0, 50, 100, 150, 200, 250, 300, 350, max_step):
        px = x(step)
        parts += [f'<line x1="{px:.1f}" y1="{top}" x2="{px:.1f}" y2="{top + plot_h}" class="grid"/>',
                  f'<text x="{px:.1f}" y="{top + plot_h + 24}" text-anchor="middle" class="axis">{step}</text>']
    for tick in (.5, 1, 2, 5, 10):
        if math.exp(log_min) <= tick <= math.exp(log_max):
            py = y(tick)
            parts += [f'<line x1="{left}" y1="{py:.1f}" x2="{left + plot_w}" y2="{py:.1f}" class="grid"/>',
                      f'<text x="{left - 11}" y="{py + 4:.1f}" text-anchor="end" class="axis">{tick:g}</text>']
    for variant in VARIANTS:
        color = COLORS[variant]
        line = " ".join(f"{x(step):.1f},{y(loss):.1f}" for step, loss in values[variant]["train"])
        parts.append(f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2.2" stroke-linejoin="round"/>')
        vy = y(values[variant]["validation_loss"])
        parts.append(f'<rect x="{x(max_step) - 4:.1f}" y="{vy - 4:.1f}" width="8" height="8" fill="{color}" stroke="#fff"/>')
    for index, variant in enumerate(VARIANTS):
        column, row = index % 4, index // 4
        lx, ly = left + column * 260, height - 65 + row * 28
        parts += [f'<line x1="{lx}" y1="{ly}" x2="{lx + 27}" y2="{ly}" stroke="{COLORS[variant]}" stroke-width="3"/>',
                  f'<text x="{lx + 35}" y="{ly + 4}" class="axis">{html.escape(LABELS[variant])}</text>']
    parts += [f'<text x="{width / 2}" y="{top + plot_h + 50}" text-anchor="middle" class="axis">Optimizer step</text>',
              f'<text x="22" y="{top + plot_h / 2}" text-anchor="middle" class="axis" transform="rotate(-90 22 {top + plot_h / 2})">Loss（対数目盛）</text>', '</svg>']
    return "\n".join(parts) + "\n"


def evaluation_svg(comparison: dict[str, Any]) -> str:
    rows = {row["variant"]: row for row in comparison["models"]}
    suites = list(rows["u3"]["suites"])
    columns = [*suites, "all"]
    labels = {name: name.replace("_", " ") for name in suites} | {"all": "5集合合計"}
    values: dict[str, list[float]] = {}
    for variant in VARIANTS:
        item = rows[variant]
        rates = []
        for column in columns:
            if column == "all":
                rates.append(100 * float(item["pass_rate"]))
            else:
                suite = item["suites"][column]
                rates.append(100 * suite["passed_record_count"] / suite["evaluated_record_count"])
        values[variant] = rates
    maximum = max(value for rates in values.values() for value in rates) or 1
    width, height = 1120, 540
    left, top, cell_w, cell_h = 245, 98, 136, 51
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<title>1M loop修正4候補の固定5集合実行評価</title>',
        '<desc>各セルは生成コードの実行正解率。濃いほど高い。</desc>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:system-ui,sans-serif;fill:#172033}.title{font-size:22px;font-weight:600}.sub{font-size:12px;fill:#5b6577}.axis{font-size:11px}.value{font-size:12px;font-weight:600}</style>',
        '<text x="560" y="34" text-anchor="middle" class="title">固定5集合の実行正解率</text>',
        '<text x="560" y="57" text-anchor="middle" class="sub">全84,550件。候補は元2周版から一要因だけ変更。</text>',
    ]
    for column, name in enumerate(columns):
        x = left + (column + .5) * cell_w
        parts.append(f'<text x="{x:.1f}" y="{top - 15}" text-anchor="middle" class="axis">{html.escape(labels[name])}</text>')
    for row_index, variant in enumerate(VARIANTS):
        y = top + row_index * cell_h
        parts.append(f'<text x="{left - 12}" y="{y + 31}" text-anchor="end" class="axis">{html.escape(LABELS[variant])}</text>')
        for column, value in enumerate(values[variant]):
            ratio = value / maximum
            start, end = (237, 244, 255), (30, 64, 175)
            rgb = tuple(round(a + (b - a) * ratio) for a, b in zip(start, end, strict=True))
            fill = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            x = left + column * cell_w
            text_color = "#fff" if ratio > .55 else "#172033"
            parts += [f'<rect x="{x + 2:.1f}" y="{y + 2:.1f}" width="{cell_w - 4:.1f}" height="{cell_h - 4:.1f}" fill="{fill}"/>',
                      f'<text x="{x + cell_w / 2:.1f}" y="{y + 31:.1f}" text-anchor="middle" class="value" fill="{text_color}">{value:.3f}%</text>']
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def main() -> None:
    args = parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    losses = load_losses(args.run_directory)
    comparison = json.loads((args.run_directory / "comparison.json").read_text(encoding="utf-8"))
    (args.output_directory / "training_loss.svg").write_text(loss_svg(losses), encoding="utf-8")
    (args.output_directory / "evaluation_pass_rate.svg").write_text(evaluation_svg(comparison), encoding="utf-8")
    (args.output_directory / "values.json").write_text(
        json.dumps({"losses": losses, "evaluation": comparison}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote revision figures to {args.output_directory}")


if __name__ == "__main__":
    main()
