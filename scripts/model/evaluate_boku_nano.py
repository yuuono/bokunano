"""Boku-nanoの生成コードを5種類の固定評価集合で実行評価する。"""

# 型注釈を実行時評価から分離する
from __future__ import annotations

# CLI引数を処理する
import argparse
# 件数を分類別に集計する
from collections import Counter, defaultdict
# ZIP内JSONLをtext streamとして読む
import io
# SHA-256と生成コードhashを計算する
import hashlib
# JSON設定、レコード、結果を読み書きする
import json
# 実行環境情報を記録する
import platform
# パスを安全に扱う
from pathlib import Path
# リポジトリ直下moduleをimport可能にする
import sys
# 処理時間を測る
import time
# ZIP内の評価データを直接読む
import zipfile
# 任意のJSON値を型注釈で表す
from typing import Any, Iterable, Mapping, Sequence

# YAML評価設定を読む
import yaml
# safetensors形式の最終重みを読む
from safetensors.torch import load_file as load_safetensors
# 推論を実行する
import torch
# BPEトークナイザを読む
from tokenizers import Tokenizer


# リポジトリ直下をmodule探索先へ加える
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 直接実行時だけ不足する探索先を補う
if str(PROJECT_ROOT) not in sys.path:
    # 既存の同名moduleよりリポジトリを優先する
    sys.path.insert(0, str(PROJECT_ROOT))

# 既存の隔離実行検証を再利用する
from generated_code_verifier import GeneratedCodeVerifierSession  # noqa: E402
# Boku-nano本体を読み込む
from scripts.model.boku_nano import (  # noqa: E402
    BokuNanoConfig,
    BokuNanoForCausalLM,
)


# 評価結果形式を固定する
EVALUATOR_VERSION = "1"
# 学習時と同じprompt形式を固定する
PROMPT_TEMPLATE = "<|bos|><|task|>\n{instruction_ja}\n<|code|>\n"
# 正式な5評価集合を固定する
SUPPORTED_SUITES = (
    "normal",
    "compositional",
    "paraphrase",
    "repetition",
    "boundary",
)


# CLI引数を定義する
def parse_args() -> argparse.Namespace:
    """評価実行条件をCLIから読む。"""

    # 評価用parserを作る
    parser = argparse.ArgumentParser(
        description="Boku-nanoを5種類の固定テスト集合で生成・実行評価します。"
    )
    # 評価設定を必須にする
    parser.add_argument("--config", type=Path, required=True, help="評価設定YAML")
    # 推論せず固定artifactだけ確認できるようにする
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="設定、hash、ZIP memberを確認し、推論せず終了します。",
    )
    # 一部集合だけ実行できるようにする
    parser.add_argument(
        "--suite",
        action="append",
        choices=SUPPORTED_SUITES,
        help="実行する集合。複数指定可。省略時は5集合すべて。",
    )
    # smoke test用に各集合の新規処理件数を制限する
    parser.add_argument(
        "--max-records",
        type=int,
        help="各集合で今回新たに評価する最大件数。",
    )
    # 3 epochと10 epochを同じ設定で比較可能にする
    parser.add_argument(
        "--model-directory",
        type=Path,
        help="設定内model.directoryを実行時だけ差し替えます。",
    )
    # モデルごとに別の出力先を指定可能にする
    parser.add_argument(
        "--output-directory",
        type=Path,
        help="設定内output.directoryを実行時だけ差し替えます。",
    )
    # 中断済みJSONLの続きから再開できるようにする
    parser.add_argument(
        "--resume",
        action="store_true",
        help="既存結果のrecord_idを読み飛ばして追記します。",
    )
    # 明示した場合だけ既存の評価結果を置き換える
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="選択した集合の既存結果を削除して最初から実行します。",
    )
    # 解析済み引数を返す
    return parser.parse_args()


# ファイル内容のSHA-256を計算する
def file_sha256(path: Path) -> str:
    """ファイルを分割読み込みしてSHA-256を返す。"""

    # hash計算器を作る
    digest = hashlib.sha256()
    # binaryで入力を開く
    with path.open("rb") as handle:
        # EOFまで固定サイズで読む
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            # 現在の断片をhashへ加える
            digest.update(chunk)
    # 16進表記を返す
    return digest.hexdigest()


# 文字列内容のSHA-256を計算する
def text_sha256(value: str) -> str:
    """UTF-8文字列のSHA-256を返す。"""

    # UTF-8 byte列をhash化する
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# リポジトリ相対または絶対パスを統一する
def configured_path(value: Any) -> Path:
    """設定値をリポジトリ基準の絶対パスへ変換する。"""

    # 文字列化した設定をPathへ変換する
    path = Path(str(value))
    # 絶対パスはそのまま正規化する
    if path.is_absolute():
        # 実在しない出力先も扱えるresolveを使う
        return path.resolve()
    # 相対パスはリポジトリ直下基準にする
    return (PROJECT_ROOT / path).resolve()


# 表示用パスから環境依存の絶対prefixを外す
def display_path(path: Path) -> str:
    """リポジトリ内パスを相対表示する。"""

    # リポジトリ内なら相対パスを返す
    try:
        # clone先に依存しない表記へする
        return str(path.resolve().relative_to(PROJECT_ROOT))
    # リポジトリ外の明示パスは絶対表記を維持する
    except ValueError:
        # 解決済み絶対パスを返す
        return str(path.resolve())


# JSONを一時ファイル経由で置き換える
def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    """途中状態を見せずにJSONを書き換える。"""

    # 親ディレクトリを作る
    path.parent.mkdir(parents=True, exist_ok=True)
    # 同じfilesystemの一時パスを作る
    temporary_path = path.with_name(path.name + ".tmp")
    # キー順固定、末尾改行付きで保存する
    temporary_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # 完成ファイルへ原子的に置き換える
    temporary_path.replace(path)


