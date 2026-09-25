"""ルール生成訓練指示へ承認済み教師言い換えを一対一で置換反映する。"""

# 将来のPythonでも現在の型注釈をそのまま評価できるようにする
from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse
# 件数分布を集計するために使う
from collections import Counter
# ファイルのSHA-256を計算するために使う
import hashlib
# JSONとJSONLを読み書きするために使う
import json
# 一時ファイルを完成ファイルへ安全に置き換えるために使う
import os
# 入出力パスを扱うために使う
from pathlib import Path
# 任意のJSON値を型注釈で表すために使う
from typing import Any, Iterable, TextIO
# 置換済みJSONLを決定的なZIPへ格納するために使う
import zipfile


# ZIP内メンバーの固定日時を定義する
ZIP_TIMESTAMP = (2026, 9, 25, 0, 0, 0)
# ZIP内で使う固定ファイル名を定義する
ARCHIVE_MEMBER = "replacement_resolved_train_instructions.jsonl"


# この工程を担当する関数を定義する
def parse_args() -> argparse.Namespace:
    """置換反映と検証に必要な入出力を受け取る。"""

    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        # 処理内容をコマンドのヘルプへ表示する
        description="教師言い換えを追加せず元指示へ一対一で置換反映します。"
    )
    # 全splitを含む元のルール生成指示JSONLを受け取る
    parser.add_argument("--rule-instructions", required=True, type=Path)
    # 全承認済み教師言い換えJSONLを受け取る
    parser.add_argument("--approved-paraphrases", required=True, type=Path)
    # 教師生成失敗IDを持つ集計JSONを受け取る
    parser.add_argument("--paraphrase-generation-stats", required=True, type=Path)
    # 置換反映済み訓練指示JSONLの保存先を受け取る
    parser.add_argument("--output-jsonl", required=True, type=Path)
    # Git管理用ZIPの保存先を受け取る
    parser.add_argument("--archive", required=True, type=Path)
    # 件数とハッシュを保存する集計JSONのパスを受け取る
    parser.add_argument("--stats", required=True, type=Path)
    # 置換後に必要な訓練指示総数を受け取る
    parser.add_argument("--expected-output-count", required=True, type=int)
    # 置換する承認済み教師指示数を受け取る
    parser.add_argument("--expected-replacement-count", required=True, type=int)
    # 既存成果物を意図的に置き換える場合だけ使う
    parser.add_argument("--overwrite", action="store_true")
    # 解析済み引数を返す
    return parser.parse_args()


# この工程を担当する関数を定義する
def canonical_json(value: Any) -> str:
    """JSON値を比較できる決定的文字列へ変換する。"""

    # キー順と空白を固定して返す
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# この工程を担当する関数を定義する
def text_sha256(value: str) -> str:
    """文字列のUTF-8バイト列に対するSHA-256を返す。"""

    # UTF-8へ変換してハッシュを計算する
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# この工程を担当する関数を定義する
def file_sha256(path: Path) -> str:
    """大きなファイルを分割してSHA-256を計算する。"""

    # SHA-256計算器を作る
    digest = hashlib.sha256()
    # 対象ファイルをバイナリで開く
    with path.open("rb") as handle:
        # ファイル末尾まで1 MiBずつ読み込む
        while chunk := handle.read(1024 * 1024):
            # 現在のバイト列をハッシュ計算へ追加する
            digest.update(chunk)
    # 16進小文字のSHA-256を返す
    return digest.hexdigest()


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
def operation_count(record: dict[str, Any], source_name: str) -> int:
    """レコードの意味ASTから操作数を取得する。"""

    # 意味ASTを取得する
    semantic_ast = record.get("semantic_ast")
    # 意味ASTがobjectであることを確認する
    if not isinstance(semantic_ast, dict):
        # 想定外形式を拒否する
        raise ValueError(f"{source_name}のsemantic_astがobjectではありません")
    # 操作列を取得する
    sequence = semantic_ast.get("sequence")
    # 1〜3操作の配列であることを確認する
    if not isinstance(sequence, list) or not 1 <= len(sequence) <= 3:
        # 操作数を判断できない入力を拒否する
        raise ValueError(f"{source_name}のsemantic_ast.sequenceが不正です")
    # 操作列の長さを返す
    return len(sequence)


