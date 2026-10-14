-- Quarantine invalid legacy fields before enforcing the same invariant for new
-- writes. The snapshot is evidence, not a CRS guess or a geographic correction.
-- The explicit transaction and write locks leave no gap between quarantine and
-- constraints. Metadata-only H01/H02 updates can then replay these rows safely.
BEGIN;
LOCK TABLE homes.proyecto, homes.licencia IN SHARE ROW EXCLUSIVE MODE;

CREATE OR REPLACE FUNCTION homes.valid_wgs84_coordinates(lat double precision, lng double precision)
RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
  SELECT (lat IS NULL AND lng IS NULL) OR
    (lat IS NOT NULL AND lng IS NOT NULL AND lat BETWEEN 27 AND 44 AND lng BETWEEN -19 AND 5)
$$;

CREATE OR REPLACE FUNCTION homes.valid_wgs84_bbox(x0 double precision, y0 double precision,
                                                x1 double precision, y1 double precision)
RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
  SELECT (x0 IS NULL AND y0 IS NULL AND x1 IS NULL AND y1 IS NULL) OR
    (x0 IS NOT NULL AND y0 IS NOT NULL AND x1 IS NOT NULL AND y1 IS NOT NULL
     AND x0 BETWEEN -19 AND 5 AND x1 BETWEEN -19 AND 5
     AND y0 BETWEEN 27 AND 44 AND y1 BETWEEN 27 AND 44 AND x0 <= x1 AND y0 <= y1)
$$;

CREATE OR REPLACE FUNCTION homes.valid_wgs84_geometry(value jsonb)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
  geom public.geometry;
BEGIN
  IF value IS NULL THEN RETURN true; END IF;
  -- PostGIS accepts numeric strings, including "NaN"/"Infinity", as ordinates.
  -- GeoJSON requires numeric leaves; reject those values before parsing.
  IF jsonb_path_exists(value, '$.coordinates.** ? (@.type() != "array" && @.type() != "number")') THEN
    RETURN false;
  END IF;
  -- Only data parse failures are quarantined. UndefinedFunction and validation
  -- implementation errors must escape, failing/rolling back the migration.
  BEGIN
    geom := public.ST_GeomFromGeoJSON(value::text);
  EXCEPTION WHEN invalid_parameter_value OR invalid_text_representation
                 OR numeric_value_out_of_range OR SQLSTATE 'XX000' THEN
    RETURN false;
  END;
  RETURN COALESCE(public.ST_SRID(geom) = 4326
    AND NOT public.ST_IsEmpty(geom)
    AND public.ST_IsValid(geom)
    AND NOT EXISTS (
      SELECT 1 FROM public.ST_DumpPoints(geom) AS point
      WHERE public.ST_Z(point.geom) IN ('NaN'::double precision, 'Infinity'::double precision, '-Infinity'::double precision)
    )
    AND public.ST_XMin(public.Box3D(geom)) BETWEEN -19 AND 5
    AND public.ST_XMax(public.Box3D(geom)) BETWEEN -19 AND 5
    AND public.ST_YMin(public.Box3D(geom)) BETWEEN 27 AND 44
    AND public.ST_YMax(public.Box3D(geom)) BETWEEN 27 AND 44, false);
END;
$$;

-- Fail fast even on an empty database if PostGIS validation is unavailable.
DO $$ BEGIN
  IF NOT homes.valid_wgs84_geometry('{"type":"Point","coordinates":[-3.8,40.2]}'::jsonb) THEN
    RAISE EXCEPTION 'PostGIS WGS84 validation self-check failed';
  END IF;
END $$;

