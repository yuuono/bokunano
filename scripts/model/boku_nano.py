"""Boku-nanoのDecoder-only Transformerを定義する。"""

# 型注釈付きの設定値を簡潔に保持する
from dataclasses import asdict, dataclass
from collections import OrderedDict
# 残差倍率のNaN/Infを拒否する
import math
# 設定辞書で任意型を表現する
from typing import Any

# Transformer本体を実装する
import torch
# 損失関数とattention演算を利用する
import torch.nn.functional as F
# PyTorchの層を組み立てる
from torch import nn


# モデル構造を保存・復元できる設定として定義する
@dataclass(frozen=True)
class BokuNanoConfig:
    """Boku-nanoのモデル構造を表す。"""

    # 特殊トークンを含む語彙数を指定する
    vocab_size: int = 2048
    # 入出力埋め込みの次元数を指定する
    d_model: int = 384
    # Transformer block数を指定する
    n_layers: int = 8
    # self-attentionのhead数を指定する
    n_heads: int = 6
    # SwiGLUの中間次元数を指定する
    d_ff: int = 1024
    # 学習・生成時に扱う最大系列長を指定する
    context_length: int = 256
    # attentionと残差経路へ適用するdropout率を指定する
    dropout: float = 0.0
    # rotary position embeddingの基数を指定する
    rope_base: float = 10000.0
    # RMSNormのゼロ除算防止値を指定する
    rms_norm_eps: float = 1.0e-5
    # token embeddingと出力層の重みを共有するか指定する
    tie_word_embeddings: bool = False
    # 固有blockの層群を反復する回数。旧設定は1周として復元する
    n_loops: int = 1
    # 2周目以降に固定token embeddingを再加算するか指定する
    loop_input_mode: str = "none"
    # 全層反復か、先頭・末尾を一度だけ通る中間層反復かを指定する
    loop_pattern: str = "full"
    # attentionとFFNの各残差枝に、forwardのたびに掛ける固定倍率
    residual_scale: float = 1.0
    # middle反復部だけの各残差枝に掛ける固定倍率
    recurrent_residual_scale: float = 1.0

    @property
    def effective_layers(self) -> int:
        """重みの種類数とは区別したblock適用回数。"""
        # middleでは先頭・末尾の2層を反復数へ含めない
        if self.loop_pattern == "middle":
            return 2 + (self.n_layers - 2) * self.n_loops
        return self.n_layers * self.n_loops

    # YAMLなどの辞書から検証済み設定を作る
    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "BokuNanoConfig":
        """未知キーを拒否し、モデル設定を返す。"""

        # dataclassが受理するキーだけを取得する
        allowed = set(cls.__dataclass_fields__)
        # 入力に含まれる未知キーを抽出する
        unknown = set(values) - allowed
        # 誤記した設定を黙って無視しない
        if unknown:
            # 未知キーを並べて例外にする
            raise ValueError(f"未知のmodel設定です: {sorted(unknown)}")
        # 辞書を展開して設定を作る
        config = cls(**values)
        # 次元や範囲を検証する
        config.validate()
        # 検証済み設定を返す
        return config

    # モデルを作る前に構造上の制約を検査する
    def validate(self) -> None:
        """attentionとSwiGLUに必要な設定制約を検証する。"""

        if type(self.n_loops) is not int or self.n_loops < 1:
            raise ValueError("n_loopsはboolを除く正の整数である必要があります")
        if self.loop_input_mode not in ("none", "add"):
            raise ValueError("loop_input_modeはnoneまたはaddである必要があります")
        # 初版の4候補ではmiddleと再注入を混ぜず、単独変更として扱う
        if self.loop_pattern not in ("full", "middle"):
            raise ValueError("loop_patternはfullまたはmiddleである必要があります")
        if self.loop_pattern == "middle" and (self.n_layers < 3 or self.loop_input_mode != "none"):
            raise ValueError("middleは3物理層以上かつloop_input_mode=noneが必要です")
        # bool・文字列・非有限値・非正値を倍率として受け付けない
        if (type(self.residual_scale) not in (int, float)
                or not math.isfinite(self.residual_scale) or self.residual_scale <= 0):
            raise ValueError("residual_scaleは有限の正の数である必要があります")
        if (type(self.recurrent_residual_scale) not in (int, float)
                or not math.isfinite(self.recurrent_residual_scale)
                or self.recurrent_residual_scale <= 0):
            raise ValueError("recurrent_residual_scaleは有限の正の数である必要があります")
        if self.recurrent_residual_scale != 1.0 and self.loop_pattern != "middle":
            raise ValueError("recurrent_residual_scaleの変更にはloop_pattern=middleが必要です")
        # 語彙を正の値に限定する
        if self.vocab_size <= 0:
            # 不正値を明示する
            raise ValueError("vocab_sizeは正の整数である必要があります")
        # 各主要次元を正の値に限定する
        if min(self.d_model, self.n_layers, self.n_heads, self.d_ff) <= 0:
            # 不正次元を明示する
            raise ValueError("モデル次元、層数、head数は正の整数である必要があります")
        # headへ均等に分割できることを確認する
        if self.d_model % self.n_heads != 0:
            # 割り切れない設定を拒否する
            raise ValueError("d_modelはn_headsで割り切れる必要があります")
        # RoPEが二要素ずつ回転できることを確認する
        if (self.d_model // self.n_heads) % 2 != 0:
            # 奇数head次元を拒否する
            raise ValueError("attention head次元は偶数である必要があります")
        # 系列長を正の値に限定する
        if self.context_length <= 0:
            # 不正値を明示する
            raise ValueError("context_lengthは正の整数である必要があります")
        # dropoutを確率範囲に限定する
        if not 0.0 <= self.dropout < 1.0:
            # 不正率を明示する
            raise ValueError("dropoutは0以上1未満である必要があります")

    # checkpointへJSON互換辞書として保存する
    def to_dict(self) -> dict[str, Any]:
        """モデル設定をJSON互換辞書へ変換する。"""

        # dataclassの全項目を辞書化して返す
        return asdict(self)


# 平均を引かず二乗平均平方根だけで正規化する
class RMSNorm(nn.Module):
    """Llama系と同じ形式のRMSNormを実装する。"""

    # 学習可能なscaleを初期化する
    def __init__(self, dimension: int, eps: float) -> None:
        # nn.Moduleを初期化する
        super().__init__()
        # 各特徴次元のscaleを1で初期化する
        self.weight = nn.Parameter(torch.ones(dimension))
        # 数値安定化用の値を保存する
        self.eps = eps

    # 入力をfloat32で正規化して元dtypeへ戻す
    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """最終次元についてRMS正規化する。"""

        # 半精度での平方平均誤差を避けるためfloat32へ上げる
        values = hidden_states.float()
        # 特徴次元ごとの二乗平均から逆平方根を求める
        normalized = values * torch.rsqrt(values.pow(2).mean(dim=-1, keepdim=True) + self.eps)
        # 元dtypeへ戻して学習可能scaleを掛ける
        return normalized.to(hidden_states.dtype) * self.weight


# 学習パラメータを持たないRoPEのcosとsinを保持する
class RotaryEmbedding(nn.Module):
    """固定長のrotary position embeddingを生成する。"""

    # 最大系列長までの回転表を作る
    def __init__(self, head_dim: int, context_length: int, base: float) -> None:
        # nn.Moduleを初期化する
        super().__init__()
        # 偶数位置に対応する逆周波数を作る
        inv_freq = 1.0 / (
            base ** (torch.arange(0, head_dim, 2, dtype=torch.float32) / head_dim)
        )
        # 系列位置をfloat32で作る
        positions = torch.arange(context_length, dtype=torch.float32)
        # 位置と周波数の直積を作る
        frequencies = torch.outer(positions, inv_freq)
        # 偶数・奇数次元へ同じ角度を並べる
        angles = torch.cat((frequencies, frequencies), dim=-1)
        # checkpointを増やさない固定cos表をbufferへ登録する
        self.register_buffer("cos", angles.cos(), persistent=False)
        # checkpointを増やさない固定sin表をbufferへ登録する
        self.register_buffer("sin", angles.sin(), persistent=False)

    # queryとkeyへ同じ位置回転を適用する
    def forward(
        self, query: torch.Tensor, key: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """[batch, head, sequence, dimension]のqueryとkeyを回転する。"""

        # 現在の系列長に必要な表だけを取り出す
        cos = self.cos[: query.size(-2)].to(dtype=query.dtype)[None, None, :, :]
        # sinも同じ形に整える
        sin = self.sin[: query.size(-2)].to(dtype=query.dtype)[None, None, :, :]
        # queryへ回転を適用する
        rotated_query = query * cos + _rotate_half(query) * sin
        # keyへ回転を適用する
        rotated_key = key * cos + _rotate_half(key) * sin
        # 回転済みqueryとkeyを返す
        return rotated_query, rotated_key


# RoPE用に特徴次元の前半と後半を90度回転する
def _rotate_half(values: torch.Tensor) -> torch.Tensor:
    """最終次元を二分し、[-後半, 前半]へ並べ替える。"""

    # 特徴次元を等分する
    first, second = values.chunk(2, dim=-1)
    # 90度回転に対応する符号と順番へ変換する
    return torch.cat((-second, first), dim=-1)


# causal self-attentionを定義する
class CausalSelfAttention(nn.Module):
    """RoPE付きmulti-head causal self-attentionを実装する。"""

    # projection層とRoPEを作る
    def __init__(self, config: BokuNanoConfig) -> None:
        # nn.Moduleを初期化する
        super().__init__()
        # head数を保存する
        self.n_heads = config.n_heads
        # headごとの次元数を保存する
        self.head_dim = config.d_model // config.n_heads
        # 学習時attention dropout率を保存する
        self.dropout = config.dropout
        # query、key、valueを一度に計算するbiasなし線形層を作る
        self.qkv_proj = nn.Linear(config.d_model, 3 * config.d_model, bias=False)
        # headを結合した後のbiasなし出力層を作る
        self.out_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        # 最大文脈長までのRoPEを作る
        self.rope = RotaryEmbedding(
            self.head_dim, config.context_length, config.rope_base
        )
        # 残差経路へ適用するdropoutを作る
        self.residual_dropout = nn.Dropout(config.dropout)

    # 入力系列へcausal attentionを適用する
    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """未来tokenを参照しないself-attentionを計算する。"""

        # batch、系列長、埋め込み次元を取得する
        batch_size, sequence_length, model_dimension = hidden_states.shape
        # query、key、valueをまとめて計算する
        query, key, value = self.qkv_proj(hidden_states).chunk(3, dim=-1)
        # head軸を追加しattention APIの形へ変換する
        query = query.view(
            batch_size, sequence_length, self.n_heads, self.head_dim
        ).transpose(1, 2)
        # keyも同じ形へ変換する
        key = key.view(
            batch_size, sequence_length, self.n_heads, self.head_dim
        ).transpose(1, 2)
        # valueも同じ形へ変換する
        value = value.view(
            batch_size, sequence_length, self.n_heads, self.head_dim
        ).transpose(1, 2)
        # queryとkeyへ位置情報を与える
        query, key = self.rope(query, key)
        # 右paddingより前の実tokenはpaddingを参照しないためcausal maskだけを使う
        attended = F.scaled_dot_product_attention(
            query,
            key,
            value,
            dropout_p=self.dropout if self.training else 0.0,
            is_causal=True,
        )
        # head軸を埋め込み次元へ戻す
        attended = attended.transpose(1, 2).contiguous().view(
            batch_size, sequence_length, model_dimension
        )
        # 出力projectionと残差dropoutを適用する
        return self.residual_dropout(self.out_proj(attended))


# SwiGLU feed-forward networkを定義する
class SwiGLU(nn.Module):
    """二つの入力projectionとSiLU gateを持つFFNを実装する。"""

    # 三つのbiasなし線形層を作る
    def __init__(self, config: BokuNanoConfig) -> None:
        # nn.Moduleを初期化する
        super().__init__()
        # gate用projectionを作る
        self.gate_proj = nn.Linear(config.d_model, config.d_ff, bias=False)
        # value用projectionを作る
        self.up_proj = nn.Linear(config.d_model, config.d_ff, bias=False)
        # 埋め込み次元へ戻すprojectionを作る
        self.down_proj = nn.Linear(config.d_ff, config.d_model, bias=False)
        # 残差経路へ適用するdropoutを作る
        self.residual_dropout = nn.Dropout(config.dropout)

    # SwiGLU変換を実行する
    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """SiLU gateとvalueを要素積して埋め込み次元へ戻す。"""

        # gate側へSiLUを適用しvalue側と要素積する
        gated = F.silu(self.gate_proj(hidden_states)) * self.up_proj(hidden_states)
        # 出力projectionと残差dropoutを適用する
        return self.residual_dropout(self.down_proj(gated))


# pre-normalization形式のTransformer blockを定義する
class TransformerBlock(nn.Module):
    """RMSNorm、attention、SwiGLUを一組にする。"""

    # block内の層を初期化する
    def __init__(self, config: BokuNanoConfig) -> None:
        # nn.Moduleを初期化する
        super().__init__()
        # attention前のRMSNormを作る
        self.attention_norm = RMSNorm(config.d_model, config.rms_norm_eps)
        # causal self-attentionを作る
        self.attention = CausalSelfAttention(config)
        # FFN前のRMSNormを作る
        self.ffn_norm = RMSNorm(config.d_model, config.rms_norm_eps)
        # SwiGLU FFNを作る
        self.feed_forward = SwiGLU(config)
        # 学習可能な重みを増やさず、保存設定から固定倍率を復元する
        self.residual_scale = config.residual_scale

    # 二つのpre-norm残差更新を行う
    def forward(
        self, hidden_states: torch.Tensor, residual_scale: float | None = None
    ) -> torch.Tensor:
        """attentionとFFNを残差接続付きで順に適用する。"""

        # middle反復部だけ倍率を上書きでき、通常経路は保存設定の倍率を使う
        scale = self.residual_scale if residual_scale is None else residual_scale
        # 正規化した入力のattention結果を残差加算する
        attention_update = self.attention(self.attention_norm(hidden_states))
        # 旧モデルの倍率1では計算経路をそのまま保つ
        if scale != 1.0:
            attention_update = attention_update * scale
        hidden_states = hidden_states + attention_update
        # 正規化した中間値のFFN結果を残差加算する
        ffn_update = self.feed_forward(self.ffn_norm(hidden_states))
        if scale != 1.0:
            ffn_update = ffn_update * scale
        hidden_states = hidden_states + ffn_update
        # 更新済み表現を返す
        return hidden_states


# forward結果を名前付きで返す
@dataclass
class CausalLMOutput:
    """logitsと任意のlossを保持する。"""

    # 各位置の次token logitsを保持する
    logits: torch.Tensor
    # labels指定時だけcausal LM lossを保持する
    loss: torch.Tensor | None


# Boku-nano本体を定義する
class BokuNanoForCausalLM(nn.Module):
    """通常・共有反復のDecoder-only causal language model。"""

    # 設定から全層をランダム初期化する
    def __init__(self, config: BokuNanoConfig) -> None:
        # nn.Moduleを初期化する
        super().__init__()
        # 設定制約を再確認する
        config.validate()
        # checkpoint保存用に設定を保持する
        self.config = config
        # token IDを埋め込みへ変換する
        self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
        # 指定数のTransformer blockを作る
        self.blocks = nn.ModuleList(
            [TransformerBlock(config) for _ in range(config.n_layers)]
        )
        # 最終表現を正規化する
        self.final_norm = RMSNorm(config.d_model, config.rms_norm_eps)
        # 各位置から語彙logitsを作るbiasなし出力層を定義する
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
        # 全parameterをランダム初期化する
        self.apply(self._initialize_module)
        # 深さに応じて残差出力projectionの初期値を縮小する
        self._scale_residual_projections()
        # 設定時だけ入力と出力の重みを共有する
        if config.tie_word_embeddings:
            # 同じParameterを参照させる
            self.lm_head.weight = self.token_embedding.weight

    def load_state_dict(self, state_dict, strict: bool = True, assign: bool = False):
        """共有headを省いた保存形式と従来形式を厳密に読み込む。"""
        if self.config.tie_word_embeddings:
            state = OrderedDict(state_dict)
            if hasattr(state_dict, "_metadata"):
                state._metadata = state_dict._metadata
            embedding = state.get("token_embedding.weight")
            head = state.get("lm_head.weight")
            if embedding is not None:
                if head is not None and not torch.equal(embedding, head):
                    raise ValueError("共有embeddingとlm_headの保存値が一致しません")
                state["lm_head.weight"] = embedding
            state_dict = state
        result = super().load_state_dict(state_dict, strict=strict, assign=assign)
        if self.config.tie_word_embeddings:
            # assign=Trueでも二つのParameterへ分離させない
            self.lm_head.weight = self.token_embedding.weight
        return result

    def cpu_state_dict(self) -> dict[str, torch.Tensor]:
        """共有語彙行列を一度だけ格納する保存用stateを返す。"""
        return {
            name: value.detach().cpu().contiguous()
            for name, value in self.state_dict().items()
            if not (self.config.tie_word_embeddings and name == "lm_head.weight")
        }

    # 線形層と埋め込みを正規分布で初期化する
    @staticmethod
    def _initialize_module(module: nn.Module) -> None:
        """既存重みを使わず平均0、標準偏差0.02で初期化する。"""

        # 線形層を対象にする
        if isinstance(module, nn.Linear):
            # 重みを切断正規分布で初期化する
            nn.init.trunc_normal_(module.weight, mean=0.0, std=0.02)
            # biasを持つ拡張設定にも対応する
            if module.bias is not None:
                # biasを0で初期化する
                nn.init.zeros_(module.bias)
        # 埋め込み層を対象にする
        elif isinstance(module, nn.Embedding):
            # token embeddingも同じ分布で初期化する
            nn.init.trunc_normal_(module.weight, mean=0.0, std=0.02)

    # 残差出力層を深さに応じて縮小する
    def _scale_residual_projections(self) -> None:
        """深い残差加算で初期値が増幅しないよう出力層を縮小する。"""

        # GPT系で使われる1/sqrt(2L)を求める
        scale = (2 * self.config.n_layers) ** -0.5
        # 全blockを順に処理する
        for block in self.blocks:
            # attention出力projectionを縮小する
            block.attention.out_proj.weight.data.mul_(scale)
            # FFN出力projectionも縮小する
            block.feed_forward.down_proj.weight.data.mul_(scale)

    # token列から次token分布と任意の損失を計算する
    def forward(
        self, input_ids: torch.Tensor, labels: torch.Tensor | None = None
    ) -> CausalLMOutput:
        """右padding済みtoken列へcausal LMを適用する。"""

        # 入力を[batch, sequence]に限定する
        if input_ids.ndim != 2:
            # 想定外shapeを早期に拒否する
            raise ValueError("input_idsは[batch, sequence]である必要があります")
        # 設定文脈長を超える入力を拒否する
        if input_ids.size(1) > self.config.context_length:
            # 実際の長さを含めて例外にする
            raise ValueError(
                f"系列長がcontext_lengthを超えました: {input_ids.size(1)} > "
                f"{self.config.context_length}"
            )
        # token IDを埋め込みへ変換する
        embedded = self.token_embedding(input_ids)
        hidden_states = embedded
        # middleだけ先頭を一度通し、中間block群を反復対象にする
        if self.config.loop_pattern == "middle":
            hidden_states = self.blocks[0](hidden_states)
            recurrent_blocks = self.blocks[1:-1]
        else:
            recurrent_blocks = self.blocks
        # 同一のblock群を再利用し、全周回へ勾配を伝える
        for loop_index in range(self.config.n_loops):
            if loop_index > 0 and self.config.loop_input_mode == "add":
                hidden_states = hidden_states + embedded
            for block in recurrent_blocks:
                if self.config.loop_pattern == "middle":
                    hidden_states = block(
                        hidden_states,
                        residual_scale=self.config.recurrent_residual_scale,
                    )
                else:
                    hidden_states = block(hidden_states)
        # middleの末尾は全反復が終わった後に一度だけ適用する
        if self.config.loop_pattern == "middle":
            hidden_states = self.blocks[-1](hidden_states)
        # 最終表現を正規化する
        hidden_states = self.final_norm(hidden_states)
        # float32の語彙logitsへ変換する
        logits = self.lm_head(hidden_states).float()
        # labelsがない推論時はlossを計算しない
        if labels is None:
            # logitsだけを返す
            return CausalLMOutput(logits=logits, loss=None)
        # labels shapeが入力と一致することを確認する
        if labels.shape != input_ids.shape:
            # 不一致shapeを明示する
            raise ValueError("labelsはinput_idsと同じshapeである必要があります")
        # 現位置から次tokenを予測するlogitsを取り出す
        shifted_logits = logits[:, :-1, :].contiguous()
        # 先頭を除いた正解tokenを取り出す
        shifted_labels = labels[:, 1:].contiguous()
        # -100のprompt・padding位置を無視してcross entropyを計算する
        loss = F.cross_entropy(
            shifted_logits.view(-1, shifted_logits.size(-1)),
            shifted_labels.view(-1),
            ignore_index=-100,
        )
        # logitsとlossを返す
        return CausalLMOutput(logits=logits, loss=loss)

    # 学習可能parameter総数を返す
    def parameter_count(self) -> int:
        """requires_gradが有効なparameter要素数を数える。"""

        # 各parameterの要素数を合計する
        return sum(parameter.numel() for parameter in self.parameters() if parameter.requires_grad)


# checkpoint辞書からモデルを安全に再構築する
def model_from_checkpoint(checkpoint: dict[str, Any]) -> BokuNanoForCausalLM:
    """保存済み設定とstate_dictからBoku-nanoを復元する。"""

    # checkpoint内のモデル設定を検証して読み込む
    config = BokuNanoConfig.from_dict(checkpoint["model_config"])
    # 同じ構造をランダム初期化する
    model = BokuNanoForCausalLM(config)
    # 保存済みparameterで厳密に置き換える
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    # 復元済みモデルを返す
    return model