# YAML評価設定を読み込む
def load_config(config_path: Path) -> dict[str, Any]:
    """評価設定の必須構造を検査して返す。"""

    # YAMLを辞書として読む
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    # rootをobjectに限定する
    if not isinstance(config, dict):
        # 誤った設定形式を拒否する
        raise ValueError("評価設定rootはobjectにしてください")
    # 設定versionを固定する
    if config.get("version") != 1:
        # 未対応versionを黙って解釈しない
        raise ValueError(f"未対応の評価設定versionです: {config.get('version')!r}")
    # 必須sectionを確認する
    for section in ("model", "tokenizer", "evaluation_data", "generation", "verification", "output"):
        # object以外を拒否する
        if not isinstance(config.get(section), dict):
            # 欠落sectionを明示する
            raise ValueError(f"評価設定の{section}がobjectではありません")
    # 検査済み設定を返す
    return config


# 固定artifactと5集合定義を推論なしで検証する
def validate_configuration(
    config_path: Path,
    model_directory_override: Path | None = None,
    output_directory_override: Path | None = None,
) -> dict[str, Any]:
    """設定、hash、ZIP member、入力manifestを検証する。"""

    # 評価設定を読む
    config = load_config(config_path)
    # 実行対象modelディレクトリを決める
    model_directory = (
        model_directory_override.resolve()
        if model_directory_override is not None
        else configured_path(config["model"]["directory"])
    )
    # 最終重みパスを決める
    weights_path = model_directory / str(config["model"]["weights"])
    # モデル構造設定パスを決める
    model_config_path = model_directory / str(config["model"]["config"])
    # 学習完了manifestパスを決める
    training_manifest_path = model_directory / str(config["model"]["manifest"])
    # モデル関連3ファイルの存在を確認する
    for path in (weights_path, model_config_path, training_manifest_path):
        # 欠落時は対象を明示する
        if not path.is_file():
            # 評価不能として停止する
            raise FileNotFoundError(f"モデルartifactがありません: {path}")
    # 学習完了manifestを読む
    training_manifest = json.loads(training_manifest_path.read_text(encoding="utf-8"))
    # 未完了モデルを正式評価しない
    if training_manifest.get("status") != "completed":
        # 学習状態を含めて拒否する
        raise ValueError(f"学習manifestがcompletedではありません: {training_manifest.get('status')!r}")
    # 重みhashを計算する
    weights_sha256 = file_sha256(weights_path)
    # manifestが記録したhashと照合する
    if weights_sha256 != training_manifest.get("model_sha256"):
        # モデルとmanifestの取り違えを拒否する
        raise ValueError("model.safetensorsのSHA-256が学習manifestと一致しません")
    # モデル構造設定を読む
    model_values = json.loads(model_config_path.read_text(encoding="utf-8"))
    # モデル設定を構造検査する
    model_config = BokuNanoConfig.from_dict(model_values)
    # 実モデルparameter数を構造から計算する
    parameter_count = BokuNanoForCausalLM(model_config).parameter_count()
    # 期待parameter数と照合する
    if parameter_count != int(config["model"]["expected_parameter_count"]):
        # 異なる構造の評価を拒否する
        raise ValueError("モデルparameter数が評価設定と一致しません")
    # tokenizerパスを解決する
    tokenizer_path = configured_path(config["tokenizer"]["path"])
    # tokenizerの存在を確認する
    if not tokenizer_path.is_file():
        # 欠落パスを明示する
        raise FileNotFoundError(f"tokenizerがありません: {tokenizer_path}")
    # tokenizer hashを照合する
    tokenizer_sha256 = file_sha256(tokenizer_path)
    # 固定BPE以外を拒否する
    if tokenizer_sha256 != str(config["tokenizer"]["expected_sha256"]):
        # 設定とartifactの不一致を示す
        raise ValueError("tokenizerのSHA-256が一致しません")
    # tokenizer本体を読み込む
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    # 固定特殊token文字列を定義する
    expected_special_tokens = {
        "pad": "<|pad|>",
        "bos": "<|bos|>",
        "eos": "<|eos|>",
        "unk": "<|unk|>",
        "task": "<|task|>",
        "code": "<|code|>",
    }
    # 設定したIDとtokenizer内IDを照合する
    for name, token in expected_special_tokens.items():
        # 評価設定のIDを取得する
        configured_id = int(config["tokenizer"]["special_token_ids"][name])
        # tokenizerが返すIDと一致させる
        if tokenizer.token_to_id(token) != configured_id:
            # prompt形式を壊す不整合を拒否する
            raise ValueError(f"特殊token IDが一致しません: {name}")
    # decoding方式をgreedyへ固定する
    if config["generation"].get("decoding") != "greedy":
        # 未実装方式を黙ってgreedy扱いしない
        raise ValueError("generation.decodingはgreedyにしてください")
    # generationの正整数設定を検査する
    for key in ("batch_size", "buffer_size", "max_new_tokens"):
        # 0以下を拒否する
        if int(config["generation"].get(key, 0)) <= 0:
            # 不正項目を明示する
            raise ValueError(f"generation.{key}は正の整数にしてください")
    # bufferが最低1 batchを収容できることを確認する
    if int(config["generation"]["buffer_size"]) < int(config["generation"]["batch_size"]):
        # 不要な細切れ処理を拒否する
        raise ValueError("generation.buffer_sizeはbatch_size以上にしてください")
    # 検証上限を正値に限定する
    if int(config["verification"].get("max_source_chars", 0)) <= 0:
        # 静的検査無効化を拒否する
        raise ValueError("verification.max_source_charsは正の整数にしてください")
    # timeoutを正値に限定する
    if float(config["verification"].get("timeout_seconds", 0.0)) <= 0:
        # 無制限実行を拒否する
        raise ValueError("verification.timeout_secondsは正の値にしてください")
    # 評価ZIPパスを解決する
    archive_path = configured_path(config["evaluation_data"]["archive"])
    # 評価ZIP hashを計算する
    archive_sha256 = file_sha256(archive_path)
    # 固定済み評価ZIPと照合する
    if archive_sha256 != str(config["evaluation_data"]["expected_sha256"]):
        # データ差し替えを拒否する
        raise ValueError("評価ZIPのSHA-256が一致しません")
    # suite設定を読む
    suites = config["evaluation_data"].get("suites")
    # 5集合のobjectだけを許可する
    if not isinstance(suites, dict) or set(suites) != set(SUPPORTED_SUITES):
        # 欠落または余分な集合を拒否する
        raise ValueError("評価設定suitesは正式な5集合と完全一致させてください")
    # ZIP member一覧を取得する
    with zipfile.ZipFile(archive_path, mode="r") as archive:
        # member名を集合化する
        archive_members = set(archive.namelist())
    # 検査結果を集合ごとに作る
    suite_summaries: dict[str, Any] = {}
    # 正式順で各集合を検査する
    for suite_name in SUPPORTED_SUITES:
        # 集合設定を取得する
        suite_config = suites[suite_name]
        # object以外を拒否する
        if not isinstance(suite_config, dict):
            # 集合名を示して停止する
            raise ValueError(f"suite設定がobjectではありません: {suite_name}")
        # 指定memberを取得する
        member = str(suite_config["member"])
        # ZIP内に存在することを確認する
        if member not in archive_members:
            # 欠落memberを明示する
            raise ValueError(f"評価ZIP memberがありません: {member}")
        # 入力manifestパスを解決する
        input_path = configured_path(suite_config["inputs"])
        # 入力manifest hashを照合する
        input_sha256 = file_sha256(input_path)
        # 固定済み入力以外を拒否する
        if input_sha256 != str(suite_config["expected_input_sha256"]):
            # 集合名を含めて不一致を示す
            raise ValueError(f"評価入力SHA-256が一致しません: {suite_name}")
        # 入力manifestを読む
        input_manifest = json.loads(input_path.read_text(encoding="utf-8"))
        # 集合名とtest_set_idを照合する
        if input_manifest.get("test_suite") != suite_name:
            # 別集合の入力取り違えを拒否する
            raise ValueError(f"評価入力test_suiteが一致しません: {suite_name}")
        # レコードが参照するIDと一致させる
        if input_manifest.get("test_set_id") != suite_config.get("test_set_id"):
            # 参照の不整合を拒否する
            raise ValueError(f"評価入力test_set_idが一致しません: {suite_name}")
        # 集合別の検査結果を記録する
        suite_summaries[suite_name] = {
            "expected_record_count": int(suite_config["expected_record_count"]),
            "input_sha256": input_sha256,
            "member": member,
            "test_set_id": str(suite_config["test_set_id"]),
        }
    # 出力先を決める
    output_directory = (
        output_directory_override.resolve()
        if output_directory_override is not None
        else configured_path(config["output"]["directory"])
    )
    # 推論前検証結果を返す
    return {
        "archive": display_path(archive_path),
        "archive_sha256": archive_sha256,
        "config": display_path(config_path.resolve()),
        "config_sha256": file_sha256(config_path),
        "model_directory": display_path(model_directory),
        "model_sha256": weights_sha256,
        "output_directory": display_path(output_directory),
        "parameter_count": parameter_count,
        "suites": suite_summaries,
        "tokenizer_sha256": tokenizer_sha256,
    }


