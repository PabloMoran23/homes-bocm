from __future__ import annotations

import hashlib
import http.cookiejar
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

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://lalinea.es"
SEDE_BASE = "https://www.sedeelectronica.lalinea.es"
EDICTOS_URL = f"{SEDE_BASE}/edictos/publico?idOrgan=23"
MUNICIPIO = "La Línea de la Concepción"
ID_PREFIX = "la-linea"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/areas/economia-hacienda-y-gestion-interna/urbanismo/",
    f"{WEB_BASE}/instrumentos-de-planeamiento-urbanistico/",
    f"{WEB_BASE}/plan-general-de-ordenacion-urbanistica/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura|apertura de local|"
    r"realidad f[ií]sica alterada|protecci[oó]n de la legalidad urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bopcadiz|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|expropiaci[oó]n|avance|subrogaci[oó]n|cat[aá]logo de protecci[oó]n|"
    r"ref\.?\s*catastral|pol[ií]gono\s*\d|unidades urban)",
)
RE_EDICTO_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|funcionario de carrera|"
    r"convocatoria.*empleo|alcalde accidental|designaci[oó]n de alcalde|"
    r"t[eé]cnico de administraci[oó]n general|concurso-oposici[oó]n|"
    r"promoci[oó]n interna|concurso de m[eé]ritos)",
)
RE_WP_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_EDICTO_ROW = re.compile(
    r"<td[^>]*>\s*(\d{2}/\d{2}/\d{4})\s*</td>\s*"
    r"<td[^>]*>\s*(\d{2}/\d{2}/\d{4})\s*</td>\s*"
    r"<td[^>]*>(.*?)</td>.*?",
    re.S | re.I,
)
RE_EDICTO_CODIGO = re.compile(
    r'href="(/edictos/edicto/publico\.action[^"]*codigo=(\d{4}-\d+))"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPTE = re.compile(
    r"(?i)(?:expediente|expte|exp\.?)\s*(?:n[ºo°.]?\s*)?([A-Z0-9_./-]{6,})",
)
RE_REF_CAT = re.compile(r"(?i)\b(\d{7}[A-Z]{2}\d{3}[A-Z0-9]{8})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "catálogo de protección" in b or "catalogo de proteccion" in b:
        return "catálogo de protección"
    if "expropiaci" in b:
        return "expropiación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "subrogaci" in b:
        return "subrogación urbanística"
    if "legalidad urban" in b:
        return "protección legalidad urbanística"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "licencia" in b:
        return "licencia publicada"
    if "plan parcial" in b or "plan especial" in b:
        return "planeamiento"
    return "urbanismo"


class LaLineaDeLaConcepcionAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Elementor (PGOU PDFs) + tablón edictos Diputación Cádiz (sede Liferay)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.edictos_url = str(self.config.get("edictos_url") or EDICTOS_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-linea/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or self.web_base + "/", href))

    def _abs_sede(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.sede_base}/", href))

    def _collect_edictos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.edictos_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_EDICTO_ROW.finditer(html):
            fecha_pub = _parse_fecha_dmy(m.group(1))
            titulo_html = m.group(3)
            titulo = _strip_html(titulo_html)
            if not titulo or len(titulo) < 8:
                continue
            chunk = html[m.start() : m.start() + 2500]
            link_m = RE_EDICTO_CODIGO.search(chunk)
            if not link_m:
                continue
            codigo = link_m.group(2)
            url = self._abs_sede(link_m.group(1).split(";")[0] + f"?codigo={codigo}")
            expte_m = RE_EXPTE.search(titulo)
            refcat_m = RE_REF_CAT.search(titulo)
            expte = expte_m.group(1) if expte_m else None
            if not expte and refcat_m:
                expte = refcat_m.group(1)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha_pub,
                    "codigo": codigo,
                    "url": url,
                    "expte": expte,
                    "blob": f"{titulo} {codigo} {expte or ''}",
                    "origen": "sede_edictos",
                }
            )
        return rows

    def _collect_seed_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_WP_LINK.finditer(html):
                href = m.group(1)
                anchor = _strip_html(m.group(2))
                if "favicon" in href.lower() or href.startswith("mailto:"):
                    continue
                if not re.search(
                    r"(?i)(/recursos/urbanismo|wp-content/uploads|/documentos/).*\.(pdf|zip)(?:\?|$)",
                    href,
                ) and not re.search(r"(?i)\.(pdf|zip)(?:\?|$)", href):
                    continue
                if "/Horario" in href:
                    continue
                doc_url = self._abs_url(href, page_url)
                if doc_url in seen:
                    continue
                name = unescape(urllib.parse.unquote(Path(doc_url).name))
                titulo = anchor if len(anchor) > 5 else name
                blob = f"{titulo} {name} {doc_url} {page_url}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                seen.add(doc_url)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(f"{name} {doc_url}"),
                        "url": page_url,
                        "doc_url": doc_url,
                        "blob": blob,
                        "origen": "wordpress_seed",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.edictos_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico de anuncios y edictos",
                "url": self.edictos_url,
                "source": "ayuntamiento",
                "nota": "Edictos urbanísticos y licencias publicados en sede (Diputación Cádiz)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/tramites-disponibles"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites disponibles — sede electrónica",
                "url": f"{self.sede_base}/tramites-disponibles",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/areas/economia-hacienda-y-gestion-interna/urbanismo/"),
                "fecha_concesion": None,
                "tipo": "información urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenación del territorio y urbanismo — web municipal",
                "url": f"{self.web_base}/areas/economia-hacienda-y-gestion-interna/urbanismo/",
                "source": "ayuntamiento",
                "nota": "PGOU, instrumentos de planeamiento y documentación urbanística",
                "origen": "web_tramite",
            },
        ]

    def _edicto_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_EDICTO_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        if RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob):
            return True
        if "urb61" in blob.lower() or "urban" in blob.lower():
            return True
        return False

    def _edicto_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._edicto_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("codigo") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / notificación urbanística",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expte"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_edictos",
        }

    def _edicto_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._edicto_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("codigo") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expte"),
            "origen": "sede_edictos",
        }

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        doc_url = row["doc_url"]
        return {
            "id": _stable_id("proy", doc_url),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "pdf_url": doc_url,
            "source": "ayuntamiento",
            "origen": row.get("origen", "wordpress_seed"),
        }

    def _seed_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        doc_url = row["doc_url"]
        return {
            "id": _stable_id("lic", doc_url),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "pdf_url": doc_url,
            "source": "ayuntamiento",
            "origen": row.get("origen", "wordpress_seed"),
        }

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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_edictos():
            rec = self._edicto_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_seed_docs():
            rec = self._seed_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "edictos": sum(1 for r in rows if r.get("origen") == "sede_edictos"),
            "info": sum(
                1
                for r in rows
                if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")
            ),
            "wordpress": sum(1 for r in rows if r.get("origen") == "wordpress_seed"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_edictos():
            rec = self._edicto_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_seed_docs():
            rec = self._seed_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_edictos():
            add(self._edicto_to_proyecto(item))
        for item in self._collect_seed_docs():
            add(self._seed_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "edictos": sum(1 for r in rows if r.get("origen") == "sede_edictos"),
            "wordpress": sum(1 for r in rows if r.get("origen") == "wordpress_seed"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
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
