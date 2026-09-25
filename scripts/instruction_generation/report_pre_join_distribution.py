"""訓練用日本語指示と検証済みコードの結合前分布を検証して報告する。"""

# 将来のPythonでも現在の型注釈をそのまま評価できるようにする
from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse
# 件数分布を集計するために使う
from collections import Counter
# ZIP内JSONLを文字列として読むために使う
import io
# JSONとJSONLを読み書きするために使う
import json
# 入出力パスを扱うために使う
from pathlib import Path
# 任意のJSON値を型注釈で表すために使う
from typing import Any, Iterable, TextIO
# 複数操作コードを収録したZIPを読むために使う
import zipfile


# 訓練用複数操作コードが入るZIP内メンバーを固定する
TRAIN_CODE_MEMBERS = (
    # 2操作の検証済みコードを指定する
    "data/code_candidates/train/two_operation/python_code_candidates.jsonl",
    # 3操作の検証済みコードを指定する
    "data/code_candidates/train/three_operation/python_code_candidates.jsonl",
)


# この工程を担当する関数を定義する
def parse_args() -> argparse.Namespace:
    """分布確認に必要な入力と出力を受け取る。"""

    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        # 処理内容をコマンドのヘルプへ表示する
        description="教師言い換えを置換として扱った結合前分布を作成します。"
    )
    # 全集合を含むルール生成指示JSONLを受け取る
    parser.add_argument("--rule-instructions", required=True, type=Path)
    # 全承認済み教師言い換えJSONLを受け取る
    parser.add_argument("--approved-paraphrases", required=True, type=Path)
    # 教師生成時の選抜数と失敗IDを持つ集計JSONを受け取る
    parser.add_argument("--paraphrase-generation-stats", required=True, type=Path)
    # 単一操作の検証済みコードJSONLを受け取る
    parser.add_argument("--single-operation-codes", required=True, type=Path)
    # 2操作と3操作の検証済みコードZIPを受け取る
    parser.add_argument("--multi-operation-code-archive", required=True, type=Path)
    # 機械可読な分布集計JSONの保存先を受け取る
    parser.add_argument("--output-json", required=True, type=Path)
    # 人が確認するMarkdownレポートの保存先を受け取る
    parser.add_argument("--output-md", required=True, type=Path)
    # レポートに記録する基準日を受け取る
    parser.add_argument("--report-date", required=True)
    # 既存成果物を意図的に置き換える場合だけ使う
    parser.add_argument("--overwrite", action="store_true")
    # 解析済み引数を返す
    return parser.parse_args()


# この工程を担当する関数を定義する
def canonical_json(value: Any) -> str:
    """意味ASTを比較できる決定的JSON文字列へ変換する。"""

    # キー順と空白を固定して返す
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# この工程を担当する関数を定義する
def read_jsonl(handle: TextIO, source_name: str) -> Iterable[dict[str, Any]]:
    """開かれたJSONLを行番号付きで検査しながら返す。"""

    # 一行ずつ行番号付きで処理する
    for line_number, line in enumerate(handle, start=1):
        # 空行をレコードとして数えない
        if not line.strip():
            # 次の行へ進む
            continue
        # JSON objectへ変換する
        try:
            # 一行分のJSONを解析する
            record = json.loads(line)
        # 構文エラーへ入力位置を追加する
        except json.JSONDecodeError as error:
            # 不正な入力を明示して停止する
            raise ValueError(f"JSONLが不正です: {source_name}:{line_number}") from error
        # JSONLの各行がobjectであることを確認する
        if not isinstance(record, dict):
            # 配列や文字列を入力レコードとして許可しない
            raise ValueError(f"JSONLレコードがobjectではありません: {source_name}:{line_number}")
        # 検査済みレコードを返す
        yield record


# この工程を担当する関数を定義する
def require_string(record: dict[str, Any], key: str, source_name: str) -> str:
    """必須項目を空でない文字列として取得する。"""

    # 対象項目を取得する
    value = record.get(key)
    # 空文字列や文字列以外を拒否する
    if not isinstance(value, str) or not value:
        # 入力元と項目名を示して停止する
        raise ValueError(f"{source_name}の{key}が空でない文字列ではありません")
    # 検査済み文字列を返す
    return value


# この工程を担当する関数を定義する
def operation_count(semantic_ast: Any, source_name: str) -> int:
    """意味ASTのsequence長を操作数として返す。"""

    # 意味ASTがobjectであることを確認する
    if not isinstance(semantic_ast, dict):
        # 想定外形式を拒否する
        raise ValueError(f"{source_name}のsemantic_astがobjectではありません")
    # 操作列を取得する
    sequence = semantic_ast.get("sequence")
    # 空でない配列であることを確認する
    if not isinstance(sequence, list) or not sequence:
        # 操作数を判断できない入力を拒否する
        raise ValueError(f"{source_name}のsemantic_ast.sequenceが不正です")
    # 操作列の長さを返す
    return len(sequence)


