const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const LEAD_NAMES: Record<string, string> = {
  Jul: "end of July",
  Aug: "end of August",
  Sep: "end of September",
  Oct: "end of October",
  Nov: "end of November",
};

export const monthName = (m: number) => MONTHS[m - 1] ?? String(m);
export const leadName = (lead: string) => LEAD_NAMES[lead] ?? lead;

export function tHa(value: number | null | undefined, digits = 2): string {
  return value == null || Number.isNaN(value) ? "–" : `${value.toFixed(digits)} t/ha`;
}

export function num(value: number | null | undefined, digits = 2): string {
  return value == null || Number.isNaN(value) ? "–" : value.toFixed(digits);
}

/** Signed percentage, e.g. +4.1 % / −12 %. Uses a true minus sign. */
export function signedPct(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return "–";
  const rounded = Number(value.toFixed(digits));
  if (rounded === 0) return `±0%`;
  const sign = rounded > 0 ? "+" : "−";
  return `${sign}${Math.abs(rounded).toFixed(digits)}%`;
}

export function signed(value: number, digits = 2, unit = ""): string {
  const rounded = Number(value.toFixed(digits));
  if (rounded === 0) return `0${unit}`;
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded).toFixed(digits)}${unit}`;
}

export function integer(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? "–" : Math.round(value).toLocaleString("en-IN");
}

/** Milled rice (as published) to an approximate paddy yield in quintals per acre. */
export const RICE_TO_PADDY = 1 / 0.67; // standard Indian outturn ratio: 67 kg rice per 100 kg paddy
export function paddyQuintalPerAcre(riceTHa: number): number {
  return (riceTHa * RICE_TO_PADDY * 10) / 2.4711;
}

/** Human value for a forecast driver, by unit. */
export function driverValue(value: number, unit: string): string {
  switch (unit) {
    case "pct":
      return signedPct(value * 100);
    case "degC":
      return signed(value, 1, " °C");
    case "frac":
      return signed(value, 2);
    case "MJ":
      return signed(value, 1, " MJ/m²");
    case "mm":
      return `${Math.round(value)} mm`;
    case "days":
      return `${Math.round(value)} days`;
    case "kt":
      return value > 0 ? `${Math.round(value)} knots` : "none";
    case "flag":
      return value ? "yes" : "no";
    default:
      return String(Math.round(value * 100) / 100);
  }
}

export function dateLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function weekday(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric" });
}
