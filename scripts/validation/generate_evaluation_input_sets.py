"""評価用のvalidation・hidden・boundary入力集合を決定的に生成して検証する。"""

# 将来のPythonでも現在の型注釈をそのまま評価できるようにする
from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse
# 件数やタグ分布を集計するために使う
from collections import Counter
# SHA-256を計算するために使う
import hashlib
# JSONとJSONLを読み書きするために使う
import json
# 一時ファイルを完成ファイルへ安全に置き換えるために使う
import os
# 入出力パスを扱うために使う
from pathlib import Path
# 決定的な疑似乱数入力を作るために使う
import random
# ルート直下の参照インタプリタを読み込むために使う
import sys
# 任意のJSON値の型注釈に使う
from typing import Any


# このファイルからリポジトリルートを求める
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# ルート直下のモジュールをimportできるよう探索パスへ追加する
if str(PROJECT_ROOT) not in sys.path:
    # 既存パスより先にリポジトリルートを追加する
    sys.path.insert(0, str(PROJECT_ROOT))

# 生成対象コードとは別実装の参照インタプリタを読み込む
from reference_interpreter import interpret  # noqa: E402


# 評価入力生成器の版を定義する
GENERATOR_VERSION = "1"
# ランダム集合の生成アルゴリズム名を定義する
RANDOM_ALGORITHM = "stratified_random_integer_list_v1"
# 抽出AST向け境界ケースの生成アルゴリズム名を定義する
TARGETED_FILTER_ALGORITHM = "first_filter_all_elements_rejected_singleton_search_v1"


# CLI引数を作る関数を定義する
def parse_args() -> argparse.Namespace:
    """評価入力生成に必要な設定と上書き可否を受け取る。"""

    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        description="validation・hidden・boundary評価入力を生成して全意味ASTで検証します。"
    )
    # 入出力・seed・件数を持つ設定JSONを受け取る
    parser.add_argument("--config", required=True, type=Path)
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


# 設定内の相対パスを解決する関数を定義する
def resolve_path(config_path: Path, value: str) -> Path:
    """設定パスをリポジトリルート基準の絶対パスへ変換する。"""

    # 設定値をPathへ変換する
    path = Path(value)
    # 絶対パスならそのまま返す
    if path.is_absolute():
        # 呼出し元へ絶対パスを返す
        return path
    # 通常の設定はリポジトリルート基準で解決する
    return PROJECT_ROOT / path


# Gitへ保存しやすい表示パスを作る関数を定義する
def display_path(path: Path) -> str:
    """リポジトリ内なら相対パス、それ以外なら絶対パスを返す。"""

    # リポジトリ内相対パスへの変換を試す
    try:
        # POSIX形式の相対パスを返す
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    # テスト用一時ディレクトリなどは絶対パスのまま扱う
    except ValueError:
        # 解決済み絶対パスを返す
        return str(path.resolve())


# JSON設定を読み込む関数を定義する
def read_json_object(path: Path) -> dict[str, Any]:
    """JSONファイルをobjectとして読み込む。"""

    # UTF-8のJSONを解析する
    value = json.loads(path.read_text(encoding="utf-8"))
    # 最上位がobjectであることを確認する
    if not isinstance(value, dict):
        # 配列などを設定として許可しない
        raise ValueError(f"JSONの最上位がobjectではありません: {path}")
    # 検査済みobjectを返す
    return value


# JSONLの意味ASTを読み込む関数を定義する
def read_semantic_asts(path: Path, expected_count: int) -> list[dict[str, Any]]:
    """意味AST JSONLを読み、ID・AST・件数を検査する。"""

    # 入力ファイルが存在することを確認する
    if not path.is_file():
        # 欠落パスを明示して停止する
        raise FileNotFoundError(path)
    # 読み込んだレコードを保存する
    records: list[dict[str, Any]] = []
    # spec_idの一意性を確認する集合を作る
    spec_ids: set[str] = set()
    # JSONLを行番号付きで開く
    with path.open("r", encoding="utf-8") as handle:
        # 一行ずつ処理する
        for line_number, line in enumerate(handle, start=1):
            # 空行を無視する
            if not line.strip():
                # 次の行へ進む
                continue
            # JSON構文を解析する
            try:
                # 一行をobjectへ変換する
                record = json.loads(line)
            # 不正JSONへ行番号を追加する
            except json.JSONDecodeError as error:
                # 入力位置を示して停止する
                raise ValueError(f"JSONLが不正です: {path}:{line_number}") from error
            # レコードがobjectであることを確認する
            if not isinstance(record, dict):
                # 配列や文字列を拒否する
                raise ValueError(f"意味ASTレコードがobjectではありません: {path}:{line_number}")
            # spec_idを取得する
            spec_id = record.get("spec_id")
            # spec_idが空でない文字列であることを確認する
            if not isinstance(spec_id, str) or not spec_id:
                # 不正IDを拒否する
                raise ValueError(f"spec_idが不正です: {path}:{line_number}")
            # 同じspec_idの再登場を拒否する
            if spec_id in spec_ids:
                # 重複IDを明示して停止する
                raise ValueError(f"spec_idが重複しています: {spec_id}")
            # 意味ASTを取得する
            semantic_ast = record.get("semantic_ast")
            # 意味ASTの形式を検査する
            operation_sequence(semantic_ast)
            # ID集合へ追加する
            spec_ids.add(spec_id)
            # レコード一覧へ追加する
            records.append(record)
    # 件数を設定の期待値と照合する
    if len(records) != expected_count:
        # 件数不一致を明示して停止する
        raise ValueError(f"意味AST件数が一致しません: {path}: {len(records)} != {expected_count}")
    # 検査済み意味AST一覧を返す
    return records


