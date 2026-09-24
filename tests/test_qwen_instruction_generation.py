# 必要な定義を対象モジュールから読み込む
from __future__ import annotations

# 操作定義JSONとJSON文字列を扱うために使う
import json
# テスト対象ファイルのパスを組み立てるために使う
from pathlib import Path
# prompt展開テスト用の一時ディレクトリを作るために使う
import tempfile
# 標準ライブラリだけで単体テストを実行するために使う
import unittest

# 必要な定義を対象モジュールから読み込む
from scripts.instruction_generation.generate_instruction_paraphrase_candidates import (
    # 次の値または処理を現在の構造へ組み込む
    _normalize_sequence,
    # 次の値または処理を現在の構造へ組み込む
    _override_model_path as _override_paraphrase_model_path,
    # 次の値または処理を現在の構造へ組み込む
    _parse_paraphrase_response,
    # 次の値または処理を現在の構造へ組み込む
    _select_sources,
)
# 必要な定義を対象モジュールから読み込む
from scripts.instruction_generation.generate_atomic_expression_candidates import (
    # 次の値または処理を現在の構造へ組み込む
    _build_reference_groups,
    # 次の値または処理を現在の構造へ組み込む
    _build_selected_reference_groups,
    # 次の値または処理を現在の構造へ組み込む
    _override_model_path as _override_atomic_model_path,
    # 次の値または処理を現在の構造へ組み込む
    _parse_reference_expressions,
    # 次の値または処理を現在の構造へ組み込む
    _parse_reference_operations,
    # 次の値または処理を現在の構造へ組み込む
    _read_existing_review_csv,
    # 次の値または処理を現在の構造へ組み込む
    _resolve_max_attempts,
    # 次の値または処理を現在の構造へ組み込む
    _unique_expression_pairs,
    # 次の値または処理を現在の構造へ組み込む
    _valid_connective_expression,
    # 次の値または処理を現在の構造へ組み込む
    _valid_expression,
)
# 必要な定義を対象モジュールから読み込む
from scripts.instruction_generation.qwen_teacher import (
    # 次の値または処理を現在の構造へ組み込む
    parse_json_string_object_list,
    # 次の値または処理を現在の構造へ組み込む
    parse_json_string_list,
    # 次の値または処理を現在の構造へ組み込む
    prompt_hash,
    # 次の値または処理を現在の構造へ組み込む
    reject_thinking_output,
    # 次の値または処理を現在の構造へ組み込む
    render_prompt,
    # 次の値または処理を現在の構造へ組み込む
    validate_model_config,
)


