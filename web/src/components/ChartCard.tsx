import { useState, type ReactNode } from "react";
import { useI18n } from "../i18n";

export interface TableView {
  columns: string[];
  rows: (string | number)[][];
}

interface Props {
  title: string;
  subtitle?: string;
  /** Data behind the chart, shown on demand as an accessible table. */
  table?: TableView;
  className?: string;
  children: ReactNode;
}

/** Card with a title, an optional subtitle and a "chart / table" toggle. */
export function ChartCard({ title, subtitle, table, className, children }: Props) {
  const { t } = useI18n();
  const [showTable, setShowTable] = useState(false);
  return (
    <section className={`card ${className ?? ""}`}>
      <header className="card-header">
        <div>
          <h2>{title}</h2>
          {subtitle && <p className="card-subtitle">{subtitle}</p>}
        </div>
        {table && (
          <button
            type="button"
            className="ghost-button"
            onClick={() => setShowTable((v) => !v)}
            aria-pressed={showTable}
          >
            {showTable ? t("card.chart") : t("card.table")}
          </button>
        )}
      </header>
      {showTable && table ? (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                {table.columns.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td key={j}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card-body">{children}</div>
      )}
    </section>
  );
}