-- Replace the unpublished CHECK NOT VALID version safely if already installed
-- in a staging environment. These names belong exclusively to this control.
ALTER TABLE homes.proyecto DROP CONSTRAINT IF EXISTS proyecto_coordinates_valid;
ALTER TABLE homes.proyecto DROP CONSTRAINT IF EXISTS proyecto_derived_coordinates_valid;
ALTER TABLE homes.proyecto DROP CONSTRAINT IF EXISTS proyecto_geometry_valid;
ALTER TABLE homes.proyecto DROP CONSTRAINT IF EXISTS proyecto_bbox_valid;
ALTER TABLE homes.licencia DROP CONSTRAINT IF EXISTS licencia_coordinates_valid;

UPDATE homes.proyecto SET
  raw_features_json = COALESCE(raw_features_json, '{}'::jsonb) || jsonb_build_object(
    '_geography_quarantine', jsonb_build_object(
      'rule_version', 'h03-sql-v2', 'status', 'quarantined',
      'reason', 'invalid_canonical_geography', 'source_crs', NULL,
      'action', 'recover_declared_source_and_replay',
      'original', jsonb_build_object(
        'lat', lat, 'lng', lng, 'centroid_lat', centroid_lat, 'centroid_lng', centroid_lng,
        'geom_geojson', geom_geojson, 'has_geometry', has_geometry, 'coord_source', coord_source,
        'bbox_min_lng', bbox_min_lng, 'bbox_min_lat', bbox_min_lat,
        'bbox_max_lng', bbox_max_lng, 'bbox_max_lat', bbox_max_lat))),
  lat = NULL, lng = NULL, centroid_lat = NULL, centroid_lng = NULL,
  geom_geojson = NULL, has_geometry = false, coord_source = NULL,
  bbox_min_lng = NULL, bbox_min_lat = NULL, bbox_max_lng = NULL, bbox_max_lat = NULL
WHERE NOT homes.valid_wgs84_coordinates(lat, lng)
   OR NOT homes.valid_wgs84_coordinates(centroid_lat, centroid_lng)
   OR NOT homes.valid_wgs84_bbox(bbox_min_lng, bbox_min_lat, bbox_max_lng, bbox_max_lat)
   OR NOT homes.valid_wgs84_geometry(geom_geojson)
   OR (COALESCE(has_geometry, false) AND geom_geojson IS NULL);

UPDATE homes.licencia SET
  raw_json = COALESCE(raw_json, '{}'::jsonb) || jsonb_build_object(
    '_geography_quarantine', jsonb_build_object(
      'rule_version', 'h03-sql-v2', 'status', 'quarantined',
      'reason', 'invalid_canonical_coordinates', 'source_crs', NULL,
      'action', 'recover_declared_source_and_replay',
      'original', jsonb_build_object('lat', lat, 'lng', lng))),
  lat = NULL, lng = NULL
WHERE NOT homes.valid_wgs84_coordinates(lat, lng);

-- These CHECKs are fully validated: legacy outliers are now unlocated and their
-- originals are retained in raw. New invalid geography cannot enter by SQL.
ALTER TABLE homes.proyecto ADD CONSTRAINT proyecto_coordinates_valid
  CHECK (homes.valid_wgs84_coordinates(lat, lng));
ALTER TABLE homes.licencia ADD CONSTRAINT licencia_coordinates_valid
  CHECK (homes.valid_wgs84_coordinates(lat, lng));
ALTER TABLE homes.proyecto ADD CONSTRAINT proyecto_derived_coordinates_valid
  CHECK (homes.valid_wgs84_coordinates(centroid_lat, centroid_lng));
ALTER TABLE homes.proyecto ADD CONSTRAINT proyecto_bbox_valid
  CHECK (homes.valid_wgs84_bbox(bbox_min_lng, bbox_min_lat, bbox_max_lng, bbox_max_lat));
ALTER TABLE homes.proyecto ADD CONSTRAINT proyecto_geometry_valid CHECK (
  homes.valid_wgs84_geometry(geom_geojson)
  AND (NOT COALESCE(has_geometry, false) OR geom_geojson IS NOT NULL)
);
COMMIT;