# この工程を担当する関数を定義する
def load_rule_instructions(
    # ルール生成指示JSONLのパスを受け取る
    path: Path,
# 元指示索引と意味AST別集計を返す
) -> tuple[dict[str, tuple[str, str]], dict[str, dict[str, Any]]]:
    """訓練用ルール生成指示を元指示IDと意味AST単位で集計する。"""

    # 元指示IDから意味AST情報を引く索引を作る
    source_index: dict[str, tuple[str, str]] = {}
    # 意味ASTごとの集計を作る
    specs: dict[str, dict[str, Any]] = {}
    # 入力JSONLをUTF-8で開く
    with path.open(encoding="utf-8") as handle:
        # 全ルール生成指示を処理する
        for record in read_jsonl(handle, str(path)):
            # 訓練用以外は今回の分布対象から外す
            if record.get("split") != "train":
                # 次のレコードへ進む
                continue
            # test_only辞書の混入を拒否する
            if record.get("dictionary") != "train":
                # 不正な辞書区分を通知する
                raise ValueError("訓練用ルール生成指示にdictionary=train以外が含まれます")
            # 元指示IDを取得する
            instruction_id = require_string(record, "instruction_id", str(path))
            # 意味AST IDを取得する
            spec_id = require_string(record, "spec_id", str(path))
            # 意味ASTを取得する
            semantic_ast = record.get("semantic_ast")
            # 比較用の正規化文字列を作る
            semantic_key = canonical_json(semantic_ast)
            # 操作数を取得する
            count = operation_count(semantic_ast, str(path))
            # 元指示IDの重複を拒否する
            if instruction_id in source_index:
                # 重複IDを示して停止する
                raise ValueError(f"ルール生成instruction_idが重複しています: {instruction_id}")
            # 元指示索引へ意味AST情報を保存する
            source_index[instruction_id] = (spec_id, semantic_key)
            # 初出の意味ASTへ集計枠を作る
            if spec_id not in specs:
                # 意味AST、操作数、各種件数を保存する
                specs[spec_id] = {
                    "spec_id": spec_id,
                    "semantic_ast": semantic_ast,
                    "semantic_key": semantic_key,
                    "operation_count": count,
                    "rule_instruction_count": 0,
                    "teacher_replacement_count": 0,
                    "teacher_failure_count": 0,
                    "code_count": 0,
                }
            # 同じspec_idが別の意味ASTを指していないことを確認する
            if specs[spec_id]["semantic_key"] != semantic_key:
                # 意味AST IDの衝突を拒否する
                raise ValueError(f"spec_idが複数の意味ASTを指しています: {spec_id}")
            # 同じspec_idで操作数が変わらないことを確認する
            if specs[spec_id]["operation_count"] != count:
                # 操作数の不整合を拒否する
                raise ValueError(f"spec_idの操作数が一致しません: {spec_id}")
            # この意味ASTのルール生成指示数を増やす
            specs[spec_id]["rule_instruction_count"] += 1
    # 一件も訓練指示がなければ停止する
    if not source_index:
        # 入力選択の誤りを通知する
        raise ValueError("訓練用ルール生成指示がありません")
    # 完成した索引と集計を返す
    return source_index, specs


