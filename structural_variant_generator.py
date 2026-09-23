"""同じ意味ASTに対する構造的変種を決定的に列挙する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# 必要な定義を対象モジュールから読み込む
from itertools import product
# 必要な定義を対象モジュールから読み込む
from typing import Any, Iterable, Mapping, Sequence

# 必要な定義を対象モジュールから読み込む
from python_code_generator import (
    # 次の値または処理を現在の構造へ組み込む
    GeneratorConfig,
    # 次の値または処理を現在の構造へ組み込む
    Operation,
    # 次の値または処理を現在の構造へ組み込む
    canonical_json,
    # 次の値または処理を現在の構造へ組み込む
    expression_forms,
    # 次の値または処理を現在の構造へ組み込む
    normalize_semantic_ast,
    # 次の値または処理を現在の構造へ組み込む
    semantic_hash,
    # 次の値または処理を現在の構造へ組み込む
    sha256_text,
    # 次の値または処理を現在の構造へ組み込む
    style_id,
)


# 関連する状態と処理をまとめるクラスを定義する
class StructuralVariantGenerator:
    """意味ASTと両立するstyle_specを作る複製器。"""

    # この工程を担当する関数を定義する
    def __init__(self, config: GeneratorConfig, seed: int = 0) -> None:
        # self.configへこの工程で使用する値を設定する
        self.config = config
        # self.seedへこの工程で使用する値を設定する
        self.seed = seed

    # この工程を担当する関数を定義する
    def enumerate(
        # 次の値または処理を現在の構造へ組み込む
        self,
        # 次の値または処理を現在の構造へ組み込む
        semantic_ast: Mapping[str, Any],
        # limitへこの工程で使用する値を設定する
        limit: int | None = None,
    # 次の値または処理を現在の構造へ組み込む
    ) -> list[dict[str, Any]]:
        """同じ入力とseedから同じ順序のstyle_specを返す。"""

        # 条件を満たす場合だけ次の処理を行う
        if limit is not None and limit <= 0:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("limitは正の整数またはNoneにしてください")
        # operationsへこの工程で使用する値を設定する
        operations = normalize_semantic_ast(semantic_ast)
        # variantsへこの工程で使用する値を設定する
        variants = list(self._raw_variants(operations))

        # uniqueへこの工程で使用する値を設定する
        unique: dict[str, dict[str, Any]] = {}
        # 対象を一件ずつ取り出して処理する
        for variant in variants:
            # 次の値または処理を現在の構造へ組み込む
            unique.setdefault(canonical_json(variant), variant)

        # semanticへこの工程で使用する値を設定する
        semantic = semantic_hash(semantic_ast)
        # orderedへこの工程で使用する値を設定する
        ordered = sorted(
            # 次の値または処理を現在の構造へ組み込む
            unique.values(),
            # keyへこの工程で使用する値を設定する
            key=lambda variant: self._rank_key(semantic, style_id(variant)),
        )
        # 処理結果を呼び出し元へ返す
        return ordered if limit is None else ordered[:limit]

    # この工程を担当する関数を定義する
    def _raw_variants(self, operations: Sequence[Operation]) -> Iterable[dict[str, Any]]:
        # 対象を一件ずつ取り出して処理する
        for comments in ("none", "present"):
            # 対象を一件ずつ取り出して処理する
            for operation_styles in self._direct_operation_styles(operations):
                # 生成した値を呼び出し元へ一件ずつ返す
                yield self._style_spec(
                    # 次の値または処理を現在の構造へ組み込む
                    operations,
                    # 次の値または処理を現在の構造へ組み込む
                    operation_styles,
                    # layoutへこの工程で使用する値を設定する
                    layout="single_return",
                    # commentsへこの工程で使用する値を設定する
                    comments=comments,
                    # local_annotationsへこの工程で使用する値を設定する
                    local_annotations=False,
                )

        # 対象を一件ずつ取り出して処理する
        for comments in ("none", "present"):
            # 対象を一件ずつ取り出して処理する
            for local_annotations in (False, True):
                # 対象を一件ずつ取り出して処理する
                for operation_styles in self._staged_operation_styles(operations):
                    # 生成した値を呼び出し元へ一件ずつ返す
                    yield self._style_spec(
                        # 次の値または処理を現在の構造へ組み込む
                        operations,
                        # 次の値または処理を現在の構造へ組み込む
                        operation_styles,
                        # layoutへこの工程で使用する値を設定する
                        layout="multi_statement",
                        # commentsへこの工程で使用する値を設定する
                        comments=comments,
                        # local_annotationsへこの工程で使用する値を設定する
                        local_annotations=local_annotations,
                    )

    # この工程を担当する関数を定義する
    def _direct_operation_styles(
        # 次の値または処理を現在の構造へ組み込む
        self, operations: Sequence[Operation]
    # 次の値または処理を現在の構造へ組み込む
    ) -> Iterable[tuple[dict[str, Any], ...]]:
        # axesへこの工程で使用する値を設定する
        axes = [self._operation_choices(operation, staged=False) for operation in operations]
        # 生成した値を呼び出し元へ一件ずつ返す
        yield from product(*axes)

    # この工程を担当する関数を定義する
    def _staged_operation_styles(
        # 次の値または処理を現在の構造へ組み込む
        self, operations: Sequence[Operation]
    # 次の値または処理を現在の構造へ組み込む
    ) -> Iterable[tuple[dict[str, Any], ...]]:
        # axesへこの工程で使用する値を設定する
        axes = [self._operation_choices(operation, staged=True) for operation in operations]
        # 対象を一件ずつ取り出して処理する
        for choices in product(*axes):
            # 対象を一件ずつ取り出して処理する
            for result_names in product(self.config.result_names, repeat=len(operations)):
                # source_nameへこの工程で使用する値を設定する
                source_name = "xs"
                # validへこの工程で使用する値を設定する
                valid = True
                # styledへこの工程で使用する値を設定する
                styled: list[dict[str, Any]] = []
                # 対象を一件ずつ取り出して処理する
                for choice, target_name in zip(choices, result_names):
                    # 条件を満たす場合だけ次の処理を行う
                    if choice["collection_form"] == "for_loop" and target_name == source_name:
                        # validへこの工程で使用する値を設定する
                        valid = False
                        # 条件を満たしたため繰り返しを終了する
                        break
                    # with_targetへこの工程で使用する値を設定する
                    with_target = dict(choice)
                    # 次の値または処理を現在の構造へ組み込む
                    with_target["result_name"] = target_name
                    # 次の値または処理を現在の構造へ組み込む
                    styled.append(with_target)
                    # source_nameへこの工程で使用する値を設定する
                    source_name = target_name
                # 条件を満たす場合だけ次の処理を行う
                if valid:
                    # 生成した値を呼び出し元へ一件ずつ返す
                    yield tuple(styled)

    # この工程を担当する関数を定義する
    def _operation_choices(
        # 次の値または処理を現在の構造へ組み込む
        self, operation: Operation, staged: bool
    # 次の値または処理を現在の構造へ組み込む
    ) -> tuple[dict[str, Any], ...]:
        # 次の値または処理を現在の構造へ組み込む
        element_names: tuple[str | None, ...]
        # 次の値または処理を現在の構造へ組み込む
        collection_forms: tuple[str | None, ...]
        # 次の値または処理を現在の構造へ組み込む
        directions: tuple[str | None, ...]

        # 条件を満たす場合だけ次の処理を行う
        if operation.kind in {"filter", "map"}:
            # element_namesへこの工程で使用する値を設定する
            element_names = self.config.element_names
            # collection_formsへこの工程で使用する値を設定する
            collection_forms = (
                # 次の値または処理を現在の構造へ組み込む
                ("list_comprehension", "for_loop")
                # 条件を満たす場合だけ次の処理を行う
                if staged
                # それまでの条件に該当しない場合を処理する
                else ("list_comprehension",)
            )
        # それまでの条件に該当しない場合を処理する
        else:
            # element_namesへこの工程で使用する値を設定する
            element_names = (None,)
            # collection_formsへこの工程で使用する値を設定する
            collection_forms = (None,)

        # directionsへこの工程で使用する値を設定する
        directions = ("normal", "swapped") if operation.kind == "filter" else (None,)
        # choicesへこの工程で使用する値を設定する
        choices: list[dict[str, Any]] = []
        # 対象を一件ずつ取り出して処理する
        for collection_form, element_name, direction, expression_form in product(
            # 次の値または処理を現在の構造へ組み込む
            collection_forms,
            # 次の値または処理を現在の構造へ組み込む
            element_names,
            # 次の値または処理を現在の構造へ組み込む
            directions,
            # 次の値または処理を現在の構造へ組み込む
            expression_forms(operation),
        # 次の値または処理を現在の構造へ組み込む
        ):
            # 次の値または処理を現在の構造へ組み込む
            choices.append(
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "collection_form": collection_form,
                    # 出力レコードの項目と値を設定する
                    "element_name": element_name,
                    # 出力レコードの項目と値を設定する
                    "result_name": None,
                    # 出力レコードの項目と値を設定する
                    "condition_direction": direction,
                    # 出力レコードの項目と値を設定する
                    "expression_form": expression_form,
                }
            )
        # 処理結果を呼び出し元へ返す
        return tuple(choices)

    # この工程を担当する関数を定義する
    def _style_spec(
        # 次の値または処理を現在の構造へ組み込む
        self,
        # 次の値または処理を現在の構造へ組み込む
        operations: Sequence[Operation],
        # 次の値または処理を現在の構造へ組み込む
        operation_styles: Sequence[Mapping[str, Any]],
        # 次の値または処理を現在の構造へ組み込む
        layout: str,
        # 次の値または処理を現在の構造へ組み込む
        comments: str,
        # 次の値または処理を現在の構造へ組み込む
        local_annotations: bool,
    # 次の値または処理を現在の構造へ組み込む
    ) -> dict[str, Any]:
        # collection_valuesへこの工程で使用する値を設定する
        collection_values = [
            # 次の値または処理を現在の構造へ組み込む
            item["collection_form"]
            # 対象を一件ずつ取り出して処理する
            for item in operation_styles
            # 条件を満たす場合だけ次の処理を行う
            if item["collection_form"] is not None
        ]
        # 条件を満たす場合だけ次の処理を行う
        if not collection_values:
            # collection_formへこの工程で使用する値を設定する
            collection_form: str | None = None
        # 前の条件に該当せず、この条件を満たす場合を処理する
        elif all(value == "list_comprehension" for value in collection_values):
            # collection_formへこの工程で使用する値を設定する
            collection_form = "list_comprehension"
        # 前の条件に該当せず、この条件を満たす場合を処理する
        elif all(value == "for_loop" for value in collection_values):
            # collection_formへこの工程で使用する値を設定する
            collection_form = "for_loop"
        # それまでの条件に該当しない場合を処理する
        else:
            # collection_formへこの工程で使用する値を設定する
            collection_form = "mixed"

        # 条件を満たす場合だけ次の処理を行う
        if layout == "single_return":
            # temporary_formへこの工程で使用する値を設定する
            temporary_form = "direct_return"
            # code_styleへこの工程で使用する値を設定する
            code_style = "expression_comprehension"
        # それまでの条件に該当しない場合を処理する
        else:
            # result_namesへこの工程で使用する値を設定する
            result_names = [str(item["result_name"]) for item in operation_styles]
            # temporary_formへこの工程で使用する値を設定する
            temporary_form = (
                # この処理で扱う文字列を一覧へ加える
                "fresh_names" if len(set(result_names)) == len(result_names) else "reused_names"
            )
            # 条件を満たす場合だけ次の処理を行う
            if collection_form == "for_loop":
                # code_styleへこの工程で使用する値を設定する
                code_style = "staged_loop"
            # 前の条件に該当せず、この条件を満たす場合を処理する
            elif collection_form == "mixed":
                # code_styleへこの工程で使用する値を設定する
                code_style = "mixed"
            # それまでの条件に該当しない場合を処理する
            else:
                # code_styleへこの工程で使用する値を設定する
                code_style = "staged_comprehension"

        # 処理結果を呼び出し元へ返す
        return {
            # 出力レコードの項目と値を設定する
            "code_style": code_style,
            # 出力レコードの項目と値を設定する
            "collection_form": collection_form,
            # 出力レコードの項目と値を設定する
            "temporary_form": temporary_form,
            # 出力レコードの項目と値を設定する
            "name_set": "configured",
            # 出力レコードの項目と値を設定する
            "layout": layout,
            # 出力レコードの項目と値を設定する
            "comments": comments,
            # 出力レコードの項目と値を設定する
            "local_annotations": local_annotations,
            # 出力レコードの項目と値を設定する
            "square_form": self._single_form(operations, operation_styles, "map", "square"),
            # 出力レコードの項目と値を設定する
            "ascending_form": self._single_form(operations, operation_styles, "order", "ascending"),
            # 出力レコードの項目と値を設定する
            "descending_form": self._single_form(operations, operation_styles, "order", "descending"),
            # 出力レコードの項目と値を設定する
            "reverse_form": self._single_form(operations, operation_styles, "order", "reverse"),
            # 出力レコードの項目と値を設定する
            "slice_form": self._slice_forms(operations, operation_styles),
            # 出力レコードの項目と値を設定する
            "operation_styles": [dict(item) for item in operation_styles],
        }

    # 直後の定義へデコレータを適用する
    @staticmethod
    # この工程を担当する関数を定義する
    def _single_form(
        # 次の値または処理を現在の構造へ組み込む
        operations: Sequence[Operation],
        # 次の値または処理を現在の構造へ組み込む
        styles: Sequence[Mapping[str, Any]],
        # 次の値または処理を現在の構造へ組み込む
        kind: str,
        # 次の値または処理を現在の構造へ組み込む
        name: str,
    # 次の値または処理を現在の構造へ組み込む
    ) -> str | list[str] | None:
        # valuesへこの工程で使用する値を設定する
        values = [
            # 次の値または処理を現在の構造へ組み込む
            str(style["expression_form"])
            # 対象を一件ずつ取り出して処理する
            for operation, style in zip(operations, styles)
            # 条件を満たす場合だけ次の処理を行う
            if operation.kind == kind and operation.name == name
        ]
        # 条件を満たす場合だけ次の処理を行う
        if not values:
            # 処理結果を呼び出し元へ返す
            return None
        # 処理結果を呼び出し元へ返す
        return values[0] if len(values) == 1 else values

    # 直後の定義へデコレータを適用する
    @staticmethod
    # この工程を担当する関数を定義する
    def _slice_forms(
        # 次の値または処理を現在の構造へ組み込む
        operations: Sequence[Operation], styles: Sequence[Mapping[str, Any]]
    # 次の値または処理を現在の構造へ組み込む
    ) -> list[str] | None:
        # valuesへこの工程で使用する値を設定する
        values = [
            # 次の値または処理を現在の構造へ組み込む
            str(style["expression_form"])
            # 対象を一件ずつ取り出して処理する
            for operation, style in zip(operations, styles)
            # 条件を満たす場合だけ次の処理を行う
            if operation.kind == "slice"
        ]
        # 処理結果を呼び出し元へ返す
        return values or None

    # この工程を担当する関数を定義する
    def _rank_key(self, semantic: str, candidate_style_id: str) -> str:
        # 処理結果を呼び出し元へ返す
        return sha256_text(f"{semantic}\0{candidate_style_id}\0{self.seed}")
