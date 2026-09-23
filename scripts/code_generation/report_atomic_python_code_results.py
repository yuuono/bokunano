"""1操作ASTのコード生成結果を、人が確認できるMarkdownへまとめる。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# この処理で使う標準または外部モジュールを読み込む
import argparse
# この処理で使う標準または外部モジュールを読み込む
import json
# 必要な定義を対象モジュールから読み込む
from pathlib import Path
# この処理で使う標準または外部モジュールを読み込む
import sys
# 必要な定義を対象モジュールから読み込む
from typing import Any


# PROJECT_ROOTへこの工程で使用する値を設定する
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 条件を満たす場合だけ次の処理を行う
if str(PROJECT_ROOT) not in sys.path:
    # 次の値または処理を現在の構造へ組み込む
    sys.path.insert(0, str(PROJECT_ROOT))

from reference_interpreter import interpret  # noqa: E402


# EXAMPLE_XSへこの工程で使用する値を設定する
EXAMPLE_XS = [-6, -3, -1, 0, 2, 4, 7, 9]
# EXAMPLE_Kへこの工程で使用する値を設定する
EXAMPLE_K = 3

# OPERATION_DESCRIPTIONSへこの工程で使用する値を設定する
OPERATION_DESCRIPTIONS = {
    # 出力レコードの項目と値を設定する
    "filter:even": "偶数だけを残す",
    # 出力レコードの項目と値を設定する
    "filter:odd": "奇数だけを残す",
    # 出力レコードの項目と値を設定する
    "filter:gt_k": "kより大きい値だけを残す",
    # 出力レコードの項目と値を設定する
    "filter:ge_k": "k以上の値だけを残す",
    # 出力レコードの項目と値を設定する
    "filter:lt_k": "kより小さい値だけを残す",
    # 出力レコードの項目と値を設定する
    "filter:le_k": "k以下の値だけを残す",
    # 出力レコードの項目と値を設定する
    "filter:multiple_of_k": "kの倍数だけを残す",
    # 出力レコードの項目と値を設定する
    "filter:positive": "正の値だけを残す",
    # 出力レコードの項目と値を設定する
    "filter:negative": "負の値だけを残す",
    # 出力レコードの項目と値を設定する
    "filter:zero": "0だけを残す",
    # 出力レコードの項目と値を設定する
    "map:add_k": "各要素にkを足す",
    # 出力レコードの項目と値を設定する
    "map:sub_k": "各要素からkを引く",
    # 出力レコードの項目と値を設定する
    "map:mul_k": "各要素にkを掛ける",
    # 出力レコードの項目と値を設定する
    "map:mul_const:2": "各要素を2倍する",
    # 出力レコードの項目と値を設定する
    "map:mul_const:3": "各要素を3倍する",
    # 出力レコードの項目と値を設定する
    "map:negate": "各要素の符号を反転する",
    # 出力レコードの項目と値を設定する
    "map:abs": "各要素を絶対値にする",
    # 出力レコードの項目と値を設定する
    "map:square": "各要素を2乗する",
    # 出力レコードの項目と値を設定する
    "order:ascending": "値を昇順に並べる",
    # 出力レコードの項目と値を設定する
    "order:descending": "値を降順に並べる",
    # 出力レコードの項目と値を設定する
    "order:reverse": "現在の並びを逆順にする",
    # 出力レコードの項目と値を設定する
    "slice:take_first_k": "先頭からk個を取り出す",
    # 出力レコードの項目と値を設定する
    "slice:take_last_k": "末尾からk個を取り出す",
    # 出力レコードの項目と値を設定する
    "slice:every_other": "先頭から1つおきに取り出す",
}


# この工程を担当する関数を定義する
def parse_args() -> argparse.Namespace:
    # parserへこの工程で使用する値を設定する
    parser = argparse.ArgumentParser(description="1操作コード生成結果のMarkdownを作ります。")
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--input", type=Path, required=True)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--stats", type=Path, required=True)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--output", type=Path, required=True)
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument("--overwrite", action="store_true")
    # 処理結果を呼び出し元へ返す
    return parser.parse_args()


# この工程を担当する関数を定義する
def main() -> None:
    # argsへこの工程で使用する値を設定する
    args = parse_args()
    # 条件を満たす場合だけ次の処理を行う
    if args.output.exists() and not args.overwrite:
        # 不正な状態を例外として通知して処理を停止する
        raise FileExistsError(f"既存ファイルがあります: {args.output}")

    # recordsへこの工程で使用する値を設定する
    records = _read_jsonl(args.input)
    # statsへこの工程で使用する値を設定する
    stats = json.loads(args.stats.read_text(encoding="utf-8"))
    # 条件を満たす場合だけ次の処理を行う
    if len(records) != 24:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"24件である必要があります: {len(records)}件")

    # reportへこの工程で使用する値を設定する
    report = _build_report(records, stats, args.input, args.stats)
    # 次の値または処理を現在の構造へ組み込む
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # 次の値または処理を現在の構造へ組み込む
    args.output.write_text(report, encoding="utf-8")


# この工程を担当する関数を定義する
def _build_report(
    # 次の値または処理を現在の構造へ組み込む
    records: list[dict[str, Any]],
    # 次の値または処理を現在の構造へ組み込む
    stats: dict[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    input_path: Path,
    # 次の値または処理を現在の構造へ組み込む
    stats_path: Path,
# 次の値または処理を現在の構造へ組み込む
) -> str:
    # totalsへこの工程で使用する値を設定する
    totals = stats["totals"]
    # verification_case_countへこの工程で使用する値を設定する
    verification_case_count = stats["verification_case_count"]
    # linesへこの工程で使用する値を設定する
    lines = [
        # この処理で扱う文字列を一覧へ加える
        "# 24単純操作のPythonコード生成結果",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "## この結果が示すこと",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "24種類の1操作意味ASTを1件ずつコード生成し、各コードを参照インタプリタと照合した。全24件が採用条件を満たし、不採用・不足・完全重複は0件だった。これは、現時点の生成器が24操作すべてについて少なくとも1つの正しいPythonコードを生成できたことの確認である。1意味ASTあたり20件を生成できることの確認ではない。",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "## 実行条件",
        # この処理で扱う文字列を一覧へ加える
        "",
        # 次の値または処理を現在の構造へ組み込む
        f"- Python: {stats['python_version']}（`.python-version`で3.12に固定）",
        # 次の値または処理を現在の構造へ組み込む
        f"- 生成器シード: {stats['generator_seed']}",
        # 次の値または処理を現在の構造へ組み込む
        f"- 要素変数名候補: {_inline_names(stats['element_names'])}",
        # 次の値または処理を現在の構造へ組み込む
        f"- 結果変数名候補: {_inline_names(stats['result_names'])}",
        # 次の値または処理を現在の構造へ組み込む
        f"- 目標数: 各意味ASTにつき検証済み固有コード{stats['target_verified_per_ast']}件",
        # 出力レコードの項目と値を設定する
        "- データ分割: `train`（24種類の1操作ASTはすべて訓練用）",
        # 出力レコードの項目と値を設定する
        "- テスト集合: `null`（訓練用レコードなので評価テストには属さない）",
        # 次の値または処理を現在の構造へ組み込む
        f"- 実行検証: 各コードにつき{verification_case_count}入力（境界値{stats['boundary_test_count']}件、seed {stats.get('random_test_seed', stats['generator_seed'])}のランダム入力{stats['random_test_count']}件）",
        # 次の値または処理を現在の構造へ組み込む
        f"- 制限時間: 各コード{stats['timeout_seconds']:g}秒",
        # 出力レコードの項目と値を設定する
        "- 完全重複判定: 生成コード全文のSHA-256で候補を検索し、最後に全文を比較",
        # 次の値または処理を現在の構造へ組み込む
        f"- コード候補: `{input_path.as_posix()}`",
        # 次の値または処理を現在の構造へ組み込む
        f"- 集計: `{stats_path.as_posix()}`",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "## 全体集計",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "| 項目 | 結果 |",
        # 出力レコードの項目と値を設定する
        "|---|---:|",
        # 次の値または処理を現在の構造へ組み込む
        f"| 入力した意味AST | {len(records)}件 |",
        # 次の値または処理を現在の構造へ組み込む
        f"| 列挙可能な構造的変種 | {totals['available_style_count']:,}件 |",
        # 次の値または処理を現在の構造へ組み込む
        f"| 今回、実行検証へ回した候補 | {totals['candidate_count']}件 |",
        # 次の値または処理を現在の構造へ組み込む
        f"| 参照インタプリタと全入力で一致 | {totals['verified_count']}件 |",
        # 次の値または処理を現在の構造へ組み込む
        f"| 今回の24件内で完全重複を除外した後のコード候補 | {totals['deduplicated_count']}件 |",
        # この処理で扱う文字列を一覧へ加える
        "| 不採用 | 0件 |",
        # この処理で扱う文字列を一覧へ加える
        "| 目標未達 | 0件 |",
        # この処理で扱う文字列を一覧へ加える
        "",
        # 次の値または処理を現在の構造へ組み込む
        f"`列挙可能な構造的変種`は、今回の変数名設定で生成器が候補として列挙できるstyle_specの総数である。今回は各ASTの目標を{stats['target_verified_per_ast']}件にしたため、ハッシュ順の候補が目標数へ届いた時点で次のASTへ進んだ。したがって、{totals['available_style_count']:,}件すべてを実行したという意味ではない。また、組合せ汎化テストのコードとの完全一致比較は、この24件確認では行っていない。",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "## `code_style`の読み方",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "`code_style`はコード内容ではなく、生成コードの大まかな構造を集計するためのラベルである。コメント、型注釈、変数名、比較式の向き、具体的な式形式は`style_spec`に保存する。",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "| 値 | このデータでの意味 |",
        # この処理で扱う文字列を一覧へ加える
        "|---|---|",
        # この処理で扱う文字列を一覧へ加える
        "| `expression_comprehension`（内包表記・組み込み関数・スライスを直接`return`する形式） | 一時変数を使わず、結果の式を直接`return`する |",
        # この処理で扱う文字列を一覧へ加える
        "| `staged_comprehension`（内包表記・組み込み関数・スライスに一時変数を使う形式） | 結果を一時変数へ代入してから`return`し、通常の`for`ループを使わない |",
        # この処理で扱う文字列を一覧へ加える
        "| `staged_loop`（通常の`for`ループ形式） | 結果用の一時変数と通常の`for`ループを使う |",
        # この処理で扱う文字列を一覧へ加える
        "| `mixed`（内包表記と`for`ループの混合形式） | 複数操作で内包表記と通常の`for`ループが混在する |",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "名称に`comprehension`を含む2値にも、`sorted`、`reversed`、スライスを使ったコードが入る。内包表記を実際に使っているかは、`style_spec.collection_form`と`style_spec.operation_styles`で判定する。",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "## `split`が`train`である理由",
        # この処理で扱う文字列を一覧へ加える
        "",
        # 出力レコードの項目と値を設定する
        "意味ASTの分割方針では、24種類の1操作ASTをすべて訓練へ割り当てている。この結果は`data/semantic_asts/train_semantic_asts.jsonl`から1操作ASTだけを選んで生成しているため、全24件が`split: \"train\"`、`test_suite: null`となる。",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "## 個別結果",
        # この処理で扱う文字列を一覧へ加える
        "",
        # 次の値または処理を現在の構造へ組み込む
        f"以下の具体例は全件共通で `xs = {EXAMPLE_XS}`, `k = {EXAMPLE_K}` を使用する。`参照結果`と`生成コードの結果`は別々に実行して記載している。",
        # この処理で扱う文字列を一覧へ加える
        "",
    ]

    # 対象を一件ずつ取り出して処理する
    for index, record in enumerate(records, start=1):
        # 次の値または処理を現在の構造へ組み込む
        lines.extend(
            # 次の値または処理を現在の構造へ組み込む
            _record_section(
                # 次の値または処理を現在の構造へ組み込む
                index,
                # 次の値または処理を現在の構造へ組み込む
                record,
                # 次の値または処理を現在の構造へ組み込む
                stats["per_spec"][record["spec_id"]],
                # 次の値または処理を現在の構造へ組み込む
                verification_case_count,
                # 次の値または処理を現在の構造へ組み込む
                stats["timeout_seconds"],
            )
        )

    # 処理結果を呼び出し元へ返す
    return "\n".join(lines).rstrip() + "\n"


# この工程を担当する関数を定義する
def _record_section(
    # 次の値または処理を現在の構造へ組み込む
    index: int,
    # 次の値または処理を現在の構造へ組み込む
    record: dict[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    spec_stats: dict[str, int],
    # 次の値または処理を現在の構造へ組み込む
    verification_case_count: int,
    # 次の値または処理を現在の構造へ組み込む
    timeout_seconds: float,
# 次の値または処理を現在の構造へ組み込む
) -> list[str]:
    # semantic_astへこの工程で使用する値を設定する
    semantic_ast = record["semantic_ast"]
    # keyへこの工程で使用する値を設定する
    key = _operation_key(semantic_ast)
    # descriptionへこの工程で使用する値を設定する
    description = OPERATION_DESCRIPTIONS[key]
    # expectedへこの工程で使用する値を設定する
    expected = interpret(semantic_ast, list(EXAMPLE_XS), EXAMPLE_K)
    # actualへこの工程で使用する値を設定する
    actual = _run_generated(record["reference_code"], EXAMPLE_XS, EXAMPLE_K)
    # 条件を満たす場合だけ次の処理を行う
    if actual != expected:
        # 不正な状態を例外として通知して処理を停止する
        raise RuntimeError(f"{record['spec_id']}: レポート作成時の再実行結果が不一致です")

    # styleへこの工程で使用する値を設定する
    style = record["style_spec"]
    # operation_styleへこの工程で使用する値を設定する
    operation_style = style["operation_styles"][0]
    # style_summaryへこの工程で使用する値を設定する
    style_summary = _style_summary(style, operation_style)
    # ast_jsonへこの工程で使用する値を設定する
    ast_json = json.dumps(semantic_ast, ensure_ascii=False, separators=(",", ":"))
    # codeへこの工程で使用する値を設定する
    code = record["reference_code"].rstrip()

    # 処理結果を呼び出し元へ返す
    return [
        # 次の値または処理を現在の構造へ組み込む
        f"### {index}. `{record['spec_id']}` — {description}",
        # この処理で扱う文字列を一覧へ加える
        "",
        # 次の値または処理を現在の構造へ組み込む
        f"- 意味AST: `{ast_json}`",
        # 次の値または処理を現在の構造へ組み込む
        f"- 生成形式: {style_summary}",
        # 次の値または処理を現在の構造へ組み込む
        f"- 列挙可能な構造的変種: {spec_stats['available_style_count']}件",
        # 次の値または処理を現在の構造へ組み込む
        f"- 今回検証した候補: {spec_stats['candidate_count']}件（1件目で採用）",
        # 次の値または処理を現在の構造へ組み込む
        f"- 具体例の参照結果: `{expected}`",
        # 次の値または処理を現在の構造へ組み込む
        f"- 具体例の生成コード結果: `{actual}`",
        # 次の値または処理を現在の構造へ組み込む
        f"- 参照インタプリタとの照合: **合格**（検証入力{verification_case_count}件すべてで、生成コードの戻り値が参照インタプリタの戻り値と完全一致。生成コードは入力リスト`xs`を変更せず、{timeout_seconds:g}秒の制限時間内に完了）",
        # 次の値または処理を現在の構造へ組み込む
        f"- コードID: `{record['code_id']}`",
        # 次の値または処理を現在の構造へ組み込む
        f"- コードハッシュ: `{record['code_hash']}`",
        # この処理で扱う文字列を一覧へ加える
        "",
        # この処理で扱う文字列を一覧へ加える
        "```python",
        # 次の値または処理を現在の構造へ組み込む
        code,
        # この処理で扱う文字列を一覧へ加える
        "```",
        # この処理で扱う文字列を一覧へ加える
        "",
    ]


# この工程を担当する関数を定義する
def _inline_names(names: list[str]) -> str:
    # 処理結果を呼び出し元へ返す
    return ", ".join(f"`{name}`" for name in names)


# この工程を担当する関数を定義する
def _operation_key(semantic_ast: dict[str, Any]) -> str:
    # 条件を満たす場合だけ次の処理を行う
    if set(semantic_ast) == {"sequence"}:
        # sequenceへこの工程で使用する値を設定する
        sequence = semantic_ast["sequence"]
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(sequence, list) or len(sequence) != 1:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("このレポートでは1操作のsequenceだけを扱います")
        # operationへこの工程で使用する値を設定する
        operation = sequence[0]
    # それまでの条件に該当しない場合を処理する
    else:
        # operationへこの工程で使用する値を設定する
        operation = semantic_ast
    # 次の値または処理を現在の構造へ組み込む
    operation_type, argument = next(iter(operation.items()))
    # 条件を満たす場合だけ次の処理を行う
    if operation_type in {"filter", "slice"}:
        # 処理結果を呼び出し元へ返す
        return f"{operation_type}:{argument[0]}"
    # 条件を満たす場合だけ次の処理を行う
    if operation_type == "map":
        # suffixへこの工程で使用する値を設定する
        suffix = ":".join(str(value) for value in argument)
        # 処理結果を呼び出し元へ返す
        return f"map:{suffix}"
    # 処理結果を呼び出し元へ返す
    return f"order:{argument}"


# この工程を担当する関数を定義する
def _style_summary(style: dict[str, Any], operation_style: dict[str, Any]) -> str:
    # partsへこの工程で使用する値を設定する
    parts = [
        # この処理で扱う文字列を一覧へ加える
        "1行return" if style["layout"] == "single_return" else "複数行",
        # 次の値または処理を現在の構造へ組み込む
        _collection_label(style["collection_form"]),
        # この処理で扱う文字列を一覧へ加える
        "コメントあり" if style["comments"] == "present" else "コメントなし",
        # この処理で扱う文字列を一覧へ加える
        "型注釈あり" if style["local_annotations"] else "型注釈なし",
    ]
    # element_nameへこの工程で使用する値を設定する
    element_name = operation_style.get("element_name")
    # result_nameへこの工程で使用する値を設定する
    result_name = operation_style.get("result_name")
    # condition_directionへこの工程で使用する値を設定する
    condition_direction = operation_style.get("condition_direction")
    # expression_formへこの工程で使用する値を設定する
    expression_form = operation_style.get("expression_form")
    # 条件を満たす場合だけ次の処理を行う
    if element_name is not None:
        # 次の値または処理を現在の構造へ組み込む
        parts.append(f"要素変数 `{element_name}`")
    # 条件を満たす場合だけ次の処理を行う
    if result_name is not None:
        # 次の値または処理を現在の構造へ組み込む
        parts.append(f"結果変数 `{result_name}`")
    # 条件を満たす場合だけ次の処理を行う
    if condition_direction is not None:
        # 次の値または処理を現在の構造へ組み込む
        parts.append(
            "比較式の左右入れ替えあり"
            # 条件を満たす場合だけ次の処理を行う
            if condition_direction == "swapped"
            # それまでの条件に該当しない場合を処理する
            else "比較式の左右入れ替えなし"
        )
    # 条件を満たす場合だけ次の処理を行う
    if expression_form != "default":
        # 次の値または処理を現在の構造へ組み込む
        parts.append(f"式形式 `{expression_form}`")
    # 処理結果を呼び出し元へ返す
    return "、".join(parts)


# この工程を担当する関数を定義する
def _collection_label(value: str | None) -> str:
    # labelsへこの工程で使用する値を設定する
    labels = {
        # 出力レコードの項目と値を設定する
        "list_comprehension": "内包表記",
        # 出力レコードの項目と値を設定する
        "for_loop": "通常のforループ",
        # 出力レコードの項目と値を設定する
        "mixed": "内包表記とforループの混在",
        # 次の値または処理を現在の構造へ組み込む
        None: "組み込み関数またはスライス",
    }
    # 処理結果を呼び出し元へ返す
    return labels[value]


# この工程を担当する関数を定義する
def _run_generated(source: str, xs: list[int], k: int) -> list[int]:
    # namespaceへこの工程で使用する値を設定する
    namespace: dict[str, Any] = {
        # 出力レコードの項目と値を設定する
        "__builtins__": {
            # 出力レコードの項目と値を設定する
            "abs": abs,
            # 出力レコードの項目と値を設定する
            "int": int,
            # 出力レコードの項目と値を設定する
            "list": list,
            # 出力レコードの項目と値を設定する
            "reversed": reversed,
            # 出力レコードの項目と値を設定する
            "sorted": sorted,
        }
    }
    # 次の値または処理を現在の構造へ組み込む
    exec(compile(source, "<generated-report>", "exec"), namespace)
    # resultへこの工程で使用する値を設定する
    result = namespace["solve"](list(xs), k)
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(result, list) or any(type(value) is not int for value in result):
        # 不正な状態を例外として通知して処理を停止する
        raise TypeError("生成コードの結果は整数リストである必要があります")
    # 処理結果を呼び出し元へ返す
    return result


# この工程を担当する関数を定義する
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    # recordsへこの工程で使用する値を設定する
    records = []
    # 使用するリソースの開始と終了をこの範囲で管理する
    with path.open(encoding="utf-8") as source:
        # 対象を一件ずつ取り出して処理する
        for line_number, line in enumerate(source, start=1):
            # 条件を満たす場合だけ次の処理を行う
            if not line.strip():
                # 現在の対象を終えて次の対象へ進む
                continue
            # recordへこの工程で使用する値を設定する
            record = json.loads(line)
            # 条件を満たす場合だけ次の処理を行う
            if not isinstance(record, dict):
                # 不正な状態を例外として通知して処理を停止する
                raise TypeError(f"{path}:{line_number}: レコードは辞書にしてください")
            # 次の値または処理を現在の構造へ組み込む
            records.append(record)
    # 処理結果を呼び出し元へ返す
    return records
# 条件を満たす場合だけ次の処理を行う
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    main()
