import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { ChartCard } from "../components/ChartCard";
import { TooltipBox } from "../components/ChartTooltip";
import { FilterBar } from "../components/FilterBar";
import { KpiTiles, trendOf } from "../components/KpiTiles";
import { ALL, kpis, monthlySeries, type Dataset, type Filters } from "../data";
import { fmtEuroM2, fmtInt, fmtMonth, fmtPct } from "../format";
import { usePalette } from "../theme";

interface Props {
  data: Dataset;
  filters: Filters;
  onFilters: (f: Filters) => void;
}

export function Overview({ data, filters, onFilters }: Props) {
  const palette = usePalette();
  const k = kpis(data.overview, data.meta, filters);
  const series = monthlySeries(data.overview, filters);
  const period = filters.year === ALL ? `${data.meta.years[0]}-${data.meta.lastYear}` : filters.year;
  const versus = `${k.comparedYear} vs ${k.comparedYear - 1}`;

  const axisProps = {
    stroke: palette.axis,
    tick: { fill: palette.muted, fontSize: 12 },
    tickLine: false,
  };

  const monthTooltip = ({ active, payload, label }: TooltipContentProps<ValueType, NameType>) =>
    active && payload?.length ? (
      <TooltipBox
        title={fmtMonth(String(label))}
        lines={[
          { label: "Prix médian", value: fmtEuroM2(payload[0].payload.p) },
          { label: "Ventes", value: fmtInt(payload[0].payload.n) },
        ]}
      />
    ) : null;

  return (
    <>
      <FilterBar meta={data.meta} filters={filters} onChange={onFilters} />
      <KpiTiles
        items={[
          { label: "Nombre de ventes", value: fmtInt(k.sales), note: period },
          { label: "Prix médian au m²", value: fmtEuroM2(k.price), note: period },
          { label: "Évolution du prix au m²", value: fmtPct(k.priceChange), note: versus, trend: trendOf(k.priceChange) },
          { label: "Évolution du volume", value: fmtPct(k.volumeChange), note: versus, trend: trendOf(k.volumeChange) },
        ]}
      />
      <ChartCard
        title="Prix médian au m² par mois"
        subtitle="Survolez un mois : le graphique du volume affiche le même mois"
        table={{
          columns: ["Mois", "Prix médian au m²", "Ventes"],
          rows: series.map((s) => [fmtMonth(s.m), fmtEuroM2(s.p), fmtInt(s.n)]),
        }}
      >
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={series} syncId="month" margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            {/* band scale: each month is centred like the bars below, so both charts align */}
            <XAxis dataKey="m" scale="band" {...axisProps} interval="preserveStartEnd" minTickGap={28} tickFormatter={fmtMonth} />
            <YAxis {...axisProps} axisLine={false} width={72} domain={["auto", "auto"]} tickFormatter={(v: number) => `${fmtInt(v)} €`} />
            <Tooltip content={monthTooltip} cursor={{ stroke: palette.axis }} />
            <Line type="monotone" dataKey="p" name="Prix médian au m²" stroke={palette.series[0]} strokeWidth={2} dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: palette.surface }} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>
      <ChartCard title="Nombre de ventes par mois" subtitle="Même axe temporel que le prix : deux échelles, deux graphiques">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={series} syncId="month" margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="m" {...axisProps} interval="preserveStartEnd" minTickGap={28} tickFormatter={fmtMonth} />
            <YAxis {...axisProps} axisLine={false} width={72} tickFormatter={(v: number) => fmtInt(v)} />
            <Tooltip content={monthTooltip} cursor={{ fill: palette.grid, opacity: 0.5 }} />
            <Bar dataKey="n" name="Ventes" fill={palette.series[0]} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </>
  );
}