# この工程を担当する関数を定義する
def load_approved_paraphrases(
    # 承認済みJSONLのパスを受け取る
    path: Path,
    # 期待する承認済み件数を受け取る
    expected_count: int,
) -> dict[str, dict[str, Any]]:
    """承認済み教師言い換えを置換元指示IDで索引化する。"""

    # 置換元指示IDから教師レコードを引く索引を作る
    approved_by_source: dict[str, dict[str, Any]] = {}
    # 教師指示IDの重複検査用集合を作る
    teacher_instruction_ids: set[str] = set()
    # 承認済みJSONLをUTF-8で開く
    with path.open(encoding="utf-8") as handle:
        # 全承認済み教師言い換えを処理する
        for record in read_jsonl(handle, str(path)):
            # 教師指示IDを取得する
            instruction_id = require_string(record, "instruction_id", str(path))
            # 置換元指示IDを取得する
            source_id = require_string(record, "source_instruction_id", str(path))
            # 教師生成区分を確認する
            if record.get("instruction_source") != "teacher":
                # 別生成元の混入を拒否する
                raise ValueError(f"教師指示ではありません: {instruction_id}")
            # 承認状態を確認する
            if record.get("review_status") != "approved":
                # 未承認候補の混入を拒否する
                raise ValueError(f"承認済みではありません: {instruction_id}")
            # 一括承認方式を確認する
            if record.get("approval_mode") != "blanket_all_candidates":
                # 想定外の承認方式を拒否する
                raise ValueError(f"承認方式が一致しません: {instruction_id}")
            # 訓練辞書だけを許可する
            if record.get("dictionary") != "train":
                # test_only表現の混入を拒否する
                raise ValueError(f"dictionary=trainではありません: {instruction_id}")
            # 教師モデル名を必須にする
            require_string(record, "teacher_model", str(path))
            # 教師モデルrevisionを必須にする
            require_string(record, "teacher_revision", str(path))
            # 実際のpromptハッシュを必須にする
            require_string(record, "prompt_hash", str(path))
            # 言い換え本文を取得する
            instruction_ja = require_string(record, "instruction_ja", str(path))
            # 元文を取得する
            source_instruction_ja = require_string(record, "source_instruction_ja", str(path))
            # 元文と同じ候補を拒否する
            if instruction_ja == source_instruction_ja:
                # 言い換えになっていない候補を通知する
                raise ValueError(f"教師指示が元文と同一です: {instruction_id}")
            # 本文ハッシュを再計算して確認する
            if record.get("text_hash") != text_sha256(instruction_ja):
                # 本文とハッシュの不一致を拒否する
                raise ValueError(f"教師指示のtext_hashが一致しません: {instruction_id}")
            # 教師指示IDの重複を拒否する
            if instruction_id in teacher_instruction_ids:
                # 重複IDを示して停止する
                raise ValueError(f"教師instruction_idが重複しています: {instruction_id}")
            # 同じ元指示への複数置換を拒否する
            if source_id in approved_by_source:
                # 一対一置換でない入力を通知する
                raise ValueError(f"source_instruction_idが重複しています: {source_id}")
            # 教師指示IDを登録する
            teacher_instruction_ids.add(instruction_id)
            # 置換元指示IDで教師レコードを保存する
            approved_by_source[source_id] = record
    # 実件数と期待件数を比較する
    if len(approved_by_source) != expected_count:
        # 不完全または過剰な置換を拒否する
        raise ValueError(
            f"承認済み教師指示数が期待値と一致しません: "
            f"{len(approved_by_source)} != {expected_count}"
        )
    # 検証済み索引を返す
    return approved_by_source


