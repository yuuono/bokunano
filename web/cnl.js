const WITHOUT_K_PREFIX = "整数リストxsから";
const WITH_K_PREFIX = "整数リストxsと整数kを受け取り、";
const SUFFIX = "solve関数を書いてください。";

export const UNSUPPORTED_CNL = "対応できません。";

export const CNL_OPERATIONS = Object.freeze([
  { id: "filter_even", label: "偶数だけを残す", connective: "偶数だけを残し", final: "偶数だけを残す", requiresK: false },
  { id: "filter_odd", label: "奇数だけを残す", connective: "奇数だけを残し", final: "奇数だけを残す", requiresK: false },
  { id: "filter_gt_k", label: "kより大きい値だけを残す", connective: "kより大きい値だけを残し", final: "kより大きい値だけを残す", requiresK: true },
  { id: "filter_ge_k", label: "k以上の値だけを残す", connective: "k以上の値だけを残し", final: "k以上の値だけを残す", requiresK: true },
  { id: "filter_lt_k", label: "kより小さい値だけを残す", connective: "kより小さい値だけを残し", final: "kより小さい値だけを残す", requiresK: true },
  { id: "filter_le_k", label: "k以下の値だけを残す", connective: "k以下の値だけを残し", final: "k以下の値だけを残す", requiresK: true },
  { id: "filter_multiple_k", label: "kの倍数だけを残す", connective: "kの倍数だけを残し", final: "kの倍数だけを残す", requiresK: true },
  { id: "filter_positive", label: "正の値だけを残す", connective: "正の値だけを残し", final: "正の値だけを残す", requiresK: false },
  { id: "filter_negative", label: "負の値だけを残す", connective: "負の値だけを残し", final: "負の値だけを残す", requiresK: false },
  { id: "filter_zero", label: "ゼロだけを残す", connective: "ゼロだけを残し", final: "ゼロだけを残す", requiresK: false },
  { id: "map_add_k", label: "各要素にkを加える", connective: "各要素にkを加え", final: "各要素にkを加える", requiresK: true },
  { id: "map_sub_k", label: "各要素からkを引く", connective: "各要素からkを引き", final: "各要素からkを引く", requiresK: true },
  { id: "map_mul_k", label: "各要素にkを掛ける", connective: "各要素にkを掛け", final: "各要素にkを掛ける", requiresK: true },
  { id: "map_mul_2", label: "各要素を2倍する", connective: "各要素を2倍し", final: "各要素を2倍する", requiresK: false },
  { id: "map_mul_3", label: "各要素を3倍する", connective: "各要素を3倍し", final: "各要素を3倍する", requiresK: false },
  { id: "map_negate", label: "各要素の符号を反転する", connective: "各要素の符号を反転し", final: "各要素の符号を反転する", requiresK: false },
  { id: "map_abs", label: "各要素の絶対値を取る", connective: "各要素の絶対値を取り", final: "各要素の絶対値を取る", requiresK: false },
  { id: "map_square", label: "各要素を二乗する", connective: "各要素を二乗し", final: "各要素を二乗する", requiresK: false },
  { id: "order_ascending", label: "値を昇順に並べる", connective: "値を昇順に並べ", final: "値を昇順に並べる", requiresK: false },
  { id: "order_descending", label: "値を降順に並べる", connective: "値を降順に並べ", final: "値を降順に並べる", requiresK: false },
  { id: "order_reverse", label: "現在の要素順を反転する", connective: "現在の要素順を反転し", final: "現在の要素順を反転する", requiresK: false },
  { id: "slice_first_k", label: "先頭からk個を取る", connective: "先頭からk個を取り", final: "先頭からk個を取る", requiresK: true },
  { id: "slice_last_k", label: "末尾からk個を取る", connective: "末尾からk個を取り", final: "末尾からk個を取る", requiresK: true },
  { id: "slice_every_other", label: "先頭から1個おきに取る", connective: "先頭から1個おきに取り", final: "先頭から1個おきに取る", requiresK: false },
]);

function invalid(error, cnl = "") {
  return { valid: false, error, cnl, operations: [] };
}

