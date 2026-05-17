-- RPC para la web (Vercel): boletín de zona y ficha ubicación.

CREATE OR REPLACE FUNCTION homes.haversine_m(
  lng1 double precision,
  lat1 double precision,
  lng2 double precision,
  lat2 double precision
) RETURNS double precision
LANGUAGE sql IMMUTABLE AS $$
  SELECT 6371000.0 * 2 * asin(sqrt(
    power(sin(radians(lat2 - lat1) / 2), 2)
    + cos(radians(lat1)) * cos(radians(lat2))
    * power(sin(radians(lng2 - lng1) / 2), 2)
  ));
$$;

CREATE OR REPLACE FUNCTION homes.get_ubicacion_ficha(p_ndp text)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = homes
AS $$
DECLARE
  inv homes.inmueble%ROWTYPE;
  result jsonb;
BEGIN
  SELECT * INTO inv FROM homes.inmueble WHERE ndp_edificio = p_ndp;
  IF NOT FOUND THEN
    RETURN NULL;
  END IF;

  SELECT jsonb_build_object(
    'inmueble', to_jsonb(inv),
    'licencias', COALESCE((
      SELECT jsonb_agg(to_jsonb(a) ORDER BY a.fecha_concesion DESC NULLS LAST, a.fecha_alta DESC)
      FROM (
        SELECT id, licencia_key, anio_dataset, fecha_alta, fecha_concesion,
               procedimiento, tipo_expediente, uso, interesado, objeto, unidad
        FROM homes.actuacion_edificacion
        WHERE inmueble_id = inv.id
        ORDER BY fecha_concesion DESC NULLS LAST, fecha_alta DESC
        LIMIT 200
      ) a
    ), '[]'::jsonb),
    'expedientesSigma', COALESCE((
      SELECT jsonb_agg(DISTINCT jsonb_build_object(
        'expediente_grupo', c.expediente_grupo,
        'exp_numero_original', c.exp_numero_original,
        'sigma_layer_kind', c.sigma_layer_kind,
        'denominacion', c.denominacion,
        'fase', c.fase,
        'enlace', c.enlace,
        'match_method', l.match_method,
        'match_score', l.match_score
      ))
      FROM homes.actuacion_edificacion ae
      JOIN homes.link_licencia_sigma l ON l.licencia_id = ae.id
      JOIN homes.sigma_catalog_expediente c ON c.expediente_grupo = l.expediente_grupo
      WHERE ae.inmueble_id = inv.id
    ), '[]'::jsonb),
    'tramitacionSigma', '{}'::jsonb,
    'stats', jsonb_build_object(
      'licenciasTotal', (SELECT COUNT(*) FROM homes.actuacion_edificacion WHERE inmueble_id = inv.id),
      'expedientesSigma', (
        SELECT COUNT(DISTINCT l.expediente_grupo)
        FROM homes.actuacion_edificacion ae
        JOIN homes.link_licencia_sigma l ON l.licencia_id = ae.id
        WHERE ae.inmueble_id = inv.id
      )
    )
  ) INTO result;

  RETURN result;
END;
$$;

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
      round(homes.haversine_m(p_lng, p_lat, ae.lng, ae.lat))::int AS "distanciaM",
      LEFT(COALESCE(ae.tipo_expediente, 'Licencia urbanística'), 120) AS titulo,
      LEFT(CONCAT_WS(' · ', ae.uso, ae.procedimiento, i.direccion), 200) AS detalle,
      i.ndp_edificio AS ndp,
      i.direccion,
      i.distrito,
      ae.lat,
      ae.lng,
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
    WHERE ae.lat IS NOT NULL AND ae.lng IS NOT NULL
      AND ae.lat BETWEEN min_lat AND max_lat
      AND ae.lng BETWEEN min_lng AND max_lng
      AND homes.haversine_m(p_lng, p_lat, ae.lng, ae.lat) <= radius_m
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

GRANT EXECUTE ON FUNCTION homes.get_ubicacion_ficha(text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION homes.boletin_area(double precision, double precision, double precision, integer) TO anon, authenticated, service_role;

-- Wrappers en public para PostgREST (schema homes debe estar expuesto en API)
CREATE OR REPLACE FUNCTION public.get_ubicacion_ficha(p_ndp text)
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path = homes
AS $$ SELECT homes.get_ubicacion_ficha(p_ndp); $$;

CREATE OR REPLACE FUNCTION public.boletin_area(
  p_lat double precision,
  p_lng double precision,
  p_radius_m double precision DEFAULT 600,
  p_months integer DEFAULT 24
) RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path = homes
AS $$ SELECT homes.boletin_area(p_lat, p_lng, p_radius_m, p_months); $$;

GRANT EXECUTE ON FUNCTION public.get_ubicacion_ficha(text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.boletin_area(double precision, double precision, double precision, integer) TO anon, authenticated, service_role;
