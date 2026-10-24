import type {
  BacktestRow,
  District,
  DistrictDetail,
  Forecast,
  ForecastMap,
  Lead,
  LiveDay,
  MarketRow,
  Meta,
  ModelCard,
  MonthWeather,
  YieldRow,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  return (await res.json()) as T;
}

const q = (params: Record<string, string | number | undefined>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined) s.set(k, String(v));
  return s.toString();
};

export const api = {
  meta: (signal?: AbortSignal) => get<Meta>("/api/meta", signal),
  districts: (signal?: AbortSignal) => get<District[]>("/api/districts", signal),
  geojson: (signal?: AbortSignal) => get<GeoJSON.FeatureCollection>("/api/districts/geojson", signal),
  district: (slug: string, signal?: AbortSignal) =>
    get<DistrictDetail>(`/api/districts/${encodeURIComponent(slug)}`, signal),
  yields: (slug: string, crop: string, season: string | undefined, signal?: AbortSignal) =>
    get<{ rows: YieldRow[]; seasons: string[] }>(
      `/api/districts/${encodeURIComponent(slug)}/yields?${q({ crop, season })}`,
      signal,
    ),
  seasonWeather: (slug: string, year: number, signal?: AbortSignal) =>
    get<{ months: MonthWeather[] }>(`/api/districts/${encodeURIComponent(slug)}/weather?${q({ year })}`, signal),
  forecastMap: (year: number, lead: Lead, signal?: AbortSignal) =>
    get<ForecastMap>(`/api/forecasts?${q({ year, lead })}`, signal),
  districtForecasts: (slug: string, signal?: AbortSignal) =>
    get<{ forecasts: Forecast[] }>(`/api/forecasts/${encodeURIComponent(slug)}`, signal),
  backtest: (slug: string, lead: Lead, signal?: AbortSignal) =>
    get<{ rows: BacktestRow[] }>(`/api/backtest/${encodeURIComponent(slug)}?${q({ lead })}`, signal),
  modelCard: (signal?: AbortSignal) => get<ModelCard>("/api/model-card", signal),
  liveWeather: (slug: string, signal?: AbortSignal) =>
    get<{ days: LiveDay[]; source: string; fetched_at: string }>(
      `/api/live/weather/${encodeURIComponent(slug)}`,
      signal,
    ),
  marketPrices: (slug: string, commodity: string, signal?: AbortSignal) =>
    get<{ commodity: string; district_markets: MarketRow[]; state_markets: MarketRow[]; source: string }>(
      `/api/live/market-prices/${encodeURIComponent(slug)}?${q({ commodity })}`,
      signal,
    ),
};
