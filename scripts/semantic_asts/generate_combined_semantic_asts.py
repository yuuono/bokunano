"""24個の単独操作から、順序付きの意味ASTを1〜3操作で生成する。"""

# 順列を列挙するために使う
import itertools
# JSONL形式のデータを読み書きするために使う
import json
# OSに依存しないパス操作のために使う
from pathlib import Path


# このファイルの位置からリポジトリのルートを求める
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 意味ASTをまとめるディレクトリ
DATA_DIR = PROJECT_ROOT / "data" / "semantic_asts"
# 入力となる24個の単独操作ASTのファイル
INPUT_PATH = DATA_DIR / "atomic_semantic_asts.jsonl"
# 生成した組み合わせASTを書き出すファイル
OUTPUT_PATH = DATA_DIR / "combined_semantic_asts.jsonl"
# 組み合わせる操作数の下限
MIN_OPERATIONS = 1
# 組み合わせる操作数の上限
MAX_OPERATIONS = 3


# この工程を担当する関数を定義する
def load_atomic_asts(path: Path) -> list[dict]:
    # UTF-8で開いて1行ずつ読む
    with path.open(encoding="utf-8") as source:
        # 空行を飛ばしつつ各行をJSONとして辞書のリストにする
        records = [json.loads(line) for line in source if line.strip()]

    # 単独操作は24件ちょうどでなければ生成件数が合わなくなる
    if len(records) != 24:
        # 件数が違えば中断する
        raise ValueError(f"単独操作は24件必要です: {len(records)}件")

    # 重複チェックのため全spec_idを集める
    spec_ids = [record["spec_id"] for record in records]
    # 集合にして長さが変わればどこかが重複している
    if len(spec_ids) != len(set(spec_ids)):
        # 同じ操作が二重に入っていると組み合わせが偏るので中断する
        raise ValueError("単独操作のspec_idが重複しています")

    # 検証を通った24件を返す
    return records


# この工程を担当する関数を定義する
def generate_records(atomic_records: list[dict]):
    # 出力するspec_idの連番（1から始める）
    record_number = 1

    # 操作数を1から3まで増やしながら生成する
    for operation_count in range(MIN_OPERATIONS, MAX_OPERATIONS + 1):
        # 同じ操作を重複させず、順序の違いも別物として列挙する
        for selected in itertools.permutations(atomic_records, operation_count):
            # 1件分のレコードを都度返す（全件をメモリに溜めない）
            yield {
                # 連番を6桁ゼロ埋めしたIDを振る
                "spec_id": f"combined-{record_number:06d}",
                # 出力レコードの項目と値を設定する
                "semantic_ast": {
                    # 選んだ操作のASTを選択順に並べる
                    "sequence": [record["semantic_ast"] for record in selected]
                },
            }
            # 次のレコード用に連番を進める
            record_number += 1


# この工程を担当する関数を定義する
def save_jsonl(records, path: Path) -> int:
    # 実際に書き出した件数
    count = 0
    # 改行をLFに固定してUTF-8で上書き保存する
    with path.open("w", encoding="utf-8", newline="\n") as destination:
        # ジェネレータから1件ずつ受け取る
        for record in records:
            # 次の値または処理を現在の構造へ組み込む
            destination.write(
                # 日本語をエスケープせず、余分な空白も入れずに1行のJSONにする
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
            # 書き出した件数を数える
            count += 1
    # 呼び出し元で件数を検証できるように返す
    return count


# この工程を担当する関数を定義する
def main() -> None:
    # 24個の単独操作を読み込んで検証する
    atomic_records = load_atomic_asts(INPUT_PATH)
    # 生成したレコードをそのままファイルへ流し込み、件数を受け取る
    count = save_jsonl(generate_records(atomic_records), OUTPUT_PATH)

    # 1操作24件 + 2操作の順列 + 3操作の順列 = 12,720件が理論値
    expected_count = 24 + 24 * 23 + 24 * 23 * 22
    # 実際の件数が理論値と一致するかを確認する
    if count != expected_count:
        # 一致しなければ生成処理が壊れているので中断する
        raise RuntimeError(f"生成件数が不正です: {count}件")

    # 保存先と件数を表示する
    print(f"{OUTPUT_PATH} に {count} 件保存しました")


# スクリプトとして直接実行されたときだけmainを走らせる
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    main()
