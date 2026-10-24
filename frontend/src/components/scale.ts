/** Tiny linear scale + "nice" ticks - all the charts need, without pulling in d3-scale. */
export interface Linear {
  (v: number): number;
  domain: [number, number];
  range: [number, number];
  invert: (px: number) => number;
}

export function linear(domain: [number, number], range: [number, number]): Linear {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0);
  const f = ((v: number) => r0 + (v - d0) * k) as Linear;
  f.domain = domain;
  f.range = range;
  f.invert = (px: number) => (k === 0 ? d0 : d0 + (px - r0) / k);
  return f;
}

export function niceStep(span: number, target = 5): number {
  if (span <= 0 || !Number.isFinite(span)) return 1;
  const raw = span / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const nice = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
  return nice * mag;
}

/** Ticks from lo..hi (inclusive) on a nice step; also returns the nice upper bound. */
export function ticks(lo: number, hi: number, target = 5): { values: number[]; max: number; min: number } {
  const step = niceStep(hi - lo, target);
  const min = Math.floor(lo / step) * step;
  const max = Math.ceil(hi / step) * step;
  const values: number[] = [];
  for (let v = min; v <= max + step / 2; v += step) values.push(Number(v.toFixed(10)));
  return { values, max, min };
}

/** SVG path for a bar with a rounded data end and a square baseline end. */
export function barPath(x: number, y: number, w: number, h: number, r: number, end: "top" | "right" | "left"): string {
  r = Math.max(0, Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2));
  if (end === "top") {
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  }
  if (end === "right") {
    return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`;
  }
  return `M${x + w},${y}H${x + r}Q${x},${y} ${x},${y + r}V${y + h - r}Q${x},${y + h} ${x + r},${y + h}H${x + w}Z`;
}
