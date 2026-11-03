"""Fuentes municipales que sustituyen al retirado conjunto 300193 desde 2023."""
from __future__ import annotations

import csv
import io
import json
import urllib.request
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
        if year < 2023:
            continue  # El histórico anterior sigue procediendo del conjunto antiguo.
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
        raise ValueError(f"{kind}: no contiene filas desde 2023")
    return rows


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
    rows = [row for row in previous if int(row.get("anio_dataset") or 0) < 2023]
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
        rows.extend(records)
        cached[kind] = content
        resources[kind] = {"url": url, "dataset": dataset, "sha256": origin["resourceSha256"],
                           "downloadedThisRun": True, "downloadedAt": datetime.now(timezone.utc).isoformat(),
                           "factualUpdatedAt": None, "rows": len(records)}
        print(f"{kind}: {len(records)} filas desde 2023", flush=True)
    # Publicar únicamente tras descargar y validar ambos recursos.
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    summary = {"generatedAt": datetime.now(timezone.utc).isoformat(),
               "source": "datos.madrid.es: histórico 300193; licencias 640505 y declaraciones responsables 133556 desde 2023",
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
