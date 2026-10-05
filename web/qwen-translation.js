import { resolveSelection, validateExpectedPlan } from "./chat-utils.js?v=15";
import { buildConversationMessages, buildNormalizerUserPrompt, validateOperationPlan } from "./cnl.js?v=18";

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
      messages.push({ role: "assistant", content: candidate });
      messages.push({ role: "user", content: buildNormalizerUserPrompt(instruction, candidate, validation.error) });
    }
  }
  return { supported: false, cnl: "", plan: candidate, attempts: 2,
    error: `Qwenの出力が2回とも検査に通りませんでした。${validation.error} CNLは未確定です。`,
    diagnostic: validation.error };
}
