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

BASE = "https://www.aytovillaviciosadeodon.es"
MUNICIPIO = "Villaviciosa de Odón"
ID_PREFIX = "villaviciosa-de-odon"

ANUNCIOS_URL = f"{BASE}/actualidad-municipal/anuncios-oficiales"
PGOU_URL = f"{BASE}/es_ES/sede-electronica/plan-general-de-ordenacion-urbana"
PLANEAMIENTO_URL = (
    f"{BASE}/tu-ayuntamiento/servicios-y-areas/"
    "urbanismo-y-planificacion-del-territorio/servicios/planeamiento-en-tramitacion"
)
ENTIDADES_URL = f"{BASE}/actualidad-municipal/entidades-urbanisticas"

DEFAULT_URBANISMO_PAGES: list[str] = [
    PLANEAMIENTO_URL,
    f"{BASE}/tu-ayuntamiento/servicios-y-areas/urbanismo-y-planificacion-del-territorio/plan-general-de-ordenacion-urbana",
    PGOU_URL,
    ENTIDADES_URL,
    f"{BASE}/tu-ayuntamiento/servicios-y-areas/urbanismo-y-planificacion-del-territorio/servicios/plan-especial-nuevo-cementerio-municipal",
    f"{BASE}/tu-ayuntamiento/servicios-y-areas/urbanismo-y-planificacion-del-territorio/servicios/planeamiento-en-tramitacion/apr-9",
    f"{BASE}/tu-ayuntamiento/servicios-y-areas/urbanismo-y-planificacion-del-territorio/servicios/planeamiento-en-tramitacion/plane-especial-del-cementerio",
    f"{BASE}/tu-ayuntamiento/servicios-y-areas/urbanismo-y-planificacion-del-territorio/servicios/planeamiento-en-tramitacion/aprobacion-inicial-del-estudio-de-detalle-de-la-parcela-1-1-del-uzi-3-el-monte",
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{BASE}/tu-ayuntamiento/servicios-y-areas/urbanismo-y-planificacion-del-territorio/servicios/licencias-urbanisticas",
    f"{BASE}/tu-ayuntamiento/servicios-y-areas/urbanismo-y-planificacion-del-territorio/servicios/licencias-urbanisticas/licencias-de-obras",
    f"{BASE}/tu-ayuntamiento/servicios-y-areas/urbanismo-y-planificacion-del-territorio/servicios/licencias-urbanisticas/licencias-de-primera-ocupacion",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|t[ií]tulos habilitantes)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|edicto|reparcel|estudio de detalle|"
    r"aprobaci[oó]n (?:inicial|definitiva)|modificaci[oó]n|entidad urban|"
    r"cementerio|vereda|ordenanza.*(?:urban|tasa)|monte de la villa|uzi|parcela)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ES = re.compile(
    r"(\d{1,2})\s+de\s+"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
    r"\s+de\s+(\d{4})",
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
MESES = {
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
    try:
        return datetime(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1))).strftime(
            "%Y-%m-%d"
        )
    except (ValueError, KeyError):
        return None


def _parse_fecha(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_es(text)


def _iso_from_year(text: str) -> str | None:
    years = [int(m.group(1)) for m in RE_YEAR.finditer(text or "") if 1980 <= int(m.group(1)) <= 2030]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _title_from_pdf_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).name
    if "/" in path and not name.endswith(".pdf"):
        parts = [p for p in path.split("/") if p and not re.fullmatch(r"[0-9a-f-]{36}", p)]
        if parts:
            name = parts[-1]
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    return name.replace("+", " ").strip()[:500]


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (r"<title>([^<]+)", r'<div class="title">\s*([^<]+?)\s*</div>'):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _proyecto_tipo(title: str) -> str:
    t = title.lower()
    if "estudio de detalle" in t:
        return "estudio de detalle"
    if "plan parcial" in t:
        return "plan parcial"
    if "plan especial" in t:
        return "plan especial"
    if "informaci" in t and "p" in t and "blica" in t:
        return "información pública"
    if "pgou" in t or "plan general" in t:
        return "planeamiento"
    if "entidad urban" in t:
        return "entidad urbanística"
    if "ordenanza" in t:
        return "ordenanza urbanística"
    if "convenio" in t:
        return "convenio"
    return "urbanismo"


class VillaviciosaDeOdonAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay: Anuncios Oficiales (acordeón) + páginas urbanismo/PGOU."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.browser_cookie = str(self.config.get("browser_cookie", "browser_verified=1"))
        self.urbanismo_pages = [str(u) for u in (self.config.get("urbanismo_pages") or DEFAULT_URBANISMO_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-villaviciosa-de-odon/1.0"),
                "Cookie": self.browser_cookie,
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(BASE, href)

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

    def _parse_accordion_items(self, html: str, page_url: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for m in re.finditer(
            r'<div class="title-wrapper">\s*<div class="title">\s*([^<]+?)\s*</div>([\s\S]*?)</div>\s*</div>\s*</div>\s*</div>\s*</div>',
            html,
            re.I,
        ):
            title = unescape(re.sub(r"\s+", " ", m.group(1)).strip())
            block = m.group(0)
            pdfs = [self._abs_url(u) for u in re.findall(r'href="(/documents/[^"]+)"', block)]
            fecha = _parse_fecha(block) or _iso_from_year(title)
            items.append({"titulo": title[:500], "fecha": fecha, "url": page_url, "pdfs": pdfs})
        return items

    def _discover_urbanismo_links(self, html: str) -> list[str]:
        links: list[str] = []
        for href in re.findall(
            r'href="(/tu-ayuntamiento/servicios-y-areas/urbanismo-y-planificacion-del-territorio/[^"#?]+)"',
            html,
            re.I,
        ):
            url = self._abs_url(href).rstrip("/")
            if url not in links:
                links.append(url)
        return links

    def _collect_anuncios(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(ANUNCIOS_URL)
        except urllib.error.URLError:
            return []
        return self._parse_accordion_items(html, ANUNCIOS_URL)

    def _collect_urbanismo_pages(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue = list(self.urbanismo_pages)
        items: list[dict[str, Any]] = []

        while queue:
            url = queue.pop(0).rstrip("/")
            if url in visited:
                continue
            visited.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue

            items.extend(self._parse_accordion_items(html, url))

            page_title = _page_title(html, "")
            if page_title and RE_PROYECTO.search(page_title) and not any(
                i["titulo"] == page_title for i in items
            ):
                pdfs = [self._abs_url(u) for u in re.findall(r'href="(/documents/[^"]+\.pdf[^"]*)"', html, re.I)]
                if pdfs or "planeamiento" in url.lower() or "plan-" in url.lower():
                    items.append(
                        {
                            "titulo": page_title,
                            "fecha": _iso_from_year(page_title),
                            "url": url,
                            "pdfs": pdfs,
                        }
                    )

            for link in self._discover_urbanismo_links(html):
                if link.rstrip("/") not in visited and link not in queue:
                    queue.append(link)

        return items

    def _collect_pgou_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in {PGOU_URL, f"{BASE}/tu-ayuntamiento/servicios-y-areas/urbanismo-y-planificacion-del-territorio/plan-general-de-ordenacion-urbana"}:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            for href in re.findall(r'href="(/documents/[^"]+\.pdf[^"]*)"', html, re.I):
                pdf = self._abs_url(href)
                titulo = _title_from_pdf_url(pdf)
                rows.append(
                    {
                        "titulo": f"PGOU: {titulo}",
                        "fecha": _iso_from_year(titulo),
                        "url": url,
                        "pdfs": [pdf],
                    }
                )
        return rows

    def _title_to_licencia(self, title: str, url: str, fecha: str | None, pdf_url: str | None = None) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", pdf_url or url),
            "fecha_concesion": fecha,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        return rec

    def _title_to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str | None,
        pdfs: list[str] | None = None,
    ) -> dict[str, Any] | None:
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        pdf_url = pdfs[0] if pdfs else None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", pdf_url or url + title),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(title),
            "url": url,
            "source": "ayuntamiento",
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
            if len(pdfs or []) > 1:
                rec["pdf_urls"] = (pdfs or [])[:30]
        return rec

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self.licencia_pages:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = _page_title(html, url.rsplit("/", 1)[-1])
            if RE_LICENCIA.search(title):
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
                        "nota": "Página informativa de trámites; no concesión publicada en tablón",
                    }
                )
            for m in re.finditer(r"<strong[^>]*>([^<]*[Ll]icencia[^<]{0,200})</strong>", html):
                tramite = unescape(m.group(1).strip())
                if len(tramite) < 12:
                    continue
                rows.append(
                    {
                        "id": _stable_id("lic", url + tramite),
                        "fecha_concesion": None,
                        "tipo": tramite[:120],
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": tramite[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "nota": "Tipo de trámite publicado en web municipal",
                    }
                )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_anuncios():
            add(self._title_to_licencia(item["titulo"], item["url"], item.get("fecha"), item["pdfs"][0] if item["pdfs"] else None))

        for rec in self._collect_licencias_tramites():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "anuncios_y_tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
        after_rows = self._load_jsonl(out_jsonl)
        added = len(after_rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(after_rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(after_rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_anuncios():
            add(self._title_to_proyecto(item["titulo"], item["url"], item.get("fecha"), item["pdfs"]))

        for item in self._collect_urbanismo_pages():
            add(self._title_to_proyecto(item["titulo"], item["url"], item.get("fecha"), item["pdfs"]))

        for item in self._collect_pgou_pdfs():
            add(self._title_to_proyecto(item["titulo"], item["url"], item.get("fecha"), item["pdfs"]))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "anuncios": len(self._collect_anuncios()),
            "urbanismo_pages": len(self.urbanismo_pages),
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
