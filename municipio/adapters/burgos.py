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

WP_BASE = "https://www.aytoburgos.es"
SEDE_BASE = "https://sede.aytoburgos.es"
MUNICIPIO = "Burgos"
ID_PREFIX = "burgos"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
INSTRUMENTOS_URL = f"{WP_BASE}/instrumentos-planeamiento-gestion"
ANUNCIOS_URL = f"{WP_BASE}/anuncios-urbanismo"
LICENCIAS_URL = f"{WP_BASE}/licencias-y-servicios"

ANUNCIOS_PUBLISHER = "com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_gCaAF8Ntm38m"

RE_LICENCIA = re.compile(
    r"(?i)(licencia urban|licencia de obra|licencia ambiental|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable.*obra|solicitud de licencia|autorizaci[oó]n previa|"
    r"licencia urbanística|nueva planta|reforma o rehabilitaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|modificaci[oó]n|aprobaci[oó]n|"
    r"estudio de detalle|reparcel|sector|expropi|enajenaci[oó]n|prov-urb|exc-urb|"
    r"tram-peri|urb-pgou|est-pgou|mod-pgou|pla-fom|proyecto de urbanizaci|"
    r"autorizaci[oó]n de uso|edicto|anuncio)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_EXPEDIENTE_YEAR = re.compile(r"\b(\d{1,6})/(\d{4})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
URBANISMO_REMITENTE = re.compile(
    r"(?i)gerencia municipal de urbanismo|urbanismo,\s*infraestructuras",
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


def _fecha_from_expediente(text: str) -> str | None:
    m = RE_EXPEDIENTE_YEAR.search(text or "")
    if m:
        try:
            return datetime(int(m.group(2)), 1, 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(int(obj["year"]), int(obj["month"]), int(obj["day"])).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str, codigo: str = "") -> str:
    blob = f"{title} {codigo}".upper()
    if "EST-PGOU" in blob or "ESTUDIO DE DETALLE" in blob:
        return "estudio de detalle"
    if "MOD-PGOU" in blob or "MODIFICACI" in blob:
        return "modificación PGOU"
    if "EXC-URB" in blob:
        return "uso excepcional"
    if "PROV-URB" in blob:
        return "uso provisional"
    if "URB-PGOU" in blob or "URBANIZ" in blob:
        return "proyecto urbanización"
    if "TRAM" in blob or "ENAJEN" in blob:
        return "enajenación / tramitación"
    if "PLA-FOM" in blob or "PLAN DIRECTOR" in blob:
        return "plan director"
    if "EXPROP" in blob:
        return "expropiación"
    if "CONVENIO" in blob:
        return "convenio urbanístico"
    return "urbanismo"


class BurgosAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal Liferay (instrumentos + anuncios) + sede STA (tablón + catálogo trámites)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-burgos/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.aytoburgos.es" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
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

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _tablon_row_to_record(self, row: dict[str, Any]) -> tuple[str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or rem.get("code") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, remitente, fecha, url

    def _collect_catalog_licencias(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            keywords = item.get("keywordList") or []
            if not any(str(k.get("code") or "") == "LICENCIAS" for k in keywords):
                continue
            name = str(item.get("name") or "").strip()
            code = str(item.get("code") or item.get("dboid") or name)
            if not name:
                continue
            rows.append(
                {
                    "id": _stable_id("lic", code),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": name[:500],
                    "url": f"{CATALOGO_URL}#tramite={code}",
                    "source": "ayuntamiento",
                    "nota": "Trámite del catálogo sede; no concesión publicada",
                    "tramite_code": code,
                }
            )
        return rows

    def _collect_portal_licencias(self) -> list[dict[str, Any]]:
        """Trámites informativos Liferay cuando la sede STA no es accesible."""
        try:
            html = self._fetch(LICENCIAS_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(
            r'href="(https://www\.aytoburgos\.es/-/[^"]+)"[^>]*>([^<]+)',
            html,
            re.I,
        ):
            url = unescape(m.group(1).replace("&amp;", "&"))
            title = _strip_html(m.group(2))
            if not title or not RE_LICENCIA.search(title):
                continue
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo portal; sede STA no accesible desde CI",
                }
            )
        return rows

    def _collect_tablon_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._collect_tablon():
            title, rem, fecha, url = self._tablon_row_to_record(item)
            blob = f"{title} {rem}"
            if not RE_LICENCIA.search(blob):
                continue
            if re.search(r"(?i)auto-?taxi|convocatoria.*ayudas", blob):
                continue
            rows.append(
                {
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
            )
        return rows

    def _parse_instrumentos_table(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            cells = [_strip_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(cells) < 2 or not re.search(r"\d+/\d{4}", cells[0]):
                continue
            link_m = re.search(r'href="([^"]+)"', tr)
            codigo = cells[0]
            desc = cells[1]
            promotor = cells[2] if len(cells) > 2 else ""
            titulo = f"{codigo}: {desc}"[:500]
            url = unescape(link_m.group(1)) if link_m else INSTRUMENTOS_URL
            rows.append(
                {
                    "codigo": codigo,
                    "titulo": titulo,
                    "fecha": _fecha_from_expediente(codigo),
                    "tipo": _proyecto_tipo(desc, codigo),
                    "url": url,
                    "promotor": promotor,
                }
            )
        return rows

    def _anuncios_page_url(self, cur: int) -> str:
        params = {
            "p_p_id": ANUNCIOS_PUBLISHER,
            "p_p_lifecycle": "0",
            "p_p_state": "normal",
            "p_p_mode": "view",
            f"_{ANUNCIOS_PUBLISHER}_cur": str(cur),
            "p_r_p_resetCur": "false",
        }
        return f"{ANUNCIOS_URL}?{urllib.parse.urlencode(params)}"

    def _parse_anuncios_page(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in re.finditer(
            r'href="(https://www\.aytoburgos\.es/anuncios-urbanismo/-/asset_publisher[^"]+)"[^>]*>([^<]+)',
            html,
            re.S,
        ):
            url = unescape(m.group(1).replace("&amp;", "&"))
            title = _strip_html(m.group(2))
            if not title:
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _fecha_from_expediente(title),
                    "tipo": _proyecto_tipo(title),
                    "url": url,
                }
            )
        return rows

    def _collect_anuncios(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        max_pages = int(self.config.get("anuncios_max_pages", 5))
        for cur in range(max_pages):
            try:
                html = self._fetch(self._anuncios_page_url(cur))
            except urllib.error.URLError:
                break
            page_rows = self._parse_anuncios_page(html)
            if not page_rows:
                break
            for row in page_rows:
                key = row["url"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
        return rows

    def _collect_instrumentos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(INSTRUMENTOS_URL)
        except urllib.error.URLError:
            return []
        return self._parse_instrumentos_table(html)

    def _collect_tablon_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._collect_tablon():
            title, rem, fecha, url = self._tablon_row_to_record(item)
            blob = f"{title} {rem}"
            if not (URBANISMO_REMITENTE.search(rem) or RE_PROYECTO.search(blob)):
                continue
            if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha or _fecha_from_expediente(title),
                    "tipo": _proyecto_tipo(title),
                    "url": url,
                    "origen": "sede_tablon",
                }
            )
        return rows

    def _to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any]:
        url = rec["url"]
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": rec["titulo"],
            "fecha": rec.get("fecha") or None,
            "tipo": rec.get("tipo") or "urbanismo",
            "url": url,
            "source": "ayuntamiento",
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        catalog = self._collect_catalog_licencias()
        tablon = self._collect_tablon_licencias()
        portal = self._collect_portal_licencias() if not catalog and not tablon else []
        for rec in catalog + tablon + portal:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "catalog_tramites": len(catalog),
            "tablon_licencias": len(tablon),
            "portal_tramites": len(portal),
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

        def add(rec: dict[str, Any]) -> None:
            proy = self._to_proyecto(rec)
            if proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)

        for rec in self._collect_instrumentos():
            add(rec)
        for rec in self._collect_anuncios():
            add(rec)
        for rec in self._collect_tablon_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "instrumentos": len(self._collect_instrumentos()),
            "anuncios": len(self._collect_anuncios()),
            "tablon": len(self._collect_tablon_proyectos()),
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
