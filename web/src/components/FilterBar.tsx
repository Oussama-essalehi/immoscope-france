import { ALL, type Filters, type Meta } from "../data";
import { useI18n } from "../i18n";
import type { MessageKey } from "../locales";

interface Props {
  meta: Meta;
  filters: Filters;
  onChange: (next: Filters) => void;
  /** Which filters this page exposes. */
  show?: { dept?: boolean; type?: boolean; year?: boolean };
  yearLabel?: string;
  /** Disallow "all years" (pages that need a single year). */
  requireYear?: boolean;
}

/** Department / property type / year selectors, shared across pages. */
export function FilterBar({ meta, filters, onChange, show = { dept: true, type: true, year: true }, yearLabel, requireYear }: Props) {
  const { t } = useI18n();
  return (
    <div className="filter-bar" role="group" aria-label={t("filters.group")}>
      {show.dept && (
        <label className="field">
          <span>{t("filters.dept")}</span>
          <select value={filters.dept} onChange={(e) => onChange({ ...filters, dept: e.target.value })}>
            <option value={ALL}>{t("filters.allDepts")}</option>
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
          <span>{t("filters.type")}</span>
          <select value={filters.type} onChange={(e) => onChange({ ...filters, type: e.target.value })}>
            <option value={ALL}>{t("filters.allTypes")}</option>
            {meta.types.map((type) => (
              <option key={type} value={type}>
                {t(`type.${type}` as MessageKey)}
              </option>
            ))}
          </select>
        </label>
      )}
      {show.year && (
        <label className="field">
          <span>{yearLabel ?? t("filters.year")}</span>
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
