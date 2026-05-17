from __future__ import annotations

import csv
import os
from pathlib import Path

from .db import connect, upsert_pending
from .keys import norm_text, stable_sector_key


def _truthy_es_relevante(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in ("1", "true", "yes", "si", "sí")


def _urbanismo_row(cats: str | None) -> bool:
    if not cats:
        return False
    c = cats.lower()
    return "urbanismo" in c or "planeamiento" in c or "licencia_obra" in c


def enqueue_csv(
    csv_path: Path,
    *,
    db_path: Path,
    require_urbanismo_cat: bool = True,
) -> tuple[int, int]:
    """
    Lee filas del CSV parseado e inserta claves pendientes en sector_spatial.
    Devuelve (filas_leídas_relevantes, nuevas_inserciones).
    """
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)

    con = connect(db_path)
    inserted = 0
    scanned = 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or ()
        has_cats = "categorias_tematicas" in fieldnames
        for row in reader:
            if not _truthy_es_relevante(row.get("es_relevante")):
                continue
            municipio = (row.get("municipio") or "").strip()
            sector = (row.get("nombre_sector") or "").strip()
            if not municipio or not sector:
                continue
            if require_urbanismo_cat and has_cats and not _urbanismo_row(row.get("categorias_tematicas")):
                continue
            scanned += 1
            sk = stable_sector_key(
                municipio=municipio,
                nombre_sector=sector,
                municipio_provincia=row.get("municipio_provincia"),
                boletin_source_id=row.get("boletin_source_id"),
            )
            r = upsert_pending(
                con,
                stable_key=sk,
                municipio_raw=municipio,
                sector_raw=sector,
                municipio_norm=norm_text(municipio),
                sector_norm=norm_text(sector),
                municipio_provincia_raw=(row.get("municipio_provincia") or "").strip() or None,
                boletin_source_id=(row.get("boletin_source_id") or "").strip() or None,
                proyecto_fingerprint=(row.get("proyecto_fingerprint") or "").strip() or None,
            )
            if r == "inserted":
                inserted += 1
    con.close()
    return scanned, inserted


def default_csv_paths(repo_root: Path | None = None) -> list[Path]:
    root = repo_root or Path(__file__).resolve().parents[1]
    paths = []
    for env in ("SECTOR_ENQUEUE_CSV", "CCAA_HISTORY_CSV"):
        raw = os.getenv(env)
        if raw:
            paths.append(Path(raw))
    if not paths:
        paths = [
            root / "output" / "ccaa_history_parsed_incremental.csv",
            root / "output" / "history_parsed_incremental.csv",
        ]
    return paths
