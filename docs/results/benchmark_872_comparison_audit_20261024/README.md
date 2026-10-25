# 発表資料と872問再構成版の比較監査

監査日：2026-10-24。学習・モデル推論の再実行はしていない。保存済み採点の再集計、ファイルhash照合、問題の意味ASTを179固定入力で実行する診断、旧15Mの4操作100問の保存済み生成コードの限定再採点を実施した。この監査時点では既存の結果・図・質問・評価スクリプトは変更していない。

**2026-10-25追記：** 再構成版の質問・結果・図・生成器を現行Gitツリーから削除し、過去commitは保持した。この文書は撤回理由を残すための監査記録であり、再構成版を有効な性能結果として掲載するものではない。今後の入口は[固定872問のCUDA評価手順](../../procedures/composition_872_cuda_evaluation.md)。このPCで新しいモデル評価は実行していない。

このベンチマークは、日本語指示からPythonの`solve(xs, k)`を生成させる9カテゴリ・872問の評価である。1問につき固定179入力すべてで正しい出力を返し、構文・コード契約・入力非破壊・時間制限を満たした場合に合格とする。同じ問題数でも、問題文や操作列の選び方が違えば、同じ能力・難度の比較にはならない。

## 結論

**評価実行スクリプトは同一ではない。質問集合と難度条件も異なる。** 15Mなどの学習済み重みは同じ由来だが、再構成版の数値を発表資料と同じ872問の再評価・性能改善として扱うことはできない。

発表資料の数値は問題別採点JSONLと一致しており、図の集計誤りではない。再構成時に問題を新しく作ったことに加え、「異なる4操作」の機能的な難度条件が保存されなかった点が、比較不能になった重要な理由である。

比較上の問題が表れた例は、15Mの「異なる4操作」が発表資料で29/100、撤回した再構成版で63/100だったことである。**29→63を性能向上とは解釈できない。** 再構成版のモデル別成績表・図は削除し、ここでは比較不能になった経緯を説明する最小限の数値だけを残す。

