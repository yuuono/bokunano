"""Boku1-nanoの意味ASTを直接実行する参照インタプリタ。

生成対象の ``solve`` 関数とは実装経路を分けるため、値の操作には
``operator``、``itertools``、``heapq``、``collections.deque`` を使う。
コード生成器のテンプレート、対応表、補助関数は共有しない。
"""

# 必要な定義を対象モジュールから読み込む
from collections import deque
# この処理で使う標準または外部モジュールを読み込む
import heapq
# この処理で使う標準または外部モジュールを読み込む
import itertools
# この処理で使う標準または外部モジュールを読み込む
import operator


# この工程を担当する関数を定義する
def interpret(semantic_ast: dict, xs: list[int], k: int) -> list[int]:
    """意味ASTを先頭から実行し、結果の整数リストを返す。"""

    # 入力xsとkが仕様の範囲内かを先に検証する
    _validate_inputs(xs, k)

    # キーが"sequence"だけなら複数操作を並べたASTと判断する
    if set(semantic_ast) == {"sequence"}:
        # 実行すべき操作のリストを取り出す
        sequence = semantic_ast["sequence"]
        # リスト型かつ1〜3要素かを確認する
        if not isinstance(sequence, list) or not 1 <= len(sequence) <= 3:
            # 条件を満たさなければエラーにする
            raise ValueError("sequenceには1〜3個の操作が必要です")
    # それまでの条件に該当しない場合を処理する
    else:
        # 単独操作のASTは1要素のリストに包んで同じ処理に流す
        sequence = [semantic_ast]

    # 呼び出し元のxsを壊さないようにコピーを作業用にする
    result = list(xs)
    # 操作を先頭から順に取り出す
    for operation in sequence:
        # 直前の結果を入力として次の操作を適用する
        result = _apply_operation(operation, result, k)

    # すべての操作を適用し終えたリストを返す
    return result


# この工程を担当する関数を定義する
def _validate_inputs(xs: list[int], k: int) -> None:
    # xsがリスト型でなければ扱えない
    if not isinstance(xs, list):
        # 型が違う場合はTypeErrorにする
        raise TypeError("xsはリストである必要があります")
    # 仕様上xsの長さは0〜20に限られる
    if not 0 <= len(xs) <= 20:
        # 長さが範囲外ならエラーにする
        raise ValueError("xsの長さは0〜20である必要があります")
    # bool混入を排除しつつ各要素の値域を確認する
    if any(type(value) is not int or not -100 <= value <= 100 for value in xs):
        # 要素の型か値域が不正ならエラーにする
        raise ValueError("xsの各要素は-100〜100の整数である必要があります")
    # kも厳密にint型かつ1〜10であることを求める
    if type(k) is not int or not 1 <= k <= 10:
        # kが不正ならエラーにする
        raise ValueError("kは1〜10の整数である必要があります")


# この工程を担当する関数を定義する
def _apply_operation(operation: dict, xs: list[int], k: int) -> list[int]:
    # 1操作は「キー1つの辞書」で表現される
    if not isinstance(operation, dict) or len(operation) != 1:
        # 形式が違えば内容を添えてエラーにする
        raise ValueError(f"操作の形式が不正です: {operation!r}")

    # 唯一のキーと値を操作種別と引数として取り出す
    operation_type, argument = next(iter(operation.items()))

    # 条件で要素を絞り込む操作
    if operation_type == "filter":
        # filter用のハンドラに委譲する
        return _apply_filter(argument, xs, k)
    # 各要素を変換する操作
    if operation_type == "map":
        # map用のハンドラに委譲する
        return _apply_map(argument, xs, k)
    # 並び順を変える操作
    if operation_type == "order":
        # orderはkを使わないのでxsのみ渡す
        return _apply_order(argument, xs)
    # 位置で切り出す操作
    if operation_type == "slice":
        # slice用のハンドラに委譲する
        return _apply_slice(argument, xs, k)

    # 4種類のいずれでもなければエラーにする
    raise ValueError(f"未知の操作です: {operation_type}")


# この工程を担当する関数を定義する
def _single_name(argument: object, operation_type: str) -> str:
    # 条件を満たす場合だけ次の処理を行う
    if (
        # 引数はリスト形式でなければならない
        not isinstance(argument, list)
        # 引数なしの操作は要素1つだけ
        or len(argument) != 1
        # 唯一の要素は操作名の文字列
        or not isinstance(argument[0], str)
    # 次の値または処理を現在の構造へ組み込む
    ):
        # 形式違反はどの操作種別かを添えてエラーにする
        raise ValueError(f"{operation_type}の形式が不正です: {argument!r}")
    # 検証済みの操作名を返す
    return argument[0]


# この工程を担当する関数を定義する
def _apply_filter(argument: object, xs: list[int], k: int) -> list[int]:
    # 引数を検証してfilterの述語名を取得する
    name = _single_name(argument, "filter")

    # 選択子の列を作り、compressで元の順序を保ったまま要素を選ぶ
    if name == "even":
        # remaindersへこの工程で使用する値を設定する
        remainders = map(operator.mod, xs, itertools.repeat(2))
        # selectorsへこの工程で使用する値を設定する
        selectors = map(operator.not_, remainders)
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "odd":
        # selectorsへこの工程で使用する値を設定する
        selectors = map(operator.mod, xs, itertools.repeat(2))
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "gt_k":
        # selectorsへこの工程で使用する値を設定する
        selectors = map(operator.gt, xs, itertools.repeat(k))
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "ge_k":
        # selectorsへこの工程で使用する値を設定する
        selectors = map(operator.ge, xs, itertools.repeat(k))
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "lt_k":
        # selectorsへこの工程で使用する値を設定する
        selectors = map(operator.lt, xs, itertools.repeat(k))
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "le_k":
        # selectorsへこの工程で使用する値を設定する
        selectors = map(operator.le, xs, itertools.repeat(k))
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "multiple_of_k":
        # kは1以上なのでゼロ除算はない
        remainders = map(operator.mod, xs, itertools.repeat(k))
        # selectorsへこの工程で使用する値を設定する
        selectors = map(operator.not_, remainders)
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "positive":
        # selectorsへこの工程で使用する値を設定する
        selectors = map(operator.gt, xs, itertools.repeat(0))
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "negative":
        # selectorsへこの工程で使用する値を設定する
        selectors = map(operator.lt, xs, itertools.repeat(0))
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "zero":
        # selectorsへこの工程で使用する値を設定する
        selectors = map(operator.eq, xs, itertools.repeat(0))
    # それまでの条件に該当しない場合を処理する
    else:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"未知のfilter操作です: {name}")

    # 処理結果を呼び出し元へ返す
    return list(itertools.compress(xs, selectors))


