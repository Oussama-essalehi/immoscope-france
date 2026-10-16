/** French number formatting helpers. */

const integer = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const fmtInt = (value: number | null | undefined): string =>
  value === null || value === undefined ? "–" : integer.format(value);

export const fmtEuro = (value: number | null | undefined): string =>
  value === null || value === undefined ? "–" : `${integer.format(value)} €`;

export const fmtEuroM2 = (value: number | null | undefined): string =>
  value === null || value === undefined ? "–" : `${integer.format(value)} €/m²`;

export const fmtM2 = (value: number | null | undefined): string =>
  value === null || value === undefined ? "–" : `${integer.format(value)} m²`;

/** Signed percentage from a ratio: 0.052 -> "+5,2 %". */
export const fmtPct = (ratio: number | null | undefined): string => {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return "–";
  const sign = ratio > 0 ? "+" : ratio < 0 ? "−" : "";
  return `${sign}${oneDecimal.format(Math.abs(ratio) * 100)} %`;
};

export const fmtYears = (value: number | null | undefined): string =>
  value === null || value === undefined ? "–" : `${oneDecimal.format(value)} ans`;

/** Compact euro tick: 250000 -> "250 k€". */
export const fmtKEuro = (value: number): string => `${integer.format(value / 1000)} k€`;

const MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

/** "2024-03" -> "mars 2024". */
export const fmtMonth = (ym: string): string => {
  const [y, m] = ym.split("-");
  return `${MONTHS[Number(m) - 1]} ${y}`;
};
