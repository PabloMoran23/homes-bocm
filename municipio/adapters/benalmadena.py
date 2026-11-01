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
from urllib.parse import unquote

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.benalmadena.es"
SEDE_BASE = "https://sede.benalmadena.es"
MUNICIPIO = "Benalmádena"
ID_PREFIX = "benalmadena"
INE_CODE = "29025"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_TABLON&lang=ES"
)
CATALOGO_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_CATSERV&lang=ES"
)
EXPEDIENTES_IP_URL = (
    f"{WEB_BASE}/contenido_transparencia.php?"
    f"m=benalmadena-transparencia&s=informacion-publica-de-expedientes-de-urbanismo"
)
EXPEDIENTES_IP_ALT = f"{WEB_BASE}/informacion-publica-de-expedientes-de-urbanismo.html"
PGOU_TRANSP_URL = (
    f"{WEB_BASE}/contenido_transparencia.php?"
    f"m=benalmadena-transparencia&s=pgou-planeamiento-general-vigente"
)
SITUA_SEARCH = f"https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid={INE_CODE}"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n|vado|legalizaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|expte|"
    r"proyecto|modificaci[oó]n|reparcel|estudio (?:de detalle|ac[uú]stico)|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|sector|sp-|"
    r"innovaci[oó]n|urbanizaci[oó]n|memoria|planos|bop|edicto|ordenanza|"
    r"expropiaci[oó]n|calificaci[oó]n|parcela|suelo)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(r[eé]gimen funcionarial|convocatoria.*plaza|selecci[oó]n de personal|"
    r"padr[oó]n municipal|denegatorios en el padr[oó]n|subvenci[oó]n|deportes|"
    r"bolsa de empleo|bombero|formaci[oó]n|calendario fiscal|boe y tabl[oó]n electr[oó]nico edictos)"
)
RE_EXCLUDE_CATALOG_LIC = re.compile(
    r"(?i)(adopci[oó]n de animales|bombero|formaci[oó]n fuera del plan|"
    r"plusval[ií]a|taxi|mercado ambulante)",
)
RE_SECTION = re.compile(
    r"<thead>\s*<tr>\s*<th[^>]*colspan[^>]*>(.*?)</th>\s*</tr>\s*</thead>(.*?)"
    r"(?=<thead>\s*<tr>|<div class=\"clearfix\"|$)",
    re.I | re.S,
)
RE_PDF_HREF = re.compile(r'href="(https://www\.benalmadena\.es/docs/[^"]+\.pdf[^"]*)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_FILE = re.compile(r"(20\d{2})(\d{2})(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPTE = re.compile(
    r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*([0-9]{1,4}[/\-][0-9]{4}[^/\s]*)|"
    r"(\d{4}/\d{5,}[A-Z])|(\d{4}-\d{5,}[a-z])"
)

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "licencia de obra",
    "licencia urban",
    "comunicación previa",
    "comunicacion previa",
    "declaración responsable",
    "declaracion responsable",
    "vados",
    "primera ocupación",
    "primera ocupacion",
    "legalización",
    "legalizacion",
    "autorización previa",
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
    m = RE_FECHA_FILE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
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
    t = re.sub(r"\s+", " ", t).strip()
    return t[:500]


def _expte_from_blob(blob: str) -> str | None:
    for m in RE_EXPTE.finditer(blob):
        for g in m.groups():
            if g:
                return g.strip()
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "estudio de detalle" in n or "estudio detalle" in n:
        return "estudio de detalle"
    if "reparcel" in n:
        return "reparcelación"
    if "convenio" in n:
        return "convenio urbanístico"
    if "innovaci" in n or "pgou" in n:
        return "PGOU"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "expropiaci" in n:
        return "expropiación"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "plan parcial" in n or re.search(r"\bsp[- ]?\d", n):
        return "plan parcial"
    if "resumen ejecutivo" in n:
        return "resumen ejecutivo"
    if "licencia" in n:
        return "licencia publicada"
    return "planeamiento"


class BenalmadenaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web municipal (IP expedientes) + sede STA TAO (tablón + catálogo trámites)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.expedientes_url = str(self.config.get("expedientes_url") or EXPEDIENTES_IP_URL)
        self.situa_url = str(self.config.get("situa_url") or SITUA_SEARCH)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-benalmadena/1.0")},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            raw = resp.read()
            try:
                return raw.decode(charset)
            except UnicodeDecodeError:
                return raw.decode("latin-1", errors="replace")

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_TABLON&lang=ES"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_CATSERV&lang=ES"
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_title(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rem = item.get("remitent") or {}
            remitente = str(rem.get("description") or rem.get("code") or "")
            expte = str(item.get("externString") or "").strip() or None
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "expte": expte,
                    "remitente": remitente,
                    "url": self._tablon_detail_url(dboid),
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = _clean_title(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or "")
            if not name or not dboid:
                continue
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _collect_web_expedientes(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in (self.expedientes_url, EXPEDIENTES_IP_ALT, PGOU_TRANSP_URL):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_SECTION.finditer(html):
                section_title = _clean_title(m.group(1))
                block = m.group(2)
                if not section_title or len(section_title) < 8:
                    continue
                pdfs = RE_PDF_HREF.findall(block)
                if not pdfs and not RE_PROYECTO.search(section_title):
                    continue
                pdf_url = None
                for p in pdfs:
                    low = p.lower()
                    if "anuncio" in low or "aprobacion" in low or "resumen" in low:
                        pdf_url = p
                        break
                if not pdf_url and pdfs:
                    pdf_url = pdfs[0]
                key = f"{section_title}|{pdf_url or page_url}"
                if key in seen:
                    continue
                seen.add(key)
                blob = f"{section_title} {pdf_url or ''}"
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(section_title):
                    continue
                rows.append(
                    {
                        "titulo": section_title,
                        "fecha": _fecha_from_text(f"{section_title} {pdf_url or ''}"),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "expte": _expte_from_blob(section_title),
                        "origen": "web_ip_expedientes",
                    }
                )
            for href in RE_PDF_HREF.findall(html):
                if href in seen:
                    continue
                name = _clean_title(unquote(Path(href).name))
                blob = f"{name} {href}"
                if not RE_PROYECTO.search(blob):
                    continue
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(name):
                    continue
                seen.add(href)
                rows.append(
                    {
                        "titulo": name,
                        "fecha": _fecha_from_text(blob),
                        "url": page_url,
                        "pdf_url": href,
                        "expte": _expte_from_blob(blob),
                        "origen": "web_pdf",
                    }
                )
        return rows

    def _situa_reference(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", self.situa_url),
            "municipio": MUNICIPIO,
            "titulo": f"PGOU Benalmádena — consulta SITUA (Junta de Andalucía, INE {INE_CODE})",
            "fecha": None,
            "tipo": "PGOU",
            "url": self.situa_url,
            "source": "ayuntamiento",
            "origen": "situa_referencia",
            "nota": "Visor regional; sin geometría REST enlazada al expediente municipal",
        }

    def _title_to_licencia(
        self,
        title: str,
        url: str,
        fecha: str | None,
        *,
        nota: str | None = None,
        origen: str | None = None,
    ) -> dict[str, Any] | None:
        if RE_EXCLUDE.search(title):
            return None
        lower = title.lower()
        if not RE_LICENCIA.search(title) and not any(p in lower for p in LICENCIA_TRAMITE_PATTERNS):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha,
            "tipo": "trámite licencia" if nota else "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }
        if nota:
            rec["nota"] = nota
        if origen:
            rec["origen"] = origen
        expte = _expte_from_blob(title)
        if expte:
            rec["expte"] = expte
        return rec

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('remitente', '')} {row.get('expte', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("dboid") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("origen"):
            rec["origen"] = row["origen"]
        if row.get("expte"):
            rec["expte"] = row["expte"]
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

        for item in self._collect_tablon():
            add(
                self._title_to_licencia(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                    origen=item.get("origen"),
                )
            )

        for item in self._collect_catalog_tramites():
            if RE_EXCLUDE_CATALOG_LIC.search(item["titulo"]):
                continue
            lower = item["titulo"].lower()
            if not RE_LICENCIA.search(item["titulo"]) and not any(
                p in lower for p in LICENCIA_TRAMITE_PATTERNS
            ):
                continue
            add(
                self._title_to_licencia(
                    item["titulo"],
                    item["url"],
                    None,
                    nota="Página informativa de trámite; no concesión publicada",
                    origen=item.get("origen"),
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_sta_catalogo"}

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

        tablon = self._collect_tablon()
        web_exp = self._collect_web_expedientes()
        for item in tablon:
            add(self._row_to_proyecto(item))
        for item in web_exp:
            add(self._row_to_proyecto(item))
        add(self._situa_reference())

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": len(tablon),
            "web_expedientes": len(web_exp),
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
