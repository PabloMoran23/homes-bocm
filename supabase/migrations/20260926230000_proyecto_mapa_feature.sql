-- Geometría de un proyecto para la ficha (el mapa de detalle no depende del GeoJSON estático).

CREATE OR REPLACE FUNCTION homes.proyecto_mapa_feature(p_id text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
AS $$
  SELECT jsonb_build_object(
    'type', 'FeatureCollection',
    'features', COALESCE(jsonb_agg(feature), '[]'::jsonb)
  )
  FROM (
    SELECT jsonb_build_object(
      'type', 'Feature',
      'geometry', homes._proyecto_map_geometry(
        p.geom_geojson,
        COALESCE(p.centroid_lng, p.lng),
        COALESCE(p.centroid_lat, p.lat),
        true,
        0.00015
      ),
      'properties', jsonb_build_object(
        'id', p.id,
        'titulo', COALESCE(NULLIF(btrim(p.denominacion), ''), p.id)
      )
    ) AS feature
    FROM homes.proyecto p
    WHERE (
      p.id = trim(p_id)
      OR p.expediente_grupo = trim(p_id)
      OR p.bocm_primary_id = trim(p_id)
    )
      AND p.has_geometry
      AND p.geom_geojson IS NOT NULL
      AND jsonb_typeof(p.geom_geojson) = 'object'
      AND COALESCE(p.geom_geojson->>'type', '') IN ('Polygon', 'MultiPolygon')
    ORDER BY COALESCE(p.area_approx_m2, 0) DESC
    LIMIT 1
  ) s
  WHERE jsonb_typeof(feature->'geometry') = 'object';
$$;

CREATE OR REPLACE FUNCTION public.proyecto_mapa_feature(p_id text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
AS $$ SELECT homes.proyecto_mapa_feature(p_id); $$;

GRANT EXECUTE ON FUNCTION homes.proyecto_mapa_feature(text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.proyecto_mapa_feature(text) TO anon, authenticated, service_role;
