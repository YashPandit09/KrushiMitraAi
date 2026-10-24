import { useState } from "react";
import { monthName } from "../format";
import { useWidth } from "../hooks";
import type { MonthWeather } from "../types";
import { barPath, linear, ticks } from "./scale";

const M = { top: 12, right: 12, bottom: 28, left: 46 };

/** Monthly rainfall this season (columns) against the 1991-2020 normal (tick per month). */
export function RainColumns({ months, height = 220 }: { months: MonthWeather[]; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const maxV = Math.max(50, ...months.map((m) => Math.max(m.prcp ?? 0, m.prcp_normal ?? 0)));
  const yt = ticks(0, maxV * 1.05, 4);
  const y = linear([0, yt.max], [height - M.bottom, M.top]);
  const band = (width - M.left - M.right) / Math.max(1, months.length);
  const colW = Math.min(24, band * 0.5);

  const act = months.find((m) => m.month === active);
  return (
    <div className="chart" ref={ref}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Monthly rainfall this season compared with the 1991 to 2020 normal">
        {yt.values.map((v) => (
          <g key={v} className="tick">
            {v !== 0 && <line className="gridline" x1={M.left} x2={width - M.right} y1={y(v)} y2={y(v)} />}
            <text x={M.left - 8} y={y(v)} dy="0.32em" textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        <line className="baseline" x1={M.left} x2={width - M.right} y1={y(0)} y2={y(0)} />
        {months.map((m, i) => {
          const cx = M.left + band * i + band / 2;
          const v = m.prcp ?? 0;
          const h = Math.max(0, y(0) - y(v));
          return (
            <g
              key={m.month}
              tabIndex={0}
              aria-label={`${monthName(m.month)}: ${Math.round(v)} millimetres, normal ${Math.round(m.prcp_normal ?? 0)}`}
              onPointerEnter={() => setActive(m.month)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(m.month)}
              onBlur={() => setActive(null)}
              style={{ outline: "none" }}
            >
              <rect x={cx - band / 2} y={M.top} width={band} height={height - M.top - M.bottom} fill={active === m.month ? "var(--hover)" : "transparent"} />
              {h > 0 && <path d={barPath(cx - colW / 2, y(v), colW, h, 4, "top")} fill="var(--series-1)" />}
              {m.prcp_normal != null && (
                <line x1={cx - colW / 2 - 6} x2={cx + colW / 2 + 6} y1={y(m.prcp_normal)} y2={y(m.prcp_normal)} stroke="var(--ink-2)" strokeWidth={2} strokeLinecap="round" />
              )}
              <text x={cx} y={height - 8} textAnchor="middle" style={{ fill: "var(--muted)", fontSize: 12 }}>
                {monthName(m.month)}
              </text>
            </g>
          );
        })}
      </svg>
      {act && (
        <div
          className="tooltip"
          role="status"
          style={{ left: Math.min(Math.max(M.left + band * months.indexOf(act) + band / 2, 90), width - 90), top: y(Math.max(act.prcp ?? 0, act.prcp_normal ?? 0)) }}
        >
          <div className="tt-title">
            {monthName(act.month)} {act.year}
          </div>
          <div className="tt-row">
            <span>
              <span className="key-rect" style={{ background: "var(--series-1)", width: 10, height: 10 }} aria-hidden="true" />
              Rainfall
            </span>
            <strong>{Math.round(act.prcp ?? 0)} mm</strong>
          </div>
          <div className="tt-row">
            <span>
              <span className="key-line" style={{ background: "var(--ink-2)" }} aria-hidden="true" />
              Normal
            </span>
            <strong>{Math.round(act.prcp_normal ?? 0)} mm</strong>
          </div>
          {act.prcp_normal ? (
            <div className="tt-row">
              <span>Of normal</span>
              <strong>{Math.round(((act.prcp ?? 0) / act.prcp_normal) * 100)}%</strong>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
