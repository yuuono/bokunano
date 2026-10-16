"""1Mの反復と小型化について、loopモデルと通常モデルの比較設定を作る。"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM  # noqa: E402

# d_model, d_ff, heads, unique layers, loops, embedding tying, input mode
VARIANTS = {
    "u3": (128, 256, 4, 3, 1, False, "none"),
    # 既存1Mの3つの独立blockを保持し、層群全体だけを反復する
    "u3_r2": (128, 256, 4, 3, 2, False, "none"),
    "u3_r3": (128, 256, 4, 3, 3, False, "none"),
    "u3_r6": (128, 256, 4, 3, 6, False, "none"),
    "u2": (128, 256, 4, 2, 1, False, "none"),
    "u1": (128, 256, 4, 1, 1, False, "none"),
    "l1": (128, 256, 4, 1, 3, False, "none"),
    "l1_add": (128, 256, 4, 1, 3, False, "add"),
    "t3": (128, 256, 4, 3, 1, True, "none"),
    "t2": (128, 256, 4, 2, 1, True, "none"),
    "t1": (128, 256, 4, 1, 1, True, "none"),
    "lt1": (128, 256, 4, 1, 3, True, "none"),
    "lt1_add": (128, 256, 4, 1, 3, True, "add"),
    "lt2": (128, 256, 4, 2, 2, True, "none"),
    "f128": (128, 128, 4, 1, 3, True, "none"),
    "f128_plain": (128, 128, 4, 1, 1, True, "none"),
    "w96": (96, 192, 3, 1, 3, True, "none"),
    "w96_plain": (96, 192, 3, 1, 1, True, "none"),
    "w64": (64, 128, 2, 1, 3, True, "none"),
    "w64_plain": (64, 128, 2, 1, 1, True, "none"),
    "w64_r2": (64, 128, 2, 1, 2, True, "none"),
    "w64_r6": (64, 128, 2, 1, 6, True, "none"),
}
BASE_COMPARISON = ["u3", "u2", "u1", "l1", "t3", "t1", "lt1", "l1_add", "lt1_add"]
# 1epochの主比較は通常3層と、同じ3層を2周・3周させたモデル
ONE_M_COMPARISON = ["u3", "u3_r2", "u3_r3"]


def architecture(variant: str) -> dict:
    d, f, heads, layers, loops, tied, mode = VARIANTS[variant]
    return dict(d_model=d, d_ff=f, n_heads=heads, n_layers=layers,
                n_loops=loops, tie_word_embeddings=tied, loop_input_mode=mode)


def parameter_count(config: BokuNanoConfig) -> int:
    d, f, v = config.d_model, config.d_ff, config.vocab_size
    return (1 if config.tie_word_embeddings else 2) * v * d + config.n_layers * (
        4 * d * d + 3 * d * f + 2 * d
    ) + d


def build_configs(base: dict, evaluation_base: dict, variant: str, folder: Path,
                  seed: int, epochs: int) -> tuple[dict, dict]:
    """学習と評価のparameter期待値・出力先を一緒に決める。"""
    config = deepcopy(base)
    config["model"].update(architecture(variant))
    model_config = BokuNanoConfig.from_dict(config["model"])
    expected = parameter_count(model_config)
    actual = BokuNanoForCausalLM(model_config).parameter_count()
    if actual != expected:
        raise ValueError(f"parameter数が式と一致しません: {variant}: {actual} != {expected}")
    config["model_validation"]["expected_parameter_count"] = actual
    config["training"].update(epochs=epochs, seed=seed)
    config["output"]["directory"] = str(folder / "model")
    evaluation = deepcopy(evaluation_base)
    evaluation["model"].update(directory=str(folder / "model"), expected_parameter_count=actual)
    evaluation["output"]["directory"] = str(folder / "evaluation")
    return config, evaluation


def write_comparison(output: Path, jobs: list) -> dict:
    """全5集合の完了を確認して、通常3層との差を集計する。"""
    # 部分評価を正式な比較へ混ぜないよう、全モデルのmanifestを検査する
    rows = []
    for folder, _, evaluation, job in jobs:
        # 評価スクリプトが保存した件数と合格数を正本にする
        manifest = json.loads((folder / "evaluation/evaluation_manifest.json").read_text())
        suites = manifest["suites"]
        if set(suites) != set(evaluation["evaluation_data"]["suites"]):
            raise ValueError(f"全5集合の評価が必要です: {job['variant']}")
        for name, suite in suites.items():
            expected = evaluation["evaluation_data"]["suites"][name]["expected_record_count"]
            if suite["status"] != "completed" or suite["evaluated_record_count"] != expected:
                raise ValueError(f"未完了の評価です: {job['variant']}/{name}")
        # 集合サイズで重み付けした全体正解率を計算する
        total = sum(s["evaluated_record_count"] for s in suites.values())
        passed = sum(s["passed_record_count"] for s in suites.values())
        rows.append({"variant": job["variant"], "parameter_count": job["parameter_count"],
                     "effective_layers": job["effective_layers"], "passed": passed,
                     "total": total, "pass_rate": passed / total, "suites": suites})
    # 今回一緒に学習した通常3層がある場合だけ差を算出する
    baseline = next((r for r in rows if r["variant"] == "u3"), None)
    for row in rows:
        row["delta_vs_u3_percentage_points"] = (
            100 * (row["pass_rate"] - baseline["pass_rate"]) if baseline else None
        )
    # 小さい言い換え集合が全体平均に埋もれないようsuite別値も残す
    comparison = {"baseline": "u3" if baseline else None, "models": rows}
    (output / "comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return comparison


def main(default_variants: list[str] | None = None, default_epochs: int = 3,
         allowed_variants: list[str] | None = None, description: str | None = None) -> None:
    # 専用入口から既定の構成・epochだけを変え、実行処理は共用する
    parser = argparse.ArgumentParser(description=description or __doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--variants", nargs="+", choices=allowed_variants or VARIANTS,
                        default=default_variants or BASE_COMPARISON)
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--epochs", type=int, default=default_epochs)
    parser.add_argument("--device", default="auto", help="autoはCUDAがなければCPU")
    parser.add_argument("--dtype", choices=["float32", "bfloat16"], default="bfloat16")
    parser.add_argument("--micro-batch-size", type=int, default=512)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument("--validate", action="store_true", help="全設定のデータhashも検証")
    parser.add_argument("--run", action="store_true", help="検証後に全条件を順次学習")
    # 明示指定時だけ、学習後に全モデルを同じ固定5集合で評価する
    parser.add_argument("--evaluate", action="store_true", help="--run後に全5集合を評価してcomparison.jsonを作る")
    parser.add_argument("--max-steps", type=int, help="動作確認専用。正式比較では省略")
    args = parser.parse_args()
    if args.epochs < 1 or not 0 <= args.seed < 2**32:
        parser.error("epochsは正整数、seedは0以上2**32未満にしてください")
    if len(args.variants) != len(set(args.variants)):
        parser.error("variantを重複指定できません")
    if min(args.micro_batch_size, args.gradient_accumulation_steps) < 1:
        parser.error("batchと蓄積回数は正の整数が必要です")
    if args.micro_batch_size * args.gradient_accumulation_steps != 512:
        parser.error("公平な比較のため実効batchは512にしてください")
    if args.max_steps is not None and (args.max_steps < 1 or not args.run):
        parser.error("--max-stepsは--runとともに正の整数で指定してください")
    # 動作確認の途中重みを正式な全件評価へ誤投入しない
    if args.evaluate and (not args.run or args.max_steps is not None):
        parser.error("--evaluateは--runが必要です。--max-stepsとは併用できません")
    # 出力先は呼出し元のcwdに対して解決し、データ参照だけrepo基準にする
    output = args.output_root.resolve()
    if output.exists():
        parser.error(f"既存の出力先を上書きしません: {output}")
    os.chdir(ROOT)
    base = yaml.safe_load((ROOT / "config/boku_nano_1m_bpe_2048_1epoch.yaml").read_text())
    evaluation_base = yaml.safe_load(
        (ROOT / "config/boku_nano_1m_bpe_2048_1epoch_evaluation.yaml").read_text()
    )
    base["runtime"].update(device=args.device, dtype=args.dtype)
    evaluation_base["generation"].update(device=args.device, dtype=args.dtype)
    base["training"].update(micro_batch_size=args.micro_batch_size,
                             gradient_accumulation_steps=args.gradient_accumulation_steps)
    jobs = []
    for variant in args.variants:
        folder = output / f"{variant}_seed{args.seed}"
        config, evaluation = build_configs(base, evaluation_base, variant, folder,
                                           args.seed, args.epochs)
        command = [sys.executable, str(ROOT / "scripts/model/train_boku_nano.py"),
                   "--config", str(folder / "config.yaml")]
        if args.max_steps is not None:
            command.extend(["--max-steps", str(args.max_steps)])
        jobs.append((folder, config, evaluation, {
            "variant": variant, "model_config": config["model"],
            "effective_layers": config["model"]["n_layers"] * config["model"]["n_loops"],
            "parameter_count": config["model_validation"]["expected_parameter_count"],
            "command": command, "evaluation_config": str(folder / "evaluation.yaml"),
            # 評価だけ後から行う場合にも、そのまま再利用できるcommandを残す
            "evaluation_command": [sys.executable, str(ROOT / "scripts/model/evaluate_boku_nano.py"),
                                   "--config", str(folder / "evaluation.yaml")],
        }))
    output.mkdir(parents=True, exist_ok=False)
    for folder, config, evaluation, job in jobs:
        folder.mkdir()
        for filename, value in [("config.yaml", config), ("evaluation.yaml", evaluation)]:
            (folder / filename).write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
                                           encoding="utf-8")
        print(f"{job['variant']}: {job['parameter_count']:,} parameters, "
              f"{job['effective_layers']} block applications", flush=True)
    manifest = {"format_version": 1, "epochs": args.epochs, "seed": args.seed,
                "smoke_test": args.max_steps is not None,
                "evaluate_after_training": args.evaluate,
                "jobs": [job for _, _, _, job in jobs]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if args.validate or args.run:
        for _, _, _, job in jobs:
            subprocess.run(job["command"] + ["--validate-config"], check=True)
    if args.run:
        for folder, _, _, job in jobs:
            # ログの保存先を先に表示し、長時間実行でも進行を追えるようにする
            print(f"Training {job['variant']}: {folder / 'console.log'}", flush=True)
            with (folder / "console.log").open("x") as log:
                subprocess.run(job["command"], stdout=log, stderr=subprocess.STDOUT, check=True)
    # 全条件の学習が終わってから評価し、学習と評価の負荷を分離する
    if args.evaluate:
        for folder, _, _, job in jobs:
            print(f"Evaluating {job['variant']}: {folder / 'evaluation_console.log'}", flush=True)
            with (folder / "evaluation_console.log").open("x") as log:
                subprocess.run(job["evaluation_command"], stdout=log, stderr=subprocess.STDOUT, check=True)
        # 合計だけでなく、生成・実行評価の各集合の得点も保存する
        comparison = write_comparison(output, jobs)
        for row in comparison["models"]:
            print(f"{row['variant']}: {row['passed']}/{row['total']} "
                  f"({100 * row['pass_rate']:.4f}%)", flush=True)


if __name__ == "__main__":
    main()
