"""最終訓練データだけからBPEまたはUnigramトークナイザを学習する。"""

# 将来のPythonでも現在の型注釈をそのまま評価できるようにする
from __future__ import annotations

# コマンドライン引数を解析するために使う
import argparse
# 語彙使用回数を集計するために使う
from collections import Counter
# SHA-256を計算するために使う
import hashlib
# ZIP内JSONLをUTF-8テキストとして読むために使う
import io
# JSONとJSONLを読み書きするために使う
import json
# 一時ディレクトリを完成ディレクトリへ置き換えるために使う
import os
# 入出力パスを扱うために使う
from pathlib import Path
# 上書き時に対象出力ディレクトリだけを削除するために使う
import shutil
# Python実行版を記録するために使う
import sys
# テンプレートの置換項目を検査するために使う
from string import Formatter
# 一時ディレクトリを安全に管理するために使う
import tempfile
# 任意のJSON値とiteratorの型注釈に使う
from typing import Any, Iterator
# 訓練データZIPをストリーム読込みするために使う
import zipfile

# YAML設定を安全に読み書きするために使う
import yaml
# 高速なBPE・Unigram実装を使う
from tokenizers import Tokenizer, decoders, models, normalizers, pre_tokenizers, trainers
# tokenizersライブラリ版を来歴へ保存する
from tokenizers import __version__ as tokenizers_version


# 生成器の版を固定する
GENERATOR_VERSION = "1"
# 必須特殊トークン名を定義する
REQUIRED_SPECIAL_TOKEN_NAMES = (
    "pad",
    "bos",
    "eos",
    "unk",
    "task",
    "code",
    "explanation",
)
# sequence templateで使用できる項目を制限する
ALLOWED_TEMPLATE_FIELDS = {"instruction_ja", "reference_code"}


# CLI引数を作る
def parse_args() -> argparse.Namespace:
    """YAML設定、出力上書き、設定検査だけの実行を受け取る。"""

    # 引数解析器を作る
    parser = argparse.ArgumentParser(
        description="訓練データだけからBPEまたはUnigramトークナイザを作成します。"
    )
    # YAML設定ファイルを必須にする
    parser.add_argument("--config", required=True, type=Path)
    # YAMLの出力先を一時的に差し替えられるようにする
    parser.add_argument("--output-dir", type=Path)
    # 既存出力を明示的に置き換える場合だけ指定する
    parser.add_argument("--overwrite", action="store_true")
    # 設定と入力だけを確認し、モデル学習を行わない選択肢を用意する
    parser.add_argument("--validate-config", action="store_true")
    # 解析済み引数を返す
    return parser.parse_args()


# JSONを再現可能な一行文字列へ変換する
def canonical_json(value: Any) -> str:
    """キー順と区切りを固定したJSON文字列を返す。"""

    # ASCII化せず最小区切りで返す
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# UTF-8文字列のSHA-256を計算する
def text_sha256(value: str) -> str:
    """文字列をUTF-8へ変換してSHA-256を返す。"""

    # ハッシュを16進文字列で返す
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ファイルをストリーム処理してSHA-256を計算する
def file_sha256(path: Path) -> str:
    """大容量ファイルを一括読込みせずSHA-256を返す。"""

    # SHA-256状態を初期化する
    digest = hashlib.sha256()
    # バイナリ入力を開く
    with path.open("rb") as handle:
        # 1 MiBずつ末尾まで読む
        while chunk := handle.read(1024 * 1024):
            # 現在の断片をハッシュへ加える
            digest.update(chunk)
    # 完成した16進ハッシュを返す
    return digest.hexdigest()


# リポジトリ内のパスを移植可能な相対表記へ変換する
def display_path(path: Path) -> str:
    """現在の作業ディレクトリ内なら相対パス、それ以外なら絶対パスを返す。"""

    # 正規化済みパスを作る
    resolved = path.resolve()
    # 現在の作業ディレクトリからの相対化を試す
    try:
        # clone先に依存しないPOSIX相対パスを返す
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    # リポジトリ外のテスト入力などは絶対パスを維持する
    except ValueError:
        # 正規化済み絶対パスを返す
        return str(resolved)


# object型設定項目を取得する
def require_mapping(value: Any, label: str) -> dict[str, Any]:
    """値がobjectでなければ設定エラーにする。"""

    # dict以外を拒否する
    if not isinstance(value, dict):
        # 問題の項目を明示する
        raise ValueError(f"{label}はobjectで指定してください")
    # 型を確認した値を返す
    return value


# 空でない文字列設定を取得する
def require_string(value: Any, label: str) -> str:
    """値が空でない文字列でなければ設定エラーにする。"""

    # 空文字列と文字列以外を拒否する
    if not isinstance(value, str) or not value:
        # 問題の項目を明示する
        raise ValueError(f"{label}は空でない文字列で指定してください")
    # 型を確認した値を返す
    return value


# bool設定を取得する
def require_bool(value: Any, label: str) -> bool:
    """値がboolでなければ設定エラーにする。"""

    # intをboolとして受け付けない
    if not isinstance(value, bool):
        # 問題の項目を明示する
        raise ValueError(f"{label}はtrueまたはfalseで指定してください")
    # 型を確認した値を返す
    return value


# 正の整数設定を取得する
def require_positive_int(value: Any, label: str) -> int:
    """boolではない正の整数を返す。"""

    # 0以下と整数以外を拒否する
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        # 問題の項目を明示する
        raise ValueError(f"{label}は正の整数で指定してください")
    # 型を確認した値を返す
    return value


# リポジトリ基準の設定パスを解決する
def resolve_config_path(value: Any, label: str) -> Path:
    """設定の相対パスを現在の作業ディレクトリ基準で解決する。"""

    # パス文字列を検査する
    raw_path = require_string(value, label)
    # Pathへ変換する
    path = Path(raw_path)
    # 相対パスなら実行ディレクトリを付ける
    if not path.is_absolute():
        # 現在の作業ディレクトリ基準で解決する
        path = Path.cwd() / path
    # 絶対パスへ正規化して返す
    return path.resolve()