# 学習時と同じpromptをtoken化する
def encode_prompt(
    tokenizer: Tokenizer,
    instruction: str,
    special_ids: Mapping[str, int],
    context_length: int,
) -> list[int]:
    """日本語指示を明示特殊token付きpromptへ変換する。"""

    # 学習時と同じ改行を含むpromptを作る
    prompt = PROMPT_TEMPLATE.format(instruction_ja=instruction)
    # tokenizer側の自動特殊token追加を無効にする
    token_ids = tokenizer.encode(prompt, add_special_tokens=False).ids
    # 空promptを拒否する
    if not token_ids:
        # データまたはtokenizer不整合として停止する
        raise ValueError("token化後のpromptが空です")
    # BOSが先頭にあることを確認する
    if token_ids[0] != special_ids["bos"]:
        # 学習promptとの差異を拒否する
        raise ValueError("prompt先頭がBOSではありません")
    # 必須markerの個数を確認する
    for name in ("bos", "task", "code"):
        # 重複や欠落を拒否する
        if token_ids.count(special_ids[name]) != 1:
            # 問題のtoken名を示す
            raise ValueError(f"prompt内の特殊token個数が不正です: {name}")
    # promptにEOSが混入していないことを確認する
    if special_ids["eos"] in token_ids:
        # 指示本文による特殊token注入も拒否する
        raise ValueError("prompt内にEOSが含まれています")
    # unknownを正式評価で許可しない
    if special_ids["unk"] in token_ids:
        # 固定tokenizerとの不整合として停止する
        raise ValueError("prompt内にUNKが含まれています")
    # 最低1 token生成できる長さを要求する
    if len(token_ids) >= context_length:
        # 切り捨てによる条件変更を行わない
        raise ValueError("prompt長がモデルcontext_length以上です")
    # 検査済みID列を返す
    return token_ids


