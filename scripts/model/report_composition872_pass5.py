#!/usr/bin/env python3
"""実測したgreedy1＋sampling4のpass@1/pass@5を、旧872問の9カテゴリで作図する。"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.model import report_composition872_cuda as greedy_report  # noqa: E402
from scripts.model.evaluate_boku_composition_torch import (  # noqa: E402
    QUESTIONS_SHA256, TEST_CASES_SHA256, SCORING_HASHES, SUITE_COUNTS, display_path,
    read_json, read_jsonl, resolve_path, sha, validate_dataset, write_json,
)

SUITES = greedy_report.PRESENTATION_SUITE_ORDER
SUITE_LABELS = greedy_report.SUITE_LABELS
GROUPS = greedy_report.GROUPS
DEFAULT_GREEDY_ROOTS = [
    ROOT / "data/evaluations/composition872_cuda_20261025_baselines",
    ROOT / "data/evaluations/composition872_cuda_20261025_standard_extra",
    ROOT / "data/evaluations/composition872_cuda_20261025_short_bpe",
    ROOT / "data/evaluations/composition872_cuda_20261025_small_loops",
]
SAMPLING_CONDITIONS = {
    "candidate_count": 5,
    "sampling_candidates": 4,
    "pass_at_1_definition": "existing_greedy",
    "pass_at_5_definition": "any_of_greedy_1_and_top_p_4",
    "temperature": 0.8,
    "top_p": 0.95,
}
PALETTE = ["#2878B5", "#E07B39", "#3A936F", "#B65368", "#8263A6", "#8B6D48"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def aggregate(rows: list[dict]) -> dict:
    total = len(rows)
    require(total > 0, "集計対象が空です")
    pass1 = sum(row["pass_at_1"] for row in rows)
    pass5 = sum(row["pass_at_5"] for row in rows)
    require(pass5 >= pass1, "pass@5がpass@1を下回っています")
    return {"total": total, "pass_at_1_count": pass1, "pass_at_5_count": pass5,
            "pass_at_1": pass1 / total, "pass_at_5": pass5 / total,
            "pass_at_1_percentage": 100 * pass1 / total,
            "pass_at_5_percentage": 100 * pass5 / total,
            "additional_pass_count": pass5 - pass1,
            "gain_percentage_points": 100 * (pass5 - pass1) / total}


def verify_aggregate(actual: dict, recorded: dict, where: str) -> None:
    for key in ("total", "pass_at_1_count", "pass_at_5_count"):
        require(type(recorded.get(key)) is int and recorded[key] == actual[key],
                f"問題別結果と記録済み集計が不一致です: {where}: {key}")
    for key in ("pass_at_1", "pass_at_5"):
        value = recorded.get(key)
        require(type(value) in (int, float) and math.isclose(value, actual[key], rel_tol=0, abs_tol=1e-12),
                f"問題別結果と記録済み正解率が不一致です: {where}: {key}")


def validate_question_rows(rows: list[dict], questions: list[dict], greedy: dict, name: str) -> None:
    question_map = {question["question_id"]: question for question in questions}
    require(len(rows) == 872 and len({r["question_id"] for r in rows}) == 872
            and {r["question_id"] for r in rows} == set(question_map),
            f"872問の欠落・重複・別問題があります: {name}")
    for row in rows:
        qid = row["question_id"]
        question = question_map[qid]
        require(all(row.get(key) == question[key] for key in ("suite", "category_id", "ast_id")),
                f"問題カテゴリ・ASTが不一致です: {name}: {qid}")
        require(type(row.get("pass_at_1")) is bool and type(row.get("pass_at_5")) is bool,
                f"pass@1/pass@5は問題別のboolである必要があります: {name}: {qid}")
        require(row["pass_at_1"] == greedy[qid], f"既存greedyの合否と異なります: {name}: {qid}")
        candidates = row.get("candidates", [])
        require(len(candidates) == 5 and [c.get("candidate_index") for c in candidates] == list(range(1, 6)),
                f"候補1～5が揃っていません: {name}: {qid}")
        require(candidates[0].get("decoding") == "greedy"
                and all(c.get("decoding") == "top_p" for c in candidates[1:]),
                f"greedy1＋top-p4の条件ではありません: {name}: {qid}")
        require(all(type(c.get("passed")) is bool for c in candidates),
                f"候補ごとの合否がboolではありません: {name}: {qid}")
        count = sum(c["passed"] for c in candidates)
        require(type(row.get("passed_count")) is int and row["passed_count"] == count
                and row["pass_at_1"] == candidates[0]["passed"]
                and row["pass_at_5"] == any(c["passed"] for c in candidates),
                f"候補別合否とpass@1/pass@5が一致しません: {name}: {qid}")
        require(not row["pass_at_1"] or row["pass_at_5"],
                f"greedy成功がpass@5から欠落しています: {name}: {qid}")
    require(Counter(row["suite"] for row in rows) == SUITE_COUNTS,
            f"9カテゴリの件数が不一致です: {name}")


def collect(root: Path, greedy_roots: list[Path], expected_model_count: int = 18) -> dict:
    root = root.resolve()
    baseline = greedy_report.collect([p.resolve() for p in greedy_roots], expected_model_count)
    questions, _, _ = validate_dataset()
    comparison = read_json(root / "comparison.json")
    config = read_json(root / "config.json")
    require(comparison.get("status") == "completed", f"未完了のpass@5 runです: {root}")
    require(comparison.get("config_sha256") == sha(root / "config.json"),
            "完了集計が記録したroot設定hashが一致しません")
    require(comparison.get("questions_sha256") == QUESTIONS_SHA256
            and comparison.get("test_cases_sha256") == TEST_CASES_SHA256,
            f"固定された旧872問・179入力ではありません: {root}")
    require(config.get("questions_sha256") == QUESTIONS_SHA256
            and config.get("test_cases_sha256") == TEST_CASES_SHA256,
            "sampling設定の問題・検査入力hashが一致しません")
    for key, expected in SAMPLING_CONDITIONS.items():
        require(config.get(key) == expected, f"sampling条件が一致しません: {key}")
    require(type(config.get("sampling_seed")) is int, "sampling seedの記録がありません")
    recorded_models = comparison.get("models", [])
    require(len(recorded_models) == expected_model_count
            and len({r["model"] for r in recorded_models}) == expected_model_count,
            "pass@5の対象モデル数または一意性が不正です")
    recorded = {r["model"]: r for r in recorded_models}
    require(set(recorded) == {r["model"] for r in baseline["models"]},
            "greedyとpass@5のモデル集合が異なります")
    specs = config.get("models", [])
    require(len(specs) == expected_model_count and len({s["name"] for s in specs}) == expected_model_count,
            "sampling設定のモデル一覧が不正です")
    spec_map = {s["name"]: s for s in specs}
    require(set(spec_map) == set(recorded), "sampling設定と集計のモデル一覧が異なります")
    rows = []
    for original in baseline["models"]:
        name = original["model"]
        folder = root / name
        require(spec_map[name] == original["metadata"], f"元greedyとsamplingのモデル設定が異なります: {name}")
        model_config = read_json(folder / "config.json")
        require(all(model_config.get(key) == value for key, value in config.items() if key != "models"),
                f"モデル別設定がrootの共通条件と異なります: {name}")
        require(model_config.get("model") == name and model_config.get("model_metadata") == spec_map[name]
                and model_config.get("weight_sha256") == original["weight_sha256"]
                and model_config.get("tokenizer_sha256") == original["tokenizer_sha256"],
                f"モデル別sampling設定とroot/元greedyのmetadataが異なります: {name}")
        for key, expected in SAMPLING_CONDITIONS.items():
            require(model_config.get(key) == expected, f"モデル別sampling条件が異なります: {name}: {key}")
        require(model_config.get("sampling_seed") == config["sampling_seed"],
                f"モデル別sampling seedが異なります: {name}")
        require(model_config.get("greedy_run_root") == original["run_root"]
                and model_config.get("greedy_artifact_hashes") == original["artifact_hashes"],
                f"モデル別設定が別の元greedy成果物を参照しています: {name}")
        provenance = read_json(folder / "provenance.json")
        expected_provenance = {
            "status": "completed", "questions_sha256": QUESTIONS_SHA256,
            "test_cases_sha256": TEST_CASES_SHA256,
            "scorer_sha256": SCORING_HASHES["scripts/model/score_composition_suite.py"],
            "common_sha256": SCORING_HASHES["scripts/model/composition_suite_common.py"],
            "config_sha256": sha(folder / "config.json"),
        }
        require(all(provenance.get(key) == expected for key, expected in expected_provenance.items()),
                f"採点provenanceが一致しません: {name}")
        require(provenance.get("greedy_artifact_hashes") == original["artifact_hashes"],
                f"provenanceが別の元greedy成果物を参照しています: {name}")
        for path, expected in SCORING_HASHES.items():
            require(provenance.get("source_hashes", {}).get(path) == expected,
                    f"記録された採点コードhashが異なります: {name}: {path}")
        artifact_hashes = provenance.get("artifact_hashes", {})
        for filename in ("raw_inference.jsonl", "scored.jsonl", "question_results.jsonl", "summary.json",
                         "generation_manifest.json", "scoring_progress.json"):
            require(sha(folder / filename) == artifact_hashes.get(filename),
                    f"sampling成果物のhashが一致しません: {name}/{filename}")
        for path, expected in provenance.get("greedy_artifact_hashes", {}).items():
            require(sha(resolve_path(path)) == expected, f"元greedy成果物のhashが一致しません: {path}")
        question_path = folder / "question_results.jsonl"
        results = read_jsonl(question_path)
        validate_question_rows(results, questions, original["question_results"], name)
        expected_pairs = {(r["question_id"], index) for r in results for index in range(1, 6)}
        scored = read_jsonl(folder / "scored.jsonl")
        raw = read_jsonl(folder / "raw_inference.jsonl")
        for candidate_rows, label in ((scored, "scored"), (raw, "raw")):
            require(len(candidate_rows) == 4360
                    and {(r["question_id"], r["candidate_index"]) for r in candidate_rows} == expected_pairs,
                    f"5候補×872問の{label}記録が揃っていません: {name}")
        scored_map = {(r["question_id"], r["candidate_index"]): r for r in scored}
        for result in results:
            for candidate in result["candidates"]:
                entry = scored_map[(result["question_id"], candidate["candidate_index"])]
                require(type(entry.get("passed")) is bool and entry["passed"] == candidate["passed"]
                        and all(entry.get(key) == result[key] for key in ("suite", "category_id", "ast_id")),
                        f"候補別scoredと問題集計が不一致です: {name}: {result['question_id']}")
        totals = aggregate(results)
        suites = {suite: aggregate([r for r in results if r["suite"] == suite]) for suite in SUITES}
        verify_aggregate(totals, recorded[name], name)
        require(set(recorded[name].get("suites", {})) == set(SUITES),
                f"記録済み集計に9カテゴリが揃っていません: {name}")
        for suite in SUITES:
            verify_aggregate(suites[suite], recorded[name]["suites"][suite], f"{name}/{suite}")
        artifacts = {display_path(p): sha(p) for p in folder.iterdir() if p.is_file()}
        row = {key: original[key] for key in
               ("model", "label", "group", "group_label", "configuration_recovered", "parameter_count",
                "epochs", "tokenizer_sha256", "weight_sha256", "model_config", "architecture_sha256",
                "model_directory", "metadata")}
        row.update(totals)
        row.update(suites=suites, greedy_run_root=original["run_root"],
                   pass5_run_root=display_path(root), artifact_hashes=artifacts,
                   recorded_source_hashes=provenance.get("source_hashes", {}),
                   greedy_artifact_hashes=original["artifact_hashes"],
                   question_results={r["question_id"]: {
                       "pass_at_1": r["pass_at_1"], "pass_at_5": r["pass_at_5"],
                       "passed_count": r["passed_count"],
                   } for r in results})
        rows.append(row)
    return {
        "format_version": 1, "generated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
        "dataset": baseline["dataset"], "questions_sha256": QUESTIONS_SHA256,
        "test_cases_sha256": TEST_CASES_SHA256, "protocol_sha256": baseline["protocol_sha256"],
        "question_count": 872, "test_case_count": 179,
        "suite_order": SUITES, "suite_labels": SUITE_LABELS, "suite_counts": SUITE_COUNTS,
        "groups": GROUPS, "model_count": len(rows),
        "group_counts": dict(Counter(r["group"] for r in rows)),
        "sampling_conditions": {**SAMPLING_CONDITIONS, "sampling_seed": config["sampling_seed"]},
        "metric_note": "Empirical success among one fixed greedy candidate plus four sampled candidates; not an iid pass@k estimator. The same greedy candidate defines pass@1 and belongs to pass@5.",
        "greedy_runs": baseline["runs"], "pass5_run_root": display_path(root),
        "sampling_config": config, "completed_at": comparison.get("completed_at"),
        "source_hashes": {display_path(root / filename): sha(root / filename)
                          for filename in ("comparison.json", "config.json")},
        "report_script": {"path": display_path(Path(__file__)), "sha256": sha(Path(__file__))},
        "models": rows,
    }


def save_plot(fig, output: Path, stem: str, plt) -> None:
    for extension in ("png", "svg", "pdf"):
        fig.savefig(output / f"{stem}.{extension}", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_all(values: dict, output: Path) -> list[str]:
    import numpy as np
    from matplotlib.patches import Patch
    plt = greedy_report.configure_plotting()
    models = values["models"]
    labels = [f"{SUITE_LABELS[s]}\n(n={SUITE_COUNTS[s]})" for s in SUITES]
    stems = []
    for group in GROUPS:
        subset = [r for r in models if r["group"] == group]
        if not subset:
            continue
        fig, axes = plt.subplots(2, 1, figsize=(20, 13))
        centers = np.arange(len(SUITES))
        width = .82 / len(subset)
        for axis, metric, title in zip(axes, ("pass_at_1", "pass_at_5"),
                                      ("pass@1 — greedy 1候補", "pass@5 — greedy 1候補＋sampling 4候補")):
            for index, model in enumerate(subset):
                positions = centers - .41 + width * (index + .5)
                rates = [model["suites"][s][f"{metric}_percentage"] for s in SUITES]
                bars = axis.bar(positions, rates, width=width * .94,
                                color=PALETTE[index % len(PALETTE)], edgecolor="white", linewidth=.3)
                for bar, suite in zip(bars, SUITES):
                    percentage = model["suites"][suite][f"{metric}_percentage"]
                    label = str(int(percentage)) if percentage in (0, 100) else f"{percentage:.1f}"
                    axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.1,
                              label, ha="center", va="bottom", fontsize=8,
                              rotation=90 if len(subset) > 4 else 0)
            axis.set_ylim(0, 111)
            axis.set_yticks(range(0, 101, 20))
            axis.set_xticks(centers, labels, fontsize=10)
            axis.set_ylabel("実行正解率 (%)")
            axis.set_title(title, loc="left", fontsize=15, pad=12)
            axis.grid(axis="y", color="#DCE2E8", linewidth=.65)
            axis.set_axisbelow(True)
            axis.spines[["top", "right"]].set_visible(False)
        fig.suptitle(f"{GROUPS[group]['label']}｜旧872問・9カテゴリのpass@1 / pass@5",
                     x=.035, y=.985, ha="left", fontsize=19)
        fig.legend(handles=[Patch(facecolor=PALETTE[i % len(PALETTE)], label=row["label"])
                            for i, row in enumerate(subset)], loc="upper left", bbox_to_anchor=(.04, .947),
                   ncol=3 if len(subset) > 4 else 2, frameon=False, fontsize=11)
        fig.text(.04, .027,
                 "棒の数値は正解率(%)。pass@5は同じgreedy候補を必ず含み、計5候補の少なくとも1つが全179入力で正解なら合格。\n"
                 "sampling: temperature=0.8 / top-p=0.95。全9カテゴリを実測。seed固定の1組の結果で、訓練能力の因果比較ではない。",
                 fontsize=10, color="#46515E")
        fig.subplots_adjust(left=.055, right=.99, top=.85, bottom=.11, hspace=.32)
        stem = f"categories_{group}"
        save_plot(fig, output, stem, plt)
        stems.append(stem)

    # 全18モデルのセル文字を保つため、18列幅にせず9列の図を上下に配置する。
    fig, axes = plt.subplots(2, 1, figsize=(17, max(16, len(models) * 1.0 + 6)),
                             gridspec_kw={"hspace": .28})
    for axis, metric, title in zip(axes, ("pass_at_1", "pass_at_5"),
                                  ("pass@1：greedy 1候補", "pass@5：greedy 1＋sampling 4候補")):
        matrix = np.array([[m["suites"][s][f"{metric}_percentage"] for s in SUITES] for m in models])
        heat = axis.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=100, aspect="auto")
        axis.set_xticks(range(len(SUITES)), labels, fontsize=10)
        axis.set_yticks(range(len(models)), [m["label"] for m in models])
        axis.tick_params(top=True, labeltop=True, bottom=False, labelbottom=False, length=0, pad=8)
        axis.set_title(title, fontsize=18, pad=65)
        for i, model in enumerate(models):
            for j, suite in enumerate(SUITES):
                cell = model["suites"][suite]
                percent = cell[f"{metric}_percentage"]
                axis.text(j, i, f"{cell[f'{metric}_count']}/{cell['total']}\n{percent:.1f}%",
                          ha="center", va="center", fontsize=10,
                          color="white" if percent >= 58 else "#17212D")
            if i and models[i - 1]["group"] != model["group"]:
                axis.axhline(i - .5, color="white", linewidth=3)
        for tick, model in zip(axis.get_yticklabels(), models):
            tick.set_color(GROUPS[model["group"]]["color"])
            tick.set_fontsize(10)
    fig.subplots_adjust(left=.235, right=.93, top=.91, bottom=.055)
    colorbar = fig.add_axes([.948, .19, .012, .59])
    fig.colorbar(heat, cax=colorbar, label="実行正解率 (%)")
    fig.suptitle(f"Boku-nano {len(models)}モデル｜同じ旧872問のpass@1 / pass@5", x=.02, y=.985,
                 ha="left", fontsize=21)
    fig.text(.02, .025,
             "各セル: 合格問題数 / カテゴリ問題数、正解率。上下は同じモデル・同じ問題。列順は発表資料の9カテゴリ。\n"
             "pass@5 = greedy 1＋sampling 4 (temperature 0.8, top-p 0.95)。追加推論予算を含む実測値。［設定復元］は既存重みを使用。",
             fontsize=11, color="#46515E")
    save_plot(fig, output, "category_heatmaps_pass1_pass5", plt)
    stems.append("category_heatmaps_pass1_pass5")
    return stems


def markdown(values: dict, stems: list[str]) -> str:
    rows = values["models"]
    lines = ["# 旧872問：カテゴリ別pass@1 / pass@5", "",
             f"作成日時: {values['generated_at']}。全{len(rows)}モデル、全872問・9カテゴリ。", "",
             "pass@1は保存済みのgreedy 1候補、pass@5は同じgreedy候補と新たに生成したsampling 4候補の計5候補のうち、"
             "少なくとも1候補が179検査入力・契約検査を全て通った問題の割合。samplingはtemperature=0.8、top-p=0.95。", "",
             "同一分布から独立に5回生成した場合のpass@k推定値ではなく、greedyを含む候補集合の実測成功率である。"
             "候補数が増えるためpass@5はpass@1以上になる。改善は追加推論・検査予算の効果を含み、再学習の効果ではない。", "",
             f"sampling seed: `{values['sampling_conditions']['sampling_seed']}`。複数seedの平均・信頼区間ではない。", "",
             "## 総合", "", "| モデル | 系列 | pass@1 | pass@5 | 追加合格 | 差 (pt) |",
             "|---|---|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['model']} | {row['group_label']} | "
                     f"{row['pass_at_1_count']}/872 ({row['pass_at_1_percentage']:.2f}%) | "
                     f"{row['pass_at_5_count']}/872 ({row['pass_at_5_percentage']:.2f}%) | "
                     f"+{row['additional_pass_count']} | +{row['gain_percentage_points']:.2f} |")
    for metric in ("pass_at_1", "pass_at_5"):
        lines.extend(["", f"## カテゴリ別{metric.replace('pass_at_', 'pass@')}", "",
                      "| モデル | " + " | ".join(SUITE_LABELS[s] for s in SUITES) + " |",
                      "|---|" + "---:|" * len(SUITES)])
        for row in rows:
            cells = [f"{row['suites'][s][metric + '_count']}/{row['suites'][s]['total']} "
                     f"({row['suites'][s][metric + '_percentage']:.2f}%)" for s in SUITES]
            lines.append(f"| {row['model']} | " + " | ".join(cells) + " |")
    lines.extend(["", "## 図", ""])
    for stem in stems:
        lines.append(f"- [{stem}: PNG]({stem}.png) / [SVG]({stem}.svg) / [PDF]({stem}.pdf)")
    lines.extend(["", "## 来歴と検証", "",
                  "全872問のID・カテゴリ・AST、5候補の順序・合否、pass@1と元greedyの問題別一致、"
                  "pass@5が候補合否の論理和であること、9カテゴリと全体の記録済み集計との一致を検証した。", "",
                  "モデル容量・epoch・tokenizerは異なる。標準BPE6、短いBPE4、構造比較4、小型loop4を分けて表示する。"
                  "小型loopの［設定復元］は元学習manifestが欠けた既存重みに対する評価用設定であり、新規訓練ではない。", "",
                  f"- questions SHA-256: `{QUESTIONS_SHA256}`",
                  f"- test_cases SHA-256: `{TEST_CASES_SHA256}`",
                  f"- 実測run: `{values['pass5_run_root']}`",
                  "- 全モデルの設定、元greedy入力、sampling条件、成果物hash、問題別合否: [values.json](values.json)", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path,
                        default=ROOT / "data/evaluations/composition872_pass5_cuda_20261025")
    parser.add_argument("--greedy-run-roots", type=Path, nargs="+", default=DEFAULT_GREEDY_ROOTS)
    parser.add_argument("--output-directory", type=Path,
                        default=ROOT / "docs/results/figures/composition872_pass5_cuda_20261025")
    parser.add_argument("--expected-model-count", type=int, default=18)
    args = parser.parse_args(argv)
    if args.expected_model_count <= 0:
        parser.error("--expected-model-countは正整数にしてください")
    output = args.output_directory.resolve()
    if output.exists() or output.is_symlink():
        parser.error("既存出力は上書きしません。未使用の--output-directoryを指定してください")
    values = collect(resolve_path(args.run_root), [resolve_path(p) for p in args.greedy_run_roots],
                     args.expected_model_count)
    output.mkdir(parents=True, exist_ok=False)
    stems = plot_all(values, output)
    values["figures"] = {stem: {ext: sha(output / f"{stem}.{ext}") for ext in ("png", "svg", "pdf")}
                         for stem in stems}
    write_json(output / "values.json", values)
    (output / "summary.md").write_text(markdown(values, stems), encoding="utf-8")
    print(json.dumps({"status": "completed", "model_count": values["model_count"],
                      "group_counts": values["group_counts"], "output_directory": display_path(output),
                      "figures": stems}, ensure_ascii=False))


if __name__ == "__main__":
    main()
