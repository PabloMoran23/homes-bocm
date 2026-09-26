#!/usr/bin/env python3
"""Genera JSON + HTML del mapa de onboarding municipios (cola queue.yaml)."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1]
if str(POC_ROOT) not in sys.path:
    sys.path.insert(0, str(POC_ROOT))

from municipio.export_admin import build_municipio_admin_payload  # noqa: E402

OUT_JSON = POC_ROOT / "tools" / "municipio-onboarding-map.json"
OUT_HTML = POC_ROOT / "tools" / "municipio-onboarding-map.html"
GEOREF_CACHE = POC_ROOT / "tools" / ".cache-spain-municipios-georef.json"
HTML_TEMPLATE = POC_ROOT / "tools" / "municipio-onboarding-map.template.html"

ODS_URL = "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/georef-spain-municipio/records"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def compute_stage(row: dict) -> str:
    status = row.get("status")
    if status == "skipped":
        return "skipped"
    if status == "failed":
        return "failed"
    if status == "in_progress":
        return "in_progress"
    if row.get("openPrUrl"):
        return "pr_abierta"
    if status == "done":
        if row.get("parityOverall") == "ok" and row.get("hasAdapter"):
            return "done_ok"
        if row.get("hasAdapter"):
            return "done_adapter"
        if row.get("hasManifest"):
            return "done_manifest"
        return "done"
    if row.get("blockedReason") == "manifest_en_main" or row.get("hasManifest"):
        return "manifest_pendiente"
    return "pending"


STAGE_LABELS = {
    "done_ok": "Hecho (parity OK)",
    "done_adapter": "Hecho (adapter)",
    "done_manifest": "Hecho (solo manifest)",
    "done": "Hecho",
    "pr_abierta": "PR abierta",
    "manifest_pendiente": "Manifest sin merge",
    "in_progress": "En progreso",
    "pending": "Pendiente",
    "failed": "Fallido",
    "skipped": "Omitido (Madrid SIGMA)",
}


def fetch_georef() -> list[dict]:
    if GEOREF_CACHE.is_file():
        return json.loads(GEOREF_CACHE.read_text(encoding="utf-8"))

    rows: list[dict] = []
    offset = 0
    limit = 100
    while True:
        qs = urllib.parse.urlencode(
            {
                "limit": limit,
                "offset": offset,
                "select": "mun_name,prov_name,geo_point_2d",
            }
        )
        with urllib.request.urlopen(f"{ODS_URL}?{qs}", timeout=60) as resp:
            payload = json.loads(resp.read().decode())
        batch = payload.get("results") or []
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        if offset >= int(payload.get("total_count") or 0):
            break

    GEOREF_CACHE.parent.mkdir(parents=True, exist_ok=True)
    GEOREF_CACHE.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def build_geo_index(georef: list[dict]) -> tuple[dict, dict]:
    by_name_prov: dict[tuple[str, str], dict] = {}
    by_name: dict[str, list[dict]] = {}
    for rec in georef:
        name = rec.get("mun_name") or ""
        prov = rec.get("prov_name") or ""
        pt = rec.get("geo_point_2d") or {}
        lat, lon = pt.get("lat"), pt.get("lon")
        if lat is None or lon is None:
            continue
        key = (norm(name), norm(prov))
        by_name_prov[key] = {"lat": lat, "lon": lon, "mun_name": name, "prov_name": prov}
        nk = norm(name)
        by_name.setdefault(nk, []).append(by_name_prov[key])
    return by_name_prov, by_name


def match_coords(row: dict, by_name_prov: dict, by_name: dict) -> tuple[float | None, float | None, str | None]:
    nombre = row.get("nombre") or ""
    prov = row.get("provincia") or ""
    key = (norm(nombre), norm(prov))
    hit = by_name_prov.get(key)
    if hit:
        return hit["lat"], hit["lon"], "name+prov"
    nk = norm(nombre)
    cands = by_name.get(nk) or []
    if len(cands) == 1:
        return cands[0]["lat"], cands[0]["lon"], "name"
    # slug heuristics: valencia vs valència, etc.
    slug = norm(row.get("slug") or "").replace("del", "").replace("de", "")
    for c in cands:
        if norm(c["mun_name"]) == slug or slug in norm(c["mun_name"]):
            return c["lat"], c["lon"], "slug"
    return None, None, None


def enrich(payload: dict, georef: list[dict]) -> dict:
    by_name_prov, by_name = build_geo_index(georef)
    points: list[dict] = []
    unmatched: list[str] = []

    for row in payload["municipios"]:
        stage = compute_stage(row)
        lat, lon, match = match_coords(row, by_name_prov, by_name)
        item = {
            **row,
            "stage": stage,
            "stageLabel": STAGE_LABELS.get(stage, stage),
            "lat": lat,
            "lon": lon,
            "geoMatch": match,
        }
        if lat is None:
            unmatched.append(row["slug"])
        points.append(item)

    by_stage: dict[str, int] = {}
    by_ccaa: dict[str, dict] = {}
    for p in points:
        by_stage[p["stage"]] = by_stage.get(p["stage"], 0) + 1
        ccaa = p.get("comunidadLabel") or p.get("comunidadAutonoma")
        bucket = by_ccaa.setdefault(
            ccaa,
            {"total": 0, "done": 0, "pending": 0, "pr_abierta": 0, "skipped": 0},
        )
        bucket["total"] += 1
        if p["status"] == "done":
            bucket["done"] += 1
        elif p["status"] == "pending":
            bucket["pending"] += 1
        if p["stage"] == "pr_abierta":
            bucket["pr_abierta"] += 1
        if p["status"] == "skipped":
            bucket["skipped"] += 1

    return {
        "generatedAt": payload["generatedAt"],
        "queueUpdatedAt": payload.get("queueUpdatedAt"),
        "summary": {
            **payload["summary"],
            "byStage": by_stage,
            "withGeo": len(points) - len(unmatched),
            "withoutGeo": len(unmatched),
            "pctDone": round(
                100 * by_stage.get("done_ok", 0)
                / max(1, payload["summary"]["total"] - by_stage.get("skipped", 0)),
                1,
            ),
        },
        "byComunidadStats": by_ccaa,
        "stageLabels": STAGE_LABELS,
        "openPrsBySlug": payload.get("openPrsBySlug") or {},
        "next": payload.get("next"),
        "scrappers": {
            "framework": "scrappers/",
            "verified": ["benalmadena_29039"],
            "lastRun": "2026-05-09",
            "note": "Pipeline PDF separado; no conectado a queue.yaml",
        },
        "automations": {
            "onboardCron": "0 */4 * * *",
            "mergeCron": "0 9 */3 * *",
            "openPrs": payload["summary"].get("openPrs", 0),
        },
        "municipios": points,
        "unmatchedSlugs": unmatched[:30],
    }


def embed_html(data: dict) -> str:
    template = HTML_TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False)
    return template.replace("/*__DATA__*/", f"const MAP_DATA = {blob};")


def main() -> int:
    print("Cargando cola + manifests…", file=sys.stderr)
    payload = build_municipio_admin_payload()
    print("Descargando georef municipios (cache local)…", file=sys.stderr)
    georef = fetch_georef()
    data = enrich(payload, georef)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_HTML.write_text(embed_html(data), encoding="utf-8")
    print(f"JSON → {OUT_JSON}")
    print(f"HTML → {OUT_HTML}")
    print(
        f"{data['summary']['withGeo']}/{data['summary']['total']} con coordenadas; "
        f"{data['summary']['withoutGeo']} sin match",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
