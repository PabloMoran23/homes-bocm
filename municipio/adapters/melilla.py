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

WEB_BASE = "https://www.melilla.es/melillaportal"
SEDE_BASE = "https://sede.melilla.es"
MUNICIPIO = "Melilla"
ID_PREFIX = "melilla"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/contenedor.jsp?seccion=s_fdes_d4_v1.jsp&contenido=13911&nivel=1400&tipo=6&codResi=1&language=es",
    f"{WEB_BASE}/contenedor.jsp?seccion=s_fdoc_d4_v1.jsp&contenido=8547&nivel=1400&tipo=5&codResi=1&language=es",
    f"{WEB_BASE}/contenedor.jsp?seccion=s_fdoc_d4_v1.jsp&contenido=23991&nivel=1400&tipo=5&codResi=1&language=es",
    f"{WEB_BASE}/contenedor.jsp?seccion=s_fdes_d4_v1.jsp&contenido=31211&nivel=1400&tipo=6&codResi=1&language=es",
    f"{WEB_BASE}/contenedor.jsp?seccion=s_fdes_d4_v1.jsp&codbusqueda=799&language=es&codResi=1&layout=contenedor.jsp&codAdirecto=87",
    f"{WEB_BASE}/contenedor.jsp?seccion=s_fdes_d4_v1.jsp&contenido=3117&nivel=1400&tipo=6&codResi=1&language=es",
    f"{WEB_BASE}/contenedor.jsp?seccion=s_fdes_d4_v1.jsp&contenido=3127&nivel=1400&tipo=6&codResi=1&language=es",
    f"{WEB_BASE}/contenedor.jsp?seccion=s_fdes_d4_v1.jsp&contenido=3115&nivel=1400&tipo=6&codResi=1&language=es",
    f"{WEB_BASE}/contenedor.jsp?seccion=s_fdes_d4_v1.jsp&contenido=3119&nivel=1400&tipo=6&codResi=1&language=es",
    f"{SEDE_BASE}/melillaPortal/transparencia/se_contenedor2.jsp?codMenu=308&codMenuPN=21&codResi=1&language=es&layout=se_contenedor2.jsp&seccion=se_seccion_menus.jsp",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n|"
    r"c[eé]dula urban|demolici[oó]n|segregaci[oó]n|parcelaci[oó]n|calificaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio|memoria|planos?|aprobaci[oó]n|revisi[oó]n|bome|instrumento|"
    r"ordenaci[oó]n|suelo|ruina|sector|ue[\s-]?\d|normas urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proceso selectivo|empleo p[uú]blico|punto limpio|gaviota|huerto urbano|"
    r"ordenanza fiscal|tasa por|padrones?|impuesto sobre|subvenci[oó]n deportiv|"
    r"residuos urbanos y limpieza viaria|protecci[oó]n del medio ambiente urbano contra la emisi[oó]n de ruidos)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_GENERIC_TITLE = re.compile(
    r"(?i)^(parte\s*\d+|acuerdo|memoria|normas(?:\s+urban[ií]sticas)?|plano(?:\s+.+)?|publicaci[oó]n(?:\s+bome)?)$",
)
RE_PDF_LINK = re.compile(r'<a[^>]+href="([^"]+\.pdf[^"]*)"[^>]*>([^<]+)</a>', re.I)
RE_PAGE_TITLE = re.compile(r"<title>\s*([^<|]+)", re.I)
DGVU_HINT = re.compile(r"(?i)DGVU|vivienda.*urbanismo|PR2\.03\.10")
URBAN_REMITENTES = (
    "Dirección General de la Vivienda, Patrimonio y Urbanismo",
    "Dirección General de Obras Públicas",
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


def _fecha_from_text(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        y, mo, d = int(obj["year"]), int(obj["month"]), int(obj["day"])
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan especial" in b:
        return "plan especial"
    if "plan parcial" in b or re.search(r"ue[\s-]?\d", b):
        return "plan parcial"
    if "revisi" in b and "pgou" in b:
        return "revisión PGOU"
    if "ruina" in b:
        return "ruina"
    if "calificaci" in b:
        return "calificación urbanística"
    if "convenio" in b:
        return "convenio urbanístico"
    if "bome" in b:
        return "publicación BOME"
    if "instrumento" in b:
        return "instrumento de ordenación"
    return "urbanismo"


class MelillaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal melilla.es (EADmin) + sede STA (tablón + catálogo trámites DGVU)."""

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

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-melilla/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or self.sede_base in url else None
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            raw = resp.read()
        for enc in ("utf-8", "latin-1", "iso-8859-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _abs_url(self, href: str, page_url: str) -> str:
        return unescape(urllib.parse.urljoin(page_url, href))

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _collect_catalog(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = _clean_title(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or item.get("code") or "")
            if not name or not dboid:
                continue
            blob = name + " " + _clean_title(str(item.get("descriptionExt") or ""))
            if not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if RE_EXCLUDE.search(blob):
                continue
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                    "dgvu": bool(DGVU_HINT.search(blob)),
                }
            )
        return rows

    def _page_heading(self, html: str, fallback: str) -> str:
        m = RE_PAGE_TITLE.search(html)
        if m:
            t = _clean_title(m.group(1))
            t = re.sub(r"^Ciudad Autónoma de Melilla\s*-?\s*", "", t, flags=re.I).strip()
            if t:
                return t[:200]
        return fallback

    def _extract_portal_pdfs(self, page_url: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []
        page_title = self._page_heading(html, page_url)
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        context = page_title
        for href, raw_title in RE_PDF_LINK.findall(html):
            pdf_url = self._abs_url(href, page_url)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            title = _clean_title(raw_title)
            if RE_GENERIC_TITLE.match(title):
                title = f"{context}: {title}"
            elif len(title) >= 12:
                context = title
            fecha = _fecha_from_text(title) or _fecha_from_text(pdf_url)
            records.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "page_title": page_title,
                }
            )
        return records

    def _collect_seed_documents(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            pdfs = self._extract_portal_pdfs(page_url)
            if pdfs:
                items.extend(pdfs)
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            heading = self._page_heading(html, page_url)
            if RE_PROYECTO.search(heading) and not RE_EXCLUDE.search(heading):
                items.append(
                    {
                        "titulo": heading,
                        "fecha": _fecha_from_text(heading),
                        "url": page_url,
                        "pdf_url": None,
                        "page_title": heading,
                    }
                )
        return items

    def _tablon_row_to_record(self, row: dict[str, Any]) -> tuple[str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or rem.get("code") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, remitente, fecha, url

    def _catalog_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if not item.get("dgvu") and RE_EXCLUDE.search(blob):
            return None
        return {
            "id": _stable_id("lic", item["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": blob[:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, rem, fecha, url = self._tablon_row_to_record(row)
        blob = f"{title} {rem}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha or None,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": "tablon_sta",
        }

    def _to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str | None,
        pdf_url: str | None = None,
        origen: str | None = None,
    ) -> dict[str, Any] | None:
        blob = title or ""
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", pdf_url or url + title),
            "municipio": MUNICIPIO,
            "titulo": blob[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        if origen:
            rec["origen"] = origen
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_catalog():
            add(self._catalog_to_licencia(item))
        for item in self._collect_tablon():
            add(self._tablon_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
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

        for item in self._collect_tablon():
            title, rem, fecha, url = self._tablon_row_to_record(item)
            tab_cat = str((item.get("tablon") or {}).get("description") or "")
            if tab_cat.strip().startswith("Normativa") and rem not in URBAN_REMITENTES:
                continue
            if rem not in URBAN_REMITENTES and not RE_PROYECTO.search(f"{title} {rem}"):
                continue
            if RE_EXCLUDE.search(f"{title} {rem}"):
                continue
            add(self._to_proyecto(title, url, fecha or None, origen="tablon_sta"))

        for item in self._collect_catalog():
            add(
                self._to_proyecto(
                    item["titulo"],
                    item["url"],
                    None,
                    origen=item.get("origen"),
                )
            )

        for doc in self._collect_seed_documents():
            add(
                self._to_proyecto(
                    doc["titulo"],
                    doc["url"],
                    doc.get("fecha"),
                    pdf_url=doc.get("pdf_url"),
                    origen="portal_web",
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "portal_docs": sum(1 for r in rows if r.get("origen") == "portal_web"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
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
