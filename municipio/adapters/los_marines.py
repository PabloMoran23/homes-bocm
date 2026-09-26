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

WEB_BASE = "https://www.losmarines.es"
SEDE_BASE = "https://sede.losmarines.es"
TABLON_URL = f"{SEDE_BASE}/moad/Gtablon_web-moad/index.htm?codOrganismo=048_TA"
URBANISMO_URL = f"{WEB_BASE}/es/areas-tematicas/urbanismo/"
PGOU_URL = f"{WEB_BASE}/es/areas-tematicas/urbanismo/pgou/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=21048"
PDC_DIPHUELVA = "https://pdc.diphuelva.es/P2104800D"
MUNICIPIO = "Los Marines"
ID_PREFIX = "los-marines"
INE_CODE = "21048"

DEFAULT_PGOU_PAGES: list[str] = [
    PGOU_URL,
    URBANISMO_URL,
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|normativa urban|ordenanza|porn|prug|cat[aá]logo|"
    r"clasificaci[oó]n|calificaci[oó]n|protecci[oó]n patrimonial)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|plan de empleo|bases.*empleo|nombramiento|"
    r"convocatoria.*empleo|cobranza iae|padrones|subvenci[oó]n|fiestas|"
    r"mercadillo|bolsa de empleo|auxiliar administrativo)",
)
RE_PDF_HREF = re.compile(
    r'href=["\']([^"\']+\.(?:pdf|PDF)[^"\']*)["\']',
    re.I,
)
RE_GTABLON_NUM = re.compile(r"N\.(?:º|&ordm;)\s*(\d{4}/\d+)", re.I)
RE_GTABLON_TITLE = re.compile(
    r"N\.(?:º|&ordm;)\s*\d{4}/\d+[^<]*</[^>]+>\s*</[^>]+>\s*<[^>]+>([^<]+)",
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _pdf_title(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).stem.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", name).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "normas urban" in b or "normativa urban" in b:
        return "normativa urbanística"
    if "memoria" in b and ("ordenaci" in b or "introducci" in b):
        return "memoria planeamiento"
    if "porn" in b or "prug" in b:
        return "planeamiento territorial"
    if "cartograf" in b or "clas-y-cal" in b or "clasificaci" in b:
        return "cartografía urbanística"
    if "protecci" in b and "patrim" in b:
        return "protección patrimonial"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class LosMarinesAyuntamientoAdapter(AyuntamientoAdapter):
    """SAGA/OpenCMS web (PGOU PDFs) + GSede sede (Gtablon) + SITUA Junta de Andalucía."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.situa_url = str(self.config.get("situa_url") or SITUA_SEARCH)
        self.pgou_pages = [str(u) for u in (self.config.get("pgou_pages") or DEFAULT_PGOU_PAGES)]
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-los-marines/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

    def _collect_gtablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        nums = list(RE_GTABLON_NUM.finditer(html))
        for i, num_m in enumerate(nums):
            numero = num_m.group(1)
            if numero in seen:
                continue
            seen.add(numero)

            start = num_m.start()
            end = nums[i + 1].start() if i + 1 < len(nums) else start + 2500
            chunk = html[start:end]
            chunk_text = _strip_html(chunk)

            title_m = RE_GTABLON_TITLE.search(chunk)
            titulo = _strip_html(title_m.group(1)) if title_m else ""
            if not titulo:
                after = chunk_text.replace(f"N.º {numero}", "").strip()
                titulo = after[:200] if after else f"Anuncio {numero}"

            fecha = _parse_fecha_dmy(chunk_text)
            url = self.tablon_url

            rows.append(
                {
                    "numero": numero,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "blob": f"{numero} {titulo} {chunk_text[:300]}",
                    "origen": "gtablon",
                }
            )
        return rows

    def _collect_pgou(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(url: str, titulo: str, tipo: str | None = None, fecha: str | None = None) -> None:
            abs_url = self._abs_web(url)
            if abs_url in seen_urls:
                return
            seen_urls.add(abs_url)
            rows.append(
                {
                    "url": abs_url,
                    "titulo": titulo[:500],
                    "tipo": tipo or _proyecto_tipo(f"{titulo} {abs_url}"),
                    "fecha": fecha,
                    "blob": f"{titulo} PGOU Los Marines planeamiento",
                    "origen": "web_pgou",
                }
            )

        add(self.pgou_url, "PGOU Los Marines — documentación publicada", "PGOU")
        add(self.situa_url, "PGOU Los Marines — consulta SITUA (Junta de Andalucía)", "planeamiento")

        for page_url in self.pgou_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                href = m.group(1)
                title = _pdf_title(href)
                add(href, f"PGOU Los Marines — {title}")

        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón electrónico municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "G·TABLÓN — tablón de anuncios (sede electrónica)",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Anuncios publicados en Gtablon Guadaltel (codOrganismo=048_TA)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/opencms/sede/index.html"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de urbanismo — sede electrónica GSede",
                "url": f"{self.sede_base}/opencms/sede/index.html",
                "source": "ayuntamiento",
                "nota": "Área URBANISMO en sede; sin listado histórico público de licencias concedidas",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "información urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Área temática Urbanismo — web municipal",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "PGOU y normativa publicados en web SAGA/OpenCMS",
                "origen": "web_tramite",
            },
        ]

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_TABLON_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        tipo = "licencia de obra"
        if re.search(r"(?i)actividad", blob):
            tipo = "licencia de actividad"
        key = row.get("numero") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("numero"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "gtablon",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("numero") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("numero"),
            "origen": "gtablon",
        }

    def _pgou_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row.get("blob") or "", row["url"]),
            "tipo": row.get("tipo") or _proyecto_tipo(row.get("blob") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web_pgou",
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

        for item in self._collect_gtablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "gtablon": sum(1 for r in rows if r.get("origen") == "gtablon"),
            "info": sum(
                1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_gtablon():
            rec = self._tablon_to_licencia(item)
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

        for item in self._collect_pgou():
            add(self._pgou_to_proyecto(item))

        for item in self._collect_gtablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pgou": sum(1 for r in rows if r.get("origen") == "web_pgou"),
            "situa": sum(1 for r in rows if "situa" in (r.get("url") or "")),
            "gtablon": sum(1 for r in rows if r.get("origen") == "gtablon"),
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