# YAML設定を読み込んで構造を検査する
def load_and_validate_config(path: Path) -> dict[str, Any]:
    """BPEとUnigramに共通の設定を検査して返す。"""

    # 設定ファイルの存在を確認する
    if not path.is_file():
        # 欠落パスを明示する
        raise FileNotFoundError(path)
    # YAMLを安全なloaderで読み込む
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    # ルートobjectを検査する
    config = require_mapping(loaded, "設定ルート")
    # 設定版を確認する
    if config.get("version") != 1:
        # 未対応版を拒否する
        raise ValueError("versionは1を指定してください")
    # 主要セクションをすべて検査する
    source = require_mapping(config.get("source"), "source")
    # コーパス設定を検査する
    corpus = require_mapping(config.get("corpus"), "corpus")
    # 正規化設定を検査する
    normalizer_config = require_mapping(config.get("normalizer"), "normalizer")
    # 事前分割設定を検査する
    pre_tokenizer_config = require_mapping(
        config.get("pre_tokenizer"), "pre_tokenizer"
    )
    # モデル設定を検査する
    model = require_mapping(config.get("model"), "model")
    # 系列設定を検査する
    sequence = require_mapping(config.get("sequence"), "sequence")
    # 検証設定を検査する
    validation = require_mapping(config.get("validation"), "validation")
    # 出力設定を検査する
    output = require_mapping(config.get("output"), "output")
    # 入力ZIPパス文字列を検査する
    require_string(source.get("archive"), "source.archive")
    # ZIP内JSONL名を検査する
    require_string(source.get("member"), "source.member")
    # 期待SHA-256を検査する
    expected_sha256 = require_string(
        source.get("expected_archive_sha256"), "source.expected_archive_sha256"
    )
    # SHA-256の形式を検査する
    if len(expected_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_sha256
    ):
        # 不正ハッシュを拒否する
        raise ValueError("source.expected_archive_sha256は小文字64桁で指定してください")
    # 期待レコード数を検査する
    require_positive_int(source.get("expected_record_count"), "source.expected_record_count")
    # 必須値対応を検査する
    require_mapping(source.get("required_values"), "source.required_values")
    # コーパス項目一覧を取得する
    fields = corpus.get("fields")
    # 必ず指示とコードの2項目だけに限定する
    if fields != ["instruction_ja", "reference_code"]:
        # メタデータ混入を拒否する
        raise ValueError(
            "corpus.fieldsはinstruction_jaとreference_codeの順で指定してください"
        )
    # 項目別重複除去設定を検査する
    deduplicate = require_mapping(corpus.get("deduplicate"), "corpus.deduplicate")
    # 2項目のboolを確認する
    for field in fields:
        # 項目ごとの真偽値を検査する
        require_bool(deduplicate.get(field), f"corpus.deduplicate.{field}")
    # 正規化方式を制限する
    if normalizer_config.get("type") not in {"identity", "nfc"}:
        # コードを壊し得る未確認方式を拒否する
        raise ValueError("normalizer.typeはidentityまたはnfcを指定してください")
    # ByteLevel以外を拒否する
    if pre_tokenizer_config.get("type") != "byte_level":
        # 日本語とコードの共通byte表現を必須にする
        raise ValueError("pre_tokenizer.typeはbyte_levelを指定してください")
    # prefix space設定を検査する
    require_bool(
        pre_tokenizer_config.get("add_prefix_space"),
        "pre_tokenizer.add_prefix_space",
    )
    # 正規表現分割設定を検査する
    require_bool(pre_tokenizer_config.get("use_regex"), "pre_tokenizer.use_regex")
    # 全byte alphabet指定を必須にする
    if pre_tokenizer_config.get("initial_alphabet") != "byte_level_256":
        # 未知byteを作り得る設定を拒否する
        raise ValueError("pre_tokenizer.initial_alphabetはbyte_level_256を指定してください")
    # モデル種類を取得する
    model_type = model.get("type")
    # BPEとUnigramだけを許可する
    if model_type not in {"bpe", "unigram"}:
        # 未対応モデルを拒否する
        raise ValueError("model.typeはbpeまたはunigramを指定してください")
    # 語彙数を検査する
    vocab_size = require_positive_int(model.get("vocab_size"), "model.vocab_size")
    # byte fallbackを必須にする
    if require_bool(model.get("byte_fallback"), "model.byte_fallback") is not True:
        # 課題方針に反する設定を拒否する
        raise ValueError("model.byte_fallbackはtrueを指定してください")
    # 未知トークンを検査する
    unk_token = require_string(model.get("unk_token"), "model.unk_token")
    # BPE固有設定を検査する
    if model_type == "bpe":
        # 最小頻度を正の整数として検査する
        require_positive_int(model.get("min_frequency"), "model.min_frequency")
        # 最大piece長を検査する
        require_positive_int(model.get("max_token_length"), "model.max_token_length")
        # dropoutを数値として検査する
        dropout = model.get("dropout")
        # 0以上1未満だけを許可する
        if isinstance(dropout, bool) or not isinstance(dropout, (int, float)) or not 0 <= dropout < 1:
            # 不正確率を拒否する
            raise ValueError("model.dropoutは0以上1未満で指定してください")
    # Unigram固有設定を検査する
    else:
        # 縮小率を取得する
        shrinking_factor = model.get("shrinking_factor")
        # 0より大きく1未満に制限する
        if (
            isinstance(shrinking_factor, bool)
            or not isinstance(shrinking_factor, (int, float))
            or not 0 < shrinking_factor < 1
        ):
            # 不正縮小率を拒否する
            raise ValueError("model.shrinking_factorは0より大きく1未満で指定してください")
        # 最大piece長を検査する
        require_positive_int(model.get("max_piece_length"), "model.max_piece_length")
        # EM反復回数を検査する
        require_positive_int(model.get("n_sub_iterations"), "model.n_sub_iterations")
    # 特殊トークン設定を取得する
    special_tokens = config.get("special_tokens")
    # listであることを確認する
    if not isinstance(special_tokens, list):
        # object一覧以外を拒否する
        raise ValueError("special_tokensはlistで指定してください")
    # 名前、文字列、IDを保存する
    names: list[str] = []
    # トークン本文を保存する
    tokens: list[str] = []
    # IDを保存する
    ids: list[int] = []
    # 特殊トークンを一件ずつ検査する
    for index, item in enumerate(special_tokens):
        # objectへ変換する
        special = require_mapping(item, f"special_tokens[{index}]")
        # 名前を保存する
        names.append(require_string(special.get("name"), f"special_tokens[{index}].name"))
        # 本文を保存する
        tokens.append(require_string(special.get("token"), f"special_tokens[{index}].token"))
        # IDが0以上の整数であることを確認する
        special_id = special.get("id")
        # boolや負数を拒否する
        if isinstance(special_id, bool) or not isinstance(special_id, int) or special_id < 0:
            # 不正IDを拒否する
            raise ValueError(f"special_tokens[{index}].idは0以上の整数で指定してください")
        # IDを保存する
        ids.append(special_id)
    # 必須名を順番どおり要求する
    if tuple(names) != REQUIRED_SPECIAL_TOKEN_NAMES:
        # 意味とIDのずれを拒否する
        raise ValueError("special_tokensのnameと順序が規定と一致しません")
    # IDを0からの連番に固定する
    if ids != list(range(len(ids))):
        # 後付け特殊トークンによる語彙ずれを拒否する
        raise ValueError("special_tokens.idは0からの連番で指定してください")
    # 本文重複を拒否する
    if len(set(tokens)) != len(tokens):
        # 衝突を明示する
        raise ValueError("special_tokens.tokenが重複しています")
    # 未知トークン設定と特殊トークンを照合する
    if tokens[names.index("unk")] != unk_token:
        # unknown IDずれを拒否する
        raise ValueError("model.unk_tokenとunk特殊トークンが一致しません")
    # byte alphabetと特殊トークンを収められることを確認する
    if vocab_size < 256 + len(tokens):
        # 最小語彙数未満を拒否する
        raise ValueError("model.vocab_sizeは256 byteと特殊トークンを収める必要があります")
    # 系列テンプレートを取得する
    template = require_string(sequence.get("template"), "sequence.template")
    # テンプレート項目を抽出する
    template_fields = {
        field_name
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name is not None
    }
    # 許可した2項目がちょうど存在することを確認する
    if template_fields != ALLOWED_TEMPLATE_FIELDS:
        # 欠落やメタデータ混入を拒否する
        raise ValueError("sequence.templateはinstruction_jaとreference_codeだけを使用してください")
    # 必須特殊トークン名一覧を取得する
    required_sequence_tokens = sequence.get("required_special_tokens")
    # listかつ既知名だけであることを確認する
    if (
        not isinstance(required_sequence_tokens, list)
        or not required_sequence_tokens
        or any(name not in names for name in required_sequence_tokens)
    ):
        # 不正一覧を拒否する
        raise ValueError("sequence.required_special_tokensが不正です")
    # 指定した特殊トークンがテンプレートに一度ずつあることを確認する
    special_by_name = dict(zip(names, tokens, strict=True))
    # 必須名を一件ずつ調べる
    for name in required_sequence_tokens:
        # 対応本文が一度だけあることを要求する
        if template.count(special_by_name[name]) != 1:
            # テンプレート不正を明示する
            raise ValueError(f"sequence.template内の{name}特殊トークン数が1ではありません")
    # 最大系列長を検査する
    require_positive_int(validation.get("model_max_length"), "validation.model_max_length")
    # 検証batch sizeを検査する
    require_positive_int(validation.get("batch_size"), "validation.batch_size")
    # 検証真偽値を一件ずつ確認する
    for key in (
        "require_exact_vocab_size",
        "require_roundtrip",
        "require_zero_unk",
        "fail_on_overlength",
    ):
        # boolを要求する
        require_bool(validation.get(key), f"validation.{key}")
    # 出力ディレクトリ文字列を検査する
    require_string(output.get("directory"), "output.directory")
    # 検査済み設定を返す
    return config


