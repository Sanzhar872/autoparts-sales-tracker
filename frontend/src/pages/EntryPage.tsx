import { useEffect, useRef, useState } from "react";
import { api, ApiError, Candidate, CommitResult, EntryItem, Suggestions } from "../api";
import { hintsAt, Hint } from "../suggest";
import { formatDate, formatMoney, todayAlmaty } from "../util";

const PLACEHOLDER = `мерс210 сафа левый правый - 25000
к20 капот с обшивкой - 70 000
с ТКЕ щиток прибора - 35000
возврат к20 капот с обшивкой - 70000`;

const STATUS_TEXT = { ok: "OK", error: "Ошибка", ambiguous: "Выберите продажу" };

function describe(c: Candidate): string {
  const code = c.old_car_code ? `${c.old_car_code} ` : "";
  const where = c.line ? `строка ${c.line} этого ввода` : formatDate(c.sold_date);
  return `${where} — ${code}${c.part}, ${formatMoney(c.price)}`;
}

export default function EntryPage() {
  const [text, setText] = useState("");
  const [date, setDate] = useState(todayAlmaty());
  const [items, setItems] = useState<EntryItem[]>([]);
  const [choices, setChoices] = useState<Record<number, string>>({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestions | null>(null);
  const [hints, setHints] = useState<Hint[]>([]);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const today = todayAlmaty();

  function loadSuggestions() {
    api<Suggestions>("/suggestions").then(setSuggestions).catch(() => {});
  }
  useEffect(loadSuggestions, []);

  // Предпросмотр с задержкой после изменения текста, даты или выбора.
  useEffect(() => {
    if (!text.trim()) {
      setItems([]);
      return;
    }
    let active = true; // устаревший ответ не должен перетереть новый
    const timer = setTimeout(() => {
      api<{ items: EntryItem[] }>("/entries/preview", { method: "POST", body: { text, date, choices } })
        .then((data) => {
          if (!active) return;
          setItems(data.items);
          setError("");
        })
        .catch((e) => active && setError(e instanceof ApiError ? e.message : "Ошибка проверки"));
    }, 400);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [text, date, choices]);

  function updateHints() {
    const el = textarea.current;
    if (!el) return;
    setHints(el.selectionStart === el.selectionEnd ? hintsAt(el.value, el.selectionStart, suggestions) : []);
  }

  function changeText(value: string) {
    setText(value);
    setChoices({}); // номера строк могли сдвинуться
    setMessage("");
  }

  function applyHint(hint: Hint) {
    const value = text.slice(0, hint.from) + hint.insert + text.slice(hint.to);
    changeText(value);
    const cursor = hint.from + hint.insert.length;
    requestAnimationFrame(() => {
      const el = textarea.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(cursor, cursor);
      setHints(hintsAt(value, cursor, suggestions));
    });
  }

  async function save() {
    setBusy(true);
    setError("");
    const selected: Record<number, string> = {};
    for (const item of items) {
      if (item.status === "ambiguous" && item.selected) selected[item.line] = item.selected;
    }
    try {
      const result = await api<CommitResult>("/entries/commit", { method: "POST", body: { text, date, choices: selected } });
      // В поле остаются только строки с ошибками — их можно исправить и сохранить снова.
      const failed = new Set(result.items.filter((i) => !i.saved).map((i) => i.line));
      const rest = text.split("\n").filter((_, idx) => failed.has(idx + 1));
      setText(rest.join("\n"));
      setChoices({});
      setItems([]);
      setMessage(
        `Сохранено строк: ${result.saved}` + (result.errors ? `. Не сохранено: ${result.errors} — они остались в поле.` : ""),
      );
      loadSuggestions();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  }

  const valid = items.filter((i) => i.status !== "error").length;
  const hasReturns = items.some((i) => i.kind === "return");

  return (
    <div className="stack">
      <div className="card stack">
        <div className="row">
          <label className="grow">
            Дата продажи
            <input type="date" value={date} max={today} onChange={(e) => setDate(e.target.value || today)} />
          </label>
          {date !== today && (
            <button className="link" onClick={() => setDate(today)}>
              Сегодня
            </button>
          )}
        </div>
        {date !== today && hasReturns && (
          <div className="note">Возвраты всегда проводятся сегодняшней датой ({formatDate(today)}).</div>
        )}
        <textarea
          ref={textarea}
          rows={8}
          value={text}
          placeholder={PLACEHOLDER}
          onChange={(e) => changeText(e.target.value)}
          onKeyUp={updateHints}
          onClick={updateHints}
          onInput={updateHints}
          onBlur={() => setTimeout(() => setHints([]), 200)}
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
        />
        {hints.length > 0 && (
          <div className="hints">
            {hints.map((h) => (
              <button key={h.label} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => applyHint(h)}>
                {h.label}
              </button>
            ))}
          </div>
        )}
        <div className="muted small">
          Формат: <code>марка запчасть - цена</code>, старый завоз: <code>с код запчасть - цена</code>, возврат:{" "}
          <code>возврат …</code>
        </div>
        {error && <div className="error">{error}</div>}
        {message && <div className="success">{message}</div>}
        <button className="primary" disabled={busy || valid === 0} onClick={save}>
          {busy ? "Сохранение…" : `Сохранить${valid ? ` (${valid})` : ""}`}
        </button>
      </div>

      {items.length > 0 && (
        <div className="stack">
          {items.map((item) => (
            <div key={item.line} className={`card entry ${item.status}`}>
              <div className="entry-head">
                <span className="muted">Строка {item.line}</span>
                {item.kind && <span className="badge">{item.kind === "return" ? "Возврат" : "Продажа"}</span>}
                <span className={`status ${item.status}`}>{STATUS_TEXT[item.status]}</span>
              </div>
              {item.kind ? (
                <div className="entry-body">
                  <b>{item.car_label}</b>
                  {item.old_car_code && <> · {item.old_car_code}</>} · {item.part} · <b>{formatMoney(item.price)}</b>
                  {item.kind === "sale" && item.sold_date && <span className="muted"> · {formatDate(item.sold_date)}</span>}
                  {item.kind === "return" && item.status === "ok" && item.sold_date && (
                    <span className="muted"> · продано {formatDate(item.sold_date)}</span>
                  )}
                </div>
              ) : (
                <div className="entry-body">{item.text}</div>
              )}
              {item.error && <div className="error">{item.error}</div>}
              {item.options.length > 0 && (
                <div className="options">
                  {item.options.map((o) => (
                    <label key={o.ref} className="option">
                      <input
                        type="radio"
                        name={`line-${item.line}`}
                        checked={item.selected === o.ref}
                        onChange={() => setChoices({ ...choices, [item.line]: o.ref })}
                      />
                      {describe(o)}
                    </label>
                  ))}
                </div>
              )}
              {item.similar.length > 0 && (
                <div className="similar">
                  <div className="muted small">Похожие продажи этой марки:</div>
                  <ul>
                    {item.similar.map((s) => (
                      <li key={s.ref}>{describe(s)}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