# 同一prompt長のbatchをgreedy decodingする
def greedy_generate_equal_length(
    model: BokuNanoForCausalLM,
    prompt_token_ids: Sequence[Sequence[int]],
    eos_token_id: int,
    pad_token_id: int,
    max_new_tokens: int,
    context_length: int,
    device: torch.device,
) -> list[dict[str, Any]]:
    """padding maskを使わず安全にbatch生成できる同長promptだけを処理する。"""

    # 空batchを拒否する
    if not prompt_token_ids:
        # 呼び出し側のバグを明示する
        raise ValueError("生成batchが空です")
    # 共通prompt長を取得する
    prompt_length = len(prompt_token_ids[0])
    # 全promptが同じ長さか確認する
    if any(len(values) != prompt_length for values in prompt_token_ids):
        # paddingがattentionへ混入する条件を拒否する
        raise ValueError("greedy生成batchのprompt長が一致していません")
    # 設定上限とcontext残量の小さい方を生成可能数にする
    generation_limit = min(max_new_tokens, context_length - prompt_length)
    # token列をdevice上へ置く
    input_ids = torch.tensor(prompt_token_ids, dtype=torch.long, device=device)
    # 各系列の生成tokenを保持する
    generated: list[list[int]] = [[] for _ in prompt_token_ids]
    # 終了状態を保持する
    finished = [False for _ in prompt_token_ids]
    # 既定終了理由をcontextまたは生成上限にする
    limit_reason = (
        "max_context"
        if context_length - prompt_length <= max_new_tokens
        else "max_new_tokens"
    )
    # 各系列の終了理由を初期化する
    termination = [limit_reason for _ in prompt_token_ids]
    # gradientを構築せず自己回帰生成する
    with torch.inference_mode():
        # 上限token数まで繰り返す
        for _ in range(generation_limit):
            # 現在系列の次token logitsを得る
            next_logits = model(input_ids).logits[:, -1, :]
            # samplingせず最大logit IDを選ぶ
            next_ids = torch.argmax(next_logits, dim=-1)
            # 次回入力へ追加するIDをCPU listへ移す
            next_values = next_ids.tolist()
            # batch内の各系列を更新する
            append_values: list[int] = []
            # 各候補tokenを順に処理する
            for index, token_id in enumerate(next_values):
                # 既に終了した系列はpaddingを追加する
                if finished[index]:
                    # 他系列の生成だけを継続する
                    append_values.append(pad_token_id)
                    # この系列の結果は変更しない
                    continue
                # EOSで正常終了する
                if token_id == eos_token_id:
                    # 終了状態を記録する
                    finished[index] = True
                    # 正常終了理由を記録する
                    termination[index] = "eos"
                    # EOS自体はコード本文へ含めない
                    append_values.append(pad_token_id)
                    # 次系列へ進む
                    continue
                # 通常tokenをコード列へ保存する
                generated[index].append(int(token_id))
                # 次回forward入力にも同じtokenを追加する
                append_values.append(int(token_id))
            # 全系列が終われば不要なforwardを止める
            if all(finished):
                # 生成loopを抜ける
                break
            # 次token列をTensor化する
            appended = torch.tensor(append_values, dtype=torch.long, device=device)
            # 系列末尾へ一列追加する
            input_ids = torch.cat((input_ids, appended[:, None]), dim=1)
    # 系列ごとの結果を返す
    return [
        {
            "generated_token_ids": values,
            "termination": termination[index],
        }
        for index, values in enumerate(generated)
    ]


# 評価入力manifestから実行caseを作る
def cases_for_record(
    input_manifest: Mapping[str, Any],
    suite_name: str,
    spec_id: str,
) -> list[tuple[list[int], int]]:
    """通常集合またはboundaryのspec固有caseを返す。"""

    # boundary以外は共通64ケースを使う
    if suite_name != "boundary":
        # manifestの全caseを変換して返す
        return [
            (list(case["xs"]), int(case["k"]))
            for case in input_manifest["cases"]
        ]
    # boundary共通ケースを先に変換する
    cases = [
        (list(case["xs"]), int(case["k"]))
        for case in input_manifest["shared_cases"]
    ]
    # 対象specだけのfilter到達ケースを加える
    for case in input_manifest["targeted_filter_cases"]:
        # 他の意味AST向けcaseを飛ばす
        if case["spec_id"] != spec_id:
            # 次caseへ進む
            continue
        # 対象caseを末尾へ加える
        cases.append((list(case["xs"]), int(case["k"])))
        # specごとに最大1件なので探索を終える
        break
    # 共通30件と任意の固有1件を返す
    return cases


# 固定caseの隔離検証processを必要範囲で再利用する
class SuiteVerifier:
    """通常集合では全件、boundaryでは同一spec内でprocessを再利用する。"""

    # 検証条件を保存する
    def __init__(
        self,
        suite_name: str,
        input_manifest: Mapping[str, Any],
        timeout_seconds: float,
        max_source_chars: int,
    ) -> None:
        # 集合名を保持する
        self.suite_name = suite_name
        # 入力manifestを保持する
        self.input_manifest = input_manifest
        # 1コード全caseのtimeoutを保持する
        self.timeout_seconds = timeout_seconds
        # 静的検査の文字数上限を保持する
        self.max_source_chars = max_source_chars
        # 現在のcase組を識別するkeyを初期化する
        self.current_key: str | None = None
        # 遅延作成するsessionを初期化する
        self.session: GeneratedCodeVerifierSession | None = None

    # 生成コードを対応caseで検証する
    def verify(
        self,
        source: str,
        semantic_ast: Mapping[str, Any],
        spec_id: str,
    ) -> dict[str, Any]:
        """静的検査と隔離実行の結果を辞書で返す。"""

        # boundaryだけspecごと、他集合は全体で同じkeyを使う
        key = spec_id if self.suite_name == "boundary" else self.suite_name
        # case組が変わるときだけprocessを作り直す
        if key != self.current_key:
            # 古いsessionを安全に閉じる
            self.close()
            # 対象recordのcase組を作る
            cases = cases_for_record(self.input_manifest, self.suite_name, spec_id)
            # 新しい隔離検証sessionを作る
            self.session = GeneratedCodeVerifierSession(
                cases,
                self.timeout_seconds,
                self.max_source_chars,
            )
            # worker processを開始する
            self.session.__enter__()
            # 現在keyを更新する
            self.current_key = key
        # session存在を型checkerへ伝える
        assert self.session is not None
        # 検証結果をJSON互換辞書へ変換する
        return self.session.verify(source, semantic_ast).to_record()

    # 子processを閉じる
    def close(self) -> None:
        """現在の検証sessionがあれば終了する。"""

        # session未作成なら何もしない
        if self.session is None:
            # 終了済み状態を維持する
            return
        # processとqueueを終了する
        self.session.close()
        # session参照を破棄する
        self.session = None
        # keyも未選択へ戻す
        self.current_key = None

    # with終了時にも必ずprocessを閉じる
    def __enter__(self) -> SuiteVerifier:
        # 自身を返す
        return self

    # 例外時もprocessを残さない
    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        # 保持中sessionを閉じる
        self.close()


