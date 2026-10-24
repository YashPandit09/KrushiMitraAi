import { useMemo, useState, type KeyboardEvent, type PointerEvent } from "react";
import { useWidth } from "../hooks";
import { linear, ticks } from "./scale";

export interface LinePoint {
  x: number;
  y: number | null;
}
export interface LineSeries {
  id: string;
  label: string;
  color: string;
  points: LinePoint[];
  dots?: boolean;
}
export interface BandPoint {
  x: number;
  lo: number | null;
  hi: number | null;
}
export interface TooltipRow {
  color?: string;
  label: string;
  value: string;
}

interface Props {
  series: LineSeries[];
  band?: { color: string; points: BandPoint[] };
  height?: number;
  formatY: (v: number) => string;
  tooltip: (x: number) => { title: string; rows: TooltipRow[] };
  ariaLabel: string;
}

const MARGIN = { top: 14, right: 104, bottom: 28, left: 46 };

function segments<T>(pts: T[], ok: (p: T) => boolean): T[][] {
  const out: T[][] = [];
  let cur: T[] = [];
  for (const p of pts) {
    if (ok(p)) cur.push(p);
    else if (cur.length) {
      out.push(cur);
      cur = [];
    }
  }
  if (cur.length) out.push(cur);
  return out;
}

export function LineChart({ series, band, height = 280, formatY, tooltip, ariaLabel }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  const xs = useMemo(() => {
    const all = new Set<number>();
    series.forEach((s) => s.points.forEach((p) => all.add(p.x)));
    band?.points.forEach((p) => all.add(p.x));
    return [...all].sort((a, b) => a - b);
  }, [series, band]);

  const right = width < 520 ? 16 : MARGIN.right;
  const x = linear([xs[0] ?? 0, xs[xs.length - 1] ?? 1], [MARGIN.left, Math.max(MARGIN.left + 10, width - right)]);
  const maxY = Math.max(
    0.5,
    ...series.flatMap((s) => s.points.map((p) => p.y ?? 0)),
    ...(band?.points.map((p) => p.hi ?? 0) ?? []),
  );
  const yt = ticks(0, maxY * 1.04, 5);
  const y = linear([0, yt.max], [height - MARGIN.bottom, MARGIN.top]);

  // Evenly spaced years (1, 2, 5 or 10 apart), independent of gaps in the data.
  const x0 = xs[0] ?? 0;
  const x1 = xs[xs.length - 1] ?? 0;
  const room = Math.max(2, Math.floor((width - MARGIN.left - right) / 48));
  const step = [1, 2, 5, 10, 20].find((s) => (x1 - x0) / s <= room) ?? 20;
  const xTicks: number[] = [];
  for (let t = Math.ceil(x0 / step) * step; t <= x1; t += step) xTicks.push(t);

  const bandPaths = band
    ? segments(band.points, (p) => p.lo != null && p.hi != null).map((seg) => {
        const top = seg.map((p) => `${x(p.x)},${y(p.hi!)}`).join("L");
        const bottom = [...seg].reverse().map((p) => `${x(p.x)},${y(p.lo!)}`).join("L");
        return `M${top}L${bottom}Z`;
      })
    : [];

  // Direct end labels, dropped when they would collide (the legend still carries identity).
  const ends = series
    .map((s) => {
      const last = [...s.points].reverse().find((p) => p.y != null);
      return last ? { id: s.id, label: s.label, px: x(last.x), py: y(last.y!) } : null;
    })
    .filter((e): e is { id: string; label: string; px: number; py: number } => e !== null);
  const collide = ends.some((a, i) => ends.some((b, j) => i < j && Math.abs(a.py - b.py) < 16));
  const showEnds = width >= 520 && !collide;

  const nearest = (px: number) => {
    const v = x.invert(px);
    return xs.reduce((best, cur) => (Math.abs(cur - v) < Math.abs(best - v) ? cur : best), xs[0]);
  };
  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const rect = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    setActive(nearest(((e.clientX - rect.left) / rect.width) * width));
  };
  const onKey = (e: KeyboardEvent<SVGRectElement>) => {
    if (!xs.length) return;
    const i = active == null ? xs.length - 1 : xs.indexOf(active);
    if (e.key === "ArrowLeft") setActive(xs[Math.max(0, i - 1)]);
    else if (e.key === "ArrowRight") setActive(xs[Math.min(xs.length - 1, i + 1)]);
    else if (e.key === "Escape") setActive(null);
    else return;
    e.preventDefault();
  };

  const tip = active != null ? tooltip(active) : null;
  const tipY = active != null
    ? Math.min(...series.map((s) => s.points.find((p) => p.x === active)?.y ?? Infinity).map((v) => (v === Infinity ? height : y(v))))
    : 0;
  const tipX = active != null ? Math.min(Math.max(x(active), 90), width - 90) : 0;

  return (
    <div className="chart" ref={ref}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel}>
        {yt.values.map((v) => (
          <g key={v} className="tick">
            {v !== 0 && <line className="gridline" x1={MARGIN.left} x2={width - right} y1={y(v)} y2={y(v)} />}
            <text x={MARGIN.left - 8} y={y(v)} dy="0.32em" textAnchor="end">
              {formatY(v)}
            </text>
          </g>
        ))}
        <line className="baseline" x1={MARGIN.left} x2={width - right} y1={y(0)} y2={y(0)} />
        {xTicks.map((v) => (
          <text key={v} className="tick" x={x(v)} y={height - 8} textAnchor="middle" style={{ fill: "var(--muted)", fontSize: 12 }}>
            {v}
          </text>
        ))}
        {band && bandPaths.map((d, i) => <path key={i} d={d} fill={band.color} stroke="none" />)}
        {series.map((s) =>
          segments(s.points, (p) => p.y != null).map((seg, i) => (
            <path
              key={`${s.id}-${i}`}
              d={`M${seg.map((p) => `${x(p.x)},${y(p.y!)}`).join("L")}`}
              fill="none"
              stroke={s.color}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )),
        )}
        {series
          .filter((s) => s.dots)
          .map((s) =>
            s.points
              .filter((p) => p.y != null)
              .map((p) => (
                <circle
                  key={`${s.id}-${p.x}`}
                  cx={x(p.x)}
                  cy={y(p.y!)}
                  r={active === p.x ? 5 : 4}
                  fill={s.color}
                  stroke="var(--surface)"
                  strokeWidth={2}
                />
              )),
          )}
        {showEnds &&
          ends.map((e) => (
            <text key={e.id} className="end-label" x={e.px + 9} y={e.py} dy="0.32em">
              {e.label}
            </text>
          ))}
        {active != null && <line className="crosshair" x1={x(active)} x2={x(active)} y1={MARGIN.top} y2={height - MARGIN.bottom} />}
        <rect
          x={MARGIN.left}
          y={0}
          width={Math.max(0, width - right - MARGIN.left)}
          height={height - MARGIN.bottom}
          fill="transparent"
          tabIndex={0}
          aria-label="Chart: use left and right arrow keys to read values"
          onPointerMove={onMove}
          onPointerLeave={() => setActive(null)}
          onFocus={() => setActive((a) => a ?? xs[xs.length - 1] ?? null)}
          onBlur={() => setActive(null)}
          onKeyDown={onKey}
          style={{ outline: "none" }}
        />
      </svg>
      {tip && (
        <div className="tooltip" role="status" style={{ left: tipX, top: Math.max(tipY, MARGIN.top + 40) }}>
          <div className="tt-title">{tip.title}</div>
          {tip.rows.map((r) => (
            <div className="tt-row" key={r.label}>
              <span>
                {r.color && <span className="key-line" style={{ background: r.color }} aria-hidden="true" />}
                {r.label}
              </span>
              <strong>{r.value}</strong>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
