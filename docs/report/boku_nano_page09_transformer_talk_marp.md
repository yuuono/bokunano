---
marp: true
theme: default
size: 16:9
paginate: true
lang: ja
title: Transformerは何をしているのか：文字の予測からAttention・GPU・CPUへ
description: 本編9ページの補足。Shannonの文字実験、文脈と学習、Attention、GPUとCPUを20枚の図で説明。
style: |
  section { display:block; align-content:start; justify-content:start; padding:44px 62px 52px; background:#fff; color:#17212b; font-family:"Hiragino Sans","Noto Sans JP","Yu Gothic",sans-serif; font-size:27px; line-height:1.45; }
  h1 { font-size:38px; line-height:1.3; color:#245f8b; margin:0 0 14px; font-weight:700; letter-spacing:0; }
  p { margin:0; }
  .lead { font-size:28px; margin:0 0 24px; line-height:1.5; }
  strong { color:#245f8b; }
  a { color:#2877aa; text-decoration:none; }
  section::after { font-size:16px; color:#64748b; bottom:17px; right:26px; }
  .source { position:absolute; left:62px; right:90px; bottom:17px; font-size:15px; color:#687581; line-height:1.4; }
  .note { color:#596b7a; font-size:20px; line-height:1.5; }
  .caption { font-size:24px; color:#445769; margin-top:20px; }
  .em { color:#bd691d; font-weight:700; }
  .green { color:#327c50; }
  .purple { color:#685098; }
  .small { font-size:20px; }
  .token { display:inline-flex; min-width:66px; height:66px; padding:0 12px; align-items:center; justify-content:center; border:2px solid #92b1c8; background:#eaf3fb; border-radius:5px; font-size:29px; box-sizing:border-box; white-space:nowrap; }
  .token.new { background:#fff1df; color:#a75a15; border-color:#cf7d31; }
  .token.focus { background:#eaf6ee; color:#327c50; border-color:#76a885; }
  .token.dim { color:#b7c2cc; background:#f8fafb; border-color:#e1e6eb; }
  .token.query { color:#685098; background:#f0ecf8; border-color:#8a79c8; }
  .tokens { display:flex; gap:9px; align-items:center; }
  .arrow { font-size:39px; color:#718293; text-align:center; }
  .model { border:2px solid #8a79c8; background:#f0ecf8; color:#685098; padding:19px 14px; font-size:26px; text-align:center; border-radius:7px; }
  .flow-row { display:grid; grid-template-columns:440px 58px 225px 58px 150px; align-items:center; gap:10px; }
  .flow-labels { display:grid; grid-template-columns:498px 293px 150px; font-size:20px; color:#657686; margin-bottom:12px; }
  .flow-labels span:nth-child(2),.flow-labels span:nth-child(3) { text-align:center; }
  .ar { margin-top:33px; }
  .return { margin:10px 0 18px 345px; height:69px; color:#b96e2b; font-size:23px; display:flex; gap:20px; align-items:center; }
  .return .return-line { width:550px; height:28px; border-right:3px solid #cf7d31; border-bottom:3px solid #cf7d31; position:relative; align-self:flex-start; }
  .return .return-line:after { content:'↓'; position:absolute; left:-15px; bottom:-42px; font-size:42px; }
  .return span { position:absolute; margin-left:28px; margin-top:23px; background:white; padding:0 8px; }
  .ar-bottom { margin-top:26px; font-size:23px; }
  .alpha-layout { display:grid; grid-template-columns:650px 1fr; gap:64px; align-items:center; margin-top:30px; }
  .alphabet { display:grid; grid-template-columns:repeat(9,1fr); gap:10px; }
  .letter { height:70px; display:flex; align-items:center; justify-content:center; font-size:31px; border-bottom:3px solid #a9c7db; background:#edf4f9; }
  .letter.sel { background:#fff1df; border-color:#cf7d31; color:#a75a15; }
  .big-number { font-size:86px; font-weight:700; color:#245f8b; line-height:1.15; }
  .alpha-progress { display:flex; align-items:center; justify-content:center; gap:26px; margin-top:35px; font-size:37px; }
  .word { font-family:"SFMono-Regular",Menlo,monospace; letter-spacing:6px; }
  .prob-layout { display:grid; grid-template-columns:1fr 1fr; gap:65px; margin-top:30px; }
  .panel-title { font-size:27px; color:#245f8b; margin:0 0 18px; }
  .equal-bars { height:185px; display:flex; align-items:flex-end; gap:6px; border-bottom:2px solid #bccbd6; padding:0 10px; }
  .equal-bars i { flex:1; height:54px; background:#87b5d4; }
  .bar-row { display:grid; grid-template-columns:72px 1fr 82px; align-items:center; gap:12px; margin:13px 0; font-size:25px; }
  .bar-track { height:38px; background:#f0f3f6; }
  .bar-fill { height:100%; background:#81afd0; }
  .bar-fill.hot { background:#d98b42; }
  .bar-fill.green { background:#64a57a; }
  .prob-bottom { border-top:2px solid #dce5eb; margin-top:22px; padding-top:18px; font-size:28px; }
  .history-name { margin:0 0 22px; color:#245f8b; font-size:28px; }
  .history-name small { color:#6a7681; font-size:20px; margin-left:22px; }
  .history-row { display:grid; grid-template-columns:255px 390px 1fr; align-items:center; gap:28px; padding:17px 0; border-top:1px solid #dbe3e9; }
  .history-row .tokens { gap:7px; }
  .history-row .token { width:50px; min-width:50px; height:52px; padding:0; font-size:26px; }
  .history-label { font-size:24px; }
  .history-detail { font-size:23px; color:#506172; }
  .guess-rows { display:grid; grid-template-columns:240px 1fr 110px; align-items:center; row-gap:18px; margin:27px 0; }
  .guess-rows .word { font-size:38px; padding:12px 0; }
  .blank { display:inline-block; border-bottom:4px solid #ce8136; color:#ba681a; min-width:50px; text-align:center; }
  .guess-answer { color:#bc6b23; font-size:28px; }
  .context-line { display:flex; gap:10px; align-items:center; font-size:23px; margin-top:27px; }
  .context-line .long-rule { flex:1; border-top:3px solid #9dbbd0; }
  .markov-flow { display:grid; grid-template-columns:650px 70px 1fr; align-items:center; gap:20px; margin-top:55px; }
  .markov-prefix { font-family:Menlo,monospace; color:#b6c1cb; font-size:43px; letter-spacing:10px; }
  .markov-prefix .token { margin-left:16px; width:85px; height:85px; font-size:43px; }
  .next-options { display:flex; flex-direction:column; gap:20px; }
  .next-options .option { display:flex; align-items:center; gap:24px; }
  .next-options .line { width:90px; border-top:3px solid #8db4ce; }
  .next-options .line.heavy { border-width:10px; border-color:#d18a44; }
  .next-options .line.mid { border-width:6px; }
  .focus-label { width:550px; margin-top:22px; text-align:right; padding-right:8px; color:#327c50; font-size:24px; }
  .context-comparison { margin-top:25px; }
  .sentence-row { display:grid; grid-template-columns:575px 100px 1fr; align-items:center; height:142px; border-bottom:1px solid #dae4eb; }
  .sentence-row .tokens { gap:14px; }
  .sentence-row .token { min-width:90px; height:79px; font-size:33px; }
  .context-under { margin-top:27px; font-size:26px; }
  .learning-main { display:grid; grid-template-columns:230px 60px 250px 60px 1fr; align-items:center; margin:26px 0 18px; gap:12px; }
  .training-text { font-size:39px; text-align:center; }
  .answer { text-align:center; }
  .answer .token { width:90px; height:82px; font-size:44px; }
  .learning-check { display:flex; align-items:center; justify-content:center; gap:20px; font-size:24px; margin:15px 0 24px; padding:14px 0; border-top:1px solid #dce5eb; border-bottom:1px solid #dce5eb; }
  .learning-check .token { width:60px; min-width:60px; height:55px; font-size:32px; }
  .prediction { color:#245f8b; font-size:34px; text-align:center; }
  .learning-bars { display:grid; grid-template-columns:1fr 60px 1fr; gap:25px; align-items:center; margin:0 65px; }
  .learning-bars .bar-row { grid-template-columns:30px 1fr 85px; }
  .learning-loop { margin:22px 0 0; padding-top:15px; border-top:2px solid #dbe3eb; text-align:center; color:#685098; font-size:25px; }
  .att-sentence { display:flex; align-items:center; gap:9px; margin-top:20px; }
  .att-sentence .token { min-width:62px; font-size:26px; padding:0 12px; }
  .attention-body { display:grid; grid-template-columns:390px 170px 1fr; align-items:center; margin-top:33px; }
  .weight-row { display:grid; grid-template-columns:100px 1fr 63px; align-items:center; font-size:24px; gap:10px; margin:14px 0; }
  .weight-row .bar-track { height:25px; }
  .collect { border-left:4px solid #8a79c8; padding:16px 26px; }
  .collect strong { font-size:30px; color:#685098; }
  .collect p { font-size:24px; margin-top:13px; }
  .att-arrow { font-size:56px; color:#8a79c8; text-align:center; }
  .vector-flow { display:grid; grid-template-columns:240px 70px 1fr; align-items:center; gap:24px; margin-top:28px; }
  .vector-name { font-size:23px; text-align:right; }
  .vector-values { display:flex; gap:38px; font-size:36px; }
  .vector-values span { width:110px; text-align:center; padding:8px 0; border-bottom:3px solid #b6cbdc; background:#edf3f8; }
  .vector-values.purple span { background:#f2eef8; border-color:#a99bc7; }
  .multipliers { display:flex; gap:38px; margin:8px 0 8px 358px; }
  .multipliers span { width:110px; text-align:center; font-size:25px; color:#738393; }
  .dot-sum { display:flex; align-items:center; gap:24px; margin:26px 0 0 358px; font-size:33px; }
  .dot-sum .result { background:#fff1df; color:#a75a15; padding:9px 22px; font-size:42px; }
  .dot-caption { text-align:right; margin:18px 85px 0 0; color:#596b7a; font-size:22px; }
  .matrix-layout { display:grid; grid-template-columns:460px 1fr; align-items:center; gap:72px; margin-top:23px; }
  .matrix-wrap { padding-left:40px; position:relative; }
  .matrix-top { text-align:center; font-size:21px; color:#566c7c; margin-bottom:10px; }
  .matrix-left { position:absolute; left:-14px; top:125px; writing-mode:vertical-rl; font-size:21px; color:#566c7c; }
  .matrix { display:grid; grid-template-columns:repeat(10,1fr); gap:4px; width:350px; height:350px; }
  .matrix span { background:#a1c4df; }
  .matrix span.off { background:#f1f3f5; }
  .matrix span.hot { background:#dc964f; }
  .matrix-legend { display:flex; gap:25px; margin-top:14px; font-size:19px; }
  .matrix-legend i { display:inline-block; width:14px; height:14px; background:#a1c4df; margin-right:8px; }
  .matrix-legend i.off { background:#ebedf0; }
  .math-big { font-size:46px; color:#245f8b; line-height:1.5; }
  .math-big strong { font-size:65px; color:#b96d26; }
  .matrix-detail { font-size:25px; margin-top:15px; line-height:1.6; }
  .conditions { font-size:21px; color:#5e7180; margin:0 0 22px; }
  .players { display:flex; justify-content:center; gap:30px; margin-top:26px; }
  .player { width:63px; height:63px; border-radius:50%; border:2px solid #92b1c8; background:#eaf3fb; color:#245f8b; display:flex; align-items:center; justify-content:center; font-size:28px; }
  .timeline { margin-top:41px; display:grid; grid-template-columns:repeat(7,1fr); gap:8px; }
  .time-cell { height:82px; background:#eaf3fb; border-bottom:4px solid #91b7d2; display:flex; flex-direction:column; align-items:center; justify-content:center; font-size:24px; }
  .time-cell small { font-size:18px; color:#657787; }
  .duration { display:flex; justify-content:flex-end; align-items:baseline; gap:15px; margin-top:22px; color:#245f8b; font-size:28px; }
  .duration b { font-size:67px; color:#ba6c24; }
  .tournament-rounds { display:grid; grid-template-columns:1fr 56px 1fr 56px 1fr; gap:12px; align-items:center; margin-top:25px; }
  .round-title { font-size:25px; color:#245f8b; text-align:center; margin-bottom:14px; }
  .match-stack { height:226px; display:flex; flex-direction:column; justify-content:center; gap:10px; }
  .match { border:1px solid #a7c3d7; background:#eef5fa; padding:8px 12px; text-align:center; font-size:23px; }
  .round-time { padding-top:14px; border-top:3px solid #9dbed6; text-align:center; font-size:25px; }
  .wait { text-align:center; color:#738493; font-size:17px; }
  .wait b { display:block; font-size:33px; }
  .round-summary { display:flex; justify-content:space-between; align-items:baseline; margin-top:20px; font-size:25px; }
  .round-summary b { color:#b96d26; font-size:55px; }
  .clone-layout { display:grid; grid-template-columns:235px 1fr; gap:45px; align-items:center; margin-top:20px; }
  .clone-person { display:flex; flex-direction:column; align-items:center; gap:12px; }
  .clone-person .player { width:84px; height:84px; font-size:38px; border-color:#cf7d31; background:#fff1df; color:#a75a15; }
  .clone-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:11px; }
  .clone-grid .pair { padding:13px 0; text-align:center; border:1px solid #bdd0df; background:#eef5fa; font-size:21px; }
  .clone-grid .pair.with-a { background:#fff1df; border-color:#d99b61; color:#a75a15; }
  .clone-timing { display:flex; align-items:center; gap:22px; margin-top:27px; padding-top:18px; border-top:3px solid #b3cbdc; font-size:28px; }
  .clone-timing b { color:#b96d26; font-size:47px; }
  .gpu-layout { display:grid; grid-template-columns:390px 95px 1fr; align-items:center; gap:28px; margin-top:37px; }
  .work-grid { display:grid; grid-template-columns:repeat(8,minmax(0,1fr)); grid-template-rows:repeat(8,minmax(0,1fr)); gap:5px; width:352px; height:290px; }
  .work-grid span { background:#93bdd9; display:flex; align-items:center; justify-content:center; color:white; font-size:25px; line-height:1; min-height:0; }
  .work-grid .c1 { background:#aa99ce; }.work-grid .c2 { background:#83b696; }.work-grid .c3 { background:#dda35f; }
  .workers { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; }
  .worker { border-top:5px solid #93bdd9; padding-top:14px; text-align:center; font-size:23px; }
  .worker.c1 { border-color:#aa99ce; }.worker.c2 { border-color:#83b696; }.worker.c3 { border-color:#dda35f; }
  .worker-tasks { display:flex; flex-direction:column; gap:10px; margin-top:20px; color:#52697a; }
  .worker-tasks span { border-bottom:1px solid #dfe7ed; padding:5px; }
  .gpu-under { margin-top:27px; font-size:26px; }
  .serial-row { display:grid; grid-template-columns:210px 43px 292px 43px 160px; align-items:center; gap:17px; margin:25px 0 0 85px; }
  .parallel-box { border:2px solid #a695c6; background:#f7f4fb; padding:13px 16px; text-align:center; color:#685098; font-size:24px; }
  .mini-ops { display:grid; grid-template-columns:repeat(6,1fr); gap:5px; margin-top:8px; }
  .mini-ops span { background:#d4c9e7; font-size:19px; padding:3px; }
  .serial-result { text-align:center; }
  .serial-result .token { width:140px; height:78px; font-size:33px; }
  .serial-return { margin:12px 0 10px 390px; color:#b56b27; font-size:24px; }
  .serial-labels { display:flex; justify-content:space-between; margin:25px 55px 0; border-top:2px solid #dce5eb; padding-top:19px; font-size:25px; }
  .summary-main { margin-top:20px; display:grid; grid-template-columns:235px 65px 430px 65px 190px; align-items:center; gap:8px; }
  .summary-model { padding:18px 23px; border:2px solid #8a79c8; border-radius:7px; color:#685098; }
  .summary-model h2 { margin:0 0 17px; color:#685098; font-size:29px; }
  .summary-model p { font-size:24px; margin:8px 0; }
  .gpu-band { grid-column:3; margin-top:15px; border-top:4px solid #6da783; padding-top:12px; text-align:center; color:#327c50; font-size:24px; }
  .summary-return { margin:20px 65px 0 150px; border-bottom:3px solid #cf7d31; border-right:3px solid #cf7d31; padding:0 0 10px 0; text-align:center; color:#b56b27; font-size:25px; }
  .summary-return:before { content:'↙'; margin-right:20px; font-size:35px; }
  .summary-end { margin-top:16px; text-align:center; font-size:28px; }
  .sources-list { margin-top:23px; display:grid; grid-template-columns:110px 1fr; gap:18px 25px; font-size:24px; }
  .sources-list .year { color:#245f8b; font-size:30px; }
  .sources-list small { display:block; margin-top:4px; font-size:19px; color:#647583; }
  .sources-final { margin-top:25px; padding-top:20px; border-top:1px solid #d9e3eb; font-size:22px; }
  .example-label { font-size:20px; color:#596b7a; margin:0 0 16px; }
  .cpu-layout { display:grid; grid-template-columns:330px 90px 1fr; gap:25px; align-items:center; margin-top:28px; }
  .cpu-chip { border:2px solid #76a885; border-radius:8px; padding:18px; background:#fbfdfb; }
  .cpu-chip h2 { margin:0 0 17px; font-size:28px; color:#327c50; }
  .cpu-cores { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
  .cpu-core { padding:18px 0; text-align:center; background:#edf6ef; border:1px solid #bad3c2; font-size:24px; }
  .cpu-core.active { border:3px solid #56966d; color:#327c50; font-weight:700; }
  .cpu-zoom { text-align:center; color:#738493; font-size:18px; }
  .cpu-zoom b { display:block; font-size:42px; font-weight:400; }
  .cpu-inside { border:2px solid #76a885; border-radius:8px; padding:17px 22px; }
  .cpu-inside h2 { margin:0 0 13px; color:#327c50; font-size:27px; }
  .cpu-control { background:#f1edf8; padding:12px 17px; border-left:5px solid #9b87bd; }
  .cpu-control strong { color:#685098; font-size:25px; }
  .cpu-control p { font-size:21px; margin-top:5px; }
  .cpu-core-parts { display:grid; grid-template-columns:1fr 38px 1fr; align-items:center; gap:12px; margin-top:19px; }
  .cpu-part { border-top:4px solid #8fb7d3; padding-top:12px; font-size:24px; }
  .cpu-part.memory { border-color:#dba363; }
  .cpu-part small { display:block; font-size:20px; color:#596b7a; margin-top:7px; line-height:1.55; }
  .cpu-synthesis { margin-top:25px; padding-top:17px; border-top:1px solid #dce5eb; font-size:26px; }
  .cpu-condition { color:#596b7a; font-size:22px; margin:4px 0 25px; }
  .cpu-lane { display:grid; grid-template-columns:115px 1fr; gap:22px; align-items:center; margin:26px 0; }
  .cpu-lane-label { color:#327c50; font-size:31px; font-weight:700; }
  .cpu-lane-label.gpu { color:#245f8b; }
  .cpu-route { display:grid; grid-template-columns:1fr 48px 1fr 48px 1fr; align-items:center; gap:8px; }
  .cpu-stage { padding:16px 9px; background:#eef5fa; border:1px solid #acc8dc; font-size:24px; text-align:center; min-height:92px; box-sizing:border-box; display:flex; justify-content:center; flex-direction:column; }
  .cpu-stage.direct { grid-column:1 / 4; background:#edf6ef; border-color:#a8cbb3; }
  .cpu-stage small { display:block; margin-top:4px; font-size:19px; color:#596b7a; }
  .cpu-takeaway { margin-top:22px; padding-top:20px; border-top:2px solid #dce5eb; font-size:26px; }
  .cpu-takeaway p { margin:7px 0; }
  .sources-list { row-gap:12px; }
  .sources-final { margin-top:14px; padding-top:12px; }

---

<!-- _class: default -->

# 文章は、次の1個ずつ作る

<p class="lead">出した言葉を入力に戻し、同じモデルで続きを予測します。</p>

<div class="ar"><div class="flow-labels"><span>ここまでの文章</span><span>同じモデルを使う</span><span>次の言葉</span></div><div class="flow-row"><div class="tokens"><span class="token ">私</span><span class="token ">は</span><span class="token ">猫</span><span class="token ">が</span></div><div class="arrow">→</div><div class="model">Transformer</div><div class="arrow">→</div><span class="token new">好き</span></div><div class="return"><div class="return-line"></div><span>「好き」を後ろに付け足す</span></div><div class="flow-row"><div class="tokens"><span class="token ">私</span><span class="token ">は</span><span class="token ">猫</span><span class="token ">が</span><span class="token new">好き</span></div><div class="arrow">→</div><div class="model">Transformer</div><div class="arrow">→</div><span class="token focus">です</span></div></div><p class="ar-bottom">この繰り返しを <strong>自己回帰</strong> と呼びます。</p>

<div class="source">本編9ページの補足。言葉の区切り・出力は説明用の例。実際は「トークン」という単位で予測。</div>

<!--
伝えたいこと：長い文章も、次の1個を予測して付け足す繰り返しで生成する。
最初に話す一文：出した言葉を入力に戻し、同じモデルで続きを予測します。
話す順番：
上段の入力・出力を指し、「好き」を下段へ戻す。2つの箱は同じモデル。
実際の単位はトークン。1文字や単語の一部などで、この図は説明用の区切り。
次へ：仕組みを小さくするため、文字だけの世界で考える。
-->


---

<!-- _class: default -->

# 文字だけの世界で考える

<p class="lead">英字26文字と空白なら、候補は27種類です。</p>

<div class="alpha-layout"><div class="alphabet"><span class="letter ">a</span><span class="letter ">b</span><span class="letter ">c</span><span class="letter ">d</span><span class="letter ">e</span><span class="letter ">f</span><span class="letter ">g</span><span class="letter ">h</span><span class="letter ">i</span><span class="letter ">j</span><span class="letter ">k</span><span class="letter sel">l</span><span class="letter ">m</span><span class="letter ">n</span><span class="letter ">o</span><span class="letter ">p</span><span class="letter ">q</span><span class="letter ">r</span><span class="letter ">s</span><span class="letter ">t</span><span class="letter ">u</span><span class="letter ">v</span><span class="letter ">w</span><span class="letter ">x</span><span class="letter ">y</span><span class="letter ">z</span><span class="letter">空白</span></div><div><div class="big-number">27</div><p>種類から<br>次の1文字を選ぶ</p></div></div><div class="alpha-progress"><span class="word">hel</span><span class="arrow">→</span><span class="word">hel<span class="em">l</span></span><span class="arrow">→</span><span class="word">hell<span class="em">o</span></span></div>

<div class="source">ここでは説明を単純にするため、小文字26文字と空白だけを使う。</div>

<!--
伝えたいこと：候補を1つ選んで付け足す動作を、27文字で理解する。
最初に話す一文：英字26文字と空白なら、候補は27種類です。
話す順番：
タイルを指し、空白も1種類に数える。helの次にl、その次にoを選ぶ例を追う。
27は説明用の語彙。終了の合図を別に足すなら28種類になる。
次へ：すべてを同じ確率で選べばよいのか。
-->


---

<!-- _class: default -->

# 同じ27択でも、確率は変えられる

<p class="lead">「hel」の続きなら、「l」などを選びやすくします。</p>

<div class="prob-layout"><div><h2 class="panel-title">手がかりを使わない</h2><div class="equal-bars"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><p class="caption">27種類すべて 1/27<br><span class="note">棒1本が、1種類の文字</span></p></div><div><h2 class="panel-title">「hel」を手がかりにする</h2><div class="bar-row"><span>l</span><div class="bar-track"><div class="bar-fill hot" style="width:65%"></div></div><span>65%</span></div><div class="bar-row"><span>p</span><div class="bar-track"><div class="bar-fill " style="width:15%"></div></div><span>15%</span></div><div class="bar-row"><span>d</span><div class="bar-track"><div class="bar-fill " style="width:5%"></div></div><span>5%</span></div><p class="note">残り24種類の合計：15%</p><p class="caption">hello / help / held などの続き</p></div></div><p class="prob-bottom">候補の数は同じ。変わるのは、<strong>候補ごとの確率</strong>。</p>

<div class="source">確率は説明用の仮の数値。図の文字列は、出力を保証するものではない。</div>

<!--
伝えたいこと：候補数と選択確率を区別する。
最初に話す一文：「hel」の続きなら、「l」などを選びやすくします。
話す順番：
均等な棒と偏った棒を比べる。右は説明のための仮の数値で、実測ではない。
確率を使って選ぶ方法も、最高確率を選ぶ方法もある。詳しい選び方は本編10ページ以降へ。
次へ：この「文字の選び方を変える」考え方には、古い研究がある。
-->


---

<!-- _class: default -->

# 1948年：英語に似た文字列を作る

<p class="lead">シャノンは、文字の頻度やつながりを使って、英語に似た文字列を作りました。</p>

<p class="history-name">Claude E. Shannon <small>E = Elwood</small></p><p class="example-label">以下は仕組みを示す自作の図（原論文の出力ではありません）。</p><div class="history-row"><div class="history-label">同じ確率で選ぶ</div><div class="tokens"><span class="token ">A</span><span class="token ">Q</span><span class="token ">Z</span><span class="token ">空白</span><span class="token ">X</span><span class="token ">J</span></div><div class="history-detail">どの文字も同じ出やすさ</div></div><div class="history-row"><div class="history-label">文字の頻度を使う</div><div class="tokens"><span class="token ">E</span><span class="token ">T</span><span class="token ">A</span><span class="token ">O</span><span class="token ">E</span><span class="token ">N</span></div><div class="history-detail">よく出る文字を選びやすく</div></div><div class="history-row"><div class="history-label">前の文字も使う</div><div class="tokens"><span class="token ">Q</span><span class="token ">→</span><span class="token ">U</span></div><div class="history-detail">文字のつながりを使う</div></div>

<div class="source">図は自作の説明例。原典：<a href="https://www.cs.yale.edu/homes/yry/readings/general/shannon1948.pdf">Shannon（1948）§3</a> ／ 氏名：<a href="https://cdn.libraries.mit.edu/dissemination/diponline/AC0069_NewReleases/NewsRelease_1960/AC0069_1967/AC0069_196702_001.pdf">MIT公式略歴</a></div>

<!--
伝えたいこと：シャノンが1948年に、文字の頻度やつながりを使う英語の近似を示したこと。
最初に話す一文：シャノンは、文字の頻度やつながりを使って、英語に似た文字列を作りました。
話す順番：
名前はClaude Elwood Shannon。Eで合っている。
1948年論文は、26英字と空白を使い、等確率、文字頻度、直前の文字や単語のつながりを取り込む近似を示した。
図の文字列とQ→Uは仕組みを示す自作例。原論文の生成結果や頻度の再現ではない。
原論文のfirst-order approximationは文字を独立に頻度で選ぶ意味で、一階マルコフ連鎖と同義ではない。
出典：https://www.cs.yale.edu/homes/yry/readings/general/shannon1948.pdf §3、再録p.7。氏名：https://cdn.libraries.mit.edu/dissemination/diponline/AC0069_NewReleases/NewsRelease_1960/AC0069_1967/AC0069_196702_001.pdf PDF2ページ。
次へ：人が続きを当てるときにも、前の文章が手がかりになる。
-->


---

<!-- _class: default -->

# 1951年：次の文字を、人に当ててもらう

<p class="lead">シャノンは、英語の続きを人に予測させ、1文字あたりの情報量を推定しました。</p>

<p class="example-label">以下は考え方を伝える自作例（原論文の実験問題ではありません）。</p><div class="guess-rows"><span class="small">手がかりなし</span><span class="word"><b class="blank">?</b></span><span></span><span class="small">前の文字が見える</span><span class="word">HAPP<b class="blank">?</b></span><span class="guess-answer">Y？</span><span class="small">前の言葉も見える</span><span class="word">HAPPY BIRTHDA<b class="blank">?</b></span><span class="guess-answer">Y！</span></div><div class="context-line"><span>前の文章</span><span class="long-rule"></span><span>次の文字を考える材料</span></div>

<div class="source">図は自作例。1951年の研究は人による予測実験。原典：<a href="https://sites.socsci.uci.edu/~rfutrell/teaching/itl-davis/readings/shannon1951prediction.pdf">Prediction and Entropy of Printed English, §3</a></div>

<!--
伝えたいこと：シャノンが1951年に、人による次文字予測を使って英語の情報量を推定したこと。
最初に話す一文：シャノンは、英語の続きを人に予測させ、1文字あたりの情報量を推定しました。
話す順番：
最初は？だけを指し、次にHAPP?、最後にHAPPY BIRTHDA?を読む。これは直感のための自作例で、実験問題の転載ではない。
文字をどれくらい予測できるかを使って、1文字あたりの情報量（エントロピー）を推定した研究。
1951年の実験は人による予測。TransformerやAttentionを発明した話ではない。
原典：https://sites.socsci.uci.edu/~rfutrell/teaching/itl-davis/readings/shannon1951prediction.pdf §3、誌面pp.54–56（PDF5–7ページ）。
次へ：コンピューターに、どれくらい前まで見せるか。
-->


---

<!-- _class: default -->

# 直前の1文字だけを見る方法

<p class="lead">直前の1文字だけで次の確率を決めると、単純なマルコフ連鎖になります。</p>

<div class="markov-flow"><div><div class="markov-prefix">…h e <span class="token focus">l</span></div><p class="focus-label">使うのは、この1文字</p></div><div class="arrow">→</div><div class="next-options"><div class="option"><i class="line heavy"></i><span class="token new">l</span></div><div class="option"><i class="line mid"></i><span class="token ">e</span></div><div class="option"><i class="line"></i><span class="token ">空白</span></div></div></div><p class="caption">この例では、「l」より前の文字は使いません。</p>

<div class="source">「状態＝直前の1文字」とした一階マルコフ連鎖の例。文字の頻度・枝の太さは模式図。</div>

<!--
伝えたいこと：一階マルコフ連鎖の例では、状態を直前1文字として次の確率を決める。
最初に話す一文：直前の1文字だけで次の確率を決めると、単純なマルコフ連鎖になります。
話す順番：
灰色の文字は使わず、最後のlだけを見る。枝の太さは確率の違いの模式図で、実測の頻度ではない。
確率に応じて次を選ぶ例。1個ずつ生成するだけではマルコフ性は決まらない。
履歴全体を状態と定義する表現も可能だが、ここでは状態を直前1文字と明示する。
次へ：直前が同じでも、もっと前が違えば続きを変えたい。
-->


---

<!-- _class: default -->

# 最後の文字が同じでも、続きは変わる

<p class="lead">もっと前の言葉も使うと、続きを考える材料が増えます。</p>

<div class="context-comparison"><div class="sentence-row"><div class="tokens"><span class="token focus">私</span><span class="token focus">は</span><span class="token focus">猫</span><span class="token query">が</span></div><div class="arrow">→</div><span class="token new">好き</span></div><div class="sentence-row"><div class="tokens"><span class="token focus">強い</span><span class="token focus">風</span><span class="token query">が</span></div><div class="arrow">→</div><span class="token new">吹く</span></div></div><p class="context-under">最後はどちらも「が」。<strong>その前の話</strong>が、次の予測に役立ちます。</p>

<div class="source">文脈は「ここまでの文章」。区切りと続きは、理解のための説明例。</div>

<!--
伝えたいこと：長い文脈を使う必要を、同じ直前文字の異なる続きを通して理解する。
最初に話す一文：もっと前の言葉も使うと、続きを考える材料が増えます。
話す順番：
がだけを指してから、猫と風を指す。好き・吹くは自然な続きの一例で一意の正解ではない。
Transformerは扱える文脈の範囲で過去の情報を使う。
次へ：こうした文脈と続きの関係を、どうやって身につけるか。
-->


---

<!-- _class: default -->

# 学習は、続きを当てる練習

<p class="lead">実際の続きを見て、その言葉の確率を高くするように調整します。</p>

<div class="learning-main"><div class="training-text"><span class="word">hel</span><p class="note">途中までを見せる</p></div><div class="arrow">→</div><div class="model">予測するモデル</div><div class="arrow">→</div><div class="prediction">l：20%<p class="note">モデルの予測</p></div></div><div class="learning-check"><span>教材の正解</span><span class="token new">l</span><span>と比べて、モデルの中の数字を調整</span></div><div class="learning-bars"><div><h2 class="panel-title">調整する前</h2><div class="bar-row"><span>l</span><div class="bar-track"><div class="bar-fill " style="width:20%"></div></div><span>20%</span></div></div><div class="arrow">→</div><div><h2 class="panel-title">調整を重ねた後</h2><div class="bar-row"><span>l</span><div class="bar-track"><div class="bar-fill hot" style="width:65%"></div></div><span>65%</span></div></div></div><p class="note" style="text-align:center;margin-top:16px">たくさんの文章で、この練習を繰り返します。</p>

<div class="source">20%・65%は学習の方向を示す仮の数値。ほかの候補の棒は省略。学習の実装：scripts/model/boku_nano.py</div>

<!--
伝えたいこと：学習は実際の次トークンの確率を上げるようモデルのパラメータを調整すること。
最初に話す一文：実際の続きを見て、その言葉の確率を高くするように調整します。
話す順番：
この教材はhelloを含むので、helの次の正解はl。予測した確率を正解と比べて数字を更新する。
数値は説明用で、1回の更新で必ず20から65になる意味ではない。
学習中の更新と、生成時に既存の重みを使う処理を区別する。
次へ：学習したモデルの中で、前の情報を集める仕組みがAttention。
-->


---

<!-- _class: default -->

# Attentionは、前の情報を取り込む

<p class="lead">どの位置の情報を、どのくらい取り込むかを計算します。</p>

<div class="att-sentence"><span class="token ">太郎</span><span class="token ">は</span><span class="token new">りんご</span><span class="token ">を</span><span class="token ">買った</span><span class="token ">。</span><span class="token query">それ</span></div><div class="attention-body"><div><div class="weight-row"><span>りんご</span><div class="bar-track"><div class="bar-fill hot" style="width:60%"></div></div><span>60%</span></div><div class="weight-row"><span>太郎</span><div class="bar-track"><div class="bar-fill " style="width:10%"></div></div><span>10%</span></div><div class="weight-row"><span>買った</span><div class="bar-track"><div class="bar-fill " style="width:20%"></div></div><span>20%</span></div><div class="weight-row"><span>ほか</span><div class="bar-track"><div class="bar-fill " style="width:10%"></div></div><span>10%</span></div></div><div class="att-arrow">→</div><div class="collect"><strong>「それ」の情報に混ぜる</strong><p>「りんご」の情報を多めに<br>ほかの位置の情報も取り込む</p><p class="note">この処理を使って、続きを予測する。</p></div></div>

<div class="source">重みは説明用。実測ではなく、次の言葉を選ぶ確率とも別。原典：<a href="https://arxiv.org/html/1706.03762v7">Transformer（2017）§3.2</a></div>

<!--
伝えたいこと：Attentionは勝者を1つ選ぶのではなく、関連度から重みを決めて複数の情報を混ぜる。
最初に話す一文：どの位置の情報を、どのくらい取り込むかを計算します。
話す順番：
それが何を指すか考えるにはりんごが手がかりになる。数字の列で表された情報を、計算した重みに従って混ぜる。
60・10・20・10は仕組みのための仮の重み。実測Attentionでも、出力語彙の予測確率でもない。
Attention以外の処理も通して出力候補の確率が決まる。人のように意味を判断していると断言しない。
出典：https://arxiv.org/html/1706.03762v7 §3.2。次へ：その重みのもとになる関係の点数は、数字で計算する。
-->


---

<!-- _class: default -->

# 関係の点数は、掛け算と足し算で出す

<p class="lead">言葉を数の列で表して、対応する数を掛け、合計します。</p>

<div class="vector-flow"><div class="vector-name">「それ」側の数の列<br><span class="note">Query</span></div><div class="arrow">→</div><div class="vector-values purple"><span>1</span><span>2</span><span>1</span></div></div><div class="multipliers"><span>×</span><span>×</span><span>×</span></div><div class="vector-flow" style="margin-top:0"><div class="vector-name">「りんご」側の数の列<br><span class="note">Key</span></div><div class="arrow">→</div><div class="vector-values"><span>3</span><span>1</span><span>2</span></div></div><div class="dot-sum"><span>3</span><span>＋</span><span>2</span><span>＋</span><span>2</span><span>＝</span><span class="result">7</span></div><p class="dot-caption">1組の関係を表す「点数」</p>

<div class="source">3個の数は説明用の仮値。実際は点数の調整などをしてから重みに変換。原典：<a href="https://arxiv.org/html/1706.03762v7">§3.2</a></div>

<!--
伝えたいこと：大量の行列計算が、言葉の数値表現の内積から生じることを理解する。
最初に話す一文：言葉を数の列で表して、対応する数を掛け、合計します。
話す順番：
上と下の対応する数を掛けて、最後に足す。1×3 + 2×1 + 1×2 = 7。
数の列は学習した変換で作る。この3要素は説明用で、単語の実際の埋め込みではない。
実際のAttentionではスケール調整・未来のマスク・softmaxなどを経て重みを作り、Valueの情報を混ぜる。
次へ：この1組の計算を、多くの位置の組に対して行う。
-->


---

<!-- _class: default -->

# 文章が長いほど、調べる組が増える

<p class="lead">入力文をまとめて処理するとき、各位置と各位置の関係を計算します。</p>

<div class="matrix-layout"><div class="matrix-wrap"><p class="matrix-top">参照する位置</p><span class="matrix-left">今、計算する位置</span><div class="matrix"><span class=""></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class=""></span><span class=""></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class=""></span><span class=""></span><span class=""></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class="off"></span><span class="off"></span><span class="off"></span><span class="off"></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class="off"></span><span class="off"></span><span class="off"></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class="off"></span><span class="off"></span><span class=""></span><span class=""></span><span class=""></span><span class="hot"></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class="off"></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span><span class=""></span></div><div class="matrix-legend"><span><i></i>参照できる</span><span><i class="off"></i>未来は見ない</span></div></div><div><p class="math-big">1万 × 1万<br>表全体で <strong>1億</strong> マス</p><p class="matrix-detail">未来を除く有効な組は約5,000万。<br>各マスで、掛け算・足し算。</p><p class="note" style="margin-top:15px">図は小さくした模式図。<br>1万個は規模を示す仮の設定。</p></div></div>

<div class="source">学習・長い入力文をまとめて処理する場面。生成の各回に表全体を作り直すという意味ではない。<a href="https://arxiv.org/html/1706.03762v7">原典 §4</a></div>

<!--
伝えたいこと：全位置間の関連度計算の組数が、文脈長の二乗で増えると理解する。
最初に話す一文：入力文をまとめて処理するとき、各位置と各位置の関係を計算します。
話す順番：
横は参照する位置、縦は今計算する位置。右上の灰色は未来なので参照しない。
N=10,000なら正方形の枠は1億マス、有効な組はN(N+1)/2=50,005,000。
1ヘッド64次元で表全面を通常の方法で計算する仮定なら掛け算64億回。実装で仕事量は変わる。
KVキャッシュを使う生成では、新しい位置の計算に過去のKey/Valueを再利用できる。毎回この表全体を作り直すとは言わない。
次へ：同時にできる仕事を増やすと、時間はどうなるか。
-->


---

<!-- _class: default -->

# 8人の勝ち抜き戦を、1試合ずつ

<p class="lead">1会場で7試合を順番に行うと、7分かかります。</p>

<p class="conditions">8人から最強を1人決める。1試合1分、強い人が必ず勝つ。</p><div class="players"><span class="player">A</span><span class="player">B</span><span class="player">C</span><span class="player">D</span><span class="player">E</span><span class="player">F</span><span class="player">G</span><span class="player">H</span></div><div class="timeline"><div class="time-cell">試合1<small>0〜1分</small></div><div class="time-cell">試合2<small>1〜2分</small></div><div class="time-cell">試合3<small>2〜3分</small></div><div class="time-cell">試合4<small>3〜4分</small></div><div class="time-cell">試合5<small>4〜5分</small></div><div class="time-cell">試合6<small>5〜6分</small></div><div class="time-cell">試合7<small>6〜7分</small></div></div><div class="duration"><span>7試合 × 1分</span><b>7分</b></div>

<div class="source">計算のたとえ。準備・移動時間は省略。CPUにも複数の仕事を同時に進める機能がある。</div>

<!--
伝えたいこと：仕事を順番に処理する場合の総仕事量と所要時間を把握する。
最初に話す一文：1会場で7試合を順番に行うと、7分かかります。
話す順番：
準備・移動は省く。実力は固定し、引き分けや番狂わせはない。
勝ち抜きは1試合で1人脱落するので、8人を1人にするには7試合。
次へ：会場を4つ用意し、独立した試合を同時に始める。
-->


---

<!-- _class: default -->

# 会場を増やして、同時に進める

<p class="lead">同じラウンドを同時に行えば、7試合でも3分で終わります。</p>

<div class="tournament-rounds"><div><div class="round-title">1回戦</div><div class="match-stack"><div class="match">A 対 B</div><div class="match">C 対 D</div><div class="match">E 対 F</div><div class="match">G 対 H</div></div><div class="round-time">0〜1分</div></div><div class="wait">勝者を待つ<b>→</b></div><div><div class="round-title">準決勝</div><div class="match-stack"><div class="match">勝者 対 勝者</div><div class="match">勝者 対 勝者</div></div><div class="round-time">1〜2分</div></div><div class="wait">勝者を待つ<b>→</b></div><div><div class="round-title">決勝</div><div class="match-stack"><div class="match">勝者 対 勝者</div></div><div class="round-time">2〜3分</div></div></div><div class="round-summary"><span>4試合 ＋ 2試合 ＋ 1試合 ＝ 7試合</span><span>経過時間 <b>3分</b></span></div>

<div class="source">1試合1分、強さは固定。各ラウンドの試合を同時に開催できるとした例。</div>

<!--
伝えたいこと：独立した仕事は同時に実行できるが、結果の依存がある段階は順番に進む。
最初に話す一文：同じラウンドを同時に行えば、7試合でも3分で終わります。
話す順番：
縦に並ぶ試合は同時に実施する。横に進むには前の勝者を待つ。
総試合数は7のまま。最初4会場、次2会場、最後1会場で3段階。
次へ：選手のクローンとさらに多くの会場があれば、総当たりを同時にできる。
-->


---

<!-- _class: default -->

# クローンがいれば、総当たりも一斉に

<p class="lead">全員が7試合へ同時参加できれば、28試合を1分で行えます。</p>

<div class="clone-layout"><div class="clone-person"><span class="player">A</span><p class="small">Aも7か所で<br>同時に対戦</p><span class="arrow">→</span><p class="note">ほかの選手も同様</p></div><div class="clone-grid"><div class="pair with-a">A 対 B</div><div class="pair with-a">A 対 C</div><div class="pair with-a">A 対 D</div><div class="pair with-a">A 対 E</div><div class="pair with-a">A 対 F</div><div class="pair with-a">A 対 G</div><div class="pair with-a">A 対 H</div><div class="pair ">B 対 C</div><div class="pair ">B 対 D</div><div class="pair ">B 対 E</div><div class="pair ">B 対 F</div><div class="pair ">B 対 G</div><div class="pair ">B 対 H</div><div class="pair ">C 対 D</div><div class="pair ">C 対 E</div><div class="pair ">C 対 F</div><div class="pair ">C 対 G</div><div class="pair ">C 対 H</div><div class="pair ">D 対 E</div><div class="pair ">D 対 F</div><div class="pair ">D 対 G</div><div class="pair ">D 対 H</div><div class="pair ">E 対 F</div><div class="pair ">E 対 G</div><div class="pair ">E 対 H</div><div class="pair ">F 対 G</div><div class="pair ">F 対 H</div><div class="pair ">G 対 H</div></div></div><div class="clone-timing"><span>28会場で同時に</span><b>試合は1分</b><span class="arrow">→</span><span>結果を集計</span></div><p class="caption">仕事の数が増えても、<strong>同時にできれば待ち時間は短くなる</strong>。</p>

<div class="source">強さは固定。クローン・28会場を使える理想化した例。準備時間は省略し、集計時間は別。</div>

<!--
伝えたいこと：総仕事量と経過時間が異なることを、理想的な並列実行から理解する。
最初に話す一文：全員が7試合へ同時参加できれば、28試合を1分で行えます。
話す順番：
橙の7組がAの参加する試合。各人が同じ強さのクローンで7試合へ同時参加し、28会場ある前提。
28=8×7/2。試合部分は1分だが、勝者の確定には結果の集計が必要。
総当たりが常に最速という主張ではない。資源の上限や集計にも時間がかかる。
次へ：GPUでは、この分担を多数の数字の計算に使う。
-->


---

<!-- _class: default -->

# GPUは、計算をたくさんの担当に分ける

<p class="lead">同時にできる掛け算・足し算を、まとめて進めます。</p>

<div class="gpu-layout"><div><div class="work-grid"><span class="c0">×</span><span class="c0">×</span><span class="c0">×</span><span class="c0">×</span><span class="c1">×</span><span class="c1">×</span><span class="c1">×</span><span class="c1">×</span><span class="c0">×</span><span class="c0">×</span><span class="c0">×</span><span class="c0">×</span><span class="c1">×</span><span class="c1">×</span><span class="c1">×</span><span class="c1">×</span><span class="c0">×</span><span class="c0">×</span><span class="c0">×</span><span class="c0">×</span><span class="c1">×</span><span class="c1">×</span><span class="c1">×</span><span class="c1">×</span><span class="c0">×</span><span class="c0">×</span><span class="c0">×</span><span class="c0">×</span><span class="c1">×</span><span class="c1">×</span><span class="c1">×</span><span class="c1">×</span><span class="c2">×</span><span class="c2">×</span><span class="c2">×</span><span class="c2">×</span><span class="c3">×</span><span class="c3">×</span><span class="c3">×</span><span class="c3">×</span><span class="c2">×</span><span class="c2">×</span><span class="c2">×</span><span class="c2">×</span><span class="c3">×</span><span class="c3">×</span><span class="c3">×</span><span class="c3">×</span><span class="c2">×</span><span class="c2">×</span><span class="c2">×</span><span class="c2">×</span><span class="c3">×</span><span class="c3">×</span><span class="c3">×</span><span class="c3">×</span><span class="c2">×</span><span class="c2">×</span><span class="c2">×</span><span class="c2">×</span><span class="c3">×</span><span class="c3">×</span><span class="c3">×</span><span class="c3">×</span></div><p class="caption">大きな計算を、小さく分担</p></div><div class="arrow">→</div><div><div class="workers"><div class="worker c0">担当1<div class="worker-tasks"><span>掛ける</span><span>足す</span><span>繰り返す</span></div></div><div class="worker c1">担当2<div class="worker-tasks"><span>掛ける</span><span>足す</span><span>繰り返す</span></div></div><div class="worker c2">担当3<div class="worker-tasks"><span>掛ける</span><span>足す</span><span>繰り返す</span></div></div><div class="worker c3">担当4<div class="worker-tasks"><span>掛ける</span><span>足す</span><span>繰り返す</span></div></div></div><p class="caption" style="text-align:center">複数の担当が、同時に計算する</p></div></div><p class="gpu-under">Transformerの中にある、大量の<strong>行列の計算</strong>と相性がよい。</p>

<div class="source">4担当は仕組みを示す模式図。担当数やデータを運ぶ速度には上限がある。<a href="https://docs.nvidia.com/deeplearning/performance/dl-performance-matrix-multiplication/index.html">NVIDIA：行列積のGPU実装</a></div>

<!--
伝えたいこと：GPUは独立した数値計算を多数の担当へ分け、同時に進めるハードウェアだと理解する。
最初に話す一文：同時にできる掛け算・足し算を、まとめて進めます。
話す順番：
会場を増やすたとえを、計算の担当へ置き換える。実際に人やモデル全体を複製するという意味ではない。
行列積は小さな領域へ分割して計算する。図の4担当は簡略化で、実機の構成を表さない。
担当数、メモリ容量、データ転送、集約に限界があり、GPUが常に高速とは限らない。
出典：https://docs.nvidia.com/deeplearning/performance/dl-performance-matrix-multiplication/index.html §2.1。次へ：一方のCPUは、どんな構造で、何が得意なのか。
-->


---

<!-- _class: default -->

# CPUは、処理の流れを素早く進める

<p class="lead">CPUは、制御と高速メモリを使い、1つの処理の流れを素早く進めます。</p>

<div class="cpu-layout"><div class="cpu-chip"><h2>CPU</h2><div class="cpu-cores"><div class="cpu-core active">コア1</div><div class="cpu-core">コア2</div><div class="cpu-core">コア3</div><div class="cpu-core">コア4</div></div><p class="note" style="margin-top:16px">コア＝処理を進める担当</p></div><div class="cpu-zoom">中を見る<b>→</b></div><div class="cpu-inside"><h2>1つのコアの中（模式図）</h2><div class="cpu-control"><strong>制御・分岐予測</strong><p>命令の流れを扱い、次の命令を準備</p></div><div class="cpu-core-parts"><div class="cpu-part"><strong>演算器</strong><small>数を比べる<br>足す・掛ける</small></div><div class="arrow">↔</div><div class="cpu-part memory"><strong>キャッシュ</strong><small>近くにある高速メモリ<br>データをすぐ使う</small></div></div></div></div><p class="cpu-synthesis">結果を見て処理を切り替えながら、<strong>1つの流れの待ち時間を減らす</strong>。</p>

<div class="source">数・配置は模式図。CPUも並列処理をし、GPUにも制御やキャッシュがある。<a href="https://docs.nvidia.com/cuda/cuda-programming-guide/01-introduction/introduction.html#the-benefits-of-using-gpus">NVIDIA：CPUとGPUの設計の違い</a></div>

<!--
伝えたいこと：CPUは制御・演算・キャッシュなどを使い、1つの処理の流れを低い待ち時間で進める設計だと理解する。
最初に話す一文：CPUは、制御と高速メモリを使い、1つの処理の流れを素早く進めます。
話す順番：
左がCPU全体、右が1つのコアを拡大した模式図。4コアは説明用で、実機の数や面積比を示していない。
制御は命令の流れを扱い、演算器は比較や計算を行う。キャッシュは、よく使う命令やデータを近くに置く高速なメモリ。
多くの高性能CPUは分岐予測や、独立した命令を先に進める仕組みなどで1つの流れを速くする。分岐予測は次に実行する命令の流れを予測するもので、比較結果や試合の勝者を確定する機能ではない。
CPUも複数のコアや演算器で並列処理をする。GPUにも制御回路とキャッシュがある。図はCPUの主な働きを抜き出したもの。
出典：https://docs.nvidia.com/cuda/cuda-programming-guide/01-introduction/introduction.html#the-benefits-of-using-gpus ／ https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/technical-documentation/hardware-behavior-related-to-speculative-execution.html
次へ：少人数のトーナメントなら、CPUでその場で進める方が速い場合がある。
-->


---

<!-- _class: default -->

# 小さなトーナメントは、CPUが有利なことも

<p class="lead">少人数の比較なら、CPUでそのまま進める方が速い場合があります。</p>

<p class="cpu-condition">条件：8人の強さを表す数値がCPU側にあり、最強を1回だけ探す。</p><div class="cpu-lane"><div class="cpu-lane-label">CPU</div><div class="cpu-route"><div class="cpu-stage direct">手元のデータを7回比較<small>勝者を次の比較へ進める</small></div><div class="arrow">→</div><div class="cpu-stage">最強が決まる</div></div></div><div class="cpu-lane"><div class="cpu-lane-label gpu">GPU</div><div class="cpu-route"><div class="cpu-stage">準備・必要な転送</div><div class="arrow">→</div><div class="cpu-stage">比較を並列に行う</div><div class="arrow">→</div><div class="cpu-stage">結果を受け取る</div></div></div><div class="cpu-takeaway"><p><strong>小さい仕事</strong>では、GPUへ依頼する準備の方が目立つことがある。</p><p><strong>大量の比較</strong>なら、GPUが得意な並列処理を生かしやすい。</p></div>

<div class="source">速度は規模・実装・データの置き場所で変わる。GPUも勝ち抜き型の比較を並列に行える。<a href="https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html#what-runs-on-a-cuda-enabled-device">NVIDIA：GPUで実行する仕事の選び方</a></div>

<!--
伝えたいこと：トーナメントそのものではなく、少量のデータを一度だけ処理する条件でCPUが有利になることを理解する。
最初に話す一文：少人数の比較なら、CPUでそのまま進める方が速い場合があります。
話す順番：
さっきの大会を、実際の数の比較に置き換える。8人の強さが数値としてCPU側にあり、最大値を1回だけ求める例。7回の比較で最強が分かる。
この程度の小さな仕事は、GPUの起動・必要な転送・同期の負担をかけるより、CPUでそのまま処理した方が速い場合がある。図の箱の幅は時間を表さず、実測の速度比較でもない。
結果待ちはCPUでも残る。単純な勝ち抜きの比較は必ずしも分岐が多い処理ではなく、GPUも比較の木を並列に実行できる。
大量の数を比べる場合、すでにデータがGPU上にある場合、複数の仕事をまとめる場合は事情が変わる。トーナメントなら必ずCPUが速い、とは説明しない。
前ページの構造は、制御や近くのデータを使って、小さな処理を低い待ち時間で進めることにつながる。
出典：https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html#what-runs-on-a-cuda-enabled-device
次へ：Transformerでも、GPUで1個を決める中の計算を速くする一方、生成には順番が残る。
-->


---

<!-- _class: default -->

# 言葉を出す順番は、残る

<p class="lead">GPUは1個を決める計算を速くし、通常の生成は1個ずつ進みます。</p>

<div class="serial-row"><p class="small">私は猫が</p><div class="arrow">→</div><div class="parallel-box">同時に計算する<div class="mini-ops"><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span></div></div><div class="arrow">→</div><div class="serial-result"><span class="token new">好き</span></div></div><p class="serial-return">↓「好き」が決まったら、次の入力へ</p><div class="serial-row" style="margin-top:0"><p class="small">私は猫が好き</p><div class="arrow">→</div><div class="parallel-box">同時に計算する<div class="mini-ops"><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span><span>× +</span></div></div><div class="arrow">→</div><div class="serial-result"><span class="token focus">です</span></div></div><div class="serial-labels"><span><strong>箱の中</strong>：計算を並列に</span><span><strong>言葉の生成</strong>：前の出力を待つ</span></div>

<div class="source">通常の自己回帰生成を説明。学習時は、未来の正解を隠して複数位置の予測をまとめて計算できる。</div>

<!--
伝えたいこと：1ステップの内部の並列性と、自己回帰生成の時間方向の順番を分ける。
最初に話す一文：GPUは1個を決める計算を速くし、通常の生成は1個ずつ進みます。
話す順番：
紫の箱の中では多数の掛け算・足し算を同時に進める。
普通の生成で、ですの予測には直前に決まった好きを使うため、生成ステップには順番がある。
学習は正解列が手元にあるので、未来を隠しつつ多くの位置をまとめて計算できる。
次へ：最初の自己回帰の図に、AttentionとGPUの役割を重ねる。
-->


---

<!-- _class: default -->

# 最初の図に、役割を重ねる

<p class="lead">文脈から次を予測する計算を、GPUで速く進めます。</p>

<div class="summary-main"><div><p>ここまでの文章</p><p class="caption">私は猫が</p></div><div class="arrow">→</div><div class="summary-model"><h2>Transformer</h2><p><strong>Attention</strong><br>前の情報を取り込む</p><p>ほかの計算も行い、<br>次の候補の確率を出す</p></div><div class="arrow">→</div><div><p>次の1個を選ぶ</p><div style="margin-top:18px"><span class="token new">好き</span></div></div><div class="gpu-band">GPU：箱の中の計算を並列に進める</div></div><div class="summary-return">出した1個を、入力に付け足す</div><p class="summary-end">CPUとGPUは、得意な仕事を分担できます。</p>

<div class="source">本編 boku_nano_presentation.md の9ページ目と対応。図の出力は説明用の例。</div>

<!--
伝えたいこと：自己回帰、Attention、GPUの役割を1枚の図で結び直す。
最初に話す一文：文脈から次を予測する計算を、GPUで速く進めます。
話す順番：
外側のループが自己回帰。モデル内で前の情報を取り込むのがAttention。計算を並列に進めるのがGPU。
TransformerとAttention、GPUは同じ種類のものではない。構造・その中の処理・実行するハードウェアの関係。
典型的なGPU利用の構成では、CPUが全体の進行やデータの準備を支え、GPUがまとまった数値計算を受け持つ。常にこの分担だけになるという意味ではない。
本編へ戻る場合：「では、今話した候補の確率を、本編10ページで見てみます。」
-->


---

<!-- _class: default -->

# 出典と、図の読み方

<p class="lead">研究の内容と、仕組みを伝えるための自作例を分けています。</p>

<div class="sources-list"><span class="year">1948</span><div><a href="https://www.cs.yale.edu/homes/yry/readings/general/shannon1948.pdf">Shannon: A Mathematical Theory of Communication</a><small>§3：27記号、文字の頻度とつながりを使う英語の近似</small></div><span class="year">1951</span><div><a href="https://sites.socsci.uci.edu/~rfutrell/teaching/itl-davis/readings/shannon1951prediction.pdf">Shannon: Prediction and Entropy of Printed English</a><small>§3：人に次の文字を予測してもらう実験</small></div><span class="year">2017</span><div><a href="https://arxiv.org/html/1706.03762v7">Vaswani et al.: Attention Is All You Need</a><small>§3.2・§4：Attentionの計算と並列性</small></div><span class="year">GPU</span><div><a href="https://docs.nvidia.com/deeplearning/performance/dl-performance-matrix-multiplication/index.html">NVIDIA: Matrix Multiplication Background</a><small>§2：演算量・メモリ制約・GPUでの行列計算</small></div><span class="year">CPU</span><div><a href="https://docs.nvidia.com/cuda/cuda-programming-guide/01-introduction/introduction.html#the-benefits-of-using-gpus">NVIDIA: CPUとGPUの設計</a><small><a href="https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html#what-runs-on-a-cuda-enabled-device">仕事の選び方</a> ／ <a href="https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/technical-documentation/hardware-behavior-related-to-speculative-execution.html">Intel：分岐予測などの仕組み</a></small></div></div><p class="sources-final">氏名：<a href="https://cdn.libraries.mit.edu/dissemination/diponline/AC0069_NewReleases/NewsRelease_1960/AC0069_1967/AC0069_196702_001.pdf">MIT公式略歴</a>で Claude Elwood Shannon を確認。<br>文字列・確率・Attentionの重み・大会は、説明用に作成。</p>

<div class="source">発表者用の目的・冒頭文・話す順番は、各ページのMarkdownコメントに記載。</div>

<!--
伝えたいこと：歴史と技術の根拠を確認できるようにする。
最初に話す一文：研究の内容と、仕組みを伝えるための自作例を分けています。
話す順番：
必要なときに見せる参考ページ。普段の口頭説明は前のページで終える。
発表時間の目安は本編19枚で12〜14分。速く説明する場合は歴史か大会の説明を短くする。
元の詳細補足は boku_nano_page09_transformer_speaker_notes.md にあり、投影スライドでは数学の詳細や注意事項を詰め込まない。
-->