# 関連する状態と処理をまとめるクラスを定義する
class QwenTeacherUtilityTests(unittest.TestCase):
    # この工程を担当する関数を定義する
    def test_paraphrase_response_repairs_only_known_closing_quote_error(self) -> None:
        # Qwenが末尾の二重引用符だけを単一引用符にした実出力を用意する
        raw = '{"paraphrases":["偶数のみを抽出してください。\']}'
        # 本文を変えず候補を取得し、補正済みフラグが立つことを確認する
        self.assertEqual(
            # 実際の補正付き解析結果を取得する
            _parse_paraphrase_response(raw),
            # 期待する候補配列と補正フラグを設定する
            (["偶数のみを抽出してください。"], True),
        )

    # この工程を担当する関数を定義する
    def test_paraphrase_response_does_not_repair_unrelated_invalid_json(self) -> None:
        # 所定の末尾崩れ以外は暗黙補正しないことを確認する
        with self.assertRaises(ValueError):
            # 配列終端そのものがない不正JSONを解析する
            _parse_paraphrase_response('{"paraphrases":["候補"}')

    # この工程を担当する関数を定義する
    def test_model_path_can_be_overridden_without_changing_config(self) -> None:
        # clone先でモデル配置場所だけを差し替える場合の元設定を用意する
        config = {"model": {"model_path": "/original/model", "model_id": "qwen"}}
        # 使用するリソースの開始と終了をこの範囲で管理する
        with tempfile.TemporaryDirectory() as directory:
            # expectedへこの工程で使用する値を設定する
            expected = str(Path(directory).resolve())
            # 表現生成と全文言い換えの両方が同じ上書き動作をすることを確認する
            for override in (
                # 次の値または処理を現在の構造へ組み込む
                _override_atomic_model_path,
                # 次の値または処理を現在の構造へ組み込む
                _override_paraphrase_model_path,
            # 次の値または処理を現在の構造へ組み込む
            ):
                # 使用するリソースの開始と終了をこの範囲で管理する
                with self.subTest(override=override.__module__):
                    # overriddenへこの工程で使用する値を設定する
                    overridden = override(config, Path(directory))
                    # 次の値または処理を現在の構造へ組み込む
                    self.assertEqual(overridden["model"]["model_path"], expected)
        # 次の実行にも使えるよう、読込元の設定辞書は変更しない
        self.assertEqual(config["model"]["model_path"], "/original/model")

    # この工程を担当する関数を定義する
    def test_parse_json_string_list(self) -> None:
        # Qwenが指示どおり返す通常のJSON文字列を用意する
        raw = '{"expressions":["偶数だけを残す","奇数を除く"]}'
        # expressions配列が同じ順序の文字列一覧として得られることを確認する
        self.assertEqual(
            # 次の値または処理を現在の構造へ組み込む
            parse_json_string_list(raw, "expressions"),
            # 次の値または処理を現在の構造へ組み込む
            ["偶数だけを残す", "奇数を除く"],
        )

    # この工程を担当する関数を定義する
    def test_parse_fenced_json(self) -> None:
        # Qwenが誤ってMarkdownフェンスを付けた出力を用意する
        raw = '```json\n{"paraphrases":["言い換え文"]}\n```'
        # 外側フェンスを除去して候補を取得できることを確認する
        self.assertEqual(
            # 次の値または処理を現在の構造へ組み込む
            parse_json_string_list(raw, "paraphrases"),
            # 次の値または処理を現在の構造へ組み込む
            ["言い換え文"],
        )

    # この工程を担当する関数を定義する
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
            # 次の値または処理を現在の構造へ組み込む
            parse_json_string_object_list(
                # 次の値または処理を現在の構造へ組み込む
                raw,
                # この処理で扱う文字列を一覧へ加える
                "expressions",
                # 次の値または処理を現在の構造へ組み込む
                {"expression_ja", "connective_expression_ja"},
            ),
            # 次の値または処理を現在の構造へ組み込む
            [
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "expression_ja": "偶数だけを残す",
                    # 出力レコードの項目と値を設定する
                    "connective_expression_ja": "偶数だけを残し",
                }
            ],
        )

    # この工程を担当する関数を定義する
    def test_parse_expression_pair_rejects_missing_field(self) -> None:
        # 接続形がない候補は新しい確認CSVへ安全に保存できないため拒否する
        with self.assertRaises(ValueError):
            # 次の値または処理を現在の構造へ組み込む
            parse_json_string_object_list(
                # 出力レコードの項目と値を設定する
                '{"expressions":[{"expression_ja":"偶数だけを残す"}]}',
                # この処理で扱う文字列を一覧へ加える
                "expressions",
                # 次の値または処理を現在の構造へ組み込む
                {"expression_ja", "connective_expression_ja"},
            )

    # この工程を担当する関数を定義する
    def test_parse_rejects_extra_keys(self) -> None:
        # 説明文用の余分なキーを含む出力がValueErrorになることを確認する
        with self.assertRaises(ValueError):
            # 次の値または処理を現在の構造へ組み込む
            parse_json_string_list(
                # 出力レコードの項目と値を設定する
                '{"expressions":["候補"],"explanation":"説明"}',
                # この処理で扱う文字列を一覧へ加える
                "expressions",
            )

    # この工程を担当する関数を定義する
    def test_render_prompt_uses_dollar_placeholders(self) -> None:
        # テスト後に自動削除される一時ディレクトリを作る
        with tempfile.TemporaryDirectory() as directory:
            # 一時promptファイルのパスを作る
            path = Path(directory) / "prompt.txt"
            # $形式の変数を含むpromptテンプレートを書く
            path.write_text("ID=$operation_id JSON=$json", encoding="utf-8")
            # 操作IDとJSON文字列をテンプレートへ埋め込む
            rendered = render_prompt(
                # 次の値または処理を現在の構造へ組み込む
                path,
                # 次の値または処理を現在の構造へ組み込む
                {"operation_id": "atomic-1", "json": '{"x":1}'},
            )
        # JSON内の波括弧を壊さず置換できたことを確認する
        self.assertEqual(rendered, 'ID=atomic-1 JSON={"x":1}')

    # この工程を担当する関数を定義する
    def test_prompt_hash_distinguishes_message_boundary(self) -> None:
        # 連結文字列が同じでもsystem/user境界が違えばハッシュが変わることを確認する
        self.assertNotEqual(prompt_hash("ab", "c"), prompt_hash("a", "bc"))

    # この工程を担当する関数を定義する
    def test_reject_thinking_output_rejects_think_tag(self) -> None:
        # 開始タグだけ、終了タグだけ、大文字タグの各モデル出力を用意する
        outputs = ("<think>内部推論", "内部推論</think>", "<THINK>内部推論")
        # 形式の異なる各thinkタグを順番に検査する
        for raw in outputs:
            # 失敗時にどの出力だったか分かるようサブテストへ分ける
            with self.subTest(raw=raw):
                # thinkタグが一つでもあれば応答全体が拒否されることを確認する
                with self.assertRaisesRegex(ValueError, "<think>タグ"):
                    # 次の値または処理を現在の構造へ組み込む
                    reject_thinking_output(raw)

    # この工程を担当する関数を定義する
    def test_reject_thinking_output_accepts_final_answer_only(self) -> None:
        # 思考タグを含まない最終回答だけのモデル出力を用意する
        raw = '{"expressions":["候補"]}'
        # 検査済みの最終回答が変更されず返ることを確認する
        self.assertEqual(reject_thinking_output(raw), raw)

    # この工程を担当する関数を定義する
    def test_model_config_rejects_mutable_revision_name(self) -> None:
        # 必須ファイルを持つ一時的なローカルモデルディレクトリを作る
        with tempfile.TemporaryDirectory() as directory:
            # model_pathへこの工程で使用する値を設定する
            model_path = Path(directory)
            # 対象を一件ずつ取り出して処理する
            for name in ("config.json", "tokenizer_config.json", "tokenizer.json"):
                # 次の値または処理を現在の構造へ組み込む
                (model_path / name).write_text("{}", encoding="utf-8")
            # 次の値または処理を現在の構造へ組み込む
            (model_path / "model.safetensors").touch()
            # 正式生成で必要なモデル設定一式を作り、revisionだけをmainにする
            model_config = {
                # 出力レコードの項目と値を設定する
                "model_id": "Qwen/Qwen3-4B-AWQ",
                # 出力レコードの項目と値を設定する
                "model_path": str(model_path),
                # 出力レコードの項目と値を設定する
                "revision": "main",
                # 出力レコードの項目と値を設定する
                "device_map": "auto",
                # 出力レコードの項目と値を設定する
                "attn_implementation": "sdpa",
                # 出力レコードの項目と値を設定する
                "trust_remote_code": False,
                # 出力レコードの項目と値を設定する
                "local_files_only": True,
                # 出力レコードの項目と値を設定する
                "require_cuda": True,
                # 出力レコードの項目と値を設定する
                "enable_thinking": False,
            }
            # 内容が後から変わり得るmainでは正式生成できないことを確認する
            with self.assertRaisesRegex(ValueError, "40桁のコミットID"):
                # 次の値または処理を現在の構造へ組み込む
                validate_model_config(model_config)

    # この工程を担当する関数を定義する
    def test_model_config_rejects_missing_local_model_path(self) -> None:
        # 存在しない絶対パスを指定したローカルモデル設定を作る
        model_config = {
            # 出力レコードの項目と値を設定する
            "model_id": "Qwen/Qwen3-4B-AWQ",
            # 出力レコードの項目と値を設定する
            "model_path": "/path/that/does/not/exist/Qwen3-4B-AWQ",
            # 出力レコードの項目と値を設定する
            "revision": "74d4bd2bd4bff9cafc9345221320bffb08b406a3",
            # 出力レコードの項目と値を設定する
            "device_map": "auto",
            # 出力レコードの項目と値を設定する
            "attn_implementation": "sdpa",
            # 出力レコードの項目と値を設定する
            "trust_remote_code": False,
            # 出力レコードの項目と値を設定する
            "local_files_only": True,
            # 出力レコードの項目と値を設定する
            "require_cuda": True,
            # 出力レコードの項目と値を設定する
            "enable_thinking": False,
        }
        # 重みを誤ってHubから取得せず、生成前に設定エラーになることを確認する
        with self.assertRaisesRegex(ValueError, "model_pathが見つかりません"):
            # 次の値または処理を現在の構造へ組み込む
            validate_model_config(model_config)

    # この工程を担当する関数を定義する
    def test_atomic_expression_requires_dictionary_form_verb_ending(self) -> None:
        # 動詞基本形で終わる自然な候補だけが形式検査を通ることを確認する
        self.assertTrue(_valid_expression("偶数だけを残す", max_chars=80))
        # 次の値または処理を現在の構造へ組み込む
        self.assertTrue(_valid_expression("値を昇順に並べ替える", max_chars=80))
        # 名詞止め、丁寧語、依頼形は他の操作と接続しにくいため拒否する
        self.assertFalse(_valid_expression("偶数の選択", max_chars=80))
        # 次の値または処理を現在の構造へ組み込む
        self.assertFalse(_valid_expression("偶数だけを残します", max_chars=80))
        # 次の値または処理を現在の構造へ組み込む
        self.assertFalse(_valid_expression("偶数だけを残してください", max_chars=80))

    # この工程を担当する関数を定義する
    def test_atomic_expression_rejects_non_k_ascii_text(self) -> None:
        # 変数名k以外の外国語が混入した候補は形式検査で拒否する
        self.assertFalse(
            # 次の値または処理を現在の構造へ組み込む
            _valid_expression("kの剰余がゼロ olan を選ぶ", max_chars=80)
        )

    # この工程を担当する関数を定義する
    def test_atomic_connective_expression_requires_connective_form(self) -> None:
        # 連用形とて形の自然な接続形が形式検査を通ることを確認する
        valid = ("偶数だけを残し", "それぞれを2倍して", "昇順に並べ替えて")
        # 対象を一件ずつ取り出して処理する
        for expression in valid:
            # 使用するリソースの開始と終了をこの範囲で管理する
            with self.subTest(expression=expression):
                # 次の値または処理を現在の構造へ組み込む
                self.assertTrue(
                    # 次の値または処理を現在の構造へ組み込む
                    _valid_connective_expression(expression, max_chars=80)
                )
        # 終止形と句点付き表現は接続形として採用しない
        invalid = ("偶数だけを残す", "偶数だけを残し、")
        # 対象を一件ずつ取り出して処理する
        for expression in invalid:
            # 使用するリソースの開始と終了をこの範囲で管理する
            with self.subTest(expression=expression):
                # 次の値または処理を現在の構造へ組み込む
                self.assertFalse(
                    # 次の値または処理を現在の構造へ組み込む
                    _valid_connective_expression(expression, max_chars=80)
                )

    # この工程を担当する関数を定義する
    def test_read_existing_review_csv_groups_by_operation(self) -> None:
        # Excel保存で付く汎用ヘッダーと実ヘッダーを持つ確認CSVを作る
        with tempfile.TemporaryDirectory() as directory:
            # pathへこの工程で使用する値を設定する
            path = Path(directory) / "review.csv"
            # 次の値または処理を現在の構造へ組み込む
            path.write_text(
                "Column1,Column2,Column3,Column4,Column5\n"
                "expression_id,operation_id,expression_ja,"
                "connective_expression_ja,edited_expression_ja,"
                "edited_connective_expression_ja,review_status\n"
                "expr-1,atomic-000024,先頭から1個おきに取る,"
                "先頭から1個おきに取って,,,approved\n"
                "expr-2,atomic-000001,偶数を残す,偶数を残して,"
                # この処理で扱う文字列を一覧へ加える
                "偶数だけを残す,偶数だけを残して,approved\n",
                # encodingへこの工程で使用する値を設定する
                encoding="utf-8-sig",
            )
            # operation_idごとに元候補と人間修正版が得られることを確認する
            existing = _read_existing_review_csv(path)

        # 次の値または処理を現在の構造へ組み込む
        self.assertEqual(
            # 次の値または処理を現在の構造へ組み込む
            existing["atomic-000024"],
            # 次の値または処理を現在の構造へ組み込む
            [
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "expression_ja": "先頭から1個おきに取る",
                    # 出力レコードの項目と値を設定する
                    "connective_expression_ja": "先頭から1個おきに取って",
                }
            ],
        )
        # 次の値または処理を現在の構造へ組み込む
        self.assertEqual(
            # 次の値または処理を現在の構造へ組み込む
            existing["atomic-000001"],
            # 次の値または処理を現在の構造へ組み込む
            [
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "expression_ja": "偶数を残す",
                    # 出力レコードの項目と値を設定する
                    "connective_expression_ja": "偶数を残して",
                },
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "expression_ja": "偶数だけを残す",
                    # 出力レコードの項目と値を設定する
                    "connective_expression_ja": "偶数だけを残して",
                },
            ],
        )

    # この工程を担当する関数を定義する
    def test_unique_expression_pairs_preserves_first_order(self) -> None:
        # 同じ組だけを除き、入力順を変えないことを確認する
        pairs = [
            # 次の値または処理を現在の構造へ組み込む
            {
                # 出力レコードの項目と値を設定する
                "expression_ja": "偶数を残す",
                # 出力レコードの項目と値を設定する
                "connective_expression_ja": "偶数を残して",
            },
            # 次の値または処理を現在の構造へ組み込む
            {
                # 出力レコードの項目と値を設定する
                "expression_ja": "奇数を残す",
                # 出力レコードの項目と値を設定する
                "connective_expression_ja": "奇数を残して",
            },
            # 次の値または処理を現在の構造へ組み込む
            {
                # 出力レコードの項目と値を設定する
                "expression_ja": "偶数を残す",
                # 出力レコードの項目と値を設定する
                "connective_expression_ja": "偶数を残して",
            },
        ]
        # 次の値または処理を現在の構造へ組み込む
        self.assertEqual(_unique_expression_pairs(pairs), pairs[:2])

    # この工程を担当する関数を定義する
    def test_max_attempts_cli_override_takes_precedence(self) -> None:
        # CLI指定がある実行では設定JSONの試行回数より指定値を優先する
        self.assertEqual(_resolve_max_attempts(20, 1), 1)
        # CLI指定がなければ設定JSONの値を維持する
        self.assertEqual(_resolve_max_attempts(20, None), 20)

    # この工程を担当する関数を定義する
    def test_max_attempts_cli_override_rejects_zero(self) -> None:
        # 一度も生成しない指定は入力ミスとして拒否する
        with self.assertRaisesRegex(ValueError, "1以上"):
            # 次の値または処理を現在の構造へ組み込む
            _resolve_max_attempts(20, 0)

    # この工程を担当する関数を定義する
    def test_parse_reference_operations_groups_sources_by_target(self) -> None:
        # 複数の参照元を同じ対象操作へ指定した順序で保持する
        references = _parse_reference_operations(
            # 次の値または処理を現在の構造へ組み込む
            ["atomic-000010=atomic-000001", "atomic-000010=atomic-000002"],
            # valid_operation_idsへこの工程で使用する値を設定する
            valid_operation_ids={
                # この処理で扱う文字列を一覧へ加える
                "atomic-000001",
                # この処理で扱う文字列を一覧へ加える
                "atomic-000002",
                # この処理で扱う文字列を一覧へ加える
                "atomic-000010",
            },
            # selected_operation_idsへこの工程で使用する値を設定する
            selected_operation_ids={"atomic-000010"},
        )
        # 次の値または処理を現在の構造へ組み込む
        self.assertEqual(
            # 次の値または処理を現在の構造へ組み込む
            references,
            # 次の値または処理を現在の構造へ組み込む
            {"atomic-000010": ["atomic-000001", "atomic-000002"]},
        )

    # この工程を担当する関数を定義する
    def test_parse_reference_operations_rejects_unselected_target(self) -> None:
        # 生成対象外の操作へ参考例を指定すると設定ミスとして拒否する
        with self.assertRaisesRegex(ValueError, "生成対象外"):
            # 次の値または処理を現在の構造へ組み込む
            _parse_reference_operations(
                # 次の値または処理を現在の構造へ組み込む
                ["atomic-000010=atomic-000001"],
                # valid_operation_idsへこの工程で使用する値を設定する
                valid_operation_ids={"atomic-000001", "atomic-000010"},
                # selected_operation_idsへこの工程で使用する値を設定する
                selected_operation_ids={"atomic-000001"},
            )

    # この工程を担当する関数を定義する
    def test_build_reference_groups_limits_each_source(self) -> None:
        # 参照元ごとの例数上限と意味情報がプロンプト用構造へ反映される
        groups = _build_reference_groups(
            # reference_sources_by_targetへこの工程で使用する値を設定する
            reference_sources_by_target={
                # 出力レコードの項目と値を設定する
                "atomic-000010": ["atomic-000001"]
            },
            # existing_by_operationへこの工程で使用する値を設定する
            existing_by_operation={
                # 出力レコードの項目と値を設定する
                "atomic-000001": [
                    # 次の値または処理を現在の構造へ組み込む
                    {
                        # 出力レコードの項目と値を設定する
                        "expression_ja": "偶数を残す",
                        # 出力レコードの項目と値を設定する
                        "connective_expression_ja": "偶数を残して",
                    },
                    # 次の値または処理を現在の構造へ組み込む
                    {
                        # 出力レコードの項目と値を設定する
                        "expression_ja": "偶数を選ぶ",
                        # 出力レコードの項目と値を設定する
                        "connective_expression_ja": "偶数を選んで",
                    },
                ]
            },
            # all_operationsへこの工程で使用する値を設定する
            all_operations=[
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "operation_id": "atomic-000001",
                    # 出力レコードの項目と値を設定する
                    "semantic_ast": {"filter": ["even"]},
                    # 出力レコードの項目と値を設定する
                    "canonical_meaning_ja": "偶数だけを残す",
                }
            ],
            # examples_per_operationへこの工程で使用する値を設定する
            examples_per_operation=1,
        )
        # 次の値または処理を現在の構造へ組み込む
        self.assertEqual(
            # 次の値または処理を現在の構造へ組み込む
            groups["atomic-000010"][0]["expressions"],
            # 次の値または処理を現在の構造へ組み込む
            [
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "expression_ja": "偶数を残す",
                    # 出力レコードの項目と値を設定する
                    "connective_expression_ja": "偶数を残して",
                }
            ],
        )

    # この工程を担当する関数を定義する
    def test_build_selected_reference_groups_uses_exact_expression(self) -> None:
        # 同じ参照元の複数表現から明示した終止形だけが選ばれることを確認する
        selections = _parse_reference_expressions(
            # 次の値または処理を現在の構造へ組み込む
            ["atomic-000010=atomic-000001=偶数だけを抽出する"],
            # valid_operation_idsへこの工程で使用する値を設定する
            valid_operation_ids={"atomic-000001", "atomic-000010"},
            # selected_operation_idsへこの工程で使用する値を設定する
            selected_operation_ids={"atomic-000010"},
        )
        # groupsへこの工程で使用する値を設定する
        groups = _build_selected_reference_groups(
            # selected_references_by_targetへこの工程で使用する値を設定する
            selected_references_by_target=selections,
            # existing_by_operationへこの工程で使用する値を設定する
            existing_by_operation={
                # 出力レコードの項目と値を設定する
                "atomic-000001": [
                    # 次の値または処理を現在の構造へ組み込む
                    {
                        # 出力レコードの項目と値を設定する
                        "expression_ja": "偶数を残す",
                        # 出力レコードの項目と値を設定する
                        "connective_expression_ja": "偶数を残して",
                    },
                    # 次の値または処理を現在の構造へ組み込む
                    {
                        # 出力レコードの項目と値を設定する
                        "expression_ja": "偶数だけを抽出する",
                        # 出力レコードの項目と値を設定する
                        "connective_expression_ja": "偶数だけを抽出して",
                    },
                ]
            },
            # all_operationsへこの工程で使用する値を設定する
            all_operations=[
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "operation_id": "atomic-000001",
                    # 出力レコードの項目と値を設定する
                    "semantic_ast": {"filter": ["even"]},
                    # 出力レコードの項目と値を設定する
                    "canonical_meaning_ja": "偶数だけを残す",
                }
            ],
        )
        # 次の値または処理を現在の構造へ組み込む
        self.assertEqual(
            # 次の値または処理を現在の構造へ組み込む
            groups["atomic-000010"][0]["expressions"],
            # 次の値または処理を現在の構造へ組み込む
            [
                # 次の値または処理を現在の構造へ組み込む
                {
                    # 出力レコードの項目と値を設定する
                    "expression_ja": "偶数だけを抽出する",
                    # 出力レコードの項目と値を設定する
                    "connective_expression_ja": "偶数だけを抽出して",
                }
            ],
        )


