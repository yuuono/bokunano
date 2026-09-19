"""参照インタプリタで24操作と全組み合わせASTを実行確認する。"""

# 参照実装が生成対象の表現へ戻っていないかPython構文木で確認するために使う
import ast
# JSONL形式のデータを読み書きするために使う
import json
# 操作数ごとの件数を数えるために使う
from collections import Counter
# OSに依存しないパス操作のために使う
from pathlib import Path
# import探索パスを書き換えるために使う
import sys


# このファイルの位置からリポジトリのルートディレクトリを求める
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# ルート直下のモジュールをimportできるように探索パスの先頭に追加する
sys.path.insert(0, str(PROJECT_ROOT))

# 検証対象の参照インタプリタ本体を読み込む（sys.path追加後なのでここでimportする）
from reference_interpreter import interpret  # noqa: E402


# 24個の単独操作ASTが入ったファイル
ATOMIC_PATH = PROJECT_ROOT / "data/semantic_asts/atomic_semantic_asts.jsonl"
# 1〜3操作の組み合わせASTが入ったファイル
COMBINED_PATH = PROJECT_ROOT / "data/semantic_asts/combined_semantic_asts.jsonl"
# 生成対象のコードとは別経路で実装する参照インタプリタ本体
REFERENCE_PATH = PROJECT_ROOT / "reference_interpreter.py"

# 単独操作の検証に使う入力リスト（正・負・0を混ぜてある）
ATOMIC_XS = [3, -4, 6, 0, -1, 4, 2, -3, 1]
# 単独操作の検証に使うkの値
ATOMIC_K = 4
# spec_idごとの期待出力（手計算した正解）
ATOMIC_EXPECTED = {
    # filter even: 偶数だけを残す
    "atomic-000001": [-4, 6, 0, 4, 2],
    # filter odd: 奇数だけを残す
    "atomic-000002": [3, -1, -3, 1],
    # filter gt_k: 4より大きい要素だけを残す
    "atomic-000003": [6],
    # filter ge_k: 4以上の要素だけを残す
    "atomic-000004": [6, 4],
    # filter lt_k: 4より小さい要素だけを残す
    "atomic-000005": [3, -4, 0, -1, 2, -3, 1],
    # filter le_k: 4以下の要素だけを残す
    "atomic-000006": [3, -4, 0, -1, 4, 2, -3, 1],
    # filter multiple_of_k: 4の倍数だけを残す
    "atomic-000007": [-4, 0, 4],
    # filter positive: 正の数だけを残す
    "atomic-000008": [3, 6, 4, 2, 1],
    # filter negative: 負の数だけを残す
    "atomic-000009": [-4, -1, -3],
    # filter zero: 0だけを残す
    "atomic-000010": [0],
    # map add_k: 各要素に4を足す
    "atomic-000011": [7, 0, 10, 4, 3, 8, 6, 1, 5],
    # map sub_k: 各要素から4を引く
    "atomic-000012": [-1, -8, 2, -4, -5, 0, -2, -7, -3],
    # map mul_k: 各要素に4を掛ける
    "atomic-000013": [12, -16, 24, 0, -4, 16, 8, -12, 4],
    # map mul_const 2: 各要素を2倍する
    "atomic-000014": [6, -8, 12, 0, -2, 8, 4, -6, 2],
    # map mul_const 3: 各要素を3倍する
    "atomic-000015": [9, -12, 18, 0, -3, 12, 6, -9, 3],
    # map negate: 各要素の符号を反転する
    "atomic-000016": [-3, 4, -6, 0, 1, -4, -2, 3, -1],
    # map abs: 各要素を絶対値にする
    "atomic-000017": [3, 4, 6, 0, 1, 4, 2, 3, 1],
    # map square: 各要素を2乗する
    "atomic-000018": [9, 16, 36, 0, 1, 16, 4, 9, 1],
    # order ascending: 昇順に並べ替える
    "atomic-000019": [-4, -3, -1, 0, 1, 2, 3, 4, 6],
    # order descending: 降順に並べ替える
    "atomic-000020": [6, 4, 3, 2, 1, 0, -1, -3, -4],
    # order reverse: 並び順を逆にする
    "atomic-000021": [1, -3, 2, 4, -1, 0, 6, -4, 3],
    # slice take_first_k: 先頭から4個取り出す
    "atomic-000022": [3, -4, 6, 0],
    # slice take_last_k: 末尾から4個取り出す
    "atomic-000023": [4, 2, -3, 1],
    # slice every_other: 1つ飛ばしで取り出す
    "atomic-000024": [3, 6, -1, 2, 1],
}

