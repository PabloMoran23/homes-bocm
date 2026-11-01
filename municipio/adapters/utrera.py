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

WP_BASE = "https://www.utrera.org"
TRANSP_BASE = "https://transparencia.utrera.org"
SEDE_BASE = "https://utrera.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
MUNICIPIO = "Utrera"
ID_PREFIX = "utrera"
INE_CODE = "41095"
CIF = "P4109500I"

DIPUSEVILLA_LICENCIAS = (
    f"https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif={CIF}"
)
SITUA_SEARCH = (
    f"https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid={INE_CODE}"
)

PGOU_2015_URL = (
    "https://www.utrera.org/documento-pgou-aprobacion-provisional-3a-aprobado-por-el-"
    "ayuntamiento-pleno-en-sesion-celebrada-el-dia-dieciseis-de-abril-de-dos-mil-quince-"
    "pendiente-en-su-caso-de-aprobacion-definitiva-por-el-org/"
)
PGOU_2002_URL = "http://www.utrera.org/pgou2002/"
TRANSP_PGOU_URL = (
    "https://transparencia.utrera.org/project/"
    "plan-general-de-ordenacion-urbana-pgou-y-los-mapas-y-planos-que-lo-detallan/"
)

WP_PROJECT_CATEGORIES = (12, 685)  # área + servicios urbanismo
WP_SEARCH_TERMS = (
    "pgou",
    "plan parcial",
    "informacion publica",
    "licencia urban",
    "planeamiento",
    "urbanizacion",
    "estudio de detalle",
    "convenio urban",
)
WP_POST_SEARCH_TERMS = ("pgou", "planeamiento", "licencia obra", "plan parcial")

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|licencia urban|licytal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|prestaci[oó]n compensatoria|no urbanizable|"
    r"regularizaci[oó]n|nnss|cat[aá]logo|consulta p[uú]blica|avance|situa|atu-|"
    r"reurbaniz|pol[ií]gono industrial|actuaci[oó]n)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://utrera\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_url(href: str, base: str) -> str:
    return urllib.parse.urljoin(base, unescape(href))


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "plan parcial" in blob or " pp " in blob:
        return "plan parcial"
    if "plan especial" in blob:
        return "plan especial"
    if "estudio de detalle" in blob or "estudio de ordenaci" in blob:
        return "estudio de detalle"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "licencia" in blob:
        return "licencia publicada"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "reurbaniz" in blob or "urbanizaci" in blob:
        return "urbanización"
    return "urbanismo"


class UtreraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Extra (utrera.org) + transparencia Divi + sede espublico (deshabilitada) + Licytal."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transp_base") or TRANSP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, timeout: float = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "Mozilla/5.0 poc-bocm-utrera/1.0",
                ),
            },
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, timeout: float = 90) -> Any:
        return json.loads(self._fetch(url, timeout=timeout))

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, timeout=45)
        except (urllib.error.URLError, OSError, TimeoutError):
            return []
        if "deshabilitada" in html.lower() or "disabled" in html.lower():
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))
            documento = cells.get("class_name", "")
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
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "descripcion": descripcion[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {titulo}"
                    ),
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_wp_api_items(
        self,
        endpoint: str,
        params: dict[str, str | int],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            q = dict(params)
            q["per_page"] = 100
            q["page"] = page
            url = f"{self.wp_base}/wp-json/wp/v2/{endpoint}?" + urllib.parse.urlencode(q)
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError, OSError):
                break
            if not isinstance(data, list) or not data:
                break
            for item in data:
                if not isinstance(item, dict):
                    continue
                title = _strip_html(str((item.get("title") or {}).get("rendered") or ""))
                link = str(item.get("link") or "")
                if not title or not link:
                    continue
                fecha = str(item.get("date") or item.get("modified") or "")[:10] or None
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": link,
                        "origen": f"wordpress_{endpoint}",
                    }
                )
            page += 1
        return rows

    def _collect_wp_projects(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for cat_id in WP_PROJECT_CATEGORIES:
            for item in self._collect_wp_api_items(
                "project", {"project_category": cat_id}
            ):
                if item["url"] in seen:
                    continue
                seen.add(item["url"])
                rows.append(item)
        for term in WP_SEARCH_TERMS:
            for item in self._collect_wp_api_items("project", {"search": term}):
                if item["url"] in seen:
                    continue
                if not RE_PROYECTO.search(item["titulo"]) and not RE_LICENCIA.search(
                    item["titulo"]
                ):
                    continue
                seen.add(item["url"])
                rows.append(item)
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for term in WP_POST_SEARCH_TERMS:
            for item in self._collect_wp_api_items("posts", {"search": term}):
                if item["url"] in seen:
                    continue
                if not RE_PROYECTO.search(item["titulo"]):
                    continue
                seen.add(item["url"])
                item["origen"] = "wordpress_posts"
                rows.append(item)
        return rows

    def _collect_pgou_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url, origen in (
            (PGOU_2015_URL, "pgou_2015"),
            (PGOU_2002_URL, "pgou_2002"),
            (TRANSP_PGOU_URL, "transparencia_pgou"),
        ):
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, OSError):
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf_url = _abs_url(m.group(1), page_url)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                label = _strip_html(urllib.parse.unquote(pdf_url.split("/")[-1]))
                rows.append(
                    {
                        "titulo": f"PGOU Utrera — {label}"[:500],
                        "fecha": _fecha_from_blob(label, pdf_url),
                        "url": pdf_url,
                        "pdf_url": pdf_url,
                        "origen": origen,
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón sede (deshabilitado)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Utrera (espublico)",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Página /board devuelve «Página deshabilitada» (oct 2026)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", DIPUSEVILLA_LICENCIAS),
                "fecha_concesion": None,
                "tipo": "portal licencias Diputación de Sevilla",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta pública de licencias — Diputación de Sevilla (LicytalPub)",
                "url": DIPUSEVILLA_LICENCIAS,
                "source": "ayuntamiento",
                "nota": f"CIF {CIF}; INE {INE_CODE}",
                "origen": "dipusevilla",
            },
            {
                "id": _stable_id("lic", f"{self.wp_base}/project/servicio-de-licencias-urbanisticas/"),
                "fecha_concesion": None,
                "tipo": "trámite licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Servicio de licencias urbanísticas (web municipal)",
                "url": f"{self.wp_base}/project/servicio-de-licencias-urbanisticas/",
                "source": "ayuntamiento",
                "origen": "web_tramite",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        titulo = item["titulo"]
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(titulo),
            "url": item.get("pdf_url") or item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen", "web"),
        }

    def _wp_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(item.get("titulo") or ""):
            return None
        return {
            "id": _stable_id("lic", item["url"]),
            "fecha_concesion": item.get("fecha"),
            "tipo": "licencia / trámite urbanístico",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"],
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen", "wordpress_project"),
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
        for item in self._collect_wp_projects():
            rec = self._wp_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(
                1
                for r in rows
                if r.get("origen")
                in ("sede_tablon", "sede_tramite", "dipusevilla", "web_tramite")
            ),
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
        for item in self._collect_wp_projects():
            rec = self._wp_to_licencia(item)
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
            blob = item.get("blob") or ""
            if RE_PROYECTO.search(blob) and not (
                RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob)
            ):
                add(self._item_to_proyecto({**item, "origen": "tablon"}))

        for item in self._collect_wp_projects():
            add(self._item_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._item_to_proyecto(item))
        for item in self._collect_pgou_pdfs():
            add(self._item_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU / planeamiento Utrera — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
            }
        )
        add(
            {
                "id": _stable_id("proy", TRANSP_PGOU_URL),
                "municipio": MUNICIPIO,
                "titulo": "PGOU 2015 — transparencia municipal (mapas y planos)",
                "fecha": "2015-04-16",
                "tipo": "PGOU",
                "url": TRANSP_PGOU_URL,
                "source": "ayuntamiento",
                "origen": "transparencia",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wordpress": sum(1 for r in rows if str(r.get("origen", "")).startswith("wordpress")),
            "pgou_pdf": sum(1 for r in rows if "pgou" in str(r.get("origen", ""))),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
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
