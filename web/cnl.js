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

// Friendly input phrases also cover common Qwen wording without guessing unknown operations.
export const OPERATION_REQUESTS = Object.freeze({
  filter_even: "偶数だけを残して", filter_odd: "奇数だけを残して",
  filter_gt_k: "kより大きい値だけを残して", filter_ge_k: "k以上の値だけを残して",
  filter_lt_k: "kより小さい値だけを残して", filter_le_k: "k以下の値だけを残して",
  filter_multiple_k: "kの倍数だけを残して", filter_positive: "正の値だけを残して",
  filter_negative: "負の値だけを残して", filter_zero: "ゼロだけを残して",
  map_add_k: "各要素にkを足して", map_sub_k: "各要素からkを引いて",
  map_mul_k: "各要素にkを掛けて", map_mul_2: "各要素を2倍して",
  map_mul_3: "各要素を3倍して", map_negate: "各要素の符号を反転して",
  map_abs: "各要素を絶対値にして", map_square: "各要素を二乗して",
  order_ascending: "小さい順に並べて", order_descending: "大きい順に並べて",
  order_reverse: "要素の順番を逆にして", slice_first_k: "先頭からk個を取って",
  slice_last_k: "末尾からk個を取って", slice_every_other: "先頭から1個おきに取って",
});

export function operationRequest(operations, kValue = null) {
  return operations.map(op => OPERATION_REQUESTS[op.id]).join("、") + "ください。"
    + (kValue != null ? `\nk=${kValue}` : "");
}

const OPERATION_ALIASES = {
  filter_even: ["偶数を残す", "偶数のみを残す"],
  filter_odd: ["奇数を残す", "奇数のみを残す"],
  map_add_k: ["各要素にkを足す", "各要素にkを加算する"],
  map_mul_k: ["各要素をk倍する", "各要素にkをかける"],
  map_abs: ["絶対値を取る", "各要素を絶対値にする", "絶対値にする"],
  map_square: ["各要素を2乗する"],
  order_ascending: ["昇順に並べる", "昇順にソートする", "小さい順に並べる"],
  order_descending: ["降順に並べる", "降順にソートする", "大きい順に並べる"],
  order_reverse: ["要素の順番を逆にする", "要素順を逆にする", "順番を逆にする", "逆順にする", "要素の順序を反転する"],
};

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
  return `日本語の依頼を、許可表の1～4操作に変換してください。
出力は操作名を1行ずつ。番号と説明は不要です。順序・重複を保ち、全操作を残してください。
5操作以上、許可表にない処理、異なるkの値を同時に必要とする処理には「${UNSUPPORTED_CNL}」と答えてください。
kを含む操作で具体的な整数が指定された場合だけ、末尾にk=整数を付けてください。未指定のkを補わないでください。
2倍・3倍は専用の操作なのでkは不要です。それ以外の倍率はkを掛ける操作を使います。
変更依頼では、前の手順の変更されていない部分とkを保持してください。数値だけの変更も可能です。

許可表:
${allowed}`;

}

export function buildNormalizerUserPrompt(instruction, previousOutput = "", error = "") {
  if (!previousOutput) return `入力: ${instruction}\n出力:`;
  return `入力: ${instruction}\n前回の出力: ${previousOutput}\n検査エラー: ${error}\n許可表の操作名だけを使い、全手順を1行に1つずつ再出力してください。番号は不要です。\n出力:`;
}

export function buildNormalizerMessages(instruction) {
  return [
    { role: "system", content: buildNormalizerSystemPrompt() },
    { role: "user", content: buildNormalizerUserPrompt(instruction) },
  ];
}

