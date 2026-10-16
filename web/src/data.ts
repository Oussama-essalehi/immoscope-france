/**
 * Data access layer: types of the JSON aggregates exported by `src/export_web.py`
 * and pure selectors used by the pages (unit-tested in data.test.ts).
 */

export const ALL = "all";

/** Aggregated statistics: sales count, median price/m², median price, median surface. */
export interface Stat {
  n: number;
  p: number;
  v?: number;
  s?: number;
}

export interface Meta {
  source: string;
  years: number[];
  lastYear: number;
  totalSales: number;
  communes: number;
  departments: { code: string; label: string }[];
  types: string[];
  cities: { name: string; dept: string; metropole: boolean }[];
  metropoles: string[];
  minSalesCommune: number;
  budgets: { min: number; max: number; step: number; default: number };
}

export interface Overview {
  /** key `dept|type` -> monthly points */
  monthly: Record<string, ({ m: string } & Stat)[]>;
  /** key `dept|type` -> year (or "all") -> stats */
  yearly: Record<string, Record<string, Stat>>;
}

export interface Communes {
  /** [code, name, dept, lat, lon] */
  list: [string, string, string, number, number][];
  /** key `type|year` -> [communeIndex, n, p] (only communes with enough sales) */
  stats: Record<string, [number, number, number][]>;
}

export interface Cities {
  yearly: Record<string, Record<string, Stat>>;
  quarterly: Record<string, ({ q: string } & Stat)[]>;
  /** estimated median household income (EUR / year, INSEE Filosofi 2021) */
  income: Record<string, number>;
}

export interface Dataset {
  meta: Meta;
  overview: Overview;
  communes: Communes;
  cities: Cities;
}

/** Filters shared by every page (like synchronised slicers). */
export interface Filters {
  dept: string;
  type: string;
  year: string;
}

export const key = (...parts: (string | number)[]): string => parts.join("|");

async function getJson<T>(name: string): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/${name}.json`);
  if (!response.ok) throw new Error(`Impossible de charger ${name}.json (${response.status})`);
  return (await response.json()) as T;
}

export async function loadDataset(): Promise<Dataset> {
  const [meta, overview, communes, cities] = await Promise.all([
    getJson<Meta>("meta"),
    getJson<Overview>("overview"),
    getJson<Communes>("communes"),
    getJson<Cities>("cities"),
  ]);
  return { meta, overview, communes, cities };
}

// --------------------------------------------------------------------------- //
// Selectors
// --------------------------------------------------------------------------- //

/** Relative change, or null when the reference is missing. */
export function change(current: number | undefined, previous: number | undefined): number | null {
  if (current === undefined || previous === undefined || previous === 0) return null;
  return current / previous - 1;
}

export interface Kpis {
  sales: number | null;
  price: number | null;
  priceChange: number | null;
  volumeChange: number | null;
  /** year compared with the previous one for the changes */
  comparedYear: number;
}

/**
 * Headline figures for the selection. Changes compare the selected year with the
 * previous one; with no year selected, the last year with the one before (same
 * rule as the Power BI measures).
 */
export function kpis(overview: Overview, meta: Meta, f: Filters): Kpis {
  const yearly = overview.yearly[key(f.dept, f.type)] ?? {};
  const current = yearly[f.year];
  const compared = f.year === ALL ? meta.lastYear : Number(f.year);
  const now = yearly[String(compared)];
  const before = yearly[String(compared - 1)];
  return {
    sales: current?.n ?? null,
    price: current?.p ?? null,
    priceChange: change(now?.p, before?.p),
    volumeChange: change(now?.n, before?.n),
    comparedYear: compared,
  };
}

export function monthlySeries(overview: Overview, f: Filters): ({ m: string } & Stat)[] {
  const series = overview.monthly[key(f.dept, f.type)] ?? [];
  return f.year === ALL ? series : series.filter((point) => point.m.startsWith(f.year));
}

export interface CommunePoint {
  code: string;
  name: string;
  dept: string;
  lat: number;
  lon: number;
  n: number;
  p: number;
}

export function communePoints(communes: Communes, f: Filters): CommunePoint[] {
  const rows = communes.stats[key(f.type, f.year)] ?? [];
  return rows
    .map(([index, n, p]) => {
      const [code, name, dept, lat, lon] = communes.list[index];
      return { code, name, dept, lat, lon, n, p };
    })
    .filter((point) => f.dept === ALL || point.dept === f.dept);
}

export interface CityRow {
  city: string;
  dept: string;
  metropole: boolean;
  n: number;
  p: number;
  v: number;
  s: number;
  rank: number;
}

/** Main cities for one type and year, ranked by median price/m² (1 = most expensive). */
export function cityRanking(cities: Cities, meta: Meta, type: string, year: string): CityRow[] {
  const rows = meta.cities
    .map((c) => {
      const stat = cities.yearly[key(c.name, type)]?.[year];
      return stat ? { city: c.name, dept: c.dept, metropole: c.metropole, n: stat.n, p: stat.p, v: stat.v ?? 0, s: stat.s ?? 0, rank: 0 } : null;
    })
    .filter((row): row is CityRow => row !== null)
    .sort((a, b) => b.p - a.p);
  rows.forEach((row, i) => (row.rank = i + 1));
  return rows;
}

/** Year-over-year change of the median price/m² for each city and year. */
export function yoyMatrix(cities: Cities, meta: Meta, type: string): { city: string; values: (number | null)[] }[] {
  return meta.cities.map((c) => {
    const yearly = cities.yearly[key(c.name, type)] ?? {};
    return {
      city: c.name,
      values: meta.years.map((y) => change(yearly[String(y)]?.p, yearly[String(y - 1)]?.p)),
    };
  });
}

export interface SimulatorRow extends CityRow {
  m2: number;
  income: number | null;
  yearsOfIncome: number | null;
}

/** Surface buyable with the budget at each city's median price/m², plus income ratio. */
export function simulate(cities: Cities, meta: Meta, type: string, year: string, budget: number): SimulatorRow[] {
  return cityRanking(cities, meta, type, year)
    .map((row) => {
      const income = cities.income[row.city] ?? null;
      return {
        ...row,
        m2: budget / row.p,
        income,
        yearsOfIncome: income ? row.v / income : null,
      };
    })
    .sort((a, b) => b.m2 - a.m2);
}

/** Split values into `bins` quantile classes; returns the upper bounds. */
export function quantileBreaks(values: number[], bins: number): number[] {
  if (values.length === 0) return [];
  const sorted = [...values].sort((a, b) => a - b);
  return Array.from({ length: bins - 1 }, (_, i) => sorted[Math.floor(((i + 1) * sorted.length) / bins)]);
}

export function binIndex(value: number, breaks: number[]): number {
  const i = breaks.findIndex((b) => value < b);
  return i === -1 ? breaks.length : i;
}
