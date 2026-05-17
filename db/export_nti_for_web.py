#!/usr/bin/env python3
"""Exporta documentos NTI (SQLite) para fichas web enlazadas a proyectos BOCM."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = POC_ROOT / "db" / "poc_local.sqlite"
OUT_PATH = POC_ROOT / "web" / "public" / "data" / "sigma-nti-linked.json"


def main() -> None:
    if not DB_PATH.is_file():
        print(json.dumps({"skipped": True, "reason": f"No existe {DB_PATH}"}))
        return

    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        grupos = [
            r[0]
            for r in con.execute(
                """
                SELECT DISTINCT expediente_grupo FROM link_project_sigma
                WHERE expediente_grupo IS NOT NULL AND TRIM(expediente_grupo) != ''
                ORDER BY expediente_grupo
                """
            ).fetchall()
        ]
        if not grupos:
            grupos = [
                r[0]
                for r in con.execute(
                    """
                    SELECT DISTINCT expediente_grupo FROM sigma_nti_document
                    ORDER BY expediente_grupo
                    """
                ).fetchall()
            ]

        by_grupo: dict[str, dict] = {}
        for grupo in grupos:
            rows = con.execute(
                """
                SELECT orden, url, titulo, tooltip, ruta_carpetas, tipodoc_nti,
                       fecha_documento, local_path, sha256, file_bytes, content_type,
                       http_status, download_error
                FROM sigma_nti_document
                WHERE expediente_grupo = ?
                ORDER BY orden, id
                """,
                (grupo,),
            ).fetchall()
            if not rows:
                continue

            docs = []
            downloaded = errors = bytes_total = 0
            for r in rows:
                lp = r["local_path"]
                err = r["download_error"]
                fb = r["file_bytes"] or 0
                if lp and str(lp).strip():
                    downloaded += 1
                    bytes_total += int(fb)
                if err and str(err).strip():
                    errors += 1
                docs.append(
                    {
                        "orden": r["orden"],
                        "url": r["url"],
                        "titulo": r["titulo"],
                        "tooltip": r["tooltip"],
                        "rutaCarpetas": r["ruta_carpetas"],
                        "tipodocNti": r["tipodoc_nti"],
                        "fechaDocumento": r["fecha_documento"],
                        "localPath": lp,
                        "sha256": r["sha256"],
                        "fileBytes": r["file_bytes"],
                        "contentType": r["content_type"],
                        "httpStatus": r["http_status"],
                        "downloadError": err,
                    }
                )

            by_grupo[grupo] = {
                "stats": {
                    "total": len(docs),
                    "downloaded": downloaded,
                    "errors": errors,
                    "bytesTotal": bytes_total,
                },
                "documentos": docs,
            }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "expedienteCount": len(by_grupo),
        "documentCount": sum(g["stats"]["total"] for g in by_grupo.values()),
        "byGrupo": by_grupo,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(OUT_PATH),
                "expedientes": len(by_grupo),
                "documentos": payload["documentCount"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
