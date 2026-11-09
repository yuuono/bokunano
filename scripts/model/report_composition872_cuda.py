#!/usr/bin/env python3
"""完了済みCUDA評価を検証し、旧872問のBoku-nano比較図と集計を作る（推論なし）。"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.model.evaluate_boku_composition_torch import (  # noqa: E402
    CONTEXT_LENGTH, DATASET, PROMPT_TEMPLATE, PROTOCOL_SHA256, QUESTIONS_SHA256,
    SCORING_HASHES, SUITE_COUNTS, TEST_CASES_SHA256, TOKENIZER_SHA256,
    display_path, read_json, read_jsonl, resolve_path, sha, summarize,
    validate_dataset, validate_record_identity, write_json,
)

SHORT_TOKENIZER_SHA256 = "f09f3d7eccbca2ab1224c662064b71e572d64147147b8b559ebdb428eb035dbf"
# 発表資料の表示順。採点器・protocolの集合定義や問題順は変更しない。
PRESENTATION_SUITE_ORDER = [
    "transfer_1op", "composition_2op", "transfer_3to2", "repeat_2",
    "composition_3op", "repeat_3", "general_4op", "repeat_abab", "repeat_4",
]
GROUPS = {
    "standard": {"label": "通常モデル・標準BPE", "color": "#2878B5"},
    "short": {"label": "通常モデル・短いBPE", "color": "#D07C22"},
    "ablation": {"label": "構造比較・標準BPE", "color": "#4A9277"},
    "looped": {"label": "小型Looped・標準BPE", "color": "#8861A8"},
}
SUITE_LABELS = {
    "transfer_1op": "1操作への転移", "composition_2op": "未学習2操作",
    "repeat_2": "同一操作×2", "transfer_3to2": "3→2操作への転移",
    "composition_3op": "未学習3操作", "repeat_3": "同一操作×3",
    "repeat_4": "同一操作×4", "general_4op": "一般4操作", "repeat_abab": "ABAB型4操作",
}
FIXED_CONFIG = {
    "questions_sha256": QUESTIONS_SHA256, "test_cases_sha256": TEST_CASES_SHA256,
    "prompt_template": PROMPT_TEMPLATE, "context_length": CONTEXT_LENGTH,
    "condition": "A", "decoding": "greedy", "temperature": 0,
    "history": False, "repair": False, "dtype": "float32", "tf32": False,
    "autocast": False, "sdpa_backend": "math", "kv_cache": False,
    "batching": "equal_prompt_length_no_padding",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def fixed_config(config: dict, source: Path) -> None:
    for key, value in FIXED_CONFIG.items():
        require(config.get(key) == value, f"固定評価条件が一致しません: {source}: {key}")
    require(type(config.get("batch_size")) is int and config["batch_size"] > 0,
            f"batch_sizeが不正です: {source}")


def architecture_identity(config: dict) -> str:
    normalized = {"n_loops": 1, "loop_input_mode": "none", "loop_pattern": "full",
                  "residual_scale": 1.0, "recurrent_residual_scale": 1.0, **config}
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


def classify(spec: dict) -> tuple[str, str, bool]:
    config = spec["model_config"]
    parameters, epochs = spec["parameter_count"], spec["epochs"]
    tokenizer_sha = spec["tokenizer_sha256"]
    directory = spec.get("directory", "")
    recovered = ("recovered" in json.dumps(spec, ensure_ascii=False).lower()
                 or spec.get("original_training_manifest_present") is False)
    if config.get("n_loops", 1) > 1:
        names = {(128, 256): "LT1", (128, 128): "F128", (96, 192): "W96", (64, 128): "W64"}
        name = names.get((config.get("d_model"), config.get("d_ff")), spec["name"])
        label = f"{name}  {parameters / 1e6:.3f}M・{epochs} epoch"
        return "looped", label + ("［設定復元］" if recovered else ""), recovered
    if ("architecture_ablation" in directory or "ablation" in spec["name"]
            or (config.get("d_model") == 384 and config.get("n_layers") in (2, 4, 6))
            or (config.get("d_model"), config.get("d_ff"), config.get("n_layers")) == (256, 1024, 8)):
        if (config.get("d_model"), config.get("d_ff"), config.get("n_layers")) == (384, 1024, 8):
            # 元15Mと同一の保存物は通常モデルとして扱い、重複を後で除く。
            return "standard", f"15M・{epochs} epoch", recovered
        label = (f"{config['n_layers']}層・幅{config['d_model']} / "
                 f"{parameters / 1e6:.2f}M・{epochs} epoch")
        return "ablation", label, recovered
    size = "15M" if parameters > 10_000_000 else "5M" if parameters > 3_000_000 else "1M"
    group = "short" if tokenizer_sha == SHORT_TOKENIZER_SHA256 else "standard"
    return group, f"{size}・{epochs} epoch" + ("［短いBPE］" if group == "short" else ""), recovered


def read_run(root: Path, questions: list[dict]) -> tuple[list[dict], dict]:
    comparison_path = root / "comparison.json"
    comparison = read_json(comparison_path)
    require(comparison.get("status") == "completed", f"未完了runは集計できません: {root}")
    require(comparison.get("questions_sha256") == QUESTIONS_SHA256
            and comparison.get("test_cases_sha256") == TEST_CASES_SHA256,
            f"旧872問のhashではありません: {root}")
    root_config = read_json(root / "config.json")
    fixed_config(root_config, root / "config.json")
    environment = read_json(root / "environment.json")
    require(str(environment.get("device", "")).startswith("cuda") and environment.get("cuda"),
            f"CUDA評価の記録ではありません: {root}")
    require(sha(root / "protocol.json") == PROTOCOL_SHA256, f"protocol hash不一致: {root}")
    root_specs = {s["name"]: s for s in root_config["models"]}
    results = comparison.get("models", [])
    require(bool(results) and len({r["model"] for r in results}) == len(results)
            and set(root_specs) == {r["model"] for r in results}, f"モデル一覧不一致: {root}")
    question_map = {q["question_id"]: q for q in questions}
    models = []
    for result in results:
        name = result["model"]
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) is not None
                and "qwen" not in name.lower(), f"対象外モデル名: {name}")
        folder = root / name
        config = read_json(folder / "config.json")
        fixed_config(config, folder / "config.json")
        require(config.get("model") == name, f"モデル名不一致: {folder}")
        spec = config["model_metadata"]
        require(spec == root_specs[name] and spec.get("name") == name, f"モデルmetadata不一致: {folder}")
        for key in ("parameter_count", "epochs"):
            require(type(spec.get(key)) is int and spec[key] > 0 and spec[key] == result.get(key),
                    f"{key}不一致: {folder}")
        tokenizer_sha = spec["tokenizer_sha256"]
        require(tokenizer_sha in (TOKENIZER_SHA256, SHORT_TOKENIZER_SHA256)
                and config.get("tokenizer_sha256") == tokenizer_sha
                and root_config.get("tokenizer_sha256") == tokenizer_sha,
                f"tokenizer hash不一致: {folder}")
        require(config.get("weight_sha256") == spec.get("weight_sha256")
                and re.fullmatch(r"[0-9a-f]{64}", spec["weight_sha256"]) is not None,
                f"重みhash不一致: {folder}")
        provenance = read_json(folder / "scoring_provenance.json")
        expected = {"questions_sha256": QUESTIONS_SHA256, "test_cases_sha256": TEST_CASES_SHA256,
                    "tokenizer_sha256": tokenizer_sha,
                    "scorer_sha256": SCORING_HASHES["scripts/model/score_composition_suite.py"],
                    "common_sha256": SCORING_HASHES["scripts/model/composition_suite_common.py"]}
        for key, value in expected.items():
            require(provenance.get(key) == value, f"採点provenance不一致: {folder}: {key}")
        for filename, key in (("raw_inference.jsonl", "raw_inference_sha256"),
                              ("scored.jsonl", "scored_sha256"), ("summary.json", "summary_sha256")):
            require(sha(folder / filename) == provenance.get(key), f"成果物hash不一致: {folder / filename}")
        recorded_hashes = provenance.get("source_hashes", {})
        require(read_json(folder / "source_hashes.json") == recorded_hashes,
                f"source_hashesと採点provenance不一致: {folder}")
        for path, value in SCORING_HASHES.items():
            require(recorded_hashes.get(path) == value, f"記録された採点コードhash不一致: {folder}: {path}")
        # 評価時のrunner hashは記録するが、後から拡張された現行runnerとの一致は要求しない。
        raw = read_jsonl(folder / "raw_inference.jsonl")
        require(raw and raw[-1].get("kind") == "complete" and raw[-1].get("records") == 872,
                f"生成完了記録不一致: {folder}")
        require(raw[0].get("kind") == "environment" and raw[0].get("config") == config,
                f"生成記録と設定の不一致: {folder}")
        rows = [row for row in raw if row.get("kind") == "inference"]
        scored = read_jsonl(folder / "scored.jsonl")
        validate_record_identity(rows, questions, name)
        validate_record_identity(scored, questions, name)
        for row in scored:
            q = question_map[row["question_id"]]
            require(row.get("ast_id") == q["ast_id"] and type(row.get("passed")) is bool,
                    f"採点ASTまたは合否不一致: {folder}: {q['question_id']}")
        summary = summarize(scored)
        require(summary == read_json(folder / "summary.json") == result["suites"],
                f"問題別・summary・comparisonの集計不一致: {folder}")
        require(result.get("total") == 872 and result.get("passed") == sum(row["passed"] for row in scored),
                f"総合点不一致: {folder}")
        require(read_json(folder / "run_metrics.json") == result, f"run_metrics不一致: {folder}")
        group, label, recovered = classify(spec)
        suites = {key: {**summary[key], "percentage": 100 * summary[key]["passed"] / summary[key]["total"]}
                  for key in PRESENTATION_SUITE_ORDER}
        artifacts = {display_path(folder / filename): sha(folder / filename) for filename in
                     ("config.json", "raw_inference.jsonl", "scored.jsonl", "summary.json",
                      "scoring_provenance.json", "run_metrics.json", "source_hashes.json")}
        models.append({"model": name, "label": label, "group": group, "group_label": GROUPS[group]["label"],
                       "configuration_recovered": recovered, "parameter_count": spec["parameter_count"],
                       "epochs": spec["epochs"], "tokenizer_sha256": tokenizer_sha,
                       "weight_sha256": spec["weight_sha256"], "model_config": spec["model_config"],
                       "architecture_sha256": architecture_identity(spec["model_config"]),
                       "run_root": display_path(root), "model_directory": spec.get("directory"),
                       "passed": result["passed"], "total": 872, "percentage": 100 * result["passed"] / 872,
                       "suites": suites, "metrics": result, "metadata": spec,
                       "artifact_hashes": artifacts, "recorded_source_hashes": recorded_hashes,
                       "question_results": {r["question_id"]: r["passed"] for r in scored},
                       "failure_reasons": dict(Counter(r.get("reason", "unknown") for r in scored if not r["passed"])),
                       "duplicate_evaluations": []})
    run = {"run_root": display_path(root), "completed_at": comparison.get("completed_at"),
           "environment": environment, "model_names": list(root_specs),
           "artifact_hashes": {display_path(root / filename): sha(root / filename) for filename in
                               ("comparison.json", "config.json", "environment.json", "protocol.json")}}
    return models, run


def collect(run_roots: list[Path], expected_model_count: int | None = None) -> dict:
    questions, _, _ = validate_dataset()
    unique, names, runs = {}, {}, []
    for root in run_roots:
        models, run = read_run(root.resolve(), questions)
        runs.append(run)
        for row in models:
            identity = (row["weight_sha256"], row["architecture_sha256"], row["tokenizer_sha256"])
            require(row["model"] not in names or names[row["model"]] == identity,
                    f"同じモデル名で異なる重み・構造・tokenizerがあります: {row['model']}")
            names[row["model"]] = identity
            if identity in unique:
                old = unique[identity]
                require(row["question_results"] == old["question_results"],
                        f"同一モデルの再評価で合否が異なります: {row['model']}")
                old["duplicate_evaluations"].append({"model": row["model"], "run_root": row["run_root"],
                                                      "artifact_hashes": row["artifact_hashes"]})
            else:
                unique[identity] = row
    rows = sorted(unique.values(), key=lambda r: (list(GROUPS).index(r["group"]), -r["parameter_count"],
                                                r["epochs"], r["model"]))
    require(bool(rows), "モデルがありません")
    if expected_model_count is not None:
        require(len(rows) == expected_model_count, f"固有モデル数が不一致: {len(rows)} != {expected_model_count}")
    return {"format_version": 1, "generated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
            "dataset": display_path(DATASET), "questions_sha256": QUESTIONS_SHA256,
            "test_cases_sha256": TEST_CASES_SHA256, "protocol_sha256": PROTOCOL_SHA256,
            "scoring_hashes": SCORING_HASHES, "question_count": 872, "test_case_count": 179,
            "tokenizers": {"standard": TOKENIZER_SHA256, "short": SHORT_TOKENIZER_SHA256},
            "suite_order": PRESENTATION_SUITE_ORDER, "suite_labels": SUITE_LABELS, "suite_counts": SUITE_COUNTS,
            "groups": GROUPS, "model_count": len(rows), "group_counts": dict(Counter(r["group"] for r in rows)),
            "inference_conditions": FIXED_CONFIG, "runs": runs, "models": rows,
            "report_script": {"path": display_path(Path(__file__)), "sha256": sha(Path(__file__))}}


def configure_plotting():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager, pyplot as plt
    font_path = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        family = font_manager.FontProperties(fname=str(font_path)).get_name()
    else:
        family = "Noto Sans CJK JP"
    plt.rcParams.update({"font.family": family, "font.size": 11, "axes.unicode_minus": False,
                         "svg.fonttype": "none", "pdf.fonttype": 42, "savefig.facecolor": "white"})
    return plt


def save_plot(fig, output: Path, stem: str, plt) -> None:
    for extension in ("png", "svg", "pdf"):
        fig.savefig(output / f"{stem}.{extension}", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_all(values: dict, output: Path) -> list[str]:
    import numpy as np
    from matplotlib.patches import Patch
    plt = configure_plotting()
    rows, suites = values["models"], values["suite_order"]
    labels = [f"{SUITE_LABELS[s]}\n(n={SUITE_COUNTS[s]})" for s in suites]
    matrix = np.array([[row["suites"][s]["percentage"] for s in suites] for row in rows])
    fig, ax = plt.subplots(figsize=(17, max(5, len(rows) * .62 + 2.6)))
    heat = ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(suites)), labels, fontsize=10)
    ax.set_yticks(range(len(rows)), [r["label"] for r in rows], fontsize=10)
    ax.tick_params(top=True, labeltop=True, bottom=False, labelbottom=False, length=0, pad=10)
    for index, tick in enumerate(ax.get_yticklabels()):
        tick.set_color(GROUPS[rows[index]["group"]]["color"])
    for i, row in enumerate(rows):
        for j, suite in enumerate(suites):
            item = row["suites"][suite]
            ax.text(j, i, f"{item['passed']}/{item['total']}\n{item['percentage']:.1f}%", ha="center", va="center",
                    color="white" if item["percentage"] >= 58 else "#17212D", fontsize=9)
        if i and rows[i - 1]["group"] != row["group"]:
            ax.axhline(i - .5, color="white", linewidth=3)
    ax.set_title(f"Boku-nano {len(rows)}モデル｜旧872問・カテゴリ別の実行正解率", pad=66, fontsize=17)
    fig.colorbar(heat, ax=ax, fraction=.026, pad=.025, label="実行正解率 (%)")
    fig.text(.02, .015, "各セル: 合格数 / 問題数、正解率。短いBPEは橙色の行名。設定復元は学習manifest未保存の小型loop。\n"
             "同じ問題・採点条件で評価。モデル容量・学習epoch・tokenizerは各行で異なる。CUDA float32 / greedy / 修復なし。",
             fontsize=9, color="#46515E")
    fig.tight_layout(rect=(0, .06, 1, 1))
    save_plot(fig, output, "category_heatmap", plt)

    ranked = sorted(rows, key=lambda r: (-r["passed"], list(GROUPS).index(r["group"]), -r["parameter_count"]))
    fig, ax = plt.subplots(figsize=(14, max(5, len(rows) * .44 + 2.5)))
    y = np.arange(len(ranked))
    bars = ax.barh(y, [r["percentage"] for r in ranked], color=[GROUPS[r["group"]]["color"] for r in ranked], height=.65)
    for bar, row in zip(bars, ranked):
        if row["group"] == "short":
            bar.set_hatch("//")
            bar.set_edgecolor("white")
        ax.text(row["percentage"] + .8, bar.get_y() + bar.get_height() / 2,
                f"{row['passed']}/872  ({row['percentage']:.2f}%)", va="center", fontsize=10)
    ax.set_yticks(y, [r["label"] for r in ranked])
    ax.invert_yaxis()
    ax.set_xlim(0, 114)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("実行正解率 (%)：872問を合算したmicro平均")
    fig.suptitle(f"Boku-nano {len(rows)}モデル｜旧872問の総合結果", x=.02, y=.99, ha="left", fontsize=16)
    ax.grid(axis="x", color="#D9DEE5", alpha=.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    present = [group for group in GROUPS if any(r["group"] == group for r in rows)]
    fig.legend(handles=[Patch(facecolor=GROUPS[g]["color"], label=GROUPS[g]["label"], hatch="//" if g == "short" else "")
                        for g in present], loc="upper left", bbox_to_anchor=(.23, .94), ncol=2, frameon=False, fontsize=9)
    fig.text(.02, .01, "短いBPEは斜線。小型Loopedの［設定復元］は既存重みを使用。容量・epochの異なる比較であり、構造だけの因果比較ではない。",
             fontsize=9, color="#46515E")
    fig.tight_layout(rect=(0, .04, 1, .84))
    save_plot(fig, output, "overall_pass_rate", plt)
    stems = ["category_heatmap", "overall_pass_rate"]

    palettes = {"standard": ["#173F5F", "#20639B", "#3C8DAD", "#56A8BD", "#84C5D0", "#AEDCE2"],
                "short": ["#9D4D12", "#C8781B", "#DF9F37", "#ECC368"],
                "ablation": ["#245B48", "#3D8362", "#6AA883", "#9DCAA4"],
                "looped": ["#523A75", "#79539B", "#9E7AB5", "#B9A0CE"]}
    for group in present:
        subset = [r for r in rows if r["group"] == group]
        fig, ax = plt.subplots(figsize=(16, max(8.2, 9 * len(subset) * .19 + 2.2)))
        height = .78 / len(subset)
        centers = np.arange(len(suites))
        for index, row in enumerate(subset):
            positions = centers - .39 + height * (index + .5)
            rates = [row["suites"][suite]["percentage"] for suite in suites]
            bars = ax.barh(positions, rates, height=height * .91, label=row["label"],
                           color=palettes[group][index % len(palettes[group])],
                           hatch="//" if group == "short" else None, edgecolor="white", linewidth=.3)
            for bar, suite in zip(bars, suites):
                item = row["suites"][suite]
                ax.text(item["percentage"] + .65, bar.get_y() + bar.get_height() / 2,
                        f"{item['passed']}/{item['total']}", va="center", fontsize=8)
        ax.set_yticks(centers, labels, fontsize=10)
        ax.invert_yaxis()
        ax.set_xlim(0, 113)
        ax.set_xticks(range(0, 101, 20))
        ax.set_xlabel("実行正解率 (%)　棒の右端は合格数 / 問題数")
        ax.grid(axis="x", color="#D9DEE5", alpha=.8)
        ax.set_axisbelow(True)
        for edge in ("top", "right", "left"):
            ax.spines[edge].set_visible(False)
        fig.text(.02, .99, f"{GROUPS[group]['label']}｜旧872問・9カテゴリ", ha="left", va="top", fontsize=16)
        handles, legend_labels = ax.get_legend_handles_labels()
        fig.legend(handles, legend_labels, loc="upper left", bbox_to_anchor=(.14, .95),
                   ncol=2, frameon=False, fontsize=9)
        note = ("短いBPE（minfreq2 / maxlen8）。標準BPEと同じ問題だが、入力・出力のtoken分割は異なる。"
                if group == "short" else "固定された旧872問 / 179検査入力。CUDA float32 / greedy / context 256 / 修復なし。")
        if any(r["configuration_recovered"] for r in subset):
            note += " ［設定復元］: 報告書と重みから評価用設定を復元。再学習はしていない。"
        fig.text(.02, .01, note, fontsize=9, color="#46515E")
        fig.tight_layout(rect=(0, .04, 1, .88))
        stem = f"categories_{group}"
        save_plot(fig, output, stem, plt)
        stems.append(stem)
    return stems


def markdown(values: dict, stems: list[str]) -> str:
    rows = values["models"]
    suites = values["suite_order"]
    lines = ["# Boku-nano：旧872問のCUDAバッチ評価", "", f"生成日時: {values['generated_at']}。固有モデル数: {len(rows)}。", "",
             "旧872問・9カテゴリ・179検査入力を固定し、保存済みCUDA float32のgreedy生成を集計した。履歴・修復なし、context 256。",
             "モデル容量・訓練epoch・tokenizerが異なるため、総合順位だけでloopやtokenizerの因果効果は判断しない。",
             "短いBPEは別群として表示する。［設定復元］は、元の学習manifestが保存されていない既存重みに評価用設定を復元したことを示す。", "",
             "## 総合結果", "", "| モデル | 群 | パラメータ数 | epoch | 合格 / 872 | 正解率 |",
             "|---|---|---:|---:|---:|---:|"]
    for row in sorted(rows, key=lambda r: -r["passed"]):
        lines.append(f"| {row['model']} ({row['label']}) | {row['group_label']} | {row['parameter_count']:,} | "
                     f"{row['epochs']} | {row['passed']}/872 | {row['percentage']:.4f}% |")
    lines.extend(["", "## カテゴリ別の合格数と正解率", "",
                  "| モデル | " + " | ".join(SUITE_LABELS[s] for s in suites) + " |",
                  "|---|" + "---:|" * len(suites)])
    for row in rows:
        cells = [f"{row['suites'][s]['passed']}/{row['suites'][s]['total']} ({row['suites'][s]['percentage']:.2f}%)"
                 for s in suites]
        lines.append(f"| {row['model']} | " + " | ".join(cells) + " |")
    lines.extend(["", "## 図", ""])
    for stem in stems:
        lines.append(f"- [{stem}: PNG]({stem}.png) / [SVG]({stem}.svg) / [PDF]({stem}.pdf)")
    lines.extend(["", "## 検証と再現性", "",
                  "各runのcompleted状態、問題・採点器hash、raw/scored/summaryの保存hash、872問のID・AST・カテゴリ、問題別合否からの再集計を検証した。",
                  "同一重み・構造・tokenizerの重複評価は問題別合否が一致する場合だけ統合した。異なる評価時点のrunner hashは保存し、現行ファイルとの一致は要求しない。",
                  "全モデルの設定・runパス・入力成果物hash・評価当時のsource hash・問題別合否・失敗理由は[values.json](values.json)に保存している。", "",
                  "| 固定入力 | SHA-256 |", "|---|---|",
                  f"| questions.jsonl | `{QUESTIONS_SHA256}` |", f"| test_cases.json | `{TEST_CASES_SHA256}` |",
                  f"| protocol.json | `{PROTOCOL_SHA256}` |", f"| 標準BPE | `{TOKENIZER_SHA256}` |",
                  f"| 短いBPE | `{SHORT_TOKENIZER_SHA256}` |", "",
                  "| run | 完了日時 | comparison.json SHA-256 |", "|---|---|---|"])
    for run in values["runs"]:
        path = run["run_root"] + "/comparison.json"
        lines.append(f"| `{run['run_root']}` | {run['completed_at']} | `{run['artifact_hashes'][path]}` |")
    lines.extend(["", "| モデル | 重みSHA-256 | run |", "|---|---|---|"])
    for row in rows:
        lines.append(f"| {row['model']} | `{row['weight_sha256']}` | `{row['run_root']}` |")
    lines.extend(["", "### 解釈上の範囲", "",
                  "- 正解率は固定問題に対する実行評価。訓練データの成績や通常の84,550件評価とは別の指標。",
                  "- 時間はrun_metricsに記録された推論区間の測定値で、採点・重み読込・訓練時間を含まない。",
                  "- 単一checkpointの比較であり、複数seedの平均・信頼区間ではない。", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-roots", nargs="+", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path,
                        default=ROOT / "docs/results/figures/composition872_cuda_20261025")
    parser.add_argument("--expected-model-count", type=int, help="統合後の固有モデル数。全件版では18を指定")
    args = parser.parse_args(argv)
    if args.expected_model_count is not None and args.expected_model_count <= 0:
        parser.error("--expected-model-countは正整数にしてください")
    output = args.output_directory.resolve()
    if output.exists():
        parser.error("既存出力は上書きしません。新しい--output-directoryを指定してください")
    values = collect([resolve_path(p) for p in args.run_roots], args.expected_model_count)
    output.mkdir(parents=True, exist_ok=False)
    stems = plot_all(values, output)
    values["figures"] = {stem: {ext: sha(output / f"{stem}.{ext}") for ext in ("png", "svg", "pdf")} for stem in stems}
    write_json(output / "values.json", values)
    (output / "summary.md").write_text(markdown(values, stems), encoding="utf-8")
    print(json.dumps({"status": "completed", "model_count": values["model_count"], "group_counts": values["group_counts"],
                      "output_directory": display_path(output), "figures": stems}, ensure_ascii=False))


if __name__ == "__main__":
    main()
