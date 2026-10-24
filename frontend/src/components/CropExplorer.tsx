import { useMemo, useState } from "react";
import { api } from "../api";
import { integer, num } from "../format";
import { useAsync } from "../hooks";
import { Figure } from "./Figure";
import { LineChart } from "./LineChart";

/** One point per calendar year; missing seasons become gaps rather than bridged lines. */
function withGaps(rows: { year: number; yield: number | null }[]) {
  if (!rows.length) return [];
  const byYear = new Map(rows.map((r) => [r.year, r.yield]));
  const years = rows.map((r) => r.year);
  const out = [];
  for (let y = Math.min(...years); y <= Math.max(...years); y++) out.push({ x: y, y: byYear.get(y) ?? null });
  return out;
}

/** Official yields for every crop and season the district reports. */
export function CropExplorer({ slug, crops }: { slug: string; crops: Record<string, string[]> }) {
  const cropNames = useMemo(() => Object.keys(crops).sort(), [crops]);
  const [crop, setCrop] = useState(cropNames.includes("Rice") ? "Rice" : (cropNames[0] ?? ""));
  const seasons = crops[crop] ?? [];
  const [seasonSel, setSeason] = useState<string>("");
  const season = seasons.includes(seasonSel) ? seasonSel : (seasons.includes("Total") ? "Total" : (seasons[0] ?? ""));
  const data = useAsync((s) => api.yields(slug, crop, season || undefined, s), [slug, crop, season]);
  const rows = data.data?.rows ?? [];
  const unit = rows.find((r) => r.yield_unit)?.yield_unit ?? "Tonnes/Hectare";
  const unitShort = unit.replace("Tonnes/Hectare", "t/ha").replace("Bales/Hectare", "bales/ha");

  const table = (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Season year</th>
            <th className="num">Area (ha)</th>
            <th className="num">Production</th>
            <th className="num">Yield ({unitShort})</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.year}-${r.source}`}>
              <td>{r.agri_year}</td>
              <td className="num">{integer(r.area_ha)}</td>
              <td className="num">
                {integer(r.production)} <span className="muted small">{r.production_unit.toLowerCase()}</span>
              </td>
              <td className="num">{num(r.yield, 2)}</td>
              <td>{r.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <Figure
      title="Official yields, any crop"
      subtitle="District statistics as published (DES, extended with UPAg for the newest rice seasons)."
      table={table}
      busy={data.loading}
      actions={
        <>
          <label className="field">
            Crop
            <select value={crop} onChange={(e) => setCrop(e.target.value)}>
              {cropNames.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Season
            <select value={season} onChange={(e) => setSeason(e.target.value)}>
              {seasons.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        </>
      }
    >
      {rows.length ? (
        <LineChart
          ariaLabel={`${crop} ${season} yield by year`}
          formatY={(v) => (v >= 10 ? v.toFixed(0) : v.toFixed(1))}
          series={[{ id: "y", label: `${crop}`, color: "var(--series-1)", dots: true, points: withGaps(rows) }]}
          tooltip={(x) => {
            const r = rows.find((row) => row.year === x);
            return {
              title: r?.agri_year ?? String(x),
              rows: [
                { label: "Yield", value: r?.yield == null ? "–" : `${r.yield.toFixed(2)} ${unitShort}` },
                { label: "Area", value: r?.area_ha == null ? "–" : `${integer(r.area_ha)} ha` },
              ],
            };
          }}
          height={240}
        />
      ) : (
        <p className="muted small">{data.loading ? "Loading…" : "No data for this selection."}</p>
      )}
    </Figure>
  );
}