# 関連する状態と処理をまとめるクラスを定義する
class ParaphraseSelectionTests(unittest.TestCase):
    # この工程を担当する関数を定義する
    def test_normalize_sequence(self) -> None:
        # 一つの抽出操作を表す意味ASTを用意する
        operation = {"filter": ["even"]}
        # 単独操作が一要素の配列へ変換されることを確認する
        self.assertEqual(_normalize_sequence(operation), [operation])
        # sequence形式では元の操作順が維持されることを確認する
        self.assertEqual(
            # 次の値または処理を現在の構造へ組み込む
            _normalize_sequence({"sequence": [operation, {"order": "ascending"}]}),
            # 次の値または処理を現在の構造へ組み込む
            [operation, {"order": "ascending"}],
        )

    # この工程を担当する関数を定義する
    def test_selection_is_deterministic_and_balanced_per_ast(self) -> None:
        # 選抜確認用に2意味ASTそれぞれ20件の訓練指示を作る
        records = [
            # 次の値または処理を現在の構造へ組み込む
            {
                # 出力レコードの項目と値を設定する
                "instruction_id": f"instruction-{index}",
                # 出力レコードの項目と値を設定する
                "spec_id": f"spec-{index // 20}",
                # 出力レコードの項目と値を設定する
                "instruction_ja": str(index),
                # 出力レコードの項目と値を設定する
                "semantic_ast": {"filter": ["even"]},
                # 訓練指示だけを選ぶための区分を設定する
                "split": "train",
                # 訓練辞書だけを選ぶための区分を設定する
                "dictionary": "train",
            }
            # 対象を一件ずつ取り出して処理する
            for index in range(40)
        ]
        # 除外される評価用指示を追加する
        records.append(
            {
                "instruction_id": "instruction-test",
                "spec_id": "spec-test",
                "instruction_ja": "評価用",
                "semantic_ast": {"filter": ["even"]},
                "split": "test",
                "dictionary": "train",
            }
        )
        # 固定seedで最初の選抜を実行する
        first = _select_sources(
            records,
            split="train",
            dictionary="train",
            per_ast=10,
            seed=123,
        )
        # 同じ条件でもう一度選抜する
        second = _select_sources(
            records,
            split="train",
            dictionary="train",
            per_ast=10,
            seed=123,
        )
        # 同じseedなら選抜結果と順序が同一になることを確認する
        self.assertEqual(first, second)
        # 2意味ASTから10件ずつ選ばれることを確認する
        self.assertEqual(len(first), 20)
        # 各意味ASTの選抜件数を数える
        counts = {
            spec_id: sum(record["spec_id"] == spec_id for record in first)
            for spec_id in {record["spec_id"] for record in first}
        }
        # 両方の意味ASTが10件ずつになることを確認する
        self.assertEqual(counts, {"spec-0": 10, "spec-1": 10})
        # 評価用指示が選ばれないことを確認する
        self.assertNotIn("instruction-test", {record["instruction_id"] for record in first})