# 評価ZIPから必要項目だけを逐次読む
def iter_suite_records(
    archive_path: Path,
    suite_name: str,
    suite_config: Mapping[str, Any],
) -> Iterable[dict[str, Any]]:
    """集合のJSONLを元順序の最小レコードへ変換する。"""

    # ZIPを読み取り専用で開く
    with zipfile.ZipFile(archive_path, mode="r") as archive:
        # 対象memberをbinary streamで開く
        with archive.open(str(suite_config["member"]), mode="r") as binary_handle:
            # UTF-8 text streamへ変換する
            with io.TextIOWrapper(binary_handle, encoding="utf-8") as text_handle:
                # 行番号付きで逐次処理する
                for source_index, line in enumerate(text_handle):
                    # 空行を拒否する
                    if not line.strip():
                        # 位置を示して停止する
                        raise ValueError(f"評価JSONLに空行があります: {suite_name}:{source_index + 1}")
                    # 一行JSONを読む
                    record = json.loads(line)
                    # 分割をtestへ固定する
                    if record.get("split") != "test":
                        # validation混入を拒否する
                        raise ValueError(f"評価recordのsplitがtestではありません: {suite_name}")
                    # 集合名を照合する
                    if record.get("test_suite") != suite_name:
                        # 別集合混入を拒否する
                        raise ValueError(f"評価recordのtest_suiteが一致しません: {suite_name}")
                    # 入力集合IDを一件だけ参照させる
                    if record.get("tests") != [suite_config["test_set_id"]]:
                        # hidden入力取り違えを拒否する
                        raise ValueError(f"評価recordのtestsが一致しません: {suite_name}")
                    # 必須文字列を取得する
                    required_strings = (
                        "record_id",
                        "spec_id",
                        "instruction_id",
                        "instruction_ja",
                        "reference_code",
                    )
                    # 空または非文字列を拒否する
                    if any(
                        not isinstance(record.get(key), str) or not record[key]
                        for key in required_strings
                    ):
                        # 元行を示して停止する
                        raise ValueError(f"評価recordの必須文字列が不正です: {suite_name}:{source_index + 1}")
                    # 意味ASTをobjectに限定する
                    if not isinstance(record.get("semantic_ast"), dict):
                        # 実行照合不能として拒否する
                        raise ValueError(f"semantic_astが不正です: {suite_name}:{source_index + 1}")
                    # 意味ASTを取得する
                    semantic_ast = record["semantic_ast"]
                    # sequence形式は要素数、単独形式は1操作として数える
                    operation_count = (
                        len(semantic_ast["sequence"])
                        if set(semantic_ast) == {"sequence"}
                        and isinstance(semantic_ast["sequence"], list)
                        else 1
                    )
                    # 評価に必要な項目だけ返す
                    yield {
                        "difficulty": record.get("difficulty"),
                        "instruction_id": record["instruction_id"],
                        "instruction_ja": record["instruction_ja"],
                        "operation_count": operation_count,
                        "record_id": record["record_id"],
                        "reference_code": record["reference_code"],
                        "semantic_ast": semantic_ast,
                        "source_index": source_index,
                        "spec_id": record["spec_id"],
                    }


# 既存結果から再開用record IDを読む
def read_completed_ids(path: Path) -> set[str]:
    """有効な既存JSONLのrecord_id集合を返す。"""

    # ファイル未作成なら空集合を返す
    if not path.exists():
        # 新規実行として扱う
        return set()
    # 完了IDを保持する
    completed: set[str] = set()
    # UTF-8で結果を読む
    with path.open("r", encoding="utf-8") as handle:
        # 行番号付きで検査する
        for line_number, line in enumerate(handle, start=1):
            # 途中で壊れた空行を拒否する
            if not line.strip():
                # 再開前に手動確認を促す
                raise ValueError(f"既存評価JSONLに空行があります: {path}:{line_number}")
            # 結果recordを読む
            record = json.loads(line)
            # record IDを取得する
            record_id = record.get("record_id")
            # 文字列以外を拒否する
            if not isinstance(record_id, str) or not record_id:
                # 壊れた既存結果から再開しない
                raise ValueError(f"既存評価JSONLのrecord_idが不正です: {path}:{line_number}")
            # 重複結果を拒否する
            if record_id in completed:
                # 二重集計を防ぐ
                raise ValueError(f"既存評価JSONLにrecord_id重複があります: {record_id}")
            # 完了集合へ加える
            completed.add(record_id)
    # 検査済みID集合を返す
    return completed


