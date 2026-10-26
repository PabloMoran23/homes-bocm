from __future__ import annotations

import hashlib
import http.cookiejar
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
from municipio.geometry import record_geometry

WEB_BASE = "https://www.santaeulariadesriu.com"
SEDE_BASE = "https://santaeulariadesriu.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
ORDENACION_URL = (
    f"{WEB_BASE}/ca/departaments/territori-urbanisme-i-activitats/"
    "ordenacio-del-territori-i-urbanisme"
)
VISOR_URL = "https://www.santaeularia.com:444/geoxarc/"
EXPEDIENTES_URL = f"{SEDE_BASE}/expedientes"
MUNICIPIO = "Santa Eulària des Riu"
ID_PREFIX = "santa-eularia-des-riu"

PLANEJAMENT_ARTICLES: list[dict[str, str]] = [
    {
        "url": f"{ORDENACION_URL}?view=article&id=4127:normes-subsidiaries&catid=145",
        "titulo": "Normes subsidiàries",
        "tipo": "normas subsidiarias",
        "kind": "proyecto",
    },
    {
        "url": f"{ORDENACION_URL}?view=article&id=4979:modificacions-de-les-normes-subsidiaries&catid=143",
        "titulo": "Modificacions de les normes subsidiàries",
        "tipo": "modificación planeamiento",
        "kind": "proyecto",
    },
    {
        "url": f"{ORDENACION_URL}?view=article&id=4146:plans-especials&catid=143",
        "titulo": "Plans especials",
        "tipo": "plan especial",
        "kind": "proyecto",
    },
    {
        "url": f"{ORDENACION_URL}?view=article&id=4143:estudi-de-detall&catid=143",
        "titulo": "Estudi de detall",
        "tipo": "estudio de detalle",
        "kind": "proyecto",
    },
    {
        "url": f"{ORDENACION_URL}?view=article&id=4145:estudi-acustic-i-mapa-de-sorolls-del-municipi&catid=143",
        "titulo": "Estudi acústic i mapa de sorolls del municipi",
        "tipo": "estudio acústico",
        "kind": "proyecto",
    },
    {
        "url": f"{ORDENACION_URL}?view=article&id=4144:cataleg-de-patrimoni-historic&catid=143",
        "titulo": "Catàleg de patrimoni històric",
        "tipo": "catálogo patrimonio",
        "kind": "proyecto",
    },
]

TRAMITES_LICENCIA: list[dict[str, str]] = [
    {
        "url": f"{ORDENACION_URL}?view=article&id=4135:comunicacio-previa&catid=147",
        "tipo": "comunicación previa",
        "titulo": "Comunicació prèvia execució obres",
    },
    {
        "url": (
            f"{ORDENACION_URL}?view=article&id=%204980:sol-licitud-de-llicencia-d-obra-major-amb-projecte-tecnic"
            "&catid=%20143"
        ),
        "tipo": "licencia de obra mayor",
        "titulo": "Sol·licitud de llicència d'obra major (amb projecte tècnic)",
    },
    {
        "url": f"{ORDENACION_URL}?view=article&id=4137:sol-licitud-de-llicencia-d-obra-sense-projecte-tecnic&catid=147",
        "tipo": "licencia de obra",
        "titulo": "Sol·licitud de llicència d'obra sense projecte tècnic",
    },
    {
        "url": f"{ORDENACION_URL}?view=article&id=4140:llicencies-de-segregacio&catid=143",
        "tipo": "licencia segregación",
        "titulo": "Llicències de segregació / agrupació",
    },
    {
        "url": (
            f"{WEB_BASE}/ca/departaments/territori-urbanisme-i-activitats/"
            "ordenacio-del-territori-i-urbanisme/declaracions-responsables-habitatge-decret-llei-6-2023"
        ),
        "tipo": "declaración responsable",
        "titulo": "Declaracions responsables habitatge (Decret llei 6/2023)",
    },
]

