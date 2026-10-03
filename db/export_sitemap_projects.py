#!/usr/bin/env python3
"""Exporta proyectos investigados para el sitemap, sin modificar Supabase.

Con SUPABASE_DB_URL o DATABASE_URL en el entorno:
  python3 db/export_sitemap_projects.py
Después, incluir el JSON generado en el despliegue de la web.
"""

import json
import os
from pathlib import Path

import psycopg2


def main() -> None:
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Falta SUPABASE_DB_URL o DATABASE_URL")

    with psycopg2.connect(url, connect_timeout=15) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("""
                WITH latest AS (
                    SELECT DISTINCT ON (proyecto_id)
                        proyecto_id, investigado_at, resumen
                    FROM homes.proyecto_investigacion
                    ORDER BY proyecto_id, investigado_at DESC, id DESC
                )
                SELECT proyecto_id, investigado_at
                FROM latest
                WHERE NULLIF(btrim(resumen), '') IS NOT NULL
                ORDER BY proyecto_id
            """)
            projects = [
                {"proyectoId": project_id, "investigadoAt": researched_at.isoformat()}
                for project_id, researched_at in cur.fetchall()
            ]

    target = Path(__file__).resolve().parents[1] / "web/public/data/sitemap-projects.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(projects, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    print(f"Sitemap: {len(projects)} proyectos investigados exportados a {target.name}")


if __name__ == "__main__":
    main()