発表資料の出典：[スライド](../../report/boku_nano_presentation.md)、[15Mの問題別採点](../../../data/benchmarks/composition_suite_20261008/runs/boku-15m-1epoch/scored.jsonl)。撤回前の再構成版は[過去commitの報告](https://github.com/yuuono/bokunano/blob/2c414ac33c04bc0f928e3c9dd24790611908a094/docs/results/composition_suite_872_v2_20261018.md)にのみ残る。監査の機械可読記録は[audit.json](audit.json)。

## 1. 同じ872問ではない

| ファイル | SHA-256 |
|---|---|
| 発表資料の質問 | `aa119fa2a9e8507136ad14a54b9d3d2e9043fd81af9e48251ef7f5c49c20f97f` |
| 再構成版の質問 | `f8941b0bdfcea0461727eaaa049bc984ec40a500593dd5cb9147bcf0dfa45ace` |
| 両者の179検査入力 | `0090a38d255848a813876ce3b64a8029603aa14e4181b453a89801b41ac67fc2` |

質問本文の完全一致は**47/872**。825問は異なる。異なる4操作は、問題文だけでなく操作列の意味ASTも**共通0/100**。未学習3操作の共通ASTは16/100、ABABは20/100だった。件数とカテゴリ名だけでは同一ベンチマークにはならない。

再構成版の報告には「旧質問が当時のcheckoutに無かったので再構成した」「旧図と直接の差分比較はしない」とある。これは報告された当時の状況であり、今回のローカルには旧質問、raw出力、採点JSONLが存在する。現在も旧データが無いという意味ではない。

## 2. 「異なる4操作」の出題条件が変わった

[旧生成器の保存写し](evidence/build_composition_suite.py.txt)の103–107行は、179入力での出力が訓練問題等と機能的に重複する問題、またはどれか1操作を取り除いても出力が変わらない問題を除外する。

対して[再構成時の生成器・293–309行](https://github.com/yuuono/bokunano/blob/2c414ac33c04bc0f928e3c9dd24790611908a094/scripts/model/benchmark.py#L293-L309)は、24操作から異なる4操作をランダム抽出して100操作列を選ぶ。旧版の機能的な重複・省略可能操作を除く検査は実装されていない。

実ファイルの100問を、両者共通の179入力で検査した：

| 診断 | 発表資料の100問 | 再構成版の100問 |
|---|---:|---:|
| どれか1操作を取り除いても全179出力が同じ | 0 | **59** |
| 全179入力で正解が空リスト | 0 | **26** |
| 異なる出力パターンの数 | 100 | 74 |

例：再構成版の`general_4op-004`は「奇数だけを残す → 偶数だけを残す → 隔番で取る → k以下を残す」。最初の2操作で空リストになるので、残りを省いても正解になる。この問題では`return []`で正しい出力となり、4段階を実行できることの証拠にならない。

再構成版の`general_4op-001`も「偶数 → kより大きい値 → 絶対値 → 末尾k個」で、仕様のkは1〜10だから絶対値処理を省ける。旧4操作にはこのような省略可能な問題を入れない条件があった。

これらは**固定179入力上での診断**であり、一般の全入力での形式的な等価性証明ではない。26問と59問の件数を点差34に直接割り当てることもできない。新しい問題別出力が無いため、そのうち実際に何問をモデルが省略コードで正解したかは不明である。

ABABは旧版にも機能的な冗長性を含むため、上記の「旧版で除外していた」説明をABABに拡張しない。ABABの選択方法・問題は変わっているが、別の条件差である。

## 3. 同じ名前のbenchmark.pyでも実体・実行経路が違う

発表資料にある`benchmark.py --models ... --presentation ...`は、保存済み採点を検証して図を作る呼出しである。`--evaluate-missing`等がなければモデル推論は実行しない。作図コマンドが似ていることは、同じコードで評価した証拠にならない。

発表資料の872問の実行来歴：

```text
旧672問：run_composition_suite.py → score_composition_suite.py
差替200問：evaluate_boku_composition.py → score_composition_suite.py
結合：run_composition_revision.py
保存結果の検証・作図：ローカルのbenchmark.py
```

[合成処理の保存写し](evidence/run_composition_revision.py.txt)は問題文・意味ASTなどを照合して旧672問と差替200問を結合する。[15Mの設定](../../../data/benchmarks/composition_suite_20261008/runs/boku-15m-1epoch/config.json)と[採点来歴](../../../data/benchmarks/composition_suite_20261008/runs/boku-15m-1epoch/scoring_provenance.json)に由来がある。記録された次のhashを監査時のファイルと照合し、全て一致した。旧runner 2本は[evidence/run_composition_suite.py.txt](evidence/run_composition_suite.py.txt)、[evidence/evaluate_boku_composition.py.txt](evidence/evaluate_boku_composition.py.txt)に当時のbytesを保存した。evidenceは監査用の写しであり、今回の実行入口ではない。

| 旧実行ファイル | SHA-256 |
|---|---|
| run_composition_suite.py | `7036ca62ef8fdd1c146f413146af9e70181fc816e4cc3f13065c20f371cfd194` |
| evaluate_boku_composition.py | `b384453bec58de1d96410641c2136494323345c42ed8ac677ab904d0242b40ad` |
| run_composition_revision.py | `84d341ed13d10957a1ff4f55e1eb0a98576d4b2876b25dc3cd93163111392f70` |
| score_composition_suite.py | `e4d86b978fb968040371ce12ee0c8903f056ae2a303426c4b4bebe0b3e4ab8e1` |
| composition_suite_common.py | `a38d66004952c7e896824fe6c9af36ea2f45d4848897f2ced877926deaa1da72` |

再構成版はcommit `2c414ac33c04bc0f928e3c9dd24790611908a094`で追加された別内容の[benchmark.py](https://github.com/yuuono/bokunano/blob/2c414ac33c04bc0f928e3c9dd24790611908a094/scripts/model/benchmark.py)。397–413行でPyTorchモデル読込・生成、437–441行で別の検証器を呼ぶ。

```text
再構成版benchmark.py.evaluate_model()
  → evaluate_boku_nano.load_model / greedy_generate_equal_length
  → GeneratedCodeVerifierSession
```

| 条件 | 発表資料 | 再構成版 |
|---|---|---|
| 推論 | ONNX Runtime CPU、1問ずつ | PyTorch CPU float32、同じprompt長で一括 |
| 生成終了 | EOSまたはprompt＋生成256token | EOS、最大新規160token、context制限 |
| 採点器 | score_composition_suite.py | GeneratedCodeVerifierSession |
| 静的検査 | score_browser_100_benchmark.validate | python_code_generator.validate_generated_code |
| 実行時間制限 | wall5秒・CPU2秒 | wall3秒 |
| greedy・入力テンプレート | 同じ | 同じ |
| tokenizer・179検査入力 | 同じhash | 同じhash |

2026-10-24の監査時、ローカルのbenchmark.pyは発表資料側の内容を保持しており、当時のGit HEADにある再構成版と異なっていた。以前のpullで既存ローカルファイルを保護したためである。2026-10-25に旧ローカル版を未追跡の`benchmark_presentation_legacy.py`へ同一bytesで退避し、現在の`benchmark.py`を固定872問CUDA評価の入口へ置き換えた。以下のhashは監査当時の2種類を指す。

- ローカルSHA：`5117d04d10b20b08804f7babfbf4e8b198711b0b4f646468105941da33200213`
- 再構成版SHA：`0dd37bc3cd09ae828ded9d155b859edae448dc3c7faa8e8acf4e16cce7392009`

再構成版の実体を確認するには、作業中のファイルではなく、上記commitの内容を参照する必要がある。

証拠の範囲として、旧評価は実行時のrunner/scorer hashと現在の実体まで照合できた。再構成版は報告が示す再現コードと集計JSONを確認したが、今回のローカルには再構成版の問題別raw/scoredがなく、実行時スクリプトhashも集計JSONには記録されていない。新側の全実行過程を独立に再現確認した、という意味ではない。

## 4. モデル変更・採点変更の切り分け

15MのONNX元重みと再構成版のsafetensors重みはともに`1a0002e1b50aeae59805d8087fbaa16be1b6e2716d78a085230f2cc35edbf68f`。5M・1Mも元重みhashは一致した。別の学習済みモデルを使ったことは、今回の差の説明にならない。

さらに、旧15Mの異なる4操作100問の保存済み生成コードだけを、再構成版の抽出処理とGeneratedCodeVerifierSessionで再採点した。

- 旧採点：29/100
- 新採点：29/100
- 合否変更：0問

[100問の再採点記録](rescore_old_15m_general4.json)。モデル生成を伴わない限定検証であり、少なくとも旧100問の保存済みコードでは、採点器変更で29→63になったわけではない。

旧15Mの872件はすべてEOS終了し、最大生成長34tokenだった。生成上限160tokenの違いを大差の原因とする根拠もない。推論backend差は残るが、同一問題でONNXとPyTorchを再生成していないので寄与を断定しない。

## 5. 今後の比較で固定すべきもの

発表資料との比較を行う場合は、現在存在する旧質問`aa119fa2…`、179入力`0090a38d…`、旧入力テンプレート・生成条件・採点器を正本とする。loopモデルのためPyTorch実行が必要なら、まず通常15Mを同じ旧872問で実行し、ONNX版の保存済み出力・合否と一致するかを確認してから比較する。

再構成版の質問・集計・図・現行生成器は削除した。過去commitと本監査の難度診断・撤回理由は残す。旧3モデルの保存済み出力・採点・設定は変更せず収録し、PyTorch CUDA版の結果は新しい出力先に保存する。旧キャッシュから穴埋めせず全872問を生成する。問題と採点基準は旧版へ統一するが、推論backendは変更するため「評価実行コードも完全に同一」とは表現しない。
