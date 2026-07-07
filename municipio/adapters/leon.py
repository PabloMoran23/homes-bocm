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

SEDE_BASE = "https://sede.aytoleon.es/eAdmin"
WEB_BASE = "https://aytoleon.es"
URBANISMO_URL = (
    f"{WEB_BASE}/es/tu-ayuntamiento/normativas/Paginas/urbanismo.aspx"
)
TABLON_ALL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
TRAMITES_URL = f"{SEDE_BASE}/Registrar.do?action=inicioPortalTramites"
MUNICIPIO = "León"
ID_PREFIX = "leon"

DEFAULT_SEARCH_TERMS = (
    "CONVENIO URBANISTICO",
    "MODIFICACION PGOU",
    "MOD. PGOU",
    "ESTUDIO DE DETALLE",
    "PROYECTO DE URBANIZACION",
    "SECTOR NC",
    "SECTOR ULD",
    "SECTOR PR",
    "PGOU",
    "INFORMACION PUBLICA",
)

DEFAULT_TRAMITE_IDS = (
    39,
    94,
    106,
    107,
    109,
    110,
    134,
    172,
    192,
)

RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td[^>]*>.*?verAnuncio&id=([A-F0-9]+).*?"
    r"</td>\s*<td[^>]*>\s*(.*?)\s*<br>.*?"
    r"Periodo:</span>\s*([^<]+)</td>",
    re.I | re.S,
)
RE_DOC_TOKEN = re.compile(r"abrirOriginal\('([^']+)'\)")
RE_EXPTE = re.compile(r"(?i)(?:EXP(?:EDIENTE)?\.?|N[º°]\s*)\s*([0-9]+/[0-9]{4})")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|ambiental|de obra)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable.*obra|"
    r"comunicaci[oó]n previa|autorizaci[oó]n.*obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(pgou|planeam|plan (?:parcial|especial|general)|modificaci[oó]n.*pgou|mod\.?\s*pgou|"
    r"convenio urban|estudio de detalle|estudio detalle|proyecto de urbaniz|"
    r"sector\s+(?:nc|uld|pr|aa)\s*[-\d]|informaci[oó]n p[uú]blica|reparcel|"
    r"segregaci[oó]n urban|normas urban|urbanizaci[oó]n del sector|"
    r"determinaciones.*urbaniz|proyecto de normalizaci)",
)
RE_MODAL_TITLE = re.compile(
    r'id="modalInformacion(\d+)"[^>]*>.*?<h4[^>]*>([^<]+)',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_expte(text: str) -> str | None:
    m = RE_EXPTE.search(text)
    return m.group(1).strip() if m else None


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"\s+", " ", text or "")).strip()
    if t.lower().startswith("ver documento"):
        t = t[len("ver documento") :].strip()
    return t[:500]


def _doc_url(sede_base: str, code: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(code, safe='')}&tipo=doc&mode=ori"
    )


def _proyecto_tipo(title: str, default: str = "urbanismo") -> str:
    n = title.lower()
    if "convenio urban" in n:
        return "convenio urbanístico"
    if "estudio" in n and "detalle" in n:
        return "estudio de detalle"
    if "mod" in n and "pgou" in n:
        return "modificación PGOU"
    if "plan parcial" in n or "plan especial" in n or "pgou" in n:
        return "planeamiento"
    if re.search(r"sector\s+(?:nc|uld|pr|aa)", n):
        return "sector urbanístico"
    if "urbaniz" in n:
        return "proyecto urbanización"
    if "informaci" in n:
        return "información pública"
    if "aprobaci" in n:
        return "aprobación"
    return default


class LeonAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede eAdmin (tablón urbanismo + búsqueda) + web corporativa SharePoint (PGOU, convenios)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.search_terms = list(self.config.get("search_terms") or DEFAULT_SEARCH_TERMS)
        self.tramite_ids = [int(x) for x in (self.config.get("tramite_ids") or DEFAULT_TRAMITE_IDS)]
        self.urbanismo_tablon_id = str(self.config.get("urbanismo_tablon_id") or "3")

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-leon/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "iso-8859-1"
            return raw.decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _parse_tablon_html(self, html: str) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, period_raw = m.groups()
            title = _clean_title(title_raw)
            if not title:
                continue
            row_html = m.group(0)
            doc_m = RE_DOC_TOKEN.search(row_html)
            doc_token = doc_m.group(1) if doc_m else None
            period_m = RE_PERIOD.search(period_raw or "")
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            fecha_fin = _parse_fecha_dmy(period_m.group(2)) if period_m else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha_ini": fecha_ini,
                "fecha_fin": fecha_fin,
                "url": detail_url,
                "doc_token": doc_token,
                "expte": _parse_expte(title),
            }
            if doc_token:
                rec["pdf_url"] = _doc_url(self.sede_base, doc_token)
            by_id[ann_id] = rec
        return by_id

    def _parse_tablon_section(self, html: str, section_id: str) -> dict[str, dict[str, Any]]:
        m = re.search(
            rf'id="tablon_{re.escape(section_id)}"(.*?)(?=id="tablon_\d+"|<!-- \*\*\*\* VARIOS|</section>)',
            html,
            re.S,
        )
        if not m:
            return {}
        return self._parse_tablon_html(m.group(1))

    def _search_tablon(self, term: str) -> dict[str, dict[str, Any]]:
        body = urllib.parse.urlencode({"referenciaBusqueda": term}).encode("utf-8")
        try:
            html = self._fetch(TABLON_ALL, data=body)
        except urllib.error.URLError:
            return {}
        return self._parse_tablon_html(html)

    def _collect_tablon(self) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        try:
            html = self._fetch(TABLON_ALL)
        except urllib.error.URLError:
            html = ""
        if html:
            by_id.update(self._parse_tablon_section(html, self.urbanismo_tablon_id))
            for ann_id, rec in self._parse_tablon_html(html).items():
                if RE_PROYECTO.search(rec["titulo"]) or RE_LICENCIA.search(rec["titulo"]):
                    by_id.setdefault(ann_id, rec)
        for term in self.search_terms:
            for ann_id, rec in self._search_tablon(term).items():
                by_id.setdefault(ann_id, rec)
        return by_id

    def _collect_web_proyectos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href in RE_PDF_HREF.findall(html):
            pdf = self._abs_web(href)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            if "manual" in name.lower() or "favicon" in name.lower():
                continue
            rec_id = _stable_id("proy", pdf)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "municipio": MUNICIPIO,
                    "titulo": name[:500],
                    "fecha": _parse_fecha_dmy(name),
                    "tipo": _proyecto_tipo(name),
                    "url": self.urbanismo_url,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "origen": "web_urbanismo",
                    "expte": _parse_expte(name),
                }
            )
        return rows

    def _collect_tramites_urbanismo(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TRAMITES_URL)
        except urllib.error.URLError:
            return []
        titles: dict[str, str] = {}
        for m in RE_MODAL_TITLE.finditer(html):
            tid, title = m.group(1), _clean_title(m.group(2))
            if tid in {str(x) for x in self.tramite_ids}:
                titles[tid] = title
        rows: list[dict[str, Any]] = []
        for tid in self.tramite_ids:
            title = titles.get(str(tid))
            if not title:
                continue
            url = f"{self.sede_base}/Registrar.do?action=infoTramite&tipoReg={tid}"
            rows.append(
                {
                    "id": _stable_id("lic", f"tramite-{tid}"),
                    "fecha_concesion": None,
                    "tipo": title[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo sede; no concesión publicada",
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _title_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if not RE_LICENCIA.search(title):
            return None
        tipo_m = re.search(r"(?i)(licencia[^,]{0,80}|declaraci[oó]n responsable)", title)
        out: dict[str, Any] = {
            "id": _stable_id("lic", rec.get("expte") or rec["ann_id"]),
            "fecha_concesion": rec.get("fecha_ini"),
            "tipo": (tipo_m.group(1).strip()[:120] if tipo_m else "licencia"),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "expte": rec.get("expte"),
            "url": rec["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        return out

    def _title_to_proyecto(self, rec: dict[str, Any], *, force: bool = False) -> dict[str, Any] | None:
        title = rec["titulo"]
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not force and not RE_PROYECTO.search(title):
            return None
        out: dict[str, Any] = {
            "id": _stable_id("proy", rec.get("expte") or rec["ann_id"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": rec.get("fecha_ini"),
            "tipo": _proyecto_tipo(title),
            "url": rec["url"],
            "source": "ayuntamiento",
            "expte": rec.get("expte"),
            "origen": rec.get("origen") or "tablon",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        return out

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
        tablon = self._collect_tablon()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec in tablon.values():
            lic = self._title_to_licencia(rec)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        for rec in self._collect_tramites_urbanismo():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_items": len(tablon),
            "tramites": len(self.tramite_ids),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        tablon = self._collect_tablon()
        for rec in tablon.values():
            lic = self._title_to_licencia(rec)
            if lic:
                existing[lic["id"]] = lic
        for rec in self._collect_tramites_urbanismo():
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

        for rec in self._collect_web_proyectos():
            add(rec)

        try:
            html = self._fetch(TABLON_ALL)
            urbanismo = self._parse_tablon_section(html, self.urbanismo_tablon_id)
        except urllib.error.URLError:
            urbanismo = {}
        tablon = self._collect_tablon()
        for ann_id, rec in urbanismo.items():
            rec = {**rec, "origen": "tablon_urbanismo"}
            add(self._title_to_proyecto(rec, force=True))
            tablon.pop(ann_id, None)
        for rec in tablon.values():
            add(self._title_to_proyecto(rec))

        self._write_jsonl(out_jsonl, rows)
        web = sum(1 for r in rows if r.get("origen") == "web_urbanismo")
        tab_u = sum(1 for r in rows if r.get("origen") == "tablon_urbanismo")
        return {
            "rows": len(rows),
            "status": "ok",
            "web_docs": web,
            "tablon_urbanismo": tab_u,
            "tablon_search": len(rows) - web - tab_u,
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
