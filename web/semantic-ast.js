// Dataset-compatible meaning, captured from the confirmed operations, never from generated code.
const ATOMS = {
  filter_even: { filter: ["even"] }, filter_odd: { filter: ["odd"] },
  filter_gt_k: { filter: ["gt_k"] }, filter_ge_k: { filter: ["ge_k"] },
  filter_lt_k: { filter: ["lt_k"] }, filter_le_k: { filter: ["le_k"] },
  filter_multiple_k: { filter: ["multiple_of_k"] },
  filter_positive: { filter: ["positive"] }, filter_negative: { filter: ["negative"] },
  filter_zero: { filter: ["zero"] },
  map_add_k: { map: ["add_k"] }, map_sub_k: { map: ["sub_k"] }, map_mul_k: { map: ["mul_k"] },
  map_mul_2: { map: ["mul_const", 2] }, map_mul_3: { map: ["mul_const", 3] },
  map_negate: { map: ["negate"] }, map_abs: { map: ["abs"] }, map_square: { map: ["square"] },
  order_ascending: { order: "ascending" }, order_descending: { order: "descending" },
  order_reverse: { order: "reverse" },
  slice_first_k: { slice: ["take_first_k"] }, slice_last_k: { slice: ["take_last_k"] },
  slice_every_other: { slice: ["every_other"] },
};

function freezeTree(value) {
  if (value && typeof value === "object") {
    Object.values(value).forEach(freezeTree);
    Object.freeze(value);
  }
  return value;
}

export function captureSemanticAst(validation) {
  if (!validation.valid || !validation.operations?.length || validation.operations.length > 4) {
    throw new Error("検査済みの1〜4操作が必要です。");
  }
  const sequence = validation.operations.map(({ id }) => {
    if (!Object.hasOwn(ATOMS, id)) throw new Error(`未知の操作: ${id}`);
    return structuredClone(ATOMS[id]);
  });
  return freezeTree(sequence.length === 1 ? sequence[0] : { sequence });
}

export function parseVerificationInputs(xsText, kText) {
  let xs;
  try { xs = JSON.parse(xsText); }
  catch { throw new Error("入力リストは [3, -1, 2] のように入力してください。"); }
  if (!Array.isArray(xs) || xs.length > 20 || xs.some(x => !Number.isInteger(x) || x < -100 || x > 100)) {
    throw new Error("入力リストは−100〜100の整数、最大20個で指定してください。空リスト [] も使えます。");
  }
  if (!/^[+-]?\d+$/.test(kText.trim()) || !Number.isInteger(Number(kText)) || Number(kText) < 1 || Number(kText) > 10) {
    throw new Error("参照インタプリタの検証範囲では、kは1〜10の整数で指定してください。");
  }
  return { xs, k: Number(kText) };
}
