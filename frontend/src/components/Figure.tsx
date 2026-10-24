import { useId, useState, type ReactNode } from "react";

interface FigureProps {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  /** The accessible twin of the chart. When given, a "Show table" toggle appears. */
  table?: ReactNode;
  actions?: ReactNode;
  footnote?: ReactNode;
  busy?: boolean;
}

export function Figure({ title, subtitle, children, table, actions, footnote, busy }: FigureProps) {
  const [showTable, setShowTable] = useState(false);
  const id = useId();
  return (
    <figure className="card" aria-labelledby={`${id}-t`} style={{ margin: 0 }}>
      <div className="card-head">
        <div>
          <h2 id={`${id}-t`}>{title}</h2>
          {subtitle && <p className="sub">{subtitle}</p>}
        </div>
        <div className="card-actions">
          {actions}
          {table && (
            <button type="button" className="btn-link" aria-pressed={showTable} onClick={() => setShowTable((v) => !v)}>
              {showTable ? "Show chart" : "Show table"}
            </button>
          )}
        </div>
      </div>
      <div className={busy ? "loading-fade" : undefined}>{showTable && table ? table : children}</div>
      {footnote && <figcaption className="muted small" style={{ marginTop: 8 }}>{footnote}</figcaption>}
    </figure>
  );
}

export function LegendLine({ color, label }: { color: string; label: string }) {
  return (
    <li>
      <span className="key-line" style={{ background: color }} aria-hidden="true" />
      {label}
    </li>
  );
}

export function LegendRect({ color, label }: { color: string; label: string }) {
  return (
    <li>
      <span className="key-rect" style={{ background: color }} aria-hidden="true" />
      {label}
    </li>
  );
}
