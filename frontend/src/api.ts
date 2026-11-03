export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

function errorMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Проверьте введённые данные";
  return "Ошибка запроса";
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: options.method ?? "GET",
      headers: options.body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "Нет связи с сервером");
  }
  if (response.status === 401 && !path.startsWith("/auth/login")) {
    onUnauthorized();
  }
  if ([502, 503, 504].includes(response.status)) {
    throw new ApiError(response.status, "Сервер просыпается или недоступен — повторите через минуту");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(response.status, errorMessage(data.detail));
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export interface Car {
  id: number;
  name: string;
  label: string;
  is_service: boolean;
  sales_count: number;
  returns_count: number;
}

export interface Sale {
  id: number;
  car_id: number;
  car: string;
  car_label: string;
  old_car_code: string | null;
  part: string;
  price: number;
  sold_date: string;
}

export interface ReturnItem extends Sale {
  returned_date: string;
}

export interface Paged<T> {
  items: T[];
  total: number;
  sum: number;
}

export interface Candidate {
  ref: string;
  sale_id: number | null;
  line: number | null;
  old_car_code: string | null;
  part: string;
  price: number;
  sold_date: string;
}

export interface EntryItem {
  line: number;
  text: string;
  kind: "sale" | "return" | null;
  status: "ok" | "error" | "ambiguous";
  error: string | null;
  saved: boolean;
  car?: string;
  car_label?: string;
  old_car_code?: string | null;
  part?: string;
  price?: number;
  sold_date?: string;
  returned_date?: string;
  options: Candidate[];
  selected: string | null;
  similar: Candidate[];
}

export interface CommitResult {
  items: EntryItem[];
  saved: number;
  errors: number;
}

export interface StatsRow {
  count: number;
  revenue: number;
  returns_count: number;
  returns_sum: number;
}

export interface Stats {
  group: "week" | "month";
  from: string;
  to: string;
  periods: (StatsRow & { start: string; end: string })[];
  by_car: (StatsRow & { car_id: number; label: string })[];
  total: StatsRow;
}

export interface Suggestions {
  cars: { name: string; label: string }[];
  parts: Record<string, string[]>;
  codes: string[];
}
