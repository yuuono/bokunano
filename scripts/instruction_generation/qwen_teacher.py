"""Qwen3を非thinkingモードで呼び出す共通処理。"""

# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# 生成結果を変更不能なデータクラスとして保持するために使う
from dataclasses import dataclass
# 文字列のSHA-256を計算するために使う
import hashlib
# モデル出力と設定値をJSONとして扱うために使う
import json
# プロンプトファイルのパスを扱うために使う
from pathlib import Path
# モデルrevisionとthinkingタグの形式を厳密に検査するために使う
import re
# user prompt内の$name形式の変数を置換するために使う
from string import Template
# 設定辞書と任意型の型注釈に使う
from typing import Any, Mapping


# system promptとuser promptの境界が曖昧にならないよう専用区切りを定義する
PROMPT_SEPARATOR = "\n\0\n"

# 正式生成で指定できるHugging FaceコミットIDを40桁の16進数に限定する
COMMIT_ID_PATTERN = re.compile(r"[0-9a-fA-F]{40}")
# 大文字小文字や属性の有無にかかわらずthink開始・終了タグを検出する
THINK_TAG_PATTERN = re.compile(r"<\s*/?\s*think\b[^>]*>", re.IGNORECASE)


# この工程を担当する関数を定義する
def sha256_text(text: str) -> str:
    """文字列のUTF-8バイト列からSHA-256を計算する。"""

    # 入力文字列をUTF-8へ変換してSHA-256の16進文字列を返す
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# この工程を担当する関数を定義する
def canonical_json(value: object) -> str:
    """ハッシュやプロンプトに使用する決定的なJSON文字列を作る。"""

    # 日本語を保持し、キー順と区切りを固定してJSONへ変換する
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# この工程を担当する関数を定義する
def render_prompt(path: Path, values: Mapping[str, object]) -> str:
    """テンプレート内の$nameを値で置換する。"""

    # UTF-8でプロンプトテンプレートを読み込む
    template = Template(path.read_text(encoding="utf-8"))
    # 数値やJSONも置換できるよう、すべての値を文字列へ変換する
    rendered_values = {key: str(value) for key, value in values.items()}
    # 未定義変数を見逃さないsubstituteでテンプレートを展開する
    return template.substitute(rendered_values)


# この工程を担当する関数を定義する
def prompt_hash(system_prompt: str, user_prompt: str) -> str:
    """system/user promptを区切り込みでハッシュ化する。"""

    # 二つのプロンプトを専用区切りで連結してハッシュ化する
    return sha256_text(system_prompt + PROMPT_SEPARATOR + user_prompt)


