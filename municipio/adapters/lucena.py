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

BASE = "https://lucena.es"
TRANSP_BASE = "https://transparencia.lucena.es"
SEDE_BASE = "https://sede.eprinsa.es/lucena"
TABLON_URL = f"{SEDE_BASE}/tablon-de-edictos"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Lucena"
ID_PREFIX = "lucena"

DEFAULT_SEED_PAGES = [
    f"{BASE}/medio-ambiente-urbanismo-y-obras-publicas/",
    f"{BASE}/delegacion-de-urbanismo-y-ordenacion-del-territorio/",
    f"{BASE}/normativa-municipal/",
    f"{TRANSP_BASE}/publicidad_activa/plan-general-de-ordenacion-urbana-pgou-y-los-mapas-y-planos-que-lo-detallan/",
    f"{TRANSP_BASE}/publicidad_activa/modificaciones-aprobadas-del-pgou-y-planes-parciales-aprobados/",
    f"{BASE}/catalogo-de-tramites/",
]

RE_PDF_HREF = re.compile(
    r'href=["\']((?:https://(?:lucena|transparencia\.lucena)\.es)?/wp-content/uploads/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|tasa.*licencia|ordenanza.*obra|icio\b)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional|parcial)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|innovaci[oó]n|avance|actuaci[oó]n|campo de aras|"
    r"revisi[oó]n parcial|nnss|calificaci[oó]n|urbanizaci[oó]n|per[ií]metro)",
)
RE_BOJA_DATE = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_BOP_DATE = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_HEADING = re.compile(r"<h([23])[^>]*>(.*?)</h\1>", re.S | re.I)
RE_ANCHOR_PDF = re.compile(
    r'<a\s+[^>]*href=["\']([^"\']+\.pdf[^"\']*)["\'][^>]*>(.*?)</a>',
    re.S | re.I,
)
RE_SKIP_PDF = re.compile(
    r"(?i)(ordenanza_general_aplicacion|ordenanza_ibi|ordenanza_iae|ordenanza_icio|"
    r"ordenanza_iivtnu|ordenanza_espectaculos|ordenanza_bodas|ordenanza_quioscos|"
    r"ordenanza_mesas|ordenanza_puestos|ordenanza_autotaxis|ordenanza_tasa_derechos|"
    r"vivero_de_empresas|precios-publicos-servicios-instalaciones-deportivas)",
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
    m = RE_BOP_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
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
    if "plan parcial" in b or "plan especial" in b or "campo de aras" in b:
        return "plan especial"
    if "revisi" in b and "parcial" in b:
        return "revisión PGOU"
    if "convenio" in b:
        return "convenio urbanístico"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "consulta ciudadana" in b or "consulta p" in b:
        return "consulta pública"
    if "licencia" in b and "proyecto" in b:
        return "licencia / proyecto"
    if "urbanizaci" in b:
        return "urbanización"
    if "bando" in b and ("solar" in b or "urban" in b):
        return "bando urbanístico"
    if "ordenanza" in b and ("urban" in b or "suelo" in b or "licencia" in b):
        return "ordenanza urbanística"
    if "bop" in b or "boja" in b:
        return "publicación oficial"
    return "urbanismo"


class LucenaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (lucena.es + transparencia) + sede eprinsa/Diputación Córdoba."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-lucena/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, page_url: str) -> str:
        return urllib.parse.urljoin(page_url, unescape(href))

    def _section_at(self, html: str, pos: int) -> str | None:
        section: str | None = None
        for m in RE_HEADING.finditer(html):
            if m.start() > pos:
                break
            section = _strip_html(m.group(2))
        return section

    def _pdf_is_urban(self, blob: str) -> bool:
        if RE_SKIP_PDF.search(blob):
            return False
        return bool(RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob))

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            for m in RE_ANCHOR_PDF.finditer(html):
                href = self._abs_url(m.group(1), page_url)
                if href in seen:
                    continue
                anchor = _strip_html(m.group(2))
                if not anchor:
                    anchor = unescape(urllib.parse.unquote(Path(href).name)).replace("_", " ").replace(".pdf", "")
                section = self._section_at(html, m.start())
                blob = f"{anchor} {href} {section or ''} {page_url}"
                if not self._pdf_is_urban(blob):
                    continue
                seen.add(href)
                rows.append(
                    {
                        "titulo": (f"{section} — {anchor}" if section else anchor)[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": page_url,
                        "pdf_url": href,
                        "section": section,
                        "blob": blob,
                        "origen": "web_seed",
                    }
                )

            for m in RE_PDF_HREF.finditer(html):
                href = self._abs_url(m.group(1), page_url)
                if href in seen:
                    continue
                name = unescape(urllib.parse.unquote(Path(href).name)).replace("_", " ").replace(".pdf", "")
                section = self._section_at(html, m.start())
                blob = f"{name} {href} {section or ''} {page_url}"
                if not self._pdf_is_urban(blob):
                    continue
                seen.add(href)
                rows.append(
                    {
                        "titulo": name[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": page_url,
                        "pdf_url": href,
                        "section": section,
                        "blob": blob,
                        "origen": "web_seed",
                    }
                )

            if "publicidad_activa" in page_url:
                title_m = re.search(r"<title>([^<]+)", html, re.I)
                titulo = _strip_html(title_m.group(1)) if title_m else page_url
                key = f"page:{page_url}"
                if key not in seen:
                    seen.add(key)
                    rows.append(
                        {
                            "titulo": titulo[:500],
                            "fecha": None,
                            "url": page_url,
                            "pdf_url": None,
                            "section": "publicidad activa",
                            "blob": f"{titulo} {page_url} pgou planeamiento",
                            "origen": "transparencia_pgou",
                        }
                    )

        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for term in ("planeamiento", "pgou", "urbanismo", "plan especial", "licencia"):
            url = (
                f"{BASE}/wp-json/wp/v2/posts"
                f"?search={urllib.parse.quote(term)}&per_page=25"
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
                seen.add(pid)
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                content = post.get("content", {}).get("rendered", "") or ""
                if not RE_PROYECTO.search(f"{title} {content}") and not RE_LICENCIA.search(title):
                    continue
                rows.append(
                    {
                        "id": pid,
                        "titulo": title[:500],
                        "fecha": (post.get("date") or "")[:10] or None,
                        "url": post.get("link") or "",
                        "content": content,
                        "origen": f"wp_search_{term.replace(' ', '_')}",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        tasa_lic = f"{BASE}/wp-content/uploads/2021/04/28.-_tasa_por_licencias_urbanisticas_2016.pdf"
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
                "id": _stable_id("lic", f"{BASE}/catalogo-de-tramites/"),
                "fecha_concesion": None,
                "tipo": "trámites informativos (web)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — portal municipal",
                "url": f"{BASE}/catalogo-de-tramites/",
                "source": "ayuntamiento",
                "nota": "Resumen de trámites; detalle en sede eprinsa",
                "origen": "web_tramites",
            },
            {
                "id": _stable_id("lic", tasa_lic),
                "fecha_concesion": "2016-01-01",
                "tipo": "tasa licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tasa por licencias urbanísticas (ordenanza)",
                "url": tasa_lic,
                "source": "ayuntamiento",
                "nota": "Normativa fiscal; no concesiones publicadas",
                "origen": "web_normativa",
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
            "url": item.get("url", BASE),
            "source": "ayuntamiento",
            "pdf_url": item.get("pdf_url"),
            "origen": item.get("origen"),
            "section": item.get("section"),
        }

    def _post_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        blob = f"{titulo} {item.get('content', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        key = item.get("url") or titulo
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

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
        for item in self._collect_wp_posts():
            rec = self._post_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": 0, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_seed_pdfs():
            add(self._pdf_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._post_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Lucena — consulta SITUA (Junta de Andalucía)",
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