# safetensorsから推論モデルを復元する
def load_model(
    model_directory: Path,
    model_config_name: str,
    weights_name: str,
    device_name: str,
    dtype_name: str,
) -> tuple[BokuNanoForCausalLM, torch.device]:
    """最終重みを指定deviceとdtypeへ読み込む。"""

    # autoならCUDAを優先する
    resolved_device_name = (
        "cuda" if device_name == "auto" and torch.cuda.is_available() else device_name
    )
    # CUDAなしautoはCPUへ落とす
    if resolved_device_name == "auto":
        # 実行可能なCPUを選ぶ
        resolved_device_name = "cpu"
    # CUDA指定時に利用可否を確認する
    if resolved_device_name == "cuda" and not torch.cuda.is_available():
        # 暗黙CPU実行による長時間化を避ける
        raise RuntimeError("CUDAが利用できません")
    # torch deviceを作る
    device = torch.device(resolved_device_name)
    # dtype名をtorch型へ変換する
    dtype_map = {"float32": torch.float32, "bfloat16": torch.bfloat16}
    # 未対応dtypeを拒否する
    if dtype_name not in dtype_map:
        # 設定値を明示する
        raise ValueError(f"未対応dtypeです: {dtype_name}")
    # CPU bfloat16を正式評価では許可しない
    if device.type == "cpu" and dtype_name != "float32":
        # 数値・速度条件を明確にする
        raise ValueError("CPU評価ではdtype=float32を指定してください")
    # モデル構造設定を読む
    model_values = json.loads(
        (model_directory / model_config_name).read_text(encoding="utf-8")
    )
    # 検査済みモデル設定を作る
    model_config = BokuNanoConfig.from_dict(model_values)
    # 同じ構造のモデルを作る
    model = BokuNanoForCausalLM(model_config)
    # CPU上でsafetensorsを読む
    state = load_safetensors(str(model_directory / weights_name), device="cpu")
    # 全parameterを厳密一致で読み込む
    model.load_state_dict(state, strict=True)
    # 指定deviceとdtypeへ移す
    model.to(device=device, dtype=dtype_map[dtype_name])
    # dropoutを無効化する
    model.eval()
    # モデルとdeviceを返す
    return model, device


# 一つのbufferを生成・検証して結果へ追記する
def process_buffer(
    records: Sequence[dict[str, Any]],
    model: BokuNanoForCausalLM,
    tokenizer: Tokenizer,
    special_ids: Mapping[str, int],
    generation_config: Mapping[str, Any],
    device: torch.device,
    verifier: SuiteVerifier,
    suite_name: str,
) -> list[dict[str, Any]]:
    """prompt長別batch生成後、元順序で実行検証する。"""

    # prompt長ごとにrecordをまとめる
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    # 全recordをtoken化する
    for record in records:
        # 学習時と同じprompt ID列を作る
        prompt_ids = encode_prompt(
            tokenizer,
            record["instruction_ja"],
            special_ids,
            model.config.context_length,
        )
        # 後続処理用に一時保持する
        prepared = dict(record)
        # prompt ID列を追加する
        prepared["prompt_token_ids"] = prompt_ids
        # 同じ長さのgroupへ加える
        grouped[len(prompt_ids)].append(prepared)
    # source indexごとの生成結果を保持する
    generated_by_index: dict[int, dict[str, Any]] = {}
    # batch sizeを取得する
    batch_size = int(generation_config["batch_size"])
    # prompt長の小さい順に処理する
    for prompt_length in sorted(grouped):
        # 同長record群を取得する
        group = grouped[prompt_length]
        # batch sizeごとに分割する
        for start in range(0, len(group), batch_size):
            # 現在batchを取り出す
            batch = group[start : start + batch_size]
            # greedy生成する
            outputs = greedy_generate_equal_length(
                model,
                [item["prompt_token_ids"] for item in batch],
                int(special_ids["eos"]),
                int(special_ids["pad"]),
                int(generation_config["max_new_tokens"]),
                model.config.context_length,
                device,
            )
            # recordと生成結果を対応付ける
            for item, output in zip(batch, outputs, strict=True):
                # token IDsをコード文字列へ戻す
                generated_code = tokenizer.decode(
                    output["generated_token_ids"],
                    skip_special_tokens=False,
                )
                # 一時結果を元indexへ保存する
                generated_by_index[item["source_index"]] = {
                    **item,
                    **output,
                    "generated_code": generated_code,
                }
    # 元JSONL順で検証結果を作る
    results: list[dict[str, Any]] = []
    # source index順に並べる
    for source_index in sorted(generated_by_index):
        # 対象生成結果を取得する
        item = generated_by_index[source_index]
        # 既存安全検査と固定入力実行を行う
        verification = verifier.verify(
            item["generated_code"],
            item["semantic_ast"],
            item["spec_id"],
        )
        # 永続化する結果を作る
        results.append(
            {
                "difficulty": item["difficulty"],
                "evaluator_version": EVALUATOR_VERSION,
                "exact_code_match": item["generated_code"] == item["reference_code"],
                "generated_code": item["generated_code"],
                "generated_code_sha256": text_sha256(item["generated_code"]),
                "generated_token_count": len(item["generated_token_ids"]),
                "instruction_id": item["instruction_id"],
                "operation_count": item["operation_count"],
                "passed": bool(verification["tests_passed"]),
                "prompt_token_count": len(item["prompt_token_ids"]),
                "record_id": item["record_id"],
                "source_index": item["source_index"],
                "spec_id": item["spec_id"],
                "suite": suite_name,
                "termination": item["termination"],
                "verification": verification,
            }
        )
    # buffer分の結果を返す
    return results


