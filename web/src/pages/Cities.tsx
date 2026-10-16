import { Bar, BarChart, CartesianGrid, LabelList, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "../components/ChartCard";
import { TooltipBox } from "../components/ChartTooltip";
import { FilterBar } from "../components/FilterBar";
import { ALL, citiesFor, cityRanking, key, yoyMatrix, type Dataset, type Filters } from "../data";
import { useI18n } from "../i18n";
import { divergingColor, usePalette } from "../theme";

interface Props {
  data: Dataset;
  filters: Filters;
  onFilters: (f: Filters) => void;
}

export function Cities({ data, filters, onFilters }: Props) {
  const palette = usePalette();
  const { t, f } = useI18n();
  const { meta, cities } = data;
  const list = citiesFor(meta, filters);
  const ranking = cityRanking(cities, list, filters.type, filters.year);
  const matrix = yoyMatrix(cities, list, meta.years, filters.type);
  const period = filters.year === ALL ? `${meta.years[0]}-${meta.lastYear}` : filters.year;

  // Small multiples are indexed (first quarter = 100): with prices from 1,000 to 10,000 €/m², a shared
  // euro scale would flatten every line; a shared index scale keeps the trends comparable
  const quarterly = list.map((c) => {
    const points = cities.quarterly[key(c.name, filters.type)] ?? [];
    const base = points[0]?.p;
    return { city: c.name, points: points.map((p) => ({ ...p, i: base ? (100 * p.p) / base : null })) };
  });
  const allIndices = quarterly.flatMap((q) => q.points.flatMap((p) => (p.i === null ? [] : [p.i])));
  const yDomain: [number, number] = [Math.floor(Math.min(...allIndices) / 5) * 5, Math.ceil(Math.max(...allIndices) / 5) * 5];
  const firstQuarter = quarterly.find((q) => q.points.length > 0)?.points[0]?.q ?? "";

  return (
    <>
      <FilterBar meta={meta} filters={filters} onChange={onFilters} show={{ region: true, dept: true, type: true, year: true }} yearLabel={t("filters.yearRanking")} />
      <div className="grid-2">
        <ChartCard
          title={t("ct.rankTitle")}
          subtitle={t("ct.rankSubtitle", { count: ranking.length, period })}
          table={{
            columns: [t("col.rank"), t("col.city"), t("col.medianM2"), t("col.sales")],
            rows: ranking.map((r) => [r.rank, r.city, f.euroM2(r.p), f.int(r.n)]),
          }}
        >
          <ResponsiveContainer width="100%" height={Math.max(200, 26 * ranking.length + 40)}>
            <BarChart data={ranking} layout="vertical" margin={{ top: 0, right: 72, bottom: 0, left: 8 }}>
              <CartesianGrid horizontal={false} stroke={palette.grid} />
              <XAxis type="number" stroke={palette.axis} tick={{ fill: palette.muted, fontSize: 12 }} tickFormatter={(v: number) => f.int(v)} />
              <YAxis type="category" dataKey="city" width={140} interval={0} stroke={palette.axis} tick={{ fill: palette.ink2, fontSize: 13 }} tickLine={false} />
              <Tooltip
                cursor={{ fill: palette.grid, opacity: 0.5 }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <TooltipBox
                      title={`${payload[0].payload.rank}. ${payload[0].payload.city}`}
                      lines={[
                        { label: t("tip.medianM2"), value: f.euroM2(payload[0].payload.p) },
                        { label: t("tip.sales"), value: f.int(payload[0].payload.n) },
                      ]}
                    />
                  ) : null
                }
              />
              <Bar dataKey="p" fill={palette.series[0]} radius={[0, 4, 4, 0]} barSize={16}>
                <LabelList dataKey="p" position="right" formatter={(v: unknown) => f.int(Number(v))} fill={palette.ink2} fontSize={12} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title={t("ct.yoyTitle")} subtitle={t("ct.yoySubtitle")}>
          <div className="table-scroll">
            <table className="data-table heatmap">
              <thead>
                <tr>
                  <th>{t("col.city")}</th>
                  {meta.years.map((y) => (
                    <th key={y} className="num">
                      {y}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrix.map((row) => (
                  <tr key={row.city}>
                    <td>{row.city}</td>
                    {row.values.map((v, i) => (
                      <td
                        key={meta.years[i]}
                        className="num"
                        style={v === null ? undefined : { background: divergingColor(palette, v), color: Math.abs(v) > 0.06 ? "#ffffff" : palette.ink }}
                      >
                        {f.pct(v)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      </div>

      <ChartCard title={t("ct.multiTitle")} subtitle={t("ct.multiSubtitle", { q: String(firstQuarter).slice(0, 4) })}>
        <div className="multiples">
          {quarterly.map(({ city, points }) => {
            const first = points[0]?.p;
            const last = points[points.length - 1]?.p;
            return (
              <div className="multiple" key={city}>
                <div className="multiple-title">
                  <span>{city}</span>
                  <span className="multiple-change">{f.pct(first && last ? last / first - 1 : null)}</span>
                </div>
                <ResponsiveContainer width="100%" height={110}>
                  <LineChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
                    <YAxis hide domain={yDomain} />
                    <XAxis dataKey="q" hide />
                    <Tooltip
                      content={({ active, payload, label }) =>
                        active && payload?.length ? (
                          <TooltipBox
                            title={`${city}, ${String(label).replace("-", " ")}`}
                            lines={[
                              { label: t("tip.medianM2"), value: f.euroM2(payload[0].payload.p) },
                              { label: t("tip.index"), value: f.int(payload[0].payload.i) },
                            ]}
                          />
                        ) : null
                      }
                    />
                    <Line type="monotone" dataKey="i" stroke={palette.series[0]} strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            );
          })}
        </div>
      </ChartCard>
    </>
  );
}
