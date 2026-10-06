"""1M/5Mの構造比較を生成・検証し、明示指定時だけ順次学習する。"""
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

TARGETS = {"1m": 1_016_704, "5m": 5_065_472}


def count(d: int, layers: int, ff: int) -> int:
    """非共有embedding、biasなしprojection、RMSNormの正確な総数。"""
    return 2 * 2048 * d + layers * (4 * d * d + 3 * d * ff + 2 * d) + d


def architecture(size: str, strategy: str) -> dict[str, int]:
    if strategy == "existing":
        d, layers, heads, ff = (128, 3, 4, 256) if size == "1m" else (256, 5, 4, 704)
    else:
        layers = (3 if size == "1m" else 5) if strategy == "fixed_heads" else 8
        # head固定は偶数head_dim、layer固定は1Mで2 heads、5Mで4 headsに縮小。
        candidates = []
        for d in range(24, 385):
            heads = 6 if strategy == "fixed_heads" else (2 if size == "1m" else 4)
            if heads < 1 or d % heads or (d // heads) % 2:
                continue
            for ff in range(8, 1537, 8):
                if 2 <= ff / d <= 4:
                    candidates.append((abs(count(d, layers, ff) - TARGETS[size]),
                                       abs(ff / d - 8 / 3), d, heads, ff))
        _, _, d, heads, ff = min(candidates)
    return dict(d_model=d, n_layers=layers, n_heads=heads, d_ff=ff)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True,
                        help="新規ディレクトリ。既存パスは上書きしない")
    parser.add_argument("--sizes", nargs="+", choices=TARGETS, default=list(TARGETS))
    parser.add_argument("--strategies", nargs="+", choices=["existing", "fixed_heads", "fixed_layers"],
                        default=["existing", "fixed_heads", "fixed_layers"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[20260925, 20260926, 20260927])
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--tokenizer", choices=["bpe_2048_minfreq5_maxlen24", "bpe_2048_minfreq2_maxlen8"],
                        default="bpe_2048_minfreq5_maxlen24")
    parser.add_argument("--validate", action="store_true", help="固定入力hash等も既存trainerで検証")
    parser.add_argument("--run", action="store_true", help="検証後、全条件を順次学習")
    args = parser.parse_args()
    if args.epochs < 1 or any(seed < 0 or seed >= 2**32 for seed in args.seeds):
        parser.error("epochsは正整数、seedは0以上2**32未満にしてください")
    for values in (args.sizes, args.strategies, args.seeds):
        if len(values) != len(set(values)):
            parser.error("条件の重複は指定できません")
    os.chdir(ROOT)
    output = args.output_root.resolve()
    if output.exists():
        parser.error(f"既存の出力先です: {output}")
    suffix = "" if args.tokenizer.endswith("minfreq5_maxlen24") else "_minfreq2_maxlen8"
    base_path = ROOT / f"config/boku_nano_1m_bpe_2048{suffix}_1epoch.yaml"
    base = yaml.safe_load(base_path.read_text())
    jobs = []
    for size in args.sizes:
        for strategy in args.strategies:
            model = dict(base["model"], **architecture(size, strategy))
            actual = BokuNanoForCausalLM(BokuNanoConfig.from_dict(model)).parameter_count()
            expected = count(model["d_model"], model["n_layers"], model["d_ff"])
            if actual != expected or abs(actual / TARGETS[size] - 1) > 0.01:
                raise ValueError(f"parameter検証失敗: {size}/{strategy}: {actual}")
            for seed in args.seeds:
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
