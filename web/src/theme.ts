/**
 * Colour tokens, one set per mode. Same palette as the Python charts and the
 * Power BI theme; the dark set is stepped for the dark surface, not inverted.
 */
import { createContext, useContext } from "react";

export type Mode = "light" | "dark";

export interface Palette {
  surface: string;
  ink: string;
  ink2: string;
  muted: string;
  grid: string;
  axis: string;
  series: string[];
  /** sequential blue ramp, low -> high magnitude */
  sequential: string[];
  /** diverging poles and neutral midpoint: fall / neutral / rise */
  fall: string;
  neutral: string;
  rise: string;
}

export const PALETTES: Record<Mode, Palette> = {
  light: {
    surface: "#fcfcfb",
    ink: "#0b0b0b",
    ink2: "#52514e",
    muted: "#898781",
    grid: "#e1e0d9",
    axis: "#c3c2b7",
    series: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    sequential: ["#b7d3f6", "#6da7ec", "#2a78d6", "#1c5cab", "#104281"],
    fall: "#2a78d6",
    neutral: "#f0efec",
    rise: "#e34948",
  },
  dark: {
    surface: "#1a1a19",
    ink: "#f0efec",
    ink2: "#c3c2b7",
    muted: "#898781",
    grid: "#2c2c2a",
    axis: "#383835",
    series: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
    sequential: ["#184f95", "#256abf", "#3987e5", "#6da7ec", "#b7d3f6"],
    fall: "#3987e5",
    neutral: "#383835",
    rise: "#e66767",
  },
};

export const ThemeContext = createContext<Palette>(PALETTES.light);
export const usePalette = (): Palette => useContext(ThemeContext);

/** Linear blend between two hex colours, t in [0, 1]. */
export function mix(a: string, b: string, t: number): string {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * Math.max(0, Math.min(1, t))));
  return `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

/** Diverging colour for a relative change, saturating at +/- `cap`. */
export function divergingColor(palette: Palette, ratio: number, cap = 0.1): string {
  const t = Math.min(Math.abs(ratio) / cap, 1);
  return mix(palette.neutral, ratio < 0 ? palette.fall : palette.rise, t);
}