# 設定から特殊トークン対応を作る
def special_token_maps(config: dict[str, Any]) -> tuple[list[str], dict[str, str], dict[str, int]]:
    """ID順本文一覧、名前別本文、名前別IDを返す。"""

    # ID順に並べる
    ordered = sorted(config["special_tokens"], key=lambda item: item["id"])
    # 本文一覧を作る
    tokens = [item["token"] for item in ordered]
    # 名前別本文対応を作る
    by_name = {item["name"]: item["token"] for item in ordered}
    # 名前別ID対応を作る
    ids_by_name = {item["name"]: item["id"] for item in ordered}
    # 3種類の対応を返す
    return tokens, by_name, ids_by_name


# ZIP内の訓練レコードを順番どおり返す
def iter_training_records(
    archive_path: Path, member: str, expected_count: int, required_values: dict[str, Any]
) -> Iterator[dict[str, Any]]:
    """最終訓練JSONLだけを検査しながらストリーム読込みする。"""

    # 入力ZIPを開く
    with zipfile.ZipFile(archive_path) as archive:
        # 必須メンバーの存在を確認する
        if member not in archive.namelist():
            # 欠落名を明示する
            raise ValueError(f"入力ZIPに必要なメンバーがありません: {member}")
        # ZIP内バイナリを開く
        with archive.open(member) as binary_handle:
            # UTF-8テキストへ包む
            with io.TextIOWrapper(binary_handle, encoding="utf-8") as handle:
                # レコード数を初期化する
                count = 0
                # JSONLを一行ずつ読む
                for line_number, line in enumerate(handle, start=1):
                    # 空行を拒否する
                    if not line.strip():
                        # 不正行を明示する
                        raise ValueError(f"{member}:{line_number}: 空行です")
                    # JSONを解析する
                    record = json.loads(line)
                    # object以外を拒否する
                    if not isinstance(record, dict):
                        # 行番号を示す
                        raise ValueError(f"{member}:{line_number}: objectではありません")
                    # 分割などの固定条件を一件ずつ照合する
                    for key, expected in required_values.items():
                        # 評価データ混入を拒否する
                        if record.get(key) != expected:
                            # 実際値を含めて停止する
                            raise ValueError(
                                f"{member}:{line_number}: {key}={record.get(key)!r}は"
                                f"期待値{expected!r}と一致しません"
                            )
                    # 指示とコードを検査する
                    for field in ("instruction_ja", "reference_code"):
                        # 空でない文字列を要求する
                        require_string(record.get(field), f"{member}:{line_number}:{field}")
                    # 件数を増やす
                    count += 1
                    # 検査済みレコードを返す
                    yield record
    # 全件読込み後に期待件数を照合する
    if count != expected_count:
        # 不足または過剰を拒否する
        raise ValueError(f"訓練レコード数が一致しません: {count} != {expected_count}")


