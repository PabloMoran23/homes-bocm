#!/usr/bin/env python3
"""
Crea / actualiza SQLite local desde los artefactos actuales (CSV + índice SIGMA Madrid + links).

Ejemplo desde la raíz de poc-bocm/::

  python3 db/migrate_sqlite.py
  python3 db/migrate_sqlite.py --db db/poc_local.sqlite --fresh
  python3 db/migrate_sqlite.py --skip-sigma

Requiere: output/history_parsed_incremental.csv, output/ccaa_history_parsed_incremental.csv
Opcionales para tablas Sigma: madrid_ayto_expedientes_index.json, madrid_ayto_bocm_links.jsonl

El id del proyecto coincide con la fórmula de web/scripts/build-data.mjs (rowToProject → buildProject).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sqlite3
import sys
import unicodedata
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path


POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(__file__).resolve().parent / "poc_local.sqlite"
SCHEMA = Path(__file__).resolve().parent / "schema.sqlite.sql"


SOURCES = (
    ("bocm", "comunidad-madrid", "Comunidad de Madrid"),
    ("boja", "andalucia", "Andalucía"),
    ("dogv", "comunitat-valenciana", "Comunitat Valenciana"),
    ("bocyl", "castilla-leon", "Castilla y León"),
    ("docm", "castilla-mancha", "Castilla-La Mancha"),
    ("boc_canarias", "canarias", "Canarias"),
    ("bopa", "asturias", "Principado de Asturias"),
    ("boc_cantabria", "cantabria", "Cantabria"),
    ("boib", "illes-balears", "Illes Balears"),
    ("dog", "galicia", "Galicia"),
    ("bopv", "euskadi", "Euskadi"),
    ("borm", "murcia", "Región de Murcia"),
    ("dogc", "catalunya", "Catalunya"),
)


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFC", (s or "").strip().lower())
    return re.sub(r"\s+", " ", s)


def stable_sector_key(
    boletin_source_id: str,
    municipio: str,
    nombre_sector: str,
    municipio_provincia: str,
) -> str:
    parts = [
        norm_text(boletin_source_id),
        norm_text(municipio),
        norm_text(nombre_sector),
        norm_text(municipio_provincia),
    ]
    return sha256("||".join(parts).encode("utf-8")).hexdigest()


def legacy_sector_key(municipio: str, nombre_sector: str, municipio_provincia: str) -> str:
    return stable_sector_key("", municipio, nombre_sector, municipio_provincia)


def parse_relevante(raw: object) -> int | None:
    v = str(raw or "").strip().lower()
    if v in ("true", "1", "yes"):
        return 1
    if v in ("false", "0", "no"):
        return 0
    return None


def csv_bool_int(raw: object) -> int | None:
    v = str(raw or "").strip().lower()
    if v in ("true", "1", "yes"):
        return 1
    if v in ("false", "0", "no"):
        return 0
    return None


def row_to_stub(row: dict[str, str], *, default_source: str) -> dict[str, object]:
    source_id = (
        str(row.get("boletin_source_id") or default_source).strip().lower()
    )
    municipio = (row.get("municipio") or "").strip()
    nombre_sector = (row.get("nombre_sector") or "").strip()
    municipio_provincia = (row.get("municipio_provincia") or "").strip()
    fp = (row.get("proyecto_fingerprint") or "").strip()
    pub_date = (row.get("bocm_date") or row.get("date_pub") or row.get("fecha") or "").strip()
    art_num = (row.get("art_num") or row.get("id") or "").strip()
    sector_key = stable_sector_key(source_id, municipio, nombre_sector, municipio_provincia)
    tail = fp or sector_key[:12] or "na"
    project_id = f"{source_id}-{pub_date}-{art_num}-{tail}"
    return {
        "id": project_id,
        "source_id": source_id,
        "pub_date": pub_date,
        "art_num": art_num,
        "fp": fp,
        "sector_key": sector_key,
        "sector_geo_key": legacy_sector_key(municipio, nombre_sector, municipio_provincia),
        "parse_error": (row.get("error") or "").strip() or None,
        "es_relevante": parse_relevante(row.get("es_relevante")),
        "row": row,
    }


def null_if_empty(s: str | None) -> str | None:
    s = (s or "").strip()
    return s if s else None


def ms_to_iso_date(ms: object) -> str | None:
    if ms is None or ms == "":
        return None
    try:
        n = float(ms)
        if math.isnan(n):
            return None
        return datetime.fromtimestamp(n / 1000.0, tz=UTC).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return None


def int_or_none(x: object) -> int | None:
    if x is None or x == "":
        return None
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def float_or_none(x: object) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def expediente_grupo_from_num(num: str) -> str | None:
    n = re.sub(r"\s+", "", (num or "").strip())
    parts = n.split("/")
    if len(parts) == 3 and parts[2].isdigit():
        return f"{parts[0]}/{parts[1]}/{int(parts[2]):05d}"
    return n if n else None


def apply_schema(con: sqlite3.Connection, *, fresh: bool) -> None:
    if fresh:
        con.executescript(
            """
            PRAGMA foreign_keys = OFF;
            DROP TABLE IF EXISTS sigma_boletin_sibling;
            DROP TABLE IF EXISTS sigma_nti_document;
            DROP TABLE IF EXISTS sigma_vis_tramite;
            DROP TABLE IF EXISTS link_project_sigma;
            DROP TABLE IF EXISTS sigma_catalog_expediente;
            DROP TABLE IF EXISTS project_boletin;
            DROP TABLE IF EXISTS source;
            DROP TABLE IF EXISTS link_licencia_sigma;
            DROP TABLE IF EXISTS actuacion_edificacion;
            DROP TABLE IF EXISTS inmueble;
            DROP TABLE IF EXISTS sigma_ambito_geom;
            DROP TABLE IF EXISTS hito;
            DROP TABLE IF EXISTS schema_migrations;
            PRAGMA foreign_keys = ON;
            """
        )
    schema_sql = SCHEMA.read_text(encoding="utf-8")
    con.executescript(schema_sql)
    con.execute(
        "INSERT OR IGNORE INTO schema_migrations (version) VALUES (1)"
    )
    _apply_ubicacion_schema_if_needed(con)


def _apply_ubicacion_schema_if_needed(con: sqlite3.Connection) -> None:
    """Aplica schema_ubicacion.sql (migración v2) si aún no está registrada."""
    cur = con.execute("SELECT 1 FROM schema_migrations WHERE version=2")
    if cur.fetchone():
        return
    ubicacion_sql = Path(__file__).resolve().parent / "schema_ubicacion.sql"
    if ubicacion_sql.is_file():
        con.executescript(ubicacion_sql.read_text(encoding="utf-8"))
        con.execute("INSERT OR IGNORE INTO schema_migrations (version) VALUES (2)")


def seed_sources(con: sqlite3.Connection) -> None:
    con.executemany(
        "INSERT OR REPLACE INTO source (id, territorio_id, territorio_label) VALUES (?,?,?)",
        SOURCES,
    )


def ingest_csv(con: sqlite3.Connection, path: Path, *, default_source: str) -> int:
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8")
    try:
        dialect = csv.Sniffer().sniff(text[:8192])
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    rows = list(reader)

    cols = """id, source_id, pub_date, art_num, title, pdf_path, pdf_url,
    txt_chars, latency_s, parse_error, es_relevante,
    municipio, tipo_instrumento, nombre_sector, estado_tramitacion, fecha_acuerdo, organo,
    num_viviendas_max, fecha_fin_estimada, sup_total_m2, sup_edificable_m2,
    tipo_vivienda, promotor, municipio_provincia, resumen, categorias_tematicas,
    economico_resumen, procedimiento_expediente, procedimiento_tipo, importe_total_eur,
    chars_texto_total, llm_max_context_chars, texto_truncado_llm, requiere_segunda_pasada,
    proyecto_fingerprint, sector_key, sector_geo_key"""

    sql_raw = cols.replace("\n", " ")
    ncol = sql_raw.count(",") + 1

    sql_insert = (
        f"INSERT OR REPLACE INTO project_boletin ({sql_raw}, lat, lng, coord_source, updated_at) "
        f"VALUES ({','.join(['?'] * (ncol + 3))}, datetime('now'))"
    )

    n = 0
    for row in rows:
        st = row_to_stub(row, default_source=default_source)
        if not st["pub_date"] or not st["art_num"]:
            continue

        rr = row
        valores = (
            st["id"],
            st["source_id"],
            st["pub_date"],
            st["art_num"],
            rr.get("title") or "",
            null_if_empty(rr.get("pdf_path")),
            null_if_empty(rr.get("pdf_url")),
            int_or_none(rr.get("txt_chars")),
            float_or_none(rr.get("latency_s")),
            st["parse_error"],
            st["es_relevante"],
            null_if_empty(rr.get("municipio")),
            null_if_empty(rr.get("tipo_instrumento")),
            null_if_empty(rr.get("nombre_sector")),
            null_if_empty(rr.get("estado_tramitacion")),
            null_if_empty(rr.get("fecha_acuerdo")),
            null_if_empty(rr.get("organo_aprobador")),
            int_or_none(rr.get("num_viviendas_max")),
            null_if_empty(rr.get("fecha_fin_estimada")),
            float_or_none(rr.get("sup_total_m2")),
            float_or_none(rr.get("sup_edificable_m2")),
            null_if_empty(rr.get("tipo_vivienda")),
            null_if_empty(rr.get("promotor_o_propietario")),
            null_if_empty(rr.get("municipio_provincia")),
            null_if_empty(rr.get("resumen")),
            null_if_empty(rr.get("categorias_tematicas")),
            null_if_empty(rr.get("economico_resumen")),
            null_if_empty(rr.get("procedimiento_expediente")),
            null_if_empty(rr.get("procedimiento_tipo")),
            float_or_none(rr.get("importe_total_eur_estimado")),
            int_or_none(rr.get("chars_texto_total")),
            int_or_none(rr.get("llm_max_context_chars")),
            csv_bool_int(rr.get("texto_truncado_llm")),
            1 if str(rr.get("requiere_segunda_pasada") or "").strip().lower() in ("true", "1") else 0,
            null_if_empty(rr.get("proyecto_fingerprint")),
            st["sector_key"],
            st["sector_geo_key"],
            None,
            None,
            None,
        )
        con.execute(sql_insert, valores)
        n += 1
    return n


def ingest_sigma_catalog(con: sqlite3.Connection, path: Path) -> int:
    if not path.is_file():
        return 0
    raw = json.loads(path.read_text(encoding="utf-8"))
    lista = raw.get("expedientes") or []
    sql = """INSERT OR REPLACE INTO sigma_catalog_expediente (
        expediente_grupo, exp_numero_original, sigma_layer_kind, denominacion, fase,
        fecha_aprob, infopublica_inicio, infopublica_fin,
        figura_codigo, tipo_figura, organo_tramitador, enlace,
        catalog_source, object_id, has_geometry,
        synced_at, raw_features_json
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    g_at = raw.get("generatedAt")
    count = 0
    buf: list[tuple] = []
    for e in lista:
        num = str(e.get("EXP_TX_NUMERO") or "").strip()
        grp = expediente_grupo_from_num(num)
        if not grp:
            continue
        layer_kind = (e.get("sigma_layer_kind") or e.get("source") or "").strip()
        catalog_src = (e.get("source") or "").strip()
        buf.append(
            (
                grp,
                num,
                layer_kind[:80] if layer_kind else None,
                null_if_empty(str(e.get("EXP_TX_DENOM") or "").strip()),
                null_if_empty(str(e.get("FAS_TX_DENOM") or "").strip()),
                ms_to_iso_date(e.get("FEX_DT_APROB")),
                ms_to_iso_date(e.get("FEX_DT_INFOPUB_INI")),
                ms_to_iso_date(e.get("FEX_DT_INFOPUB_FIN")),
                null_if_empty(str(e.get("FIG_TX_ETIQ") or "")[:200]),
                null_if_empty(str(e.get("TFIG_TX_ABREV") or "")[:120]),
                null_if_empty(str(e.get("ORG_TX_DESC") or "")[:400]),
                null_if_empty(str(e.get("Enlace") or "").strip()),
                catalog_src or None,
                int_or_none(e.get("EXP_ID")),
                1 if e.get("has_geometry") else 0,
                g_at,
                json.dumps({k: e.get(k) for k in e}, ensure_ascii=False),
            )
        )
        count += 1
    con.executemany(sql, buf)
    return count


def ingest_sigma_links(con: sqlite3.Connection, path: Path) -> int:
    if not path.is_file():
        return 0
    seen: set[tuple[str, str]] = set()
    n = 0
    sql = """INSERT OR REPLACE INTO link_project_sigma (
        project_id, expediente_grupo, match_type, match_score, sigma_enlace_snapshot
    ) VALUES (?,?,?,?,?)"""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        pid = rec.get("bocm_id")
        exp_raw = rec.get("sigma_expediente")
        if not pid or not exp_raw:
            continue
        grp = expediente_grupo_from_num(str(exp_raw))
        if not grp:
            continue
        key = (pid, grp)
        if key in seen:
            continue
        seen.add(key)
        cur = con.execute("SELECT 1 FROM project_boletin WHERE id=?", (pid,))
        if cur.fetchone() is None:
            continue
        con.execute(
            sql,
            (
                pid,
                grp,
                rec.get("match_type"),
                float(rec["match_score"]) if rec.get("match_score") is not None else None,
                null_if_empty(str(rec.get("sigma_enlace") or "")),
            ),
        )
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Inicializa SQLite y vuelca CSV (+ Sigma Madrid opcional).")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--fresh", action="store_true", help="Borra tablas conocidas antes de aplicar DDL.")
    ap.add_argument(
        "--skip-sigma",
        action="store_true",
        help="No cargar madrid_ayto_expedientes_index ni links jsonl.",
    )
    ap.add_argument(
        "--ubicacion",
        action="store_true",
        help="Tras migrar, ejecutar ingest_madrid_ubicacion (licencias + enlace espacial SIGMA).",
    )
    args = ap.parse_args()

    bocm_csv = POC_ROOT / "output/history_parsed_incremental.csv"
    ccaa_csv = POC_ROOT / "output/ccaa_history_parsed_incremental.csv"
    index_json = POC_ROOT / "output/madrid_ayto_expedientes_index.json"
    links_jsonl = POC_ROOT / "output/madrid_ayto_bocm_links.jsonl"

    args.db.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(args.db) as con:
        apply_schema(con, fresh=args.fresh)
        seed_sources(con)

        nb = ingest_csv(con, bocm_csv, default_source="bocm")
        nc = ingest_csv(con, ccaa_csv, default_source="dogc")

        nx = nz = 0
        if not args.skip_sigma:
            nx = ingest_sigma_catalog(con, index_json)
            nz = ingest_sigma_links(con, links_jsonl)

        con.commit()

    DB_DIR = Path(__file__).resolve().parent
    sys.path.insert(0, str(DB_DIR))
    from sqlite_assets import ensure_sigma_nti_asset_columns

    with sqlite3.connect(args.db) as con:
        ensure_sigma_nti_asset_columns(con)
        con.commit()

    if args.ubicacion:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from ingest_madrid_ubicacion import (
            apply_ubicacion_schema,
            ingest_licencias,
            ingest_sigma_geometries,
            link_licencias_sigma,
            sync_hitos_from_tramites,
        )

        with sqlite3.connect(args.db) as con:
            apply_ubicacion_schema(con)
            ingest_sigma_geometries(con)
            ingest_licencias(con)
            sync_hitos_from_tramites(con)
            link_licencias_sigma(con)
            con.commit()

    print(
        json.dumps(
            {
                "db": str(args.db),
                "project_rows_bocm": nb,
                "project_rows_ccaa": nc,
                "sigma_catalog": nx if not args.skip_sigma else None,
                "sigma_links_ok": nz if not args.skip_sigma else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
