import "leaflet/dist/leaflet.css";
import { useMemo } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip as LeafletTooltip } from "react-leaflet";
import { ChartCard } from "../components/ChartCard";
import { FilterBar } from "../components/FilterBar";
import { binIndex, communePoints, quantileBreaks, type CommunePoint, type Dataset, type Filters } from "../data";
import { fmtEuroM2, fmtInt } from "../format";
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
  return (
    <table className="data-table compact">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          <th>Commune</th>
          <th>Dép.</th>
          <th className="num">Prix médian</th>
          <th className="num">Ventes</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.code}>
            <td>{r.name}</td>
            <td>{r.dept}</td>
            <td className="num">{fmtEuroM2(r.p)}</td>
            <td className="num">{fmtInt(r.n)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PriceMap({ data, filters, onFilters, dark }: Props) {
  const palette = usePalette();
  const points = useMemo(() => communePoints(data.communes, filters), [data.communes, filters]);
  const breaks = useMemo(() => quantileBreaks(points.map((p) => p.p), palette.sequential.length), [points, palette]);
  const maxSales = Math.max(1, ...points.map((p) => p.n));
  const sorted = [...points].sort((a, b) => b.p - a.p);
  const legend = palette.sequential.map((color, i) => {
    const low = i === 0 ? null : breaks[i - 1];
    const high = i < breaks.length ? breaks[i] : null;
    const text = low === null ? `< ${fmtInt(high)} €` : high === null ? `≥ ${fmtInt(low)} €` : `${fmtInt(low)} – ${fmtInt(high)} €`;
    return { color, text };
  });

  return (
    <>
      <FilterBar meta={data.meta} filters={filters} onChange={onFilters} />
      <div className="map-layout">
        <ChartCard
          className="map-card"
          title="Prix médian au m² par commune"
          subtitle={`${fmtInt(points.length)} communes avec au moins ${data.meta.minSalesCommune} ventes ; couleur = prix, taille = nombre de ventes`}
        >
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
                  {fmtEuroM2(p.p)} · {fmtInt(p.n)} ventes
                </LeafletTooltip>
              </CircleMarker>
            ))}
          </MapContainer>
          <div className="legend" aria-label="Légende des couleurs">
            <span className="legend-title">Prix médian au m²</span>
            {legend.map((l) => (
              <span className="legend-item" key={l.text}>
                <span className="swatch" style={{ background: l.color }} />
                {l.text}
              </span>
            ))}
          </div>
        </ChartCard>
        <div className="side-tables">
          <ChartCard title="Les plus chères" subtitle="Top 10 au m²">
            <CommuneTable rows={sorted.slice(0, 10)} caption="Communes les plus chères" />
          </ChartCard>
          <ChartCard title="Les moins chères" subtitle="Top 10 au m²">
            <CommuneTable rows={sorted.slice(-10).reverse()} caption="Communes les moins chères" />
          </ChartCard>
        </div>
      </div>
    </>
  );
}