# 意味ASTを操作列へ統一する関数を定義する
def operation_sequence(semantic_ast: Any) -> list[dict[str, Any]]:
    """単独操作またはsequence形式の意味ASTから1〜3操作を返す。"""

    # 意味ASTがobjectであることを確認する
    if not isinstance(semantic_ast, dict):
        # 不正形式を拒否する
        raise ValueError("semantic_astがobjectではありません")
    # sequence形式なら内部配列を取得する
    if set(semantic_ast) == {"sequence"}:
        # 操作列を取得する
        sequence = semantic_ast["sequence"]
    # 単独操作なら一要素配列へ包む
    else:
        # 単独操作を操作列へ変換する
        sequence = [semantic_ast]
    # 操作列が1〜3要素の配列であることを確認する
    if not isinstance(sequence, list) or not 1 <= len(sequence) <= 3:
        # 対象外の操作数を拒否する
        raise ValueError("semantic_astの操作数が1〜3ではありません")
    # 各操作がキー一つのobjectであることを確認する
    if any(not isinstance(operation, dict) or len(operation) != 1 for operation in sequence):
        # 不正操作を拒否する
        raise ValueError("semantic_ast内の操作形式が不正です")
    # 型検査済みの操作列を返す
    return sequence


# 評価ケースを正規化する関数を定義する
def case_key(xs: list[int], k: int) -> str:
    """入力リストとkを完全一致比較できる文字列へ変換する。"""

    # 配列とkを決定的JSONへ変換する
    return canonical_json({"xs": xs, "k": k})


# 一件の入力条件を検査する関数を定義する
def validate_case(xs: Any, k: Any, source_name: str) -> tuple[list[int], int]:
    """参照インタプリタの公開入力条件どおりか確認する。"""

    # xsがリストであることを確認する
    if not isinstance(xs, list):
        # 不正型を拒否する
        raise ValueError(f"{source_name}のxsがリストではありません")
    # リスト長が0〜20であることを確認する
    if not 0 <= len(xs) <= 20:
        # 範囲外の長さを拒否する
        raise ValueError(f"{source_name}のxs長が0〜20ではありません")
    # boolを除く整数かつ-100〜100であることを確認する
    if any(type(value) is not int or not -100 <= value <= 100 for value in xs):
        # 範囲外または型違反を拒否する
        raise ValueError(f"{source_name}のxs要素が-100〜100の整数ではありません")
    # kがboolを除く1〜10の整数であることを確認する
    if type(k) is not int or not 1 <= k <= 10:
        # 範囲外または型違反を拒否する
        raise ValueError(f"{source_name}のkが1〜10の整数ではありません")
    # 呼出し元の変更を防ぐためxsをコピーして返す
    return list(xs), k


# 既存build検証ケースを読み込む関数を定義する
def read_excluded_build_cases(path: Path) -> set[str]:
    """訓練コード検証に使った入力を完全一致除外集合として返す。"""

    # build検証manifestを読み込む
    manifest = read_json_object(path)
    # ケース配列を取得する
    cases = manifest.get("cases")
    # ケース配列が存在することを確認する
    if not isinstance(cases, list):
        # 不正manifestを拒否する
        raise ValueError("build検証manifestのcasesが配列ではありません")
    # 完全一致キーを保存する
    keys: set[str] = set()
    # 全ケースを一件ずつ検査する
    for index, case in enumerate(cases, start=1):
        # ケースがobjectであることを確認する
        if not isinstance(case, dict):
            # 不正ケースを拒否する
            raise ValueError(f"build検証ケース{index}がobjectではありません")
        # 入力条件を検査する
        xs, k = validate_case(case.get("xs"), case.get("k"), f"build-case-{index}")
        # 重複を拒否する
        key = case_key(xs, k)
        # 同じbuildケースの重複を確認する
        if key in keys:
            # 完全重複を拒否する
            raise ValueError(f"build検証ケースが重複しています: {index}")
        # 除外集合へ追加する
        keys.add(key)
    # 検査済み集合を返す
    return keys


