---
marp: true
math: mathjax
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
    section.closing .demo-link { text-align: right; margin-top: 20px; }
    section.closing .demo-link a { display: inline-block; padding: 10px 16px; border-radius: 6px; background: #2877aa; color: #fff; font-size: 20px; font-weight: 600; text-decoration: none; }
        section.closing { font-size: 21px; line-height: 1.4; }
        section.closing h1 { margin-bottom: 18px; }
        section.closing p { margin: 8px 0; }
        section.closing table { font-size: 20px; margin: 8px 0; }
        section.closing th, section.closing td { padding: 6px 10px; }
    section.closing > h2 { font-size: 26px; margin: 26px 0 10px; padding-top: 18px; border-top: 1px solid #d8e1e9; }
      section.overview-original { padding: 0; }
    section.overview-original .canvas { width: 1920px; height: 1080px; box-sizing: border-box; padding: 22px 28px 16px; transform: scale(0.6666667); transform-origin: 0 0; color: #17212b; font-family: Arial, "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic", sans-serif; font-size: 14px; font-weight: 400; line-height: 1.33; display: block; }
    section.overview-original h1 { margin: 0; font-size: 32px; font-weight: 600; line-height: 1.2; color: #17212b; }
    section.overview-original .sub { margin: 2px 0 8px; font-size: 16px; color: #52606d; }
    section.overview-original .lane { display: grid; grid-template-columns: 52px 330px 34px 520px 34px 400px 26px 1fr; align-items: stretch; background: #f5f7f9; border-radius: 10px; padding: 7px 12px 7px 0; }
    section.overview-original .lane.alt { background: #fbfcfd; border: 1px solid #edf0f3; }
    section.overview-original .lname { display: flex; flex-direction: column; align-items: center; font-weight: 700; color: #3d4b57; }
    section.overview-original .lname .n { font-size: 22px; line-height: 1.1; }
    section.overview-original .lname .t { font-size: 15px; writing-mode: vertical-rl; margin-top: 6px; letter-spacing: 2px; }
    section.overview-original .conn { display: grid; grid-template-columns: 52px 330px 34px 520px 34px 400px 26px 1fr; height: 20px; align-items: center; font-size: 13px; color: #4a5763; }
    section.overview-original .conn .dash { color: #8a6d1f; }
    section.overview-original .box { background: #eaf2f8; border: 1.5px solid #3d7591; border-left: 7px solid #3d7591; border-radius: 8px; padding: 5px 12px 6px; }
    section.overview-original .box b.t { display: block; font-size: 17px; font-weight: 600; margin-bottom: 1px; }
    section.overview-original .rule { background: #eaf2f8; border-color: #3d7591; }
    section.overview-original .teacher { background: #fbeee3; border-color: #c47a36; }
    section.overview-original .data { background: #edf5eb; border-color: #4f8a4b; }
    section.overview-original .model { background: #f0ebf8; border-color: #6b55a3; }
    section.overview-original .eval { background: #fdf4dc; border-color: #a9821b; }
    section.overview-original .note { color: #8a4b16; font-size: 13px; }
    section.overview-original .mono { font-family: "Courier New", Menlo, Consolas, monospace; font-size: 13px; }
    section.overview-original .stack { display: flex; flex-direction: column; gap: 8px; }
    section.overview-original .stack .box { flex: 1; }
    section.overview-original .arrow { display: flex; align-items: center; justify-content: center; font-size: 22px; color: #4a5763; }
    section.overview-original .arrow.dot { color: #4f8a4b; font-size: 18px; }
    section.overview-original .span-c3c4 { grid-column: 6 / 9; }
    section.overview-original .span-c1c2 { grid-column: 2 / 5; }
    section.overview-original .demo { display: flex; align-items: stretch; gap: 0; }
    section.overview-original .demo .box { flex: 1; }
    section.overview-original .demo .arrow { width: 40px; }
    section.overview-original .legend { display: flex; gap: 34px; margin-top: 8px; font-size: 14px; align-items: center; }
    section.overview-original .legend span.k { display: inline-block; width: 16px; height: 16px; border-radius: 3px; border: 1.5px solid; vertical-align: -3px; margin-right: 6px; }
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
    section.operation-scope { font-size: 21px; }
    section.operation-scope h1 { font-size: 34px; margin-bottom: 14px; }
    section.operation-scope h2 { font-size: 23px; margin: 12px 0 6px; }
    section.operation-scope p { font-size: 18px; margin: 6px 0; }
    section.operation-scope table { font-size: 18px; margin: 6px 0; }
    section.operation-scope th, section.operation-scope td { padding: 5px 9px; }
    section.operation-scope th, section.operation-scope td { text-align: right; }
    section.operation-scope .operation-layout { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 0.9fr); gap: 30px; align-items: start; }
    section.operation-scope .operation-ast { min-width: 0; align-self: center; padding: 20px 22px; background: #eaf3fb; border: 2px solid #92b1c8; border-radius: 8px; }
    section.operation-scope .operation-ast h2 { margin-top: 0; color: #245f8b; }
    section.operation-scope .operation-ast p { font-size: 18px; line-height: 1.5; }
    section.operation-scope .operation-ast pre { margin: 12px 0 0; padding: 14px; font-size: 20px; line-height: 1.45; white-space: pre-wrap; overflow-wrap: anywhere; }

  /* 全体図の文字は2ページ目のMarkdown本文で編集する */
  section.intro-overview { font-size: 17px; line-height: 1.45; }
  section.intro-overview h1 { margin: 0 0 6px; font-size: 35px; line-height: 1.25; color: #17212b; }
  section.intro-overview h1 + p { margin: 0; font-size: 18px; color: #52606d; }
  section.intro-overview h2 { margin: 27px 0 12px; font-size: 19px; line-height: 1.25; color: #334155; }
    section.intro-overview .ov-flow { display: grid; grid-template-columns: repeat(3, 1fr); gap: 50px; height: 220px; }
  section.intro-overview .ov-card { position: relative; padding: 16px 20px; border-radius: 14px; background: #eaf3fb; }
  section.intro-overview .ov-card:nth-child(2) { background: #e9e7f8; }
  section.intro-overview .ov-card:nth-child(3) { background: #e9f5ed; }
  section.intro-overview .ov-card:not(:last-child)::after { content: "→"; position: absolute; right: -43px; top: 72px; font-size: 31px; color: #45556a; }
  section.intro-overview .ov-card h3 { margin: 0 0 12px; font-size: 21px; line-height: 1.3; color: #245f8b; }
  section.intro-overview .ov-card p { margin: 0 0 8px; font-size: 17px; line-height: 1.45; }
  section.intro-overview .ov-card p:last-child { position: absolute; left: 20px; right: 20px; bottom: 14px; margin: 0; font-size: 14px; color: #52606d; }
    section.intro-overview .ov-card:last-child p:last-child { position: absolute; left: 20px; right: 20px; bottom: 14px; margin: 0; font-size: 15px; color: #17212b; }
  section.intro-overview .ov-card code { background: transparent; font-size: 15px; white-space: normal; }
    section.intro-overview .ov-card:last-child pre { margin: 0 0 8px; padding: 10px 12px; font-size: 20px; line-height: 1.3; }
    section.intro-overview .ov-card:last-child pre code { display: block; font-size: 1em; white-space: pre-wrap; overflow-wrap: anywhere; }
  section.intro-overview .ov-steps { position: relative; display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-top: 48px; padding-top: 31px; }
  section.intro-overview .ov-steps::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 4px; background: #ced7e1; }
  section.intro-overview .ov-step { position: relative; padding: 0 8px; }
  section.intro-overview .ov-step h3 { margin: 0 0 10px; font-size: 20px; line-height: 1.3; color: #245f8b; }
  section.intro-overview .ov-step h3 strong { position: absolute; left: 39%; top: -50px; width: 42px; height: 42px; border-radius: 50%; background: #2877aa; color: #fff; font-size: 22px; line-height: 42px; text-align: center; }
  section.intro-overview .ov-step:nth-child(3) h3 strong { background: #745db3; }
  section.intro-overview .ov-step:nth-child(4) h3 strong { background: #3b9460; }
  section.intro-overview .ov-step p { margin: 0 0 6px; font-size: 17px; line-height: 1.45; }
  section.intro-overview .ov-step p:last-child { font-size: 14px; color: #52606d; }
    section.intro-overview .ov-step:nth-child(3) p:last-child { font-size: 14px; line-height: 1.45; color: #52606d; }
    section.intro-overview .ov-step:nth-child(3) p { font-size: 17px; line-height: 1.4; color: #17212b; }
    section.intro-overview .ov-step:first-child pre { margin: 8px 0 0; padding: 8px; font-size: 14px; line-height: 1.3; white-space: pre-wrap; overflow-wrap: anywhere; }
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
  section.logit-overview { padding: 44px 54px; font-size: 22px; }
  section.logit-overview h1 { font-size: 36px; margin-bottom: 18px; }
  section.logit-overview p { margin: 10px 0; }
  section.logit-overview .lp-context { display: flex; align-items: center; gap: 18px; margin: 18px 0 24px; }
  section.logit-overview .lp-input { padding: 12px 18px; background: #eaf3fb; font-size: 27px; }
  section.logit-overview .lp-model { padding: 12px 22px; background: #efeaf8; color: #685098; font-weight: 700; }
    section.logit-overview .lp-grid { display: grid; grid-template-columns: minmax(0, 0.95fr) 76px minmax(0, 0.95fr) 76px minmax(0, 1.1fr); column-gap: 6px; align-items: stretch; }
    section.logit-overview .lp-panel { min-width: 0; padding: 12px; border: 1px solid #cddae6; border-radius: 8px; background: #f8fafc; }
  section.logit-overview .lp-panel h2 { font-size: 23px; margin: 0 0 10px; line-height: 1.35; }
    section.logit-overview .lp-panel:last-child h2 { font-size: 21px; }
  section.logit-overview .lp-panel p { font-size: 17px; margin: 8px 0 12px; }
  section.logit-overview .lp-arrow { align-self: center; text-align: center; font-size: 29px; color: #685098; }
    section.logit-overview .lp-arrow small { display: table; min-width: 58px; box-sizing: border-box; margin: 0 auto 4px; padding: 3px 6px; border-radius: 4px; background: #efeaf8; color: #514078; font-size: 12px; font-weight: 700; white-space: nowrap; }
  section.logit-overview .lp-row { display: grid; grid-template-columns: 48px 1fr 76px; gap: 8px; align-items: center; height: 36px; font-size: 22px; }
  section.logit-overview .lp-track { position: relative; height: 25px; }
  section.logit-overview .lp-score .lp-track::before { content: ''; position: absolute; left: 40%; top: -9px; bottom: -9px; border-left: 1px solid #8b98a5; }
  section.logit-overview .lp-bar { display: block; height: 25px; background: #d9822b; }
  section.logit-overview .lp-score .lp-bar { position: absolute; left: 40%; }
  section.logit-overview .lp-row:nth-of-type(2) .lp-bar { background: #5b8fc7; }
  section.logit-overview .lp-row:nth-of-type(3) .lp-bar { background: #5a9a6a; }
  section.logit-overview .lp-row:nth-of-type(4) .lp-bar { background: #aaa; }
  section.logit-overview .lp-row b { font-size: 20px; font-weight: 500; white-space: nowrap; }
  section.logit-overview .lp-pick { margin: 25px 0 14px; padding: 15px 10px; border: 2px solid #d9822b; background: #fff3e5; text-align: center; font-size: 30px; color: #b8661a; }
  section.logit-overview .lp-panel .lp-next { font-size: 23px; text-align: center; margin: 12px 0; }
  section.logit-overview .lp-summary { margin-top: 20px; padding: 10px 15px; background: #f3f1f9; border-left: 4px solid #8b74c4; font-size: 22px; }
  section.logit-overview .figure-reference { font-size: 14px; color: #52606d; margin-top: 10px; }
  section.generation-page { font-size: 22px; line-height: 1.45; }
  section.generation-page h1 { font-size: 35px; margin-bottom: 16px; }
  section.generation-page h2 { font-size: 24px; margin: 0 0 12px; }
  section.generation-page h3 { font-size: 21px; margin: 16px 0 8px; color: #245f8b; }
  section.generation-page p { margin: 10px 0; }
  section.generation-page .generation-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; margin-top: 12px; }
  section.generation-page .generation-columns > div { min-width: 0; }
  section.generation-page .generation-stage { border-top: 4px solid #2877aa; padding: 16px 0 0; }
  section.generation-page .generation-stage:last-child { border-color: #745db3; }
  section.generation-page .generation-example { padding: 12px 16px; background: #f1f6fb; margin: 12px 0; }
  section.generation-page .generation-example p { margin: 6px 0; }
  section.generation-page .generation-check { font-size: 19px; padding: 10px 14px; border-left: 3px solid #d9822b; background: #fff7ed; }
  section.generation-page .generation-note { font-size: 16px; color: #52606d; margin-top: 10px; }
  section.generation-page .generation-example ul { margin: 6px 0; }
  section.generation-page .generation-example li { margin: 5px 0; }
  section.generation-page .generation-prompt { font-size: 19px; line-height: 1.5; padding: 10px 14px; border-left: 3px solid #745db3; background: #f5f3fa; }
  section.generation-page pre { font-size: 19px; line-height: 1.3; padding: 12px 16px; margin: 8px 0; }
  section.generation-page table { font-size: 19px; margin: 14px 0; }
  section.generation-page th, section.generation-page td { padding: 5px 10px; }
  section.generation-page .generation-result { padding: 10px 16px; background: #edf6ef; margin-top: 16px; }
  section.split-design { font-size: 22px; line-height: 1.4; }
  section.split-design h1 { font-size: 35px; margin-bottom: 18px; }
  section.split-design .split-key { font-size: 29px; padding: 15px 20px; background: #eaf3fb; border-left: 5px solid #2877aa; margin-bottom: 16px; }
  section.split-design .split-order { font-size: 24px; margin: 15px 0; }
  section.split-design table { font-size: 20px; margin: 16px 0; }
  section.split-design td, section.split-design th { padding: 8px 12px; }
  section.split-design .split-warning { font-size: 22px; background: #fff5e9; border-left: 4px solid #cf7d31; padding: 12px 16px; }
  section.split-design .split-note { font-size: 15px; color: #52606d; margin-top: 12px; }
  section.benchmark-findings table { font-size: 20px; }
  section.benchmark-findings th, section.benchmark-findings td { padding: 8px 7px; }
  section.test-summary { font-size: 22px; line-height: 1.4; }
  section.test-summary h1 { font-size: 35px; }
  section.test-summary .result-columns { display: grid; grid-template-columns: 1.2fr 1fr; gap: 32px; }
  section.test-summary h2 { font-size: 25px; margin: 12px 0; }
  section.test-summary table { font-size: 18px; margin: 12px 0; }
  section.test-summary td { font-weight: 400; }
  section.test-summary td strong { font-weight: 700; color: inherit; }
  section.test-summary th, section.test-summary td { padding: 12px 8px; white-space: nowrap; }
  section.test-summary .result-note { font-size: 17px; color: #52606d; margin-top: 18px; }
  section.model-settings { font-size: 22px; line-height: 1.3; }
  section.model-settings p { margin: 8px 0; }
  section.model-settings h1 { font-size: 35px; margin-bottom: 14px; }
  section.model-settings table { font-size: 20px; margin: 12px 0; }
  section.model-settings th, section.model-settings td { padding: 5px 12px; }
  section.model-settings h2 { font-size: 25px; margin: 12px 0; }
  section.model-settings .tokenizer-settings { padding: 12px 18px; background: #edf6ef; line-height: 1.6; }
  section.model-settings .settings-note { font-size: 16px; margin-top: 12px; color: #52606d; }
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
  section.temperature-example .katex-display { margin: 6px 0; }
  section.decoder-logits h1 { font-size: 33px; margin-bottom: 18px; }
  section.decoder-logits .code-columns { grid-template-columns: 1fr 1fr; gap: 36px; }
  section.decoder-logits pre { font-size: 17px; line-height: 1.35; margin-bottom: 10px; }
  section.decoder-logits .decoder-flow { font-size: 17px; line-height: 1.2; text-align: center; }
  section.decoder-logits .decoder-output { padding: 8px; border: 2px solid #d9822b; background: #fff3e5; color: #a95d16; font-size: 23px; font-weight: 700; }
  section.decoder-logits .decoder-output small { font-size: 16px; font-weight: 400; margin-left: 12px; }
  section.decoder-logits .decoder-up { position: relative; height: 15px; width: 100%; }
  section.decoder-logits .decoder-up::before { content: ''; position: absolute; left: 50%; top: 3px; bottom: 0; border-left: 2px solid #52606d; transform: translateX(-1px); }
  section.decoder-logits .decoder-up::after { content: ''; position: absolute; left: 50%; top: 0; transform: translateX(-50%); border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 5px solid #52606d; }
  section.decoder-logits .decoder-model { position: relative; padding: 8px 14px; border: 2px solid #aab8c5; border-radius: 12px; background: #f8fafc; }
  section.decoder-logits .decoder-name { position: absolute; right: 8px; top: 10px; font-size: 12px; color: #52606d; }
  section.decoder-logits .decoder-node { box-sizing: border-box; width: 76%; margin: 0 auto; padding: 5px 8px; border: 1px solid #92b1c8; border-radius: 5px; background: #eaf3fb; }
  section.decoder-logits .decoder-head { width: 48%; background: #eee; border-color: #9aa0a6; }
  section.decoder-logits .decoder-norm { background: #fff4c2; border-color: #cabd72; }
  section.decoder-logits .decoder-embedding { background: #fce3e5; border-color: #d5a3aa; }
  section.decoder-logits .decoder-block { margin: 0 auto; width: 94%; box-sizing: border-box; padding: 7px 8px; border: 1px solid #a1aec3; border-radius: 8px; background: #edf0f5; }
  section.decoder-logits .decoder-block-title { font-size: 15px; text-align: left; margin-bottom: 7px; }
  section.decoder-logits .decoder-block .decoder-node { width: 80%; }
  section.decoder-logits .decoder-node small { display: block; font-size: 12px; margin-top: 2px; }
  section.decoder-logits .decoder-attention { background: #ffe4be; border-color: #d1a675; }
  section.decoder-logits .decoder-mlp { background: #d6f1fa; border-color: #87b8c8; }
  section.decoder-logits .decoder-input { font-size: 16px; padding: 6px; border: 1px solid #92b1c8; }
  section.decoder-logits .residual-map { position: relative; height: 282px; padding: 0; }
  section.decoder-logits .residual-map .decoder-block-title { position: absolute; top: 7px; left: 8px; }
  section.decoder-logits .residual-map .decoder-node { position: absolute; left: 10%; width: 80%; margin: 0; z-index: 1; padding: 4px 5px; }
  section.decoder-logits .residual-map .decoder-up { position: absolute; left: 0; width: 100%; height: 12px; }
  section.decoder-logits .add-norm-group { position: absolute; left: 10%; top: 106px; width: 80%; height: 62px; box-sizing: border-box; border: 1px solid #cabd72; border-radius: 5px; background: #fff4c2; }
  section.decoder-logits .add-norm-group .norm-step { position: absolute; top: 4px; width: 100%; font-size: 15px; }
  section.decoder-logits .add-norm-group .add-step { position: absolute; bottom: 4px; width: 100%; font-size: 15px; }
  section.decoder-logits .add-norm-group .decoder-up { top: 25px; height: 10px; }
  section.decoder-logits .skip-attn, section.decoder-logits .skip-mlp { position: absolute; width: 46%; z-index: 2; box-sizing: border-box; border-bottom: 2px solid; }
  section.decoder-logits .skip-attn { left: 4%; top: 152px; height: 116px; border-left: 2px solid; color: #2877aa; }
  section.decoder-logits .skip-mlp { right: 4%; top: 40px; height: 98px; border-right: 2px solid; color: #8751a5; }
  section.decoder-logits .skip-attn::before, section.decoder-logits .skip-mlp::before { content: ''; position: absolute; top: 0; width: 13%; border-top: 2px solid; }
  section.decoder-logits .skip-attn::before { left: 0; }
  section.decoder-logits .skip-mlp::before { right: 0; }
  section.decoder-logits .skip-attn::after { content: ''; position: absolute; left: 13%; top: -4px; border-left: 6px solid; border-top: 5px solid transparent; border-bottom: 5px solid transparent; }
  section.decoder-logits .skip-mlp::after { content: ''; position: absolute; right: 13%; top: -4px; border-right: 6px solid; border-top: 5px solid transparent; border-bottom: 5px solid transparent; }
  section.decoder-logits .skip-attn span { position: absolute; left: -17px; top: 51px; font-size: 15px; background: #edf0f5; }
  section.decoder-logits .skip-mlp span { position: absolute; right: -17px; top: 42px; font-size: 15px; background: #edf0f5; }
  section.decoder-logits .residual-dot { position: absolute; left: 50%; width: 6px; height: 6px; transform: translate(-50%, -50%); border-radius: 50%; z-index: 3; }
  section.ar-code .temperature-panels { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin: 18px 0; }
  section.ar-code .temperature-panel { padding: 14px 20px 10px; border: 1px solid #d8e1e9; border-radius: 8px; background: #f7f9fc; }
  section.ar-code .temperature-panel h2 { font-size: 23px; margin: 0 0 5px; }
  section.ar-code .temperature-panel p { margin: 5px 0; font-size: 18px; }
  section.ar-code .prob-bars { height: 115px; display: flex; align-items: end; justify-content: space-around; border-bottom: 2px solid #64748b; margin-top: 28px; }
  section.ar-code .prob-bar { position: relative; width: 54px; background: #745db3; }
  section.ar-code .prob-bar span { position: absolute; top: -25px; width: 80px; left: -13px; text-align: center; font-size: 18px; }
  section.ar-code.temperature-example .prob-bars { height: 85px; }
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
    section.ar-diagram .ar-feedback::before { content: ""; position: absolute; left: 408px; right: 100px; top: -12px; height: 48px; border-right: 3px solid #cf7d31; border-bottom: 3px solid #cf7d31; }
  section.ar-diagram .ar-feedback::after { content: ""; position: absolute; left: 401px; top: 37px; width: 14px; height: 54px; background: #cf7d31; clip-path: polygon(40% 0, 60% 0, 60% 85%, 100% 85%, 50% 100%, 0 85%, 40% 85%); }
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

整数リストxsと整数kを受け取り、  
偶数だけを残し、 
各要素に k を加える  
solve 関数を書いてください

決められた操作・文型の範囲

</div>
<div class="ov-card">

### ② Boku-nano

語彙数2048のトークナイザ
1M, 5M & 15M パラメータ
トークナイザとモデルをゼロから学習
decoder Transformerによる
next token prediction 

日本語指示から、python関数を生成

</div>
<div class="ov-card">

### ③ Python関数

```python
def solve(xs, k):
    return [x + k for x in xs
            if x % 2 == 0]
```

参照インタプリタによる実行・検証
</div>
</div>

## 作り方と確かめ方

<div class="ov-steps">
<div class="ov-step">

### **1** 中間表現を定義

訓練データ合成のための<br>中間表現（意味AST）
24基本操作を最大3つ組み合せ

```json
{"sequence": [{"filter": ["even"]},
              {"map": ["add_k"]}]}
```

</div>
<div class="ov-step">

### **2** 合成データ作成

意味ASTから、日本語指示文と
pythonコードを生成

それぞれ基本操作に対して、20通りの
日本語表現とpythonコード合成し、
ルールベースで組み合わせる
訓練データ 約19万件

</div>
<div class="ov-step">

### **3** フルスクラッチ学習

トークナイザと
transformer をゼロから学習

15M parameter
8 layers・6 heads
1ヘッドあたり64次元

</div>
<div class="ov-step">

### **4** テスト検証・<br>ベンチマークによる評価

出力されたコードを
参照インタプリタで検証

84,180 / 84,550問 合格

</div>
</div>

<!-- > 評価結果は「24操作・最大3操作」という限定された範囲でのものです。ブラウザデモの自由な日本語入力は、別モデルで決められた文型に整えてから -nano に渡します。 -->

<!--
日本語の指示からPython関数を作る流れと、合成データ生成・学習・実行評価の流れを説明する。
このページの本文はboku1_nano_overview_intro_marp.mdからコピーした。
根拠：../results/model_reports/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch.md
-->

<!-- ---  -->
<!-- 1_class: key-goal -->
<!-- 1_header: "1. 課題と狙い" -->

<!-- # 課題と狙い

抽出や順序の変更など、**対象を24種類の操作に限定**する

| 範囲を絞る | 目指すモデル |
| :--- | :--- |
| あらかじめ定めた整数リストの操作 | 学生一人でもフルスクラッチで作れる |
| 操作を組み合わせて処理を表す | **小規模言語モデル（SLM）** |

## 別の用途への応用

関数の組み合わせで表せる処理なら、  
同じ考え方を **NPCの挙動などにも応用できる可能性**がある -->

<!--
目安：60秒

今回の対象は、抽出・変換・順序変更・切り出しの24操作です。あらゆるコード生成を扱うのではなく、対象の処理をあらかじめ定めることで、学生一人でトークナイザーとTransformerをフルスクラッチで作れる規模を目指しました。既存のモデル重みは使わず学習しています。
関数の組み合わせで表現できる処理なら、同じ考え方をNPCの挙動など別の用途へ応用できる可能性があります。これは今後の構想であり、今回実装・評価した成果ではありません。

根拠：
- [atomic_semantic_asts.md](../specifications/atomic_semantic_asts.md)
- [trained_model_inventory.md](../results/trained_model_inventory.md)
-->

<!-- --- -->
<!-- 2_class: default -->
<!-- 2_header: "2. 学習を成立させるための工夫" -->
<!-- # 意味ASTの具体例

日本語：**偶数だけを残して、各要素にkを加える**

```json
{
  "sequence": [
    {"filter": ["even"]},
    {"map": ["add_k"]}
  ]
}
```

偶数の抽出 → kを加える、という処理の順序を保存 -->

<!--
目安：40秒

実際の仕様からsemantic_astの部分を抜き出しています。抽出がfilter、各要素への変換がmapです。ASTは合成データを作るために使用し、推論時には日本語だけをモデルへ渡します。

根拠：
- [atomic_semantic_asts.md](../specifications/atomic_semantic_asts.md)
-->

---
<!-- _class: operation-scope -->

# 意味ASTは24種類、3操作まで組み合せで12,720通り

<div class="operation-layout">
<div class="operation-tables">

## 基本操作

| 種類 | 操作数 | 例 |
| ---: | ---: | ---: |
| 条件に合う数を残す | 10 | 偶数、奇数、正の値、kより大きい値 |
| 一つずつ値を変える | 8 | kを加える、2倍、絶対値、二乗 |
| 順序を変える | 3 | 昇順、降順、現在の順序の反転 |
| 一部を取り出す | 3 | 先頭k個、末尾k個、1個おき |

## 操作の組み合わせ

<!-- 同じ操作を繰り返さず、順序を区別して数える。 -->

| 操作数 | 数え方 | 意味の種類 |
| ---: | ---: | ---: |
| 1操作 | 24 | 24 |
| 2操作 | 24 × 23 | 552 |
| 3操作 | 24 × 23 × 22 | 12,144 |
| 合計 | 24 ＋ 552 ＋ 12,144 | **12,720** |

</div>
<div class="operation-ast">

## 意味ASTの例

日本語：奇数だけを残し、各要素を2倍して降順に並べる

```json
{
    "sequence": [
        {"filter": ["odd"]},
        {"map": ["mul_const", 2]},
        {"order": "descending"}
    ]
}
```

</div>
</div>

<!-- 同じ操作の反復は、テストで確かめる。 -->

<!--
汎用のプログラミング全般を扱う実験ではありません。
根拠：../specifications/atomic_semantic_asts.md
-->

---
<!-- _class: split-design -->
<!-- _header: "" -->

# 訓練・検証・テストは、意味ASTの段階で分ける

<div class="split-key"><strong>日本語文やコードを生成する前に、意味AST単位で分割する。</strong></div>

<div class="split-order">意味ASTを分割　→　<strong>各集合の中で</strong>言い換え・コード変換</div>

訓練 **約80%** ／ 検証 **約10%** ／ 通常テスト **約10%**

| テスト | 何を変えて確かめるか |
| :--- | :--- |
| **通常** | 同じ基本操作の範囲で、訓練に含まれない意味ASTを評価する。 |
| **言い換え** | 既知の単独操作に、訓練で使わなかった日本語表現を使う。 |
| **組合せ汎化** | 例：別々に学んだ「偶数抽出」と「降順整列」を組み合わせる。 |
| **同じ操作の反復** | 同じ操作を2回・3回続けて適用する。例：「各要素にkを加える」を2回行う。 |
| **境界値** | 空リスト、要素1個、条件を満たす要素なし、全要素同値、負数など。 |

<div class="split-warning"><strong>生成してから分けると、同じ問題の表記違いが訓練とテストに混入する。</strong><br>同じ意味ASTから作った言い換え・等価コードは、同じ分割先にまとめる。</div>

<!-- <div class="split-note">組合せ汎化用のASTを先に確保し、残りを約80：10：10に分割。言い換えは表現の汎化を測る別枠。<br>実際の評価には「同じ操作の反復」も追加し、計5種類のテストを使う。</div> -->

<!--
既存の「五つのテストで、生成コードを実行する」を4ページ目に移し、生成前の分割を主題に改訂。
根拠：../policies/ast_split_policy.md。compositional=670を先に確保し、残り12,050をtrain=9,646、val=1,202、normal=1,202へ分割。約80/10/10であり全12,720の一律分割ではない。
通常テストを「同じ操作の組み合わせで指示と定数だけ変更」とすると既存の意味AST分割と矛盾するため、訓練にないASTと記載。言い換えは訓練済み単独ASTと未学習表現の組による独立評価で、通常テストとの違いを明示。
境界値はnormalと同じASTで実行入力を変える。反復AST1,152件は別途生成。
固定5テストの指示件数はnormal=24,040、compositional=13,400、paraphrase=30、repetition=23,040、boundary=24,040。合計84,550であり一意な指示数ではない。生成コードを実行し、参照実装との一致等を確認する。
-->

---
<!-- _class: ast-training-pair ast-merged -->
<!-- 2_header: "2. 学習を成立させるための工夫" -->

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

**Qwen3-4B-AWQで各操作の日本語表現を生成**<br>
ASTの順に結合し、テンプレートの<br>
`{operations}`をルールベースで埋める。

</div>
<div class="ast-example">

#### 生成例

整数リストxsと整数kを受け取り、  
偶数だけを残し、各要素にkを加える  
solve関数を書いてください

</div>
</div>
<div class="ast-output">

### 検証済みのPythonコード

<div class="ast-method">

#### 生成の手順

**ASTの操作をPythonコードへ変換**  
構文を確認し、実行結果を  
参照インタプリタの結果と検証

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
<!-- _class: generation-page -->

# Qwen3-4B-AWQで日本語表現を生成し、組み合わせで指示文作成

**表現辞書の作成**と、**承認済み表現の組み合わせ**の二段階で指示を作る。

<div class="generation-columns">
<div class="generation-stage">

## ① 表現辞書を作る：Qwen3-4B-AWQ ＋ 人

Qwen3-4B-AWQに、各基本操作の表現を約20種類作成

### 保存済みプロンプト（要約）

<div class="generation-prompt">
意味ASTと厳守事項に従い、指定件数の表現を作る。<br>
操作・比較境界・入力順序を変えず、別の操作を加えない。<br>
終止形と接続形を同じ意味で作り、指定のJSONだけを返す。
</div>

### 例：「偶数を残す」の生成候補

<div class="generation-example">
「偶数だけを残す」／「偶数だけを残し」<br>
「偶数を選び出す」／「偶数を選び出して」
</div>

**人が意味を確認し、承認した表現だけを辞書に登録**

</div>
<div class="generation-stage">

## ② 指示を作る：ルールベース

意味ASTに沿って、承認済みの表現を組み合わせる

### 例：偶数を残す → 各要素にkを加える

<div class="generation-example">

**選ぶ表現**

「偶数の要素を取り出す」<br class="compact-break">「各要素にkを加える」

**つなぐルール**

操作1し、操作2する

</div>

**生成する日本語指示**

「偶数の要素を取り出し、各要素にkを加える」

</div>
</div>

<!-- <div class="generation-note">30件は候補数。承認後の採用数とは異なる。意味ASTを訓練・検証・テストに分けてから、表現を増やす。</div> -->

<!--
二段階のうち、第一段階に「Qwen3の候補生成」と「人による意味確認・承認」を含める。
プロンプトは原文の要約。原文：../../prompts/japanese_instruction_generation/atomic_expression_system.txt、atomic_expression_user.txt。userテンプレートの$countは「指定件数」と要約。意味AST・正準な意味・厳守事項・既存表現も渡す。
モデル名・候補数：../results/japanese_atomic_expression_generation_results.md、../../config/qwen_atomic_expression_generation.json。Qwen3-4B-AWQで24操作×30件を生成。各操作で20件以上の承認を得るための候補母数。
候補文・合成文は説明例。人による意味確認・承認は工程として示す。
アトミック操作は意味ASTの基本操作。「偶数を残す」は元の順序・重複を保持し、並べ替えを追加しない。
既存資料：../results/rule_generated_instruction_results.md、../results/replacement_resolved_train_instruction_results.md、../policies/ast_split_policy.md。
-->

---
<!-- _class: generation-page -->

# 意味ASTから、ルールで等価なPythonコード生成

同じ意味ASTでも、異なる書き方のコードを生成

<div class="generation-columns">
<div>

## 内包表記でまとめて選ぶ

```python
def solve(xs, k):
    # 条件に合う要素のリストを返す
    return [
        value
        for value in xs
        if value % 2 == 0]
```

</div>
<div>

## forループで順に選ぶ
```python
def solve(xs, k):
    result = []
    for value in xs:
        if value % 2 == 0:
            result = result + [value]
    return result
```
</div>
</div>

<div class="generation-result">共通の入力：<code>[3, 2, 4, 2]</code>　→　どちらの出力も <strong><code>[2, 4, 2]</code></strong></div>

| 変える箇所 | 変換例 |
| :--- | :--- |
| 処理の構造 | 内包表記 ↔ forループ ／ 直接return ↔ 一時変数を使う複数行 |
| 名前・補足 | 変数名の変更 ／ コメント・型注釈の有無 |
| 条件・並べ替え | 独立した条件の順序変更 ／ `reverse=True` ↔ 昇順ソート後の逆順（整数） |

**生成コードは、完全重複がなく、意味ASTの参照実装との結果一致を確認**

<!-- <div class="generation-note">生成器はCodexで実装してよい。変換ルールは人が確認し、意味を変えない範囲で適用する。</div> -->

<!--
コードは説明例。対象は整数リストを処理する単一関数で、クラス・再帰・非同期処理・外部アクセス・外部ライブラリは使わない。両例とも7行。右はappendを使わず、リストの連結で結果を作る。タスク共通のsolve(xs,k)形式に合わせるが、この操作ではkは使わない。順序・重複を保持し、xsを変更しない。
構造変換は意味ASTを固定して行う。生成器をCodexで実装できることと、学習用コードを毎回LLMに自由生成させることは区別する。
条件の交換は副作用や評価順依存がなく等価性が成立する場合に限る。reverse=Trueと昇順後の逆順はここでは整数リストの値によるソートが対象で、任意のキー付きソートの安定性まで同一とする主張ではない。
複数入力での一致は全入力に対する等価性の証明ではない。変換規則と参照実装による検査を併用。
根拠：../results/multi_operation_python_code_generation_results.md、../specifications/reference_interpreter.md。
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

<!-- --- -->
<!-- 1_class: compact -->

<!-- # 三つの大きさを、1 epochで比較する

**パラメータ**は、学習で調整するモデル内部の数値。

| 呼び名 | パラメータ数 | 今回の学習 |
| :--- | ---: | :--- |
| 1M | 約100万 | 合成データ全体を1回使う |
| 5M | 約500万 | 合成データ全体を1回使う |
| 15M | 約1,500万 | 合成データ全体を1回使う | -->

<!-- 合成データ全体を1回使う学習を、**1 epoch（1エポック）**と呼ぶ。 -->

<!-- 既存の学習済み重みを使わず、Transformerをゼロから学習する。 -->

<!--
正確には1,016,704、5,065,472、15,735,168パラメータ。共通の分割設定で学習した3モデルを本編に採用。Transformerは文章内の情報を参照しながら次の単位を予測するモデル。すべてDecoder-only、最大系列長256。
根拠：../results/trained_model_inventory.md
-->

---
<!-- _class: autoregressive ar-diagram -->
<!-- _header: "4. モデルと評価方法" -->

# 自己回帰：出力を次の入力に加えて繰り返す

decoder型transformerは、直前までの言葉から次の言葉を予測する。

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

**transformer**

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

**transformer**

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

<!-- 説明用に言葉で区切った例。実際はトークン単位で予測し、生成を繰り返す。 -->

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
<!-- _class: logit-overview -->
<!-- _header: "" -->

# 次の言葉の候補に確率が割り当てられる

「私は猫が…」の続きも、候補の点数を確率に直し、その中から1つ選ぶ。

<div class="lp-context">
<div class="lp-input">私 は 猫 が <strong>？</strong></div>
<span>→</span><div class="lp-model">decoder transformer </div><span>→</span>
<span>次の候補すべてに点数をつける</span>
</div>

<div class="lp-grid">
<div class="lp-panel lp-score">

## ① ロジット＝候補の点数

ロジットは確率ではなく、負にもなる

<div class="lp-row"><span>好き</span><div class="lp-track"><span class="lp-bar" style="width:60%"></span></div><b>3.0</b></div>
<div class="lp-row"><span>嫌い</span><div class="lp-track"><span class="lp-bar" style="width:40%"></span></div><b>2.0</b></div>
<div class="lp-row"><span>苦手</span><div class="lp-track"><span class="lp-bar" style="width:20%"></span></div><b>1.0</b></div>
<div class="lp-row"><span>机</span><div class="lp-track"><span class="lp-bar" style="left:0;width:40%"></span></div><b>−2.0</b></div>

<!-- <p>縦線は0。説明用に4候補と仮定。</p> -->
</div>
<div class="lp-arrow"><small>softmax</small>→</div>
<div class="lp-panel">

## ② 合計1となる確率

softmaxで変換。

<div class="lp-row"><span>好き</span><div class="lp-track"><span class="lp-bar" style="width:66.2272%"></span></div><b>66.2%</b></div>
<div class="lp-row"><span>嫌い</span><div class="lp-track"><span class="lp-bar" style="width:24.3636%"></span></div><b>24.4%</b></div>
<div class="lp-row"><span>苦手</span><div class="lp-track"><span class="lp-bar" style="width:8.9629%"></span></div><b>9.0%</b></div>
<div class="lp-row"><span>机</span><div class="lp-track"><span class="lp-bar" style="width:0.4462%"></span></div><b>0.4%</b></div>

<!-- <p>棒の長さは確率。順位は変わらない。</p> -->
</div>
<div class="lp-arrow"><small>選ぶ</small>→</div>
<div class="lp-panel">

## ③ 最も確率が高い候補を選ぶ

今回のBoku評価で使う選び方。

<div class="lp-pick"><strong>好き</strong>　66.2%</div>
<div class="lp-next">↓ 入力の末尾に追加<br>私は猫が<strong>好き</strong></div>

<p>新たな入力で、次のトークンを予測する。</p>
</div>
</div>

<div class="lp-summary">ロジットは<strong>softmax</strong>で、合計1となるそれぞれの確率に変換される。</div>

<!-- <div class="figure-reference">説明用の単語と数値。実際は全語彙を対象に、トークン（単語や単語の一部など）単位で生成する。<br>参考：<a href="https://www.3blue1brown.com/lessons/gpt/">3Blue1Brown：Softmax</a>・<a href="https://www.youtube.com/watch?v=yMQPQuz5WpA">指定動画</a>。</div> -->

<!--
自己回帰の説明とPythonコードの間をつなぐ概念図。添付SVGを構成の参考にし、文字・棒グラフ・矢印をすべてMarkdown内のHTML/CSSで記述。画像ファイルは参照しない。
説明用に語彙を「好き・嫌い・苦手・机」の4候補に限定し、ロジット[3,2,1,-2]をsoftmaxで変換。T=1の確率は約[66.2272,24.3636,8.9629,0.4462]%。表示は小数1桁に丸める。
実測出力やBokuの実際のトークン分割ではない。「上位3候補だけに絞る」処理でもない。
元SVGのくじ引きの例を、今回のBoku評価の最大確率選択に修正。実装では順位が同じなのでロジットのargmaxを使い、確率への変換を省略できる。
元SVGの「大小だけが意味を持つ」は不正確なので、ロジットの差が確率の比を決めると修正。
YouTubeの動画本文は直接取得できず、ユーザー添付のキャプチャと3Blue1Brownの公式テキスト解説を参照。
https://www.3blue1brown.com/lessons/gpt/ （Unembedding / Softmax）
https://www.youtube.com/watch?v=yMQPQuz5WpA
-->

---
<!-- _class: ar-code decoder-logits -->
<!-- 2_header: "4. モデルと評価方法" -->

# ① ロジットはDecoder Transformerモデルの出力

<div class="code-columns">
<div>

```python
# トークンIDを埋め込みへ変換
h = self.token_embedding(input_ids)
for block in self.blocks:
    # ① 正規化前のhを保存し、Attention後に足す
    residual = h
    h = block.attention_norm(h)
    h = block.attention(h)
    h = residual + h
    # ② 正規化前のhを保存し、MLP後に足す
    residual = h
    h = block.ffn_norm(h)
    h = block.feed_forward(h)
    h = residual + h
# 最後の正規化と、語彙ごとの点数への変換
h = self.final_norm(h)
logits = self.lm_head(h).float()  # ここがロジット
# 推論時はロジットを返す
if labels is None:
    return CausalLMOutput(logits=logits, loss=None)
```

**`lm_head` の出力が、全候補の点数（ロジット）。**

<div class="code-source">boku_nano.pyのforwardとブロック内部を展開して記載。<br>hidden_statesをhと表記し、残差加算を分けて示した。<br>図の①・②は、同じ番号のresidualをそのまま足す経路。</div>

</div>
<div class="decoder-flow">
<div class="decoder-output">logits <small>全候補の点数。確率ではない。</small></div>
<div class="decoder-up"></div>
<div class="decoder-model">
<div class="decoder-name">Decoder型<br>Transformer</div>
<div class="decoder-node decoder-head">lm_head（線形層）</div>
<div class="decoder-up"></div>
<div class="decoder-node decoder-norm">final_norm</div>
<div class="decoder-up"></div>
<div class="decoder-block residual-map">
<div class="decoder-block-title">n_layers 回繰り返す</div>
<div class="decoder-node decoder-norm" style="top:26px;height:28px">Add（＋②）</div>
<div class="decoder-up" style="top:54px"></div>
<div class="decoder-node decoder-mlp" style="top:66px;height:28px">MLP / Feed-forward</div>
<div class="decoder-up" style="top:94px"></div>
<div class="add-norm-group">
<div class="norm-step">Norm（RMSNorm）</div>
<div class="decoder-up"></div>
<div class="add-step">Add（＋①）</div>
</div>
<div class="decoder-up" style="top:168px"></div>
<div class="decoder-node decoder-attention" style="top:180px;height:36px">Multi-Head Self-Attention</div>
<div class="decoder-up" style="top:216px"></div>
<div class="decoder-node decoder-norm" style="top:228px;height:28px">Norm（RMSNorm）</div>
<div class="decoder-up" style="top:256px"></div>
<div class="skip-attn"><span>①</span></div>
<div class="skip-mlp"><span>②</span></div>
<div class="residual-dot" style="top:267px;background:#2877aa"></div>
<div class="residual-dot" style="top:137px;background:#8751a5"></div>
</div>
<div class="decoder-up"></div>
<div class="decoder-node decoder-embedding">token_embedding</div>
</div>
<div class="decoder-up"></div>
<div class="decoder-input">入力テキスト → Tokenizer → トークンID列</div>
</div>
</div>

<!--
図は下から上へ読む。全ノードと縦矢印の中心を50%に統一し、図はMD内のHTML/CSSのみで記述。
青の①は最初のNorm前からAttention後のAddへ。紫の②は①のAdd後かつFFNのNorm前からMLP後のAddへ。Add & Normの枠内で加算と正規化を分け、②の分岐位置を明示。
左コードはboku_nano.pyのモデルforward（389–400行）へTransformerBlock.forward（285–294行）をインライン展開した説明用の同値コード。hidden_statesをhへ改名し、残差をresidualへ保存。実装のMLP・Attention呼び出しと順序は同じ。
Pre-Norm実装に合わせ、最初のNorm、Attentionの残差加算＋FFN前NormをまとめたAdd & Norm、MLPの残差Addを示す。Post-Normへ処理を入れ替えていない。
MLP側のresidualはffn_norm前のh、Attention側はattention_norm前のhを保存する。「入力を残差加算」は正規化前の入力の意味。
attention内部のQ/K/V投影とRoPEは省略。入力ID列から上がモデルで、Tokenizerは前処理。lm_headはbias=Falseの線形層。softmaxはこのforwardには含まれない。
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

<!-- 点数0でも確率0ではない。$e^0=1$ だから。 -->

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

# ④ 温度は、候補の確率の偏りを調整する

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

<div class="code-source">evaluate_boku_nano_comparison.py：209–211行。<br>確率に従って抽選する場合の実装から抜粋。<br>今回のBoku評価では、最も確率が高いトークンを選ぶ。<br>参考：<a href="https://aman.ai/primers/ai/token-sampling/#temperature">Aman AI：Temperature</a></div>

</div>
<div>

## 抽選する場合の分布を温度で調整する

$$p_i(T)=\frac{e^{z_i/T}}{\sum_{j=1}^{V}e^{z_j/T}},\quad T>0$$

$T$：生成時に指定する温度。$T=1$ が基準。
学習済みの重みは変えず、ロジットを $T$ で割る。

AとBの点数が2と1なら、差は1。割った後の差は **$1/T$** になる。

| 温度 $T$ | Aの点数 $2/T$ | Bの点数 $1/T$ | 差 |
| ---: | ---: | ---: | ---: |
| 0.5 | 4 | 2 | 2 |
| 1 | 2 | 1 | 1 |
| 2 | 1 | 0.5 | 0.5 |

**$0<T<1$**：点数差が広がり、高確率の候補に集中する。

**$T>1$**：点数差が縮まり、分布が平らになる。

</div>
</div>

<!--
出典：../../scripts/model/evaluate_boku_nano_comparison.py 209–211行。正のtemperatureの検査は105–106行。
温度を変更しても学習済み重みは変わらない。softmaxに入力する相対的な点数差を調整する。
参考：https://aman.ai/primers/ai/token-sampling/#temperature （The Role of Temperature in Softmax）。Tが0に近づくと最大候補に集中（最大が一つの場合）、十分大きくなると有限語彙上の一様分布に近づく。T=0で除算しない。
数式と順位不変性は3Blue1Brown公式解説およびローカルPython実装でも照合。
-->

---
<!-- _class: ar-code temperature-example -->

# ⑤ 温度を上げると、低い確率の候補も選ばれやすくなる

ここでは3候補 **A=2、B=1、C=0** の点数を固定し、温度だけを変えて比べる。

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

**確率に従って抽選する場合**は、温度を上げると出力のばらつきが増える。

**最も確率が高い候補を選ぶ場合**は、正の温度を変えても選ぶ候補は同じ。

<div class="code-source">参考：<a href="https://aman.ai/primers/ai/token-sampling/#temperature">Aman AI：Temperature</a>。温度は正解率の向上を保証しない。</div>

<!--
参考：ユーザー提供の書籍画像 IMG_0947.jpg（p.124）、IMG_0948.jpg（p.125）。書名・著者は画像から未確認。説明の構成を参考にし、図は独自の3候補の数値からMarkdown/CSSで作成。
3候補の説明用の計算例。丸めにより合計100%にならない場合がある。
確率比ではsoftmaxの共通分母が相殺される。図はtemperatureだけを変えたsoftmaxの分布。
Pythonのsampling関数はT>0のみを受け付ける。T=0を渡して分岐する実装ではなく、greedyは別の実装。
出典：../../scripts/model/evaluate_boku_nano_comparison.py 105–106、209–211行、../../scripts/model/export_boku_nano_onnx.py 237行。
-->

---
<!-- _class: model-settings -->
<!-- _header: "" -->

# モデル構成とトークナイザー

<!-- 本編で比較する既存BPEの **1M・5M・15M**。Mは約100万パラメータを表す。 -->

| 項目 | 1M | 5M | 15M |
| :--- | ---: | ---: | ---: |
| **総パラメータ数** | **1,016,704** | **5,065,472** | **15,735,168** |
| 隠れ次元 `d_model` | 128 | 256 | 384 |
| 層数 `n_layers` | 3 | 5 | 8 |
| Attentionのhead数 | 4 | 4 | 6 |
| 1 headの次元 | 32 | 64 | 64 |
| FFNの中間次元 `d_ff` | 256 | 704 | 1,024 |
| この後に示す学習曲線 | 3 epoch | 1 epoch | 1 epoch |

## トークナイザーは共通

<div class="tokenizer-settings">
<strong>BPE</strong> ／ 語彙数 <strong>2,048</strong><br>
最小頻度 <code>min_frequency = 5</code> ／ 最大piece長 <code>max_token_length = 24</code>
</div>

<!-- <div class="settings-note">共通：最大系列長256 token、dropout 0、入力埋め込みと出力層の重み共有なし。<br>数値は保存済みのモデル設定と学習記録に基づく。</div> -->

<!--
モデル設定：../../data/models/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/model_config.json、../../data/models/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/model_config.json、../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/model_config.json。
パラメータ数：../results/trained_model_inventory.md。head_dim=d_model/n_heads。
BPE設定：../../config/tokenizer_bpe_2048.yaml。min_frequency=5、max_token_length=24、vocab_size=2048。
後続の1epoch比較には同じ1M構造の1epochチェックポイントもある。構造が同じならepoch数を変えてもパラメータ数は変わらない。
-->

---
<!-- _class: scientific -->
<!-- _header: "5. 学習結果と課題" -->

# 1M：3 epochまでの損失の推移

3 epochの学習。訓練損失は20 stepごと、検証損失は各epoch終了時の実測値。

![w:1100 h:380](figure/loss_1m_3epoch.png)

**val loss：1 epoch 0.8737 ／ 2 epoch 0.4691 ／ 3 epoch 0.4364**

<!-- 20 stepごとのvalidationは未記録。図は保存済みの3点を表示。 -->

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

<!-- val lossは終了時の1点。途中の検証値は保存されていない。 -->

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

<!-- val lossは終了時の1点。途中の検証値は保存されていない。 -->

<!--
保存された19点のtrain lossと、1点のvalidation lossをすべて使用。曲線はtrain lossだけであり、val lossの推移を補間していない。縦軸は保存済みの各モデルの図の対数目盛をそのまま使用する。モデルごとに範囲は異なる。最終stepは377。validationは24,040レコードのコード部分を評価。
使用図：../results/figures/training_loss_20step/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch.svg
根拠：../../data/models/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch/training_metrics.jsonl
-->

---
<!-- _class: test-summary -->
<!-- _header: "5. 学習結果と課題" -->

# モデル規模・学習回数による違い：五つのテスト別結果

各モデルの列は **合格数・合格率**。生成コードが各問の検査入力をすべて満たせば合格。

| テスト | 1M・1 epoch | 1M・3 epoch | 5M・1 epoch | 15M・1 epoch |
| :--- | ---: | ---: | ---: | ---: |
| 通常（24,040問） | 446問（1.86%） | 23,950問（99.63%） | 23,261問（96.76%） | **24,003問（99.85%）** |
| 組合せ汎化（13,400問） | 103問（0.77%） | **13,311問（99.34%）** | 12,657問（94.46%） | 13,188問（98.42%） |
| 日本語の言い換え（30問） | 2問（6.67%） | **15問（50.00%）** | 8問（26.67%） | **15問（50.00%）** |
| 同じ操作の反復（23,040問） | 508問（2.20%） | 22,945問（99.59%） | 22,370問（97.09%） | **22,971問（99.70%）** |
| 境界値（24,040問） | 408問（1.70%） | 23,950問（99.63%） | 23,261問（96.76%） | **24,003問（99.85%）** |

**1Mは3 epochで大きく改善。一方、言い換えは1M・3 epochと15M・1 epochでも50%。**

<div class="result-note">共通の既存BPE設定・単一seed。通常と境界値は同じ指示に異なる検査入力を使用。<br>ここでの固定5テストと、次に示す872問の組み合わせ汎化ベンチマークは別の評価。</div>

<!--
各結果は保存済みのモデル別評価報告から取得。合格率は合格数/評価件数から小数点以下2桁に丸めた。
根拠：../results/model_reports/boku_nano_1m_bpe_2048_minfreq5_maxlen24_1epoch.md、../results/model_reports/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch.md、../results/model_reports/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch.md、../results/model_reports/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch.md。
-->

---
<!-- _class: compact -->
<!-- _header: "6. ベンチマークで能力を測る" -->

# ベンチマークの役割と、自分の研究での作り方

**モデルの能力と限界を観測し、次に取り組む研究課題を明確にする。**
成功例だけで判断せず、共通の基準で能力の向上を定量的に確かめる。

| 設計・評価の手順 | 自分の研究で考えること |
| :--- | :--- |
| ① 測りたい能力を決める | 何ができるようになったかを確かめたいのか |
| ② 課題と正解基準を作る | 何を変え、何を固定し、どう正誤を判定するか |
| ③ 共通条件で測り、分析する | 成功・失敗の条件を調べ、比較条件と作成手順を記録する |
| ④ 次の課題につなげる | 残る誤りを調べ、高得点で差が見えなくなれば評価を見直す |

## 一例：組み合わせ汎化を測る

**学習済みの操作を、新しい組み合わせでも実行できるか。**
今回は既知の日本語表現を使って構成を変え、生成コードの実行結果で正誤を判定する。

<!--
組み合わせ汎化は、研究目的に合わせたベンチマーク設計の一例として紹介する。
評価872問と訓練192,900件の指示全文を照合した一致は0件。個々の表現・操作まで未知という意味ではない。Qwenの事前学習との重複は不明。
根拠：../results/composition_suite_20261008/report.md、../../data/benchmarks/composition_suite_20261008/questions.jsonl。
学生には、得点の比較に加え、測りたい能力・課題・採点基準・次の研究課題を自分で設計する考え方を伝える。
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

![bg contain](figure/composition_benchmark_with_5m_no_values/plot.png)

<!--
Boku・Qwenは条件A、greedy、全872問で各問題1生成・修復なし。Astraは独立チャット・low、各カテゴリ10問のみの参考値。Astraの温度は未指定でありgreedyとは主張しない。訓練回数・生成上限・実行基盤などは一致しない。
図：figure/composition_benchmark_with_5m_no_values/plot.png（棒の数値ラベルなし）
数値・実行条件・入力hash：figure/composition_benchmark_with_5m_no_values/values.json
作図：.venv/bin/python scripts/model/benchmark.py --models boku-15m-1epoch boku-5m-1epoch boku-1m-3epoch qwen3-1.7b --astra-reference --presentation --rows 1 --columns 9 --values no --output docs/report/figure/composition_benchmark_with_5m_no_values
-->

---
<!-- _class: compact benchmark-findings -->
<!-- _header: "6. 組み合わせ汎化を測る" -->

# 高得点の課題と、残る課題を分けて読む

| 問題の種類 | Boku 15M・1ep | Boku 5M・1ep | Boku 1M・3ep | Qwen3-1.7B | Astra・参考値 |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 初めて組み合わせる2操作 | 98 / 100 | 94 / 100 | 99 / 100 | 34 / 100 | 9 / 10 |
| 初めてのペアを含む3操作 | 96 / 100 | 95 / 100 | 100 / 100 | 27 / 100 | 10 / 10 |
| 異なる4操作を組み合わせる | 29 / 100 | 7 / 100 | 43 / 100 | 26 / 100 | 9 / 10 |

Astraだけ各カテゴリ10問。**分母と対象問題が異なるため、参考比較。**

- **今回の2・3操作の課題では、小規模モデルにも有望な結果がある。**
- Bokuの4操作では誤りが多く残る。どの操作を落とすか、順序を変えるかを分析する。
- 1Mは3epoch、5M・15Mは1epoch。生成条件も異なり、規模だけの優劣とは解釈しない。

<!--
2操作は10種類の意味ASTの表現違い。3操作と4操作は対応した同一問題ではないため、1操作の増加だけの効果を示す比較ではない。
Bokuは入力込み256 token、Qwenは最大512新規token・thinking無効。各構成単一seed。
根拠：figure/composition_benchmark_with_5m_no_values/values.json、../results/composition_suite_20261008/report.md
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
<!-- _header: "8. ブラウザデモ" -->
<!-- _class: closing -->

# デモ：学習済みモデルをブラウザで試す

ベンチマークでは、2・3操作で有望な結果が得られ、4操作では課題が残った。

**ここからは、自由な日本語を文型に整え、コードが生成されるまでを実演する。**

ONNX形式で保存したモデルを、ONNX Runtimeでブラウザ内実行。Python環境・推論サーバーは不要。

| デモの流れ | 役割 |
| :--- | :--- |
| ① 自由な日本語を入力 | 作りたい処理を伝える |
| ② Qwen3-0.6Bで文型を整える | 自由文を決められた文型（CNL）に変換。コードは書かない |
| ③ JavaScriptで指示を検査 | 24操作・最大3操作・定型文法に合うか確認 |
| ④ Boku-nanoでコードを生成 | 選択した学習済みモデルがPython関数を出力 |

<p class="demo-link"><a href="https://yuuono.github.io/bokunano/">ブラウザデモを開く</a></p>

<!--
デモの文型整形の効果は上記の実験評価値に含めていません。整形はQwen3-0.6B、生成は選択したBoku Nano。デモでは1 epochモデルを選択してください。自由な日本語をBoku Nano単体が扱うとは説明しないこと。
根拠：../../web/index.html、../../web/app.js、../procedures/boku_nano_onnx_web_demo.md
-->

---
<!-- _class: default -->
<!-- _header: "" -->

# Appendix：追加解析と補足資料

本編の評価を補足し、日本語表現への弱さとモデル内部の挙動を調べる。

| 内容 | 確かめること |
| :--- | :--- |
| A. 日本語表現への頑健性 | 言い換えや指示の冒頭を変えると、生成結果はどう変わるか |
| B. Attentionの可視化と介入 | どこを参照し、指示の情報が生成にどう寄与するか |
| C. 追加解析のまとめと限界 | 結果から言えることと、追加検証が必要なこと |
| D. 全体図 | データ生成・学習・評価・デモのつながり |

---
<!-- _header: "Appendix A. 日本語表現への頑健性" -->
<!-- _class: compact -->

# 全体が高精度でも、言い換えには弱い

1M・3 epochと15M・1 epochの比較。各セルは合格数（合格率）。

| テスト（評価件数） | 1M・3 epoch | 15M・1 epoch |
| :--- | ---: | ---: |
| 通常（24,040問） | 23,950（99.63%） | 24,003（99.85%） |
| 組合せ（13,400問） | 13,311（99.34%） | 13,188（98.42%） |
| 日本語の言い換え（30問） | **15（50.00%）** | **15（50.00%）** |
| 同じ操作の反復（23,040問） | 22,945（99.59%） | 22,971（99.70%） |
| 境界値（24,040問） | 23,950（99.63%） | 24,003（99.85%） |

**どちらも全体では約99.6%だが、未学習の言い換えは50%にとどまる。**

<!--
固定30表現の言い換えテストです。後の14操作の冒頭変更とは別の評価。
根拠：../results/model_reports/boku_nano_15m_bpe_2048_minfreq5_maxlen24_1epoch.md
-->


<!-- 1M・3 epochの追加根拠：../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/analysis.json、../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/prompt_prefix_comparison.json、../results/model_reports/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch.md。冒頭変更は2026-10-13に同じ14操作・33入力・seed=20260930・最大64新規tokenで評価。変更前の14生成コードが保存済み結果と一致することを確認。 -->
---
<!-- _header: "Appendix A. 日本語表現への頑健性" -->
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
<!-- _header: "Appendix A. 日本語表現への頑健性" -->
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
<!-- _header: "Appendix A. 日本語表現への頑健性" -->
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
<!-- _header: "Appendix A. 日本語表現への頑健性" -->
<!-- _class: result -->

# 5Mモデルでは、12件の合格が1件に減った

**5M・1 epoch。比較した14操作の合格数。**

| 指示の冒頭 | 合格数を表す図 | 合格数・合格率 |
| :--- | :--- | :--- |
| 整数リストxsから | ■■■■■■■■■■■■□□ | **12 / 14・85.7%** |
| 整数リストxsに対して、 | ■□□□□□□□□□□□□□ | **1 / 14・7.1%** |

■は合格1件、□は不合格1件。左から合格数を並べた図。

1M・3 epochでも、同じ14操作で **12 / 14 → 9 / 14** に低下した。

**冒頭を変えただけで、ほとんど正しく生成できなくなった。**

<!--
図は合格数・不合格数の内訳で、各操作の並びではありません。合格は固定33ケースの検査をすべて通ること。24操作全体の22→1を「から」だけの変更として扱わず、14操作に限定。
根拠：../results/attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/analysis.json とlegacy_taishite_prompt/analysis.json
-->


<!-- 1M・3 epochの追加根拠：../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/analysis.json、../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/prompt_prefix_comparison.json、../results/model_reports/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch.md。冒頭変更は2026-10-13に同じ14操作・33入力・seed=20260930・最大64新規tokenで評価。変更前の14生成コードが保存済み結果と一致することを確認。 -->
---
<!-- _header: "Appendix A. 日本語表現への頑健性" -->
<!-- _class: default -->

# 失敗例：偶数を残す指示を別の処理にした

変更後の指示：**整数リストxsに対して、偶数だけを残すsolve関数を書いてください。**

| | 指示どおり | 5M・1 epoch | 1M・3 epoch |
| :--- | :--- | :--- | :--- |
| 処理 | 偶数だけを残す | 順序を反転し、k以上を残す | 正の数だけを残す |
| 同じ検査入力 | `xs = [0], k = 1` | `xs = [0], k = 1` | `xs = [0], k = 1` |
| 出力 | `[0]` | `[]` | `[]` |

両モデルとも構文は正しいが、**指示された処理の意味が変わった。**

<!--
5Mモデルのatomic-000001の実際の生成コードと最初の不一致入力。変更前はvalue % 2 == 0で抽出し33ケース合格。変更後はlist(reversed(xs))の後にk <= xで抽出。評価器は全操作でsolve(xs, k)を要求するため、指示にkがなくても検査入力にはkがあります。
根拠：../results/attention_1epoch/boku_nano_5m_bpe_2048_minfreq5_maxlen24_1epoch/analysis.json とlegacy_taishite_prompt/analysis.json
-->


<!-- 1M・3 epochの追加根拠：../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/analysis.json、../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/prompt_prefix_comparison.json、../results/model_reports/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch.md。冒頭変更は2026-10-13に同じ14操作・33入力・seed=20260930・最大64新規tokenで評価。変更前の14生成コードが保存済み結果と一致することを確認。 -->
---
<!-- _header: "Appendix A. 日本語表現への頑健性" -->
<!-- _class: default -->

# 表現への強さは、モデルによって違う

冒頭だけを変えた14操作の合格数。学習回数も併記する。

| モデル | 「xsから」 | 「xsに対して、」 |
| :--- | ---: | ---: |
| 1M・3 epoch | 12 / 14 | 9 / 14 |
| 5M・1 epoch | **12 / 14** | **1 / 14** |
| 15M・1 epoch | 12 / 14 | 12 / 14 |

1M・3 epochでは3件減り、15M・1 epochでは合格数を保った。
**変化の大きさは、モデルと学習回数によって異なる。**

<!--
共通の分割設定。samplesをoperation_idで対応付け、指示が「整数リストxsから」で始まる14操作を集計。後半の文が同じと確認。合格数が同じでも生成コードの一致を主張しない。
根拠：../results/attention_1epoch/ 配下の5M・15Mのminfreq5_maxlen24_1epoch/analysis.jsonとlegacy_taishite_prompt/analysis.json
-->


<!-- 1M・3 epochの追加根拠：../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/analysis.json、../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/prompt_prefix_comparison.json、../results/model_reports/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch.md。冒頭変更は2026-10-13に同じ14操作・33入力・seed=20260930・最大64新規tokenで評価。変更前の14生成コードが保存済み結果と一致することを確認。 -->
---
<!-- _header: "Appendix A. 日本語表現への頑健性" -->
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
<!-- _header: "Appendix B. Attentionの可視化と介入" -->
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
図の読み方を説明した後の6ページは、同一の絶対値・降順の指示について、1M（1・3 epoch）・5M・15Mの全層・全ヘッドの生成中のattentionを表示する。Value ablationでは指示位置のKeyとattention weightを保ち、Valueだけを0にします。
根拠：../results/boku_nano_1epoch_attention_comparison.md
-->

---
<!-- _class: chart -->
<!-- _header: "Appendix B. Attentionの可視化と介入" -->

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
<!-- _header: "Appendix B. Attentionの可視化と介入" -->

# 1M・1 epoch：attention の可視化

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
<!-- _header: "Appendix B. Attentionの可視化と介入" -->

# 1M・3 epoch：attention の可視化

同じ指示：**各要素を絶対値にして、降順に並べる**

![w:1100 h:380](figure/attention_1m_3epoch_l1_l3.svg)

**生成結果：未定義の output を参照し、この指示では実行できなかった。**

3層・4 head、12生成step。色の濃さはモデル間で直接比較しない。

<!--
保存済みSVGのviewBoxを48 62 618 320に設定し、他のページと同じくヘッド別ヒートマップ領域だけを切り抜いて掲載。セル・色・順序は変更していない。1 epochと同じ指示全文：xsの各要素を絶対値にして降順に並べるsolve関数を書いてください。
生成コードはoutput = [abs(value) for value in output]で未初期化変数を参照する。単一指示の事例であり、全体性能を表すものではない。
根拠：../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/detail_analysis.json。
-->

---
<!-- _class: scientific attention-result -->
<!-- _header: "Appendix B. Attentionの可視化と介入" -->

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
<!-- _header: "Appendix B. Attentionの可視化と介入" -->

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
<!-- _header: "Appendix B. Attentionの可視化と介入" -->

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
<!-- _header: "Appendix B. Attentionの可視化と介入" -->

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
<!-- _header: "Appendix B. Attentionの可視化と介入" -->
<!-- _class: compact -->

# 指示の情報を止めると合格数が落ちる

学習時に準拠した文型で、24操作を診断。

| モデル | 通常の生成 | 指示の情報を止めた生成 |
| :--- | ---: | ---: |
| 1M・1 epoch | 3 / 24 | **0 / 24** |
| 1M・3 epoch | 19 / 24 | **0 / 24** |
| 5M・1 epoch | 22 / 24 | **0 / 24** |
| 15M・1 epoch | 22 / 24 | **2 / 24** |

**指示から受け取る情報が、操作の選択に寄与している。**

24操作の内部診断。冒頭変更の14操作、固定5テストとは別。

<!--
本編採用の4構成の実測値。全層で日本語指示位置のValueを0にした介入であり、指示自体を削除したものではない。各prompt33入力、greedy最大64 token。
根拠：../results/attention_1epoch/ 配下のminfreq5_maxlen24_1epoch/analysis.json
-->


<!-- 1M・3 epochの追加根拠：../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/analysis.json、../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/prompt_prefix_comparison.json、../results/model_reports/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch.md。冒頭変更は2026-10-13に同じ14操作・33入力・seed=20260930・最大64新規tokenで評価。変更前の14生成コードが保存済み結果と一致することを確認。 -->
---
<!-- _header: "Appendix C. 追加解析のまとめと限界" -->
<!-- _class: default -->

# 評価では、表現を変えた場合も確かめる

| 調べること | 今回、分かったこと |
| :--- | :--- |
| 決めた文型での動作 | 1M・3 epochも高い全体合格率を示した |
| 未学習の言い換え | 1M・3 epochと15M・1 epochは15 / 30 |
| 指示の冒頭の変更 | 1M・3 epochは12→9、5M・1 epochは12→1（各14操作） |

**一種類のプロンプトでの精度に加え、表現を変えても性能が保たれるかを評価する必要がある。**

<!--
先行研究は分類・二択質問、今回の実験は限定したコード生成。課題と指標が違うことに注意。
根拠：Appendix Aの各ページに記載した出典、Gan and Mori（2023）、Takayama et al.（2026）
-->


<!-- 1M・3 epochの追加根拠：../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/analysis.json、../results/attention_3epoch/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch/prompt_prefix_comparison.json、../results/model_reports/boku_nano_1m_bpe_2048_minfreq5_maxlen24_3epoch.md。冒頭変更は2026-10-13に同じ14操作・33入力・seed=20260930・最大64新規tokenで評価。変更前の14生成コードが保存済み結果と一致することを確認。 -->
---
<!-- _header: "Appendix C. 追加解析のまとめと限界" -->
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
<!-- _class: overview-original -->
<!-- _paginate: false -->
<!-- _header: "" -->

<div class="canvas">

<h1>Appendix D：Boku-nano 全体図</h1>
<div class="sub">日本語の限定的な指示から solve(xs, k) を生成する小型Decoder-only Transformer。意味ASTを起点に、データ生成・学習・評価をすべて同じ意味仕様でつなぐ。</div>

<div class="lane">
    <div class="lname"><span class="n">1</span><span class="t">意味</span></div>
    <div class="box rule">
        <b class="t">24の基本操作</b>
        抽出 10：偶数・奇数・&gt;k・≥k・&lt;k・≤k・kの倍数・正・負・ゼロ<br>
        変換 8：+k・−k・×k・2倍・3倍・符号反転・絶対値・二乗<br>
        並べ替え 3／切り出し 3
    </div>
    <div class="arrow">→</div>
    <div class="box rule">
        <b class="t">意味AST　12,720仕様</b>
        24操作から1〜3操作を順序付きで選ぶ（重複なし）<br>
        24 ＋ 24×23 ＋ 24×23×22 ＝ 12,720<br>
        <span class="mono">{"sequence": [{"filter": ["even"]}, {"map": ["add_k"]}]}</span><br>
        <span class="note">※日本語・コード・期待値・splitの共通の根拠</span>
    </div>
    <div class="arrow">→</div>
    <div class="box rule span-c3c4">
        <b class="t">参照インタプリタ（期待値の計算）</b>
        意味ASTを入力リストに適用して、正しい出力を計算する<br>
        operator・itertools・heapq・deque・while で実装し、生成されるsolve関数の表現空間の外側に置く<br>
        → 正解コードの検証（2）とhidden test採点（4）に使う<br>
        <span class="note">※参照実装と生成コードが同じ式を書いて誤りを共有しないため</span>
    </div>
</div>

<div class="conn">
    <div></div>
    <div>↓ 意味ASTを分割</div>
    <div></div>
    <div class="dash" style="text-align:right">⇣ 期待値で検証（参照インタプリタ → 正解コード生成）</div>
</div>

<div class="lane alt">
    <div class="lname"><span class="n">2</span><span class="t">データ</span></div>
    <div class="box rule">
        <b class="t">意味ASTの分割</b>
        12,720 から 670 を組合せ汎化へ<br>
        残り 12,050 をハッシュ順で分割<br>
        　train　9,646（1操作24は全部）<br>
        　validation　1,202<br>
        　通常テスト　1,202（境界値も流用）<br>
        別枠：同一操作の反復 1,152<br>
        　　　日本語言い換え 30指示
    </div>
    <div class="arrow">→</div>
    <div class="stack">
        <div class="box rule">
            <b class="t">正解コード生成（自作テンプレート）</b>
            style_specでfor／内包表記・変数名・スライス表記などを変える<br>
            277,440候補 → 構文・Safe-AST・signature・入力非破壊・<br>
            41入力で参照インタプリタと出力一致、を全部通したものだけ
        </div>
        <div class="box teacher">
            <b class="t">日本語指示生成</b>
            ルール：承認済み表現辞書（train 522件）を定型文へ連結<br>
            教師言い換え：Qwen3-4B-AWQ が意味と順序を保って言い換え<br>
            <span class="note">※Qwenは日本語だけを作り、コードや重みは提供しない</span>
        </div>
    </div>
    <div class="arrow">→</div>
    <div class="stack">
        <div class="box data">
            <b class="t">評価JSONL　108,590件</b>
            validation 24,040<br>
            正式5テスト 84,550問<br>
            hidden入力はコード作成時と別
        </div>
        <div class="box data">
            <b class="t">訓練JSONL　192,900件</b>
            1操作 460／2操作 8,680／3操作 183,760<br>
            ルール文 96,510＋言い換え 96,390<br>
            1意味ASTあたり原則20件
        </div>
    </div>
    <div class="arrow dot">┅</div>
    <div class="box data">
        <b class="t">1レコードの中身</b>
        instruction_ja（日本語指示）<br>
        semantic_ast（意味AST）<br>
        reference_code（正解コード）<br>
        style_spec・code_style<br>
        split・tests・verification<br>
        SHA-256・seed・生成器version<br>
        教師モデル由来かどうかの来歴
    </div>
</div>

<div class="conn">
    <div></div>
    <div>↓ train の指示とコード（訓練JSONLから）</div>
</div>

<div class="lane">
    <div class="lname"><span class="n">3</span><span class="t">学習</span></div>
    <div class="box rule">
        <b class="t">BPEトークナイザ</b>
        ByteLevel BPE・語彙 2,048<br>
        trainの日本語指示と正解コードだけから学習<br>
        （評価データは入れない）<br>
        min_frequency 5・最大token長 24<br>
        unknown token 0件
    </div>
    <div class="arrow">→</div>
    <div class="box model">
        <b class="t">学習系列とloss</b>
        <span class="mono">&lt;|bos|&gt;&lt;|task|&gt; {instruction_ja}</span><br>
        <span class="mono">&lt;|code|&gt; {reference_code}&lt;|eos|&gt;</span><br>
        lossはコードとEOSだけ（指示は条件として読むだけ）<br>
        batch 512件・1エポック 377 step・AdamW・bf16
    </div>
    <div class="arrow">→</div>
    <div class="box model span-c3c4">
        <b class="t">Decoder-only Transformer（ランダム初期値から学習）</b>
        RoPE・RMSNorm・SwiGLU・通常のMulti-Head Attention・最大系列長 256<br>
        　1M　d=128・3層・4 head<br>
        　5M　d=256・5層・4 head<br>
        　15M　d=384・8層・6 head<br>
        3つの規模を、それぞれ1エポック学習（RTX 5090）
    </div>
</div>

<div class="conn">
    <div></div>
    <div>↓ 学習済みモデル</div>
    <div></div><div></div><div></div><div></div><div></div>
    <div style="padding-left:120px">↓</div>
</div>

<div class="lane alt">
    <div class="lname"><span class="n">4</span><span class="t">評価</span></div>
    <div class="box eval span-c1c2">
        <b class="t">hidden test評価（正式5テスト 84,550問）</b>
        greedy生成 → 構文 → Safe-AST → signature → 隔離実行<br>
        → hidden入力すべてで参照インタプリタと同じ出力なら合格<br>
        文字列一致ではなく、実行結果で判定する<br>
        　通常 24,040　　組合せ汎化 13,400　　日本語言い換え 30<br>
        　同一操作の反復 23,040　　境界値 24,040<br>
        <span class="note">※attention診断の24問（1操作）はこれとは別の解析用テスト</span>
    </div>
    <div class="arrow">→</div>
    <div class="box eval">
        <b class="t">主な結果（1エポック・正式5テスト合計）</b>
        15M　99.56%（84,180 / 84,550）<br>
        5M　96.46%（81,557 / 84,550）<br>
        1M　1.74%（1,467 / 84,550）<br>
        <span class="note">※弱点：未学習の言い換え（15Mでも30問中15問）</span>
    </div>
    <div></div>
    <div class="box eval">
        <b class="t">内部解析</b>
        Q・K・Vを取り出しattentionを計算<br>
        head別のattention配分・Value norm・<br>
        BOS sink・attention rollout<br>
        head／位置ablation：NLL差（nat）と<br>
        再生成コードの合格数で因果を確認
    </div>
</div>

<div class="conn"></div>

<div class="lane">
    <div class="lname"><span class="n">5</span><span class="t">デモ</span></div>
    <div class="demo" style="grid-column: 2 / 9;">
        <div class="box rule">
            <b class="t">自由な日本語</b>
            例：全部プラスにして大きい順に並べて
        </div>
        <div class="arrow">→</div>
        <div class="box teacher">
            <b class="t">Qwen3-0.6B（ブラウザ）</b>
            自由文をCNLへ翻訳するだけ<br>
            追加学習なし・コードは書かない
        </div>
        <div class="arrow">→</div>
        <div class="box rule">
            <b class="t">JavaScript検査</b>
            24操作・最大3操作・<br>
            定型文法に合うか確認
        </div>
        <div class="arrow">→</div>
        <div class="box model">
            <b class="t">Boku1-nano ONNX</b>
            学習済みモデルを選んで<br>
            ブラウザ内でgreedy生成
        </div>
        <div class="arrow">→</div>
        <div class="box data">
            <b class="t">Pythonコード</b>
            <span class="mono">def solve(xs, k) -&gt; list[int]</span>
        </div>
    </div>
</div>

<div class="legend">
    <div><span class="k" style="background:#eaf2f8;border-color:#3d7591"></span>自作ルール・決定的な処理</div>
    <div><span class="k" style="background:#fbeee3;border-color:#c47a36"></span>Qwenを使う処理（日本語のみ）</div>
    <div><span class="k" style="background:#edf5eb;border-color:#4f8a4b"></span>データ・出力</div>
    <div><span class="k" style="background:#f0ebf8;border-color:#6b55a3"></span>学習・モデル</div>
    <div><span class="k" style="background:#fdf4dc;border-color:#a9821b"></span>評価・解析</div>
    <div style="color:#8a6d1f">⇣ 参照インタプリタによる検証</div>
</div>

</div>
