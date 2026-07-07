from __future__ import annotations

import hashlib
import html as htmlmod
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, unquote

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.aytosalamanca.es"
SEDE_BASE = "https://www.aytosalamanca.gob.es"
MUNICIPIO = "Salamanca"
ID_PREFIX = "salamanca"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=TABLON_EDICTOS"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
VISOR_PGOU_URL = f"{WEB_BASE}/w/visor-pgou-1"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/inicio",
    f"{WEB_BASE}/urbanismo-vivienda-y-obras",
    f"{WEB_BASE}/urbanismo-vivienda-y-obras/planes-tramitacion",
    f"{WEB_BASE}/archivo-urban%C3%ADstico",
    VISOR_PGOU_URL,
]

LICENCIA_TRAMITE_NAMES: tuple[str, ...] = (
    "Licencia de obra mayor",
    "Licencia de demolición o derribo total o parcial",
    "Licencia de parcelación y/o segregación",
    "Licencia de primera utilización / declaración responsable",
    "Licencia de apertura de calicatas o zanjas y obras en el pavimento de las vías públicas",
    "Prórroga de licencias de obras, ITC o actos comunicados",
    "Solicitud de vado permanente",
    "Comunicación de apertura con obras de adecuación del establecimiento",
    "Solicitud de autorización para instalación de grua torre",
    "Solicitud de autorización ocupación de vía pública vallas y andamios",
)

