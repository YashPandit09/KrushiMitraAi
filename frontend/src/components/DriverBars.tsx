import { useState } from "react";
import { useWidth } from "../hooks";
import { barPath, linear } from "./scale";

export interface DriverBar {
  key: string;
  label: string;
  value: string; // observed value, e.g. "−32%"
  effect: number; // t/ha
}

const ROW = 46; // label line + bar line
const BAR = 12;

/** Horizontal diverging bars: each driver's effect on the forecast, centred on zero. */
export function DriverBars({ bars, format }: { bars: DriverBar[]; format: (v: number) => string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<string | null>(null);
  const pad = 52; // room for the value at the tip
  const maxAbs = Math.max(0.02, ...bars.map((b) => Math.abs(b.effect)));
  const x = linear([-maxAbs, maxAbs], [pad, width - pad]);
  const zero = x(0);
  const height = bars.length * ROW;

  return (
    <div className="chart" ref={ref}>
      <svg viewBox={`0 0 ${width} ${height}`} role="list" aria-label="Effect of each driver on the forecast, tonnes per hectare">
        {bars.map((b, i) => {
          const top = i * ROW;
          const yBar = top + 24;
          const positive = b.effect >= 0;
          const w = Math.max(2, Math.abs(x(b.effect) - zero));
          const d = positive
            ? barPath(zero, yBar, w, BAR, 4, "right")
            : barPath(zero - w, yBar, w, BAR, 4, "left");
          return (
            <g
              key={b.key}
              tabIndex={0}
              role="listitem"
              aria-label={`${b.label}: ${b.value}. Effect on forecast ${format(b.effect)} tonnes per hectare`}
              onPointerEnter={() => setActive(b.key)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(b.key)}
              onBlur={() => setActive(null)}
              style={{ outline: "none" }}
            >
              <rect x={0} y={top + 2} width={width} height={ROW - 4} rx={6} fill={active === b.key ? "var(--hover)" : "transparent"} />
              <text x={4} y={top + 14} style={{ fill: "var(--ink-2)", fontSize: 13 }}>
                {b.label}
                <tspan style={{ fill: "var(--ink)", fontWeight: 600 }} dx={6}>
                  {b.value}
                </tspan>
              </text>
              <line className="baseline" x1={zero} x2={zero} y1={yBar - 4} y2={yBar + BAR + 4} />
              <path d={d} fill={positive ? "var(--div-p3)" : "var(--div-n3)"} />
              <text
                x={positive ? zero + w + 6 : zero - w - 6}
                y={yBar + BAR / 2}
                dy="0.32em"
                textAnchor={positive ? "start" : "end"}
                style={{ fill: "var(--ink)", fontSize: 12, fontVariantNumeric: "tabular-nums", fontWeight: 600 }}
              >
                {format(b.effect)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
