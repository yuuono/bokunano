"""置換反映済み日本語指示と検証済みPythonコードを一対一で結合する。"""

# 将来のPythonでも現在の型注釈をそのまま評価できるようにする
from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse
# 件数分布を集計するために使う
from collections import Counter
# 連続する同一spec_idのレコードをまとめるために使う
from contextlib import ExitStack
# SHA-256を計算するために使う
import hashlib
# ZIP内バイナリをUTF-8テキストとして読むために使う
import io
# JSONとJSONLを読み書きするために使う
import json
# 一時ファイルを完成ファイルへ安全に置き換えるために使う
import os
# 入出力パスを扱うために使う
from pathlib import Path
# 決定的な検証入力を作るために使う
import random
# 任意のJSON値とストリームの型注釈に使う
from typing import Any, Iterable, Iterator, TextIO
# コード候補ZIPの読込みと最終成果物ZIPの作成に使う
import zipfile


# ZIP内メンバーの固定日時を定義する
ZIP_TIMESTAMP = (2026, 9, 25, 0, 0, 0)
# 最終訓練JSONLのZIP内ファイル名を定義する
ARCHIVE_MEMBER = "final_dataset_records.jsonl"
# 2操作コード候補のZIP内パスを定義する
TWO_OPERATION_MEMBER = (
    "data/code_candidates/train/two_operation/python_code_candidates.jsonl"
)
# 3操作コード候補のZIP内パスを定義する
THREE_OPERATION_MEMBER = (
    "data/code_candidates/train/three_operation/python_code_candidates.jsonl"
)
# コード生成時に使った検証入力集合のIDを定義する
TEST_SET_ID = "build-verification-v1-seed-0-boundary-9-random-32"
# 最終レコード生成器の版を定義する
GENERATOR_VERSION = "1"
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
    """結合・検証・ZIP作成に必要な入出力を受け取る。"""

    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        description="日本語指示と検証済みコードを意味ASTごとに一対一結合します。"
    )
    # 置換反映済み訓練指示JSONLを受け取る
    parser.add_argument("--instructions", required=True, type=Path)
    # 1操作コード候補JSONLを受け取る
    parser.add_argument("--single-operation-codes", required=True, type=Path)
    # 2・3操作コード候補を持つZIPを受け取る
    parser.add_argument("--multi-operation-code-archive", required=True, type=Path)
    # 最終訓練レコードJSONLの保存先を受け取る
    parser.add_argument("--output-jsonl", required=True, type=Path)
    # 最終訓練レコードZIPの保存先を受け取る
    parser.add_argument("--archive", required=True, type=Path)
    # 指示不足で使わなかったコードJSONLの保存先を受け取る
    parser.add_argument("--rejected-codes", required=True, type=Path)
    # コード検証入力集合の保存先を受け取る
    parser.add_argument("--test-set-manifest", required=True, type=Path)
    # 実行条件と検証結果の保存先を受け取る
    parser.add_argument("--stats", required=True, type=Path)
    # 出力すべき最終レコード総数を受け取る
    parser.add_argument("--expected-record-count", required=True, type=int)
    # 入力コード候補総数を受け取る
    parser.add_argument("--expected-code-count", required=True, type=int)
    # 決定的選抜に使うseedを受け取る
    parser.add_argument("--pairing-seed", default=20260925, type=int)
    # 既存成果物を意図的に置き換える場合だけ使う
    parser.add_argument("--overwrite", action="store_true")
    # 解析済み引数を返す
    return parser.parse_args()


# JSONを決定的に直列化する関数を定義する
def canonical_json(value: Any) -> str:
    """JSON値をキー順・空白なしの比較用文字列へ変換する。"""

    # キー順と区切りを固定して返す
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# 文字列のSHA-256を計算する関数を定義する
def text_sha256(value: str) -> str:
    """文字列のUTF-8バイト列に対するSHA-256を返す。"""

    # UTF-8へ変換してSHA-256を返す
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ファイルのSHA-256を計算する関数を定義する
def file_sha256(path: Path) -> str:
    """大きなファイルを分割してSHA-256を計算する。"""

    # SHA-256計算器を作る
    digest = hashlib.sha256()
    # 対象ファイルをバイナリで開く
    with path.open("rb") as handle:
        # ファイル末尾まで1 MiBずつ読み込む
        while chunk := handle.read(1024 * 1024):
            # 現在のバイト列をハッシュへ追加する
            digest.update(chunk)
    # 16進小文字のSHA-256を返す
    return digest.hexdigest()


# JSONLを検査しながら読む関数を定義する
def read_jsonl(handle: TextIO, source_name: str) -> Iterator[dict[str, Any]]:
    """開かれたJSONLからobjectレコードを一件ずつ返す。"""

    # 一行ずつ行番号付きで処理する
    for line_number, line in enumerate(handle, start=1):
        # 空行はレコードとして数えない
        if not line.strip():
            # 次の行へ進む
            continue
        # JSON構文を解析する
        try:
            # 一行分のJSONをobjectへ変換する
            record = json.loads(line)
        # JSON構文エラーへ入力位置を追加する
        except json.JSONDecodeError as error:
            # 不正な入力を明示して停止する
            raise ValueError(f"JSONLが不正です: {source_name}:{line_number}") from error
        # JSONLの各行がobjectであることを確認する
        if not isinstance(record, dict):
            # 配列や文字列を入力レコードとして許可しない
            raise ValueError(f"JSONLレコードがobjectではありません: {source_name}:{line_number}")
        # 検査済みレコードを返す
        yield record


