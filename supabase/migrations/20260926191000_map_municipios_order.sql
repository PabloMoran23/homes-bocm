-- Lista del selector del mapa: más proyectos primero.

CREATE OR REPLACE FUNCTION homes.map_cm_municipios()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
SET statement_timeout = '8s'
AS $$
  SELECT jsonb_build_object(
    'municipios', COALESCE((
      SELECT jsonb_agg(to_jsonb(s) ORDER BY s.n DESC, s.nombre)
      FROM (
        SELECT
          slug,
          nombre,
          count(*)::int AS n,
          min(lng) FILTER (WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90) AS west,
          min(lat) FILTER (WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90) AS south,
          max(lng) FILTER (WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90) AS east,
          max(lat) FILTER (WHERE lng BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90) AS north
        FROM (
          SELECT m.slug, m.nombre, p.id,
            COALESCE(p.centroid_lng, p.lng) AS lng,
            COALESCE(p.centroid_lat, p.lat) AS lat
          FROM homes.municipio m
          JOIN homes.proyecto p ON p.municipio_slug = m.slug
          UNION ALL
          SELECT m.slug, m.nombre, p.id,
            COALESCE(p.centroid_lng, p.lng),
            COALESCE(p.centroid_lat, p.lat)
          FROM homes.municipio m
          JOIN homes.proyecto p
            ON p.municipio_slug IS NULL
           AND lower(btrim(COALESCE(p.municipio, p.bocm_municipio, ''))) = lower(btrim(m.nombre))
        ) u
        GROUP BY slug, nombre
      ) s
    ), '[]'::jsonb)
  );
$$;