# この工程を担当する関数を定義する
def load_approved_replacements(
    # 承認済み教師言い換えJSONLのパスを受け取る
    path: Path,
    # 元指示ID索引を受け取る
    source_index: dict[str, tuple[str, str]],
    # 意味AST別集計を受け取る
    specs: dict[str, dict[str, Any]],
# 置換された元指示ID集合を返す
) -> set[str]:
    """承認済み教師言い換えが一対一の置換として有効か検査する。"""

    # 置換済み元指示IDの集合を作る
    replaced_source_ids: set[str] = set()
    # 教師候補IDの重複検査用集合を作る
    teacher_instruction_ids: set[str] = set()
    # 承認済みJSONLをUTF-8で開く
    with path.open(encoding="utf-8") as handle:
        # 全承認済み言い換えを処理する
        for record in read_jsonl(handle, str(path)):
            # 承認済み以外を拒否する
            if record.get("review_status") != "approved":
                # 状態の不一致を通知する
                raise ValueError("承認済みJSONLにapproved以外が含まれます")
            # 全承認方式以外の混入を拒否する
            if record.get("approval_mode") != "blanket_all_candidates":
                # 承認方式の不一致を通知する
                raise ValueError("承認済みJSONLのapproval_modeが一致しません")
            # 教師指示IDを取得する
            instruction_id = require_string(record, "instruction_id", str(path))
            # 置換元指示IDを取得する
            source_id = require_string(record, "source_instruction_id", str(path))
            # 意味AST IDを取得する
            spec_id = require_string(record, "spec_id", str(path))
            # 意味ASTを正規化する
            semantic_key = canonical_json(record.get("semantic_ast"))
            # 教師指示IDの重複を拒否する
            if instruction_id in teacher_instruction_ids:
                # 重複IDを示して停止する
                raise ValueError(f"教師instruction_idが重複しています: {instruction_id}")
            # 同じ元指示を複数回置換する候補を拒否する
            if source_id in replaced_source_ids:
                # 一対一置換でない入力を通知する
                raise ValueError(f"source_instruction_idが重複しています: {source_id}")
            # 置換元が訓練用ルール生成指示に存在することを確認する
            if source_id not in source_index:
                # 評価用や未知の元指示を拒否する
                raise ValueError(f"置換元が訓練用ルール指示にありません: {source_id}")
            # 置換元の意味AST情報を取得する
            source_spec_id, source_semantic_key = source_index[source_id]
            # 教師候補と置換元のspec_idが一致することを確認する
            if spec_id != source_spec_id:
                # 意味AST IDの変更を拒否する
                raise ValueError(f"教師候補と置換元のspec_idが一致しません: {source_id}")
            # 教師候補と置換元の意味AST本体が一致することを確認する
            if semantic_key != source_semantic_key:
                # 意味ASTの変更を拒否する
                raise ValueError(f"教師候補と置換元のsemantic_astが一致しません: {source_id}")
            # 教師指示IDを登録する
            teacher_instruction_ids.add(instruction_id)
            # 置換元指示IDを登録する
            replaced_source_ids.add(source_id)
            # この意味ASTの教師置換成功数を増やす
            specs[spec_id]["teacher_replacement_count"] += 1
    # 置換された元指示ID集合を返す
    return replaced_source_ids


# この工程を担当する関数を定義する
def load_teacher_failures(
    # 教師生成集計JSONのパスを受け取る
    path: Path,
    # 元指示ID索引を受け取る
    source_index: dict[str, tuple[str, str]],
    # 置換成功元指示ID集合を受け取る
    replaced_source_ids: set[str],
    # 意味AST別集計を受け取る
    specs: dict[str, dict[str, Any]],
# 教師生成の全体件数を返す
) -> dict[str, int]:
    """教師生成で置換できなかった元指示を検査して集計する。"""

    # 集計JSONをUTF-8で開く
    with path.open(encoding="utf-8") as handle:
        # JSON objectを解析する
        stats = json.load(handle)
    # 集計JSONがobjectであることを確認する
    if not isinstance(stats, dict):
        # 想定外形式を拒否する
        raise ValueError("教師生成集計JSONがobjectではありません")
    # 必要な全体件数を整数として取得する
    selected_count = int(stats.get("selected_source_count", -1))
    # 候補成功数を整数として取得する
    candidate_count = int(stats.get("candidate_count", -1))
    # 失敗数を整数として取得する
    failure_count = int(stats.get("failure_count", -1))
    # 選抜対象意味AST数を整数として取得する
    selected_ast_count = int(stats.get("selected_source_ast_count", -1))
    # 意味AST当たり選抜数を整数として取得する
    selected_per_ast = int(stats.get("source_instructions_per_ast", -1))
    # 失敗一覧を取得する
    failures = stats.get("failures")
    # 失敗一覧が配列であることを確認する
    if not isinstance(failures, list):
        # 不正な集計形式を拒否する
        raise ValueError("教師生成集計のfailuresが配列ではありません")
    # 集計上の候補成功数と承認済み置換数を比較する
    if candidate_count != len(replaced_source_ids):
        # 入力世代の混在を拒否する
        raise ValueError("教師候補数と承認済み置換数が一致しません")
    # 選抜数が成功数と失敗数の和であることを確認する
    if selected_count != candidate_count + failure_count:
        # 集計内部の不整合を拒否する
        raise ValueError("教師選抜数が成功数と失敗数の和ではありません")
    # 失敗一覧の長さが集計値と一致することを確認する
    if len(failures) != failure_count:
        # 欠落した失敗情報を拒否する
        raise ValueError("教師失敗一覧の長さがfailure_countと一致しません")
    # 選抜対象意味ASTがルール生成側と一致することを確認する
    if selected_ast_count != len(specs):
        # 一部意味ASTだけの教師生成を拒否する
        raise ValueError("教師選抜対象意味AST数が訓練用意味AST数と一致しません")
    # 失敗元指示IDの重複検査用集合を作る
    failure_source_ids: set[str] = set()
    # 全失敗を処理する
    for failure in failures:
        # 各失敗がobjectであることを確認する
        if not isinstance(failure, dict):
            # 不正な失敗レコードを拒否する
            raise ValueError("教師生成失敗レコードがobjectではありません")
        # 失敗した元指示IDを取得する
        source_id = require_string(failure, "source_instruction_id", str(path))
        # 失敗IDの重複を拒否する
        if source_id in failure_source_ids:
            # 重複IDを示して停止する
            raise ValueError(f"教師失敗source_instruction_idが重複しています: {source_id}")
        # 失敗元が訓練用ルール生成指示に存在することを確認する
        if source_id not in source_index:
            # 未知の失敗元を拒否する
            raise ValueError(f"教師失敗元が訓練用ルール指示にありません: {source_id}")
        # 成功した置換と失敗が重なっていないことを確認する
        if source_id in replaced_source_ids:
            # 状態の二重計上を拒否する
            raise ValueError(f"教師成功と失敗に同じ元指示があります: {source_id}")
        # 失敗IDを登録する
        failure_source_ids.add(source_id)
        # 元指示の意味AST IDを取得する
        spec_id = source_index[source_id][0]
        # この意味ASTの教師失敗数を増やす
        specs[spec_id]["teacher_failure_count"] += 1
    # 全意味ASTの選抜件数が設定どおりか確認する
    for spec_id, spec in specs.items():
        # 成功置換数と失敗数を足す
        actual_selected = spec["teacher_replacement_count"] + spec["teacher_failure_count"]
        # 各意味ASTで同じ件数を選抜したことを確認する
        if actual_selected != selected_per_ast:
            # 不足または過剰な意味ASTを示して停止する
            raise ValueError(f"教師選抜数が意味AST当たり設定と一致しません: {spec_id}")
    # 報告に必要な全体件数を返す
    return {
        "selected_source_count": selected_count,
        "candidate_count": candidate_count,
        "failure_count": failure_count,
        "selected_source_ast_count": selected_ast_count,
        "source_instructions_per_ast": selected_per_ast,
    }


