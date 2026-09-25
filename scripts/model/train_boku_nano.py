"""固定BPEと最終訓練データからBoku-nanoをフルスクラッチ学習する。"""

# 将来のPythonでも現在の型注釈をそのまま評価できるようにする
from __future__ import annotations

# コマンドライン引数を解析する
import argparse
# token IDを省メモリで保持する
from array import array
# 学習率のcosine減衰を計算する
import math
# SHA-256を計算する
import hashlib
# pad IDをcollate関数へ固定する
from functools import partial
# ZIP内JSONLをUTF-8として読む
import io
# 設定・manifest・metricsをJSONで保存する
import json
# 実行環境のpackage版を記録する
from importlib.metadata import version as package_version
# 出力パスを扱う
from pathlib import Path
# Python乱数を固定する
import random
# 明示的上書き時だけ既存出力を削除する
import shutil
# Python実行版を記録する
import sys
# 経過時間とUTC時刻を記録する
import time
# 任意の設定値の型注釈に使う
from typing import Any
# 訓練レコードZIPを検査して読む
import zipfile

# YAML設定を安全に読み込む
import yaml
# 最終推論重みをpickleなしで保存する
from safetensors.torch import save_file as save_safetensors
# モデル学習を実行する
import torch
# batchを読み込む
from torch.utils.data import DataLoader, Dataset
# 固定済みtokenizer.jsonを読み込む
from tokenizers import Tokenizer

# packageとしてimportされた場合のモデル定義を読み込む
try:
    # リポジトリルートからのimportを優先する
    from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM
# scriptファイルを直接実行した場合にも対応する
except ModuleNotFoundError:
    # 同じディレクトリのモデル定義を読み込む
    from boku_nano import BokuNanoConfig, BokuNanoForCausalLM


# 学習スクリプトの版をmanifestへ固定する
TRAINER_VERSION = "1"
# コード生成のみを教師信号にする損失方式名を固定する
LOSS_SCOPE = "code_and_eos_only"
# dataset内で損失を無視するlabel値を固定する
IGNORE_INDEX = -100


# CLI引数を定義する
def parse_args() -> argparse.Namespace:
    """YAML設定と安全な実行時上書きだけを受け取る。"""

    # 学習用引数解析器を作る
    parser = argparse.ArgumentParser(
        description="BPE 2,048語彙でBoku-nanoをランダム初期値から学習します。"
    )
    # 再現条件をまとめたYAMLを必須にする
    parser.add_argument("--config", required=True, type=Path)
    # 実験時だけ成果物ディレクトリを差し替えられるようにする
    parser.add_argument("--output-dir", type=Path)
    # 構成と固定成果物だけを検査して終了する選択肢を用意する
    parser.add_argument("--validate-config", action="store_true")
    # 短いsmoke testだけに使う最大optimizer step数を受け取る
    parser.add_argument("--max-steps", type=int)
    # 既存出力を意図的に置き換える場合だけ明示させる
    parser.add_argument("--overwrite", action="store_true")
    # epoch境界checkpointから再開する場合のファイルを受け取る
    parser.add_argument("--resume-from", type=Path)
    # 解析済み引数を返す
    return parser.parse_args()


# byte単位の固定ハッシュを計算する
def file_sha256(path: Path) -> str:
    """ファイル全体のSHA-256を16進文字列で返す。"""

    # SHA-256計算器を作る
    digest = hashlib.sha256()
    # 大きなZIPも分割して読む
    with path.open("rb") as handle:
        # 1 MiBずつEOFまで読む
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            # 現在のchunkをハッシュへ追加する
            digest.update(chunk)
    # 完成した16進ハッシュを返す
    return digest.hexdigest()


# clone先の絶対パスを成果物へ残さない
def display_path(path: Path) -> str:
    """現在のリポジトリ配下ならPOSIX相対パスを返す。"""

    # 記号リンクと相対要素を解決する
    resolved = path.resolve()
    # 現在のリポジトリルートを解決する
    repository_root = Path.cwd().resolve()
    # リポジトリ内パスへの変換を試す
    try:
        # clone位置を含めない相対パスを返す
        return resolved.relative_to(repository_root).as_posix()
    # リポジトリ外の明示入力だけは絶対パスのまま扱う
    except ValueError:
        # OS表記の解決済みパスを返す
        return str(resolved)


# YAMLを辞書として読み込む
def load_config(config_path: Path) -> dict[str, Any]:
    """設定ファイルを読み、最上位が辞書であることを確認する。"""

    # 設定ファイルの存在を確認する
    if not config_path.is_file():
        # 欠落パスを明示する
        raise FileNotFoundError(f"設定ファイルがありません: {config_path}")
    # YAMLを安全なloaderで読む
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    # 空ファイルや配列設定を拒否する
    if not isinstance(config, dict):
        # 必須形式を説明する
        raise ValueError("設定YAMLの最上位はmappingである必要があります")
    # 必須最上位sectionを確認する
    required_sections = {
        "model",
        "tokenizer",
        "data",
        "validation_data",
        "training",
        "optimizer",
        "runtime",
        "output",
    }
    # 欠落sectionを抽出する
    missing = required_sections - set(config)
    # 欠落があれば誤実行前に止める
    if missing:
        # 欠落名を並べて例外にする
        raise ValueError(f"必須設定sectionがありません: {sorted(missing)}")
    # 読み込んだ設定を返す
    return config


# 設定内パスをconfig位置ではなくリポジトリルート基準で解決する
def configured_path(value: Any) -> Path:
    """YAMLのpath文字列を展開せずPathへ変換する。"""

    # パス以外の型を拒否する
    if not isinstance(value, str) or not value:
        # 設定値の要件を示す
        raise ValueError("path設定は空でない文字列である必要があります")
    # ユーザー依存の環境変数やチルダを暗黙展開せずPath化する
    return Path(value)


