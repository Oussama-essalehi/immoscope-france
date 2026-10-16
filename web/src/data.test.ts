import { describe, expect, it } from "vitest";
import {
  ALL,
  binIndex,
  change,
  cityRanking,
  communePoints,
  kpis,
  monthlySeries,
  quantileBreaks,
  simulate,
  yoyMatrix,
  type Cities,
  type Communes,
  type Meta,
  type Overview,
} from "./data";
import { fmtEuroM2, fmtPct } from "./format";

const meta: Meta = {
  source: "test",
  years: [2024, 2025],
  lastYear: 2025,
  totalSales: 30,
  communes: 2,
  departments: [{ code: "69", label: "Rhône" }],
  types: ["Appartement", "Maison"],
  cities: [
    { name: "Lyon", dept: "69", metropole: true },
    { name: "Villeurbanne", dept: "69", metropole: false },
  ],
  metropoles: ["Lyon"],
  minSalesCommune: 30,
  budgets: { min: 100000, max: 500000, step: 10000, default: 250000 },
};

const overview: Overview = {
  monthly: {
    "all|all": [
      { m: "2024-12", n: 10, p: 3000 },
      { m: "2025-01", n: 12, p: 3100 },
    ],
  },
  yearly: {
    "all|all": {
      "2024": { n: 100, p: 3000 },
      "2025": { n: 120, p: 2970 },
      all: { n: 220, p: 2985 },
    },
  },
};

const cities: Cities = {
  yearly: {
    "Lyon|all": { "2024": { n: 50, p: 4500, v: 250000, s: 60 }, "2025": { n: 55, p: 4400, v: 245000, s: 62 } },
    "Villeurbanne|all": { "2024": { n: 20, p: 3600, v: 200000, s: 63 }, "2025": { n: 22, p: 3700, v: 205000, s: 64 } },
  },
  quarterly: {},
  income: { Lyon: 35000, Villeurbanne: 31000 },
};

describe("change", () => {
  it("returns the relative change or null without reference", () => {
    expect(change(110, 100)).toBeCloseTo(0.1);
    expect(change(110, undefined)).toBeNull();
    expect(change(110, 0)).toBeNull();
  });
});

describe("kpis", () => {
  it("compares the last year with the previous one when no year is selected", () => {
    const k = kpis(overview, meta, { dept: ALL, type: ALL, year: ALL });
    expect(k.sales).toBe(220);
    expect(k.comparedYear).toBe(2025);
    expect(k.priceChange).toBeCloseTo(-0.01);
    expect(k.volumeChange).toBeCloseTo(0.2);
  });

  it("returns no change for the first year", () => {
    const k = kpis(overview, meta, { dept: ALL, type: ALL, year: "2024" });
    expect(k.sales).toBe(100);
    expect(k.priceChange).toBeNull();
  });
});

describe("monthlySeries", () => {
  it("keeps only the selected year", () => {
    expect(monthlySeries(overview, { dept: ALL, type: ALL, year: "2025" })).toHaveLength(1);
    expect(monthlySeries(overview, { dept: ALL, type: ALL, year: ALL })).toHaveLength(2);
  });
});

describe("cities", () => {
  it("ranks cities from the most expensive", () => {
    const rows = cityRanking(cities, meta, ALL, "2025");
    expect(rows.map((r) => [r.city, r.rank])).toEqual([
      ["Lyon", 1],
      ["Villeurbanne", 2],
    ]);
  });

  it("computes year-over-year changes, null for the first year", () => {
    const lyon = yoyMatrix(cities, meta, ALL)[0];
    expect(lyon.values[0]).toBeNull();
    expect(lyon.values[1]).toBeCloseTo(4400 / 4500 - 1);
  });

  it("simulates buyable surface and years of income", () => {
    const rows = simulate(cities, meta, ALL, "2025", 220000);
    expect(rows[0].city).toBe("Villeurbanne");
    expect(rows[1].m2).toBeCloseTo(50);
    expect(rows[1].yearsOfIncome).toBeCloseTo(7);
  });
});

describe("communePoints", () => {
  const communes: Communes = {
    list: [
      ["69381", "Lyon 1er", "69", 45.77, 4.83],
      ["31555", "Toulouse", "31", 43.6, 1.44],
    ],
    stats: { "all|all": [[0, 40, 5000], [1, 90, 3300]] },
  };
  it("joins stats to the commune list and filters by department", () => {
    expect(communePoints(communes, { dept: ALL, type: ALL, year: ALL })).toHaveLength(2);
    const rhone = communePoints(communes, { dept: "69", type: ALL, year: ALL });
    expect(rhone).toEqual([{ code: "69381", name: "Lyon 1er", dept: "69", lat: 45.77, lon: 4.83, n: 40, p: 5000 }]);
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
  it("formats in French", () => {
    expect(fmtPct(-0.111)).toBe("−11,1 %");
    expect(fmtPct(null)).toBe("–");
    expect(fmtEuroM2(4468.1).replace(/\s/g, " ")).toBe("4 468 €/m²");
  });
});
