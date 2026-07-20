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

PORTAL_BASE = "https://www.aytosalamanca.es"
SEDE_BASE = "https://www.aytosalamanca.gob.es"
MUNICIPIO = "Salamanca"
ID_PREFIX = "salamanca"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=TABLON_EDICTOS"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
PLANES_URL = f"{PORTAL_BASE}/urbanismo-vivienda-y-obras/planes-tramitacion"
ANUNCIOS_URL = f"{PORTAL_BASE}/anuncios?category=39289&delta=50"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|primera utilizaci[oó]n|"
    r"demolici[oó]n|parcelaci[oó]n|calicatas|terrazas?)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pogu|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|sector|expropi|junta de compensaci[oó]n|actuaci[oó]n|"
    r"normalizaci[oó]n de fincas|evaluaci[oó]n ambiental)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ES = re.compile(
    r"(?i)(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo),\s*"
    r"(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+de\s+(\d{4})"
)
MESES_ES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


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


def _parse_fecha_es(text: str) -> str | None:
    m = RE_FECHA_ES.search(text or "")
    if not m:
        return None
    mes = MESES_ES.get(m.group(2).lower())
    if not mes:
        return None
    try:
        return datetime(int(m.group(3)), mes, int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_es(text)


def _abs_url(url: str) -> str:
    if not url:
        return PORTAL_BASE
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        base = SEDE_BASE if url.startswith("/sta/") else PORTAL_BASE
        return f"{base}{url}"
    return urllib.parse.urljoin(f"{SEDE_BASE}/sta/CarpetaPublic/", url)


def _proyecto_tipo(titulo: str) -> str:
    blob = titulo.lower()
    if "convenio" in blob:
        return "convenio urbanístico"
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "plan parcial" in blob:
        return "plan parcial"
    if "plan especial" in blob:
        return "plan especial"
    if "expropi" in blob:
        return "expropiación"
    if "informaci" in blob and "pública" in blob:
        return "información pública"
    if "modificaci" in blob and "pgou" in blob:
        return "modificación PGOU"
    if "junta de compensaci" in blob:
        return "junta de compensación"
    if "evaluaci" in blob and "ambiental" in blob:
        return "evaluación ambiental"
    return "planeamiento"


class SalamancaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay portal urbanismo + sede STA (tablón edictos, catálogo trámites)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or PORTAL_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.portal_base = str(self.config.get("portal_base") or PORTAL_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.planes_url = str(self.config.get("planes_url") or PLANES_URL)
        self.anuncios_url = str(self.config.get("anuncios_url") or ANUNCIOS_URL)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-salamanca/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    @staticmethod
    def _extract_sta_rows(html: str) -> list[dict[str, Any]]:
        m = re.search(r'"rows":(\[.*?\]),"hasMoreRows"', html, re.S)
        if not m:
            return []
        try:
            rows = json.loads(m.group(1))
            return rows if isinstance(rows, list) else []
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _extract_catserv(html: str) -> list[dict[str, Any]]:
        start = html.find("var dataset_CATSERV = [")
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        try:
            data = json.loads(html[start + len("var dataset_CATSERV = ") : end + 1])
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for row in self._extract_sta_rows(html):
            data = row.get("data") or []
            if len(data) < 3:
                continue
            fecha_raw = str(data[0].get("value") or "")
            titulo = unescape(str(data[1].get("value") or "")).strip()
            categoria = unescape(str(data[2].get("value") or "")).strip()
            link = str(data[1].get("linkHref") or "")
            if not titulo:
                continue
            fecha = None
            ym = re.match(r"(\d{4})/(\d{2})/(\d{2})", fecha_raw)
            if ym:
                fecha = f"{ym.group(1)}-{ym.group(2)}-{ym.group(3)}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "categoria": categoria,
                    "url": _abs_url(link),
                    "origen": "tablon_edictos",
                }
            )
        return rows

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_catserv(html):
            keywords = item.get("keywordList") or []
            if not any(str(k.get("code") or "") == "STA_AMB_URBANISMO" for k in keywords):
                continue
            name = str(item.get("name") or "").strip()
            dboid = str(item.get("dboid") or item.get("code") or name)
            if not name:
                continue
            url = (
                f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
                f"APP_CODE=STA&PAGE_CODE=CATALOGO&DETALLE={dboid}"
            )
            rows.append(
                {
                    "titulo": name[:500],
                    "url": url,
                    "tramite_code": str(item.get("code") or ""),
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _collect_planes_tramitacion(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.planes_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in re.finditer(
            r'<h2 class="h5">([^<]+)</h2>(.*?)(?=<h2 class="h5">|$)',
            html,
            re.S,
        ):
            titulo = unescape(m.group(1).strip())
            block = m.group(2)
            link_m = re.search(r'href="(/w/[^"]+)"', block)
            if not titulo:
                continue
            url = _abs_url(link_m.group(1)) if link_m else self.planes_url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "origen": "planes_tramitacion",
                }
            )
        return rows

    def _collect_anuncios(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.anuncios_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        titles = re.findall(
            r'class="slm-anuncio-title[^"]*"[^>]*>(.*?)</p>',
            html,
            re.S,
        )
        links = re.findall(
            r'href="(/w/[^"]+)"[^>]*>\s*<span class="slm-anuncio-link',
            html,
        )
        fechas = re.findall(r'class="pb-2 text-muted d-block">([^<]+)', html)
        for titulo_raw, link, fecha_raw in zip(titles, links, fechas):
            titulo = _strip_html(titulo_raw)
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(fecha_raw) or _fecha_from_blob(titulo),
                    "url": _abs_url(link),
                    "origen": "anuncios_urbanismo",
                }
            )
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('categoria', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("categoria") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": row.get("origen"),
            "tramite_code": row.get("tramite_code"),
        }

    def _anuncio_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        if RE_PROYECTO.search(row["titulo"]) and not re.search(
            r"(?i)licencia de uso|licencia urban",
            row["titulo"],
        ):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "tablon_edictos" and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "catalogo_tramites":
            if not RE_PROYECTO.search(blob):
                return None
            if RE_LICENCIA.search(blob) and not re.search(
                r"(?i)planeam|actuaci[oó]n urban|convenio|proyecto de urbanizaci",
                blob,
            ):
                return None
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
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

    def _merge_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_licencia(item))
        for item in self._collect_catalog_tramites():
            add(self._tramite_to_licencia(item))
        for item in self._collect_anuncios():
            add(self._anuncio_to_licencia(item))
        return rows

    def _merge_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_planes_tramitacion():
            add(self._to_proyecto(item))
        for item in self._collect_anuncios():
            add(self._to_proyecto(item))
        for item in self._collect_tablon():
            add(self._to_proyecto(item))
        for item in self._collect_catalog_tramites():
            add(self._to_proyecto(item))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._merge_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_edictos"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "anuncios": sum(1 for r in rows if r.get("origen") == "anuncios_urbanismo"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._merge_licencias():
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
        rows = self._merge_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "planes": sum(1 for r in rows if r.get("origen") == "planes_tramitacion"),
            "anuncios": sum(1 for r in rows if r.get("origen") == "anuncios_urbanismo"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_edictos"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
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
