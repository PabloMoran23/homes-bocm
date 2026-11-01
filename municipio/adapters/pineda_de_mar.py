from __future__ import annotations

import hashlib
import html as html_module
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

WEB_BASE = "https://www.pinedademar.cat"
SEDE_BASE = "https://seu.pinedademar.cat/eAdmin"
MUNICIPIO = "Pineda de Mar"
ID_PREFIX = "pineda-de-mar"

TABLON_URL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
PLANEJAMENT_PAGE = f"{WEB_BASE}/serveis/urbanisme/plantejament-i-gestio-urbanistica-vigent"
LICENCIES_PAGE = (
    f"{WEB_BASE}/serveis/urbanisme/llicencies-dobres-activitats-i-ocupacions-de-via-publica"
)
TRAMITS_URBANISME = f"{WEB_BASE}/serveis/urbanisme/tramits"
SEDE_TRAMITS = f"{SEDE_BASE}/Registrar.do?action=inicioPortalTramites"

DEFAULT_LICENCIA_PAGES: list[str] = [
    LICENCIES_PAGE,
    TRAMITS_URBANISME,
    SEDE_TRAMITS,
    f"{WEB_BASE}/seu-electronica-1/tramits",
]

DEFAULT_PROYECTO_PAGES: list[str] = [
    PLANEJAMENT_PAGE,
    f"{WEB_BASE}/serveis/urbanisme/plantejament-i-gestio-urbanistica-vigent/pla-dordenacio-urbanistica",
]

RE_TABLON_ROW = re.compile(
    r'verAnuncio&id=([A-F0-9]+)"[^>]*>.*?</td>\s*<td[^>]*width="50%"[^>]*>\s*(.*?)\s*<br>\s*'
    r'.*?Per[íi]ode:</span>\s*(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})',
    re.S | re.I,
)
RE_GROUP_URBAN = re.compile(
    r"(?i)urbanisme|llicen.*urban|planej|disciplina urban|mediambient urban",
)
RE_TABLON_PROYECTO = re.compile(
    r"(?i)(projecte (?:bàsic|de)|junta de compens|sector pp|planej|pgmo|pgou|"
    r"taxa per llicències|matèria d'urbanisme|figure[s]? de planejament|"
    r"aprovació definitiva del [Pp]rojecte|reforma i millora de la plaça|"
    r"edicte relatiu.*(?:projecte|junta de compens|sector pp|planej|urban))",
)
RE_LICENCIA = re.compile(
    r"(?i)(llicen[cs]|comunicaci[oó] previa|assabentat|taxa per llicències|"
    r"matèria d'urbanisme|figure[s]? de planejament)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|pgou|pgmo|projecte|expedient|modificaci[oó]|sector|"
    r"junta de compens|informaci[oó] p[uú]blica|norma urban|planol)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"', re.I)


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


def _fecha_from_pdf_url(url: str) -> str | None:
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(Path(url).name)
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(titulo: str) -> str:
    n = (titulo or "").lower()
    if "junta de compens" in n or "sector pp" in n:
        return "junta de compensación / sector"
    if "projecte bàsic" in n or "projecte de" in n:
        return "proyecto técnico"
    if "taxa per llic" in n or "ordenança fiscal" in n:
        return "normativa fiscal urbanismo"
    if "pgmo" in n or "pgou" in n or "plan general" in n:
        return "planeamiento general"
    if "planol" in n or "ft-" in n:
        return "documentación gráfica PGMO"
    if "edicte" in n:
        return "edicto urbanismo"
    return "urbanismo"


class PinedaDeMarAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone urbanisme + sede eAdmin (Tablon.do) — Catalunya, Barcelona."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.proyecto_pages = [str(u) for u in (self.config.get("proyecto_pages") or DEFAULT_PROYECTO_PAGES)]
        self.max_tablon_detail = int(self.config.get("max_tablon_detail", 0))

    def _fetch(self, url: str, *, latin1: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pineda-de-mar/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
        if latin1:
            return raw.decode("iso-8859-1", errors="replace")
        return raw.decode("utf-8", errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

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

    def _parse_tablon_rows(self, html: str) -> list[dict[str, Any]]:
        """Filas del tablón con título y fechas (HTML eAdmin)."""
        group_urban_ids: set[str] = set()
        parts = re.split(r'<div class="toggle toggle-', html)
        for part in parts[1:]:
            title_m = re.search(r'<span style="font-size: 22px">([^<]+)</span>', part)
            if not title_m:
                continue
            group_title = html_module.unescape(title_m.group(1))
            if not RE_GROUP_URBAN.search(group_title):
                continue
            for m in RE_TABLON_ROW.finditer(part):
                group_urban_ids.add(m.group(1))

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, titulo_raw, f_ini, _f_fin = m.group(1), m.group(2), m.group(3), m.group(4)
            if ann_id in seen:
                continue
            titulo = _strip_html(titulo_raw)
            in_urban_group = ann_id in group_urban_ids
            if not in_urban_group and not RE_TABLON_PROYECTO.search(titulo):
                continue
            seen.add(ann_id)
            url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rows.append(
                {
                    "ann_id": ann_id,
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(f_ini),
                    "url": url,
                    "origen": "tablon_urbanisme" if in_urban_group else "tablon",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url, latin1=True)
        except (urllib.error.URLError, urllib.error.HTTPError):
            return []
        return self._parse_tablon_rows(html)

    def _collect_plone_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.proyecto_pages:
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, urllib.error.HTTPError):
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_web(m.group(1))
                if "@@download" in pdf and pdf.count(".pdf") > 1:
                    continue
                if not RE_PROYECTO.search(pdf) and not RE_PROYECTO.search(page_url):
                    if "urbanisme" not in pdf.lower() and "serveis-urbanisme" not in pdf.lower():
                        continue
                rec_id = _stable_id("proy", pdf)
                if rec_id in seen:
                    continue
                seen.add(rec_id)
                name = unescape(urllib.parse.unquote(Path(pdf.split("/@@download")[0]).name))
                rows.append(
                    {
                        "id": rec_id,
                        "municipio": MUNICIPIO,
                        "titulo": name[:500],
                        "fecha": _fecha_from_pdf_url(pdf),
                        "tipo": _proyecto_tipo(name),
                        "url": page_url,
                        "pdf_url": pdf.split("/@@download")[0] if "/@@download" in pdf else pdf,
                        "source": "ayuntamiento",
                        "origen": "plone_planejament",
                    }
                )
        return rows

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row.get("ann_id") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "tablon"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row.get("titulo") or ""):
            return None
        return {
            "id": _stable_id("lic", row.get("ann_id") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "normativa / trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url, latin1="pinedademar.cat/eAdmin" not in page_url)
            except (urllib.error.URLError, urllib.error.HTTPError):
                continue
            rec_id = _stable_id("lic", page_url)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            title_m = re.search(r"<title>([^<]+)", html, re.I)
            title = _strip_html(title_m.group(1)) if title_m else "Tràmits urbanístics"
            title = re.sub(r"\s*[-|].*Pineda.*$", "", title, flags=re.I).strip() or title
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": page_url,
                    "source": "ayuntamiento",
                    "origen": "tramite_info",
                    "nota": "Tramitación telemática via seu.pinedademar.cat; sin listado de concesiones",
                }
            )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencias_tramites():
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
            "tramites": sum(1 for r in rows if r.get("origen") == "tramite_info"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencias_tramites():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
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

        for rec in self._collect_plone_pdfs():
            add(rec)
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "plone": sum(1 for r in rows if r.get("origen") == "plone_planejament"),
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
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
