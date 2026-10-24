export type Lead = "Jul" | "Aug" | "Sep" | "Oct" | "Nov";

export interface District {
  slug: string;
  name: string;
  aliases: string[];
  lon: number;
  lat: number;
  coastal: boolean;
  kbk: boolean;
}

export interface Meta {
  version: string;
  generated_at: string;
  weather_through: string;
  last_season_with_official_yield: number;
  model: string;
  target: string;
  leads: Lead[];
  forecast_years: Record<string, Lead[]>;
  features: { market_prices: boolean; live_weather: boolean };
  commodities: Record<string, string>;
}

export interface Driver {
  feature: string;
  label: string;
  unit: string;
  value: number;
  effect_t_ha: number;
}

export interface CycloneEvent {
  name: string;
  date: string;
  closest_km: number;
  max_wind_kt: number;
}

export interface Forecast {
  district_slug: string;
  year: number;
  lead: Lead;
  model: string;
  issued_after: string;
  forecast_t_ha: number;
  trend_t_ha: number;
  anomaly_pct: number;
  baseline_anomaly_pct: number;
  lo80: number;
  hi80: number;
  lo90: number;
  hi90: number;
  season_rain_anomaly_pct: number;
  cyclones?: CycloneEvent[];
  drivers?: Driver[];
}

export interface ForecastMap {
  year: number;
  lead: Lead;
  state: { forecast_t_ha: number; trend_t_ha: number; lo80: number; hi80: number; lo90: number; hi90: number };
  districts: Forecast[];
}

export interface KharifRow {
  year: number;
  yield_t_ha: number | null;
  area_ha: number | null;
  production_t: number | null;
  source: string;
  qc_flag: string | null;
}

export interface DistrictDetail extends District {
  kharif_rice: KharifRow[];
  crops: Record<string, string[]>;
}

export interface BacktestRow {
  year: number;
  actual: number | null;
  forecast: number | null;
  trend: number | null;
  lo80: number | null;
  hi80: number | null;
  lo90: number | null;
  hi90: number | null;
  persistence: number | null;
  mean5: number | null;
  qc_flag: string | null;
}

export interface YieldRow {
  year: number;
  agri_year: string;
  crop: string;
  season: string;
  area_ha: number | null;
  production: number | null;
  production_unit: string;
  yield: number | null;
  yield_unit: string;
  source: string;
}

export interface MonthWeather {
  year: number;
  month: number;
  prcp: number | null;
  prcp_normal: number | null;
  tmax: number | null;
  tmax_normal: number | null;
  tmin: number | null;
  tmin_normal: number | null;
  gwet: number | null;
  heavy_days: number | null;
  wet_days: number | null;
}

export interface LiveDay {
  date: string;
  rain_mm: number | null;
  rain_probability_pct: number | null;
  tmax_c: number | null;
  tmin_c: number | null;
  wind_max_kmh: number | null;
}

export interface MarketRow {
  market: string;
  district: string;
  variety: string;
  arrival_date: string;
  min_price: number;
  max_price: number;
  modal_price: number;
}

export interface Score {
  n: number;
  rmse: number;
  mae: number;
  mape: number;
  bias: number;
  r2: number;
  skill_vs_trend?: number;
}

export interface CandidateResult {
  key: string;
  model: string;
  features: string;
  trend_window: number | null;
  validation_rmse_mean: number;
  test_rmse_mean: number;
  in_selection_pool: boolean;
  by_lead: Record<string, { validation: Score; test: Score; state_validation: Score; state_test: Score }>;
}

export interface ModelCard {
  generated_at: string;
  target: string;
  data: {
    districts: number;
    first_season: number;
    last_season_with_official_yield: number;
    district_seasons: number;
    weather_through: string;
  };
  flagged_rows: { district_slug: string; year: number; yield_t_ha: number; qc_flag: string }[];
  protocol: {
    evaluation: string;
    first_backtest_season: number;
    validation_seasons: number[];
    test_seasons: number[];
    selection: string;
    intervals: string;
    leads: Record<string, string>;
    disclosure: string;
  };
  candidates: CandidateResult[];
  baselines: Record<string, { validation: Score; test: Score }>;
  chosen: {
    key: string;
    description: string;
    pool: string[];
    window_seasons: number;
    current_choice: Record<string, string>;
    selection_history: Record<string, Record<string, string>>;
    coverage: Record<string, Record<string, { coverage: number; mean_width_pct: number }>>;
    test_by_lead: Record<string, Score>;
    state_test_by_lead: Record<string, Score>;
    sensitivity_excluding_flagged_rows: Record<string, Score>;
    test_rmse_by_district: Record<string, number>;
    feature_importance: Record<string, { feature: string; label: string; unit: string; mean_abs_anomaly_pct: number }[]>;
    fixed_split_protocol: { would_have_chosen: string; validation_rmse_mean: number; test_rmse_mean: number; note: string };
  };
}
