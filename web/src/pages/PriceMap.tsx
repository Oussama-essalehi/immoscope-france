import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip as LeafletTooltip, useMap } from "react-leaflet";
import { ChartCard } from "../components/ChartCard";
import { FilterBar } from "../components/FilterBar";
import {
  ALL,
  binIndex,
  key,
  loadRegionCommunes,
  mapPoints,
  quantileBreaks,
  type CommuneRow,
  type Dataset,
  type Filters,
  type MapPoint,
  type Points,
} from "../data";
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
const FRANCE: [[number, number], [number, number]] = [[42.3, -4.8], [51.1, 8.3]];

/** Zoom the map onto the displayed points when the selection changes. */
function FitBounds({ points, selection }: { points: MapPoint[]; selection: string }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    const lats = points.map((p) => p.lat);
    const lons = points.map((p) => p.lon);
    map.fitBounds(
      [
        [Math.min(...lats), Math.min(...lons)],
        [Math.max(...lats), Math.max(...lons)],
      ],
      { padding: [24, 24] },
    );
    // re-fit only when the geographic selection changes, not on every filter
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, selection, points.length > 0]);
  return null;
}

function CommuneTable({ rows, caption }: { rows: CommuneRow[]; caption: string }) {
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
        {rows.map(([code, name, dept, n, p]) => (
          <tr key={code}>
            <td>{name}</td>
            <td>{dept}</td>
            <td className="num">{f.euroM2(p)}</td>
            <td className="num">{f.int(n)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PriceMap({ data, filters, onFilters, dark }: Props) {
  const palette = usePalette();
  const { t, f } = useI18n();
  const regional = filters.region !== ALL;
  const [communes, setCommunes] = useState<Points | null>(null);
  const [loading, setLoading] = useState(false);

  // Communes of the selected region are downloaded on demand (one file per region)
  useEffect(() => {
    if (!regional) return;
    let cancelled = false;
    setLoading(true);
    setCommunes(null);
    loadRegionCommunes(filters.region)
      .then((points) => !cancelled && setCommunes(points))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [regional, filters.region]);

  const points = useMemo(() => {
    if (!regional) {
      const depts = filters.dept === ALL ? undefined : new Set([filters.dept]);
      return mapPoints(data.departments, filters, depts);
    }
    if (!communes) return [];
    return mapPoints(communes, filters, filters.dept === ALL ? undefined : new Set([filters.dept]));
  }, [regional, communes, data.departments, filters]);

  const breaks = useMemo(() => quantileBreaks(points.map((p) => p.p), palette.sequential.length), [points, palette]);
  const maxSales = Math.max(1, ...points.map((p) => p.n));
  const radius = (n: number) => (regional ? 3 + 13 * Math.sqrt(n / maxSales) : 6 + 18 * Math.sqrt(n / maxSales));

  // Tables: the whole scope (pre-computed national top) or the communes of the region
  const tables = useMemo((): { top: CommuneRow[]; bottom: CommuneRow[] } => {
    if (!regional) return data.topCommunes[key(filters.type, filters.year)] ?? { top: [], bottom: [] };
    const sorted = [...points].sort((a, b) => b.p - a.p).map((p): CommuneRow => [p.code, p.name, p.dept, p.n, p.p]);
    return { top: sorted.slice(0, 10), bottom: sorted.slice(-10).reverse() };
  }, [regional, points, data.topCommunes, filters.type, filters.year]);

  // No points yet (region file still loading): no legend rather than empty classes
  const legend = breaks.length === 0 ? [] : palette.sequential.map((color, i) => {
    const low = i === 0 ? null : breaks[i - 1];
    const high = i < breaks.length ? breaks[i] : null;
    const text = low === null ? `< ${f.euro(high)}` : high === null ? `≥ ${f.euro(low)}` : `${f.euro(low)} – ${f.euro(high)}`;
    return { color, text };
  });

  const title = regional ? t("map.title") : t("map.titleDept");
  const subtitle = regional
    ? t("map.subtitle", { n: f.int(points.length), min: data.meta.minSalesCommune })
    : t("map.subtitleDept", { n: f.int(points.length) });

  return (
    <>
      <FilterBar meta={data.meta} filters={filters} onChange={onFilters} />
      <div className="map-layout">
        <ChartCard className="map-card" title={title} subtitle={loading ? t("map.loading") : subtitle}>
          <MapContainer bounds={FRANCE} scrollWheelZoom={false} zoomSnap={0.25} className="map" preferCanvas>
            <TileLayer url={TILES} attribution={ATTRIBUTION} className={dark ? "tiles-dark" : "tiles-light"} />
            <FitBounds points={points} selection={`${filters.region}|${filters.dept}`} />
            {points.map((p) => (
              <CircleMarker
                key={p.code}
                center={[p.lat, p.lon]}
                radius={radius(p.n)}
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
              <span className="legend-item" key={l.color}>
                <span className="swatch" style={{ background: l.color }} />
                {l.text}
              </span>
            ))}
          </div>
        </ChartCard>
        <div className="side-tables">
          <ChartCard title={t("map.top")} subtitle={t("map.top10", { min: data.meta.minSalesCommune })}>
            <CommuneTable rows={tables.top} caption={t("map.top")} />
          </ChartCard>
          <ChartCard title={t("map.bottom")} subtitle={t("map.top10", { min: data.meta.minSalesCommune })}>
            <CommuneTable rows={tables.bottom} caption={t("map.bottom")} />
          </ChartCard>
        </div>
      </div>
    </>
  );
}