# この工程を担当する関数を定義する
def load_teacher_failures(
    # 教師生成集計JSONのパスを受け取る
    path: Path,
    # 承認済み置換元ID集合を受け取る
    approved_source_ids: set[str],
) -> tuple[set[str], dict[str, int]]:
    """言い換えを取得できず元文を維持するIDを読み込む。"""

    # 集計JSONをUTF-8で開く
    with path.open(encoding="utf-8") as handle:
        # JSON objectを解析する
        stats = json.load(handle)
    # 集計JSONがobjectであることを確認する
    if not isinstance(stats, dict):
        # 想定外形式を拒否する
        raise ValueError("教師生成集計JSONがobjectではありません")
    # 選抜数を取得する
    selected_count = int(stats.get("selected_source_count", -1))
    # 候補成功数を取得する
    candidate_count = int(stats.get("candidate_count", -1))
    # 失敗数を取得する
    failure_count = int(stats.get("failure_count", -1))
    # 失敗一覧を取得する
    failures = stats.get("failures")
    # 失敗一覧が配列であることを確認する
    if not isinstance(failures, list):
        # 不正な集計形式を拒否する
        raise ValueError("教師生成集計のfailuresが配列ではありません")
    # 候補成功数と承認済み置換数を比較する
    if candidate_count != len(approved_source_ids):
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
    # 失敗元指示IDを保存する集合を作る
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
        # 成功した置換と失敗が重なっていないことを確認する
        if source_id in approved_source_ids:
            # 状態の二重計上を拒否する
            raise ValueError(f"教師成功と失敗に同じ元指示があります: {source_id}")
        # 失敗IDを登録する
        failure_source_ids.add(source_id)
    # 件数と一緒に返す
    return failure_source_ids, {
        "selected_source_count": selected_count,
        "candidate_count": candidate_count,
        "failure_count": failure_count,
    }


# この工程を担当する関数を定義する
def validate_source_and_teacher(
    # 元のルール生成指示を受け取る
    source: dict[str, Any],
    # 承認済み教師言い換えを受け取る
    teacher: dict[str, Any],
    # 元指示IDを受け取る
    source_id: str,
) -> None:
    """一対一置換で変えてはいけない情報が一致することを確認する。"""

    # spec_idが一致することを確認する
    if teacher.get("spec_id") != source.get("spec_id"):
        # 別意味ASTへの誤置換を拒否する
        raise ValueError(f"教師候補と元指示のspec_idが一致しません: {source_id}")
    # 意味AST本体が一致することを確認する
    if canonical_json(teacher.get("semantic_ast")) != canonical_json(source.get("semantic_ast")):
        # spec_idだけが同じ不正な置換を拒否する
        raise ValueError(f"教師候補と元指示のsemantic_astが一致しません: {source_id}")
    # 辞書区分が一致することを確認する
    if teacher.get("dictionary") != source.get("dictionary"):
        # test_only混入を拒否する
        raise ValueError(f"教師候補と元指示のdictionaryが一致しません: {source_id}")
    # 教師側に保存された元文が実際の元文と一致することを確認する
    if teacher.get("source_instruction_ja") != source.get("instruction_ja"):
        # 別の元文から作られた候補を拒否する
        raise ValueError(f"教師候補のsource_instruction_jaが一致しません: {source_id}")


# この工程を担当する関数を定義する
def make_teacher_replaced_record(
    # 元のルール生成指示を受け取る
    source: dict[str, Any],
    # 承認済み教師言い換えを受け取る
    teacher: dict[str, Any],
) -> dict[str, Any]:
    """元指示と教師来歴を両方保持した置換済みレコードを作る。"""

    # 元のルール生成指示の全項目を複製する
    resolved = dict(source)
    # 承認済み教師言い換えの全項目を重ねる
    resolved.update(teacher)
    # 元指示本文のハッシュを別項目として保存する
    resolved["source_text_hash"] = source["text_hash"]
    # 一対一置換されたレコードであることを保存する
    resolved["replacement_status"] = "teacher_replaced"
    # 追加ではなく置換する方式を保存する
    resolved["replacement_mode"] = "replace_source_instruction_one_to_one"
    # 元のルール生成指示IDが保持されていることを確認する
    if resolved.get("source_instruction_id") != source.get("instruction_id"):
        # 来歴を失う置換を拒否する
        raise ValueError("置換済みレコードのsource_instruction_idが元指示を指していません")
    # 完成した置換済みレコードを返す
    return resolved


