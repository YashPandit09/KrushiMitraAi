/** Binned colour scales for the district map. Colours themselves live in styles.css as tokens. */

export interface ScaleClass {
  token: string; // CSS custom property name
  label: string;
  test: (v: number) => boolean;
}

/** Diverging: forecast vs the district's own trend, in percent. Neutral band is ±3 %. */
export const DIVERGING: ScaleClass[] = [
  { token: "--div-n3", label: "≤ −20%", test: (v) => v <= -20 },
  { token: "--div-n2", label: "−20 to −10%", test: (v) => v > -20 && v <= -10 },
  { token: "--div-n1", label: "−10 to −3%", test: (v) => v > -10 && v < -3 },
  { token: "--div-0", label: "within ±3%", test: (v) => v >= -3 && v <= 3 },
  { token: "--div-p1", label: "+3 to +10%", test: (v) => v > 3 && v < 10 },
  { token: "--div-p2", label: "+10 to +20%", test: (v) => v >= 10 && v < 20 },
  { token: "--div-p3", label: "≥ +20%", test: (v) => v >= 20 },
];

/** Sequential: forecast yield level, t/ha (milled rice). */
export const SEQUENTIAL: ScaleClass[] = [
  { token: "--seq-1", label: "< 1.5", test: (v) => v < 1.5 },
  { token: "--seq-2", label: "1.5–2.0", test: (v) => v >= 1.5 && v < 2.0 },
  { token: "--seq-3", label: "2.0–2.5", test: (v) => v >= 2.0 && v < 2.5 },
  { token: "--seq-4", label: "2.5–3.0", test: (v) => v >= 2.5 && v < 3.0 },
  { token: "--seq-5", label: "≥ 3.0", test: (v) => v >= 3.0 },
];

export function classFor(scale: ScaleClass[], value: number | null | undefined): ScaleClass | undefined {
  if (value == null || Number.isNaN(value)) return undefined;
  return scale.find((c) => c.test(value));
}

export const tokenVar = (token: string) => `var(${token})`;
