---
marp: true
theme: default
size: 16:9
paginate: true
lang: ja
title: Boku-nano 日本語の指示からコードを作る小さなモデル
description: モデル規模別評価、1Mの3epoch loss、attention、組み合わせ汎化ベンチマークと評価設計
style: |
  section { display: block; padding: 48px 62px 46px; background: #fff; color: #17212b; font-family: "Hiragino Sans", "Noto Sans JP", "Yu Gothic", sans-serif; font-size: 27px; line-height: 1.5; }
  h1 { font-size: 38px; line-height: 1.3; color: #245f8b; margin: 0 0 24px; }
  h2 { font-size: 30px; line-height: 1.4; margin: 20px 0; }
  p { margin: 18px 0; }
  strong { color: #245f8b; }
  ul, ol { padding-left: 1.25em; margin: 18px 0; }
  li { margin: 12px 0; }
  table { display: table; width: 100%; border-collapse: collapse; font-size: 24px; margin: 20px 0; }
  th, td { padding: 10px 13px; border: 0; border-bottom: 1px solid #d8e1e9; text-align: left; }
  th { background: #eaf3fb; color: #245f8b; }
  tr { background: #fff !important; }
  tbody tr:nth-child(even) { background: #f7f9fc !important; }
  blockquote { margin: 20px 0; padding: 10px 18px; border-left: 4px solid #745db3; background: #f5f3fa; }
  blockquote p { margin: 0; font-size: 25px; }
  code { font-family: "SFMono-Regular", Menlo, "Hiragino Sans", monospace; font-size: .88em; background: #eef3f7; }
  pre { padding: 16px 22px; border: 1px solid #d8e1e9; background: #f7f9fc; font-size: 23px; line-height: 1.45; }
  pre code { font-size: 1em; background: transparent; }
  a { color: #2877aa; }
    section.cover { position: relative; display: flex; flex-direction: column; align-items: flex-start; justify-content: center; padding: 65px 540px 65px 100px; }
  section.cover h1 { font-size: 62px; }
    section.cover h2 { font-size: 36px; margin-top: 42px; color: #17212b; }
    section.cover img.cover-avatar { position: absolute; top: 42%; right: 90px; width: 360px; height: 360px; transform: translateY(-50%); object-fit: cover; border-radius: 50%; }
  section.compact { font-size: 25px; }
  section.compact table { font-size: 22px; }
  section.compact th, section.compact td { padding: 9px 12px; }
  section.diagram table { font-size: 25px; }
  section.diagram td:first-child { white-space: nowrap; }
  section.result table { font-size: 25px; }
  section.result td:nth-child(2) { font-family: "Hiragino Sans", "Noto Sans JP", sans-serif; white-space: nowrap; letter-spacing: 1px; }
  section.sources { font-size: 25px; }
  section.sources p:last-of-type { font-size: 18px; line-height: 1.45; }
  section::after { color: #64748b; font-size: 16px; }
  section.key-goal, section.key-ast, section.key-data { font-size: 28px; }
  section.key-goal h1, section.key-ast h1, section.key-data h1 { margin-bottom: 24px; }
  section.key-goal h2, section.key-ast h2 { font-size: 29px; margin: 28px 0 14px; }
  section.key-goal table, section.key-data table {
    table-layout: fixed; border-collapse: separate; border-spacing: 16px 0;
    width: calc(100% + 32px); margin-left: -16px;
  }
  section.key-goal th, section.key-data th { font-size: 27px; padding: 15px 20px; }
  section.key-goal td, section.key-data td { font-size: 25px; padding: 12px 20px; line-height: 1.5; }
  section.key-goal th:first-child, section.key-data th:first-child { background: #eaf3fb; color: #245f8b; }
  section.key-goal td:first-child, section.key-data td:first-child { background: #f1f6fb; }
  section.key-goal th:nth-child(2), section.key-data th:nth-child(2) { background: #e9f5ed; color: #327c50; }
  section.key-goal td:nth-child(2), section.key-data td:nth-child(2) { background: #f1f8f3; }
  section.key-ast table { font-size: 26px; margin-top: 24px; }
  section.key-ast blockquote { margin: 14px 0 24px; padding: 18px 24px; }
  section.key-ast blockquote p { font-size: 31px; text-align: center; }
  section.key-data { font-size: 26px; }
  section.key-data h1 { font-size: 38px; }
  section.key-data h2 { font-size: 28px; text-align: center; margin: 18px 0; color: #745db3; }
  section.key-data p { margin: 18px 0; }
  section.key-data blockquote p { font-size: 27px; }

  /* 全体図の文字は2ページ目のMarkdown本文で編集する */
  section.intro-overview { font-size: 17px; line-height: 1.45; }
  section.intro-overview h1 { margin: 0 0 6px; font-size: 35px; line-height: 1.25; color: #17212b; }
  section.intro-overview h1 + p { margin: 0; font-size: 18px; color: #52606d; }
  section.intro-overview h2 { margin: 27px 0 12px; font-size: 19px; line-height: 1.25; color: #334155; }
  section.intro-overview .ov-flow { display: grid; grid-template-columns: repeat(3, 1fr); gap: 50px; height: 184px; }
  section.intro-overview .ov-card { position: relative; padding: 16px 20px; border-radius: 14px; background: #eaf3fb; }
  section.intro-overview .ov-card:nth-child(2) { background: #e9e7f8; }
  section.intro-overview .ov-card:nth-child(3) { background: #e9f5ed; }
  section.intro-overview .ov-card:not(:last-child)::after { content: "→"; position: absolute; right: -43px; top: 72px; font-size: 31px; color: #45556a; }
  section.intro-overview .ov-card h3 { margin: 0 0 12px; font-size: 21px; line-height: 1.3; color: #245f8b; }
  section.intro-overview .ov-card p { margin: 0 0 8px; font-size: 17px; line-height: 1.45; }
  section.intro-overview .ov-card p:last-child { position: absolute; left: 20px; right: 20px; bottom: 14px; margin: 0; font-size: 14px; color: #52606d; }
  section.intro-overview .ov-card:last-child p:last-child { position: static; font-size: 15px; color: #17212b; }
  section.intro-overview .ov-card code { background: transparent; font-size: 15px; white-space: normal; }
  section.intro-overview .ov-steps { position: relative; display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-top: 48px; padding-top: 31px; }
  section.intro-overview .ov-steps::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 4px; background: #ced7e1; }
  section.intro-overview .ov-step { position: relative; padding: 0 8px; }
  section.intro-overview .ov-step h3 { margin: 0 0 10px; font-size: 20px; line-height: 1.3; color: #245f8b; }
  section.intro-overview .ov-step h3 strong { position: absolute; left: 39%; top: -50px; width: 42px; height: 42px; border-radius: 50%; background: #2877aa; color: #fff; font-size: 22px; line-height: 42px; text-align: center; }
  section.intro-overview .ov-step:nth-child(3) h3 strong { background: #745db3; }
  section.intro-overview .ov-step:nth-child(4) h3 strong { background: #3b9460; }
  section.intro-overview .ov-step p { margin: 0 0 6px; font-size: 17px; line-height: 1.45; }
  section.intro-overview .ov-step p:last-child { font-size: 14px; color: #52606d; }
  section.intro-overview blockquote { margin: 31px 0 0; padding: 10px 18px; border: 0; border-radius: 11px; background: #f4f6f9; }
  section.intro-overview blockquote p { margin: 0; color: #46566a; font-size: 14px; line-height: 1.5; }
  section.astra-matched { font-size: 20px; }
  section.astra-matched h1 { font-size: 34px; margin-bottom: 12px; }
  section.astra-matched p { margin: 10px 0; }
  section.astra-matched table { font-size: 18px; margin: 10px 0; }
  section.astra-matched th, section.astra-matched td { padding: 4px 10px; }
  section.astra-settings { font-size: 22px; }
  section.astra-settings table { font-size: 21px; margin: 14px 0; }
  section.astra-settings th, section.astra-settings td { padding: 7px 11px; }
  section.astra-settings blockquote p { font-size: 22px; line-height: 1.5; }
  section.benchmark-data { font-size: 22px; }
  section.benchmark-data table { font-size: 20px; margin: 14px 0; }
  section.benchmark-data th, section.benchmark-data td { padding: 7px 11px; }
  section.ar-code { font-size: 21px; line-height: 1.4; }
  section.ar-code h1 { font-size: 34px; margin-bottom: 22px; }
  section.ar-code .code-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }
  section.ar-code .code-columns > div { min-width: 0; }
  section.ar-code h2 { font-size: 24px; margin: 6px 0 14px; }
  section.ar-code p { margin: 12px 0; }
  section.ar-code pre { font-size: 17px; line-height: 1.4; padding: 13px 15px; margin: 0 0 14px; }
  section.ar-code pre code { white-space: pre-wrap; overflow-wrap: anywhere; }
  section.ar-code table { font-size: 20px; margin: 14px 0; }
  section.ar-code th, section.ar-code td { padding: 6px 9px; }
  section.ar-code li { margin: 9px 0; }
  section.ar-code .code-source { font-size: 14px; color: #52606d; margin-top: 12px; }
  section.temperature-example .katex-display { margin: 10px 0; }
  section.ar-code .temperature-panels { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin: 18px 0; }
  section.ar-code .temperature-panel { padding: 14px 20px 10px; border: 1px solid #d8e1e9; border-radius: 8px; background: #f7f9fc; }
  section.ar-code .temperature-panel h2 { font-size: 23px; margin: 0 0 5px; }
  section.ar-code .temperature-panel p { margin: 5px 0; font-size: 18px; }
  section.ar-code .prob-bars { height: 115px; display: flex; align-items: end; justify-content: space-around; border-bottom: 2px solid #64748b; margin-top: 28px; }
  section.ar-code .prob-bar { position: relative; width: 54px; background: #745db3; }
  section.ar-code .prob-bar span { position: absolute; top: -25px; width: 80px; left: -13px; text-align: center; font-size: 18px; }
  section.ar-code .prob-labels { display: flex; justify-content: space-around; font-size: 18px; margin-top: 4px; }
  /* 損失とattentionは保存済みの結果図をファイル参照で使用する。 */
  section.scientific { font-size: 23px; }
  section.scientific h1 { margin: 0 0 14px; font-size: 36px; }
  section.scientific p { margin: 12px 0; line-height: 1.4; }
  section.scientific .result-figure { display: block; width: 1100px; height: 380px; margin: 14px auto; }
  section.scientific p:last-of-type { font-size: 19px; color: #52606d; }
  section.attention-result h1 { font-size: 35px; }
  /* 元資料25ページの拡大図の配置 */
  section.chart { padding: 50px 62px 46px; font-size: 27px; line-height: 1.55; }
  section.chart h1 { margin: 0 0 12px; font-size: 38px; line-height: 1.3; }
  section.chart p { margin: 12px 0; font-size: 25px; }
  section.chart svg.figure { display: block; margin: 12px auto; max-width: 100%; }
  section.chart header { font-size: 20px; top: 16px; left: 62px; color: #64748b; }
  /* 保存済みの図ファイルを参照する。セルはMarkdownに記述しない。 */
  section.scientific img { display: block; margin: 14px auto; max-width: 100%; object-fit: contain; }
  section.chart .attention-guide-labels { display: grid; grid-template-columns: 160px 550px 230px; width: 940px; margin: 12px auto 8px; font-size: 22px; }
  section.chart .attention-guide-labels > div { display: flex; justify-content: space-between; }
  section.chart .attention-guide-grid { display: grid; grid-template-columns: 160px 550px 230px; align-items: center; width: 940px; height: 342px; margin: 0 auto; font-size: 23px; }
  section.chart .attention-guide-grid p { margin: 0; }
  section.chart .attention-guide-grid > div:last-child { padding-left: 35px; }
  section.chart .attention-guide-grid img { display: block; width: 550px; height: 342px; }
  section.chart .attention-guide-x { width: 550px; margin: 12px auto 24px; text-align: center; font-size: 24px; }
  /* 分岐図の文章・コードは本文のMarkdownで編集する。 */
  section.ast-training-pair { font-size: 25px; }
  section.ast-training-pair h1 { margin-bottom: 16px; }
  section.ast-training-pair .ast-source { position: relative; width: 570px; margin: 0 auto; padding: 12px 22px; background: #f0ecf8; border: 2px solid #8a79c8; border-radius: 8px; }
  section.ast-training-pair h3 { font-size: 25px; margin: 0 0 8px; color: #245f8b; }
  section.ast-training-pair .ast-source h3 { color: #685098; text-align: center; }
  section.ast-training-pair .ast-source pre { margin: 0; padding: 0; border: 0; background: transparent; font-size: 18px; line-height: 1.3; }
  section.ast-training-pair .ast-source::after { content: ""; position: absolute; bottom: -24px; left: 50%; height: 22px; border-left: 3px solid #697786; }
  section.ast-training-pair .ast-outputs { position: relative; display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin-top: 56px; }
  section.ast-training-pair .ast-outputs::before { content: ""; position: absolute; top: -34px; left: calc(25% - 10px); right: calc(25% - 10px); border-top: 3px solid #697786; }
  section.ast-training-pair .ast-output { position: relative; padding: 16px 22px; background: #edf5fc; border: 1px solid #9ebed7; border-radius: 8px; }
  section.ast-training-pair .ast-output::before { content: "↓"; position: absolute; top: -45px; left: calc(50% - 15px); color: #697786; font-size: 38px; line-height: 1.2; }
  section.ast-training-pair .ast-output:last-child { background: #eef7f1; border-color: #91b99e; }
  section.ast-training-pair .ast-output:last-child h3 { color: #327c50; }
  section.ast-training-pair .ast-output p { margin: 8px 0 0; font-size: 24px; line-height: 1.5; }
  section.ast-training-pair .ast-output pre { padding: 0; margin: 12px 0 0; background: transparent; border: 0; font-size: 21px; line-height: 1.55; }
  section.ast-training-pair > blockquote { margin: 22px 0 0; padding: 12px 18px; }
  section.ast-training-pair > blockquote p { font-size: 25px; }
  /* 合成データ生成・検証の説明を分岐図へ統合する。 */
  section.ast-merged h1 { margin-bottom: 14px; }
  section.ast-merged .ast-source { width: 610px; padding: 10px 20px; }
  section.ast-merged .ast-source h3 { font-size: 23px; margin-bottom: 6px; }
  section.ast-merged .ast-source pre { font-size: 18px; line-height: 1.25; }
  section.ast-merged .ast-outputs { margin-top: 52px; }
  section.ast-merged .ast-outputs::before { top: -30px; }
  section.ast-merged .ast-output { padding: 14px 20px; }
  section.ast-merged .ast-output::before { top: -41px; }
  section.ast-merged .ast-output h3 { font-size: 24px; margin-bottom: 10px; }
  section.ast-merged .ast-output p { font-size: 22px; line-height: 1.4; margin: 8px 0; }
  section.ast-merged .ast-method { height: 148px; padding-top: 6px; }
  section.ast-merged .ast-method p { margin: 0; font-size: 22px; line-height: 1.55; }
  section.ast-merged .ast-output h4 { margin: 0 0 10px; font-size: 20px; font-weight: 600; color: #52606d; }
  section.ast-merged .ast-example { height: 144px; padding-top: 14px; border-top: 1px solid #b7cddd; }
  section.ast-merged .ast-output:last-child .ast-example { border-color: #b4d1bd; }
  section.ast-merged .ast-example p { margin: 0; font-size: 22px; line-height: 1.5; }
  section.ast-merged .ast-example pre { margin: 0; padding: 0; font-size: 21px; line-height: 1.5; }
  section.autoregressive { font-size: 25px; }
  section.autoregressive h1 { font-size: 36px; margin-bottom: 20px; }
  section.autoregressive table { table-layout: fixed; margin: 22px 0 14px; font-size: 26px; }
  section.autoregressive table th:first-child { width: 60%; }
  section.autoregressive th, section.autoregressive td { padding: 12px 18px; }
  section.autoregressive .ar-note p { margin: 12px 0 22px; font-size: 21px; color: #52606d; }
  section.autoregressive blockquote { margin: 22px 0 16px; }
  section.autoregressive > p { margin: 16px 0; }
  /* 自己回帰の図は本文の語句を枠と矢印で配置する。 */
  section.ar-diagram h1 { font-size: 36px; margin-bottom: 18px; }
  section.ar-diagram > p { margin: 14px 0 18px; font-size: 25px; }
  section.ar-diagram .ar-flow { width: 1100px; margin: 16px auto 20px; }
  section.ar-diagram .ar-labels { display: grid; grid-template-columns: 520px 380px 200px; margin-bottom: 8px; color: #52606d; font-size: 21px; }
  section.ar-diagram .ar-labels p { margin: 0; text-align: center; }
  section.ar-diagram .ar-labels p:first-child { text-align: left; }
  section.ar-diagram .ar-flow-row { display: grid; grid-template-columns: 520px 80px 220px 80px 200px; align-items: center; height: 104px; }
  section.ar-diagram .ar-flow-row p { margin: 0; }
  section.ar-diagram .ar-tokens p { display: flex; align-items: center; gap: 12px; }
  section.ar-diagram .ar-tokens code { display: inline-block; box-sizing: border-box; width: 80px; height: 70px; line-height: 66px; padding: 0; text-align: center; font-family: "Hiragino Sans", sans-serif; font-size: 28px; background: #eaf3fb; border: 2px solid #92b1c8; border-radius: 6px; }
  section.ar-diagram .ar-arrow p { text-align: center; color: #697786; font-size: 38px; }
  section.ar-diagram .ar-model { box-sizing: border-box; height: 84px; display: flex; justify-content: center; align-items: center; border: 2px solid #8a79c8; border-radius: 8px; background: #f0ecf8; }
  section.ar-diagram .ar-model strong { color: #685098; font-size: 28px; }
  section.ar-diagram .ar-output { box-sizing: border-box; width: 120px; height: 80px; margin: 0 auto; display: flex; align-items: center; justify-content: center; border: 2px solid #cf7d31; border-radius: 6px; background: #fff1df; }
  section.ar-diagram .ar-output strong { color: #a75a15; font-size: 30px; }
  section.ar-diagram .ar-appended code:last-child { background: #fff1df; color: #a75a15; border-color: #cf7d31; }
  section.ar-diagram .ar-next { background: #edf7ef; border-color: #78a785; }
  section.ar-diagram .ar-next strong { color: #327c50; }
  section.ar-diagram .ar-feedback { position: relative; height: 76px; color: #a75a15; }
  section.ar-diagram .ar-feedback::before { content: ""; position: absolute; left: 408px; right: 100px; top: -12px; height: 52px; border-right: 3px solid #cf7d31; border-bottom: 3px solid #cf7d31; }
  section.ar-diagram .ar-feedback::after { content: "↓"; position: absolute; left: 388px; top: 21px; width: 40px; text-align: center; font-size: 36px; line-height: 1.5; color: #cf7d31; }
  section.ar-diagram .ar-feedback p { position: absolute; left: 442px; top: 3px; margin: 0; font-size: 22px; background: #fff; }
  section.ar-diagram > blockquote { margin: 22px 0 16px; padding: 14px 18px; }
  section.ar-diagram > blockquote p { font-size: 24px; }
  section.ar-diagram .ar-note p { margin: 16px 0 0; font-size: 19px; }

---
<!-- _class: cover -->

<!-- _paginate: false -->

# Boku-nano

## 限られた日本語指示から<br>Python関数を生成する小型言語モデル

<img class="cover-avatar" src="figures/bokunano_circle.png" alt="Boku-nanoのキャラクター">

<!--
小さなモデルをゼロから学習し、動作と表現への強さを確かめる

**基本比較は1 epoch学習。1Mの損失には3 epoch学習の結果も掲載。**


1 epochは、訓練データ全体を1回使う学習です。先行研究のモデルの学習回数を主張するものではありません。
根拠：../results/trained_model_inventory.md
-->

---
<!-- _class: intro-overview -->
<!-- _header: "" -->

# Boku-nano：限られた日本語指示からPython関数を生成するSLM

24種類の整数リスト操作を扱う、小型言語モデルをフルスクラッチ学習

##

<div class="ov-flow">
<div class="ov-card">

### ① 制限された日本語指示文

整数リストxs から
偶数だけを残し、 各要素に k を加える  
solve 関数を書いて

決められた操作・文型の範囲

</div>
<div class="ov-card">

### ② Boku-nano

1M, 5M, 15M パラメータ

Decoder Transformerによる
next token prediction 

日本語指示から、python関数を生成

</div>
<div class="ov-card">

### ③ Python の関数

`def solve(xs, k):`

`return [x + k for x in xs`  
`if x % 2 == 0]`

参照インタプリタによる実行・検証
</div>
</div>

## 作り方と確かめ方

<div class="ov-steps">
<div class="ov-step">

### **1** 意味を定義

24操作を最大3つ

順序も含めて組み合わせる

</div>
<div class="ov-step">

### **2** 訓練データ合成

日本語指示文と正解コード

訓練データ 192,900件

</div>
<div class="ov-step">

### **3** フルスクラッチ学習

トークナイザとモデルを
ランダム初期値から学習

ついて

</div>
<div class="ov-step">

### **4** テスト検証・<br>ベンチマークによる評価

生成コードの動作を確認

84,180 / 84,550問 合格

</div>
</div>

<!-- > 評価結果は「24操作・最大3操作」という限定された範囲でのものです。Webデモの自由な日本語入力は、別モデルで決められた文型に整えてから -nano に渡します。 -->

<!--
日本語の指示からPython関数を作る流れと、合成データ生成・学習・実行評価の流れを説明する。
このページの本文はboku1_nano_overview_intro_marp.mdからコピーした。
根拠：../results/model_reports/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch.md
-->

---
<!-- _class: key-goal -->
<!-- _header: "1. 課題と狙い" -->

# 課題と狙い

抽出や順序の変更など、**対象を24種類の操作に限定**する

| 範囲を絞る | 目指すモデル |
| :--- | :--- |
| あらかじめ定めた整数リストの操作 | 学生一人でもフルスクラッチで作れる |
| 操作を組み合わせて処理を表す | **小規模言語モデル（SLM）** |

## 別の用途への応用

関数の組み合わせで表せる処理なら、  
同じ考え方を **NPCの挙動などにも応用できる可能性**がある

<!--
目安：60秒

今回の対象は、抽出・変換・順序変更・切り出しの24操作です。あらゆるコード生成を扱うのではなく、対象の処理をあらかじめ定めることで、学生一人でトークナイザーとTransformerをフルスクラッチで作れる規模を目指しました。既存のモデル重みは使わず学習しています。
関数の組み合わせで表現できる処理なら、同じ考え方をNPCの挙動など別の用途へ応用できる可能性があります。これは今後の構想であり、今回実装・評価した成果ではありません。

根拠：
- [atomic_semantic_asts.md](../specifications/atomic_semantic_asts.md)
- [trained_model_inventory.md](../results/trained_model_inventory.md)
-->

---
<!-- _class: default -->
<!-- _header: "2. 学習を成立させるための工夫" -->

# 意味ASTの具体例

日本語：**偶数だけを残して、各要素にkを加える**

```json
{
  "sequence": [
    {"filter": ["even"]},
    {"map": ["add_k"]}
  ]
}
```

偶数の抽出 → kを加える、という処理の順序を保存

<!--
目安：40秒

実際の仕様からsemantic_astの部分を抜き出しています。抽出がfilter、各要素への変換がmapです。ASTは合成データを作るために使用し、推論時には日本語だけをモデルへ渡します。

根拠：
- [atomic_semantic_asts.md](../specifications/atomic_semantic_asts.md)
-->

---
<!-- _class: ast-training-pair ast-merged -->
<!-- _header: "2. 学習を成立させるための工夫" -->

# 意味ASTから訓練データを自動生成・検証する

<div class="ast-source">

### 共通の処理の定義：意味AST

```json
{"sequence": [
  {"filter": ["even"]}, {"map": ["add_k"]}
]}
```

</div>

<div class="ast-outputs">
<div class="ast-output">

### 日本語の指示文

<div class="ast-method">

#### 生成の手順

**Qwenで各操作の日本語表現を生成。**  
ASTの順に結合し、テンプレートの  
`{operations}`をルールベースで埋める。

</div>
<div class="ast-example">

#### 生成例

整数リストxsと整数kを受け取り、  
偶数だけを残し、各要素にkを加える  
solve関数を書いてください。

</div>
</div>
<div class="ast-output">

### 検証済みのPythonコード

<div class="ast-method">

#### 生成の手順

**ASTの操作をPythonコードへ変換。**  
構文を確認し、実行結果を  
参照インタプリタの期待値と照合する。

</div>
<div class="ast-example">

#### 生成例

```python
def solve(xs, k):
    return [x + k for x in xs
            if x % 2 == 0]
```

</div>
</div>
</div>

<!--
旧5ページの分岐図に、旧6ページの合成データ生成・検証の説明を統合。
意味ASTが共通の生成元であり、そこから日本語の指示文と正解のPythonコードの両方を作る。日本語をモデルでコードに翻訳して合成データを作るという図ではない。
説明用に同じ処理の例を示し、Pythonの型注釈は省略した。filter(even)を先に適用し、その結果にmap(add_k)を適用する。
日本語側では、Qwenで各単純操作の終止形・接続形の候補を生成し、検査・承認した表現を使う。意味ASTの操作順に表現を結合し、固定した外側文の{operations}へ挿入する。外側テンプレートへの挿入はルールベースで行う。
根拠：../policies/rule_generated_instruction_policy.md
生成したコードはPythonとして解析し、実行結果を独立に実装した参照インタプリタの期待値と比較する。合成データのコードは境界値9件とランダム32件の計41入力で検証。有限個の入力での検証であり、全入力に対する正しさの証明ではない。
意味ASTは合成データの生成・検証用であり、学習と推論の入力へASTそのものを加えるわけではない。
対象を24操作に限定し、合成データを自動生成・検証することで、小規模モデルの学習を目指す。実験のGPUはRTX 5090であり、計算資源が不要という意味ではない。
根拠：../specifications/atomic_semantic_asts.md
根拠：../results/final_train_dataset_results.md
根拠：../results/multi_operation_python_code_generation_results.md
根拠：../specifications/reference_interpreter.md
-->

---
<!-- _class: default -->

# 扱う範囲は24種類の操作

| 種類 | 操作数 | 例 |
| :--- | ---: | :--- |
| 条件に合う数を残す | 10 | 偶数、奇数、正の値、kより大きい値 |
| 一つずつ値を変える | 8 | kを加える、2倍、絶対値、二乗 |
| 順序を変える | 3 | 昇順、降順、現在の順序の反転 |
| 一部を取り出す | 3 | 先頭k個、末尾k個、1個おき |

**最大3操作を組み合わせる、限定されたコード生成課題。**

<!--
汎用のプログラミング全般を扱う実験ではありません。
根拠：../specifications/atomic_semantic_asts.md
-->

---
<!-- _class: diagram -->



<!--
説明用の例です。意味定義は操作の順序を含みます。
根拠：../specifications/atomic_semantic_asts.md
-->



<!-- _class: default -->



<!--
ASTは抽象構文木の略です。本研究では操作の種類と順序を構造化した意味仕様を指します。初学者向けに日本語で示しています。
根拠：../specifications/atomic_semantic_asts.md
-->



<!-- _class: diagram -->

# 同じ意味から、日本語とコードを作る

| 段階 | 作るもの | 例 |
| :--- | :--- | :--- |
| ① 意味を決める | 操作と順序の記録 | 偶数を残す。その後、kを加える |
| ② 指示を作る | 日本語の説明 | 偶数だけを残して、各要素にkを加える |
| ③ 正解を作る | Pythonコード | 指示どおりに処理するsolve関数 |
| ④ 動作を確認する | 入力と出力の比較 | 参照実装と結果が一致するか |

**指示と正解を、一つの意味に対応付ける。**

<!--
意味ASTは合成データの生成と検証に使います。推論では意味ASTを与えず、日本語の指示をモデルに渡します。
根拠：../results/final_train_dataset_results.md、../specifications/reference_interpreter.md
-->

---
<!-- _class: default -->

# 操作の組み合わせは12,720種類

同じ操作を繰り返さず、順序を区別して数える。

| 操作の数 | 数え方 | 意味の種類 |
| :--- | :--- | ---: |
| 1操作 | 24 | 24 |
| 2操作 | 24 × 23 | 552 |
| 3操作 | 24 × 23 × 22 | 12,144 |
| 合計 | 24 ＋ 552 ＋ 12,144 | **12,720** |

同じ操作の繰り返しは、別のテストで確かめる。

<!--
12,720は指示文やコードの件数ではなく、反復のない意味仕様の総数です。
根拠：../policies/ast_split_policy.md
-->

---
<!-- _class: default -->

# 一つの意味に、複数の日本語を用意する

| 共通の意味 | 指示の言い回し |
| :--- | :--- |
| 偶数を残す | 偶数だけを残す |
| 偶数を残す | 偶数の要素を取り出す |
| 偶数を残す | 偶数の値を抽出する |

ルールと補助モデルを使い、意味を確認して合成データに採用する。

**訓練・検証・テストに意味を分けてから、表現を増やす。**

<!--
表は仕組みの説明例です。補助モデルはQwen3-4B-AWQ。Boku Nanoの重みを流用したものではありません。
根拠：../results/rule_generated_instruction_results.md、../results/replacement_resolved_train_instruction_results.md、../policies/ast_split_policy.md
-->

---
<!-- _class: default -->

# コードの書き方にも変化を付ける

どちらも「偶数だけを残す」正しい書き方。

```python
result = [x for x in xs if x % 2 == 0]
```

```python
result = []
for x in xs:
    if x % 2 == 0:
        result.append(x)
```

**文字列が同じかではなく、動作が同じかを重視する。**

<!--
説明用のコードです。内包表記、ループなど複数の構造を生成します。
根拠：../results/multi_operation_python_code_generation_results.md
-->

---
<!-- _class: default -->



<!--
41入力の一致は、あらゆる入力での正しさの証明ではありません。学習用の検査入力はモデル評価用と分離しています。
根拠：../results/multi_operation_python_code_generation_results.md、../specifications/reference_interpreter.md
-->



<!-- _class: default -->

# 学習に使った合成データは192,900件

1件は「日本語の指示」と「正解コード」の組。

| 処理の長さ | 訓練データの件数 |
| :--- | ---: |
| 1操作 | 460 |
| 2操作 | 8,680 |
| 3操作 | 183,760 |
| 合計 | **192,900** |

**約95%が3操作の合成データ。** 単独操作の合成データは少ない。

<!--
3操作の割合は95.2618%。データの偏りは文型依存の考察につながります。
根拠：../results/final_train_dataset_results.md
-->

---
<!-- _class: compact -->

# 三つの大きさを、1 epochで比較する

**パラメータ**は、学習で調整するモデル内部の数値。

| 呼び名 | パラメータ数 | 今回の学習 |
| :--- | ---: | :--- |
| 1M | 約100万 | 合成データ全体を1回使う |
| 5M | 約500万 | 合成データ全体を1回使う |
| 15M | 約1,500万 | 合成データ全体を1回使う |

<!-- 合成データ全体を1回使う学習を、**1 epoch（1エポック）**と呼ぶ。 -->

既存の学習済み重みを使わず、Transformerをゼロから学習する。

<!--
正確には1,016,704、5,065,472、15,735,168パラメータ。共通の分割設定で学習した3モデルを本編に採用。Transformerは文章内の情報を参照しながら次の単位を予測するモデル。すべてDecoder-only、最大系列長256。
根拠：../results/trained_model_inventory.md
-->

---
<!-- _class: autoregressive ar-diagram -->
<!-- _header: "4. モデルと評価方法" -->

# 自己回帰：出力を次の入力に加えて繰り返す

GPTなどの言語モデルは、**直前までの言葉から次を予測**して文章を作る。

<div class="ar-flow">
<div class="ar-labels">

入力：ここまでの文章

予測するモデル

出力：次の言葉

</div>
<div class="ar-flow-row">
<div class="ar-tokens">

`私` `は` `猫` `が`

</div>
<div class="ar-arrow">

→

</div>
<div class="ar-model">

**言語モデル**

</div>
<div class="ar-arrow">

→

</div>
<div class="ar-output">

**好き**

</div>
</div>
<div class="ar-feedback">

出力した「好き」を、次の入力の末尾へ

</div>
<div class="ar-flow-row">
<div class="ar-tokens ar-appended">

`私` `は` `猫` `が` `好き`

</div>
<div class="ar-arrow">

→

</div>
<div class="ar-model">

**同じモデル**

</div>
<div class="ar-arrow">

→

</div>
<div class="ar-output ar-next">

**です**

</div>
</div>
</div>

> **学習では**、文章の途中までを見せ、実際の次の言葉を当てるように学ぶ。

<div class="ar-note">

説明用に言葉で区切った例。実際はトークン単位で予測し、生成を繰り返す。

</div>

<!--
図の例は「私は猫が好きです」。上段で「好き」を生成し、その出力を次の入力の末尾へ加える。下段は同じモデルをもう一度使い、「です」を生成する。二つの別モデルを直列に学習するという意味ではない。
各語を囲む枠、モデル、矢印、出力を入力へ戻す経路を使い、自己回帰生成を説明する。実際のモデルの実測出力やトークン分割結果ではない。
学習では正解文章の直前までの系列から実際に続くトークンを予測し、正解トークンの確率を高めるように重みを更新する。causal maskにより未来の正解は見えない。学習時は各位置の予測を一括して計算できる。
図の生成時には自分で出したトークンを次の入力へ加える。候補は確率分布として予測され、次の言葉が一意に決まるわけではない。
Boku1-nanoはDecoder-onlyであり、この記事のEncoder-Decoder構成のCross-Attentionは本モデルに含まれない。
図示の参考： https://disassemble-channel.com/transformer-decoder/ （Decoderの役割・自己回帰生成）
参考記事の画像自体は使用せず、説明図をMarkdownの本文とCSSの配置で作成。
実装の根拠：../../scripts/model/boku_nano.py（causal attention、shifted labels、cross entropy）
実装の根拠：../../scripts/model/train_boku_nano.py（collate_training_batch）
-->

---
<!-- _class: ar-code -->
<!-- _header: "4. モデルと評価方法" -->

# ① ロジットは、確率に変換する前の「候補の点数」

<div class="code-columns">
<div>

```python
# 語彙の各トークンに点数を付ける層を定義
self.lm_head = nn.Linear(
    config.d_model, config.vocab_size,
    bias=False)

# …（初期化の続き・forwardの前半を省略）
# 入力から得た表現を整える
hidden_states = self.final_norm(hidden_states)

# 表現を、全候補の点数（logits）へ変換
logits = self.lm_head(hidden_states).float()

# 推論時は、この点数を返す
if labels is None:
    return CausalLMOutput(
        logits=logits, loss=None)
```

<div class="code-source">boku_nano.py：330、395–400行から抜粋。<br>省略を明示。コメントを追加し、改行を調整。</div>

</div>
<div>

## 「次に続きそうか」を比べる点数

今の入力に続く候補ごとに、モデルがロジット $z_i$ を計算する。**高い候補ほど選ばれやすい。**

$$z_i = \mathbf{w}_i^\top \mathbf{h}$$

$\mathbf{h}$：ここまでの入力から作った表現<br>
$\mathbf{w}_i$：候補 $i$ に対応する学習済みの重み

## ロジットは確率ではない

ロジットは負の値も取れ、合計も1とは限らない。例えば `[2, 1, 0]` は、A・B・Cの点数。

**softmaxで確率に変換してから、候補を選ぶ。**

</div>
</div>

<!--
式は最後の入力位置のhidden_statesをhとし、bias=Falseのlm_headを表す。w_iは出力重み行列の候補iに対応する行。ロジットは正答率や校正済みの信頼度そのものではない。
出典：../../scripts/model/boku_nano.py 330、395–400行。コードは非連続箇所の抜粋。日本語コメントと改行・字下げを調整。
-->

---
<!-- _class: ar-code -->

# ② softmaxは、点数を「合計1の確率」に変換する

<div class="code-columns">
<div>

```python
# 入力の最後の位置にある、全候補の点数
# このページでは temperature=1.0 とする
logits = (
    model(input_ids).logits[:, -1, :]
    / temperature
)

# 候補を点数の高い順に並べる
sorted_logits, sorted_indices = torch.sort(
    logits, descending=True, dim=-1
)

# 点数を、合計1の確率分布に変換する
sorted_probabilities = torch.softmax(
    sorted_logits, dim=-1
)
```

<div class="code-source">evaluate_boku_nano_comparison.py：209–211行。<br>コメントを追加し、改行を調整。</div>

</div>
<div>

## 指数に変換し、全候補の合計で割る

$$p_i = \frac{e^{z_i}}{\sum_{j=1}^{V} e^{z_j}}$$

$z_i$：候補 $i$ の点数、$p_i$：その選択確率<br>
$V$：候補数、$\sum$：全候補の足し算、$e\approx2.718$

| 候補 | 点数 $z_i$ | $e^{z_i}$ | 確率 $p_i$ |
| :--- | ---: | ---: | ---: |
| A | 2 | 7.389 | 66.5% |
| B | 1 | 2.718 | 24.5% |
| C | 0 | 1.000 | 9.0% |

$$p_A=\frac{7.389}{7.389+2.718+1}\approx0.665$$

**点数0でも確率0ではない。** $e^0=1$ だから。

</div>
</div>

<!--
3候補の数値は説明用。実際は全語彙に対する分布。候補をソートしても各トークンの確率は変わらない。
temperature=1.0なので左の除算は点数を変えない。モデルの直接出力はロジット。
出典：../../scripts/model/evaluate_boku_nano_comparison.py sample_generate_equal_length、209–211行。
softmaxは最後の語彙次元dim=-1に適用する。表はsoftmaxで計算した確率。
-->

---
<!-- _class: ar-code -->

# ③ 選んだトークンを入力に加え、予測を繰り返す

<div class="code-columns">
<div>

```python
# 日本語指示を含む入力ID列をコピーする
current = prompt_ids.copy()
generated: list[int] = []

# 勾配を計算せず、次のトークンを順に生成
with torch.inference_mode():
    for _ in range(min(
        max_new_tokens,
        model.config.context_length - len(current)
    )):
        values = torch.tensor(
            [current], dtype=torch.long)
        # 最も確率が高いトークンを選ぶ
        token_id = int(torch.argmax(
            model(values).logits[0, -1]).item())
        # 終了トークンなら生成を止める
        if token_id == eos_token_id:
            break
        # 選んだIDを出力と次回の入力へ追加
        generated.append(token_id)
        current.append(token_id)
```

<div class="code-source">Python推論から抜粋。コメントを追加し、改行を調整。<br>export_boku_nano_onnx.py：232–241行</div>

</div>
<div>

`logits[0, -1]` は先頭の入力系列の **最後の位置** にある、全候補の点数。

## 自己回帰の中心は `current.append`

1. **ここまでの入力**から次の候補を予測する。
2. 候補を1つ選び、**入力末尾に追加**する。
3. 伸びた入力を使って、**同じモデル**でもう一度予測する。

## 各ステップで、最も確率が高いトークンを選ぶ

選んだトークンを入力に加え、次の予測でも **最も確率が高いトークン** を選ぶ。終了トークンか長さの上限まで繰り返す。

softmaxで確率に変換しても、候補の順位は変わらない。

そのため、コードでは **ロジットが最大の位置を求める `argmax`** で、同じトークンを選べる。

</div>
</div>

<!--
出典：../../scripts/model/export_boku_nano_onnx.py generate_with_pytorch、232–241行。関数宣言と末尾のreturnを省略し、日本語コメント・空行を追加。
ONNXとの一致確認に使う実際のPyTorch推論ループ。通常のバッチ評価にも同じargmax方式がある：../../scripts/model/evaluate_boku_nano.py 488–490行。
currentは特殊トークンを含むプロンプトIDと生成済みID。毎回全入力を与える実装。KVキャッシュの説明ではない。
-->

---
<!-- _class: ar-code -->

# ④ 温度は、softmaxに入れる点数の差を変える

<div class="code-columns">
<div>

```python
# 全候補のロジットを温度Tで割る
logits = (
    model(input_ids).logits[:, -1, :]
    / temperature
)

# 候補のIDを保持して点数順に並べる
sorted_logits, sorted_indices = torch.sort(
    logits, descending=True, dim=-1
)

# 調整後の点数をsoftmaxで確率にする
sorted_probabilities = torch.softmax(
    sorted_logits, dim=-1
)
```

<div class="code-source">evaluate_boku_nano_comparison.py：209–211行。<br>確率に従って抽選する場合の実装から抜粋。<br>今回のBoku評価では、最も確率が高いトークンを選ぶ。</div>

</div>
<div>

## 抽選する場合の分布を温度で調整する

$$p_i(T)=\frac{e^{z_i/T}}{\sum_{j=1}^{V}e^{z_j/T}},\quad T>0$$

$T$：温度。$T=1$ なら元のsoftmaxと同じ。

AとBの点数が2と1なら、差は1。割った後の差は **$1/T$** になる。

| 温度 $T$ | Aの点数 $2/T$ | Bの点数 $1/T$ | 差 |
| ---: | ---: | ---: | ---: |
| 0.5 | 4 | 2 | 2 |
| 1 | 2 | 1 | 1 |
| 2 | 1 | 0.5 | 0.5 |

**小さい温度 → 差が広がる → 高い点数に集中**

**大きい温度 → 差が縮まる → 他の候補も選ばれる**

</div>
</div>

<!--
出典：../../scripts/model/evaluate_boku_nano_comparison.py 209–211行。正のtemperatureの検査は105–106行。
温度を変更しても学習済み重みは変わらない。softmaxに入力する相対的な点数差を調整する。
-->

---
<!-- _class: ar-code temperature-example -->

# ⑤ 同じロジットでも、温度で「選ばれる割合」が変わる

元の点数はずっと **A=2、B=1、C=0**。温度だけを変えた確率分布を比べる。

<div class="temperature-panels">
<div class="temperature-panel">
<h2>T = 0.5：Aに集中</h2>
<p>割った後の点数：[4, 2, 0]</p>
<div class="prob-bars">
<div class="prob-bar" style="height:86.7%"><span>86.7%</span></div>
<div class="prob-bar" style="height:11.7%"><span>11.7%</span></div>
<div class="prob-bar" style="height:1.6%"><span>1.6%</span></div>
</div>
<div class="prob-labels"><span>A</span><span>B</span><span>C</span></div>
</div>
<div class="temperature-panel">
<h2>T = 1：基準</h2>
<p>割った後の点数：[2, 1, 0]</p>
<div class="prob-bars">
<div class="prob-bar" style="height:66.5%"><span>66.5%</span></div>
<div class="prob-bar" style="height:24.5%"><span>24.5%</span></div>
<div class="prob-bar" style="height:9.0%"><span>9.0%</span></div>
</div>
<div class="prob-labels"><span>A</span><span>B</span><span>C</span></div>
</div>
<div class="temperature-panel">
<h2>T = 2：B・Cも選びやすい</h2>
<p>割った後の点数：[1, 0.5, 0]</p>
<div class="prob-bars">
<div class="prob-bar" style="height:50.6%"><span>50.6%</span></div>
<div class="prob-bar" style="height:30.7%"><span>30.7%</span></div>
<div class="prob-bar" style="height:18.6%"><span>18.6%</span></div>
</div>
<div class="prob-labels"><span>A</span><span>B</span><span>C</span></div>
</div>
</div>

## AはBの何倍選ばれやすいか（棒の高さは共通尺度：0〜100%）

$$\frac{p_A(T)}{p_B(T)}=e^{(z_A-z_B)/T}=e^{1/T}$$

$T=0.5$ なら約 **7.39倍**、$T=1$ なら約 **2.72倍**、$T=2$ なら約 **1.65倍**。

正の温度では順位は同じ。**抽選のばらつき**が変わる。温度を上げても正解率が上がるとは限らない。

$T \to 0^+$ では最大候補に集中（最大が1つの場合）。$T=0$ の除算はせず、最大の候補を直接選ぶ。

<!--
参考：ユーザー提供の書籍画像 IMG_0947.jpg（p.124）、IMG_0948.jpg（p.125）。書名・著者は画像から未確認。説明の構成を参考にし、図は独自の3候補の数値からMarkdown/CSSで作成。
3候補の説明用の計算例。丸めにより合計100%にならない場合がある。
確率比ではsoftmaxの共通分母が相殺される。図はtemperatureだけを変えたsoftmaxの分布。
Pythonのsampling関数はT>0のみを受け付ける。T=0を渡して分岐する実装ではなく、greedyは別の実装。
出典：../../scripts/model/evaluate_boku_nano_comparison.py 105–106、209–211行、../../scripts/model/export_boku_nano_onnx.py 237行。
-->

---
<!-- _class: compact -->

# 五つのテストで、生成コードを実行する

| テスト | 確かめること | 指示の件数 |
| :--- | :--- | ---: |
| 通常 | 未学習の操作の並びを扱えるか | 24,040 |
| 組合せ | 訓練から隔離した操作対を組めるか | 13,400 |
| 日本語の言い換え | 未学習の30表現を理解できるか | 30 |
| 同じ操作の反復 | 同じ操作を2回・3回実行できるか | 23,040 |
| 境界値 | 空リストなどでも正しく動くか | 24,040 |

1指示につきコードを1候補生成し、全検査を通ったら合格。

通常と境界値では同じ指示を使い、検査する入力を変える。

<!--
合計84,550件は評価集合の合計で、重複のない指示数ではありません。greedy最大160 token。構文、安全AST、signature、入力非変更、返値型、制限時間も検査。通常・組合せ・言い換え・反復は各64入力。境界値は共通30入力と操作固有入力。
根拠：../policies/boku_nano_model_evaluation_policy.md
-->

---
<!-- _class: scientific -->
<!-- _header: "5. 学習結果と課題" -->

# 1M：3 epochまでの損失の推移

3 epochの学習。訓練損失は20 stepごと、検証損失は各epoch終了時の実測値。

![w:1100 h:380](figure/loss_1m_3epoch.png)

**val loss：1 epoch 0.8737 ／ 2 epoch 0.4691 ／ 3 epoch 0.4364**

20 stepごとのvalidationは未記録。図は保存済みの3点を表示。

<!--
3epoch設定の1回の訓練ログを使用。train loss 57点、validation loss 3点。最終stepは1131、epoch境界は377・754・1131。validationは24,040レコードのコード部分を評価。
1epoch専用runとは学習率スケジュールが異なるため、1epoch専用runの終了値1.3781と接続しない。
使用図：figure/loss_1m_3epoch.svg
根拠：../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/training_metrics.jsonl
-->

---
<!-- _class: scientific -->
<!-- _header: "5. 学習結果と課題" -->

# 5M：損失の推移

1 epochの学習。訓練損失と、検証データで測った損失を示す。

![w:1100 h:380](figure/loss_5m.png)

**学習終了時の val loss：0.4855**

val lossは終了時の1点。途中の検証値は保存されていない。

<!--
保存された19点のtrain lossと、1点のvalidation lossをすべて使用。曲線はtrain lossだけであり、val lossの推移を補間していない。縦軸は保存済みの各モデルの図の対数目盛をそのまま使用する。モデルごとに範囲は異なる。最終stepは377。validationは24,040レコードのコード部分を評価。
使用図：../results/figures/training_loss_20step/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch.svg
根拠：../../data/models/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/training_metrics.jsonl
-->

---
<!-- _class: scientific -->
<!-- _header: "5. 学習結果と課題" -->

# 15M：損失の推移

1 epochの学習。訓練損失と、検証データで測った損失を示す。

![w:1100 h:380](figure/loss_15m.png)

**学習終了時の val loss：0.4106**

val lossは終了時の1点。途中の検証値は保存されていない。

<!--
保存された19点のtrain lossと、1点のvalidation lossをすべて使用。曲線はtrain lossだけであり、val lossの推移を補間していない。縦軸は保存済みの各モデルの図の対数目盛をそのまま使用する。モデルごとに範囲は異なる。最終stepは377。validationは24,040レコードのコード部分を評価。
使用図：../results/figures/training_loss_20step/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch.svg
根拠：../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/training_metrics.jsonl
-->

---
<!-- _class: compact -->

# 1 epochの結果：モデル規模による違い

五つのテストを合計した参考値。分母は84,550件。

| モデル | 合格数 | 合格率 |
| :--- | ---: | ---: |
| 1M | 1,467件 | 1.74% |
| 5M | 81,557件 | 96.46% |
| 15M | 84,180件 | 99.56% |

**今回の条件では、5Mと15Mは高い全体合格率を示した。**

ただし、件数の少ない言い換えテストは全体値に表れにくい。

<!--
本編は全てmin_frequency=5/max_token_length=24の設定。すべて1 epoch・単一seed。モデル間の比較で分割方法は共通。
根拠：../results/trained_model_inventory.md
-->

---
<!-- _class: compact -->

# 全体が高精度でも、言い換えには弱い

15Mモデル・1 epochのテスト別結果。

| テスト | 合格数 | 合格率 |
| :--- | ---: | ---: |
| 通常 | 24,003 / 24,040 | 99.85% |
| 組合せ | 13,188 / 13,400 | 98.42% |
| 日本語の言い換え | **15 / 30** | **50.00%** |
| 同じ操作の反復 | 22,971 / 23,040 | 99.70% |
| 境界値 | 24,003 / 24,040 | 99.85% |

**全体の99.56%だけでは、日本語表現への弱さが見えない。**

<!--
固定30表現の言い換えテストです。後の14操作の冒頭変更とは別の評価。
根拠：../results/model_reports/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch.md
-->

---
<!-- _class: sources -->

# 先行研究：日本語の書き方で正解率が変わる

Gan and Mori（2023）は、意味や指示が近い5種類のプロンプトを比較した。

**プロンプト**は、モデルに渡す指示文や質問文のこと。

| 日本語の課題 | モデル | 正解率の範囲 |
| :--- | :--- | :--- |
| 2文の意味関係を分類するJNLI | GPT-4 | **25.44〜49.21%** |

意味が近くても、書き方によって性能が大きく変わる場合がある。

出典：[Gan and Mori, PACLIC 2023, Table 3](https://aclanthology.org/2023.paclic-1.1/)

<!--
JNLIは含意・矛盾・中立の3分類。各課題1,000件のzero-shot評価。今回のコード生成と同じ実験ではありません。
Chengguang Gan and Tatsunori Mori. Sensitivity and Robustness of Large Language Models to Prompt Template in Japanese Text Classification Tasks. PACLIC 2023, pp. 1–11. https://aclanthology.org/2023.paclic-1.1/
-->

---
<!-- _class: sources -->

# 先行研究：言い換えで回答の傾向も変わる

Takayama et al.（2026）は、日本語を含む「はい／いいえ」の質問を評価した。

| 表現の変え方 | 日本語での観察 |
| :--- | :--- |
| 同意を求める「〜ですよね？」 | 道徳判断で「はい」が増える傾向 |
| 反対語への置き換え | 答えの反転を考慮しても、一貫性が低下 |

**同じ判断を求めても、表現によって答えが動く。**

モデルの評価には、複数の言い回しを含める必要がある。

出典：[Takayama et al., LREC 2026, Table 1](https://aclanthology.org/2026.lrec-1.225/)

<!--
日本語はJCommonsenseMoralityとWRIME。道徳判断の同意表現でYes割合は指示調整済みモデル群平均4.9ポイント、GPT-4o5.5ポイント増加。反対語では答えが反転することを考慮。一貫性と正解率は異なる指標です。
Junya Takayama, Masaya Ohagi, Tomoya Mizumoto, and Katsumasa Yoshikawa. Evaluating the Effect of Question Wording Variations on Answer Consistency in Large Language Models. LREC 2026, pp. 2874–2886. https://aclanthology.org/2026.lrec-1.225/
-->

---
<!-- _class: default -->

# 今回は、指示の冒頭だけを変えて比較する

| 条件 | モデルに渡す指示 |
| :--- | :--- |
| 変更前 | **整数リストxsから偶数だけを残すsolve関数を書いてください。** |
| 変更後 | **整数リストxsに対して、偶数だけを残すsolve関数を書いてください。** |

後半の操作の指示をそろえ、冒頭だけが異なる**14操作**を比較。

同じモデルを使い、追加学習せず、同じ入力でコードを検査する。

<!--
保存済み24操作から、kを使わず「整数リストxsから」で始まる14操作を抽出。残り10操作は「xsと整数kを受け取り、」も変更するため除外。「から」の変更には読点の追加も含みます。各指示33入力、greedy最大64 token。
根拠：../results/boku_nano_1epoch_attention_comparison.md、../results/boku_nano_1epoch_attention_comparison_legacy_taishite_prompt.md
-->

---
<!-- _class: result -->

# 5Mモデルでは、12件の合格が1件に減った

**5M・1 epoch。比較した14操作の合格数。**

| 指示の冒頭 | 合格数を表す図 | 合格数・合格率 |
| :--- | :--- | :--- |
| 整数リストxsから | ■■■■■■■■■■■■□□ | **12 / 14・85.7%** |
| 整数リストxsに対して、 | ■□□□□□□□□□□□□□ | **1 / 14・7.1%** |

■は合格1件、□は不合格1件。左から合格数を並べた図。

**冒頭を変えただけで、ほとんど正しく生成できなくなった。**

<!--
図は合格数・不合格数の内訳で、各操作の並びではありません。合格は固定33ケースの検査をすべて通ること。24操作全体の22→1を「から」だけの変更として扱わず、14操作に限定。
根拠：../results/attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/analysis.json とlegacy_taishite_prompt/analysis.json
-->

---
<!-- _class: default -->

# 失敗例：偶数を残す指示を別の処理にした

変更後の指示：**整数リストxsに対して、偶数だけを残すsolve関数を書いてください。**

| | 指示どおりの処理 | 変更後に生成した処理 |
| :--- | :--- | :--- |
| 操作 | 偶数だけを残す | 順序を反転し、k以上の値を残す |
| 検査入力 | `xs = [0]`、`k = 1` | 同じ入力 |
| 出力 | **`[0]`** | **`[]`** |

構文は正しかったが、**処理の意味が変わった。**

<!--
5Mモデルのatomic-000001の実際の生成コードと最初の不一致入力。変更前はvalue % 2 == 0で抽出し33ケース合格。変更後はlist(reversed(xs))の後にk <= xで抽出。評価器は全操作でsolve(xs, k)を要求するため、指示にkがなくても検査入力にはkがあります。
根拠：../results/attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/analysis.json とlegacy_taishite_prompt/analysis.json
-->

---
<!-- _class: default -->

# 表現への強さは、モデルによって違う

すべて1 epoch。冒頭だけを変えた14操作の合格数。

| モデル | 「xsから」 | 「xsに対して、」 |
| :--- | ---: | ---: |
| 5M | **12 / 14** | **1 / 14** |
| 15M | 12 / 14 | 12 / 14 |

**15Mでは合格数を保った。** すべてが同様に崩れるわけではない。

<!--
共通の分割設定。samplesをoperation_idで対応付け、指示が「整数リストxsから」で始まる14操作を集計。後半の文が同じと確認。合格数が同じでも生成コードの一致を主張しない。
根拠：../results/attention_1epoch/ 配下の5M・15Mのminfreq5_maxlen24_1epoch/analysis.jsonとlegacy_taishite_prompt/analysis.json
-->

---
<!-- _class: default -->

# 学習データの文型との結び付きが考えられる

訓練データで「整数リストxsに対して、」と始まる指示は84件。

| その文型で学習した処理 | 件数 |
| :--- | ---: |
| 1操作 | **0** |
| 2操作 | 1 |
| 3操作 | 83 |

この文型を、複数の操作と結び付けて覚えた可能性がある。

**原因の確定には、合成データを変えた追加比較が必要。**

<!--
解釈は仮説です。頻度や操作数の偏り以外に、モデル規模も関係し得ます。失敗だけで原因を断定しません。
根拠：../results/boku_nano_1epoch_attention_comparison.md「新旧文型の比較」
-->

---
<!-- _class: compact -->

# モデルが情報を読み取る仕組み

**アテンション**は、次のコードを作るときに、どこから情報を読むかを決める仕組み。

| 参照できる情報 | 内容 |
| :--- | :--- |
| 日本語の指示 | 「偶数」「残す」など、求める処理 |
| すでに生成したコード | 変数名、構文、処理の続き |
| 開始の印など | 入力の始まりや区切り |

参照割合だけでは、その情報が必要だったかは確定できない。

**情報の受け渡しを止めて、生成結果が変わるかを調べる。**

<!--
図の読み方を説明した後の5ページは、同一の絶対値・降順の指示について、1M・5M・15Mの全層・全ヘッドの生成中のattentionを表示する。Value ablationでは指示位置のKeyとattention weightを保ち、Valueだけを0にします。
根拠：../results/boku_nano_1epoch_attention_comparison.md
-->

---
<!-- _class: chart -->
<!-- _header: "6. アテンションの可視化" -->

# アテンションの図の読み方

<div class="attention-guide-labels"><span></span><div><span>入力の指示・区切り</span><span>生成済みコード</span></div><span></span></div>

<div class="attention-guide-grid">
<div>生成<br>ステップ<br>↓</div>

![w:550 h:342](figure/attention_15m_l8_h5.png)

<div>薄い：弱い<br><br>濃い：強い</div>
</div>

<div class="attention-guide-x">横：参照するトークン位置 →</div>

濃い位置ほど強く参照。15M・1エポックのL8・H5の例

<!--
目安：40秒

保存済みのattention_by_layer_head.svgをPNGへ出力し、第8層第5ヘッドの領域をそのまま切り出して拡大しています。図のセルを描き直していません。横は参照先、縦は生成ステップです。赤線は指示側と生成コード側の境界です。灰色はまだ存在しない位置です。指示は『各要素を絶対値にして降順に並べる』です。色は元の図の尺度を維持し、上位2％は濃い色で飽和します。

根拠：
- [detail_analysis.json](../results/attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/detail_analysis.json)
- [attention_by_layer_head.svg](../results/attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_by_layer_head.svg)
-->

---
<!-- _class: scientific attention-result -->
<!-- _header: "6. アテンションの可視化" -->

# 1M：attention の可視化

同じ指示：**各要素を絶対値にして、降順に並べる**

![w:1100 h:380](figure/attention_1m_l1_l3.png)

**生成結果：未定義の result を参照し、この指示では実行できなかった。**

色は各モデル内の相対的な強さ。モデル間で濃さを直接比較しない。

<!--
入力全文：xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。
3層×4head。全headを掲載。縦軸は13生成step。参照位置数・生成長はモデルによって異なる。
保存済みのattention_by_layer_head.svgをPNGへ出力し、掲載する層の領域をそのまま切り出して使用。セル・色・層とヘッドの並びを描き直していない。色の上限は元図のモデル別98パーセンタイル。
一つの指示での生成事例であり、固定5テストの合格率や24操作診断とは別。attentionの濃さだけで因果的寄与を断定しない。
生成コード：
def solve(xs: list[int], k: int) -> list[int]:
    # 現在の要素順を反転する
    output = list(reversed(result))
    # 昇順に並べる
    result = sorted(result)[::-1]
    return result

根拠：../results/attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/detail_analysis.json
元図：../results/attention_1epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_by_layer_head.svg
-->

---
<!-- _class: scientific attention-result -->
<!-- _header: "6. アテンションの可視化" -->

# 5M：attention の可視化（L1〜L3）

同じ指示：**各要素を絶対値にして、降順に並べる**

![w:1100 h:380](figure/attention_5m_l1_l3.png)

**生成結果：絶対値の処理は生成したが、k加算が入り、降順の処理が抜けた。**

色は各モデル内の相対的な強さ。モデル間で濃さを直接比較しない。

<!--
入力全文：xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。
5層×4head。全headを掲載。縦軸は14生成step。参照位置数・生成長はモデルによって異なる。
保存済みのattention_by_layer_head.svgをPNGへ出力し、掲載する層の領域をそのまま切り出して使用。セル・色・層とヘッドの並びを描き直していない。色の上限は元図のモデル別98パーセンタイル。
一つの指示での生成事例であり、固定5テストの合格率や24操作診断とは別。attentionの濃さだけで因果的寄与を断定しない。
生成コード：
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value + k]
    output: list[int] = []
    for value in result:
        output += [abs(value)]
    return output

根拠：../results/attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/detail_analysis.json
元図：../results/attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_by_layer_head.svg
-->

---
<!-- _class: scientific attention-result -->
<!-- _header: "6. アテンションの可視化" -->

# 5M：attention の可視化（L4〜L5）

同じ指示：**各要素を絶対値にして、降順に並べる**

![w:1100 h:380](figure/attention_5m_l4_l5.png)

**生成結果：絶対値の処理は生成したが、k加算が入り、降順の処理が抜けた。**

色は各モデル内の相対的な強さ。モデル間で濃さを直接比較しない。

<!--
入力全文：xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。
5層×4head。全headを掲載。縦軸は14生成step。参照位置数・生成長はモデルによって異なる。
保存済みのattention_by_layer_head.svgをPNGへ出力し、掲載する層の領域をそのまま切り出して使用。セル・色・層とヘッドの並びを描き直していない。色の上限は元図のモデル別98パーセンタイル。
一つの指示での生成事例であり、固定5テストの合格率や24操作診断とは別。attentionの濃さだけで因果的寄与を断定しない。
生成コード：
def solve(xs: list[int], k: int) -> list[int]:
    result: list[int] = []
    for value in xs:
        result += [value + k]
    output: list[int] = []
    for value in result:
        output += [abs(value)]
    return output

根拠：../results/attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/detail_analysis.json
元図：../results/attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_by_layer_head.svg
-->

---
<!-- _class: scientific attention-result -->
<!-- _header: "6. アテンションの可視化" -->

# 15M：attention の可視化（L1〜L4）

同じ指示：**各要素を絶対値にして、降順に並べる**

![w:1100 h:380](figure/attention_15m_l1_l4.png)

**生成結果：絶対値を取って降順に並べるコードを生成した。**

色は各モデル内の相対的な強さ。モデル間で濃さを直接比較しない。

<!--
入力全文：xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。
8層×6head。全headを掲載。縦軸は16生成step。参照位置数・生成長はモデルによって異なる。
保存済みのattention_by_layer_head.svgをPNGへ出力し、掲載する層の領域をそのまま切り出して使用。セル・色・層とヘッドの並びを描き直していない。色の上限は元図のモデル別98パーセンタイル。
一つの指示での生成事例であり、固定5テストの合格率や24操作診断とは別。attentionの濃さだけで因果的寄与を断定しない。
生成コード：
def solve(xs: list[int], k: int) -> list[int]:
    # 各要素の絶対値を取る
    result: list[int] = []
    for value in xs:
        result += [abs(value)]
    # 降順に並べる
    output: list[int] = sorted(result, reverse=True)
    return output

根拠：../results/attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/detail_analysis.json
元図：../results/attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_by_layer_head.svg
-->

---
<!-- _class: scientific attention-result -->
<!-- _header: "6. アテンションの可視化" -->

# 15M：attention の可視化（L5〜L8）

同じ指示：**各要素を絶対値にして、降順に並べる**

![w:1100 h:380](figure/attention_15m_l5_l8.png)

**生成結果：絶対値を取って降順に並べるコードを生成した。**

色は各モデル内の相対的な強さ。モデル間で濃さを直接比較しない。

<!--
入力全文：xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。
8層×6head。全headを掲載。縦軸は16生成step。参照位置数・生成長はモデルによって異なる。
保存済みのattention_by_layer_head.svgをPNGへ出力し、掲載する層の領域をそのまま切り出して使用。セル・色・層とヘッドの並びを描き直していない。色の上限は元図のモデル別98パーセンタイル。
一つの指示での生成事例であり、固定5テストの合格率や24操作診断とは別。attentionの濃さだけで因果的寄与を断定しない。
生成コード：
def solve(xs: list[int], k: int) -> list[int]:
    # 各要素の絶対値を取る
    result: list[int] = []
    for value in xs:
        result += [abs(value)]
    # 降順に並べる
    output: list[int] = sorted(result, reverse=True)
    return output

根拠：../results/attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/detail_analysis.json
元図：../results/attention_1epoch/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/figures/attention_by_layer_head.svg
-->

---
<!-- _class: compact -->

# 指示の情報を止めると合格数が落ちる

1 epochモデル。学習時に準拠した文型で、24操作を診断。

| モデル | 通常の生成 | 指示の情報を止めた生成 |
| :--- | ---: | ---: |
| 1M | 3 / 24 | **0 / 24** |
| 5M | 22 / 24 | **0 / 24** |
| 15M | 22 / 24 | **2 / 24** |

**指示から受け取る情報が、操作の選択に寄与している。**

24操作の内部診断。冒頭変更の14操作、固定5テストとは別。

<!--
本編採用の3モデルの実測値。全層で日本語指示位置のValueを0にした介入であり、指示自体を削除したものではない。各prompt33入力、greedy最大64 token。
根拠：../results/attention_1epoch/ 配下のminfreq5_maxlen24_1epoch/analysis.json
-->

---
<!-- _class: default -->

# 評価では、表現を変えた場合も確かめる

| 調べること | 今回、分かったこと |
| :--- | :--- |
| 決めた文型での動作 | 5M・15Mは高い全体合格率を示した |
| 未学習の言い換え | 15Mでも30件中15件の合格 |
| 指示の冒頭の変更 | 5Mは14件中12件から1件へ低下 |

**一種類のプロンプトでの精度に加え、表現を変えても性能が保たれるかを評価する必要がある。**

<!--
先行研究は分類・二択質問、今回の実験は限定したコード生成。課題と指標が違うことに注意。
根拠：スライド17〜24の出典、Gan and Mori（2023）、Takayama et al.（2026）
-->

---
<!-- _class: compact -->
<!-- _header: "6. 組み合わせ汎化を測る" -->

# 組み合わせ汎化ベンチマークの前提

**各操作を表す日本語表現は、Bokuの訓練データに登場する。**
**ただし、完成した指示文は訓練データと完全一致しない。**

評価872問と訓練192,900件を照合し、指示全文の一致は0件。

| 課題 | 訓練と評価で何が変わるか |
| :--- | :--- |
| 複数操作で学んだ表現を1操作で使う | 複数操作の指示でだけ使った言い方を、単独操作に使う |
| 初めて組み合わせる2操作 | 訓練では同じ指示に登場しない2操作を組み合わせる |
| 3操作で学んだ順序を2操作で使う | 3操作中の既知の順序を、未学習の2操作列として使う |

未知の日本語表現への強さとは分けて、**既知の表現を異なる構成で使う能力**を調べる。

<!--
全文未出でも、操作や機能まで未知とは限らない。Qwenの事前学習との重複は不明。
根拠：../results/composition_suite_20261008/report.md、../../data/benchmarks/composition_suite_20261008/questions.jsonl
全文一致0件は2026年10月8日に訓練アーカイブを走査して確認。
-->

---
<!-- _class: benchmark-data -->

# データセットの構成：9種類・872問

| 操作数 | 問題の種類 | 問数 | 構成 |
| ---: | :--- | ---: | :--- |
| 1 | 複数操作で学んだ表現を1操作で使う | 96 | 24操作 × 4表現 |
| 2 | 初めて組み合わせる2操作 | 100 | 5ペア × 両順序 × 10表現 |
| 2 | 同じ操作を2回 | 96 | 24操作 × 4表現 |
| 2 | 3操作で学んだ順序を2操作で使う | 88 | 88種類の操作列 |
| 3 | 初めてのペアを含む3操作 | 100 | 100種類の操作列 |
| 3 | 同じ操作を3回 | 96 | 24操作 × 4表現 |
| 4 | 同じ操作を4回 | 96 | 24操作 × 4表現 |
| 4 | 異なる4操作を組み合わせる | 100 | 100種類の操作列 |
| 4 | 2操作の組を2回繰り返す | 100 | A・B・A・Bの100種類 |

各問題でコードを1つ生成。**179通りの共通テスト入力ですべて合格した問題の割合**を正答率とする。

<!--
関数契約・許可構文・入力非変更も採点条件。179入力は境界9、固定seedのランダム128、k関連40、操作順序確認2。任意入力での正しさの証明ではない。
根拠：../../data/benchmarks/composition_suite_20261008/protocol.json、../results/composition_suite_20261008/report.md
-->

---
<!-- _class: astra-settings -->
<!-- _header: "6. 組み合わせ汎化を測る" -->

# Astraの評価設定：思考low・ツール使用を禁止

| 項目 | 設定 |
| :--- | :--- |
| モデル・推論設定 | `gpt-6-astra` ／ reasoning effort：**low** |
| 評価対象 | 872問から固定seedで抽出した各カテゴリ10問、計90問 |
| 会話・回答 | 1問ごとに独立チャット。最初の回答1回を採点。修正・再生成なし |
| ツール | 使用禁止を指示。**90問すべての実行記録で使用0件を確認** |

各問題の冒頭に与えた指示：

> ツールは一切使用せず、このメッセージだけから回答してください。ファイル閲覧、検索、コード実行、他のエージェントへの依頼は行わないでください。回答は一度だけ、指定されたコードのみを出力してください。

ツールの技術的な無効化ではなく、**指示による禁止と記録確認**。採点は回答保存後に行い、結果をAstraへ返していない。

<!--
上記の後にQwenと同じ共通のコード生成指示と各問題の日本語指示を続けた。AST・参照コード・テスト入力・過去の得点は渡していない。
温度は未指定。出力上限は製品既定で呼出側から制御していない。製品側の既定指示が残るため、Qwenとの完全に同一の実行条件ではない。
根拠：../../data/benchmarks/composition_suite_20261008/runs/astra-chat-low/sample90/config.json、chat_audit.json
抽出seed：20261009。各カテゴリで10種類の異なる意味ASTから各1表現。
-->

---
<!-- _class: default -->
<!-- _header: "" -->

![bg contain](figure/composition_benchmark_astra_no_values/plot.png)

<!--
Boku・Qwenは条件A、greedy、全872問で各問題1生成・修復なし。Astraは独立チャット・low、各カテゴリ10問のみの参考値。Astraの温度は未指定でありgreedyとは主張しない。訓練回数・生成上限・実行基盤などは一致しない。
図：figure/composition_benchmark_astra_no_values/plot.png（棒の数値ラベルなし）
数値・実行条件・入力hash：figure/composition_benchmark_astra/values.json
作図：.venv/bin/python scripts/model/benchmark.py --models boku-15m-1epoch boku-1m-3epoch qwen3-1.7b --astra-reference --presentation --rows 1 --columns 9 --values no --output docs/report/figure/composition_benchmark_astra_no_values
-->

---
<!-- _class: compact -->
<!-- _header: "6. 組み合わせ汎化を測る" -->

# 高得点の課題と、残る課題を分けて読む

| 問題の種類 | Boku 15M・1ep | Boku 1M・3ep | Qwen3-1.7B | Astra・参考値 |
| :--- | ---: | ---: | ---: | ---: |
| 初めて組み合わせる2操作 | 98 / 100 | 99 / 100 | 34 / 100 | 9 / 10 |
| 初めてのペアを含む3操作 | 96 / 100 | 100 / 100 | 27 / 100 | 10 / 10 |
| 異なる4操作を組み合わせる | 29 / 100 | 43 / 100 | 26 / 100 | 9 / 10 |

Astraだけ各カテゴリ10問。**分母と対象問題が異なるため、参考比較。**

- **今回の2・3操作の課題では、小規模モデルにも有望な結果がある。**
- Bokuの4操作では誤りが多く残る。どの操作を落とすか、順序を変えるかを分析する。
- 1Mは3epoch、15Mは1epoch。生成条件も異なり、規模だけの優劣とは解釈しない。

<!--
2操作は10種類の意味ASTの表現違い。3操作と4操作は対応した同一問題ではないため、1操作の増加だけの効果を示す比較ではない。
Bokuは入力込み256 token、Qwenは最大512新規token・thinking無効。各構成単一seed。
根拠：figure/composition_benchmark_astra/values.json、../results/composition_suite_20261008/report.md
-->

---
<!-- _class: astra-matched -->
<!-- _header: "" -->

# Astraとの比較：同じ90問に揃えた結果

Boku・Qwenも、Astraに出した**同じ各10問**の結果だけを再集計。

| 問題の種類 | Boku 15M・1ep | Boku 1M・3ep | Qwen3-1.7B | Astra・low |
| :--- | ---: | ---: | ---: | ---: |
| 複数操作の表現を1操作に使用 | 10 / 10 | 8 / 10 | 6 / 10 | 10 / 10 |
| 初めて組み合わせる2操作 | 10 / 10 | 10 / 10 | 4 / 10 | 9 / 10 |
| 3操作の順序を2操作に使用 | 10 / 10 | 10 / 10 | 2 / 10 | 10 / 10 |
| 同じ操作を2回 | 10 / 10 | 10 / 10 | 5 / 10 | 10 / 10 |
| 初めてのペアを含む3操作 | 10 / 10 | 10 / 10 | 0 / 10 | 10 / 10 |
| 同じ操作を3回 | 10 / 10 | 10 / 10 | 5 / 10 | 10 / 10 |
| 異なる4操作 | 3 / 10 | 6 / 10 | 3 / 10 | 9 / 10 |
| 2操作の組を2回（ABAB） | 4 / 10 | 6 / 10 | 0 / 10 | 10 / 10 |
| 同じ操作を4回 | 10 / 10 | 8 / 10 | 6 / 10 | 9 / 10 |
| **全90問** | **77 / 90** | **78 / 90** | **31 / 90** | **87 / 90** |
| **正答率** | **85.6%** | **86.7%** | **34.4%** | **96.7%** |

Astraは87/90正解。各カテゴリは**1問差で10ポイント**。問題は同じでも、推論・実行条件は完全には揃っていない。

<!--
Astraの温度・出力上限は製品既定。独立チャットの本文へ共通指示を配置。Boku/Qwenの生成をやり直したものではなく保存済み結果の再集計。
根拠：../results/astra_chat_sample90_20261009/report.md、values.json
-->

---
<!-- _class: default -->
<!-- _header: "7. ベンチマークから研究課題を考える" -->

# 今回の結果の意義と、次の研究課題

**今回のベンチマークでは、小規模モデルの組み合わせ汎化について有望な結果が得られた。**

今後は比較条件を揃え、より大きなモデルとの比較を追加するとともに、**評価設計と作成手順を明文化する。**

- 比較条件：訓練回数、プロンプト、生成上限などを記録し、揃えられる条件を揃える。
- 評価設計：何を既知・未知とするか、どの誤りを検出したいかを定める。
- 作成手順：問題の選定、訓練との照合、採点方法、再現手順を公開可能な形に整理する。

<!--
小規模モデルの一般的優位を主張するものではなく、今回の限定した課題での結果と今後の研究方針。
-->

---
<!-- _class: default -->

# ベンチマークの役割

**モデルの能力と限界を観測し、次に取り組む研究課題を明確にする。**

- 入出力の成功例だけでは、能力を獲得したか判断できない。共通の基準で定量評価する。
- 正誤を検証できる課題では、評価基準を明確にしやすい。小規模モデルでも改善を確かめられる。
- 得点だけでなく、どの条件で成功し、どの条件で失敗するかを見る。

今回なら、**2・3操作での高得点と、4操作で残る誤り**が、次の分析対象を教えてくれる。

---
<!-- _class: default -->

# 自分の研究でベンチマークを作るには

1. **測りたい能力を先に決める。** 例：既知の操作を、新しい組み合わせで実行できるか。
2. **目的に沿って課題と正解基準を作る。** 何を変え、何を固定するかを決める。
3. **共通条件で測り、成功と失敗を分析する。** 作成手順と比較条件も記録する。
4. **高得点で差が見えなくなったら、評価の役割を見直す。** 元の結果を残し、次に測る能力を定める。

**得点を上げる研究と、能力向上を観測できる評価を作る研究を、両方考える。**

<!--
学生に求めるのは結果の暗記ではなく、自分の研究で測りたい能力、評価課題、採点基準、次の研究課題を説明できること。
-->

---
<!-- _class: default -->

# この結果が示す範囲

- 訓練は24操作を最大3つ組み合わせるコード生成。追加評価では4操作まで調べた。
- 冒頭変更の比較は14操作。日本語能力全体の測定ではない。
- 学習は一つの乱数設定。繰り返し実験のばらつきは未確認。

今後は文型の偏りを減らした合成データで、表現への強さを再評価する。

<!--
乱数seedは学習20260925、内部診断20260930。追加実験は今後の提案です。
根拠：../results/trained_model_inventory.md、../results/boku_nano_1epoch_attention_comparison.md
-->

---
<!-- _class: diagram -->

# まとめとWebデモ

**限定したコード生成は、小さなモデルでも1 epochで学習できた。**

**表現を変えた場合の性能と、操作を組み合わせる能力は、分けて確かめる必要がある。**

| デモの流れ | 役割 |
| :--- | :--- |
| ① 自由な日本語を入力 | 作りたい処理を伝える |
| ② 補助モデルで文型を整える | 対象の操作と表現にそろえる |
| ③ 指示を確認して生成する | Boku-nanoがPythonコードを作る |
| Webデモ | [Boku-nanoを試す](https://yuuono.github.io/bokunano/) |

<!--
デモの文型整形の効果は上記の実験評価値に含めていません。整形はQwen3-0.6B、生成は選択したBoku Nano。デモでは1 epochモデルを選択してください。自由な日本語をBoku Nano単体が扱うとは説明しないこと。
根拠：../../web/index.html、../../web/app.js、../procedures/boku_nano_onnx_web_demo.md
-->
