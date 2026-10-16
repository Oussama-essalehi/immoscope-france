import { Bar, BarChart, CartesianGrid, LabelList, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "../components/ChartCard";
import { TooltipBox } from "../components/ChartTooltip";
import { FilterBar } from "../components/FilterBar";
import { ALL, cityRanking, key, yoyMatrix, type Dataset, type Filters } from "../data";
import { fmtEuroM2, fmtInt, fmtPct } from "../format";
import { divergingColor, usePalette } from "../theme";

interface Props {
  data: Dataset;
  filters: Filters;
  onFilters: (f: Filters) => void;
}

export function Cities({ data, filters, onFilters }: Props) {
  const palette = usePalette();
  const { meta, cities } = data;
  const ranking = cityRanking(cities, meta, filters.type, filters.year);
  const matrix = yoyMatrix(cities, meta, filters.type);
  const period = filters.year === ALL ? `${meta.years[0]}-${meta.lastYear}` : filters.year;

  // Shared y range for the small multiples, so that panels are comparable
  const quarterly = meta.cities.map((c) => ({ city: c.name, points: cities.quarterly[key(c.name, filters.type)] ?? [] }));
  const allPrices = quarterly.flatMap((q) => q.points.map((p) => p.p));
  const yDomain: [number, number] = [Math.floor(Math.min(...allPrices) / 500) * 500, Math.ceil(Math.max(...allPrices) / 500) * 500];

  return (
    <>
      <FilterBar meta={meta} filters={filters} onChange={onFilters} show={{ type: true, year: true }} yearLabel="Année du classement" />
      <div className="grid-2">
        <ChartCard
          title="Classement par prix médian au m²"
          subtitle={`15 villes suivies, ${period}`}
          table={{
            columns: ["Rang", "Ville", "Prix médian au m²", "Ventes"],
            rows: ranking.map((r) => [r.rank, r.city, fmtEuroM2(r.p), fmtInt(r.n)]),
          }}
        >
          <ResponsiveContainer width="100%" height={520}>
            <BarChart data={ranking} layout="vertical" margin={{ top: 0, right: 72, bottom: 0, left: 8 }}>
              <CartesianGrid horizontal={false} stroke={palette.grid} />
              <XAxis type="number" stroke={palette.axis} tick={{ fill: palette.muted, fontSize: 12 }} tickFormatter={(v: number) => fmtInt(v)} />
              <YAxis type="category" dataKey="city" width={110} stroke={palette.axis} tick={{ fill: palette.ink2, fontSize: 13 }} tickLine={false} />
              <Tooltip
                cursor={{ fill: palette.grid, opacity: 0.5 }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <TooltipBox
                      title={`${payload[0].payload.rank}. ${payload[0].payload.city}`}
                      lines={[
                        { label: "Prix médian", value: fmtEuroM2(payload[0].payload.p) },
                        { label: "Ventes", value: fmtInt(payload[0].payload.n) },
                      ]}
                    />
                  ) : null
                }
              />
              <Bar dataKey="p" fill={palette.series[0]} radius={[0, 4, 4, 0]} barSize={20}>
                <LabelList dataKey="p" position="right" formatter={(v: unknown) => fmtInt(Number(v))} fill={palette.ink2} fontSize={12} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Évolution annuelle du prix médian au m²" subtitle="Variation par rapport à l'année précédente ; bleu = baisse, rouge = hausse">
          <div className="table-scroll">
            <table className="data-table heatmap">
              <thead>
                <tr>
                  <th>Ville</th>
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
                        {fmtPct(v)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      </div>

      <ChartCard title="Tendance trimestrielle du prix médian au m², ville par ville" subtitle="Même échelle pour toutes les villes">
        <div className="multiples">
          {quarterly.map(({ city, points }) => {
            const first = points[0]?.p;
            const last = points[points.length - 1]?.p;
            return (
              <div className="multiple" key={city}>
                <div className="multiple-title">
                  <span>{city}</span>
                  <span className="multiple-change">{fmtPct(first && last ? last / first - 1 : null)}</span>
                </div>
                <ResponsiveContainer width="100%" height={110}>
                  <LineChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
                    <YAxis hide domain={yDomain} />
                    <XAxis dataKey="q" hide />
                    <Tooltip
                      content={({ active, payload, label }) =>
                        active && payload?.length ? (
                          <TooltipBox title={`${city}, ${String(label).replace("-", " ")}`} lines={[{ label: "Prix médian", value: fmtEuroM2(payload[0].payload.p) }]} />
                        ) : null
                      }
                    />
                    <Line type="monotone" dataKey="p" stroke={palette.series[0]} strokeWidth={2} dot={false} />
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