# JSONL結果を集計する
def summarize_results(
    results_path: Path,
    suite_name: str,
    expected_record_count: int,
) -> dict[str, Any]:
    """集合全体の正解率と失敗内訳を再計算する。"""

    # 総件数を初期化する
    total = 0
    # 合格件数を初期化する
    passed = 0
    # 完全一致件数を初期化する
    exact_matches = 0
    # 終了理由を集計する
    termination_counts: Counter[str] = Counter()
    # timeout件数を初期化する
    timeout_count = 0
    # operation数別集計を保持する
    by_operation_count: dict[int, Counter[str]] = defaultdict(Counter)
    # 結果JSONLを読む
    with results_path.open("r", encoding="utf-8") as handle:
        # 一件ずつ集計する
        for line in handle:
            # JSONへ変換する
            record = json.loads(line)
            # 対象集合以外を拒否する
            if record.get("suite") != suite_name:
                # 出力先混同を明示する
                raise ValueError(f"結果JSONLに別suiteが含まれます: {results_path}")
            # 総件数を増やす
            total += 1
            # 合否を加算する
            passed += int(bool(record["passed"]))
            # 完全一致を加算する
            exact_matches += int(bool(record["exact_code_match"]))
            # 終了理由を加算する
            termination_counts[str(record["termination"])] += 1
            # timeoutを加算する
            timeout_count += int(bool(record["verification"]["timeout"]))
            # 操作数を取得する
            operation_count = int(record["operation_count"])
            # 操作数別総数を加算する
            by_operation_count[operation_count]["total"] += 1
            # 操作数別合格数を加算する
            by_operation_count[operation_count]["passed"] += int(bool(record["passed"]))
    # 0除算を避けて率を計算する
    pass_rate = passed / total if total else 0.0
    # 集合summaryを返す
    return {
        "by_operation_count": {
            str(key): {
                "pass_rate": values["passed"] / values["total"],
                "passed": values["passed"],
                "total": values["total"],
            }
            for key, values in sorted(by_operation_count.items())
        },
        "evaluated_record_count": total,
        "exact_code_match_count": exact_matches,
        "expected_record_count": expected_record_count,
        "pass_rate": pass_rate,
        "passed_record_count": passed,
        "status": "completed" if total == expected_record_count else "partial",
        "suite": suite_name,
        "termination_counts": dict(sorted(termination_counts.items())),
        "timeout_count": timeout_count,
    }


# 一つの評価集合を実行する
def evaluate_suite(
    config: Mapping[str, Any],
    suite_name: str,
    model: BokuNanoForCausalLM,
    device: torch.device,
    tokenizer: Tokenizer,
    special_ids: Mapping[str, int],
    archive_path: Path,
    output_directory: Path,
    max_records: int | None,
    resume: bool,
    overwrite: bool,
) -> dict[str, Any]:
    """一集合を再開可能なJSONLへ逐次評価する。"""

    # 集合設定を取得する
    suite_config = config["evaluation_data"]["suites"][suite_name]
    # 結果パスを決める
    results_path = output_directory / f"{suite_name}_results.jsonl"
    # summaryパスを決める
    summary_path = output_directory / f"{suite_name}_summary.json"
    # 上書き指定時だけ既存2ファイルを削除する
    if overwrite:
        # 結果JSONLがあれば削除する
        results_path.unlink(missing_ok=True)
        # 古いsummaryも削除する
        summary_path.unlink(missing_ok=True)
    # 再開なしで既存結果を保護する
    if results_path.exists() and not resume:
        # 明示選択を求める
        raise FileExistsError(
            f"評価結果が既にあります: {results_path}. --resumeまたは--overwriteを指定してください"
        )
    # 再開時の完了IDを読む
    completed_ids = read_completed_ids(results_path) if resume else set()
    # 入力manifestを読む
    input_path = configured_path(suite_config["inputs"])
    # JSON objectへ変換する
    input_manifest = json.loads(input_path.read_text(encoding="utf-8"))
    # 出力先を作る
    output_directory.mkdir(parents=True, exist_ok=True)
    # 今回の新規処理件数を初期化する
    new_count = 0
    # 生成bufferを初期化する
    buffer: list[dict[str, Any]] = []
    # buffer上限を取得する
    buffer_size = int(config["generation"]["buffer_size"])
    # append modeで結果を開く
    with results_path.open("a", encoding="utf-8") as output_handle:
        # 集合に対応した検証sessionを管理する
        with SuiteVerifier(
            suite_name,
            input_manifest,
            float(config["verification"]["timeout_seconds"]),
            int(config["verification"]["max_source_chars"]),
        ) as verifier:
            # 評価レコードを元順序で読む
            for record in iter_suite_records(archive_path, suite_name, suite_config):
                # 再開済みrecordを飛ばす
                if record["record_id"] in completed_ids:
                    # 次recordへ進む
                    continue
                # 今回の件数上限へ達したら読むのを止める
                if max_records is not None and new_count + len(buffer) >= max_records:
                    # 残りを次回再開へ残す
                    break
                # bufferへ加える
                buffer.append(record)
                # 上限未満なら続けて読む
                if len(buffer) < buffer_size:
                    # 次recordへ進む
                    continue
                # bufferを生成・検証する
                results = process_buffer(
                    buffer,
                    model,
                    tokenizer,
                    special_ids,
                    config["generation"],
                    device,
                    verifier,
                    suite_name,
                )
                # 全結果をJSONLへ追記する
                for result in results:
                    # 一行JSONとして保存する
                    output_handle.write(
                        json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n"
                    )
                # 中断時に再開可能な位置まで反映する
                output_handle.flush()
                # 新規件数を加算する
                new_count += len(results)
                # bufferを空にする
                buffer.clear()
            # 最後の端数bufferを処理する
            if buffer:
                # 端数も同じ条件で生成・検証する
                results = process_buffer(
                    buffer,
                    model,
                    tokenizer,
                    special_ids,
                    config["generation"],
                    device,
                    verifier,
                    suite_name,
                )
                # 結果を一件ずつ保存する
                for result in results:
                    # 一行JSONとして追記する
                    output_handle.write(
                        json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n"
                    )
                # 全端数をfilesystemへ渡す
                output_handle.flush()
                # 新規件数を更新する
                new_count += len(results)
    # 全結果からsummaryを作り直す
    summary = summarize_results(
        results_path,
        suite_name,
        int(suite_config["expected_record_count"]),
    )
    # 件数制限なしの正式実行では期待件数との完全一致を要求する
    if max_records is None and summary["status"] != "completed":
        # 欠落データや壊れたresume結果を成功扱いしない
        raise ValueError(
            f"評価件数が期待値と一致しません: {suite_name}: "
            f"{summary['evaluated_record_count']} != {summary['expected_record_count']}"
        )
    # 今回追加した件数を記録する
    summary["new_record_count"] = new_count
    # summaryを原子的に保存する
    write_json_atomic(summary_path, summary)
    # 呼び出し元へ返す
    return summary


