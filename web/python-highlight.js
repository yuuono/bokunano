const KEYWORDS = new Set('False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case'.split(' '));
const BUILTINS = new Set('abs all any bool dict enumerate filter float int len list map max min range reversed round set sorted str sum tuple zip print'.split(' '));
// Highlight only; never parse as HTML or execute model output. Unmatched text is preserved.
export function pythonTokens(source) {
  const pattern = /#[^\n]*|(?:[rRuUbBfF]{0,2})(?:"""[\s\S]*?(?:"""|$)|'''[\s\S]*?(?:'''|$)|"(?:\\.|[^"\\\n])*(?:"|$)|'(?:\\.|[^'\\\n])*(?:'|$))|\b(?:0[xX][\da-fA-F_]+|0[bB][01_]+|\d[\d_]*(?:\.[\d_]*)?(?:[eE][+-]?\d+)?)\b|\b[A-Za-z_]\w*\b/g;
  const tokens = [];
  let cursor = 0;
  let expectName = false;
  for (const match of source.matchAll(pattern)) {
    if (match.index > cursor) tokens.push({ text: source.slice(cursor, match.index), kind: '' });
    const text = match[0];
    let kind = '';
    if (text.startsWith('#')) kind = 'comment';
    else if (/^(?:[rRuUbBfF]{0,2})["']/.test(text)) kind = 'string';
    else if (/^\d/.test(text)) kind = 'number';
    else if (KEYWORDS.has(text)) kind = 'keyword';
    else if (expectName) kind = 'function';
    else if (BUILTINS.has(text)) kind = 'builtin';
    tokens.push({ text, kind });
    expectName = text === 'def' || text === 'class';
    cursor = match.index + text.length;
  }
  if (cursor < source.length) tokens.push({ text: source.slice(cursor), kind: '' });
  return tokens;
}

export function highlightPython(element, source) {
  const fragment = document.createDocumentFragment();
  for (const { text, kind } of pythonTokens(source)) {
    if (!kind) fragment.append(document.createTextNode(text));
    else {
      const span = document.createElement('span');
      span.className = `syntax-${kind}`;
      span.textContent = text;
      fragment.append(span);
    }
  }
  element.replaceChildren(fragment);
}
