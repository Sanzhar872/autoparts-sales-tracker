const TZ = "Asia/Almaty";

/** Сегодняшняя дата в Алматы в формате YYYY-MM-DD. */
export function todayAlmaty(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(
    new Date(),
  );
}

export function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function monthStart(iso: string): string {
  return `${iso.slice(0, 8)}01`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

export function formatMoney(value: number | undefined): string {
  return `${(value ?? 0).toLocaleString("ru-RU")} ₸`;
}

const LATIN_TO_CYRILLIC: Record<string, string> = {
  a: "а", c: "с", e: "е", k: "к", m: "м", o: "о", p: "р", t: "т", x: "х", y: "у", b: "в", h: "н",
};

/** Нормализация марки — как на сервере. */
export function normalizeCar(name: string): string {
  return [...name.toLowerCase()].map((ch) => LATIN_TO_CYRILLIC[ch] ?? ch).join("");
}

export function partKey(part: string): string {
  return part.trim().split(/\s+/).join(" ").toLowerCase();
}