# この工程を担当する関数を定義する
def validate_model_config(model_config: Mapping[str, Any]) -> dict[str, Any]:
    """Qwen読み込み設定をモデルのロード前に検査する。"""

    # モデル設定として認めるキーを列挙する
    expected = {
        # この処理で扱う文字列を一覧へ加える
        "model_id",
        # この処理で扱う文字列を一覧へ加える
        "model_path",
        # この処理で扱う文字列を一覧へ加える
        "revision",
        # この処理で扱う文字列を一覧へ加える
        "device_map",
        # この処理で扱う文字列を一覧へ加える
        "attn_implementation",
        # この処理で扱う文字列を一覧へ加える
        "trust_remote_code",
        # この処理で扱う文字列を一覧へ加える
        "local_files_only",
        # この処理で扱う文字列を一覧へ加える
        "require_cuda",
        # この処理で扱う文字列を一覧へ加える
        "enable_thinking",
    }
    # キーの不足や余分なキーがあれば設定ミスとして停止する
    if set(model_config) != expected:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("model設定の項目が不正です")
    # モデルIDが空でない文字列であることを確認する
    _required_string(model_config, "model_id")
    # 実際に読み込むローカル重みのディレクトリを確認する
    model_path = Path(_required_string(model_config, "model_path"))
    # 条件を満たす場合だけ次の処理を行う
    if not model_path.is_absolute():
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("model_pathは絶対パスにしてください")
    # 条件を満たす場合だけ次の処理を行う
    if not model_path.is_dir():
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"model_pathが見つかりません: {model_path}")
    # Transformersが最低限必要とする設定、tokenizer、重みの存在を確認する
    required_files = ("config.json", "tokenizer_config.json", "tokenizer.json")
    # missing_filesへこの工程で使用する値を設定する
    missing_files = [
        # 次の値または処理を現在の構造へ組み込む
        name for name in required_files if not (model_path / name).is_file()
    ]
    # 条件を満たす場合だけ次の処理を行う
    if missing_files:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"model_pathに必要なファイルがありません: {missing_files}")
    # 条件を満たす場合だけ次の処理を行う
    if not any(model_path.glob("*.safetensors")):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("model_pathにsafetensors重みがありません")
    # モデルrevisionが再現可能な40桁のコミットIDであることを確認する
    _commit_id(model_config, "revision")
    # デバイス割当方法が空でない文字列であることを確認する
    _required_string(model_config, "device_map")
    # Attention実装名を設定から取り出す
    attn_implementation = model_config.get("attn_implementation")
    # Attention実装名は文字列またはnullだけを許可する
    if attn_implementation is not None and not isinstance(attn_implementation, str):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("attn_implementationは文字列またはnullにしてください")
    # 真偽値で指定する設定項目を順番に検査する
    for key in (
        # この処理で扱う文字列を一覧へ加える
        "trust_remote_code",
        # この処理で扱う文字列を一覧へ加える
        "local_files_only",
        # この処理で扱う文字列を一覧へ加える
        "require_cuda",
        # この処理で扱う文字列を一覧へ加える
        "enable_thinking",
    # 次の値または処理を現在の構造へ組み込む
    ):
        # bool以外の値が指定されていれば停止する
        if type(model_config.get(key)) is not bool:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"{key}は真偽値にしてください")
    # 思考過程を保存しない課題方針に合わせてthinkingを必ず無効にする
    if model_config["enable_thinking"] is not False:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("Qwen3はenable_thinking=falseで使用してください")
    # ローカル重みだけを使い、実行時にHubへ接続しない設定を必須にする
    if model_config["local_files_only"] is not True:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("ローカル重みの使用時はlocal_files_only=trueにしてください")
    # 呼び出し元が安全に保持できるよう設定辞書をコピーして返す
    return dict(model_config)


# この工程を担当する関数を定義する
def validate_sampling_config(sampling: Mapping[str, Any]) -> dict[str, Any]:
    """生成sampling設定をモデルのロード前に検査する。"""

    # sampling設定として認めるキーを列挙する
    expected = {
        # この処理で扱う文字列を一覧へ加える
        "max_new_tokens",
        # この処理で扱う文字列を一覧へ加える
        "do_sample",
        # この処理で扱う文字列を一覧へ加える
        "temperature",
        # この処理で扱う文字列を一覧へ加える
        "top_p",
        # この処理で扱う文字列を一覧へ加える
        "top_k",
        # この処理で扱う文字列を一覧へ加える
        "repetition_penalty",
    }
    # キーの不足や余分なキーがあれば停止する
    if set(sampling) != expected:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("sampling設定の項目が不正です")
    # 最大生成トークン数が正の整数であることを確認する
    _positive_int(sampling, "max_new_tokens")
    # samplingの有効・無効が真偽値であることを確認する
    if type(sampling.get("do_sample")) is not bool:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("do_sampleは真偽値にしてください")
    # 温度が正の数であることを確認する
    _positive_number(sampling, "temperature")
    # top-pが0より大きく1以下であることを確認する
    _probability(sampling, "top_p")
    # top-kが正の整数であることを確認する
    _positive_int(sampling, "top_k")
    # 反復ペナルティが正の数であることを確認する
    _positive_number(sampling, "repetition_penalty")
    # 検査済み設定のコピーを返す
    return dict(sampling)


