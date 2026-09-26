#!/usr/bin/env python3
"""Inserta una investigación de proyecto (foto + datos + hallazgos).

Lee un JSON por stdin o por --file. Requiere SUPABASE_DB_URL o DATABASE_URL.
No imprime la URL. Escribe el id de la investigación en stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

BLOQUES = {
    "situacion",
    "programa",
    "cifras",
    "actores",
    "prensa",
    "cronologia",
}
CONFIANZA = {"alta", "media", "baja"}
FUENTE = {"oficial", "prensa", "web"}
ESTADO = {"completa", "parcial"}


def _db_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Falta SUPABASE_DB_URL o DATABASE_URL")
    return url


def _need(obj: dict[str, Any], key: str) -> Any:
    if key not in obj or obj[key] in (None, ""):
        raise SystemExit(f"Falta {key}")
    return obj[key]


def _load(path: str | None) -> dict[str, Any]:
    raw = PathRead(path) if path else sys.stdin.read()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit("El JSON raíz tiene que ser un objeto")
    return data


def PathRead(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def validate(data: dict[str, Any]) -> None:
    _need(data, "proyecto_id")
    estado = _need(data, "estado")
    if estado not in ESTADO:
        raise SystemExit(f"estado no válido: {estado}")
    resumen = _need(data, "resumen")
    if len(str(resumen).strip()) < 400:
        raise SystemExit("resumen demasiado corto: hace falta el relato completo")
    datos = data.get("datos") or []
    if not isinstance(datos, list) or not datos:
        raise SystemExit("datos tiene que ser una lista con al menos una fila")
    for i, row in enumerate(datos):
        if not isinstance(row, dict):
            raise SystemExit(f"datos[{i}] no es un objeto")
        bloque = _need(row, "bloque")
        if bloque not in BLOQUES:
            raise SystemExit(f"datos[{i}].bloque no válido: {bloque}")
        _need(row, "etiqueta")
        _need(row, "valor")
        confianza = _need(row, "confianza")
        if confianza not in CONFIANZA:
            raise SystemExit(f"datos[{i}].confianza no válida: {confianza}")
        fuente = _need(row, "fuente_tipo")
        if fuente not in FUENTE:
            raise SystemExit(f"datos[{i}].fuente_tipo no válido: {fuente}")
    for i, row in enumerate(data.get("hallazgos") or []):
        if not isinstance(row, dict):
            raise SystemExit(f"hallazgos[{i}] no es un objeto")
        _need(row, "titulo")
        _need(row, "cuerpo")


def save(data: dict[str, Any]) -> int:
    import psycopg2

    validate(data)
    conn = psycopg2.connect(_db_url())
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO homes.proyecto_investigacion
                  (proyecto_id, estado, resumen, huecos)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (
                    data["proyecto_id"],
                    data["estado"],
                    data["resumen"].strip(),
                    (data.get("huecos") or None),
                ),
            )
            inv_id = cur.fetchone()[0]
            for i, row in enumerate(data["datos"]):
                cur.execute(
                    """
                    INSERT INTO homes.proyecto_dato_extra (
                      investigacion_id, proyecto_id, bloque, clave, etiqueta, valor,
                      valor_numero, unidad, confianza, fuente_tipo, fuente_nombre,
                      fuente_url, fuente_fecha, extracto, destacado, publicable, orden
                    ) VALUES (
                      %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        inv_id,
                        data["proyecto_id"],
                        row["bloque"],
                        row.get("clave"),
                        row["etiqueta"],
                        row["valor"],
                        row.get("valor_numero"),
                        row.get("unidad"),
                        row["confianza"],
                        row["fuente_tipo"],
                        row.get("fuente_nombre"),
                        row.get("fuente_url"),
                        row.get("fuente_fecha"),
                        row.get("extracto"),
                        bool(row.get("destacado")),
                        row.get("publicable", True),
                        int(row.get("orden", i)),
                    ),
                )
            for i, row in enumerate(data.get("hallazgos") or []):
                cur.execute(
                    """
                    INSERT INTO homes.proyecto_hallazgo (
                      investigacion_id, proyecto_id, titulo, cuerpo,
                      fuente_nombre, fuente_url, fuente_fecha, nota,
                      publicable, orden
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        inv_id,
                        data["proyecto_id"],
                        row["titulo"],
                        row["cuerpo"],
                        row.get("fuente_nombre"),
                        row.get("fuente_url"),
                        row.get("fuente_fecha"),
                        row.get("nota"),
                        row.get("publicable", True),
                        int(row.get("orden", i)),
                    ),
                )
        conn.commit()
        return int(inv_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="JSON de la investigación. Si falta, se lee stdin.")
    args = parser.parse_args()
    inv_id = save(_load(args.file))
    print(inv_id)


if __name__ == "__main__":
    main()
