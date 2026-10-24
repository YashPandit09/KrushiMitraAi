import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../api";
import { classFor, DIVERGING, SEQUENTIAL, tokenVar } from "../colors";
import { ChoroplethMap, ScaleLegend, type MapDatum } from "../components/ChoroplethMap";
import { Figure } from "../components/Figure";
import { ErrorNote, Loading } from "../components/State";
import { dateLabel, leadName, signedPct, tHa } from "../format";
import { useAsync } from "../hooks";
import type { Forecast, Lead } from "../types";

type SortKey = "name" | "forecast" | "anomaly" | "rain";

export default function Overview() {
  const meta = useAsync((s) => api.meta(s), []);
  const geo = useAsync((s) => api.geojson(s), []);
  const districts = useAsync((s) => api.districts(s), []);
  const card = useAsync((s) => api.modelCard(s), []);

  const years = useMemo(
    () => (meta.data ? Object.keys(meta.data.forecast_years).map(Number).sort((a, b) => a - b) : []),
    [meta.data],
  );
  const [params, setParams] = useSearchParams();
  const yearParam = Number(params.get("season"));
  const yearSel = years.includes(yearParam) ? yearParam : null;
  const leadSel = params.get("lead") as Lead | null;
  const setYear = (y: number) =>
    setParams(
      (p) => {
        p.set("season", String(y));
        return p;
      },
      { replace: true },
    );
  const setLead = (l: Lead) =>
    setParams(
      (p) => {
        p.set("lead", l);
        return p;
      },
      { replace: true },
    );
  const [colorChoice, setColorBy] = useState<"anomaly" | "level" | null>(null);
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "anomaly", desc: false });

  const year = yearSel ?? years[years.length - 1];
  const available = meta.data?.forecast_years[String(year)] ?? [];
  const lead = leadSel && available.includes(leadSel) ? leadSel : available[available.length - 1];
  const map = useAsync((s) => (year && lead ? api.forecastMap(year, lead, s) : Promise.resolve(undefined)), [year, lead]);

  const names = useMemo(() => Object.fromEntries((districts.data ?? []).map((d) => [d.slug, d.name])), [districts.data]);
  const rows: Forecast[] = useMemo(() => map.data?.districts ?? [], [map.data]);
  // Until the user picks, colour by deviation only when some district actually deviates from its trend
  // (early issue dates use the trend alone, which would make the "vs trend" map uniformly neutral).
  const anyDeviation = rows.some((r) => Math.abs(r.forecast_t_ha / r.trend_t_ha - 1) > 0.03);
  const colorBy = colorChoice ?? (anyDeviation ? "anomaly" : "level");
  const scale = colorBy === "anomaly" ? DIVERGING : SEQUENTIAL;
  const mapData = useMemo(() => {
    const out: Record<string, MapDatum> = {};
    for (const r of rows) {
      out[r.district_slug] = {
        slug: r.district_slug,
        name: names[r.district_slug] ?? r.district_slug,
        value: colorBy === "anomaly" ? (r.forecast_t_ha / r.trend_t_ha - 1) * 100 : r.forecast_t_ha,
        lines: [
          { label: "Forecast", value: tHa(r.forecast_t_ha) },
          { label: "80% range", value: `${r.lo80.toFixed(2)}–${r.hi80.toFixed(2)}` },
          { label: "vs trend", value: signedPct((r.forecast_t_ha / r.trend_t_ha - 1) * 100) },
        ],
      };
    }
    return out;
  }, [rows, names, colorBy]);

  if (meta.error) return <ErrorNote error={meta.error} />;
  if (!meta.data || !geo.data) return <Loading />;

  const latest = meta.data.last_season_with_official_yield;
  const status = year > latest + 1 ? "in season" : "awaiting official figures";
  const below = rows.filter((r) => r.forecast_t_ha < r.trend_t_ha * 0.97).length;
  const typical = card.data && lead ? card.data.chosen.test_by_lead[lead] : undefined;
  const stateTypical = card.data && lead ? card.data.chosen.state_test_by_lead?.[lead] : undefined;
  const coverage = card.data && lead ? card.data.chosen.coverage[lead]?.["80"]?.coverage : undefined;
  const st = map.data?.state;

  const sorted = [...rows].sort((a, b) => {
    const val = (r: Forecast) =>
      sort.key === "name"
        ? (names[r.district_slug] ?? "")
        : sort.key === "forecast"
          ? r.forecast_t_ha
          : sort.key === "anomaly"
            ? r.forecast_t_ha / r.trend_t_ha
            : r.season_rain_anomaly_pct;
    const va = val(a);
    const vb = val(b);
    const c = typeof va === "string" ? va.localeCompare(vb as string) : (va as number) - (vb as number);
    return sort.desc ? -c : c;
  });
  const th = (key: SortKey, label: string, num = true) => (
    <th className={num ? "num" : undefined} aria-sort={sort.key === key ? (sort.desc ? "descending" : "ascending") : "none"}>
      <button type="button" onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : false }))}>
        {label}
        {sort.key === key ? (sort.desc ? " ↓" : " ↑") : ""}
      </button>
    </th>
  );

  const table = (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {th("name", "District", false)}
            {th("forecast", "Forecast (t/ha)")}
            <th className="num">80% range</th>
            {th("anomaly", "vs trend")}
            {th("rain", "Season rain vs normal")}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const cls = classFor(scale, mapData[r.district_slug]?.value);
            return (
              <tr key={r.district_slug}>
                <td>
                  <span className="dot" style={{ background: cls ? tokenVar(cls.token) : "transparent" }} aria-hidden="true" />
                  <Link className="row-link" to={`/district/${r.district_slug}?season=${year}&lead=${lead}`}>
                    {names[r.district_slug] ?? r.district_slug}
                  </Link>
                </td>
                <td className="num">{r.forecast_t_ha.toFixed(2)}</td>
                <td className="num">
                  {r.lo80.toFixed(2)}–{r.hi80.toFixed(2)}
                </td>
                <td className="num">{signedPct((r.forecast_t_ha / r.trend_t_ha - 1) * 100)}</td>
                <td className="num">{signedPct(r.season_rain_anomaly_pct)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  return (
    <>
      <div className="page-head">
        <div className="eyebrow">
          Kharif {year} · {status}
        </div>
        <h1>Kharif rice yield outlook for Odisha's 30 districts</h1>
        <p>
          Each forecast starts from the district's long-run yield trend and - at issue dates where that has proven
          useful - adjusts it for this season's rainfall, soil moisture, heat and cyclones, using only what was known on
          the issue date. Ranges are calibrated on past misses.
        </p>
      </div>

      <div className="filters" role="group" aria-label="Forecast filters">
        <label className="field">
          Season
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {years.map((y) => (
              <option key={y} value={y}>
                Kharif {y}
                {y > latest + 1 ? " (in season)" : " (awaiting official figures)"}
              </option>
            ))}
          </select>
        </label>
        <div className="field">
          Forecast issued after
          <div className="seg" role="group" aria-label="Forecast issue date">
            {meta.data.leads.map((l) => (
              <button key={l} type="button" aria-pressed={l === lead} disabled={!available.includes(l)} onClick={() => setLead(l)}>
                {l}
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          Colour districts by
          <div className="seg" role="group" aria-label="Map colour">
            <button type="button" aria-pressed={colorBy === "anomaly"} onClick={() => setColorBy("anomaly")}>
              vs trend
            </button>
            <button type="button" aria-pressed={colorBy === "level"} onClick={() => setColorBy("level")}>
              Yield
            </button>
          </div>
        </div>
      </div>

      <div className="grid-2">
        <Figure
          title={colorBy === "anomaly" ? "Forecast compared with each district's trend" : "Forecast yield by district"}
          subtitle={`Kharif ${year}, issued after the ${lead ? leadName(lead) : ""}. Select a district for details.`}
          table={table}
          busy={map.loading}
          footnote="Rice yields are milled-rice equivalent, as published by the Directorate of Economics & Statistics."
        >
          <ChoroplethMap
            geojson={geo.data}
            data={mapData}
            linkQuery={`season=${year}&lead=${lead}`}
            scale={scale}
            ariaLabel={`Map of Odisha districts coloured by ${colorBy === "anomaly" ? "forecast versus trend" : "forecast yield"}`}
          />
          <ScaleLegend scale={scale} title={colorBy === "anomaly" ? "Forecast vs trend" : "Forecast, t/ha"} />
        </Figure>

        <div className="stack">
          <section className="card" aria-labelledby="state-h">
            <div className="hero">
              <span className="hero-label" id="state-h">
                Odisha, area-weighted forecast
              </span>
              <span className="hero-value">
                {st ? st.forecast_t_ha.toFixed(2) : "–"}
                <small>t/ha</small>
              </span>
              <span className="hero-meta">
                {st ? `80% range ${st.lo80.toFixed(2)}–${st.hi80.toFixed(2)} · trend ${st.trend_t_ha.toFixed(2)}` : ""}
              </span>
            </div>
            <div className="tiles">
              <div className="tile">
                <div className="tile-label">vs trend</div>
                <div className="tile-value">{st ? signedPct((st.forecast_t_ha / st.trend_t_ha - 1) * 100, 1) : "–"}</div>
                <div className="tile-note">weather & cyclone adjustment</div>
              </div>
              <div className="tile">
                <div className="tile-label">Districts below trend</div>
                <div className="tile-value">
                  {rows.length ? below : "–"} <span className="muted small">of {rows.length}</span>
                </div>
                <div className="tile-note">more than 3% below</div>
              </div>
              <div className="tile">
                <div className="tile-label">Weather data through</div>
                <div className="tile-value" style={{ fontSize: "1.1rem" }}>
                  {dateLabel(meta.data.weather_through)}
                </div>
                <div className="tile-note">NASA POWER, daily</div>
              </div>
            </div>
          </section>

          <section className="card" aria-labelledby="trust-h">
            <h2 id="trust-h">How much to trust this</h2>
            {typical ? (
              <p className="sub" style={{ marginBottom: 6 }}>
                In 2015–2024 backtests at this issue date, district forecasts missed the official yield by{" "}
                <strong>{typical.mape.toFixed(0)}%</strong> on average
                {stateTypical ? (
                  <>
                    {" "}
                    (the state-wide figure by <strong>{stateTypical.mape.toFixed(0)}%</strong>)
                  </>
                ) : null}
                . The 80% range contained the official figure {coverage != null ? `${Math.round(coverage * 100)}%` : "–"}{" "}
                of the time.
              </p>
            ) : (
              <p className="sub">Loading backtest results…</p>
            )}
            <p className="small muted" style={{ margin: 0 }}>
              District statistics swing a lot from year to year. Use the range, not just the central number.{" "}
              <Link to="/methodology">See how it works</Link>.
            </p>
          </section>
        </div>
      </div>
    </>
  );
}