# この工程を担当する関数を定義する
def _apply_map(argument: object, xs: list[int], k: int) -> list[int]:
    # mapの引数は空でないリストでなければならない
    if not isinstance(argument, list) or not argument:
        # 形式違反はエラーにする
        raise ValueError(f"mapの形式が不正です: {argument!r}")

    # 先頭要素が変換名
    name = argument[0]
    # mul_constだけは定数引数を1つ取る特別扱い
    if name == "mul_const":
        # 要素数2かつ定数は2か3に限る
        if len(argument) != 2 or argument[1] not in (2, 3):
            # 定数が仕様外ならエラーにする
            raise ValueError(f"mul_constの形式が不正です: {argument!r}")
        # 掛ける定数を取り出す
        multiplier = argument[1]
        # 2つのイテラブルをmapへ渡し、各要素を定数倍する
        return list(map(operator.mul, xs, itertools.repeat(multiplier)))

    # mul_const以外は定数を取らないので要素1つだけ
    if len(argument) != 1:
        # 余分な要素があればエラーにする
        raise ValueError(f"mapの形式が不正です: {argument!r}")

    # lambdaや内包表記を使わず、operatorとmapで各要素を変換する
    if name == "add_k":
        # mappedへこの工程で使用する値を設定する
        mapped = map(operator.add, xs, itertools.repeat(k))
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "sub_k":
        # xsを第1引数にすることで、k - xではなくx - kにする
        mapped = map(operator.sub, xs, itertools.repeat(k))
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "mul_k":
        # mappedへこの工程で使用する値を設定する
        mapped = map(operator.mul, xs, itertools.repeat(k))
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "negate":
        # mappedへこの工程で使用する値を設定する
        mapped = map(operator.neg, xs)
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "abs":
        # mappedへこの工程で使用する値を設定する
        mapped = map(operator.abs, xs)
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif name == "square":
        # mappedへこの工程で使用する値を設定する
        mapped = map(operator.pow, xs, itertools.repeat(2))
    # それまでの条件に該当しない場合を処理する
    else:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"未知のmap操作です: {name}")

    # 処理結果を呼び出し元へ返す
    return list(mapped)


# この工程を担当する関数を定義する
def _apply_order(argument: object, xs: list[int]) -> list[int]:
    # 昇順に並べ替える
    if argument == "ascending":
        # nsmallestは内部でsortedへ委譲するため使わず、明示的にヒープを空にする
        heap = list(xs)
        # 次の値または処理を現在の構造へ組み込む
        heapq.heapify(heap)
        # resultへこの工程で使用する値を設定する
        result = []
        # 条件を満たす間は処理を繰り返す
        while heap:
            # 次の値または処理を現在の構造へ組み込む
            result.append(heapq.heappop(heap))
        # 処理結果を呼び出し元へ返す
        return result
    # 降順に並べ替える
    if argument == "descending":
        # 符号反転した値の最小ヒープを使い、元の値を大きい順に取り出す
        heap = list(map(operator.neg, xs))
        # 次の値または処理を現在の構造へ組み込む
        heapq.heapify(heap)
        # resultへこの工程で使用する値を設定する
        result = []
        # 条件を満たす間は処理を繰り返す
        while heap:
            # 次の値または処理を現在の構造へ組み込む
            result.append(operator.neg(heapq.heappop(heap)))
        # 処理結果を呼び出し元へ返す
        return result
    # 並べ替えではなく現在の順序を逆にする
    if argument == "reverse":
        # スライスやreversedを使わず、末尾から順に取り出す
        remaining = deque(xs)
        # resultへこの工程で使用する値を設定する
        result = []
        # 条件を満たす間は処理を繰り返す
        while remaining:
            # 次の値または処理を現在の構造へ組み込む
            result.append(remaining.pop())
        # 処理結果を呼び出し元へ返す
        return result
    # 3種類のいずれでもなければエラーにする
    raise ValueError(f"未知のorder操作です: {argument}")


# この工程を担当する関数を定義する
def _apply_slice(argument: object, xs: list[int], k: int) -> list[int]:
    # 引数を検証してsliceの操作名を取得する
    name = _single_name(argument, "slice")

    # 先頭からk個取り出す
    if name == "take_first_k":
        # isliceは要素数がkより少なければあるだけ返す
        return list(itertools.islice(xs, 0, k))
    # 末尾からk個取り出す
    if name == "take_last_k":
        # maxlen付きdequeに、末尾側の最大k要素だけを保持させる
        return list(deque(xs, maxlen=k))
    # 1つ飛ばしで取り出す
    if name == "every_other":
        # 位置0からstep=2で取得する
        return list(itertools.islice(xs, 0, None, 2))
    # 3種類のいずれでもなければエラーにする
    raise ValueError(f"未知のslice操作です: {name}")
