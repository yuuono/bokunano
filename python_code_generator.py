"""意味ASTと構造的変種から学習対象のPythonコードを組み立てる。

このモジュールはコード文字列の生成と静的検査だけを担当する。
参照インタプリタをimportせず、実行結果の照合は
``generated_code_verifier.py``へ分離する。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import keyword
from typing import Any, Mapping, Sequence


GENERATOR_VERSION = "1"
ALLOWED_CALLS = frozenset({"abs", "list", "reversed", "sorted"})

FILTER_NAMES = frozenset(
    {
        "even",
        "odd",
        "gt_k",
        "ge_k",
        "lt_k",
        "le_k",
        "multiple_of_k",
        "positive",
        "negative",
        "zero",
    }
)
MAP_NAMES = frozenset(
    {"add_k", "sub_k", "mul_k", "mul_const", "negate", "abs", "square"}
)
ORDER_NAMES = frozenset({"ascending", "descending", "reverse"})
SLICE_NAMES = frozenset({"take_first_k", "take_last_k", "every_other"})


class SemanticAstError(ValueError):
    """意味ASTが公開仕様に合わない場合のエラー。"""


class StyleSpecError(ValueError):
    """構造的変種が意味ASTと両立しない場合のエラー。"""


class GeneratedCodeSafetyError(ValueError):
    """生成コードが静的な安全性検査に失敗した場合のエラー。"""


@dataclass(frozen=True)
class Operation:
    """検証済みの単独操作。"""

    kind: str
    name: str
    argument: int | None = None


@dataclass(frozen=True)
class GeneratorConfig:
    """実行前に利用者が確定する変数名と長さ上限。"""

    element_names: tuple[str, ...]
    result_names: tuple[str, ...]
    max_source_chars: int = 4_096

    def __post_init__(self) -> None:
        if not self.element_names:
            raise ValueError("element_namesを1つ以上指定してください")
        if len(self.result_names) < 2:
            raise ValueError("forループの入力と出力を分けるためresult_namesは2つ以上必要です")
        if self.max_source_chars <= 0:
            raise ValueError("max_source_charsは正の整数にしてください")

        all_names = self.element_names + self.result_names
        if len(all_names) != len(set(all_names)):
            raise ValueError("変数名候補は役割をまたいで重複できません")
        for name in all_names:
            _validate_configured_name(name)


@dataclass(frozen=True)
class GeneratedCode:
    """静的検査まで完了したコード候補。"""

    reference_code: str
    code_style: str
    style_id: str
    style_spec: dict[str, Any]
    semantic_hash: str
    code_hash: str


def canonical_json(value: object) -> str:
    """ID計算用の正規化JSONを返す。"""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    """UTF-8文字列のSHA-256を16進文字列で返す。"""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def semantic_hash(semantic_ast: Mapping[str, Any]) -> str:
    """意味ASTの正規化内容からハッシュを計算する。"""

    normalize_semantic_ast(semantic_ast)
    return sha256_text(canonical_json(semantic_ast))


def style_id(style_spec: Mapping[str, Any]) -> str:
    """構造的変種の正規化内容からIDを計算する。"""

    return "style-" + sha256_text(canonical_json(style_spec))


def code_id(
    spec_id: str,
    candidate_style_id: str,
    rewrite_id: str | None,
    reference_code: str,
) -> str:
    """データレコード方針に従ってコード候補IDを計算する。"""

    rewrite_value = canonical_json(rewrite_id)
    payload = "\0".join((spec_id, candidate_style_id, rewrite_value, reference_code))
    return "code-" + sha256_text(payload)


def normalize_semantic_ast(semantic_ast: Mapping[str, Any]) -> tuple[Operation, ...]:
    """単独またはsequence形式を検証し、操作列へ正規化する。"""

    if not isinstance(semantic_ast, Mapping):
        raise SemanticAstError("semantic_astは辞書である必要があります")

    if set(semantic_ast) == {"sequence"}:
        raw_sequence = semantic_ast["sequence"]
        if not isinstance(raw_sequence, list) or not 1 <= len(raw_sequence) <= 3:
            raise SemanticAstError("sequenceには1〜3個の操作が必要です")
    else:
        raw_sequence = [semantic_ast]

    return tuple(_normalize_operation(operation) for operation in raw_sequence)


def generate_python_code(
    semantic_ast: Mapping[str, Any],
    style_spec: Mapping[str, Any],
    config: GeneratorConfig,
) -> GeneratedCode:
    """1つの意味ASTとstyle_specから検査済みコード文字列を生成する。"""

    operations = normalize_semantic_ast(semantic_ast)
    normalized_style = _validate_and_copy_style_spec(style_spec, operations, config)

    if normalized_style["layout"] == "single_return":
        source = _render_single_return(operations, normalized_style)
    else:
        source = _render_multi_statement(operations, normalized_style)

    validate_generated_code(source, config.max_source_chars)
    candidate_style_id = style_id(normalized_style)
    return GeneratedCode(
        reference_code=source,
        code_style=str(normalized_style["code_style"]),
        style_id=candidate_style_id,
        style_spec=normalized_style,
        semantic_hash=semantic_hash(semantic_ast),
        code_hash=sha256_text(source),
    )


def validate_generated_code(source: str, max_source_chars: int) -> ast.Module:
    """固定シグネチャと許可構文だけで構成されることを確認する。"""

    if len(source) > max_source_chars:
        raise GeneratedCodeSafetyError(
            f"生成コードが長さ上限を超えています: {len(source)} > {max_source_chars}"
        )
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise GeneratedCodeSafetyError("生成コードをast.parseできません") from error

    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise GeneratedCodeSafetyError("トップレベルにはsolve関数を1つだけ置いてください")
    function = tree.body[0]
    if function.name != "solve" or function.decorator_list:
        raise GeneratedCodeSafetyError("装飾なしのsolve関数だけを許可します")
    _validate_signature(function)

    allowed_nodes = (
        ast.Module,
        ast.FunctionDef,
        ast.arguments,
        ast.arg,
        ast.Return,
        ast.Assign,
        ast.AnnAssign,
        ast.For,
        ast.If,
        ast.AugAssign,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.ListComp,
        ast.comprehension,
        ast.BinOp,
        ast.UnaryOp,
        ast.Compare,
        ast.Call,
        ast.Subscript,
        ast.Slice,
        ast.List,
        ast.Constant,
        ast.keyword,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Pow,
        ast.Mod,
        ast.USub,
        ast.Eq,
        ast.NotEq,
        ast.Gt,
        ast.GtE,
        ast.Lt,
        ast.LtE,
    )

    bound_names = {"xs", "k"}
    bound_names.update(
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    )

    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise GeneratedCodeSafetyError(
                f"許可されていない構文です: {type(node).__name__}"
            )
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_CALLS:
                raise GeneratedCodeSafetyError("許可されていない関数呼び出しです")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id in {"xs", "k"}:
                raise GeneratedCodeSafetyError("入力xsとkへ代入してはいけません")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in bound_names | ALLOWED_CALLS | {"int", "list"}:
                raise GeneratedCodeSafetyError(f"未定義または許可されていない名前です: {node.id}")
        if isinstance(node, ast.Constant):
            if not (
                node.value is None
                or type(node.value) is bool
                or (type(node.value) is int and node.value in {0, 1, 2, 3})
            ):
                raise GeneratedCodeSafetyError(f"許可されていない定数です: {node.value!r}")

    return tree


def make_code_candidate_record(
    input_record: Mapping[str, Any],
    generated: GeneratedCode,
    generator_seed: int,
    verification: Mapping[str, Any],
) -> dict[str, Any]:
    """検証済みコードからコード候補レコードを組み立てる。"""

    spec_id_value = input_record.get("spec_id")
    semantic_ast_value = input_record.get("semantic_ast")
    if not isinstance(spec_id_value, str) or not spec_id_value:
        raise ValueError("入力レコードに空でないspec_idが必要です")
    if not isinstance(semantic_ast_value, Mapping):
        raise ValueError("入力レコードにsemantic_astが必要です")
    if "test_suite" not in input_record:
        raise ValueError("意味ASTレコードにtest_suiteが必要です")

    test_suite_value = input_record["test_suite"]
    allowed_test_suites = {
        None,
        "normal",
        "paraphrase",
        "compositional",
        "boundary",
        "repetition",
    }
    if test_suite_value not in allowed_test_suites:
        raise ValueError(f"未知のtest_suiteです: {test_suite_value!r}")

    split_value = input_record.get("split")
    if split_value is None and test_suite_value is not None:
        split_value = "test"
    if split_value not in {"train", "val", "test"}:
        raise ValueError(f"未知のsplitです: {split_value!r}")
    if split_value in {"train", "val"} and test_suite_value is not None:
        raise ValueError("trainとvalのtest_suiteはnullにしてください")
    if split_value == "test" and test_suite_value is None:
        raise ValueError("testのtest_suiteには評価集合名が必要です")

    rewrite_id: str | None = None
    return {
        "code_id": code_id(
            spec_id_value,
            generated.style_id,
            rewrite_id,
            generated.reference_code,
        ),
        "spec_id": spec_id_value,
        "semantic_ast": dict(semantic_ast_value),
        "reference_code": generated.reference_code,
        "code_style": generated.code_style,
        "style_id": generated.style_id,
        "style_spec": generated.style_spec,
        "rewrite_id": rewrite_id,
        "split": split_value,
        "test_suite": test_suite_value,
        "semantic_hash": generated.semantic_hash,
        "code_hash": generated.code_hash,
        "generator_version": GENERATOR_VERSION,
        "generator_seed": generator_seed,
        "verification": dict(verification),
    }


def _validate_configured_name(name: str) -> None:
    if (
        not isinstance(name, str)
        or not name.isidentifier()
        or keyword.iskeyword(name)
        or name in ALLOWED_CALLS
        or name in {"xs", "k", "solve", "int"}
    ):
        raise ValueError(f"使用できない変数名です: {name!r}")


def _normalize_operation(raw: object) -> Operation:
    if not isinstance(raw, Mapping) or len(raw) != 1:
        raise SemanticAstError(f"操作はキー1つの辞書である必要があります: {raw!r}")
    kind, argument = next(iter(raw.items()))

    if kind == "filter":
        name = _single_list_name(argument, kind)
        if name not in FILTER_NAMES:
            raise SemanticAstError(f"未知の抽出操作です: {name}")
        return Operation(kind, name)

    if kind == "map":
        if not isinstance(argument, list) or not argument:
            raise SemanticAstError(f"変換の形式が不正です: {argument!r}")
        name = argument[0]
        if name == "mul_const":
            if len(argument) != 2 or type(argument[1]) is not int or argument[1] not in (2, 3):
                raise SemanticAstError(f"mul_constの形式が不正です: {argument!r}")
            return Operation(kind, name, argument[1])
        if len(argument) != 1 or name not in MAP_NAMES:
            raise SemanticAstError(f"未知または不正な変換です: {argument!r}")
        return Operation(kind, str(name))

    if kind == "order":
        if not isinstance(argument, str) or argument not in ORDER_NAMES:
            raise SemanticAstError(f"未知の並べ替え操作です: {argument!r}")
        return Operation(kind, argument)

    if kind == "slice":
        name = _single_list_name(argument, kind)
        if name not in SLICE_NAMES:
            raise SemanticAstError(f"未知の切り出し操作です: {name}")
        return Operation(kind, name)

    raise SemanticAstError(f"未知の意味ASTキーです: {kind!r}")


def _single_list_name(argument: object, kind: str) -> str:
    if (
        not isinstance(argument, list)
        or len(argument) != 1
        or not isinstance(argument[0], str)
    ):
        raise SemanticAstError(f"{kind}の形式が不正です: {argument!r}")
    return argument[0]


def _validate_and_copy_style_spec(
    style_spec: Mapping[str, Any],
    operations: Sequence[Operation],
    config: GeneratorConfig,
) -> dict[str, Any]:
    if not isinstance(style_spec, Mapping):
        raise StyleSpecError("style_specは辞書である必要があります")
    required = {
        "code_style",
        "collection_form",
        "temporary_form",
        "name_set",
        "layout",
        "comments",
        "local_annotations",
        "square_form",
        "ascending_form",
        "descending_form",
        "reverse_form",
        "slice_form",
        "operation_styles",
    }
    if set(style_spec) != required:
        missing = sorted(required - set(style_spec))
        extra = sorted(set(style_spec) - required)
        raise StyleSpecError(f"style_specのキーが不正です: missing={missing}, extra={extra}")

    copied = json.loads(canonical_json(style_spec))
    operation_styles = copied["operation_styles"]
    if not isinstance(operation_styles, list) or len(operation_styles) != len(operations):
        raise StyleSpecError("operation_stylesは操作数と同じ長さにしてください")
    if copied["layout"] not in {"single_return", "multi_statement"}:
        raise StyleSpecError("layoutが不正です")
    if copied["comments"] not in {"none", "present"}:
        raise StyleSpecError("commentsはnoneまたはpresentにしてください")
    if type(copied["local_annotations"]) is not bool:
        raise StyleSpecError("local_annotationsはboolにしてください")
    if copied["name_set"] != "configured":
        raise StyleSpecError("name_setはconfiguredにしてください")

    for operation, operation_style in zip(operations, operation_styles):
        _validate_operation_style(operation, operation_style, config, copied["layout"])

    if copied["layout"] == "single_return":
        if copied["temporary_form"] != "direct_return":
            raise StyleSpecError("single_returnではtemporary_formをdirect_returnにしてください")
        if copied["local_annotations"]:
            raise StyleSpecError("single_returnではローカル型注釈を使用できません")
    elif copied["temporary_form"] not in {"reused_names", "fresh_names"}:
        raise StyleSpecError("multi_statementのtemporary_formが不正です")

    return copied


def _validate_operation_style(
    operation: Operation,
    operation_style: object,
    config: GeneratorConfig,
    layout: str,
) -> None:
    if not isinstance(operation_style, Mapping):
        raise StyleSpecError("各operation_styleは辞書にしてください")
    expected_keys = {
        "collection_form",
        "element_name",
        "result_name",
        "condition_direction",
        "expression_form",
    }
    if set(operation_style) != expected_keys:
        raise StyleSpecError("operation_styleのキーが不正です")

    element_name = operation_style["element_name"]
    result_name = operation_style["result_name"]
    collection_form = operation_style["collection_form"]
    direction = operation_style["condition_direction"]
    expression_form = operation_style["expression_form"]

    if operation.kind in {"filter", "map"}:
        if element_name not in config.element_names:
            raise StyleSpecError("要素変数名が設定候補に含まれていません")
        allowed_collection = {"list_comprehension"}
        if layout == "multi_statement":
            allowed_collection.add("for_loop")
        if collection_form not in allowed_collection:
            raise StyleSpecError("抽出・変換のcollection_formが不正です")
    elif element_name is not None or collection_form is not None:
        raise StyleSpecError("並べ替え・切り出しでは要素変数とcollection_formを使いません")

    if layout == "single_return":
        if result_name is not None:
            raise StyleSpecError("single_returnではresult_nameを使いません")
    elif result_name not in config.result_names:
        raise StyleSpecError("結果変数名が設定候補に含まれていません")

    if operation.kind == "filter":
        if direction not in {"normal", "swapped"} or expression_form != "default":
            raise StyleSpecError("抽出の条件式形式が不正です")
    elif direction is not None:
        raise StyleSpecError("抽出以外ではcondition_directionを使いません")

    if expression_form not in _expression_forms(operation):
        raise StyleSpecError(
            f"{operation.kind}:{operation.name}では{expression_form!r}を使用できません"
        )


def _render_single_return(
    operations: Sequence[Operation], style_spec: Mapping[str, Any]
) -> str:
    operation_styles = style_spec["operation_styles"]
    expression = "xs"
    for operation, operation_style in zip(operations, operation_styles):
        expression = _render_expression(operation, operation_style, expression)

    body: list[str] = []
    if style_spec["comments"] == "present":
        body.extend(f"    # {_comment_for(operation)}" for operation in operations)
    body.append(f"    return {expression}")
    return "def solve(xs: list[int], k: int) -> list[int]:\n" + "\n".join(body) + "\n"


def _render_multi_statement(
    operations: Sequence[Operation], style_spec: Mapping[str, Any]
) -> str:
    operation_styles = style_spec["operation_styles"]
    body: list[str] = []
    source_name = "xs"
    annotated_names: set[str] = set()

    for operation, operation_style in zip(operations, operation_styles):
        target_name = str(operation_style["result_name"])
        if style_spec["comments"] == "present":
            body.append(f"    # {_comment_for(operation)}")

        if operation_style["collection_form"] == "for_loop":
            if target_name == source_name:
                raise StyleSpecError("forループの入力変数と出力変数は分けてください")
            annotation = _local_annotation(
                target_name, bool(style_spec["local_annotations"]), annotated_names
            )
            body.append(f"    {target_name}{annotation} = []")
            element_name = str(operation_style["element_name"])
            body.append(f"    for {element_name} in {source_name}:")
            if operation.kind == "filter":
                condition = _filter_condition(
                    operation.name,
                    element_name,
                    str(operation_style["condition_direction"]),
                )
                body.append(f"        if {condition}:")
                body.append(f"            {target_name} += [{element_name}]")
            else:
                mapped = _map_expression(
                    operation,
                    element_name,
                    str(operation_style["expression_form"]),
                )
                body.append(f"        {target_name} += [{mapped}]")
        else:
            expression = _render_expression(operation, operation_style, source_name)
            annotation = _local_annotation(
                target_name, bool(style_spec["local_annotations"]), annotated_names
            )
            body.append(f"    {target_name}{annotation} = {expression}")
        source_name = target_name

    body.append(f"    return {source_name}")
    return "def solve(xs: list[int], k: int) -> list[int]:\n" + "\n".join(body) + "\n"


def _local_annotation(name: str, enabled: bool, annotated_names: set[str]) -> str:
    if enabled and name not in annotated_names:
        annotated_names.add(name)
        return ": list[int]"
    return ""


def _render_expression(
    operation: Operation, operation_style: Mapping[str, Any], source: str
) -> str:
    form = str(operation_style["expression_form"])
    if operation.kind == "filter":
        element_name = str(operation_style["element_name"])
        condition = _filter_condition(
            operation.name,
            element_name,
            str(operation_style["condition_direction"]),
        )
        return f"[{element_name} for {element_name} in {source} if {condition}]"
    if operation.kind == "map":
        element_name = str(operation_style["element_name"])
        mapped = _map_expression(operation, element_name, form)
        return f"[{mapped} for {element_name} in {source}]"
    if operation.kind == "order":
        if operation.name == "ascending":
            return f"sorted({source})" if form == "default" else f"sorted({source}, reverse=False)"
        if operation.name == "descending":
            return (
                f"sorted({source}, reverse=True)"
                if form == "reverse_keyword"
                else f"sorted({source})[::-1]"
            )
        return f"{source}[::-1]" if form == "slice_notation" else f"list(reversed({source}))"
    if operation.name == "take_first_k":
        return f"{source}[:k]" if form == "implicit_start" else f"{source}[0:k]"
    if operation.name == "take_last_k":
        return f"{source}[-k:]" if form == "implicit_step" else f"{source}[-k::]"
    return f"{source}[::2]" if form == "implicit_start" else f"{source}[0::2]"


def _filter_condition(name: str, element: str, direction: str) -> str:
    normal = {
        "even": f"{element} % 2 == 0",
        "odd": f"{element} % 2 != 0",
        "gt_k": f"{element} > k",
        "ge_k": f"{element} >= k",
        "lt_k": f"{element} < k",
        "le_k": f"{element} <= k",
        "multiple_of_k": f"{element} % k == 0",
        "positive": f"{element} > 0",
        "negative": f"{element} < 0",
        "zero": f"{element} == 0",
    }
    swapped = {
        "even": f"0 == {element} % 2",
        "odd": f"0 != {element} % 2",
        "gt_k": f"k < {element}",
        "ge_k": f"k <= {element}",
        "lt_k": f"k > {element}",
        "le_k": f"k >= {element}",
        "multiple_of_k": f"0 == {element} % k",
        "positive": f"0 < {element}",
        "negative": f"0 > {element}",
        "zero": f"0 == {element}",
    }
    return normal[name] if direction == "normal" else swapped[name]


def _map_expression(operation: Operation, element: str, form: str) -> str:
    if operation.name == "add_k":
        return f"{element} + k"
    if operation.name == "sub_k":
        return f"{element} - k"
    if operation.name == "mul_k":
        return f"{element} * k"
    if operation.name == "mul_const":
        return f"{element} * {operation.argument}"
    if operation.name == "negate":
        return f"-{element}"
    if operation.name == "abs":
        return f"abs({element})"
    return f"{element} * {element}" if form == "multiply" else f"{element} ** 2"


def _expression_forms(operation: Operation) -> frozenset[str]:
    if operation.kind == "filter":
        return frozenset({"default"})
    if operation.kind == "map":
        return frozenset({"multiply", "power"}) if operation.name == "square" else frozenset({"default"})
    if operation.kind == "order":
        forms = {
            "ascending": {"default", "reverse_false"},
            "descending": {"reverse_keyword", "sort_then_slice"},
            "reverse": {"slice_notation", "reversed_call"},
        }
        return frozenset(forms[operation.name])
    forms = {
        "take_first_k": {"implicit_start", "explicit_zero"},
        "take_last_k": {"implicit_step", "explicit_empty_step"},
        "every_other": {"implicit_start", "explicit_zero"},
    }
    return frozenset(forms[operation.name])


def expression_forms(operation: Operation) -> tuple[str, ...]:
    """複製器が使用する、安定した順序の実装表現一覧。"""

    return tuple(sorted(_expression_forms(operation)))


def _comment_for(operation: Operation) -> str:
    comments = {
        ("filter", "even"): "偶数だけを残す",
        ("filter", "odd"): "奇数だけを残す",
        ("filter", "gt_k"): "kより大きい値だけを残す",
        ("filter", "ge_k"): "k以上の値だけを残す",
        ("filter", "lt_k"): "kより小さい値だけを残す",
        ("filter", "le_k"): "k以下の値だけを残す",
        ("filter", "multiple_of_k"): "kの倍数だけを残す",
        ("filter", "positive"): "正の値だけを残す",
        ("filter", "negative"): "負の値だけを残す",
        ("filter", "zero"): "ゼロだけを残す",
        ("map", "add_k"): "各要素にkを加える",
        ("map", "sub_k"): "各要素からkを引く",
        ("map", "mul_k"): "各要素にkを掛ける",
        ("map", "mul_const"): f"各要素を{operation.argument}倍する",
        ("map", "negate"): "各要素の符号を反転する",
        ("map", "abs"): "各要素の絶対値を取る",
        ("map", "square"): "各要素を二乗する",
        ("order", "ascending"): "昇順に並べる",
        ("order", "descending"): "降順に並べる",
        ("order", "reverse"): "現在の要素順を反転する",
        ("slice", "take_first_k"): "先頭からk個を取る",
        ("slice", "take_last_k"): "末尾からk個を取る",
        ("slice", "every_other"): "先頭から1個おきに取る",
    }
    return comments[(operation.kind, operation.name)]


def _validate_signature(function: ast.FunctionDef) -> None:
    arguments = function.args
    if (
        arguments.posonlyargs
        or arguments.vararg is not None
        or arguments.kwonlyargs
        or arguments.kwarg is not None
        or arguments.defaults
        or arguments.kw_defaults
        or [argument.arg for argument in arguments.args] != ["xs", "k"]
    ):
        raise GeneratedCodeSafetyError("solveの引数はxsとkの2個に固定します")

    expected_list_int = ast.Subscript(
        value=ast.Name(id="list", ctx=ast.Load()),
        slice=ast.Name(id="int", ctx=ast.Load()),
        ctx=ast.Load(),
    )
    if arguments.args[0].annotation is None or ast.dump(arguments.args[0].annotation) != ast.dump(
        expected_list_int
    ):
        raise GeneratedCodeSafetyError("xsの型注釈はlist[int]に固定します")
    if not isinstance(arguments.args[1].annotation, ast.Name) or arguments.args[1].annotation.id != "int":
        raise GeneratedCodeSafetyError("kの型注釈はintに固定します")
    if function.returns is None or ast.dump(function.returns) != ast.dump(expected_list_int):
        raise GeneratedCodeSafetyError("戻り値の型注釈はlist[int]に固定します")