# トークナイザ学習用文字列を返す
def iter_corpus_texts(
    config: dict[str, Any], archive_path: Path, stats: dict[str, Any]
) -> Iterator[str]:
    """日本語指示とPythonコードだけを項目別重複除去して返す。"""

    # 入力設定を取得する
    source = config["source"]
    # コーパス設定を取得する
    corpus = config["corpus"]
    # 特殊トークン本文を取得する
    special_tokens, _, _ = special_token_maps(config)
    # 項目別の既出SHA-256集合を作る
    seen_hashes = {field: set() for field in corpus["fields"]}
    # 項目別件数を初期化する
    yielded_counts = Counter()
    # 項目別重複除外件数を初期化する
    skipped_counts = Counter()
    # 文字数を初期化する
    character_counts = Counter()
    # UTF-8 byte数を初期化する
    byte_counts = Counter()
    # 全訓練レコードを順番どおり読む
    for record in iter_training_records(
        archive_path,
        source["member"],
        source["expected_record_count"],
        source["required_values"],
    ):
        # 設定順に日本語指示とコードを処理する
        for field in corpus["fields"]:
            # 本文を取得する
            text = record[field]
            # 特殊トークン文字列が通常本文に混入していないことを確認する
            if any(token in text for token in special_tokens):
                # 境界トークンとの衝突を拒否する
                raise ValueError(f"{field}本文に特殊トークン文字列が含まれています")
            # 完全一致判定用ハッシュを計算する
            text_hash = text_sha256(text)
            # 重複除去対象か確認する
            if corpus["deduplicate"][field] and text_hash in seen_hashes[field]:
                # 除外件数を加算する
                skipped_counts[field] += 1
                # 次の項目へ進む
                continue
            # 既出集合へ追加する
            seen_hashes[field].add(text_hash)
            # 出力件数を加算する
            yielded_counts[field] += 1
            # 文字数を加算する
            character_counts[field] += len(text)
            # UTF-8 byte数を加算する
            byte_counts[field] += len(text.encode("utf-8"))
            # トークナイザtrainerへ本文だけを渡す
            yield text
    # 学習コーパス集計を保存する
    stats["yielded_text_count_by_field"] = dict(sorted(yielded_counts.items()))
    # 重複除外件数を保存する
    stats["deduplicated_text_count_by_field"] = dict(sorted(skipped_counts.items()))
    # 文字数を保存する
    stats["character_count_by_field"] = dict(sorted(character_counts.items()))
    # byte数を保存する
    stats["utf8_byte_count_by_field"] = dict(sorted(byte_counts.items()))
    # 合計本文数を保存する
    stats["yielded_text_count"] = sum(yielded_counts.values())


# YAML設定に対応するTokenizerとTrainerを作る
def create_tokenizer_and_trainer(
    config: dict[str, Any],
) -> tuple[Tokenizer, trainers.Trainer]:
    """ByteLevelを共有し、model.typeだけでBPEとUnigramを切り替える。"""

    # モデル設定を取得する
    model_config = config["model"]
    # 特殊トークン一覧を取得する
    special_tokens, _, ids_by_name = special_token_maps(config)
    # unknownトークンを取得する
    unk_token = model_config["unk_token"]
    # 256 byteの初期alphabetを取得する
    initial_alphabet = pre_tokenizers.ByteLevel.alphabet()
    # BPE設定を作る
    if model_config["type"] == "bpe":
        # 0なら決定的encodeのためNoneへ変換する
        dropout = None if model_config["dropout"] == 0 else float(model_config["dropout"])
        # byte fallback付きBPEモデルを作る
        model = models.BPE(
            dropout=dropout,
            unk_token=unk_token,
            byte_fallback=model_config["byte_fallback"],
        )
        # BPE trainerを作る
        trainer = trainers.BpeTrainer(
            vocab_size=model_config["vocab_size"],
            min_frequency=model_config["min_frequency"],
            show_progress=False,
            special_tokens=special_tokens,
            initial_alphabet=initial_alphabet,
            max_token_length=model_config["max_token_length"],
        )
    # Unigram設定を作る
    else:
        # trainer実行前にunknown IDまでを含む最小Unigram語彙を作る
        initial_unigram_vocab = [
            (special_tokens[token_id], 0.0)
            for token_id in range(ids_by_name["unk"] + 1)
        ]
        # 最小Unigramモデルを作る
        model = models.Unigram(
            initial_unigram_vocab,
            ids_by_name["unk"],
            model_config["byte_fallback"],
        )
        # Unigram trainerを作る
        trainer = trainers.UnigramTrainer(
            vocab_size=model_config["vocab_size"],
            show_progress=False,
            special_tokens=special_tokens,
            initial_alphabet=initial_alphabet,
            shrinking_factor=model_config["shrinking_factor"],
            unk_token=unk_token,
            max_piece_length=model_config["max_piece_length"],
            n_sub_iterations=model_config["n_sub_iterations"],
        )
    # 共通Tokenizerを作る
    tokenizer = Tokenizer(model)
    # identityまたはNFC正規化を設定する
    if config["normalizer"]["type"] == "identity":
        # 空Sequenceで明示的identityにする
        tokenizer.normalizer = normalizers.Sequence([])
    # NFC指定を反映する
    else:
        # Unicode NFCを設定する
        tokenizer.normalizer = normalizers.NFC()
    # ByteLevel事前分割を設定する
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(
        add_prefix_space=config["pre_tokenizer"]["add_prefix_space"],
        use_regex=config["pre_tokenizer"]["use_regex"],
    )
    # ByteLevelから元byte列へ戻すdecoderを設定する
    tokenizer.decoder = decoders.ByteLevel()
    # TokenizerとTrainerを返す
    return tokenizer, trainer


