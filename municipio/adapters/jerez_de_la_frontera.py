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

WEB_BASE = "https://www.jerez.es"
TABLON_API = "https://tramites.aytojerez.es/api/tablon-anuncios"
TABLON_PAGE = "https://tramites.aytojerez.es/public/general/tablon-anuncios"
SEDE_BASE = "https://www.sedeelectronica.jerez.es"
URBANISMO_TRAMITES = (
    "https://www.sedeelectronica.jerez.es/tramites?"
    "no_cache=1&tema=Urbanismo&"
    "tx_tramiteskey_tramitesfrontendkey%5Baction%5D=listurbanismo&"
    "tx_tramiteskey_tramitesfrontendkey%5Bcontroller%5D=Tramite&"
    "cHash=d8804040b9a9321c2d80946c948e7547"
)
MUNICIPIO = "Jerez de la Frontera"
ID_PREFIX = "jerez-de-la-frontera"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/webs-municipales/urbanismo/instrumentos-de-planeamiento/instrumentos-de-planeamiento-en-fase-de-informacion",
    f"{WEB_BASE}/webs-municipales/urbanismo/instrumentos-de-planeamiento/instrumentos-de-planeamiento-aprobados-definitivamente/planeamiento-general",
    f"{WEB_BASE}/webs-municipales/urbanismo/instrumentos-de-planeamiento/instrumentos-de-planeamiento-aprobados-definitivamente/planes-parciales",
    f"{WEB_BASE}/webs-municipales/urbanismo/instrumentos-de-planeamiento/instrumentos-de-planeamiento-aprobados-definitivamente/planes-especiales",
    f"{WEB_BASE}/webs-municipales/urbanismo/instrumentos-de-planeamiento/instrumentos-de-planeamiento-aprobados-definitivamente/estudios-de-detalle",
    f"{WEB_BASE}/webs-municipales/urbanismo/pgou",
    f"{WEB_BASE}/webs-municipales/urbanismo/info-publica/convenios-urbanisticos",
    f"{WEB_BASE}/webs-municipales/urbanismo/info-publica/bandos",
    f"{WEB_BASE}/webs-municipales/urbanismo/info-publica/proyectos-de-urbanizacion",
    f"{WEB_BASE}/webs-municipales/urbanismo/info-publica/urbanismo-y-obras-de-infraestructura",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|legalizaci[oó]n de obra|"
    r"rehabilitaci[oó]n de edificio|adecuaci[oó]n y ampliaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|de ordenaci[oó]n)|pgou|pou|pto|ptoe|ptopri|ptoeo|"
    r"convenio|informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|api\b|ari\b|"
    r"cambio de uso|ordenanza|avance|calificaci[oó]n|instalaci[oó]n el[eé]ctrica|"
    r"reforma.*actividad|rehabilitaci[oó]n|juntas? de compensaci[oó]n|peer\b)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"padr[oó]n|liquidaci[oó]n|recaudaci[oó]n|tribut|bajof|baja de oficio|"
    r"cobranza|citaci[oó]n para notificar|jurisdicci[oó]n voluntaria|"
    r"tracto sucesivo|tribunal calificador.*empleo)",
)
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_H3 = re.compile(r"<h3[^>]*>(.*?)</h3>", re.I | re.S)
RE_PDF_HREF = re.compile(r'href="(/fileadmin/[^"]+\.pdf[^"]*)"', re.I)
RE_TRAMITE_HREF = re.compile(r'href="(/tramites/[^"#?]+)"', re.I)
RE_TRAMITE_TITLE = re.compile(
    r'href="/tramites/([^"]+)"[^>]*>\s*<[^>]+>\s*([^<]+)',
    re.I | re.S,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dash(text: str) -> str | None:
    m = RE_FECHA_DMY_DASH.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
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


def _fecha_from_blob(text: str) -> str | None:
    d = _parse_fecha_dash(text) or _parse_fecha_dmy(text)
    if d:
        return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "ptoeo" in b or "estudio de ordenaci" in b:
        return "estudio de ordenación"
    if "ptopri" in b or "reforma interior" in b:
        return "plan de reforma interior"
    if "ptoe" in b or "estudio de detalle" in b:
        return "estudio de detalle"
    if "peer" in b or "plan especial" in b:
        return "plan especial"
    if "pou" in b and "cuartillos" in b:
        return "plan de ordenación urbana"
    if "plan parcial" in b:
        return "plan parcial"
    if "modificaci" in b and "pgou" in b:
        return "modificación PGOU"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "convenio" in b:
        return "convenio urbanístico"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "avance" in b:
        return "planeamiento"
    if "licencia" in b:
        return "licencia publicada"
    if "proyecto" in b:
        return "proyecto urbanístico"
    return "urbanismo"


class JerezDeLaFronteraAyuntamientoAdapter(AyuntamientoAdapter):
    """TYPO3 jerez.es + API tablón tramites.aytojerez.es + sede electrónica urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tablon_api = str(self.config.get("tablon_api") or TABLON_API).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.urbanismo_tramites_url = str(
            self.config.get("urbanismo_tramites_url") or URBANISMO_TRAMITES
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-jerez-de-la-frontera/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            payload = self._fetch_json(self.tablon_api)
        except (urllib.error.URLError, json.JSONDecodeError, KeyError):
            return []
        rows: list[dict[str, Any]] = []
        for item in payload.get("datos") or []:
            extracto = (item.get("extracto") or "").strip()
            if not extracto:
                continue
            exp_id = item.get("idExpediente")
            fecha = _parse_fecha_dash(item.get("fechaExposicion") or "")
            url = f"{TABLON_PAGE}#{exp_id}" if exp_id else TABLON_PAGE
            blob = f"{extracto} {item.get('entidad') or ''}"
            rows.append(
                {
                    "titulo": extracto[:500],
                    "fecha": fecha,
                    "url": url,
                    "blob": blob,
                    "origen": "tablon",
                    "tablon_id": exp_id,
                    "entidad": item.get("entidad"),
                }
            )
        return rows

    def _crawl_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_H3.finditer(html):
                titulo = _strip_html(m.group(1))
                if len(titulo) < 15 or titulo in seen:
                    continue
                seen.add(titulo)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo),
                        "url": page_url,
                        "blob": titulo,
                        "origen": "web_planeamiento",
                    }
                )
            for m in RE_PDF_HREF.finditer(html):
                pdf_path = unescape(m.group(1))
                pdf_url = self._abs_web(pdf_path)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = unescape(urllib.parse.unquote(Path(urllib.parse.urlparse(pdf_url).path).name))
                rows.append(
                    {
                        "titulo": name[:500],
                        "fecha": _fecha_from_blob(f"{name} {pdf_path}"),
                        "url": pdf_url,
                        "pdf_url": pdf_url,
                        "blob": f"{name} {pdf_path}",
                        "origen": "web_pdf",
                    }
                )
        return rows

    def _collect_sede_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_tramites_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TRAMITE_HREF.finditer(html):
            path = unescape(m.group(1))
            if path in seen:
                continue
            seen.add(path)
            slug_part = path.rsplit("/", 1)[-1]
            titulo = slug_part.replace("_", " ").replace("-", " ").strip().title()
            url = self._abs_sede(path)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": None,
                    "url": url,
                    "blob": titulo,
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _is_urban(self, blob: str) -> bool:
        if RE_TABLON_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if row.get("origen") == "sede_tramite":
            if not RE_LICENCIA.search(blob) and "tramite" not in blob.lower():
                pass
        elif not RE_LICENCIA.search(blob):
            return None
        tipo = "licencia"
        low = blob.lower()
        if "declaraci" in low and "responsable" in low:
            tipo = "declaración responsable"
        elif "comunicaci" in low and "previa" in low:
            tipo = "comunicación previa"
        elif "apertura" in low or "actividad" in low:
            tipo = "licencia de apertura/actividad"
        elif "obra menor" in low or "obras menor" in low:
            tipo = "licencia de obra menor"
        elif "obra mayor" in low or "obras mayor" in low:
            tipo = "licencia de obra mayor"
        elif "demolic" in low:
            tipo = "licencia de demolición"
        elif "rehabilit" in low:
            tipo = "licencia de rehabilitación"
        key = row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row.get("titulo"),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if row.get("origen") in ("web_planeamiento", "web_pdf"):
            if not RE_PROYECTO.search(blob) and len(blob) < 20:
                return None
        elif not self._is_urban(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row.get("titulo"),
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("tablon_id"):
            rec["tablon_id"] = row["tablon_id"]
        return rec

    def _merge_rows(self, *groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for group in groups:
            for row in group:
                key = row.get("url") or row.get("titulo") or ""
                if not key:
                    continue
                if key in by_key:
                    prev = by_key[key]
                    for k, v in row.items():
                        if v is not None and (k not in prev or prev[k] in (None, "")):
                            prev[k] = v
                else:
                    by_key[key] = dict(row)
        return list(by_key.values())

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
        tablon = self._collect_tablon()
        tramites = self._collect_sede_tramites()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in tramites:
            lic = self._to_licencia(item)
            if lic and lic["id"] not in seen:
                rows.append(lic)
                seen.add(lic["id"])
        for item in tablon:
            lic = self._to_licencia(item)
            if lic and lic["id"] not in seen:
                rows.append(lic)
                seen.add(lic["id"])
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "tablon+sede_tramites",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "sede_tramite": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        tablon = self._collect_tablon()
        seeds = self._crawl_seed_pages()
        merged = self._merge_rows(tablon, seeds)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in merged:
            proy = self._to_proyecto(item)
            if proy and proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "tablon+web_planeamiento",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web_planeamiento": sum(1 for r in rows if r.get("origen") == "web_planeamiento"),
            "web_pdf": sum(1 for r in rows if r.get("origen") == "web_pdf"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
