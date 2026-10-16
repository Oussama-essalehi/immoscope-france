/** Number and date formatting, French or English conventions. */

export type Lang = "fr" | "en";

export interface Formatters {
  int: (value: number | null | undefined) => string;
  euro: (value: number | null | undefined) => string;
  euroM2: (value: number | null | undefined) => string;
  m2: (value: number | null | undefined) => string;
  /** signed percentage from a ratio: 0.052 -> "+5,2 %" / "+5.2%" */
  pct: (ratio: number | null | undefined) => string;
  years: (value: number | null | undefined) => string;
  /** compact euro tick: 250000 -> "250 k€" / "€250k" */
  kEuro: (value: number) => string;
  /** multiplier: 2.34 -> "x 2,3" / "x2.3" */
  times: (value: number) => string;
  /** "2024-03" -> "mars 2024" / "Mar 2024" */
  month: (ym: string) => string;
}

const MISSING = "–";

const MONTHS: Record<Lang, string[]> = {
  fr: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
};

export function makeFormatters(lang: Lang): Formatters {
  const locale = lang === "fr" ? "fr-FR" : "en-GB";
  const integer = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
  const oneDecimal = new Intl.NumberFormat(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const fr = lang === "fr";
  const guard =
    (fn: (v: number) => string) =>
    (value: number | null | undefined): string =>
      value === null || value === undefined || Number.isNaN(value) ? MISSING : fn(value);

  return {
    int: guard((v) => integer.format(v)),
    euro: guard((v) => (fr ? `${integer.format(v)} €` : `€${integer.format(v)}`)),
    euroM2: guard((v) => (fr ? `${integer.format(v)} €/m²` : `€${integer.format(v)}/m²`)),
    m2: guard((v) => `${integer.format(v)} m²`),
    pct: guard((ratio) => {
      const sign = ratio > 0 ? "+" : ratio < 0 ? "−" : "";
      const body = oneDecimal.format(Math.abs(ratio) * 100);
      return fr ? `${sign}${body} %` : `${sign}${body}%`;
    }),
    years: guard((v) => (fr ? `${oneDecimal.format(v)} ans` : `${oneDecimal.format(v)} yrs`)),
    kEuro: (v) => (fr ? `${integer.format(v / 1000)} k€` : `€${integer.format(v / 1000)}k`),
    times: (v) => (fr ? `x ${oneDecimal.format(v)}` : `x${oneDecimal.format(v)}`),
    month: (ym) => {
      const [y, m] = ym.split("-");
      return `${MONTHS[lang][Number(m) - 1]} ${y}`;
    },
  };
}
