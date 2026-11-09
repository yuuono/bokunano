#!/usr/bin/env python3
"""保存済みpass@5 runを統合し、middle4を含む比較図を別の出力先へ作る。推論は行わない。"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.model import report_composition872_cuda as greedy_report  # noqa: E402
from scripts.model import report_composition872_pass5 as previous_report  # noqa: E402
from scripts.model.evaluate_boku_composition_torch import (  # noqa: E402
    display_path, read_json, resolve_path, sha, write_json,
)

SUITES = greedy_report.PRESENTATION_SUITE_ORDER
LABELS = greedy_report.SUITE_LABELS
COUNTS = greedy_report.SUITE_COUNTS
GROUPS = {
    "standard": greedy_report.GROUPS["standard"],
    "short": greedy_report.GROUPS["short"],
    "ablation": greedy_report.GROUPS["ablation"],
    "middle": {"label": "1M・中間層反復", "color": "#B35C45"},
    "looped": greedy_report.GROUPS["looped"],
}
EXCLUDED_MODELS = ["boku-1m-1epoch", "boku-1m-short-1epoch"]
MAIN_MODELS = ["boku-1m-3epoch", "middle4-1m-3epoch", "middle4-scaled025-1m-3epoch"]
DEFAULT_GREEDY_ROOTS = [*previous_report.DEFAULT_GREEDY_ROOTS,
                        ROOT / "data/evaluations/composition872_cuda_20261025_middle4"]
DEFAULT_SAMPLING_ROOTS = [ROOT / "data/evaluations/composition872_pass5_cuda_20261025",
                          ROOT / "data/evaluations/composition872_pass5_cuda_20261025_middle4"]
require = previous_report.require


def display_metadata(row: dict) -> dict:
    """保存済み評価の来歴を変えず、middle反復と小型full-loopの表示を分ける。"""
    result = deepcopy(row)
    config = row["model_config"]
    if config.get("loop_pattern", "full") == "middle":
        require(row["model"] in MAIN_MODELS[1:], f"未定義のmiddleモデルです: {row['model']}")
        scale = .25 if row["model"] == MAIN_MODELS[2] else 1.0
        expected = {"d_model": 128, "d_ff": 256, "n_layers": 3, "n_heads": 4, "n_loops": 4,
                    "loop_pattern": "middle", "loop_input_mode": "none", "residual_scale": 1.0,
                    "recurrent_residual_scale": scale, "tie_word_embeddings": False}
        require(all(config.get(k) == v for k, v in expected.items())
                and row["parameter_count"] == 1016704 and row["epochs"] == 3,
                f"middle4の指定条件と異なります: {row['model']}")
        result.update(group="middle", group_label=GROUPS["middle"]["label"],
                      label=f"中間層×4・残差{scale:g} / 1M・3 epoch")
    else:
        require(row["model"] not in MAIN_MODELS[1:], "middle4の名前で別の構造を表示できません")
    return result


def merge_reports(reports: list[dict], baseline: dict, exclusions: list[str], expected_count: int) -> dict:
    require(bool(reports), "sampling runがありません")
    expected = {r["model"]: r for r in baseline["models"]}
    require(len(exclusions) == len(set(exclusions)), "表示除外モデルが重複しています")
    conditions = reports[0]["sampling_conditions"]
    merged = {}
    for report in reports:
        require(report["sampling_conditions"] == conditions, "sampling条件またはseedの異なるrunは統合しません")
        for key in ("questions_sha256", "test_cases_sha256", "protocol_sha256", "suite_order", "suite_counts"):
            require(report[key] == baseline[key], f"固定問題・カテゴリ条件が異なります: {key}")
        for row in report["models"]:
            name = row["model"]
            require(name not in merged, f"同じモデルを複数sampling runから混合できません: {name}")
            require(name in expected and row["metadata"] == expected[name]["metadata"],
                    f"統合対象とsamplingの重み・構造・tokenizerが異なります: {name}")
            merged[name] = display_metadata(row)
    require(set(merged) == set(expected), "sampling結果が入力greedyモデル集合と一致しません")
    require(set(exclusions) <= set(merged), "指定した表示除外モデルが入力にありません")
    for name in exclusions:
        row = merged[name]
        require(row["parameter_count"] == 1016704 and row["epochs"] == 1
                and row["model_config"].get("n_loops", 1) == 1,
                f"除外指定が通常1M・1epoch以外を指しています: {name}")
    visible = [r for name, r in merged.items() if name not in exclusions]
    visible.sort(key=lambda r: (list(GROUPS).index(r["group"]), -r["parameter_count"], r["epochs"], r["model"]))
    require(len(visible) == expected_count, f"表示モデル数が不一致です: {len(visible)} != {expected_count}")
    require(set(MAIN_MODELS) <= {r["model"] for r in visible}, "1M・3epochの主比較3モデルが揃っていません")
    return {
        "format_version": 2, "generated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
        **{key: baseline[key] for key in ("dataset", "questions_sha256", "test_cases_sha256", "protocol_sha256",
                                         "question_count", "test_case_count", "suite_order", "suite_labels", "suite_counts")},
        "groups": GROUPS, "input_model_count": len(merged), "model_count": len(visible),
        "group_counts": dict(Counter(r["group"] for r in visible)), "main_comparison_models": MAIN_MODELS,
        "display_exclusions": [{"model": name, "reason": "User-requested display exclusion of the 1M 1-epoch model; original evaluation artifacts are retained.",
                                "greedy_run_root": merged[name]["greedy_run_root"],
                                "pass5_run_root": merged[name]["pass5_run_root"],
                                "weight_sha256": merged[name]["weight_sha256"],
                                "artifact_hashes": merged[name]["artifact_hashes"]} for name in exclusions],
        "sampling_conditions": conditions, "metric_note": reports[0]["metric_note"],
        "greedy_runs": baseline["runs"],
        "sampling_runs": [{key: report[key] for key in ("pass5_run_root", "sampling_config", "completed_at", "source_hashes")}
                          for report in reports],
        "validation_dependencies": {display_path(Path(module.__file__)): sha(Path(module.__file__))
                                    for module in (greedy_report, previous_report)},
        "report_script": {"path": display_path(Path(__file__)), "sha256": sha(Path(__file__))},
        "models": visible,
    }


def collect(sampling_roots: list[Path], greedy_roots: list[Path], exclusions: list[str],
            expected_input_count: int = 20, expected_count: int = 18) -> dict:
    greedy_roots = [p.resolve() for p in greedy_roots]
    baseline = greedy_report.collect(greedy_roots, expected_input_count)
    allowed_roots = set(greedy_roots)
    reports = []
    for root in sampling_roots:
        root = root.resolve()
        config = read_json(root / "config.json")
        specs = config.get("models", [])
        names = [s["name"] for s in specs]
        require(bool(names) and len(names) == len(set(names)), f"samplingモデル一覧が不正です: {root}")
        source_roots = []
        for name in names:
            model_config = read_json(root / name / "config.json")
            source = resolve_path(model_config["greedy_run_root"]).resolve()
            require(source in allowed_roots, f"指定外の元greedy runです: {source}")
            if source not in source_roots:
                source_roots.append(source)
        # 元18モデルと追加2モデルを、それぞれ実際に使った元greedy集合で検証する。
        # 凍結済み検証器がモデル集合・hash・4360候補・全872問の合否を再確認する。
        reports.append(previous_report.collect(root, source_roots, len(names)))
    return merge_reports(reports, baseline, exclusions, expected_count)


def plot_bars(rows: list[dict], title: str, stem: str, output: Path, plt, *, main: bool = False) -> None:
    import numpy as np
    from matplotlib.patches import Patch
    fig, axes = plt.subplots(2, 1, figsize=(20, 13))
    centers = np.arange(len(SUITES))
    width = .82 / len(rows)
    labels = [f"{LABELS[s]}\n(n={COUNTS[s]})" for s in SUITES]
    legend_labels = (["通常3層・1M・3 epoch", "中間層×4・残差1.0・1M・3 epoch",
                      "中間層×4・残差0.25・1M・3 epoch"] if main else [r["label"] for r in rows])
    for ax, metric, panel in zip(axes, ("pass_at_1", "pass_at_5"),
                               ("pass@1 — greedy 1候補", "pass@5 — greedy 1候補＋sampling 4候補")):
        for index, row in enumerate(rows):
            rates = [row["suites"][s][metric + "_percentage"] for s in SUITES]
            positions = centers - .41 + width * (index + .5)
            bars = ax.bar(positions, rates, width=width * .94,
                          color=previous_report.PALETTE[index], edgecolor="white", linewidth=.3)
            for bar, value in zip(bars, rates):
                text = str(int(value)) if value in (0, 100) else f"{value:.1f}"
                ax.text(bar.get_x() + bar.get_width() / 2, value + 1.1, text,
                        ha="center", va="bottom", fontsize=8.5, rotation=90 if len(rows) > 4 else 0)
        ax.set_ylim(0, 111)
        ax.set_yticks(range(0, 101, 20))
        ax.set_xticks(centers, labels, fontsize=10)
        ax.set_ylabel("実行正解率 (%)")
        ax.set_title(panel, loc="left", fontsize=15, pad=12)
        ax.grid(axis="y", color="#DCE2E8", linewidth=.65)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"{title}｜旧872問・9カテゴリのpass@1 / pass@5", x=.035, y=.985, ha="left", fontsize=19)
    fig.legend(handles=[Patch(facecolor=previous_report.PALETTE[i], label=label)
                        for i, label in enumerate(legend_labels)], loc="upper left", bbox_to_anchor=(.04, .947),
               ncol=3 if main or len(rows) > 4 else 2, frameon=False, fontsize=11)
    note = ("主比較は全て1,016,704 parameters・3 epoch。通常3層は3回、中間反復は6回のblock適用。"
            if main else "モデル容量・epoch・tokenizerは各系列の凡例を参照。1M・1epochの2モデルは新図の表示対象外。")
    fig.text(.04, .024, "棒の数値は正解率(%)。pass@5は同じgreedyを含む計5候補の少なくとも1つが全179入力で正解なら合格。\n"
             "sampling: temperature=0.8 / top-p=0.95。" + note, fontsize=10, color="#46515E")
    fig.subplots_adjust(left=.055, right=.99, top=.85, bottom=.11, hspace=.32)
    previous_report.save_plot(fig, output, stem, plt)


def plot_all(values: dict, output: Path) -> list[str]:
    import numpy as np
    plt = greedy_report.configure_plotting()
    rows = values["models"]
    mapping = {r["model"]: r for r in rows}
    stems = ["categories_1m_3epoch"]
    plot_bars([mapping[name] for name in MAIN_MODELS], "1M・3 epoch：通常層と中間層反復", stems[0], output, plt, main=True)
    for group in greedy_report.GROUPS:
        subset = [r for r in rows if r["group"] == group]
        require(bool(subset), f"表示系列が空です: {group}")
        stem = f"categories_{group}"
        plot_bars(subset, GROUPS[group]["label"], stem, output, plt)
        stems.append(stem)
    fig, axes = plt.subplots(2, 1, figsize=(17, max(16, len(rows) + 6)), gridspec_kw={"hspace": .28})
    labels = [f"{LABELS[s]}\n(n={COUNTS[s]})" for s in SUITES]
    for ax, metric, title in zip(axes, ("pass_at_1", "pass_at_5"),
                               ("pass@1：greedy 1候補", "pass@5：greedy 1＋sampling 4候補")):
        matrix = np.array([[row["suites"][s][metric + "_percentage"] for s in SUITES] for row in rows])
        heat = ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=100, aspect="auto")
        ax.set_xticks(range(len(SUITES)), labels, fontsize=10)
        ax.set_yticks(range(len(rows)), [r["label"] for r in rows])
        ax.tick_params(top=True, labeltop=True, bottom=False, labelbottom=False, length=0, pad=8)
        ax.set_title(title, fontsize=18, pad=65)
        for i, row in enumerate(rows):
            for j, suite in enumerate(SUITES):
                cell = row["suites"][suite]
                percent = cell[metric + "_percentage"]
                ax.text(j, i, f"{cell[metric + '_count']}/{cell['total']}\n{percent:.1f}%",
                        ha="center", va="center", fontsize=10, color="white" if percent >= 58 else "#17212D")
            if i and rows[i - 1]["group"] != row["group"]:
                ax.axhline(i - .5, color="white", linewidth=3)
        for tick, row in zip(ax.get_yticklabels(), rows):
            tick.set_color(GROUPS[row["group"]]["color"])
            tick.set_fontsize(10)
    fig.subplots_adjust(left=.25, right=.93, top=.91, bottom=.06)
    colorbar = fig.add_axes([.948, .19, .012, .59])
    fig.colorbar(heat, cax=colorbar, label="実行正解率 (%)")
    fig.suptitle(f"Boku-nano {len(rows)}モデル｜middle4追加後のカテゴリ別pass@1 / pass@5",
                 x=.02, y=.985, ha="left", fontsize=21)
    fig.text(.02, .024, "各セル: 合格問題数 / カテゴリ問題数、正解率。上下は同じモデル・同じ問題。全9カテゴリを表示。\n"
             "既存18＋追加middle4 2モデルから、通常1M・1epochの標準/短いBPEを表示除外。元の評価結果は保持。\n"
             "pass@5 = greedy 1＋sampling 4 (temperature 0.8, top-p 0.95)。［設定復元］は小型loopの既存重みを使用。",
             fontsize=10, color="#46515E")
    stem = "category_heatmaps_pass1_pass5"
    previous_report.save_plot(fig, output, stem, plt)
    stems.append(stem)
    return stems


def markdown(values: dict, stems: list[str]) -> str:
    mapping = {r["model"]: r for r in values["models"]}
    lines = ["# middle4追加後：旧872問のカテゴリ別pass@1 / pass@5", "",
             f"作成日時: {values['generated_at']}。入力{values['input_model_count']}モデル、表示{values['model_count']}モデル。", "",
             "既存greedy/pass@5を再生成せず、別runのmiddle4 2モデルを統合した。通常1M・1epochの標準BPEと短いBPEは新図から除外し、元結果を保持した。", "",
             "pass@1は既存greedy 1候補。pass@5は同じgreedyとtemperature=0.8、top-p=0.95のsampling 4候補を合わせた実測成功率。"
             "計5候補の少なくとも1つが179入力・契約検査を全て通れば合格。同一分布のiid pass@k推定量とは異なり、追加推論予算を含む。", "",
             f"sampling seed: `{values['sampling_conditions']['sampling_seed']}`。", "",
             "## 主比較：通常1M・3epochとmiddle4", "",
             "![主比較](categories_1m_3epoch.png)", "",
             "| モデル | pass@1 | pass@5 | block適用数 |", "|---|---:|---:|---:|"]
    for name in MAIN_MODELS:
        row = mapping[name]
        lines.append(f"| {row['label']} | {row['pass_at_1_count']}/872 ({row['pass_at_1_percentage']:.2f}%) | "
                     f"{row['pass_at_5_count']}/872 ({row['pass_at_5_percentage']:.2f}%) | {3 if name == MAIN_MODELS[0] else 6} |")
    lines.extend(["", "全3モデルは1,016,704 parameters・3 epoch。中間反復は圧縮モデルではなく、追加のblock計算を行う。", "",
                  "## 表示対象の全モデル", "", "| モデル | 系列 | parameters | epoch | pass@1 | pass@5 |",
                  "|---|---|---:|---:|---:|---:|"])
    for row in values["models"]:
        lines.append(f"| {row['model']} | {row['group_label']} | {row['parameter_count']:,} | {row['epochs']} | "
                     f"{row['pass_at_1_count']}/872 ({row['pass_at_1_percentage']:.2f}%) | "
                     f"{row['pass_at_5_count']}/872 ({row['pass_at_5_percentage']:.2f}%) |")
    for metric in ("pass_at_1", "pass_at_5"):
        lines.extend(["", "## カテゴリ別" + metric.replace("pass_at_", "pass@"), "",
                      "| モデル | " + " | ".join(LABELS[s] for s in SUITES) + " |", "|---|" + "---:|" * len(SUITES)])
        for row in values["models"]:
            cells = [f"{row['suites'][s][metric + '_count']}/{row['suites'][s]['total']} "
                     f"({row['suites'][s][metric + '_percentage']:.2f}%)" for s in SUITES]
            lines.append(f"| {row['model']} | " + " | ".join(cells) + " |")
    lines.extend(["", "## 図", ""])
    for stem in stems:
        lines.append(f"- [{stem}: PNG]({stem}.png) / [SVG]({stem}.svg) / [PDF]({stem}.pdf)")
    lines.extend(["", "## 入力と表示除外", "",
                  "各sampling runは、そのrunが使用した元greedy集合で独立に検証した。完了状態、設定・成果物hash、"
                  "同一重み・構造・tokenizer、872問×5候補、カテゴリ別/全体の合計、pass@5 ≥ pass@1を確認した。", ""])
    for run in values["sampling_runs"]:
        lines.append(f"- sampling入力: `{run['pass5_run_root']}`")
    for row in values["display_exclusions"]:
        lines.append(f"- 表示除外のみ: `{row['model']}`。元結果: `{row['pass5_run_root']}`")
    lines.extend(["", "全モデルの来歴・問題別合否・表示除外理由・依存scriptのhashは[values.json](values.json)に記録。"
                  "過去の図と評価結果は上書きしていない。", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sampling-run-roots", nargs="+", type=Path, default=DEFAULT_SAMPLING_ROOTS)
    parser.add_argument("--greedy-run-roots", nargs="+", type=Path, default=DEFAULT_GREEDY_ROOTS)
    parser.add_argument("--exclude-models", nargs="+", default=EXCLUDED_MODELS)
    parser.add_argument("--expected-input-model-count", type=int, default=20)
    parser.add_argument("--expected-model-count", type=int, default=18)
    parser.add_argument("--output-directory", type=Path,
                        default=ROOT / "docs/results/figures/composition872_pass5_cuda_20261025_with_middle4")
    args = parser.parse_args(argv)
    if min(args.expected_input_model_count, args.expected_model_count) <= 0:
        parser.error("モデル数は正整数にしてください")
    output = args.output_directory.resolve()
    if output.exists() or output.is_symlink():
        parser.error("既存出力は上書きしません。新しい出力先を指定してください")
    values = collect([resolve_path(p) for p in args.sampling_run_roots],
                     [resolve_path(p) for p in args.greedy_run_roots], args.exclude_models,
                     args.expected_input_model_count, args.expected_model_count)
    output.mkdir(parents=True, exist_ok=False)
    stems = plot_all(values, output)
    values["figures"] = {stem: {ext: sha(output / f"{stem}.{ext}") for ext in ("png", "svg", "pdf")} for stem in stems}
    write_json(output / "values.json", values)
    (output / "summary.md").write_text(markdown(values, stems), encoding="utf-8")
    print(json.dumps({"status": "completed", "input_model_count": values["input_model_count"],
                      "model_count": values["model_count"], "group_counts": values["group_counts"],
                      "output_directory": display_path(output), "figures": stems}, ensure_ascii=False))


if __name__ == "__main__":
    main()