# この工程を担当する関数を定義する
def register_code(
    # コードレコードを受け取る
    record: dict[str, Any],
    # 入力元の表示名を受け取る
    source_name: str,
    # 意味AST別集計を受け取る
    specs: dict[str, dict[str, Any]],
    # コードID重複検査用集合を受け取る
    code_ids: set[str],
) -> None:
    """検証済み訓練コードを対応する意味ASTへ一件登録する。"""

    # 訓練用コード以外を拒否する
    if record.get("split") != "train":
        # ZIPメンバーや単一操作入力の取り違えを通知する
        raise ValueError(f"訓練用以外のコードが含まれます: {source_name}")
    # 検証がすべて成功していることを確認する
    verification = record.get("verification")
    # 検証情報がobjectであることを確認する
    if not isinstance(verification, dict) or verification.get("tests_passed") is not True:
        # 未検証または失敗コードを拒否する
        raise ValueError(f"検証成功でないコードが含まれます: {source_name}")
    # コードIDを取得する
    code_id = require_string(record, "code_id", source_name)
    # 意味AST IDを取得する
    spec_id = require_string(record, "spec_id", source_name)
    # 意味ASTを正規化する
    semantic_key = canonical_json(record.get("semantic_ast"))
    # コードIDの重複を拒否する
    if code_id in code_ids:
        # 重複IDを示して停止する
        raise ValueError(f"code_idが重複しています: {code_id}")
    # コード側にしかない意味ASTを拒否する
    if spec_id not in specs:
        # 指示と結合できないコードを通知する
        raise ValueError(f"コードのspec_idが訓練指示にありません: {spec_id}")
    # 指示側とコード側の意味AST本体が一致することを確認する
    if semantic_key != specs[spec_id]["semantic_key"]:
        # spec_idだけが一致する不正な結合を防ぐ
        raise ValueError(f"コードと指示のsemantic_astが一致しません: {spec_id}")
    # コードIDを登録する
    code_ids.add(code_id)
    # この意味ASTのコード数を増やす
    specs[spec_id]["code_count"] += 1


