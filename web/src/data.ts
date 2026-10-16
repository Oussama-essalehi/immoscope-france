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

export interface Region {
  code: string;
  name: string;
  departments: { code: string; label: string }[];
}

export interface CityMeta {
  name: string;
  dept: string;
  region: string;
  /** population rank in the scope (1 = largest) */
  rank: number;
  metropole: boolean;
}

export interface Meta {
  source: string;
  years: number[];
  lastYear: number;
  totalSales: number;
  communes: number;
  regions: Region[];
  departmentCount: number;
  types: string[];
  cities: CityMeta[];
  minSalesCommune: number;
  budgets: { min: number; max: number; step: number; default: number };
}

export interface Overview {
  /** key `zone|type` -> monthly points; zone = "all", "R11" (region) or "75" (department) */
  monthly: Record<string, ({ m: string } & Stat)[]>;
  /** key `zone|type` -> year (or "all") -> stats */
  yearly: Record<string, Record<string, Stat>>;
}

/** Map points (departments or communes) and their stats. */
export interface Points {
  /** [code, name, dept, lat, lon] */
  list: [string, string, string, number, number][];
  /** key `type|year` -> [pointIndex, n, p] (only points with enough sales) */
  stats: Record<string, [number, number, number][]>;
}

/** [code, name, dept, n, p] */
export type CommuneRow = [string, string, string, number, number];

export interface TopCommunes {
  /** key `type|year` -> most / least expensive communes of the whole scope */
  [key: string]: { top: CommuneRow[]; bottom: CommuneRow[] };
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
  departments: Points;
  topCommunes: TopCommunes;
  cities: Cities;
}

/** Filters shared by every page (like synchronised slicers). */
export interface Filters {
  region: string;
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
  const [meta, overview, departments, topCommunes, cities] = await Promise.all([
    getJson<Meta>("meta"),
    getJson<Overview>("overview"),
    getJson<Points>("departements"),
    getJson<TopCommunes>("communes_top"),
    getJson<Cities>("cities"),
  ]);
  return { meta, overview, departments, topCommunes, cities };
}

const regionCache = new Map<string, Promise<Points>>();

/** Communes of one region, downloaded once when the map needs them. */
export function loadRegionCommunes(region: string): Promise<Points> {
  if (!regionCache.has(region)) {
    const request = getJson<Points>(`communes_R${region}`);
    request.catch(() => regionCache.delete(region)); // allow a retry after a network error
    regionCache.set(region, request);
  }
  return regionCache.get(region)!;
}

// --------------------------------------------------------------------------- //
// Selectors
// --------------------------------------------------------------------------- //

/** Zone key of the overview series for the current filters. */
export function zoneOf(f: Pick<Filters, "region" | "dept">): string {
  if (f.dept !== ALL) return f.dept;
  if (f.region !== ALL) return `R${f.region}`;
  return ALL;
}

/** Region of a department code. */
export function regionOfDept(meta: Meta, dept: string): string | undefined {
  return meta.regions.find((r) => r.departments.some((d) => d.code === dept))?.code;
}

/** Departments offered by the department filter (those of the selected region). */
export function departmentsFor(meta: Meta, region: string): { code: string; label: string }[] {
  const regions = region === ALL ? meta.regions : meta.regions.filter((r) => r.code === region);
  return regions.flatMap((r) => r.departments).sort((a, b) => a.code.localeCompare(b.code));
}

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
  const yearly = overview.yearly[key(zoneOf(f), f.type)] ?? {};
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
  const series = overview.monthly[key(zoneOf(f), f.type)] ?? [];
  return f.year === ALL ? series : series.filter((point) => point.m.startsWith(f.year));
}

export interface MapPoint {
  code: string;
  name: string;
  dept: string;
  lat: number;
  lon: number;
  n: number;
  p: number;
}

/** Points with their stats for the type / year filters, optionally restricted to departments. */
export function mapPoints(points: Points, f: Pick<Filters, "type" | "year">, depts?: Set<string>): MapPoint[] {
  const rows = points.stats[key(f.type, f.year)] ?? [];
  return rows
    .map(([index, n, p]) => {
      const [code, name, dept, lat, lon] = points.list[index];
      return { code, name, dept, lat, lon, n, p };
    })
    .filter((point) => !depts || depts.has(point.dept));
}

/** Cities of the selection (all, or those of the selected region / department). */
export function citiesFor(meta: Meta, f: Pick<Filters, "region" | "dept">): CityMeta[] {
  return meta.cities.filter(
    (c) => (f.region === ALL || c.region === f.region) && (f.dept === ALL || c.dept === f.dept),
  );
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

/** Cities for one type and year, ranked by median price/m² (1 = most expensive). */
export function cityRanking(cities: Cities, list: CityMeta[], type: string, year: string): CityRow[] {
  const rows = list
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
export function yoyMatrix(cities: Cities, list: CityMeta[], years: number[], type: string): { city: string; values: (number | null)[] }[] {
  return list.map((c) => {
    const yearly = cities.yearly[key(c.name, type)] ?? {};
    return {
      city: c.name,
      values: years.map((y) => change(yearly[String(y)]?.p, yearly[String(y - 1)]?.p)),
    };
  });
}

export interface SimulatorRow extends CityRow {
  m2: number;
  income: number | null;
  yearsOfIncome: number | null;
}

/** Surface buyable with the budget at each city's median price/m², plus income ratio. */
export function simulate(cities: Cities, list: CityMeta[], type: string, year: string, budget: number): SimulatorRow[] {
  return cityRanking(cities, list, type, year)
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
