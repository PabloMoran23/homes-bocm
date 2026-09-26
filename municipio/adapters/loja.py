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

WEB_BASE = "http://aytoloja.org"
PLANEAMIENTO_URL = f"{WEB_BASE}/ayuntamiento/planeamiento.htm"
ORDENANZAS_URL = f"{WEB_BASE}/ayuntamiento/ordenanzasyreglamentos.htm"
URBANISMO_URL = f"{WEB_BASE}/cartadeservicios/urbanismo.htm"
SEDE_BASE = "https://loja.sedelectronica.es"
SITUA_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=18140"
MUNICIPIO = "Loja"
ID_PREFIX = "loja"

DEFAULT_SEED_PAGES: list[str] = [
    PLANEAMIENTO_URL,
    ORDENANZAS_URL,
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|cartel de obra|aviso.*obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|innovaci[oó]n|pmus|agenda urbana|normas subsidiarias|"
    r"clasificaci[oó]n|calificaci[oó]n|zonificaci[oó]n|unidad de ejecuci[oó]n|"
    r"registro de entidades urban|compensaci[oó]n|vertido|habitabilidad|edificaci[oó]n)",
)
RE_ORDENANZA_URBAN = re.compile(
    r"(?i)(urban|edific|suelo|planeam|obra|licencia|vertido|habitabilidad|"
    r"compensaci[oó]n|entidades urban|aprovechamiento)",
)
RE_DOC_HREF = re.compile(
    r'<a[^>]+href=["\']([^"\']+\.(?:pdf|zip)(?:\?[^"\']*)?)["\'][^>]*>([^<]{3,400})</a>',
    re.I | re.S,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_PATH = re.compile(r"(?:^|/)(20\d{2})[_-](\d{2})[_-]")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_PATH.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b or "planeamiento vigente" in b:
        return "PGOU"
    if "pmus" in b:
        return "PMUS"
    if "agenda urbana" in b:
        return "agenda urbana"
    if "plan parcial" in b or re.search(r"\bpv[-_ ]?4", b):
        return "plan parcial"
    if "innovaci" in b or "modificaci" in b:
        return "modificación planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b or "reglamento" in b:
        return "ordenanza urbanística"
    if "memoria" in b:
        return "memoria planeamiento"
    if "plano" in b or "cartograf" in b or "zonificaci" in b:
        return "cartografía urbanística"
    if "estudio ac" in b:
        return "estudio acústico"
    if "licencia" in b or "cartel" in b:
        return "licencia / aviso obra"
    return "urbanismo"


class LojaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web estática aytoloja.org (planeamiento PDFs) + sede espublico inactiva + SITUA."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.planeamiento_url = str(self.config.get("planeamiento_url") or PLANEAMIENTO_URL)
        self.ordenanzas_url = str(self.config.get("ordenanzas_url") or ORDENANZAS_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.situa_url = str(self.config.get("situa_url") or SITUA_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-loja/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str, page_url: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        return urllib.parse.urljoin(page_url, href)

    def _collect_page_docs(self, page_url: str, *, urban_only: bool = False) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_DOC_HREF.finditer(html):
            href = self._abs_web(m.group(1), page_url)
            if href in seen:
                continue
            title = _strip_html(m.group(2)) or Path(urllib.parse.unquote(href)).name
            blob = f"{title} {href}"
            if urban_only and not RE_ORDENANZA_URBAN.search(blob):
                continue
            seen.add(href)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _fecha_from_blob(blob),
                    "url": href,
                    "page_url": page_url,
                    "blob": blob,
                    "origen": "web_planeamiento" if "planeamiento" in page_url else "web_ordenanzas",
                }
            )
        return rows

    def _collect_planeamiento(self) -> list[dict[str, Any]]:
        rows = self._collect_page_docs(self.planeamiento_url)
        for page in self.seed_pages:
            if page == self.planeamiento_url:
                continue
            rows.extend(self._collect_page_docs(page, urban_only=(page == self.ordenanzas_url)))
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "oficina técnica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Carta de servicios — Urbanismo (Oficina Técnica Municipal)",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Gestión de licencias y trámites urbanísticos; sin listado histórico público",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica (inactiva)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica espublico — no configurada",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "nota": "loja.sedelectronica.es devuelve «Sede Electrónica Indeterminada»; sin tablón ni dossier",
                "origen": "sede_inactiva",
            },
            {
                "id": _stable_id("lic", f"{self.planeamiento_url}#cartel-obras"),
                "fecha_concesion": "2024-01-01",
                "tipo": "aviso cartel de obras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Aviso normativa cartel de obras",
                "url": f"{self.web_base}/ayuntamiento/doc/2024_aviso_normativa_cartel_obras.pdf",
                "source": "ayuntamiento",
                "nota": "Documento informativo sobre licencias y cartel de obra",
                "origen": "web_planeamiento",
            },
        ]

    def _doc_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        blob = item.get("blob") or item.get("titulo") or ""
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _doc_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", item["url"]),
            "fecha_concesion": item.get("fecha"),
            "tipo": "aviso / licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"],
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
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
        for item in self._collect_planeamiento():
            rec = self._doc_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": 0, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_planeamiento():
            add(self._doc_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", self.planeamiento_url),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento urbanístico — índice documentación municipal",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.planeamiento_url,
                "source": "ayuntamiento",
                "origen": "web_indice",
            }
        )
        add(
            {
                "id": _stable_id("proy", self.situa_url),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Loja — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": self.situa_url,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": "Visor regional de planeamiento digitalizado (INE 18140)",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "web_planeamiento": sum(1 for r in rows if r.get("origen") == "web_planeamiento"),
            "web_ordenanzas": sum(1 for r in rows if r.get("origen") == "web_ordenanzas"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_proyectos(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": result.get("rows", 0),
                    "added": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": result.get("rows", 0), "added": 0, "status": "ok"}
