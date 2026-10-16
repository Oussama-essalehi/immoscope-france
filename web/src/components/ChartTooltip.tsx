import type { ReactNode } from "react";

export interface TooltipLine {
  label: string;
  value: string;
  color?: string;
}

/** Tooltip box used by every chart: a heading and label / value lines. */
export function TooltipBox({ title, lines }: { title: ReactNode; lines: TooltipLine[] }) {
  return (
    <div className="tooltip">
      <div className="tooltip-title">{title}</div>
      {lines.map((l) => (
        <div className="tooltip-line" key={l.label}>
          {l.color && <span className="swatch" style={{ background: l.color }} />}
          <span className="tooltip-label">{l.label}</span>
          <span className="tooltip-value">{l.value}</span>
        </div>
      ))}
    </div>
  );
}