# ランダムケースへ層化特徴を加える関数を定義する
def apply_stratum(xs: list[int], k: int, mode: int, generator: random.Random) -> list[str]:
    """ケース番号に応じた値を埋め込み、操作分岐を通りやすくする。"""

    # mode 0では0と符号混在を必ず入れる
    if mode == 0:
        # 先頭値を0へ固定する
        xs[0] = 0
        # 二番目を負数へ固定する
        xs[1] = -generator.randint(1, 100)
        # 対応タグを返す
        return ["contains_zero", "mixed_sign"]
    # mode 1ではkとの等値・近傍を入れる
    if mode == 1:
        # 先頭をkと同じ値へする
        xs[0] = k
        # 二番目をk未満へする
        xs[1] = k - 1
        # 三番目があればk超過へする
        if len(xs) >= 3:
            # kの直上値を入れる
            xs[2] = k + 1
        # 対応タグを返す
        return ["threshold_equal", "threshold_neighbors"]
    # mode 2ではkの倍数と非倍数を混ぜる
    if mode == 2:
        # 先頭を負の倍数へする
        xs[0] = -k
        # 二番目を正の倍数へする
        xs[1] = k
        # 三番目があれば非倍数候補を入れる
        if len(xs) >= 3:
            # kが1でも異なる値になるようk+1を入れる
            xs[2] = k + 1
        # 対応タグを返す
        return ["multiples_and_nonmultiples"]
    # mode 3では重複値を必ず入れる
    if mode == 3:
        # 範囲内の値を一つ選ぶ
        repeated = generator.randint(-100, 100)
        # 先頭二要素を同じ値へする
        xs[0] = repeated
        # 二番目も同じ値へする
        xs[1] = repeated
        # 対応タグを返す
        return ["duplicates"]
    # mode 4では入力値域の両端を入れる
    if mode == 4:
        # 最小値を入れる
        xs[0] = -100
        # 最大値を入れる
        xs[1] = 100
        # 対応タグを返す
        return ["value_extremes", "mixed_sign"]
    # mode 5では偶数・奇数・符号を混在させる
    if mode == 5:
        # 先頭を負の偶数へする
        xs[0] = -2
        # 二番目を正の奇数へする
        xs[1] = 3
        # 三番目があれば正の偶数へする
        if len(xs) >= 3:
            # 偶数を追加する
            xs[2] = 4
        # 対応タグを返す
        return ["parity_mix", "mixed_sign"]
    # mode 6では入力を昇順へ揃える
    if mode == 6:
        # 値を小さい順に並べる
        xs.sort()
        # 対応タグを返す
        return ["already_ascending"]
    # mode 7では入力を降順へ揃える
    if mode == 7:
        # 値を大きい順に並べる
        xs.sort(reverse=True)
        # 対応タグを返す
        return ["already_descending"]
    # 到達しないmodeを明示的に拒否する
    raise ValueError(f"未知の層化modeです: {mode}")


# 決定的ランダム入力集合を作る関数を定義する
def generate_random_cases(
    *, name: str, seed: int, count: int, forbidden_keys: set[str]
) -> list[dict[str, Any]]:
    """build入力や他集合と重ならない層化ランダムケースを作る。"""

    # 正の件数だけを許可する
    if count <= 0:
        # 不正設定を拒否する
        raise ValueError(f"{name}のcase_countは正の整数にしてください")
    # 固定seedの乱数生成器を作る
    generator = random.Random(seed)
    # 作成済みケースを保存する
    cases: list[dict[str, Any]] = []
    # 無限再試行を防ぐ上限を設定する
    attempt_limit = count * 100
    # 試行回数を初期化する
    attempts = 0
    # 必要件数へ達するまで候補を作る
    while len(cases) < count:
        # 試行回数を増やす
        attempts += 1
        # 上限超過時は設定またはアルゴリズム異常として停止する
        if attempts > attempt_limit:
            # 生成不能を明示する
            raise ValueError(f"{name}で固有ケース{count}件を生成できません")
        # 境界専用の空・単要素を避けて長さ2〜20を選ぶ
        length = generator.randint(2, 20)
        # kを仕様範囲1〜10から選ぶ
        k = generator.randint(1, 10)
        # 元のランダム整数列を作る
        xs = [generator.randint(-100, 100) for _ in range(length)]
        # 採用済み件数から8種の層を順番に割り当てる
        mode = len(cases) % 8
        # 操作分岐用の値とタグを埋め込む
        tags = apply_stratum(xs, k, mode, generator)
        # 完全一致比較キーを作る
        key = case_key(xs, k)
        # build入力または先行評価集合と重なる候補を捨てる
        if key in forbidden_keys:
            # 次候補を生成する
            continue
        # 新ケースを全後続集合の除外対象へ加える
        forbidden_keys.add(key)
        # 安定した連番ID付きで保存する
        cases.append(
            {
                "case_id": f"{name}-case-{len(cases) + 1:03d}",
                "xs": xs,
                "k": k,
                "tags": tags,
            }
        )
    # 完成したケース一覧を返す
    return cases


