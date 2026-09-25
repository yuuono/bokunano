"""評価用日本語指示、検証済みコード、評価入力参照を最終レコードへ結合する。"""

# 将来のPythonでも現在の型注釈をそのまま評価できるようにする
from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse
# 件数分布を集計するために使う
from collections import Counter
# 複数のファイルとZIPストリームを安全に閉じるために使う
from contextlib import ExitStack
# ZIP内バイナリをUTF-8テキストとして読むために使う
import io
# JSONとJSONLを読み書きするために使う
import json
# 一時ファイルを完成ファイルへ安全に置き換えるために使う
import os
# 入出力パスを扱うために使う
from pathlib import Path
# ファイル指定実行時にリポジトリ直下をimport探索先へ加えるために使う
import sys
# 任意のJSON値とiteratorの型注釈に使う
from typing import Any, Iterable, Iterator, TextIO
# 入力ZIPの読込みと評価成果物ZIPの作成に使う
import zipfile

# このファイルから見たリポジトリ直下を取得する
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# ファイル指定実行でもscriptsパッケージを読み込めるようにする
if str(PROJECT_ROOT) not in sys.path:
    # リポジトリ直下を探索順の先頭へ追加する
    sys.path.insert(0, str(PROJECT_ROOT))

# 訓練最終結合と同じ正規化・ハッシュ規則を再利用する
from scripts.instruction_generation.build_final_train_records import (  # noqa: E402
    canonical_json,
    file_sha256,
    grouped_by_spec,
    operation_count,
    read_jsonl,
    require_string,
    stable_rank,
    text_sha256,
)


# 評価指示ZIP内のJSONLパスを定義する
EVALUATION_INSTRUCTION_MEMBER = "data/instructions/rule_generated_evaluation_instructions.jsonl"
# 言い換え指示ZIP内のJSONLパスを定義する
PARAPHRASE_INSTRUCTION_MEMBER = "data/instructions/paraphrase_test_instructions.jsonl"
# 評価コードZIP内のメンバーを集合別に定義する
EVALUATION_CODE_MEMBERS = {
    "validation": (
        "data/code_candidates/validation/two_operation/python_code_candidates.jsonl",
        "data/code_candidates/validation/three_operation/python_code_candidates.jsonl",
    ),
    "normal": (
        "data/code_candidates/normal/two_operation/python_code_candidates.jsonl",
        "data/code_candidates/normal/three_operation/python_code_candidates.jsonl",
    ),
    "repetition": (
        "data/code_candidates/repetition/two_operation/python_code_candidates.jsonl",
        "data/code_candidates/repetition/three_operation/python_code_candidates.jsonl",
    ),
}
# 複数操作コードZIP内の組合せ汎化メンバーを定義する
COMPOSITIONAL_CODE_MEMBERS = (
    "data/code_candidates/compositional/two_operation/python_code_candidates.jsonl",
    "data/code_candidates/compositional/three_operation/python_code_candidates.jsonl",
)
# 集合ごとの最終JSONLファイル名を定義する
OUTPUT_FILENAMES = {
    "validation": "validation_dataset_records.jsonl",
    "normal": "normal_test_dataset_records.jsonl",
    "compositional": "compositional_test_dataset_records.jsonl",
    "paraphrase": "paraphrase_test_dataset_records.jsonl",
    "repetition": "repetition_test_dataset_records.jsonl",
    "boundary": "boundary_test_dataset_records.jsonl",
}
# 基本4集合の分割、test_suite、辞書、入力集合を定義する
SUITE_RULES = {
    "validation": {
        "split": "val",
        "test_suite": None,
        "dictionary": "train",
        "input_set": "build",
        "expected_count": 24040,
        "expected_ast_count": 1202,
    },
    "normal": {
        "split": "test",
        "test_suite": "normal",
        "dictionary": "train",
        "input_set": "hidden",
        "expected_count": 24040,
        "expected_ast_count": 1202,
    },
    "compositional": {
        "split": "test",
        "test_suite": "compositional",
        "dictionary": "train",
        "input_set": "hidden",
        "expected_count": 13400,
        "expected_ast_count": 670,
    },
    "repetition": {
        "split": "test",
        "test_suite": "repetition",
        "dictionary": "train",
        "input_set": "hidden",
        "expected_count": 23040,
        "expected_ast_count": 1152,
    },
}
# 最終評価レコード生成器の版を定義する
GENERATOR_VERSION = "1"
# ZIP内メンバーの固定日時を定義する
ZIP_TIMESTAMP = (2026, 9, 25, 0, 0, 0)
# 合格済みコードへ必須の検証結果を定義する
REQUIRED_VERIFICATION_FLAGS = (
    "syntax_ok",
    "ast_safe",
    "signature_ok",
    "tests_passed",
    "input_unchanged",
)


# CLI引数を作る関数を定義する
def parse_args() -> argparse.Namespace:
    """評価最終結合に必要な入出力と期待件数を受け取る。"""

    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        description="評価指示・コード・入力参照を最終評価レコードへ結合します。"
    )
    # 4集合のルール生成指示ZIPを受け取る
    parser.add_argument("--evaluation-instructions-archive", required=True, type=Path)
    # 言い換えテスト30文ZIPを受け取る
    parser.add_argument("--paraphrase-instructions-archive", required=True, type=Path)
    # validation・normal・repetitionコードZIPを受け取る
    parser.add_argument("--evaluation-code-archive", required=True, type=Path)
    # compositionalコードを含む複数操作ZIPを受け取る
    parser.add_argument("--multi-operation-code-archive", required=True, type=Path)
    # paraphraseへ割り当てる単独操作コードJSONLを受け取る
    parser.add_argument("--single-operation-codes", required=True, type=Path)
    # 評価入力生成集計JSONを受け取る
    parser.add_argument("--evaluation-input-stats", required=True, type=Path)
    # 展開済み6 JSONLの保存ディレクトリを受け取る
    parser.add_argument("--output-dir", required=True, type=Path)
    # Git管理用評価ZIPの保存先を受け取る
    parser.add_argument("--archive", required=True, type=Path)
    # 件数・ハッシュ・来歴の集計JSONを受け取る
    parser.add_argument("--stats", required=True, type=Path)
    # 最終評価レコード総数を受け取る
    parser.add_argument("--expected-record-count", required=True, type=int)
    # paraphraseコード選抜と最終生成に使うseedを受け取る
    parser.add_argument("--pairing-seed", default=20260925, type=int)
    # 既存成果物を意図的に置き換える場合だけ使う
    parser.add_argument("--overwrite", action="store_true")
    # 解析済み引数を返す
    return parser.parse_args()


