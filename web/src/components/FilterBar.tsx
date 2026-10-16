import { ALL, type Filters, type Meta } from "../data";

interface Props {
  meta: Meta;
  filters: Filters;
  onChange: (next: Filters) => void;
  /** Which filters this page exposes. */
  show?: { dept?: boolean; type?: boolean; year?: boolean };
  yearLabel?: string;
  /** Disallow "toutes les années" (pages that need a single year). */
  requireYear?: boolean;
}

/** Department / property type / year selectors, shared across pages. */
export function FilterBar({ meta, filters, onChange, show = { dept: true, type: true, year: true }, yearLabel = "Année", requireYear }: Props) {
  return (
    <div className="filter-bar" role="group" aria-label="Filtres">
      {show.dept && (
        <label className="field">
          <span>Département</span>
          <select value={filters.dept} onChange={(e) => onChange({ ...filters, dept: e.target.value })}>
            <option value={ALL}>Tous les départements</option>
            {meta.departments.map((d) => (
              <option key={d.code} value={d.code}>
                {d.code} - {d.label}
              </option>
            ))}
          </select>
        </label>
      )}
      {show.type && (
        <label className="field">
          <span>Type de bien</span>
          <select value={filters.type} onChange={(e) => onChange({ ...filters, type: e.target.value })}>
            <option value={ALL}>Maisons et appartements</option>
            {meta.types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
      )}
      {show.year && (
        <label className="field">
          <span>{yearLabel}</span>
          <select value={filters.year} onChange={(e) => onChange({ ...filters, year: e.target.value })}>
            {!requireYear && <option value={ALL}>{`${meta.years[0]}-${meta.lastYear}`}</option>}
            {[...meta.years].reverse().map((y) => (
              <option key={y} value={String(y)}>
                {y}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