# この工程を担当する関数を定義する
def load_codes(
    # 単一操作コードJSONLを受け取る
    single_path: Path,
    # 複数操作コードZIPを受け取る
    multi_archive: Path,
    # 意味AST別集計を受け取る
    specs: dict[str, dict[str, Any]],
) -> int:
    """単一・2・3操作の訓練コードを意味AST別に集計する。"""

    # 全入力を通したコードID重複検査用集合を作る
    code_ids: set[str] = set()
    # 単一操作コードJSONLをUTF-8で開く
    with single_path.open(encoding="utf-8") as handle:
        # 全単一操作コードを処理する
        for record in read_jsonl(handle, str(single_path)):
            # 検証して意味ASTへ登録する
            register_code(record, str(single_path), specs, code_ids)
    # 複数操作コードZIPを開く
    with zipfile.ZipFile(multi_archive) as archive:
        # 訓練用2・3操作メンバーを順番に処理する
        for member in TRAIN_CODE_MEMBERS:
            # 必須メンバーの存在を確認する
            if member not in archive.namelist():
                # 不足メンバーを示して停止する
                raise ValueError(f"コードZIPに必要なメンバーがありません: {member}")
            # ZIP内JSONLをバイナリで開く
            with archive.open(member) as binary_handle:
                # UTF-8テキストとして読み取れるラッパーを作る
                with io.TextIOWrapper(binary_handle, encoding="utf-8") as text_handle:
                    # 全コードを処理する
                    for record in read_jsonl(text_handle, f"{multi_archive}:{member}"):
                        # 検証して意味ASTへ登録する
                        register_code(record, member, specs, code_ids)
    # 登録したコード総数を返す
    return len(code_ids)


# この工程を担当する関数を定義する
def histogram(values: Iterable[int]) -> dict[str, int]:
    """整数列をJSONへ保存しやすい昇順ヒストグラムにする。"""

    # 件数別の出現数を集計する
    counts = Counter(values)
    # 数値順で文字列キーへ変換して返す
    return {str(value): counts[value] for value in sorted(counts)}


# この工程を担当する関数を定義する
def build_summary(
    # 意味AST別集計を受け取る
    specs: dict[str, dict[str, Any]],
    # 教師生成全体件数を受け取る
    teacher_stats: dict[str, int],
    # コード総数を受け取る
    code_count: int,
    # レポート日を受け取る
    report_date: str,
) -> dict[str, Any]:
    """置換後件数と結合前差分を検証して集計する。"""

    # 操作数別集計を作る
    by_operation_count: dict[str, dict[str, int]] = {}
    # 20件未満の意味AST一覧を作る
    under_twenty: list[dict[str, Any]] = []
    # 全意味ASTをID順に処理する
    for spec_id in sorted(specs):
        # この意味ASTの集計を取得する
        spec = specs[spec_id]
        # 置換後も指示総数は元のルール生成数と同じにする
        final_count = spec["rule_instruction_count"]
        # 教師置換されずルール生成のまま残る件数を計算する
        retained_rule_count = final_count - spec["teacher_replacement_count"]
        # 負数は追加扱いや重複置換を意味するため拒否する
        if retained_rule_count < 0:
            # 不正な意味ASTを示して停止する
            raise ValueError(f"教師置換数が元指示数を超えています: {spec_id}")
        # 各意味ASTのコードが20件であることを確認する
        if spec["code_count"] != 20:
            # コード生成の不足または過剰を通知する
            raise ValueError(f"コード数が20件ではありません: {spec_id}")
        # 計算結果を意味AST集計へ追加する
        spec["retained_rule_count"] = retained_rule_count
        # 置換後指示数を保存する
        spec["final_instruction_count"] = final_count
        # コードとの差を保存する
        spec["instruction_minus_code"] = final_count - spec["code_count"]
        # 操作数を文字列キーにする
        operation_key = str(spec["operation_count"])
        # 初出の操作数へ集計枠を作る
        if operation_key not in by_operation_count:
            # 各合計をゼロで初期化する
            by_operation_count[operation_key] = {
                "semantic_ast_count": 0,
                "rule_instruction_count": 0,
                "teacher_replacement_count": 0,
                "teacher_failure_count": 0,
                "retained_rule_count": 0,
                "final_instruction_count": 0,
                "code_count": 0,
                "instruction_minus_code": 0,
            }
        # 操作数別集計を取得する
        operation_summary = by_operation_count[operation_key]
        # 意味AST数を増やす
        operation_summary["semantic_ast_count"] += 1
        # 数値項目を操作数別に足し上げる
        for key in (
            "rule_instruction_count",
            "teacher_replacement_count",
            "teacher_failure_count",
            "retained_rule_count",
            "final_instruction_count",
            "code_count",
            "instruction_minus_code",
        ):
            # この意味ASTの値を加算する
            operation_summary[key] += int(spec[key])
        # 20件未満の意味ASTを詳細一覧へ追加する
        if final_count < 20:
            # 操作列を取得する
            sequence = spec["semantic_ast"]["sequence"]
            # 一覧用レコードを追加する
            under_twenty.append(
                {
                    "spec_id": spec_id,
                    "operation_count": spec["operation_count"],
                    "operation": canonical_json(sequence[0]) if len(sequence) == 1 else canonical_json(sequence),
                    "final_instruction_count": final_count,
                    "teacher_replacement_count": spec["teacher_replacement_count"],
                    "retained_rule_count": retained_rule_count,
                    "code_count": spec["code_count"],
                    "instruction_shortfall": spec["code_count"] - final_count,
                }
            )
    # 全体のルール生成指示数を計算する
    total_rule = sum(spec["rule_instruction_count"] for spec in specs.values())
    # 全体の教師置換成功数を計算する
    total_teacher = sum(spec["teacher_replacement_count"] for spec in specs.values())
    # 全体の元文維持数を計算する
    total_retained = sum(spec["retained_rule_count"] for spec in specs.values())
    # 全体の置換後指示数を計算する
    total_final = sum(spec["final_instruction_count"] for spec in specs.values())
    # 置換で総数が変わっていないことを確認する
    if total_final != total_rule or total_teacher + total_retained != total_final:
        # 追加扱いまたは欠落を拒否する
        raise ValueError("教師言い換えが一対一置換として集計されていません")
    # コード引数と意味AST別合計が一致することを確認する
    if code_count != sum(spec["code_count"] for spec in specs.values()):
        # コード集計の不整合を拒否する
        raise ValueError("コード総数と意味AST別コード数の合計が一致しません")
    # 機械可読な集計を組み立てる
    return {
        "report_date": report_date,
        "scope": "train",
        "replacement_policy": "replace_source_instruction_one_to_one",
        "semantic_ast_count": len(specs),
        "rule_instruction_count_before_replacement": total_rule,
        "teacher_selected_source_count": teacher_stats["selected_source_count"],
        "teacher_replacement_count": total_teacher,
        "teacher_failure_count": teacher_stats["failure_count"],
        "retained_rule_instruction_count": total_retained,
        "final_instruction_count_after_replacement": total_final,
        "verified_code_count": code_count,
        "instruction_minus_code": total_final - code_count,
        "distribution": {
            "final_instructions_per_ast": histogram(
                spec["final_instruction_count"] for spec in specs.values()
            ),
            "teacher_replacements_per_ast": histogram(
                spec["teacher_replacement_count"] for spec in specs.values()
            ),
            "teacher_failures_per_ast": histogram(
                spec["teacher_failure_count"] for spec in specs.values()
            ),
            "codes_per_ast": histogram(spec["code_count"] for spec in specs.values()),
        },
        "by_operation_count": by_operation_count,
        "under_twenty_instruction_asts": under_twenty,
    }


