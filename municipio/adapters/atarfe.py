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

SEDE_BASE = "https://atarfe.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
WEB_BASE = "https://www.atarfe.es"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
ORDENANZAS_TRANSP = (
    f"{SEDE_BASE}/transparency/43805ba8-ae16-47ec-b379-184d3b166287/"
)
MUNICIPIO = "Atarfe"
ID_PREFIX = "atarfe"

DEFAULT_WEB_SEEDS: list[str] = [
    f"{WEB_BASE}/urbanismo",
    f"{WEB_BASE}/anuncios-plenos-municipales",
    f"{WEB_BASE}/modificacion-de-las-ordenanzas-fiscales-reguladoras-construcciones-instalaciones-obras-icio-ibi",
    f"{WEB_BASE}/recurso-casacion-tribunal-supremo-urbanizacion-medina-elvira-atarfe",
    f"{WEB_BASE}/adjudicada-la-obra-de-urbanizacion-de-la-calle-capote",
    ORDENANZAS_TRANSP,
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|\bicio\b|construcciones.*instalaciones.*obras)",
)
RE_PROYECTO = re.compile(
    r"(?i)(planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente urban|junta de compens|"
    r"medina elvira|recurso.*casaci[oó]n|sector si-|bop.*(?:aprob|constituc)|"
    r"ordenanza.*(?:icio|urban|fiscal)|modificaci[oó]n.*ordenanza|"
    r"urbanizaci[oó]n de la calle|estatutos y bases de actuaci[oó]n|"
    r"licencia urban|anuncio.*aprobaci[oó]n.*junta)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"material escolar|juez de paz|formaci[oó]n online|romer[ií]a|fiestas|"
    r"comunidad de regantes|oferta empleo p[uú]blico|objetivos calidad ac[uú]stica|"
    r"calendario laboral|relaci[oó]n de puestos|subasta del servicio de barra|"
    r"cuota de administraci[oó]n|canon confederaci[oó]n)",
)
RE_WEB_NON_URBAN = re.compile(
    r"(?i)(fiestas de las urbanizaciones|gymkhana urbana|planazo|plan emergencia|"
    r"hora del planeta|autobus urbano|feria steam|villa europea del deporte|"
    r"plan siga|recogida de basura|corte por reparaci|apagon|coronavirus|"
    r"concurso de cruces|festival.*rock|desescalada|accesibilidad|violencia de genero|"
    r"ciclismo|triatlon|telefonos|orienta|recaudacion|barbacoas|terraza|"
    r"ordenanza de terrazas|pasacalles|olivos lucios|basura|limpieza|"
    r"urbanizacion llanos de silva|urbanizacion buenavista|urbanizacion los cortijos|"
    r"urbanizacion vista alegre|corredor verde|fiestas de verano|ibi urbano|"
    r"conoce el proyecto|proyectos innovadores|concurso.*cruz|condiciones para|"
    r"contactar con|aver[ií]a en el servicio|emprendimiento rural|escuela de m[uú]sica|"
    r"presentaci[oó]n de proyectos para el ii concurso|restituci[oó]n del servicio de autobuses)",
)
RE_BOARD_ROW = re.compile(r'<tr[^>]*>\s*<td class="class_name".*?</tr>', re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://atarfe\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WEB_LINK = re.compile(r'href="(/[a-z0-9\-]+(?:/[a-z0-9\-]+)?)"', re.I)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.atarfe\.es)?/pdf/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_PAGE_TITLE = re.compile(r"<title>([^<|]+)", re.I)
RE_POST_TITLE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.I | re.S)
RE_POST_META = re.compile(r'class="post-meta"[^>]*>(.*?)</div>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "junta de compens" in b:
        return "junta de compensación"
    if "medina elvira" in b:
        return "expediente urbanístico"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "ordenanza" in b and ("icio" in b or "ibi" in b):
        return "ordenanza fiscal urbanística"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "urbanizaci" in b and "calle" in b:
        return "obra de urbanización"
    if "licencia" in b:
        return "licencia publicada"
    if "planeamiento" in b or "situa" in b:
        return "planeamiento"
    return "urbanismo"


class AtarfeAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal PHP Porto (www.atarfe.es) + sede espublico gestiona (tablón)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_seeds = [str(u) for u in (self.config.get("web_seeds") or DEFAULT_WEB_SEEDS)]
        self.ordenanzas_url = str(self.config.get("ordenanzas_url") or ORDENANZAS_TRANSP)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, insecure: bool | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-atarfe/1.0")},
        )
        use_insecure = self.config.get("insecure_ssl", True) if insecure is None else insecure
        if use_insecure and "sedelectronica.es" in url:
            with self._opener.open(req, timeout=90) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

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
                cls = cm.group(1)
                cells[cls] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento",):
                continue

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

    def _discover_web_article_urls(self) -> set[str]:
        seen: set[str] = set()
        for seed in self.web_seeds:
            seen.add(seed if seed.startswith("http") else self._abs_web(seed))

        listing_pages = [
            f"{self.web_base}/urbanismo",
            f"{self.web_base}/anuncios-plenos-municipales",
        ]
        for listing_url in listing_pages:
            try:
                html = self._fetch(listing_url)
            except urllib.error.URLError:
                continue
            for m in RE_WEB_LINK.finditer(html):
                path = m.group(1).split("#")[0].split("?")[0]
                slug = path.strip("/")
                if not slug or "/" in slug:
                    continue
                if slug in ("urbanismo", "noticias", "anuncios-plenos-municipales"):
                    continue
                if RE_WEB_NON_URBAN.search(slug.replace("-", " ")):
                    continue
                if not RE_PROYECTO.search(slug.replace("-", " ")):
                    continue
                seen.add(self._abs_web(path))
        return seen

    def _parse_web_article(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None

        title_m = RE_POST_TITLE.search(html)
        if title_m:
            title = _strip_html(title_m.group(1))
        else:
            page_title_m = RE_PAGE_TITLE.search(html)
            title = _strip_html(page_title_m.group(1)) if page_title_m else ""
            title = re.sub(r"\s*\|\s*Ayuntamiento de Atarfe\s*$", "", title).strip()
            if title.lower() in ("ayuntamiento de atarfe", "portal institucional", ""):
                title = url.rsplit("/", 1)[-1].replace("-", " ")

        meta_m = RE_POST_META.search(html)
        meta_text = _strip_html(meta_m.group(1)) if meta_m else html[:4000]
        fecha = _parse_fecha_dmy(meta_text) or _fecha_from_blob(f"{title} {meta_text}")

        blob = f"{title} {meta_text}"
        if RE_WEB_NON_URBAN.search(blob) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(blob):
            return None

        pdfs = [self._abs_web(h) if not h.startswith("http") else h for h in RE_PDF_HREF.findall(html)]
        pdfs = [p for p in pdfs if "proteccion-datos" not in p.lower()]

        return {
            "titulo": title[:500],
            "fecha": fecha,
            "url": url,
            "blob": blob[:2000],
            "pdfs": pdfs[:5],
            "origen": "web_articulo",
        }

    def _collect_web_articles(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for url in sorted(self._discover_web_article_urls()):
            if "sedelectronica.es" in url:
                continue
            rec = self._parse_web_article(url)
            if not rec:
                continue
            key = rec["titulo"].lower()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            rows.append(rec)
            for pdf_url in rec.get("pdfs") or []:
                rows.append(
                    {
                        "titulo": f"{rec['titulo']} — PDF",
                        "fecha": rec.get("fecha"),
                        "url": pdf_url,
                        "blob": f"{rec['titulo']} {pdf_url}",
                        "origen": "web_pdf",
                    }
                )
        return rows

    def _collect_situa_metadata(self) -> dict[str, Any]:
        return {
            "titulo": "Consulta planeamiento urbanístico — SITUA (Junta de Andalucía)",
            "fecha": None,
            "url": SITUA_SEARCH,
            "blob": "SITUA planeamiento Atarfe Granada INE 18010",
            "tipo": "planeamiento",
            "origen": "situa",
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias urbanísticas",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y edictos publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/info.0"),
                "fecha_concesion": None,
                "tipo": "sede electrónica — trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — instancias y trámites",
                "url": f"{self.sede_base}/info.0",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.ordenanzas_url),
                "fecha_concesion": None,
                "tipo": "ordenanzas fiscales ICIO/IBI",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenanzas fiscales — construcciones, instalaciones y obras",
                "url": self.ordenanzas_url,
                "source": "ayuntamiento",
                "nota": "Normativa fiscal de licencias urbanísticas en transparencia sede",
                "origen": "sede_transparencia",
            },
            {
                "id": _stable_id("lic", f"{WEB_BASE}/urbanismo"),
                "fecha_concesion": None,
                "tipo": "información urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Área de Urbanismo — portal institucional",
                "url": f"{WEB_BASE}/urbanismo",
                "source": "ayuntamiento",
                "nota": "Sección urbanismo web municipal (noticias y anuncios)",
                "origen": "web_urbanismo",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("licencia", "urban", "planeamiento", "información pública")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if "licencias urban" not in proc and not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "licencias urban" in proc:
            tipo = "licencia urbanística"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if "licencias urban" not in proc and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"] + " " + blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _web_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("url") or row["titulo"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web",
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") != "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_web_articles():
            add(self._web_to_proyecto(item))
        add(self._web_to_proyecto(self._collect_situa_metadata()))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web")),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
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
