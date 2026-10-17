#!/usr/bin/env python3
"""Inserta una investigación de proyecto (foto + datos + hallazgos).

Lee un JSON por stdin o por --file. Requiere SUPABASE_DB_URL o DATABASE_URL.
Requiere --owner y --token de db/research_lease.py. Reintentos idénticos son idempotentes.
No imprime la URL. Escribe el id de la investigación en stdout.
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import date
from urllib.parse import urlparse
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
    if not any(r.get("bloque") == "situacion" and r.get("clave") == "nombre_publico"
               and r.get("destacado") is True for r in datos if isinstance(r, dict)):
        raise SystemExit("Falta nombre_publico destacado")
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
        _need(row, "fuente_nombre")
        url = urlparse(_need(row, "fuente_url"))
        if url.scheme not in ("https", "http") or not url.netloc:
            raise SystemExit(f"datos[{i}].fuente_url no válida")
        if row.get("fuente_fecha"):
            date.fromisoformat(row["fuente_fecha"])
        fuente = _need(row, "fuente_tipo")
        if fuente not in FUENTE:
            raise SystemExit(f"datos[{i}].fuente_tipo no válido: {fuente}")
    for i, row in enumerate(data.get("hallazgos") or []):
        if not isinstance(row, dict):
            raise SystemExit(f"hallazgos[{i}] no es un objeto")
        _need(row, "titulo")
        _need(row, "cuerpo")


def save(data: dict[str, Any], *, owner: str, token: str) -> int:
    import psycopg2

    validate(data)
    if not owner or not token:
        raise ValueError("Se requiere owner y token de reserva")
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":")).encode()).hexdigest()
    conn = psycopg2.connect(_db_url(), connect_timeout=10,
                            options="-c statement_timeout=15000 -c lock_timeout=5000")
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM homes.proyecto WHERE id=%s FOR UPDATE", (data["proyecto_id"],))
            cur.execute("""SELECT owner, token::text, expires_at > clock_timestamp(),
                                  investigacion_id, payload_sha256
                           FROM homes.proyecto_investigacion_lease WHERE proyecto_id=%s FOR UPDATE""",
                        (data["proyecto_id"],))
            lease = cur.fetchone()
            if not lease or lease[0:2] != (owner, token):
                raise ValueError("Reserva no pertenece a owner/token")
            if lease[3] is not None:
                if lease[4] != digest:
                    raise ValueError("Reintento con contenido distinto")
                conn.rollback()
                return int(lease[3])
            if not lease[2]:
                raise ValueError("Reserva caducada")
            cur.execute("SELECT set_config('homes.research_owner',%s,true), "
                        "set_config('homes.research_token',%s,true)", (owner, token))
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
            cur.execute("""UPDATE homes.proyecto_investigacion_lease SET investigacion_id=%s,
                              payload_sha256=%s WHERE proyecto_id=%s
                              AND expires_at > clock_timestamp() RETURNING proyecto_id""",
                        (inv_id, digest, data["proyecto_id"]))
            if not cur.fetchone():
                raise ValueError("Reserva caducada durante el guardado")
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
    parser.add_argument("--owner", required=True, help="Propietario de la reserva")
    parser.add_argument("--token", required=True, help="Token de fencing de la reserva")
    args = parser.parse_args()
    inv_id = save(_load(args.file), owner=args.owner, token=args.token)
    print(inv_id)


if __name__ == "__main__":
    main()
