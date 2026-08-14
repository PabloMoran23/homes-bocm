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

WEB_BASE = "https://www.santjoandalacant.es"
SEDE_BASE = "https://santjoandalacant.sedelectronica.es"
MUNICIPIO = "Sant Joan d'Alacant"
ID_PREFIX = "sant-joan-d-alacant"

WP_API = f"{WEB_BASE}/wp-json/wp/v2"
URBANISMO_AREA_ID = 505
AREA_URBANISMO_PAGE_ID = 85149
PGOU_PAGE_ID = 98643

RE_PREVIEW = re.compile(
    r'href="(https://santjoandalacant\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="(https://santjoandalacant\.sedelectronica\.es/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href=["\'](https://www\.santjoandalacant\.es/wp-content/uploads/[^"\']+\.pdf)["\']',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n|parcelaci[oó]n|segregaci[oó]n|"
    r"ocupaci[oó]n (?:de |en )?v[ií]a p[uú]blica|legalidad urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmod|modificaci[oó]n|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|consulta p[uú]blica|"
    r"expediente|proyecto|reparcel|estudio (?:de detalle|ac[uú]stico)|memoria|planos|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|sometimiento|sector|"
    r"unidad de actuaci[oó]n|\bua\b|\bue\b|programa de paisaje|agrupaci[oó]n|"
    r"registro de programas|nou nazareth|benimagrel|viario|ordenaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(subvenci[oó]n|convocatoria.*empleo|campamento de verano|huerto urbano|"
    r"mercadillo|luto oficial|escuela de navidad|festival|concurso|premio|"
    r"cobranza|impuesto|tribut|padrones|nombramiento|estatutos del creama)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_ISO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
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
    n = blob.lower()
    if "modificaci" in n and ("pgou" in n or "plan general" in n):
        return "modificación PGOU"
    if "programa de paisaje" in n:
        return "programa de paisaje"
    if "plan parcial" in n or re.search(r"\bpp\b", n):
        return "plan parcial"
    if "informaci" in n or "exposici" in n or "consulta p" in n:
        return "información pública"
    if "pgou" in n or "planeam" in n:
        return "planeamiento"
    if "proyecto" in n and "obra" in n:
        return "proyecto de obra"
    if "licencia" in n:
        return "licencia publicada"
    if "memoria" in n or "plano" in n:
        return "documentación técnica"
    return "urbanismo"


class SantJoanDAlacantAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Elementor (área urbanismo/PGOU) + sede espublico gestiona (tablón + trámites)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info")
        self.urbanismo_area_id = int(self.config.get("urbanismo_area_id") or URBANISMO_AREA_ID)
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
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "Mozilla/5.0 (compatible; poc-bocm-sant-joan-d-alacant/1.0)",
                )
            },
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = (
                f"{WP_API}/posts?areas={self.urbanismo_area_id}"
                f"&per_page=100&page={page}&_fields=id,date,link,title,excerpt"
            )
            try:
                batch = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(batch, list) or not batch:
                break
            for post in batch:
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                excerpt = _strip_html(post.get("excerpt", {}).get("rendered", ""))
                blob = f"{title} {excerpt}"
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _iso_date_wp(str(post.get("date") or "")),
                        "url": str(post.get("link") or ""),
                        "blob": blob,
                        "origen": "wp_noticia_urbanismo",
                    }
                )
            if len(batch) < 100:
                break
            page += 1
        return rows

    def _collect_wp_pages(self, parent_id: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        url = f"{WP_API}/pages?parent={parent_id}&per_page=100&_fields=id,date,link,title,content"
        try:
            pages = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return rows
        if not isinstance(pages, list):
            return rows
        for page in pages:
            page_id = int(page.get("id") or 0)
            title = _strip_html(page.get("title", {}).get("rendered", ""))
            html = str(page.get("content", {}).get("rendered") or "")
            link = str(page.get("link") or "")
            fecha = _iso_date_wp(str(page.get("date") or ""))
            heading_m = re.search(
                r'elementor-heading-title[^>]*>([^<]{20,500})<',
                html,
                re.I,
            )
            heading = _strip_html(heading_m.group(1)) if heading_m else ""
            blob = f"{title} {heading}"
            rows.append(
                {
                    "titulo": (heading or title)[:500],
                    "fecha": fecha,
                    "url": link,
                    "blob": blob,
                    "origen": "wp_pagina_urbanismo",
                }
            )
            for pdf_url in RE_PDF_HREF.findall(html):
                label_m = re.search(
                    rf'href=["\']{re.escape(pdf_url)}["\'][^>]*>.*?elementor-icon-list-text">([^<]+)',
                    html,
                    re.I | re.S,
                )
                label = _strip_html(label_m.group(1)) if label_m else Path(pdf_url).name
                rows.append(
                    {
                        "titulo": f"{title} — {label}"[:500],
                        "fecha": _fecha_from_blob(label) or fecha,
                        "url": pdf_url,
                        "blob": f"{title} {label} {heading}",
                        "origen": "wp_pdf_urbanismo",
                        "parent_url": link,
                    }
                )
            if page_id:
                rows.extend(self._collect_wp_pages(page_id))
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S | re.I):
            if "preview-document" not in tr:
                continue
            cells: dict[str, str] = {}
            for cm in re.finditer(
                r'class="(class_[^"]+)"[^>]*data-label[^>]*>(.*?)</td>',
                tr,
                re.S | re.I,
            ):
                cells[cm.group(1)] = _strip_html(cm.group(2))
            link_m = re.search(
                r'href="(https://santjoandalacant\.sedelectronica\.es/preview-document/[^"]+)"',
                tr,
                re.I,
            )
            if not link_m:
                continue
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or cells.get("class_name", "")
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": cells.get("class_folderCode", ""),
                    "procedimiento": cells.get("class_folderName", ""),
                    "categoria": cells.get("class_boardCategory", ""),
                    "descripcion": cells.get("class_description", ""),
                    "fecha": _parse_fecha_dmy(cells.get("class_dateFrom", "")),
                    "url": link_m.group(1),
                    "blob": " ".join(
                        str(cells.get(k) or "")
                        for k in (
                            "class_name",
                            "class_folderCode",
                            "class_folderName",
                            "class_boardCategory",
                            "class_description",
                        )
                    )
                    + f" {titulo}",
                    "origen": "sede_tablon",
                }
            )
        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "blob": titulo,
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_EXCLUDE.search(blob) and not RE_LICENCIA.search(blob):
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
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row.get("blob") or row.get("titulo", "")):
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
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo", "")
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "sede_tablon":
            if not RE_PROYECTO.search(blob):
                return None
        elif row.get("origen") == "sede_tramite":
            if not RE_PROYECTO.search(blob):
                return None
        elif not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expediente"):
            rec["expte"] = row["expediente"]
        if row.get("parent_url"):
            rec["parent_url"] = row["parent_url"]
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
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

        for item in self._collect_wp_pages(AREA_URBANISMO_PAGE_ID):
            add(self._to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._to_proyecto(item))
        for item in self._collect_board():
            add(self._to_proyecto(item))
        for item in self._collect_tramites():
            add(self._to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_paginas": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_pagina")),
            "wp_pdfs": sum(1 for r in rows if r.get("origen") == "wp_pdf_urbanismo"),
            "wp_noticias": sum(1 for r in rows if r.get("origen") == "wp_noticia_urbanismo"),
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
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