# 固定tokenizerと特殊IDを検証する
def validate_tokenizer(
    config: dict[str, Any], model_config: BokuNanoConfig
) -> tuple[Tokenizer, dict[str, int], str]:
    """tokenizer本体、SHA-256、語彙数、特殊token IDを照合する。"""

    # tokenizer設定を取り出す
    tokenizer_config = config["tokenizer"]
    # tokenizer.jsonのパスを解決する
    tokenizer_path = configured_path(tokenizer_config["path"])
    # tokenizer成果物の存在を確認する
    if not tokenizer_path.is_file():
        # 欠落パスを明示する
        raise FileNotFoundError(f"tokenizer.jsonがありません: {tokenizer_path}")
    # 実ファイルのSHA-256を計算する
    tokenizer_sha256 = file_sha256(tokenizer_path)
    # 設定に固定したSHA-256を読む
    expected_sha256 = str(tokenizer_config["expected_sha256"])
    # 暗黙のtokenizer差し替えを拒否する
    if tokenizer_sha256 != expected_sha256:
        # 期待値と実値を示す
        raise ValueError(
            f"tokenizer SHA-256が一致しません: {tokenizer_sha256} != {expected_sha256}"
        )
    # tokenizers実装で完成tokenizerを読む
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    # 特殊token込みの実語彙数を取得する
    actual_vocab_size = tokenizer.get_vocab_size(with_added_tokens=True)
    # モデル出力次元との一致を確認する
    if actual_vocab_size != model_config.vocab_size:
        # 語彙不一致を明示する
        raise ValueError(
            f"tokenizerとmodelの語彙数が一致しません: "
            f"{actual_vocab_size} != {model_config.vocab_size}"
        )
    # YAMLに固定した特殊token対応を読む
    configured_special_tokens = tokenizer_config["special_tokens"]
    # 名前から実IDへの対応を作る
    special_ids: dict[str, int] = {}
    # 全特殊tokenを順に照合する
    for name, values in configured_special_tokens.items():
        # token本文を取得する
        token = str(values["token"])
        # 期待IDを整数化する
        expected_id = int(values["id"])
        # 完成tokenizerから実IDを得る
        actual_id = tokenizer.token_to_id(token)
        # 欠落またはID差し替えを拒否する
        if actual_id != expected_id:
            # 不一致の名前と値を示す
            raise ValueError(
                f"特殊token IDが一致しません: {name}={actual_id} != {expected_id}"
            )
        # 後続検査用にIDを保存する
        special_ids[str(name)] = expected_id
    # 必須特殊tokenがすべて設定されたことを確認する
    required_names = {"pad", "bos", "eos", "unk", "task", "code"}
    # 不足名を抽出する
    missing_names = required_names - set(special_ids)
    # 不足があれば系列検証前に止める
    if missing_names:
        # 不足名を並べて例外にする
        raise ValueError(f"必須特殊tokenがありません: {sorted(missing_names)}")
    # tokenizer、特殊ID、ハッシュを返す
    return tokenizer, special_ids, tokenizer_sha256


# 訓練ZIPを固定値とCRCで検証する
def validate_source_archive(config: dict[str, Any]) -> tuple[Path, str]:
    """訓練ZIPの存在、SHA-256、member、CRCを検証する。"""

    # データ設定を取り出す
    data_config = config["data"]
    # 訓練ZIPパスを解決する
    archive_path = configured_path(data_config["archive"])
    # 入力ZIPの存在を確認する
    if not archive_path.is_file():
        # 欠落パスを明示する
        raise FileNotFoundError(f"訓練ZIPがありません: {archive_path}")
    # 処理前SHA-256を計算する
    archive_sha256 = file_sha256(archive_path)
    # 設定に固定した期待値を読む
    expected_sha256 = str(data_config["expected_sha256"])
    # 別データへの暗黙変更を拒否する
    if archive_sha256 != expected_sha256:
        # 期待値と実値を示す
        raise ValueError(
            f"訓練ZIP SHA-256が一致しません: {archive_sha256} != {expected_sha256}"
        )
    # ZIPを読み取り専用で開く
    with zipfile.ZipFile(archive_path, mode="r") as archive:
        # member名一覧を取得する
        members = archive.namelist()
        # 指定memberが一つ存在することを確認する
        if str(data_config["member"]) not in members:
            # ZIP内一覧と期待名を示す
            raise ValueError(
                f"訓練JSONL memberがありません: {data_config['member']} in {members}"
            )
        # 正式訓練ZIPでは全memberのCRCを展開検査する
        if bool(data_config.get("validate_all_members_crc", True)):
            # 最初のCRC不一致memberを取得する
            broken_member = archive.testzip()
            # CRC不一致memberがあれば拒否する
            if broken_member is not None:
                # 壊れたmember名を示す
                raise ValueError(f"入力ZIPのCRC検査に失敗しました: {broken_member}")
    # 検証済みパスとSHA-256を返す
    return archive_path, archive_sha256


# token化済み訓練例を省メモリで保持する
class TokenizedCodeDataset(Dataset[tuple[array, int]]):
    """token ID列とcode教師開始位置を保持する。"""

    # 事前token化済み例を受け取る
    def __init__(self, examples: list[tuple[array, int]]) -> None:
        # 全例を順序どおり保存する
        self.examples = examples

    # DataLoaderへ件数を返す
    def __len__(self) -> int:
        # 保持例数を返す
        return len(self.examples)

    # 指定位置のtoken列と教師開始位置を返す
    def __getitem__(self, index: int) -> tuple[array, int]:
        # 元レコード順の例を返す
        return self.examples[index]


