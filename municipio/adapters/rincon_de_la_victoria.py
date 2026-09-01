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

WEB_BASE = "https://www.rincondelavictoria.es"
SEDE_BASE = "https://sede.rincondelavictoria.es"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Rincón de la Victoria"
ID_PREFIX = "rincon-de-la-victoria"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/plan-general-de-ordenacion-urbanistica",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/catalogo",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/desarrollo",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/desarrollo/la-cala-del-moral",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/desarrollo/rincon-de-la-victoria",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/desarrollo/benagalbon",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/desarrollo/torre-de-benagalbon",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/modificaciones",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/modificaciones/la-cala-del-moral",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/modificaciones/rincon-de-la-victoria",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/modificaciones/benagalbon",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/modificaciones/torre-de-benagalbon",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/normativa-relacionada",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/ordenacion-urbanistica/entidades-de-conservacion",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/nuevo-plan-general",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/nuevo-plan-general/avance",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/nuevo-plan-general/aprobacion-inicial",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/nuevo-POU",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/nuevo-POU/avance",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/informacion-publica",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/convenios-urbanisticos",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/registros-urbanisticos",
    f"{WEB_BASE}/areas/urbanismo-y-vivienda/visor-urbanismo",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura|apertura de local)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|pou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|bopma|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|atu|delimitaci[oó]n|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n|expropiaci[oó]n|avance|"
    r"calificaci[oó]n|divisi[oó]n en fases|uer|diligencia|acuerdo jgl|regeneraci[oó]n|"
    r"catalogo|desarrollo|conservaci[oó]n|normativa urban|clasificaci[oó]n)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza|padr[oó]n|polic[ií]a local|aparcamiento|abono|f[ií]sicas|"
    r"modificaci[oó]n presupuestaria|ibi|iae|nichos|inmatriculaci[oó]n)",
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.rincondelavictoria\.es)?/sites/default/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_URBAN_LINK = re.compile(
    r'href="((?:https://www\.rincondelavictoria\.es)?/areas/urbanismo[^"#?]+)"',
    re.I,
)
RE_GRID_CTL = re.compile(
    r'id="ctl00_principal__gridDetalle_ctl(\d+)_lblFec_inici"[^>]*>([^<]*)</span>',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(url or text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(f"{text} {url}") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgom" in b or "plan general" in b and "ordenaci" in b:
        return "PGOM"
    if "pgou" in b:
        return "PGOU"
    if "pou" in b:
        return "POU"
    if "plan parcial" in b or " sup " in b or "sup-" in b:
        return "plan parcial"
    if "plan especial" in b or " sunp " in b:
        return "plan especial"
    if "convenio" in b:
        return "convenio urbanístico"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "catalogo" in b or "catálogo" in b:
        return "catálogo urbanístico"
    if "desarrollo" in b:
        return "desarrollo urbanístico"
    if "normativa" in b or "ordenanza" in b:
        return "normativa urbanística"
    if "licencia" in b:
        return "licencia publicada"
    if "avance" in b:
        return "planeamiento"
    return "urbanismo"


class RinconDeLaVictoriaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 10 urbanismo (PDFs) + tablón SWAL sede (ASP.NET postback)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 40))
        self.tablon_max_pages = int(self.config.get("tablon_max_pages", 15))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._tablon_url: str | None = None

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            data=data,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-rincon-de-la-victoria/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(self.web_base, unescape(href))

    def _get_form_fields(self, html: str) -> dict[str, str]:
        vs = re.search(r'name="__VIEWSTATE"[^>]*value="([^"]*)"', html)
        ev = re.search(r'name="__EVENTVALIDATION"[^>]*value="([^"]*)"', html)
        vsg = re.search(r'name="__VIEWSTATEGENERATOR"[^>]*value="([^"]*)"', html)
        action = re.search(r'<form[^>]*action="([^"]*)"', html)
        return {
            "__VIEWSTATE": vs.group(1) if vs else "",
            "__EVENTVALIDATION": ev.group(1) if ev else "",
            "__VIEWSTATEGENERATOR": vsg.group(1) if vsg else "",
            "action": action.group(1) if action else "/Default.aspx",
        }

    def _postback(self, html: str, target: str = "", argument: str = "") -> str:
        fields = self._get_form_fields(html)
        action = fields.pop("action")
        if not action.startswith("http"):
            action = f"{self.sede_base}{action}"
        data = urllib.parse.urlencode(
            {**fields, "__EVENTTARGET": target, "__EVENTARGUMENT": argument}
        ).encode()
        return self._fetch(action, data)

    def _open_tablon(self) -> str:
        html = self._fetch(f"{self.sede_base}/")
        html = self._postback(html, "ctl00$principal$blLateral", "3")
        m = re.search(r'<form[^>]*action="([^"]*)"', html)
        if m:
            action = m.group(1)
            self._tablon_url = action if action.startswith("http") else f"{self.sede_base}{action}"
        return html

    def _parse_tablon_rows(self, html: str) -> list[dict[str, Any]]:
        grid = re.search(r'id="ctl00_principal__gridDetalle"(.*?</table>)', html, re.S | re.I)
        if not grid:
            return []
        body = grid.group(1)
        rows: list[dict[str, Any]] = []
        for m in RE_GRID_CTL.finditer(body):
            ctl = m.group(1)
            fecha = m.group(2).strip()

            def cell(suffix: str) -> str:
                cm = re.search(
                    rf'id="ctl00_principal__gridDetalle_ctl{ctl}_{suffix}"[^>]*>(.*?)</span>',
                    body,
                    re.S | re.I,
                )
                if not cm:
                    return ""
                return _strip_html(cm.group(1))

            entidad = cell("lblEntidadOrigen")
            seccion = cell("lblSeccionOrigen")
            edicto = cell("lblIdeEdicto")
            descripcion = cell("lblDescripcion")
            tablon_url = self._tablon_url or f"{self.sede_base}/"
            rows.append(
                {
                    "fecha": _parse_fecha_dmy(fecha),
                    "fecha_raw": fecha,
                    "entidad": entidad,
                    "seccion": seccion,
                    "edicto": edicto,
                    "titulo": descripcion[:500],
                    "url": f"{tablon_url}#edicto-{edicto}",
                    "blob": f"{fecha} {entidad} {seccion} {edicto} {descripcion}",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._open_tablon()
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _ in range(self.tablon_max_pages):
            for row in self._parse_tablon_rows(html):
                key = row.get("edicto") or row.get("titulo") or ""
                if key and key not in seen:
                    seen.add(key)
                    rows.append(row)
            try:
                next_html = self._postback(html, "ctl00$principal$miniBotoneraDetalle$lnkSiguiente", "")
            except urllib.error.URLError:
                break
            if next_html == html or not self._parse_tablon_rows(next_html):
                break
            html = next_html
        return rows

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>([^<]+)',
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = _strip_html(m.group(1))
                t = re.sub(r"\s*[-|].*Rincón.*$", "", t, flags=re.I).strip()
                if t and len(t) > 3:
                    return t[:500]
        return fallback

    def _collect_drupal_pages(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        queue = list(dict.fromkeys(self.seed_pages))
        visited: set[str] = set()
        pages: list[dict[str, Any]] = []
        pdfs: list[dict[str, Any]] = []

        while queue and len(visited) < self.max_crawl_pages:
            url = queue.pop(0).rstrip("/")
            if url in visited:
                continue
            visited.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue

            title = self._page_title(html, url.split("/")[-1].replace("-", " "))
            if RE_PROYECTO.search(title) or RE_PROYECTO.search(url):
                pages.append(
                    {
                        "titulo": title,
                        "url": url,
                        "fecha": _fecha_from_blob(title, url),
                        "blob": f"{title} {url}",
                    }
                )

            for m in RE_URBAN_LINK.finditer(html):
                link = self._abs_url(m.group(1)).rstrip("/")
                if link not in visited and link not in queue and len(link) > len(self.web_base) + 10:
                    queue.append(link)

            for m in RE_PDF_HREF.finditer(html):
                pdf_url = self._abs_url(m.group(1))
                if "favicon" in pdf_url.lower():
                    continue
                name = Path(urllib.parse.unquote(pdf_url.split("?")[0])).stem.replace("_", " ").replace("-", " ")
                titulo = f"{title} — {name}"[:500]
                blob = f"{titulo} {pdf_url} {url}"
                if not RE_PROYECTO.search(blob):
                    continue
                pdfs.append(
                    {
                        "titulo": titulo,
                        "url": pdf_url,
                        "fecha": _fecha_from_blob(name, pdf_url),
                        "page_url": url,
                        "blob": blob,
                    }
                )

        return pages, pdfs

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", f"{self.sede_base}/tablon"),
                "fecha_concesion": None,
                "tipo": "tablón electrónico de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios y edictos — sede electrónica SWAL",
                "url": self._tablon_url or f"{self.sede_base}/",
                "source": "ayuntamiento",
                "nota": "Edictos municipales (ASP.NET postback)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/tramites"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/",
                "source": "ayuntamiento",
                "nota": "Licencias y certificados urbanísticos vía sede (certificado digital)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/urbanismo-contacto"),
                "fecha_concesion": None,
                "tipo": "consulta urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Contactar con urbanismo — sin listado histórico de licencias",
                "url": f"{self.web_base}/areas/urbanismo-y-vivienda/contactar-urbanismo",
                "source": "ayuntamiento",
                "nota": "No hay dataset público de licencias concedidas",
                "origen": "web_tramite",
            },
        ]

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_TABLON_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        ent = (row.get("entidad") or "").lower()
        sec = (row.get("seccion") or "").lower()
        if any(k in ent for k in ("urbanismo", "obras", "intervenci")):
            return True
        if any(k in sec for k in ("urbanismo", "obra", "licencia")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("edicto") or row.get("url")
        return {
            "id": _stable_id("lic", str(key)),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / edicto urbanístico",
            "distrito": row.get("seccion") or None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("edicto") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("edicto") or row.get("url")
        return {
            "id": _stable_id("proy", str(key)),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("edicto") or None,
            "origen": "tablon",
        }

    def _page_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "drupal_page",
        }

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "drupal_pdf",
            "page_url": row.get("page_url"),
        }

    def _situa_proyecto(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", SITUA_SEARCH),
            "municipio": MUNICIPIO,
            "titulo": "PGOU/PGOM — consulta SITUA (Junta de Andalucía)",
            "fecha": None,
            "tipo": "planeamiento general",
            "url": SITUA_SEARCH,
            "source": "ayuntamiento",
            "origen": "situa",
            "nota": "Visor regional de planeamiento aprobado (sin geometría por expediente)",
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
        self._open_tablon()
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
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self._open_tablon()
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
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

        pages, pdfs = self._collect_drupal_pages()
        for page in pages:
            add(self._page_to_proyecto(page))
        for pdf in pdfs:
            add(self._pdf_to_proyecto(pdf))
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        add(self._situa_proyecto())

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "drupal_page": sum(1 for r in rows if r.get("origen") == "drupal_page"),
            "drupal_pdf": sum(1 for r in rows if r.get("origen") == "drupal_pdf"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
