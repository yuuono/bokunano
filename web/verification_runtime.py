"""Compare the frozen meaning with the actual generated solve, inside a disposable worker."""
import ast
import builtins
import json
import sys

import reference_interpreter as reference


def _bounded_range(*args):
    result = range(*args)
    if len(result) > 1000:
        raise ValueError("rangeの上限（1000）を超えました")
    return result


SAFE_BUILTINS = {name: getattr(builtins, name) for name in (
    "abs", "all", "any", "bool", "enumerate", "int", "len", "list", "max", "min",
    "reversed", "sorted", "sum", "tuple", "zip",
)}
SAFE_BUILTINS["range"] = _bounded_range
ALLOWED_NODES = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
    ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For, ast.If, ast.IfExp,
    ast.Break, ast.Continue, ast.Pass, ast.Expr,
    ast.Name, ast.Load, ast.Store, ast.Constant, ast.List, ast.Tuple,
    ast.ListComp, ast.GeneratorExp, ast.comprehension, ast.Subscript, ast.Slice,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call, ast.keyword,
    ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
)


def _checked_code(source):
    if not isinstance(source, str) or len(source) > 16000:
        raise ValueError("コードが長すぎます")
    tree = ast.parse(source, filename="generated_solve.py")
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef) or tree.body[0].name != "solve":
        raise ValueError("solve関数1つだけを実行できます")
    function = tree.body[0]
    if function.decorator_list or getattr(function, "type_params", []):
        raise ValueError("デコレータ・型パラメータは実行できません")
    args = function.args
    if [arg.arg for arg in args.args] != ["xs", "k"] or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg:
        raise ValueError("solve(xs, k)形式の関数が必要です")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"この検証では実行できない構文です: {type(node).__name__}")
        if isinstance(node, ast.FunctionDef) and node is not function:
            raise ValueError("入れ子の関数は実行できません")
        if isinstance(node, (ast.Name, ast.arg)) and "__" in (node.id if isinstance(node, ast.Name) else node.arg):
            raise ValueError("特殊名へのアクセスは実行できません")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in SAFE_BUILTINS):
            raise ValueError("呼び出せるのはリスト処理用の組み込み関数だけです")
        if isinstance(node, ast.Constant) and (type(node.value) not in (int, bool, type(None)) or isinstance(node.value, int) and abs(node.value) > 1000000):
            raise ValueError("整数・真偽値以外の定数や大きすぎる定数は実行できません")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow) and not (isinstance(node.right, ast.Constant) and type(node.right.value) is int and 0 <= node.right.value <= 2):
            raise ValueError("累乗の指数は0〜2に限定しています")
    return compile(tree, "generated_solve.py", "exec")


def _reference_result(semantic_ast, xs, k):
    # Keep the dataset interpreter unchanged. The demo's fourth step uses the same handlers.
    sequence = semantic_ast.get("sequence") if set(semantic_ast) == {"sequence"} else None
    if sequence is not None and len(sequence) == 4:
        reference._validate_inputs(xs, k)
        result = list(xs)
        for operation in sequence:
            result = reference._apply_operation(operation, result, k)
        return result
    return reference.interpret(semantic_ast, xs, k)


def verify(payload):
    xs, k = payload["xs"], payload["k"]
    try:
        expected = _reference_result(payload["semanticAst"], xs, k)
    except Exception as error:
        return {"status": "reference_error", "error": f"{type(error).__name__}: {error}"}
    result = {"expected": repr(expected)}
    try:
        compiled = _checked_code(payload["code"])
        scope = {"__builtins__": dict(SAFE_BUILTINS)}
        remaining = 50000

        def budget(frame, event, arg):
            nonlocal remaining
            if frame.f_code.co_filename == "generated_solve.py":
                remaining -= 1
                if remaining <= 0:
                    raise TimeoutError("実行ステップの上限を超えました")
            return budget

        sys.settrace(budget)
        try:
            exec(compiled, scope)
            actual = scope["solve"](list(xs), k)
        finally:
            sys.settrace(None)
        if type(actual) is not list or len(actual) > 1000 or any(type(x) is not int or x.bit_length() > 1024 for x in actual):
            raise ValueError("戻り値が検証可能な整数リストではありません")
        result.update(actual=repr(actual), status="match" if actual == expected else "mismatch")
    except Exception as error:
        result.update(status="code_error", error=f"{type(error).__name__}: {error}")
    return result


def verify_json(request_json):
    return json.dumps(verify(json.loads(request_json)), ensure_ascii=False)
