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

WP_BASE = "https://www.aytoburgos.es"
SEDE_BASE = "https://sede.aytoburgos.es"
MUNICIPIO = "Burgos"
ID_PREFIX = "burgos"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"

ANUNCIOS_BASE = f"{WP_BASE}/anuncios-urbanismo"
INSTRUMENTOS_BASE = f"{WP_BASE}/instrumentos-planeamiento-gestion"
URBANISMO_URL = f"{WP_BASE}/urbanismo"

ANUNCIOS_PORTLET = "com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_gCaAF8Ntm38m"
INSTRUMENTOS_PORTLET = "com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_o6ZrRXHm8Z7I"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban|de uso)|obra(?:s)? (?:mayor|menor|en v[ií]a)|"
    r"primera ocupaci[oó]n|vado|exc-urb|prov-urb)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|peri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de detalle|ac[uú]stico)|memoria|aprobaci[oó]n|urbanizaci[oó]n|"
    r"enajenaci[oó]n|expropi|sector|pla-fom|est-pgou|mod-pgou|norm-pgou|"
    r"exc-urb|prov-urb|subasta|gamonal|bulevar|villatoro)",
)
RE_NOISE = re.compile(
    r"(?i)(ordenanza fiscal|ordenanza n[uú]mero|base de precios|decreto legislativo|"
    r"documentaci[oó]n necesaria para tramitar|estatutos del consorcio|"
    r"ley 5/1999|reguladora del impuesto|reguladora de la tasa|"
    r"reguladora instalaciones|reguladora de la señalizaci[oó]n|"
    r"plan municipal de vivienda 2023|plan de accesibilidad|calendario fiscal)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_MY = re.compile(r"(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LIFERAY_LINK = re.compile(
    r'href="(https://www\.aytoburgos\.es/(?:anuncios-urbanismo|instrumentos-planeamiento-gestion|urbanismo)'
    r'/-/asset_publisher/[^"]+)"[^>]*>\s*([^<\n\t][^<\n]{4,500})',
    re.I,
)
RE_CARD_LINK = re.compile(
    r'href="(https://www\.aytoburgos\.es/[^"]*asset_publisher/[^"]+)"[^>]*class="[^"]*card-title[^"]*"[^>]*>\s*([^<]+)',
    re.I,
)
URBANISMO_REMITENT = re.compile(r"(?i)gerencia municipal de urbanismo")


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
    m = RE_FECHA_MY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(2)), int(m.group(1)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y) for y in RE_YEAR.findall(text or "") if 1980 <= int(y) <= 2035]
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


def _clean_title(raw: str) -> str:
    return unescape(re.sub(r"\s+", " ", raw or "")).strip()[:500]


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "exc-urb" in n or "uso excepcional" in n:
        return "autorización uso excepcional"
    if "prov-urb" in n or "uso provisional" in n:
        return "autorización uso provisional"
    if "pla-fom" in n or "plan de fomento" in n:
        return "plan de fomento"
    if "est-pgou" in n or "estudio de detalle" in n:
        return "estudio de detalle"
    if "mod-pgou" in n or "modificaci" in n:
        return "modificación PGOU"
    if "norm-pgou" in n:
        return "normas PGOU"
    if "plan parcial" in n or "plpar" in n:
        return "plan parcial"
    if "plan especial" in n or "peri" in n:
        return "plan especial"
    if "urbanizaci" in n or "proyecto de urbanizaci" in n:
        return "proyecto urbanización"
    if "enajenaci" in n or "subasta" in n:
        return "enajenación suelo"
    if "expropi" in n:
        return "expropiación"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    return "planeamiento"


class BurgosAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal Liferay + sede STA (tablón JSON + catálogo CATSERV)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.delay_s = float(self.config.get("request_delay_s", 0.35))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-burgos/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

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

    def _liferay_page_url(self, base: str, portlet: str, cur: int) -> str:
        if cur == 0:
            return base
        return (
            f"{base}?p_p_id={portlet}&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view"
            f"&_{portlet}_cur={cur}&p_r_p_resetCur=false"
        )

    def _collect_liferay_links(self, base: str, portlet: str, max_pages: int = 12) -> list[dict[str, str]]:
        seen: set[str] = set()
        rows: list[dict[str, str]] = []
        for cur in range(max_pages):
            try:
                html = self._fetch(self._liferay_page_url(base, portlet, cur))
            except urllib.error.URLError:
                break
            found = 0
            for m in RE_LIFERAY_LINK.finditer(html):
                url = unescape(m.group(1).split("&amp;")[0])
                title = _clean_title(m.group(2))
                if url in seen:
                    continue
                seen.add(url)
                found += 1
                rows.append({"url": url, "titulo": title})
            if found == 0:
                break
        return rows

    def _collect_urbanismo_cards(self) -> list[dict[str, str]]:
        try:
            html = self._fetch(URBANISMO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for m in RE_CARD_LINK.finditer(html):
            url = unescape(m.group(1).split("&amp;")[0])
            title = _clean_title(m.group(2))
            if url in seen:
                continue
            seen.add(url)
            rows.append({"url": url, "titulo": title})
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _tablon_row(self, row: dict[str, Any]) -> tuple[str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or rem.get("code") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, remitente, fecha, url

    def _collect_catalog_licencias(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            family = str(item.get("nameFamily") or "")
            name = str(item.get("name") or "").strip()
            code = str(item.get("code") or item.get("dboid") or name)
            if family != "Licencias":
                continue
            if not RE_LICENCIA.search(name):
                continue
            dboid = str((item.get("procedimiento") or {}).get("dboid") or item.get("dboid") or code)
            url = f"{CATALOGO_URL}&DETALLE={dboid}"
            rows.append(
                {
                    "id": _stable_id("lic", code),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": name[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite catálogo sede; no concesión publicada",
                    "tramite_code": code,
                }
            )
        return rows

    def _to_licencia(self, title: str, url: str, fecha: str) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
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
        }

    def _to_proyecto(self, title: str, url: str, fecha: str, origen: str) -> dict[str, Any] | None:
        if RE_NOISE.search(title):
            return None
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        parsed_fecha = fecha or _parse_fecha_dmy(title) or ""
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": parsed_fecha or None,
            "tipo": _proyecto_tipo(title),
            "url": url,
            "source": "ayuntamiento",
            "origen": origen,
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_catalog_licencias():
            add(item)

        for item in self._collect_tablon():
            title, rem, fecha, url = self._tablon_row(item)
            blob = f"{title} {rem}"
            if URBANISMO_REMITENT.search(rem) or RE_LICENCIA.search(blob):
                add(self._to_licencia(title, url, fecha))

        for link in self._collect_liferay_links(ANUNCIOS_BASE, ANUNCIOS_PORTLET, max_pages=4):
            add(self._to_licencia(link["titulo"], link["url"], _parse_fecha_dmy(link["titulo"]) or ""))

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_catalogo+tablon+anuncios"}

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

        for link in self._collect_liferay_links(INSTRUMENTOS_BASE, INSTRUMENTOS_PORTLET, max_pages=10):
            add(
                self._to_proyecto(
                    link["titulo"],
                    link["url"],
                    _parse_fecha_dmy(link["titulo"]) or "",
                    "instrumentos_planeamiento",
                )
            )

        for link in self._collect_liferay_links(ANUNCIOS_BASE, ANUNCIOS_PORTLET, max_pages=4):
            add(
                self._to_proyecto(
                    link["titulo"],
                    link["url"],
                    _parse_fecha_dmy(link["titulo"]) or "",
                    "anuncios_urbanismo",
                )
            )

        for link in self._collect_urbanismo_cards():
            add(
                self._to_proyecto(
                    link["titulo"],
                    link["url"],
                    _parse_fecha_dmy(link["titulo"]) or "",
                    "urbanismo_actualidad",
                )
            )

        for item in self._collect_tablon():
            title, rem, fecha, url = self._tablon_row(item)
            if URBANISMO_REMITENT.search(rem) or RE_PROYECTO.search(title):
                add(self._to_proyecto(title, url, fecha, "sede_tablon"))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "instrumentos": len(self._collect_liferay_links(INSTRUMENTOS_BASE, INSTRUMENTOS_PORTLET, max_pages=1)),
            "anuncios": len(self._collect_liferay_links(ANUNCIOS_BASE, ANUNCIOS_PORTLET, max_pages=1)),
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