# 全訓練レコードを固定tokenizerでtoken化する
def build_training_dataset(
    config: dict[str, Any],
    tokenizer: Tokenizer,
    special_ids: dict[str, int],
    archive_path: Path,
    archive_sha256_before: str,
) -> tuple[TokenizedCodeDataset, dict[str, Any]]:
    """入力分離条件と系列長を検証し、code-only教師例を作る。"""

    # データ設定を取り出す
    data_config = config["data"]
    # 系列テンプレートを取得する
    template = str(data_config["sequence_template"])
    # 損失範囲が意図した固定方式であることを確認する
    if str(data_config["loss_scope"]) != LOSS_SCOPE:
        # 未実装方式を黙って使わない
        raise ValueError(f"対応していないloss_scopeです: {data_config['loss_scope']}")
    # 訓練例を元レコード順に保存する
    examples: list[tuple[array, int]] = []
    # 系列token総数を数える
    sequence_token_count = 0
    # 教師信号token総数を数える
    supervised_token_count = 0
    # 最短系列長を初期化する
    minimum_length: int | None = None
    # 最長系列長を初期化する
    maximum_length = 0
    # unknown token総数を数える
    unknown_count = 0
    # 期待する固定分割条件を取得する
    required_values = data_config["required_values"]
    # ZIPを読み取り専用で開く
    with zipfile.ZipFile(archive_path, mode="r") as archive:
        # 指定JSONL memberをbinaryで開く
        with archive.open(str(data_config["member"]), mode="r") as binary_handle:
            # UTF-8 text streamへ変換する
            with io.TextIOWrapper(binary_handle, encoding="utf-8") as text_handle:
                # 全JSONL行を順に処理する
                for line_number, line in enumerate(text_handle, start=1):
                    # 空行を訓練例として扱わない
                    if not line.strip():
                        # 空行位置を明示して拒否する
                        raise ValueError(f"訓練JSONLに空行があります: {line_number}")
                    # 一行JSONを辞書として読む
                    record = json.loads(line)
                    # 評価データ混入を防ぐ固定項目を照合する
                    for key, expected_value in required_values.items():
                        # 実値を取得する
                        actual_value = record.get(key)
                        # 期待分割と異なるレコードを拒否する
                        if actual_value != expected_value:
                            # 行番号、項目、値を示す
                            raise ValueError(
                                f"訓練レコード固定値が一致しません: line={line_number}, "
                                f"{key}={actual_value!r} != {expected_value!r}"
                            )
                    # 日本語指示を文字列として取得する
                    instruction = record.get("instruction_ja")
                    # Pythonコードを文字列として取得する
                    reference_code = record.get("reference_code")
                    # 必須本文の型と空文字を検査する
                    if not isinstance(instruction, str) or not instruction:
                        # 不正行を明示する
                        raise ValueError(f"instruction_jaが不正です: line={line_number}")
                    # コードも同様に検査する
                    if not isinstance(reference_code, str) or not reference_code:
                        # 不正行を明示する
                        raise ValueError(f"reference_codeが不正です: line={line_number}")
                    # tokenizer訓練時と同じ完成系列を作る
                    sequence = template.format(
                        instruction_ja=instruction,
                        reference_code=reference_code,
                    )
                    # 自動特殊token追加を使わず明示系列をencodeする
                    token_ids = tokenizer.encode(
                        sequence, add_special_tokens=False
                    ).ids
                    # 空系列を拒否する
                    if not token_ids:
                        # 行番号を示す
                        raise ValueError(f"token化後の系列が空です: line={line_number}")
                    # 最大文脈長超過を拒否する
                    context_length = int(config["model"]["context_length"])
                    # 切り捨てず完全系列を守る
                    if len(token_ids) > context_length:
                        # 長さと行番号を示す
                        raise ValueError(
                            f"系列長が文脈長を超えました: line={line_number}, "
                            f"{len(token_ids)} > {context_length}"
                        )
                    # 必須特殊tokenごとの出現数を確認する
                    for name in ("bos", "task", "code", "eos"):
                        # 対応IDの出現数を数える
                        count = token_ids.count(special_ids[name])
                        # 各一回以外を拒否する
                        if count != 1:
                            # 行番号とtoken名を示す
                            raise ValueError(
                                f"特殊token出現数が不正です: line={line_number}, "
                                f"{name}={count}"
                            )
                    # BOSが系列先頭にあることを確認する
                    if token_ids[0] != special_ids["bos"]:
                        # テンプレート変更を拒否する
                        raise ValueError(f"BOSが系列先頭にありません: line={line_number}")
                    # EOSが系列末尾にあることを確認する
                    if token_ids[-1] != special_ids["eos"]:
                        # テンプレート変更を拒否する
                        raise ValueError(f"EOSが系列末尾にありません: line={line_number}")
                    # code marker位置を取得する
                    code_index = token_ids.index(special_ids["code"])
                    # code marker自体は教師から外し直後tokenから教師にする
                    target_start = code_index + 1
                    # 少なくともEOSを教師に含むことを確認する
                    if target_start >= len(token_ids):
                        # 不正テンプレートを拒否する
                        raise ValueError(f"code教師tokenがありません: line={line_number}")
                    # unknown出現数を加算する
                    unknown_count += token_ids.count(special_ids["unk"])
                    # 16-bit ID配列で系列を保存する
                    examples.append((array("H", token_ids), target_start))
                    # 完成系列token数を加算する
                    sequence_token_count += len(token_ids)
                    # codeとEOSの教師token数を加算する
                    supervised_token_count += len(token_ids) - target_start
                    # 最短長を更新する
                    minimum_length = (
                        len(token_ids)
                        if minimum_length is None
                        else min(minimum_length, len(token_ids))
                    )
                    # 最長長を更新する
                    maximum_length = max(maximum_length, len(token_ids))
    # 件数を期待値と照合する
    expected_count = int(data_config["expected_record_count"])
    # レコード不足・過剰を拒否する
    if len(examples) != expected_count:
        # 実件数と期待件数を示す
        raise ValueError(f"訓練件数が一致しません: {len(examples)} != {expected_count}")
    # unknownが一つでもあれば固定BPE不整合として拒否する
    if unknown_count != 0:
        # unknown総数を示す
        raise ValueError(f"訓練系列に<|unk|>が含まれます: {unknown_count}")
    # 読み取り後の入力ZIP SHA-256を再計算する
    archive_sha256_after = file_sha256(archive_path)
    # 入力を変更していないことを確認する
    if archive_sha256_after != archive_sha256_before:
        # 処理前後値を示す
        raise ValueError("訓練ZIPがデータ準備中に変更されました")
    # 3 epochなど設定回数でモデルが見るtoken数を計算する
    epochs = int(config["training"]["epochs"])
    # dataset集計を作る
    stats = {
        "record_count": len(examples),
        "sequence_token_count_per_epoch": sequence_token_count,
        "supervised_token_count_per_epoch": supervised_token_count,
        "sequence_token_count_all_epochs": sequence_token_count * epochs,
        "supervised_token_count_all_epochs": supervised_token_count * epochs,
        "minimum_sequence_length": minimum_length,
        "maximum_sequence_length": maximum_length,
        "unknown_token_count": unknown_count,
        "archive_sha256_before": archive_sha256_before,
        "archive_sha256_after": archive_sha256_after,
        "archive_unchanged": archive_sha256_before == archive_sha256_after,
    }
    # datasetと集計を返す
    return TokenizedCodeDataset(examples), stats


