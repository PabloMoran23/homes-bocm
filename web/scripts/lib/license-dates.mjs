/** Temporal contract v1: no Date.parse, two-digit years, or invented precision. */
export const DATE_RULE_VERSION = "license-dates-v1";
export function parseLicenseDate(raw, { asOf = new Date().toISOString().slice(0, 10), meaning = "observed" } = {}) {
  const result = { raw: raw ?? null, value: null, precision: null, reason: null };
  const text = String(raw ?? "").trim();
  if (!text) return result;
  const iso = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/.exec(text);
  const dmy = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(text);
  let year, month, day, precision;
  if (iso) {
    year = Number(iso[1]); month = Number(iso[2] || 1); day = Number(iso[3] || 1);
    precision = iso[3] ? "day" : iso[2] ? "month" : "year";
  } else if (dmy) {
    year = Number(dmy[3]); month = Number(dmy[2]); day = Number(dmy[1]); precision = "day";
  } else return { ...result, reason: "unsupported_or_ambiguous_format" };
  if (year < 1900 || year > 2100) return { ...result, reason: "year_out_of_range" };
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (month < 1 || month > 12 || day < 1 || day > days[month - 1]) return { ...result, reason: "invalid_calendar_date" };
  const full = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  if (meaning !== "planned" && full > asOf) return { ...result, reason: "future_observed_date" };
  return { ...result, value: full.slice(0, precision === "day" ? 10 : precision === "month" ? 7 : 4), precision };
}
export function licenseTemporal(row, options) {
  // Always replay original evidence when a previous build normalized/quarantined it.
  const aliases = { fecha_concesion: "fechaConcesion", fecha_alta: "fechaAlta", anio_dataset: "anioDataset" };
  row = { ...row, ...Object.fromEntries(Object.entries(row.temporal?.fields || {}).map(([key, value]) => [aliases[key] || key, value.raw])) };
  const fields = Object.fromEntries(["fechaConcesion", "fechaAlta", "anioDataset"].map(key => [key, parseLicenseDate(row[key], options)]));
  const primary = row.fechaConcesion ? fields.fechaConcesion : fields.fechaAlta;
  const value = primary.value || (!primary.reason ? fields.anioDataset.value : null);
  return { ruleVersion: DATE_RULE_VERSION, fields, year: value ? Number(value.slice(0, 4)) : null,
    month: primary.value && primary.precision !== "year" ? primary.value.slice(0, 7) : null,
    quarantine: Object.entries(fields).filter(([, v]) => v.reason).map(([field, v]) => ({ field, ...v })) };
}
export function parseMonthKey(concesion, alta, options) {
  return licenseTemporal({ fechaConcesion: concesion, fechaAlta: alta }, options).month;
}
