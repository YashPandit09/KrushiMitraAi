import { useState } from "react";
import { api } from "../api";
import { integer } from "../format";
import { useAsync } from "../hooks";

export function MarketPrices({ slug, districtName, commodities }: { slug: string; districtName: string; commodities: Record<string, string> }) {
  const [commodity, setCommodity] = useState("paddy");
  const prices = useAsync((s) => api.marketPrices(slug, commodity, s), [slug, commodity]);
  const local = prices.data?.district_markets ?? [];
  const rows = local.length ? local : (prices.data?.state_markets ?? []);
  return (
    <section className="card" aria-labelledby="mandi-h">
      <div className="card-head">
        <div>
          <h2 id="mandi-h">Mandi prices today</h2>
          <p className="sub">
            {local.length ? `Markets in ${districtName}` : `No ${districtName} market reported today - showing Odisha markets`}
            , ₹ per quintal.
          </p>
        </div>
        <label className="field">
          Commodity
          <select value={commodity} onChange={(e) => setCommodity(e.target.value)}>
            {Object.entries(commodities).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
      </div>
      {prices.error ? (
        <p className="muted small">Prices are unavailable right now. {prices.error.message}.</p>
      ) : !prices.data ? (
        <p className="muted small">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted small">No arrivals reported today for this commodity.</p>
      ) : (
        <div className={`table-wrap${prices.loading ? " loading-fade" : ""}`}>
          <table>
            <thead>
              <tr>
                <th>Market</th>
                <th>Variety</th>
                <th className="num">Min</th>
                <th className="num">Modal</th>
                <th className="num">Max</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.market}-${r.variety}-${r.arrival_date}`}>
                  <td>
                    {r.market}
                    {local.length ? "" : <span className="muted small"> · {r.district}</span>}
                  </td>
                  <td>{r.variety}</td>
                  <td className="num">{integer(r.min_price)}</td>
                  <td className="num">
                    <strong>{integer(r.modal_price)}</strong>
                  </td>
                  <td className="num">{integer(r.max_price)}</td>
                  <td>{r.arrival_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted small" style={{ marginBottom: 0 }}>
        Source: Agmarknet via data.gov.in (Government Open Data License - India).
      </p>
    </section>
  );
}
