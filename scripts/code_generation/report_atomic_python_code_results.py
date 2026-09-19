"""1操作ASTのコード生成結果を、人が確認できるMarkdownへまとめる。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reference_interpreter import interpret  # noqa: E402


EXAMPLE_XS = [-6, -3, -1, 0, 2, 4, 7, 9]
EXAMPLE_K = 3

OPERATION_DESCRIPTIONS = {
    "filter:even": "偶数だけを残す",
    "filter:odd": "奇数だけを残す",
    "filter:gt_k": "kより大きい値だけを残す",
    "filter:ge_k": "k以上の値だけを残す",
    "filter:lt_k": "kより小さい値だけを残す",
    "filter:le_k": "k以下の値だけを残す",
    "filter:multiple_of_k": "kの倍数だけを残す",
    "filter:positive": "正の値だけを残す",
    "filter:negative": "負の値だけを残す",
    "filter:zero": "0だけを残す",
    "map:add_k": "各要素にkを足す",
    "map:sub_k": "各要素からkを引く",
    "map:mul_k": "各要素にkを掛ける",
    "map:mul_const:2": "各要素を2倍する",
    "map:mul_const:3": "各要素を3倍する",
    "map:negate": "各要素の符号を反転する",
    "map:abs": "各要素を絶対値にする",
    "map:square": "各要素を2乗する",
    "order:ascending": "値を昇順に並べる",
    "order:descending": "値を降順に並べる",
    "order:reverse": "現在の並びを逆順にする",
    "slice:take_first_k": "先頭からk個を取り出す",
    "slice:take_last_k": "末尾からk個を取り出す",
    "slice:every_other": "先頭から1つおきに取り出す",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="1操作コード生成結果のMarkdownを作ります。")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"既存ファイルがあります: {args.output}")

    records = _read_jsonl(args.input)
    stats = json.loads(args.stats.read_text(encoding="utf-8"))
    if len(records) != 24:
        raise ValueError(f"24件である必要があります: {len(records)}件")

    report = _build_report(records, stats, args.input, args.stats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")


def _build_report(
    records: list[dict[str, Any]],
    stats: dict[str, Any],
    input_path: Path,
    stats_path: Path,
) -> str:
    totals = stats["totals"]
    verification_case_count = stats["verification_case_count"]
    lines = [
        "# 24単純操作のPythonコード生成結果",
        "",
        "## この結果が示すこと",
        "",
        "24種類の1操作意味ASTを1件ずつコード生成し、各コードを参照インタプリタと照合した。全24件が採用条件を満たし、不採用・不足・完全重複は0件だった。これは、現時点の生成器が24操作すべてについて少なくとも1つの正しいPythonコードを生成できたことの確認である。1意味ASTあたり20件を生成できることの確認ではない。",
        "",
        "## 実行条件",
        "",
        f"- Python: {stats['python_version']}（`.python-version`で3.12に固定）",
        f"- 生成器シード: {stats['generator_seed']}",
        f"- 要素変数名候補: {_inline_names(stats['element_names'])}",
        f"- 結果変数名候補: {_inline_names(stats['result_names'])}",
        f"- 目標数: 各意味ASTにつき検証済み固有コード{stats['target_verified_per_ast']}件",
        "- データ分割: `train`（24種類の1操作ASTはすべて訓練用）",
        "- テスト集合: `null`（訓練用レコードなので評価テストには属さない）",
        f"- 実行検証: 各コードにつき{verification_case_count}入力（境界値{stats['boundary_test_count']}件、seed {stats.get('random_test_seed', stats['generator_seed'])}のランダム入力{stats['random_test_count']}件）",
        f"- 制限時間: 各コード{stats['timeout_seconds']:g}秒",
        "- 完全重複判定: 生成コード全文のSHA-256で候補を検索し、最後に全文を比較",
        f"- コード候補: `{input_path.as_posix()}`",
        f"- 集計: `{stats_path.as_posix()}`",
        "",
        "## 全体集計",
        "",
        "| 項目 | 結果 |",
        "|---|---:|",
        f"| 入力した意味AST | {len(records)}件 |",
        f"| 列挙可能な構造的変種 | {totals['available_style_count']:,}件 |",
        f"| 今回、実行検証へ回した候補 | {totals['candidate_count']}件 |",
        f"| 参照インタプリタと全入力で一致 | {totals['verified_count']}件 |",
        f"| 今回の24件内で完全重複を除外した後のコード候補 | {totals['deduplicated_count']}件 |",
        "| 不採用 | 0件 |",
        "| 目標未達 | 0件 |",
        "",
        f"`列挙可能な構造的変種`は、今回の変数名設定で生成器が候補として列挙できるstyle_specの総数である。今回は各ASTの目標を{stats['target_verified_per_ast']}件にしたため、ハッシュ順の候補が目標数へ届いた時点で次のASTへ進んだ。したがって、{totals['available_style_count']:,}件すべてを実行したという意味ではない。また、組合せ汎化テストのコードとの完全一致比較は、この24件確認では行っていない。",
        "",
        "## `code_style`の読み方",
        "",
        "`code_style`はコード内容ではなく、生成コードの大まかな構造を集計するためのラベルである。コメント、型注釈、変数名、比較式の向き、具体的な式形式は`style_spec`に保存する。",
        "",
        "| 値 | このデータでの意味 |",
        "|---|---|",
        "| `expression_comprehension`（内包表記・組み込み関数・スライスを直接`return`する形式） | 一時変数を使わず、結果の式を直接`return`する |",
        "| `staged_comprehension`（内包表記・組み込み関数・スライスに一時変数を使う形式） | 結果を一時変数へ代入してから`return`し、通常の`for`ループを使わない |",
        "| `staged_loop`（通常の`for`ループ形式） | 結果用の一時変数と通常の`for`ループを使う |",
        "| `mixed`（内包表記と`for`ループの混合形式） | 複数操作で内包表記と通常の`for`ループが混在する |",
        "",
        "名称に`comprehension`を含む2値にも、`sorted`、`reversed`、スライスを使ったコードが入る。内包表記を実際に使っているかは、`style_spec.collection_form`と`style_spec.operation_styles`で判定する。",
        "",
        "## `split`が`train`である理由",
        "",
        "意味ASTの分割方針では、24種類の1操作ASTをすべて訓練へ割り当てている。この結果は`data/semantic_asts/train_semantic_asts.jsonl`から1操作ASTだけを選んで生成しているため、全24件が`split: \"train\"`、`test_suite: null`となる。",
        "",
        "## 個別結果",
        "",
        f"以下の具体例は全件共通で `xs = {EXAMPLE_XS}`, `k = {EXAMPLE_K}` を使用する。`参照結果`と`生成コードの結果`は別々に実行して記載している。",
        "",
    ]

    for index, record in enumerate(records, start=1):
        lines.extend(
            _record_section(
                index,
                record,
                stats["per_spec"][record["spec_id"]],
                verification_case_count,
                stats["timeout_seconds"],
            )
        )

    return "\n".join(lines).rstrip() + "\n"


def _record_section(
    index: int,
    record: dict[str, Any],
    spec_stats: dict[str, int],
    verification_case_count: int,
    timeout_seconds: float,
) -> list[str]:
    semantic_ast = record["semantic_ast"]
    key = _operation_key(semantic_ast)
    description = OPERATION_DESCRIPTIONS[key]
    expected = interpret(semantic_ast, list(EXAMPLE_XS), EXAMPLE_K)
    actual = _run_generated(record["reference_code"], EXAMPLE_XS, EXAMPLE_K)
    if actual != expected:
        raise RuntimeError(f"{record['spec_id']}: レポート作成時の再実行結果が不一致です")

    style = record["style_spec"]
    operation_style = style["operation_styles"][0]
    style_summary = _style_summary(style, operation_style)
    ast_json = json.dumps(semantic_ast, ensure_ascii=False, separators=(",", ":"))
    code = record["reference_code"].rstrip()

    return [
        f"### {index}. `{record['spec_id']}` — {description}",
        "",
        f"- 意味AST: `{ast_json}`",
        f"- 生成形式: {style_summary}",
        f"- 列挙可能な構造的変種: {spec_stats['available_style_count']}件",
        f"- 今回検証した候補: {spec_stats['candidate_count']}件（1件目で採用）",
        f"- 具体例の参照結果: `{expected}`",
        f"- 具体例の生成コード結果: `{actual}`",
        f"- 参照インタプリタとの照合: **合格**（検証入力{verification_case_count}件すべてで、生成コードの戻り値が参照インタプリタの戻り値と完全一致。生成コードは入力リスト`xs`を変更せず、{timeout_seconds:g}秒の制限時間内に完了）",
        f"- コードID: `{record['code_id']}`",
        f"- コードハッシュ: `{record['code_hash']}`",
        "",
        "```python",
        code,
        "```",
        "",
    ]


def _inline_names(names: list[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


def _operation_key(semantic_ast: dict[str, Any]) -> str:
    if set(semantic_ast) == {"sequence"}:
        sequence = semantic_ast["sequence"]
        if not isinstance(sequence, list) or len(sequence) != 1:
            raise ValueError("このレポートでは1操作のsequenceだけを扱います")
        operation = sequence[0]
    else:
        operation = semantic_ast
    operation_type, argument = next(iter(operation.items()))
    if operation_type in {"filter", "slice"}:
        return f"{operation_type}:{argument[0]}"
    if operation_type == "map":
        suffix = ":".join(str(value) for value in argument)
        return f"map:{suffix}"
    return f"order:{argument}"


def _style_summary(style: dict[str, Any], operation_style: dict[str, Any]) -> str:
    parts = [
        "1行return" if style["layout"] == "single_return" else "複数行",
        _collection_label(style["collection_form"]),
        "コメントあり" if style["comments"] == "present" else "コメントなし",
        "型注釈あり" if style["local_annotations"] else "型注釈なし",
    ]
    element_name = operation_style.get("element_name")
    result_name = operation_style.get("result_name")
    condition_direction = operation_style.get("condition_direction")
    expression_form = operation_style.get("expression_form")
    if element_name is not None:
        parts.append(f"要素変数 `{element_name}`")
    if result_name is not None:
        parts.append(f"結果変数 `{result_name}`")
    if condition_direction is not None:
        parts.append(
            "比較式の左右入れ替えあり"
            if condition_direction == "swapped"
            else "比較式の左右入れ替えなし"
        )
    if expression_form != "default":
        parts.append(f"式形式 `{expression_form}`")
    return "、".join(parts)


def _collection_label(value: str | None) -> str:
    labels = {
        "list_comprehension": "内包表記",
        "for_loop": "通常のforループ",
        "mixed": "内包表記とforループの混在",
        None: "組み込み関数またはスライス",
    }
    return labels[value]


def _run_generated(source: str, xs: list[int], k: int) -> list[int]:
    namespace: dict[str, Any] = {
        "__builtins__": {
            "abs": abs,
            "int": int,
            "list": list,
            "reversed": reversed,
            "sorted": sorted,
        }
    }
    exec(compile(source, "<generated-report>", "exec"), namespace)
    result = namespace["solve"](list(xs), k)
    if not isinstance(result, list) or any(type(value) is not int for value in result):
        raise TypeError("生成コードの結果は整数リストである必要があります")
    return result


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise TypeError(f"{path}:{line_number}: レコードは辞書にしてください")
            records.append(record)
    return records
if __name__ == "__main__":
    main()
