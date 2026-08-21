/** Teselas ráster de respaldo (el mapa vivo usa el estilo vectorial masterplan). */
export const HOMES_MAP_TILE_URL =
  "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";

export const HOMES_MAP_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> · <a href="https://openfreemap.org">OpenFreeMap</a>';

/** Leaflet.markercluster exige maxZoom en el mapa; las teselas ráster lo aportaban solas. */
export const HOMES_MAP_MIN_ZOOM = 5;
export const HOMES_MAP_MAX_ZOOM = 19;
