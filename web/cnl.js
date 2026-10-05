const WITHOUT_K_PREFIX = "整数リストxsから";
const WITH_K_PREFIX = "整数リストxsと整数kを受け取り、";
const SUFFIX = "solve関数を書いてください。";

export const UNSUPPORTED_CNL = "対応できません。";
export const MAX_OPERATIONS = 4;

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
  if (phrases.length < 1 || phrases.length > MAX_OPERATIONS || phrases.some((item) => !item)) {
    return invalid(`操作数は1～${MAX_OPERATIONS}個にしてください。`, cnl);
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
    experimental: operations.length > 3,
    operations: operations.map(({ id, label, requiresK: operationRequiresK }) => ({
      id,
      label,
      requiresK: operationRequiresK,
    })),
  };
}

export function buildNormalizerSystemPrompt() {
  const allowed = CNL_OPERATIONS.map(item => `- ${item.label}`).join("\n");
  return `あなたは整数リスト処理の手順を選ぶアシスタントです。
日本語の依頼を、次の24操作から1～4操作の番号付きリストにしてください。
各行は「1. 操作名」の形式です。操作名は許可表と完全に同じ文字を使ってください。
全ての手順を指示の順番で残してください。重複する操作も省略しないでください。
コード、CNL、説明、Markdownのコードフェンスは出力しないでください。
未対応操作、5操作以上、曖昧な依頼には「${UNSUPPORTED_CNL}」だけを出力してください。

許可表:
${allowed}

変更依頼の場合:
- 変更されていない操作はそのまま保つ。
- 「AをBに変更」はAをBに置き換える。「最後にB」は末尾へ追加する。
- 新しい処理を一から依頼された場合は以前の手順を引き継がない。

例:
入力: 偶数を残して2倍して
出力:
1. 偶数だけを残す
2. 各要素を2倍する

入力: 絶対値にして大きい順に並べて
出力:
1. 各要素の絶対値を取る
2. 値を降順に並べる`;
}

export function buildNormalizerUserPrompt(instruction, previousOutput = "", error = "") {
  if (!previousOutput) return `入力: ${instruction}\n出力:`;
  return `入力: ${instruction}\n前回の出力: ${previousOutput}\n検査エラー: ${error}\n許可表の操作名だけを使い、全手順を番号付きリストで再出力してください。\n出力:`;
}

export function buildNormalizerMessages(instruction) {
  return [
    { role: "system", content: buildNormalizerSystemPrompt() },
    { role: "user", content: buildNormalizerUserPrompt(instruction) },
  ];
}

export function buildRevisionMessages(instruction, contextCnl) {
  const previous = validateCnl(contextCnl);
  if (!previous.valid) throw new Error("変更元の指示が不正です。");
  const steps = previous.operations.map((operation, index) => `${index + 1}. ${operation.label}`).join("\n");
  return [
    { role: "system", content: buildNormalizerSystemPrompt() },
    { role: "user", content: `現在の手順:\n${steps}\n\n変更依頼: ${instruction}\n\n変更後の全手順:` },
  ];
}

export function numberedSteps(text) {
  const lines = text.trim().split(/\r?\n/).filter(line => line.trim());
  if (!lines.length) return [];
  const steps = [];
  for (const [index, line] of lines.entries()) {
    const match = line.match(/^\s*(\d+)[.)．、]\s*(.+?)\s*$/);
    if (!match || Number(match[1]) !== index + 1) return [];
    steps.push(match[2]);
  }
  return steps;
}

// Strict serialization of Qwen-selected operations, never interpretation of user text.
export function validateOperationPlan(text) {
  const steps = numberedSteps(text);
  if (!steps.length || steps.length > MAX_OPERATIONS) {
    return invalid("1～4操作を、1から始まる番号付きリストで出力してください。");
  }
  const operations = steps.map(label => CNL_OPERATIONS.find(operation => operation.label === label));
  const unknown = steps.filter((_, index) => !operations[index]);
  if (unknown.length) return invalid(`許可表と一致しない操作名: ${unknown.join(" / ")}。許可表の操作名をそのまま使ってください。`);
  const usesK = operations.some(operation => operation.requiresK);
  const phrases = operations.map((operation, index) => index === operations.length - 1 ? operation.final : operation.connective);
  return validateCnl(`${usesK ? WITH_K_PREFIX : WITHOUT_K_PREFIX}${phrases.join("、")}${SUFFIX}`);
}