# trainerが上書きし得るモデル設定を最終JSONへ固定する
def restore_model_options(tokenizer: Tokenizer, config: dict[str, Any]) -> Tokenizer:
    """byte_fallbackとBPE dropoutを学習後モデルへ明示的に戻す。"""

    # Tokenizer全体をJSON objectへ変換する
    serialized = json.loads(tokenizer.to_str())
    # model objectを取得する
    model = require_mapping(serialized.get("model"), "tokenizer.model")
    # byte fallbackをYAMLどおり固定する
    model["byte_fallback"] = config["model"]["byte_fallback"]
    # BPEの場合はdropoutもYAMLどおり固定する
    if config["model"]["type"] == "bpe":
        # 0を決定的なnullへ変換する
        model["dropout"] = (
            None if config["model"]["dropout"] == 0 else config["model"]["dropout"]
        )
    # 更新済みJSONからTokenizerを再構成する
    return Tokenizer.from_str(canonical_json(serialized))


# 特殊トークンIDと語彙数を検査する
def validate_trained_vocabulary(tokenizer: Tokenizer, config: dict[str, Any]) -> None:
    """固定ID、unknown ID、byte fallback、語彙総数を確認する。"""

    # 特殊トークン一覧を取得する
    _, by_name, ids_by_name = special_token_maps(config)
    # 名前別にIDを照合する
    for name in REQUIRED_SPECIAL_TOKEN_NAMES:
        # 実際IDを取得する
        actual_id = tokenizer.token_to_id(by_name[name])
        # 固定IDと一致しない場合は停止する
        if actual_id != ids_by_name[name]:
            # ずれた名前とIDを示す
            raise ValueError(
                f"特殊トークンIDが一致しません: {name}={actual_id} != {ids_by_name[name]}"
            )
    # 実語彙数を取得する
    actual_vocab_size = tokenizer.get_vocab_size(with_added_tokens=True)
    # 完全一致を要求する設定なら照合する
    if (
        config["validation"]["require_exact_vocab_size"]
        and actual_vocab_size != config["model"]["vocab_size"]
    ):
        # 不足語彙を拒否する
        raise ValueError(
            f"最終語彙数が一致しません: {actual_vocab_size} != "
            f"{config['model']['vocab_size']}"
        )
    # 保存JSONからmodel設定を読み直す
    serialized = json.loads(tokenizer.to_str())
    # byte fallbackが有効であることを確認する
    if serialized["model"].get("byte_fallback") is not True:
        # 無効化を拒否する
        raise ValueError("学習済みtokenizerのbyte_fallbackがtrueではありません")
    # Unigramのunknown IDを固定値と照合する
    if config["model"]["type"] == "unigram":
        # model内部IDの不一致を拒否する
        if serialized["model"].get("unk_id") != ids_by_name["unk"]:
            # 不正IDを明示する
            raise ValueError("Unigramのunk_idが特殊トークンIDと一致しません")


