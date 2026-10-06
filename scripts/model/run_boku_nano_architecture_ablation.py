"""15Mからhead数だけ／layer数だけを変更し、明示指定時だけ順次学習する。"""
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

BASELINES = {"15m": (384, 8, 6, 1024)}
STRATEGIES = ("existing", "heads_4", "layers_2")


def count(d: int, layers: int, ff: int) -> int:
    """非共有embedding、biasなしprojection、RMSNormの正確な総数。"""
    return 2 * 2048 * d + layers * (4 * d * d + 3 * d * ff + 2 * d) + d


def architecture(size: str, strategy: str) -> dict[str, int]:
    d, layers, heads, ff = BASELINES[size]
    if strategy == "heads_4":
        heads = 4
    elif strategy == "layers_2":
        layers = 2
    elif strategy != "existing":
        raise ValueError(f"未知の比較条件: {strategy}")
    return dict(d_model=d, n_layers=layers, n_heads=heads, d_ff=ff)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True,
                        help="新規ディレクトリ。既存パスは上書きしない")
    parser.add_argument("--sizes", nargs="+", choices=BASELINES, default=list(BASELINES))
    parser.add_argument("--strategies", nargs="+", choices=STRATEGIES, default=list(STRATEGIES))
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--tokenizer", choices=["bpe_2048_minfreq5_maxlen24", "bpe_2048_minfreq2_maxlen8"],
                        default="bpe_2048_minfreq5_maxlen24")
    parser.add_argument("--validate", action="store_true", help="固定入力hash等も既存trainerで検証")
    parser.add_argument("--run", action="store_true", help="検証後、全条件を順次学習")
    args = parser.parse_args()
    if args.epochs < 1 or not 0 <= args.seed < 2**32:
        parser.error("epochsは正整数、seedは0以上2**32未満にしてください")
    for values in (args.sizes, args.strategies):
        if len(values) != len(set(values)):
            parser.error("条件の重複は指定できません")
    os.chdir(ROOT)
    output = args.output_root.resolve()
    if output.exists():
        parser.error(f"既存の出力先です: {output}")
    suffix = "" if args.tokenizer.endswith("minfreq5_maxlen24") else "_minfreq2_maxlen8"
    base_path = ROOT / f"config/boku_nano_bpe_2048{suffix}_1epoch.yaml"
    base = yaml.safe_load(base_path.read_text())
    jobs = []
    for size in args.sizes:
        for strategy in args.strategies:
            model = dict(base["model"], **architecture(size, strategy))
            actual = BokuNanoForCausalLM(BokuNanoConfig.from_dict(model)).parameter_count()
            expected = count(model["d_model"], model["n_layers"], model["d_ff"])
            if actual != expected:
                raise ValueError(f"parameter検証失敗: {size}/{strategy}: {actual}")
            seed = args.seed
            name = f"{size}_{strategy}_seed{seed}"
            config = deepcopy(base)
            config["model"] = model
            config["model_validation"]["expected_parameter_count"] = actual
            config["training"].update(seed=seed, epochs=args.epochs)
            config["output"]["directory"] = str(output / name / "model")
            jobs.append((name, config, actual))
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for name, config, actual in jobs:
        folder = output / name
        folder.mkdir()
        path = folder / "config.yaml"
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        command = [sys.executable, str(ROOT / "scripts/model/train_boku_nano.py"), "--config", str(path)]
        manifest.append(dict(name=name, parameter_count=actual, model=config["model"], command=command))
        print(f"{name}: {actual:,} parameters", flush=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # 全条件の入力検証を完了してから最初の学習を開始する。
    if args.validate or args.run:
        for job in manifest:
            subprocess.run(job["command"] + ["--validate-config"], check=True)
    if args.run:
        for job in manifest:
            with (output / job["name"] / "console.log").open("x") as log:
                subprocess.run(job["command"], stdout=log, stderr=subprocess.STDOUT, check=True)


if __name__ == "__main__":
    main()
