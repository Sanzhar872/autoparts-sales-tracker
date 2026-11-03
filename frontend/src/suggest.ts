import type { Suggestions } from "./api";
import { normalizeCar, partKey } from "./util";

export interface Hint {
  label: string;
  /** Начало и конец заменяемого фрагмента в тексте. */
  from: number;
  to: number;
  insert: string;
}

const MAX_HINTS = 8;
const SEPARATOR = /\s[-–—]\s/;

/** Подсказки для слова под курсором: марка → код старой машины → запчасть. */
export function hintsAt(text: string, cursor: number, data: Suggestions | null): Hint[] {
  if (!data) return [];
  const lineStart = text.lastIndexOf("\n", cursor - 1) + 1;
  const beforeCursor = text.slice(lineStart, cursor);
  if (SEPARATOR.test(beforeCursor)) return [];

  // Разбиваем на слова, запоминая позиции.
  const words: { text: string; start: number }[] = [];
  const re = /\S+/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(beforeCursor))) words.push({ text: m[0], start: lineStart + m.index });
  const endsWithSpace = beforeCursor === "" || /\s$/.test(beforeCursor);
  if (endsWithSpace) words.push({ text: "", start: cursor });

  let i = 0;
  if (words.length > 1 && words[0].text.toLowerCase() === "возврат") i = 1;
  const carWord = words[i];
  if (!carWord) return [];

  // Курсор на марке.
  if (words.length - 1 === i) {
    const prefix = normalizeCar(carWord.text);
    return data.cars
      .filter((c) => c.name.startsWith(prefix) && c.name !== prefix)
      .slice(0, MAX_HINTS)
      .map((c) => ({ label: c.name === "с" ? "с (старый завоз)" : c.name, from: carWord.start, to: cursor, insert: `${c.name} ` }));
  }

  const car = normalizeCar(carWord.text);
  if (!data.cars.some((c) => c.name === car)) return [];
  let partStart = i + 1;

  if (car === "с") {
    const codeWord = words[i + 1];
    if (words.length - 1 === i + 1) {
      const prefix = codeWord.text.toUpperCase();
      return data.codes
        .filter((code) => code.startsWith(prefix) && code !== prefix)
        .slice(0, MAX_HINTS)
        .map((code) => ({ label: code, from: codeWord.start, to: cursor, insert: `${code} ` }));
    }
    partStart = i + 2;
  }

  const partWords = words.slice(partStart);
  if (!partWords.length) return [];
  const typed = partKey(partWords.map((w) => w.text).join(" "));
  if (!typed) return [];
  const from = partWords[0].start;
  return (data.parts[car] ?? [])
    .filter((p) => partKey(p).startsWith(typed) && partKey(p) !== typed)
    .slice(0, MAX_HINTS)
    .map((p) => ({ label: p, from, to: cursor, insert: `${p} - ` }));
}
