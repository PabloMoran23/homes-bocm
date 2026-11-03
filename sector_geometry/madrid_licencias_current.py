"""Fuentes municipales que sustituyen al retirado conjunto 300193 desde 2023."""
from __future__ import annotations

import csv
import io
import json
import urllib.request
import unicodedata
import re
from collections import Counter
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path

DATASETS = {
    "licencias": ("640505-0-licencias-urbanisticas-otorgadas", "640505-1-licencias-urbanisticas-otorgadas", "licencias.csv"),
    "declaraciones": ("133556-0-declaraciones-responsables", "133556-0-declaraciones-responsables", "dr.csv"),
}
MONTHS = {name: i for i, name in enumerate(("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"), 1)}
GEO_FIELDS = ("latitud", "longitud", "coordenadas_x", "coordenadas_y", "coordenada_x", "coordenada_y", "descripcin_distrito", "descripcion_barrio_bdc")


def source_date(row: dict, prefix: str) -> str:
    year = int(row[f"{prefix} - Año"])
    month = MONTHS[row[f"{prefix} - Mes"].strip().lower()]
    day = int(row[f"{prefix} - Día"])
    return date(year, month, day).isoformat()


def parse_csv(content: bytes, kind: str, *, origin: dict, locations: dict) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), delimiter=";")
    required = {"Nº_EXPEDIENTE", "TIPO", "NDP", "FECHA_ALTA", "DIRECCION"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError(f"{kind}: esquema CSV inesperado: {reader.fieldnames}")
    rows = []
    for raw in reader:
        alta = source_date(raw, "FECHA_ALTA" if kind == "licencias" else "FECHA_ALTA_EXPEDIENTE")
        grant = source_date(raw, "FECHA_FIRMA_RESOLUCION") if kind == "licencias" else None
        year = int((grant or alta)[:4])
        if kind == "licencias" and raw.get("RESOLUCION") != "Conceder":
            raise ValueError("Resolución distinta de concesión en el recurso de licencias otorgadas")
        ndp = raw["NDP"].strip()
        expediente = raw["Nº_EXPEDIENTE"].strip()
        if not ndp or not expediente:
            raise ValueError(f"{kind}: falta NDP o expediente")
        location = locations.get(ndp, {})
        rows.append({
            **{key: location[key] for key in GEO_FIELDS if location.get(key)},
            "anio_dataset": year, "fecha_de_alta": alta, "fecha_concesin": grant,
            "procedimiento": "Licencia urbanística" if kind == "licencias" else "Declaración responsable",
            "tipo_de_expediente": raw["TIPO"], "ndp_edificio": ndp,
            "tipo_via": raw.get("VIA"), "nombre_via": raw["DIRECCION"], "nmero": raw.get("Nº"),
            "unidad_responsable": raw.get("ORGANO_COMPETENTE"), "interesado": raw.get("PERSONA_INTERESADA"),
            "numero_expediente": expediente,
            "source": "madrid-opendata", "source_dataset": origin["dataset"],
            "_territorial_origin": origin, "_source_record": raw,
            "_coordinate_origin": location.get("_territorial_origin") if location else None,
        })
    if not rows:
        raise ValueError(f"{kind}: no contiene filas")
    return rows


def merge_snapshot_rows(historical: list[dict], current: list[dict]) -> tuple[list[dict], dict]:
    from sector_geometry.madrid_licencias_download import licencia_key
    from db.license_dates import parse_date

    def registration(row):
        procedure = unicodedata.normalize("NFKD", str(row.get("procedimiento") or "")).encode("ascii", "ignore").decode().lower()
        if "declaracion responsable" not in procedure:
            return None
        alta = parse_date(row.get("fecha_de_alta"))["value"]
        # A building/day match alone can conflate separate proceedings.
        kind = unicodedata.normalize("NFKD", str(row.get("tipo_de_expediente") or "")).encode("ascii", "ignore").decode().lower()
        kind = re.sub(r"[^a-z0-9]", "", kind)
        return (str(row.get("ndp_edificio") or "").strip(), alta, kind) if alta and kind else None

    # A previous full snapshot also contains current-source rows from 2022.
    # Replay their archived legacy aliases, rather than treating the previous
    # CSV row as a historical duplicate and nesting it on every refresh.
    historical = [old for row in historical
                  for old in (row.get("_source_variants", [])
                              if row.get("numero_expediente") and row.get("source_dataset") else [row])]
    current = [{**row, **({"_source_variants": list(row["_source_variants"])} if "_source_variants" in row else {})} for row in current]
    current_matches = {}
    historical_matches = Counter(registration(row) for row in historical if int(row.get("anio_dataset") or 0) < 2023)
    for row in current:
        identity = registration(row)
        if identity and int(row["anio_dataset"]) < 2023:
            current_matches.setdefault(identity, []).append(row)
    overlapping = {identity for identity, rows in current_matches.items()
                   if len(rows) == 1 and historical_matches[identity] == 1}
    merged = {}
    stats = {"historicalRowsSuperseded": 0, "duplicateRowsCollapsed": 0, "currentRows": len(current)}
    for row in historical:
        if int(row.get("anio_dataset") or 0) >= 2023:
            continue
        if registration(row) in overlapping:
            target = current_matches[registration(row)][0]
            target.setdefault("_source_variants", []).append(row)
            stats["historicalRowsSuperseded"] += 1
            continue
        key = licencia_key(row, anio=int(row["anio_dataset"]))
        if key in merged:
            prior = merged[key]
            variants = prior.get("_source_variants", []) + [{k: v for k, v in prior.items() if k != "_source_variants"}]
            row = {**row, "_source_variants": variants}
            stats["duplicateRowsCollapsed"] += 1
        merged[key] = row
    for row in current:
        key = licencia_key(row, anio=int(row["anio_dataset"]))
        if key in merged:
            if merged[key] != row:
                raise ValueError(f"Filas contradictorias para el mismo expediente y edificio: {key}")
            stats["duplicateRowsCollapsed"] += 1
        merged[key] = row
    return list(merged.values()), stats


def refresh(output_dir: Path, raw_dir: Path, jsonl_out: Path, summary_out: Path) -> dict:
    previous = []
    if jsonl_out.is_file():
        previous = [json.loads(line) for line in jsonl_out.read_text().splitlines() if line.strip()]
    # Reprocesar XLSX históricos disponibles para conservar su procedencia real.
    from sector_geometry.madrid_licencias_download import _rows_from_xlsx, _download_url_for_year
    historical_resources = {}
    for path in sorted(raw_dir.glob("licencias_urbanisticas_*.xlsx")):
        year = int(path.stem.rsplit("_", 1)[1])
        if year >= 2023:
            continue
        print(f"Reprocesando histórico {year} desde XLSX cacheado", flush=True)
        historical = _rows_from_xlsx(path, year)
        previous = [row for row in previous if int(row.get("anio_dataset") or 0) != year]
        previous.extend(historical)
        historical_resources[str(year)] = {"url": _download_url_for_year(year),
            "sha256": sha256(path.read_bytes()).hexdigest(), "downloadedThisRun": False,
            "cacheModifiedAt": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            "factualUpdatedAt": None}
    # Las coordenadas se reutilizan por identificador municipal de edificio, nunca
    # por texto de dirección. El CSV nuevo no publica coordenadas.
    locations = {}
    for row in previous:
        ndp = str(row.get("ndp_edificio") or "").strip()
        if ndp and any(row.get(key) for key in GEO_FIELDS[:6]):
            locations[ndp] = row
    current_rows = []
    resources = historical_resources
    cached = {}
    for kind, (dataset, resource, filename) in DATASETS.items():
        url = f"https://datos.madrid.es/dataset/{dataset}/resource/{resource}/download/{filename}"
        print(f"Descargando {kind}: {url}", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "homes-madrid-licencias/2.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()
        origin = {"municipio_slug": "madrid", "adapter": "madrid-opendata", "url": url,
                  "dataset": dataset, "resourceSha256": sha256(content).hexdigest()}
        records = parse_csv(content, kind, origin=origin, locations=locations)
        current_rows.extend(records)
        cached[kind] = content
        resources[kind] = {"url": url, "dataset": dataset, "sha256": origin["resourceSha256"],
                           "downloadedThisRun": True, "downloadedAt": datetime.now(timezone.utc).isoformat(),
                           "factualUpdatedAt": None, "rows": len(records)}
        print(f"{kind}: {len(records)} filas del CSV completo", flush=True)
    rows, reconciliation = merge_snapshot_rows(previous, current_rows)
    # Publicar únicamente tras descargar y validar ambos recursos.
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    summary = {"generatedAt": datetime.now(timezone.utc).isoformat(),
               "source": "datos.madrid.es: histórico 300193 y CSV completos de licencias 640505 y declaraciones responsables 133556",
               "reconciliation": reconciliation,
               "sourceSnapshot": {"mode": "current-csv-download", "resources": resources, "factualUpdatedAt": None},
               "totalRows": len(rows), "byYear": dict(Counter(str(row["anio_dataset"]) for row in rows))}
    temp = jsonl_out.with_suffix(".jsonl.tmp")
    with temp.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    temp_summary = summary_out.with_suffix(".json.tmp")
    temp_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    for kind, content in cached.items():
        (raw_dir / f"{kind}_current.csv").write_bytes(content)
    temp.replace(jsonl_out)
    temp_summary.replace(summary_out)
    return summary
