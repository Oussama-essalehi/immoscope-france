import { describe, expect, it } from "vitest";
import {
  ALL,
  binIndex,
  change,
  citiesFor,
  cityRanking,
  departmentsFor,
  kpis,
  mapPoints,
  monthlySeries,
  quantileBreaks,
  regionOfDept,
  simulate,
  yoyMatrix,
  zoneOf,
  type Cities,
  type Meta,
  type Overview,
  type Points,
} from "./data";
import { makeFormatters } from "./format";
import { makeI18n } from "./i18n";
import { en, fr } from "./locales";

const meta: Meta = {
  source: "test",
  years: [2024, 2025],
  lastYear: 2025,
  totalSales: 30,
  communes: 2,
  regions: [
    { code: "84", name: "Auvergne-Rhône-Alpes", departments: [{ code: "69", label: "Rhône" }] },
    { code: "11", name: "Île-de-France", departments: [{ code: "92", label: "Hauts-de-Seine" }, { code: "75", label: "Paris" }] },
  ],
  departmentCount: 3,
  types: ["Appartement", "Maison"],
  cities: [
    { name: "Lyon", dept: "69", region: "84", rank: 2, metropole: true },
    { name: "Villeurbanne", dept: "69", region: "84", rank: 3, metropole: false },
    { name: "Paris", dept: "75", region: "11", rank: 1, metropole: true },
  ],
  minSalesCommune: 30,
  budgets: { min: 100000, max: 500000, step: 10000, default: 250000 },
};

const all = { region: ALL, dept: ALL, type: ALL, year: ALL };

const overview: Overview = {
  monthly: {
    "all|all": [
      { m: "2024-12", n: 10, p: 3000 },
      { m: "2025-01", n: 12, p: 3100 },
    ],
    "R84|all": [{ m: "2025-01", n: 5, p: 4000 }],
  },
  yearly: {
    "all|all": {
      "2024": { n: 100, p: 3000 },
      "2025": { n: 120, p: 2970 },
      all: { n: 220, p: 2985 },
    },
    "69|all": { all: { n: 50, p: 4100 } },
  },
};

const cities: Cities = {
  yearly: {
    "Lyon|all": { "2024": { n: 50, p: 4500, v: 250000, s: 60 }, "2025": { n: 55, p: 4400, v: 245000, s: 62 } },
    "Villeurbanne|all": { "2024": { n: 20, p: 3600, v: 200000, s: 63 }, "2025": { n: 22, p: 3700, v: 205000, s: 64 } },
    "Paris|all": { "2025": { n: 99, p: 9500, v: 400000, s: 40 } },
  },
  quarterly: {},
  income: { Lyon: 35000, Villeurbanne: 31000 },
};

const rhone = citiesFor(meta, { region: "84", dept: ALL });

describe("geography", () => {
  it("builds the overview zone from region and department", () => {
    expect(zoneOf({ region: ALL, dept: ALL })).toBe("all");
    expect(zoneOf({ region: "84", dept: ALL })).toBe("R84");
    expect(zoneOf({ region: "84", dept: "69" })).toBe("69");
  });

  it("lists the departments of the selected region and finds a department's region", () => {
    expect(departmentsFor(meta, "11").map((d) => d.code)).toEqual(["75", "92"]);
    expect(departmentsFor(meta, ALL)).toHaveLength(3);
    expect(regionOfDept(meta, "92")).toBe("11");
  });

  it("keeps the cities of the selected region or department", () => {
    expect(citiesFor(meta, { region: ALL, dept: ALL })).toHaveLength(3);
    expect(rhone.map((c) => c.name)).toEqual(["Lyon", "Villeurbanne"]);
    expect(citiesFor(meta, { region: "11", dept: "75" }).map((c) => c.name)).toEqual(["Paris"]);
  });
});

describe("change", () => {
  it("returns the relative change or null without reference", () => {
    expect(change(110, 100)).toBeCloseTo(0.1);
    expect(change(110, undefined)).toBeNull();
    expect(change(110, 0)).toBeNull();
  });
});

