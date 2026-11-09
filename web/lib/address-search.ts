export type AddressLocation = {
  lat: number;
  lng: number;
  label: string;
  municipality?: string;
};

export function isMadridLocation(value: { lat: number; lng: number }) {
  return Number.isFinite(value.lat) && Number.isFinite(value.lng)
    && value.lat >= 40.31 && value.lat <= 40.65
    && value.lng >= -3.9 && value.lng <= -3.5;
}

export function isSpainLocation(value: { lat: number; lng: number }) {
  // Mainland, Balearic and Canary Islands, Ceuta and Melilla.
  return Number.isFinite(value.lat) && Number.isFinite(value.lng)
    && value.lat >= 27 && value.lat <= 44
    && value.lng >= -19 && value.lng <= 5;
}