# 5評価集合を指定順で実行する
def evaluate(
    config_path: Path,
    selected_suites: Sequence[str],
    max_records: int | None,
    model_directory_override: Path | None,
    output_directory_override: Path | None,
    resume: bool,
    overwrite: bool,
) -> dict[str, Any]:
    """モデルを一度だけ読み、選択した集合を評価する。"""

    # 設定と固定artifactを推論前に検査する
    validation = validate_configuration(
        config_path,
        model_directory_override,
        output_directory_override,
    )
    # 評価設定を読む
    config = load_config(config_path)
    # modelディレクトリを決める
    model_directory = configured_path(validation["model_directory"])
    # 出力先を決める
    output_directory = configured_path(validation["output_directory"])
    # tokenizerを読み込む
    tokenizer = Tokenizer.from_file(str(configured_path(config["tokenizer"]["path"])))
    # 特殊token IDを整数へ変換する
    special_ids = {
        name: int(value)
        for name, value in config["tokenizer"]["special_token_ids"].items()
    }
    # 最終モデルを読み込む
    model, device = load_model(
        model_directory,
        str(config["model"]["config"]),
        str(config["model"]["weights"]),
        str(config["generation"]["device"]),
        str(config["generation"]["dtype"]),
    )
    # 評価ZIPパスを取得する
    archive_path = configured_path(config["evaluation_data"]["archive"])
    # 入力変更検査用hashを保存する
    archive_sha256_before = file_sha256(archive_path)
    # 開始時刻を保存する
    started = time.monotonic()
    # 集合別結果を保持する
    suite_summaries: dict[str, Any] = {}
    # 正式順を維持して選択集合を実行する
    for suite_name in SUPPORTED_SUITES:
        # 未選択集合を飛ばす
        if suite_name not in selected_suites:
            # 次集合へ進む
            continue
        # 一集合を評価する
        suite_summaries[suite_name] = evaluate_suite(
            config,
            suite_name,
            model,
            device,
            tokenizer,
            special_ids,
            archive_path,
            output_directory,
            max_records,
            resume,
            overwrite,
        )
    # 読み取り後hashを再計算する
    archive_sha256_after = file_sha256(archive_path)
    # 評価データが変化していないことを確認する
    if archive_sha256_after != archive_sha256_before:
        # 結果の前提が崩れたため停止する
        raise ValueError("評価中に評価ZIPが変更されました")
    # 全体manifestを作る
    manifest = {
        "archive_sha256_after": archive_sha256_after,
        "archive_sha256_before": archive_sha256_before,
        "archive_unchanged": archive_sha256_after == archive_sha256_before,
        "config": display_path(config_path.resolve()),
        "config_sha256": validation["config_sha256"],
        "device": str(device),
        "dtype": str(config["generation"]["dtype"]),
        "elapsed_seconds": time.monotonic() - started,
        "evaluator_version": EVALUATOR_VERSION,
        "generation": dict(config["generation"]),
        "model_directory": display_path(model_directory),
        "model_sha256": validation["model_sha256"],
        "platform": platform.platform(),
        "python": platform.python_version(),
        "selected_suites": list(selected_suites),
        "suites": suite_summaries,
        "tokenizer_sha256": validation["tokenizer_sha256"],
        "torch": torch.__version__,
    }
    # 全体manifestを保存する
    write_json_atomic(output_directory / "evaluation_manifest.json", manifest)
    # 結果を返す
    return manifest


# CLIを実行する
def main() -> None:
    """引数を検査し、設定確認または評価を実行する。"""

    # CLI引数を読む
    args = parse_args()
    # 排他的な出力操作を同時指定させない
    if args.resume and args.overwrite:
        # 意図が曖昧な操作を拒否する
        raise ValueError("--resumeと--overwriteは同時指定できません")
    # 件数上限を正に限定する
    if args.max_records is not None and args.max_records <= 0:
        # 0件実行の曖昧さを避ける
        raise ValueError("--max-recordsは正の整数にしてください")
    # 推論前検証だけを実行する
    if args.validate_config:
        # artifact検査結果を得る
        result = validate_configuration(
            args.config.resolve(),
            args.model_directory,
            args.output_directory,
        )
        # 人間と自動処理の両方が読めるJSONを表示する
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        # 推論せず終了する
        return
    # 未指定時は正式5集合すべてを選ぶ
    selected_suites = tuple(args.suite or SUPPORTED_SUITES)
    # 重複suite指定を拒否する
    if len(selected_suites) != len(set(selected_suites)):
        # 二重評価を防ぐ
        raise ValueError("--suiteが重複しています")
    # 評価を実行する
    result = evaluate(
        args.config.resolve(),
        selected_suites,
        args.max_records,
        args.model_directory,
        args.output_directory,
        args.resume,
        args.overwrite,
    )
    # 完了manifestを標準出力にも表示する
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


# 直接実行時だけCLIを開始する
if __name__ == "__main__":
    # mainを呼び出す
    main()
