-- Carta de presentación: los de más viviendas, solo Madrid capital.

CREATE OR REPLACE FUNCTION homes.list_proyectos_investigados()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
AS $$
  WITH latest AS (
    SELECT DISTINCT ON (i.proyecto_id) i.*
    FROM homes.proyecto_investigacion i
    ORDER BY i.proyecto_id, i.investigado_at DESC
  ),
  cards AS (
    SELECT
      l.proyecto_id,
      l.estado,
      l.resumen,
      p.municipio,
      COALESCE(NULLIF(btrim(p.denominacion), ''), NULLIF(btrim(p.bocm_title), ''), l.proyecto_id) AS denominacion,
      (
        SELECT NULLIF(btrim(d.valor), '')
        FROM homes.proyecto_dato_extra d
        WHERE d.investigacion_id = l.id
          AND d.clave = 'nombre_publico'
          AND d.publicable
        ORDER BY d.orden, d.id
        LIMIT 1
      ) AS nombre_publico,
      (
        SELECT d.valor_numero
        FROM homes.proyecto_dato_extra d
        WHERE d.investigacion_id = l.id
          AND d.clave = 'num_viviendas'
          AND d.publicable
          AND d.valor_numero IS NOT NULL
        ORDER BY CASE d.confianza WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, d.orden, d.id
        LIMIT 1
      ) AS viviendas,
      (
        SELECT d.valor_numero
        FROM homes.proyecto_dato_extra d
        WHERE d.investigacion_id = l.id
          AND d.clave = 'sup_total_m2'
          AND d.publicable
          AND d.valor_numero IS NOT NULL
        ORDER BY CASE d.confianza WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, d.orden, d.id
        LIMIT 1
      ) AS superficie,
      (
        SELECT NULLIF(btrim(d.valor), '')
        FROM homes.proyecto_dato_extra d
        WHERE d.investigacion_id = l.id
          AND d.clave = 'promotor'
          AND d.publicable
        ORDER BY d.orden, d.id
        LIMIT 1
      ) AS promotor
    FROM latest l
    LEFT JOIN homes.proyecto p ON p.id = l.proyecto_id
  ),
  top AS (
    SELECT *
    FROM cards
    WHERE viviendas IS NOT NULL
      AND municipio ILIKE 'madrid'
    ORDER BY viviendas DESC NULLS LAST, superficie DESC NULLS LAST
    LIMIT 12
  )
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'proyectoId', c.proyecto_id,
        'municipio', c.municipio,
        'denominacion', c.denominacion,
        'nombrePublico', c.nombre_publico,
        'resumen', left(c.resumen, 480),
        'estado', c.estado,
        'viviendas', c.viviendas,
        'superficieM2', c.superficie,
        'promotor', c.promotor
      )
      ORDER BY c.viviendas DESC NULLS LAST, c.superficie DESC NULLS LAST
    ),
    '[]'::jsonb
  )
  FROM top c;
$$;

CREATE OR REPLACE FUNCTION public.list_proyectos_investigados()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
AS $$
  SELECT homes.list_proyectos_investigados();
$$;