# 参照インタプリタで入力集合を検証する関数を定義する
def verify_cases_against_asts(
    semantic_asts: list[dict[str, Any]], cases: list[dict[str, Any]], source_name: str
) -> dict[str, int]:
    """全意味ASTと全ケースを実行し、型と入力不変を確認する。"""

    # 実行件数を初期化する
    execution_count = 0
    # 空出力件数を初期化する
    empty_output_count = 0
    # 全意味ASTを一件ずつ処理する
    for ast_record in semantic_asts:
        # 意味AST本体を取得する
        semantic_ast = ast_record["semantic_ast"]
        # 全入力ケースを一件ずつ処理する
        for case in cases:
            # ケース入力を検査する
            xs, k = validate_case(case.get("xs"), case.get("k"), source_name)
            # 入力不変確認用コピーを作る
            before = list(xs)
            # 参照インタプリタで期待出力を計算する
            output = interpret(semantic_ast, xs, k)
            # 入力リストが変更されていないことを確認する
            if xs != before:
                # 破壊的変更を拒否する
                raise ValueError(f"{source_name}で参照実装が入力xsを変更しました")
            # 出力が整数リストであることを確認する
            if not isinstance(output, list) or any(type(value) is not int for value in output):
                # 不正出力を拒否する
                raise ValueError(f"{source_name}で参照出力が整数リストではありません")
            # 実行件数を増やす
            execution_count += 1
            # 空出力なら件数を増やす
            if not output:
                # 空出力件数を加算する
                empty_output_count += 1
    # 検証集計を返す
    return {
        "reference_execution_count": execution_count,
        "empty_output_count": empty_output_count,
    }


# 最初の抽出操作位置を探す関数を定義する
def first_filter_index(semantic_ast: dict[str, Any]) -> int | None:
    """意味ASTの最初のfilter位置を返し、なければNoneを返す。"""

    # 操作列を取得する
    sequence = operation_sequence(semantic_ast)
    # 操作を位置付きで調べる
    for index, operation in enumerate(sequence):
        # filter操作なら現在位置を返す
        if "filter" in operation:
            # 最初のfilter位置を返す
            return index
    # filterがなければ対象外を返す
    return None


# 抽出AST固有の全要素不合格ケースを作る関数を定義する
def build_targeted_filter_case(
    *,
    spec_id: str,
    semantic_ast: dict[str, Any],
    forbidden_keys: set[str],
) -> dict[str, Any] | None:
    """最初のfilter直前を非空に保ち、そのfilterで空になる入力を探す。"""

    # 最初のfilter位置を取得する
    target_index = first_filter_index(semantic_ast)
    # filterを含まないASTでは固有ケースを作らない
    if target_index is None:
        # 対象外を返す
        return None
    # 操作列を取得する
    sequence = operation_sequence(semantic_ast)
    # 対象filter操作を取得する
    target_filter = sequence[target_index]
    # filterより前の非filter操作列を取得する
    prefix = sequence[:target_index]
    # 全有効なsingleton入力候補を作る
    candidates = [(value, k) for k in range(1, 11) for value in range(-100, 101)]
    # spec_idごとに異なる決定的順位で候補を並べる
    candidates.sort(
        key=lambda item: text_sha256(
            f"{TARGETED_FILTER_ALGORITHM}\0{spec_id}\0{item[0]}\0{item[1]}"
        )
    )
    # 候補を一件ずつ試す
    for value, k in candidates:
        # singleton入力を作る
        xs = [value]
        # build・共有境界・他spec固有ケースとの完全重複を避ける
        key = case_key(xs, k)
        # 既使用ケースなら次へ進む
        if key in forbidden_keys:
            # 次候補を試す
            continue
        # prefixが空なら元入力をfilter直前値とする
        if not prefix:
            # singletonをコピーする
            before_filter = list(xs)
        # prefixがある場合はその操作列だけを参照実行する
        else:
            # prefixをsequence ASTとして実行する
            before_filter = interpret({"sequence": prefix}, xs, k)
        # filter直前が空では境界条件を満たさない
        if not before_filter:
            # 次候補を試す
            continue
        # 元入力からprefixと対象filterを一続きで実行する
        # prefixのmapで±100を超える中間値は仕様上有効なので再入力にはしない
        after_filter = interpret({"sequence": [*prefix, target_filter]}, xs, k)
        # 全要素が除外されなければ次候補を試す
        if after_filter:
            # 次候補を試す
            continue
        # filter名を取得する
        filter_name = target_filter["filter"][0]
        # 検査条件を満たした固有ケースを返す
        return {
            "case_id": f"boundary-filter-target-{spec_id}",
            "spec_id": spec_id,
            "semantic_hash": text_sha256(canonical_json(semantic_ast)),
            "xs": xs,
            "k": k,
            "tags": ["all_elements_rejected", "targeted_first_filter", "singleton"],
            "target_operation_index": target_index,
            "target_filter": filter_name,
        }
    # 全候補でfilterが必ず通過する場合は到達不能としてNoneを返す
    return None


