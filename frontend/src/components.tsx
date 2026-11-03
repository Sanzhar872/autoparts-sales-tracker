import { useEffect, useState } from "react";
import { api, Car, query } from "./api";
import { formatMoney } from "./util";

export function useCars(): [Car[], () => void] {
  const [cars, setCars] = useState<Car[]>([]);
  const load = () => {
    api<Car[]>("/cars").then(setCars).catch(() => {});
  };
  useEffect(load, []);
  return [cars, load];
}

export function CarSelect({
  cars,
  value,
  onChange,
  allLabel,
}: {
  cars: Car[];
  value: number | "";
  onChange: (value: number | "") => void;
  allLabel?: string;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : "")}>
      {allLabel && <option value="">{allLabel}</option>}
      {cars.map((c) => (
        <option key={c.id} value={c.id}>
          {c.label}
        </option>
      ))}
    </select>
  );
}

export interface FilterValues {
  from: string;
  to: string;
  carId: number | "";
  q: string;
}

export const EMPTY_FILTERS: FilterValues = { from: "", to: "", carId: "", q: "" };

export function Filters({ cars, value, onChange }: { cars: Car[]; value: FilterValues; onChange: (v: FilterValues) => void }) {
  return (
    <div className="card filters">
      <label>
        С
        <input type="date" value={value.from} onChange={(e) => onChange({ ...value, from: e.target.value })} />
      </label>
      <label>
        По
        <input type="date" value={value.to} onChange={(e) => onChange({ ...value, to: e.target.value })} />
      </label>
      <label>
        Марка
        <CarSelect cars={cars} value={value.carId} onChange={(carId) => onChange({ ...value, carId })} allLabel="Все" />
      </label>
      <label className="grow">
        Поиск
        <input type="search" value={value.q} placeholder="запчасть или код" onChange={(e) => onChange({ ...value, q: e.target.value })} />
      </label>
    </div>
  );
}

export function Summary({ total, sum, shown }: { total: number; sum: number; shown: number }) {
  return (
    <div className="muted small">
      Найдено: {total} на {formatMoney(sum)}
      {shown < total && ` · показано ${shown}`}
    </div>
  );
}

export function ExportPanel() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const href = `/api/export.xlsx${query({ from, to })}`;
  return (
    <div className="card filters">
      <label>
        С
        <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
      </label>
      <label>
        По
        <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
      </label>
      <a className="button primary" href={href} download>
        Скачать Excel
      </a>
      <span className="muted small">Без дат — выгрузка за всё время</span>
    </div>
  );
}

export function BarChart({ data }: { data: { label: string; value: number; title: string }[] }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="chart">
      {data.map((d) => (
        <div key={d.label} className="bar-col" title={d.title}>
          <div className="bar-value">{d.value ? Math.round(d.value / 1000).toLocaleString("ru-RU") + "к" : ""}</div>
          <div className="bar" style={{ height: `${(d.value / max) * 100}%` }} />
          <div className="bar-label">{d.label}</div>
        </div>
      ))}
    </div>
  );
}
