const byteValues = [];
for (let value = 33; value <= 126; value += 1) byteValues.push(value);
for (let value = 161; value <= 172; value += 1) byteValues.push(value);
for (let value = 174; value <= 255; value += 1) byteValues.push(value);

const unicodeValues = [...byteValues];
let extraIndex = 0;
for (let value = 0; value <= 255; value += 1) {
  if (!byteValues.includes(value)) {
    byteValues.push(value);
    unicodeValues.push(256 + extraIndex);
    extraIndex += 1;
  }
}

const BYTE_TO_UNICODE = new Map(
  byteValues.map((value, index) => [value, String.fromCodePoint(unicodeValues[index])]),
);
const UNICODE_TO_BYTE = new Map(
  byteValues.map((value, index) => [String.fromCodePoint(unicodeValues[index]), value]),
);

export class BokuNanoTokenizer {
  constructor(configuration) {
    this.vocab = new Map(Object.entries(configuration.model.vocab));
    this.mergeRanks = new Map(
      configuration.model.merges.map((pair, index) => [`${pair[0]}\u0000${pair[1]}`, index]),
    );
    this.encoder = new TextEncoder();
    this.decoder = new TextDecoder("utf-8", { fatal: false });
  }

  static async load(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`tokenizerを取得できませんでした: ${response.status}`);
    return new BokuNanoTokenizer(await response.json());
  }

  encodeText(text) {
    const byteSymbols = Array.from(this.encoder.encode(text), (value) => BYTE_TO_UNICODE.get(value));
    const tokens = this.applyBpe(byteSymbols);
    return tokens.map((token) => {
      const tokenId = this.vocab.get(token);
      if (tokenId === undefined) throw new Error(`tokenizer語彙にないtokenです: ${token}`);
      return Number(tokenId);
    });
  }

  encodePrompt(instruction) {
    return [1, 4, ...this.encodeText(`\n${instruction}\n`), 5, ...this.encodeText("\n")];
  }

  applyBpe(initialSymbols) {
    const symbols = [...initialSymbols];
    while (symbols.length > 1) {
      let bestRank = Number.POSITIVE_INFINITY;
      let bestPair = null;
      for (let index = 0; index < symbols.length - 1; index += 1) {
        const key = `${symbols[index]}\u0000${symbols[index + 1]}`;
        const rank = this.mergeRanks.get(key);
        if (rank !== undefined && rank < bestRank) {
          bestRank = rank;
          bestPair = [symbols[index], symbols[index + 1]];
        }
      }
      if (bestPair === null) break;
      const merged = [];
      for (let index = 0; index < symbols.length; ) {
        if (
          index < symbols.length - 1 &&
          symbols[index] === bestPair[0] &&
          symbols[index + 1] === bestPair[1]
        ) {
          merged.push(bestPair[0] + bestPair[1]);
          index += 2;
        } else {
          merged.push(symbols[index]);
          index += 1;
        }
      }
      symbols.splice(0, symbols.length, ...merged);
    }
    return symbols;
  }

  decode(tokenIds) {
    const inverseVocab = this.inverseVocab ?? new Map(
      Array.from(this.vocab.entries(), ([token, tokenId]) => [Number(tokenId), token]),
    );
    this.inverseVocab = inverseVocab;
    const bytes = [];
    for (const tokenId of tokenIds) {
      if (tokenId <= 6) continue;
      const token = inverseVocab.get(tokenId);
      if (token === undefined) throw new Error(`未知のtoken IDです: ${tokenId}`);
      for (const character of token) {
        const value = UNICODE_TO_BYTE.get(character);
        if (value === undefined) throw new Error(`ByteLevel文字へ復号できません: ${character}`);
        bytes.push(value);
      }
    }
    return this.decoder.decode(new Uint8Array(bytes));
  }
}
