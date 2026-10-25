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
from municipio.http import fetch_text

PORTAL_BASE = "https://www.santurtzi.eus"
MUNICIPIO = "Santurtzi"
ID_PREFIX = "santurtzi"

BIZKAIA_PUR_URL = (
    "https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador"
    "?p_p_id=IYBIWPUC_INSTANCE_CadYBlTy6tfn&p_p_lifecycle=0"
    "&p_p_state=normal&p_p_mode=view"
)
BIZKAIA_MUNICIPIO_ID = "82"

TABLON_URBANISMO = (
    f"{PORTAL_BASE}/es-ES/organizacion-municipal-transparencia/tablonanuncios/"
    "ayuntamiento/Paginas/urbanismo.aspx"
)
TABLON_OBRAS = (
    f"{PORTAL_BASE}/es-ES/organizacion-municipal-transparencia/tablonanuncios/"
    "ayuntamiento/Paginas/obras.aspx"
)
TRAMITES_URL = f"{PORTAL_BASE}/es-ES/Tramites/Paginas/iniciar-tramite.aspx"
SEDE_URL = f"{PORTAL_BASE}/es-ES/Mi-Ciudad/Paginas/bienvenida.aspx"

DEFAULT_LICENCIA_SEEDS: list[tuple[str, str]] = [
    (TRAMITES_URL, "Portal de trámites municipales"),
    (SEDE_URL, "Sede electrónica municipal (Mi ciudad)"),
    (
        f"{PORTAL_BASE}/es-ES/organizacion-municipal-transparencia/tablonanuncios/"
        "Paginas/default.aspx",
        "Tablón electrónico de anuncios",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:menor|mayor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|urbanizaci[oó]n|instrumento|sector|polvor)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPTE = re.compile(
    r"(?i)\b(?:expte\.?|expediente)\s*[:.]?\s*([0-9A-Z./_-]+/[0-9]{4}|[0-9]+/[0-9]{4})",
)
RE_BIZKAIA_CARD = re.compile(
    r'role="heading"[^>]*>(\d{4})</p>\s*<p>([^<]+)</p>.*?'
    r'href="([^"]+_IYBIWPUC_INSTANCE_CadYBlTy6tfn_idInstrumento=\d+[^"]*)"',
    re.S | re.I,
)
RE_BIZKAIA_CODE = re.compile(
    r'<span class="mw-100 text-right">\(([^)]+)\)</span>',
    re.I,
)
RE_TABLON_H3_PDF = re.compile(
    r"<h3[^>]*>\s*([^<]+?)\s*</h3>.*?href=\"([^\"]+\.pdf[^\"]*)\"",
    re.S | re.I,
)
RE_TRAMITE_LINK = re.compile(
    r'href="((?:https://www\.santurtzi\.eus)?/es-ES/[^"]+)"[^>]*>([^<]{5,200})',
    re.I,
)


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


def _iso_from_year(text: str) -> str | None:
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2035
    ]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _tipo_proyecto(titulo: str) -> str:
    blob = titulo.lower()
    if "plan general" in blob or "pgou" in blob:
        return "PGOU"
    if "plan parcial" in blob:
        return "plan parcial"
    if "plan especial" in blob:
        return "plan especial"
    if "modificaci" in blob and "pgou" in blob:
        return "modificación PGOU"
    if "modificaci" in blob:
        return "modificación puntual"
    if "informaci" in blob and "pública" in blob:
        return "información pública"
    if "convenio" in blob:
        return "convenio"
    return "planeamiento"


