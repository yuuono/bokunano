"""Pythonの各論理行に直前の説明コメントがあることを検査・補完する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# この処理で使う標準または外部モジュールを読み込む
import argparse
# この処理で使う標準または外部モジュールを読み込む
import io
# 必要な定義を対象モジュールから読み込む
from pathlib import Path
# この処理で使う標準または外部モジュールを読み込む
import re
# この処理で使う標準または外部モジュールを読み込む
import tokenize


# PROJECT_ROOTへこの工程で使用する値を設定する
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# EXCLUDED_PARTSへこの工程で使用する値を設定する
EXCLUDED_PARTS = {".git", ".venv", "__pycache__"}
# ONLY_CLOSING_TOKENSへこの工程で使用する値を設定する
ONLY_CLOSING_TOKENS = re.compile(r"^[\]\)},]+[,]?$")


# この工程を担当する関数を定義する
def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""

    # parserへこの工程で使用する値を設定する
    parser = argparse.ArgumentParser(
        # descriptionへこの工程で使用する値を設定する
        description="Pythonの処理行に日本語コメントがあることを確認します。"
    )
    # 次の値または処理を現在の構造へ組み込む
    parser.add_argument(
        # この処理で扱う文字列を一覧へ加える
        "--write",
        # actionへこの工程で使用する値を設定する
        action="store_true",
        # helpへこの工程で使用する値を設定する
        help="コメントがない処理行の直前へ説明コメントを追加します。",
    )
    # 処理結果を呼び出し元へ返す
    return parser.parse_args()


# この工程を担当する関数を定義する
def main() -> None:
    """リポジトリ内のPythonファイルを一括検査する。"""

    # argsへこの工程で使用する値を設定する
    args = parse_args()
    # pathsへこの工程で使用する値を設定する
    paths = _python_paths(PROJECT_ROOT)
    # changedへこの工程で使用する値を設定する
    changed = 0
    # missing_totalへこの工程で使用する値を設定する
    missing_total = 0
    # 対象を一件ずつ取り出して処理する
    for path in paths:
        # sourceへこの工程で使用する値を設定する
        source = path.read_text(encoding="utf-8")
        # missingへこの工程で使用する値を設定する
        missing = _uncommented_line_indexes(source)
        # 次の値または処理を現在の構造へ組み込む
        missing_total += len(missing)
        # 条件を満たす場合だけ次の処理を行う
        if args.write and missing:
            # 次の値または処理を現在の構造へ組み込む
            path.write_text(_add_comments(source, missing), encoding="utf-8")
            # 次の値または処理を現在の構造へ組み込む
            changed += 1
        # 前の条件に該当せず、この条件を満たす場合を処理する
        elif missing:
            # relativeへこの工程で使用する値を設定する
            relative = path.relative_to(PROJECT_ROOT)
            # 処理結果を利用者へ表示する
            print(f"{relative}: {', '.join(str(index + 1) for index in missing)}")
    # 条件を満たす場合だけ次の処理を行う
    if args.write:
        # 処理結果を利用者へ表示する
        print(f"コメント補完完了: files={changed}, lines={missing_total}")
        # 処理結果を呼び出し元へ返す
        return
    # 条件を満たす場合だけ次の処理を行う
    if missing_total:
        # 不正な状態を例外として通知して処理を停止する
        raise SystemExit(f"説明コメントがない処理行があります: {missing_total}行")
    # 処理結果を利用者へ表示する
    print(f"コメント検査完了: files={len(paths)}, missing=0")


# この工程を担当する関数を定義する
def _python_paths(root: Path) -> list[Path]:
    """仮想環境などを除いたPythonファイルを列挙する。"""

    # 処理結果を呼び出し元へ返す
    return sorted(
        # 次の値または処理を現在の構造へ組み込む
        path
        # 対象を一件ずつ取り出して処理する
        for path in root.rglob("*.py")
        # 条件を満たす場合だけ次の処理を行う
        if not EXCLUDED_PARTS.intersection(path.relative_to(root).parts)
    )


# この工程を担当する関数を定義する
def _uncommented_line_indexes(source: str) -> list[int]:
    """直前または同じ行にコメントがない処理行番号を返す。"""

    # linesへこの工程で使用する値を設定する
    lines = source.splitlines(keepends=True)
    # skippedへこの工程で使用する値を設定する
    skipped = _string_line_indexes(source)
    # inline_commentsへこの工程で使用する値を設定する
    inline_comments = _inline_comment_line_indexes(source)
    # missingへこの工程で使用する値を設定する
    missing: list[int] = []
    # 対象を一件ずつ取り出して処理する
    for index, line in enumerate(lines):
        # strippedへこの工程で使用する値を設定する
        stripped = line.strip()
        # 条件を満たす場合だけ次の処理を行う
        if not stripped or stripped.startswith("#"):
            # 現在の対象を終えて次の対象へ進む
            continue
        # 条件を満たす場合だけ次の処理を行う
        if index in skipped or ONLY_CLOSING_TOKENS.fullmatch(stripped):
            # 現在の対象を終えて次の対象へ進む
            continue
        # 同じ行の実コメントまたは直前の説明コメントがあれば補完済みとみなす
        if index in inline_comments or _has_preceding_comment(lines, index):
            # 現在の対象を終えて次の対象へ進む
            continue
        # 条件を満たす場合だけ次の処理を行う
        if index > 0 and lines[index - 1].rstrip().endswith("\\"):
            # 現在の対象を終えて次の対象へ進む
            continue
        # 次の値または処理を現在の構造へ組み込む
        missing.append(index)
    # 処理結果を呼び出し元へ返す
    return missing


# この工程を担当する関数を定義する
def _string_line_indexes(source: str) -> set[int]:
    """文字列リテラルだけで構成される行と複数行文字列の範囲を返す。"""

    # tokensへこの工程で使用する値を設定する
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    # skippedへこの工程で使用する値を設定する
    skipped: set[int] = set()
    # significant_by_lineへこの工程で使用する値を設定する
    significant_by_line: dict[int, list[tokenize.TokenInfo]] = {}
    # ignored_typesへこの工程で使用する値を設定する
    ignored_types = {
        # 次の値または処理を現在の構造へ組み込む
        tokenize.ENCODING,
        # 次の値または処理を現在の構造へ組み込む
        tokenize.ENDMARKER,
        # 次の値または処理を現在の構造へ組み込む
        tokenize.INDENT,
        # 次の値または処理を現在の構造へ組み込む
        tokenize.DEDENT,
        # 次の値または処理を現在の構造へ組み込む
        tokenize.NEWLINE,
        # 次の値または処理を現在の構造へ組み込む
        tokenize.NL,
        # 次の値または処理を現在の構造へ組み込む
        tokenize.COMMENT,
    }
    # 対象を一件ずつ取り出して処理する
    for token in tokens:
        # 条件を満たす場合だけ次の処理を行う
        # 複数行文字列の内部だけはコメントを挿入できないため範囲ごと除外する
        if token.type == tokenize.STRING and token.start[0] != token.end[0]:
            # 次の値または処理を現在の構造へ組み込む
            skipped.update(range(token.start[0] - 1, token.end[0]))
        # 条件を満たす場合だけ次の処理を行う
        if token.type not in ignored_types:
            # 次の値または処理を現在の構造へ組み込む
            significant_by_line.setdefault(token.start[0] - 1, []).append(token)
    # 対象を一件ずつ取り出して処理する
    for index, line_tokens in significant_by_line.items():
        # 条件を満たす場合だけ次の処理を行う
        if all(token.type == tokenize.STRING for token in line_tokens):
            # 次の値または処理を現在の構造へ組み込む
            skipped.add(index)
    # 処理結果を呼び出し元へ返す
    return skipped


# この工程を担当する関数を定義する
def _inline_comment_line_indexes(source: str) -> set[int]:
    """文字列中の#と区別し、実際のインラインコメント行だけを返す。"""

    # tokensへこの工程で使用する値を設定する
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    # 処理結果を呼び出し元へ返す
    return {
        # コメントトークンの行番号を0始まりへ変換して追加する
        token.start[0] - 1
        # 対象を一件ずつ取り出して処理する
        for token in tokens
        # 条件を満たす場合だけ次の処理を行う
        if token.type == tokenize.COMMENT and token.line[: token.start[1]].strip()
    }


