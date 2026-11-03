import { useEffect, useState } from "react";
import { api, ApiError, query, Stats } from "../api";
import { BarChart, CarSelect, ExportPanel, useCars } from "../components";
import { formatDate, formatMoney } from "../util";

const MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

function periodLabel(start: string, group: "week" | "month"): string {
  const [y, m, d] = start.split("-");
  return group === "month" ? `${MONTHS[Number(m) - 1]} ${y.slice(2)}` : `${d}.${m}`;
}

export default function StatsPage() {
  const [cars] = useCars();
  const [group, setGroup] = useState<"week" | "month">("week");
  const [carId, setCarId] = useState<number | "">("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Stats>(`/stats${query({ group, car_id: carId, from, to })}`)
      .then((s) => {
        setStats(s);
        setError("");
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Ошибка загрузки"));
  }, [group, carId, from, to]);

  return (
    <div className="stack">
      <div className="card filters">
        <div className="segmented">
          <button className={group === "week" ? "active" : ""} onClick={() => setGroup("week")}>
            По неделям
          </button>
          <button className={group === "month" ? "active" : ""} onClick={() => setGroup("month")}>
            По месяцам
          </button>
        </div>
        <label>
          Марка
          <CarSelect cars={cars} value={carId} onChange={setCarId} allLabel="Все марки" />
        </label>
        <label>
          С
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label>
          По
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
      </div>
      {error && <div className="error">{error}</div>}
      {stats && (
        <>
          <div className="muted small">
            {formatDate(stats.from)} — {formatDate(stats.to)}. Выручка — по действующим продажам; возвращённые продажи в
            неё уже не входят.
          </div>
          <div className="tiles">
            <div className="card tile">
              <div className="muted small">Выручка</div>
              <div className="tile-value">{formatMoney(stats.total.revenue)}</div>
            </div>
            <div className="card tile">
              <div className="muted small">Продаж</div>
              <div className="tile-value">{stats.total.count}</div>
            </div>
            <div className="card tile">
              <div className="muted small">Возвраты</div>
              <div className="tile-value">
                {stats.total.returns_count} · {formatMoney(stats.total.returns_sum)}
              </div>
            </div>
          </div>
          <div className="card">
            <BarChart
              data={stats.periods.map((p) => ({
                label: periodLabel(p.start, stats.group),
                value: p.revenue,
                title: `${formatDate(p.start)} — ${formatDate(p.end)}: ${formatMoney(p.revenue)}, продаж ${p.count}`,
              }))}
            />
          </div>
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{stats.group === "week" ? "Неделя" : "Месяц"}</th>
                  <th className="num">Продаж</th>
                  <th className="num">Выручка</th>
                  <th className="num">Возвратов</th>
                  <th className="num">Сумма возвратов</th>
                </tr>
              </thead>
              <tbody>
                {[...stats.periods].reverse().map((p) => (
                  <tr key={p.start}>
                    <td>
                      {formatDate(p.start)} — {formatDate(p.end)}
                    </td>
                    <td className="num">{p.count}</td>
                    <td className="num">{formatMoney(p.revenue)}</td>
                    <td className="num">{p.returns_count}</td>
                    <td className="num">{formatMoney(p.returns_sum)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {carId === "" && stats.by_car.length > 0 && (
            <div className="card table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Марка</th>
                    <th className="num">Продаж</th>
                    <th className="num">Выручка</th>
                    <th className="num">Возвратов</th>
                    <th className="num">Сумма возвратов</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.by_car.map((c) => (
                    <tr key={c.car_id}>
                      <td>{c.label}</td>
                      <td className="num">{c.count}</td>
                      <td className="num">{formatMoney(c.revenue)}</td>
                      <td className="num">{c.returns_count}</td>
                      <td className="num">{formatMoney(c.returns_sum)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      <h3>Выгрузка в Excel</h3>
      <ExportPanel />
    </div>
  );
}
