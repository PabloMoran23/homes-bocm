from __future__ import annotations

import hashlib
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

WEB_BASE = "https://www.almonasterlareal.es"
SEDE_BASE = "https://almonasterlareal.sedelectronica.es"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Almonaster la Real"
ID_PREFIX = "almonaster-la-real"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/areas-tematicas/urbanismo/",
    f"{WEB_BASE}/es/areas-tematicas/urbanismo/pgou/",
    f"{WEB_BASE}/es/gobierno-abierto/portal-transparencia/indicadores-de-transparencia/",
    f"{WEB_BASE}/es/ayuntamiento/publicaciones-oficiales/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|v[ií]as y obras|establecimiento hosteler)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|ppr|ppt|ppi|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|normas subsidiarias|loua|adaptaci[oó]n|dotacional|ficha urban|"
    r"ordenaci[oó]n|snu|estructural)",
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*(?:title="([^"]*)")?[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"(20\d{2})(\d{2})(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
DOC_EXTENSIONS = (".pdf", ".zip")


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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YMD.search(url or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _title_from_url(url: str) -> str:
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    for ext in DOC_EXTENSIONS:
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break
    name = re.sub(r"[_-]+", " ", name).strip()
    return name[:500] if name else url


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "ordenaci" in b and "estructural" in b:
        return "ordenación estructural SNU"
    if "adaptaci" in b and "loua" in b:
        return "adaptación LOUA"
    if "loua" in b:
        return "LOUA / PGOU"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "memoria" in b:
        return "memoria planeamiento"
    if "planos" in b:
        return "planos urbanísticos"
    return "urbanismo"


class AlmonasterLaRealAyuntamientoAdapter(AyuntamientoAdapter):
    """SAGA Diputación Huelva (ZIP/PDF PGOU) + sede propia (informativa) + SITUA."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.situa_url = str(self.config.get("situa_search_url") or SITUA_SEARCH)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-almonaster-la-real/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or f"{self.web_base}/", href))

    def _is_doc_href(self, href: str) -> bool:
        low = href.lower()
        return any(ext in low for ext in DOC_EXTENSIONS)

    def _collect_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            for match in RE_LINK.finditer(html):
                href = match.group(1)
                title_attr = (match.group(2) or "").strip()
                inner = match.group(3) or ""
                if not self._is_doc_href(href):
                    continue
                url = self._abs_web(href, page_url)
                if url in seen:
                    continue
                seen.add(url)
                anchor = _strip_html(inner)
                titulo = title_attr if title_attr else (anchor if anchor and len(anchor) > 3 else _title_from_url(url))
                blob = f"{titulo} {url}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if "/urbanismo/" not in url.lower() and "pgou" not in url.lower():
                        continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo, url),
                        "url": url,
                        "blob": blob,
                        "origen": "web_doc",
                    }
                )

        pgou_page = f"{self.web_base}/es/areas-tematicas/urbanismo/pgou/"
        if pgou_page not in seen:
            rows.append(
                {
                    "titulo": "PGOU Almonaster la Real — Plan General de Ordenación Urbana",
                    "fecha": None,
                    "url": pgou_page,
                    "blob": "pgou plan general ordenacion urbana almonaster",
                    "origen": "web_pgou",
                }
            )

        rows.append(
            {
                "titulo": "PGOU Almonaster la Real — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "url": self.situa_url,
                "blob": "planeamiento general pgou situa almonaster la real",
                "origen": "situa",
            }
        )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        urbanismo_url = f"{self.web_base}/es/areas-tematicas/urbanismo/"
        sede_url = f"{self.sede_base}/info.2"
        pgou_url = f"{self.web_base}/es/areas-tematicas/urbanismo/pgou/"
        return [
            {
                "id": _stable_id("lic", urbanismo_url),
                "fecha_concesion": None,
                "tipo": "servicio vías y obras — contacto",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — Servicio de Vías y Obras",
                "url": urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Contacto municipal para licencias; sin listado de concesiones",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", sede_url),
                "fecha_concesion": None,
                "tipo": "sede electrónica — trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — oficina virtual",
                "url": sede_url,
                "source": "ayuntamiento",
                "nota": "Trámites de licencias vía sede; sin histórico público scrapeable",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", pgou_url),
                "fecha_concesion": None,
                "tipo": "documentación PGOU",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "PGOU — documentación de planeamiento",
                "url": pgou_url,
                "source": "ayuntamiento",
                "nota": "Descarga de LOUA y ordenación estructural SNU",
                "origen": "web_tramite",
            },
        ]

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row["titulo"]
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "web_doc"),
        }

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
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_docs():
            rec = self._doc_to_proyecto(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "docs": sum(1 for r in rows if r.get("origen") == "web_doc"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
            "pgou_page": sum(1 for r in rows if r.get("origen") == "web_pgou"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_docs():
            rec = self._doc_to_proyecto(item)
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}