# 関連する状態と処理をまとめるクラスを定義する
class AtomicOperationConfigTests(unittest.TestCase):
    # この工程を担当する関数を定義する
    def test_operation_definitions_match_atomic_input(self) -> None:
        # テストファイルから一階層上をプロジェクトルートとして取得する
        project_root = Path(__file__).resolve().parents[1]
        # 日本語生成用の24操作定義を読み込む
        definitions = json.loads(
            # 次の値または処理を現在の構造へ組み込む
            (project_root / "config/japanese_atomic_operations.json").read_text(
                # encodingへこの工程で使用する値を設定する
                encoding="utf-8"
            )
        # 次の値または処理を現在の構造へ組み込む
        )["operations"]
        # 正式な単独操作意味ASTのJSONLを読み込む
        atomic_records = [
            # 次の値または処理を現在の構造へ組み込む
            json.loads(line)
            # 対象を一件ずつ取り出して処理する
            for line in (
                # 次の値または処理を現在の構造へ組み込む
                project_root / "data/semantic_asts/atomic_semantic_asts.jsonl"
            )
            # 次の値または処理を現在の構造へ組み込む
            .read_text(encoding="utf-8")
            # 次の値または処理を現在の構造へ組み込む
            .splitlines()
            # 条件を満たす場合だけ次の処理を行う
            if line
        ]
        # 日本語操作定義を操作IDから意味ASTへの辞書へ変換する
        defined = {
            # 次の値または処理を現在の構造へ組み込む
            value["operation_id"]: value["semantic_ast"] for value in definitions
        }
        # 正式入力も操作IDから意味ASTへの辞書へ変換する
        source = {
            # 次の値または処理を現在の構造へ組み込む
            value["spec_id"]: value["semantic_ast"] for value in atomic_records
        }
        # 日本語操作定義と正式入力が完全一致することを確認する
        self.assertEqual(defined, source)
        # 操作定義が24件であることを確認する
        self.assertEqual(len(defined), 24)


# テストファイルを直接実行した場合だけunittestを開始する
if __name__ == "__main__":
    # 次の値または処理を現在の構造へ組み込む
    unittest.main()
