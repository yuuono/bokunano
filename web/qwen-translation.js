import { resolveSelection, validateExpectedPlan } from "./chat-utils.js?v=23";
import { buildConversationMessages, buildNormalizerUserPrompt, validateOperationPlan } from "./cnl.js?v=23";

// Both examples and free text use the same two-attempt loop.
export async function translateWithRetry({ instruction, contextCnl = "", contextK = null, selection = null, generate, onAttempt = () => {} }) {
  const expected = resolveSelection(instruction, selection);
  const messages = buildConversationMessages(instruction, contextCnl, contextK, Boolean(expected));
  let candidate = "";
  let validation;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    candidate = await generate(messages, attempt);
    validation = validateExpectedPlan(validateOperationPlan(candidate), expected);
    onAttempt({ attempt, plan: candidate, valid: validation.valid, error: validation.error });
    if (validation.valid) {
      return { supported: true, cnl: validation.cnl, operations: validation.operations,
        kValue: validation.kValue, plan: candidate, attempts: attempt };
    }
    if (attempt < 2) {
      if (expected?.valid) {
        // Do not prime the repair generation with the same malformed wording again.
        // The rejected raw response is still recorded by onAttempt above.
        const parameter = expected.kValue === null ? "入力にないkの数値を補わないでください。" : `最後にk=${expected.kValue}を出力してください。`;
        messages.splice(1, messages.length - 1, { role: "user", content:
          `入力: ${instruction}\n前回の出力は検査に通りませんでした。入力から確認できた全${expected.operations.length}操作は次の順番です。表記を変えず、1行ずつ出力してください。\n${parameter}\n\n${expected.operations.map(op => op.label).join("\n")}` });
      } else {
        messages.push({ role: "assistant", content: candidate });
        messages.push({ role: "user", content: buildNormalizerUserPrompt(instruction, candidate, validation.error) });
      }
    }
  }
  return { supported: false, cnl: "", plan: candidate, attempts: 2,
    error: `Qwenの出力が2回とも検査に通りませんでした。${validation.error} CNLは未確定です。`,
    diagnostic: validation.error };
}
