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

BASE = "https://fuentepalmera.es"
URBANISMO_URL = f"{BASE}/urbanismo/"
SEDE_BASE = "https://sede.eprinsa.es/ftepalm"
TABLON_URL = f"{SEDE_BASE}/tablon-de-edictos"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Fuente Palmera"
ID_PREFIX = "fuente-palmera"
URBANISMO_CATEGORY_ID = 47

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    f"{BASE}/agenda-urbana/",
    f"{BASE}/bases-y-anuncios/",
]

RE_PDF_HREF = re.compile(
    r'href=["\']((?:https://fuentepalmera\.es)?/wp-content/uploads/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|modelo.*licencia|lc-0|dr-0|cp-0|aoe-0)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional|parcial)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|innovaci[oó]n|avance|nnss|normas subsidiarias|"
    r"clasificaci[oó]n|calificaci[oó]n|agenda urbana|vivienda y suelo|"
    r"instrumento urban|suelo no urbanizable|suelo urbanizable)",
)
RE_BOJA_DATE = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_HEADING = re.compile(r"<h([23])[^>]*>(.*?)</h\1>", re.S | re.I)
RE_ANCHOR_PDF = re.compile(
    r'<a\s+[^>]*href=["\']([^"\']+\.pdf[^"\']*)["\'][^>]*>(.*?)</a>',
    re.S | re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _fecha_from_blob(text: str) -> str | None:
    m = RE_BOJA_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
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


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "modificaci" in b and ("puntual" in b or "normativa" in b):
        return "modificación puntual"
    if "plan parcial" in b:
        return "plan parcial"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "nnss" in b or "normas subsidiarias" in b:
        return "normas subsidiarias"
    if "agenda urbana" in b or "vivienda y suelo" in b:
        return "agenda urbana"
    if "innovaci" in b:
        return "innovación normativa"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class FuentePalmeraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (ePrinsa) + sede eprinsa/Diputación Córdoba (tablón SPA)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wp_categories = [int(x) for x in (self.config.get("wp_categories") or [URBANISMO_CATEGORY_ID])]
        self.wp_max_pages = int(self.config.get("wp_max_pages", 5))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-fuente-palmera/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _section_at(self, html: str, pos: int) -> str | None:
        section: str | None = None
        for m in RE_HEADING.finditer(html):
            if m.start() > pos:
                break
            section = _strip_html(m.group(2))
        return section

    def _collect_urbanismo_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_ANCHOR_PDF.finditer(html):
            href = self._abs_url(m.group(1))
            if href in seen:
                continue
            seen.add(href)
            anchor = _strip_html(m.group(2))
            if not anchor:
                anchor = unescape(urllib.parse.unquote(Path(href).name)).replace("_", " ").replace(".pdf", "")
            section = self._section_at(html, m.start())
            titulo = anchor[:500]
            if section and section.lower() not in titulo.lower():
                titulo = f"{section} — {anchor}"[:500]
            blob = f"{titulo} {href} {section or ''}"
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_blob(blob),
                    "url": self.urbanismo_url,
                    "pdf_url": href,
                    "section": section,
                    "blob": blob,
                    "origen": "web_urbanismo",
                }
            )

        for m in RE_PDF_HREF.finditer(html):
            href = self._abs_url(m.group(1))
            if href in seen:
                continue
            seen.add(href)
            name = unescape(urllib.parse.unquote(Path(href).name)).replace("_", " ").replace(".pdf", "")
            section = self._section_at(html, m.start())
            blob = f"{name} {href} {section or ''}"
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(blob),
                    "url": self.urbanismo_url,
                    "pdf_url": href,
                    "section": section,
                    "blob": blob,
                    "origen": "web_urbanismo",
                }
            )
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            if page_url == self.urbanismo_url:
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                href = self._abs_url(m.group(1))
                if href in seen:
                    continue
                seen.add(href)
                name = unescape(urllib.parse.unquote(Path(href).name)).replace("_", " ").replace(".pdf", "")
                blob = f"{name} {href}"
                if not RE_PROYECTO.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": name[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": page_url,
                        "pdf_url": href,
                        "blob": blob,
                        "origen": page_url,
                    }
                )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()

        for cat in self.wp_categories:
            for page in range(1, self.wp_max_pages + 1):
                url = (
                    f"{self.wp_base}/wp-json/wp/v2/posts"
                    f"?categories={cat}&per_page=100&page={page}"
                    f"&_fields=id,date,link,title,content"
                )
                try:
                    data = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(data, list) or not data:
                    break
                for post in data:
                    pid = int(post.get("id") or 0)
                    if pid in seen:
                        continue
                    seen.add(pid)
                    title = _strip_html(post.get("title", {}).get("rendered", ""))
                    content = post.get("content", {}).get("rendered", "") or ""
                    pdf_m = RE_PDF_HREF.search(content)
                    rows.append(
                        {
                            "id": pid,
                            "titulo": title[:500],
                            "fecha": (post.get("date") or "")[:10] or None,
                            "url": post.get("link") or "",
                            "pdf_url": pdf_m.group(1) if pdf_m else None,
                            "content": content,
                            "origen": f"wp_category_{cat}",
                        }
                    )
                if len(data) < 100:
                    break

        for term in ("planeamiento", "modificacion puntual", "urbanismo", "pgou"):
            url = (
                f"{self.wp_base}/wp-json/wp/v2/posts"
                f"?search={urllib.parse.quote(term)}&per_page=20"
                f"&_fields=id,date,link,title,content"
            )
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(data, list):
                continue
            for post in data:
                pid = int(post.get("id") or 0)
                if pid in seen:
                    continue
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                content = post.get("content", {}).get("rendered", "") or ""
                if not RE_PROYECTO.search(f"{title} {content}") and not RE_LICENCIA.search(title):
                    continue
                seen.add(pid)
                pdf_m = RE_PDF_HREF.search(content)
                rows.append(
                    {
                        "id": pid,
                        "titulo": title[:500],
                        "fecha": (post.get("date") or "")[:10] or None,
                        "url": post.get("link") or "",
                        "pdf_url": pdf_m.group(1) if pdf_m else None,
                        "content": content,
                        "origen": f"wp_search_{term.replace(' ', '_')}",
                    }
                )
        return rows

    def _collect_licencia_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._collect_urbanismo_pdfs():
            blob = item.get("blob") or item.get("titulo", "")
            if not RE_LICENCIA.search(blob):
                continue
            pdf = item.get("pdf_url") or item["url"]
            rec = {
                "id": _stable_id("lic", pdf),
                "fecha_concesion": item.get("fecha"),
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": item["titulo"],
                "url": item.get("url", self.urbanismo_url),
                "pdf_url": pdf,
                "source": "ayuntamiento",
                "nota": "Modelo/solicitud informativa; no concesión publicada en tablón",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos — licencias y urbanismo",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Sede eprinsa (Diputación Córdoba); listado vía SPA Ember sin API pública",
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
                "url": f"{self.sede_base}/tramites",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin histórico público estructurado)",
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
                "nota": "Requiere identificación Cl@ve/certificado; no hay listado abierto",
                "origen": "sede_tramite",
            },
        ]

    def _pdf_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        pdf = item.get("pdf_url") or item["url"]
        blob = item.get("blob") or item.get("titulo", "")
        return {
            "id": _stable_id("proy", pdf),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", self.urbanismo_url),
            "source": "ayuntamiento",
            "pdf_url": pdf,
            "origen": item.get("origen"),
            "section": item.get("section"),
        }

    def _post_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        blob = f"{titulo} {item.get('content', '')}"
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = item.get("pdf_url") or item.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        return rec

    def _post_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        if not RE_LICENCIA.search(titulo):
            return None
        key = item.get("url") or titulo
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": item.get("fecha"),
            "tipo": "noticia urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
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
        for rec in self._collect_licencia_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_wp_posts():
            rec = self._post_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_licencias(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": result["rows"],
                    "added": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": result["rows"], "added": 0, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_urbanismo_pdfs():
            blob = item.get("blob") or item.get("titulo", "")
            if RE_PROYECTO.search(blob):
                add(self._pdf_to_proyecto(item))
        for item in self._collect_seed_pdfs():
            add(self._pdf_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._post_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Fuente Palmera — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": "Visor regional de planeamiento; sin geometría por expediente municipal",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pdfs": sum(1 for r in rows if r.get("pdf_url")),
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
