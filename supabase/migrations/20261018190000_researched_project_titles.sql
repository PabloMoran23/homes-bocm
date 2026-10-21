-- Expose the identified subject title in the existing public reader.
-- Original project names and source documents remain unchanged.
CREATE OR REPLACE FUNCTION homes.get_proyecto_info_extra(p_id text)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = homes, public
AS $$
  WITH match AS (
    SELECT p.id
    FROM homes.proyecto p
    WHERE p.id = trim(p_id)
       OR p.expediente_grupo = trim(p_id)
       OR p.bocm_primary_id = trim(p_id)
       OR p.id = 'bocm:' || trim(p_id)
    LIMIT 1
  ),
  inv AS (
    SELECT i.*
    FROM homes.proyecto_investigacion i
    JOIN match m ON m.id = i.proyecto_id
    ORDER BY i.investigado_at DESC, i.id DESC
    LIMIT 1
  )
  SELECT jsonb_build_object(
    'id', i.id,
    'proyectoId', i.proyecto_id,
    'investigadoAt', i.investigado_at,
    'estado', i.estado,
    'resumen', i.resumen,
    'huecos', i.huecos,
    'tipoEntrada', i.tipo_entrada,
    'asuntoId', i.asunto_id,
    'titulo', (SELECT a.titulo FROM homes.asunto a WHERE a.id=i.asunto_id),
    'municipio', (SELECT a.municipio FROM homes.asunto a WHERE a.id=i.asunto_id),
    'padreId', (SELECT a.padre_id FROM homes.asunto a WHERE a.id=i.asunto_id),
    'razonPendiente', i.razon_pendiente,
    'datos', COALESCE((
      SELECT jsonb_agg(
        jsonb_build_object(
          'bloque', d.bloque,
          'clave', d.clave,
          'etiqueta', d.etiqueta,
          'valor', d.valor,
          'valorNumero', d.valor_numero,
          'unidad', d.unidad,
          'confianza', d.confianza,
          'fuenteTipo', d.fuente_tipo,
          'fuenteNombre', d.fuente_nombre,
          'fuenteUrl', d.fuente_url,
          'fuenteFecha', d.fuente_fecha,
          'extracto', d.extracto,
          'destacado', d.destacado,
          'orden', d.orden
        )
        ORDER BY d.orden, d.id
      )
      FROM homes.proyecto_dato_extra d
      WHERE d.investigacion_id = i.id
        AND d.publicable
    ), '[]'::jsonb),
    'hallazgos', COALESCE((
      SELECT jsonb_agg(
        jsonb_build_object(
          'titulo', h.titulo,
          'cuerpo', h.cuerpo,
          'fuenteNombre', h.fuente_nombre,
          'fuenteUrl', h.fuente_url,
          'fuenteFecha', h.fuente_fecha,
          'orden', h.orden
        )
        ORDER BY h.orden, h.id
      )
      FROM homes.proyecto_hallazgo h
      WHERE h.investigacion_id = i.id
        AND h.publicable
    ), '[]'::jsonb)
  )
  FROM inv i;
$$;