PDF_PROYECTOS: list[dict[str, str]] = [
    {
        "url": f"{WEB_BASE}/images/20250508 BOIB n58 CAT.pdf",
        "titulo": "BOIB n.58 — mesures legalització extraordinària",
        "tipo": "información pública BOIB",
    },
    {
        "url": f"{WEB_BASE}/images/00_recursos/urbanismo/TEXTO CONSOLIDADO NORMAS DILIG_20_08_25.pdf",
        "titulo": "Text consolidat modificacions Normes Subsidiàries (diligenciat)",
        "tipo": "normas subsidiarias",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licen|licèn|llic[eè]ncia|obra|comunicaci|declaraci|autoritz|autoriz|"
    r"certificat|reforma|ampliaci|demolici|edificaci|segregaci|agrupaci)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|planej|plan (?:parcial|especial|general)|pgou|pla especial|"
    r"informaci[oó] p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"sector|normes subsidi|estudi de detall|boib|anunci|actuaci[oó]n urban)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvencion|subvenci[oó]|ajudes|ocupaci[oó] p[uú]blica|ple\b|"
    r"convocat[oò]ria de.*ple|policia local|proces selectiv)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://santaeulariadesriu\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EL_ITEM = re.compile(
    r'<a class="el-item[^"]*" href="([^"]+)"[^>]*>.*?<h3 class="el-title[^"]*">\s*([^<]+)',
    re.I | re.S,
)
RE_ARTICLE_LINK = re.compile(
    r'href="((?:https://www\.santaeulariadesriu\.com)?/ca/[^"]*view=article[^"]+)"',
    re.I,
)
RE_PDF_LINK = re.compile(
    r'href="((?:https://www\.santaeulariadesriu\.com)?/images/[^"]+\.pdf)"',
    re.I,
)


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


def _fecha_from_url(url: str) -> str | None:
    m = re.search(r"(\d{4})(\d{2})(\d{2})", Path(url).name)
    if m:
        try:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(url) if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "pla especial" in n or "plan especial" in n:
        return "plan especial"
    if "normes subsidi" in n or "normas subsidi" in n:
        return "normas subsidiarias"
    if "estudi de detall" in n or "estudio de detalle" in n:
        return "estudio de detalle"
    if "boib" in n:
        return "información pública BOIB"
    if "acust" in n:
        return "estudio acústico"
    if "patrimoni" in n or "patrimonio" in n:
        return "catálogo patrimonio"
    if "visor" in n or "geoxarc" in n:
        return "visor GIS"
    return "planeamiento"


def _licencia_tipo(text: str) -> str:
    n = (text or "").lower()
    if "comunicaci" in n:
        return "comunicación previa"
    if "declaraci" in n:
        return "declaración responsable"
    if "segregaci" in n or "agrupaci" in n:
        return "licencia segregación"
    if "major" in n:
        return "licencia de obra mayor"
    if "certificat" in n:
        return "certificación urbanística"
    return "licencia de obra"


class SantaEulariaDesRiuAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla/YOOtheme web + sede espublico gestiona + visor GeoXarc (WMS interno no público)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.ordenacion_url = str(self.config.get("ordenacion_url") or ORDENACION_URL)
        self.visor_url = str(self.config.get("visor_url") or VISOR_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._ua = self.config.get("user_agent", "poc-bocm-santa-eularia-des-riu/1.0")

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua})
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href.replace("&amp;", "&"))

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            if not documento or documento in ("Document", "Documento"):
                continue

            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if "urban" in proc or "obra" in proc:
            return True
        return bool(RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob))

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", f"board:{key}"),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", f"board:{key}"),
            "fecha_concesion": row.get("fecha"),
            "tipo": _licencia_tipo(blob),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _scrape_ordenacion_page(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        proyectos: list[dict[str, Any]] = []
        licencias: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.ordenacion_url)
        except urllib.error.URLError:
            return proyectos, licencias

        seen_urls: set[str] = set()

        def add_item(url: str, titulo: str, *, kind: str, tipo: str) -> None:
            url = self._abs_web(url)
            if url in seen_urls:
                return
            seen_urls.add(url)
            blob = f"{titulo} {url}"
            if kind == "licencia" or RE_LICENCIA.search(blob):
                licencias.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": _fecha_from_url(url),
                        "tipo": _licencia_tipo(blob),
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": titulo[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "web_tramite",
                    }
                )
            if kind == "proyecto" or RE_PROYECTO.search(blob) or ".pdf" in url.lower():
                proyectos.append(
                    {
                        "id": _stable_id("proy", url),
                        "municipio": MUNICIPIO,
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_url(url),
                        "tipo": tipo or _proyecto_tipo(blob),
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "web_cms",
                    }
                )

        for m in RE_EL_ITEM.finditer(html):
            href, titulo = m.group(1), _strip_html(m.group(2))
            blob = titulo.lower()
            kind = "licencia" if RE_LICENCIA.search(blob) else "proyecto"
            add_item(href, titulo, kind=kind, tipo=_proyecto_tipo(blob))

        for m in RE_ARTICLE_LINK.finditer(html):
            href = self._abs_web(m.group(1))
            slug_part = href.split("id=")[-1].split("&")[0] if "id=" in href else href
            titulo = unescape(slug_part.replace(":", " — ").replace("-", " "))
            kind = "licencia" if RE_LICENCIA.search(titulo) else "proyecto"
            add_item(href, titulo, kind=kind, tipo=_proyecto_tipo(titulo))

        for m in RE_PDF_LINK.finditer(html):
            href = self._abs_web(m.group(1))
            name = Path(href).name
            add_item(href, name, kind="proyecto", tipo=_proyecto_tipo(name))

        return proyectos, licencias

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tauler d'anuncis — sede electrònica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios públicos espublico (urbanismo cuando se publiquen)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", EXPEDIENTES_URL),
                "fecha_concesion": None,
                "tipo": "consulta expedientes",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta d'expedients — sede electrònica",
                "url": EXPEDIENTES_URL,
                "source": "ayuntamiento",
                "origen": "sede_expedientes",
            },
        ]
        for item in TRAMITES_LICENCIA:
            rows.append(
                {
                    "id": _stable_id("lic", item["url"]),
                    "fecha_concesion": None,
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "origen": "web_tramite",
                }
            )
        return rows

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("proy", self.ordenacion_url),
                "municipio": MUNICIPIO,
                "titulo": "Ordenació del territori i urbanisme — documentació",
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.ordenacion_url,
                "source": "ayuntamiento",
                "origen": "web_cms",
            },
            {
                "id": _stable_id("proy", self.visor_url),
                "municipio": MUNICIPIO,
                "titulo": "Visor cartogràfic GeoXarc",
                "fecha": None,
                "tipo": "visor GIS",
                "url": self.visor_url,
                "source": "ayuntamiento",
                "origen": "visor",
                "nota": "WMS municipal en :444/map no expone GetCapabilities público",
            },
        ]
        for item in PLANEJAMENT_ARTICLES:
            rows.append(
                {
                    "id": _stable_id("proy", item["url"]),
                    "municipio": MUNICIPIO,
                    "titulo": item["titulo"],
                    "fecha": None,
                    "tipo": item["tipo"],
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "origen": "web_cms",
                }
            )
        for item in PDF_PROYECTOS:
            rows.append(
                {
                    "id": _stable_id("proy", item["url"]),
                    "municipio": MUNICIPIO,
                    "titulo": item["titulo"],
                    "fecha": _fecha_from_url(item["url"]),
                    "tipo": item["tipo"],
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "origen": "web_pdf",
                }
            )
        return rows

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

    def _merge_rows(self, seen: set[str], rows: list[dict[str, Any]], new: dict[str, Any] | None) -> None:
        if new and new["id"] not in seen:
            seen.add(new["id"])
            rows.append(new)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        for rec in self._collect_licencia_info_pages():
            self._merge_rows(seen, rows, rec)

        scraped_p, scraped_l = self._scrape_ordenacion_page()
        for rec in scraped_l:
            self._merge_rows(seen, rows, rec)

        for item in self._collect_board():
            self._merge_rows(seen, rows, self._board_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "web_tramite", "sede_expedientes")),
            "with_geometry": with_geom,
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

        for rec in self._collect_proyecto_info_pages():
            self._merge_rows(seen, rows, rec)

        scraped_p, _ = self._scrape_ordenacion_page()
        for rec in scraped_p:
            self._merge_rows(seen, rows, rec)

        for item in self._collect_board():
            self._merge_rows(seen, rows, self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web")),
            "with_geometry": with_geom,
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
