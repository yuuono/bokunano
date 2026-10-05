import { CNL_OPERATIONS, MAX_OPERATIONS, numberedSteps, validateOperationPlan } from './cnl.js?v=3';

// Exact operation lists already express the user's choice. Do not re-interpret them.
export function explicitOperationPlan(text, revision = false) {
  if (revision) return null;
  const plan = validateOperationPlan(text);
  if (plan.valid) return plan;
  const steps = numberedSteps(text.replace(/\n\s*k\s*=.*$/, ''));
  return steps.length && steps.every(label => CNL_OPERATIONS.some(op => op.label === label)) ? plan : null;
}

export function appendOperationToDraft(text, id) {
  const operation = CNL_OPERATIONS.find(op => op.id === id);
  if (!operation) throw new Error('操作を選択してください。');
  const draft = text.trim();
  const previous = draft ? validateOperationPlan(draft) : null;
  if (previous?.valid || !draft) {
    const operations = [...(previous?.operations || []), operation];
    if (operations.length > MAX_OPERATIONS) throw new Error('一度に選べる操作は4つまでです。入力欄で操作を減らしてください。');
    return operations.map((op, index) => `${index + 1}. ${op.label}`).join('\n')
      + (previous?.kValue != null ? `\nk=${previous.kValue}` : '');
  }
  // Preserve free text and concrete values; Qwen will interpret the combined request.
  return `${draft}\n${operation.label}`;
}

export function nearBottom({ scrollHeight, clientHeight, scrollTop }, threshold = 80) {
  return scrollHeight - clientHeight - scrollTop <= threshold;
}