describe("kpis", () => {
  it("compares the last year with the previous one when no year is selected", () => {
    const k = kpis(overview, meta, all);
    expect(k.sales).toBe(220);
    expect(k.comparedYear).toBe(2025);
    expect(k.priceChange).toBeCloseTo(-0.01);
    expect(k.volumeChange).toBeCloseTo(0.2);
  });

  it("returns no change for the first year", () => {
    const k = kpis(overview, meta, { ...all, year: "2024" });
    expect(k.sales).toBe(100);
    expect(k.priceChange).toBeNull();
  });

  it("reads the department series when a department is selected", () => {
    expect(kpis(overview, meta, { ...all, region: "84", dept: "69" }).price).toBe(4100);
  });
});

describe("monthlySeries", () => {
  it("keeps only the selected year and zone", () => {
    expect(monthlySeries(overview, { ...all, year: "2025" })).toHaveLength(1);
    expect(monthlySeries(overview, all)).toHaveLength(2);
    expect(monthlySeries(overview, { ...all, region: "84" })[0].p).toBe(4000);
  });
});

describe("cities", () => {
  it("ranks cities from the most expensive", () => {
    const rows = cityRanking(cities, rhone, ALL, "2025");
    expect(rows.map((r) => [r.city, r.rank])).toEqual([
      ["Lyon", 1],
      ["Villeurbanne", 2],
    ]);
  });

  it("computes year-over-year changes, null for the first year", () => {
    const lyon = yoyMatrix(cities, rhone, meta.years, ALL)[0];
    expect(lyon.values[0]).toBeNull();
    expect(lyon.values[1]).toBeCloseTo(4400 / 4500 - 1);
  });

  it("simulates buyable surface and years of income", () => {
    const rows = simulate(cities, rhone, ALL, "2025", 220000);
    expect(rows[0].city).toBe("Villeurbanne");
    expect(rows[1].m2).toBeCloseTo(50);
    expect(rows[1].yearsOfIncome).toBeCloseTo(7);
  });

  it("has no income ratio without income data", () => {
    const paris = simulate(cities, citiesFor(meta, { region: "11", dept: ALL }), ALL, "2025", 250000)[0];
    expect(paris.yearsOfIncome).toBeNull();
  });
});

describe("mapPoints", () => {
  const points: Points = {
    list: [
      ["69381", "Lyon 1er", "69", 45.77, 4.83],
      ["31555", "Toulouse", "31", 43.6, 1.44],
    ],
    stats: { "all|all": [[0, 40, 5000], [1, 90, 3300]] },
  };
  it("joins stats to the point list and filters by department", () => {
    expect(mapPoints(points, all)).toHaveLength(2);
    expect(mapPoints(points, all, new Set(["69"]))).toEqual([
      { code: "69381", name: "Lyon 1er", dept: "69", lat: 45.77, lon: 4.83, n: 40, p: 5000 },
    ]);
  });
});

describe("quantile classes", () => {
  it("splits values into ordered classes", () => {
    const breaks = quantileBreaks([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5);
    expect(breaks).toEqual([3, 5, 7, 9]);
    expect(binIndex(1, breaks)).toBe(0);
    expect(binIndex(10, breaks)).toBe(4);
  });
});

describe("format", () => {
  const nbsp = (text: string) => text.replace(/\s/g, " ");

  it("formats in French", () => {
    const f = makeFormatters("fr");
    expect(f.pct(-0.111)).toBe("−11,1 %");
    expect(f.pct(null)).toBe("–");
    expect(nbsp(f.euroM2(4468.1))).toBe("4 468 €/m²");
    expect(nbsp(f.kEuro(250000))).toBe("250 k€");
    expect(f.month("2024-03")).toBe("mars 2024");
  });

  it("formats in English", () => {
    const f = makeFormatters("en");
    expect(f.pct(0.052)).toBe("+5.2%");
    expect(f.euroM2(4468.1)).toBe("€4,468/m²");
    expect(f.kEuro(250000)).toBe("€250k");
    expect(f.years(4.83)).toBe("4.8 yrs");
    expect(f.month("2024-03")).toBe("Mar 2024");
  });
});

describe("i18n", () => {
  it("has the same keys in both languages, none empty", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(fr).sort());
    expect(Object.values(en).every((text) => text.length > 0)).toBe(true);
  });

  it("translates and fills placeholders", () => {
    expect(makeI18n("fr").t("ov.versus", { a: 2025, b: 2024 })).toBe("2025 vs 2024");
    expect(makeI18n("en").t("map.salesCount", { n: "1,234" })).toBe("1,234 sales");
    expect(makeI18n("en").t("nav.map")).toBe("Price map");
  });
});