# この工程を担当する関数を定義する
def _parse_json_object(raw_text: str) -> dict[str, Any]:
    """モデル出力からJSONオブジェクトを取り出す。"""

    # モデル出力の前後に付いた空白と改行を除く
    text = raw_text.strip()
    # モデルが誤ってMarkdownコードフェンスを付けた場合だけ外側を除去する
    if text.startswith("```"):
        # フェンスを行単位で扱う
        lines = text.splitlines()
        # 開始行、本文、終了フェンスが揃っていることを確認する
        if len(lines) >= 3 and lines[-1].strip() == "```":
            # 先頭と末尾のフェンスを取り除く
            text = "\n".join(lines[1:-1]).strip()
            # 独立したjson言語指定が残った場合は取り除く
            if text.startswith("json\n"):
                # textへこの工程で使用する値を設定する
                text = text[5:].lstrip()

    # まず出力全体をJSONとして解析する
    try:
        # parsedへこの工程で使用する値を設定する
        parsed = json.loads(text)
    # 発生した例外を受け取り、安全に処理する
    except json.JSONDecodeError:
        # 前後に説明が混入した場合に備え、最初の開き波括弧を探す
        start = text.find("{")
        # JSON候補の末尾となる最後の閉じ波括弧を探す
        end = text.rfind("}")
        # 波括弧で囲まれた範囲がなければ解析不能として停止する
        if start < 0 or end <= start:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("モデル出力にJSONオブジェクトがありません") from None
        # 波括弧で囲まれた範囲だけを再度JSONとして解析する
        try:
            # parsedへこの工程で使用する値を設定する
            parsed = json.loads(text[start : end + 1])
        # 発生した例外を受け取り、安全に処理する
        except json.JSONDecodeError as error:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError("モデル出力のJSONを解析できません") from error

    # ルートがJSONオブジェクトであることを確認する
    if not isinstance(parsed, dict):
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError("モデル出力のルートはJSONオブジェクトにしてください")
    # 後続の形式別検査へ渡す
    return parsed


# この工程を担当する関数を定義する
def parse_json_string_list(raw_text: str, key: str) -> list[str]:
    """モデル出力から、指定キーに入った文字列配列を取り出す。"""

    # コードフェンスや前後の説明を処理してJSONオブジェクトを取得する
    parsed = _parse_json_object(raw_text)
    # 指定キー一つだけを持つJSONオブジェクトであることを確認する
    if set(parsed) != {key}:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"モデル出力はキー{key!r}だけを持つJSONにしてください")
    # 指定キーに対応する候補一覧を取り出す
    values = parsed[key]
    # 候補一覧が空でない配列であることを確認する
    if not isinstance(values, list) or not values:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key!r}は空でない配列にしてください")

    # 検査済み文字列を格納する空の配列を作る
    result: list[str] = []
    # モデルが返した各候補を順番に検査する
    for value in values:
        # 候補が文字列でなければ停止する
        if not isinstance(value, str):
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"{key!r}の各要素は文字列にしてください")
        # 候補の前後に付いた空白を除く
        candidate = value.strip()
        # 空文字列になった候補は許可しない
        if not candidate:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(f"{key!r}に空文字列を入れないでください")
        # 検査を通過した候補を結果へ追加する
        result.append(candidate)
    # 検査済み候補一覧を返す
    return result


