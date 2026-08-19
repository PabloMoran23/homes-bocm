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

BASE = "https://www.elcampello.es"
SEDE_BASE = "https://elcampello.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
MUNICIPIO = "El Campello"
ID_PREFIX = "el-campello"

DEFAULT_NEWS_AREAS = (18, 35, 37, 58)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|legalizaci[oó]n|c[eé]dula|certificado de compatibilidad)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|movilidad)|pgou|pmus|"
    r"informaci[oó]n p[uú]blica|expediente|expte\.?|modificaci[oó]n|reparcel|"
    r"estudio (?:de detalle|ac[uú]stico|ambiental|integraci[oó]n)|consulta p[uú]blica|"
    r"exposici[oó]n p[uú]blica|expropiaci|programa de actuaci|sector|ordenanza|"
    r"terrazas|desarrollo urban|nulidad plan|evaluaci[oó]n ambiental)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"oficial alba[nñ]il|concurso-oposici|subvenci[oó]n.*empleo)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://elcampello\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_NEWS_LINK = re.compile(
    r'href="/index\.php\?s=noticias&amp;id=(\d+)"[^>]*>([^<]+)',
    re.I,
)
RE_NEWS_FECHA = re.compile(r'<dt class="fecha">([^<]+)</dt>', re.I)
RE_NEWS_TITULO = re.compile(r'<dt class="titulo">([^<]+)</dt>', re.I)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "estudio de detalle" in n or "modificaci" in n and "estudio" in n:
        return "estudio de detalle"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "plan especial" in n:
        return "plan especial"
    if "pmus" in n or "movilidad" in n:
        return "plan movilidad"
    if "programa de actuaci" in n:
        return "programa actuación"
    if "reparcel" in n:
        return "reparcelación"
    if "expropiaci" in n:
        return "expropiación"
    if "consulta p" in n and "blica" in n:
        return "consulta pública"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "exposici" in n and "p" in n and "blica" in n:
        return "exposición pública"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "evaluaci" in n and "ambiental" in n:
        return "evaluación ambiental"
    return "planeamiento"


