"""Qwen3を非thinkingモードで呼び出す共通処理。"""

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


def sha256_text(text: str) -> str:
    """文字列のUTF-8バイト列からSHA-256を計算する。"""

    # 入力文字列をUTF-8へ変換してSHA-256の16進文字列を返す
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(value: object) -> str:
    """ハッシュやプロンプトに使用する決定的なJSON文字列を作る。"""

    # 日本語を保持し、キー順と区切りを固定してJSONへ変換する
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def render_prompt(path: Path, values: Mapping[str, object]) -> str:
    """テンプレート内の$nameを値で置換する。"""

    # UTF-8でプロンプトテンプレートを読み込む
    template = Template(path.read_text(encoding="utf-8"))
    # 数値やJSONも置換できるよう、すべての値を文字列へ変換する
    rendered_values = {key: str(value) for key, value in values.items()}
    # 未定義変数を見逃さないsubstituteでテンプレートを展開する
    return template.substitute(rendered_values)


def prompt_hash(system_prompt: str, user_prompt: str) -> str:
    """system/user promptを区切り込みでハッシュ化する。"""

    # 二つのプロンプトを専用区切りで連結してハッシュ化する
    return sha256_text(system_prompt + PROMPT_SEPARATOR + user_prompt)


def validate_model_config(model_config: Mapping[str, Any]) -> dict[str, Any]:
    """Qwen読み込み設定をモデルのロード前に検査する。"""

    # モデル設定として認めるキーを列挙する
    expected = {
        "model_id",
        "revision",
        "device_map",
        "attn_implementation",
        "trust_remote_code",
        "local_files_only",
        "require_cuda",
        "enable_thinking",
    }
    # キーの不足や余分なキーがあれば設定ミスとして停止する
    if set(model_config) != expected:
        raise ValueError("model設定の項目が不正です")
    # モデルIDが空でない文字列であることを確認する
    _required_string(model_config, "model_id")
    # モデルrevisionが再現可能な40桁のコミットIDであることを確認する
    _commit_id(model_config, "revision")
    # デバイス割当方法が空でない文字列であることを確認する
    _required_string(model_config, "device_map")
    # Attention実装名を設定から取り出す
    attn_implementation = model_config.get("attn_implementation")
    # Attention実装名は文字列またはnullだけを許可する
    if attn_implementation is not None and not isinstance(attn_implementation, str):
        raise ValueError("attn_implementationは文字列またはnullにしてください")
    # 真偽値で指定する設定項目を順番に検査する
    for key in (
        "trust_remote_code",
        "local_files_only",
        "require_cuda",
        "enable_thinking",
    ):
        # bool以外の値が指定されていれば停止する
        if type(model_config.get(key)) is not bool:
            raise ValueError(f"{key}は真偽値にしてください")
    # 思考過程を保存しない課題方針に合わせてthinkingを必ず無効にする
    if model_config["enable_thinking"] is not False:
        raise ValueError("Qwen3はenable_thinking=falseで使用してください")
    # 呼び出し元が安全に保持できるよう設定辞書をコピーして返す
    return dict(model_config)


def validate_sampling_config(sampling: Mapping[str, Any]) -> dict[str, Any]:
    """生成sampling設定をモデルのロード前に検査する。"""

    # sampling設定として認めるキーを列挙する
    expected = {
        "max_new_tokens",
        "do_sample",
        "temperature",
        "top_p",
        "top_k",
        "repetition_penalty",
    }
    # キーの不足や余分なキーがあれば停止する
    if set(sampling) != expected:
        raise ValueError("sampling設定の項目が不正です")
    # 最大生成トークン数が正の整数であることを確認する
    _positive_int(sampling, "max_new_tokens")
    # samplingの有効・無効が真偽値であることを確認する
    if type(sampling.get("do_sample")) is not bool:
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