# この工程を担当する関数を定義する
def parse_json_string_object_list(
    # 次の値または処理を現在の構造へ組み込む
    raw_text: str,
    # 次の値または処理を現在の構造へ組み込む
    key: str,
    # 次の値または処理を現在の構造へ組み込む
    object_keys: set[str],
# 次の値または処理を現在の構造へ組み込む
) -> list[dict[str, str]]:
    """指定キー配下から、同じ文字列キーを持つオブジェクト配列を取り出す。"""

    # コードフェンスや前後の説明を処理してJSONオブジェクトを取得する
    parsed = _parse_json_object(raw_text)
    # 最上位には指定された配列キー一つだけを許可する
    if set(parsed) != {key}:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"モデル出力はキー{key!r}だけを持つJSONにしてください")
    # 指定キーに対応する候補一覧を取り出す
    values = parsed[key]
    # 候補一覧が空でない配列であることを確認する
    if not isinstance(values, list) or not values:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key!r}は空でない配列にしてください")

    # 検査済みの文字列オブジェクトを格納する
    result: list[dict[str, str]] = []
    # 配列内の各オブジェクトを順番に検査する
    for value in values:
        # オブジェクト以外やキーの過不足を拒否する
        if not isinstance(value, dict) or set(value) != object_keys:
            # 不正な状態を例外として通知して処理を停止する
            raise ValueError(
                # 次の値または処理を現在の構造へ組み込む
                f"{key!r}の各要素はキー{sorted(object_keys)!r}だけを持つ"
                "オブジェクトにしてください"
            )
        # 各フィールドの前後空白を除いて保持する
        item: dict[str, str] = {}
        # 対象を一件ずつ取り出して処理する
        for object_key in sorted(object_keys):
            # fieldへこの工程で使用する値を設定する
            field = value[object_key]
            # 条件を満たす場合だけ次の処理を行う
            if not isinstance(field, str) or not field.strip():
                # 不正な状態を例外として通知して処理を停止する
                raise ValueError(
                    # 次の値または処理を現在の構造へ組み込む
                    f"{key!r}内の{object_key!r}は空でない文字列にしてください"
                )
            # item[object_key]へこの工程で使用する値を設定する
            item[object_key] = field.strip()
        # すべてのフィールドが検査済みの候補だけを追加する
        result.append(item)
    # 検査済みオブジェクト配列を返す
    return result


# この工程を担当する関数を定義する
def reject_thinking_output(raw_text: str) -> str:
    """thinkタグを含むモデル出力を、解析や保存の前に拒否する。"""

    # 非thinking設定に反してthink開始・終了タグが一つでも出たかを調べる
    if THINK_TAG_PATTERN.search(raw_text):
        # 思考過程を候補や生出力へ保存しないため、その応答全体を例外にする
        raise ValueError("Qwen出力に<think>タグが含まれているため拒否しました")
    # thinkingタグを含まない検査済み出力だけを呼び出し元へ返す
    return raw_text


# 直後の定義へデコレータを適用する
@dataclass(frozen=True)
# 関連する状態と処理をまとめるクラスを定義する
class GenerationResult:
    """1回の生成結果と再現用メタデータ。"""

    # 次の値または処理を現在の構造へ組み込む
    text: str
    # 次の値または処理を現在の構造へ組み込む
    resolved_revision: str
    # 次の値または処理を現在の構造へ組み込む
    transformers_version: str
    # 次の値または処理を現在の構造へ組み込む
    torch_version: str


