#!/usr/bin/env python3
"""Exporta al sitemap las fichas investigadas con más contenido, sin modificar Supabase.

Con SUPABASE_DB_URL o DATABASE_URL en el entorno:
  python3 db/export_sitemap_projects.py              # tope por defecto: 2000
  python3 db/export_sitemap_projects.py --limit 500  # o SITEMAP_PROJECT_LIMIT=500
Después, incluir el JSON generado en el despliegue de la web.

Criterio de calidad (sobre la última investigación de cada proyecto):
  - Se descartan las fichas casi plantilla: estado distinto de completa/parcial,
    resumen de menos de 800 caracteres o menos de 3 datos extra publicables.
  - calidad = min(datos, 10) + 2 * min(hallazgos, 5) + min(resumen_chars / 500, 6)
              + 5 si la investigación está completa  (máximo 31)
  - Orden: calidad DESC, investigado_at DESC, proyecto_id.
Solo entran proyectos visibles en homes.proyecto_actividad (política de publicación).

La consulta lee proyecto_investigacion completa (payload grande): tarda ~1 min en el
plan Micro, por eso se ejecuta offline y la web solo lee el JSON estático.
"""

import argparse
import json
import os
from datetime import timezone
from pathlib import Path

import psycopg2

from entity_reprocess import require_policy_active

DEFAULT_LIMIT = 2000

QUERY = """
WITH latest AS (
    SELECT DISTINCT ON (i.proyecto_id)
        i.id, i.proyecto_id, i.estado, i.investigado_at,
        length(btrim(coalesce(i.resumen, ''))) AS resumen_chars
    FROM homes.proyecto_investigacion i
    WHERE i.estado IN ('completa', 'parcial', 'pendiente_identificar')
    ORDER BY i.proyecto_id, i.investigado_at DESC, i.id DESC
),
datos AS (
    SELECT investigacion_id, count(*) AS n
    FROM homes.proyecto_dato_extra
    WHERE publicable
    GROUP BY investigacion_id
),
hallazgos AS (
    SELECT investigacion_id, count(*) AS n
    FROM homes.proyecto_hallazgo
    WHERE publicable
    GROUP BY investigacion_id
),
puntuadas AS (
    SELECT l.proyecto_id, l.investigado_at,
           least(coalesce(d.n, 0), 10)
           + 2 * least(coalesce(h.n, 0), 5)
           + least(l.resumen_chars / 500, 6)
           + CASE WHEN l.estado = 'completa' THEN 5 ELSE 0 END AS calidad
    FROM latest l
    LEFT JOIN datos d ON d.investigacion_id = l.id
    LEFT JOIN hallazgos h ON h.investigacion_id = l.id
    WHERE l.estado IN ('completa', 'parcial')
      AND l.resumen_chars >= 800
      AND coalesce(d.n, 0) >= 3
)
SELECT s.proyecto_id, s.investigado_at, s.calidad
FROM puntuadas s
-- proyecto_actividad aplica la política de publicación (entidades activas).
WHERE EXISTS (SELECT 1 FROM homes.proyecto_actividad p WHERE p.id = s.proyecto_id)
ORDER BY s.calidad DESC, s.investigado_at DESC, s.proyecto_id
LIMIT %(limit)s
"""


def parse_limit() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.environ.get("SITEMAP_PROJECT_LIMIT") or DEFAULT_LIMIT),
        help=f"Máximo de fichas a exportar (por defecto SITEMAP_PROJECT_LIMIT o {DEFAULT_LIMIT})",
    )
    limit = parser.parse_args().limit
    if limit < 0:
        raise SystemExit("--limit debe ser >= 0")
    return limit


def main() -> None:
    limit = parse_limit()
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Falta SUPABASE_DB_URL o DATABASE_URL")

    with psycopg2.connect(url, connect_timeout=15) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            require_policy_active(cur)
            # Solo para esta transacción de lectura; no cambia la configuración de la BD.
            cur.execute("SET LOCAL statement_timeout = '300s'")
            cur.execute(QUERY, {"limit": limit})
            projects = [
                {
                    "proyectoId": project_id,
                    "investigadoAt": researched_at.astimezone(timezone.utc)
                    .isoformat(timespec="milliseconds")
                    .replace("+00:00", "Z"),
                    "calidad": int(calidad),
                }
                for project_id, researched_at, calidad in cur.fetchall()
            ]

    target = Path(__file__).resolve().parents[1] / "web/public/data/sitemap-projects.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(projects, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    print(f"Sitemap: {len(projects)} fichas exportadas (tope {limit}) a {target.name}")


if __name__ == "__main__":
    main()