# この工程を担当する関数を定義する
def _has_preceding_comment(lines: list[str], index: int) -> bool:
    """対象行の直前に同じ字下げの説明コメントがあるかを返す。"""

    # 条件を満たす場合だけ次の処理を行う
    if index == 0:
        # 処理結果を呼び出し元へ返す
        return False
    # current_indentへこの工程で使用する値を設定する
    current_indent = len(lines[index]) - len(lines[index].lstrip())
    # previousへこの工程で使用する値を設定する
    previous = lines[index - 1]
    # previous_indentへこの工程で使用する値を設定する
    previous_indent = len(previous) - len(previous.lstrip())
    # 処理結果を呼び出し元へ返す
    return previous.lstrip().startswith("#") and previous_indent == current_indent


# この工程を担当する関数を定義する
def _add_comments(source: str, indexes: list[int]) -> str:
    """指定された各処理行の直前へ内容に応じたコメントを追加する。"""

    # targetsへこの工程で使用する値を設定する
    targets = set(indexes)
    # outputへこの工程で使用する値を設定する
    output: list[str] = []
    # 対象を一件ずつ取り出して処理する
    for index, line in enumerate(source.splitlines(keepends=True)):
        # 条件を満たす場合だけ次の処理を行う
        if index in targets:
            # indentへこの工程で使用する値を設定する
            indent = line[: len(line) - len(line.lstrip())]
            # 次の値または処理を現在の構造へ組み込む
            output.append(f"{indent}# {_comment_for(line.strip())}\n")
        # 次の値または処理を現在の構造へ組み込む
        output.append(line)
    # 処理結果を呼び出し元へ返す
    return "".join(output)


