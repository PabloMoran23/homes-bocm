#!/usr/bin/env python3
"""
Vierte madrid_viso_expedientes.json en sigma_vis_tramite y sigma_nti_document (+ stubs catálogo).

Desde poc-bocm/::

  python3 db/ingest_visor_sqlite.py
  python3 db/ingest_visor_sqlite.py --db db/poc_local.sqlite \\
      --visor-json output/madrid_viso_expedientes.json

Antes conviene refrescar fuentes grandes::

  python3 -m sector_geometry.madrid_viso_fetch
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DB_DIR))

from sqlite_assets import ensure_sigma_nti_asset_columns  # noqa: E402

DEFAULT_DB = DB_DIR / "poc_local.sqlite"
DEFAULT_VISOR = POC_ROOT / "output/madrid_viso_expedientes.json"


def _nti_docs(rec: dict) -> list[dict]:
    nti = rec.get("ntiArbol") if isinstance(rec.get("ntiArbol"), dict) else None
    if not nti:
        return []
    full = nti.get("documentos")
    if isinstance(full, list) and full:
        return full
    muestra = nti.get("documentosMuestra")
    if isinstance(muestra, list):
        return muestra
    return []


def _ensure_stub_catalog(
    con: sqlite3.Connection,
    grupo: str,
    *,
    visor_url: str | None,
    layer_kind: str | None,
    synced_at: str | None,
) -> None:
    cur = con.execute(
        "SELECT 1 FROM sigma_catalog_expediente WHERE expediente_grupo=?",
        (grupo,),
    )
    if cur.fetchone():
        if visor_url or layer_kind or synced_at:
            con.execute(
                """
                UPDATE sigma_catalog_expediente SET
                  enlace = COALESCE(enlace, ?),
                  sigma_layer_kind = COALESCE(sigma_layer_kind, ?),
                  synced_at = COALESCE(?, synced_at)
                WHERE expediente_grupo = ?
                """,
                (visor_url, layer_kind, synced_at, grupo),
            )
        return
    con.execute(
        """
        INSERT INTO sigma_catalog_expediente (
          expediente_grupo, exp_numero_original, enlace, sigma_layer_kind,
          has_geometry, synced_at
        ) VALUES (?,?,?,?,0,?)
        """,
        (grupo, grupo, visor_url, layer_kind, synced_at),
    )


def ingest(*, db_path: Path, visor_path: Path, replace_nti_metadatos: bool) -> dict[str, int]:
    raw = json.loads(visor_path.read_text(encoding="utf-8"))
    by_g = raw.get("byGrupoExpediente") or {}
    gen_at = raw.get("generatedAt")

    tram_ins = exp_con_tram = doc_ins = skips = stubs = 0

    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON")
        ensure_sigma_nti_asset_columns(con)

        for grupo, rec in sorted(by_g.items()):
            if not grupo or rec.get("sinDatosVisor"):
                skips += 1
                continue

            visor_u = (
                rec.get("visorUrlUsada").strip()
                if isinstance(rec.get("visorUrlUsada"), str)
                else None
            )
            layer = (
                rec.get("sigmaLayerKind").strip()
                if isinstance(rec.get("sigmaLayerKind"), str)
                else None
            )

            stubs += 1
            _ensure_stub_catalog(
                con, grupo, visor_url=visor_u or None, layer_kind=layer or None, synced_at=gen_at
            )

            tram = rec.get("tramitacion")
            if isinstance(tram, list) and tram:
                con.execute("DELETE FROM sigma_vis_tramite WHERE expediente_grupo = ?", (grupo,))
                exp_con_tram += 1
                for i, t in enumerate(tram):
                    if not isinstance(t, dict):
                        continue
                    con.execute(
                        """
                        INSERT INTO sigma_vis_tramite (
                          expediente_grupo, orden, fecha, tramite, organo, visor_url, fetched_at
                        ) VALUES (?,?,?,?,?,?,?)
                        """,
                        (
                            grupo,
                            i,
                            (t.get("fecha") or "").strip() or None,
                            (t.get("tramite") or "").strip() or None,
                            (t.get("organo") or "").strip() or None,
                            visor_u,
                            gen_at,
                        ),
                    )
                    tram_ins += 1

            docs = _nti_docs(rec)
            if docs:
                if replace_nti_metadatos:
                    con.execute("DELETE FROM sigma_nti_document WHERE expediente_grupo = ?", (grupo,))
                for i, meta in enumerate(docs):
                    if not isinstance(meta, dict):
                        continue
                    url = (meta.get("url") or "").strip()
                    if not url:
                        continue
                    con.execute(
                        """
                        INSERT INTO sigma_nti_document (
                          expediente_grupo, orden, url, titulo, tooltip, ruta_carpetas,
                          tipodoc_nti, fecha_documento, fecha_creacion, fetched_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(expediente_grupo, url) DO UPDATE SET
                          orden = excluded.orden,
                          titulo = excluded.titulo,
                          tooltip = excluded.tooltip,
                          ruta_carpetas = excluded.ruta_carpetas,
                          tipodoc_nti = excluded.tipodoc_nti,
                          fecha_documento = excluded.fecha_documento,
                          fecha_creacion = excluded.fecha_creacion,
                          fetched_at = excluded.fetched_at
                        """,
                        (
                            grupo,
                            i,
                            url,
                            (meta.get("titulo") or "").strip() or None,
                            (meta.get("tooltip") or "").strip() or None,
                            (meta.get("rutaCarpetas") or "").strip() or None,
                            (meta.get("tipodocNti") or "").strip() or None,
                            (meta.get("fechaDocumento") or "").strip() or None,
                            (meta.get("fechaCreacion") or "").strip() or None,
                            gen_at,
                        ),
                    )
                    doc_ins += 1

        con.commit()

    return {
        "tramite_rows_written": tram_ins,
        "expedientes_tramites_refrescados": exp_con_tram,
        "nti_rows_upserted": doc_ins,
        "stubs_catalog_actualizados": stubs,
        "skipped_sin_datos_visor": skips,
        "expedientes_en_json": len(by_g),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingesta madrid_viso_expedientes → SQLite Sigma.")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--visor-json", type=Path, default=DEFAULT_VISOR)
    ap.add_argument(
        "--preserve-nti-local",
        action="store_true",
        help="UPSERT metadata NTI sin DELETE previo por expediente (conserva IDs y mejor con descargas hechas)",
    )
    args = ap.parse_args()

    if not args.db.is_file():
        raise SystemExit(f"No existe DB {args.db}: ejecuta db/migrate_sqlite.py primero")
    if not args.visor_json.is_file():
        raise SystemExit(f"No existe {args.visor_json}: ejecuta madrid_viso_fetch")

    stats = ingest(
        db_path=args.db,
        visor_path=args.visor_json,
        replace_nti_metadatos=not args.preserve_nti_local,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
