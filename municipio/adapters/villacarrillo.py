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

WP_BASE = "https://www.villacarrillo.es"
SEDE_BASE = "https://villacarrillo.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
PMVS_URL = f"{WP_BASE}/plan-municipal-de-vivienda-y-suelo/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Villacarrillo"
ID_PREFIX = "villacarrillo"

URBANISMO_CATEGORY_ID = 218
OBRAS_CATEGORY_ID = 40

DEFAULT_SEED_PAGES: list[str] = [
    PMVS_URL,
    f"{WP_BASE}/transparencia/agenda-urbana-2030/",
    f"{WP_BASE}/ayuntamiento/ordenanzas-y-reglamentos/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|autorizaci[oó]n.*obra|"
    r"tarjeta.*estacionamiento|estacionamiento.*residente)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|municipal)|pgou|pmvs|convenio|"
    r"informaci[oó]n p[uú]blica|consulta p[uú]blica|exposici[oó]n p[uú]blica|"
    r"expediente|proyecto|modificaci[oó]n|reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|"
    r"memoria|planos|boja|edicto|aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|vivienda y suelo|agenda urbana|cerro molinos|"
    r"instalaci[oó]n solar|fotovoltaica|pasos peatonales|urbanizaci[oó]n|"
    r"obras.*(?:mejora|acceso|paviment|infraestructura))",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza|padrones|oferta empleo|mercadillo|puestos mercadillo|"
    r"reglamento de r[eé]gimen interior|residencia de adultos|"
    r"l[ií]nea 132 kv|subestaci[oó]n)",
)
RE_WP_EXCLUDE = re.compile(
    r"(?i)(fiestas|cine|empleo|concurso|deporte|cementerio|horario especial|"
    r"proceso selectivo|almacenista|corresponsabilidad|nota informativa transversal)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|proceso selectivo|pleno|"
    r"subvenci[oó]n deportiv|iae|cobranza|oferta empleo|mercadillo|"
    r"reglamento de r[eé]gimen interior|residencia de adultos)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://villacarrillo\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https://storage\.googleapis\.com/stateless-www-villacarrillo-es/|'
    r'(?:https://www\.villacarrillo\.es)?/wp-content/uploads/)[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|documents|stateless-www-villacarrillo-es)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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
    m = re.search(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b", text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    iso = _parse_fecha_iso(text)
    if iso:
        return iso
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "pmvs" in b or "plan municipal de vivienda" in b:
        return "PMVS"
    if "agenda urbana" in b:
        return "agenda urbana"
    if "consulta p" in b and "blica" in b:
        return "consulta pública"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "memoria" in b:
        return "memoria planeamiento"
    if "planos" in b or "plano" in b:
        return "planos planeamiento"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "licencia" in b:
        return "licencia publicada"
    if "obra" in b or "instalaci" in b:
        return "obra pública"
    return "urbanismo"


class VillacarrilloAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress WPBakery + sede espublico tablón + PMVS PDFs + SITUA (metadato PGOU)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.wp_api = f"{self.wp_base}/wp-json/wp/v2"
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.pmvs_url = str(self.config.get("pmvs_url") or PMVS_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wp_categories = [int(x) for x in (self.config.get("wp_categories") or [URBANISMO_CATEGORY_ID])]
        self.obras_category_id = int(self.config.get("obras_category_id") or OBRAS_CATEGORY_ID)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-villacarrillo/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

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

    def _paginate_wp(self, endpoint: str, max_pages: int = 5, **params: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page_num in range(1, max_pages + 1):
            q = {"per_page": 100, "page": page_num, "status": "publish", **params}
            url = f"{self.wp_api}/{endpoint}?{urllib.parse.urlencode(q)}"
            try:
                batch = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(batch, list) or not batch:
                break
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = ""
            m = re.search(r"<title>([^<]+)", html, re.I)
            if m:
                page_title = _strip_html(m.group(1))
            for m in RE_PDF_HREF.finditer(html):
                pdf = m.group(1)
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
                link_text = ""
                ctx = html[max(0, m.start() - 200) : m.end() + 50]
                text_m = re.search(r">([^<]{3,120})</a>", ctx)
                if text_m:
                    link_text = _strip_html(text_m.group(1))
                titulo = link_text or name
                blob = f"{page_title} {titulo} {pdf}"
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if "vivienda" not in page_url.lower() and "urban" not in page_url.lower():
                        continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": page_url,
                        "pdf_url": pdf,
                        "fecha": _fecha_from_blob(pdf + " " + titulo),
                        "origen": "wp_pdf",
                        "page_title": page_title,
                    }
                )
        return rows

    def _wp_item_to_proyecto(self, item: dict[str, Any], origen: str) -> dict[str, Any] | None:
        title = _strip_html(str((item.get("title") or {}).get("rendered") or ""))
        if not title or RE_WP_EXCLUDE.search(title):
            return None
        content = str((item.get("content") or {}).get("rendered") or "")
        blob = f"{title} {_strip_html(content)}"
        if origen != "wp_urbanismo" and not RE_PROYECTO.search(blob):
            return None
        if origen == "wp_urbanismo" and not RE_PROYECTO.search(blob):
            if not re.search(
                r"(?i)(obra|proyecto|paviment|acera|instalaci|solar|pgou|vivienda|urban)",
                blob,
            ):
                return None
        url = str(item.get("link") or "").strip()
        if not url:
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": _iso_date_wp(str(item.get("date") or item.get("modified") or "")),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": origen,
        }
        pdfs = [m.group(1) for m in RE_PDF_HREF.finditer(content)]
        if pdfs:
            rec["pdf_url"] = pdfs[0]
        return rec

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')} {row.get('page_title', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
            return None
        key = row.get("pdf_url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or row.get("pdf_url") or self.pmvs_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias de obra y actividad",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y edictos publicados en sede electrónica espublico",
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
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación Cl@ve; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "disposiciones")):
            return True
        if "ordenanza" in cat or "urban" in cat:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
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
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "disposiciones" not in proc and "ordenanza" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite")),
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

        for cat_id, origen in (
            (URBANISMO_CATEGORY_ID, "wp_urbanismo"),
            (self.obras_category_id, "wp_obras"),
        ):
            for item in self._paginate_wp("posts", categories=cat_id):
                add(self._wp_item_to_proyecto(item, origen))

        for item in self._collect_seed_pdfs():
            add(self._pdf_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Villacarrillo — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": "Visor regional SituaDIFusión; planeamiento digitalizado sin WFS enlazable",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
            "pdf": sum(1 for r in rows if r.get("origen") == "wp_pdf"),
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
