-- The municipality picker needs counts and bounds, never full project rows or geometries.
-- Let PostgreSQL answer its canonical-slug branch from a small covering index.
CREATE INDEX IF NOT EXISTS idx_homes_proyecto_map_municipios_cover
  ON homes.proyecto (municipio_slug)
  INCLUDE (centroid_lng, lng, centroid_lat, lat);