# この工程を担当する関数を定義する
def _comment_for(line: str) -> str:
    """コード行の先頭構文から短い日本語説明を作る。"""

    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("from "):
        # 処理結果を呼び出し元へ返す
        return "必要な定義を対象モジュールから読み込む"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("import "):
        # 処理結果を呼び出し元へ返す
        return "この処理で使う標準または外部モジュールを読み込む"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("class "):
        # 処理結果を呼び出し元へ返す
        return "関連する状態と処理をまとめるクラスを定義する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith(("def ", "async def ")):
        # 処理結果を呼び出し元へ返す
        return "この工程を担当する関数を定義する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("@"):
        # 処理結果を呼び出し元へ返す
        return "直後の定義へデコレータを適用する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("if "):
        # 処理結果を呼び出し元へ返す
        return "条件を満たす場合だけ次の処理を行う"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("elif "):
        # 処理結果を呼び出し元へ返す
        return "前の条件に該当せず、この条件を満たす場合を処理する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("else"):
        # 処理結果を呼び出し元へ返す
        return "それまでの条件に該当しない場合を処理する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith(("for ", "async for ")):
        # 処理結果を呼び出し元へ返す
        return "対象を一件ずつ取り出して処理する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("while "):
        # 処理結果を呼び出し元へ返す
        return "条件を満たす間は処理を繰り返す"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith(("with ", "async with ")):
        # 処理結果を呼び出し元へ返す
        return "使用するリソースの開始と終了をこの範囲で管理する"
    # 条件を満たす場合だけ次の処理を行う
    if line == "try:":
        # 処理結果を呼び出し元へ返す
        return "失敗する可能性がある処理を開始する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("except "):
        # 処理結果を呼び出し元へ返す
        return "発生した例外を受け取り、安全に処理する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("finally"):
        # 処理結果を呼び出し元へ返す
        return "成否にかかわらず必要な後処理を行う"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("return"):
        # 処理結果を呼び出し元へ返す
        return "処理結果を呼び出し元へ返す"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("yield"):
        # 処理結果を呼び出し元へ返す
        return "生成した値を呼び出し元へ一件ずつ返す"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("raise "):
        # 処理結果を呼び出し元へ返す
        return "不正な状態を例外として通知して処理を停止する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("assert "):
        # 処理結果を呼び出し元へ返す
        return "後続処理が前提とする状態を確認する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("print("):
        # 処理結果を呼び出し元へ返す
        return "処理結果を利用者へ表示する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("continue"):
        # 処理結果を呼び出し元へ返す
        return "現在の対象を終えて次の対象へ進む"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("break"):
        # 処理結果を呼び出し元へ返す
        return "条件を満たしたため繰り返しを終了する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith("pass"):
        # 処理結果を呼び出し元へ返す
        return "この分岐では追加の処理を行わない"
    # assignmentへこの工程で使用する値を設定する
    assignment = re.match(r"([A-Za-z_][A-Za-z0-9_\[\].]*)\s*(?::[^=]+)?=", line)
    # 条件を満たす場合だけ次の処理を行う
    if assignment:
        # 処理結果を呼び出し元へ返す
        return f"{assignment.group(1)}へこの工程で使用する値を設定する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith(("\"", "'")) and ":" in line:
        # 処理結果を呼び出し元へ返す
        return "出力レコードの項目と値を設定する"
    # 条件を満たす場合だけ次の処理を行う
    if line.startswith(("\"", "'")):
        # 処理結果を呼び出し元へ返す
        return "この処理で扱う文字列を一覧へ加える"
    # 処理結果を呼び出し元へ返す
    return "次の値または処理を現在の構造へ組み込む"


# 条件を満たす場合だけ次の処理を行う
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    main()
