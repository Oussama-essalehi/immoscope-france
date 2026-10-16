import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "../components/ChartCard";
import { TooltipBox } from "../components/ChartTooltip";
import { FilterBar } from "../components/FilterBar";
import { KpiTiles } from "../components/KpiTiles";
import { ALL, citiesFor, simulate, type Dataset, type Filters } from "../data";
import { useI18n } from "../i18n";
import { usePalette } from "../theme";

interface Props {
  data: Dataset;
  filters: Filters;
  onFilters: (f: Filters) => void;
  budget: number;
  onBudget: (b: number) => void;
}

export function Simulator({ data, filters, onFilters, budget, onBudget }: Props) {
  const palette = usePalette();
  const { t, f } = useI18n();
  const { meta, cities } = data;
  // The simulator needs one year of prices: the latest one unless another is selected
  const year = filters.year === ALL ? String(meta.lastYear) : filters.year;
  const rows = simulate(cities, citiesFor(meta, filters), filters.type, year, budget);
  const bySurface = [...rows].sort((a, b) => b.s - a.s);
  const best = rows[0];
  const worst = rows[rows.length - 1];
  const { min, max, step } = meta.budgets;

  return (
    <>
      <FilterBar meta={meta} filters={{ ...filters, year }} onChange={onFilters} show={{ region: true, dept: true, type: true, year: true }} yearLabel={t("filters.yearPrices")} requireYear />
      <div className="budget-panel card">
        <label className="budget-field">
          <span>{t("sim.budget")}</span>
          <strong className="budget-value">{f.euro(budget)}</strong>
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={budget}
            onChange={(e) => onBudget(Number(e.target.value))}
            aria-valuetext={f.euro(budget)}
          />
          <span className="budget-scale">
            <span>{f.kEuro(min)}</span>
            <span>{f.kEuro(max)}</span>
          </span>
        </label>
        {best && worst && (
          <KpiTiles
            items={[
              { label: t("sim.most"), value: f.m2(best.m2), note: best.city },
              { label: t("sim.least"), value: f.m2(worst.m2), note: worst.city },
              { label: t("sim.gap"), value: f.times(best.m2 / worst.m2), note: `${best.city} / ${worst.city}` },
            ]}
          />
        )}
      </div>
      <div className="grid-2">
        <ChartCard
          title={t("sim.buyTitle")}
          subtitle={t("sim.buySubtitle", { year })}
          table={{
            columns: [t("col.city"), t("col.medianM2"), t("col.m2Buyable")],
            rows: rows.map((r) => [r.city, f.euroM2(r.p), f.m2(r.m2)]),
          }}
        >
          <ResponsiveContainer width="100%" height={Math.max(200, 26 * rows.length + 40)}>
            <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 64, bottom: 0, left: 8 }}>
              <CartesianGrid horizontal={false} stroke={palette.grid} />
              <XAxis type="number" stroke={palette.axis} tick={{ fill: palette.muted, fontSize: 12 }} />
              <YAxis type="category" dataKey="city" width={140} interval={0} stroke={palette.axis} tick={{ fill: palette.ink2, fontSize: 13 }} tickLine={false} />
              <Tooltip
                cursor={{ fill: palette.grid, opacity: 0.5 }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <TooltipBox
                      title={payload[0].payload.city}
                      lines={[
                        { label: t("sim.buyTip"), value: f.m2(payload[0].payload.m2) },
                        { label: t("tip.medianM2"), value: f.euroM2(payload[0].payload.p) },
                      ]}
                    />
                  ) : null
                }
              />
              <Bar dataKey="m2" fill={palette.series[0]} radius={[0, 4, 4, 0]} barSize={16}>
                <LabelList dataKey="m2" position="right" formatter={(v: unknown) => f.m2(Number(v))} fill={palette.ink2} fontSize={12} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <div className="stack">
          <ChartCard
            title={t("sim.surfaceTitle")}
            subtitle={t("sim.surfaceSubtitle", { year })}
            table={{ columns: [t("col.city"), t("col.medianSurface")], rows: bySurface.map((r) => [r.city, f.m2(r.s)]) }}
          >
            <ResponsiveContainer width="100%" height={Math.max(200, 22 * rows.length + 40)}>
              <BarChart data={bySurface} layout="vertical" margin={{ top: 0, right: 56, bottom: 0, left: 8 }}>
                <CartesianGrid horizontal={false} stroke={palette.grid} />
                <XAxis type="number" stroke={palette.axis} tick={{ fill: palette.muted, fontSize: 12 }} />
                <YAxis type="category" dataKey="city" width={140} interval={0} stroke={palette.axis} tick={{ fill: palette.ink2, fontSize: 13 }} tickLine={false} />
                <Tooltip
                  cursor={{ fill: palette.grid, opacity: 0.5 }}
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <TooltipBox title={payload[0].payload.city} lines={[{ label: t("col.medianSurface"), value: f.m2(payload[0].payload.s) }]} />
                    ) : null
                  }
                />
                <Bar dataKey="s" fill={palette.series[2]} radius={[0, 4, 4, 0]} barSize={13}>
                  <LabelList dataKey="s" position="right" formatter={(v: unknown) => f.m2(Number(v))} fill={palette.ink2} fontSize={12} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
          <ChartCard title={t("sim.detailTitle")} subtitle={t("sim.detailSubtitle")}>
            <div className="table-scroll short">
              <table className="data-table compact">
                <thead>
                  <tr>
                    <th>{t("col.city")}</th>
                    <th className="num">{t("col.medianPrice")}</th>
                    <th className="num">m²</th>
                    <th className="num">{t("col.yearsIncome")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.city}>
                      <td>{r.city}</td>
                      <td className="num">{f.euro(r.v)}</td>
                      <td className="num">{f.int(r.m2)}</td>
                      <td className="num">{f.years(r.yearsOfIncome)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ChartCard>
        </div>
      </div>
    </>
  );
}
