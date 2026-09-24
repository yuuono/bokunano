"""教師言い換え候補を明示的な一括承認で承認済みJSONLへ変換する。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse
# 承認日時のタイムゾーン有無を検査するために使う
from datetime import datetime
# ハッシュ計算に使う
import hashlib
# JSONLと集計JSONを読み書きするために使う
import json
# 一時ファイルを最終パスへ安全に置き換えるために使う
import os
# 入出力ファイルのパスを扱うために使う
from pathlib import Path
# レコード型の注釈に使う
from typing import Any
# 承認済みJSONLを決定的なZIPへ格納するために使う
import zipfile


# ZIP内メンバーの固定日時を定義する
ZIP_TIMESTAMP = (2026, 9, 24, 0, 0, 0)
# 承認前候補に必須の項目を定義する
REQUIRED_CANDIDATE_FIELDS = {
    # 教師候補そのもののIDを必須にする
    "instruction_id",
    # 元のルール生成指示IDを必須にする
    "source_instruction_id",
    # 意味ASTを識別するIDを必須にする
    "spec_id",
    # 意味AST本体を必須にする
    "semantic_ast",
    # 元の日本語指示を必須にする
    "source_instruction_ja",
    # 教師が言い換えた日本語指示を必須にする
    "instruction_ja",
    # 教師生成であることを示す区分を必須にする
    "instruction_source",
    # 使用した表現辞書区分を必須にする
    "dictionary",
    # 承認前状態を必須にする
    "review_status",
    # 教師モデルIDを必須にする
    "teacher_model",
    # 教師モデルrevisionを必須にする
    "teacher_revision",
    # sampling seedを必須にする
    "teacher_seed",
    # sampling設定を必須にする
    "teacher_sampling",
    # 実際のpromptを識別するハッシュを必須にする
    "prompt_hash",
    # 言い換え本文のハッシュを必須にする
    "text_hash",
}


# この工程を担当する関数を定義する
def parse_args() -> argparse.Namespace:
    """一括承認に必要なパスと監査情報を受け取る。"""

    # このスクリプト用の引数解析器を作る
    parser = argparse.ArgumentParser(
        # 一括承認であることを利用者へ明示する
        description="教師言い換え候補を全件承認したJSONLとZIPを作成します。"
    )
    # 承認前候補JSONLを受け取る
    parser.add_argument("--candidate-jsonl", required=True, type=Path)
    # 承認済みJSONLの保存先を受け取る
    parser.add_argument("--output-jsonl", required=True, type=Path)
    # Git管理用ZIPの保存先を受け取る
    parser.add_argument("--archive", required=True, type=Path)
    # 実行件数とハッシュを保存する集計JSONのパスを受け取る
    parser.add_argument("--stats", required=True, type=Path)
    # 一括承認を指示した人の識別名を受け取る
    parser.add_argument("--reviewer", required=True)
    # タイムゾーン付きISO 8601承認日時を受け取る
    parser.add_argument("--approved-at", required=True)
    # 入力候補の期待件数を受け取る
    parser.add_argument("--expected-count", required=True, type=int)
    # 誤操作防止のため一括承認を明示するフラグを受け取る
    parser.add_argument("--approve-all", action="store_true")
    # 既存成果物を置き換える場合だけ指定するフラグを受け取る
    parser.add_argument("--overwrite", action="store_true")
    # 解析済み引数を返す
    return parser.parse_args()


# この工程を担当する関数を定義する
def main() -> None:
    """入力候補を検証し、承認済みJSONL、ZIP、集計を作る。"""

    # コマンドライン引数を取得する
    args = parse_args()
    # 一括承認成果物を作成する
    result = prepare_approved_paraphrases(
        # 承認前候補JSONLを渡す
        candidate_jsonl=args.candidate_jsonl.resolve(),
        # 承認済みJSONLの保存先を渡す
        output_jsonl=args.output_jsonl.resolve(),
        # ZIPの保存先を渡す
        archive=args.archive.resolve(),
        # 集計JSONの保存先を渡す
        stats=args.stats.resolve(),
        # 一括承認者を渡す
        reviewer=args.reviewer,
        # 一括承認日時を渡す
        approved_at=args.approved_at,
        # 入力候補の期待件数を渡す
        expected_count=args.expected_count,
        # 一括承認の明示フラグを渡す
        approve_all=args.approve_all,
        # 既存成果物の上書き可否を渡す
        overwrite=args.overwrite,
    )
    # 作成件数と保存先を利用者へ表示する
    print(
        # 承認済み件数とJSONLパスを表示する
        f"承認済み教師言い換えを作成しました: approved={result['approved_count']}, "
        # ZIPパスを続けて表示する
        f"jsonl={result['output_jsonl']}, archive={result['archive']}"
    )


# この工程を担当する関数を定義する
def prepare_approved_paraphrases(
    # すべての引数を名前付きで受け取る
    *,
    # 承認前候補JSONLを受け取る
    candidate_jsonl: Path,
    # 承認済みJSONLの保存先を受け取る
    output_jsonl: Path,
    # Git管理用ZIPの保存先を受け取る
    archive: Path,
    # 集計JSONの保存先を受け取る
    stats: Path,
    # 承認者名を受け取る
    reviewer: str,
    # 承認日時を受け取る
    approved_at: str,
    # 入力期待件数を受け取る
    expected_count: int,
    # 全件承認の明示状態を受け取る
    approve_all: bool,
    # 既存成果物の上書き可否を受け取る
    overwrite: bool,
# 作成結果の集計を返す
) -> dict[str, Any]:
    """候補全件の来歴を保持して承認情報を追加する。"""

    # 一括承認が明示されていない実行を拒否する
    if not approve_all:
        # 誤って全候補を承認しないよう例外で停止する
        raise ValueError("全件承認には--approve-allの明示が必要です")
    # 承認者名の前後空白を除く
    reviewer = reviewer.strip()
    # 空の承認者名を拒否する
    if not reviewer:
        # 監査情報を欠くため例外で停止する
        raise ValueError("reviewerは空でない文字列にしてください")
    # 期待件数が正であることを確認する
    if expected_count <= 0:
        # 不正な件数を例外で通知する
        raise ValueError("expected_countは正の整数にしてください")
    # 承認日時をISO 8601として解析する
    try:
        # タイムゾーン情報も保持したdatetimeへ変換する
        parsed_approved_at = datetime.fromisoformat(approved_at)
    # ISO 8601でない値を明確な設定エラーにする
    except ValueError as error:
        # 元例外を保持して利用者向けメッセージを返す
        raise ValueError("approved_atはISO 8601形式にしてください") from error
    # タイムゾーンなしの承認日時を拒否する
    if parsed_approved_at.tzinfo is None:
        # 実行環境によって時刻解釈が変わらないよう停止する
        raise ValueError("approved_atにはタイムゾーンを含めてください")
    # 入力候補JSONLが存在することを確認する
    if not candidate_jsonl.is_file():
        # 対象パスを含めて不足を通知する
        raise ValueError(f"候補JSONLが見つかりません: {candidate_jsonl}")
    # この実行で作成する成果物パスをまとめる
    outputs = [output_jsonl, archive, stats]
    # 既存成果物があるパスだけを抽出する
    existing = [str(path) for path in outputs if path.exists()]
    # 上書き指定がない場合は既存成果物を保護する
    if existing and not overwrite:
        # 置換対象を列挙して停止する
        raise ValueError(
            "既存出力があります。置き換える場合は--overwriteを指定してください: "
            + ", ".join(existing)
        )

    # 出力先ディレクトリを必要に応じて作る
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    # ZIP保存先ディレクトリを必要に応じて作る
    archive.parent.mkdir(parents=True, exist_ok=True)
    # 集計保存先ディレクトリを必要に応じて作る
    stats.parent.mkdir(parents=True, exist_ok=True)
    # 中断時に完成ファイルを壊さない同一ディレクトリ一時パスを作る
    temporary_jsonl = output_jsonl.with_name(output_jsonl.name + ".tmp")
    # 処理した候補数を初期化する
    approved_count = 0
    # 候補IDの重複検査用集合を作る
    instruction_ids: set[str] = set()
    # 元指示IDの重複検査用集合を作る
    source_instruction_ids: set[str] = set()
    # 一時ファイルを必ず片付けられる範囲で生成する
    try:
        # 承認前候補と一時出力をUTF-8で開く
        with candidate_jsonl.open(encoding="utf-8") as source_handle, temporary_jsonl.open(
            "w", encoding="utf-8"
        ) as output_handle:
            # 候補JSONLを行番号付きで一件ずつ処理する
            for line_number, line in enumerate(source_handle, start=1):
                # 空行はレコードとして数えず読み飛ばす
                if not line.strip():
                    # 次の入力行へ進む
                    continue
                # 一行をJSON objectへ変換する
                try:
                    # 入力文字列をPython値へ解析する
                    candidate = json.loads(line)
                # JSON構文エラーへ行番号を付けて停止する
                except json.JSONDecodeError as error:
                    # 不正な入力位置を通知する
                    raise ValueError(
                        f"候補JSONLが不正です: {candidate_jsonl}:{line_number}"
                    ) from error
                # JSONLの各行がobjectであることを確認する
                if not isinstance(candidate, dict):
                    # 配列や文字列などの不正レコードを拒否する
                    raise ValueError(
                        f"候補JSONLレコードがobjectではありません: 行{line_number}"
                    )
                # 承認済みレコードに必要な入力項目の不足を調べる
                missing_fields = sorted(REQUIRED_CANDIDATE_FIELDS - set(candidate))
                # 必須項目が一つでも欠けていれば停止する
                if missing_fields:
                    # 行番号と不足項目を通知する
                    raise ValueError(
                        f"候補JSONLに必須項目がありません: 行{line_number}: "
                        + ", ".join(missing_fields)
                    )
                # 教師候補IDを空でない文字列として取得する
                instruction_id = _required_string(candidate, "instruction_id", line_number)
                # 元のルール生成指示IDを空でない文字列として取得する
                source_instruction_id = _required_string(
                    candidate, "source_instruction_id", line_number
                )
                # 教師候補IDの重複を拒否する
                if instruction_id in instruction_ids:
                    # 重複IDを含めて停止する
                    raise ValueError(f"instruction_idが重複しています: {instruction_id}")
                # 元指示IDの重複を拒否する
                if source_instruction_id in source_instruction_ids:
                    # 重複IDを含めて停止する
                    raise ValueError(
                        f"source_instruction_idが重複しています: {source_instruction_id}"
                    )
                # 承認前候補の状態がpendingであることを確認する
                if candidate.get("review_status") != "pending":
                    # 想定外状態の二重承認を拒否する
                    raise ValueError(
                        f"承認前review_statusがpendingではありません: {instruction_id}"
                    )
                # 教師候補だけをこの工程の対象として許可する
                if candidate.get("instruction_source") != "teacher":
                    # 別生成元の混入を拒否する
                    raise ValueError(
                        f"instruction_sourceがteacherではありません: {instruction_id}"
                    )
                # 訓練辞書を使った候補だけを承認対象として許可する
                if candidate.get("dictionary") != "train":
                    # test_only混入を拒否する
                    raise ValueError(f"dictionaryがtrainではありません: {instruction_id}")
                # 元文と同じ候補が再混入していないことを確認する
                if candidate.get("instruction_ja") == candidate.get(
                    "source_instruction_ja"
                ):
                    # 言い換えになっていない候補を拒否する
                    raise ValueError(f"元文と同一の候補です: {instruction_id}")
                # 検査済み候補IDを集合へ追加する
                instruction_ids.add(instruction_id)
                # 検査済み元指示IDを集合へ追加する
                source_instruction_ids.add(source_instruction_id)
                # 元候補の全項目を保持した新しいobjectを作る
                approved = dict(candidate)
                # 上書き前の候補状態を別項目へ保存する
                approved["candidate_review_status"] = candidate["review_status"]
                # 利用可能な承認済み状態へ更新する
                approved["review_status"] = "approved"
                # 一括承認を指示した人を保存する
                approved["approved_by"] = reviewer
                # タイムゾーン付き承認日時を保存する
                approved["approved_at"] = approved_at
                # 個別CSV判定ではなく明示的一括承認であることを保存する
                approved["approval_mode"] = "blanket_all_candidates"
                # 日本語を保つ決定的な一行JSONとして書き込む
                output_handle.write(
                    json.dumps(approved, ensure_ascii=False, separators=(",", ":"))
                )
                # JSONLのレコード区切りとなる改行を書く
                output_handle.write("\n")
                # 承認済み件数を1増やす
                approved_count += 1
        # 実件数が設定した候補数と一致することを確認する
        if approved_count != expected_count:
            # 不完全な一括承認を防ぐため件数差を通知する
            raise ValueError(
                f"承認件数が期待値と一致しません: {approved_count} != {expected_count}"
            )
        # 完成した一時JSONLを最終パスへ原子的に置き換える
        os.replace(temporary_jsonl, output_jsonl)
    # 成否にかかわらず未完成一時JSONLだけを削除する
    finally:
        # 一時ファイルが残っている場合だけ削除する
        temporary_jsonl.unlink(missing_ok=True)

    # 承認済みJSONLを決定的なZIPへ格納する
    _write_deterministic_zip(
        # 完成した承認済みJSONLを渡す
        output_jsonl,
        # Git管理用ZIPの保存先を渡す
        archive,
        # ZIP内では配置に依存しない固定名を使う
        "approved_teacher_paraphrases.jsonl",
    )
    # 入力候補JSONLのSHA-256を計算する
    candidate_sha256 = _sha256_file(candidate_jsonl)
    # 承認済みJSONLのSHA-256を計算する
    output_sha256 = _sha256_file(output_jsonl)
    # ZIPのSHA-256を計算する
    archive_sha256 = _sha256_file(archive)
    # 実行条件と検証値を持つ集計objectを作る
    stats_record = {
        # 処理段階名を保存する
        "phase": "approved_teacher_paraphrases",
        # 承認方式を保存する
        "approval_mode": "blanket_all_candidates",
        # 一括承認者を保存する
        "approved_by": reviewer,
        # 一括承認日時を保存する
        "approved_at": approved_at,
        # 承認済み件数を保存する
        "approved_count": approved_count,
        # 入力候補パスを保存する
        "candidate_jsonl": str(candidate_jsonl),
        # 入力候補ハッシュを保存する
        "candidate_sha256": candidate_sha256,
        # 承認済みJSONLパスを保存する
        "output_jsonl": str(output_jsonl),
        # 承認済みJSONLハッシュを保存する
        "output_sha256": output_sha256,
        # ZIPパスを保存する
        "archive": str(archive),
        # ZIPハッシュを保存する
        "archive_sha256": archive_sha256,
    }
    # 集計JSONを読みやすい形式で保存する
    stats.write_text(
        # 日本語を保った整形JSONと末尾改行を作る
        json.dumps(stats_record, ensure_ascii=False, indent=2) + "\n",
        # UTF-8で保存する
        encoding="utf-8",
    )
    # 呼び出し元が件数とパスを確認できる結果を返す
    return {
        # 承認済み件数を返す
        "approved_count": approved_count,
        # 承認済みJSONLパスを返す
        "output_jsonl": str(output_jsonl),
        # ZIPパスを返す
        "archive": str(archive),
        # 集計JSONパスを返す
        "stats": str(stats),
        # 承認済みJSONLハッシュを返す
        "output_sha256": output_sha256,
        # ZIPハッシュを返す
        "archive_sha256": archive_sha256,
    }


# この工程を担当する関数を定義する
def _required_string(record: dict[str, Any], key: str, line_number: int) -> str:
    """指定項目を空でない文字列として取得する。"""

    # 指定項目の値を取得する
    value = record.get(key)
    # 空でない文字列以外を拒否する
    if not isinstance(value, str) or not value:
        # 項目名と行番号を含めて停止する
        raise ValueError(f"{key}が空です: 行{line_number}")
    # 検査済み文字列を返す
    return value


# この工程を担当する関数を定義する
def _write_deterministic_zip(source: Path, archive: Path, member: str) -> None:
    """固定メタデータと圧縮設定で単一JSONLのZIPを作る。"""

    # ZIP内ファイルの固定メタデータを作る
    info = zipfile.ZipInfo(member, date_time=ZIP_TIMESTAMP)
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
            # 承認済みJSONLをバイナリで開く
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
def _sha256_file(path: Path) -> str:
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


# 直接実行された場合だけCLI処理を開始する
if __name__ == "__main__":
    # コマンドライン引数を使って一括承認成果物を作る
    main()
