import { FormEvent, useState } from "react";
import { api, ApiError, Car } from "../api";
import { useCars } from "../components";

export default function CarsPage() {
  const [cars, reload] = useCars();
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState("");

  async function run(action: () => Promise<unknown>) {
    setError("");
    try {
      await action();
      reload();
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Ошибка");
      return false;
    }
  }

  async function add(e: FormEvent) {
    e.preventDefault();
    if (await run(() => api("/cars", { method: "POST", body: { name } }))) setName("");
  }

  async function rename(car: Car) {
    if (await run(() => api(`/cars/${car.id}`, { method: "PATCH", body: { name: newName } }))) setEditing(null);
  }

  function remove(car: Car) {
    if (confirm(`Удалить марку «${car.name}»?`)) run(() => api(`/cars/${car.id}`, { method: "DELETE" }));
  }

  return (
    <div className="stack">
      <form className="card row" onSubmit={add}>
        <input className="grow" value={name} placeholder="Новая марка" onChange={(e) => setName(e.target.value)} />
        <button className="primary" disabled={!name.trim()}>
          Добавить
        </button>
      </form>
      <div className="muted small">Одно слово. Названия приводятся к нижнему регистру, латинские двойники заменяются на кириллицу.</div>
      {error && <div className="error">{error}</div>}
      <div className="list">
        {cars.map((car) => {
          const used = car.sales_count + car.returns_count > 0;
          return (
            <div key={car.id} className="card item">
              {editing === car.id ? (
                <div className="row grow">
                  <input className="grow" value={newName} onChange={(e) => setNewName(e.target.value)} autoFocus />
                  <button className="primary" onClick={() => rename(car)}>
                    Сохранить
                  </button>
                  <button onClick={() => setEditing(null)}>Отмена</button>
                </div>
              ) : (
                <>
                  <div className="item-main">
                    <div>
                      <b>{car.name}</b>
                      {car.is_service && <span className="muted"> — {car.label}, служебная</span>}
                    </div>
                    <div className="muted small">
                      продаж: {car.sales_count} · возвратов: {car.returns_count}
                    </div>
                  </div>
                  {!car.is_service && (
                    <div className="item-actions">
                      <button
                        onClick={() => {
                          setEditing(car.id);
                          setNewName(car.name);
                        }}
                      >
                        Переименовать
                      </button>
                      <button
                        className="danger"
                        disabled={used}
                        title={used ? "Есть продажи или возвраты" : ""}
                        onClick={() => remove(car)}
                      >
                        Удалить
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
