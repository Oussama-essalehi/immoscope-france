import "leaflet/dist/leaflet.css";
import { useMemo } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip as LeafletTooltip } from "react-leaflet";
import { ChartCard } from "../components/ChartCard";
import { FilterBar } from "../components/FilterBar";
import { binIndex, communePoints, quantileBreaks, type CommunePoint, type Dataset, type Filters } from "../data";
import { useI18n } from "../i18n";
import { usePalette } from "../theme";

interface Props {
  data: Dataset;
  filters: Filters;
  onFilters: (f: Filters) => void;
  dark: boolean;
}

// OpenStreetMap standard tiles (no API key); toned down / inverted in CSS so the data stays prominent
const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function CommuneTable({ rows, caption }: { rows: CommunePoint[]; caption: string }) {
  const { t, f } = useI18n();
  return (
    <table className="data-table compact">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          <th>{t("col.commune")}</th>
          <th>{t("col.dept")}</th>
          <th className="num">{t("col.medianPrice")}</th>
          <th className="num">{t("col.sales")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.code}>
            <td>{r.name}</td>
            <td>{r.dept}</td>
            <td className="num">{f.euroM2(r.p)}</td>
            <td className="num">{f.int(r.n)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PriceMap({ data, filters, onFilters, dark }: Props) {
  const palette = usePalette();
  const { t, f } = useI18n();
  const points = useMemo(() => communePoints(data.communes, filters), [data.communes, filters]);
  const breaks = useMemo(() => quantileBreaks(points.map((p) => p.p), palette.sequential.length), [points, palette]);
  const maxSales = Math.max(1, ...points.map((p) => p.n));
  const sorted = [...points].sort((a, b) => b.p - a.p);
  const legend = palette.sequential.map((color, i) => {
    const low = i === 0 ? null : breaks[i - 1];
    const high = i < breaks.length ? breaks[i] : null;
    const text = low === null ? `< ${f.euro(high)}` : high === null ? `≥ ${f.euro(low)}` : `${f.euro(low)} – ${f.euro(high)}`;
    return { color, text };
  });

  return (
    <>
      <FilterBar meta={data.meta} filters={filters} onChange={onFilters} />
      <div className="map-layout">
        <ChartCard className="map-card" title={t("map.title")} subtitle={t("map.subtitle", { n: f.int(points.length), min: data.meta.minSalesCommune })}>
          <MapContainer center={[45.2, 1.9]} zoom={6} scrollWheelZoom={false} className="map">
            <TileLayer url={TILES} attribution={ATTRIBUTION} className={dark ? "tiles-dark" : "tiles-light"} />
            {points.map((p) => (
              <CircleMarker
                key={p.code}
                center={[p.lat, p.lon]}
                radius={3 + 13 * Math.sqrt(p.n / maxSales)}
                pathOptions={{
                  color: palette.surface,
                  weight: 1,
                  fillColor: palette.sequential[binIndex(p.p, breaks)],
                  fillOpacity: 0.85,
                }}
              >
                <LeafletTooltip>
                  <strong>{p.name}</strong> ({p.dept})
                  <br />
                  {f.euroM2(p.p)} · {t("map.salesCount", { n: f.int(p.n) })}
                </LeafletTooltip>
              </CircleMarker>
            ))}
          </MapContainer>
          <div className="legend" aria-label={t("map.legendLabel")}>
            <span className="legend-title">{t("map.legend")}</span>
            {legend.map((l) => (
              <span className="legend-item" key={l.text}>
                <span className="swatch" style={{ background: l.color }} />
                {l.text}
              </span>
            ))}
          </div>
        </ChartCard>
        <div className="side-tables">
          <ChartCard title={t("map.top")} subtitle={t("map.top10")}>
            <CommuneTable rows={sorted.slice(0, 10)} caption={t("map.top")} />
          </ChartCard>
          <ChartCard title={t("map.bottom")} subtitle={t("map.top10")}>
            <CommuneTable rows={sorted.slice(-10).reverse()} caption={t("map.bottom")} />
          </ChartCard>
        </div>
      </div>
    </>
  );
}
