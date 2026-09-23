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
    _override_model_path as _override_paraphrase_model_path,
    _select_sources,
)
from scripts.instruction_generation.generate_atomic_expression_candidates import (
    _build_reference_groups,
    _build_selected_reference_groups,
    _override_model_path as _override_atomic_model_path,
    _parse_reference_expressions,
    _parse_reference_operations,
    _read_existing_review_csv,
    _resolve_max_attempts,
    _unique_expression_pairs,
    _valid_connective_expression,
    _valid_expression,
)
from scripts.instruction_generation.qwen_teacher import (
    parse_json_string_object_list,
    parse_json_string_list,
    prompt_hash,
    reject_thinking_output,
    render_prompt,
    validate_model_config,
)


class QwenTeacherUtilityTests(unittest.TestCase):
    def test_model_path_can_be_overridden_without_changing_config(self) -> None:
        # clone先でモデル配置場所だけを差し替える場合の元設定を用意する
        config = {"model": {"model_path": "/original/model", "model_id": "qwen"}}
        with tempfile.TemporaryDirectory() as directory:
            expected = str(Path(directory).resolve())
            # 表現生成と全文言い換えの両方が同じ上書き動作をすることを確認する
            for override in (
                _override_atomic_model_path,
                _override_paraphrase_model_path,
            ):
                with self.subTest(override=override.__module__):
                    overridden = override(config, Path(directory))
                    self.assertEqual(overridden["model"]["model_path"], expected)
        # 次の実行にも使えるよう、読込元の設定辞書は変更しない
        self.assertEqual(config["model"]["model_path"], "/original/model")

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

    def test_parse_expression_pair_list(self) -> None:
        # 終止形と接続形の組を持つ正式なモデル出力を用意する
        raw = (
            '{"expressions":['
            '{"expression_ja":"偶数だけを残す",'
            '"connective_expression_ja":"偶数だけを残し"}'
            "]}"
        )
        # 二つの必須フィールドを保った辞書配列として得られることを確認する
        self.assertEqual(
            parse_json_string_object_list(
                raw,
                "expressions",
                {"expression_ja", "connective_expression_ja"},
            ),
            [
                {
                    "expression_ja": "偶数だけを残す",
                    "connective_expression_ja": "偶数だけを残し",
                }
            ],
        )

    def test_parse_expression_pair_rejects_missing_field(self) -> None:
        # 接続形がない候補は新しい確認CSVへ安全に保存できないため拒否する
        with self.assertRaises(ValueError):
            parse_json_string_object_list(
                '{"expressions":[{"expression_ja":"偶数だけを残す"}]}',
                "expressions",
                {"expression_ja", "connective_expression_ja"},
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
        # 必須ファイルを持つ一時的なローカルモデルディレクトリを作る
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory)
            for name in ("config.json", "tokenizer_config.json", "tokenizer.json"):
                (model_path / name).write_text("{}", encoding="utf-8")
            (model_path / "model.safetensors").touch()
            # 正式生成で必要なモデル設定一式を作り、revisionだけをmainにする
            model_config = {
                "model_id": "Qwen/Qwen3-4B-AWQ",
                "model_path": str(model_path),
                "revision": "main",
                "device_map": "auto",
                "attn_implementation": "sdpa",
                "trust_remote_code": False,
                "local_files_only": True,
                "require_cuda": True,
                "enable_thinking": False,
            }
            # 内容が後から変わり得るmainでは正式生成できないことを確認する
            with self.assertRaisesRegex(ValueError, "40桁のコミットID"):
                validate_model_config(model_config)

    def test_model_config_rejects_missing_local_model_path(self) -> None:
        # 存在しない絶対パスを指定したローカルモデル設定を作る
        model_config = {
            "model_id": "Qwen/Qwen3-4B-AWQ",
            "model_path": "/path/that/does/not/exist/Qwen3-4B-AWQ",
            "revision": "74d4bd2bd4bff9cafc9345221320bffb08b406a3",
            "device_map": "auto",
            "attn_implementation": "sdpa",
            "trust_remote_code": False,
            "local_files_only": True,
            "require_cuda": True,
            "enable_thinking": False,
        }
        # 重みを誤ってHubから取得せず、生成前に設定エラーになることを確認する
        with self.assertRaisesRegex(ValueError, "model_pathが見つかりません"):
            validate_model_config(model_config)

    def test_atomic_expression_requires_dictionary_form_verb_ending(self) -> None:
        # 動詞基本形で終わる自然な候補だけが形式検査を通ることを確認する
        self.assertTrue(_valid_expression("偶数だけを残す", max_chars=80))
        self.assertTrue(_valid_expression("値を昇順に並べ替える", max_chars=80))
        # 名詞止め、丁寧語、依頼形は他の操作と接続しにくいため拒否する
        self.assertFalse(_valid_expression("偶数の選択", max_chars=80))
        self.assertFalse(_valid_expression("偶数だけを残します", max_chars=80))
        self.assertFalse(_valid_expression("偶数だけを残してください", max_chars=80))

    def test_atomic_expression_rejects_non_k_ascii_text(self) -> None:
        # 変数名k以外の外国語が混入した候補は形式検査で拒否する
        self.assertFalse(
            _valid_expression("kの剰余がゼロ olan を選ぶ", max_chars=80)
        )

    def test_atomic_connective_expression_requires_connective_form(self) -> None:
        # 連用形とて形の自然な接続形が形式検査を通ることを確認する
        valid = ("偶数だけを残し", "それぞれを2倍して", "昇順に並べ替えて")
        for expression in valid:
            with self.subTest(expression=expression):
                self.assertTrue(
                    _valid_connective_expression(expression, max_chars=80)
                )
        # 終止形と句点付き表現は接続形として採用しない
        invalid = ("偶数だけを残す", "偶数だけを残し、")
        for expression in invalid:
            with self.subTest(expression=expression):
                self.assertFalse(
                    _valid_connective_expression(expression, max_chars=80)
                )

    def test_read_existing_review_csv_groups_by_operation(self) -> None:
        # Excel保存で付く汎用ヘッダーと実ヘッダーを持つ確認CSVを作る
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            path.write_text(
                "Column1,Column2,Column3,Column4,Column5\n"
                "expression_id,operation_id,expression_ja,"
                "connective_expression_ja,edited_expression_ja,"
                "edited_connective_expression_ja,review_status\n"
                "expr-1,atomic-000024,先頭から1個おきに取る,"
                "先頭から1個おきに取って,,,approved\n"
                "expr-2,atomic-000001,偶数を残す,偶数を残して,"
                "偶数だけを残す,偶数だけを残して,approved\n",
                encoding="utf-8-sig",
            )
            # operation_idごとに元候補と人間修正版が得られることを確認する
            existing = _read_existing_review_csv(path)

        self.assertEqual(
            existing["atomic-000024"],
            [
                {
                    "expression_ja": "先頭から1個おきに取る",
                    "connective_expression_ja": "先頭から1個おきに取って",
                }
            ],
        )
        self.assertEqual(
            existing["atomic-000001"],
            [
                {
                    "expression_ja": "偶数を残す",
                    "connective_expression_ja": "偶数を残して",
                },
                {
                    "expression_ja": "偶数だけを残す",
                    "connective_expression_ja": "偶数だけを残して",
                },
            ],
        )

    def test_unique_expression_pairs_preserves_first_order(self) -> None:
        # 同じ組だけを除き、入力順を変えないことを確認する
        pairs = [
            {
                "expression_ja": "偶数を残す",
                "connective_expression_ja": "偶数を残して",
            },
            {
                "expression_ja": "奇数を残す",
                "connective_expression_ja": "奇数を残して",
            },
            {
                "expression_ja": "偶数を残す",
                "connective_expression_ja": "偶数を残して",
            },
        ]
        self.assertEqual(_unique_expression_pairs(pairs), pairs[:2])

    def test_max_attempts_cli_override_takes_precedence(self) -> None:
        # CLI指定がある実行では設定JSONの試行回数より指定値を優先する
        self.assertEqual(_resolve_max_attempts(20, 1), 1)
        # CLI指定がなければ設定JSONの値を維持する
        self.assertEqual(_resolve_max_attempts(20, None), 20)

    def test_max_attempts_cli_override_rejects_zero(self) -> None:
        # 一度も生成しない指定は入力ミスとして拒否する
        with self.assertRaisesRegex(ValueError, "1以上"):
            _resolve_max_attempts(20, 0)

    def test_parse_reference_operations_groups_sources_by_target(self) -> None:
        # 複数の参照元を同じ対象操作へ指定した順序で保持する
        references = _parse_reference_operations(
            ["atomic-000010=atomic-000001", "atomic-000010=atomic-000002"],
            valid_operation_ids={
                "atomic-000001",
                "atomic-000002",
                "atomic-000010",
            },
            selected_operation_ids={"atomic-000010"},
        )
        self.assertEqual(
            references,
            {"atomic-000010": ["atomic-000001", "atomic-000002"]},
        )

    def test_parse_reference_operations_rejects_unselected_target(self) -> None:
        # 生成対象外の操作へ参考例を指定すると設定ミスとして拒否する
        with self.assertRaisesRegex(ValueError, "生成対象外"):
            _parse_reference_operations(
                ["atomic-000010=atomic-000001"],
                valid_operation_ids={"atomic-000001", "atomic-000010"},
                selected_operation_ids={"atomic-000001"},
            )

    def test_build_reference_groups_limits_each_source(self) -> None:
        # 参照元ごとの例数上限と意味情報がプロンプト用構造へ反映される
        groups = _build_reference_groups(
            reference_sources_by_target={
                "atomic-000010": ["atomic-000001"]
            },
            existing_by_operation={
                "atomic-000001": [
                    {
                        "expression_ja": "偶数を残す",
                        "connective_expression_ja": "偶数を残して",
                    },
                    {
                        "expression_ja": "偶数を選ぶ",
                        "connective_expression_ja": "偶数を選んで",
                    },
                ]
            },
            all_operations=[
                {
                    "operation_id": "atomic-000001",
                    "semantic_ast": {"filter": ["even"]},
                    "canonical_meaning_ja": "偶数だけを残す",
                }
            ],
            examples_per_operation=1,
        )
        self.assertEqual(
            groups["atomic-000010"][0]["expressions"],
            [
                {
                    "expression_ja": "偶数を残す",
                    "connective_expression_ja": "偶数を残して",
                }
            ],
        )

    def test_build_selected_reference_groups_uses_exact_expression(self) -> None:
        # 同じ参照元の複数表現から明示した終止形だけが選ばれることを確認する
        selections = _parse_reference_expressions(
            ["atomic-000010=atomic-000001=偶数だけを抽出する"],
            valid_operation_ids={"atomic-000001", "atomic-000010"},
            selected_operation_ids={"atomic-000010"},
        )
        groups = _build_selected_reference_groups(
            selected_references_by_target=selections,
            existing_by_operation={
                "atomic-000001": [
                    {
                        "expression_ja": "偶数を残す",
                        "connective_expression_ja": "偶数を残して",
                    },
                    {
                        "expression_ja": "偶数だけを抽出する",
                        "connective_expression_ja": "偶数だけを抽出して",
                    },
                ]
            },
            all_operations=[
                {
                    "operation_id": "atomic-000001",
                    "semantic_ast": {"filter": ["even"]},
                    "canonical_meaning_ja": "偶数だけを残す",
                }
            ],
        )
        self.assertEqual(
            groups["atomic-000010"][0]["expressions"],
            [
                {
                    "expression_ja": "偶数だけを抽出する",
                    "connective_expression_ja": "偶数だけを抽出して",
                }
            ],
        )


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
