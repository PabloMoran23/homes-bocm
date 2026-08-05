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

SEDE_BASE = "https://sede.alhaurindelatorre.es"
WP_BASE = "https://alhaurindelatorre.es"
WP_API = f"{WP_BASE}/wp-json/wp/v2/posts"
MUNICIPIO = "Alhaurín de la Torre"
ID_PREFIX = "alhaurin-de-la-torre"

DEFAULT_WP_CATEGORIES = [91, 92, 93, 90]  # planeamiento, obras ejecutadas/en ejecución, planimetría
DEFAULT_SEED_PAGES = [
    f"{WP_BASE}/category/areas-municipales/urbanismo-obras-e-infraestructura-viaria/planeamiento-urbanistico/",
    f"{WP_BASE}/category/areas-municipales/urbanismo-obras-e-infraestructura-viaria/tramites-de-urbanismo/",
    f"{WP_BASE}/sugerencias-al-pgom/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|v[ií]a p[uú]blica|bando.*obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n|calificaci[oó]n|"
    r"reurbanizaci[oó]n|planimetr|adaptaci[oó]n|bando|encauzamiento)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza|padr[oó]n|polic[ií]a local|activa-t joven|subvenci[oó]n|"
    r"empleo dana|consejos sectoriales|auxiliar administrativo|pe[oó]n)",
)
RE_PDF_HREF = re.compile(
    r'href="(https://alhaurindelatorre\.es/wp-content/uploads/[^"]+\.pdf)"',
    re.I,
)
RE_WP_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_GRID_CTL = re.compile(
    r'id="ctl00_principal__gridDetalle_ctl(\d+)_lblFec_inici"[^>]*>([^<]*)</span>',
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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"/(\d{4})/(\d{2})/", text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "pgom" in b or "sugerencia" in b:
        return "PGOM"
    if "calificaci" in b:
        return "calificación urbanística"
    if "planimetr" in b:
        return "planimetría"
    if "plan parcial" in b or "sector" in b:
        return "plan parcial / sector"
    if "reurbaniz" in b:
        return "reurbanización"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "bando" in b and "obra" in b:
        return "bando de obra"
    if "licencia" in b:
        return "licencia publicada"
    if "encauzamiento" in b:
        return "obra hidráulica"
    return "urbanismo"


class AlhaurinDeLaTorreAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress urbanismo (PDFs/obras) + tablón SWAL sede (ASP.NET postback)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.wp_categories = [int(x) for x in (self.config.get("wp_categories") or DEFAULT_WP_CATEGORIES)]
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.tablon_max_pages = int(self.config.get("tablon_max_pages", 12))
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alhaurin-de-la-torre/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

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
        html = self._postback(html, "ctl00$principal$lbAccion", "")
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
            has_doc = bool(
                re.search(rf"ctl00\\$principal\\$_gridDetalle\\$ctl{ctl}\\$lnkVerDocum", body)
            )
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
                    "has_doc": has_doc,
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

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        for cat in self.wp_categories:
            page = 1
            while page <= 5:
                url = f"{self.wp_base}/wp-json/wp/v2/posts?categories={cat}&per_page=100&page={page}"
                try:
                    raw = self._fetch(url)
                    posts = json.loads(raw)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not posts:
                    break
                for post in posts:
                    pid = int(post.get("id") or 0)
                    if not pid or pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    title = _strip_html(post.get("title", {}).get("rendered", ""))
                    link = str(post.get("link") or "")
                    fecha = (post.get("date") or "")[:10] or None
                    rows.append(
                        {
                            "titulo": title,
                            "url": link,
                            "fecha": fecha,
                            "blob": f"{title} {link}",
                            "wp_id": pid,
                        }
                    )
                page += 1
        return rows

    def _collect_wp_pdfs(self, post: dict[str, Any]) -> list[dict[str, Any]]:
        url = post.get("url") or ""
        if not url:
            return []
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []

        seen: set[str] = set()
        pdfs: list[dict[str, Any]] = []
        for m in RE_PDF_HREF.finditer(html):
            pdf_url = m.group(1)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            name = Path(urllib.parse.unquote(pdf_url)).stem.replace("_", " ").replace("-", " ")
            pdfs.append(
                {
                    "titulo": f"{post['titulo']} — {name}"[:500],
                    "url": pdf_url,
                    "fecha": post.get("fecha") or _fecha_from_blob(pdf_url),
                    "blob": f"{post['titulo']} {name} {pdf_url}",
                    "post_url": url,
                }
            )
        return pdfs

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        tramites = f"{self.wp_base}/category/areas-municipales/urbanismo-obras-e-infraestructura-viaria/tramites-de-urbanismo/"
        return [
            {
                "id": _stable_id("lic", f"{self.sede_base}/tablon"),
                "fecha_concesion": None,
                "tipo": "tablón electrónico de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica SWAL",
                "url": self._tablon_url or f"{self.sede_base}/",
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios municipales (ASP.NET postback)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", tramites),
                "fecha_concesion": None,
                "tipo": "formularios y trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de urbanismo — formularios licencias y vía pública",
                "url": tramites,
                "source": "ayuntamiento",
                "nota": "Sin listado histórico de concesiones; solo impresos informativos",
                "origen": "wp_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/tramites"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/",
                "source": "ayuntamiento",
                "nota": "Licencias y certificados urbanísticos vía sede (certificado digital)",
                "origen": "sede_tramite",
            },
        ]

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_TABLON_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        ent = (row.get("entidad") or "").lower()
        if any(k in ent for k in ("urbanismo", "obras", "infraestructura")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        tipo = "licencia / bando de obra"
        if re.search(r"(?i)bando", blob):
            tipo = "bando de obra"
        elif re.search(r"(?i)v[ií]a p[uú]blica", blob):
            tipo = "ocupación vía pública"
        key = row.get("edicto") or row.get("url")
        return {
            "id": _stable_id("lic", str(key)),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
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

    def _wp_post_to_proyecto(self, post: dict[str, Any]) -> dict[str, Any] | None:
        blob = post.get("blob") or ""
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", f"wp:{post.get('wp_id')}:{post['url']}"),
            "municipio": MUNICIPIO,
            "titulo": post["titulo"],
            "fecha": post.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": post["url"],
            "source": "ayuntamiento",
            "origen": "wordpress",
        }

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or ""
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "wordpress_pdf",
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "wp_tramite")),
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

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for post in self._collect_wp_posts():
            add(self._wp_post_to_proyecto(post))
            for pdf in self._collect_wp_pdfs(post):
                add(self._pdf_to_proyecto(pdf))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "wordpress": sum(1 for r in rows if r.get("origen") == "wordpress"),
            "wordpress_pdf": sum(1 for r in rows if r.get("origen") == "wordpress_pdf"),
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
