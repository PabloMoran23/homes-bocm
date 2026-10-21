from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.tarragona.cat"
SEDE_BASE = "https://seu.tarragona.cat"
MUNICIPIO = "Tarragona"
ID_PREFIX = "tarragona"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES"
URBANISME_RSS = f"{WEB_BASE}/lajuntament/territori/actualitat-durbanisme/RSS"

PLANEJAMENT_PAGES: tuple[tuple[str, str], ...] = (
    ("PTS2_PLA_GENERAL_VIGENT", "planeamiento general"),
    ("PTS2_PLANEJAMENT_ATRAMIT", "planeamiento en trámite"),
    ("PTS2_PROJECTES_URB", "proyecto de urbanización"),
)

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "llicència d'obres",
    "llicencia de obras",
    "comunicació prèvia",
    "comunicacion previa",
    "declaració responsable",
    "declaracion responsable",
    "informe urbanístic",
    "informe urbanistico",
    "primera ocupació",
    "primera ocupacion",
    "certificat d'obra",
    "certificado de obra",
)

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|licències|licencias|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|declaraci[oó] responsable|autoritzaci[oó] previa|"
    r"obra (?:major|menor|mayor)|primera ocupaci[oó]|informe urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|plan (?:parcial|especial|general)|pgou|poum|pau\b|"
    r"pol[ií]gon d'actuaci|projecte d'urban|projecto de urban|modificaci[oó]|"
    r"informaci[oó] p[uú]blica|exposici[oó] p[uú]blica|expedient|edict|reparcel|"
    r"estudi de detall|sector|peu\b|pmu|pge|conveni urban|suspensi[oó] de llic|"
    r"pla especial|pla de millora|avan[cç] de poum|urbanitz)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proc[eé]s selectiu|oposici[oó]n|subvenci[oó]n|padr[oó]n|iae\b|"
    r"notificaci[oó]n colectiva|impost sobre|tribut|festa|agenda|concert|"
    r"guardia urbana|adn cani|protecci[oó] civil.*incendi)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(
            int(obj["year"]),
            int(obj["month"]),
            int(obj["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _proyecto_tipo(blob: str, section: str = "") -> str:
    n = f"{blob} {section}".lower()
    if "informaci" in n and ("públic" in n or "public" in n):
        return "información pública"
    if "pla especial" in n or "plan especial" in n:
        return "plan especial"
    if "pla de millora" in n or "plan de mejora" in n:
        return "plan de mejora urbana"
    if "poum" in n or "avanç de poum" in n:
        return "avance POUM"
    if "projecte d'urban" in n or "proyecto de urbaniz" in n:
        return "proyecto de urbanización"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "pla general" in n or "pgou" in n:
        return "planeamiento general"
    if "pau" in n or "polígon" in n or "poligon" in n:
        return "polígono de actuación"
    if "conveni" in n:
        return "convenio urbanístico"
    return section or "urbanismo"


class TarragonaAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone tarragona.cat + sede STA (tablón, planejament) + RSS actualitat urbanisme."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.fetch_timeout = int(self.config.get("fetch_timeout_s", 180))

    def _fetch(self, url: str, *, timeout: int | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-tarragona/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout or self.fetch_timeout) as resp:
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
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON&lang=ES"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO&lang=ES"
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            raw = str(item.get("descriptionProc") or item.get("externString") or "")
            titulo = _strip_html(raw)[:500]
            if not titulo or not dboid:
                continue
            rem = item.get("remitent") or {}
            tab = item.get("tablon") or {}
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "extern": str(item.get("externString") or ""),
                    "remitente": str(rem.get("description") or ""),
                    "seccion": str(tab.get("description") or ""),
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _collect_planejament(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_code, section in PLANEJAMENT_PAGES:
            url = (
                f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
                f"APP_CODE=STA&PAGE_CODE={page_code}&lang=ES"
            )
            try:
                html = self._fetch(url, timeout=90)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for item in self._extract_sta_dataset(html, page_code):
                dboid = str(item.get("dboid") or "")
                raw = str(item.get("descriptionProc") or item.get("externString") or "")
                titulo = _strip_html(raw)[:500]
                if not titulo:
                    continue
                tab = item.get("tablon") or {}
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _xml_date(item.get("pubDateIni")),
                        "url": self._tablon_detail_url(dboid) if dboid else url,
                        "extern": str(item.get("externString") or ""),
                        "seccion": str(tab.get("description") or section),
                        "origen": f"planejament_{page_code}",
                    }
                )
        return rows

    def _collect_rss(self) -> list[dict[str, Any]]:
        try:
            xml = self._fetch(URBANISME_RSS, timeout=60)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return rows
        ns = {
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "dc": "http://purl.org/dc/elements/1.1/",
        }
        for item in root.findall(".//{http://purl.org/rss/1.0/}item"):
            about = item.attrib.get(f"{{{ns['rdf']}}}about", "")
            title_el = item.find("{http://purl.org/rss/1.0/}title")
            date_el = item.find("dc:date", ns)
            title = (title_el.text or "").strip() if title_el is not None else ""
            fecha = None
            if date_el is not None and date_el.text:
                fecha = _parse_fecha_iso(date_el.text[:10])
            if title and about:
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": about,
                        "origen": "rss_urbanisme",
                    }
                )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, timeout=90)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = _strip_html(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or "")
            if not name or not dboid:
                continue
            low = name.lower()
            if not any(p in low for p in LICENCIA_TRAMITE_PATTERNS):
                continue
            rows.append(
                {
                    "titulo": name,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                }
            )
        return rows

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
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            rows.append(obj)
                    except json.JSONDecodeError:
                        pass
        return rows

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('remitente', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        if RE_EXCLUDE.search(blob) and not RE_LICENCIA.search(blob):
            return None
        url = str(row.get("url") or self.sede_base)
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row.get("titulo"),
            "url": url,
            "source": "ayuntamiento",
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('extern', '')} {row.get('remitente', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        url = str(row.get("url") or self.web_base)
        section = str(row.get("seccion") or "")
        return {
            "id": _stable_id("proy", url + str(row.get("titulo", ""))),
            "municipio": MUNICIPIO,
            "titulo": row.get("titulo"),
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob, section),
            "url": url,
            "source": "ayuntamiento",
        }

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._collect_tablon():
            add(self._row_to_licencia(row))

        for tram in self._collect_licencia_tramites():
            add(
                {
                    "id": _stable_id("lic", tram["url"]),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": tram["titulo"],
                    "url": tram["url"],
                    "source": "ayuntamiento",
                }
            )

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_sta"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
        for row in tablon:
            add(self._row_to_proyecto(row))
        planejament = self._collect_planejament()
        for row in planejament:
            add(self._row_to_proyecto(row))
        rss = self._collect_rss()
        for row in rss:
            add(self._row_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": len(tablon),
            "planejament": len(planejament),
            "rss": len(rss),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
