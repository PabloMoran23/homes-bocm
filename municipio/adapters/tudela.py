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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.tudela.es"
SEDE_BASE = "https://sede.tudela.es"
MUNICIPIO = "Tudela"
ID_PREFIX = "tudela"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
URBANISMO_WEB = f"{WEB_BASE}/tu-ciudad/urbanismo-vivienda-obras"
ANUNCIOS_URBANISMO = f"{WEB_BASE}/anuncios/urbanismo-viviendas-obras"
INSTANCIAS_URL = f"{WEB_BASE}/ventanilla-municipal/instancias-modelos"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|ocupaci[oó]n temporal|gr[uú]a|instalaci[oó]n de gr[uú]a)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pum\b|peau|pepri|"
    r"emot|pmus|informaci[oó]n p[uú]blica|consulta p[uú]blica|exposici[oó]n p[uú]blica|"
    r"expediente|participaci[oó]n ciudadana|modificaci[oó]n|reparcel|estudio|"
    r"aprobaci[oó]n|ordenanza.*urban|rehabilitaci[oó]n|regeneraci[oó]n urban|"
    r"normativa urban|convenio urban|disciplina urban|pol[ií]gono|parcela)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(subvenci[oó]n navide|agenda deportiva|a tu bola|taller psicolog|"
    r"convocatoria.*peñas|carteles.*publicidad general|ordenanza.*postes de recarga)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPTE = re.compile(
    r"(?i)\b(?:exp(?:ediente)?\.?\s*)?((?:\d{1,4}/\d{4}/[A-Z]{2,8})|(?:\d{1,4}/\d{4}/[A-Z]+))\b"
)
RE_ANUNCIO_HREF = re.compile(r'href="(/anuncio/[^"]+)"[^>]*>([^<]+)', re.I)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)
RE_FECHA_ACTUALIDAD = re.compile(r'class="fecha_actualidad"[^>]*>\s*([^<]+)', re.I)
RE_URBANISMO_DOC = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        m = RE_FECHA_DASH.search(text or "")
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
    if "peau" in n:
        return "plan especial de actuación urbana"
    if "pepri" in n:
        return "plan parcial"
    if "pum" in n or "plan urbanístico municipal" in n or "pgou" in n:
        return "planeamiento municipal"
    if "emot" in n:
        return "EMOT"
    if "pmus" in n:
        return "plan de movilidad urbana"
    if "participaci" in n and "ciudadana" in n:
        return "participación ciudadana"
    if "consulta p" in n and "blica" in n:
        return "consulta pública"
    if "exposici" in n or "informaci" in n:
        return "información pública"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "convenio" in n:
        return "convenio urbanístico"
    return "urbanismo"


class TudelaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal tudela.es (anuncios + docs urbanismo) + sede STA (tablón + catálogo)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.max_anuncio_pages = int(self.config.get("max_anuncio_pages", 25))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-tudela/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str, page_url: str = WEB_BASE) -> str:
        return unescape(urljoin(page_url, href))

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
            html = self._fetch(TABLON_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_title(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rem = item.get("remitent") or {}
            expte_raw = str(item.get("externString") or "").strip()
            expte_m = RE_EXPTE.search(expte_raw) or RE_EXPTE.search(titulo)
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "expte": expte_m.group(1) if expte_m else (expte_raw or None),
                    "remitente": str(rem.get("description") or ""),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _collect_catalog(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL)
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

    def _collect_urbanismo_docs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(URBANISMO_WEB)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in RE_URBANISMO_DOC.findall(html):
            if "/docs/urbanismo/" not in href.lower() and "urbanismo" not in href.lower():
                continue
            if not re.search(r"\.(pdf|zip)$", href, re.I):
                continue
            full = self._abs_url(href, URBANISMO_WEB)
            if full in seen:
                continue
            seen.add(full)
            titulo = _clean_title(title)
            if len(titulo) < 3:
                titulo = full.rsplit("/", 1)[-1]
            rows.append(
                {
                    "titulo": f"Planeamiento Tudela — {titulo}",
                    "fecha": _fecha_from_text(titulo) or _fecha_from_text(full),
                    "url": full,
                    "origen": "web_planeamiento",
                }
            )
        return rows

    def _collect_anuncios_urbanismo(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for page in range(1, self.max_anuncio_pages + 1):
            list_url = ANUNCIOS_URBANISMO if page == 1 else f"{ANUNCIOS_URBANISMO}/{page}"
            try:
                html = self._fetch(list_url)
            except urllib.error.URLError:
                break
            found = 0
            for path, raw_title in RE_ANUNCIO_HREF.findall(html):
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                titulo = _clean_title(raw_title)
                if not titulo or RE_EXCLUDE.search(titulo):
                    continue
                detail_url = self._abs_url(path, self.web_base)
                fecha = None
                try:
                    detail_html = self._fetch(detail_url)
                    m = RE_H1.search(detail_html)
                    if m:
                        titulo = _clean_title(m.group(1)) or titulo
                    fm = RE_FECHA_ACTUALIDAD.search(detail_html)
                    if fm:
                        fecha = _parse_fecha_dmy(fm.group(1).strip())
                except urllib.error.URLError:
                    pass
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": fecha or _fecha_from_text(titulo),
                        "url": detail_url,
                        "origen": "web_anuncios_urbanismo",
                    }
                )
                found += 1
            if found == 0:
                break
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", TABLON_URL),
                "fecha_concesion": None,
                "tipo": "tablón electrónico de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios y edictos (sede electrónica)",
                "url": TABLON_URL,
                "source": "ayuntamiento",
                "nota": "Edictos de licencias y exposiciones públicas urbanísticas",
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
                "nota": "Trámites telemáticos STA (licencias, comunicaciones, grúas)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", INSTANCIAS_URL),
                "fecha_concesion": None,
                "tipo": "instancias y modelos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Instancias y modelos — licencias de obra y actividad",
                "url": INSTANCIAS_URL,
                "source": "ayuntamiento",
                "nota": "Formularios PDF (licencia de obras, obras comunicadas, ocupación vía pública)",
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
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
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
        for item in self._collect_urbanismo_docs():
            add(self._web_to_proyecto(item))
        for item in self._collect_anuncios_urbanismo():
            if self._is_urban_blob(item["titulo"]):
                add(self._web_to_proyecto(item))
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "anuncios": sum(1 for r in rows if r.get("origen") == "web_anuncios_urbanismo"),
            "planeamiento": sum(1 for r in rows if r.get("origen") == "web_planeamiento"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_proyectos(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": result["rows"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result