# 一覧から指定percentileをnearest-rank方式で求める
def percentile(values: list[int], percent: int) -> int:
    """空でない整数一覧のpercentileを再現可能に返す。"""

    # 空一覧を拒否する
    if not values:
        # 集計バグとして扱う
        raise ValueError("percentile対象が空です")
    # 昇順へ並べる
    ordered = sorted(values)
    # nearest-rankの0始まり位置を計算する
    index = max(0, ((percent * len(ordered) + 99) // 100) - 1)
    # 範囲内の値を返す
    return ordered[min(index, len(ordered) - 1)]


# トークン長一覧を要約する
def summarize_lengths(values: list[int]) -> dict[str, float | int]:
    """件数、平均、中央値、p95、p99、最大を返す。"""

    # 空一覧を拒否する
    if not values:
        # 集計不能を明示する
        raise ValueError("トークン長一覧が空です")
    # 基本統計を返す
    return {
        "count": len(values),
        "mean": sum(values) / len(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": max(values),
    }


# 学習済みTokenizerを全訓練レコードで検証する
def validate_tokenizer_on_training_data(
    tokenizer: Tokenizer, config: dict[str, Any], archive_path: Path
) -> dict[str, Any]:
    """完全復元、unknown、fallback、系列長、語彙使用状況を全件集計する。"""

    # 入力設定を取得する
    source = config["source"]
    # 系列テンプレートを取得する
    template = config["sequence"]["template"]
    # 検証設定を取得する
    validation = config["validation"]
    # 特殊トークン対応を取得する
    _, by_name, ids_by_name = special_token_maps(config)
    # unknown IDを取得する
    unk_id = ids_by_name["unk"]
    # 必須系列特殊IDを取得する
    required_special_ids = {
        ids_by_name[name] for name in config["sequence"]["required_special_tokens"]
    }
    # 項目別トークン長を保存する
    instruction_lengths: list[int] = []
    # コード長を保存する
    code_lengths: list[int] = []
    # 完成系列長を保存する
    sequence_lengths: list[int] = []
    # 語彙ID使用回数を保存する
    token_counts: Counter[int] = Counter()
    # unknown数を初期化する
    unk_count = 0
    # `<0xXX>`形式fallback token数を初期化する
    fallback_token_count = 0
    # 総token数を初期化する
    total_token_count = 0
    # roundtrip不一致数を初期化する
    roundtrip_mismatch_count = 0
    # 必須特殊トークン欠落数を初期化する
    required_special_mismatch_count = 0
    # batchへ入れるレコードを初期化する
    batch: list[dict[str, Any]] = []

    # 一つのbatchを検証する内部関数を定義する
    def process_batch(records: list[dict[str, Any]]) -> None:
        """複数レコードをまとめてencodeし、外側集計を更新する。"""

        # 外側の数値集計を更新可能にする
        nonlocal unk_count
        # fallback数も更新可能にする
        nonlocal fallback_token_count
        # 総token数も更新可能にする
        nonlocal total_token_count
        # roundtrip不一致も更新可能にする
        nonlocal roundtrip_mismatch_count
        # 特殊トークン不一致も更新可能にする
        nonlocal required_special_mismatch_count
        # 空batchは何もしない
        if not records:
            # 即時終了する
            return
        # 指示一覧を作る
        instructions = [record["instruction_ja"] for record in records]
        # コード一覧を作る
        codes = [record["reference_code"] for record in records]
        # 完成系列一覧を作る
        sequences = [
            template.format(
                instruction_ja=record["instruction_ja"],
                reference_code=record["reference_code"],
            )
            for record in records
        ]
        # 3種類を一度にencodeする
        encodings = tokenizer.encode_batch([*instructions, *codes, *sequences])
        # batch件数を取得する
        size = len(records)
        # 結果を3種類へ分ける
        instruction_encodings = encodings[:size]
        # コード結果を分ける
        code_encodings = encodings[size : size * 2]
        # 完成系列結果を分ける
        sequence_encodings = encodings[size * 2 :]
        # 各レコードの3結果を同時処理する
        for instruction, code, sequence, instruction_encoding, code_encoding, sequence_encoding in zip(
            instructions,
            codes,
            sequences,
            instruction_encodings,
            code_encodings,
            sequence_encodings,
            strict=True,
        ):
            # 項目別長を保存する
            instruction_lengths.append(len(instruction_encoding.ids))
            # コード長を保存する
            code_lengths.append(len(code_encoding.ids))
            # 完成系列長を保存する
            sequence_lengths.append(len(sequence_encoding.ids))
            # 3結果を順番に検査する
            for original, encoding in (
                (instruction, instruction_encoding),
                (code, code_encoding),
                (sequence, sequence_encoding),
            ):
                # ID使用回数を加算する
                token_counts.update(encoding.ids)
                # 総token数を加算する
                total_token_count += len(encoding.ids)
                # unknown出現数を加算する
                unk_count += encoding.ids.count(unk_id)
                # 明示fallback token数を加算する
                fallback_token_count += sum(
                    1
                    for token in encoding.tokens
                    if len(token) == 6
                    and token.startswith("<0x")
                    and token.endswith(">")
                )
                # 特殊トークンを残して復号する
                decoded = tokenizer.decode(encoding.ids, skip_special_tokens=False)
                # 完全一致しない場合を数える
                if decoded != original:
                    # 不一致数を増やす
                    roundtrip_mismatch_count += 1
            # 完成系列に必須特殊IDが各1回あることを確認する
            if any(sequence_encoding.ids.count(token_id) != 1 for token_id in required_special_ids):
                # 欠落または重複を数える
                required_special_mismatch_count += 1

    # 全訓練レコードを読む
    for record in iter_training_records(
        archive_path,
        source["member"],
        source["expected_record_count"],
        source["required_values"],
    ):
        # batchへ追加する
        batch.append(record)
        # 設定件数に達したら処理する
        if len(batch) >= validation["batch_size"]:
            # 現batchを検証する
            process_batch(batch)
            # 次batch用に空へ戻す
            batch = []
    # 末尾の端数batchを処理する
    process_batch(batch)
    # roundtrip必須時に不一致を拒否する
    if validation["require_roundtrip"] and roundtrip_mismatch_count:
        # 件数を明示する
        raise ValueError(f"encode/decode完全一致に{roundtrip_mismatch_count}件失敗しました")
    # unknownゼロ必須時に出現を拒否する
    if validation["require_zero_unk"] and unk_count:
        # 件数を明示する
        raise ValueError(f"unknownトークンが{unk_count}個出現しました")
    # 必須特殊トークン不一致を拒否する
    if required_special_mismatch_count:
        # 件数を明示する
        raise ValueError(
            f"完成系列の必須特殊トークンが{required_special_mismatch_count}件不正です"
        )
    # 最大系列長超過件数を数える
    overlength_count = sum(
        length > validation["model_max_length"] for length in sequence_lengths
    )
    # 超過を失敗条件にしている場合は拒否する
    if validation["fail_on_overlength"] and overlength_count:
        # 件数を明示する
        raise ValueError(
            f"最大系列長{validation['model_max_length']}を{overlength_count}件が超えました"
        )
    # IDからtoken本文を引く語彙を取得する
    vocab = tokenizer.get_vocab(with_added_tokens=True)
    # 逆引き対応を作る
    token_by_id = {token_id: token for token, token_id in vocab.items()}
    # 使用頻度上位100件を作る
    top_tokens = [
        {"id": token_id, "token": token_by_id[token_id], "count": count}
        for token_id, count in token_counts.most_common(100)
    ]
    # 検証集計を返す
    return {
        "record_count": len(sequence_lengths),
        "instruction_token_lengths": summarize_lengths(instruction_lengths),
        "code_token_lengths": summarize_lengths(code_lengths),
        "sequence_token_lengths": summarize_lengths(sequence_lengths),
        "model_max_length": validation["model_max_length"],
        "overlength_count": overlength_count,
        "overlength_rate": overlength_count / len(sequence_lengths),
        "roundtrip_mismatch_count": roundtrip_mismatch_count,
        "required_special_mismatch_count": required_special_mismatch_count,
        "unk_token": by_name["unk"],
        "unk_token_count": unk_count,
        "explicit_byte_fallback_token_count": fallback_token_count,
        "total_encoded_token_count": total_token_count,
        "used_vocab_count": len(token_counts),
        "unused_vocab_count": tokenizer.get_vocab_size(with_added_tokens=True)
        - len(token_counts),
        "top_100_tokens": top_tokens,
    }


# Transformers互換の補助設定を書く
def write_compatibility_files(
    output_dir: Path, config: dict[str, Any], tokenizer: Tokenizer
) -> None:
    """tokenizer_config、special token map、ID順語彙一覧を保存する。"""

    # 特殊トークン対応を取得する
    _, by_name, _ = special_token_maps(config)
    # Transformers用特殊トークン対応を作る
    special_map = {
        "pad_token": by_name["pad"],
        "bos_token": by_name["bos"],
        "eos_token": by_name["eos"],
        "unk_token": by_name["unk"],
        "additional_special_tokens": [
            by_name["task"],
            by_name["code"],
            by_name["explanation"],
        ],
    }
    # 特殊トークン対応を保存する
    (output_dir / "special_tokens_map.json").write_text(
        json.dumps(special_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # tokenizer読込み設定を作る
    tokenizer_config = {
        **special_map,
        "tokenizer_class": "PreTrainedTokenizerFast",
        "clean_up_tokenization_spaces": False,
        "model_max_length": config["validation"]["model_max_length"],
        "add_prefix_space": config["pre_tokenizer"]["add_prefix_space"],
    }
    # tokenizer設定を保存する
    (output_dir / "tokenizer_config.json").write_text(
        json.dumps(tokenizer_config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # 語彙をID順へ並べる
    vocabulary = sorted(
        tokenizer.get_vocab(with_added_tokens=True).items(), key=lambda item: item[1]
    )
    # 可視化しやすいTSVを開く
    with (output_dir / "vocab.tsv").open("w", encoding="utf-8") as handle:
        # 見出しを書く
        handle.write("id\ttoken_json\n")
        # 全語彙を一件ずつ書く
        for token, token_id in vocabulary:
            # 制御文字を壊さないJSON文字列として保存する
            handle.write(f"{token_id}\t{json.dumps(token, ensure_ascii=False)}\n")


# トークナイザ一式を生成する
def train_tokenizer(
    *, config_path: Path, output_override: Path | None, overwrite: bool
) -> dict[str, Any]:
    """YAML設定に従って学習、全件検査、決定的成果物保存を行う。"""

    # 設定を読み込む
    config = load_and_validate_config(config_path)
    # 入力ZIPを解決する
    archive_path = resolve_config_path(config["source"]["archive"], "source.archive")
    # 入力ZIPの存在を確認する
    if not archive_path.is_file():
        # 欠落を明示する
        raise FileNotFoundError(archive_path)
    # 出力先をCLI優先で決める
    output_dir = (
        output_override.resolve()
        if output_override is not None
        else resolve_config_path(config["output"]["directory"], "output.directory")
    )
    # 作業ディレクトリ自体やルートを出力先にしない
    if output_dir in {Path.cwd().resolve(), Path("/")}:
        # 広すぎる上書き対象を拒否する
        raise ValueError("output directoryにリポジトリ直下または/は指定できません")
    # 既存出力を上書き指定なしで保護する
    if output_dir.exists() and not overwrite:
        # 明示的な方法を案内する
        raise FileExistsError(f"出力が既に存在します: {output_dir}; --overwriteを指定してください")
    # 入力ZIPの処理前SHA-256を計算する
    source_sha256_before = file_sha256(archive_path)
    # 設定値と照合する
    if source_sha256_before != config["source"]["expected_archive_sha256"]:
        # 異なる訓練データを拒否する
        raise ValueError("入力訓練ZIPのSHA-256がYAML設定と一致しません")
    # 出力親ディレクトリを作る
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    # 親ディレクトリ内に一時出力を作る
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=output_dir.parent
    ) as temporary_directory:
        # 一時パスへ変換する
        temporary_output = Path(temporary_directory)
        # コーパス集計を初期化する
        corpus_stats: dict[str, Any] = {}
        # TokenizerとTrainerを作る
        tokenizer, trainer = create_tokenizer_and_trainer(config)
        # 訓練コーパスiteratorから学習する
        tokenizer.train_from_iterator(
            iter_corpus_texts(config, archive_path, corpus_stats), trainer=trainer
        )
        # trainer後もbyte fallbackなどを設定どおり固定する
        tokenizer = restore_model_options(tokenizer, config)
        # 語彙と特殊トークンを検査する
        validate_trained_vocabulary(tokenizer, config)
        # 全訓練レコードで復元と系列長を検証する
        validation_stats = validate_tokenizer_on_training_data(
            tokenizer, config, archive_path
        )
        # tokenizer本体を保存する
        tokenizer_path = temporary_output / "tokenizer.json"
        # JSONを整形せずライブラリ標準形式で保存する
        tokenizer.save(str(tokenizer_path), pretty=True)
        # Transformers互換設定と語彙一覧を保存する
        write_compatibility_files(temporary_output, config, tokenizer)
        # 解決済み設定を保存する
        (temporary_output / "training_config.yaml").write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        # 処理後入力ハッシュを確認する
        source_sha256_after = file_sha256(archive_path)
        # 入力変更を拒否する
        if source_sha256_after != source_sha256_before:
            # 読取り中の改変を明示する
            raise ValueError("トークナイザ学習中に入力訓練ZIPが変更されました")
        # 特殊トークンIDを集計用に取得する
        _, by_name, ids_by_name = special_token_maps(config)
        # 実行結果をまとめる
        stats = {
            "phase": "tokenizer_training",
            "generator_version": GENERATOR_VERSION,
            "software": {
                "python": sys.version.split()[0],
                "pyyaml": yaml.__version__,
                "tokenizers": tokenizers_version,
            },
            "model_type": config["model"]["type"],
            "configured_vocab_size": config["model"]["vocab_size"],
            "actual_vocab_size": tokenizer.get_vocab_size(with_added_tokens=True),
            "byte_fallback": True,
            "normalizer": config["normalizer"],
            "pre_tokenizer": config["pre_tokenizer"],
            "model_parameters": config["model"],
            "special_tokens": {
                name: {"token": by_name[name], "id": ids_by_name[name]}
                for name in REQUIRED_SPECIAL_TOKEN_NAMES
            },
            "source_archive": display_path(archive_path),
            "source_member": config["source"]["member"],
            "source_record_count": config["source"]["expected_record_count"],
            "source_sha256_before": source_sha256_before,
            "source_sha256_after": source_sha256_after,
            "source_unchanged": True,
            "config_path": display_path(config_path),
            "config_sha256": file_sha256(config_path),
            "corpus": corpus_stats,
            "validation": validation_stats,
            "files": {
                filename: {
                    "bytes": (temporary_output / filename).stat().st_size,
                    "sha256": file_sha256(temporary_output / filename),
                }
                for filename in (
                    "tokenizer.json",
                    "tokenizer_config.json",
                    "special_tokens_map.json",
                    "training_config.yaml",
                    "vocab.tsv",
                )
            },
        }
        # 集計JSONを保存する
        (temporary_output / "training_stats.json").write_text(
            json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        # 明示上書き時だけ既存の対象ディレクトリを削除する
        if output_dir.exists():
            # 検証完了後に限定して削除する
            shutil.rmtree(output_dir)
        # 一時ディレクトリを完成出力へ移す
        os.replace(temporary_output, output_dir)
    # 完成集計へ出力先を追加する
    result = dict(stats)
    # 呼出し元用に実出力パスを保存する
    result["output_directory"] = str(output_dir)
    # 結果を返す
    return result


# 設定と入力だけを確認する
def validate_config_and_source(config_path: Path, output_override: Path | None) -> dict[str, Any]:
    """モデル学習前にYAML、入力ZIP、出力先を検査する。"""

    # YAMLを検査する
    config = load_and_validate_config(config_path)
    # 入力ZIPを解決する
    archive_path = resolve_config_path(config["source"]["archive"], "source.archive")
    # 入力ZIPの存在を確認する
    if not archive_path.is_file():
        # 欠落を明示する
        raise FileNotFoundError(archive_path)
    # SHA-256を計算する
    actual_sha256 = file_sha256(archive_path)
    # 固定済み入力と照合する
    if actual_sha256 != config["source"]["expected_archive_sha256"]:
        # 別データ混入を拒否する
        raise ValueError("入力訓練ZIPのSHA-256がYAML設定と一致しません")
    # ZIPメンバーを確認する
    with zipfile.ZipFile(archive_path) as archive:
        # 対象JSONLの存在を確認する
        if config["source"]["member"] not in archive.namelist():
            # 欠落名を明示する
            raise ValueError("入力訓練ZIPに指定JSONLがありません")
        # CRC検査を行う
        if archive.testzip() is not None:
            # 破損ZIPを拒否する
            raise ValueError("入力訓練ZIPのCRC検査に失敗しました")
    # 出力先を解決する
    output_dir = (
        output_override.resolve()
        if output_override is not None
        else resolve_config_path(config["output"]["directory"], "output.directory")
    )
    # 確認結果を返す
    return {
        "model_type": config["model"]["type"],
        "vocab_size": config["model"]["vocab_size"],
        "source_archive": str(archive_path),
        "source_sha256": actual_sha256,
        "source_member": config["source"]["member"],
        "expected_record_count": config["source"]["expected_record_count"],
        "output_directory": str(output_dir),
    }


# CLI入口を定義する
def main() -> None:
    """YAML設定を読み、検査またはトークナイザ学習を実行する。"""

    # CLI引数を取得する
    args = parse_args()
    # 設定検査だけなら学習を行わない
    if args.validate_config:
        # 設定と入力を検査する
        result = validate_config_and_source(args.config.resolve(), args.output_dir)
        # 要点をJSONで表示する
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        # 正常終了する
        return
    # トークナイザを学習する
    result = train_tokenizer(
        config_path=args.config.resolve(),
        output_override=args.output_dir,
        overwrite=args.overwrite,
    )
    # 完成結果を簡潔に表示する
    print(
        "トークナイザを作成しました: "
        f"type={result['model_type']}, "
        f"vocab={result['actual_vocab_size']}, "
        f"records={result['source_record_count']}, "
        f"output={result['output_directory']}"
    )


# 直接実行された場合だけCLIを開始する
if __name__ == "__main__":
    # メイン処理を呼ぶ
    main()
