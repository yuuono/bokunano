// Both engines use T=0 for greedy and positive T for temperature sampling.
export function validateTemperature(value) {
  const temperature = Number(value);
  if (!Number.isFinite(temperature) || temperature < 0 || temperature > 2) {
    throw new Error("温度は0〜2の数値を指定してください。");
  }
  return temperature;
}

export function temperatureProbabilities(logits, temperature) {
  const t = validateTemperature(temperature);
  if (t === 0) throw new Error("T=0ではsoftmaxを使わず最大の候補を選択します。");
  if (!logits.length) throw new Error("次のトークン候補がありません。");
  let maximum = -Infinity;
  for (const value of logits) {
    if (!Number.isFinite(value)) throw new Error("モデルが不正なlogitsを返しました。");
    maximum = Math.max(maximum, value);
  }
  // Subtracting before division also avoids overflow at very small positive T.
  const probabilities = Float64Array.from(logits, value => Math.exp((value - maximum) / t));
  const sum = probabilities.reduce((total, value) => total + value, 0);
  return probabilities.map(value => value / sum);
}

export function selectToken(logits, temperature, random = Math.random) {
  const t = validateTemperature(temperature);
  if (!logits.length) throw new Error("次のトークン候補がありません。");
  if (t === 0) {
    let best = 0;
    for (let i = 0; i < logits.length; i += 1) {
      if (!Number.isFinite(logits[i])) throw new Error("モデルが不正なlogitsを返しました。");
      if (logits[i] > logits[best]) best = i;
    }
    return best;
  }
  const probabilities = temperatureProbabilities(logits, t);
  let threshold = random();
  if (!(threshold >= 0 && threshold < 1)) throw new Error("乱数は0以上1未満である必要があります。");
  for (let i = 0; i < probabilities.length; i += 1) {
    threshold -= probabilities[i];
    if (threshold < 0) return i;
  }
  // Roundoff can leave a tiny positive remainder; return the last possible token.
  for (let i = probabilities.length - 1; i >= 0; i -= 1) {
    if (probabilities[i] > 0) return i;
  }
}

export function qwenSamplingOptions(temperature) {
  const t = validateTemperature(temperature);
  return t === 0
    ? { do_sample: false }
    : { do_sample: true, temperature: t, top_k: 0, top_p: 1 };
}
