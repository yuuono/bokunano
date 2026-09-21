from __future__ import annotations

# 操作定義JSONとJSON文字列を扱うために使う
import json
# テスト対象ファイルのパスを組み立てるために使う
from pathlib import Path
# prompt展開テスト用の一時ディレクトリを作るために使う
import tempfile
# 標準ライブラリだけで単体テストを実行するために使う
import unittest

from scripts.instruction_generation.generate_instruction_paraphrase_candidates import (
    _normalize_sequence,
    _select_sources,
)
from scripts.instruction_generation.qwen_teacher import (
    parse_json_string_list,
    prompt_hash,
    reject_thinking_output,
    render_prompt,
    validate_model_config,
)


class QwenTeacherUtilityTests(unittest.TestCase):
    def test_parse_json_string_list(self) -> None:
        # Qwenが指示どおり返す通常のJSON文字列を用意する
        raw = '{"expressions":["偶数だけを残す","奇数を除く"]}'
        # expressions配列が同じ順序の文字列一覧として得られることを確認する
        self.assertEqual(
            parse_json_string_list(raw, "expressions"),
            ["偶数だけを残す", "奇数を除く"],
        )

    def test_parse_fenced_json(self) -> None:
        # Qwenが誤ってMarkdownフェンスを付けた出力を用意する
        raw = '```json\n{"paraphrases":["言い換え文"]}\n```'
        # 外側フェンスを除去して候補を取得できることを確認する
        self.assertEqual(
            parse_json_string_list(raw, "paraphrases"),
            ["言い換え文"],
        )

    def test_parse_rejects_extra_keys(self) -> None:
        # 説明文用の余分なキーを含む出力がValueErrorになることを確認する
        with self.assertRaises(ValueError):
            parse_json_string_list(
                '{"expressions":["候補"],"explanation":"説明"}',
                "expressions",
            )

    def test_render_prompt_uses_dollar_placeholders(self) -> None:
        # テスト後に自動削除される一時ディレクトリを作る
        with tempfile.TemporaryDirectory() as directory:
            # 一時promptファイルのパスを作る
            path = Path(directory) / "prompt.txt"
            # $形式の変数を含むpromptテンプレートを書く
            path.write_text("ID=$operation_id JSON=$json", encoding="utf-8")
            # 操作IDとJSON文字列をテンプレートへ埋め込む
            rendered = render_prompt(
                path,
                {"operation_id": "atomic-1", "json": '{"x":1}'},
            )
        # JSON内の波括弧を壊さず置換できたことを確認する
        self.assertEqual(rendered, 'ID=atomic-1 JSON={"x":1}')

    def test_prompt_hash_distinguishes_message_boundary(self) -> None:
        # 連結文字列が同じでもsystem/user境界が違えばハッシュが変わることを確認する
        self.assertNotEqual(prompt_hash("ab", "c"), prompt_hash("a", "bc"))

    def test_reject_thinking_output_rejects_think_tag(self) -> None:
        # 開始タグだけ、終了タグだけ、大文字タグの各モデル出力を用意する
        outputs = ("<think>内部推論", "内部推論</think>", "<THINK>内部推論")
        # 形式の異なる各thinkタグを順番に検査する
        for raw in outputs:
            # 失敗時にどの出力だったか分かるようサブテストへ分ける
            with self.subTest(raw=raw):
                # thinkタグが一つでもあれば応答全体が拒否されることを確認する
                with self.assertRaisesRegex(ValueError, "<think>タグ"):
                    reject_thinking_output(raw)

    def test_reject_thinking_output_accepts_final_answer_only(self) -> None:
        # 思考タグを含まない最終回答だけのモデル出力を用意する
        raw = '{"expressions":["候補"]}'
        # 検査済みの最終回答が変更されず返ることを確認する
        self.assertEqual(reject_thinking_output(raw), raw)

    def test_model_config_rejects_mutable_revision_name(self) -> None:
        # 正式生成で必要なモデル設定一式を作り、revisionだけをmainにする
        model_config = {
            "model_id": "Qwen/Qwen3-4B-AWQ",
            "revision": "main",
            "device_map": "auto",
            "attn_implementation": "sdpa",
            "trust_remote_code": False,
            "local_files_only": False,
            "require_cuda": True,
            "enable_thinking": False,
        }
        # 内容が後から変わり得るmainでは正式生成できないことを確認する
        with self.assertRaisesRegex(ValueError, "40桁のコミットID"):
            validate_model_config(model_config)


class ParaphraseSelectionTests(unittest.TestCase):
    def test_normalize_sequence(self) -> None:
        # 一つの抽出操作を表す意味ASTを用意する
        operation = {"filter": ["even"]}
        # 単独操作が一要素の配列へ変換されることを確認する
        self.assertEqual(_normalize_sequence(operation), [operation])
        # sequence形式では元の操作順が維持されることを確認する
        self.assertEqual(
            _normalize_sequence({"sequence": [operation, {"order": "ascending"}]}),
            [operation, {"order": "ascending"}],
        )

    def test_selection_is_deterministic_and_bounded(self) -> None:
        # 選抜確認用に100件の指示レコードを作る
        records = [
            {
                "instruction_id": f"instruction-{index}",
                "instruction_ja": str(index),
                "semantic_ast": {"filter": ["even"]},
            }
            for index in range(100)
        ]
        # 固定seedで最初の選抜を実行する
        first = _select_sources(records, rate=0.5, maximum=10, seed=123)
        # 同じ条件でもう一度選抜する
        second = _select_sources(records, rate=0.5, maximum=10, seed=123)
        # 同じseedなら選抜結果と順序が同一になることを確認する
        self.assertEqual(first, second)
        # 選抜件数が設定上限を超えないことを確認する
        self.assertLessEqual(len(first), 10)


class AtomicOperationConfigTests(unittest.TestCase):
    def test_operation_definitions_match_atomic_input(self) -> None:
        # テストファイルから一階層上をプロジェクトルートとして取得する
        project_root = Path(__file__).resolve().parents[1]
        # 日本語生成用の24操作定義を読み込む
        definitions = json.loads(
            (project_root / "config/japanese_atomic_operations.json").read_text(
                encoding="utf-8"
            )
        )["operations"]
        # 正式な単独操作意味ASTのJSONLを読み込む
        atomic_records = [
            json.loads(line)
            for line in (
                project_root / "data/semantic_asts/atomic_semantic_asts.jsonl"
            )
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        # 日本語操作定義を操作IDから意味ASTへの辞書へ変換する
        defined = {
            value["operation_id"]: value["semantic_ast"] for value in definitions
        }
        # 正式入力も操作IDから意味ASTへの辞書へ変換する
        source = {
            value["spec_id"]: value["semantic_ast"] for value in atomic_records
        }
        # 日本語操作定義と正式入力が完全一致することを確認する
        self.assertEqual(defined, source)
        # 操作定義が24件であることを確認する
        self.assertEqual(len(defined), 24)


# テストファイルを直接実行した場合だけunittestを開始する
if __name__ == "__main__":
    unittest.main()
