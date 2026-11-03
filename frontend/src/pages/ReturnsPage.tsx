import { useEffect, useState } from "react";
import { api, ApiError, Paged, query, ReturnItem } from "../api";
import { EMPTY_FILTERS, Filters, FilterValues, Summary, useCars } from "../components";
import { formatDate, formatMoney } from "../util";

const PAGE = 100;

export default function ReturnsPage() {
  const [cars] = useCars();
  const [filters, setFilters] = useState<FilterValues>(EMPTY_FILTERS);
  const [data, setData] = useState<Paged<ReturnItem>>({ items: [], total: 0, sum: 0 });
  const [limit, setLimit] = useState(PAGE);
  const [error, setError] = useState("");

  function load() {
    const params = { from: filters.from, to: filters.to, car_id: filters.carId, q: filters.q, limit };
    api<Paged<ReturnItem>>(`/returns${query(params)}`)
      .then((d) => {
        setData(d);
        setError("");
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Ошибка загрузки"));
  }

  useEffect(() => {
    const timer = setTimeout(load, 300);
    return () => clearTimeout(timer);
  }, [filters, limit]);

  async function cancel(ret: ReturnItem) {
    if (!confirm(`Отменить возврат «${ret.part}»? Продажа восстановится с датой ${formatDate(ret.sold_date)}.`)) return;
    try {
      await api(`/returns/${ret.id}/cancel`, { method: "POST" });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Ошибка отмены");
    }
  }

  return (
    <div className="stack">
      <div className="muted small">Период фильтруется по дате возврата.</div>
      <Filters cars={cars} value={filters} onChange={(f) => { setFilters(f); setLimit(PAGE); }} />
      <Summary total={data.total} sum={data.sum} shown={data.items.length} />
      {error && <div className="error">{error}</div>}
      <div className="list">
        {data.items.map((ret) => (
          <div key={ret.id} className="card item">
            <div className="item-main">
              <div>
                <b>{ret.car_label}</b>
                {ret.old_car_code && <> · {ret.old_car_code}</>} · {ret.part}
              </div>
              <div className="muted small">
                продано {formatDate(ret.sold_date)} · возврат {formatDate(ret.returned_date)}
              </div>
            </div>
            <div className="item-price">{formatMoney(ret.price)}</div>
            <div className="item-actions">
              <button onClick={() => cancel(ret)}>Отменить возврат</button>
            </div>
          </div>
        ))}
        {data.items.length === 0 && <div className="muted center-text">Возвратов не найдено</div>}
      </div>
      {data.items.length < data.total && <button onClick={() => setLimit(limit + PAGE)}>Показать ещё</button>}
    </div>
  );
}