# リポジトリ内なら相対パスを作る関数を定義する
def display_path(path: Path) -> str:
    """現在の作業ディレクトリ内なら相対パス、それ以外なら絶対パスを返す。"""

    # 作業ディレクトリ基準の相対パスへの変換を試す
    try:
        # POSIX形式の相対パスを返す
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    # 外部パスは絶対パスのまま扱う
    except ValueError:
        # 解決済みパスを返す
        return str(path.resolve())


# ZIPメンバーをUTF-8 JSONLとして開く関数を定義する
def open_zip_text(stack: ExitStack, archive: zipfile.ZipFile, member: str) -> TextIO:
    """存在確認したZIPメンバーをExitStack管理のテキストストリームで返す。"""

    # 必須メンバーの存在を確認する
    if member not in archive.namelist():
        # 欠落メンバーを明示して停止する
        raise ValueError(f"ZIPに必要なメンバーがありません: {member}")
    # バイナリストリームを開く
    binary = stack.enter_context(archive.open(member))
    # UTF-8テキストへ包んで返す
    return stack.enter_context(io.TextIOWrapper(binary, encoding="utf-8"))


# 複数レコード列を順番どおり連結する関数を定義する
def chain_records(*iterables: Iterable[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """複数のJSONL iteratorを指定順で一つの列として返す。"""

    # 入力iteratorを一つずつ処理する
    for iterable in iterables:
        # 現在のiteratorから全レコードを返す
        yield from iterable


# 二つのグループ列を同数確認付きで結合する関数を定義する
def zip_groups_exact(
    left: Iterable[tuple[str, list[dict[str, Any]]]],
    right: Iterable[tuple[str, list[dict[str, Any]]]],
) -> Iterator[
    tuple[tuple[str, list[dict[str, Any]]], tuple[str, list[dict[str, Any]]]]
]:
    """二つのグループ列を結合し、片側だけの余りを拒否する。"""

    # 左右をiteratorへ変換する
    left_iterator = iter(left)
    # 右側もiteratorへ変換する
    right_iterator = iter(right)
    # 終端判定用の固有objectを作る
    sentinel = object()
    # 両方が終端へ達するまで処理する
    while True:
        # 左の次グループまたは終端を取得する
        left_item = next(left_iterator, sentinel)
        # 右の次グループまたは終端を取得する
        right_item = next(right_iterator, sentinel)
        # 両方が同時に終わった場合は正常終了する
        if left_item is sentinel and right_item is sentinel:
            # iteratorを終了する
            return
        # 片側だけが終わった場合は件数不一致とする
        if left_item is sentinel or right_item is sentinel:
            # グループ欠落を明示して停止する
            raise ValueError("指示とコードの意味ASTグループ数が一致しません")
        # sentinelではない左右グループを返す
        yield left_item, right_item  # type: ignore[misc]


# 指定した集合の指示だけを返す関数を定義する
def filter_instruction_records(
    records: Iterable[dict[str, Any]], split: str, test_suite: str | None
) -> Iterator[dict[str, Any]]:
    """大きな評価指示JSONLから一つのsplit・test_suiteだけを返す。"""

    # 全レコードを一件ずつ調べる
    for record in records:
        # 対象集合と一致する場合だけ返す
        if record.get("split") == split and record.get("test_suite") == test_suite:
            # 対象指示を返す
            yield record


# 指示レコードを検査する関数を定義する
def validate_instruction(
    record: dict[str, Any], *, split: str, test_suite: str | None, dictionary: str
) -> None:
    """評価指示の意味、分割、辞書、本文ハッシュ、教師項目を確認する。"""

    # 必須IDと本文を検査する
    require_string(record, "instruction_id", "evaluation_instruction")
    # spec_idも検査する
    require_string(record, "spec_id", "evaluation_instruction")
    # 指示本文を取得する
    instruction_ja = require_string(record, "instruction_ja", "evaluation_instruction")
    # 意味ASTの操作数を検査する
    operation_count(record.get("semantic_ast"), "evaluation_instruction")
    # 本文ハッシュを再計算して照合する
    if record.get("text_hash") != text_sha256(instruction_ja):
        # 本文改変を拒否する
        raise ValueError("評価指示のtext_hashが一致しません")
    # 分割とtest_suiteを照合する
    if record.get("split") != split or record.get("test_suite") != test_suite:
        # 集合混入を拒否する
        raise ValueError("評価指示のsplitまたはtest_suiteが一致しません")
    # 辞書区分を照合する
    if record.get("dictionary") != dictionary:
        # test_onlyとtrainの混入を拒否する
        raise ValueError("評価指示のdictionaryが一致しません")
    # 評価指示はルール生成であることを確認する
    if record.get("instruction_source") != "rule":
        # 教師言い換え混入を拒否する
        raise ValueError("評価指示のinstruction_sourceがruleではありません")
    # 教師関係三項目がnullであることを確認する
    for key in ("teacher_model", "teacher_revision", "prompt_hash"):
        # null以外を拒否する
        if record.get(key) is not None:
            # 不正項目を明示して停止する
            raise ValueError(f"評価指示の{key}がnullではありません")


# コード候補を検査する関数を定義する
def validate_code(
    record: dict[str, Any], *, expected_split: str, expected_test_suite: str | None
) -> None:
    """コード候補の意味・ハッシュ・分割・検証状態を確認する。"""

    # 必須IDを検査する
    require_string(record, "code_id", "evaluation_code")
    # spec_idを検査する
    require_string(record, "spec_id", "evaluation_code")
    # コード本文を取得する
    reference_code = require_string(record, "reference_code", "evaluation_code")
    # 意味ASTを取得する
    semantic_ast = record.get("semantic_ast")
    # 意味ASTの操作数を検査する
    operation_count(semantic_ast, "evaluation_code")
    # 意味ハッシュを照合する
    if record.get("semantic_hash") != text_sha256(canonical_json(semantic_ast)):
        # 意味不一致を拒否する
        raise ValueError("評価コードのsemantic_hashが一致しません")
    # コードハッシュを照合する
    if record.get("code_hash") != text_sha256(reference_code):
        # コード改変を拒否する
        raise ValueError("評価コードのcode_hashが一致しません")
    # 元コード候補の分割を照合する
    if (
        record.get("split") != expected_split
        or record.get("test_suite") != expected_test_suite
    ):
        # 異なる集合のコード混入を拒否する
        raise ValueError("評価コードのsplitまたはtest_suiteが一致しません")
    # 検証結果を取得する
    verification = record.get("verification")
    # 検証結果がobjectであることを確認する
    if not isinstance(verification, dict):
        # 検証情報欠落を拒否する
        raise ValueError("評価コードのverificationがobjectではありません")
    # 必須合格フラグを一件ずつ確認する
    for flag in REQUIRED_VERIFICATION_FLAGS:
        # true以外を不合格として扱う
        if verification.get(flag) is not True:
            # 不合格項目を明示して停止する
            raise ValueError(f"評価コードのverification.{flag}がtrueではありません")
    # timeoutがfalseであることを確認する
    if verification.get("timeout") is not False:
        # timeout済みコードを拒否する
        raise ValueError("評価コードのverification.timeoutがfalseではありません")


# 評価入力manifestと集計を読み込む関数を定義する
def load_evaluation_input_metadata(stats_path: Path) -> tuple[dict[str, str], list[Path]]:
    """6集合のtest_set_idを取得し、各manifestのハッシュを集計値と照合する。"""

    # 評価入力集計を読み込む
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    # objectであることを確認する
    if not isinstance(stats, dict) or not isinstance(stats.get("sets"), dict):
        # 不正集計を拒否する
        raise ValueError("評価入力集計の形式が不正です")
    # test_set_idを保存する
    test_set_ids: dict[str, str] = {}
    # manifestパスを保存する
    manifest_paths: list[Path] = []
    # 必須6集合を一件ずつ処理する
    for name in OUTPUT_FILENAMES:
        # 集合別集計を取得する
        details = stats["sets"].get(name)
        # objectであることを確認する
        if not isinstance(details, dict):
            # 欠落集合を拒否する
            raise ValueError(f"評価入力集計に{name}がありません")
        # test_set_idを取得する
        test_set_id = details.get("test_set_id")
        # 空でない文字列であることを確認する
        if not isinstance(test_set_id, str) or not test_set_id:
            # 不正IDを拒否する
            raise ValueError(f"{name}のtest_set_idが不正です")
        # manifestパスを集計JSONの親ではなくリポジトリルートから解決する
        manifest_path = Path(details["output"])
        # 相対パスは現在の作業ディレクトリ基準で解決する
        if not manifest_path.is_absolute():
            # 作業ディレクトリを付ける
            manifest_path = Path.cwd() / manifest_path
        # manifestが存在することを確認する
        if not manifest_path.is_file():
            # 欠落を明示して停止する
            raise FileNotFoundError(manifest_path)
        # 保存済みハッシュと実ファイルを照合する
        if file_sha256(manifest_path) != details.get("output_sha256"):
            # 評価入力の変更を拒否する
            raise ValueError(f"{name}入力manifestのSHA-256が集計と一致しません")
        # manifest本体のtest_set_idも照合する
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # ID不一致を拒否する
        if not isinstance(manifest, dict) or manifest.get("test_set_id") != test_set_id:
            # 参照ずれを明示して停止する
            raise ValueError(f"{name}入力manifestのtest_set_idが一致しません")
        # 検査済みIDを保存する
        test_set_ids[name] = test_set_id
        # 検査済みパスを保存する
        manifest_paths.append(manifest_path.resolve())
    # test_set_idが6集合で一意であることを確認する
    if len(set(test_set_ids.values())) != len(test_set_ids):
        # ID重複を拒否する
        raise ValueError("評価入力のtest_set_idが重複しています")
    # ID対応とmanifest一覧を返す
    return test_set_ids, manifest_paths


# 最終評価レコードを作る関数を定義する
def make_evaluation_record(
    *,
    instruction: dict[str, Any],
    code: dict[str, Any],
    split: str,
    test_suite: str | None,
    dictionary: str,
    input_set: str,
    test_set_id: str,
    pairing_seed: int,
    pairing_strategy: str,
) -> dict[str, Any]:
    """一件の指示とコードから来歴付き最終評価レコードを作る。"""

    # spec_idを両入力で照合する
    if instruction["spec_id"] != code["spec_id"]:
        # 異なる意味IDの結合を拒否する
        raise ValueError("評価指示とコードのspec_idが一致しません")
    # 正規化意味ASTを両入力で照合する
    if canonical_json(instruction["semantic_ast"]) != canonical_json(code["semantic_ast"]):
        # 意味不一致を拒否する
        raise ValueError("評価指示とコードのsemantic_astが一致しません")
    # 主要値を取得する
    semantic_ast = instruction["semantic_ast"]
    # 意味ハッシュを計算する
    semantic_hash = text_sha256(canonical_json(semantic_ast))
    # 指示本文を取得する
    instruction_ja = instruction["instruction_ja"]
    # コードIDを取得する
    code_id = code["code_id"]
    # テスト参照一覧を作る
    tests = [test_set_id]
    # record_id計算文字列を方針どおり作る
    record_key = (
        f"{code_id}\0{instruction_ja}\0{canonical_json(test_suite)}\0{canonical_json(tests)}"
    )
    # 指示の全来歴をコピーする
    record = dict(instruction)
    # コードと最終結合固有項目を追加する
    record.update(
        {
            "record_id": f"record-{text_sha256(record_key)}",
            "family_id": f"family-{semantic_hash}",
            "code_id": code_id,
            "spec_id": code["spec_id"],
            "semantic_ast": semantic_ast,
            "reference_code": code["reference_code"],
            "tests": tests,
            "difficulty": operation_count(semantic_ast, "evaluation_record"),
            "code_style": code["code_style"],
            "style_id": code["style_id"],
            "style_spec": code["style_spec"],
            "rewrite_id": code.get("rewrite_id"),
            "split": split,
            "test_suite": test_suite,
            "dictionary": dictionary,
            "input_set": input_set,
            "semantic_hash": semantic_hash,
            "code_hash": code["code_hash"],
            "text_hash": text_sha256(instruction_ja),
            "code_source_split": code.get("split"),
            "code_source_test_suite": code.get("test_suite"),
            "code_generator_version": code.get("generator_version"),
            "code_generator_seed": code.get("generator_seed"),
            "instruction_generator_version": instruction.get("generator_version"),
            "instruction_generator_seed": instruction.get("generator_seed"),
            "generator_version": GENERATOR_VERSION,
            "generator_seed": pairing_seed,
            "pairing_seed": pairing_seed,
            "pairing_strategy": pairing_strategy,
            "verification": code["verification"],
        }
    )
    # paraphraseで訓練コード再利用を明示する
    if test_suite == "paraphrase":
        # 意味は訓練済みで表現だけ未学習という評価目的を記録する
        record["code_reuse_policy"] = "reuse_verified_train_code_for_language_only_test"
    # 完成レコードを返す
    return record


# 最終評価レコードを再検査する関数を定義する
def validate_evaluation_record(
    record: dict[str, Any], *, split: str, test_suite: str | None, dictionary: str,
    input_set: str, test_set_id: str
) -> None:
    """最終評価レコードのID、ハッシュ、分割、テスト参照を再確認する。"""

    # 必須文字列項目を一件ずつ検査する
    for key in (
        "record_id",
        "family_id",
        "code_id",
        "spec_id",
        "instruction_id",
        "instruction_ja",
        "reference_code",
        "semantic_hash",
        "code_hash",
        "text_hash",
    ):
        # 空でない文字列を要求する
        require_string(record, key, "evaluation_record")
    # 意味ASTと操作数を確認する
    semantic_ast = record.get("semantic_ast")
    # 難易度が操作数と一致することを確認する
    if record.get("difficulty") != operation_count(semantic_ast, "evaluation_record"):
        # 難易度不一致を拒否する
        raise ValueError("評価レコードのdifficultyが一致しません")
    # 意味ハッシュを再計算する
    semantic_hash = text_sha256(canonical_json(semantic_ast))
    # 意味ハッシュとfamily_idを照合する
    if record["semantic_hash"] != semantic_hash or record["family_id"] != f"family-{semantic_hash}":
        # 意味追跡不一致を拒否する
        raise ValueError("評価レコードのsemantic_hashまたはfamily_idが一致しません")
    # 本文ハッシュを照合する
    if record["text_hash"] != text_sha256(record["instruction_ja"]):
        # 指示改変を拒否する
        raise ValueError("評価レコードのtext_hashが一致しません")
    # コードハッシュを照合する
    if record["code_hash"] != text_sha256(record["reference_code"]):
        # コード改変を拒否する
        raise ValueError("評価レコードのcode_hashが一致しません")
    # 分割項目を照合する
    if (
        record.get("split") != split
        or record.get("test_suite") != test_suite
        or record.get("dictionary") != dictionary
        or record.get("input_set") != input_set
        or record.get("tests") != [test_set_id]
    ):
        # 集合混入を拒否する
        raise ValueError("評価レコードの分割またはテスト参照が一致しません")
    # record_idを再計算する
    expected_record_id = "record-" + text_sha256(
        f"{record['code_id']}\0{record['instruction_ja']}\0"
        f"{canonical_json(test_suite)}\0{canonical_json([test_set_id])}"
    )
    # record_idを照合する
    if record["record_id"] != expected_record_id:
        # ID不一致を拒否する
        raise ValueError("評価レコードのrecord_idが一致しません")


# 集合別集計状態を初期化する関数を定義する
def new_suite_state() -> dict[str, Any]:
    """最終レコードを書きながら更新する集計状態を返す。"""

    # 一意性集合と分布カウンタを返す
    return {
        "record_count": 0,
        "spec_ids": set(),
        "record_ids": set(),
        "instruction_ids": set(),
        "code_ids": set(),
        "operation_counts": Counter(),
        "code_styles": Counter(),
    }


# 一件をJSONLへ保存して集計する関数を定義する
def write_and_count_record(
    handle: TextIO, record: dict[str, Any], state: dict[str, Any]
) -> None:
    """レコードID重複を拒否し、JSONL保存と分布集計を行う。"""

    # record_idを取得する
    record_id = record["record_id"]
    # 集合内重複を拒否する
    if record_id in state["record_ids"]:
        # 重複IDを明示して停止する
        raise ValueError(f"record_idが集合内で重複しています: {record_id}")
    # 一意性集合へ追加する
    state["record_ids"].add(record_id)
    # 指示IDを保存する
    state["instruction_ids"].add(record["instruction_id"])
    # コードIDを保存する
    state["code_ids"].add(record["code_id"])
    # spec_idを保存する
    state["spec_ids"].add(record["spec_id"])
    # 操作数分布を加算する
    state["operation_counts"][record["difficulty"]] += 1
    # コード形式分布を加算する
    state["code_styles"][record["code_style"]] += 1
    # レコード総数を増やす
    state["record_count"] += 1
    # 一行JSONとして保存する
    handle.write(canonical_json(record) + "\n")


# 基本4集合を一対一結合する関数を定義する
def build_one_to_one_suite(
    *, suite_name: str, instruction_archive_path: Path, code_archive_path: Path,
    code_members: tuple[str, ...], output_path: Path, test_set_id: str,
    pairing_seed: int
) -> dict[str, Any]:
    """同じ順序の指示20件とコード20件を意味ASTごとに一対一結合する。"""

    # 集合規則を取得する
    rule = SUITE_RULES[suite_name]
    # 集計状態を初期化する
    state = new_suite_state()
    # 一時出力パスを作る
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    # 古い未完成ファイルを削除する
    temporary.unlink(missing_ok=True)
    # ストリームを安全に管理する
    try:
        # 複数ストリームを一括管理する
        with ExitStack() as stack:
            # 指示ZIPを開く
            instruction_archive = stack.enter_context(zipfile.ZipFile(instruction_archive_path))
            # 評価指示JSONLを開く
            instruction_handle = open_zip_text(
                stack, instruction_archive, EVALUATION_INSTRUCTION_MEMBER
            )
            # 対象集合だけを抽出する
            instruction_records = filter_instruction_records(
                read_jsonl(instruction_handle, str(instruction_archive_path)),
                rule["split"],
                rule["test_suite"],
            )
            # コードZIPを開く
            code_archive = stack.enter_context(zipfile.ZipFile(code_archive_path))
            # メンバーごとのコードiteratorを作る
            code_iterables = []
            # 指定メンバーを順番に開く
            for member in code_members:
                # コードJSONLを開く
                code_handle = open_zip_text(stack, code_archive, member)
                # JSONL iteratorを追加する
                code_iterables.append(read_jsonl(code_handle, f"{code_archive_path}:{member}"))
            # 2・3操作コード列を連結する
            code_records = chain_records(*code_iterables)
            # 指示とコードをspec_idグループへ変換する
            instruction_groups = grouped_by_spec(instruction_records, f"{suite_name}_instructions")
            # コードもspec_idグループへ変換する
            code_groups = grouped_by_spec(code_records, f"{suite_name}_codes")
            # 一時JSONLを書込み用に開く
            output_handle = stack.enter_context(temporary.open("w", encoding="utf-8"))
            # グループを一件ずつ同時処理する
            for instruction_group, code_group in zip_groups_exact(
                instruction_groups, code_groups
            ):
                # spec_idとレコード一覧を分ける
                instruction_spec_id, instructions = instruction_group
                # コード側も分ける
                code_spec_id, codes = code_group
                # グループIDを照合する
                if instruction_spec_id != code_spec_id:
                    # 順序ずれを拒否する
                    raise ValueError(f"{suite_name}の指示とコードのspec_id順が一致しません")
                # 20対20であることを確認する
                if len(instructions) != 20 or len(codes) != 20:
                    # 件数不一致を拒否する
                    raise ValueError(f"{suite_name}:{instruction_spec_id}が20対20ではありません")
                # 同一グループ内の意味ASTを基準化する
                expected_ast = canonical_json(instructions[0]["semantic_ast"])
                # 指示20件を検査する
                for instruction in instructions:
                    # 指示本体を検査する
                    validate_instruction(
                        instruction,
                        split=rule["split"],
                        test_suite=rule["test_suite"],
                        dictionary=rule["dictionary"],
                    )
                    # 意味AST混在を拒否する
                    if canonical_json(instruction["semantic_ast"]) != expected_ast:
                        # spec内の意味不一致を明示する
                        raise ValueError(f"{suite_name}:{instruction_spec_id}の指示ASTが混在しています")
                # コード20件を検査する
                for code in codes:
                    # コード本体を検査する
                    validate_code(
                        code,
                        expected_split=rule["split"],
                        expected_test_suite=rule["test_suite"],
                    )
                    # 指示との意味不一致を拒否する
                    if canonical_json(code["semantic_ast"]) != expected_ast:
                        # 不一致を明示して停止する
                        raise ValueError(f"{suite_name}:{code_spec_id}のコードASTが一致しません")
                # 元順序の20対20で結合する
                for instruction, code in zip(instructions, codes, strict=True):
                    # 最終評価レコードを作る
                    record = make_evaluation_record(
                        instruction=instruction,
                        code=code,
                        split=rule["split"],
                        test_suite=rule["test_suite"],
                        dictionary=rule["dictionary"],
                        input_set=rule["input_set"],
                        test_set_id=test_set_id,
                        pairing_seed=pairing_seed,
                        pairing_strategy="source_order_one_to_one_within_semantic_ast",
                    )
                    # 最終レコードを再検査する
                    validate_evaluation_record(
                        record,
                        split=rule["split"],
                        test_suite=rule["test_suite"],
                        dictionary=rule["dictionary"],
                        input_set=rule["input_set"],
                        test_set_id=test_set_id,
                    )
                    # JSONLへ保存して集計する
                    write_and_count_record(output_handle, record, state)
        # 件数を期待値と照合する
        if state["record_count"] != rule["expected_count"]:
            # 件数不一致を拒否する
            raise ValueError(f"{suite_name}件数が期待値と一致しません")
        # 意味AST数を期待値と照合する
        if len(state["spec_ids"]) != rule["expected_ast_count"]:
            # AST数不一致を拒否する
            raise ValueError(f"{suite_name}意味AST数が期待値と一致しません")
        # 20対20集合では指示・コードも全件一意であることを確認する
        if (
            len(state["instruction_ids"]) != state["record_count"]
            or len(state["code_ids"]) != state["record_count"]
        ):
            # 再利用混入を拒否する
            raise ValueError(f"{suite_name}で指示またはコードが再利用されています")
        # 完成JSONLを所定パスへ置き換える
        os.replace(temporary, output_path)
    # 成否にかかわらず未完成ファイルを削除する
    finally:
        # 残った一時ファイルを削除する
        temporary.unlink(missing_ok=True)
    # 集合別集計を返す
    return summarize_suite_state(state, output_path, test_set_id)


# 単独操作コードをspec_id別に読み込む関数を定義する
def load_single_operation_codes(path: Path) -> dict[str, list[dict[str, Any]]]:
    """単独操作コード480件を24意味ASTの辞書へ読み込む。"""

    # spec_id別辞書を初期化する
    grouped: dict[str, list[dict[str, Any]]] = {}
    # UTF-8 JSONLを開く
    with path.open("r", encoding="utf-8") as handle:
        # spec_idグループを一件ずつ処理する
        for spec_id, codes in grouped_by_spec(read_jsonl(handle, str(path)), str(path)):
            # 各単独操作に20コードあることを確認する
            if len(codes) != 20:
                # 不足または過剰を拒否する
                raise ValueError(f"単独操作コードが20件ではありません: {spec_id}")
            # 全コードを訓練候補として検査する
            for code in codes:
                # 元コードはtrain/test_suite=nullであることを確認する
                validate_code(code, expected_split="train", expected_test_suite=None)
            # 辞書へ保存する
            grouped[spec_id] = codes
    # 24意味ASTであることを確認する
    if len(grouped) != 24:
        # 件数不一致を拒否する
        raise ValueError("単独操作コードの意味AST数が24ではありません")
    # 検査済み辞書を返す
    return grouped


# 言い換えテスト30件を作る関数を定義する
def build_paraphrase_suite(
    *, instruction_archive_path: Path, single_operation_codes_path: Path,
    output_path: Path, test_set_id: str, pairing_seed: int
) -> dict[str, Any]:
    """30表現へ同一操作内の異なる検証済み訓練コードを決定的に割り当てる。"""

    # 単独操作コードを読み込む
    codes_by_spec = load_single_operation_codes(single_operation_codes_path)
    # spec_id別の使用済みコードIDを保存する
    used_code_ids_by_spec: dict[str, set[str]] = {}
    # spec_id別の安定順位コード一覧を作る
    ranked_codes_by_spec: dict[str, list[dict[str, Any]]] = {}
    # 全24意味ASTを一件ずつ処理する
    for spec_id, codes in codes_by_spec.items():
        # pairing seedから決まる順序で並べる
        ranked_codes_by_spec[spec_id] = sorted(
            codes,
            key=lambda code: stable_rank(
                pairing_seed, "paraphrase-code", spec_id, code["code_id"]
            ),
        )
        # 使用済み集合を初期化する
        used_code_ids_by_spec[spec_id] = set()
    # 集計状態を初期化する
    state = new_suite_state()
    # 一時出力パスを作る
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    # 古い一時ファイルを削除する
    temporary.unlink(missing_ok=True)
    # 完成前の処理を開始する
    try:
        # ZIPと出力を安全に管理する
        with ExitStack() as stack:
            # 言い換え指示ZIPを開く
            archive = stack.enter_context(zipfile.ZipFile(instruction_archive_path))
            # 30文JSONLを開く
            instruction_handle = open_zip_text(stack, archive, PARAPHRASE_INSTRUCTION_MEMBER)
            # 出力一時JSONLを開く
            output_handle = stack.enter_context(temporary.open("w", encoding="utf-8"))
            # 指示を一件ずつ処理する
            for instruction in read_jsonl(instruction_handle, str(instruction_archive_path)):
                # test_onlyのparaphrase指示として検査する
                validate_instruction(
                    instruction,
                    split="test",
                    test_suite="paraphrase",
                    dictionary="test_only",
                )
                # spec_idを取得する
                spec_id = instruction["spec_id"]
                # 対応する単独操作コードが存在することを確認する
                if spec_id not in ranked_codes_by_spec:
                    # 未対応操作を拒否する
                    raise ValueError(f"paraphraseに対応する単独操作コードがありません: {spec_id}")
                # 未使用コードを順位順に探す
                code = next(
                    (
                        candidate
                        for candidate in ranked_codes_by_spec[spec_id]
                        if candidate["code_id"] not in used_code_ids_by_spec[spec_id]
                    ),
                    None,
                )
                # 20件を超える表現割当を拒否する
                if code is None:
                    # 対応不能を明示する
                    raise ValueError(f"paraphraseで単独操作コードが不足しています: {spec_id}")
                # 使用済みコードとして保存する
                used_code_ids_by_spec[spec_id].add(code["code_id"])
                # 意味ASTを照合して最終レコードを作る
                record = make_evaluation_record(
                    instruction=instruction,
                    code=code,
                    split="test",
                    test_suite="paraphrase",
                    dictionary="test_only",
                    input_set="hidden",
                    test_set_id=test_set_id,
                    pairing_seed=pairing_seed,
                    pairing_strategy="stable_rank_distinct_train_code_within_semantic_ast",
                )
                # 最終レコードを再検査する
                validate_evaluation_record(
                    record,
                    split="test",
                    test_suite="paraphrase",
                    dictionary="test_only",
                    input_set="hidden",
                    test_set_id=test_set_id,
                )
                # 保存して集計する
                write_and_count_record(output_handle, record, state)
        # 30文であることを確認する
        if state["record_count"] != 30:
            # 件数不一致を拒否する
            raise ValueError("paraphrase最終レコード数が30ではありません")
        # 24操作を覆うことを確認する
        if len(state["spec_ids"]) != 24:
            # 操作欠落を拒否する
            raise ValueError("paraphraseが24操作を覆っていません")
        # 指示とコードを各一度だけ使用したことを確認する
        if len(state["instruction_ids"]) != 30 or len(state["code_ids"]) != 30:
            # 重複割当を拒否する
            raise ValueError("paraphraseの指示またはコードが重複しています")
        # 完成JSONLを所定パスへ置き換える
        os.replace(temporary, output_path)
    # 成否にかかわらず未完成ファイルを削除する
    finally:
        # 残った一時ファイルを削除する
        temporary.unlink(missing_ok=True)
    # 集合別集計を返す
    return summarize_suite_state(state, output_path, test_set_id)


# normalからboundaryを派生する関数を定義する
def build_boundary_suite(
    *, normal_path: Path, output_path: Path, test_set_id: str, pairing_seed: int
) -> dict[str, Any]:
    """normalの指示・コード・familyを維持し、境界入力参照だけを変更する。"""

    # 集計状態を初期化する
    state = new_suite_state()
    # normal由来record_idの一意性を保存する
    source_record_ids: set[str] = set()
    # 一時出力パスを作る
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    # 古い一時ファイルを削除する
    temporary.unlink(missing_ok=True)
    # 完成前の処理を開始する
    try:
        # normal入力とboundary出力を開く
        with normal_path.open("r", encoding="utf-8") as normal_handle, temporary.open(
            "w", encoding="utf-8"
        ) as output_handle:
            # normal最終レコードを一件ずつ処理する
            for normal_record in read_jsonl(normal_handle, str(normal_path)):
                # normalの必須分割を確認する
                if (
                    normal_record.get("split") != "test"
                    or normal_record.get("test_suite") != "normal"
                    or normal_record.get("input_set") != "hidden"
                ):
                    # 異なる集合混入を拒否する
                    raise ValueError("boundary派生元にnormal以外が混入しています")
                # 派生元record_idを取得する
                source_record_id = normal_record["record_id"]
                # 派生元重複を拒否する
                if source_record_id in source_record_ids:
                    # 重複を明示して停止する
                    raise ValueError("normal派生元record_idが重複しています")
                # 使用済み派生元へ追加する
                source_record_ids.add(source_record_id)
                # normalレコードをコピーする
                boundary_record = dict(normal_record)
                # 境界集合固有項目へ変更する
                boundary_record.update(
                    {
                        "test_suite": "boundary",
                        "input_set": "boundary",
                        "tests": [test_set_id],
                        "derived_from_record_id": source_record_id,
                        "generator_version": GENERATOR_VERSION,
                        "generator_seed": pairing_seed,
                        "pairing_seed": pairing_seed,
                        "pairing_strategy": "reuse_normal_instruction_code_with_boundary_inputs",
                    }
                )
                # boundary用record_idを再計算する
                boundary_record["record_id"] = "record-" + text_sha256(
                    f"{boundary_record['code_id']}\0{boundary_record['instruction_ja']}\0"
                    f"{canonical_json('boundary')}\0{canonical_json([test_set_id])}"
                )
                # 最終boundaryレコードを検査する
                validate_evaluation_record(
                    boundary_record,
                    split="test",
                    test_suite="boundary",
                    dictionary="train",
                    input_set="boundary",
                    test_set_id=test_set_id,
                )
                # normalとfamily_idが同一であることを確認する
                if boundary_record["family_id"] != normal_record["family_id"]:
                    # 派生関係不一致を拒否する
                    raise ValueError("normalとboundaryのfamily_idが一致しません")
                # 保存して集計する
                write_and_count_record(output_handle, boundary_record, state)
        # normalと同じ24,040件であることを確認する
        if state["record_count"] != 24040:
            # 件数不一致を拒否する
            raise ValueError("boundary最終レコード数が24,040ではありません")
        # normalと同じ1,202 ASTであることを確認する
        if len(state["spec_ids"]) != 1202:
            # AST数不一致を拒否する
            raise ValueError("boundary意味AST数が1,202ではありません")
        # 完成JSONLを所定パスへ置き換える
        os.replace(temporary, output_path)
    # 成否にかかわらず未完成ファイルを削除する
    finally:
        # 残った一時ファイルを削除する
        temporary.unlink(missing_ok=True)
    # 集合別集計を返す
    summary = summarize_suite_state(state, output_path, test_set_id)
    # 派生元件数を記録する
    summary["derived_from_normal_record_count"] = len(source_record_ids)
    # 集計を返す
    return summary


# 集合状態をJSON化可能な集計へ変換する関数を定義する
def summarize_suite_state(
    state: dict[str, Any], output_path: Path, test_set_id: str
) -> dict[str, Any]:
    """集合別の件数、分布、ファイルハッシュを返す。"""

    # JSON保存可能な集計を返す
    return {
        "record_count": state["record_count"],
        "semantic_ast_count": len(state["spec_ids"]),
        "unique_record_id_count": len(state["record_ids"]),
        "unique_instruction_id_count": len(state["instruction_ids"]),
        "unique_code_id_count": len(state["code_ids"]),
        "counts_by_operation_count": {
            str(key): state["operation_counts"][key]
            for key in sorted(state["operation_counts"])
        },
        "counts_by_code_style": {
            key: state["code_styles"][key] for key in sorted(state["code_styles"])
        },
        "test_set_id": test_set_id,
        "output": display_path(output_path),
        "output_bytes": output_path.stat().st_size,
        "output_sha256": file_sha256(output_path),
    }


# 複数JSONLを決定的BZIP2 ZIPへ格納する関数を定義する
def write_deterministic_archive(output_paths: dict[str, Path], archive_path: Path) -> None:
    """固定日時・権限・順序で6 JSONLをBZIP2 ZIPへ格納する。"""

    # ZIP64対応で新規ZIPを開く
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_BZIP2,
        compresslevel=9,
        allowZip64=True,
    ) as archive:
        # 公開順序を固定して6集合を格納する
        for suite_name in OUTPUT_FILENAMES:
            # 元JSONLパスを取得する
            source_path = output_paths[suite_name]
            # ZIP内メンバー情報を作る
            member = zipfile.ZipInfo(OUTPUT_FILENAMES[suite_name], date_time=ZIP_TIMESTAMP)
            # Unix由来ファイルとして記録する
            member.create_system = 3
            # 通常ファイルの0644権限を固定する
            member.external_attr = 0o100644 << 16
            # BZIP2圧縮を指定する
            member.compress_type = zipfile.ZIP_BZIP2
            # ZIPメンバーを開く
            with archive.open(member, mode="w", force_zip64=True) as destination:
                # 元JSONLをバイナリで開く
                with source_path.open("rb") as source:
                    # 1 MiBずつ末尾までコピーする
                    while chunk := source.read(1024 * 1024):
                        # 圧縮ストリームへ書き込む
                        destination.write(chunk)


# 評価最終レコード一式を作る関数を定義する
def build_final_evaluation_records(
    *, evaluation_instructions_archive: Path,
    paraphrase_instructions_archive: Path,
    evaluation_code_archive: Path,
    multi_operation_code_archive: Path,
    single_operation_codes: Path,
    evaluation_input_stats: Path,
    output_dir: Path,
    archive: Path,
    stats: Path,
    expected_record_count: int,
    pairing_seed: int,
    overwrite: bool,
) -> dict[str, Any]:
    """6集合の最終評価JSONL、ZIP、集計を生成して全件検査する。"""

    # 主要入力パスをまとめる
    primary_inputs = (
        evaluation_instructions_archive,
        paraphrase_instructions_archive,
        evaluation_code_archive,
        multi_operation_code_archive,
        single_operation_codes,
        evaluation_input_stats,
    )
    # 全入力の存在を確認する
    for input_path in primary_inputs:
        # 通常ファイルであることを要求する
        if not input_path.is_file():
            # 欠落パスを明示して停止する
            raise FileNotFoundError(input_path)
    # 6集合の評価入力IDとmanifestを検査する
    test_set_ids, input_manifest_paths = load_evaluation_input_metadata(evaluation_input_stats)
    # 出力JSONLパスを作る
    output_paths = {
        name: output_dir / filename for name, filename in OUTPUT_FILENAMES.items()
    }
    # 全出力パスをまとめる
    all_output_paths = [*output_paths.values(), archive, stats]
    # 上書き未指定時は既存成果物を保護する
    if not overwrite:
        # 既存出力を一件ずつ確認する
        for output_path in all_output_paths:
            # 既存ファイルがあれば停止する
            if output_path.exists():
                # 上書き方法を示す
                raise FileExistsError(
                    f"出力が既に存在します: {output_path}; --overwriteを指定してください"
                )
    # 出力ディレクトリを作る
    output_dir.mkdir(parents=True, exist_ok=True)
    # ZIPと集計の親ディレクトリも作る
    archive.parent.mkdir(parents=True, exist_ok=True)
    # 集計親ディレクトリを作る
    stats.parent.mkdir(parents=True, exist_ok=True)
    # 全入力パスを重複なしでまとめる
    input_paths = {
        str(path.resolve()): path.resolve()
        for path in [*primary_inputs, *input_manifest_paths]
    }
    # 処理前ハッシュを保存する
    input_hashes_before = {
        display_path(path): file_sha256(path) for path in input_paths.values()
    }
    # 集合別集計を保存する
    suite_stats: dict[str, dict[str, Any]] = {}
    # validationを一対一結合する
    suite_stats["validation"] = build_one_to_one_suite(
        suite_name="validation",
        instruction_archive_path=evaluation_instructions_archive,
        code_archive_path=evaluation_code_archive,
        code_members=EVALUATION_CODE_MEMBERS["validation"],
        output_path=output_paths["validation"],
        test_set_id=test_set_ids["validation"],
        pairing_seed=pairing_seed,
    )
    # normalを一対一結合する
    suite_stats["normal"] = build_one_to_one_suite(
        suite_name="normal",
        instruction_archive_path=evaluation_instructions_archive,
        code_archive_path=evaluation_code_archive,
        code_members=EVALUATION_CODE_MEMBERS["normal"],
        output_path=output_paths["normal"],
        test_set_id=test_set_ids["normal"],
        pairing_seed=pairing_seed,
    )
    # compositionalを一対一結合する
    suite_stats["compositional"] = build_one_to_one_suite(
        suite_name="compositional",
        instruction_archive_path=evaluation_instructions_archive,
        code_archive_path=multi_operation_code_archive,
        code_members=COMPOSITIONAL_CODE_MEMBERS,
        output_path=output_paths["compositional"],
        test_set_id=test_set_ids["compositional"],
        pairing_seed=pairing_seed,
    )
    # repetitionを一対一結合する
    suite_stats["repetition"] = build_one_to_one_suite(
        suite_name="repetition",
        instruction_archive_path=evaluation_instructions_archive,
        code_archive_path=evaluation_code_archive,
        code_members=EVALUATION_CODE_MEMBERS["repetition"],
        output_path=output_paths["repetition"],
        test_set_id=test_set_ids["repetition"],
        pairing_seed=pairing_seed,
    )
    # paraphrase 30件を作る
    suite_stats["paraphrase"] = build_paraphrase_suite(
        instruction_archive_path=paraphrase_instructions_archive,
        single_operation_codes_path=single_operation_codes,
        output_path=output_paths["paraphrase"],
        test_set_id=test_set_ids["paraphrase"],
        pairing_seed=pairing_seed,
    )
    # normal 24,040件からboundaryを派生する
    suite_stats["boundary"] = build_boundary_suite(
        normal_path=output_paths["normal"],
        output_path=output_paths["boundary"],
        test_set_id=test_set_ids["boundary"],
        pairing_seed=pairing_seed,
    )
    # 全集合の合計件数を計算する
    total_record_count = sum(item["record_count"] for item in suite_stats.values())
    # 総数を期待値と照合する
    if total_record_count != expected_record_count:
        # 件数不一致を拒否する
        raise ValueError(
            f"最終評価レコード総数が一致しません: {total_record_count} != {expected_record_count}"
        )
    # 全record_idの一意性を横断確認する
    all_record_ids: set[str] = set()
    # 全指示IDとコードIDも横断集計する
    all_instruction_ids: set[str] = set()
    # コードID集合を初期化する
    all_code_ids: set[str] = set()
    # 6 JSONLを順番に読み直す
    for suite_name in OUTPUT_FILENAMES:
        # 対象JSONLを開く
        with output_paths[suite_name].open("r", encoding="utf-8") as handle:
            # 全レコードを一件ずつ処理する
            for record in read_jsonl(handle, str(output_paths[suite_name])):
                # record_id横断重複を拒否する
                if record["record_id"] in all_record_ids:
                    # 重複IDを明示する
                    raise ValueError(f"評価集合間でrecord_idが重複しています: {record['record_id']}")
                # ID集合へ追加する
                all_record_ids.add(record["record_id"])
                # 指示IDを横断集合へ追加する
                all_instruction_ids.add(record["instruction_id"])
                # コードIDを横断集合へ追加する
                all_code_ids.add(record["code_id"])
    # 全record_idが一意であることを確認する
    if len(all_record_ids) != total_record_count:
        # 一意性違反を拒否する
        raise ValueError("最終評価record_idが一意ではありません")
    # 決定的BZIP2 ZIPを作る
    write_deterministic_archive(output_paths, archive)
    # ZIPを開いてメンバー順とCRCを検査する
    with zipfile.ZipFile(archive) as result_archive:
        # 期待するメンバー名一覧を作る
        expected_members = [OUTPUT_FILENAMES[name] for name in OUTPUT_FILENAMES]
        # メンバー名と順序を照合する
        if result_archive.namelist() != expected_members:
            # ZIP構成不一致を拒否する
            raise ValueError("評価ZIPのメンバー名または順序が一致しません")
        # CRC検査エラーがないことを確認する
        if result_archive.testzip() is not None:
            # 破損ZIPを拒否する
            raise ValueError("評価ZIPのCRC検査に失敗しました")
    # 処理後入力ハッシュを再計算する
    input_hashes_after = {
        display_path(path): file_sha256(path) for path in input_paths.values()
    }
    # 入力不変を確認する
    if input_hashes_after != input_hashes_before:
        # 処理中の入力変更を拒否する
        raise ValueError("評価最終結合中に入力ファイルが変更されました")
    # 集計レコードを作る
    stats_record = {
        "phase": "final_evaluation_record_join",
        "generator_version": GENERATOR_VERSION,
        "pairing_seed": pairing_seed,
        "total_record_count": total_record_count,
        "unique_record_id_count": len(all_record_ids),
        "unique_instruction_id_count": len(all_instruction_ids),
        "unique_code_id_count": len(all_code_ids),
        "source_inputs_unchanged": True,
        "input_sha256_before": input_hashes_before,
        "input_sha256_after": input_hashes_after,
        "sets": {key: suite_stats[key] for key in sorted(suite_stats)},
        "archive": display_path(archive),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": file_sha256(archive),
        "archive_compression": "bzip2",
        "archive_members": [OUTPUT_FILENAMES[name] for name in OUTPUT_FILENAMES],
    }
    # 集計JSONを整形して保存する
    stats.write_text(
        json.dumps(stats_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # 呼出し元へ集計を返す
    return stats_record


# CLI入口を定義する
def main() -> None:
    """コマンドライン引数を使って最終評価レコード一式を作る。"""

    # コマンドライン引数を取得する
    args = parse_args()
    # 最終評価レコードを生成する
    result = build_final_evaluation_records(
        evaluation_instructions_archive=args.evaluation_instructions_archive.resolve(),
        paraphrase_instructions_archive=args.paraphrase_instructions_archive.resolve(),
        evaluation_code_archive=args.evaluation_code_archive.resolve(),
        multi_operation_code_archive=args.multi_operation_code_archive.resolve(),
        single_operation_codes=args.single_operation_codes.resolve(),
        evaluation_input_stats=args.evaluation_input_stats.resolve(),
        output_dir=args.output_dir.resolve(),
        archive=args.archive.resolve(),
        stats=args.stats.resolve(),
        expected_record_count=args.expected_record_count,
        pairing_seed=args.pairing_seed,
        overwrite=args.overwrite,
    )
    # 作成結果の要点を表示する
    print(
        "最終評価レコードを作成しました: "
        f"records={result['total_record_count']}, "
        f"unique_records={result['unique_record_id_count']}, "
        f"archive_bytes={result['archive_bytes']}"
    )


# 直接実行された場合だけCLI処理を開始する
if __name__ == "__main__":
    # 評価最終結合を開始する
    main()
