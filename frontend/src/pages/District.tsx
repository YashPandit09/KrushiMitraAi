import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { api } from "../api";
import { CropExplorer } from "../components/CropExplorer";
import { DriverBars } from "../components/DriverBars";
import { Figure, LegendLine, LegendRect } from "../components/Figure";
import { LineChart } from "../components/LineChart";
import { LiveWeather } from "../components/LiveWeather";
import { MarketPrices } from "../components/MarketPrices";
import { RainColumns } from "../components/RainColumns";
import { ErrorNote, Loading, WarningIcon } from "../components/State";
import { dateLabel, driverValue, leadName, monthName, paddyQuintalPerAcre, signed, signedPct, tHa } from "../format";
import { useAsync } from "../hooks";
import type { Lead } from "../types";

/** IMD classification by maximum sustained wind (knots). */
function imdCategory(kt: number): string {
  if (kt >= 120) return "Super cyclonic storm";
  if (kt >= 90) return "Extremely severe cyclonic storm";
  if (kt >= 64) return "Very severe cyclonic storm";
  if (kt >= 48) return "Severe cyclonic storm";
  return "Cyclonic storm";
}

const MODEL_NAMES: Record<string, string> = {
  "trend|none|w=all": "trend only",
  "ridge|compact|w=all": "trend + weather (ridge regression)",
  "lgbm|compact|w=all": "trend + weather (gradient boosting)",
  "ensemble|compact|w=all": "trend + weather (ensemble average)",
};

