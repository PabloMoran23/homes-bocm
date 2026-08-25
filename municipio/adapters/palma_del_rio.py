from __future__ import annotations

import hashlib
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

WP_BASE = "https://palmadelrio.es"
SEDE_BASE = "https://sede.eprinsa.es/palmario"
TABLON_URL = f"{SEDE_BASE}/tablon-de-edictos"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Palma del Río"
ID_PREFIX = "palma-del-rio"

URBANISMO_CATEGORY_ID = 135
DEFAULT_SEED_PAGES = [
    f"{WP_BASE}/urbanismo-y-vivienda/planes/",
    f"{WP_BASE}/urbanismo-y-vivienda/otros-servicios-urbanisticos/",
]
DEFAULT_LICENCIA_PAGES = [
    f"{WP_BASE}/urbanismo-y-vivienda/licencia-para-obras-y-cocheras/",
    f"{WP_BASE}/urbanismo-y-vivienda/declaracion-responsable/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|cambio de uso|concesi[oó]n de licencia|licencia de urbanizaci[oó]n|"
    r"licitaci[oó]n.*(?:vivienda|inmueble|obra))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|consulta p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|innovaci[oó]n|avance|expropiaci[oó]n|bando|"
    r"reforma interior|peri|pei|pmvs|actuaci[oó]n|urbanizaci[oó]n|transformaci[oó]n urban)",
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https://palmadelrio\.es)?/wp-content/uploads/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_VISOR_HREF = re.compile(
    r'href=["\'](https://palmario-ofvirtual\.e-admin\.es/[^"\']+)["\']',
    re.I,
)
RE_WP_PDF_LINK = re.compile(
    r'href="(https://palmadelrio\.es/wp-content/uploads/[^"]+\.pdf)"',
    re.I,
)
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def _fecha_from_blob(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
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
    if "peri" in b or "reforma interior" in b:
        return "plan especial reforma interior"
    if "pei" in b or "plan especial de infraestructura" in b:
        return "plan especial infraestructuras"
    if "pmvs" in b or "plan municipal de vivienda" in b:
        return "plan municipal vivienda"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "convenio" in b:
        return "convenio urbanístico"
    if "estudio de ordenaci" in b:
        return "estudio de ordenación"
    if "urbanizaci" in b:
        return "urbanización"
    if "expropiaci" in b:
        return "expropiación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "consulta p" in b and "blica" in b:
        return "consulta pública"
    if "innovaci" in b:
        return "innovación normativa"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "licencia" in b:
        return "licencia publicada"
    if "bando" in b or "bop" in b:
        return "publicación oficial"
    if "actuaci" in b:
        return "actuación urbanística"
    return "urbanismo"


class PalmaDelRioAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (categoría urbanismo) + PDFs PGOU/planes + sede eprinsa (trámites informativos)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.wp_categories = [int(x) for x in (self.config.get("wp_categories") or [URBANISMO_CATEGORY_ID])]
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.wp_max_pages = int(self.config.get("wp_max_pages", 2))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-palma-del-rio/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60, context=self._ssl_ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for cat in self.wp_categories:
            for page in range(1, self.wp_max_pages + 1):
                url = (
                    f"{self.wp_base}/wp-json/wp/v2/posts"
                    f"?categories={cat}&per_page=100&page={page}&_fields=id,date,link,title,content"
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
                    pdf_m = RE_WP_PDF_LINK.search(content)
                    pdf_url = pdf_m.group(1) if pdf_m else None
                    rows.append(
                        {
                            "id": pid,
                            "titulo": title[:500],
                            "fecha": (post.get("date") or "")[:10] or None,
                            "url": post.get("link") or "",
                            "pdf_url": pdf_url,
                            "content": content,
                            "origen": f"wp_category_{cat}",
                        }
                    )
                if len(data) < 100:
                    break

        for term in ("planeamiento", "pgou", "convenio urban"):
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
                pdf_m = RE_WP_PDF_LINK.search(content)
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

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                ctx_start = max(0, m.start() - 600)
                ctx = _strip_html(html[ctx_start : m.start() + 200])
                titulo = name[:500]
                link_m = re.search(
                    r"((?:Plan|PGOU|PEI|PMVS|Aprobaci[oó]n|Modificaci[oó]n|Tomo)[^.]{8,180})",
                    ctx,
                    re.I,
                )
                if link_m:
                    titulo = link_m.group(1).strip()[:500]
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(pdf + " " + ctx),
                        "url": page_url,
                        "pdf_url": pdf,
                        "origen": page_url,
                    }
                )
            for m in RE_VISOR_HREF.finditer(html):
                visor = m.group(1)
                if visor in seen:
                    continue
                seen.add(visor)
                rows.append(
                    {
                        "titulo": "PGOU Palma del Río — visor documental e-admin",
                        "fecha": _fecha_from_blob(visor),
                        "url": page_url,
                        "visor_url": visor,
                        "origen": page_url,
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
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
        ]
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                if not re.search(r"(?i)licencia|obra|declaracion|solicitud|ocupacion", name + " " + pdf):
                    continue
                rows.append(
                    {
                        "id": _stable_id("lic", pdf),
                        "fecha_concesion": _fecha_from_blob(pdf),
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": name[:500],
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "nota": "Modelo/solicitud informativa; no concesión publicada en tablón",
                        "origen": page_url,
                    }
                )
        return rows

    def _post_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        if not RE_LICENCIA.search(titulo):
            return None
        key = item.get("pdf_url") or item.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": item.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": item.get("url", ""),
            "source": "ayuntamiento",
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        return rec

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

    def _pdf_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        key = item.get("pdf_url") or item.get("visor_url") or item.get("url", "")
        blob = f"{item.get('titulo', '')} {key}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        if item.get("visor_url"):
            rec["visor_url"] = item["visor_url"]
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
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_wp_posts():
            rec = self._post_to_licencia(item)
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
            add(self._post_to_proyecto(item))
        for item in self._collect_seed_pdfs():
            add(self._pdf_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Palma del Río — consulta SITUA (Junta de Andalucía)",
                "fecha": "2011-06-13",
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
            "wp_categories": self.wp_categories,
            "seed_pages": len(self.seed_pages),
            "pdfs": sum(1 for r in rows if r.get("pdf_url")),
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
