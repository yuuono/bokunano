"""BPE・Unigram共通トークナイザ訓練を検証する。"""

# JSON成果物とJSONL入力を作るために使う
import json
# 一時ディレクトリ内のパスを扱う
from pathlib import Path
# 一時ディレクトリを安全に作成・削除する
import tempfile
# 標準ライブラリだけでテストを自動検出する
import unittest
# 訓練入力ZIPを作る
import zipfile

# YAMLテスト設定を保存する
import yaml
# 完成tokenizerを再読込みする
from tokenizers import Tokenizer

# トークナイザ訓練関数とハッシュ関数を読み込む
from scripts.tokenizer.train_tokenizer import file_sha256, train_tokenizer


# BPE・Unigram共通処理をまとめて検証する
class TrainTokenizerTest(unittest.TestCase):
    """両model typeの固定ID、完全復元、入力不変を確認する。"""

    # BPEとUnigramを同じ入力・設定構造から生成する
    def test_trains_bpe_and_unigram_from_train_records_only(self) -> None:
        """両方式がbyte fallback付き成果物と検証集計を作る。"""

        # テスト専用一時ディレクトリを作る
        with tempfile.TemporaryDirectory() as temporary_directory:
            # Pathへ変換する
            root = Path(temporary_directory)
            # 入力ZIPを作る
            archive_path = root / "train.zip"
            # 小さな訓練レコードを作る
            records = [
                _record(
                    "整数リストxsから偶数だけを残してください。",
                    "def solve(xs, k):\n    return [x for x in xs if x % 2 == 0]\n",
                ),
                _record(
                    "整数リストxsの各値にkを足してください。",
                    "def solve(xs, k):\n    return [value + k for value in xs]\n",
                ),
                _record(
                    "整数リストxsを逆順にしてください。",
                    "def solve(xs, k):\n    result = list(reversed(xs))\n    return result\n",
                ),
                _record(
                    "整数リストxsを小さい順に並べてください。",
                    "def solve(xs, k):\n    return sorted(xs)\n",
                ),
            ]
            # ZIP内JSONLを作る
            with zipfile.ZipFile(archive_path, mode="w") as archive:
                # 一行JSONを連結して保存する
                archive.writestr(
                    "final_dataset_records.jsonl",
                    "".join(
                        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                        for record in records
                    ),
                )
            # 処理前バイト列を保存する
            archive_bytes_before = archive_path.read_bytes()
            # 両model typeを順番に検証する
            for model_type in ("bpe", "unigram"):
                # subTestで失敗方式を明確にする
                with self.subTest(model_type=model_type):
                    # YAMLパスを作る
                    config_path = root / f"{model_type}.yaml"
                    # 出力パスを作る
                    output_dir = root / f"output-{model_type}"
                    # 小規模設定を保存する
                    config_path.write_text(
                        yaml.safe_dump(
                            _config(model_type, archive_path, output_dir),
                            allow_unicode=True,
                            sort_keys=False,
                        ),
                        encoding="utf-8",
                    )
                    # トークナイザを学習する
                    result = train_tokenizer(
                        config_path=config_path,
                        output_override=None,
                        overwrite=False,
                    )
                    # 指定方式で完成したことを確認する
                    self.assertEqual(result["model_type"], model_type)
                    # 全4レコードを検証したことを確認する
                    self.assertEqual(result["validation"]["record_count"], 4)
                    # unknownが出ていないことを確認する
                    self.assertEqual(result["validation"]["unk_token_count"], 0)
                    # encode/decode不一致がないことを確認する
                    self.assertEqual(
                        result["validation"]["roundtrip_mismatch_count"], 0
                    )
                    # 完成tokenizerを読み込む
                    tokenizer = Tokenizer.from_file(str(output_dir / "tokenizer.json"))
                    # 特殊トークンIDを順番どおり確認する
                    self.assertEqual(tokenizer.token_to_id("<|pad|>"), 0)
                    # unknown IDを確認する
                    self.assertEqual(tokenizer.token_to_id("<|unk|>"), 3)
                    # 日本語、改行、インデントを完全復元できることを確認する
                    sample = records[0]["instruction_ja"] + "\n" + records[0]["reference_code"]
                    # encodeしてからdecodeする
                    decoded = tokenizer.decode(
                        tokenizer.encode(sample).ids, skip_special_tokens=False
                    )
                    # 元本文と完全一致することを確認する
                    self.assertEqual(decoded, sample)
                    # model JSONでbyte fallbackが有効なことを確認する
                    tokenizer_json = json.loads(
                        (output_dir / "tokenizer.json").read_text(encoding="utf-8")
                    )
                    # 設定値を照合する
                    self.assertTrue(tokenizer_json["model"]["byte_fallback"])
                    # 必須成果物がすべてあることを確認する
                    self.assertTrue((output_dir / "training_stats.json").is_file())
                    # 語彙一覧も確認する
                    self.assertTrue((output_dir / "vocab.tsv").is_file())
            # 両方式の処理後も入力ZIPが変わっていないことを確認する
            self.assertEqual(archive_path.read_bytes(), archive_bytes_before)