export default function DistrictPage() {
  const { slug = "" } = useParams();
  const meta = useAsync((s) => api.meta(s), []);
  const detail = useAsync((s) => api.district(slug, s), [slug]);
  const fcs = useAsync((s) => api.districtForecasts(slug, s), [slug]);

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
  const year = yearSel ?? years[years.length - 1];
  const available = meta.data?.forecast_years[String(year)] ?? [];
  const lead = leadSel && available.includes(leadSel) ? leadSel : available[available.length - 1];

  const bt = useAsync((s) => (lead ? api.backtest(slug, lead, s) : Promise.resolve(undefined)), [slug, lead]);
  const season = useAsync((s) => (year ? api.seasonWeather(slug, year, s) : Promise.resolve(undefined)), [slug, year]);

  if (detail.error) return <ErrorNote error={detail.error} />;
  if (!detail.data || !meta.data) return <Loading />;

  const d = detail.data;
  const forecast = fcs.data?.forecasts.find((f) => f.year === year && f.lead === lead);
  // Monsoon depressions are part of normal rainfall; flag only systems of cyclonic-storm strength.
  const storms = (forecast?.cyclones ?? []).filter((c) => c.max_wind_kt >= 34);
  const seasonal = (forecast?.drivers ?? []).filter((dr) => dr.unit !== "flag");
  const futureForLead = (fcs.data?.forecasts ?? []).filter((f) => f.lead === lead).sort((a, b) => a.year - b.year);
  const lastOfficial = [...d.kharif_rice].reverse().find((r) => r.yield_t_ha != null);
  const rows = bt.data?.rows ?? [];
  const months = season.data?.months ?? [];

  const pastMisses = rows.filter((r) => r.actual != null && r.forecast != null && r.year >= 2015);
  const mape = pastMisses.length
    ? (pastMisses.reduce((acc, r) => acc + Math.abs(r.forecast! / r.actual! - 1), 0) / pastMisses.length) * 100
    : null;

  const backtestTable = (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Kharif</th>
            <th className="num">Official (t/ha)</th>
            <th className="num">Forecast (t/ha)</th>
            <th className="num">80% range</th>
            <th className="num">Miss</th>
          </tr>
        </thead>
        <tbody>
          {[...rows].reverse().map((r) => (
            <tr key={r.year}>
              <td>
                {r.year}
                {r.qc_flag ? <span className="muted small"> · {r.qc_flag.replace("_", " ")}</span> : null}
              </td>
              <td className="num">{r.actual?.toFixed(2) ?? "–"}</td>
              <td className="num">{r.forecast?.toFixed(2) ?? "–"}</td>
              <td className="num">{r.lo80 != null && r.hi80 != null ? `${r.lo80.toFixed(2)}–${r.hi80.toFixed(2)}` : "–"}</td>
              <td className="num">{r.actual && r.forecast ? signedPct((r.forecast / r.actual - 1) * 100) : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const rainTable = (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Month</th>
            <th className="num">Rainfall (mm)</th>
            <th className="num">Normal (mm)</th>
            <th className="num">Of normal</th>
            <th className="num">Heavy-rain days</th>
          </tr>
        </thead>
        <tbody>
          {months.map((m) => (
            <tr key={m.month}>
              <td>{monthName(m.month)}</td>
              <td className="num">{m.prcp == null ? "–" : Math.round(m.prcp)}</td>
              <td className="num">{m.prcp_normal == null ? "–" : Math.round(m.prcp_normal)}</td>
              <td className="num">{m.prcp != null && m.prcp_normal ? `${Math.round((m.prcp / m.prcp_normal) * 100)}%` : "–"}</td>
              <td className="num">{m.heavy_days ?? "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const actualPts = rows.map((r) => ({ x: r.year, y: r.actual }));
  const forecastPts = [
    ...rows.map((r) => ({ x: r.year, y: r.forecast })),
    ...futureForLead.map((f) => ({ x: f.year, y: f.forecast_t_ha })),
  ];
  const bandPts = [
    ...rows.map((r) => ({ x: r.year, lo: r.lo80, hi: r.hi80 })),
    ...futureForLead.map((f) => ({ x: f.year, lo: f.lo80, hi: f.hi80 })),
  ];

  return (
    <>
      <div className="page-head">
        <div className="eyebrow">
          <Link to={`/?season=${year}&lead=${lead}`}>Outlook</Link> · District
        </div>
        <h1>{d.name}</h1>
        <p>
          {d.aliases.length ? `Also written ${d.aliases.join(", ")}. ` : ""}
          {d.coastal ? "Coastal district. " : ""}
          {d.kbk ? "Part of the drought-prone KBK region. " : ""}
          Latest official Kharif rice yield: {lastOfficial ? `${tHa(lastOfficial.yield_t_ha)} (${lastOfficial.year})` : "–"}.
        </p>
      </div>

      <div className="filters" role="group" aria-label="Forecast filters">
        <label className="field">
          Season
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {years.map((y) => (
              <option key={y} value={y}>
                Kharif {y}
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
      </div>

      <div className="grid-2">
        <section className="card" aria-labelledby="fc-h">
          <div className="hero">
            <span className="hero-label" id="fc-h">
              Kharif {year} forecast · issued after the {lead ? leadName(lead) : ""}
            </span>
            <span className="hero-value">
              {forecast ? forecast.forecast_t_ha.toFixed(2) : "–"}
              <small>t/ha rice</small>
            </span>
            {forecast && (
              <span className="hero-meta">
                80% range {forecast.lo80.toFixed(2)}–{forecast.hi80.toFixed(2)} · 90% range {forecast.lo90.toFixed(2)}–
                {forecast.hi90.toFixed(2)}
              </span>
            )}
          </div>
          {forecast && (
            <>
              <div className="tiles">
                <div className="tile">
                  <div className="tile-label">vs trend</div>
                  <div className="tile-value">{signedPct((forecast.forecast_t_ha / forecast.trend_t_ha - 1) * 100, 1)}</div>
                  <div className="tile-note">trend {forecast.trend_t_ha.toFixed(2)} t/ha</div>
                </div>
                <div className="tile">
                  <div className="tile-label">vs {lastOfficial?.year ?? "last"} official</div>
                  <div className="tile-value">
                    {lastOfficial?.yield_t_ha ? signedPct((forecast.forecast_t_ha / lastOfficial.yield_t_ha - 1) * 100, 0) : "–"}
                  </div>
                  <div className="tile-note">{tHa(lastOfficial?.yield_t_ha)}</div>
                </div>
                <div className="tile">
                  <div className="tile-label">As paddy, roughly</div>
                  <div className="tile-value">{paddyQuintalPerAcre(forecast.forecast_t_ha).toFixed(1)}</div>
                  <div className="tile-note">quintal per acre</div>
                </div>
              </div>
              <p className="small muted" style={{ marginBottom: 0 }}>
                Method: {MODEL_NAMES[forecast.model] ?? forecast.model}. Season rainfall so far{" "}
                {signedPct(forecast.season_rain_anomaly_pct)} vs normal.
                {mape != null ? ` Past forecasts at this issue date missed by ${mape.toFixed(0)}% on average (2015–2024).` : ""}
              </p>
              {storms.length > 0 && (
                <ul style={{ listStyle: "none", padding: 0, margin: "12px 0 0", display: "grid", gap: 6 }}>
                  {storms.map((c) => (
                    <li key={`${c.name}-${c.date}`}>
                      <span className="badge">
                        <WarningIcon />
                        <span>
                          <strong>{imdCategory(c.max_wind_kt)}:</strong>{" "}
                          {c.name === "Unnamed depression" ? "unnamed" : c.name}, {dateLabel(c.date)} - passed{" "}
                          {c.closest_km} km away, up to {c.max_wind_kt} knots
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
          {!forecast && <p className="muted">No forecast for this selection.</p>}
        </section>

        <section className="card" aria-labelledby="drv-h">
          <h2 id="drv-h">What moves this forecast</h2>
          {seasonal.length > 0 ? (
            <>
              <p className="sub">
                Change from the trend, in tonnes per hectare. Blue raises the forecast, red lowers it.
              </p>
              <DriverBars
                format={(v) => signed(v, 2)}
                bars={seasonal.map((dr) => ({
                  key: dr.feature,
                  label: dr.label,
                  value: driverValue(dr.value, dr.unit),
                  effect: dr.effect_t_ha,
                }))}
              />
            </>
          ) : (
            <div className="notice">
              <strong>Trend only at this issue date.</strong> In recent seasons, weather-adjusted forecasts issued at
              this point were not more accurate than the district's trend, so the system uses the trend alone. Other
              issue dates add rainfall, soil moisture, heat and cyclone information where that has proven useful - see{" "}
              <Link to="/methodology">How it works</Link>.
            </div>
          )}
        </section>
      </div>

      <div className="stack" style={{ marginTop: 16 }}>
        <Figure
          title="How these forecasts have done before"
          subtitle={`Each orange point was forecast after the ${lead ? leadName(lead) : ""} using only earlier seasons, then compared with the official yield.`}
          table={backtestTable}
          busy={bt.loading}
          footnote="Shaded: 80% range. The last points without an official value are the current forecasts."
        >
          <ul className="legend">
            <LegendLine color="var(--series-1)" label="Official yield" />
            <LegendLine color="var(--series-2)" label="Forecast (made before harvest)" />
            <LegendRect color="var(--band-2)" label="80% range" />
          </ul>
          <LineChart
            ariaLabel={`Official Kharif rice yields and forecasts for ${d.name}`}
            formatY={(v) => v.toFixed(1)}
            series={[
              { id: "actual", label: "Official", color: "var(--series-1)", dots: true, points: actualPts },
              { id: "forecast", label: "Forecast", color: "var(--series-2)", dots: true, points: forecastPts },
            ]}
            band={{ color: "var(--band-2)", points: bandPts }}
            tooltip={(x) => {
              const r = rows.find((row) => row.year === x);
              const f = futureForLead.find((ff) => ff.year === x);
              const fcVal = r?.forecast ?? f?.forecast_t_ha ?? null;
              const lo = r?.lo80 ?? f?.lo80 ?? null;
              const hi = r?.hi80 ?? f?.hi80 ?? null;
              return {
                title: `Kharif ${x}`,
                rows: [
                  { color: "var(--series-1)", label: "Official", value: r?.actual != null ? tHa(r.actual) : "not yet published" },
                  { color: "var(--series-2)", label: "Forecast", value: tHa(fcVal) },
                  { label: "80% range", value: lo != null && hi != null ? `${lo.toFixed(2)}–${hi.toFixed(2)}` : "–" },
                  ...(r?.actual && r.forecast ? [{ label: "Miss", value: signedPct((r.forecast / r.actual - 1) * 100) }] : []),
                ],
              };
            }}
          />
        </Figure>

        <div className="grid-2">
          <Figure
            title={`Rainfall this season - Kharif ${year}`}
            subtitle="Monthly rainfall against the 1991–2020 normal (NASA POWER). Only complete months are shown."
            table={rainTable}
            busy={season.loading}
          >
            <ul className="legend">
              <LegendRect color="var(--series-1)" label={`${year} rainfall`} />
              <LegendLine color="var(--ink-2)" label="1991–2020 normal" />
            </ul>
            {months.length ? <RainColumns months={months} /> : <p className="muted small">No complete months yet.</p>}
          </Figure>
          <LiveWeather slug={slug} />
        </div>

        {meta.data.features.market_prices && (
          <MarketPrices slug={slug} districtName={d.name} commodities={meta.data.commodities} />
        )}

        <CropExplorer slug={slug} crops={d.crops} />
      </div>
    </>
  );
}
