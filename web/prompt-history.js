// Sent prompts are kept only for the current conversation, never sent as model context.
export class PromptHistory {
  entries = [];
  position = 0;
  draft = "";

  add(text) {
    this.entries.push(text);
    this.resetDraft("");
  }

  resetDraft(text) {
    this.position = this.entries.length;
    this.draft = text;
  }

  clear() {
    this.entries = [];
    this.resetDraft("");
  }

  move(direction, currentText) {
    if (!this.entries.length) return null;
    if (this.position === this.entries.length) this.draft = currentText;
    const next = Math.max(0, Math.min(this.entries.length, this.position + direction));
    if (next === this.position) return null;
    this.position = next;
    return next === this.entries.length ? this.draft : this.entries[next];
  }
}

export function canRecallPrompt(event, input) {
  if (event.isComposing || event.keyCode === 229 || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return false;
  if (input.selectionStart !== input.selectionEnd) return false;
  if (event.key === "ArrowUp") return !input.value.slice(0, input.selectionStart).includes("\n");
  if (event.key === "ArrowDown") return !input.value.slice(input.selectionEnd).includes("\n");
  return false;
}