class ElCampelloAyuntamientoAdapter(AyuntamientoAdapter):
    """CMS elcampello.es (noticias áreas urbanismo) + sede espublico gestiona (/board/)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.news_area_ids = tuple(
            int(x) for x in (self.config.get("news_area_ids") or DEFAULT_NEWS_AREAS)
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(
        self,
        url: str,
        *,
        portal: bool = False,
        timeout: int = 60,
    ) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-campello/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or ("latin-1" if portal else "utf-8")
            return raw.decode(charset, errors="replace")

    def _abs_portal(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin(f"{BASE}/", href.lstrip("/"))

    def _abs_sede(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin(f"{self.sede_base}/", href.lstrip("/"))

    def _fetch_geometry_attempt(self, rec: dict[str, Any]) -> dict[str, Any]:
        """Intento best-effort ArcGIS REST (bloqueado en CI → sin geometría)."""
        geom_cfg = self.config.get("geometry") or {}
        base = str(geom_cfg.get("base_url") or "").rstrip("/")
        if not base:
            return rec
        url = f"{base}?f=json"
        try:
            self._fetch(url, timeout=15)
        except (urllib.error.URLError, TimeoutError, OSError):
            return rec
        return rec

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
            if not documento or documento in ("Documento",):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            url = self._abs_sede(url)

            titulo = cells.get("class_description") or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()

            expediente = cells.get("class_folderCode", "")
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": cells.get("class_folderName", "")[:200],
                    "categoria": cells.get("class_boardCategory", "")[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(cells.get("class_dateFrom", "")),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {cells.get('class_folderName', '')} "
                        f"{cells.get('class_boardCategory', '')} "
                        f"{cells.get('class_description', '')} "
                        f"{title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if cat == "urbanismo" or any(k in proc for k in ("planeamiento", "licencia", "urban", "obra")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _collect_news_index(self) -> dict[str, str]:
        seen: dict[str, str] = {}
        for area_id in self.news_area_ids:
            url = f"{BASE}/index.php?s=area_noticias&id={area_id}"
            try:
                html = self._fetch(url, portal=True)
            except urllib.error.URLError:
                continue
            for nid, title in RE_NEWS_LINK.findall(html):
                seen.setdefault(nid, _clean(title))
        return seen

    def _fetch_news_detail(self, news_id: str, fallback_title: str) -> dict[str, Any] | None:
        url = f"{BASE}/index.php?s=noticias&id={news_id}"
        try:
            html = self._fetch(url, portal=True)
        except urllib.error.URLError:
            return None

        titulo_m = RE_NEWS_TITULO.search(html)
        titulo = _clean(titulo_m.group(1)) if titulo_m else _clean(fallback_title)
        fecha_m = RE_NEWS_FECHA.search(html)
        fecha = _parse_fecha_dmy(fecha_m.group(1)) if fecha_m else None

        pdfs = [self._abs_portal(h) for h in RE_PDF_HREF.findall(html)]
        pdfs = list(dict.fromkeys(pdfs))
        detail_url = pdfs[0] if pdfs else url

        return {
            "news_id": news_id,
            "titulo": titulo,
            "fecha": fecha,
            "url": detail_url,
            "page_url": url,
            "pdfs": pdfs,
            "blob": titulo,
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        tramites = [
            (
                "tablon_sede",
                "Tablón de anuncios — licencias y urbanismo",
                self.board_url,
                "tablón licencias y actividad",
            ),
            (
                "sede_dossier",
                "Catálogo de trámites — sede electrónica",
                f"{self.sede_base}/dossier",
                "catálogo trámites urbanismo",
            ),
            (
                "obra_mayor",
                "Guía tramitación obra mayor",
                f"{BASE}/upload/areas_ficheros/territorio_y_vivienda/tramitacion_obra_mayor.pdf",
                "obra mayor",
            ),
            (
                "cert_compat",
                "Certificado compatibilidad urbanística (sede)",
                self.sede_base,
                "certificado compatibilidad",
            ),
            (
                "dr_primera_ocup",
                "Modelo DR primera ocupación",
                f"{BASE}/upload/areas_ficheros/territorio_y_vivienda/modelo_dr_primera_ocupacion_rellenable_no_residencial.pdf",
                "declaración responsable",
            ),
        ]
        rows: list[dict[str, Any]] = []
        for key, titulo, url, tipo in tramites:
            rows.append(
                {
                    "id": _stable_id("lic", key),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_info",
                }
            )
        return rows

    def _news_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or ""
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob.replace("licencia", "")):
            return None
        key = f"news-{item['news_id']}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": "noticia",
            "news_id": item["news_id"],
        }
        if item.get("page_url"):
            rec["page_url"] = item["page_url"]
        return self._fetch_geometry_attempt(rec)

    def _news_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = f"news-{item['news_id']}"
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": item.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"],
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": "noticia",
        }

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
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "urban" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
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
        return self._fetch_geometry_attempt(rec)

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

        news_index = self._collect_news_index()
        for nid, title in news_index.items():
            detail = self._fetch_news_detail(nid, title)
            if not detail:
                continue
            rec = self._news_to_licencia(detail)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "noticias": sum(1 for r in rows if r.get("origen") == "noticia"),
            "info": sum(1 for r in rows if r.get("origen") == "tramite_info"),
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
        news_index = self._collect_news_index()
        for nid, title in news_index.items():
            detail = self._fetch_news_detail(nid, title)
            if not detail:
                continue
            rec = self._news_to_licencia(detail)
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

        news_index = self._collect_news_index()
        for nid, title in news_index.items():
            detail = self._fetch_news_detail(nid, title)
            if detail:
                add(self._news_to_proyecto(detail))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "noticias": sum(1 for r in rows if r.get("origen") == "noticia"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
