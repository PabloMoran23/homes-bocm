-- Mapa del boletín: coordenadas del edificio (como el mapa de exploración), no solo las de cada actuación.
CREATE OR REPLACE FUNCTION homes.boletin_area(
  p_lat double precision,
  p_lng double precision,
  p_radius_m double precision DEFAULT 600,
  p_months integer DEFAULT 24
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
DECLARE
  radius_m double precision := LEAST(GREATEST(COALESCE(p_radius_m, 600), 100), 3000);
  months_i integer := LEAST(GREATEST(COALESCE(p_months, 24), 6), 120);
  cutoff date := (CURRENT_DATE - (months_i * 30));
  center_row homes.inmueble%ROWTYPE;
  best_d double precision := 1e18;
  d double precision;
  licencias jsonb := '[]'::jsonb;
  sigma_events jsonb := '[]'::jsonb;
  timeline jsonb;
  lat_delta double precision := radius_m / 111000.0;
  lng_delta double precision := radius_m / (111000.0 * cos(radians(p_lat)));
  min_lat double precision := p_lat - lat_delta;
  max_lat double precision := p_lat + lat_delta;
  min_lng double precision := p_lng - lng_delta;
  max_lng double precision := p_lng + lng_delta;
BEGIN
  FOR center_row IN
    SELECT * FROM homes.inmueble
    WHERE lat IS NOT NULL AND lng IS NOT NULL
      AND lat BETWEEN min_lat AND max_lat
      AND lng BETWEEN min_lng AND max_lng
  LOOP
    d := homes.haversine_m(p_lng, p_lat, center_row.lng, center_row.lat);
    IF d <= radius_m AND d < best_d THEN
      best_d := d;
    END IF;
  END LOOP;

  SELECT COALESCE(jsonb_agg(row_to_json(t)::jsonb ORDER BY t.fecha_sort DESC), '[]'::jsonb)
  INTO licencias
  FROM (
    SELECT
      'licencia' AS tipo,
      COALESCE(ae.fecha_concesion, ae.fecha_alta) AS fecha,
      round(
        homes.haversine_m(
          p_lng, p_lat,
          COALESCE(i.lng, ae.lng),
          COALESCE(i.lat, ae.lat)
        )
      )::int AS "distanciaM",
      LEFT(COALESCE(ae.tipo_expediente, 'Licencia urbanística'), 120) AS titulo,
      LEFT(CONCAT_WS(' · ', ae.uso, ae.procedimiento, i.direccion), 200) AS detalle,
      i.ndp_edificio AS ndp,
      i.direccion,
      i.distrito,
      COALESCE(i.lat, ae.lat) AS lat,
      COALESCE(i.lng, ae.lng) AS lng,
      COALESCE(
        CASE WHEN ae.fecha_concesion ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(substring(ae.fecha_concesion from 1 for 10), 'DD/MM/YYYY')
             WHEN ae.fecha_concesion ~ '^\d{4}-\d{2}-\d{2}' THEN ae.fecha_concesion::date
             ELSE NULL END,
        CASE WHEN ae.fecha_alta ~ '^\d{2}/\d{2}/\d{4}' THEN to_date(substring(ae.fecha_alta from 1 for 10), 'DD/MM/YYYY')
             WHEN ae.fecha_alta ~ '^\d{4}-\d{2}-\d{2}' THEN ae.fecha_alta::date
             ELSE DATE '1900-01-01' END
      ) AS fecha_sort
    FROM homes.actuacion_edificacion ae
    LEFT JOIN homes.inmueble i ON i.id = ae.inmueble_id
    WHERE COALESCE(i.lat, ae.lat) IS NOT NULL
      AND COALESCE(i.lng, ae.lng) IS NOT NULL
      AND COALESCE(i.lat, ae.lat) BETWEEN min_lat AND max_lat
      AND COALESCE(i.lng, ae.lng) BETWEEN min_lng AND max_lng
      AND homes.haversine_m(
        p_lng, p_lat,
        COALESCE(i.lng, ae.lng),
        COALESCE(i.lat, ae.lat)
      ) <= radius_m
    LIMIT 40
  ) t
  WHERE t.fecha_sort IS NULL OR t.fecha_sort >= cutoff;

  SELECT COALESCE(jsonb_agg(row_to_json(s)::jsonb ORDER BY s.fecha_sort DESC), '[]'::jsonb)
  INTO sigma_events
  FROM (
    SELECT
      'sigma' AS tipo,
      COALESCE(c.fecha_aprob, '01/01/' || split_part(c.exp_numero_original, '/', 2)) AS fecha,
      round(homes.haversine_m(p_lng, p_lat, g.centroid_lng, g.centroid_lat))::int AS "distanciaM",
      LEFT(COALESCE(c.denominacion, g.expediente_grupo), 140) AS titulo,
      LEFT(CONCAT_WS(' · ', c.fase, 'A ' || round(homes.haversine_m(p_lng, p_lat, g.centroid_lng, g.centroid_lat))::text || ' m'), 200) AS detalle,
      g.expediente_grupo AS "expedienteGrupo",
      false AS "contienePunto",
      c.sigma_layer_kind AS "sigmaLayerKind",
      g.centroid_lat AS lat,
      g.centroid_lng AS lng,
      COALESCE(
        CASE WHEN c.fecha_aprob ~ '^\d{4}-\d{2}-\d{2}' THEN c.fecha_aprob::date ELSE NULL END,
        DATE '2000-01-01'
      ) AS fecha_sort
    FROM homes.sigma_ambito_geom g
    JOIN homes.sigma_catalog_expediente c ON c.expediente_grupo = g.expediente_grupo
    WHERE g.centroid_lat IS NOT NULL AND g.centroid_lng IS NOT NULL
      AND g.bbox_max_lng >= min_lng AND g.bbox_min_lng <= max_lng
      AND g.bbox_max_lat >= min_lat AND g.bbox_min_lat <= max_lat
      AND homes.haversine_m(p_lng, p_lat, g.centroid_lng, g.centroid_lat) <= radius_m
    LIMIT 40
  ) s
  WHERE s.fecha_sort >= cutoff;

  SELECT COALESCE(jsonb_agg(e ORDER BY (e->>'fecha') DESC NULLS LAST), '[]'::jsonb)
  INTO timeline
  FROM (
    SELECT e FROM jsonb_array_elements(licencias) e
    UNION ALL
    SELECT e FROM jsonb_array_elements(sigma_events) e
  ) q
  LIMIT 80;

  RETURN jsonb_build_object(
    'center', jsonb_build_object(
      'lat', p_lat,
      'lng', p_lng,
      'ndp', (SELECT ndp_edificio FROM homes.inmueble
              WHERE lat IS NOT NULL AND lng IS NOT NULL
              ORDER BY homes.haversine_m(p_lng, p_lat, lng, lat)
              LIMIT 1),
      'direccion', NULL,
      'distrito', NULL,
      'barrio', NULL
    ),
    'params', jsonb_build_object('radiusM', radius_m::int, 'months', months_i),
    'stats', jsonb_build_object(
      'licencias', jsonb_array_length(licencias),
      'expedientesSigma', jsonb_array_length(sigma_events),
      'eventos', jsonb_array_length(timeline)
    ),
    'licencias', licencias,
    'expedientesSigma', sigma_events,
    'timeline', timeline
  );
END;
$$;
