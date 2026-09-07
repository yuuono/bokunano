"""Boku1-nanoの意味ASTを直接実行する参照インタプリタ。"""


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


def _single_name(argument: object, operation_type: str) -> str:
    if (
        # 引数はリスト形式でなければならない
        not isinstance(argument, list)
        # 引数なしの操作は要素1つだけ
        or len(argument) != 1
        # 唯一の要素は操作名の文字列
        or not isinstance(argument[0], str)
    ):
        # 形式違反はどの操作種別かを添えてエラーにする
        raise ValueError(f"{operation_type}の形式が不正です: {argument!r}")
    # 検証済みの操作名を返す
    return argument[0]


def _apply_filter(argument: object, xs: list[int], k: int) -> list[int]:
    # 引数を検証してfilterの述語名を取得する
    name = _single_name(argument, "filter")

    # 述語名から判定関数への対応表
    predicates = {
        # 偶数だけ残す（Pythonの%は負数でも0か1を返す）
        "even": lambda x: x % 2 == 0,
        # 奇数だけ残す
        "odd": lambda x: x % 2 != 0,
        # kより大きい要素だけ残す
        "gt_k": lambda x: x > k,
        # k以上の要素だけ残す
        "ge_k": lambda x: x >= k,
        # kより小さい要素だけ残す
        "lt_k": lambda x: x < k,
        # k以下の要素だけ残す
        "le_k": lambda x: x <= k,
        # kの倍数だけ残す（kは1以上なのでゼロ除算はない）
        "multiple_of_k": lambda x: x % k == 0,
        # 正の数だけ残す（0は除く）
        "positive": lambda x: x > 0,
        # 負の数だけ残す
        "negative": lambda x: x < 0,
        # 0だけ残す
        "zero": lambda x: x == 0,
    }

    # 対応表にない述語名は受け付けない
    if name not in predicates:
        # 未知の述語名はエラーにする
        raise ValueError(f"未知のfilter操作です: {name}")
    # 述語を満たす要素だけを元の順序で集めた新しいリストを返す
    return [x for x in xs if predicates[name](x)]


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
        # 全要素を定数倍した新しいリストを返す
        return [x * multiplier for x in xs]

    # mul_const以外は定数を取らないので要素1つだけ
    if len(argument) != 1:
        # 余分な要素があればエラーにする
        raise ValueError(f"mapの形式が不正です: {argument!r}")

    # 変換名から変換関数への対応表
    transforms = {
        # 各要素にkを足す
        "add_k": lambda x: x + k,
        # 各要素からkを引く
        "sub_k": lambda x: x - k,
        # 各要素にkを掛ける
        "mul_k": lambda x: x * k,
        # 各要素の符号を反転する
        "negate": lambda x: -x,
        # 各要素の絶対値を取る（組み込み関数をそのまま使う）
        "abs": abs,
        # 各要素を2乗する
        "square": lambda x: x * x,
    }

    # 対応表にない変換名は受け付けない
    if name not in transforms:
        # 未知の変換名はエラーにする
        raise ValueError(f"未知のmap操作です: {name}")
    # 全要素に変換を適用した新しいリストを返す
    return [transforms[name](x) for x in xs]


def _apply_order(argument: object, xs: list[int]) -> list[int]:
    # 昇順に並べ替える
    if argument == "ascending":
        # sortedは新しいリストを返すのでxsは変更されない
        return sorted(xs)
    # 降順に並べ替える
    if argument == "descending":
        # reverse=Trueで大きい順にする
        return sorted(xs, reverse=True)
    # 並べ替えではなく現在の順序を逆にする
    if argument == "reverse":
        # reversedのイテレータをリストに変換して返す
        return list(reversed(xs))
    # 3種類のいずれでもなければエラーにする
    raise ValueError(f"未知のorder操作です: {argument}")


def _apply_slice(argument: object, xs: list[int], k: int) -> list[int]:
    # 引数を検証してsliceの操作名を取得する
    name = _single_name(argument, "slice")

    # 先頭からk個取り出す
    if name == "take_first_k":
        # 要素数がkより少なければあるだけ返る
        return xs[:k]
    # 末尾からk個取り出す
    if name == "take_last_k":
        # kは1以上なので添字が0になって全体が返ることはない
        return xs[-k:]
    # 1つ飛ばしで取り出す
    if name == "every_other":
        # 添字0,2,4...の要素を集める
        return xs[::2]
    # 3種類のいずれでもなければエラーにする
    raise ValueError(f"未知のslice操作です: {name}")
