import { CNL_OPERATIONS, MAX_OPERATIONS, operationRequest, OPERATION_REQUESTS, validateOperationPlan } from './cnl.js?v=23';

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

// Known input meaning is a validator only; never substitute it for model output.
export function validateExpectedPlan(generated, expected) {
  if (!expected?.valid) return generated;
  const required = `入力の全${expected.operations.length}操作をこの順番で出力してください: ${expected.operations.map(op => op.label).join(" → ")}`;
  // A parse failure must not hide the known order/meaning from the repair turn.
  if (!generated.valid) {
    const parameter = expected.kValue === null ? "入力にないkの数値を補わないでください。" : `k=${expected.kValue}を出力してください。`;
    return { ...generated, error: `${generated.error}\n${required}\n${parameter}` };
  }
  const ids = plan => plan.operations.map(op => op.id);
  let error = null;
  if (JSON.stringify(ids(generated)) !== JSON.stringify(ids(expected))) {
    error = `操作の欠落・追加、または順序の不一致があります。${required}`;
  } else if (generated.kValue !== expected.kValue) {
    error = expected.kValue === null
      ? "入力にないkの数値を補わないでください。"
      : `入力の数値が一致しません。k=${expected.kValue}を出力してください。`;
  }
  return error ? { valid: false, error, cnl: "", operations: [] } : generated;
}