# batch内最大長まで右paddingする
def collate_training_batch(
    batch: list[tuple[array, int]], pad_token_id: int
) -> dict[str, torch.Tensor]:
    """可変長系列からinput、masked labels、token件数を作る。"""

    # 空batchを拒否する
    if not batch:
        # DataLoader異常を明示する
        raise ValueError("空batchはcollateできません")
    # batch内最大系列長を取得する
    maximum_length = max(len(token_ids) for token_ids, _ in batch)
    # 入力をpad IDで初期化する
    input_ids = torch.full(
        (len(batch), maximum_length), pad_token_id, dtype=torch.long
    )
    # promptとpaddingを無視するlabelsを初期化する
    labels = torch.full(
        (len(batch), maximum_length), IGNORE_INDEX, dtype=torch.long
    )
    # 非padding token数を数える
    sequence_token_count = 0
    # 教師token数を数える
    supervised_token_count = 0
    # 各例を右padding行へコピーする
    for row, (stored_ids, target_start) in enumerate(batch):
        # arrayをTensorへ変換する
        token_ids = torch.tensor(stored_ids, dtype=torch.long)
        # 実系列長を取得する
        sequence_length = token_ids.numel()
        # 入力先頭へ実tokenをコピーする
        input_ids[row, :sequence_length] = token_ids
        # code marker直後からEOSまでだけを教師labelへコピーする
        labels[row, target_start:sequence_length] = token_ids[target_start:]
        # 非padding token数を加算する
        sequence_token_count += sequence_length
        # 教師token数を加算する
        supervised_token_count += sequence_length - target_start
    # 学習loopで使うTensor辞書を返す
    return {
        "input_ids": input_ids,
        "labels": labels,
        "sequence_token_count": torch.tensor(sequence_token_count),
        "supervised_token_count": torch.tensor(supervised_token_count),
    }


# Python・PyTorch乱数を固定する
def seed_everything(seed: int) -> None:
    """モデル初期値とepochごとの順序を再現可能にする。"""

    # Python標準乱数を固定する
    random.seed(seed)
    # CPUのPyTorch乱数を固定する
    torch.manual_seed(seed)
    # CUDAが使える場合は全deviceの乱数を固定する
    if torch.cuda.is_available():
        # 全GPUのseedを揃える
        torch.cuda.manual_seed_all(seed)


# autoを含むdevice設定を解決する
def resolve_device(runtime_config: dict[str, Any]) -> torch.device:
    """設定とCUDA可用性から単一学習deviceを決める。"""

    # YAMLのdevice指定を読む
    requested = str(runtime_config["device"])
    # autoならCUDAを優先する
    if requested == "auto":
        # CUDAがあればcuda、なければcpuを返す
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # CUDA指定なのに利用できない場合を拒否する
    if requested.startswith("cuda") and not torch.cuda.is_available():
        # 実行環境不一致を示す
        raise RuntimeError("CUDAが利用できない環境でcudaが指定されました")
    # 明示device文字列をPyTorchへ渡す
    return torch.device(requested)


# 混合精度dtypeを設定から解決する
def resolve_dtype(runtime_config: dict[str, Any], device: torch.device) -> torch.dtype:
    """float32またはbfloat16を安全に選ぶ。"""

    # YAMLのdtype指定を読む
    requested = str(runtime_config["dtype"])
    # float32を明示した場合はそのまま返す
    if requested == "float32":
        # AMPを使わないdtypeを返す
        return torch.float32
    # bfloat16以外の未実装方式を拒否する
    if requested != "bfloat16":
        # 対応値を明示する
        raise ValueError("runtime.dtypeはfloat32またはbfloat16にしてください")
    # CPUでもautocast可能だが本学習はCUDAを前提にする
    if device.type == "cuda" and not torch.cuda.is_bf16_supported():
        # 精度非対応GPUで暗黙にfloat16へ落とさない
        raise RuntimeError("指定GPUはbfloat16をサポートしていません")
    # bfloat16を返す
    return torch.bfloat16


# weight decay対象と除外対象を分ける
def build_optimizer(
    model: BokuNanoForCausalLM, optimizer_config: dict[str, Any], device: torch.device
) -> torch.optim.AdamW:
    """行列parameterだけへweight decayを適用するAdamWを作る。"""

    # 2次元以上の重みをdecay対象にする
    decay_parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad and parameter.ndim >= 2
    ]
    # RMSNormなど1次元parameterをdecay対象外にする
    no_decay_parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad and parameter.ndim < 2
    ]
    # parameter groupを構成する
    parameter_groups = [
        {
            "params": decay_parameters,
            "weight_decay": float(optimizer_config["weight_decay"]),
        },
        {"params": no_decay_parameters, "weight_decay": 0.0},
    ]
    # beta値を二要素へ変換する
    betas = tuple(float(value) for value in optimizer_config["betas"])
    # beta数を検証する
    if len(betas) != 2:
        # AdamW要件を示す
        raise ValueError("optimizer.betasは二要素である必要があります")
    # CUDA時だけfused AdamWを使う
    fused = bool(optimizer_config.get("fused", True)) and device.type == "cuda"
    # AdamWを作って返す
    return torch.optim.AdamW(
        parameter_groups,
        lr=float(optimizer_config["learning_rate"]),
        betas=(betas[0], betas[1]),
        eps=float(optimizer_config["eps"]),
        fused=fused,
    )


# warmup付きcosine学習率を計算する
def learning_rate_for_step(
    step: int,
    total_steps: int,
    warmup_steps: int,
    maximum_learning_rate: float,
    minimum_learning_rate: float,
) -> float:
    """1始まりoptimizer stepに対応する学習率を返す。"""

    # warmup区間では0から最大値へ線形増加する
    if warmup_steps > 0 and step <= warmup_steps:
        # 現在割合を掛けた値を返す
        return maximum_learning_rate * step / warmup_steps
    # warmup後の進捗を0から1へ正規化する
    denominator = max(1, total_steps - warmup_steps)
    # 最終stepを超えない範囲へ丸める
    progress = min(1.0, max(0.0, (step - warmup_steps) / denominator))
    # cosine係数を1から0へ減衰させる
    cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
    # 最小学習率を下限とする値を返す
    return minimum_learning_rate + cosine * (
        maximum_learning_rate - minimum_learning_rate
    )


# optimizer全groupへ同じ学習率を設定する
def set_optimizer_learning_rate(
    optimizer: torch.optim.Optimizer, learning_rate: float
) -> None:
    """次の更新に使う学習率を全parameter groupへ反映する。"""

    # 全parameter groupを順に処理する
    for group in optimizer.param_groups:
        # 現在stepの学習率へ置き換える
        group["lr"] = learning_rate


