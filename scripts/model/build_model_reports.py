#!/usr/bin/env python3
"""保存済み学習・評価成果物からモデル別の統一報告書を生成する。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_ROOT = ROOT / "data/models"
EVALUATION_ROOT = ROOT / "data/evaluations"
OUTPUT_ROOT = ROOT / "docs/results/model_reports"
LOSS_FIGURE_ROOT = ROOT / "docs/results/figures/training_loss_20step"

SUITES = (
    ("normal", "通常テスト"),
    ("compositional", "組合せ汎化テスト"),
    ("paraphrase", "日本語言い換えテスト"),
    ("repetition", "同一操作反復テスト"),
    ("boundary", "境界値テスト"),
)

EVALUATION_DIRECTORIES = {
    "boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch": "boku_nano_1m_bpe_2048_1epoch",
    "boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch": "boku_nano_1m_bpe_2048_minfreq2_maxlen8_1epoch",
    "boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch": "boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch",
    "boku_nano_1m_bpe_2048_minfreq2_maxlen8_3epoch": "boku_nano_1m_bpe_2048_minfreq2_maxlen8_3epoch",
    "boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch": "boku_nano_5m_bpe_2048_1epoch",
    "boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch": "boku_nano_5m_bpe_2048_minfreq2_maxlen8_1epoch",
    "boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch": "boku_nano_bpe_2048_1epoch",
    "boku_nano_15m_bpe_2048_minfreq2_maxlen8_1epoch": "boku_nano_bpe_2048_minfreq2_maxlen8_1epoch",
    "boku_nano_15m_bpe_2048_minfreq5_maxlen24_3epoch": "boku_nano_bpe_2048",
    "boku_nano_15m_bpe_2048_minfreq5_maxlen24_10epoch": "boku_nano_bpe_2048_10epoch",
}

NAME_PATTERN = re.compile(
    r"^boku_nano_(?P<size>1m|5m|15m)_bpe_2048_"
    r"minfreq(?P<minfreq>2|5)_maxlen(?P<maxlen>8|24)_"
    r"(?P<epochs>1|3|10)epoch$"
)


@dataclass(frozen=True)
class ModelIdentity:
    directory: str
    size: str
    min_frequency: int
    max_token_length: int
    epochs: int

    @property
    def tokenizer_label(self) -> str:
        return "既存BPE" if self.min_frequency == 5 else "短いpiece版BPE"

    @property
    def display_name(self) -> str:
        return f"{self.size.upper()}・{self.tokenizer_label}・{self.epochs}エポック"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_identity(directory: str) -> ModelIdentity:
    match = NAME_PATTERN.fullmatch(directory)
    if match is None:
        raise ValueError(f"未対応のモデル名です: {directory}")
    return ModelIdentity(
        directory=directory,
        size=match.group("size"),
        min_frequency=int(match.group("minfreq")),
        max_token_length=int(match.group("maxlen")),
        epochs=int(match.group("epochs")),
    )


def load_epoch_metrics(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    latest_train: dict[str, Any] | None = None
    results: list[dict[str, Any]] = []
    for row in rows:
        if "loss" in row:
            latest_train = row
        elif row.get("event") == "validation":
            if latest_train is None:
                raise ValueError(f"validationより前にtrain lossがありません: {path}")
            results.append(
                {
                    "epoch": int(row["epoch"]),
                    "epoch_end_step": int(row["global_step"]),
                    "train_step": int(latest_train["global_step"]),
                    "train_loss": float(latest_train["loss"]),
                    "validation_loss": float(row["validation_loss"]),
                    "validation_perplexity": float(row["validation_perplexity"]),
                }
            )
    return results


def is_executable(verification: dict[str, Any]) -> bool:
    if not bool(verification["signature_ok"]) or bool(verification["timeout"]):
        return False
    error = verification.get("error")
    return error is None or str(error).startswith("不一致:")


def aggregate_evaluation(directory: Path) -> dict[str, Any]:
    totals = {
        "total": 0,
        "passed": 0,
        "syntax": 0,
        "safe": 0,
        "signature": 0,
        "executable": 0,
        "timeout": 0,
        "static_failure": 0,
        "runtime_failure": 0,
        "semantic_failure": 0,
    }
    suites: dict[str, dict[str, int]] = {}
    for suite, _ in SUITES:
        suite_total = 0
        suite_passed = 0
        for line in (directory / f"{suite}_results.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            verification = row["verification"]
            passed = bool(row["passed"])
            executable = is_executable(verification)
            suite_total += 1
            suite_passed += int(passed)
            totals["total"] += 1
            totals["passed"] += int(passed)
            totals["syntax"] += int(bool(verification["syntax_ok"]))
            totals["safe"] += int(bool(verification["ast_safe"]))
            totals["signature"] += int(bool(verification["signature_ok"]))
            totals["executable"] += int(executable)
            totals["timeout"] += int(bool(verification["timeout"]))
            if not bool(verification["signature_ok"]):
                totals["static_failure"] += 1
            elif not executable:
                totals["runtime_failure"] += 1
            elif not passed:
                totals["semantic_failure"] += 1
        suites[suite] = {"total": suite_total, "passed": suite_passed}
    totals["suites"] = suites
    return totals


def percentage(value: int, total: int) -> str:
    return f"{100 * value / total:.4f}%"


def attention_section(identity: ModelIdentity) -> tuple[str, str]:
    for group in ("attention_1epoch", "attention_3epoch"):
        analysis_dir = ROOT / "docs/results" / group / identity.directory
        if analysis_dir.is_dir():
            relative = f"../{group}/{identity.directory}"
            body = f"""## attention解析

