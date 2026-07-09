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

WP_BASE = "https://www.ciudadrodrigo.es/ayuntamiento"
SEDE_BASE = "https://ciudadrodrigo.sedelectronica.es"
MUNICIPIO = "Ciudad Rodrigo"
ID_PREFIX = "ciudad-rodrigo"

WP_API = f"{WP_BASE}/wp-json/wp/v2"
TRAMITES_URL = f"{WP_BASE}/tramites-y-gestiones-impresos/"
PGOU_URL = f"{WP_BASE}/plan-general-de-ordenacion-urbana-municipal/"

URBANISMO_CATEGORY_SLUGS: tuple[str, ...] = (
    "normativa-urbanistica-de-aplicacion-planeamiento",
    "normativa-urbanistica-de-aplicacion-gestion",
    "normativa-urbanistica-en-tramitacion-planeamiento",
    "normativa-urbanistica-en-tramitacion-gestion",
    "urbanismo-autorizaciones-de-uso-excepcional",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|"
    r"obra mayor|primera ocupaci[oó]n|parcelaci[oó]n|segregaci[oó]n|"
    r"ocupaci[oó]n (?:de )?v[ií]a p[uú]blica|autorizaci[oó]n de uso excepcional)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|"
    r"autorizaci[oó]n de uso excepcional|pech|conjunto hist[oó]rico|"
    r"ordenaci[oó]n|urbanizaci[oó]n|suelo r[uú]stico|suelo urban)",
)
RE_SKIP_BOARD = re.compile(
    r"(?i)(oposici[oó]n|concurso|proceso selectivo|baremaci[oó]n|"
    r"subvenci[oó]n|beca|miropincho|martes chico|martes mayor|"
    r"licencia de transporte|auto taxi|director de la escuela)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_FECHA_YM = re.compile(r"/wp-content/uploads/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PREVIEW = re.compile(
    r'href="(https://ciudadrodrigo\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?ciudadrodrigo\.es)?/ayuntamiento/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_LIC_BLOCK = re.compile(
    r"((?:Solicitud|Declaraci[oó]n)[^<]{0,120}(?:licencia|obra|ocupaci[oó]n|segregaci[oó]n)[^<]{0,120})"
    r".*?href=\"([^\"]+\.pdf)\"",
    re.I | re.S,
)
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,4}/\d{4}[^/\s]*)")


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(url or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _fecha_from_text(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_iso(text)


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_url(href: str, base: str = WP_BASE) -> str:
    return urllib.parse.urljoin(base, unescape(href))


def _proyecto_tipo(title: str, categoria: str = "") -> str:
    blob = f"{title} {categoria}".lower()
    if "autorizaci" in blob and "uso excepcional" in blob:
        return "autorización uso excepcional"
    if "convenio" in blob or "reparcel" in blob:
        return "convenio urbanístico"
    if "informaci" in blob and "públic" in blob:
        return "información pública"
    if "plan parcial" in blob or "plan especial" in blob:
        return "plan parcial"
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "modificaci" in blob and "pgou" in blob:
        return "modificación PGOU"
    if "proyecto de actuaci" in blob or "urbanizaci" in blob:
        return "actuación urbanística"
    if "pech" in blob or "conjunto hist" in blob:
        return "plan especial"
    if "pgou" in blob or "planeam" in blob:
        return "planeamiento"
    return "urbanismo"


class CiudadRodrigoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (normativa urbanística) + tablón espublico + trámites PDF."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.wp_api = str(self.config.get("wp_api") or f"{self.wp_base}/wp-json/wp/v2").rstrip("/")
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ciudad-rodrigo/1.0")},
        )
        if use_sede_ssl or self.sede_base in url:
            with self._opener.open(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _category_id(self, slug: str) -> int | None:
        try:
            cats = self._fetch_json(f"{self.wp_api}/categories?slug={urllib.parse.quote(slug)}")
        except (urllib.error.URLError, json.JSONDecodeError):
            return None
        if not cats:
            return None
        return int(cats[0]["id"])

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for cat_slug in URBANISMO_CATEGORY_SLUGS:
            cat_id = self._category_id(cat_slug)
            if not cat_id:
                continue
            page = 1
            while page <= 20:
                url = (
                    f"{self.wp_api}/posts?categories={cat_id}"
                    f"&per_page=100&page={page}&_fields=id,slug,link,title,date,content"
                )
                try:
                    posts = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not posts:
                    break
                for post in posts:
                    link = str(post.get("link") or "")
                    if not link or link in seen:
                        continue
                    seen.add(link)
                    titulo = _strip_html(post.get("title", {}).get("rendered", ""))
                    content = str(post.get("content", {}).get("rendered") or "")
                    pdfs = [_abs_url(m.group(1), self.wp_base) for m in RE_PDF_HREF.finditer(content)]
                    fecha = _parse_fecha_iso(str(post.get("date") or "")) or _fecha_from_text(titulo)
                    rows.append(
                        {
                            "titulo": titulo[:500],
                            "fecha": fecha,
                            "url": link,
                            "tipo": _proyecto_tipo(titulo, cat_slug),
                            "categoria": cat_slug,
                            "origen": "wp_categoria",
                            **({"pdf_url": pdfs[0], "pdf_count": len(pdfs)} if pdfs else {}),
                        }
                    )
                if len(posts) < 100:
                    break
                page += 1
        return rows

    def _collect_pgou_page(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(f"{self.pgou_url}")
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf_url = _abs_url(m.group(1), self.wp_base)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            local = html[max(0, m.start() - 300) : m.start()]
            label = _strip_html(local)[-200:] or pdf_url.rsplit("/", 1)[-1]
            rows.append(
                {
                    "titulo": f"PGOU — {label[:400]}",
                    "fecha": _fecha_from_url(pdf_url),
                    "url": self.pgou_url,
                    "pdf_url": pdf_url,
                    "tipo": "planeamiento",
                    "categoria": "pgou",
                    "origen": "pgou_pdf",
                }
            )
        return rows

    def _parse_board_table(self, html: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            link_m = re.search(
                r'href="(https://ciudadrodrigo\.sedelectronica\.es/preview-document/[^"]+)"',
                tr,
                re.I,
            )
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or _strip_html(cells[0] if cells else "")
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": _strip_html(cells[1]) if len(cells) > 1 else "",
                    "procedimiento": _strip_html(cells[2]) if len(cells) > 2 else "",
                    "categoria": _strip_html(cells[3]) if len(cells) > 3 else "",
                    "descripcion": _strip_html(cells[4]) if len(cells) > 4 else "",
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])) if len(cells) > 5 else None,
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        items = self._parse_board_table(html)
        if items:
            return items
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            if url in seen:
                continue
            seen.add(url)
            local = html[max(0, m.start() - 400) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": "",
                    "procedimiento": "",
                    "categoria": "",
                    "descripcion": titulo,
                    "fecha": _fecha_from_text(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_tramites_licencias(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tramites_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_LIC_BLOCK.finditer(html):
            title = _strip_html(m.group(1))
            pdf_url = _abs_url(m.group(2), self.wp_base)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            rows.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": _fecha_from_url(pdf_url),
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": self.tramites_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "nota": "Formulario de solicitud; no concesión publicada",
                    "origen": "tramites_pdf",
                }
            )
        return rows

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y exposiciones públicas en sede electrónica",
                "origen": "sede_tablon",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_SKIP_BOARD.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if not RE_LICENCIA.search(blob):
            if "licencias urban" not in proc and "licencias urban" not in cat:
                if "licencias de actividad" not in proc:
                    return None
        key = row.get("expediente") or row.get("url") or row.get("titulo")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha") or _fecha_from_text(row.get("titulo", "")),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_SKIP_BOARD.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            proc = (row.get("procedimiento") or "").lower()
            if "licencias urban" in proc or "licencias de actividad" in proc:
                return None
        if not RE_PROYECTO.search(blob):
            if "urban" not in (row.get("categoria") or "").lower():
                return None
        key = row.get("expediente") or row.get("url") or row.get("titulo")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_text(row.get("titulo", "")),
            "tipo": _proyecto_tipo(row["titulo"], row.get("procedimiento", "")),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or "urbanismo",
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "categoria": row.get("categoria"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

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
        for rec in self._licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for rec in self._collect_tramites_licencias():
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
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "tramites": sum(1 for r in rows if r.get("origen") == "tramites_pdf"),
            "info": sum(1 for r in rows if r.get("origen") == "sede_tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._licencia_info_pages():
            existing[rec["id"]] = rec
        for rec in self._collect_tramites_licencias():
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

        for item in self._collect_wp_posts():
            add(self._wp_to_proyecto(item))
        for item in self._collect_pgou_page():
            add(self._wp_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp": sum(1 for r in rows if r.get("origen") == "wp_categoria"),
            "pgou": sum(1 for r in rows if r.get("origen") == "pgou_pdf"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
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
