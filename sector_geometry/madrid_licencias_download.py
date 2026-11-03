#!/usr/bin/env python3
"""
Descarga licencias urbanísticas otorgadas (datos abiertos Ayto. Madrid 300193).

Salidas en output/:
  - madrid_licencias_raw/*.xlsx   (un fichero por año)
  - madrid_licencias.jsonl          (todas las filas unificadas)
  - madrid_licencias_summary.json   (conteos por año y columnas)

Fuente: https://datos.madrid.es/dataset/300193-0-licencias-urbanisticas

Uso:
  python3 -m sector_geometry.madrid_licencias_download --current  # fuentes actuales desde 2023
  # El conjunto anual antiguo está retirado; estas opciones sirven para replay de caché:
  python3 -m sector_geometry.madrid_licencias_download
  python3 -m sector_geometry.madrid_licencias_download --years 2020,2021,2022
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import urllib.request
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

POC_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = POC_ROOT / "output"
RAW_DIR = OUTPUT_DIR / "madrid_licencias_raw"
JSONL_OUT = OUTPUT_DIR / "madrid_licencias.jsonl"
SUMMARY_OUT = OUTPUT_DIR / "madrid_licencias_summary.json"

# Slug del recurso CKAN por año (descarga directa: …/resource/{slug}/download/{slug}.xlsx)
LICENCIAS_RESOURCE_SLUG_BY_YEAR: dict[int, str] = {
    2015: "300193-9-licencias-urbanisticas-xlsx",
    2016: "300193-8-licencias-urbanisticas-xlsx",
    2017: "300193-7-licencias-urbanisticas-xlsx",
    2018: "300193-6-licencias-urbanisticas-xlsx",
    2019: "300193-12-licencias-urbanisticas-xlsx",
    2020: "300193-4-licencias-urbanisticas-xlsx",
    2021: "300193-5-licencias-urbanisticas-xlsx",
    2022: "300193-3-licencias-urbanisticas-xlsx",
    2023: "300193-1-licencias-urbanisticas-xlsx",
    2024: "300193-11-licencias-urbanisticas-xlsx",
    2025: "300193-0-licencias-urbanisticas-xlsx",
    2026: "300193-2-licencias-urbanisticas-xlsx",
}

DATASET_BASE = "https://datos.madrid.es/dataset/300193-0-licencias-urbanisticas/resource"


def _download_url_for_year(year: int) -> str | None:
    slug = LICENCIAS_RESOURCE_SLUG_BY_YEAR.get(year)
    if not slug:
        return None
    return f"{DATASET_BASE}/{slug}/download/{slug}.xlsx"


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "poc-bocm-madrid-licencias/1.0 (+datos.madrid.es)"},
    )
    with urllib.request.urlopen(req, timeout=60.0) as resp:
        content = resp.read()
    # Un error HTML o un XLSX truncado nunca debe sustituir la caché válida.
    import zipfile
    from io import BytesIO
    if not zipfile.is_zipfile(BytesIO(content)):
        raise ValueError("La descarga no es un XLSX válido")
    dest.write_bytes(content)


def _norm_col(name: str) -> str:
    s = re.sub(r"\s+", "_", (name or "").strip().lower())
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s or "col"


def licencia_key(row: dict[str, Any], *, anio: int | None) -> str:
    if row.get("numero_expediente") and row.get("source_dataset"):
        return sha256(f"{row['source_dataset']}|{row['numero_expediente']}|{row.get('ndp_edificio', '')}".encode()).hexdigest()[:32]
    parts = [
        str(anio or row.get("anio_dataset") or row.get("anioDataset") or ""),
        str(row.get("ndp_edificio") or row.get("ndpEdificio") or ""),
        str(row.get("fecha_de_alta") or row.get("fechaAlta") or ""),
        str(row.get("tipo_de_expediente") or row.get("tipoExpediente") or ""),
        str(row.get("fecha_concesin") or row.get("fechaConcesion") or ""),
    ]
    return sha256("|".join(parts).encode()).hexdigest()[:32]


def _rows_from_xlsx(path: Path, year: int) -> list[dict[str, Any]]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit(
            "Faltan dependencias. Instala con: pip install pandas openpyxl\n"
            f"({exc})"
        ) from exc

    df = pd.read_excel(path, sheet_name=0, dtype=object)
    if df.empty:
        return []
    df = df.dropna(how="all")
    df = df.rename(columns={orig: _norm_col(str(orig)) for orig in df.columns})
    out: list[dict[str, Any]] = []
    origin = {"municipio_slug": "madrid", "adapter": "madrid-opendata",
        "url": _download_url_for_year(year), "dataset": "300193-0-licencias-urbanisticas",
        "resourceSha256": sha256(path.read_bytes()).hexdigest(),
        "cacheModifiedAt": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}
    for _, row in df.iterrows():
        rec: dict[str, Any] = {"anio_dataset": year, "source": "madrid-opendata",
            "_territorial_origin": origin}
        empty = True
        for key, val in row.items():
            if pd.isna(val) or (isinstance(val, str) and not val.strip()):
                rec[key] = None
                continue
            empty = False
            if isinstance(val, pd.Timestamp):
                rec[key] = val.date().isoformat()
            elif isinstance(val, (datetime, date)):
                rec[key] = val.isoformat() if isinstance(val, date) else val.date().isoformat()
            else:
                rec[key] = val
        if not empty:
            out.append(rec)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Descarga licencias urbanísticas Madrid (XLSX → JSONL).")
    ap.add_argument(
        "--years",
        type=str,
        default="",
        help="Años coma-separados (default: todos 2015-2026)",
    )
    ap.add_argument("--skip-download", action="store_true", help="Sólo convertir XLSX ya en raw/")
    ap.add_argument("--current", action="store_true", help="Fuentes actuales: licencias y declaraciones responsables desde 2023")
    ap.add_argument(
        "--merge-jsonl",
        action="store_true",
        help="Fusionar filas descargadas en madrid_licencias.jsonl existente (por licencia_key).",
    )
    args = ap.parse_args()
    if args.current:
        from sector_geometry.madrid_licencias_current import refresh
        summary = refresh(OUTPUT_DIR, RAW_DIR, JSONL_OUT, SUMMARY_OUT)
        print(json.dumps({"ok": True, "totalRows": summary["totalRows"], "byYear": summary["byYear"]}))
        return

    years = sorted(LICENCIAS_RESOURCE_SLUG_BY_YEAR.keys())
    if args.years.strip():
        years = [int(y.strip()) for y in args.years.split(",") if y.strip()]
    unknown = set(years) - LICENCIAS_RESOURCE_SLUG_BY_YEAR.keys()
    if unknown:
        ap.error(f"Años sin recurso configurado: {sorted(unknown)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    resources: dict[str, dict[str, Any]] = {}
    per_year: dict[str, int] = {}
    all_rows: list[dict[str, Any]] = []
    columns_seen: set[str] = set()
    failures: list[str] = []

    for year in years:
        url = _download_url_for_year(year)
        if not url:
            print(f"  omitido {year}: sin URL", flush=True)
            continue
        dest = RAW_DIR / f"licencias_urbanisticas_{year}.xlsx"
        parse_path = dest
        if not args.skip_download:
            print(f"  Descargando {year}…", flush=True)
            with tempfile.NamedTemporaryFile(dir=RAW_DIR, suffix=".xlsx", delete=False) as tmp:
                parse_path = Path(tmp.name)
            try:
                _download(url, parse_path)
            except Exception as exc:
                parse_path.unlink(missing_ok=True)
                failures.append(f"{year}: {exc}")
                print(f"  ERROR {year}: {exc}", flush=True)
                continue
        elif not dest.is_file():
            failures.append(f"{year}: no existe {dest.name}")
            print(f"  omitido {year}: no existe {dest.name}", flush=True)
            continue

        print(f"  Parseando {dest.name}…", flush=True)
        try:
            rows = _rows_from_xlsx(parse_path, year)
            if not rows:
                raise ValueError("El recurso no contiene licencias")
        except Exception as exc:
            if parse_path != dest:
                parse_path.unlink(missing_ok=True)
            failures.append(f"{year}: {exc}")
            print(f"  ERROR parse {year}: {exc}", flush=True)
            continue
        if parse_path != dest:
            parse_path.replace(dest)
        resources[str(year)] = {"url": url, "sha256": sha256(dest.read_bytes()).hexdigest(),
            "cacheModifiedAt": datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).isoformat(),
            "downloadedThisRun": not args.skip_download, "factualUpdatedAt": None}
        per_year[str(year)] = len(rows)
        for r in rows:
            columns_seen.update(r.keys())
        all_rows.extend(rows)
        print(f"    {len(rows)} filas", flush=True)

    if failures:
        raise SystemExit("No se publican JSONL ni resumen; falló la actualización: " + "; ".join(failures))

    rows_to_write = all_rows
    if args.merge_jsonl and JSONL_OUT.is_file():
        merged: dict[str, dict[str, Any]] = {}
        with JSONL_OUT.open(encoding="utf-8") as lf:
            for line in lf:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                anio = row.get("anio_dataset") or row.get("anioDataset")
                try:
                    anio_i = int(anio) if anio is not None else None
                except (TypeError, ValueError):
                    anio_i = None
                merged[licencia_key(row, anio=anio_i)] = row
        for row in all_rows:
            anio_i = int(row["anio_dataset"]) if row.get("anio_dataset") is not None else None
            merged[licencia_key(row, anio=anio_i)] = row
        rows_to_write = list(merged.values())
        print(f"  JSONL merge: {len(rows_to_write)} filas totales", flush=True)

    tmp_jsonl = JSONL_OUT.with_suffix(".jsonl.tmp")
    with tmp_jsonl.open("w", encoding="utf-8") as lf:
        for row in rows_to_write:
            lf.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    if args.merge_jsonl and SUMMARY_OUT.is_file():
        previous = json.loads(SUMMARY_OUT.read_text(encoding="utf-8"))
        cached_resources = {
            key: {**value, "downloadedThisRun": False}
            for key, value in previous.get("sourceSnapshot", {}).get("resources", {}).items()
        }
        resources = {**cached_resources, **resources}
        columns_seen.update(previous.get("columns", []))
    per_year = {}
    for row in rows_to_write:
        year_key = str(row.get("anio_dataset") or row.get("anioDataset"))
        per_year[year_key] = per_year.get(year_key, 0) + 1

    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "datos.madrid.es dataset 300193-0-licencias-urbanisticas",
        "sourceSnapshot": {"mode": "cached-xlsx-replay" if args.skip_download else "xlsx-download",
                           "resources": resources, "factualUpdatedAt": None},
        "totalRows": len(rows_to_write),
        "byYear": per_year,
        "columns": sorted(columns_seen),
        "rawDir": str(RAW_DIR),
        "jsonl": str(JSONL_OUT),
    }
    tmp_summary = SUMMARY_OUT.with_suffix(".json.tmp")
    tmp_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_jsonl.replace(JSONL_OUT)
    tmp_summary.replace(SUMMARY_OUT)

    print(
        json.dumps(
            {
                "ok": True,
                "totalRows": len(rows_to_write),
                "byYear": per_year,
                "jsonl": str(JSONL_OUT),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