# この工程を担当する関数を定義する
def markdown_histogram_rows(distribution: dict[str, int]) -> list[str]:
    """件数ヒストグラムをMarkdown表の行へ変換する。"""

    # 件数を数値順に並べて表の行を作る
    return [
        # 一件数ごとの意味AST数を表示する
        f"| {count} | {distribution[count]:,} |"
        # 文字列キーを整数として並べ替える
        for count in sorted(distribution, key=int)
    ]


# この工程を担当する関数を定義する
def render_markdown(summary: dict[str, Any]) -> str:
    """集計を人が確認できるMarkdownへ変換する。"""

    # 操作数別表の行を作る
    operation_rows: list[str] = []
    # 1操作から順に処理する
    for operation_count_key in sorted(summary["by_operation_count"], key=int):
        # 対象操作数の集計を取得する
        item = summary["by_operation_count"][operation_count_key]
        # 操作数別の一行を追加する
        operation_rows.append(
            # 意味AST、置換前、置換、維持、置換後、コード、差を表示する
            f"| {operation_count_key}操作 | {item['semantic_ast_count']:,} | "
            f"{item['rule_instruction_count']:,} | {item['teacher_replacement_count']:,} | "
            f"{item['retained_rule_count']:,} | {item['final_instruction_count']:,} | "
            f"{item['code_count']:,} | {item['instruction_minus_code']:,} |"
        )
    # 20件未満一覧の行を作る
    under_twenty_rows: list[str] = []
    # 意味AST ID順に処理する
    for item in summary["under_twenty_instruction_asts"]:
        # 不足意味ASTの一行を追加する
        under_twenty_rows.append(
            # ID、操作、置換内訳、コード、不足を表示する
            f"| `{item['spec_id']}` | `{item['operation']}` | "
            f"{item['final_instruction_count']} | {item['teacher_replacement_count']} | "
            f"{item['retained_rule_count']} | {item['code_count']} | "
            f"{item['instruction_shortfall']} |"
        )
    # 置換成功数分布の表を作る
    replacement_rows = markdown_histogram_rows(
        # 教師置換成功数のヒストグラムを渡す
        summary["distribution"]["teacher_replacements_per_ast"]
    )
    # 置換後指示数分布の表を作る
    final_rows = markdown_histogram_rows(
        # 最終指示数のヒストグラムを渡す
        summary["distribution"]["final_instructions_per_ast"]
    )
    # Markdown本文を行単位で組み立てる
    lines = [
        # レポート見出しを追加する
        "# 訓練用日本語指示とコードの結合前分布",
        # 見出し後の空行を追加する
        "",
        # 基準日と対象を説明する
        f"基準日: {summary['report_date']}。対象は`split=train`の意味ASTだけである。",
        # 段落間の空行を追加する
        "",
        # 件数の由来の節を追加する
        "## 1. 192,900件になる理由",
        # 見出し後の空行を追加する
        "",
        # 計算式の説明を追加する
        "訓練用意味ASTは9,646件ある。2操作・3操作では各意味ASTにつき20件、単一操作では固有全文だけを最大20件作成した。内訳は次のとおりである。",
        # 段落間の空行を追加する
        "",
        # 計算式をコードブロックで開始する
        "```text",
        # 単一操作の件数を示す
        "単一操作:       24 AST →     460指示",
        # 2操作の計算を示す
        "2操作:         434 AST × 20 =   8,680指示",
        # 3操作の計算を示す
        "3操作:       9,188 AST × 20 = 183,760指示",
        # 合計を示す
        "合計:        9,646 AST       = 192,900指示",
        # 計算式をコードブロックで閉じる
        "```",
        # 段落間の空行を追加する
        "",
        # 置換方針の節を追加する
        "## 2. 教師言い換えは追加ではなく置換",
        # 見出し後の空行を追加する
        "",
        # 置換成功数を説明する
        f"教師生成では{summary['teacher_selected_source_count']:,}件の元指示を選び、{summary['teacher_replacement_count']:,}件で元文と異なる承認済み言い換えを得た。これらは`source_instruction_id`が指す元指示と一対一で置換する。",
        # 段落間の空行を追加する
        "",
        # 失敗時の扱いを説明する
        f"言い換えを得られなかった{summary['teacher_failure_count']:,}件は元のルール生成指示を維持する。このため置換後の指示総数は{summary['final_instruction_count_after_replacement']:,}件のままであり、教師言い換えを加算した件数にはしない。",
        # 段落間の空行を追加する
        "",
        # 全体内訳表のヘッダーを追加する
        "| 置換後の指示種別 | 件数 |",
        # 区切り行を追加する
        "|---|---:|",
        # 教師言い換え数を追加する
        f"| 教師言い換えへ置換 | {summary['teacher_replacement_count']:,} |",
        # 元文維持数を追加する
        f"| ルール生成指示のまま維持 | {summary['retained_rule_instruction_count']:,} |",
        # 合計を追加する
        f"| 置換後合計 | {summary['final_instruction_count_after_replacement']:,} |",
        # 段落間の空行を追加する
        "",
        # 操作数別分布の節を追加する
        "## 3. 操作数別の結合前分布",
        # 見出し後の空行を追加する
        "",
        # 操作数別表のヘッダーを追加する
        "| 操作数 | 意味AST | 置換前指示 | 教師置換 | 元文維持 | 置換後指示 | コード | 指示−コード |",
        # 区切り行を追加する
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        # 集計済み行を展開する
        *operation_rows,
        # 段落間の空行を追加する
        "",
        # 指示数分布の節を追加する
        "## 4. 1意味AST当たりの置換後指示数",
        # 見出し後の空行を追加する
        "",
        # 分布表のヘッダーを追加する
        "| 置換後指示数 | 意味AST数 |",
        # 区切り行を追加する
        "|---:|---:|",
        # 集計済み分布行を展開する
        *final_rows,
        # 段落間の空行を追加する
        "",
        # 不足一覧の節を追加する
        "## 5. 20件未満の意味AST",
        # 見出し後の空行を追加する
        "",
        # 不足一覧の説明を追加する
        "20件未満なのは単一操作の6意味ASTだけである。終止形が同じ全文を別IDとして水増ししなかった結果であり、教師置換後も件数は増減しない。",
        # 段落間の空行を追加する
        "",
        # 不足一覧表のヘッダーを追加する
        "| spec_id | 操作 | 置換後指示 | 教師置換 | 元文維持 | コード | 不足 |",
        # 区切り行を追加する
        "|---|---|---:|---:|---:|---:|---:|",
        # 不足意味AST行を展開する
        *under_twenty_rows,
        # 段落間の空行を追加する
        "",
        # 教師置換分布の節を追加する
        "## 6. 1意味AST当たりの教師置換成功数",
        # 見出し後の空行を追加する
        "",
        # 選抜方針を説明する
        "各意味ASTから10件を教師言い換え対象に選んだ。元文と同一になった70件は置換せず、元文を維持するため、成功置換数には意味ASTごとの差がある。",
        # 段落間の空行を追加する
        "",
        # 置換分布表のヘッダーを追加する
        "| 教師置換成功数 | 意味AST数 |",
        # 区切り行を追加する
        "|---:|---:|",
        # 置換成功分布行を展開する
        *replacement_rows,
        # 段落間の空行を追加する
        "",
        # 結論の節を追加する
        "## 7. 結合方針への結論",
        # 見出し後の空行を追加する
        "",
        # コード総数との差を説明する
        f"検証済み訓練コードは{summary['verified_code_count']:,}件で、全9,646意味ASTに20件ずつある。置換後指示は{summary['final_instruction_count_after_replacement']:,}件なので、指示が20件少ない。差はすべて単一操作6意味ASTにある。",
        # 段落間の空行を追加する
        "",
        # 次の実装方針を説明する
        "最終結合では全直積を作らない。同じ`spec_id`かつ同じ意味ASTの内部で、置換後指示とコードを決定的に一対一対応させる。20件の余剰コードは、追加の固有日本語指示を作らない限り最終訓練レコードへ採用しない。",
        # 最終改行を作るため空行を追加する
        "",
    ]
    # 改行で連結したMarkdownを返す
    return "\n".join(lines)


