import { api } from "../api";
import { ErrorNote, Loading } from "../components/State";
import { dateLabel, signed } from "../format";
import { useAsync } from "../hooks";
import type { Score } from "../types";

const LEADS = ["Jul", "Aug", "Sep", "Oct", "Nov"];
const pct = (v: number | undefined) => (v == null ? "–" : `${Math.round(v * 100)}%`);
const f3 = (v: number | undefined) => (v == null ? "–" : v.toFixed(3));

function SkillCell({ s }: { s?: Score }) {
  if (!s || s.skill_vs_trend == null) return <td className="num">–</td>;
  const k = s.skill_vs_trend;
  return (
    <td className="num">
      <span className={k > 0.005 ? "delta-up" : k < -0.005 ? "delta-down" : undefined}>{signed(k, 2)}</span>
    </td>
  );
}

export default function Methodology() {
  const card = useAsync((s) => api.modelCard(s), []);
  if (card.error) return <ErrorNote error={card.error} />;
  if (!card.data) return <Loading />;
  const c = card.data;
  const ch = c.chosen;
  const trend = c.candidates.find((x) => x.key === "trend|none|w=all");
  const trendLeads = LEADS.filter((l) => ch.current_choice[l]?.startsWith("trend"));
  const weatherLeads = LEADS.filter((l) => ch.current_choice[l] && !ch.current_choice[l].startsWith("trend"));
  const cov80 = LEADS.map((l) => ch.coverage[l]?.["80"]?.coverage).filter((v): v is number => v != null);
  const list = (ls: string[]) => ls.map((l) => `end of ${l}`).join(", ");

  return (
    <div className="prose" style={{ maxWidth: "none" }}>
      <div className="page-head">
        <div className="eyebrow">Model card</div>
        <h1>How KrushiMitra AI forecasts yields - and how well it does</h1>
        <p>
          Everything on this page is computed by the open pipeline in the repository and regenerated with each data
          refresh (last: {dateLabel(c.generated_at.slice(0, 10))}).
        </p>
      </div>

      <div className="grid-2">
        <section className="card">
          <h2>What is forecast</h2>
          <p>
            {c.target}. One number per district per Kharif season (autumn + winter rice, sown June–August, harvested
            October–December), for all {c.data.districts} districts of Odisha. Official figures exist for{" "}
            {c.data.first_season}–{c.data.last_season_with_official_yield} ({c.data.district_seasons} district-seasons).
          </p>
          <p>
            A forecast can be issued after the end of July, August, September, October or November. Each one uses only
            the weather, cyclone and yield information that existed on that date.
          </p>
        </section>
        <section className="card">
          <h2>Method in one paragraph</h2>
          <p>
            <strong>Forecast = district trend × (1 + weather adjustment).</strong> The trend - a robust (Huber) line
            through the district's past yields - captures the steady gains from seeds, irrigation and practice. The
            adjustment comes from this season's rainfall vs normal, soil moisture, heat, dry spells, heavy-rain days and
            cyclone winds near the district, learned jointly from all 30 districts. For each issue date the system uses
            whichever of four candidates (trend only, ridge regression, gradient boosting, or their average) had the
            smallest error over the previous {ch.window_seasons} seasons.
          </p>
        </section>
      </div>

      <section className="card" style={{ marginTop: 16 }}>
        <h2>How well it works (2015–2024, out of sample)</h2>
        <p className="sub">
          Every number comes from forecasts made as if in real time: each season was predicted by models trained only on
          earlier seasons. Skill compares squared error with the plain trend: +0.10 means 10% less error, negative means
          worse than the trend.
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Issued after</th>
                <th className="num">District RMSE (t/ha)</th>
                <th className="num">District MAPE</th>
                <th className="num">District skill</th>
                <th className="num">State RMSE (t/ha)</th>
                <th className="num">State skill</th>
                <th className="num">80% range coverage</th>
                <th className="num">90% range coverage</th>
                <th>Used for the current season</th>
              </tr>
            </thead>
            <tbody>
              {LEADS.map((l) => (
                <tr key={l}>
                  <td>End of {l}</td>
                  <td className="num">{f3(ch.test_by_lead[l]?.rmse)}</td>
                  <td className="num">{ch.test_by_lead[l] ? `${ch.test_by_lead[l].mape.toFixed(1)}%` : "–"}</td>
                  <SkillCell s={ch.test_by_lead[l]} />
                  <td className="num">{f3(ch.state_test_by_lead[l]?.rmse)}</td>
                  <SkillCell s={ch.state_test_by_lead[l]} />
                  <td className="num">{pct(ch.coverage[l]?.["80"]?.coverage)}</td>
                  <td className="num">{pct(ch.coverage[l]?.["90"]?.coverage)}</td>
                  <td className="small">{ch.current_choice[l]?.split("|")[0]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="small muted">
          Reference points (all issue dates): trend only RMSE {f3(trend?.test_rmse_mean)} t/ha · last season's yield{" "}
          {f3(c.baselines.persistence?.test.rmse)} · mean of the last five seasons {f3(c.baselines.mean5?.test.rmse)}.
        </p>
        <div className="notice" style={{ marginTop: 12 }}>
          <strong>Plain reading.</strong> Official district yields swing a lot from one season to the next, and much of
          that is not explained by weather.{" "}
          {trendLeads.length > 0 &&
            `For forecasts issued after the ${list(trendLeads)}, weather-adjusted models were not more accurate than the trend in recent seasons, so the system currently uses the trend alone. `}
          {weatherLeads.length > 0 &&
            `For the ${list(weatherLeads)}, the weather-aware model is in use because it beat the trend in recent seasons - see the skill columns above.`}
        </div>
      </section>

      <div className="grid-2" style={{ marginTop: 16 }}>
        <section className="card">
          <h2>Uncertainty</h2>
          <p>
            The ranges are split-conformal prediction intervals: the size of the misses this system made over the
            previous ten seasons at the same issue date sets the width. No assumption about the error's shape is needed,
            and the target season itself is never used. In 2015–2024 the 80% range contained the official figure{" "}
            {cov80.length ? `${pct(Math.min(...cov80))}–${pct(Math.max(...cov80))}` : "–"} of the time, depending on the
            issue date.
          </p>
        </section>
        <section className="card">
          <h2>Protocol disclosure</h2>
          <p>{c.protocol.disclosure}</p>
          <p className="small muted">
            The original protocol would have deployed <span className="kbd">{ch.fixed_split_protocol.would_have_chosen}</span>{" "}
            (test RMSE {f3(ch.fixed_split_protocol.test_rmse_mean)} t/ha). New seasons (2025 onwards) are the first truly
            independent test.
          </p>
        </section>
      </div>

      <section className="card" style={{ marginTop: 16 }}>
        <h2>Every candidate, including the ones not deployed</h2>
        <p className="sub">Mean RMSE across issue dates on the validation (2006–2014) and test (2015–2024) seasons.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Features</th>
                <th>Trend window</th>
                <th className="num">Validation RMSE</th>
                <th className="num">Test RMSE</th>
                <th>In selection pool</th>
              </tr>
            </thead>
            <tbody>
              {[...c.candidates]
                .sort((a, b) => a.test_rmse_mean - b.test_rmse_mean)
                .map((x) => (
                  <tr key={x.key}>
                    <td>{x.model}</td>
                    <td>{x.features}</td>
                    <td>{x.trend_window ? `${x.trend_window} seasons` : "all seasons"}</td>
                    <td className="num">{x.validation_rmse_mean.toFixed(3)}</td>
                    <td className="num">{x.test_rmse_mean.toFixed(3)}</td>
                    <td>{x.in_selection_pool ? "yes" : "no"}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid-2" style={{ marginTop: 16 }}>
        <section className="card">
          <h2>Data</h2>
          <ul>
            <li>
              District crop statistics - Directorate of Economics & Statistics (1997-98 to 2022-23) and UPAg (newest rice
              seasons), via the India Data Portal (ODC-By). On their shared years the two agree exactly.
            </li>
            <li>Daily weather - NASA POWER (MERRA-2 based, about 50 km grid) at each district centre, 1991 to {c.data.weather_through}.</li>
            <li>Cyclone tracks - NOAA IBTrACS v4 (IMD winds), North Indian Ocean.</li>
            <li>District boundaries - geoBoundaries (2021, ODbL).</li>
          </ul>
          <p className="small muted">
            No official value is dropped. {c.flagged_rows.length} district-seasons that look unusual compared with their
            neighbours (often real cyclones, droughts or pest outbreaks) are labelled; excluding them barely changes the
            scores.
          </p>
        </section>
        <section className="card">
          <h2>Limitations</h2>
          <ul>
            <li>Weather is sampled at one point per district on a coarse grid; local storms can be missed.</li>
            <li>No data on irrigation, varieties, sowing dates or input use, which drive much of the year-to-year change.</li>
            <li>Official district yields are themselves estimates with reporting noise.</li>
            <li>Yields are milled-rice equivalent; the paddy conversion shown is approximate (67% outturn).</li>
            <li>A statistical outlook, not farm-level advice. Consult the Department of Agriculture for decisions.</li>
          </ul>
        </section>
      </div>

      <section className="card" style={{ marginTop: 16 }}>
        <h2>Reproduce everything</h2>
        <p>
          <span className="kbd">python -m pipeline all</span> downloads every public input, rebuilds the data, re-runs
          all backtests and writes the files this site serves. See the repository README.
        </p>
      </section>
    </div>
  );
}