# 組み合わせASTを流し込む(xs, k)の検証入力セット
COMBINATION_CASES = (
    # 空リスト: 要素がなくても落ちないことを確認する
    ([], 1),
    # 0のみ: ゼロ絡みの分岐を通す
    ([0], 1),
    # 1要素かつk=10: kが要素数より大きい場合を通す
    ([5], 10),
    # 負数・0・正数を等間隔で並べた対称なケース
    ([-8, -4, 0, 4, 8], 2),
    # 奇数のみ: 偶数フィルタで空になる経路を通す
    ([1, 3, 5, 7, 9], 4),
    # 同じ値の重複: 並べ替えの安定性や重複処理を通す
    ([2, 2, 2, 2], 3),
    # 値域の端(-100と100)を含む幅広いケース
    ([-100, -10, -3, -2, -1, 0, 1, 2, 3, 10, 100], 10),
    # 上限の20要素: 長さ制限ぎりぎりのケース
    ([9, -9, 8, -8, 7, -7, 6, -6, 5, -5, 4, -4, 3, -3, 2, -2, 1, -1, 0, 10], 5),
)


def _call_name(node: ast.Call):
    """単純な関数呼び出しを検査用の名前へ変換する。"""

    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        return f"{node.func.value.id}.{node.func.attr}"
    return None


def verify_implementation_separation() -> None:
    """4個の操作ハンドラが規定した独立経路を守っているか確認する。"""

    source = REFERENCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(REFERENCE_PATH))
    handler_names = {"_apply_filter", "_apply_map", "_apply_order", "_apply_slice"}
    handlers = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in handler_names
    }
    if set(handlers) != handler_names:
        missing = sorted(handler_names - set(handlers))
        raise AssertionError(f"参照実装の操作ハンドラが不足しています: {missing}")

    forbidden_nodes = (ast.Lambda, ast.ListComp, ast.Slice)
    forbidden_calls = {
        "abs",
        "compile",
        "eval",
        "exec",
        "heapq.nlargest",
        "heapq.nsmallest",
        "reversed",
        "sorted",
    }
    forbidden_binary_operators = (ast.Add, ast.Sub, ast.Mult, ast.Pow, ast.Mod)
    required_calls = {
        "_apply_filter": {"itertools.compress", "map"},
        "_apply_map": {"map"},
        "_apply_order": {"deque", "heapq.heapify", "heapq.heappop"},
        "_apply_slice": {"deque", "itertools.islice"},
    }

    for handler_name, handler in handlers.items():
        actual_calls = {
            call_name
            for node in ast.walk(handler)
            if isinstance(node, ast.Call)
            if (call_name := _call_name(node)) is not None
        }
        missing_calls = required_calls[handler_name] - actual_calls
        if missing_calls:
            raise AssertionError(
                f"{handler_name} が規定の参照経路を使用していません: "
                f"{sorted(missing_calls)}"
            )

        for node in ast.walk(handler):
            if isinstance(node, forbidden_nodes):
                raise AssertionError(
                    f"{handler_name} が生成対象の構文を直接使用しています: "
                    f"{type(node).__name__}"
                )
            if isinstance(node, ast.Call) and _call_name(node) in forbidden_calls:
                raise AssertionError(
                    f"{handler_name} が禁止された関数を呼んでいます: "
                    f"{_call_name(node)}"
                )
            if isinstance(node, ast.BinOp) and isinstance(
                node.op, forbidden_binary_operators
            ):
                raise AssertionError(
                    f"{handler_name} が生成対象の演算子を直接使用しています: "
                    f"{type(node.op).__name__}"
                )
            if handler_name in {"_apply_filter", "_apply_map"} and isinstance(
                node, ast.For
            ):
                raise AssertionError(
                    f"{handler_name} が集約にforループを使用しています"
                )


def load_jsonl(path: Path) -> list[dict]:
    # UTF-8で開いて1行ずつ読む
    with path.open(encoding="utf-8") as source:
        # 空行を飛ばしつつ各行をJSONとして辞書のリストにする
        return [json.loads(line) for line in source if line.strip()]