# この工程を担当する関数を定義する
def write_outputs(
    # 集計objectを受け取る
    summary: dict[str, Any],
    # 集計JSONの保存先を受け取る
    output_json: Path,
    # Markdownの保存先を受け取る
    output_md: Path,
    # 上書き可否を受け取る
    overwrite: bool,
) -> None:
    """検証済み集計をJSONとMarkdownへ保存する。"""

    # 作成対象をまとめる
    outputs = (output_json, output_md)
    # 既存出力を抽出する
    existing = [str(path) for path in outputs if path.exists()]
    # 明示的な上書き指定なしでは既存成果物を保護する
    if existing and not overwrite:
        # 置換対象と必要なフラグを通知する
        raise ValueError("既存出力があります。--overwriteを指定してください: " + ", ".join(existing))
    # JSON保存先ディレクトリを作る
    output_json.parent.mkdir(parents=True, exist_ok=True)
    # Markdown保存先ディレクトリを作る
    output_md.parent.mkdir(parents=True, exist_ok=True)
    # 集計JSONを読みやすい形式で保存する
    output_json.write_text(
        # 非ASCII文字を保持し、キー順を固定したJSONへ変換する
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        # UTF-8で保存する
        encoding="utf-8",
    )
    # Markdownレポートを保存する
    output_md.write_text(render_markdown(summary), encoding="utf-8")