このモデルは24単独操作診断と生成step解析まで実施済みである。正式な固定5テストとはpromptと目的が異なるため、attention診断の合格数を正式pass@1と同一視しない。

![head別の記述的役割]({relative}/figures/attention_head_roles.svg)

![因果的ablation]({relative}/figures/attention_causal_ablation.svg)

![生成step×参照token位置]({relative}/figures/attention_by_layer_head.svg)

- [24操作解析JSON]({relative}/analysis.json)
- [生成step解析JSON]({relative}/detail_analysis.json)
"""
            return "実施済み", body
    if identity.directory == "boku_nano_15m_bpe_2048_minfreq5_maxlen24_3epoch":
        body = """## attention解析

15M・3エポックモデルは、K/V内部状態、head別attention、sink、rollout、Value・head ablationを解析済みである。

![head別の記述的役割](../figures/boku_nano_attention_head_roles.svg)

![因果的ablation](../figures/boku_nano_attention_causal_ablation.svg)

詳細は[KVキャッシュ・attention詳細解析レポート](../boku_nano_kv_cache_visualization.md)を参照。
"""
        return "実施済み", body
    return "未実施", """## attention解析

このモデル単体のattention詳細解析は未実施である。学習・実行評価の数値とは区別して記録する。
"""


def build_report(identity: ModelIdentity) -> tuple[str, dict[str, Any]]:
    model_dir = MODEL_ROOT / identity.directory
    manifest = read_json(model_dir / "training_manifest.json")
    model = manifest["model_config"]
    metrics = load_epoch_metrics(model_dir / "training_metrics.jsonl")
    evaluation_name = EVALUATION_DIRECTORIES[identity.directory]
    evaluation_dir = EVALUATION_ROOT / evaluation_name
    evaluation_manifest = read_json(evaluation_dir / "evaluation_manifest.json")
    evaluation = aggregate_evaluation(evaluation_dir)
    total = int(evaluation["total"])
    passed = int(evaluation["passed"])
    if len(metrics) != identity.epochs:
        raise ValueError(
            f"{identity.directory}: epoch metrics={len(metrics)}, expected={identity.epochs}"
        )
    if evaluation_manifest["model_sha256"] != manifest["model_sha256"]:
        raise ValueError(f"{identity.directory}: 学習モデルと評価モデルのSHA-256が一致しません")
    if evaluation_manifest["tokenizer_sha256"] != manifest["tokenizer_sha256"]:
        raise ValueError(f"{identity.directory}: 学習時と評価時のtokenizer SHA-256が一致しません")
    if total != 84_550:
        raise ValueError(f"{identity.directory}: 固定5テストが84,550件ではありません: {total}")
    attention_status, attention_body = attention_section(identity)
    final_validation = metrics[-1]["validation_loss"]

    lines = [
        f"# {identity.display_name}：学習・評価報告",
        "",
        "## 結論",
        "",
        (
            f"{int(manifest['parameter_count']):,}パラメータのDecoder-only Transformerを、"
            f"{identity.tokenizer_label}（語彙数2,048、`min_frequency={identity.min_frequency}`、"
            f"`max_token_length={identity.max_token_length}`）でランダム初期値から"
            f"{identity.epochs}エポック学習した。固定5テストでは{passed:,} / {total:,}件に合格し、"
            f"pass@1は{percentage(passed, total)}、最終validation lossは{final_validation:.6f}だった。"
        ),
        "",
        "## モデルとトークナイザー",
        "",
        "| 項目 | 値 |",
        "|---|---:|",
        f"| 総パラメータ数 | {int(manifest['parameter_count']):,} |",
        f"| 語彙数 | {int(model['vocab_size']):,} |",
        f"| hidden size | {int(model['d_model']):,} |",
        f"| 層数 | {int(model['n_layers'])} |",
        f"| Attention head数 | {int(model['n_heads'])} |",
        f"| 1 head当たりの次元数 | {int(model['d_model']) // int(model['n_heads'])} |",
        f"| FFN size | {int(model['d_ff']):,} |",
        f"| 最大系列長 | {int(model['context_length'])} |",
        "| 位置表現 | RoPE |",
        "| 正規化 / 活性化 | RMSNorm / SwiGLU |",
        f"| 入出力embedding共有 | {'あり' if model['tie_word_embeddings'] else 'なし'} |",
        f"| tokenizer最小頻度 / 最大piece長 | {identity.min_frequency} / {identity.max_token_length} |",
        f"| tokenizer SHA-256 | `{manifest['tokenizer_sha256']}` |",
        f"| seed | {int(manifest['seed'])} |",
        f"| dtype / device | {manifest['dtype']} / {manifest['device']} |",
        f"| micro / effective batch size | {int(manifest['micro_batch_size'])} / {int(manifest['effective_batch_size'])} |",
        "",
        "## 学習結果",
        "",
        "| 項目 | 結果 |",
        "|---|---:|",
        f"| エポック | {identity.epochs} |",
        f"| optimizer step | {int(manifest['effective_optimizer_steps']):,} |",
        f"| 1エポックの系列token | {int(manifest['dataset']['sequence_token_count_per_epoch']):,} |",
        f"| 全エポックの系列token | {int(manifest['dataset']['sequence_token_count_all_epochs']):,} |",
        f"| 1エポックのloss対象token | {int(manifest['dataset']['supervised_token_count_per_epoch']):,} |",
        f"| 全エポックのloss対象token | {int(manifest['dataset']['supervised_token_count_all_epochs']):,} |",
        f"| 学習時間 | {float(manifest['elapsed_seconds']):.3f}秒 |",
        f"| モデルSHA-256 | `{manifest['model_sha256']}` |",
        "",
        "| Epoch | 終了step | train記録step | 最終train loss | Validation loss | Validation perplexity |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in metrics:
        lines.append(
            f"| {row['epoch']} | {row['epoch_end_step']:,} | {row['train_step']:,} | "
            f"{row['train_loss']:.6f} | {row['validation_loss']:.6f} | "
            f"{row['validation_perplexity']:.6f} |"
        )
    lines.extend(
        [
            "",
            "train lossは原則として直近20 optimizer stepの区間平均であり、validation lossは各epoch終了時に固定validation 24,040件全体で計算した値である。縦軸は初期と収束後を同じ図で読めるよう対数目盛にしている。",
            "",
            f"![{identity.display_name}の20 stepごとのloss](../figures/training_loss_20step/{identity.directory}.svg)",
            "",
            "## 固定5テストの評価",
            "",
            (
                f"`{evaluation_manifest['generation']['decoding']}`生成、最大"
                f"{int(evaluation_manifest['generation']['max_new_tokens'])} token、"
                f"{evaluation_manifest['dtype']}で評価した。参照コードとの文字列一致ではなく、"
                "構文、安全AST、`solve(xs, k)`、入力非変更、各問のhidden testをすべて満たした場合を合格とした。"
            ),
            "",
            "| テスト | 合格 | 不合格 | pass@1 |",
            "|---|---:|---:|---:|",
        ]
    )
    for suite, label in SUITES:
        item = evaluation["suites"][suite]
        lines.append(
            f"| {label} | {item['passed']:,} / {item['total']:,} | "
            f"{item['total'] - item['passed']:,} | {percentage(item['passed'], item['total'])} |"
        )
    lines.extend(
        [
            f"| **合計・参考値** | **{passed:,} / {total:,}** | **{total - passed:,}** | **{percentage(passed, total)}** |",
            "",
            "| 段階別指標 | 件数 | 率 |",
            "|---|---:|---:|",
            f"| Syntax-valid | {evaluation['syntax']:,} / {total:,} | {percentage(evaluation['syntax'], total)} |",
            f"| Safe-AST | {evaluation['safe']:,} / {total:,} | {percentage(evaluation['safe'], total)} |",
            f"| Signature-valid | {evaluation['signature']:,} / {total:,} | {percentage(evaluation['signature'], total)} |",
            f"| Executable | {evaluation['executable']:,} / {total:,} | {percentage(evaluation['executable'], total)} |",
            f"| pass@1 | {passed:,} / {total:,} | {percentage(passed, total)} |",
            (
                f"| 組合せ汎化率 | {evaluation['suites']['compositional']['passed']:,} / "
                f"{evaluation['suites']['compositional']['total']:,} | "
                f"{percentage(evaluation['suites']['compositional']['passed'], evaluation['suites']['compositional']['total'])} |"
            ),
            "",
            "### 不合格の分類",
            "",
            "| 分類 | 件数 |",
            "|---|---:|",
            f"| hidden testで意味不一致 | {evaluation['semantic_failure']:,} |",
            f"| 構文・安全AST・signatureの静的不合格 | {evaluation['static_failure']:,} |",
            f"| 実行時例外またはtimeout | {evaluation['runtime_failure']:,} |",
            f"| timeout（上段との重複内数） | {evaluation['timeout']:,} |",
            "",
            attention_body.rstrip(),
            "",
            "## 成果物と再現情報",
            "",
            f"- [モデル本体](../../../data/models/{identity.directory}/model.safetensors)",
            f"- [モデル設定](../../../data/models/{identity.directory}/model_config.json)",
            f"- [学習設定](../../../data/models/{identity.directory}/training_config.yaml)",
            f"- [学習manifest](../../../data/models/{identity.directory}/training_manifest.json)",
            f"- [学習metrics](../../../data/models/{identity.directory}/training_metrics.jsonl)",
            f"- 評価生データ: `data/evaluations/{evaluation_name}/`（Git管理対象外）",
            "",
            "```bash",
            "scripts/model/run_boku_nano_experiment_nohup.sh \\",
            f"  --model-size {identity.size} --epochs {identity.epochs} \\",
            f"  --tokenizer bpe_2048_minfreq{identity.min_frequency}_maxlen{identity.max_token_length}",
            "",
            "uv run --group model-training --python 3.12.12 python \\",
            "  scripts/model/evaluate_boku_nano.py \\",
            f"  --config {evaluation_manifest['config']} \\",
            f"  --model-directory data/models/{identity.directory} \\",
            f"  --output-directory data/evaluations/{evaluation_name}",
            "```",
            "",
        ]
    )
    metadata = {
        "identity": identity,
        "passed": passed,
        "total": total,
        "validation_loss": final_validation,
        "attention": attention_status,
        "parameter_count": int(manifest["parameter_count"]),
        "tokens": int(manifest["dataset"]["sequence_token_count_all_epochs"]),
    }
    return "\n".join(lines), metadata


def build_index(items: list[dict[str, Any]]) -> str:
    lines = [
        "# 学習済みモデル別の統一報告書",
        "",
        "保存済みの全10モデルについて、モデル設定、トークナイザー、学習量、20 stepごとのloss、固定5テスト、段階別評価、attention解析状況、再現情報を同じ書式でまとめた。",
        "",
        "モデル間の比較ではpass@1を主指標とする。異なるトークナイザー間ではtoken分割単位が違うため、lossの絶対値だけを直接比較しない。",
        "",
        "| モデル | パラメータ | 学習系列token | 最終Validation loss | 固定5テスト | attention |",
        "|---|---:|---:|---:|---:|---|",
    ]
    order = {"1m": 1, "5m": 2, "15m": 3}
    items.sort(
        key=lambda item: (
            order[item["identity"].size],
            0 if item["identity"].min_frequency == 5 else 1,
            item["identity"].epochs,
        )
    )
    for item in items:
        identity = item["identity"]
        lines.append(
            f"| [{identity.display_name}]({identity.directory}.md) | {item['parameter_count']:,} | "
            f"{item['tokens']:,} | {item['validation_loss']:.6f} | "
            f"{item['passed']:,} / {item['total']:,}（{percentage(item['passed'], item['total'])}） | "
            f"{item['attention']} |"
        )
    lines.extend(
        [
            "",
            "## 関連資料",
            "",
            "- [全モデルの20 stepごとのloss図](../training_loss_every_20_steps.md)",
            "- [学習済みモデル一覧とハッシュ](../trained_model_inventory.md)",
            "- [モデル評価方針](../../policies/boku_nano_model_evaluation_policy.md)",
            "- [ドキュメント全体の入口](../../README.md)",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for directory in sorted(EVALUATION_DIRECTORIES):
        identity = parse_identity(directory)
        loss_figure = LOSS_FIGURE_ROOT / f"{directory}.svg"
        if not loss_figure.is_file():
            raise FileNotFoundError(loss_figure)
        report, metadata = build_report(identity)
        (OUTPUT_ROOT / f"{directory}.md").write_text(report, encoding="utf-8")
        items.append(metadata)
    (OUTPUT_ROOT / "README.md").write_text(build_index(items), encoding="utf-8")
    print(f"wrote {len(items)} model reports to {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
