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

WEB_BASE = "https://www.andujar.es"
SEDE_BASE = "https://sede.andujar.es"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
VITUA_URL = (
    "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/"
)
DIPU_TABLON = "https://sede.dipujaen.es/Tablon"
MUNICIPIO = "Andújar"
ID_PREFIX = "andujar"

DEFAULT_WEB_SEEDS: list[str] = [
    f"{WEB_BASE}/areas-municipales/servicios-infraestructuras-y-urbanismo",
    f"{WEB_BASE}/areas-municipales/servicios-infraestructuras-y-urbanismo?tx_news_pi1=266",
]

DEFAULT_SEDE_SEEDS: list[str] = [
    f"{SEDE_BASE}/",
    f"{SEDE_BASE}/Editors/DlgTramiteSede.aspx",
]

DEFAULT_PLANEAMIENTO_SEEDS: list[dict[str, Any]] = [
    {
        "titulo": (
            "Plan de Sectorización del Sector NS-2 del PGOU — información pública "
            "(EAE-JA-010/2015)"
        ),
        "url": "https://www.juntadeandalucia.es/boja/2026/92/66",
        "fecha": "2026-05-07",
        "tipo": "plan parcial",
        "expte": "EAE-JA-010/2015",
        "origen": "boja_publicacion",
        "nota": "Documentación en sede / Google Drive enlazado desde el anuncio BOJA",
    },
    {
        "titulo": (
            "Innovación del PGOU de Andújar — área logística intermodal "
            "(aprobación inicial, información pública)"
        ),
        "url": "https://www.juntadeandalucia.es/boja/2024/5/34",
        "fecha": "2023-11-13",
        "tipo": "PGOU",
        "expte": None,
        "origen": "boja_publicacion",
    },
    {
        "titulo": "Documentación sector NS-2 — carpeta pública (Drive)",
        "url": "https://drive.google.com/drive/folders/1feIcaAx9jDoMj1tPj6K-lMaDQV5s9wNV?usp=sharing",
        "fecha": "2026-05-07",
        "tipo": "información pública",
        "expte": "EAE-JA-010/2015",
        "origen": "portal_drive",
    },
    {
        "titulo": "Consulta de planeamiento urbanístico — SITUADIFUSION (Junta de Andalucía)",
        "url": SITUA_SEARCH,
        "fecha": None,
        "tipo": "planeamiento",
        "origen": "situa",
        "nota": "Instrumentos digitalizados; filtrar provincia Jaén → Andújar (INE 23005)",
    },
    {
        "titulo": "Visor territorial VITUA — cartografía urbanística regional",
        "url": VITUA_URL,
        "fecha": None,
        "tipo": "cartografía urbanística",
        "origen": "vitua",
    },
    {
        "titulo": "Tablón de anuncios — Diputación Provincial de Jaén",
        "url": DIPU_TABLON,
        "fecha": None,
        "tipo": "edicto provincial",
        "origen": "dipujaen_tablon",
    },
]

