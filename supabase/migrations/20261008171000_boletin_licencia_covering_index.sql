-- Licencia contains large source payloads. Read the bulletin fields from a
-- compact covering index rather than visiting hundreds of scattered heap pages.
-- Run outside a transaction: concurrent builds keep imports and queries available.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_homes_licencia_boletin_cover
  ON homes.licencia (inmueble_id)
  INCLUDE (fecha_concesion, fecha_alta, tipo_expediente, uso, procedimiento)
  WHERE inmueble_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_homes_licencia_orphan_coords
  ON homes.licencia (lat, lng)
  WHERE inmueble_id IS NULL AND lat IS NOT NULL AND lng IS NOT NULL;
