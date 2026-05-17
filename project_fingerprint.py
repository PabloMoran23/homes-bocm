"""
Huella determinista de «proyecto» a partir de campos ya parseados del BOCM.

No sustituye a un expediente oficial: agrupa filas cuando municipio + tipo
canonizado + nombre de sector coinciden tras normalización.
"""

from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from pathlib import Path

_TIPO_CANON = {
    "plan parcial": "plan_parcial",
    "plan especial": "plan_especial",
    "modificación pgou": "modificacion_pgou",
    "modificacion pgou": "modificacion_pgou",
    "normas subsidiarias": "normas_subsidiarias",
    "estudio de detalle": "estudio_detalle",
    "proyecto de urbanización": "proyecto_urbanizacion",
    "proyecto de urbanizacion": "proyecto_urbanizacion",
    "licencia de obra": "licencia_obra",
    "convenio urbanístico": "convenio_urbanistico",
    "convenio urbanistico": "convenio_urbanistico",
    "junta de compensación": "junta_compensacion",
    "junta de compensacion": "junta_compensacion",
    "otro": "otro",
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def norm_text(s: str | None) -> str:
    if not s:
        return ""
    t = unicodedata.normalize("NFKC", str(s))
    t = _strip_accents(t.lower().strip())
    t = re.sub(r"\s+", " ", t)
    return t


def municipio_effective(row: dict) -> str:
    m = norm_text(row.get("municipio"))
    if m:
        return m
    mp = row.get("municipio_provincia") or ""
    first = mp.split(",")[0].strip()
    return norm_text(first)


def canon_tipo(tipo: str | None) -> str:
    t = norm_text(tipo)
    if not t:
        return "sin_tipo"
    if t in _TIPO_CANON:
        return _TIPO_CANON[t]
    slug = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return (slug or "sin_tipo")[:80]


def compute_proyecto_fingerprint(row: dict) -> str:
    m = municipio_effective(row)
    t = canon_tipo(row.get("tipo_instrumento"))
    n = norm_text(row.get("nombre_sector"))
    if not m and not n:
        return ""
    raw = f"{m}|{t}|{n}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def backfill_csv(csv_path: Path) -> tuple[int, list[str]]:
    """
    Añade o recalcula la columna proyecto_fingerprint en todo el CSV.
    Devuelve (número de filas, lista de fieldnames final).
    """
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames_in = reader.fieldnames or []
        rows = list(reader)

    fieldnames = list(fieldnames_in)
    col = "proyecto_fingerprint"
    if col not in fieldnames:
        fieldnames.append(col)

    for row in rows:
        row[col] = compute_proyecto_fingerprint(row)

    tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    tmp.replace(csv_path)
    return len(rows), fieldnames


def main() -> None:
    import os

    base = Path(__file__).resolve().parent
    default = base / "output" / "history_parsed_incremental.csv"
    path = Path(os.getenv("HISTORY_CSV", str(default)))
    n, fields = backfill_csv(path)
    print(f"OK {path}  filas={n}  columnas={len(fields)}  última={fields[-1]}")


if __name__ == "__main__":
    main()
