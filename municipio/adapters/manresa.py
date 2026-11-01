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

WEB_BASE = "https://web.manresa.cat"
SEU_BASE = "https://www.manresa.cat"
MUNICIPIO = "Manresa"
ID_PREFIX = "manresa"

URBANISME_TRAMITS = f"{WEB_BASE}/web/menu/632-urbanisme/tramits"

PROJECT_SEEDS: list[tuple[str, str]] = [
    (f"{WEB_BASE}/web/article/1804-planejament-en-tramit", "planejament en tràmit"),
    (f"{WEB_BASE}/web/article/3074-convenis-urbanistics", "conveni urbanístic"),
    (f"{WEB_BASE}/web/article/2349-plans-especials", "pla especial"),
    (f"{WEB_BASE}/web/article/3684-planejament-vigent", "planejament vigent"),
]

RE_CHILD_ARTICLE = re.compile(
    r'href="((?:https://web\.manresa\.cat)?/web/article/\d+-[^"/]+/\d+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n|comunicaci[oó] d'obra|"
    r"declaraci[oó] responsable|enderroc|primera ocupaci[oó]|parcel·laci[oó]|"
    r"moviment de terres|obra (?:petita|menor|major))",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")
RE_FECHA_PDF = re.compile(r"(?:/|_)(\d{2})-(\d{2})-(\d{2})(?:_|\.|-)")
RE_TRAMIT_FITXA = re.compile(r'href="(/seu/menu/fitxa/\d+)"[^>]*>\s*Informaci', re.I)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)
RE_PDF = re.compile(
    r'href="((?:https://web\.manresa\.cat)?/media/docs/[^"]+\.pdf)"',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_pdf(text: str) -> str | None:
    m = RE_FECHA_PDF.search(text or "")
    if not m:
        return None
    yy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year = 2000 + yy if yy < 70 else 1900 + yy
    try:
        return datetime(year, mm, dd).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_context(html: str, pdfs: list[str]) -> str | None:
    for pdf in pdfs:
        d = _parse_fecha_pdf(pdf)
        if d:
            return d
    return _parse_fecha_dmy(html) or _parse_fecha_pdf(html)


def _proyecto_tipo(titulo: str, section: str) -> str:
    blob = f"{titulo} {section}".lower()
    if "conveni" in blob:
        return "convenio urbanístico"
    if "pla especial" in blob or "pe " in blob or "pes " in blob:
        return "plan especial"
    if "pmu" in blob or "millora urbana" in blob:
        return "plan de mejora urbana"
    if "pou" in blob or "pla d'ordenaci" in blob or "planejament vigent" in blob:
        return "planeamiento vigente"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "informaci" in blob and ("públic" in blob or "public" in blob):
        return "información pública"
    if "planejament en tràmit" in section.lower():
        return "planeamiento en trámite"
    return section or "urbanismo"


class ManresaAyuntamientoAdapter(AyuntamientoAdapter):
    """CMS web.manresa.cat (articles urbanisme) + seu /seu/menu (trámites licencias)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seu_base = str(self.config.get("seu_base") or SEU_BASE).rstrip("/")
        self.tramits_url = str(self.config.get("tramits_url") or URBANISME_TRAMITS)
        self.project_seeds = [
            (str(u), s) for u, s in (self.config.get("project_seeds") or PROJECT_SEEDS)
        ]
        self.max_articles = int(self.config.get("max_articles", 150))
        self.fetch_timeout_s = int(self.config.get("fetch_timeout_s", 60))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-manresa/1.0")},
        )
        with urllib.request.urlopen(req, timeout=self.fetch_timeout_s) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href)).split("#")[0]

    def _page_h1(self, html: str) -> str:
        m = RE_H1.search(html or "")
        return _strip_html(m.group(1)) if m else ""

    def _extract_child_urls(self, html: str) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for m in RE_CHILD_ARTICLE.finditer(html):
            url = self._abs_url(m.group(1))
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def _extract_pdfs(self, html: str) -> list[str]:
        seen: set[str] = set()
        pdfs: list[str] = []
        for m in RE_PDF.finditer(html):
            u = self._abs_url(m.group(1))
            if u not in seen:
                seen.add(u)
                pdfs.append(u)
        return pdfs

    def _article_to_proyecto(self, url: str, section: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
        titulo = self._page_h1(html)
        if not titulo or len(titulo) < 4:
            return None
        pdfs = self._extract_pdfs(html)
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": _fecha_from_context(html, pdfs),
            "tipo": _proyecto_tipo(titulo, section),
            "url": url,
            "source": "ayuntamiento",
            "seccion": section,
        }
        if pdfs:
            rec["pdf_url"] = pdfs[0]
        return rec

    def _collect_proyectos_from_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        fetched_children = 0
        for seed_url, section in self.project_seeds:
            try:
                html = self._fetch(seed_url)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            children = self._extract_child_urls(html)
            if children:
                for child in children:
                    if fetched_children >= self.max_articles:
                        break
                    rec = self._article_to_proyecto(child, section)
                    if rec:
                        rows.append(rec)
                    fetched_children += 1
            else:
                titulo = self._page_h1(html)
                if titulo:
                    pdfs = self._extract_pdfs(html)
                    rows.append(
                        {
                            "id": _stable_id("proy", seed_url),
                            "municipio": MUNICIPIO,
                            "titulo": titulo[:500],
                            "fecha": _fecha_from_context(html, pdfs),
                            "tipo": _proyecto_tipo(titulo, section),
                            "url": seed_url,
                            "source": "ayuntamiento",
                            "seccion": section,
                            **({"pdf_url": pdfs[0]} if pdfs else {}),
                        }
                    )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tramits_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row_m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
            row_html = row_m.group(1)
            m = RE_TRAMIT_FITXA.search(row_html)
            if not m:
                continue
            path = m.group(1)
            titulo = _strip_html(row_html)
            titulo = re.sub(r"\s*Informaci[oó]\s*(Tramitar)?\s*$", "", titulo, flags=re.I).strip()
            titulo = re.sub(r"^\d{1,2}\.\s*", "", titulo)
            if not titulo or not RE_LICENCIA.search(titulo):
                continue
            url = f"{self.seu_base}{path}"
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite sede Manresa; sin tablón histórico de concesiones",
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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
        rows = self._collect_licencia_tramites()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "urbanisme_tramits"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos_from_seeds()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "web_articles"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
