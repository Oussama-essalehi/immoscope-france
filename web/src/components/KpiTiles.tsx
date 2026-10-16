export interface Kpi {
  label: string;
  value: string;
  /** small context line under the value */
  note?: string;
  /** direction of a change, shown with an arrow and a word (never colour alone) */
  trend?: "up" | "down" | "flat";
}

const ARROWS = { up: "▲", down: "▼", flat: "■" } as const;
const WORDS = { up: "hausse", down: "baisse", flat: "stable" } as const;

/** Row of headline figures. */
export function KpiTiles({ items }: { items: Kpi[] }) {
  return (
    <div className="kpi-row">
      {items.map((k) => (
        <div className="kpi" key={k.label}>
          <span className="kpi-label">{k.label}</span>
          <span className="kpi-value">
            {k.trend && (
              <span className={`trend trend-${k.trend}`} aria-label={WORDS[k.trend]}>
                {ARROWS[k.trend]}
              </span>
            )}
            {k.value}
          </span>
          {k.note && <span className="kpi-note">{k.note}</span>}
        </div>
      ))}
    </div>
  );
}

export const trendOf = (ratio: number | null): Kpi["trend"] =>
  ratio === null ? undefined : ratio > 0.005 ? "up" : ratio < -0.005 ? "down" : "flat";