class SanturtziAyuntamientoAdapter(AyuntamientoAdapter):
    """Tablón SharePoint municipal + Registro PUR Diputación Foral de Bizkaia (municipio 82)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or PORTAL_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.portal_timeout_s = float(self.config.get("portal_timeout_s", 12))
        self.bizkaia_municipio_id = str(
            self.config.get("bizkaia_municipio_id") or BIZKAIA_MUNICIPIO_ID
        )
        self.tablon_max_pages = int(self.config.get("tablon_max_pages", 6))
        self._portal_reachable: bool | None = None
        raw_seeds = self.config.get("licencia_seeds")
        if raw_seeds:
            self.licencia_seeds = [(str(s["url"]), str(s["titulo"])) for s in raw_seeds]
        else:
            self.licencia_seeds = list(DEFAULT_LICENCIA_SEEDS)

    def _fetch(
        self, url: str, data: bytes | None = None, *, portal: bool = False
    ) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-santurtzi/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        if portal:
            with urllib.request.urlopen(req, timeout=self.portal_timeout_s) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        return fetch_text(req)

    def _portal_available(self) -> bool:
        if self._portal_reachable is not None:
            return self._portal_reachable
        try:
            self._fetch(TABLON_URBANISMO, portal=True)
            self._portal_reachable = True
        except (urllib.error.URLError, TimeoutError, OSError):
            self._portal_reachable = False
        return self._portal_reachable

    def _abs_portal(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return urllib.parse.urljoin(PORTAL_BASE + "/", path.lstrip("/"))

    def _bizkaia_form_date(self) -> str:
        try:
            html = self._fetch(BIZKAIA_PUR_URL)
        except (urllib.error.URLError, TimeoutError):
            return str(int(time.time() * 1000))
        m = re.search(
            r'name="_IYBIWPUC_INSTANCE_CadYBlTy6tfn_formDate"[^>]*value="(\d+)"',
            html,
            re.I,
        )
        return m.group(1) if m else str(int(time.time() * 1000))

    def _collect_bizkaia_planeamiento(self) -> list[dict[str, Any]]:
        form_date = self._bizkaia_form_date()
        payload = urllib.parse.urlencode(
            {
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_formDate": form_date,
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_select-municipios": self.bizkaia_municipio_id,
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_select-figuras": "",
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_filtro-texto": "",
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_submit": "Buscar",
            }
        ).encode("utf-8")
        try:
            html = self._fetch(BIZKAIA_PUR_URL, data=payload)
        except (urllib.error.URLError, TimeoutError):
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_BIZKAIA_CARD.finditer(html):
            year, titulo, url = m.group(1), unescape(m.group(2).strip()), m.group(3)
            titulo = re.sub(r"\s+", " ", titulo)
            block = m.group(0)
            code_m = RE_BIZKAIA_CODE.search(block)
            codigo = code_m.group(1).strip() if code_m else None
            inst_m = re.search(r"idInstrumento=(\d+)", url)
            inst_id = inst_m.group(1) if inst_m else url
            detail_url = url if url.startswith("http") else f"https://www.bizkaia.eus{url}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"bizkaia-pur-{inst_id}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": f"{year}-01-01",
                "tipo": _tipo_proyecto(titulo),
                "url": detail_url,
                "source": "ayuntamiento",
                "origen": "bizkaia_pur",
                "instrumento_id": inst_id,
            }
            if codigo:
                rec["codigo_instrumento"] = codigo
            rows.append(rec)
        return rows

    def _parse_tablon_html(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TABLON_H3_PDF.finditer(html):
            titulo = unescape(_strip_html(m.group(1)))
            pdf_url = self._abs_portal(unescape(m.group(2)))
            if not titulo or titulo in seen:
                continue
            seen.add(titulo)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "fecha": _parse_fecha_dmy(titulo) or _iso_from_year(titulo),
                    "expte": _parse_expte(titulo),
                    "origen": "tablon_sharepoint",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        if not self._portal_available():
            return []
        bases = [TABLON_URBANISMO, TABLON_OBRAS]
        rows: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for base in bases:
            for page in range(1, self.tablon_max_pages + 1):
                url = base if page == 1 else f"{base}?page={page}"
                try:
                    html = self._fetch(url, portal=True)
                except (urllib.error.URLError, TimeoutError, OSError):
                    break
                chunk = self._parse_tablon_html(html, url)
                if not chunk and page > 1:
                    break
                for item in chunk:
                    key = item["titulo"].lower()
                    if key in seen_titles:
                        continue
                    seen_titles.add(key)
                    rows.append(item)
        return rows

    def _tablon_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item["titulo"]
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        if not RE_PROYECTO.search(titulo):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", item.get("pdf_url") or titulo),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _tipo_proyecto(titulo),
            "url": item.get("url") or titulo,
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        if item.get("expte"):
            rec["expte"] = item["expte"]
        return rec

    def _tablon_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item["titulo"]
        if not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", item.get("pdf_url") or titulo),
            "fecha_concesion": item.get("fecha"),
            "tipo": "licencia / autorización",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": item.get("url") or titulo,
            "source": "ayuntamiento",
            "origen": item.get("origen"),
            "pdf_url": item.get("pdf_url"),
        }

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(url: str, titulo: str, nota: str) -> None:
            url = self._abs_portal(url)
            rec_id = _stable_id("lic", url)
            if rec_id in seen:
                return
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": nota,
                    "origen": "tramites_info",
                }
            )

        for url, titulo in self.licencia_seeds:
            add(url, titulo, "Página informativa; sin listado público de concesiones")

        if not self._portal_available():
            return rows
        try:
            html = self._fetch(TRAMITES_URL, portal=True)
        except (urllib.error.URLError, TimeoutError, OSError):
            return rows

        for m in RE_TRAMITE_LINK.finditer(html):
            href, text = m.group(1), _strip_html(m.group(2))
            if not RE_LICENCIA.search(text) and not RE_LICENCIA.search(href):
                continue
            add(href, text[:500] or href, "Trámite enlazado desde el portal de trámites")
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
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "tramites_info"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sharepoint"),
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

        for rec in self._collect_bizkaia_planeamiento():
            add(rec)
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "bizkaia_pur": sum(1 for r in rows if r.get("origen") == "bizkaia_pur"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sharepoint"),
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
