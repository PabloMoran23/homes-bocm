from __future__ import annotations

import hashlib
import html
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
from municipio.geometry import geometry_centroid, record_geometry

LIFERAY_BASE = "https://www.aytosalamanca.es"
SEDE_BASE = "https://www.aytosalamanca.gob.es"
MUNICIPIO = "Salamanca"
ID_PREFIX = "salamanca"

TABLON_URL = f"{SEDE_BASE}/es/edictos/"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/?APP_CODE=STA&PAGE_CODE=CATALOGO"
SIUCYL_WFS = "https://idecyl.jcyl.es/geoserver/urbanismo/wfs"

DEFAULT_SEMILLAS = [
    f"{LIFERAY_BASE}/urbanismo-vivienda-y-obras/planes-tramitacion",
    f"{LIFERAY_BASE}/archivo-urban%C3%ADstico",
    f"{LIFERAY_BASE}/urbanismo-vivienda-y-obras",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|demolici[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|sector|estudio de detalle|urbanizaci[oó]n|expropiaci[oó]n|peri|"
    r"normalizaci[oó]n|junta de compensaci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_STA = re.compile(r"(\d{4})/(\d{2})/(\d{2})")
RE_LIFERAY_PATH = re.compile(r'href="(/w/[^"#?]+)"', re.I)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"SU[-\s]?NC\.?\s*(?:N[ºo°]\.?\s*)?\d+(?:[-/]\d+)?|"
    r"SUNC[-\s]?\d+(?:[-/]\d+)?|"
    r"SECTOR\s+[A-Z]{1,4}|"
    r"PERI\s+acci[oó]n\s*(?:n[ºo°]\.?\s*)?\d+"
    r")\b",
)
RE_EXPEDIENTE = re.compile(
    r"(?i)\b(?:expte\.?|expediente)\s*[:.]?\s*([0-9]+/[0-9]{4}/[A-Z]+|[0-9]+/[0-9]{4}/[a-z]+)",
)
RE_CATALOGO_ITEM = re.compile(
    r'\{"dboid":"(\d+)","code":"[^"]*","name":"([^"]+)"',
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_sta(text: str) -> str | None:
    m = RE_FECHA_STA.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", " ", code)
    code = code.replace("SU NC", "SU-NC")
    code = code.replace("SU-NC ", "SU-NC.")
    code = re.sub(r"SU-NC\.?\s*N[ºO°]\.?\s*", "SU-NC.", code)
    code = re.sub(r"SUNC\s*", "SUNC-", code)
    code = re.sub(r"SUNC-(\d+)-(\d+)", r"SUNC-\1-\2", code)
    if re.fullmatch(r"SU-NC\.(\d+)", code):
        return code
    if re.fullmatch(r"SUNC-\d+(?:-\d+)?", code):
        return code
    if re.fullmatch(r"SECTOR [A-Z]{1,4}", code):
        return code
    return code


def _sector_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_SECTOR_CODE.finditer(text or ""):
        code = _normalize_sector_code(m.group(1))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


class SalamancaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay urbanismo + STA tablón/catálogo; geometría parcial vía SIUCyL WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or LIFERAY_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.liferay_base = str(self.config.get("liferay_base") or LIFERAY_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.semilla_urls = list(self.config.get("semilla_urls") or DEFAULT_SEMILLAS)
        self._sector_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-salamanca/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_liferay(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.liferay_base}{path if path.startswith('/') else '/' + path}"

    def _abs_sede(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.sede_base}{path if path.startswith('/') else '/' + path}"

    def _parse_tablon_rows(self, html_text: str) -> list[dict[str, Any]]:
        m = re.search(r"var metadata_TABLON_EDICTOS_LISTADO = ({.*?}),\s*\n", html_text, re.S)
        if not m:
            return []
        blob = m.group(1)
        rows: list[dict[str, Any]] = []
        pat = re.compile(
            r'\{"data":\[\{"value":"([^"]+)"\},\{"value":"([^"]+)","linkHref":"([^"]+)"[^}]*\},\{"value":"([^"]+)"\}\]\}',
        )
        for match in pat.finditer(blob):
            fecha_raw, desc_raw, link, cat_raw = match.groups()
            desc = html.unescape(desc_raw)
            rows.append(
                {
                    "fecha": _parse_fecha_sta(fecha_raw) or _parse_fecha_dmy(fecha_raw),
                    "titulo": desc[:500],
                    "categoria": html.unescape(cat_raw),
                    "url": self._abs_sede(link),
                    "origen": "tablon_edictos",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            return self._parse_tablon_rows(self._fetch(self.tablon_url))
        except urllib.error.URLError:
            return []

    def _collect_catalogo_tramites(self) -> list[dict[str, Any]]:
        try:
            html_text = self._fetch(self.catalogo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for dboid, name in RE_CATALOGO_ITEM.findall(html_text):
            if dboid in seen:
                continue
            seen.add(dboid)
            title = html.unescape(name).strip()
            if not RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
                continue
            url = (
                f"{self.sede_base}/sta/CarpetaPublic/?APP_CODE=STA&PAGE_CODE=CATALOGO&DETALLE={dboid}"
            )
            rows.append({"titulo": title[:500], "url": url, "origen": "catalogo_sta"})
        return rows

    def _collect_liferay_links(self) -> list[dict[str, Any]]:
        by_path: dict[str, dict[str, Any]] = {}
        for seed in self.semilla_urls:
            try:
                html_text = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for m in RE_LIFERAY_PATH.finditer(html_text):
                path = unescape(m.group(1))
                if not RE_PROYECTO.search(path):
                    continue
                by_path[path] = {
                    "path": path,
                    "url": self._abs_liferay(path),
                    "origen": "liferay_semilla",
                }
        return list(by_path.values())

    def _page_title(self, html_text: str, fallback: str = "") -> str:
        for pat in (
            r'<meta\s+property="og:title"\s+content="([^"]+)"',
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html_text, re.I | re.S)
            if m:
                title = _strip_html(m.group(1))
                title = re.sub(r"\s*-\s*Ayto Salamanca\s*$", "", title, flags=re.I).strip()
                if title:
                    return title[:500]
        return fallback[:500]

    def _page_fecha(self, html_text: str, fallback: str | None = None) -> str | None:
        m = re.search(r"Fecha Web:\s*&nbsp;(\d{1,2}/\d{1,2}/\d{4})", html_text, re.I)
        if m:
            return _parse_fecha_dmy(m.group(1))
        m = re.search(r"Fecha B\.O\.C\.Y\.L:\s*&nbsp;(\d{1,2}/\d{1,2}/\d{4})", html_text, re.I)
        if m:
            return _parse_fecha_dmy(m.group(1))
        return fallback

    def _enrich_liferay_page(self, row: dict[str, Any]) -> dict[str, Any]:
        try:
            html_text = self._fetch(row["url"])
        except urllib.error.URLError:
            return row
        title = self._page_title(html_text, row.get("titulo") or row["path"])
        fecha = self._page_fecha(html_text, row.get("fecha"))
        expte_m = RE_EXPEDIENTE.search(html_text) or RE_EXPEDIENTE.search(title)
        out = {**row, "titulo": title, "fecha": fecha}
        if expte_m:
            out["expte"] = expte_m.group(1)
        return out

    def _wfs_sector_geometry(self, sector_code: str) -> tuple[dict[str, Any] | None, str | None]:
        if sector_code in self._sector_cache:
            hit = self._sector_cache[sector_code]
            if hit:
                return hit["geom_geojson"], hit["geometry_source_url"]
            return None, None

        cql = f"n_mun='Salamanca' AND n_num_sect='{sector_code.replace(chr(39), chr(39)+chr(39))}'"
        qs = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": "urbanismo:plau_cyl_sectores",
                "count": "1",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "CQL_FILTER": cql,
            }
        )
        url = f"{SIUCYL_WFS}?{qs}"
        geom: dict[str, Any] | None = None
        try:
            time.sleep(self.delay_s)
            req = urllib.request.Request(url, headers={"User-Agent": self.config.get("user_agent", "poc-bocm-salamanca/1.0")})
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            feats = data.get("features") or []
            if feats and isinstance(feats[0], dict):
                geom = feats[0].get("geometry")
        except (urllib.error.URLError, json.JSONDecodeError, KeyError):
            geom = None

        if isinstance(geom, dict) and geom.get("type"):
            self._sector_cache[sector_code] = {"geom_geojson": geom, "geometry_source_url": url}
            return geom, url
        self._sector_cache[sector_code] = None
        return None, None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "expte", "url"))
        for code in _sector_codes_from_text(blob):
            geom, source_url = self._wfs_sector_geometry(code)
            if not geom:
                continue
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = source_url
            rec["coord_source"] = "portal_geometry_centroid"
            rec["sector_code"] = code
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            return

    def _tipo_proyecto(self, blob: str) -> str:
        if re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            return "información pública"
        if re.search(r"(?i)convenio urban", blob):
            return "convenio"
        if re.search(r"(?i)plan parcial|estudio de detalle|modificaci[oó]n.*pgou|pgou", blob):
            return "planeamiento"
        if re.search(r"(?i)licencia", blob):
            return "licencia"
        if re.search(r"(?i)aprobaci[oó]n", blob):
            return "aprobación"
        return "urbanismo"

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "categoria"))
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "tablon_edictos" and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "catalogo_sta" and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expte") or row.get("url") or row.get("path") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": self._tipo_proyecto(blob),
            "url": row.get("url") or self.liferay_base,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expte"):
            rec["expte"] = row["expte"]
        if row.get("categoria"):
            rec["categoria"] = row["categoria"]
        self._attach_geometry(rec)
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "categoria"))
        if row.get("origen") == "catalogo_sta":
            if not RE_LICENCIA.search(blob):
                return None
        elif not RE_LICENCIA.search(blob):
            return None
        key = row.get("expte") or row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia" if row.get("origen") == "tablon_edictos" else "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("url") or self.sede_base,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("origen") == "catalogo_sta":
            rec["nota"] = "Página informativa de trámite; no concesión publicada en tablón"
        if row.get("expte"):
            rec["expte"] = row["expte"]
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_tablon():
            rec = self._to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_catalogo_tramites():
            rec = self._to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_edictos"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_sta"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._to_proyecto(item))
        for item in self._collect_liferay_links():
            enriched = self._enrich_liferay_page(item)
            enriched["titulo"] = enriched.get("titulo") or _strip_html(enriched["path"].split("/")[-1].replace("-", " "))
            add(self._to_proyecto(enriched))
        for item in self._collect_catalogo_tramites():
            add(self._to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_edictos"),
            "liferay": sum(1 for r in rows if r.get("origen") == "liferay_semilla"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_sta"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