# 境界入力集合を作る関数を定義する
def build_boundary_manifest(
    *,
    boundary_config: dict[str, Any],
    semantic_asts: list[dict[str, Any]],
    forbidden_keys: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """共通境界ケースとfilter AST固有ケースを作り、全件検証する。"""

    # 設定上の共通ケース配列を取得する
    configured_cases = boundary_config.get("shared_cases")
    # 配列であることを確認する
    if not isinstance(configured_cases, list) or not configured_cases:
        # 空または不正設定を拒否する
        raise ValueError("boundary_set.shared_casesは空でない配列にしてください")
    # ID付き共通ケースを保存する
    shared_cases: list[dict[str, Any]] = []
    # タグ分布を集計する
    tag_counts: Counter[str] = Counter()
    # 設定ケースを一件ずつ検査する
    for index, configured_case in enumerate(configured_cases, start=1):
        # ケースがobjectであることを確認する
        if not isinstance(configured_case, dict):
            # 不正ケースを拒否する
            raise ValueError(f"boundary shared case {index}がobjectではありません")
        # 入力条件を検査する
        xs, k = validate_case(
            configured_case.get("xs"), configured_case.get("k"), f"boundary-shared-{index}"
        )
        # タグ配列を取得する
        tags = configured_case.get("tags")
        # タグが空でない文字列配列であることを確認する
        if not isinstance(tags, list) or not tags or any(
            not isinstance(tag, str) or not tag for tag in tags
        ):
            # 不正タグを拒否する
            raise ValueError(f"boundary shared case {index}のtagsが不正です")
        # 完全一致キーを作る
        key = case_key(xs, k)
        # build・random評価・同じ境界集合との重複を拒否する
        if key in forbidden_keys:
            # 重複位置を明示して停止する
            raise ValueError(f"boundary shared case {index}が既存入力と重複しています")
        # 後続ケースの除外対象へ加える
        forbidden_keys.add(key)
        # タグ分布を加算する
        tag_counts.update(tags)
        # ID付きケースを追加する
        shared_cases.append(
            {
                "case_id": f"boundary-shared-case-{index:03d}",
                "xs": xs,
                "k": k,
                "tags": tags,
            }
        )
    # 全共通ケースを全normal ASTで参照実行する
    shared_verification = verify_cases_against_asts(
        semantic_asts, shared_cases, "boundary-shared"
    )
    # spec固有filterケースを保存する
    targeted_cases: list[dict[str, Any]] = []
    # 全要素不合格が意味上到達不能なASTを保存する
    unreachable_filter_asts: list[dict[str, Any]] = []
    # normal ASTを一件ずつ処理する
    for ast_record in semantic_asts:
        # spec_idを取得する
        spec_id = ast_record["spec_id"]
        # 抽出を含む場合だけ固有ケースを作る
        targeted_case = build_targeted_filter_case(
            spec_id=spec_id,
            semantic_ast=ast_record["semantic_ast"],
            forbidden_keys=forbidden_keys,
        )
        # filterを含まないASTなら追加しない
        if first_filter_index(ast_record["semantic_ast"]) is None:
            # 次のASTへ進む
            continue
        # filterを含むが全要素不合格へ到達できない場合を記録する
        if targeted_case is None:
            # 最初のfilter位置を取得する
            target_index = first_filter_index(ast_record["semantic_ast"])
            # 直前の条件でNoneではないことを確認済みとする
            assert target_index is not None
            # 操作列を取得する
            sequence = operation_sequence(ast_record["semantic_ast"])
            # 到達不能理由と対象filterを保存する
            unreachable_filter_asts.append(
                {
                    "spec_id": spec_id,
                    "semantic_hash": text_sha256(canonical_json(ast_record["semantic_ast"])),
                    "target_operation_index": target_index,
                    "target_filter": sequence[target_index]["filter"][0],
                    "reason": "no_nonempty_singleton_can_be_rejected_after_prefix",
                    "searched_input_domain": {
                        "xs": "all singleton integer values from -100 through 100",
                        "k": "all integers from 1 through 10",
                    },
                }
            )
            # 次のASTへ進む
            continue
        # 固有ケース全体を参照実行する
        xs = list(targeted_case["xs"])
        # 入力不変確認用コピーを作る
        before = list(xs)
        # AST全体の出力を取得する
        output = interpret(ast_record["semantic_ast"], xs, targeted_case["k"])
        # 入力不変を確認する
        if xs != before:
            # 破壊的変更を拒否する
            raise ValueError(f"boundary targetedで入力が変更されました: {spec_id}")
        # 最初のfilterで空になるため最終出力も空であることを確認する
        if output != []:
            # 境界条件の検証失敗を拒否する
            raise ValueError(f"boundary targetedの最終出力が空ではありません: {spec_id}")
        # 検証済み固有ケースを保存する
        targeted_cases.append(targeted_case)
    # filterを含むAST数を独立に数える
    filter_ast_count = sum(
        first_filter_index(record["semantic_ast"]) is not None for record in semantic_asts
    )
    # 全filter ASTが固有ケースまたは到達不能記録のどちらかに入ることを確認する
    if len(targeted_cases) + len(unreachable_filter_asts) != filter_ast_count:
        # 対象漏れを拒否する
        raise ValueError("filter AST数と固有境界ケース・到達不能記録の合計が一致しません")
    # 境界manifestを作る
    manifest = {
        "test_set_id": boundary_config["test_set_id"],
        "name": boundary_config["name"],
        "split": boundary_config["split"],
        "test_suite": boundary_config["test_suite"],
        "input_set": boundary_config["input_set"],
        "reference": "reference_interpreter.py",
        "generator_version": GENERATOR_VERSION,
        "shared_case_count": len(shared_cases),
        "targeted_filter_case_count": len(targeted_cases),
        "unreachable_filter_ast_count": len(unreachable_filter_asts),
        "targeted_filter_algorithm": TARGETED_FILTER_ALGORITHM,
        "shared_cases": shared_cases,
        "targeted_filter_cases": targeted_cases,
        "unreachable_filter_asts": unreachable_filter_asts,
    }
    # 境界集合の検証集計を作る
    verification = {
        "semantic_ast_count": len(semantic_asts),
        "filter_semantic_ast_count": filter_ast_count,
        "shared_case_count": len(shared_cases),
        "targeted_filter_case_count": len(targeted_cases),
        "unreachable_filter_ast_count": len(unreachable_filter_asts),
        "reference_execution_count": (
            shared_verification["reference_execution_count"] + len(targeted_cases)
        ),
        "empty_output_count_on_shared_cases": shared_verification["empty_output_count"],
        "targeted_final_empty_output_count": len(targeted_cases),
        "shared_tag_counts": {key: tag_counts[key] for key in sorted(tag_counts)},
    }
    # manifestと検証集計を返す
    return manifest, verification


# JSON成果物を安全に保存する関数を定義する
def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    """整形JSONを一時ファイルへ書いてから所定パスへ置き換える。"""

    # 親ディレクトリを作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 同じディレクトリの一時パスを作る
    temporary = path.with_name(f".{path.name}.tmp")
    # 古い未完成一時ファイルを削除する
    temporary.unlink(missing_ok=True)
    # 整形JSONと末尾改行を保存する
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # 完成ファイルへ原子的に置き換える
    os.replace(temporary, path)


# 評価入力一式を生成する関数を定義する
def generate_evaluation_input_sets(
    *, config_path: Path, overwrite: bool
) -> dict[str, Any]:
    """設定に従って6入力集合を生成・実行検証し、集計を返す。"""

    # 設定ファイルが存在することを確認する
    if not config_path.is_file():
        # 欠落設定を明示して停止する
        raise FileNotFoundError(config_path)
    # 設定JSONを読み込む
    config = read_json_object(config_path)
    # 設定上の生成器版を実装版と照合する
    if config.get("generator_version") != GENERATOR_VERSION:
        # 版違いを拒否する
        raise ValueError("configのgenerator_versionが実装と一致しません")
    # ランダム集合設定を取得する
    random_set_configs = config.get("random_sets")
    # 5集合が設定されていることを確認する
    if not isinstance(random_set_configs, list) or len(random_set_configs) != 5:
        # 欠落や余分な集合を拒否する
        raise ValueError("random_setsは5集合にしてください")
    # 境界集合設定を取得する
    boundary_config = config.get("boundary_set")
    # 境界設定がobjectであることを確認する
    if not isinstance(boundary_config, dict):
        # 欠落を拒否する
        raise ValueError("boundary_setがobjectではありません")
    # build検証manifestのパスを解決する
    build_manifest_path = resolve_path(config_path, config["exclude_build_test_set"])
    # 集計出力パスを解決する
    stats_path = resolve_path(config_path, config["stats"])
    # 各ランダム集合出力パスを解決する
    random_output_paths = [resolve_path(config_path, item["output"]) for item in random_set_configs]
    # 境界出力パスを解決する
    boundary_output_path = resolve_path(config_path, boundary_config["output"])
    # 全出力パスをまとめる
    output_paths = [*random_output_paths, boundary_output_path, stats_path]
    # 上書き未指定なら既存成果物を保護する
    if not overwrite:
        # 既存パスを一件ずつ確認する
        for output_path in output_paths:
            # 既存ファイルがあれば停止する
            if output_path.exists():
                # 上書き方法を示す
                raise FileExistsError(
                    f"出力が既に存在します: {output_path}; --overwriteを指定してください"
                )
    # 参照する全入力ファイルのパスを集める
    semantic_paths = [
        resolve_path(config_path, item["semantic_asts"]) for item in random_set_configs
    ]
    # boundary用意味ASTパスも加える
    semantic_paths.append(resolve_path(config_path, boundary_config["semantic_asts"]))
    # 入力ファイルの重複を除いて処理前ハッシュを保存する
    input_paths = [config_path.resolve(), build_manifest_path.resolve(), *semantic_paths]
    # パス文字列をキーに重複排除する
    unique_input_paths = {str(path.resolve()): path.resolve() for path in input_paths}
    # 全入力の処理前ハッシュを計算する
    input_hashes_before = {
        display_path(path): file_sha256(path) for path in unique_input_paths.values()
    }
    # build検証入力を除外集合として読み込む
    forbidden_keys = read_excluded_build_cases(build_manifest_path)
    # build入力件数を保存する
    build_case_count = len(forbidden_keys)
    # ランダム集合のmanifestを保存する
    random_manifests: list[tuple[Path, dict[str, Any]]] = []
    # 集合別検証結果を保存する
    set_stats: dict[str, dict[str, Any]] = {}
    # テスト集合IDの一意性を確認する集合を作る
    test_set_ids: set[str] = set()
    # ランダム集合を設定順に一件ずつ作る
    for item, output_path in zip(random_set_configs, random_output_paths, strict=True):
        # 必須nameを取得する
        name = item.get("name")
        # 空でない文字列か確認する
        if not isinstance(name, str) or not name:
            # 不正nameを拒否する
            raise ValueError("random setのnameが不正です")
        # テスト集合IDを取得する
        test_set_id = item.get("test_set_id")
        # 空でない文字列か確認する
        if not isinstance(test_set_id, str) or not test_set_id:
            # 不正IDを拒否する
            raise ValueError(f"{name}のtest_set_idが不正です")
        # テスト集合ID重複を拒否する
        if test_set_id in test_set_ids:
            # 重複IDを明示して停止する
            raise ValueError(f"test_set_idが重複しています: {test_set_id}")
        # 使用済みIDへ追加する
        test_set_ids.add(test_set_id)
        # 意味AST入力パスを解決する
        semantic_path = resolve_path(config_path, item["semantic_asts"])
        # 期待件数付きで意味ASTを読み込む
        semantic_asts = read_semantic_asts(
            semantic_path, int(item["expected_semantic_ast_count"])
        )
        # 固定seedと件数で固有ケースを生成する
        cases = generate_random_cases(
            name=name,
            seed=int(item["random_seed"]),
            count=int(item["case_count"]),
            forbidden_keys=forbidden_keys,
        )
        # 全意味ASTで全入力を参照実行する
        verification = verify_cases_against_asts(semantic_asts, cases, name)
        # ケースタグ分布を作る
        tag_counts = Counter(tag for case in cases for tag in case["tags"])
        # 保存manifestを作る
        manifest = {
            "test_set_id": test_set_id,
            "name": name,
            "split": item.get("split"),
            "test_suite": item.get("test_suite"),
            "input_set": item.get("input_set"),
            "reference": config.get("reference"),
            "generator_version": GENERATOR_VERSION,
            "algorithm": RANDOM_ALGORITHM,
            "random_seed": int(item["random_seed"]),
            "case_count": len(cases),
            "cases": cases,
        }
        # 後で一括保存できるよう保持する
        random_manifests.append((output_path, manifest))
        # 集合別集計を保存する
        set_stats[name] = {
            "test_set_id": test_set_id,
            "semantic_asts": display_path(semantic_path),
            "semantic_ast_count": len(semantic_asts),
            "output": display_path(output_path),
            "split": item.get("split"),
            "test_suite": item.get("test_suite"),
            "input_set": item.get("input_set"),
            "random_seed": int(item["random_seed"]),
            "case_count": len(cases),
            "tag_counts": {key: tag_counts[key] for key in sorted(tag_counts)},
            **verification,
        }
    # boundaryのテスト集合IDを取得する
    boundary_test_set_id = boundary_config.get("test_set_id")
    # 空でない文字列か確認する
    if not isinstance(boundary_test_set_id, str) or not boundary_test_set_id:
        # 不正IDを拒否する
        raise ValueError("boundaryのtest_set_idが不正です")
    # 他集合とのID重複を拒否する
    if boundary_test_set_id in test_set_ids:
        # 重複IDを明示して停止する
        raise ValueError(f"test_set_idが重複しています: {boundary_test_set_id}")
    # boundary用意味ASTパスを解決する
    boundary_semantic_path = resolve_path(config_path, boundary_config["semantic_asts"])
    # normal意味ASTを期待件数付きで読み込む
    boundary_semantic_asts = read_semantic_asts(
        boundary_semantic_path, int(boundary_config["expected_semantic_ast_count"])
    )
    # 共通・spec固有境界ケースを生成する
    boundary_manifest, boundary_verification = build_boundary_manifest(
        boundary_config=boundary_config,
        semantic_asts=boundary_semantic_asts,
        forbidden_keys=forbidden_keys,
    )
    # boundary集計を保存する
    set_stats[boundary_config["name"]] = {
        "test_set_id": boundary_test_set_id,
        "semantic_asts": display_path(boundary_semantic_path),
        "output": display_path(boundary_output_path),
        "split": boundary_config.get("split"),
        "test_suite": boundary_config.get("test_suite"),
        "input_set": boundary_config.get("input_set"),
        **boundary_verification,
    }
    # 全manifestを検証後に保存する
    for output_path, manifest in random_manifests:
        # JSON成果物を安全に保存する
        write_json_atomic(output_path, manifest)
    # boundary manifestを保存する
    write_json_atomic(boundary_output_path, boundary_manifest)
    # 入力ファイルの処理後ハッシュを再計算する
    input_hashes_after = {
        display_path(path): file_sha256(path) for path in unique_input_paths.values()
    }
    # 全入力が変更されていないことを確認する
    if input_hashes_after != input_hashes_before:
        # 読み取り専用入力の変更を拒否する
        raise ValueError("評価入力生成中に入力ファイルが変更されました")
    # 出力manifestのハッシュとサイズを集合別集計へ追加する
    for name, output_path in [
        *[
            (item["name"], output_path)
            for item, output_path in zip(random_set_configs, random_output_paths, strict=True)
        ],
        (boundary_config["name"], boundary_output_path),
    ]:
        # 保存サイズを追加する
        set_stats[name]["output_bytes"] = output_path.stat().st_size
        # 保存内容のSHA-256を追加する
        set_stats[name]["output_sha256"] = file_sha256(output_path)
    # 全ランダム評価ケースがbuildと相互に完全一致しない件数を計算する
    random_case_total = sum(int(item["case_count"]) for item in random_set_configs)
    # 最終集計を作る
    stats_record = {
        "phase": "evaluation_input_generation",
        "config": display_path(config_path),
        "config_sha256": file_sha256(config_path),
        "generator_version": GENERATOR_VERSION,
        "random_algorithm": RANDOM_ALGORITHM,
        "targeted_filter_algorithm": TARGETED_FILTER_ALGORITHM,
        "excluded_build_case_count": build_case_count,
        "random_evaluation_case_count": random_case_total,
        "random_case_overlap_with_build": 0,
        "random_case_overlap_between_sets": 0,
        "source_inputs_unchanged": True,
        "input_sha256_before": input_hashes_before,
        "input_sha256_after": input_hashes_after,
        "sets": {key: set_stats[key] for key in sorted(set_stats)},
    }
    # 集計JSONを保存する
    write_json_atomic(stats_path, stats_record)
    # 呼出し元へ集計を返す
    return stats_record


# CLI入口を定義する
def main() -> None:
    """設定ファイルを使って評価入力6集合を生成する。"""

    # コマンドライン引数を取得する
    args = parse_args()
    # 評価入力一式を生成する
    result = generate_evaluation_input_sets(
        config_path=args.config.resolve(), overwrite=args.overwrite
    )
    # 集合別件数を短く表示する
    summary = ", ".join(
        f"{name}={details.get('case_count', details.get('shared_case_count'))}"
        for name, details in result["sets"].items()
    )
    # 完了メッセージを表示する
    print(f"評価入力を生成しました: {summary}")


# 直接実行された場合だけCLI処理を開始する
if __name__ == "__main__":
    # 評価入力生成を開始する
    main()