# 関連する状態と処理をまとめるクラスを定義する
class QwenTeacher:
    """Transformers経由でQwen3を1プロセスに1回だけ読み込む。"""

    # この工程を担当する関数を定義する
    def __init__(self, model_config: Mapping[str, Any]) -> None:
        # 大容量依存関係は実生成時だけ読み込む
        try:
            # テンソル処理とCUDA推論に使うPyTorchを読み込む
            import torch
            # seed固定とバージョン記録に使うTransformers本体を読み込む
            import transformers
            # モデルとtokenizerを自動選択して読み込むクラスを取得する
            from transformers import AutoModelForCausalLM, AutoTokenizer
        # 発生した例外を受け取り、安全に処理する
        except ImportError as error:
            # 不正な状態を例外として通知して処理を停止する
            raise RuntimeError(
                "Qwen用依存関係がありません。スクリプトをuv runで実行してください。"
            # 次の値または処理を現在の構造へ組み込む
            ) from error

        # generate内でもPyTorchを使えるようインスタンスへ保持する
        self._torch = torch
        # seed固定とバージョン参照のためTransformersを保持する
        self._transformers = transformers
        # 単独利用時にも同じ厳密な設定検査を必ず適用する
        validated_config = validate_model_config(model_config)
        # 生成物へ記録するHugging FaceモデルIDを設定から取得する
        self._model_id = _required_string(validated_config, "model_id")
        # モデルとtokenizerを読み込むローカルディレクトリを取得する
        self._model_path = Path(_required_string(validated_config, "model_path"))
        # 要求するモデルrevisionを40桁の固定コミットIDとして取得する
        revision = _commit_id(validated_config, "revision")
        # CUDAを必須にするかを設定から取得する
        require_cuda = bool(validated_config.get("require_cuda", True))
        # AWQモデルをCUDA必須設定でCPU実行しようとした場合は早期停止する
        if require_cuda and not torch.cuda.is_available():
            # 不正な状態を例外として通知して処理を停止する
            raise RuntimeError(
                "Qwen3 AWQの実行にはCUDA対応環境が必要です。"
                "CUDA環境で実行するか、設定のモデルを変更してください。"
            )

        # tokenizer読込時に渡す再現性・安全性設定をまとめる
        tokenizer_kwargs = {
            # 出力レコードの項目と値を設定する
            "trust_remote_code": bool(validated_config.get("trust_remote_code", False)),
            # 出力レコードの項目と値を設定する
            "local_files_only": True,
        }
        # 指定されたローカルディレクトリからtokenizerを読み込む
        self._tokenizer = AutoTokenizer.from_pretrained(
            # 次の値または処理を現在の構造へ組み込む
            self._model_path,
            # 次の値または処理を現在の構造へ組み込む
            **tokenizer_kwargs,
        )

        # モデル読込時に渡すデバイス割当と安全性設定をまとめる
        model_kwargs: dict[str, Any] = {
            # 出力レコードの項目と値を設定する
            "device_map": validated_config.get("device_map", "auto"),
            # 出力レコードの項目と値を設定する
            "trust_remote_code": bool(validated_config.get("trust_remote_code", False)),
            # 出力レコードの項目と値を設定する
            "local_files_only": True,
            # 出力レコードの項目と値を設定する
            "low_cpu_mem_usage": True,
        }
        # 任意指定のAttention実装名を取り出す
        attn_implementation = validated_config.get("attn_implementation")
        # Attention実装が指定された場合だけモデル引数へ追加する
        if attn_implementation is not None:
            # 次の値または処理を現在の構造へ組み込む
            model_kwargs["attn_implementation"] = attn_implementation
        # Qwen3の因果言語モデルを指定されたローカル重みから読み込む
        self._model = AutoModelForCausalLM.from_pretrained(
            # 次の値または処理を現在の構造へ組み込む
            self._model_path,
            # 次の値または処理を現在の構造へ組み込む
            **model_kwargs,
        )
        # Dropoutなどの学習時動作を止めて推論モードにする
        self._model.eval()
        # ローカル設定にコミットIDがあれば優先し、なければ固定設定値を記録する
        self._resolved_revision = (
            # 次の値または処理を現在の構造へ組み込む
            getattr(self._model.config, "_commit_hash", None)
            # 次の値または処理を現在の構造へ組み込む
            or getattr(self._tokenizer, "_commit_hash", None)
            # 次の値または処理を現在の構造へ組み込む
            or revision
        )

    # 直後の定義へデコレータを適用する
    @property
    # この工程を担当する関数を定義する
    def resolved_revision(self) -> str:
        # JSONへ保存できる文字列として解決済みrevisionを返す
        return str(self._resolved_revision)

    # 直後の定義へデコレータを適用する
    @property
    # この工程を担当する関数を定義する
    def model_id(self) -> str:
        # 実際に読み込んだモデルIDを返す
        return self._model_id

    # 直後の定義へデコレータを適用する
    @property
    # この工程を担当する関数を定義する
    def model_path(self) -> str:
        # 実際に読み込んだローカルモデルディレクトリを返す
        return str(self._model_path)

    # この工程を担当する関数を定義する
    def generate(
        # 次の値または処理を現在の構造へ組み込む
        self,
        # 次の値または処理を現在の構造へ組み込む
        *,
        # 次の値または処理を現在の構造へ組み込む
        system_prompt: str,
        # 次の値または処理を現在の構造へ組み込む
        user_prompt: str,
        # 次の値または処理を現在の構造へ組み込む
        sampling: Mapping[str, Any],
        # 次の値または処理を現在の構造へ組み込む
        seed: int,
    # 次の値または処理を現在の構造へ組み込む
    ) -> GenerationResult:
        """non-thinking chat templateで1件生成する。"""

        # Qwen3のchat templateへ渡すsystem/userメッセージを作る
        messages = [
            # 次の値または処理を現在の構造へ組み込む
            {"role": "system", "content": system_prompt},
            # 次の値または処理を現在の構造へ組み込む
            {"role": "user", "content": user_prompt},
        ]
        # thinkingを明示的に無効化してモデル入力文字列へ変換する
        rendered = self._tokenizer.apply_chat_template(
            # 次の値または処理を現在の構造へ組み込む
            messages,
            # tokenizeへこの工程で使用する値を設定する
            tokenize=False,
            # add_generation_promptへこの工程で使用する値を設定する
            add_generation_prompt=True,
            # enable_thinkingへこの工程で使用する値を設定する
            enable_thinking=False,
        )
        # モデル入力文字列をPyTorchテンソルへ変換する
        model_inputs = self._tokenizer([rendered], return_tensors="pt")
        # 入力テンソルをモデルが配置されたデバイスへ移す
        model_inputs = {
            # 次の値または処理を現在の構造へ組み込む
            name: tensor.to(self._model.device)
            # 対象を一件ずつ取り出して処理する
            for name, tensor in model_inputs.items()
        }

        # Python・NumPy・PyTorchでTransformersが使う乱数seedを固定する
        self._transformers.set_seed(seed)
        # CUDAが有効な場合は全CUDAデバイスのseedも固定する
        if self._torch.cuda.is_available():
            # 次の値または処理を現在の構造へ組み込む
            self._torch.cuda.manual_seed_all(seed)

        # 検査済みsampling値をmodel.generate用引数へ変換する
        generation_kwargs = {
            # 出力レコードの項目と値を設定する
            "max_new_tokens": _positive_int(sampling, "max_new_tokens"),
            # 出力レコードの項目と値を設定する
            "do_sample": bool(sampling.get("do_sample", True)),
            # 出力レコードの項目と値を設定する
            "temperature": _positive_number(sampling, "temperature"),
            # 出力レコードの項目と値を設定する
            "top_p": _probability(sampling, "top_p"),
            # 出力レコードの項目と値を設定する
            "top_k": _positive_int(sampling, "top_k"),
            # 出力レコードの項目と値を設定する
            "repetition_penalty": _positive_number(sampling, "repetition_penalty"),
            # 出力レコードの項目と値を設定する
            "pad_token_id": self._tokenizer.eos_token_id,
        }
        # 勾配計算を無効化してメモリ消費を抑えながら生成する
        with self._torch.inference_mode():
            # generatedへこの工程で使用する値を設定する
            generated = self._model.generate(**model_inputs, **generation_kwargs)
        # 入力部分と生成部分を分離するため入力トークン長を取得する
        prompt_length = model_inputs["input_ids"].shape[1]
        # モデル出力から入力トークン部分を除き、生成部分だけを取り出す
        completion_ids = generated[0][prompt_length:]
        # 特殊トークンも残して生成トークンを検査専用文字列へ戻す
        unchecked_text = self._tokenizer.decode(
            # 次の値または処理を現在の構造へ組み込む
            completion_ids,
            # skip_special_tokensへこの工程で使用する値を設定する
            skip_special_tokens=False,
        )
        # 特殊トークン扱いのthinkタグも解析・保存へ渡さず必ず拒否する
        reject_thinking_output(unchecked_text)
        # 検査合格後にだけ特殊トークンを除いて最終回答文字列へ戻す
        text = self._tokenizer.decode(
            # 次の値または処理を現在の構造へ組み込む
            completion_ids,
            # skip_special_tokensへこの工程で使用する値を設定する
            skip_special_tokens=True,
        # 次の値または処理を現在の構造へ組み込む
        ).strip()
        # 生成文と再現性情報をまとめて返す
        return GenerationResult(
            # textへこの工程で使用する値を設定する
            text=text,
            # resolved_revisionへこの工程で使用する値を設定する
            resolved_revision=self.resolved_revision,
            # transformers_versionへこの工程で使用する値を設定する
            transformers_version=self._transformers.__version__,
            # torch_versionへこの工程で使用する値を設定する
            torch_version=self._torch.__version__,
        )

    # この工程を担当する関数を定義する
    def generate_batch(
        # 次の値または処理を現在の構造へ組み込む
        self,
        # 次の値または処理を現在の構造へ組み込む
        *,
        # 次の値または処理を現在の構造へ組み込む
        system_prompt: str,
        # 次の値または処理を現在の構造へ組み込む
        user_prompts: list[str],
        # 次の値または処理を現在の構造へ組み込む
        sampling: Mapping[str, Any],
        # 次の値または処理を現在の構造へ組み込む
        seed: int,
    # 次の値または処理を現在の構造へ組み込む
    ) -> list[GenerationResult]:
        """同じsystem promptを使う複数件をnon-thinkingで一括生成する。"""

        # 空バッチはモデルを呼ばず空配列として返す
        if not user_prompts:
            # 処理結果を呼び出し元へ返す
            return []
        # バッチ内の各user promptをchat templateへ変換する配列を作る
        rendered_prompts: list[str] = []
        # 各user promptを順番にモデル入力文字列へ変換する
        for user_prompt in user_prompts:
            # Qwen3のchat templateへ渡すsystem/userメッセージを作る
            messages = [
                # system指示を会話の先頭へ配置する
                {"role": "system", "content": system_prompt},
                # 言い換え対象ごとのuser指示を続けて配置する
                {"role": "user", "content": user_prompt},
            ]
            # thinkingを明示的に無効化したモデル入力文字列を追加する
            rendered_prompts.append(
                # tokenizer固有のchat templateを適用する
                self._tokenizer.apply_chat_template(
                    # 今回の二つのメッセージを渡す
                    messages,
                    # ここでは文字列を得て後でまとめてtokenizeする
                    tokenize=False,
                    # assistant回答開始位置までを入力へ加える
                    add_generation_prompt=True,
                    # Qwen3のthinking出力を無効化する
                    enable_thinking=False,
                )
            )

        # decoder-onlyモデルのバッチ生成に必要な左paddingへ一時的に切り替える
        previous_padding_side = self._tokenizer.padding_side
        # 短い入力の左側へpaddingを置いて末尾位置を揃える
        self._tokenizer.padding_side = "left"
        # 長さの異なる入力を一つのPyTorchテンソルへまとめる
        model_inputs = self._tokenizer(
            # chat template適用済み文字列をまとめて渡す
            rendered_prompts,
            # PyTorchテンソルとして返す
            return_tensors="pt",
            # バッチ内の最大長までpaddingする
            padding=True,
        )
        # tokenizerを共有する他の呼び出しへ影響を残さないよう元の設定へ戻す
        self._tokenizer.padding_side = previous_padding_side
        # 入力テンソルをモデルが配置されたデバイスへ移す
        model_inputs = {
            # 各テンソルをモデルの主デバイスへ移す
            name: tensor.to(self._model.device)
            # tokenizerが返した入力項目を順番に処理する
            for name, tensor in model_inputs.items()
        }

        # バッチ全体のsampling乱数を固定して同一条件の再実行を可能にする
        self._transformers.set_seed(seed)
        # CUDAが有効な場合は全CUDAデバイスのseedも固定する
        if self._torch.cuda.is_available():
            # CUDA側のsampling乱数seedを固定する
            self._torch.cuda.manual_seed_all(seed)

        # 検査済みsampling値をmodel.generate用引数へ変換する
        generation_kwargs = {
            # 新しく生成してよい最大トークン数を設定する
            "max_new_tokens": _positive_int(sampling, "max_new_tokens"),
            # samplingを使うかを設定する
            "do_sample": bool(sampling.get("do_sample", True)),
            # 出力分布の温度を設定する
            "temperature": _positive_number(sampling, "temperature"),
            # nucleus samplingの累積確率を設定する
            "top_p": _probability(sampling, "top_p"),
            # 候補語彙数の上限を設定する
            "top_k": _positive_int(sampling, "top_k"),
            # 同じ表現の過剰な反復を抑える係数を設定する
            "repetition_penalty": _positive_number(sampling, "repetition_penalty"),
            # paddingにはtokenizerのEOS IDを使う
            "pad_token_id": self._tokenizer.eos_token_id,
        }
        # 勾配計算を無効化してバッチをまとめて生成する
        with self._torch.inference_mode():
            # 全入力の続きを一回のmodel.generateで作る
            generated = self._model.generate(**model_inputs, **generation_kwargs)
        # 左padding後の共通入力幅を生成部分の開始位置として取得する
        prompt_length = model_inputs["input_ids"].shape[1]
        # 各生成結果を再現性メタデータ付きで返す配列を作る
        results: list[GenerationResult] = []
        # バッチ内の生成結果を入力順に一件ずつ復号する
        for generated_ids in generated:
            # 入力部分を除き新しく生成されたトークンだけを取り出す
            completion_ids = generated_ids[prompt_length:]
            # thinking用特殊トークンも見える検査文字列へ戻す
            unchecked_text = self._tokenizer.decode(
                # 今回の生成トークンを渡す
                completion_ids,
                # thinking混入を検出できるよう特殊トークンを残す
                skip_special_tokens=False,
            )
            # non-thinking条件に反する出力があれば採用せず停止する
            reject_thinking_output(unchecked_text)
            # 検査後に特殊トークンを除いて保存用文字列へ戻す
            text = self._tokenizer.decode(
                # 今回の生成トークンを渡す
                completion_ids,
                # EOSなどの特殊トークンを保存文から除く
                skip_special_tokens=True,
            # 前後の空白を除いてJSON解析しやすい文字列にする
            ).strip()
            # 一件分の生成文と実行環境メタデータを追加する
            results.append(
                # 既存の単件生成と同じ結果型を使う
                GenerationResult(
                    # 復号した生成文を保存する
                    text=text,
                    # 実際に読み込んだモデルrevisionを保存する
                    resolved_revision=self.resolved_revision,
                    # Transformersのバージョンを保存する
                    transformers_version=self._transformers.__version__,
                    # PyTorchのバージョンを保存する
                    torch_version=self._torch.__version__,
                )
            )
        # 入力と同じ順番の生成結果を返す
        return results


