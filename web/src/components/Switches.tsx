import type { Lang } from "../format";
import { useI18n } from "../i18n";
import type { Mode } from "../theme";

const Sun = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
    <circle cx="12" cy="12" r="4.5" fill="currentColor" />
    {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
      <line key={a} x1="12" y1="2.5" x2="12" y2="5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" transform={`rotate(${a} 12 12)`} />
    ))}
  </svg>
);

const Moon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
    <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" fill="currentColor" />
  </svg>
);

/** Light / dark switch: a real `role="switch"` control with sun and moon icons. */
export function ThemeSwitch({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  const { t } = useI18n();
  const dark = mode === "dark";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label={t("theme.dark")}
      title={dark ? t("theme.light") : t("theme.dark")}
      className="theme-switch"
      onClick={() => onChange(dark ? "light" : "dark")}
    >
      <span className="theme-switch-icon">
        <Sun />
      </span>
      <span className="theme-switch-icon">
        <Moon />
      </span>
      <span className="theme-switch-thumb" aria-hidden="true" />
    </button>
  );
}

/** FR / EN segmented control. */
export function LangSwitch({ lang, onChange }: { lang: Lang; onChange: (l: Lang) => void }) {
  const { t } = useI18n();
  return (
    <div className="lang-switch" role="radiogroup" aria-label={t("lang.label")}>
      {(["fr", "en"] as const).map((l) => (
        <button key={l} type="button" role="radio" aria-checked={lang === l} className={lang === l ? "active" : ""} onClick={() => onChange(l)} lang={l}>
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
