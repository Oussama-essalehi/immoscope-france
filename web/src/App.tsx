import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { LangSwitch, ThemeSwitch } from "./components/Switches";
import { WelcomeDialog } from "./components/WelcomeDialog";
import { ALL, loadDataset, type Dataset, type Filters } from "./data";
import type { Lang } from "./format";
import { browserLang, I18nContext, makeI18n } from "./i18n";
import type { MessageKey } from "./locales";
import { Cities } from "./pages/Cities";
import { Overview } from "./pages/Overview";
import { Simulator } from "./pages/Simulator";
import { PALETTES, ThemeContext, type Mode } from "./theme";

// The map page (Leaflet) is only downloaded when it is opened
const PriceMap = lazy(() => import("./pages/PriceMap").then((m) => ({ default: m.PriceMap })));

const PAGES: { id: string; label: MessageKey }[] = [
  { id: "vue-ensemble", label: "nav.overview" },
  { id: "carte", label: "nav.map" },
  { id: "villes", label: "nav.cities" },
  { id: "simulateur", label: "nav.simulator" },
];

const REPO_URL = "https://github.com/Oussama-essalehi/immoscope-france";
const STORAGE = { theme: "dvf-theme", lang: "dvf-lang", welcome: "dvf-welcome-seen" };

/** Current page from the URL hash (#/carte), so that links and reloads keep the page. */
function pageFromHash(): string {
  const id = window.location.hash.replace(/^#\/?/, "");
  return PAGES.find((p) => p.id === id)?.id ?? "vue-ensemble";
}

/** localStorage can be unavailable (private mode, blocked storage): never fail on it. */
function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* the preference simply is not remembered */
  }
}

function initialMode(): Mode {
  const stored = readStorage(STORAGE.theme);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function initialLang(): Lang {
  const stored = readStorage(STORAGE.lang);
  return stored === "fr" || stored === "en" ? stored : browserLang();
}

export default function App() {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<string>(pageFromHash);
  const [filters, setFilters] = useState<Filters>({ region: ALL, dept: ALL, type: ALL, year: ALL });
  const [budget, setBudget] = useState(250_000);
  const [mode, setMode] = useState<Mode>(initialMode);
  const [lang, setLang] = useState<Lang>(initialLang);
  // Introduction dialog: opened automatically on the first visit only
  const [welcomeOpen, setWelcomeOpen] = useState(() => readStorage(STORAGE.welcome) === null);

  const i18n = useMemo(() => makeI18n(lang), [lang]);
  const { t, f } = i18n;

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

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = lang === "fr" ? "Marché immobilier DVF" : "French housing market (DVF)";
  }, [lang]);

  const changeMode = (next: Mode) => {
    setMode(next);
    writeStorage(STORAGE.theme, next);
  };

  const changeLang = (next: Lang) => {
    setLang(next);
    writeStorage(STORAGE.lang, next);
  };

  const closeWelcome = () => {
    setWelcomeOpen(false);
    writeStorage(STORAGE.welcome, "1");
  };

  return (
    <I18nContext.Provider value={i18n}>
      <ThemeContext.Provider value={PALETTES[mode]}>
        <div className="app">
          <header className="app-header">
            <div>
              <h1>{t("app.title", { r: data?.meta.regions.length ?? 10 })}</h1>
              <p className="lede">
                {data ? t("app.lede", { n: f.int(data.meta.totalSales), d: data.meta.departmentCount }) : t("app.loadingData")}
              </p>
            </div>
            <div className="header-controls">
              <button type="button" className="ghost-button" onClick={() => setWelcomeOpen(true)}>
                {t("app.about")}
              </button>
              <LangSwitch lang={lang} onChange={changeLang} />
              <ThemeSwitch mode={mode} onChange={changeMode} />
            </div>
          </header>

          <nav className="tabs" aria-label={t("app.pagesNav")}>
            {PAGES.map((p) => (
              <a key={p.id} href={`#/${p.id}`} className={p.id === page ? "tab active" : "tab"} aria-current={p.id === page ? "page" : undefined}>
                {t(p.label)}
              </a>
            ))}
          </nav>

          <main>
            {error && <p className="error">{error}</p>}
            {!data && !error && <p className="loading">{t("app.loading")}</p>}
            {data && page === "vue-ensemble" && <Overview data={data} filters={filters} onFilters={setFilters} />}
            {data && page === "carte" && (
              <Suspense fallback={<p className="loading">{t("app.loadingMap")}</p>}>
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
              {t("footer.source")} <a href="https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees">DVF géolocalisées</a> (Etalab /
              DGFiP) {t("footer.and")} <a href="https://www.insee.fr/fr/statistiques/7756729">INSEE Filosofi 2021</a>. {t("footer.method")}{" "}
              <a href={REPO_URL}>{t("footer.repo")}</a>.
            </p>
            <p>
              Oussama Essalehi · <a href="https://www.linkedin.com/in/oussama-essalehi">LinkedIn</a> ·{" "}
              <a href="https://oussama-essalehi.dev">oussama-essalehi.dev</a>
            </p>
          </footer>
        </div>

        <WelcomeDialog open={welcomeOpen} onClose={closeWelcome} meta={data?.meta ?? null} lang={lang} onLang={changeLang} />
      </ThemeContext.Provider>
    </I18nContext.Provider>
  );
}