PROYECTO_TRAMITE_PATTERNS: tuple[str, ...] = (
    "Solicitud de Aprobación de Planeam",
    "Información urbanística",
    "Segregación, división y agregación de fincas",
    "Actas de alineaciones y rasantes",
    "Modificación del Plan General",
    "Plan Parcial",
    "Plan Especial",
    "Estudio de Detalle",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia (?:de |municipal|ambiental|urban)|solicitud de licencia|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|"
    r"obra mayor|vado|calicatas|demolici[oó]n|parcelaci[oó]n|segregaci[oó]n|"
    r"primera (?:ocupaci[oó]n|utilizaci)|pr[oó]rroga de licencias)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto de actuaci|modificaci[oó]n|"
    r"reparcel|estudio de detalle|sector su[- ]?nc|junta de compensaci|"
    r"evaluaci[oó]n ambiental|aprobaci[oó]n (?:inicial|definitiva)|"
    r"normalizaci[oó]n de fincas|suelo urbano|alineaciones y rasantes)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|plaza de|empleo p[uú]blico|"
    r"presupuest|pleno|junta de gobierno|convocatoria del pleno|acta de la sesi|"
    r"subvenci[oó]n deportiv|empadron|tribut|matrimonio civil|teleasistencia|"
    r"recogida de voluminosos|ropa usada|herederos|notoriedad)",
)
RE_FECHA_YMD_SLASH = re.compile(r"\b((?:19|20)\d{2})/(\d{2})/(\d{2})\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,4}/\d{4}[^/\s]*)")
RE_WEB_LINK = re.compile(r'href="(/w/[^"#?]+)"', re.I)
RE_H1 = re.compile(r'<h1[^>]*>([^<]+)</h1>', re.I)
RE_SR_H1 = re.compile(
    r'<h1[^>]*class="[^"]*sr-only[^"]*"[^>]*>([^<]+)</h1>',
    re.I,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_ymd_slash(text: str) -> str | None:
    m = RE_FECHA_YMD_SLASH.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_text(text: str) -> str | None:
    return _parse_fecha_ymd_slash(text) or _parse_fecha_dmy(text) or _parse_fecha_iso(text)


def _clean_title(text: str) -> str:
    t = unescape(htmlmod.unescape(text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t[:500]


def _title_from_slug(path: str) -> str:
    slug = path.rstrip("/").rsplit("/", 1)[-1]
    slug = unquote(slug)
    slug = slug.replace("-", " ").replace(".", " ")
    return _clean_title(slug)


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "convenio urban" in n:
        return "convenio urbanístico"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "plan parcial" in n or "plan especial" in n:
        return "plan parcial"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "evaluaci" in n and "ambiental" in n:
        return "evaluación ambiental"
    if "reparcel" in n or "actuaci" in n:
        return "actuación urbanística"
    if "pgou" in n or "planeam" in n:
        return "planeamiento"
    return "urbanismo"


class SalamancaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay web (IP/planeamiento) + sede STA (tablón + catálogo trámites)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-salamanca/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "aytosalamanca.gob.es" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    @staticmethod
    def _extract_tablon_rows(html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        pattern = re.compile(
            r'\{"data":\[\{"value":"([^"]*)"\},\{"value":"([^"]*)","linkHref":"([^"]*)"[^}]*\},\{"value":"([^"]*)"\}\]\}',
        )
        for fecha, desc_raw, link_href, cat_raw in pattern.findall(html):
            desc = _clean_title(htmlmod.unescape(desc_raw))
            cat = _clean_title(htmlmod.unescape(cat_raw))
            url = urljoin(f"{SEDE_BASE}/sta/CarpetaPublic/", link_href)
            dboid_m = re.search(r"DBOID=(\d+)", link_href)
            rows.append(
                {
                    "fecha": _parse_fecha_ymd_slash(fecha),
                    "titulo": desc,
                    "categoria": cat,
                    "url": url,
                    "dboid": dboid_m.group(1) if dboid_m else None,
                    "origen": "tablon_edictos",
                }
            )
        return rows

    @staticmethod
    def _extract_catalog_items(html: str) -> list[dict[str, Any]]:
        needle = "var dataset_CATSERV = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        items: list[dict[str, Any]] = []
        for row in data:
            dboid = str(row.get("dboid") or "")
            name = _clean_title(htmlmod.unescape(str(row.get("name") or "")))
            if not name or not dboid:
                continue
            url = (
                f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?"
                f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
            )
            items.append({"titulo": name, "url": url, "dboid": dboid, "origen": "catalogo_tramites"})
        return items

    def _collect_web_pages(self) -> list[dict[str, Any]]:
        seen_paths: set[str] = set()
        queue: list[str] = list(self.seed_pages)
        records: list[dict[str, Any]] = []

        while queue and len(seen_paths) < 80:
            page_url = queue.pop(0)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            for href in RE_WEB_LINK.findall(html):
                if href in seen_paths:
                    continue
                slug_title = _title_from_slug(href)
                blob = slug_title.lower()
                if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                seen_paths.add(href)
                full_url = urljoin(f"{self.web_base}/", href)
                records.append(
                    {
                        "titulo": slug_title,
                        "url": full_url,
                        "fecha": _fecha_from_text(slug_title),
                        "origen": "web_liferay",
                        "path": href,
                    }
                )
                if href.count("/") <= 2 and len(seen_paths) < 80:
                    queue.append(full_url)

            for href in RE_WEB_LINK.findall(html):
                full = urljoin(f"{self.web_base}/", href)
                if full not in queue and href not in seen_paths and len(queue) < 40:
                    if any(k in unquote(href).lower() for k in ("urban", "pgou", "convenio", "planeam", "informaci")):
                        queue.append(full)

        return records

    def _enrich_web_page(self, rec: dict[str, Any]) -> dict[str, Any]:
        try:
            html = self._fetch(rec["url"])
        except urllib.error.URLError:
            return rec
        h1 = RE_SR_H1.search(html) or RE_H1.search(html)
        if h1:
            rec["titulo"] = _clean_title(h1.group(1))
        rec["fecha"] = rec.get("fecha") or _fecha_from_text(html[:8000])
        pdf_m = RE_PDF.search(html)
        if pdf_m:
            rec["pdf_url"] = urljoin(rec["url"], pdf_m.group(1))
        return rec

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        names_lower = {n.lower() for n in LICENCIA_TRAMITE_NAMES}
        for item in self._extract_catalog_items(html):
            if item["titulo"].lower() not in names_lower:
                continue
            rows.append(item)
        return rows

    def _collect_proyecto_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_catalog_items(html):
            titulo = item["titulo"]
            if any(p.lower() in titulo.lower() for p in PROYECTO_TRAMITE_PATTERNS):
                rows.append(item)
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('categoria', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        if RE_NOISE.search(blob) and not re.search(r"(?i)licencia", blob):
            return None
        key = row.get("dboid") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"expte": m.group(1)} if (m := RE_EXPTE.search(row["titulo"])) else {}),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Trámite del catálogo sede; no concesión publicada",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = titulo
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("dboid") or row.get("pdf_url") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if m := RE_EXPTE.search(titulo):
            rec["expte"] = m.group(1)
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

        try:
            tablon_html = self._fetch(TABLON_URL, use_sede_ssl=True)
            for item in self._extract_tablon_rows(tablon_html):
                rec = self._tablon_to_licencia(item)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        except urllib.error.URLError:
            pass

        for item in self._collect_licencia_tramites():
            rec = self._tramite_to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_edictos"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        stats = self.backfill_licencias(out_jsonl)
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        try:
            tablon_html = self._fetch(TABLON_URL, use_sede_ssl=True)
            for item in self._extract_tablon_rows(tablon_html):
                add(self._row_to_proyecto(item))
        except urllib.error.URLError:
            pass

        for item in self._collect_proyecto_tramites():
            add(self._row_to_proyecto(item))

        for item in self._collect_web_pages():
            enriched = self._enrich_web_page(item)
            add(self._row_to_proyecto(enriched))

        add(
            {
                "titulo": "Visor PGOU de Salamanca",
                "url": VISOR_PGOU_URL,
                "fecha": None,
                "origen": "visor_pgou",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "web": sum(1 for r in rows if r.get("origen") == "web_liferay"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_edictos"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
