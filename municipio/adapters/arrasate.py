from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.arrasate.eus"
EXPOSICION_ES = (
    f"{BASE}/es/ayuntamiento/transparencia/decisiones-normativa-y-documentacion/"
    "documentacion-en-exposicion-publica"
)

RE_CHILD_LINK = re.compile(
    rf'href="({re.escape(EXPOSICION_ES)}/([^"/?#]+))"',
    re.I,
)
RE_H1 = re.compile(
    r'<h1[^>]*class="documentFirstHeading"[^>]*>([^<]+)</h1>',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="(https://www\.arrasate\.eus/[^"]+\.pdf)"',
    re.I,
)
RE_PDF_FECHA = re.compile(r"(?:gaoko-iragarkia_|iragarki[a-z_]*_)(\d{4})_(\d{2})_(\d{2})\.pdf", re.I)
RE_YEAR_IN_TITLE = re.compile(r"\b(20\d{2})\b")

RE_PROY_URBAN = re.compile(
    r"(?i)(urbaniz|planeam|ordenaci[oó]n|plan (?:parcial|especial)|pgou|convenio|"
    r"reparcel|actuaci[oó]n integrada|[aá]mbito|proyecto de reurbanizaci[oó]n|"
    r"plan especial|documento (?:lan|peou)|edificabilidad|suelo)",
)
RE_LIC = re.compile(
    r"(?i)(licencia|licencias|actividad clasificada|comunicaci[oó]n previa|declaraci[oó]n responsable)",
)
RE_EXCLUDE_PROY = re.compile(r"(?i)(movilidad|diagn[oó]stico educativo)")


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"arrasate-{prefix}-{h}"


class ArrasateAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone (documentación en exposición pública) + ArcGIS REST (planeamiento PGOU)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = str(self.config.get("user_agent", "poc-bocm-arrasate/1.0"))
        self.exposicion_url = str(self.config.get("exposicion_url", EXPOSICION_ES))
        self.arcgis_query = str(
            self.config.get(
                "arcgis_query_url",
                (
                    "https://gis.arrasate.eus/server/rest/services/"
                    "Arrasate_planeamendua/Arrasate_planeamendua/MapServer/21/query"
                ),
            )
        )
        self.arcgis_page_size = int(self.config.get("arcgis_page_size", 200))
        self.arcgis_max_features = int(self.config.get("arcgis_max_features", 60))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _parse_fecha_from_pdfs(self, html: str) -> str | None:
        for m in RE_PDF_HREF.finditer(html):
            href = m.group(1)
            tail = href.rsplit("/", 1)[-1]
            fm = RE_PDF_FECHA.search(tail)
            if fm:
                try:
                    return datetime(int(fm.group(1)), int(fm.group(2)), int(fm.group(3))).strftime("%Y-%m-%d")
                except ValueError:
                    pass
        return None

    def _parse_year_fallback(self, titulo: str) -> str | None:
        m = RE_YEAR_IN_TITLE.search(titulo or "")
        if m:
            return f"{m.group(1)}-01-01"
        return None

    def _list_exposicion_child_urls(self) -> list[str]:
        try:
            html = self._fetch(self.exposicion_url)
        except urllib.error.URLError:
            return []
        seen: set[str] = set()
        out: list[str] = []
        for m in RE_CHILD_LINK.finditer(html):
            url = m.group(1).rstrip("/")
            slug = m.group(2)
            if not slug or slug.lower() in {"documentacion-en-exposicion-publica"}:
                continue
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def _fetch_document_row(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None
        hm = RE_H1.search(html)
        titulo = unescape((hm.group(1) if hm else "").strip()) if hm else ""
        if not titulo:
            return None
        fecha = self._parse_fecha_from_pdfs(html) or self._parse_year_fallback(titulo)
        return {
            "titulo": titulo[:500],
            "fecha": fecha or "1970-01-01",
            "url": url,
        }

    def _arcgis_features(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while len(rows) < self.arcgis_max_features:
            params = {
                "where": "1=1",
                "returnGeometry": "true",
                # OBJECTID is not a field name on this service; use Feature "id" from GeoJSON.
                "outFields": "A01_KATEGORIA",
                "f": "geojson",
                "outSR": "4326",
                "resultRecordCount": str(self.arcgis_page_size),
                "resultOffset": str(offset),
            }
            qurl = f"{self.arcgis_query}?{urllib.parse.urlencode(params)}"
            try:
                time.sleep(self.delay_s)
                req = urllib.request.Request(qurl, headers={"User-Agent": self.ua})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, json.JSONDecodeError, OSError):
                break
            feats = raw.get("features") if isinstance(raw, dict) else None
            if not isinstance(feats, list) or not feats:
                break
            for feat in feats:
                if not isinstance(feat, dict):
                    continue
                geom = feat.get("geometry")
                props = feat.get("properties") if isinstance(feat.get("properties"), dict) else {}
                cat = str(props.get("A01_KATEGORIA") or "planeamiento")
                oid = feat.get("id")
                key = f"arcgis|21|{oid}|{cat}"
                g = geom if isinstance(geom, dict) and geom.get("type") == "Polygon" else None
                rows.append(
                    {
                        "id": _stable_id("proy", key),
                        "municipio": "Arrasate / Mondragón",
                        "titulo": f"Planeamiento PGOU — {cat}"[:500],
                        "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "tipo": "uso suelo / planeamiento (visor municipal)",
                        "url": (
                            "https://gis.arrasate.eus/portal/apps/webappviewer/"
                            "index.html?id=b6aa5004a32a471285315be80b9cd7e6"
                        ),
                        "source": "ayuntamiento",
                        "geom_geojson": g,
                        "geometry_source": "portal_visor_arcgis",
                        "geometry_source_url": qurl,
                        "coord_source": "portal_geometry_centroid",
                        "source_crs": "EPSG:4326",
                        "origen": "arcgis_pgou",
                    }
                )
                if len(rows) >= self.arcgis_max_features:
                    break
            if len(feats) < self.arcgis_page_size:
                break
            offset += self.arcgis_page_size
        return rows

    def _collect_proyectos_exposicion(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self._list_exposicion_child_urls():
            meta = self._fetch_document_row(url)
            if not meta:
                continue
            titulo = meta["titulo"]
            if RE_EXCLUDE_PROY.search(titulo):
                continue
            if not RE_PROY_URBAN.search(titulo):
                continue
            rec: dict[str, Any] = {
                "id": _stable_id("proy", url),
                "municipio": "Arrasate / Mondragón",
                "titulo": titulo,
                "fecha": meta["fecha"],
                "tipo": "documentación en exposición pública (urbanismo)",
                "url": meta["url"],
                "source": "ayuntamiento",
                "origen": "exposicion_publica",
            }
            rows.append(rec)
        return rows

    def _collect_licencias_exposicion(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self._list_exposicion_child_urls():
            meta = self._fetch_document_row(url)
            if not meta:
                continue
            titulo = meta["titulo"]
            if not RE_LIC.search(titulo):
                continue
            rec: dict[str, Any] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": meta["fecha"],
                "tipo": "licencia / solicitud (exposición pública)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": titulo[:300],
                "url": meta["url"],
                "source": "ayuntamiento",
            }
            rows.append(rec)
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_exposicion()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "exposicion_publica"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_exposicion():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_proyectos_exposicion():
            add(rec)
        for rec in self._arcgis_features():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "exposicion": sum(1 for r in rows if r.get("origen") == "exposicion_publica"),
            "arcgis": sum(1 for r in rows if r.get("origen") == "arcgis_pgou"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, after - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