def parse_json_string_list(raw_text: str, key: str) -> list[str]:
    """モデル出力から、指定キーに入った文字列配列を取り出す。"""

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
                text = text[5:].lstrip()

    # まず出力全体をJSONとして解析する
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # 前後に説明が混入した場合に備え、最初の開き波括弧を探す
        start = text.find("{")
        # JSON候補の末尾となる最後の閉じ波括弧を探す
        end = text.rfind("}")
        # 波括弧で囲まれた範囲がなければ解析不能として停止する
        if start < 0 or end <= start:
            raise ValueError("モデル出力にJSONオブジェクトがありません") from None
        # 波括弧で囲まれた範囲だけを再度JSONとして解析する
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as error:
            raise ValueError("モデル出力のJSONを解析できません") from error

    # 指定キー一つだけを持つJSONオブジェクトであることを確認する
    if not isinstance(parsed, dict) or set(parsed) != {key}:
        raise ValueError(f"モデル出力はキー{key!r}だけを持つJSONにしてください")
    # 指定キーに対応する候補一覧を取り出す
    values = parsed[key]
    # 候補一覧が空でない配列であることを確認する
    if not isinstance(values, list) or not values:
        raise ValueError(f"{key!r}は空でない配列にしてください")

    # 検査済み文字列を格納する空の配列を作る
    result: list[str] = []
    # モデルが返した各候補を順番に検査する
    for value in values:
        # 候補が文字列でなければ停止する
        if not isinstance(value, str):
            raise ValueError(f"{key!r}の各要素は文字列にしてください")
        # 候補の前後に付いた空白を除く
        candidate = value.strip()
        # 空文字列になった候補は許可しない
        if not candidate:
            raise ValueError(f"{key!r}に空文字列を入れないでください")
        # 検査を通過した候補を結果へ追加する
        result.append(candidate)
    # 検査済み候補一覧を返す
    return result


def reject_thinking_output(raw_text: str) -> str:
    """thinkタグを含むモデル出力を、解析や保存の前に拒否する。"""

    # 非thinking設定に反してthink開始・終了タグが一つでも出たかを調べる
    if THINK_TAG_PATTERN.search(raw_text):
        # 思考過程を候補や生出力へ保存しないため、その応答全体を例外にする
        raise ValueError("Qwen出力に<think>タグが含まれているため拒否しました")
    # thinkingタグを含まない検査済み出力だけを呼び出し元へ返す
    return raw_text


@dataclass(frozen=True)
class GenerationResult:
    """1回の生成結果と再現用メタデータ。"""

    text: str
    resolved_revision: str
    transformers_version: str
    torch_version: str