def verify_atomic_operations(records: list[dict]) -> None:
    # 単独操作は24件ちょうどのはず
    if len(records) != 24:
        # 件数が違えば期待値の対応が崩れるので中断する
        raise AssertionError(f"単独操作の件数が不正です: {len(records)}")

    # 1件ずつ実行して期待結果と比べる
    for record in records:
        # 破壊的変更を検出するため、渡す用のコピーを作る
        original = list(ATOMIC_XS)
        # 参照インタプリタでASTを実行する
        actual = interpret(record["semantic_ast"], original, ATOMIC_K)
        # そのspec_idに対応する期待出力を引く
        expected = ATOMIC_EXPECTED[record["spec_id"]]
        # 実行結果と期待出力が一致するか確認する
        if actual != expected:
            # 不一致なら実際と期待の両方を示して中断する
            raise AssertionError(
                f"{record['spec_id']} の結果が不一致です: {actual} != {expected}"
            )
        # 渡したリストが書き換えられていないか確認する
        if original != ATOMIC_XS:
            # 入力を破壊する実装は仕様違反なので中断する
            raise AssertionError(f"{record['spec_id']} が入力xsを変更しました")


def verify_combinations(records: list[dict]) -> Counter:
    # 24 + 24*23 + 24*23*22 = 12,720件のはず
    if len(records) != 12_720:
        # 件数が違えば生成側が壊れているので中断する
        raise AssertionError(f"組み合わせASTの件数が不正です: {len(records)}")

    # 操作数ごとの件数を集計するカウンタ
    operation_counts = Counter()
    # 組み合わせASTを1件ずつ実行する
    for record in records:
        # 順序付きの操作リストを取り出す
        sequence = record["semantic_ast"]["sequence"]
        # この件の操作数(1〜3)を集計に加える
        operation_counts[len(sequence)] += 1

        # 用意した全検証入力でASTを実行する
        for xs, k in COMBINATION_CASES:
            # 破壊的変更を検出するため、渡す用のコピーを作る
            original = list(xs)
            # 参照インタプリタでASTを実行する
            actual = interpret(record["semantic_ast"], original, k)
            # 出力がint（boolを除く）だけのリストかを確認する
            if not isinstance(actual, list) or any(type(x) is not int for x in actual):
                # 型が崩れていれば中断する
                raise AssertionError(f"{record['spec_id']} の出力が整数リストではありません")
            # 渡したリストが書き換えられていないか確認する
            if original != xs:
                # 入力を破壊する実装は仕様違反なので中断する
                raise AssertionError(f"{record['spec_id']} が入力xsを変更しました")

    # 順列で数えたときの操作数ごとの理論値
    expected_counts = Counter({1: 24, 2: 552, 3: 12_144})
    # 実際の内訳が理論値どおりかを確認する
    if operation_counts != expected_counts:
        # 内訳が違えば生成側が壊れているので中断する
        raise AssertionError(f"操作数の内訳が不正です: {operation_counts}")

    # 呼び出し元で表示するため集計結果を返す
    return operation_counts


def main() -> None:
    # 参照側が規定した実装経路を守っていることを確認する
    verify_implementation_separation()
    # 単独操作ASTを読み込む
    atomic_records = load_jsonl(ATOMIC_PATH)
    # 組み合わせASTを読み込む
    combined_records = load_jsonl(COMBINED_PATH)

    # 24個の単独操作が期待どおり動くかを検証する
    verify_atomic_operations(atomic_records)
    # 全組み合わせASTを実行し、操作数の内訳を受け取る
    operation_counts = verify_combinations(combined_records)

    # 実装分離の検証が通ったことを表示する
    print("参照実装: 規定した独立経路を確認")
    # 単独操作の検証が通ったことを表示する
    print("24個の単独操作: 期待結果と一致")
    # 1操作ASTの確認件数を表示する
    print(f"1操作AST: {operation_counts[1]}件を実行確認")
    # 2操作ASTの確認件数を表示する
    print(f"2操作AST: {operation_counts[2]}件を実行確認")
    # 3操作ASTの確認件数を表示する
    print(f"3操作AST: {operation_counts[3]}件を実行確認")
    # 組み合わせASTの合計確認件数を表示する
    print(f"組み合わせAST合計: {sum(operation_counts.values())}件を実行確認")
    # 1件あたり何種類の入力で確認したかを表示する
    print(f"各組み合わせASTの確認入力数: {len(COMBINATION_CASES)}件")


# スクリプトとして直接実行されたときだけmainを走らせる
if __name__ == "__main__":
    main()
