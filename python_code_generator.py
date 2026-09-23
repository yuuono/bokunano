"""意味ASTと構造的変種から学習対象のPythonコードを組み立てる。

このモジュールはコード文字列の生成と静的検査だけを担当する。
参照インタプリタをimportせず、実行結果の照合は
``generated_code_verifier.py``へ分離する。
"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# この処理で使う標準または外部モジュールを読み込む
import ast
# 必要な定義を対象モジュールから読み込む
from dataclasses import dataclass
# この処理で使う標準または外部モジュールを読み込む
import hashlib
# この処理で使う標準または外部モジュールを読み込む
import json
# この処理で使う標準または外部モジュールを読み込む
import keyword
# 必要な定義を対象モジュールから読み込む
from typing import Any, Mapping, Sequence


# GENERATOR_VERSIONへこの工程で使用する値を設定する
GENERATOR_VERSION = "1"
# ALLOWED_CALLSへこの工程で使用する値を設定する
ALLOWED_CALLS = frozenset({"abs", "list", "reversed", "sorted"})

# FILTER_NAMESへこの工程で使用する値を設定する
FILTER_NAMES = frozenset(
    # 次の値または処理を現在の構造へ組み込む
    {
        # この処理で扱う文字列を一覧へ加える
        "even",
        # この処理で扱う文字列を一覧へ加える
        "odd",
        # この処理で扱う文字列を一覧へ加える
        "gt_k",
        # この処理で扱う文字列を一覧へ加える
        "ge_k",
        # この処理で扱う文字列を一覧へ加える
        "lt_k",
        # この処理で扱う文字列を一覧へ加える
        "le_k",
        # この処理で扱う文字列を一覧へ加える
        "multiple_of_k",
        # この処理で扱う文字列を一覧へ加える
        "positive",
        # この処理で扱う文字列を一覧へ加える
        "negative",
        # この処理で扱う文字列を一覧へ加える
        "zero",
    }
)
# MAP_NAMESへこの工程で使用する値を設定する
MAP_NAMES = frozenset(
    # 次の値または処理を現在の構造へ組み込む
    {"add_k", "sub_k", "mul_k", "mul_const", "negate", "abs", "square"}
)
# ORDER_NAMESへこの工程で使用する値を設定する
ORDER_NAMES = frozenset({"ascending", "descending", "reverse"})
# SLICE_NAMESへこの工程で使用する値を設定する
SLICE_NAMES = frozenset({"take_first_k", "take_last_k", "every_other"})


# 関連する状態と処理をまとめるクラスを定義する
class SemanticAstError(ValueError):
    """意味ASTが公開仕様に合わない場合のエラー。"""


# 関連する状態と処理をまとめるクラスを定義する
class StyleSpecError(ValueError):
    """構造的変種が意味ASTと両立しない場合のエラー。"""


# 関連する状態と処理をまとめるクラスを定義する
class GeneratedCodeSafetyError(ValueError):
    """生成コードが静的な安全性検査に失敗した場合のエラー。"""


# 直後の定義へデコレータを適用する
@dataclass(frozen=True)
# 関連する状態と処理をまとめるクラスを定義する
class Operation:
    """検証済みの単独操作。"""

    # 次の値または処理を現在の構造へ組み込む
    kind: str
    # 次の値または処理を現在の構造へ組み込む
    name: str
    # argumentへこの工程で使用する値を設定する
    argument: int | None = None


# 直後の定義へデコレータを適用する
@dataclass(frozen=True)
# 関連する状態と処理をまとめるクラスを定義する
class GeneratorConfig:
    """実行前に利用者が確定する変数名と長さ上限。"""

    # 次の値または処理を現在の構造へ組み込む
    element_names: tuple[str, ...]
    # 次の値または処理を現在の構造へ組み込む
    result_names: tuple[str, ...]
    # max_source_charsへこの工程で使用する値を設定する
    max_source_chars: int = 4_096

    # この工程を担当する関数を定義する
    def __post_init__(self) -> None:
        # 条件を満たす場合だけ次の処理を行う
        if not self.element_names:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("element_namesを1つ以上指定してください")
        # 条件を満たす場合だけ次の処理を行う
        if len(self.result_names) < 2:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("forループの入力と出力を分けるためresult_namesは2つ以上必要です")
        # 条件を満たす場合だけ次の処理を行う
        if self.max_source_chars <= 0:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("max_source_charsは正の整数にしてください")

        # all_namesへこの工程で使用する値を設定する
        all_names = self.element_names + self.result_names
        # 条件を満たす場合だけ次の処理を行う
        if len(all_names) != len(set(all_names)):
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("変数名候補は役割をまたいで重複できません")
        # 対象を一件ずつ取り出して処理する
        for name in all_names:
            # 次の値または処理を現在の構造へ組み込む
            _validate_configured_name(name)


# 直後の定義へデコレータを適用する
@dataclass(frozen=True)
# 関連する状態と処理をまとめるクラスを定義する
class GeneratedCode:
    """静的検査まで完了したコード候補。"""

    # 次の値または処理を現在の構造へ組み込む
    reference_code: str
    # 次の値または処理を現在の構造へ組み込む
    code_style: str
    # 次の値または処理を現在の構造へ組み込む
    style_id: str
    # 次の値または処理を現在の構造へ組み込む
    style_spec: dict[str, Any]
    # 次の値または処理を現在の構造へ組み込む
    semantic_hash: str
    # 次の値または処理を現在の構造へ組み込む
    code_hash: str


# この工程を担当する関数を定義する
def canonical_json(value: object) -> str:
    """ID計算用の正規化JSONを返す。"""

    # 処理結果を呼び出し元へ返す
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# この工程を担当する関数を定義する
def sha256_text(value: str) -> str:
    """UTF-8文字列のSHA-256を16進文字列で返す。"""

    # 処理結果を呼び出し元へ返す
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# この工程を担当する関数を定義する
def semantic_hash(semantic_ast: Mapping[str, Any]) -> str:
    """意味ASTの正規化内容からハッシュを計算する。"""

    # 次の値または処理を現在の構造へ組み込む
    normalize_semantic_ast(semantic_ast)
    # 処理結果を呼び出し元へ返す
    return sha256_text(canonical_json(semantic_ast))


# この工程を担当する関数を定義する
def style_id(style_spec: Mapping[str, Any]) -> str:
    """構造的変種の正規化内容からIDを計算する。"""

    # 処理結果を呼び出し元へ返す
    return "style-" + sha256_text(canonical_json(style_spec))


# この工程を担当する関数を定義する
def code_id(
    # 次の値または処理を現在の構造へ組み込む
    spec_id: str,
    # 次の値または処理を現在の構造へ組み込む
    candidate_style_id: str,
    # 次の値または処理を現在の構造へ組み込む
    rewrite_id: str | None,
    # 次の値または処理を現在の構造へ組み込む
    reference_code: str,
# 次の値または処理を現在の構造へ組み込む
) -> str:
    """データレコード方針に従ってコード候補IDを計算する。"""

    # rewrite_valueへこの工程で使用する値を設定する
    rewrite_value = canonical_json(rewrite_id)
    # payloadへこの工程で使用する値を設定する
    payload = "\0".join((spec_id, candidate_style_id, rewrite_value, reference_code))
    # 処理結果を呼び出し元へ返す
    return "code-" + sha256_text(payload)


# この工程を担当する関数を定義する
def normalize_semantic_ast(semantic_ast: Mapping[str, Any]) -> tuple[Operation, ...]:
    """単独またはsequence形式を検証し、操作列へ正規化する。"""

    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(semantic_ast, Mapping):
        # 不正な状態を例外として通知して処理を停止する
        raise SemanticAstError("semantic_astは辞書である必要があります")

    # 条件を満たす場合だけ次の処理を行う
    if set(semantic_ast) == {"sequence"}:
        # raw_sequenceへこの工程で使用する値を設定する
        raw_sequence = semantic_ast["sequence"]
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(raw_sequence, list) or not 1 <= len(raw_sequence) <= 3:
            # 不正な状態を例外として通知して処理を停止する
            raise SemanticAstError("sequenceには1〜3個の操作が必要です")
    # それまでの条件に該当しない場合を処理する
    else:
        # raw_sequenceへこの工程で使用する値を設定する
        raw_sequence = [semantic_ast]

    # 処理結果を呼び出し元へ返す
    return tuple(_normalize_operation(operation) for operation in raw_sequence)


# この工程を担当する関数を定義する
def generate_python_code(
    # 次の値または処理を現在の構造へ組み込む
    semantic_ast: Mapping[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    style_spec: Mapping[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    config: GeneratorConfig,
# 次の値または処理を現在の構造へ組み込む
) -> GeneratedCode:
    """1つの意味ASTとstyle_specから検査済みコード文字列を生成する。"""

    # operationsへこの工程で使用する値を設定する
    operations = normalize_semantic_ast(semantic_ast)
    # normalized_styleへこの工程で使用する値を設定する
    normalized_style = _validate_and_copy_style_spec(style_spec, operations, config)

    # 条件を満たす場合だけ次の処理を行う
    if normalized_style["layout"] == "single_return":
        # sourceへこの工程で使用する値を設定する
        source = _render_single_return(operations, normalized_style)
    # それまでの条件に該当しない場合を処理する
    else:
        # sourceへこの工程で使用する値を設定する
        source = _render_multi_statement(operations, normalized_style)

    # 次の値または処理を現在の構造へ組み込む
    validate_generated_code(source, config.max_source_chars)
    # candidate_style_idへこの工程で使用する値を設定する
    candidate_style_id = style_id(normalized_style)
    # 処理結果を呼び出し元へ返す
    return GeneratedCode(
        # reference_codeへこの工程で使用する値を設定する
        reference_code=source,
        # code_styleへこの工程で使用する値を設定する
        code_style=str(normalized_style["code_style"]),
        # style_idへこの工程で使用する値を設定する
        style_id=candidate_style_id,
        # style_specへこの工程で使用する値を設定する
        style_spec=normalized_style,
        # semantic_hashへこの工程で使用する値を設定する
        semantic_hash=semantic_hash(semantic_ast),
        # code_hashへこの工程で使用する値を設定する
        code_hash=sha256_text(source),
    )


# この工程を担当する関数を定義する
def validate_generated_code(source: str, max_source_chars: int) -> ast.Module:
    """固定シグネチャと許可構文だけで構成されることを確認する。"""

    # 条件を満たす場合だけ次の処理を行う
    if len(source) > max_source_chars:
        # 不正な状態を例外として通知して処理を停止する
        raise GeneratedCodeSafetyError(
            # 次の値または処理を現在の構造へ組み込む
            f"生成コードが長さ上限を超えています: {len(source)} > {max_source_chars}"
        )
    # 失敗する可能性がある処理を開始する
    try:
        # treeへこの工程で使用する値を設定する
        tree = ast.parse(source)
    # 発生した例外を受け取り、安全に処理する
    except SyntaxError as error:
        # 不正な状態を例外として通知して処理を停止する
        raise GeneratedCodeSafetyError("生成コードをast.parseできません") from error

    # 条件を満たす場合だけ次の処理を行う
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        # 不正な状態を例外として通知して処理を停止する
        raise GeneratedCodeSafetyError("トップレベルにはsolve関数を1つだけ置いてください")
    # functionへこの工程で使用する値を設定する
    function = tree.body[0]
    # 条件を満たす場合だけ次の処理を行う
    if function.name != "solve" or function.decorator_list:
        # 不正な状態を例外として通知して処理を停止する
        raise GeneratedCodeSafetyError("装飾なしのsolve関数だけを許可します")
    # 次の値または処理を現在の構造へ組み込む
    _validate_signature(function)

    # allowed_nodesへこの工程で使用する値を設定する
    allowed_nodes = (
        # 次の値または処理を現在の構造へ組み込む
        ast.Module,
        # 次の値または処理を現在の構造へ組み込む
        ast.FunctionDef,
        # 次の値または処理を現在の構造へ組み込む
        ast.arguments,
        # 次の値または処理を現在の構造へ組み込む
        ast.arg,
        # 次の値または処理を現在の構造へ組み込む
        ast.Return,
        # 次の値または処理を現在の構造へ組み込む
        ast.Assign,
        # 次の値または処理を現在の構造へ組み込む
        ast.AnnAssign,
        # 次の値または処理を現在の構造へ組み込む
        ast.For,
        # 次の値または処理を現在の構造へ組み込む
        ast.If,
        # 次の値または処理を現在の構造へ組み込む
        ast.AugAssign,
        # 次の値または処理を現在の構造へ組み込む
        ast.Name,
        # 次の値または処理を現在の構造へ組み込む
        ast.Load,
        # 次の値または処理を現在の構造へ組み込む
        ast.Store,
        # 次の値または処理を現在の構造へ組み込む
        ast.ListComp,
        # 次の値または処理を現在の構造へ組み込む
        ast.comprehension,
        # 次の値または処理を現在の構造へ組み込む
        ast.BinOp,
        # 次の値または処理を現在の構造へ組み込む
        ast.UnaryOp,
        # 次の値または処理を現在の構造へ組み込む
        ast.Compare,
        # 次の値または処理を現在の構造へ組み込む
        ast.Call,
        # 次の値または処理を現在の構造へ組み込む
        ast.Subscript,
        # 次の値または処理を現在の構造へ組み込む
        ast.Slice,
        # 次の値または処理を現在の構造へ組み込む
        ast.List,
        # 次の値または処理を現在の構造へ組み込む
        ast.Constant,
        # 次の値または処理を現在の構造へ組み込む
        ast.keyword,
        # 次の値または処理を現在の構造へ組み込む
        ast.Add,
        # 次の値または処理を現在の構造へ組み込む
        ast.Sub,
        # 次の値または処理を現在の構造へ組み込む
        ast.Mult,
        # 次の値または処理を現在の構造へ組み込む
        ast.Pow,
        # 次の値または処理を現在の構造へ組み込む
        ast.Mod,
        # 次の値または処理を現在の構造へ組み込む
        ast.USub,
        # 次の値または処理を現在の構造へ組み込む
        ast.Eq,
        # 次の値または処理を現在の構造へ組み込む
        ast.NotEq,
        # 次の値または処理を現在の構造へ組み込む
        ast.Gt,
        # 次の値または処理を現在の構造へ組み込む
        ast.GtE,
        # 次の値または処理を現在の構造へ組み込む
        ast.Lt,
        # 次の値または処理を現在の構造へ組み込む
        ast.LtE,
    )

    # bound_namesへこの工程で使用する値を設定する
    bound_names = {"xs", "k"}
    # 次の値または処理を現在の構造へ組み込む
    bound_names.update(
        # 次の値または処理を現在の構造へ組み込む
        node.id
        # 対象を一件ずつ取り出して処理する
        for node in ast.walk(function)
        # 条件を満たす場合だけ次の処理を行う
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    )

    # 対象を一件ずつ取り出して処理する
    for node in ast.walk(tree):
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(node, allowed_nodes):
            # 不正な状態を例外として通知して処理を停止する
            raise GeneratedCodeSafetyError(
                # 次の値または処理を現在の構造へ組み込む
                f"許可されていない構文です: {type(node).__name__}"
            )
        # 条件を満たす場合だけ次の処理を行う
        if isinstance(node, ast.Call):
            # 条件を満たす場合だけ次の処理を行う
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_CALLS:
                # 不正な状態を例外として通知して処理を停止する
                raise GeneratedCodeSafetyError("許可されていない関数呼び出しです")
        # 条件を満たす場合だけ次の処理を行う
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            # 条件を満たす場合だけ次の処理を行う
            if node.id in {"xs", "k"}:
                # 不正な状態を例外として通知して処理を停止する
                raise GeneratedCodeSafetyError("入力xsとkへ代入してはいけません")
        # 条件を満たす場合だけ次の処理を行う
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            # 条件を満たす場合だけ次の処理を行う
            if node.id not in bound_names | ALLOWED_CALLS | {"int", "list"}:
                # 不正な状態を例外として通知して処理を停止する
                raise GeneratedCodeSafetyError(f"未定義または許可されていない名前です: {node.id}")
        # 条件を満たす場合だけ次の処理を行う
        if isinstance(node, ast.Constant):
            # 条件を満たす場合だけ次の処理を行う
            if not (
                # 次の値または処理を現在の構造へ組み込む
                node.value is None
                # 次の値または処理を現在の構造へ組み込む
                or type(node.value) is bool
                # 次の値または処理を現在の構造へ組み込む
                or (type(node.value) is int and node.value in {0, 1, 2, 3})
            # 次の値または処理を現在の構造へ組み込む
            ):
                # 不正な状態を例外として通知して処理を停止する
                raise GeneratedCodeSafetyError(f"許可されていない定数です: {node.value!r}")

    # 処理結果を呼び出し元へ返す
    return tree


# この工程を担当する関数を定義する
def make_code_candidate_record(
    # 次の値または処理を現在の構造へ組み込む
    input_record: Mapping[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    generated: GeneratedCode,
    # 次の値または処理を現在の構造へ組み込む
    generator_seed: int,
    # 次の値または処理を現在の構造へ組み込む
    verification: Mapping[str, Any],
# 次の値または処理を現在の構造へ組み込む
) -> dict[str, Any]:
    """検証済みコードからコード候補レコードを組み立てる。"""

    # spec_id_valueへこの工程で使用する値を設定する
    spec_id_value = input_record.get("spec_id")
    # semantic_ast_valueへこの工程で使用する値を設定する
    semantic_ast_value = input_record.get("semantic_ast")
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(spec_id_value, str) or not spec_id_value:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("入力レコードに空でないspec_idが必要です")
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(semantic_ast_value, Mapping):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("入力レコードにsemantic_astが必要です")
    # 条件を満たす場合だけ次の処理を行う
    if "test_suite" not in input_record:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("意味ASTレコードにtest_suiteが必要です")

    # test_suite_valueへこの工程で使用する値を設定する
    test_suite_value = input_record["test_suite"]
    # allowed_test_suitesへこの工程で使用する値を設定する
    allowed_test_suites = {
        # 次の値または処理を現在の構造へ組み込む
        None,
        # この処理で扱う文字列を一覧へ加える
        "normal",
        # この処理で扱う文字列を一覧へ加える
        "paraphrase",
        # この処理で扱う文字列を一覧へ加える
        "compositional",
        # この処理で扱う文字列を一覧へ加える
        "boundary",
        # この処理で扱う文字列を一覧へ加える
        "repetition",
    }
    # 条件を満たす場合だけ次の処理を行う
    if test_suite_value not in allowed_test_suites:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"未知のtest_suiteです: {test_suite_value!r}")

    # split_valueへこの工程で使用する値を設定する
    split_value = input_record.get("split")
    # 条件を満たす場合だけ次の処理を行う
    if split_value is None and test_suite_value is not None:
        # split_valueへこの工程で使用する値を設定する
        split_value = "test"
    # 条件を満たす場合だけ次の処理を行う
    if split_value not in {"train", "val", "test"}:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"未知のsplitです: {split_value!r}")
    # 条件を満たす場合だけ次の処理を行う
    if split_value in {"train", "val"} and test_suite_value is not None:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("trainとvalのtest_suiteはnullにしてください")
    # 条件を満たす場合だけ次の処理を行う
    if split_value == "test" and test_suite_value is None:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("testのtest_suiteには評価集合名が必要です")

    # rewrite_idへこの工程で使用する値を設定する
    rewrite_id: str | None = None
    # 処理結果を呼び出し元へ返す
    return {
        # 出力レコードの項目と値を設定する
        "code_id": code_id(
            # 次の値または処理を現在の構造へ組み込む
            spec_id_value,
            # 次の値または処理を現在の構造へ組み込む
            generated.style_id,
            # 次の値または処理を現在の構造へ組み込む
            rewrite_id,
            # 次の値または処理を現在の構造へ組み込む
            generated.reference_code,
        ),
        # 出力レコードの項目と値を設定する
        "spec_id": spec_id_value,
        # 出力レコードの項目と値を設定する
        "semantic_ast": dict(semantic_ast_value),
        # 出力レコードの項目と値を設定する
        "reference_code": generated.reference_code,
        # 出力レコードの項目と値を設定する
        "code_style": generated.code_style,
        # 出力レコードの項目と値を設定する
        "style_id": generated.style_id,
        # 出力レコードの項目と値を設定する
        "style_spec": generated.style_spec,
        # 出力レコードの項目と値を設定する
        "rewrite_id": rewrite_id,
        # 出力レコードの項目と値を設定する
        "split": split_value,
        # 出力レコードの項目と値を設定する
        "test_suite": test_suite_value,
        # 出力レコードの項目と値を設定する
        "semantic_hash": generated.semantic_hash,
        # 出力レコードの項目と値を設定する
        "code_hash": generated.code_hash,
        # 出力レコードの項目と値を設定する
        "generator_version": GENERATOR_VERSION,
        # 出力レコードの項目と値を設定する
        "generator_seed": generator_seed,
        # 出力レコードの項目と値を設定する
        "verification": dict(verification),
    }


# この工程を担当する関数を定義する
def _validate_configured_name(name: str) -> None:
    # 条件を満たす場合だけ次の処理を行う
    if (
        # 次の値または処理を現在の構造へ組み込む
        not isinstance(name, str)
        # 次の値または処理を現在の構造へ組み込む
        or not name.isidentifier()
        # 次の値または処理を現在の構造へ組み込む
        or keyword.iskeyword(name)
        # 次の値または処理を現在の構造へ組み込む
        or name in ALLOWED_CALLS
        # 次の値または処理を現在の構造へ組み込む
        or name in {"xs", "k", "solve", "int"}
    # 次の値または処理を現在の構造へ組み込む
    ):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"使用できない変数名です: {name!r}")


# この工程を担当する関数を定義する
def _normalize_operation(raw: object) -> Operation:
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(raw, Mapping) or len(raw) != 1:
        # 不正な状態を例外として通知して処理を停止する
        raise SemanticAstError(f"操作はキー1つの辞書である必要があります: {raw!r}")
    # 次の値または処理を現在の構造へ組み込む
    kind, argument = next(iter(raw.items()))

    # 条件を満たす場合だけ次の処理を行う
    if kind == "filter":
        # nameへこの工程で使用する値を設定する
        name = _single_list_name(argument, kind)
        # 条件を満たす場合だけ次の処理を行う
        if name not in FILTER_NAMES:
            # 不正な状態を例外として通知して処理を停止する
            raise SemanticAstError(f"未知の抽出操作です: {name}")
        # 処理結果を呼び出し元へ返す
        return Operation(kind, name)

    # 条件を満たす場合だけ次の処理を行う
    if kind == "map":
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(argument, list) or not argument:
            # 不正な状態を例外として通知して処理を停止する
            raise SemanticAstError(f"変換の形式が不正です: {argument!r}")
        # nameへこの工程で使用する値を設定する
        name = argument[0]
        # 条件を満たす場合だけ次の処理を行う
        if name == "mul_const":
            # 条件を満たす場合だけ次の処理を行う
            if len(argument) != 2 or type(argument[1]) is not int or argument[1] not in (2, 3):
                # 不正な状態を例外として通知して処理を停止する
                raise SemanticAstError(f"mul_constの形式が不正です: {argument!r}")
            # 処理結果を呼び出し元へ返す
            return Operation(kind, name, argument[1])
        # 条件を満たす場合だけ次の処理を行う
        if len(argument) != 1 or name not in MAP_NAMES:
            # 不正な状態を例外として通知して処理を停止する
            raise SemanticAstError(f"未知または不正な変換です: {argument!r}")
        # 処理結果を呼び出し元へ返す
        return Operation(kind, str(name))

    # 条件を満たす場合だけ次の処理を行う
    if kind == "order":
        # 条件を満たす場合だけ次の処理を行う
        if not isinstance(argument, str) or argument not in ORDER_NAMES:
            # 不正な状態を例外として通知して処理を停止する
            raise SemanticAstError(f"未知の並べ替え操作です: {argument!r}")
        # 処理結果を呼び出し元へ返す
        return Operation(kind, argument)

    # 条件を満たす場合だけ次の処理を行う
    if kind == "slice":
        # nameへこの工程で使用する値を設定する
        name = _single_list_name(argument, kind)
        # 条件を満たす場合だけ次の処理を行う
        if name not in SLICE_NAMES:
            # 不正な状態を例外として通知して処理を停止する
            raise SemanticAstError(f"未知の切り出し操作です: {name}")
        # 処理結果を呼び出し元へ返す
        return Operation(kind, name)

    # 不正な状態を例外として通知して処理を停止する
    raise SemanticAstError(f"未知の意味ASTキーです: {kind!r}")


# この工程を担当する関数を定義する
def _single_list_name(argument: object, kind: str) -> str:
    # 条件を満たす場合だけ次の処理を行う
    if (
        # 次の値または処理を現在の構造へ組み込む
        not isinstance(argument, list)
        # 次の値または処理を現在の構造へ組み込む
        or len(argument) != 1
        # 次の値または処理を現在の構造へ組み込む
        or not isinstance(argument[0], str)
    # 次の値または処理を現在の構造へ組み込む
    ):
        # 不正な状態を例外として通知して処理を停止する
        raise SemanticAstError(f"{kind}の形式が不正です: {argument!r}")
    # 処理結果を呼び出し元へ返す
    return argument[0]


# この工程を担当する関数を定義する
def _validate_and_copy_style_spec(
    # 次の値または処理を現在の構造へ組み込む
    style_spec: Mapping[str, Any],
    # 次の値または処理を現在の構造へ組み込む
    operations: Sequence[Operation],
    # 次の値または処理を現在の構造へ組み込む
    config: GeneratorConfig,
# 次の値または処理を現在の構造へ組み込む
) -> dict[str, Any]:
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(style_spec, Mapping):
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("style_specは辞書である必要があります")
    # requiredへこの工程で使用する値を設定する
    required = {
        # この処理で扱う文字列を一覧へ加える
        "code_style",
        # この処理で扱う文字列を一覧へ加える
        "collection_form",
        # この処理で扱う文字列を一覧へ加える
        "temporary_form",
        # この処理で扱う文字列を一覧へ加える
        "name_set",
        # この処理で扱う文字列を一覧へ加える
        "layout",
        # この処理で扱う文字列を一覧へ加える
        "comments",
        # この処理で扱う文字列を一覧へ加える
        "local_annotations",
        # この処理で扱う文字列を一覧へ加える
        "square_form",
        # この処理で扱う文字列を一覧へ加える
        "ascending_form",
        # この処理で扱う文字列を一覧へ加える
        "descending_form",
        # この処理で扱う文字列を一覧へ加える
        "reverse_form",
        # この処理で扱う文字列を一覧へ加える
        "slice_form",
        # この処理で扱う文字列を一覧へ加える
        "operation_styles",
    }
    # 条件を満たす場合だけ次の処理を行う
    if set(style_spec) != required:
        # missingへこの工程で使用する値を設定する
        missing = sorted(required - set(style_spec))
        # extraへこの工程で使用する値を設定する
        extra = sorted(set(style_spec) - required)
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError(f"style_specのキーが不正です: missing={missing}, extra={extra}")

    # copiedへこの工程で使用する値を設定する
    copied = json.loads(canonical_json(style_spec))
    # operation_stylesへこの工程で使用する値を設定する
    operation_styles = copied["operation_styles"]
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(operation_styles, list) or len(operation_styles) != len(operations):
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("operation_stylesは操作数と同じ長さにしてください")
    # 条件を満たす場合だけ次の処理を行う
    if copied["layout"] not in {"single_return", "multi_statement"}:
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("layoutが不正です")
    # 条件を満たす場合だけ次の処理を行う
    if copied["comments"] not in {"none", "present"}:
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("commentsはnoneまたはpresentにしてください")
    # 条件を満たす場合だけ次の処理を行う
    if type(copied["local_annotations"]) is not bool:
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("local_annotationsはboolにしてください")
    # 条件を満たす場合だけ次の処理を行う
    if copied["name_set"] != "configured":
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("name_setはconfiguredにしてください")

    # 対象を一件ずつ取り出して処理する
    for operation, operation_style in zip(operations, operation_styles):
        # 次の値または処理を現在の構造へ組み込む
        _validate_operation_style(operation, operation_style, config, copied["layout"])

    # 条件を満たす場合だけ次の処理を行う
    if copied["layout"] == "single_return":
        # 条件を満たす場合だけ次の処理を行う
        if copied["temporary_form"] != "direct_return":
            # 不正な状態を例外として通知して処理を停止する
            raise StyleSpecError("single_returnではtemporary_formをdirect_returnにしてください")
        # 条件を満たす場合だけ次の処理を行う
        if copied["local_annotations"]:
            # 不正な状態を例外として通知して処理を停止する
            raise StyleSpecError("single_returnではローカル型注釈を使用できません")
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif copied["temporary_form"] not in {"reused_names", "fresh_names"}:
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("multi_statementのtemporary_formが不正です")

    # 処理結果を呼び出し元へ返す
    return copied


# この工程を担当する関数を定義する
def _validate_operation_style(
    # 次の値または処理を現在の構造へ組み込む
    operation: Operation,
    # 次の値または処理を現在の構造へ組み込む
    operation_style: object,
    # 次の値または処理を現在の構造へ組み込む
    config: GeneratorConfig,
    # 次の値または処理を現在の構造へ組み込む
    layout: str,
# 次の値または処理を現在の構造へ組み込む
) -> None:
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(operation_style, Mapping):
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("各operation_styleは辞書にしてください")
    # expected_keysへこの工程で使用する値を設定する
    expected_keys = {
        # この処理で扱う文字列を一覧へ加える
        "collection_form",
        # この処理で扱う文字列を一覧へ加える
        "element_name",
        # この処理で扱う文字列を一覧へ加える
        "result_name",
        # この処理で扱う文字列を一覧へ加える
        "condition_direction",
        # この処理で扱う文字列を一覧へ加える
        "expression_form",
    }
    # 条件を満たす場合だけ次の処理を行う
    if set(operation_style) != expected_keys:
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("operation_styleのキーが不正です")

    # element_nameへこの工程で使用する値を設定する
    element_name = operation_style["element_name"]
    # result_nameへこの工程で使用する値を設定する
    result_name = operation_style["result_name"]
    # collection_formへこの工程で使用する値を設定する
    collection_form = operation_style["collection_form"]
    # directionへこの工程で使用する値を設定する
    direction = operation_style["condition_direction"]
    # expression_formへこの工程で使用する値を設定する
    expression_form = operation_style["expression_form"]

    # 条件を満たす場合だけ次の処理を行う
    if operation.kind in {"filter", "map"}:
        # 条件を満たす場合だけ次の処理を行う
        if element_name not in config.element_names:
            # 不正な状態を例外として通知して処理を停止する
            raise StyleSpecError("要素変数名が設定候補に含まれていません")
        # allowed_collectionへこの工程で使用する値を設定する
        allowed_collection = {"list_comprehension"}
        # 条件を満たす場合だけ次の処理を行う
        if layout == "multi_statement":
            # 次の値または処理を現在の構造へ組み込む
            allowed_collection.add("for_loop")
        # 条件を満たす場合だけ次の処理を行う
        if collection_form not in allowed_collection:
            # 不正な状態を例外として通知して処理を停止する
            raise StyleSpecError("抽出・変換のcollection_formが不正です")
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif element_name is not None or collection_form is not None:
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("並べ替え・切り出しでは要素変数とcollection_formを使いません")

    # 条件を満たす場合だけ次の処理を行う
    if layout == "single_return":
        # 条件を満たす場合だけ次の処理を行う
        if result_name is not None:
            # 不正な状態を例外として通知して処理を停止する
            raise StyleSpecError("single_returnではresult_nameを使いません")
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif result_name not in config.result_names:
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("結果変数名が設定候補に含まれていません")

    # 条件を満たす場合だけ次の処理を行う
    if operation.kind == "filter":
        # 条件を満たす場合だけ次の処理を行う
        if direction not in {"normal", "swapped"} or expression_form != "default":
            # 不正な状態を例外として通知して処理を停止する
            raise StyleSpecError("抽出の条件式形式が不正です")
    # 前の条件に該当せず、この条件を満たす場合を処理する
    elif direction is not None:
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError("抽出以外ではcondition_directionを使いません")

    # 条件を満たす場合だけ次の処理を行う
    if expression_form not in _expression_forms(operation):
        # 不正な状態を例外として通知して処理を停止する
        raise StyleSpecError(
            # 次の値または処理を現在の構造へ組み込む
            f"{operation.kind}:{operation.name}では{expression_form!r}を使用できません"
        )


# この工程を担当する関数を定義する
def _render_single_return(
    # 次の値または処理を現在の構造へ組み込む
    operations: Sequence[Operation], style_spec: Mapping[str, Any]
# 次の値または処理を現在の構造へ組み込む
) -> str:
    # operation_stylesへこの工程で使用する値を設定する
    operation_styles = style_spec["operation_styles"]
    # expressionへこの工程で使用する値を設定する
    expression = "xs"
    # 対象を一件ずつ取り出して処理する
    for operation, operation_style in zip(operations, operation_styles):
        # expressionへこの工程で使用する値を設定する
        expression = _render_expression(operation, operation_style, expression)

    # bodyへこの工程で使用する値を設定する
    body: list[str] = []
    # 条件を満たす場合だけ次の処理を行う
    if style_spec["comments"] == "present":
        # 次の値または処理を現在の構造へ組み込む
        body.extend(f"    # {_comment_for(operation)}" for operation in operations)
    # 次の値または処理を現在の構造へ組み込む
    body.append(f"    return {expression}")
    # 処理結果を呼び出し元へ返す
    return "def solve(xs: list[int], k: int) -> list[int]:\n" + "\n".join(body) + "\n"


# この工程を担当する関数を定義する
def _render_multi_statement(
    # 次の値または処理を現在の構造へ組み込む
    operations: Sequence[Operation], style_spec: Mapping[str, Any]
# 次の値または処理を現在の構造へ組み込む
) -> str:
    # operation_stylesへこの工程で使用する値を設定する
    operation_styles = style_spec["operation_styles"]
    # bodyへこの工程で使用する値を設定する
    body: list[str] = []
    # source_nameへこの工程で使用する値を設定する
    source_name = "xs"
    # annotated_namesへこの工程で使用する値を設定する
    annotated_names: set[str] = set()

    # 対象を一件ずつ取り出して処理する
    for operation, operation_style in zip(operations, operation_styles):
        # target_nameへこの工程で使用する値を設定する
        target_name = str(operation_style["result_name"])
        # 条件を満たす場合だけ次の処理を行う
        if style_spec["comments"] == "present":
            # 次の値または処理を現在の構造へ組み込む
            body.append(f"    # {_comment_for(operation)}")

        # 条件を満たす場合だけ次の処理を行う
        if operation_style["collection_form"] == "for_loop":
            # 条件を満たす場合だけ次の処理を行う
            if target_name == source_name:
                # 不正な状態を例外として通知して処理を停止する
                raise StyleSpecError("forループの入力変数と出力変数は分けてください")
            # annotationへこの工程で使用する値を設定する
            annotation = _local_annotation(
                # 次の値または処理を現在の構造へ組み込む
                target_name, bool(style_spec["local_annotations"]), annotated_names
            )
            # 次の値または処理を現在の構造へ組み込む
            body.append(f"    {target_name}{annotation} = []")
            # element_nameへこの工程で使用する値を設定する
            element_name = str(operation_style["element_name"])
            # 次の値または処理を現在の構造へ組み込む
            body.append(f"    for {element_name} in {source_name}:")
            # 条件を満たす場合だけ次の処理を行う
            if operation.kind == "filter":
                # conditionへこの工程で使用する値を設定する
                condition = _filter_condition(
                    # 次の値または処理を現在の構造へ組み込む
                    operation.name,
                    # 次の値または処理を現在の構造へ組み込む
                    element_name,
                    # 次の値または処理を現在の構造へ組み込む
                    str(operation_style["condition_direction"]),
                )
                # 次の値または処理を現在の構造へ組み込む
                body.append(f"        if {condition}:")
                # 次の値または処理を現在の構造へ組み込む
                body.append(f"            {target_name} += [{element_name}]")
            # それまでの条件に該当しない場合を処理する
            else:
                # mappedへこの工程で使用する値を設定する
                mapped = _map_expression(
                    # 次の値または処理を現在の構造へ組み込む
                    operation,
                    # 次の値または処理を現在の構造へ組み込む
                    element_name,
                    # 次の値または処理を現在の構造へ組み込む
                    str(operation_style["expression_form"]),
                )
                # 次の値または処理を現在の構造へ組み込む
                body.append(f"        {target_name} += [{mapped}]")
        # それまでの条件に該当しない場合を処理する
        else:
            # expressionへこの工程で使用する値を設定する
            expression = _render_expression(operation, operation_style, source_name)
            # annotationへこの工程で使用する値を設定する
            annotation = _local_annotation(
                # 次の値または処理を現在の構造へ組み込む
                target_name, bool(style_spec["local_annotations"]), annotated_names
            )
            # 次の値または処理を現在の構造へ組み込む
            body.append(f"    {target_name}{annotation} = {expression}")
        # source_nameへこの工程で使用する値を設定する
        source_name = target_name

    # 次の値または処理を現在の構造へ組み込む
    body.append(f"    return {source_name}")
    # 処理結果を呼び出し元へ返す
    return "def solve(xs: list[int], k: int) -> list[int]:\n" + "\n".join(body) + "\n"


# この工程を担当する関数を定義する
def _local_annotation(name: str, enabled: bool, annotated_names: set[str]) -> str:
    # 条件を満たす場合だけ次の処理を行う
    if enabled and name not in annotated_names:
        # 次の値または処理を現在の構造へ組み込む
        annotated_names.add(name)
        # 処理結果を呼び出し元へ返す
        return ": list[int]"
    # 処理結果を呼び出し元へ返す
    return ""


# この工程を担当する関数を定義する
def _render_expression(
    # 次の値または処理を現在の構造へ組み込む
    operation: Operation, operation_style: Mapping[str, Any], source: str
# 次の値または処理を現在の構造へ組み込む
) -> str:
    # formへこの工程で使用する値を設定する
    form = str(operation_style["expression_form"])
    # 条件を満たす場合だけ次の処理を行う
    if operation.kind == "filter":
        # element_nameへこの工程で使用する値を設定する
        element_name = str(operation_style["element_name"])
        # conditionへこの工程で使用する値を設定する
        condition = _filter_condition(
            # 次の値または処理を現在の構造へ組み込む
            operation.name,
            # 次の値または処理を現在の構造へ組み込む
            element_name,
            # 次の値または処理を現在の構造へ組み込む
            str(operation_style["condition_direction"]),
        )
        # 処理結果を呼び出し元へ返す
        return f"[{element_name} for {element_name} in {source} if {condition}]"
    # 条件を満たす場合だけ次の処理を行う
    if operation.kind == "map":
        # element_nameへこの工程で使用する値を設定する
        element_name = str(operation_style["element_name"])
        # mappedへこの工程で使用する値を設定する
        mapped = _map_expression(operation, element_name, form)
        # 処理結果を呼び出し元へ返す
        return f"[{mapped} for {element_name} in {source}]"
    # 条件を満たす場合だけ次の処理を行う
    if operation.kind == "order":
        # 条件を満たす場合だけ次の処理を行う
        if operation.name == "ascending":
            # 処理結果を呼び出し元へ返す
            return f"sorted({source})" if form == "default" else f"sorted({source}, reverse=False)"
        # 条件を満たす場合だけ次の処理を行う
        if operation.name == "descending":
            # 処理結果を呼び出し元へ返す
            return (
                # 次の値または処理を現在の構造へ組み込む
                f"sorted({source}, reverse=True)"
                # 条件を満たす場合だけ次の処理を行う
                if form == "reverse_keyword"
                # それまでの条件に該当しない場合を処理する
                else f"sorted({source})[::-1]"
            )
        # 処理結果を呼び出し元へ返す
        return f"{source}[::-1]" if form == "slice_notation" else f"list(reversed({source}))"
    # 条件を満たす場合だけ次の処理を行う
    if operation.name == "take_first_k":
        # 処理結果を呼び出し元へ返す
        return f"{source}[:k]" if form == "implicit_start" else f"{source}[0:k]"
    # 条件を満たす場合だけ次の処理を行う
    if operation.name == "take_last_k":
        # 処理結果を呼び出し元へ返す
        return f"{source}[-k:]" if form == "implicit_step" else f"{source}[-k::]"
    # 処理結果を呼び出し元へ返す
    return f"{source}[::2]" if form == "implicit_start" else f"{source}[0::2]"


# この工程を担当する関数を定義する
def _filter_condition(name: str, element: str, direction: str) -> str:
    # normalへこの工程で使用する値を設定する
    normal = {
        # 出力レコードの項目と値を設定する
        "even": f"{element} % 2 == 0",
        # 出力レコードの項目と値を設定する
        "odd": f"{element} % 2 != 0",
        # 出力レコードの項目と値を設定する
        "gt_k": f"{element} > k",
        # 出力レコードの項目と値を設定する
        "ge_k": f"{element} >= k",
        # 出力レコードの項目と値を設定する
        "lt_k": f"{element} < k",
        # 出力レコードの項目と値を設定する
        "le_k": f"{element} <= k",
        # 出力レコードの項目と値を設定する
        "multiple_of_k": f"{element} % k == 0",
        # 出力レコードの項目と値を設定する
        "positive": f"{element} > 0",
        # 出力レコードの項目と値を設定する
        "negative": f"{element} < 0",
        # 出力レコードの項目と値を設定する
        "zero": f"{element} == 0",
    }
    # swappedへこの工程で使用する値を設定する
    swapped = {
        # 出力レコードの項目と値を設定する
        "even": f"0 == {element} % 2",
        # 出力レコードの項目と値を設定する
        "odd": f"0 != {element} % 2",
        # 出力レコードの項目と値を設定する
        "gt_k": f"k < {element}",
        # 出力レコードの項目と値を設定する
        "ge_k": f"k <= {element}",
        # 出力レコードの項目と値を設定する
        "lt_k": f"k > {element}",
        # 出力レコードの項目と値を設定する
        "le_k": f"k >= {element}",
        # 出力レコードの項目と値を設定する
        "multiple_of_k": f"0 == {element} % k",
        # 出力レコードの項目と値を設定する
        "positive": f"0 < {element}",
        # 出力レコードの項目と値を設定する
        "negative": f"0 > {element}",
        # 出力レコードの項目と値を設定する
        "zero": f"0 == {element}",
    }
    # 処理結果を呼び出し元へ返す
    return normal[name] if direction == "normal" else swapped[name]


# この工程を担当する関数を定義する
def _map_expression(operation: Operation, element: str, form: str) -> str:
    # 条件を満たす場合だけ次の処理を行う
    if operation.name == "add_k":
        # 処理結果を呼び出し元へ返す
        return f"{element} + k"
    # 条件を満たす場合だけ次の処理を行う
    if operation.name == "sub_k":
        # 処理結果を呼び出し元へ返す
        return f"{element} - k"
    # 条件を満たす場合だけ次の処理を行う
    if operation.name == "mul_k":
        # 処理結果を呼び出し元へ返す
        return f"{element} * k"
    # 条件を満たす場合だけ次の処理を行う
    if operation.name == "mul_const":
        # 処理結果を呼び出し元へ返す
        return f"{element} * {operation.argument}"
    # 条件を満たす場合だけ次の処理を行う
    if operation.name == "negate":
        # 処理結果を呼び出し元へ返す
        return f"-{element}"
    # 条件を満たす場合だけ次の処理を行う
    if operation.name == "abs":
        # 処理結果を呼び出し元へ返す
        return f"abs({element})"
    # 処理結果を呼び出し元へ返す
    return f"{element} * {element}" if form == "multiply" else f"{element} ** 2"


# この工程を担当する関数を定義する
def _expression_forms(operation: Operation) -> frozenset[str]:
    # 条件を満たす場合だけ次の処理を行う
    if operation.kind == "filter":
        # 処理結果を呼び出し元へ返す
        return frozenset({"default"})
    # 条件を満たす場合だけ次の処理を行う
    if operation.kind == "map":
        # 処理結果を呼び出し元へ返す
        return frozenset({"multiply", "power"}) if operation.name == "square" else frozenset({"default"})
    # 条件を満たす場合だけ次の処理を行う
    if operation.kind == "order":
        # formsへこの工程で使用する値を設定する
        forms = {
            # 出力レコードの項目と値を設定する
            "ascending": {"default", "reverse_false"},
            # 出力レコードの項目と値を設定する
            "descending": {"reverse_keyword", "sort_then_slice"},
            # 出力レコードの項目と値を設定する
            "reverse": {"slice_notation", "reversed_call"},
        }
        # 処理結果を呼び出し元へ返す
        return frozenset(forms[operation.name])
    # formsへこの工程で使用する値を設定する
    forms = {
        # 出力レコードの項目と値を設定する
        "take_first_k": {"implicit_start", "explicit_zero"},
        # 出力レコードの項目と値を設定する
        "take_last_k": {"implicit_step", "explicit_empty_step"},
        # 出力レコードの項目と値を設定する
        "every_other": {"implicit_start", "explicit_zero"},
    }
    # 処理結果を呼び出し元へ返す
    return frozenset(forms[operation.name])


# この工程を担当する関数を定義する
def expression_forms(operation: Operation) -> tuple[str, ...]:
    """複製器が使用する、安定した順序の実装表現一覧。"""

    # 処理結果を呼び出し元へ返す
    return tuple(sorted(_expression_forms(operation)))


# この工程を担当する関数を定義する
def _comment_for(operation: Operation) -> str:
    # commentsへこの工程で使用する値を設定する
    comments = {
        # 次の値または処理を現在の構造へ組み込む
        ("filter", "even"): "偶数だけを残す",
        # 次の値または処理を現在の構造へ組み込む
        ("filter", "odd"): "奇数だけを残す",
        # 次の値または処理を現在の構造へ組み込む
        ("filter", "gt_k"): "kより大きい値だけを残す",
        # 次の値または処理を現在の構造へ組み込む
        ("filter", "ge_k"): "k以上の値だけを残す",
        # 次の値または処理を現在の構造へ組み込む
        ("filter", "lt_k"): "kより小さい値だけを残す",
        # 次の値または処理を現在の構造へ組み込む
        ("filter", "le_k"): "k以下の値だけを残す",
        # 次の値または処理を現在の構造へ組み込む
        ("filter", "multiple_of_k"): "kの倍数だけを残す",
        # 次の値または処理を現在の構造へ組み込む
        ("filter", "positive"): "正の値だけを残す",
        # 次の値または処理を現在の構造へ組み込む
        ("filter", "negative"): "負の値だけを残す",
        # 次の値または処理を現在の構造へ組み込む
        ("filter", "zero"): "ゼロだけを残す",
        # 次の値または処理を現在の構造へ組み込む
        ("map", "add_k"): "各要素にkを加える",
        # 次の値または処理を現在の構造へ組み込む
        ("map", "sub_k"): "各要素からkを引く",
        # 次の値または処理を現在の構造へ組み込む
        ("map", "mul_k"): "各要素にkを掛ける",
        # 次の値または処理を現在の構造へ組み込む
        ("map", "mul_const"): f"各要素を{operation.argument}倍する",
        # 次の値または処理を現在の構造へ組み込む
        ("map", "negate"): "各要素の符号を反転する",
        # 次の値または処理を現在の構造へ組み込む
        ("map", "abs"): "各要素の絶対値を取る",
        # 次の値または処理を現在の構造へ組み込む
        ("map", "square"): "各要素を二乗する",
        # 次の値または処理を現在の構造へ組み込む
        ("order", "ascending"): "昇順に並べる",
        # 次の値または処理を現在の構造へ組み込む
        ("order", "descending"): "降順に並べる",
        # 次の値または処理を現在の構造へ組み込む
        ("order", "reverse"): "現在の要素順を反転する",
        # 次の値または処理を現在の構造へ組み込む
        ("slice", "take_first_k"): "先頭からk個を取る",
        # 次の値または処理を現在の構造へ組み込む
        ("slice", "take_last_k"): "末尾からk個を取る",
        # 次の値または処理を現在の構造へ組み込む
        ("slice", "every_other"): "先頭から1個おきに取る",
    }
    # 処理結果を呼び出し元へ返す
    return comments[(operation.kind, operation.name)]


# この工程を担当する関数を定義する
def _validate_signature(function: ast.FunctionDef) -> None:
    # argumentsへこの工程で使用する値を設定する
    arguments = function.args
    # 条件を満たす場合だけ次の処理を行う
    if (
        # 次の値または処理を現在の構造へ組み込む
        arguments.posonlyargs
        # 次の値または処理を現在の構造へ組み込む
        or arguments.vararg is not None
        # 次の値または処理を現在の構造へ組み込む
        or arguments.kwonlyargs
        # 次の値または処理を現在の構造へ組み込む
        or arguments.kwarg is not None
        # 次の値または処理を現在の構造へ組み込む
        or arguments.defaults
        # 次の値または処理を現在の構造へ組み込む
        or arguments.kw_defaults
        # 次の値または処理を現在の構造へ組み込む
        or [argument.arg for argument in arguments.args] != ["xs", "k"]
    # 次の値または処理を現在の構造へ組み込む
    ):
        # 不正な状態を例外として通知して処理を停止する
        raise GeneratedCodeSafetyError("solveの引数はxsとkの2個に固定します")

    # expected_list_intへこの工程で使用する値を設定する
    expected_list_int = ast.Subscript(
        # valueへこの工程で使用する値を設定する
        value=ast.Name(id="list", ctx=ast.Load()),
        # sliceへこの工程で使用する値を設定する
        slice=ast.Name(id="int", ctx=ast.Load()),
        # ctxへこの工程で使用する値を設定する
        ctx=ast.Load(),
    )
    # 条件を満たす場合だけ次の処理を行う
    if arguments.args[0].annotation is None or ast.dump(arguments.args[0].annotation) != ast.dump(
        # 次の値または処理を現在の構造へ組み込む
        expected_list_int
    # 次の値または処理を現在の構造へ組み込む
    ):
        # 不正な状態を例外として通知して処理を停止する
        raise GeneratedCodeSafetyError("xsの型注釈はlist[int]に固定します")
    # 条件を満たす場合だけ次の処理を行う
    if not isinstance(arguments.args[1].annotation, ast.Name) or arguments.args[1].annotation.id != "int":
        # 不正な状態を例外として通知して処理を停止する
        raise GeneratedCodeSafetyError("kの型注釈はintに固定します")
    # 条件を満たす場合だけ次の処理を行う
    if function.returns is None or ast.dump(function.returns) != ast.dump(expected_list_int):
        # 不正な状態を例外として通知して処理を停止する
        raise GeneratedCodeSafetyError("戻り値の型注釈はlist[int]に固定します")