# この工程を担当する関数を定義する
def make_retained_rule_record(
    # 元のルール生成指示を受け取る
    source: dict[str, Any],
    # 元文を維持する理由を受け取る
    reason: str,
) -> dict[str, Any]:
    """ルール生成指示を本文変更なしで維持したレコードを作る。"""

    # 元の全項目を複製する
    resolved = dict(source)
    # 教師置換していない状態を保存する
    resolved["replacement_status"] = "rule_retained"
    # 元文維持理由を保存する
    resolved["retention_reason"] = reason
    # 教師置換用の元IDは存在しないためnullを保存する
    resolved["source_instruction_id"] = None
    # 教師置換用の元文は存在しないためnullを保存する
    resolved["source_instruction_ja"] = None
    # 教師置換用の元文ハッシュは存在しないためnullを保存する
    resolved["source_text_hash"] = None
    # 置換しなかったことを表す方式を保存する
    resolved["replacement_mode"] = "retain_rule_instruction"
    # 元文が変更されていないことを確認する
    if resolved["instruction_ja"] != source["instruction_ja"]:
        # 意図しない本文変更を拒否する
        raise ValueError("維持対象のルール生成指示本文が変更されました")
    # 完成した元文維持レコードを返す
    return resolved


# この工程を担当する関数を定義する
def write_deterministic_zip(source: Path, archive: Path) -> None:
    """固定メタデータと圧縮設定で置換済みJSONLをZIPへ格納する。"""

    # ZIP内ファイルの固定メタデータを作る
    info = zipfile.ZipInfo(ARCHIVE_MEMBER, date_time=ZIP_TIMESTAMP)
    # Unix上の通常ファイル権限644を固定する
    info.external_attr = 0o100644 << 16
    # deflate圧縮を指定する
    info.compress_type = zipfile.ZIP_DEFLATED
    # UTF-8ファイル名フラグを有効にする
    info.flag_bits |= 0x800
    # 未完成ZIPを最終成果物と区別する一時パスを作る
    temporary_archive = archive.with_name(archive.name + ".tmp")
    # 中断時に一時ZIPを片付けられる範囲で作成する
    try:
        # 固定圧縮レベルで新しいZIPを作る
        with zipfile.ZipFile(
            temporary_archive,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as zip_handle:
            # 置換済みJSONLをバイナリで開く
            with source.open("rb") as source_handle:
                # ZIP内メンバーを書き込み用に開く
                with zip_handle.open(info, "w", force_zip64=True) as member_handle:
                    # 大きなJSONLを1 MiBずつ読み込む
                    while chunk := source_handle.read(1024 * 1024):
                        # 読み込んだバイト列を変更せずZIPへ書く
                        member_handle.write(chunk)
        # 完成した一時ZIPを最終パスへ原子的に置き換える
        os.replace(temporary_archive, archive)
    # 成否にかかわらず未完成一時ZIPだけを削除する
    finally:
        # 一時ZIPが残っている場合だけ削除する
        temporary_archive.unlink(missing_ok=True)


# この工程を担当する関数を定義する
def build_replacement_resolved_instructions(
    # すべての引数を名前付きで受け取る
    *,
    # 元のルール生成指示JSONLを受け取る
    rule_instructions: Path,
    # 承認済み教師言い換えJSONLを受け取る
    approved_paraphrases: Path,
    # 教師生成集計JSONを受け取る
    paraphrase_generation_stats: Path,
    # 置換反映済みJSONLの保存先を受け取る
    output_jsonl: Path,
    # Git管理用ZIPの保存先を受け取る
    archive: Path,
    # 集計JSONの保存先を受け取る
    stats: Path,
    # 期待する置換後総数を受け取る
    expected_output_count: int,
    # 期待する教師置換数を受け取る
    expected_replacement_count: int,
    # 既存成果物の上書き可否を受け取る
    overwrite: bool,
) -> dict[str, Any]:
    """元入力を変更せず、訓練指示へ教師言い換えを置換反映する。"""

    # 期待総数が正であることを確認する
    if expected_output_count <= 0:
        # 不正な期待値を拒否する
        raise ValueError("expected_output_countは正の整数にしてください")
    # 期待置換数が正で総数以下であることを確認する
    if not 0 < expected_replacement_count <= expected_output_count:
        # 不正な期待値を拒否する
        raise ValueError("expected_replacement_countが不正です")
    # 必須入力がすべて存在することを確認する
    for input_path in (
        rule_instructions,
        approved_paraphrases,
        paraphrase_generation_stats,
    ):
        # ファイルでなければ停止する
        if not input_path.is_file():
            # 不足した入力を示す
            raise ValueError(f"入力ファイルが見つかりません: {input_path}")
    # 作成対象をまとめる
    outputs = (output_jsonl, archive, stats)
    # 既存成果物を抽出する
    existing = [str(path) for path in outputs if path.exists()]
    # 明示的な上書き指定なしでは既存成果物を保護する
    if existing and not overwrite:
        # 置換対象と必要なフラグを通知する
        raise ValueError("既存出力があります。--overwriteを指定してください: " + ", ".join(existing))
    # 処理前のルール生成指示ハッシュを計算する
    rule_sha256_before = file_sha256(rule_instructions)
    # 処理前の承認済み教師言い換えハッシュを計算する
    approved_sha256_before = file_sha256(approved_paraphrases)
    # 処理前の教師生成集計ハッシュを計算する
    generation_stats_sha256_before = file_sha256(paraphrase_generation_stats)
    # 承認済み教師言い換えを置換元IDで読み込む
    approved_by_source = load_approved_paraphrases(
        # 入力パスを渡す
        approved_paraphrases,
        # 期待置換数を渡す
        expected_replacement_count,
    )
    # 教師生成失敗IDと全体件数を読み込む
    failure_source_ids, teacher_counts = load_teacher_failures(
        # 教師生成集計JSONを渡す
        paraphrase_generation_stats,
        # 承認済み置換元ID集合を渡す
        set(approved_by_source),
    )
    # 出力先ディレクトリを作る
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    # ZIP保存先ディレクトリを作る
    archive.parent.mkdir(parents=True, exist_ok=True)
    # 集計保存先ディレクトリを作る
    stats.parent.mkdir(parents=True, exist_ok=True)
    # 未完成JSONL用の一時パスを作る
    temporary_jsonl = output_jsonl.with_name(output_jsonl.name + ".tmp")
    # 全ルール生成レコード数を初期化する
    all_rule_count = 0
    # 訓練用元指示数を初期化する
    train_source_count = 0
    # 評価用など除外した元指示数を初期化する
    non_train_source_count = 0
    # 教師置換数を初期化する
    teacher_replaced_count = 0
    # 元文維持数を初期化する
    rule_retained_count = 0
    # 教師失敗による元文維持数を初期化する
    failure_retained_count = 0
    # 非選抜による元文維持数を初期化する
    unselected_retained_count = 0
    # 使用した教師置換元IDを保存する集合を作る
    consumed_teacher_source_ids: set[str] = set()
    # 確認した教師失敗元IDを保存する集合を作る
    consumed_failure_source_ids: set[str] = set()
    # 全元指示IDの重複検査用集合を作る
    source_instruction_ids: set[str] = set()
    # 出力指示IDの重複検査用集合を作る
    output_instruction_ids: set[str] = set()
    # spec_id別の元指示数を集計する
    source_counts_by_spec: Counter[str] = Counter()
    # spec_id別の出力指示数を集計する
    output_counts_by_spec: Counter[str] = Counter()
    # 操作数別の出力指示数を集計する
    output_counts_by_operation: Counter[int] = Counter()
    # 置換状態別件数を集計する
    replacement_status_counts: Counter[str] = Counter()
    # 中断時に未完成JSONLを片付けられる範囲で生成する
    try:
        # 元指示JSONLと一時出力JSONLをUTF-8で開く
        with rule_instructions.open(encoding="utf-8") as source_handle, temporary_jsonl.open(
            "w", encoding="utf-8", newline="\n"
        ) as output_handle:
            # 全ルール生成指示を元順序のまま処理する
            for source in read_jsonl(source_handle, str(rule_instructions)):
                # 全ルール生成レコード数を増やす
                all_rule_count += 1
                # 元指示IDを取得する
                source_id = require_string(source, "instruction_id", str(rule_instructions))
                # 元指示IDの重複を拒否する
                if source_id in source_instruction_ids:
                    # 重複IDを示して停止する
                    raise ValueError(f"元instruction_idが重複しています: {source_id}")
                # 元指示IDを登録する
                source_instruction_ids.add(source_id)
                # 訓練用以外は置換後訓練JSONLへ出力しない
                if source.get("split") != "train":
                    # 除外件数を増やす
                    non_train_source_count += 1
                    # 次の元指示へ進む
                    continue
                # 訓練辞書以外を拒否する
                if source.get("dictionary") != "train":
                    # test_only混入を通知する
                    raise ValueError(f"訓練元指示のdictionaryがtrainではありません: {source_id}")
                # 訓練用ではtest_suiteがnullであることを確認する
                if source.get("test_suite") is not None:
                    # 評価用レコードの混入を拒否する
                    raise ValueError(f"訓練元指示のtest_suiteがnullではありません: {source_id}")
                # 元指示本文を取得する
                source_instruction_ja = require_string(source, "instruction_ja", str(rule_instructions))
                # 元指示本文ハッシュを再計算して確認する
                if source.get("text_hash") != text_sha256(source_instruction_ja):
                    # 本文とハッシュの不一致を拒否する
                    raise ValueError(f"元指示のtext_hashが一致しません: {source_id}")
                # 意味AST IDを取得する
                spec_id = require_string(source, "spec_id", str(rule_instructions))
                # 訓練元指示数を増やす
                train_source_count += 1
                # 元指示のspec_id別件数を増やす
                source_counts_by_spec[spec_id] += 1
                # 承認済み教師言い換えがあれば置換する
                if source_id in approved_by_source:
                    # 対応する教師言い換えを取得する
                    teacher = approved_by_source[source_id]
                    # 変えてはいけない意味情報を照合する
                    validate_source_and_teacher(source, teacher, source_id)
                    # 元指示と教師来歴を保持した置換済みレコードを作る
                    resolved = make_teacher_replaced_record(source, teacher)
                    # 教師置換数を増やす
                    teacher_replaced_count += 1
                    # 使用した置換元IDを登録する
                    consumed_teacher_source_ids.add(source_id)
                # 教師生成に失敗した元指示は元文を維持する
                elif source_id in failure_source_ids:
                    # 失敗理由付きの元文維持レコードを作る
                    resolved = make_retained_rule_record(
                        source, "teacher_paraphrase_unavailable"
                    )
                    # 元文維持数を増やす
                    rule_retained_count += 1
                    # 失敗による維持数を増やす
                    failure_retained_count += 1
                    # 確認した失敗元IDを登録する
                    consumed_failure_source_ids.add(source_id)
                # 教師対象に選ばれなかった元指示も元文を維持する
                else:
                    # 非選抜理由付きの元文維持レコードを作る
                    resolved = make_retained_rule_record(
                        source, "not_selected_for_teacher_paraphrase"
                    )
                    # 元文維持数を増やす
                    rule_retained_count += 1
                    # 非選抜による維持数を増やす
                    unselected_retained_count += 1
                # 出力指示IDを取得する
                output_instruction_id = require_string(resolved, "instruction_id", "置換済み出力")
                # 出力指示IDの重複を拒否する
                if output_instruction_id in output_instruction_ids:
                    # 重複IDを示して停止する
                    raise ValueError(f"出力instruction_idが重複しています: {output_instruction_id}")
                # 出力指示IDを登録する
                output_instruction_ids.add(output_instruction_id)
                # 出力本文を取得する
                output_instruction_ja = require_string(resolved, "instruction_ja", "置換済み出力")
                # 出力本文ハッシュを再計算して確認する
                if resolved.get("text_hash") != text_sha256(output_instruction_ja):
                    # 本文とハッシュの不一致を拒否する
                    raise ValueError(f"出力text_hashが一致しません: {output_instruction_id}")
                # 訓練分割が保たれていることを確認する
                if resolved.get("split") != "train" or resolved.get("test_suite") is not None:
                    # 分割情報の変化を拒否する
                    raise ValueError(f"置換後の分割情報が不正です: {output_instruction_id}")
                # 意味AST IDが保たれていることを確認する
                if resolved.get("spec_id") != spec_id:
                    # 別意味ASTへの変更を拒否する
                    raise ValueError(f"置換後のspec_idが変化しています: {output_instruction_id}")
                # 出力のspec_id別件数を増やす
                output_counts_by_spec[spec_id] += 1
                # 出力の操作数別件数を増やす
                output_counts_by_operation[operation_count(resolved, "置換済み出力")] += 1
                # 置換状態別件数を増やす
                replacement_status_counts[resolved["replacement_status"]] += 1
                # 日本語を保つ決定的な一行JSONとして書き込む
                output_handle.write(json.dumps(resolved, ensure_ascii=False, separators=(",", ":")))
                # JSONLのレコード区切りとなる改行を書く
                output_handle.write("\n")
        # 置換後総数が期待値と一致することを確認する
        if len(output_instruction_ids) != expected_output_count:
            # 不完全または過剰な出力を拒否する
            raise ValueError(
                f"置換後指示数が期待値と一致しません: "
                f"{len(output_instruction_ids)} != {expected_output_count}"
            )
        # 置換数が期待値と一致することを確認する
        if teacher_replaced_count != expected_replacement_count:
            # 一部教師候補の未使用を拒否する
            raise ValueError(
                f"教師置換数が期待値と一致しません: "
                f"{teacher_replaced_count} != {expected_replacement_count}"
            )
        # 全承認済み教師候補を一度ずつ使用したことを確認する
        if consumed_teacher_source_ids != set(approved_by_source):
            # 未使用または未知の置換元を拒否する
            raise ValueError("承認済み教師候補の置換元IDをすべて消費できていません")
        # 全教師失敗IDが訓練元指示に存在したことを確認する
        if consumed_failure_source_ids != failure_source_ids:
            # 未知または評価用の失敗IDを拒否する
            raise ValueError("教師生成失敗IDをすべて訓練元指示で確認できていません")
        # 元と出力の意味AST別件数が完全一致することを確認する
        if source_counts_by_spec != output_counts_by_spec:
            # 意味AST別の増減を拒否する
            raise ValueError("置換前後でspec_id別指示数が一致しません")
        # 教師置換と元文維持の和が出力総数であることを確認する
        if teacher_replaced_count + rule_retained_count != expected_output_count:
            # 追加または欠落を拒否する
            raise ValueError("教師置換数と元文維持数の和が出力総数と一致しません")
        # 失敗維持と非選抜維持の和が元文維持数であることを確認する
        if failure_retained_count + unselected_retained_count != rule_retained_count:
            # 維持理由の不明なレコードを拒否する
            raise ValueError("元文維持理由別件数の和が一致しません")
        # 完成した一時JSONLを最終パスへ原子的に置き換える
        os.replace(temporary_jsonl, output_jsonl)
    # 成否にかかわらず未完成一時JSONLだけを削除する
    finally:
        # 一時ファイルが残っている場合だけ削除する
        temporary_jsonl.unlink(missing_ok=True)
    # 処理後の入力ファイルハッシュを再計算する
    rule_sha256_after = file_sha256(rule_instructions)
    # 処理後の承認済み教師言い換えハッシュを再計算する
    approved_sha256_after = file_sha256(approved_paraphrases)
    # 処理後の教師生成集計ハッシュを再計算する
    generation_stats_sha256_after = file_sha256(paraphrase_generation_stats)
    # 元ルール生成指示が変更されていないことを確認する
    if rule_sha256_after != rule_sha256_before:
        # 入力変更を検出して停止する
        raise ValueError("元のルール生成指示JSONLが処理中に変更されました")
    # 承認済み教師言い換えが変更されていないことを確認する
    if approved_sha256_after != approved_sha256_before:
        # 入力変更を検出して停止する
        raise ValueError("承認済み教師言い換えJSONLが処理中に変更されました")
    # 教師生成集計が変更されていないことを確認する
    if generation_stats_sha256_after != generation_stats_sha256_before:
        # 入力変更を検出して停止する
        raise ValueError("教師生成集計JSONが処理中に変更されました")
    # 置換済みJSONLを決定的なZIPへ格納する
    write_deterministic_zip(output_jsonl, archive)
    # 置換済みJSONLのSHA-256を計算する
    output_sha256 = file_sha256(output_jsonl)
    # ZIPのSHA-256を計算する
    archive_sha256 = file_sha256(archive)
    # 意味AST当たり指示数の分布を作る
    instructions_per_spec_distribution = Counter(output_counts_by_spec.values())
    # 実行条件と検証値を持つ集計objectを作る
    stats_record = {
        "phase": "replacement_resolved_train_instructions",
        "replacement_mode": "replace_source_instruction_one_to_one",
        "all_rule_instruction_count": all_rule_count,
        "train_source_instruction_count": train_source_count,
        "non_train_source_instruction_count": non_train_source_count,
        "teacher_selected_source_count": teacher_counts["selected_source_count"],
        "teacher_replaced_count": teacher_replaced_count,
        "rule_retained_count": rule_retained_count,
        "failure_retained_count": failure_retained_count,
        "unselected_retained_count": unselected_retained_count,
        "output_instruction_count": len(output_instruction_ids),
        "semantic_ast_count": len(output_counts_by_spec),
        "counts_by_operation_count": {
            str(key): output_counts_by_operation[key] for key in sorted(output_counts_by_operation)
        },
        "replacement_status_counts": {
            key: replacement_status_counts[key] for key in sorted(replacement_status_counts)
        },
        "instructions_per_semantic_ast_distribution": {
            str(key): instructions_per_spec_distribution[key]
            for key in sorted(instructions_per_spec_distribution)
        },
        "source_inputs_unchanged": True,
        "rule_instructions": str(rule_instructions),
        "rule_instructions_sha256_before": rule_sha256_before,
        "rule_instructions_sha256_after": rule_sha256_after,
        "approved_paraphrases": str(approved_paraphrases),
        "approved_paraphrases_sha256_before": approved_sha256_before,
        "approved_paraphrases_sha256_after": approved_sha256_after,
        "paraphrase_generation_stats": str(paraphrase_generation_stats),
        "paraphrase_generation_stats_sha256_before": generation_stats_sha256_before,
        "paraphrase_generation_stats_sha256_after": generation_stats_sha256_after,
        "output_jsonl": str(output_jsonl),
        "output_jsonl_bytes": output_jsonl.stat().st_size,
        "output_jsonl_sha256": output_sha256,
        "archive": str(archive),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": archive_sha256,
        "archive_member": ARCHIVE_MEMBER,
    }
    # 集計JSONを読みやすい形式で保存する
    stats.write_text(
        # 日本語を保った整形JSONと末尾改行を作る
        json.dumps(stats_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        # UTF-8で保存する
        encoding="utf-8",
    )
    # 呼び出し元が成果物を確認できる集計を返す
    return stats_record


# この工程を担当する関数を定義する
def main() -> None:
    """コマンドライン引数を使って置換反映済み訓練指示を作る。"""

    # コマンドライン引数を取得する
    args = parse_args()
    # 置換反映済み成果物を作る
    result = build_replacement_resolved_instructions(
        # 元ルール生成指示JSONLの絶対パスを渡す
        rule_instructions=args.rule_instructions.resolve(),
        # 承認済み教師言い換えJSONLの絶対パスを渡す
        approved_paraphrases=args.approved_paraphrases.resolve(),
        # 教師生成集計JSONの絶対パスを渡す
        paraphrase_generation_stats=args.paraphrase_generation_stats.resolve(),
        # 置換済みJSONLの絶対パスを渡す
        output_jsonl=args.output_jsonl.resolve(),
        # ZIPの絶対パスを渡す
        archive=args.archive.resolve(),
        # 集計JSONの絶対パスを渡す
        stats=args.stats.resolve(),
        # 期待する置換後総数を渡す
        expected_output_count=args.expected_output_count,
        # 期待する教師置換数を渡す
        expected_replacement_count=args.expected_replacement_count,
        # 上書き可否を渡す
        overwrite=args.overwrite,
    )
    # 作成結果の要点を表示する
    print(
        # 置換数、元文維持数、総数を表示する
        f"置換反映済み訓練指示を作成しました: "
        f"teacher_replaced={result['teacher_replaced_count']}, "
        f"rule_retained={result['rule_retained_count']}, "
        f"total={result['output_instruction_count']}"
    )


# 直接実行された場合だけCLI処理を開始する
if __name__ == "__main__":
    # 置換反映処理を開始する
    main()