# validation集合でcode-only lossを測る
@torch.no_grad()
def evaluate_validation_loss(
    model: Any,
    dataset: TokenizedCodeDataset,
    batch_size: int,
    pad_token_id: int,
    device: torch.device,
    training_dtype: torch.dtype,
) -> dict[str, Any]:
    """parameterを更新せずvalidation平均lossとperplexityを返す。"""

    # 評価modeへ切り替える
    model.eval()
    # 右padding collatorへpad IDを固定する
    collate_fn = partial(collate_training_batch, pad_token_id=pad_token_id)
    # 元順序のvalidation DataLoaderを作る
    data_loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=device.type == "cuda",
        collate_fn=collate_fn,
        drop_last=False,
    )
    # token重み付きloss合計を初期化する
    weighted_loss = 0.0
    # 教師token総数を初期化する
    supervised_tokens = 0
    # 全validation batchを順に処理する
    for batch in data_loader:
        # 入力を学習deviceへ移す
        input_ids = batch["input_ids"].to(device, non_blocking=True)
        # labelsも学習deviceへ移す
        labels = batch["labels"].to(device, non_blocking=True)
        # 現batchの教師token数を取得する
        batch_tokens = int(batch["supervised_token_count"].item())
        # 本学習と同じ混合精度でforwardする
        with torch.autocast(
            device_type=device.type,
            dtype=training_dtype,
            enabled=training_dtype != torch.float32,
        ):
            # validation lossを計算する
            output = model(input_ids=input_ids, labels=labels)
        # labels指定時のloss欠落を拒否する
        if output.loss is None:
            # 実装不整合を示す
            raise RuntimeError("validationでlossが返されませんでした")
        # token数を重みとしてlossを加算する
        weighted_loss += float(output.loss.item()) * batch_tokens
        # 教師token数を加算する
        supervised_tokens += batch_tokens
    # 空validation集合を拒否する
    if supervised_tokens == 0:
        # データ不整合を示す
        raise ValueError("validationの教師token数が0です")
    # 全教師tokenの平均lossを求める
    average_loss = weighted_loss / supervised_tokens
    # overflowを避けながらperplexityを求める
    perplexity = math.exp(min(average_loss, 80.0))
    # 学習modeへ戻す
    model.train()
    # 評価結果を返す
    return {
        "validation_loss": average_loss,
        "validation_perplexity": perplexity,
        "validation_supervised_tokens": supervised_tokens,
        "validation_record_count": len(dataset),
    }


# JSONを一時ファイル経由で安全に保存する
def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    """同一ディレクトリ内の一時ファイルからJSONを置き換える。"""

    # 親ディレクトリを作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 対象固有の一時パスを作る
    temporary_path = path.with_name(path.name + ".tmp")
    # UTF-8、キー順固定、末尾改行付きで保存する
    temporary_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # 完成後に同一filesystem内で置き換える
    temporary_path.replace(path)


# checkpointを一時ファイル経由で保存する
def save_training_checkpoint(
    path: Path,
    model: BokuNanoForCausalLM,
    optimizer: torch.optim.Optimizer,
    next_epoch: int,
    global_step: int,
    seen_sequence_tokens: int,
    seen_supervised_tokens: int,
) -> None:
    """epoch境界から再開するための状態を保存する。"""

    # checkpointディレクトリを作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 一時保存先を作る
    temporary_path = path.with_name(path.name + ".tmp")
    # CPUへ移したモデル状態を作る
    model_state = {
        name: tensor.detach().cpu() for name, tensor in model.state_dict().items()
    }
    # 再開に必要な状態をまとめる
    checkpoint = {
        "trainer_version": TRAINER_VERSION,
        "model_config": model.config.to_dict(),
        "model_state_dict": model_state,
        "optimizer_state_dict": optimizer.state_dict(),
        "next_epoch": next_epoch,
        "global_step": global_step,
        "seen_sequence_tokens": seen_sequence_tokens,
        "seen_supervised_tokens": seen_supervised_tokens,
    }
    # PyTorch形式で一時保存する
    torch.save(checkpoint, temporary_path)
    # 完成後に置き換える
    temporary_path.replace(path)


# safetensors形式の推論重みを安全に保存する
def save_final_weights(path: Path, model: BokuNanoForCausalLM) -> str:
    """CPUへ移した連続Tensorを保存しSHA-256を返す。"""

    # 親ディレクトリを作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 一時保存先を作る
    temporary_path = path.with_name(path.name + ".tmp")
    # safetensorsが扱える連続CPU Tensorへ変換する
    state = {
        name: tensor.detach().cpu().contiguous()
        for name, tensor in model.state_dict().items()
    }
    # 由来を最低限のmetadataへ入れて保存する
    save_safetensors(
        state,
        str(temporary_path),
        metadata={"format": "pt", "model": "Boku-nano"},
    )
    # 完成後に置き換える
    temporary_path.replace(path)
    # 完成重みのSHA-256を返す
    return file_sha256(path)


# 出力ディレクトリを安全に準備する
def prepare_output_directory(
    output_dir: Path, overwrite: bool, resume_from: Path | None
) -> None:
    """既存成果物を暗黙に上書きしない。"""

    # resume時は既存ディレクトリを維持する
    if resume_from is not None:
        # checkpointの存在を確認する
        if not resume_from.is_file():
            # 欠落パスを示す
            raise FileNotFoundError(f"再開checkpointがありません: {resume_from}")
        # 出力先を作成済みでも許可する
        output_dir.mkdir(parents=True, exist_ok=True)
        # 以降の新規出力処理を省略する
        return
    # 既存ディレクトリが空でないか確認する
    if output_dir.exists() and any(output_dir.iterdir()):
        # 明示上書きがなければ保護する
        if not overwrite:
            # 必要な選択肢を説明する
            raise FileExistsError(
                f"出力先が空ではありません: {output_dir}. "
                "置き換える場合だけ--overwriteを指定してください。"
            )
        # 明示上書き時だけ対象ディレクトリを削除する
        shutil.rmtree(output_dir)
    # 空の出力ディレクトリを作る
    output_dir.mkdir(parents=True, exist_ok=True)


# metrics JSONLへ一行追記する
def append_metric(path: Path, metric: dict[str, Any]) -> None:
    """各log時点の測定値をJSONLとして逐次保存する。"""

    # 親ディレクトリを作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 追記モードで一行JSONを保存する
    with path.open("a", encoding="utf-8") as handle:
        # キー順固定のJSONと改行を書き込む
        handle.write(json.dumps(metric, ensure_ascii=False, sort_keys=True) + "\n")


