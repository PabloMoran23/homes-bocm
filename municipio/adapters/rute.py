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

BASE = "https://rute.es"
PGOU_URL = f"{BASE}/servicios/urbanismo/pgou/"
URBANISMO_URL = f"{BASE}/servicios/urbanismo/"
LOCALIZAIN_URL = f"{BASE}/servicios/urbanismo/programa-localizain/"
INSTANCIAS_URL = f"{BASE}/ayuntamiento/normativa-municipal/modelos-de-solicitud/"
SEDE_BASE = "https://sede.eprinsa.es/rute"
TABLON_URL = f"{SEDE_BASE}/tablon-de-edictos"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Rute"
ID_PREFIX = "rute"

PGOU_PAGE_ID = 7582
URBANISMO_PAGE_ID = 8975
LOCALIZAIN_PAGE_ID = 8936
MODELOS_PAGE_ID = 8864

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|parcelaci[oó]n|ocupaci[oó]n edificaci[oó]n|finalizaci[oó]n de obra|"
    r"consulta urban|dr-obras|primera ocupaci)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional|parcial)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|innovaci[oó]n|avance|cat[aá]logo|normas urban|"
    r"localizain|pol[ií]gono industrial|espacios productivos|calificaci[oó]n|actuaci[oó]n)",
)
RE_ANCHOR = re.compile(
    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.S | re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://rute\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _fecha_from_blob(text: str) -> str | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
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
    if "localizain" in b or "polígono industrial" in b or "poligono industrial" in b:
        return "programa localización industrial"
    if "bop" in b or "boja" in b:
        return "publicación oficial"
    if "catálogo" in b or "catalogo" in b:
        return "catálogo urbanístico"
    if "normas urban" in b:
        return "normativa urbanística"
    if "memoria" in b:
        return "memoria planeamiento"
    if "plano" in b:
        return "cartografía urbanística"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    return "urbanismo"


class RuteAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress ePrinsa (PGOU Google Drive + modelos PDF) + sede eprinsa/Diputación Córdoba."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.localizain_url = str(self.config.get("localizain_url") or LOCALIZAIN_URL)
        self.instancias_url = str(self.config.get("instancias_url") or INSTANCIAS_URL)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-rute/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{BASE}/", href)

    def _collect_wp_page_links(self, page_id: int, page_url: str, origen: str) -> list[dict[str, Any]]:
        url = f"{BASE}/wp-json/wp/v2/pages/{page_id}?_fields=id,link,title,content,modified"
        try:
            page = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(page, dict):
            return []

        content = page.get("content", {}).get("rendered", "") or ""
        modified = (page.get("modified") or "")[:10] or None
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_ANCHOR.finditer(content):
            href = m.group(1).strip()
            if href.startswith("#") or "mailto:" in href.lower():
                continue
            title = _strip_html(m.group(2))
            if not title or len(title) < 3:
                title = unescape(urllib.parse.unquote(Path(href).name))[:500]
            abs_href = href if href.startswith("http") else self._abs_url(href)
            if abs_href in seen:
                continue
            seen.add(abs_href)
            blob = f"{title} {abs_href}"
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": modified or _fecha_from_blob(blob),
                    "url": page_url,
                    "doc_url": abs_href,
                    "blob": blob,
                    "origen": origen,
                }
            )

        for m in RE_PDF_HREF.finditer(content):
            pdf = self._abs_url(m.group(1))
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": modified or _fecha_from_blob(pdf),
                    "url": page_url,
                    "doc_url": pdf,
                    "blob": f"{name} {pdf}",
                    "origen": origen,
                }
            )
        return rows

    def _collect_instancias_urbanismo(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.instancias_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf = self._abs_url(m.group(1))
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            blob = f"{name} {pdf}"
            if not RE_LICENCIA.search(blob) and not re.search(
                r"(?i)licencia|obra|declaracion|comunicacion|urban", blob
            ):
                continue
            if pdf in seen:
                continue
            seen.add(pdf)
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(blob),
                    "url": self.instancias_url,
                    "doc_url": pdf,
                    "blob": blob,
                    "origen": "web_modelos",
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for term in ("planeamiento", "pgou", "urbanismo", "localizain"):
            url = (
                f"{BASE}/wp-json/wp/v2/posts"
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
                        "origen": f"wp_search_{term}",
                    }
                )
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
                "id": _stable_id("lic", self.instancias_url),
                "fecha_concesion": None,
                "tipo": "modelos licencias y obras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Modelos de solicitud — urbanismo",
                "url": self.instancias_url,
                "source": "ayuntamiento",
                "nota": "Formularios PDF (licencia obra, DR, comunicación previa); no concesiones publicadas",
                "origen": "web_modelos",
            },
        ]

    def _doc_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo", "")
        if not RE_PROYECTO.search(blob):
            return None
        doc = item.get("doc_url") or item.get("url", "")
        return {
            "id": _stable_id("proy", doc),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", self.pgou_url),
            "source": "ayuntamiento",
            "doc_url": doc,
            "origen": item.get("origen"),
        }

    def _instancia_to_licencia(self, item: dict[str, Any]) -> dict[str, Any]:
        doc = item.get("doc_url") or item.get("url", "")
        return {
            "id": _stable_id("lic", doc),
            "fecha_concesion": item.get("fecha"),
            "tipo": "modelo trámite urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"],
            "url": item.get("url", self.instancias_url),
            "source": "ayuntamiento",
            "doc_url": doc,
            "origen": item.get("origen"),
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
        for item in self._collect_instancias_urbanismo():
            rec = self._instancia_to_licencia(item)
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

        for item in self._collect_wp_page_links(PGOU_PAGE_ID, self.pgou_url, "web_pgou"):
            add(self._doc_to_proyecto(item))
        for item in self._collect_wp_page_links(URBANISMO_PAGE_ID, self.urbanismo_url, "web_urbanismo"):
            add(self._doc_to_proyecto(item))
        for item in self._collect_wp_page_links(LOCALIZAIN_PAGE_ID, self.localizain_url, "web_localizain"):
            add(self._doc_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._post_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "Planeamiento urbanístico vigente — consulta SITUA (Junta de Andalucía)",
                "fecha": "2018-08-09",
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": "Visor regional de planeamiento; enlace desde página PGOU municipal",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pgou_docs": sum(1 for r in rows if r.get("origen") == "web_pgou"),
            "urbanismo": sum(1 for r in rows if r.get("origen") == "web_urbanismo"),
            "localizain": sum(1 for r in rows if r.get("origen") == "web_localizain"),
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
