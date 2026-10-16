import { lazy, Suspense, useEffect, useState } from "react";
import { ALL, loadDataset, type Dataset, type Filters } from "./data";
import { fmtInt } from "./format";
import { Cities } from "./pages/Cities";
import { Overview } from "./pages/Overview";
import { Simulator } from "./pages/Simulator";
import { PALETTES, ThemeContext, type Mode } from "./theme";

// The map page (Leaflet) is only downloaded when it is opened
const PriceMap = lazy(() => import("./pages/PriceMap").then((m) => ({ default: m.PriceMap })));

const PAGES = [
  { id: "vue-ensemble", label: "Vue d'ensemble" },
  { id: "carte", label: "Carte des prix" },
  { id: "villes", label: "Comparaison des villes" },
  { id: "simulateur", label: "Simulateur budget" },
] as const;
type PageId = (typeof PAGES)[number]["id"];

const REPO_URL = "https://github.com/Oussama-essalehi/dvf-immobilier-analyse";

/** Current page from the URL hash (#/carte), so that links and reloads keep the page. */
function pageFromHash(): PageId {
  const id = window.location.hash.replace(/^#\/?/, "");
  return (PAGES.find((p) => p.id === id)?.id ?? "vue-ensemble") as PageId;
}

function systemMode(): Mode {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function storedMode(): Mode | null {
  try {
    const value = localStorage.getItem("dvf-theme");
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

export default function App() {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<PageId>(pageFromHash);
  const [filters, setFilters] = useState<Filters>({ dept: ALL, type: ALL, year: ALL });
  const [budget, setBudget] = useState(250_000);
  const [mode, setMode] = useState<Mode>(() => storedMode() ?? systemMode());

  useEffect(() => {
    loadDataset()
      .then((d) => {
        setData(d);
        setBudget(d.meta.budgets.default);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = mode;
  }, [mode]);

  const toggleMode = () => {
    const next = mode === "dark" ? "light" : "dark";
    setMode(next);
    try {
      localStorage.setItem("dvf-theme", next);
    } catch {
      /* storage unavailable: the choice simply is not remembered */
    }
  };

  return (
    <ThemeContext.Provider value={PALETTES[mode]}>
      <div className="app">
        <header className="app-header">
          <div>
            <h1>Marché immobilier : 5 départements, 2021-2025</h1>
            <p className="lede">
              {data
                ? `${fmtInt(data.meta.totalSales)} ventes d'un seul logement (maison ou appartement) en Haute-Garonne, Gironde, Hérault, Loire-Atlantique et Rhône.`
                : "Chargement des données…"}
            </p>
          </div>
          <button type="button" className="ghost-button" onClick={toggleMode} aria-label="Changer de thème">
            {mode === "dark" ? "Thème clair" : "Thème sombre"}
          </button>
        </header>

        <nav className="tabs" aria-label="Pages du tableau de bord">
          {PAGES.map((p) => (
            <a key={p.id} href={`#/${p.id}`} className={p.id === page ? "tab active" : "tab"} aria-current={p.id === page ? "page" : undefined}>
              {p.label}
            </a>
          ))}
        </nav>

        <main>
          {error && <p className="error">{error}</p>}
          {!data && !error && <p className="loading">Chargement…</p>}
          {data && page === "vue-ensemble" && <Overview data={data} filters={filters} onFilters={setFilters} />}
          {data && page === "carte" && (
            <Suspense fallback={<p className="loading">Chargement de la carte…</p>}>
              <PriceMap data={data} filters={filters} onFilters={setFilters} dark={mode === "dark"} />
            </Suspense>
          )}
          {data && page === "villes" && <Cities data={data} filters={filters} onFilters={setFilters} />}
          {data && page === "simulateur" && (
            <Simulator data={data} filters={filters} onFilters={setFilters} budget={budget} onBudget={setBudget} />
          )}
        </main>

        <footer className="app-footer">
          <p>
            Source : <a href="https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees">DVF géolocalisées</a> (Etalab / DGFiP) et{" "}
            <a href="https://www.insee.fr/fr/statistiques/7756729">INSEE Filosofi 2021</a>. Médianes en euros courants, ventes d'un seul logement après
            nettoyage. Méthode et code : <a href={REPO_URL}>dépôt GitHub</a>.
          </p>
          <p>
            Oussama Essalehi · <a href="https://www.linkedin.com/in/oussama-essalehi">LinkedIn</a> · <a href="https://oussama-essalehi.dev">oussama-essalehi.dev</a>
          </p>
        </footer>
      </div>
    </ThemeContext.Provider>
  );
}