# テスト用最終訓練レコードを作る
def _record(instruction_ja: str, reference_code: str) -> dict[str, object]:
    """必要な分割項目と本文だけを持つレコードを返す。"""

    # train固定のレコードを返す
    return {
        "split": "train",
        "test_suite": None,
        "dictionary": "train",
        "input_set": "build",
        "instruction_ja": instruction_ja,
        "reference_code": reference_code,
    }


# テスト用YAML設定を作る
def _config(model_type: str, archive_path: Path, output_dir: Path) -> dict[str, object]:
    """実設定と同じ構造を持つ小規模設定を返す。"""

    # 共通model設定を作る
    model: dict[str, object] = {
        "type": model_type,
        "vocab_size": 300,
        "byte_fallback": True,
        "unk_token": "<|unk|>",
    }
    # BPE固有値を追加する
    if model_type == "bpe":
        # BPE trainer設定を追加する
        model.update({"min_frequency": 1, "max_token_length": 24, "dropout": 0.0})
    # Unigram固有値を追加する
    else:
        # Unigram trainer設定を追加する
        model.update(
            {"shrinking_factor": 0.75, "max_piece_length": 24, "n_sub_iterations": 2}
        )
    # 完成設定を返す
    return {
        "version": 1,
        "source": {
            "archive": str(archive_path),
            "member": "final_dataset_records.jsonl",
            "expected_archive_sha256": file_sha256(archive_path),
            "expected_record_count": 4,
            "required_values": {
                "split": "train",
                "test_suite": None,
                "dictionary": "train",
                "input_set": "build",
            },
        },
        "corpus": {
            "fields": ["instruction_ja", "reference_code"],
            "deduplicate": {"instruction_ja": True, "reference_code": True},
        },
        "normalizer": {"type": "identity"},
        "pre_tokenizer": {
            "type": "byte_level",
            "add_prefix_space": False,
            "use_regex": False,
            "initial_alphabet": "byte_level_256",
        },
        "model": model,
        "special_tokens": [
            {"name": "pad", "token": "<|pad|>", "id": 0},
            {"name": "bos", "token": "<|bos|>", "id": 1},
            {"name": "eos", "token": "<|eos|>", "id": 2},
            {"name": "unk", "token": "<|unk|>", "id": 3},
            {"name": "task", "token": "<|task|>", "id": 4},
            {"name": "code", "token": "<|code|>", "id": 5},
            {"name": "explanation", "token": "<|explanation|>", "id": 6},
        ],
        "sequence": {
            "template": "<|bos|><|task|>\n{instruction_ja}\n<|code|>\n{reference_code}<|eos|>",
            "required_special_tokens": ["bos", "task", "code", "eos"],
        },
        "validation": {
            "model_max_length": 256,
            "batch_size": 2,
            "require_exact_vocab_size": False,
            "require_roundtrip": True,
            "require_zero_unk": True,
            "fail_on_overlength": False,
        },
        "output": {"directory": str(output_dir)},
    }


# 直接実行時もテストを走らせる
if __name__ == "__main__":
    # unittestの標準実行を開始する
    unittest.main()
