import { CNL_OPERATIONS, MAX_OPERATIONS, operationRequest, OPERATION_REQUESTS, validateOperationPlan } from './cnl.js?v=10';

export function appendOperationToDraft(text, id) {
  const operation = CNL_OPERATIONS.find(op => op.id === id);
  if (!operation) throw new Error('操作を選択してください。');
  const draft = text.trim();
  const previous = draft ? validateOperationPlan(draft) : null;
  if (previous?.valid || !draft) {
    const operations = [...(previous?.operations || []), operation];
    if (operations.length > MAX_OPERATIONS) throw new Error('一度に選べる操作は4つまでです。入力欄で操作を減らしてください。');
    return operationRequest(operations, previous?.kValue);
  }
  // Preserve free text and concrete values; Qwen will interpret the combined request.
  return `${draft}\nその後、${OPERATION_REQUESTS[operation.id]}ください。`;
}

export function nearBottom({ scrollHeight, clientHeight, scrollTop }, threshold = 80) {
  return scrollHeight - clientHeight - scrollTop <= threshold;
}


// An edited draft must be interpreted afresh; never reuse stale button choices.
export function captureSelection(text) {
  const plan = validateOperationPlan(text);
  return plan.valid ? { text: text.trim(), ids: plan.operations.map(op => op.id), kValue: plan.kValue } : null;
}

export function resolveSelection(text, snapshot) {
  if (!snapshot || snapshot.text !== text.trim()) return null;
  const plan = validateOperationPlan(text);
  if (!plan.valid || JSON.stringify(plan.operations.map(op => op.id)) !== JSON.stringify(snapshot.ids)
      || plan.kValue !== snapshot.kValue) return null;
  return plan;
}

export function reconcileSelection(generated, selected) {
  if (!selected?.valid) return { ...generated, selectionRecovered: false };
  const matches = generated.valid && generated.cnl === selected.cnl;
  return { ...selected, selectionRecovered: !matches };
}
