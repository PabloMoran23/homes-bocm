-- Existing outliers need replay through the normalizer. NOT VALID deliberately
-- keeps that historical evidence available, while enforcing all new/updated rows.
ALTER TABLE homes.proyecto ADD CONSTRAINT proyecto_coordinates_valid CHECK (
  (lat IS NULL AND lng IS NULL) OR
  (lat IS NOT NULL AND lng IS NOT NULL AND lat BETWEEN 27 AND 44 AND lng BETWEEN -19 AND 5)
) NOT VALID;
ALTER TABLE homes.licencia ADD CONSTRAINT licencia_coordinates_valid CHECK (
  (lat IS NULL AND lng IS NULL) OR
  (lat IS NOT NULL AND lng IS NOT NULL AND lat BETWEEN 27 AND 44 AND lng BETWEEN -19 AND 5)
) NOT VALID;
ALTER TABLE homes.proyecto ADD CONSTRAINT proyecto_derived_coordinates_valid CHECK (
  (centroid_lat IS NULL AND centroid_lng IS NULL) OR
  (centroid_lat IS NOT NULL AND centroid_lng IS NOT NULL AND centroid_lat BETWEEN 27 AND 44 AND centroid_lng BETWEEN -19 AND 5)
) NOT VALID;

-- Covers canonical SQL/legacy writers that do not call Python ingestion.
CREATE OR REPLACE FUNCTION homes.valid_wgs84_geometry(value jsonb)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
  geom public.geometry;
BEGIN
  IF value IS NULL THEN RETURN true; END IF;
  geom := public.ST_GeomFromGeoJSON(value::text);
  RETURN COALESCE(public.ST_SRID(geom) = 4326
    AND NOT public.ST_IsEmpty(geom)
    AND public.ST_IsValid(geom)
    AND public.ST_XMin(public.ST_Box3D(geom)) BETWEEN -19 AND 5
    AND public.ST_XMax(public.ST_Box3D(geom)) BETWEEN -19 AND 5
    AND public.ST_YMin(public.ST_Box3D(geom)) BETWEEN 27 AND 44
    AND public.ST_YMax(public.ST_Box3D(geom)) BETWEEN 27 AND 44, false);
EXCEPTION WHEN OTHERS THEN
  RETURN false;
END;
$$;
ALTER TABLE homes.proyecto ADD CONSTRAINT proyecto_geometry_valid CHECK (
  homes.valid_wgs84_geometry(geom_geojson)
  AND (NOT COALESCE(has_geometry, false) OR geom_geojson IS NOT NULL)
) NOT VALID;