# 設定と固定成果物だけを検査する
def validate_configuration(
    config_path: Path, output_override: Path | None
) -> dict[str, Any]:
    """本学習前にモデル規模、tokenizer、訓練ZIPを照合する。"""

    # YAMLを読み込む
    config = load_config(config_path)
    # CLI出力先があれば設定辞書のcopyへ反映する
    if output_override is not None:
        # output sectionをcopyする
        config["output"] = dict(config["output"])
        # 実行時出力先を保存する
        config["output"]["directory"] = str(output_override)
    # モデル設定を検証する
    model_config = BokuNanoConfig.from_dict(config["model"])
    # tokenizer固定条件を検証する
    _, special_ids, tokenizer_sha256 = validate_tokenizer(config, model_config)
    # 訓練ZIP固定条件を検証する
    archive_path, archive_sha256 = validate_source_archive(config)
    # validation sectionだけをdataとして見る一時設定を作る
    validation_view = dict(config)
    # hidden集合を開かずvalidation memberだけを指定する
    validation_view["data"] = config["validation_data"]
    # validation ZIPの固定条件を検証する
    validation_archive_path, validation_archive_sha256 = validate_source_archive(
        validation_view
    )
    # seedを固定してparameter数も再現可能にする
    seed_everything(int(config["training"]["seed"]))
    # CPU上でモデルをランダム初期化する
    model = BokuNanoForCausalLM(model_config)
    # 学習parameter数を数える
    parameter_count = model.parameter_count()
    # 期待parameter数があれば照合する
    expected_parameter_count = int(config["model_validation"]["expected_parameter_count"])
    # アーキテクチャの意図しない変更を拒否する
    if parameter_count != expected_parameter_count:
        # 実値と期待値を示す
        raise ValueError(
            f"parameter数が一致しません: {parameter_count} != {expected_parameter_count}"
        )
    # 検証結果を返す
    return {
        "config_path": display_path(config_path),
        "output_directory": display_path(configured_path(config["output"]["directory"])),
        "model_config": model_config.to_dict(),
        "parameter_count": parameter_count,
        "tokenizer_sha256": tokenizer_sha256,
        "tokenizer_special_ids": special_ids,
        "source_archive": display_path(archive_path),
        "source_archive_sha256": archive_sha256,
        "validation_archive": display_path(validation_archive_path),
        "validation_archive_sha256": validation_archive_sha256,
    }