# この工程を担当する関数を定義する
def _required_string(values: Mapping[str, Any], key: str) -> str:
    # 指定キーの値を辞書から取得する
    value = values.get(key)
    # 空でない文字列以外は設定エラーとする
    if not isinstance(value, str) or not value:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は空でない文字列にしてください")
    # 検査済み文字列を返す
    return value


# この工程を担当する関数を定義する
def _commit_id(values: Mapping[str, Any], key: str) -> str:
    # まず値が空でない文字列であることを確認する
    value = _required_string(values, key)
    # mainや短縮ハッシュではなく完全な40桁コミットIDだけを許可する
    if COMMIT_ID_PATTERN.fullmatch(value) is None:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は40桁のコミットIDにしてください")
    # 表記ゆれをなくすため小文字へ統一したコミットIDを返す
    return value.lower()


# この工程を担当する関数を定義する
def _positive_int(values: Mapping[str, Any], key: str) -> int:
    # 指定キーの値を辞書から取得する
    value = values.get(key)
    # boolを含まない正の整数だけを許可する
    if type(value) is not int or value <= 0:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は正の整数にしてください")
    # 検査済み整数を返す
    return value


# この工程を担当する関数を定義する
def _positive_number(values: Mapping[str, Any], key: str) -> float:
    # 指定キーの値を辞書から取得する
    value = values.get(key)
    # boolを除く正の整数または小数だけを許可する
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は正の数にしてください")
    # 後続処理で型を統一するためfloatへ変換して返す
    return float(value)


# この工程を担当する関数を定義する
def _probability(values: Mapping[str, Any], key: str) -> float:
    # まず指定値が正の数であることを確認する
    value = _positive_number(values, key)
    # 確率の上限である1を超える値を拒否する
    if value > 1:
        # 不正な状態を例外として通知して処理を停止する
        raise ValueError(f"{key}は0より大きく1以下にしてください")
    # 検査済み確率を返す
    return value
