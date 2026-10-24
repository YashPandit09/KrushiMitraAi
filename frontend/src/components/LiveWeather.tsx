import { api } from "../api";
import { weekday } from "../format";
import { useAsync } from "../hooks";

export function LiveWeather({ slug }: { slug: string }) {
  const live = useAsync((s) => api.liveWeather(slug, s), [slug]);
  return (
    <section className="card" aria-labelledby="live-h">
      <h2 id="live-h">Next 7 days</h2>
      <p className="sub">Live forecast at the district centre. Not used by the yield model.</p>
      {live.error ? (
        <p className="muted small">Live weather is unavailable right now. {live.error.message}.</p>
      ) : !live.data ? (
        <p className="muted small">Loading…</p>
      ) : (
        <>
          <div className="days">
            {live.data.days.map((d) => (
              <div className="day" key={d.date}>
                <div className="d">{weekday(d.date)}</div>
                <div className="r">{d.rain_mm == null ? "–" : `${d.rain_mm.toFixed(d.rain_mm < 10 ? 1 : 0)} mm`}</div>
                <div className="muted small">
                  {d.rain_probability_pct == null ? "" : `${d.rain_probability_pct}% chance`}
                </div>
                <div className="small">
                  {d.tmax_c == null ? "–" : Math.round(d.tmax_c)}° / {d.tmin_c == null ? "–" : Math.round(d.tmin_c)}°
                </div>
              </div>
            ))}
          </div>
          <p className="muted small" style={{ marginBottom: 0 }}>
            Weather data by <a href="https://open-meteo.com/">Open-Meteo.com</a> (CC BY 4.0).
          </p>
        </>
      )}
    </section>
  );
}