export function buildRevisionMessages(instruction, contextCnl, contextK = null) {
  const previous = validateCnl(contextCnl);
  if (!previous.valid) throw new Error("変更元の指示が不正です。");
  const steps = previous.operations.map((operation, index) => `${index + 1}. ${operation.label}`).join("\n");
  return [
    { role: "system", content: buildNormalizerSystemPrompt() },
    { role: "user", content: "現在の手順を確認してください。" },
    { role: "assistant", content: `${steps}${previous.usesK && contextK !== null ? `\nk=${parseK(contextK)}` : ""}` },
    { role: "user", content: `変更依頼: ${instruction}\n変更後の全手順とkの値を出力してください。` },
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

// Tolerate presentation differences, but never discard an unknown step or negation.
export function validateOperationPlan(text) {
  if (typeof text !== "string" || !text.trim()) return invalid("やりたい処理を入力してください。");
  const normalized = text.normalize("NFKC").trim();
  if (normalized === UNSUPPORTED_CNL) return invalid("この指示は24種類の操作では表現できません。");
  const lines = normalized.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  const body = [];
  let kValue = null;
  let hasK = false;
  for (let line of lines) {
    if (/^```(?:text|plaintext|markdown|md|japanese)?$/i.test(line)) continue;
    line = line.replace(/\*\*([^*]+)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1");
    if (/^(?:出力|手順|操作|処理手順|操作一覧|以下の操作|以下の手順)[:：]?$/.test(line)) continue;
    line = line.replace(/^(?:出力|手順|操作一覧)[:：]\s*/, "");
    line = line.replace(/^(?:[-*•・]\s*|(?:\(\d+\)|\d+[.)、:])\s*)/, "");
    if (/^k\s*[=:]/i.test(line)) {
      const parameter = line.match(/^k\s*[=:]\s*([+-]?\d+)[。.]?$/i);
      if (hasK || !parameter) return invalid("kには整数を1つ指定してください。");
      try { kValue = parseK(parameter[1]); } catch (error) { return invalid(error.message); }
      hasK = true;
    } else body.push(line);
  }
  // A complete trained CNL is another valid representation of the same plan.
  const completeCnl = validateCnl(body.join(""));
  if (completeCnl.valid) {
    if (hasK && !completeCnl.usesK) return invalid("kの値には、kを使う操作が必要です。");
    return { ...completeCnl, kValue };
  }
  const phrases = body.join("\n").split(/\n|、|。|\s*(?:→|->|;)\s*/).map(part => part.trim()).filter(Boolean);
  const operations = [];
  const findOperation = phrase => CNL_OPERATIONS.find(op =>
    [op.label, op.connective, op.final, OPERATION_REQUESTS[op.id], ...(OPERATION_ALIASES[op.id] || [])].includes(phrase));
  for (let phrase of phrases) {
    phrase = phrase.replace(/^(?:その後|次に|最後に)\s*/, "").replace(/[.]$/, "").replace(/ください$/, "").replace(/元素/g, "要素").trim();
    if (!phrase) continue;
    let operation = findOperation(phrase);
    if (!operation) {
      // Concrete numbers are fine too: "各要素に3を足す" means add_k with k=3.
      const numbers = [...phrase.matchAll(/[+-]?\d+/g)];
      if (numbers.length === 1) {
        const number = numbers[0];
        const parameterized = phrase.slice(0, number.index) + "k" + phrase.slice(number.index + number[0].length);
        const candidate = findOperation(parameterized);
        if (candidate?.requiresK) {
          let value;
          try { value = parseK(number[0]); } catch (error) { return invalid(error.message); }
          if (hasK && kValue !== value) return invalid("異なる数値を同時に使う操作には対応していません。kの値を1つにしてください。");
          kValue = value;
          hasK = true;
          operation = candidate;
        }
      }
    }
    if (!operation) return invalid(`操作内容を読み取れませんでした: ${phrase}。やりたい処理を具体的に伝えてください。`);
    operations.push(operation);
  }
  if (!operations.length || operations.length > MAX_OPERATIONS) return invalid("一度に扱える操作は1～4個です。");
  const usesK = operations.some(operation => operation.requiresK);
  if (hasK && !usesK) return invalid("kの値には、kを使う操作が必要です。");
  const forms = operations.map((operation, index) => index === operations.length - 1 ? operation.final : operation.connective);
  return { ...validateCnl(`${usesK ? WITH_K_PREFIX : WITHOUT_K_PREFIX}${forms.join("、")}${SUFFIX}`), kValue };
}

export function parseK(value) {
  if (value === null || value === undefined || String(value).trim() === "") return null;
  if (!/^[+-]?\d+$/.test(String(value).trim()) || !Number.isSafeInteger(Number(value))) {
    throw new Error("kには安全に扱える範囲の整数を入力してください。");
  }
  return Number(value);
}

// Only bind the default argument. Never rewrite the model-generated function body.
export function bindKDefault(code, value) {
  const k = parseK(value);
  if (k === null) return code;
  const signature = /^(def solve\(xs: list\[int\], k: int)(\) -> list\[int\]:)\r?$/m;
  if (!signature.test(code)) throw new Error("生成された関数にkの初期値を設定できませんでした。モデルを変えて再生成してください。");
  return code.replace(signature, (_, start, end) => `${start} = ${k}${end}`);
}