class QwenTeacher:
    """Transformers経由でQwen3を1プロセスに1回だけ読み込む。"""

    def __init__(self, model_config: Mapping[str, Any]) -> None:
        # 大容量依存関係は実生成時だけ読み込む
        try:
            # テンソル処理とCUDA推論に使うPyTorchを読み込む
            import torch
            # seed固定とバージョン記録に使うTransformers本体を読み込む
            import transformers
            # モデルとtokenizerを自動選択して読み込むクラスを取得する
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as error:
            raise RuntimeError(
                "Qwen用依存関係がありません。スクリプトをuv runで実行してください。"
            ) from error

        # generate内でもPyTorchを使えるようインスタンスへ保持する
        self._torch = torch
        # seed固定とバージョン参照のためTransformersを保持する
        self._transformers = transformers
        # 使用するHugging FaceモデルIDを設定から取得する
        self._model_id = _required_string(model_config, "model_id")
        # 要求するモデルrevisionを40桁の固定コミットIDとして取得する
        revision = _commit_id(model_config, "revision")
        # CUDAを必須にするかを設定から取得する
        require_cuda = bool(model_config.get("require_cuda", True))
        # AWQモデルをCUDA必須設定でCPU実行しようとした場合は早期停止する
        if require_cuda and not torch.cuda.is_available():
            raise RuntimeError(
                "Qwen3 AWQの実行にはCUDA対応環境が必要です。"
                "CUDA環境で実行するか、設定のモデルを変更してください。"
            )

        # tokenizer読込時に渡す再現性・安全性設定をまとめる
        tokenizer_kwargs = {
            "revision": revision,
            "trust_remote_code": bool(model_config.get("trust_remote_code", False)),
            "local_files_only": bool(model_config.get("local_files_only", False)),
        }
        # 指定モデルとrevisionに対応するtokenizerを読み込む
        self._tokenizer = AutoTokenizer.from_pretrained(
            self._model_id,
            **tokenizer_kwargs,
        )

        # モデル読込時に渡すデバイス割当と安全性設定をまとめる
        model_kwargs: dict[str, Any] = {
            "revision": revision,
            "device_map": model_config.get("device_map", "auto"),
            "trust_remote_code": bool(model_config.get("trust_remote_code", False)),
            "local_files_only": bool(model_config.get("local_files_only", False)),
            "low_cpu_mem_usage": True,
        }
        # 任意指定のAttention実装名を取り出す
        attn_implementation = model_config.get("attn_implementation")
        # Attention実装が指定された場合だけモデル引数へ追加する
        if attn_implementation is not None:
            model_kwargs["attn_implementation"] = attn_implementation
        # Qwen3の因果言語モデルを指定revisionから読み込む
        self._model = AutoModelForCausalLM.from_pretrained(
            self._model_id,
            **model_kwargs,
        )
        # Dropoutなどの学習時動作を止めて推論モードにする
        self._model.eval()
        # 実際に解決されたコミットIDを優先して記録する
        self._resolved_revision = (
            getattr(self._model.config, "_commit_hash", None)
            or getattr(self._tokenizer, "_commit_hash", None)
            or revision
        )

    @property
    def resolved_revision(self) -> str:
        # JSONへ保存できる文字列として解決済みrevisionを返す
        return str(self._resolved_revision)

    @property
    def model_id(self) -> str:
        # 実際に読み込んだモデルIDを返す
        return self._model_id

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        sampling: Mapping[str, Any],
        seed: int,
    ) -> GenerationResult:
        """non-thinking chat templateで1件生成する。"""

        # Qwen3のchat templateへ渡すsystem/userメッセージを作る
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        # thinkingを明示的に無効化してモデル入力文字列へ変換する
        rendered = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        # モデル入力文字列をPyTorchテンソルへ変換する
        model_inputs = self._tokenizer([rendered], return_tensors="pt")
        # 入力テンソルをモデルが配置されたデバイスへ移す
        model_inputs = {
            name: tensor.to(self._model.device)
            for name, tensor in model_inputs.items()
        }

        # Python・NumPy・PyTorchでTransformersが使う乱数seedを固定する
        self._transformers.set_seed(seed)
        # CUDAが有効な場合は全CUDAデバイスのseedも固定する
        if self._torch.cuda.is_available():
            self._torch.cuda.manual_seed_all(seed)

        # 検査済みsampling値をmodel.generate用引数へ変換する
        generation_kwargs = {
            "max_new_tokens": _positive_int(sampling, "max_new_tokens"),
            "do_sample": bool(sampling.get("do_sample", True)),
            "temperature": _positive_number(sampling, "temperature"),
            "top_p": _probability(sampling, "top_p"),
            "top_k": _positive_int(sampling, "top_k"),
            "repetition_penalty": _positive_number(sampling, "repetition_penalty"),
            "pad_token_id": self._tokenizer.eos_token_id,
        }
        # 勾配計算を無効化してメモリ消費を抑えながら生成する
        with self._torch.inference_mode():
            generated = self._model.generate(**model_inputs, **generation_kwargs)
        # 入力部分と生成部分を分離するため入力トークン長を取得する
        prompt_length = model_inputs["input_ids"].shape[1]
        # モデル出力から入力トークン部分を除き、生成部分だけを取り出す
        completion_ids = generated[0][prompt_length:]
        # 特殊トークンも残して生成トークンを検査専用文字列へ戻す
        unchecked_text = self._tokenizer.decode(
            completion_ids,
            skip_special_tokens=False,
        )
        # 特殊トークン扱いのthinkタグも解析・保存へ渡さず必ず拒否する
        reject_thinking_output(unchecked_text)
        # 検査合格後にだけ特殊トークンを除いて最終回答文字列へ戻す
        text = self._tokenizer.decode(
            completion_ids,
            skip_special_tokens=True,
        ).strip()
        # 生成文と再現性情報をまとめて返す
        return GenerationResult(
            text=text,
            resolved_revision=self.resolved_revision,
            transformers_version=self._transformers.__version__,
            torch_version=self._torch.__version__,
        )


def _required_string(values: Mapping[str, Any], key: str) -> str:
    # 指定キーの値を辞書から取得する
    value = values.get(key)
    # 空でない文字列以外は設定エラーとする
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key}は空でない文字列にしてください")
    # 検査済み文字列を返す
    return value


def _commit_id(values: Mapping[str, Any], key: str) -> str:
    # まず値が空でない文字列であることを確認する
    value = _required_string(values, key)
    # mainや短縮ハッシュではなく完全な40桁コミットIDだけを許可する
    if COMMIT_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{key}は40桁のコミットIDにしてください")
    # 表記ゆれをなくすため小文字へ統一したコミットIDを返す
    return value.lower()


def _positive_int(values: Mapping[str, Any], key: str) -> int:
    # 指定キーの値を辞書から取得する
    value = values.get(key)
    # boolを含まない正の整数だけを許可する
    if type(value) is not int or value <= 0:
        raise ValueError(f"{key}は正の整数にしてください")
    # 検査済み整数を返す
    return value


def _positive_number(values: Mapping[str, Any], key: str) -> float:
    # 指定キーの値を辞書から取得する
    value = values.get(key)
    # boolを除く正の整数または小数だけを許可する
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{key}は正の数にしてください")
    # 後続処理で型を統一するためfloatへ変換して返す
    return float(value)


def _probability(values: Mapping[str, Any], key: str) -> float:
    # まず指定値が正の数であることを確認する
    value = _positive_number(values, key)
    # 確率の上限である1を超える値を拒否する
    if value > 1:
        raise ValueError(f"{key}は0より大きく1以下にしてください")
    # 検査済み確率を返す
    return value
