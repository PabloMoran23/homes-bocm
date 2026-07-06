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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.villadeajalvir.es"
MUNICIPIO = "Ajalvir"
ID_PREFIX = "ajalvir"

PLAN_GENERAL_ROOT = f"{BASE}/plan-general"
TRANSP_PGOU = f"{BASE}/transparencia/plan-general"
TABLON_URL = f"{BASE}/transparencia/tablon-de-anuncios"
SOLICITUDES_URL = f"{BASE}/transparencia/solicitudes"
PGOU_URL = f"{BASE}/areas-de-gobierno/urbanismo/pgou"

DEFAULT_K2_CATEGORIES: list[str] = [
    f"{BASE}/noticias-y-actualidad-de-ajalvir/itemlist/category/169-urbanismo",
    f"{BASE}/noticias-y-actualidad-de-ajalvir/itemlist/category/255-plan-general",
]

DEFAULT_DOCMAN_ROOTS: list[str] = [
    "/plan-general",
    "/transparencia/plan-general",
]

RE_DOCMAN_FILE = re.compile(
    r'href="(/[^"]+/file)"[^>]*data-title="([^"]*)"',
    re.I,
)
RE_DOCMAN_FILE_REV = re.compile(
    r'data-title="([^"]*)"[^>]*href="(/[^"]+/file)"',
    re.I,
)
RE_DOCMAN_FOLDER = re.compile(
    r'href="(/(?:plan-general|transparencia/plan-general)[^"#?]*)"', re.I
)
RE_K2_ITEM = re.compile(
    r'<article class="itemView[^"]*"[^>]*>.*?'
    r'<a href="(/noticias-y-actualidad-de-ajalvir/item/\d+[^"]*)"[^>]*title="([^"]*)"',
    re.I | re.S,
)
RE_K2_ITEM_ALT = re.compile(
    r'href="(/noticias-y-actualidad-de-ajalvir/item/\d+[^"]*)"[^>]*>([^<]{10,300})</a>',
    re.I,
)
RE_K2_DATE = re.compile(
    r'<p class="nspInfo[^"]*">(\d{1,2}-\d{1,2}-\d{4})</p>',
    re.I,
)
RE_ITEM_DATE = re.compile(
    r'<span class="itemDateCreated"[^>]*>([^<]+)</span>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|instalaci|funcionamiento)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable|"
    r"comunicaci[oó]n previa|autorizaci[oó]n previa|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|actuaci[oó]n comunicada|segregaci[oó]n|"
    r"procedimiento normal|instancia normalizada)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"modificaci[oó]n|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|"
    r"sector|parcela|suelo|bocm|avance|die|ordenanza.*urban|resoluci[oó]n convenio)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(cobranza|impuesto|iae|polic[ií]a local|convocatoria.*plaza|"
    r"pruebas m[eé]dicas|bando.*fiestas|ludoteca|declaraci[oó]n jurada|"
    r"estructura de costes|presupuesto)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_BOCM_DATE = re.compile(r"BOCM[- ](\d{4})(\d{2})(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                pass
    m = RE_BOCM_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _proyecto_tipo(title: str, url: str = "") -> str:
    blob = f"{title} {url}".lower()
    if "convenio" in blob or "reparcel" in blob:
        return "convenio urbanístico"
    if "avance" in blob or "pgou" in blob:
        return "PGOU"
    if "plan parcial" in blob or "plan especial" in blob:
        return "planeamiento"
    if "informaci" in blob:
        return "información pública"
    if "sector" in blob or "parcela" in blob:
        return "sector urbanístico"
    if "bocm" in blob:
        return "publicación BOCM"
    if "memoria" in blob:
        return "memoria"
    if "die" in blob or "anexo" in blob:
        return "documento ambiental"
    if "plano" in blob or re.search(r"\bpo\b|\bpi\b|p inf", blob):
        return "planos"
    return "urbanismo"


class AjalvirAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla + DOCman (PGOU, tablón, solicitudes) + noticias K2 urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.docman_roots = [str(x) for x in (self.config.get("docman_roots") or DEFAULT_DOCMAN_ROOTS)]
        self.k2_categories = [str(x) for x in (self.config.get("k2_categories") or DEFAULT_K2_CATEGORIES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ajalvir/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, page_url: str = BASE) -> str:
        return urljoin(page_url, href)

    def _extract_docman_docs(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pat in (RE_DOCMAN_FILE, RE_DOCMAN_FILE_REV):
            for m in pat.finditer(html):
                if pat is RE_DOCMAN_FILE:
                    href, title = m.group(1), m.group(2)
                else:
                    title, href = m.group(1), m.group(2)
                title = _clean_title(title)
                link = self._abs_url(href, page_url)
                if link in seen:
                    continue
                seen.add(link)
                rows.append(
                    {
                        "titulo": title,
                        "url": link,
                        "page_url": page_url,
                        "fecha": _parse_fecha_dmy(title),
                    }
                )
        return rows

    def _crawl_docman_tree(self, root_path: str) -> list[dict[str, Any]]:
        root_url = self._abs_url(root_path)
        visited_pages: set[str] = set()
        queue = [root_url]
        docs: list[dict[str, Any]] = []
        seen_docs: set[str] = set()

        while queue:
            page_url = queue.pop(0)
            if page_url in visited_pages:
                continue
            visited_pages.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            for rec in self._extract_docman_docs(html, page_url):
                if rec["url"] not in seen_docs:
                    seen_docs.add(rec["url"])
                    rec["origen"] = root_path
                    docs.append(rec)

            for m in RE_DOCMAN_FOLDER.finditer(html):
                sub = self._abs_url(m.group(1), page_url)
                if sub not in visited_pages and not sub.endswith("/file"):
                    queue.append(sub)

        return docs

    def _collect_k2_news(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for cat_url in self.k2_categories:
            try:
                html = self._fetch(cat_url)
            except urllib.error.URLError:
                continue

            items: list[tuple[str, str]] = []
            for m in RE_K2_ITEM.finditer(html):
                items.append((m.group(1), _clean_title(m.group(2))))
            if not items:
                for m in RE_K2_ITEM_ALT.finditer(html):
                    title = _clean_title(m.group(2))
                    if len(title) >= 10:
                        items.append((m.group(1), title))

            for href, title in items:
                item_url = self._abs_url(href)
                if item_url in seen:
                    continue
                seen.add(item_url)
                fecha = None
                try:
                    art_html = self._fetch(item_url)
                    dm = RE_ITEM_DATE.search(art_html)
                    if dm:
                        fecha = _parse_fecha_dmy(dm.group(1))
                    if not fecha:
                        for dm in RE_K2_DATE.finditer(html):
                            fecha = _parse_fecha_dmy(dm.group(1))
                            break
                except urllib.error.URLError:
                    pass
                rows.append(
                    {
                        "titulo": title,
                        "url": item_url,
                        "fecha": fecha or _parse_fecha_dmy(title),
                        "origen": cat_url,
                    }
                )
        return rows

    def _doc_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec.get("titulo") or ""
        url = rec.get("url") or ""
        blob = f"{title} {url}"
        if RE_TABLON_SKIP.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": rec.get("fecha") or _parse_fecha_dmy(title),
            "tipo": _proyecto_tipo(title, url),
            "url": url,
            "source": "ayuntamiento",
            "origen": rec.get("origen", "docman"),
        }

    def _news_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec.get("titulo") or ""
        if not RE_PROYECTO.search(title):
            return None
        url = rec.get("url") or ""
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": rec.get("fecha"),
            "tipo": _proyecto_tipo(title, url),
            "url": url,
            "source": "ayuntamiento",
            "origen": rec.get("origen", "k2_news"),
        }

    def _doc_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec.get("titulo") or ""
        if not RE_LICENCIA.search(title):
            return None
        url = rec.get("url") or ""
        tipo = "trámite licencia"
        tl = title.lower()
        if "obra mayor" in tl:
            tipo = "licencia obra mayor"
        elif "obra menor" in tl:
            tipo = "licencia obra menor"
        elif "declaraci" in tl:
            tipo = "declaración responsable"
        elif "actuaci" in tl and "comunicad" in tl:
            tipo = "actuación comunicada"
        elif "procedimiento normal" in tl:
            tipo = "licencia de actividad"
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": rec.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
            "nota": "Modelo/formulario de trámite; no concesión publicada",
            "origen": rec.get("origen", "solicitudes"),
        }

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for root in self.docman_roots:
            for doc in self._crawl_docman_tree(root):
                add(self._doc_to_proyecto(doc))

        try:
            tablon_html = self._fetch(TABLON_URL)
            for doc in self._extract_docman_docs(tablon_html, TABLON_URL):
                doc["origen"] = "tablon"
                add(self._doc_to_proyecto(doc))
        except urllib.error.URLError:
            pass

        for news in self._collect_k2_news():
            add(self._news_to_proyecto(news))

        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in (SOLICITUDES_URL, f"{BASE}/Solicitudes/"):
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                continue
            for doc in self._extract_docman_docs(html, page):
                doc["origen"] = "solicitudes"
                rec = self._doc_to_licencia(doc)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        return rows

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
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "solicitudes_docman"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "docman": sum(1 for r in rows if "docman" in str(r.get("origen", "")) or "tablon" in str(r.get("origen", ""))),
            "k2": sum(1 for r in rows if "k2" in str(r.get("origen", ""))),
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
