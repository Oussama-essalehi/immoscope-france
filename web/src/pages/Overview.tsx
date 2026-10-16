import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import { ChartCard } from "../components/ChartCard";
import { TooltipBox } from "../components/ChartTooltip";
import { FilterBar } from "../components/FilterBar";
import { KpiTiles, trendOf } from "../components/KpiTiles";
import { ALL, kpis, monthlySeries, type Dataset, type Filters } from "../data";
import { useI18n } from "../i18n";
import { usePalette } from "../theme";

interface Props {
  data: Dataset;
  filters: Filters;
  onFilters: (f: Filters) => void;
}

export function Overview({ data, filters, onFilters }: Props) {
  const palette = usePalette();
  const { t, f } = useI18n();
  const k = kpis(data.overview, data.meta, filters);
  const series = monthlySeries(data.overview, filters);
  const period = filters.year === ALL ? `${data.meta.years[0]}-${data.meta.lastYear}` : filters.year;
  const versus = t("ov.versus", { a: k.comparedYear, b: k.comparedYear - 1 });

  const axisProps = {
    stroke: palette.axis,
    tick: { fill: palette.muted, fontSize: 12 },
    tickLine: false,
  };

  const monthTooltip = ({ active, payload, label }: TooltipContentProps<ValueType, NameType>) =>
    active && payload?.length ? (
      <TooltipBox
        title={f.month(String(label))}
        lines={[
          { label: t("tip.medianM2"), value: f.euroM2(payload[0].payload.p) },
          { label: t("tip.sales"), value: f.int(payload[0].payload.n) },
        ]}
      />
    ) : null;

  return (
    <>
      <FilterBar meta={data.meta} filters={filters} onChange={onFilters} />
      <KpiTiles
        items={[
          { label: t("ov.kpiSales"), value: f.int(k.sales), note: period },
          { label: t("ov.kpiPrice"), value: f.euroM2(k.price), note: period },
          { label: t("ov.kpiPriceChange"), value: f.pct(k.priceChange), note: versus, trend: trendOf(k.priceChange) },
          { label: t("ov.kpiVolumeChange"), value: f.pct(k.volumeChange), note: versus, trend: trendOf(k.volumeChange) },
        ]}
      />
      <ChartCard
        title={t("ov.priceTitle")}
        subtitle={t("ov.priceSubtitle")}
        table={{
          columns: [t("col.month"), t("col.medianM2"), t("col.sales")],
          rows: series.map((s) => [f.month(s.m), f.euroM2(s.p), f.int(s.n)]),
        }}
      >
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={series} syncId="month" margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            {/* band scale: each month is centred like the bars below, so both charts align */}
            <XAxis dataKey="m" scale="band" {...axisProps} interval="preserveStartEnd" minTickGap={28} tickFormatter={f.month} />
            <YAxis {...axisProps} axisLine={false} width={72} domain={["auto", "auto"]} tickFormatter={(v: number) => f.euro(v)} />
            <Tooltip content={monthTooltip} cursor={{ stroke: palette.axis }} />
            <Line type="monotone" dataKey="p" name={t("col.medianM2")} stroke={palette.series[0]} strokeWidth={2} dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: palette.surface }} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>
      <ChartCard title={t("ov.volumeTitle")} subtitle={t("ov.volumeSubtitle")}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={series} syncId="month" margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid vertical={false} stroke={palette.grid} />
            <XAxis dataKey="m" {...axisProps} interval="preserveStartEnd" minTickGap={28} tickFormatter={f.month} />
            <YAxis {...axisProps} axisLine={false} width={72} tickFormatter={(v: number) => f.int(v)} />
            <Tooltip content={monthTooltip} cursor={{ fill: palette.grid, opacity: 0.5 }} />
            <Bar dataKey="n" name={t("col.sales")} fill={palette.series[0]} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </>
  );
}
