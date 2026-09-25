"""Boku-nanoの構造、損失mask、本学習設定を検証する。"""

# 省メモリtoken列を作る
from array import array
# 実設定ファイルを参照する
from pathlib import Path
# 一時保存先を安全に作る
import tempfile
# 標準ライブラリでテストを実行する
import unittest

# forwardとbackwardを検証する
import torch

# モデル構造を読み込む
from scripts.model.boku_nano import BokuNanoConfig, BokuNanoForCausalLM
# 学習データ処理とscheduleを読み込む
from scripts.model.train_boku_nano import (
    IGNORE_INDEX,
    collate_training_batch,
    learning_rate_for_step,
    save_final_weights,
    validate_configuration,
)


# Boku-nanoの本学習前提をまとめて検証する
class BokuNanoTrainingTest(unittest.TestCase):
    """parameter数、causal loss、固定artifactを確認する。"""

    # 本番仕様が約1,600万parameterであることを固定する
    def test_production_model_has_expected_parameter_count(self) -> None:
        """入力・出力embedding非共有で15,735,168 parameterになる。"""

        # 本番仕様の設定を作る
        config = BokuNanoConfig()
        # seedを固定してモデルを初期化する
        torch.manual_seed(0)
        # CPU上に本番モデルを作る
        model = BokuNanoForCausalLM(config)
        # 意図したparameter数と一致することを確認する
        self.assertEqual(model.parameter_count(), 15_735_168)
        # 入力・出力重みが別parameterであることを確認する
        self.assertNotEqual(
            model.token_embedding.weight.data_ptr(), model.lm_head.weight.data_ptr()
        )

    # 小型構成でforwardとbackwardを確認する
    def test_forward_uses_masked_causal_labels(self) -> None:
        """promptとpaddingを除外したcode tokenだけでlossを計算する。"""

        # テストを高速にする小型設定を作る
        config = BokuNanoConfig(
            vocab_size=32,
            d_model=16,
            n_layers=2,
            n_heads=2,
            d_ff=32,
            context_length=16,
        )
        # 小型モデルを作る
        model = BokuNanoForCausalLM(config)
        # 2系列を右paddingする
        batch = collate_training_batch(
            [
                (array("H", [1, 4, 8, 5, 9, 10, 2]), 4),
                (array("H", [1, 4, 7, 5, 11, 2]), 4),
            ],
            pad_token_id=0,
        )
        # prompt部分が損失除外値であることを確認する
        self.assertTrue(torch.all(batch["labels"][:, :4] == IGNORE_INDEX))
        # 短い系列のpaddingも損失除外値であることを確認する
        self.assertEqual(int(batch["labels"][1, -1].item()), IGNORE_INDEX)
        # forwardしてlossを得る
        output = model(batch["input_ids"], labels=batch["labels"])
        # 語彙logitsのshapeを確認する
        self.assertEqual(tuple(output.logits.shape), (2, 7, 32))
        # lossが有限であることを確認する
        self.assertIsNotNone(output.loss)
        # 型checkerへloss存在を伝える
        assert output.loss is not None
        # 数値が有限であることを確認する
        self.assertTrue(torch.isfinite(output.loss).item())
        # backwardが全構造を通ることを確認する
        output.loss.backward()
        # 出力headにgradientが作られたことを確認する
        self.assertIsNotNone(model.lm_head.weight.grad)

    # warmupとcosine終端を確認する
    def test_learning_rate_schedule_endpoints(self) -> None:
        """warmup終端で最大値、最終stepで最小値になる。"""

        # warmup最初の値を求める
        first = learning_rate_for_step(1, 100, 10, 3.0e-4, 3.0e-5)
        # warmup終端値を求める
        warmup_end = learning_rate_for_step(10, 100, 10, 3.0e-4, 3.0e-5)
        # 全step終端値を求める
        final = learning_rate_for_step(100, 100, 10, 3.0e-4, 3.0e-5)
        # 1 step目が最大値の10分の1であることを確認する
        self.assertAlmostEqual(first, 3.0e-5)
        # warmup終端が最大値であることを確認する
        self.assertAlmostEqual(warmup_end, 3.0e-4)
        # 最終stepが最小値であることを確認する
        self.assertAlmostEqual(final, 3.0e-5)

    # safetensorsの最終保存経路を実際に通す
    def test_final_weights_can_be_saved(self) -> None:
        """model-training依存だけでsafetensors保存を完了できる。"""

        # 小型モデル設定を作る
        config = BokuNanoConfig(
            vocab_size=32,
            d_model=16,
            n_layers=1,
            n_heads=2,
            d_ff=32,
            context_length=16,
        )
        # 小型モデルを初期化する
        model = BokuNanoForCausalLM(config)
        # 自動削除される一時ディレクトリを作る
        with tempfile.TemporaryDirectory() as temporary_directory:
            # 最終重みパスを作る
            output_path = Path(temporary_directory) / "model.safetensors"
            # 本学習と同じ保存関数を実行する
            sha256 = save_final_weights(output_path, model)
            # 重みファイルが作られたことを確認する
            self.assertTrue(output_path.is_file())
            # SHA-256が64文字であることを確認する
            self.assertEqual(len(sha256), 64)

    # Git管理済み設定とartifactの固定値を確認する
    def test_production_configuration_is_self_consistent(self) -> None:
        """BPE・訓練ZIP・validation ZIP・parameter数を照合する。"""

        # 実設定を検証する
        summary = validate_configuration(
            Path("config/boku_nano_bpe_2048.yaml"), output_override=None
        )
        # parameter数を確認する
        self.assertEqual(summary["parameter_count"], 15_735_168)
        # 標準設定が3 epochであることを確認する
        self.assertEqual(summary["epochs"], 3)
        # 固定BPEのSHA-256を確認する
        self.assertEqual(
            summary["tokenizer_sha256"],
            "6840a392e8fcae1083be06842774fa912a1797217c7033944ba2d87f1c227293",
        )
        # 訓練ZIPのSHA-256を確認する
        self.assertEqual(
            summary["source_archive_sha256"],
            "799e6dd8be7e80e48df69fed4f70f5922f7a215a8669cf0f523f3de59ae91807",
        )

    # CLI相当のepoch差し替えを確認する
    def test_epoch_override_is_applied_without_editing_yaml(self) -> None:
        """10 epoch指定が検証結果へ反映される。"""

        # 実YAMLへ10 epochの実行時上書きを適用する
        summary = validate_configuration(
            Path("config/boku_nano_bpe_2048.yaml"),
            output_override=Path("data/models/boku_nano_bpe_2048_10epoch"),
            epochs_override=10,
        )
        # 実行時epoch数だけが10へ変わることを確認する
        self.assertEqual(summary["epochs"], 10)
        # 別出力先が使われることを確認する
        self.assertEqual(
            summary["output_directory"],
            "data/models/boku_nano_bpe_2048_10epoch",
        )


# 直接実行時にも標準test runnerを起動する
if __name__ == "__main__":
    # このファイル内のテストを実行する
    unittest.main()