export function validateCnl(rawCnl) {
  if (typeof rawCnl !== "string") return invalid("CNLが文字列ではありません。");
  const cnl = rawCnl.trim();
  if (!cnl) return invalid("CNLを入力してください。");
  if (cnl === UNSUPPORTED_CNL) return invalid("この指示は24種類の操作では表現できません。", cnl);
  if (cnl.includes("\n") || cnl.includes("\r")) return invalid("CNLは1行で入力してください。", cnl);

  let usesK;
  let body;
  if (cnl.startsWith(WITH_K_PREFIX) && cnl.endsWith(SUFFIX)) {
    usesK = true;
    body = cnl.slice(WITH_K_PREFIX.length, -SUFFIX.length);
  } else if (cnl.startsWith(WITHOUT_K_PREFIX) && cnl.endsWith(SUFFIX)) {
    usesK = false;
    body = cnl.slice(WITHOUT_K_PREFIX.length, -SUFFIX.length);
  } else {
    return invalid("CNLの外側テンプレートが規定と一致しません。", cnl);
  }

  const phrases = body.split("、");
  if (phrases.length < 1 || phrases.length > 3 || phrases.some((item) => !item)) {
    return invalid("操作数は1～3個にしてください。", cnl);
  }

  const operations = [];
  for (let index = 0; index < phrases.length; index += 1) {
    const form = index === phrases.length - 1 ? "final" : "connective";
    const operation = CNL_OPERATIONS.find((item) => item[form] === phrases[index]);
    if (!operation) {
      return invalid(`許可されていない操作表現です: ${phrases[index]}`, cnl);
    }
    operations.push(operation);
  }

  const requiresK = operations.some((item) => item.requiresK);
  if (requiresK !== usesK) {
    return invalid(
      requiresK
        ? "kを使う操作には「整数リストxsと整数kを受け取り」の形式が必要です。"
        : "kを使わない操作には「整数リストxsから」の形式を使用してください。",
      cnl,
    );
  }

  return {
    valid: true,
    error: null,
    cnl,
    usesK,
    operations: operations.map(({ id, label, requiresK: operationRequiresK }) => ({
      id,
      label,
      requiresK: operationRequiresK,
    })),
  };
}

export function buildNormalizerSystemPrompt() {
  const grammar = CNL_OPERATIONS.map(
    (item) => `- ${item.label}: 接続形「${item.connective}」／最終形「${item.final}」`,
  ).join("\n");
  return `あなたは自由な日本語をBoku1-nano用Controlled Natural Languageへ翻訳する正規化器です。
追加説明、Markdown、JSON、Pythonコード、思考過程は出力せず、完成したCNLを必ず1行だけ出力してください。
入力の処理順を変えず、次の24操作から1～3操作だけを選んでください。

${grammar}

規則:
- 最後以外の操作には接続形、最後の操作には最終形を使い、読点「、」で連結する。
- kを使う操作が一つでもあれば「${WITH_K_PREFIX}{操作列}${SUFFIX}」とする。
- kを使う操作がなければ「${WITHOUT_K_PREFIX}{操作列}${SUFFIX}」とする。
- 対応できない操作、4操作以上、意味が曖昧な入力には「${UNSUPPORTED_CNL}」だけを出力する。

例:
入力: 数字の中から偶数だけ選んで
出力: 整数リストxsから偶数だけを残すsolve関数を書いてください。

入力: 全部プラスの値に直してから、大きい順に並べて
出力: 整数リストxsから各要素の絶対値を取り、値を降順に並べるsolve関数を書いてください。

入力: 後ろからk個を取って、その中からマイナスだけ残して
出力: 整数リストxsと整数kを受け取り、末尾からk個を取り、負の値だけを残すsolve関数を書いてください。

入力: 偶数を残して2倍し、それから逆順にして
出力: 整数リストxsから偶数だけを残し、各要素を2倍し、現在の要素順を反転するsolve関数を書いてください。`;
}

export function buildNormalizerUserPrompt(instruction, previousOutput = "", error = "") {
  if (!previousOutput) return `入力: ${instruction}\n出力:`;
  return `入力: ${instruction}\n前回の出力: ${previousOutput}\n検査エラー: ${error}\n規則どおりのCNLを1行だけ再出力してください。\n出力:`;
}