# 本学習を実行する
def train(
    config_path: Path,
    output_override: Path | None,
    overwrite: bool,
    resume_from: Path | None,
    max_steps_override: int | None,
) -> dict[str, Any]:
    """データ全件を3 epoch学習し、checkpointとmanifestを保存する。"""

    # 設定と固定成果物を先に検証する
    validate_configuration(config_path, output_override)
    # YAMLをもう一度読み込む
    config = load_config(config_path)
    # CLI出力先があれば実行設定へ反映する
    if output_override is not None:
        # output sectionをcopyする
        config["output"] = dict(config["output"])
        # 実行時出力先を保存する
        config["output"]["directory"] = str(output_override)
    # 出力先を解決する
    output_dir = configured_path(config["output"]["directory"])
    # 既存成果物を保護しながら出力先を準備する
    prepare_output_directory(output_dir, overwrite, resume_from)
    # 実行開始UTC時刻を保存する
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # 経過時間測定を開始する
    started_monotonic = time.monotonic()
    # モデル設定を作る
    model_config = BokuNanoConfig.from_dict(config["model"])
    # tokenizerを再読込みする
    tokenizer, special_ids, tokenizer_sha256 = validate_tokenizer(config, model_config)
    # 訓練ZIPを再確認する
    archive_path, archive_sha256 = validate_source_archive(config)
    # 全レコードをtoken化して分離・長さを検証する
    dataset, dataset_stats = build_training_dataset(
        config,
        tokenizer,
        special_ids,
        archive_path,
        archive_sha256,
    )
    # validation sectionだけをdataとして扱う一時設定を作る
    validation_view = dict(config)
    # validation memberと固定条件を設定する
    validation_view["data"] = config["validation_data"]
    # 集計上はvalidationを一回だけ読むためepoch数を1へする
    validation_view["training"] = dict(config["training"], epochs=1)
    # validation ZIPのSHA-256とmemberを検証する
    validation_archive_path, validation_archive_sha256 = validate_source_archive(
        validation_view
    )
    # validationだけをtoken化し、hidden 5集合は読み込まない
    validation_dataset, validation_dataset_stats = build_training_dataset(
        validation_view,
        tokenizer,
        special_ids,
        validation_archive_path,
        validation_archive_sha256,
    )
    # seedをモデル初期化前に固定する
    seed = int(config["training"]["seed"])
    # 全乱数を固定する
    seed_everything(seed)
    # 学習deviceを決める
    device = resolve_device(config["runtime"])
    # 学習dtypeを決める
    training_dtype = resolve_dtype(config["runtime"], device)
    # CUDA上のfloat32行列積でTF32を許可する
    if device.type == "cuda":
        # matmul精度と速度のバランスを高設定にする
        torch.set_float32_matmul_precision("high")
    # モデルをランダム初期化する
    model = BokuNanoForCausalLM(model_config)
    # parameter数を記録する
    parameter_count = model.parameter_count()
    # モデルを学習deviceへ移す
    model.to(device)
    # optimizerを作る
    optimizer = build_optimizer(model, config["optimizer"], device)
    # 訓練設定を取り出す
    training_config = config["training"]
    # micro batch sizeを読む
    micro_batch_size = int(training_config["micro_batch_size"])
    # gradient accumulation回数を読む
    accumulation_steps = int(training_config["gradient_accumulation_steps"])
    # 不正batch設定を拒否する
    if micro_batch_size <= 0 or accumulation_steps <= 0:
        # 必須範囲を示す
        raise ValueError("batch sizeとgradient accumulationは正の整数にしてください")
    # 1 epochのmicro batch数を切り上げ計算する
    batches_per_epoch = math.ceil(len(dataset) / micro_batch_size)
    # 1 epochのoptimizer step数を切り上げ計算する
    optimizer_steps_per_epoch = math.ceil(batches_per_epoch / accumulation_steps)
    # epoch数を読む
    epochs = int(training_config["epochs"])
    # 全optimizer step数を求める
    configured_total_steps = optimizer_steps_per_epoch * epochs
    # smoke test指定があれば全stepを上限で切る
    total_steps = (
        min(configured_total_steps, max_steps_override)
        if max_steps_override is not None
        else configured_total_steps
    )
    # 最大stepの正値を検証する
    if total_steps <= 0:
        # 不正overrideを拒否する
        raise ValueError("総optimizer step数は正である必要があります")
    # warmup step数を割合から切り上げる
    warmup_steps = math.ceil(
        configured_total_steps * float(config["optimizer"]["warmup_ratio"])
    )
    # 再開前のepochを初期化する
    start_epoch = 0
    # optimizer stepを初期化する
    global_step = 0
    # 実際に読んだ系列token数を初期化する
    seen_sequence_tokens = 0
    # 実際に損失へ使ったtoken数を初期化する
    seen_supervised_tokens = 0
    # checkpoint再開が指定された場合に状態を復元する
    if resume_from is not None:
        # ローカルの信頼済みcheckpointをCPUへ読む
        checkpoint = torch.load(resume_from, map_location="cpu", weights_only=True)
        # モデル設定が完全一致することを確認する
        if checkpoint["model_config"] != model_config.to_dict():
            # 異なる構造への再開を拒否する
            raise ValueError("checkpointのmodel_configが現在設定と一致しません")
        # モデルparameterを復元する
        model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        # optimizer状態を復元する
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        # optimizer Tensorを現在deviceへ移す
        for optimizer_state in optimizer.state.values():
            # state内の各値を処理する
            for key, value in optimizer_state.items():
                # Tensorだけをdeviceへ移す
                if isinstance(value, torch.Tensor):
                    # 同じキーへ移動済みTensorを保存する
                    optimizer_state[key] = value.to(device)
        # 次に開始するepochを読む
        start_epoch = int(checkpoint["next_epoch"])
        # optimizer stepを復元する
        global_step = int(checkpoint["global_step"])
        # 系列token数を復元する
        seen_sequence_tokens = int(checkpoint["seen_sequence_tokens"])
        # 教師token数を復元する
        seen_supervised_tokens = int(checkpoint["seen_supervised_tokens"])
    # metrics保存先を作る
    metrics_path = output_dir / "training_metrics.jsonl"
    # 新規実行では古いmetricsを残さない
    if resume_from is None and metrics_path.exists():
        # 出力初期化後なので対象ファイルだけ削除する
        metrics_path.unlink()
    # 解決済み設定を保存する
    resolved_config_path = output_dir / "training_config.yaml"
    # YAMLをclone可能な相対パスのまま保存する
    resolved_config_path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    # 実行中manifestを作る
    manifest: dict[str, Any] = {
        "trainer_version": TRAINER_VERSION,
        "status": "running",
        "started_at": started_at,
        "completed_at": None,
        "config_path": display_path(config_path),
        "model_config": model_config.to_dict(),
        "parameter_count": parameter_count,
        "tokenizer_path": display_path(configured_path(config["tokenizer"]["path"])),
        "tokenizer_sha256": tokenizer_sha256,
        "source_archive": display_path(archive_path),
        "source_archive_sha256": archive_sha256,
        "dataset": dataset_stats,
        "validation_archive": display_path(validation_archive_path),
        "validation_archive_sha256": validation_archive_sha256,
        "validation_dataset": validation_dataset_stats,
        "epochs": epochs,
        "configured_optimizer_steps": configured_total_steps,
        "effective_optimizer_steps": total_steps,
        "micro_batch_size": micro_batch_size,
        "gradient_accumulation_steps": accumulation_steps,
        "effective_batch_size": micro_batch_size * accumulation_steps,
        "loss_scope": LOSS_SCOPE,
        "seed": seed,
        "device": str(device),
        "dtype": str(training_dtype).replace("torch.", ""),
        "max_steps_override": max_steps_override,
        "resume_from": display_path(resume_from) if resume_from is not None else None,
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "tokenizers": package_version("tokenizers"),
            "pyyaml": package_version("pyyaml"),
            "safetensors": package_version("safetensors"),
        },
    }
    # 実行前manifestを保存する
    write_json_atomic(output_dir / "training_manifest.json", manifest)
    # 設定に応じてモデルをcompileする
    training_model: Any = model
    # compileは性能実験として明示時だけ有効にする
    if bool(config["runtime"].get("compile", False)):
        # PyTorch compilerでforward/backwardを最適化する
        training_model = torch.compile(model)
    # モデルをtrain modeへ切り替える
    training_model.train()
    # optimizer gradientをNoneへ初期化する
    optimizer.zero_grad(set_to_none=True)
    # log間のloss合計を初期化する
    rolling_loss = 0.0
    # log間のmicro batch数を初期化する
    rolling_batches = 0
    # log間の教師token数を初期化する
    rolling_supervised_tokens = 0
    # log間の開始時刻を記録する
    rolling_started = time.monotonic()
    # 完了判定を初期化する
    reached_step_limit = global_step >= total_steps
    # epoch境界から順に学習する
    for epoch in range(start_epoch, epochs):
        # すでにstep上限へ達したらepochを開始しない
        if reached_step_limit:
            # 外側loopを終了する
            break
        # epochごとの決定的shuffle generatorを作る
        generator = torch.Generator()
        # epoch番号を加えたseedを固定する
        generator.manual_seed(seed + epoch)
        # 右padding collatorへpad IDを固定する
        collate_fn = partial(
            collate_training_batch, pad_token_id=special_ids["pad"]
        )
        # 現epochのDataLoaderを作る
        data_loader = DataLoader(
            dataset,
            batch_size=micro_batch_size,
            shuffle=bool(training_config["shuffle"]),
            generator=generator,
            num_workers=int(config["runtime"]["num_workers"]),
            pin_memory=bool(config["runtime"]["pin_memory"]) and device.type == "cuda",
            collate_fn=collate_fn,
            drop_last=False,
        )
        # 現epochのmicro batchを順に処理する
        for batch_index, batch in enumerate(data_loader):
            # 入力を非同期転送可能な形でdeviceへ移す
            input_ids = batch["input_ids"].to(device, non_blocking=True)
            # labelsも同じdeviceへ移す
            labels = batch["labels"].to(device, non_blocking=True)
            # accumulation末尾またはepoch最終batchか判定する
            is_epoch_last_batch = batch_index + 1 == len(data_loader)
            # 今回更新するか判定する
            should_update = (batch_index + 1) % accumulation_steps == 0 or is_epoch_last_batch
            # bfloat16時だけautocastを有効にする
            with torch.autocast(
                device_type=device.type,
                dtype=training_dtype,
                enabled=training_dtype != torch.float32,
            ):
                # logitsとcode-only lossを計算する
                output = training_model(input_ids=input_ids, labels=labels)
                # labels指定時にlossがない異常を拒否する
                if output.loss is None:
                    # 実装不整合を示す
                    raise RuntimeError("labels指定時にlossが返されませんでした")
                # accumulation回数で割ってgradient規模を揃える
                scaled_loss = output.loss / accumulation_steps
            # gradientを計算する
            scaled_loss.backward()
            # log用に割る前のlossを加算する
            rolling_loss += float(output.loss.detach().item())
            # log用batch数を加算する
            rolling_batches += 1
            # 実際に読んだ非padding token数を加算する
            seen_sequence_tokens += int(batch["sequence_token_count"].item())
            # 実際の教師token数を加算する
            batch_supervised_tokens = int(batch["supervised_token_count"].item())
            # 累積教師token数へ加算する
            seen_supervised_tokens += batch_supervised_tokens
            # log区間の教師token数へ加算する
            rolling_supervised_tokens += batch_supervised_tokens
            # accumulation途中ならparameter更新を延期する
            if not should_update:
                # 次micro batchへ進む
                continue
            # 次のoptimizer step番号を求める
            next_step = global_step + 1
            # warmup + cosineの現在学習率を計算する
            learning_rate = learning_rate_for_step(
                next_step,
                configured_total_steps,
                warmup_steps,
                float(config["optimizer"]["learning_rate"]),
                float(config["optimizer"]["minimum_learning_rate"]),
            )
            # optimizerへ現在学習率を設定する
            set_optimizer_learning_rate(optimizer, learning_rate)
            # gradient normを設定上限へclipする
            gradient_norm = torch.nn.utils.clip_grad_norm_(
                model.parameters(), float(config["optimizer"]["gradient_clip_norm"])
            )
            # parameterを更新する
            optimizer.step()
            # 次step用にgradientを解放する
            optimizer.zero_grad(set_to_none=True)
            # optimizer stepを確定する
            global_step = next_step
            # 定期logまたは最終stepか判定する
            should_log = (
                global_step % int(config["runtime"]["log_every_steps"]) == 0
                or global_step == total_steps
            )
            # log対象ならmetricsを保存する
            if should_log:
                # log区間時間を計算する
                now = time.monotonic()
                # 開始からの経過秒を計算する
                elapsed = now - started_monotonic
                # 区間時間を0除算しないよう下限を置く
                interval_seconds = max(now - rolling_started, 1.0e-9)
                # 測定値をまとめる
                metric = {
                    "epoch": epoch + 1,
                    "global_step": global_step,
                    "loss": rolling_loss / max(1, rolling_batches),
                    "learning_rate": learning_rate,
                    "gradient_norm": float(gradient_norm.detach().item()),
                    "seen_sequence_tokens": seen_sequence_tokens,
                    "seen_supervised_tokens": seen_supervised_tokens,
                    "elapsed_seconds": elapsed,
                    "supervised_tokens_per_second_since_last_log": (
                        rolling_supervised_tokens / interval_seconds
                    ),
                }
                # JSONLへ追記する
                append_metric(metrics_path, metric)
                # 端末へ一行表示する
                print(json.dumps(metric, ensure_ascii=False, sort_keys=True), flush=True)
                # rolling lossをリセットする
                rolling_loss = 0.0
                # rolling batch数をリセットする
                rolling_batches = 0
                # rolling教師token数をリセットする
                rolling_supervised_tokens = 0
                # 次区間の開始時刻を更新する
                rolling_started = now
            # step上限へ達したら終了する
            if global_step >= total_steps:
                # 完了フラグを立てる
                reached_step_limit = True
                # batch loopを抜ける
                break
        # 完全なepochを終えた場合だけ再開checkpointを保存する
        completed_epoch = is_epoch_last_batch
        # 正式設定時は各epoch後にvalidation lossを測定する
        if completed_epoch and bool(training_config["validate_after_each_epoch"]):
            # parameter更新なしで固定validationを評価する
            validation_metric = evaluate_validation_loss(
                training_model,
                validation_dataset,
                int(training_config["validation_batch_size"]),
                special_ids["pad"],
                device,
                training_dtype,
            )
            # epochとstepを評価記録へ追加する
            validation_metric.update(
                {"event": "validation", "epoch": epoch + 1, "global_step": global_step}
            )
            # metrics JSONLへ追記する
            append_metric(metrics_path, validation_metric)
            # 端末にも一行表示する
            print(
                json.dumps(validation_metric, ensure_ascii=False, sort_keys=True),
                flush=True,
            )
        # 完全なepochを終えた場合だけ再開checkpointを保存する
        if completed_epoch:
            # epoch番号付きcheckpointパスを作る
            checkpoint_path = output_dir / "checkpoints" / f"epoch_{epoch + 1:02d}.pt"
            # 次epochから再開できる状態を保存する
            save_training_checkpoint(
                checkpoint_path,
                model,
                optimizer,
                epoch + 1,
                global_step,
                seen_sequence_tokens,
                seen_supervised_tokens,
            )
        # step上限なら次epochへ進まない
        if reached_step_limit:
            # epoch loopを抜ける
            break
    # 正式3 epochを全step終えたか判定する
    completed_full_training = global_step >= configured_total_steps
    # 現在重みを最終safetensorsへ保存する
    model_path = output_dir / "model.safetensors"
    # 保存してSHA-256を得る
    model_sha256 = save_final_weights(model_path, model)
    # 推論に必要なモデル設定を保存する
    write_json_atomic(output_dir / "model_config.json", model_config.to_dict())
    # 実行完了時刻を保存する
    completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # manifestを最終状態へ更新する
    manifest.update(
        {
            "status": "completed" if completed_full_training else "stopped_at_max_steps",
            "completed_at": completed_at,
            "elapsed_seconds": time.monotonic() - started_monotonic,
            "global_step": global_step,
            "seen_sequence_tokens": seen_sequence_tokens,
            "seen_supervised_tokens": seen_supervised_tokens,
            "model_path": display_path(model_path),
            "model_sha256": model_sha256,
        }
    )
    # 最終manifestを安全に保存する
    write_json_atomic(output_dir / "training_manifest.json", manifest)
    # 完成結果を返す
    return manifest


# CLI入口を定義する
def main() -> None:
    """設定検査または本学習を実行して結果を表示する。"""

    # CLI引数を読む
    args = parse_args()
    # max stepsの不正値を早期に拒否する
    if args.max_steps is not None and args.max_steps <= 0:
        # CLI利用誤りを示す
        raise ValueError("--max-stepsは正の整数にしてください")
    # 設定検査だけならGPU学習と全件token化を行わない
    if args.validate_config:
        # 固定成果物とモデル構造を検証する
        result = validate_configuration(args.config, args.output_dir)
    # 通常時は本学習を実行する
    else:
        # 全件をtoken化して学習する
        result = train(
            config_path=args.config,
            output_override=args.output_dir,
            overwrite=args.overwrite,
            resume_from=args.resume_from,
            max_steps_override=args.max_steps,
        )
    # 最終結果を読みやすいJSONで表示する
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


# 直接実行時だけCLI入口を呼ぶ
if __name__ == "__main__":
    # 学習または検証を開始する
    main()
