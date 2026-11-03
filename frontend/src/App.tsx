import { useEffect, useState } from "react";
import { api, setUnauthorizedHandler } from "./api";
import LoginPage from "./pages/LoginPage";
import EntryPage from "./pages/EntryPage";
import SalesPage from "./pages/SalesPage";
import ReturnsPage from "./pages/ReturnsPage";
import CarsPage from "./pages/CarsPage";
import StatsPage from "./pages/StatsPage";

const PAGES = [
  { id: "entry", title: "Ввод", component: EntryPage },
  { id: "sales", title: "Продажи", component: SalesPage },
  { id: "returns", title: "Возвраты", component: ReturnsPage },
  { id: "stats", title: "Статистика", component: StatsPage },
  { id: "cars", title: "Марки", component: CarsPage },
] as const;

function currentPage(): string {
  const id = window.location.hash.replace(/^#\/?/, "");
  return PAGES.some((p) => p.id === id) ? id : "entry";
}

export default function App() {
  const [auth, setAuth] = useState<"loading" | "in" | "out">("loading");
  const [page, setPage] = useState(currentPage);

  useEffect(() => {
    setUnauthorizedHandler(() => setAuth("out"));
    api("/auth/me")
      .then(() => setAuth("in"))
      .catch(() => setAuth("out"));
    const onHash = () => setPage(currentPage());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (auth === "loading") return <div className="center muted">Загрузка…</div>;
  if (auth === "out") return <LoginPage onLogin={() => setAuth("in")} />;

  const current = PAGES.find((p) => p.id === page)!;
  const Page = current.component;

  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    setAuth("out");
  }

  return (
    <div className="app">
      <header className="header">
        <span className="page-title">{current.title}</span>
        <nav className="nav">
          {PAGES.map((p) => (
            <a key={p.id} href={`#/${p.id}`} className={p.id === page ? "active" : ""}>
              {p.title}
            </a>
          ))}
        </nav>
        <button className="link" onClick={logout}>
          Выйти
        </button>
      </header>
      <main className="main">
        <Page />
      </main>
    </div>
  );
}
