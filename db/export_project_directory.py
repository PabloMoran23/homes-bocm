#!/usr/bin/env python3
"""Exporta el directorio web desde Supabase (solo lectura).

SUPABASE_DB_URL=... python3 db/export_project_directory.py --municipios referencia.json
La referencia es una lista con mun_name, prov_name y geo_point_2d (georef Spain).
No consulta Supabase durante el build ni durante la navegación del directorio.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import unicodedata

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]

# Equivalencias de nombres oficiales/castellanos presentes en nuestras fuentes.
NAME_ALIASES = {
    "alboraya": "alboraia", "alcoy": "alcoi", "benicasim": "benicassim",
    "burriana": "borriana", "castellon-de-la-plana": "castello-de-la-plana",
    "elche": "elx", "javea": "xabia", "sagunto": "sagunt", "mogente": "moixent",
    "el-boalo-cerceda-mataelpino": "el-boalo", "la-cisterniga": "cisterniga",
}

NON_URBAN_TITLE = re.compile(
    r"registro de animales|domiciliaci[oó]n de tributos|calendario fiscal|"
    r"oferta p[uú]blica de empleo|bolsa de (?:trabajo|empleo)|proceso selectivo|"
    r"provisi[oó]n de plazas|concejales electos|bono infantil|"
    r"celebra (?:la maya|las fiestas)|celebraci[oó]n de evento|"
    r"prevenir robos|franja horaria para los menores|plan de transici[oó]n a la nueva normalidad",
    re.I,
)


def exclusion_reason(row, title):
    if not title:
        return "sin_titulo"
    if row.get("investigado"):
        return None
    if row.get("bocm_es_relevante") is False:
        return "marcado_no_relevante"
    if re.match(r"^(formulario|impreso|modelo de solicitud|solicitud permiso obras|autoliquidaci[oó]n|tasas? urban[ií]sticas)\b", title, re.I):
        return "formulario_o_tramite_generico"
    if row.get("fuente") == "ayuntamiento" and NON_URBAN_TITLE.search(title):
        return "noticia_o_tramite_ajeno_al_urbanismo"
    return None


def slug(text):
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


def names(text):
    # Nombres bilingües y artículos pospuestos del nomenclátor.
    variants = {text}
    for name in (text or "").split("/"):
        variants.add(name)
        if ", " in name:
            base, article = name.rsplit(", ", 1)
            variants.add(f"{article} {base}")
    return {slug(name) for name in variants if name}


def territory(row, reference, by_name):
    candidates = set()
    for name in (row.get("municipio_nombre"), row.get("municipio"), row.get("municipio_slug")):
        for key in names(name or ""):
            key = NAME_ALIASES.get(key, key)
            candidates.update(by_name.get(key, []))
    if not candidates and row.get("expediente_grupo"):
        candidates.update(by_name.get("madrid", []))
    if len(candidates) > 1:
        province = slug(row.get("provincia"))
        matching = {i for i in candidates if f'-{slug(reference[i]["prov_name"])}-' in f'-{province}-'}
        if matching:
            candidates = matching
    if len(candidates) > 1:
        community = slug(row.get("comunidad_autonoma"))
        matching = {i for i in candidates if slug(reference[i]["prov_name"]) == community}
        if matching:
            candidates = matching
    if len(candidates) > 1 and row.get("municipio_lat") is not None and row.get("municipio_lng") is not None:
        lat, lng = float(row["municipio_lat"]), float(row["municipio_lng"])
        distances = sorted((math.hypot(lat-reference[i]["geo_point_2d"]["lat"], lng-reference[i]["geo_point_2d"]["lon"]), i) for i in candidates)
        if distances[0][0] < 0.2 and distances[1][0] > distances[0][0] * 2:
            candidates = {distances[0][1]}
    if len(candidates) != 1:
        return None
    return reference[next(iter(candidates))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--municipios", type=Path, default=ROOT / "tools/.cache-spain-municipios-georef.json")
    args = parser.parse_args()
    reference = json.loads(args.municipios.read_text())
    by_name = defaultdict(set)
    for i, place in enumerate(reference):
        for key in names(place["mun_name"]):
            by_name[key].add(i)

    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Falta SUPABASE_DB_URL o DATABASE_URL")
    with psycopg2.connect(url, connect_timeout=15) as conn:
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id, p.bocm_primary_id, p.expediente_grupo,
                       p.denominacion, p.bocm_title, p.resumen_contenido, p.bocm_resumen,
                       p.municipio, p.municipio_slug, p.programa_id, p.sector_key, p.fuente, p.bocm_es_relevante,
                       p.tipo_figura, p.bocm_tipo_instrumento, p.fase, p.bocm_estado_tramitacion,
                       m.nombre AS municipio_nombre, m.provincia, m.comunidad_autonoma,
                       m.lat AS municipio_lat, m.lng AS municipio_lng,
                       EXISTS (SELECT 1 FROM homes.proyecto_investigacion i WHERE i.proyecto_id=p.id) AS investigado,
                       (SELECT left(i.resumen, 240) FROM homes.proyecto_investigacion i WHERE i.proyecto_id=p.id ORDER BY i.investigado_at DESC, i.id DESC LIMIT 1) AS investigacion_resumen
                FROM homes.proyecto p LEFT JOIN homes.municipio m ON m.slug=p.municipio_slug
                ORDER BY p.id
            """)
            rows = cur.fetchall()

    projects, municipalities, provinces = [], {}, {}
    skipped = Counter()
    unresolved = Counter()
    for row in rows:
        title = re.sub(r"\s+", " ", row["denominacion"] or row["bocm_title"] or "").strip()
        # No excluir todos los PDF: muchos contienen el título real del planeamiento.
        reason = exclusion_reason(row, title)
        if reason:
            skipped[reason] += 1
            continue
        place = territory(row, reference, by_name)
        if place is None:
            skipped["territorio_sin_resolver"] += 1
            unresolved[row["municipio_slug"] or row["municipio"] or "sin municipio"] += 1
            continue
        province = slug(place["prov_name"])
        municipality = slug(place["mun_name"])
        key = f"{province}/{municipality}"
        provinces[province] = {"slug": province, "name": place["prov_name"]}
        municipalities[key] = {"slug": municipality, "name": place["mun_name"], "province": province,
                               "center": [place["geo_point_2d"]["lon"], place["geo_point_2d"]["lat"]]}
        project_id = row["id"]
        if re.fullmatch(r"\d+/\d+/\d+", project_id):
            a, b, n = project_id.split("/")
            canonical = f"{a}-{b}-{n.zfill(5)}"
        else:
            canonical = project_id
        aliases = sorted({project_id, row["bocm_primary_id"]} - {None, canonical})
        summary = re.sub(r"\s+", " ", row["investigacion_resumen"] or row["resumen_contenido"] or row["bocm_resumen"] or "").strip()
        projects.append({
            "id": canonical, "aliases": aliases, "title": title[:220], "municipality": key,
            "summary": summary[:240] if summary != title else "",
            "type": row["tipo_figura"] or row["bocm_tipo_instrumento"] or "",
            "status": row["fase"] or row["bocm_estado_tramitacion"] or "",
            "researched": row["investigado"],
            "group": str(row["programa_id"] or row["sector_key"] or ""),
        })

    ids = [p["id"] for p in projects]
    if len(ids) != len(set(ids)):
        raise SystemExit("Hay URLs canónicas duplicadas; no se sobrescribe el directorio")
    data = {"generatedAt": datetime.now(timezone.utc).isoformat(),
            "provinces": sorted(provinces.values(), key=lambda p: p["slug"]),
            "municipalities": sorted(municipalities.values(), key=lambda m: (m["province"], m["slug"])),
            "projects": projects}
    target = ROOT / "web/data/project-directory.json"
    target.parent.mkdir(exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(target)
    print(json.dumps({"total": len(rows), "exported": len(projects), "municipalities": len(municipalities), "provinces": len(provinces), "excluded": dict(skipped), "unresolved": dict(unresolved)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