# 同じspec_idの連続レコードをまとめる関数を定義する
def grouped_by_spec(
    records: Iterable[dict[str, Any]], source_name: str
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """連続する同一spec_idをまとめ、同じIDの再登場を拒否する。"""

    # すでに完了したspec_idを保存する
    completed_spec_ids: set[str] = set()
    # 現在処理中のspec_idを初期化する
    current_spec_id: str | None = None
    # 現在のグループを初期化する
    current_group: list[dict[str, Any]] = []
    # 入力レコードを一件ずつ処理する
    for record in records:
        # 必須spec_idを取得する
        spec_id = require_string(record, "spec_id", source_name)
        # 最初のレコードでは現在IDを設定する
        if current_spec_id is None:
            # 最初のspec_idを保存する
            current_spec_id = spec_id
        # spec_idが変わった場合に前グループを確定する
        if spec_id != current_spec_id:
            # 完了済みIDへ前グループIDを追加する
            completed_spec_ids.add(current_spec_id)
            # 同じIDが離れた位置へ再登場していないことを確認する
            if spec_id in completed_spec_ids:
                # ストリーム結合できない並びを拒否する
                raise ValueError(f"{source_name}でspec_idが再登場しました: {spec_id}")
            # 完成した前グループを返す
            yield current_spec_id, current_group
            # 新しいグループIDへ切り替える
            current_spec_id = spec_id
            # 新しいグループを空で開始する
            current_group = []
        # 現在のグループへレコードを追加する
        current_group.append(record)
    # 最後のグループが存在する場合に返す
    if current_spec_id is not None:
        # 最後のグループを返す
        yield current_spec_id, current_group


# 必須文字列を取得する関数を定義する
def require_string(record: dict[str, Any], key: str, source_name: str) -> str:
    """指定項目を空でない文字列として取得する。"""

    # 対象項目を取得する
    value = record.get(key)
    # 空文字列や文字列以外を拒否する
    if not isinstance(value, str) or not value:
        # 入力元と項目名を示して停止する
        raise ValueError(f"{source_name}の{key}が空でない文字列ではありません")
    # 検査済み文字列を返す
    return value


# 意味ASTの操作数を取得する関数を定義する
def operation_count(semantic_ast: Any, source_name: str) -> int:
    """意味ASTを検査し、sequence内の操作数を返す。"""

    # 意味ASTがobjectであることを確認する
    if not isinstance(semantic_ast, dict):
        # 不正な意味ASTを拒否する
        raise ValueError(f"{source_name}のsemantic_astがobjectではありません")
    # 操作列を取得する
    sequence = semantic_ast.get("sequence")
    # 1〜3操作の配列であることを確認する
    if not isinstance(sequence, list) or not 1 <= len(sequence) <= 3:
        # 対象外の操作数を拒否する
        raise ValueError(f"{source_name}のsemantic_ast.sequenceが1〜3操作ではありません")
    # 操作数を返す
    return len(sequence)


# コード候補を検査する関数を定義する
def validate_code_record(record: dict[str, Any], source_name: str) -> None:
    """コード候補の意味・ハッシュ・検証状態を確認する。"""

    # 必須IDを検査する
    require_string(record, "code_id", source_name)
    # コード本文を取得する
    reference_code = require_string(record, "reference_code", source_name)
    # 意味ASTを取得する
    semantic_ast = record.get("semantic_ast")
    # 意味ASTと操作数を検査する
    operation_count(semantic_ast, source_name)
    # 意味ASTの期待ハッシュを計算する
    expected_semantic_hash = text_sha256(canonical_json(semantic_ast))
    # 保存済み意味ハッシュと一致することを確認する
    if record.get("semantic_hash") != expected_semantic_hash:
        # 意味ハッシュ不一致を拒否する
        raise ValueError(f"{source_name}のsemantic_hashが一致しません")
    # コード本文の期待ハッシュを計算する
    expected_code_hash = text_sha256(reference_code)
    # 保存済みコードハッシュと一致することを確認する
    if record.get("code_hash") != expected_code_hash:
        # コードハッシュ不一致を拒否する
        raise ValueError(f"{source_name}のcode_hashが一致しません")
    # 訓練用コードであることを確認する
    if record.get("split") != "train" or record.get("test_suite") is not None:
        # 評価用コード混入を拒否する
        raise ValueError(f"{source_name}がtrain/test_suite=nullではありません")
    # 検証結果を取得する
    verification = record.get("verification")
    # 検証結果がobjectであることを確認する
    if not isinstance(verification, dict):
        # 検証情報の欠落を拒否する
        raise ValueError(f"{source_name}のverificationがobjectではありません")
    # 必須合格フラグを一件ずつ確認する
    for flag in REQUIRED_VERIFICATION_FLAGS:
        # true以外を不合格として扱う
        if verification.get(flag) is not True:
            # 不合格項目を明示して停止する
            raise ValueError(f"{source_name}のverification.{flag}がtrueではありません")
    # timeoutがfalseであることを確認する
    if verification.get("timeout") is not False:
        # timeout済みコードを拒否する
        raise ValueError(f"{source_name}のverification.timeoutがfalseではありません")


# 日本語指示を検査する関数を定義する
def validate_instruction_record(record: dict[str, Any], source_name: str) -> None:
    """置換反映済み指示の必須項目とハッシュを確認する。"""

    # 指示IDを検査する
    require_string(record, "instruction_id", source_name)
    # 指示文を取得する
    instruction_ja = require_string(record, "instruction_ja", source_name)
    # 意味ASTを取得する
    semantic_ast = record.get("semantic_ast")
    # 意味ASTと操作数を検査する
    operation_count(semantic_ast, source_name)
    # 指示本文ハッシュを照合する
    if record.get("text_hash") != text_sha256(instruction_ja):
        # 本文とハッシュの不一致を拒否する
        raise ValueError(f"{source_name}のtext_hashが一致しません")
    # 訓練用指示であることを確認する
    if record.get("split") != "train" or record.get("test_suite") is not None:
        # 評価用指示混入を拒否する
        raise ValueError(f"{source_name}がtrain/test_suite=nullではありません")
    # 訓練辞書の表現であることを確認する
    if record.get("dictionary") != "train":
        # 言い換え評価専用表現の混入を拒否する
        raise ValueError(f"{source_name}のdictionaryがtrainではありません")
    # 指示生成元を取得する
    instruction_source = record.get("instruction_source")
    # ルール生成または教師言い換えだけを許可する
    if instruction_source not in {"rule", "teacher"}:
        # 未知の生成元を拒否する
        raise ValueError(f"{source_name}のinstruction_sourceが不正です")
    # 教師言い換えでは追跡情報が揃っていることを確認する
    if instruction_source == "teacher":
        # 教師モデル・revision・promptハッシュを一件ずつ検査する
        for key in ("teacher_model", "teacher_revision", "prompt_hash"):
            # 空でない文字列であることを要求する
            require_string(record, key, source_name)
    # ルール生成では教師情報がnullであることを確認する
    else:
        # 教師固有三項目を一件ずつ確認する
        for key in ("teacher_model", "teacher_revision", "prompt_hash"):
            # null以外を混入として拒否する
            if record.get(key) is not None:
                # 不正項目を明示して停止する
                raise ValueError(f"{source_name}のルール生成指示で{key}がnullではありません")


# 決定的順位を作る関数を定義する
def stable_rank(seed: int, category: str, spec_id: str, item_id: str) -> str:
    """seed・用途・spec_id・項目IDから決定的な順位文字列を返す。"""

    # 区切りを固定した文字列のSHA-256を順位として返す
    return text_sha256(f"{seed}\0{category}\0{spec_id}\0{item_id}")


# 指示数に合わせてコードを選ぶ関数を定義する
def select_codes_balanced(
    codes: list[dict[str, Any]], required_count: int, spec_id: str, pairing_seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """不足ASTではcode_styleを均等化しながらコードを決定的に選ぶ。"""

    # 負数やコード数超過を拒否する
    if not 0 <= required_count <= len(codes):
        # 呼出し条件の誤りを明示する
        raise ValueError(f"{spec_id}の必要コード数が範囲外です: {required_count}")
    # 全件使用できる場合は元順序をそのまま返す
    if required_count == len(codes):
        # 不採用なしで返す
        return list(codes), []
    # code_styleごとの候補一覧を作る
    candidates_by_style: dict[str, list[dict[str, Any]]] = {}
    # コード候補を一件ずつ分類する
    for code in codes:
        # code_styleを取得する
        code_style = require_string(code, "code_style", f"code:{spec_id}")
        # 対応する形式一覧へ追加する
        candidates_by_style.setdefault(code_style, []).append(code)
    # 各形式内の候補を決定的順位で並べる
    for code_style, candidates in candidates_by_style.items():
        # code_idを使う決定的順位で並べ替える
        candidates.sort(
            key=lambda item: stable_rank(
                pairing_seed,
                f"code-selection:{code_style}",
                spec_id,
                require_string(item, "code_id", f"code:{spec_id}"),
            )
        )
    # 各形式からの選抜数を初期化する
    selected_counts: Counter[str] = Counter()
    # 選抜済みコードを保存する
    selected: list[dict[str, Any]] = []
    # 必要件数へ達するまで一件ずつ選ぶ
    while len(selected) < required_count:
        # 未選抜候補が残る形式を列挙する
        available_styles = [
            style
            for style, candidates in candidates_by_style.items()
            if selected_counts[style] < len(candidates)
        ]
        # 候補が尽きた異常を検出する
        if not available_styles:
            # 選抜不能として停止する
            raise ValueError(f"{spec_id}で必要件数のコードを選抜できません")
        # 現在の採択数が少ない形式を優先し、同数なら形式名で固定する
        chosen_style = min(available_styles, key=lambda style: (selected_counts[style], style))
        # その形式の次候補を追加する
        selected.append(candidates_by_style[chosen_style][selected_counts[chosen_style]])
        # 形式別採択数を増やす
        selected_counts[chosen_style] += 1
    # 元入力順へ戻すためcode_id集合を作る
    selected_ids = {require_string(item, "code_id", f"code:{spec_id}") for item in selected}
    # 選抜コードを元入力順で作る
    selected_in_source_order = [
        item
        for item in codes
        if require_string(item, "code_id", f"code:{spec_id}") in selected_ids
    ]
    # 不採用コードを元入力順で作る
    rejected_in_source_order = [
        item
        for item in codes
        if require_string(item, "code_id", f"code:{spec_id}") not in selected_ids
    ]
    # 選抜と不採用を返す
    return selected_in_source_order, rejected_in_source_order


# 共有検証入力集合を作る関数を定義する
def build_test_set_manifest() -> dict[str, Any]:
    """コード候補生成と同じseed 0の境界9件・ランダム32件を作る。"""

    # 固定の境界入力9件を作る
    cases: list[tuple[list[int], int]] = [
        ([], 1),
        ([0], 1),
        ([1], 1),
        ([-1], 10),
        ([0, 0, 0], 3),
        ([-5, -1, 0, 1, 5], 2),
        ([5, 4, 3, 2, 1], 5),
        ([1, 1, 2, 2, 3, 3], 10),
        ([-100, 100], 1),
    ]
    # コード生成時と同じseedの乱数生成器を作る
    generator = random.Random(0)
    # ランダム入力32件を追加する
    for _ in range(32):
        # リスト長を0〜20から選ぶ
        length = generator.randint(0, 20)
        # 各要素を-100〜100から選ぶ
        xs = [generator.randint(-100, 100) for _ in range(length)]
        # kを1〜10から選んでケースへ追加する
        cases.append((xs, generator.randint(1, 10)))
    # ケースへ安定したIDを付ける
    case_records = [
        {"case_id": f"build-case-{index:03d}", "xs": xs, "k": k}
        for index, (xs, k) in enumerate(cases, start=1)
    ]
    # 入力集合の来歴を含むmanifestを返す
    return {
        "test_set_id": TEST_SET_ID,
        "purpose": "generated_code_build_verification",
        "reference": "reference_interpreter.py",
        "boundary_case_count": 9,
        "random_case_count": 32,
        "random_seed": 0,
        "case_count": len(case_records),
        "cases": case_records,
    }


# 最終レコードを作る関数を定義する
def make_final_record(
    instruction: dict[str, Any], code: dict[str, Any], pairing_seed: int
) -> dict[str, Any]:
    """一件の指示とコードから来歴を保持した最終レコードを作る。"""

    # 意味ASTを取得する
    semantic_ast = instruction["semantic_ast"]
    # 正規化意味ASTのSHA-256を計算する
    semantic_hash = text_sha256(canonical_json(semantic_ast))
    # コードIDを取得する
    code_id = require_string(code, "code_id", "code")
    # 指示IDを取得する
    instruction_id = require_string(instruction, "instruction_id", "instruction")
    # 指示本文を取得する
    instruction_ja = require_string(instruction, "instruction_ja", "instruction")
    # 訓練レコードのtest_suite正規化値を作る
    normalized_test_suite = canonical_json(None)
    # 共有テスト参照一覧を作る
    tests = [TEST_SET_ID]
    # レコードIDの入力文字列を方針どおり作る
    record_key = (
        f"{code_id}\0{instruction_ja}\0{normalized_test_suite}\0{canonical_json(tests)}"
    )
    # コード生成器の来歴を別名で保存する
    code_generator_version = code.get("generator_version")
    # コード生成seedを別名で保存する
    code_generator_seed = code.get("generator_seed")
    # 指示生成器の来歴を別名で保存する
    instruction_generator_version = instruction.get("generator_version")
    # 指示生成seedを別名で保存する
    instruction_generator_seed = instruction.get("generator_seed")
    # 指示レコード全項目をコピーして来歴を落とさない
    final_record = dict(instruction)
    # 最終結合固有項目とコード全項目を追加する
    final_record.update(
        {
            "record_id": f"record-{text_sha256(record_key)}",
            "family_id": f"family-{semantic_hash}",
            "code_id": code_id,
            "spec_id": code["spec_id"],
            "semantic_ast": semantic_ast,
            "instruction_id": instruction_id,
            "instruction_ja": instruction_ja,
            "reference_code": code["reference_code"],
            "tests": tests,
            "difficulty": operation_count(semantic_ast, "final_record"),
            "code_style": code["code_style"],
            "style_id": code["style_id"],
            "style_spec": code["style_spec"],
            "rewrite_id": code.get("rewrite_id"),
            "split": "train",
            "test_suite": None,
            "dictionary": "train",
            "input_set": "build",
            "semantic_hash": semantic_hash,
            "code_hash": code["code_hash"],
            "text_hash": text_sha256(instruction_ja),
            "code_generator_version": code_generator_version,
            "code_generator_seed": code_generator_seed,
            "instruction_generator_version": instruction_generator_version,
            "instruction_generator_seed": instruction_generator_seed,
            "generator_version": GENERATOR_VERSION,
            "generator_seed": pairing_seed,
            "pairing_strategy": "source_order_with_balanced_code_style_shortfall_selection",
            "pairing_seed": pairing_seed,
            "verification": code["verification"],
        }
    )
    # 完成した最終レコードを返す
    return final_record


# 最終レコードを検査する関数を定義する
def validate_final_record(record: dict[str, Any]) -> None:
    """最終レコードの必須項目、ID、ハッシュ、分割を再確認する。"""

    # 必須文字列項目を一件ずつ検査する
    for key in (
        "record_id",
        "family_id",
        "code_id",
        "spec_id",
        "instruction_id",
        "instruction_ja",
        "reference_code",
        "code_style",
        "style_id",
        "instruction_source",
        "semantic_hash",
        "code_hash",
        "text_hash",
    ):
        # 空でない文字列を要求する
        require_string(record, key, "final_record")
    # 意味ASTを取得する
    semantic_ast = record.get("semantic_ast")
    # 操作数とdifficultyが一致することを確認する
    if record.get("difficulty") != operation_count(semantic_ast, "final_record"):
        # 難易度不一致を拒否する
        raise ValueError("final_recordのdifficultyが操作数と一致しません")
    # 意味ハッシュを再計算する
    semantic_hash = text_sha256(canonical_json(semantic_ast))
    # 意味ハッシュとfamily_idを照合する
    if record["semantic_hash"] != semantic_hash or record["family_id"] != f"family-{semantic_hash}":
        # 意味追跡情報の不一致を拒否する
        raise ValueError("final_recordのsemantic_hashまたはfamily_idが一致しません")
    # コードハッシュを再計算して照合する
    if record["code_hash"] != text_sha256(record["reference_code"]):
        # コード本文改変を拒否する
        raise ValueError("final_recordのcode_hashが一致しません")
    # 指示ハッシュを再計算して照合する
    if record["text_hash"] != text_sha256(record["instruction_ja"]):
        # 指示本文改変を拒否する
        raise ValueError("final_recordのtext_hashが一致しません")
    # record_idを再計算する
    expected_record_id = "record-" + text_sha256(
        f"{record['code_id']}\0{record['instruction_ja']}\0"
        f"{canonical_json(record['test_suite'])}\0{canonical_json(record['tests'])}"
    )
    # record_idが方針どおりであることを確認する
    if record["record_id"] != expected_record_id:
        # ID不一致を拒否する
        raise ValueError("final_recordのrecord_idが一致しません")
    # 訓練分割の固定値を確認する
    if (
        record.get("split") != "train"
        or record.get("test_suite") is not None
        or record.get("dictionary") != "train"
        or record.get("input_set") != "build"
    ):
        # 評価データやhidden入力の混入を拒否する
        raise ValueError("final_recordの分割項目が訓練用ではありません")
    # 共有テスト集合だけを参照することを確認する
    if record.get("tests") != [TEST_SET_ID]:
        # 不明なテスト参照を拒否する
        raise ValueError("final_recordのtestsが共有検証集合を参照していません")
    # 元コードと同じ検証合格状態を再確認する
    validate_code_record(record, "final_record")


# 決定的ZIPを作る関数を定義する
def write_deterministic_zip(source_path: Path, archive_path: Path) -> None:
    """固定メタデータとLZMA圧縮で最終JSONLをZIPへ格納する。"""

    # ZIP内メンバー情報を作る
    member = zipfile.ZipInfo(ARCHIVE_MEMBER, date_time=ZIP_TIMESTAMP)
    # Unix由来ファイルとして記録する
    member.create_system = 3
    # 通常ファイルの0644権限を固定する
    member.external_attr = 0o100644 << 16
    # GitHubの単一ファイル上限内へ収めるため標準LZMA圧縮を指定する
    member.compress_type = zipfile.ZIP_LZMA
    # ZIP64対応で新規ZIPを開く
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_LZMA,
        allowZip64=True,
    ) as archive:
        # ZIP内メンバーを書込み用に開く
        with archive.open(member, mode="w", force_zip64=True) as destination:
            # 元JSONLをバイナリで開く
            with source_path.open("rb") as source:
                # 1 MiBずつ末尾までコピーする
                while chunk := source.read(1024 * 1024):
                    # 圧縮ストリームへ書き込む
                    destination.write(chunk)


# 結合本体を定義する
def build_final_train_records(
    *,
    instructions: Path,
    single_operation_codes: Path,
    multi_operation_code_archive: Path,
    output_jsonl: Path,
    archive: Path,
    rejected_codes: Path,
    test_set_manifest: Path,
    stats: Path,
    expected_record_count: int,
    expected_code_count: int,
    pairing_seed: int,
    overwrite: bool,
) -> dict[str, Any]:
    """全入力を照合し、最終JSONL・不採用記録・ZIP・集計を作る。"""

    # 入力パスを一件ずつ確認する
    for input_path in (instructions, single_operation_codes, multi_operation_code_archive):
        # 入力ファイルが存在することを要求する
        if not input_path.is_file():
            # 欠落パスを明示して停止する
            raise FileNotFoundError(input_path)
    # 出力パス一覧を作る
    output_paths = (output_jsonl, archive, rejected_codes, test_set_manifest, stats)
    # 上書き未指定時は既存成果物を保護する
    if not overwrite:
        # 既存出力を一件ずつ確認する
        for output_path in output_paths:
            # 既存ファイルがある場合は停止する
            if output_path.exists():
                # 上書き方法を示す
                raise FileExistsError(f"出力が既に存在します: {output_path}; --overwriteを指定してください")
    # すべての出力親ディレクトリを作る
    for output_path in output_paths:
        # 必要な親だけを作る
        output_path.parent.mkdir(parents=True, exist_ok=True)
    # 入力ファイルの処理前ハッシュを保存する
    input_hashes_before = {
        "instructions": file_sha256(instructions),
        "single_operation_codes": file_sha256(single_operation_codes),
        "multi_operation_code_archive": file_sha256(multi_operation_code_archive),
    }
    # test set manifestを決定的に作る
    test_manifest_record = build_test_set_manifest()
    # 一時出力JSONLのパスを作る
    temporary_output = output_jsonl.with_name(f".{output_jsonl.name}.tmp")
    # 一時不採用JSONLのパスを作る
    temporary_rejected = rejected_codes.with_name(f".{rejected_codes.name}.tmp")
    # 以前の未完成一時ファイルを削除する
    temporary_output.unlink(missing_ok=True)
    # 以前の未完成不採用ファイルを削除する
    temporary_rejected.unlink(missing_ok=True)
    # 一意性検査用ID集合を初期化する
    record_ids: set[str] = set()
    # 採用コードID集合を初期化する
    selected_code_ids: set[str] = set()
    # 不採用コードID集合を初期化する
    rejected_code_ids: set[str] = set()
    # 指示ID集合を初期化する
    instruction_ids: set[str] = set()
    # spec_id集合を初期化する
    spec_ids: set[str] = set()
    # 操作数別件数を初期化する
    counts_by_operation: Counter[int] = Counter()
    # 指示生成元別件数を初期化する
    counts_by_instruction_source: Counter[str] = Counter()
    # 置換状態別件数を初期化する
    counts_by_replacement_status: Counter[str] = Counter()
    # コード形式別件数を初期化する
    counts_by_code_style: Counter[str] = Counter()
    # 意味AST当たり件数分布用の一覧を初期化する
    records_per_spec: Counter[str] = Counter()
    # 指示不足ASTの詳細を初期化する
    shortfall_specs: list[dict[str, Any]] = []
    # 入力コード総数を初期化する
    input_code_count = 0
    # 出力レコード総数を初期化する
    output_record_count = 0
    # すべてのストリームを一括管理する
    try:
        # 複数のファイル・ZIPストリームを安全に閉じる
        with ExitStack() as stack:
            # 指示JSONLをUTF-8で開く
            instruction_handle = stack.enter_context(instructions.open("r", encoding="utf-8"))
            # 1操作コードJSONLをUTF-8で開く
            single_handle = stack.enter_context(
                single_operation_codes.open("r", encoding="utf-8")
            )
            # 2・3操作コード候補ZIPを開く
            code_archive = stack.enter_context(zipfile.ZipFile(multi_operation_code_archive))
            # 必須ZIPメンバーが存在することを確認する
            for member_name in (TWO_OPERATION_MEMBER, THREE_OPERATION_MEMBER):
                # メンバー欠落を明示して停止する
                if member_name not in code_archive.namelist():
                    # ZIP構成不正を拒否する
                    raise ValueError(f"コード候補ZIPに必要なメンバーがありません: {member_name}")
            # 2操作メンバーをバイナリで開く
            two_binary = stack.enter_context(code_archive.open(TWO_OPERATION_MEMBER))
            # 2操作メンバーをUTF-8テキストとして開く
            two_handle = stack.enter_context(io.TextIOWrapper(two_binary, encoding="utf-8"))
            # 3操作メンバーをバイナリで開く
            three_binary = stack.enter_context(code_archive.open(THREE_OPERATION_MEMBER))
            # 3操作メンバーをUTF-8テキストとして開く
            three_handle = stack.enter_context(io.TextIOWrapper(three_binary, encoding="utf-8"))
            # 1・2・3操作コードを元の生成順で連結する
            code_records = _chain_records(
                read_jsonl(single_handle, str(single_operation_codes)),
                read_jsonl(two_handle, f"{multi_operation_code_archive}:{TWO_OPERATION_MEMBER}"),
                read_jsonl(three_handle, f"{multi_operation_code_archive}:{THREE_OPERATION_MEMBER}"),
            )
            # 指示をspec_idごとのグループへ変換する
            instruction_groups = grouped_by_spec(
                read_jsonl(instruction_handle, str(instructions)), str(instructions)
            )
            # コードをspec_idごとのグループへ変換する
            code_groups = grouped_by_spec(code_records, "train_code_candidates")
            # 最終JSONL一時ファイルを開く
            output_handle = stack.enter_context(temporary_output.open("w", encoding="utf-8"))
            # 不採用JSONL一時ファイルを開く
            rejected_handle = stack.enter_context(temporary_rejected.open("w", encoding="utf-8"))
            # 指示とコードのグループを同時に一件ずつ処理する
            for instruction_group, code_group in _zip_groups_exact(
                instruction_groups, code_groups
            ):
                # 指示側spec_idとレコード一覧を分ける
                instruction_spec_id, instruction_records = instruction_group
                # コード側spec_idとレコード一覧を分ける
                code_spec_id, code_records_for_spec = code_group
                # 両入力のグループ順とIDが一致することを確認する
                if instruction_spec_id != code_spec_id:
                    # 対応ずれを明示して停止する
                    raise ValueError(
                        "指示とコードのspec_id順が一致しません: "
                        f"{instruction_spec_id} != {code_spec_id}"
                    )
                # spec_id重複を拒否する
                if instruction_spec_id in spec_ids:
                    # 一意性違反を明示して停止する
                    raise ValueError(f"spec_idが重複しています: {instruction_spec_id}")
                # 検査済みspec_idを保存する
                spec_ids.add(instruction_spec_id)
                # 指示グループを一件ずつ検査する
                for instruction_record in instruction_records:
                    # 指示レコード本体を検査する
                    validate_instruction_record(
                        instruction_record, f"instruction:{instruction_spec_id}"
                    )
                    # 指示IDを取得する
                    instruction_id = require_string(
                        instruction_record,
                        "instruction_id",
                        f"instruction:{instruction_spec_id}",
                    )
                    # 指示ID重複を拒否する
                    if instruction_id in instruction_ids:
                        # 重複IDを明示して停止する
                        raise ValueError(f"instruction_idが重複しています: {instruction_id}")
                    # 使用済み指示IDへ追加する
                    instruction_ids.add(instruction_id)
                # コードグループを一件ずつ検査する
                for code_record in code_records_for_spec:
                    # コードレコード本体を検査する
                    validate_code_record(code_record, f"code:{code_spec_id}")
                # 入力コード件数を加算する
                input_code_count += len(code_records_for_spec)
                # 先頭指示の正規化ASTを取得する
                expected_ast = canonical_json(instruction_records[0]["semantic_ast"])
                # 同一指示グループ内の意味ASTを照合する
                if any(
                    canonical_json(record["semantic_ast"]) != expected_ast
                    for record in instruction_records
                ):
                    # spec内の意味AST混在を拒否する
                    raise ValueError(f"指示グループ内のsemantic_astが不一致です: {instruction_spec_id}")
                # コード側の意味ASTと指示側を照合する
                if any(
                    canonical_json(record["semantic_ast"]) != expected_ast
                    for record in code_records_for_spec
                ):
                    # 指示とコードの意味不一致を拒否する
                    raise ValueError(f"指示とコードのsemantic_astが不一致です: {instruction_spec_id}")
                # 指示数がコード数以下であることを確認する
                if len(instruction_records) > len(code_records_for_spec):
                    # 対応するコード不足を拒否する
                    raise ValueError(f"コード数が指示数より少ないです: {instruction_spec_id}")
                # 必要数だけコードを形式均等で決定的に選ぶ
                selected_codes, rejected_for_spec = select_codes_balanced(
                    code_records_for_spec,
                    len(instruction_records),
                    instruction_spec_id,
                    pairing_seed,
                )
                # 不足ASTの集計を保存する
                if rejected_for_spec:
                    # 操作名を含む詳細を追加する
                    shortfall_specs.append(
                        {
                            "spec_id": instruction_spec_id,
                            "semantic_ast": instruction_records[0]["semantic_ast"],
                            "instruction_count": len(instruction_records),
                            "code_count": len(code_records_for_spec),
                            "rejected_code_count": len(rejected_for_spec),
                        }
                    )
                # 不採用コードを来歴付きで一件ずつ保存する
                for rejected_code in rejected_for_spec:
                    # コード全項目をコピーする
                    rejected_record = dict(rejected_code)
                    # 不採用理由と選抜条件を追加する
                    rejected_record.update(
                        {
                            "reason": "instruction_shortfall",
                            "instruction_count": len(instruction_records),
                            "code_count": len(code_records_for_spec),
                            "selection_strategy": "balanced_code_style_then_stable_rank",
                            "pairing_seed": pairing_seed,
                        }
                    )
                    # 不採用コードIDを取得する
                    rejected_code_id = require_string(
                        rejected_code, "code_id", f"rejected:{instruction_spec_id}"
                    )
                    # 不採用コードID重複を拒否する
                    if rejected_code_id in rejected_code_ids:
                        # 重複を明示して停止する
                        raise ValueError(f"不採用code_idが重複しています: {rejected_code_id}")
                    # 不採用ID集合へ追加する
                    rejected_code_ids.add(rejected_code_id)
                    # 一行JSONとして保存する
                    rejected_handle.write(canonical_json(rejected_record) + "\n")
                # 指示と選抜コードを元順序で一対一結合する
                for instruction_record, code_record in zip(
                    instruction_records, selected_codes, strict=True
                ):
                    # 最終レコードを作る
                    final_record = make_final_record(
                        instruction_record, code_record, pairing_seed
                    )
                    # 最終レコードを機械検査する
                    validate_final_record(final_record)
                    # 最終レコードIDを取得する
                    record_id = final_record["record_id"]
                    # 同一最終レコードIDを拒否する
                    if record_id in record_ids:
                        # 重複IDを明示して停止する
                        raise ValueError(f"record_idが重複しています: {record_id}")
                    # 最終レコードID集合へ追加する
                    record_ids.add(record_id)
                    # 採用コードIDを取得する
                    selected_code_id = final_record["code_id"]
                    # 同一コードの再利用を拒否する
                    if selected_code_id in selected_code_ids:
                        # 重複使用を明示して停止する
                        raise ValueError(f"code_idを再利用しています: {selected_code_id}")
                    # 採用コードID集合へ追加する
                    selected_code_ids.add(selected_code_id)
                    # 操作数別件数を加算する
                    counts_by_operation[final_record["difficulty"]] += 1
                    # 指示生成元別件数を加算する
                    counts_by_instruction_source[final_record["instruction_source"]] += 1
                    # 置換状態別件数を加算する
                    counts_by_replacement_status[final_record["replacement_status"]] += 1
                    # コード形式別件数を加算する
                    counts_by_code_style[final_record["code_style"]] += 1
                    # spec別件数を加算する
                    records_per_spec[instruction_spec_id] += 1
                    # 出力総数を加算する
                    output_record_count += 1
                    # 一行JSONとして保存する
                    output_handle.write(canonical_json(final_record) + "\n")
        # 最終件数を期待値と照合する
        if output_record_count != expected_record_count:
            # 件数不一致を明示して停止する
            raise ValueError(
                f"最終レコード数が期待値と一致しません: {output_record_count} != {expected_record_count}"
            )
        # 入力コード総数を期待値と照合する
        if input_code_count != expected_code_count:
            # 件数不一致を明示して停止する
            raise ValueError(
                f"入力コード数が期待値と一致しません: {input_code_count} != {expected_code_count}"
            )
        # 全指示が一度ずつ使われたことを確認する
        if len(instruction_ids) != output_record_count:
            # 指示の欠落または重複を拒否する
            raise ValueError("全指示が一度ずつ最終レコードへ使われていません")
        # 採用と不採用のコード数合計を確認する
        if len(selected_code_ids) + len(rejected_code_ids) != input_code_count:
            # コードの欠落を拒否する
            raise ValueError("採用・不採用コードの合計が入力コード数と一致しません")
        # 採用コードと不採用コードが重ならないことを確認する
        if selected_code_ids & rejected_code_ids:
            # 同じコードの二重分類を拒否する
            raise ValueError("採用コードと不採用コードが重複しています")
        # 完成JSONLを所定パスへ置き換える
        os.replace(temporary_output, output_jsonl)
        # 完成不採用JSONLを所定パスへ置き換える
        os.replace(temporary_rejected, rejected_codes)
    # 成否にかかわらず未完成一時ファイルだけを削除する
    finally:
        # 未完成JSONLが残っていれば削除する
        temporary_output.unlink(missing_ok=True)
        # 未完成不採用JSONLが残っていれば削除する
        temporary_rejected.unlink(missing_ok=True)
    # 検証入力集合manifestを整形JSONで保存する
    test_set_manifest.write_text(
        json.dumps(test_manifest_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # 最終JSONLを決定的ZIPへ格納する
    write_deterministic_zip(output_jsonl, archive)
    # 入力ファイルの処理後ハッシュを再計算する
    input_hashes_after = {
        "instructions": file_sha256(instructions),
        "single_operation_codes": file_sha256(single_operation_codes),
        "multi_operation_code_archive": file_sha256(multi_operation_code_archive),
    }
    # 全入力が変更されていないことを確認する
    if input_hashes_after != input_hashes_before:
        # 読み取り専用入力の変更を拒否する
        raise ValueError("結合処理中に入力ファイルが変更されました")
    # 意味AST当たり件数の分布を作る
    records_per_spec_distribution = Counter(records_per_spec.values())
    # 集計レコードを作る
    stats_record = {
        "phase": "final_train_record_join",
        "generator_version": GENERATOR_VERSION,
        "pairing_seed": pairing_seed,
        "pairing_strategy": "source_order_with_balanced_code_style_shortfall_selection",
        "output_record_count": output_record_count,
        "semantic_ast_count": len(spec_ids),
        "input_code_count": input_code_count,
        "selected_code_count": len(selected_code_ids),
        "rejected_code_count": len(rejected_code_ids),
        "instruction_count": len(instruction_ids),
        "counts_by_operation_count": {
            str(key): counts_by_operation[key] for key in sorted(counts_by_operation)
        },
        "counts_by_instruction_source": {
            key: counts_by_instruction_source[key]
            for key in sorted(counts_by_instruction_source)
        },
        "counts_by_replacement_status": {
            key: counts_by_replacement_status[key]
            for key in sorted(counts_by_replacement_status)
        },
        "counts_by_code_style": {
            key: counts_by_code_style[key] for key in sorted(counts_by_code_style)
        },
        "records_per_semantic_ast_distribution": {
            str(key): records_per_spec_distribution[key]
            for key in sorted(records_per_spec_distribution)
        },
        "shortfall_semantic_asts": shortfall_specs,
        "test_set_id": TEST_SET_ID,
        "test_case_count": test_manifest_record["case_count"],
        "source_inputs_unchanged": True,
        "inputs": {
            "instructions": str(instructions),
            "single_operation_codes": str(single_operation_codes),
            "multi_operation_code_archive": str(multi_operation_code_archive),
        },
        "input_sha256_before": input_hashes_before,
        "input_sha256_after": input_hashes_after,
        "output_jsonl": str(output_jsonl),
        "output_jsonl_bytes": output_jsonl.stat().st_size,
        "output_jsonl_sha256": file_sha256(output_jsonl),
        "archive": str(archive),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": file_sha256(archive),
        "archive_member": ARCHIVE_MEMBER,
        "rejected_codes": str(rejected_codes),
        "rejected_codes_bytes": rejected_codes.stat().st_size,
        "rejected_codes_sha256": file_sha256(rejected_codes),
        "test_set_manifest": str(test_set_manifest),
        "test_set_manifest_sha256": file_sha256(test_set_manifest),
    }
    # 集計JSONを読みやすい形式で保存する
    stats.write_text(
        json.dumps(stats_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # 呼出し元へ集計を返す
    return stats_record


# 複数レコード列を順番どおり連結する関数を定義する
def _chain_records(*iterables: Iterable[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """複数のJSONL iteratorを指定順で一つの列として返す。"""

    # 入力iteratorを一つずつ処理する
    for iterable in iterables:
        # 現在のiteratorから全レコードを返す
        yield from iterable


# 二つのグループ列を同数確認付きで結合する関数を定義する
def _zip_groups_exact(
    left: Iterable[tuple[str, list[dict[str, Any]]]],
    right: Iterable[tuple[str, list[dict[str, Any]]]],
) -> Iterator[
    tuple[tuple[str, list[dict[str, Any]]], tuple[str, list[dict[str, Any]]]]
]:
    """二つのグループ列を結合し、片側だけの余りを拒否する。"""

    # iteratorへ変換する
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
        # 型検査器へsentinelではないことを示して返す
        yield left_item, right_item  # type: ignore[misc]


# CLI入口を定義する
def main() -> None:
    """コマンドライン引数を使って最終訓練レコードを作る。"""

    # コマンドライン引数を取得する
    args = parse_args()
    # 最終訓練レコード一式を生成する
    result = build_final_train_records(
        instructions=args.instructions.resolve(),
        single_operation_codes=args.single_operation_codes.resolve(),
        multi_operation_code_archive=args.multi_operation_code_archive.resolve(),
        output_jsonl=args.output_jsonl.resolve(),
        archive=args.archive.resolve(),
        rejected_codes=args.rejected_codes.resolve(),
        test_set_manifest=args.test_set_manifest.resolve(),
        stats=args.stats.resolve(),
        expected_record_count=args.expected_record_count,
        expected_code_count=args.expected_code_count,
        pairing_seed=args.pairing_seed,
        overwrite=args.overwrite,
    )
    # 作成結果の要点を表示する
    print(
        "最終訓練レコードを作成しました: "
        f"records={result['output_record_count']}, "
        f"semantic_asts={result['semantic_ast_count']}, "
        f"rejected_codes={result['rejected_code_count']}"
    )


# 直接実行された場合だけCLI処理を開始する
if __name__ == "__main__":
    # 結合処理を開始する
    main()
