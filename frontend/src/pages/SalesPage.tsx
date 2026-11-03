import { useEffect, useState } from "react";
import { api, ApiError, Car, Paged, query, Sale } from "../api";
import { CarSelect, EMPTY_FILTERS, ExportPanel, Filters, FilterValues, Summary, useCars } from "../components";
import { formatDate, formatMoney, todayAlmaty } from "../util";

const PAGE = 100;

function SaleEditor({ sale, cars, onDone }: { sale: Sale; cars: Car[]; onDone: (changed: boolean) => void }) {
  const [carId, setCarId] = useState<number | "">(sale.car_id);
  const [code, setCode] = useState(sale.old_car_code ?? "");
  const [part, setPart] = useState(sale.part);
  const [price, setPrice] = useState(String(sale.price));
  const [date, setDate] = useState(sale.sold_date);
  const [error, setError] = useState("");
  const isOld = cars.find((c) => c.id === carId)?.is_service ?? false;

  async function save() {
    try {
      await api(`/sales/${sale.id}`, {
        method: "PATCH",
        body: { car_id: carId, old_car_code: isOld ? code : null, part, price: Number(price.replace(/\s/g, "")), sold_date: date },
      });
      onDone(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Ошибка сохранения");
    }
  }

  return (
    <div className="editor">
      <div className="filters">
        <label>
          Марка
          <CarSelect cars={cars} value={carId} onChange={setCarId} />
        </label>
        {isOld && (
          <label>
            Код машины
            <input value={code} onChange={(e) => setCode(e.target.value)} />
          </label>
        )}
        <label className="grow">
          Запчасть
          <input value={part} onChange={(e) => setPart(e.target.value)} />
        </label>
        <label>
          Цена
          <input inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value)} />
        </label>
        <label>
          Дата
          <input type="date" value={date} max={todayAlmaty()} onChange={(e) => setDate(e.target.value)} />
        </label>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="row">
        <button className="primary" onClick={save}>
          Сохранить
        </button>
        <button onClick={() => onDone(false)}>Отмена</button>
      </div>
    </div>
  );
}

export default function SalesPage() {
  const [cars] = useCars();
  const [filters, setFilters] = useState<FilterValues>(EMPTY_FILTERS);
  const [data, setData] = useState<Paged<Sale>>({ items: [], total: 0, sum: 0 });
  const [limit, setLimit] = useState(PAGE);
  const [editing, setEditing] = useState<number | null>(null);
  const [error, setError] = useState("");

  function load() {
    const params = { from: filters.from, to: filters.to, car_id: filters.carId, q: filters.q, limit };
    api<Paged<Sale>>(`/sales${query(params)}`)
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

  async function remove(sale: Sale) {
    if (!confirm(`Удалить продажу «${sale.part}» за ${formatMoney(sale.price)}?`)) return;
    try {
      await api(`/sales/${sale.id}`, { method: "DELETE" });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Ошибка удаления");
    }
  }

  return (
    <div className="stack">
      <Filters cars={cars} value={filters} onChange={(f) => { setFilters(f); setLimit(PAGE); }} />
      <Summary total={data.total} sum={data.sum} shown={data.items.length} />
      {error && <div className="error">{error}</div>}
      <div className="list">
        {data.items.map((sale) => (
          <div key={sale.id} className="card item">
            {editing === sale.id ? (
              <SaleEditor
                sale={sale}
                cars={cars}
                onDone={(changed) => {
                  setEditing(null);
                  if (changed) load();
                }}
              />
            ) : (
              <>
                <div className="item-main">
                  <div>
                    <b>{sale.car_label}</b>
                    {sale.old_car_code && <> · {sale.old_car_code}</>} · {sale.part}
                  </div>
                  <div className="muted small">{formatDate(sale.sold_date)}</div>
                </div>
                <div className="item-price">{formatMoney(sale.price)}</div>
                <div className="item-actions">
                  <button onClick={() => setEditing(sale.id)}>Изменить</button>
                  <button className="danger" onClick={() => remove(sale)}>
                    Удалить
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
        {data.items.length === 0 && <div className="muted center-text">Продаж не найдено</div>}
      </div>
      {data.items.length < data.total && <button onClick={() => setLimit(limit + PAGE)}>Показать ещё</button>}
      <h3>Выгрузка</h3>
      <ExportPanel />
    </div>
  );
}