DEFAULT_LICENCIA_INFO: list[dict[str, str]] = [
    {
        "titulo": "Procedimiento urbanístico (licencias, consultas) — sede electrónica",
        "url": f"{SEDE_BASE}/",
        "tipo": "trámite urbanístico",
    },
    {
        "titulo": "Catálogo de trámites — licencias y autorizaciones urbanísticas",
        "url": f"{SEDE_BASE}/Editors/DlgTramiteSede.aspx",
        "tipo": "catálogo trámites",
    },
    {
        "titulo": "Licencia de alteración de fincas",
        "url": f"{SEDE_BASE}/Editors/DlgTramiteSede.aspx",
        "tipo": "licencia de obra",
    },
    {
        "titulo": "Licencia de apertura de establecimientos",
        "url": f"{SEDE_BASE}/Editors/DlgTramiteSede.aspx",
        "tipo": "licencia de actividad",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|alteraci[oó]n de fincas|apertura de establecimiento)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|sector|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|"
    r"cambio de uso|ordenanza|innovaci[oó]n|sectoriz|log[ií]stic|eae-ja)",
)
RE_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"becas|escuela de verano|ayudas.*empresarial|bonificaci[oó]n pension|"
    r"empadronamiento|certificado de convivencia|autotaxi|mercadillo)",
)
RE_BOJA_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_BOJA_FECHA = re.compile(
    r"(?i)(?:Anuncio|Edicto) de (\d{1,2}) de (\w+) de (\d{4})",
)
RE_BOJA_EXPDTE = re.compile(r"(?i)Expediente:\s*([A-Z0-9\-/]+)")
RE_WEB_PDF = re.compile(
    r'href=["\']((?:https://www\.andujar\.es)?/fileadmin/[^"\']+\.pdf)["\']',
    re.I,
)
RE_WEB_NEWS = re.compile(
    r'href=["\']((?:https://www\.andujar\.es)?/[^"\']*(?:noticia|news|tx_news)[^"\']*)["\']',
    re.I,
)
RE_SEDE_TRAMITE = re.compile(
    r"(?i)(Licencia[^|]+|Procedimiento Urban[^|]+|Ocupaci[oó]n Privativa[^|]+)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
MONTHS_ES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


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
    m = RE_BOJA_FECHA.search(text or "")
    if m:
        day, month_name, year = m.group(1), m.group(2).lower(), m.group(3)
        mo = MONTHS_ES.get(month_name)
        if mo:
            try:
                return datetime(int(year), mo, int(day)).strftime("%Y-%m-%d")
            except ValueError:
                pass
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "sector" in b and ("ns-2" in b or "sectoriz" in b):
        return "plan parcial"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "innovaci" in b:
        return "innovación PGOU"
    if "evaluaci" in b and "ambiental" in b:
        return "evaluación ambiental"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class AndujarAyuntamientoAdapter(AyuntamientoAdapter):
    """TYPO3 andujar.es + sede propia (ASP.NET) + BOJA/SITUA/VITUA (Jaén)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_seeds = [str(u) for u in (self.config.get("web_seeds") or DEFAULT_WEB_SEEDS)]
        self.sede_seeds = [str(u) for u in (self.config.get("sede_seeds") or DEFAULT_SEDE_SEEDS)]
        self.planeamiento_seeds = list(
            self.config.get("planeamiento_seeds") or DEFAULT_PLANEAMIENTO_SEEDS
        )
        self.licencia_info = list(self.config.get("licencia_info") or DEFAULT_LICENCIA_INFO)
        self.portal_timeout_s = float(self.config.get("portal_timeout_s", 25))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(
        self,
        url: str,
        *,
        timeout: float | None = None,
        use_insecure: bool = True,
    ) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-andujar/1.0")},
        )
        ctx = self._ssl_ctx if use_insecure else None
        with urllib.request.urlopen(req, timeout=timeout or self.portal_timeout_s, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _try_fetch(self, url: str, *, timeout: float | None = None) -> str | None:
        try:
            return self._fetch(url, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _seed_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        titulo = str(item["titulo"])
        url = str(item["url"])
        blob = f"{titulo} {item.get('expte') or ''} {item.get('nota') or ''}"
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha") or _fecha_from_blob(titulo),
            "tipo": item.get("tipo") or _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "expte": item.get("expte"),
            "origen": item.get("origen") or "planeamiento_seed",
            "nota": item.get("nota"),
        }

    def _boja_enriched(self, url: str) -> dict[str, Any] | None:
        html = self._try_fetch(url, timeout=45)
        if not html:
            return None
        title_m = RE_BOJA_TITLE.search(html)
        titulo = _strip_html(title_m.group(1)) if title_m else url
        if "andujar" not in titulo.lower() and "andújar" not in titulo.lower():
            return None
        fecha = _fecha_from_blob(titulo) or _fecha_from_blob(html)
        expte_m = RE_BOJA_EXPDTE.search(html)
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "expte": expte_m.group(1) if expte_m else None,
            "origen": "boja_publicacion",
        }

    def _collect_web(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in self.web_seeds:
            html = self._try_fetch(seed)
            if not html:
                continue
            for href in RE_WEB_PDF.findall(html):
                pdf_url = self._abs_web(href)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = Path(urllib.parse.unquote(pdf_url)).stem.replace("_", " ")
                blob = name
                if not RE_PROYECTO.search(blob) and not RE_PROYECTO.search(seed):
                    continue
                rows.append(
                    {
                        "id": _stable_id("proy", pdf_url),
                        "municipio": MUNICIPIO,
                        "titulo": name[:500],
                        "fecha": _fecha_from_blob(name),
                        "tipo": _proyecto_tipo(blob),
                        "url": pdf_url,
                        "source": "ayuntamiento",
                        "origen": "web_pdf",
                    }
                )
            for href in RE_WEB_NEWS.findall(html):
                page_url = self._abs_web(href)
                if page_url in seen:
                    continue
                seen.add(page_url)
                sub = self._try_fetch(page_url)
                if not sub:
                    continue
                text = _strip_html(sub)
                if RE_NON_URBAN.search(text) and not RE_PROYECTO.search(text):
                    continue
                if not RE_PROYECTO.search(text):
                    continue
                rows.append(
                    {
                        "id": _stable_id("proy", page_url),
                        "municipio": MUNICIPIO,
                        "titulo": text[:500],
                        "fecha": _fecha_from_blob(text),
                        "tipo": _proyecto_tipo(text),
                        "url": page_url,
                        "source": "ayuntamiento",
                        "origen": "web_news",
                    }
                )
        return rows

    def _collect_sede_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in self.sede_seeds:
            html = self._try_fetch(seed)
            if not html:
                continue
            for match in RE_SEDE_TRAMITE.findall(html):
                label = _strip_html(match)
                if not RE_LICENCIA.search(label) and "urban" not in label.lower():
                    continue
                url = seed
                rows.append(
                    {
                        "id": _stable_id("lic", f"{label}|{url}"),
                        "fecha_concesion": None,
                        "tipo": "licencia de obra" if "licencia" in label.lower() else "trámite urbanístico",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": label[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "sede_catalogo",
                    }
                )
        return rows

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.licencia_info:
            url = str(item["url"])
            rows.append(
                {
                    "id": _stable_id("lic", url + item["titulo"]),
                    "fecha_concesion": None,
                    "tipo": item.get("tipo") or "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_info",
                }
            )
        return rows

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
        for rec in self._collect_licencia_info() + self._collect_sede_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": sum(1 for r in rows if r.get("origen") == "sede_info"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "sede_catalogo"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info() + self._collect_sede_tramites():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, len(rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self.planeamiento_seeds:
            add(self._seed_to_proyecto(item))
        for url in {
            str(x.get("url"))
            for x in self.planeamiento_seeds
            if x.get("origen") == "boja_publicacion"
        }:
            add(self._boja_enriched(url))
        for rec in self._collect_web():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "boja": sum(1 for r in rows if r.get("origen") == "boja_publicacion"),
            "seeds": sum(
                1
                for r in rows
                if r.get("origen")
                in ("situa", "vitua", "dipujaen_tablon", "portal_drive", "planeamiento_seed")
            ),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web_")),
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
