import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "../components/ChartCard";
import { TooltipBox } from "../components/ChartTooltip";
import { FilterBar } from "../components/FilterBar";
import { KpiTiles } from "../components/KpiTiles";
import { simulate, type Dataset, type Filters } from "../data";
import { fmtEuro, fmtEuroM2, fmtInt, fmtKEuro, fmtM2, fmtYears } from "../format";
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
  const { meta, cities } = data;
  // The simulator needs one year of prices: the latest one unless another is selected
  const year = filters.year === "all" ? String(meta.lastYear) : filters.year;
  const rows = simulate(cities, meta, filters.type, year, budget);
  const bySurface = [...rows].sort((a, b) => b.s - a.s);
  const best = rows[0];
  const worst = rows[rows.length - 1];
  const { min, max, step } = meta.budgets;

  return (
    <>
      <FilterBar meta={meta} filters={{ ...filters, year }} onChange={onFilters} show={{ type: true, year: true }} yearLabel="Prix de l'année" requireYear />
      <div className="budget-panel card">
        <label className="budget-field">
          <span>Budget d'achat (hors frais de notaire)</span>
          <strong className="budget-value">{fmtEuro(budget)}</strong>
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={budget}
            onChange={(e) => onBudget(Number(e.target.value))}
            aria-valuetext={fmtEuro(budget)}
          />
          <span className="budget-scale">
            <span>{fmtKEuro(min)}</span>
            <span>{fmtKEuro(max)}</span>
          </span>
        </label>
        {best && worst && (
          <KpiTiles
            items={[
              { label: "Le plus de surface", value: fmtM2(best.m2), note: best.city },
              { label: "Le moins de surface", value: fmtM2(worst.m2), note: worst.city },
              { label: "Écart", value: `x ${(best.m2 / worst.m2).toFixed(1).replace(".", ",")}`, note: `${best.city} / ${worst.city}` },
            ]}
          />
        )}
      </div>
      <div className="grid-2">
        <ChartCard
          title="Surface achetable avec ce budget"
          subtitle={`Budget / prix médian au m² ${year}`}
          table={{
            columns: ["Ville", "Prix médian au m²", "m² achetables"],
            rows: rows.map((r) => [r.city, fmtEuroM2(r.p), fmtM2(r.m2)]),
          }}
        >
          <ResponsiveContainer width="100%" height={520}>
            <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 64, bottom: 0, left: 8 }}>
              <CartesianGrid horizontal={false} stroke={palette.grid} />
              <XAxis type="number" stroke={palette.axis} tick={{ fill: palette.muted, fontSize: 12 }} />
              <YAxis type="category" dataKey="city" width={110} stroke={palette.axis} tick={{ fill: palette.ink2, fontSize: 13 }} tickLine={false} />
              <Tooltip
                cursor={{ fill: palette.grid, opacity: 0.5 }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <TooltipBox
                      title={payload[0].payload.city}
                      lines={[
                        { label: "Surface achetable", value: fmtM2(payload[0].payload.m2) },
                        { label: "Prix médian", value: fmtEuroM2(payload[0].payload.p) },
                      ]}
                    />
                  ) : null
                }
              />
              <Bar dataKey="m2" fill={palette.series[0]} radius={[0, 4, 4, 0]} barSize={20}>
                <LabelList dataKey="m2" position="right" formatter={(v: unknown) => fmtM2(Number(v))} fill={palette.ink2} fontSize={12} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <div className="stack">
          <ChartCard
            title="Surface médiane des logements vendus"
            subtitle={`Ce qui se vend réellement, ${year}`}
            table={{ columns: ["Ville", "Surface médiane"], rows: bySurface.map((r) => [r.city, fmtM2(r.s)]) }}
          >
            <ResponsiveContainer width="100%" height={420}>
              <BarChart data={bySurface} layout="vertical" margin={{ top: 0, right: 56, bottom: 0, left: 8 }}>
                <CartesianGrid horizontal={false} stroke={palette.grid} />
                <XAxis type="number" stroke={palette.axis} tick={{ fill: palette.muted, fontSize: 12 }} />
                <YAxis type="category" dataKey="city" width={110} stroke={palette.axis} tick={{ fill: palette.ink2, fontSize: 13 }} tickLine={false} />
                <Tooltip
                  cursor={{ fill: palette.grid, opacity: 0.5 }}
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <TooltipBox title={payload[0].payload.city} lines={[{ label: "Surface médiane", value: fmtM2(payload[0].payload.s) }]} />
                    ) : null
                  }
                />
                <Bar dataKey="s" fill={palette.series[2]} radius={[0, 4, 4, 0]} barSize={16}>
                  <LabelList dataKey="s" position="right" formatter={(v: unknown) => fmtM2(Number(v))} fill={palette.ink2} fontSize={12} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
          <ChartCard title="Détail par ville" subtitle="Années de revenu : prix médian / revenu médian d'un ménage (INSEE Filosofi 2021)">
            <div className="table-scroll short">
              <table className="data-table compact">
                <thead>
                  <tr>
                    <th>Ville</th>
                    <th className="num">Prix médian</th>
                    <th className="num">m²</th>
                    <th className="num">Années de revenu</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.city}>
                      <td>{r.city}</td>
                      <td className="num">{fmtEuro(r.v)}</td>
                      <td className="num">{fmtInt(r.m2)}</td>
                      <td className="num">{fmtYears(r.yearsOfIncome)}</td>
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
