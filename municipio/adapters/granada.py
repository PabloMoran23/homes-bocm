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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.granada.org"
SEDE_BASE = "https://sede.granada.org"
MUNICIPIO = "Granada"
ID_PREFIX = "granada"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
TABLON_EDICTOS_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON_EDICTOS"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
PLANEAMIENTO_URL = f"{WEB_BASE}/urbanismo.nsf/vwplan"
AVANCE_PGOM_URL = f"{WEB_BASE}/urbanismo.nsf/byclave/avancepgom"
URBANISMO_HOME_URL = f"{WEB_BASE}/urbanismo.nsf/byclave/inicio"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n|puesta en funcionamiento)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|consulta p[uú]blica|exposici[oó]n p[uú]blica|"
    r"expediente|proyecto|modificaci[oó]n|reparcel|estudio (?:de detalle|ac[uú]stico)|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|ordenanza (?:urban|fiscal)|"
    r"parcela|suelo|sector|innovaci[oó]n|pepri|avance)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(sesi[oó]n de jgl|junta de gobierno local|selecci[oó]n de personal|"
    r"nombramiento|convocatoria.*empleo|subvenci[oó]n deportiv|padrones|"
    r"impuesto sobre construcciones|ordenanza fiscal n[ºo°] 4|ordenanza fiscal n[ºo°] 9)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPTE = re.compile(r"\b((?:19|20)\d{2}[-/]\d{4,6}[A-Z]?)\b")
RE_PLAN_LINK = re.compile(
    r'<a href="(/urbanismo\.nsf/[^"]+!OpenDocument)">([^<]+)</a>',
    re.I,
)
RE_PGOM_LINK = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>([^<]{8,200})</a>',
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
    n = blob.lower()
    if "pgom" in n or "avance" in n:
        return "PGOM"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "plan parcial" in n or "pepri" in n:
        return "plan parcial"
    if "consulta p" in n and "blica" in n:
        return "consulta pública"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "innovaci" in n:
        return "innovación planeamiento"
    if "ordenanza" in n:
        return "ordenanza"
    if "convenio" in n:
        return "convenio urbanístico"
    return "urbanismo"


class GranadaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA (tablón + catálogo) + web Lotus urbanismo (planeamiento PGOU/PGOM)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-granada/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.granada.org" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

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
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON"
        )

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
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_title(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rem = item.get("remitent") or {}
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "expte": str(item.get("externString") or "").strip() or None,
                    "remitente": str(rem.get("description") or ""),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "origen": "tablon_sta",
                }
            )
        return rows

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
            blob = name
            if not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
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

    def _collect_planeamiento_web(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for start in range(1, 120, 30):
            page_url = f"{self.web_base}/urbanismo.nsf/vwplan!OpenView&Start={start}&Count=30"
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                break
            links = RE_PLAN_LINK.findall(html)
            if not links:
                break
            for href, title in links:
                if href in seen:
                    continue
                seen.add(href)
                titulo = _clean_title(title)
                expte_m = RE_EXPTE.search(titulo)
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_text(titulo),
                        "expte": expte_m.group(1) if expte_m else None,
                        "url": urljoin(f"{self.web_base}/", href),
                        "origen": "web_planeamiento",
                    }
                )
        return rows

    def _collect_avance_pgom(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(AVANCE_PGOM_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in RE_PGOM_LINK.findall(html):
            titulo = _clean_title(title)
            if not titulo or len(titulo) < 8:
                continue
            if not re.search(r"(?i)pgom|plano|memoria|ordenaci|informaci|avance|edicto", titulo):
                continue
            full = href if href.startswith("http") else urljoin(f"{self.web_base}/", href)
            if full in seen:
                continue
            seen.add(full)
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_text(titulo),
                    "url": full if full.endswith((".pdf", ".PDF")) else AVANCE_PGOM_URL,
                    "pdf_url": full if full.lower().endswith(".pdf") else None,
                    "origen": "web_avance_pgom",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", TABLON_EDICTOS_URL),
                "fecha_concesion": None,
                "tipo": "tablón edictos electrónicos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico de anuncios y edictos",
                "url": TABLON_EDICTOS_URL,
                "source": "ayuntamiento",
                "nota": "Edictos urbanísticos y licencias desde marzo 2025 (sede STA)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", CATALOGO_URL),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — licencias y obras",
                "url": CATALOGO_URL,
                "source": "ayuntamiento",
                "nota": "Declaraciones responsables y comunicaciones previas vía sede",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", URBANISMO_HOME_URL),
                "fecha_concesion": None,
                "tipo": "portal urbanismo y licencias",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo, obras y licencias — web municipal",
                "url": URBANISMO_HOME_URL,
                "source": "ayuntamiento",
                "nota": "Información y trámites de urbanismo en granada.org",
                "origen": "web_tramite",
            },
        ]

    def _is_urban_blob(self, blob: str) -> bool:
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('remitente') or ''}"
        if not self._is_urban_blob(blob) or not RE_LICENCIA.search(blob):
            return None
        key = row.get("expte") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expte"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_sta",
        }

    def _catalog_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["dboid"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": "catalogo_tramites",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('remitente') or ''}"
        if not self._is_urban_blob(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expte") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "expte": row.get("expte"),
            "source": "ayuntamiento",
            "origen": "tablon_sta",
        }

    def _catalog_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", row["dboid"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "catalogo_tramites",
        }

    def _web_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expte"):
            rec["expte"] = row["expte"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_catalog():
            rec = self._catalog_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_catalog():
            rec = self._catalog_to_licencia(item)
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

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_catalog():
            add(self._catalog_to_proyecto(item))
        for item in self._collect_planeamiento_web():
            add(self._web_to_proyecto(item))
        for item in self._collect_avance_pgom():
            add(self._web_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "web_planeamiento": sum(1 for r in rows if r.get("origen") == "web_planeamiento"),
            "web_avance_pgom": sum(1 for r in rows if r.get("origen") == "web_avance_pgom"),
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