# この工程を担当する関数を定義する
def main() -> None:
    """入力を突き合わせて結合前分布レポートを作成する。"""

    # コマンドライン引数を取得する
    args = parse_args()
    # 訓練用ルール生成指示を集計する
    source_index, specs = load_rule_instructions(args.rule_instructions.resolve())
    # 承認済み教師言い換えを一対一置換として検査する
    replaced_source_ids = load_approved_replacements(
        # 承認済みJSONLの絶対パスを渡す
        args.approved_paraphrases.resolve(),
        # 元指示索引を渡す
        source_index,
        # 意味AST別集計を渡す
        specs,
    )
    # 教師生成失敗を検査して元文維持数へ反映する
    teacher_stats = load_teacher_failures(
        # 教師生成集計JSONの絶対パスを渡す
        args.paraphrase_generation_stats.resolve(),
        # 元指示索引を渡す
        source_index,
        # 置換成功元指示ID集合を渡す
        replaced_source_ids,
        # 意味AST別集計を渡す
        specs,
    )
    # 検証済み訓練コードを集計する
    code_count = load_codes(
        # 単一操作コードJSONLの絶対パスを渡す
        args.single_operation_codes.resolve(),
        # 複数操作コードZIPの絶対パスを渡す
        args.multi_operation_code_archive.resolve(),
        # 意味AST別集計を渡す
        specs,
    )
    # 置換後指示とコードの分布を作る
    summary = build_summary(specs, teacher_stats, code_count, args.report_date)
    # 集計JSONとMarkdownを保存する
    write_outputs(
        # 検証済み集計を渡す
        summary,
        # 集計JSONの絶対パスを渡す
        args.output_json.resolve(),
        # Markdownの絶対パスを渡す
        args.output_md.resolve(),
        # 上書き可否を渡す
        args.overwrite,
    )
    # 作成結果の要点を表示する
    print(
        # 意味AST数、最終指示数、コード数、差を表示する
        f"結合前分布を作成しました: ast={summary['semantic_ast_count']}, "
        f"instructions={summary['final_instruction_count_after_replacement']}, "
        f"codes={summary['verified_code_count']}, "
        f"difference={summary['instruction_minus_code']}"
    )


# 直接実行された場合だけmain関数を呼ぶ
if __name__ == "__main__":
    # レポート作成処理を開始する
    main()
