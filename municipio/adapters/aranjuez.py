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

BASE = "https://www.aranjuez.es"
TABLON_EDICTOS = f"{BASE}/tablon-de-edictos/"
MUNICIPIO = "Aranjuez"
ID_PREFIX = "aranjuez"

DEFAULT_URBANISMO_PAGES: list[str] = [
    f"{BASE}/concejalias/urbanismo/",
    f"{BASE}/concejalias/urbanismo/pgou1996/",
    f"{BASE}/concejalias/urbanismo/normativa-tecnica/",
    f"{BASE}/concejalias/urbanismo/sector-la-montana/",
    f"{BASE}/concejalias/urbanismo/sector-i-ciudad-de-las-artes/",
    f"{BASE}/concejalias/urbanismo/sector-puente-largo-avance/",
    f"{BASE}/concejalias/urbanismo/sector-xi-cerro-de-la-linterna/",
    f"{BASE}/concejalias/urbanismo/obras-de-acceso-norte/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|instalaci[oó]n para|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|"
    r"edicto.*licencia|obra vinculada)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|reparcel|sector|normas urban|"
    r"modificaci[oó]n|aprobaci[oó]n|ordenanza|estudio|memoria|planos|suelo|"
    r"edicto|instalaci[oó]n)",
)
RE_FECHA_PREFIX = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})\.\s*")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|files)/(?:urbanismo/)?(\d{4})[-/]?(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?aranjuez\.es)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_TABLON_ITEM = re.compile(
    r'<li>\s*<a href="([^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_PREFIX.match(text.strip()) or RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(Path(url).name) if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r"<title>([^<]+)",
        r"<h1[^>]*>([^<]+)",
        r'<meta property="og:title" content="([^"]+)"',
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _clean_tablon_title(raw: str) -> str:
    t = unescape(raw or "").strip()
    t = RE_FECHA_PREFIX.sub("", t).strip()
    return t[:500]


class AranjuezAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress: tablón de edictos + páginas urbanismo/PGOU/sectores."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_EDICTOS)
        self.urbanismo_pages = [str(u) for u in (self.config.get("urbanismo_pages") or DEFAULT_URBANISMO_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-aranjuez/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(BASE, href))

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        parts = re.split(r"<h3[^>]*>([^<]+)</h3>", html, flags=re.I)
        for i in range(1, len(parts), 2):
            section = unescape(parts[i].strip())
            block = parts[i + 1] if i + 1 < len(parts) else ""
            for m in RE_TABLON_ITEM.finditer(block):
                url = self._abs_url(m.group(1))
                raw_title = m.group(2).strip()
                title = _clean_tablon_title(raw_title)
                fecha = _parse_fecha_dmy(raw_title)
                rows.append(
                    {
                        "section": section,
                        "titulo": title,
                        "fecha": fecha,
                        "url": url,
                        "pdf_url": url if url.lower().endswith(".pdf") else None,
                    }
                )
        return rows

    def _collect_urbanismo_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.urbanismo_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = _page_title(html, page_url.rsplit("/", 2)[-2].replace("-", " "))
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                titulo = f"{page_title}: {name}" if page_title else name
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_url(pdf),
                        "url": page_url,
                        "pdf_url": pdf,
                        "origen": page_url,
                    }
                )
        return rows

    def _tablon_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{item['section']} {item['titulo']}"
        if item["section"].lower() != "urbanismo" and not RE_LICENCIA.search(blob):
            return None
        tipo = "licencia urbanística"
        if re.search(r"(?i)instalaci[oó]n", item["titulo"]):
            tipo = "licencia de actividad"
        rec: dict[str, Any] = {
            "id": _stable_id("lic", item["url"]),
            "fecha_concesion": item.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"],
            "url": item["url"],
            "source": "ayuntamiento",
            "seccion": item["section"],
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        return rec

    def _tablon_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{item['section']} {item['titulo']}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        tipo = "urbanismo"
        if re.search(r"(?i)instalaci[oó]n|licencia", blob):
            tipo = "información pública"
        elif re.search(r"(?i)edicto", blob):
            tipo = "edicto"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": tipo,
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
            "seccion": item["section"],
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        return rec

    def _pdf_to_proyecto(self, doc: dict[str, Any]) -> dict[str, Any]:
        titulo = doc["titulo"]
        blob = f"{titulo} {doc.get('pdf_url', '')}"
        tipo = "documento urbanismo"
        if re.search(r"(?i)pgou|plan general", blob):
            tipo = "PGOU"
        elif re.search(r"(?i)plan parcial|sector", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)ordenanza|normas urban", blob):
            tipo = "normativa urbanística"
        elif re.search(r"(?i)reparcel", blob):
            tipo = "reparcelación"
        return {
            "id": _stable_id("proy", doc["pdf_url"]),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": doc.get("fecha"),
            "tipo": tipo,
            "url": doc["url"],
            "pdf_url": doc["pdf_url"],
            "source": "ayuntamiento",
            "origen": doc.get("origen", "urbanismo"),
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
        rows: list[dict[str, Any]] = []
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon_edictos"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
            elif rec:
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        for doc in self._collect_urbanismo_pdfs():
            add(self._pdf_to_proyecto(doc))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "urbanismo_pdfs": sum(1 for r in rows if r.get("origen") != "tablon"),
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
