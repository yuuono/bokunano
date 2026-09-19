"""同じ意味ASTに対する構造的変種を決定的に列挙する。"""

from __future__ import annotations

from itertools import product
from typing import Any, Iterable, Mapping, Sequence

from python_code_generator import (
    GeneratorConfig,
    Operation,
    canonical_json,
    expression_forms,
    normalize_semantic_ast,
    semantic_hash,
    sha256_text,
    style_id,
)


class StructuralVariantGenerator:
    """意味ASTと両立するstyle_specを作る複製器。"""

    def __init__(self, config: GeneratorConfig, seed: int = 0) -> None:
        self.config = config
        self.seed = seed

    def enumerate(
        self,
        semantic_ast: Mapping[str, Any],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """同じ入力とseedから同じ順序のstyle_specを返す。"""

        if limit is not None and limit <= 0:
            raise ValueError("limitは正の整数またはNoneにしてください")
        operations = normalize_semantic_ast(semantic_ast)
        variants = list(self._raw_variants(operations))

        unique: dict[str, dict[str, Any]] = {}
        for variant in variants:
            unique.setdefault(canonical_json(variant), variant)

        semantic = semantic_hash(semantic_ast)
        ordered = sorted(
            unique.values(),
            key=lambda variant: self._rank_key(semantic, style_id(variant)),
        )
        return ordered if limit is None else ordered[:limit]

    def _raw_variants(self, operations: Sequence[Operation]) -> Iterable[dict[str, Any]]:
        for comments in ("none", "present"):
            for operation_styles in self._direct_operation_styles(operations):
                yield self._style_spec(
                    operations,
                    operation_styles,
                    layout="single_return",
                    comments=comments,
                    local_annotations=False,
                )

        for comments in ("none", "present"):
            for local_annotations in (False, True):
                for operation_styles in self._staged_operation_styles(operations):
                    yield self._style_spec(
                        operations,
                        operation_styles,
                        layout="multi_statement",
                        comments=comments,
                        local_annotations=local_annotations,
                    )

    def _direct_operation_styles(
        self, operations: Sequence[Operation]
    ) -> Iterable[tuple[dict[str, Any], ...]]:
        axes = [self._operation_choices(operation, staged=False) for operation in operations]
        yield from product(*axes)

    def _staged_operation_styles(
        self, operations: Sequence[Operation]
    ) -> Iterable[tuple[dict[str, Any], ...]]:
        axes = [self._operation_choices(operation, staged=True) for operation in operations]
        for choices in product(*axes):
            for result_names in product(self.config.result_names, repeat=len(operations)):
                source_name = "xs"
                valid = True
                styled: list[dict[str, Any]] = []
                for choice, target_name in zip(choices, result_names):
                    if choice["collection_form"] == "for_loop" and target_name == source_name:
                        valid = False
                        break
                    with_target = dict(choice)
                    with_target["result_name"] = target_name
                    styled.append(with_target)
                    source_name = target_name
                if valid:
                    yield tuple(styled)

    def _operation_choices(
        self, operation: Operation, staged: bool
    ) -> tuple[dict[str, Any], ...]:
        element_names: tuple[str | None, ...]
        collection_forms: tuple[str | None, ...]
        directions: tuple[str | None, ...]

        if operation.kind in {"filter", "map"}:
            element_names = self.config.element_names
            collection_forms = (
                ("list_comprehension", "for_loop")
                if staged
                else ("list_comprehension",)
            )
        else:
            element_names = (None,)
            collection_forms = (None,)

        directions = ("normal", "swapped") if operation.kind == "filter" else (None,)
        choices: list[dict[str, Any]] = []
        for collection_form, element_name, direction, expression_form in product(
            collection_forms,
            element_names,
            directions,
            expression_forms(operation),
        ):
            choices.append(
                {
                    "collection_form": collection_form,
                    "element_name": element_name,
                    "result_name": None,
                    "condition_direction": direction,
                    "expression_form": expression_form,
                }
            )
        return tuple(choices)

    def _style_spec(
        self,
        operations: Sequence[Operation],
        operation_styles: Sequence[Mapping[str, Any]],
        layout: str,
        comments: str,
        local_annotations: bool,
    ) -> dict[str, Any]:
        collection_values = [
            item["collection_form"]
            for item in operation_styles
            if item["collection_form"] is not None
        ]
        if not collection_values:
            collection_form: str | None = None
        elif all(value == "list_comprehension" for value in collection_values):
            collection_form = "list_comprehension"
        elif all(value == "for_loop" for value in collection_values):
            collection_form = "for_loop"
        else:
            collection_form = "mixed"

        if layout == "single_return":
            temporary_form = "direct_return"
            code_style = "expression_comprehension"
        else:
            result_names = [str(item["result_name"]) for item in operation_styles]
            temporary_form = (
                "fresh_names" if len(set(result_names)) == len(result_names) else "reused_names"
            )
            if collection_form == "for_loop":
                code_style = "staged_loop"
            elif collection_form == "mixed":
                code_style = "mixed"
            else:
                code_style = "staged_comprehension"

        return {
            "code_style": code_style,
            "collection_form": collection_form,
            "temporary_form": temporary_form,
            "name_set": "configured",
            "layout": layout,
            "comments": comments,
            "local_annotations": local_annotations,
            "square_form": self._single_form(operations, operation_styles, "map", "square"),
            "ascending_form": self._single_form(operations, operation_styles, "order", "ascending"),
            "descending_form": self._single_form(operations, operation_styles, "order", "descending"),
            "reverse_form": self._single_form(operations, operation_styles, "order", "reverse"),
            "slice_form": self._slice_forms(operations, operation_styles),
            "operation_styles": [dict(item) for item in operation_styles],
        }

    @staticmethod
    def _single_form(
        operations: Sequence[Operation],
        styles: Sequence[Mapping[str, Any]],
        kind: str,
        name: str,
    ) -> str | list[str] | None:
        values = [
            str(style["expression_form"])
            for operation, style in zip(operations, styles)
            if operation.kind == kind and operation.name == name
        ]
        if not values:
            return None
        return values[0] if len(values) == 1 else values

    @staticmethod
    def _slice_forms(
        operations: Sequence[Operation], styles: Sequence[Mapping[str, Any]]
    ) -> list[str] | None:
        values = [
            str(style["expression_form"])
            for operation, style in zip(operations, styles)
            if operation.kind == "slice"
        ]
        return values or None

    def _rank_key(self, semantic: str, candidate_style_id: str) -> str:
        return sha256_text(f"{semantic}\0{candidate_style_id}\0{self.seed}")
