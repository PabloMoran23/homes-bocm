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
from urllib.parse import urljoin, unquote

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.ayto-pinto.es"
GOBIERNO = "https://gobiernoabierto.ayto-pinto.es"
MUNICIPIO = "Pinto"
ID_PREFIX = "pinto"

DL_BASE = (
    f"{GOBIERNO}/planeamiento-urbanistico/-/document_library/kjPbdvcB2YEh/view"
)

ROOT_FOLDERS: dict[int, str] = {
    1649655: "PGOU texto",
    1650583: "PGOU planos",
    1650587: "Desarrollos urbanísticos",
    1650591: "Modificaciones PGOU",
    1650595: "Planes Especiales",
    1650599: "Estudios de detalle",
    1650603: "Convenios Urbanísticos",
    1650607: "Planeamiento",
}

DEFAULT_SEED_PAGES: list[str] = [
    f"{GOBIERNO}/planes-programas",
    (
        f"{BASE}/impresos-y-solicitudes/-/asset_publisher/QAJT1uxGBlsu/"
        "content/id/368979"
    ),
    f"{BASE}/licencias-y-disciplina-urbanistica",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|parcelaci[oó]n|obra (?:mayor|menor|r[aá]pida))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|estudio de detalle|modificaci[oó]n|"
    r"reparcel|memoria|planos|certificado|aprobaci[oó]n|normas urban|cat[aá]logo|"
    r"entidad urban|unidad de ejecuci|mejora urbana|desarrollo)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DOC_LINK = re.compile(
    r'href="((?:https?://(?:www\.)?ayto-pinto\.es|'
    r"https://gobiernoabierto\.ayto-pinto\.es)?/documents/[^\"?]+"
    r'(?:\?download=true)?)"',
    re.I,
)
RE_DOC_TITLE = re.compile(
    r'data-title="([^"]+)"[^>]*>.*?'
    r'href="(/documents/(?:1618300|34817)/[^"?]+(?:\?download=true)?)"',
    re.S | re.I,
)
RE_DOC_TITLE_REV = re.compile(
    r'href="(/documents/(?:1618300|34817)/[^"?]+(?:\?download=true)?)"[^>]*'
    r'data-title="([^"]+)"',
    re.S | re.I,
)
RE_TEXT_BEFORE_DOC = re.compile(
    r"([^<]{5,200})\s*<a[^>]+href=\"(/documents/[^\"]+)\"",
    re.I,
)
RE_PDF_LINK = re.compile(
    r"([^<]{10,200})\s*\(\s*pdf[^)]*\)\s*<a[^>]+href=\"(/documents/[^\"]+)\"",
    re.I,
)
RE_DOCUMENT_ENTRY = re.compile(
    r'class="document-entry"[^>]*>(.*?)</li>',
    re.S | re.I,
)
RE_FOLDER_VIEW = re.compile(r"/view/(\d+)")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            pass
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            pass
    return None


def _iso_from_year(text: str) -> str | None:
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2030
    ]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _tipo_from_folder(folder: str, title: str) -> str:
    blob = f"{folder} {title}".lower()
    if "convenio" in blob:
        return "convenio urbanístico"
    if "estudio de detalle" in blob or "estudio detalle" in blob:
        return "estudio de detalle"
    if "plan especial" in blob or "p.e." in blob or "pemu" in blob:
        return "plan especial"
    if "plan parcial" in blob or "p. parcial" in blob or "p.parcial" in blob:
        return "plan parcial"
    if "modificaci" in blob:
        return "modificación PGOU"
    if "pgou" in blob:
        return "PGOU"
    if "desarrollo" in blob:
        return "desarrollo urbanístico"
    return "documento urbanismo"


class PintoAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay: biblioteca documental planeamiento (gobierno abierto) + impresos urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.gobierno_base = str(self.config.get("gobierno_base") or GOBIERNO).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.root_folders = dict(
            self.config.get("root_folders") or ROOT_FOLDERS
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pinto/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str = BASE) -> str:
        return urljoin(base, href)

    def _is_favicon(self, url: str) -> bool:
        return "158209dd-1329-9b54-d5ac-8ffa1d54df00" in url

    def _extract_dl_docs(self, html: str) -> list[tuple[str, str]]:
        docs: list[tuple[str, str]] = []
        for pat in (RE_DOC_TITLE, RE_DOC_TITLE_REV):
            for m in pat.finditer(html):
                if pat is RE_DOC_TITLE:
                    title, href = m.group(1), m.group(2)
                else:
                    href, title = m.group(1), m.group(2)
                title = unescape(title.strip())
                link = self._abs_url(href, self.gobierno_base)
                if self._is_favicon(link):
                    continue
                docs.append((title, link))
        return docs

    def _crawl_document_library(self) -> list[dict[str, Any]]:
        visited: set[int] = set()
        queue: list[tuple[int, str]] = [
            (fid, folder) for fid, folder in self.root_folders.items()
        ]
        rows: list[dict[str, Any]] = []
        seen_links: set[str] = set()

        while queue:
            fid, folder = queue.pop(0)
            if fid in visited:
                continue
            visited.add(fid)
            url = f"{DL_BASE}/{fid}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue

            for title, link in self._extract_dl_docs(html):
                key = link.split("?")[0]
                if key in seen_links:
                    continue
                seen_links.add(key)
                fecha = _parse_fecha_dmy(title) or _iso_from_year(title)
                rows.append(
                    {
                        "id": _stable_id("proy", link),
                        "municipio": MUNICIPIO,
                        "titulo": title[:500],
                        "fecha": fecha,
                        "tipo": _tipo_from_folder(folder, title),
                        "url": url,
                        "pdf_url": link,
                        "source": "ayuntamiento",
                        "origen": f"dl:{folder}",
                    }
                )

            for m in RE_FOLDER_VIEW.finditer(html):
                sid = int(m.group(1))
                if sid not in visited and sid not in {x[0] for x in queue}:
                    queue.append((sid, folder))

        return rows

    def _extract_page_docs(self, html: str, page_url: str) -> list[tuple[str, str, str]]:
        out: list[tuple[str, str, str]] = []
        seen: set[str] = set()

        def add(title: str, href: str) -> None:
            link = self._abs_url(href, page_url)
            key = link.split("?")[0]
            if self._is_favicon(link) or key in seen:
                return
            seen.add(key)
            out.append((title[:500], link, page_url))

        for m in RE_PDF_LINK.finditer(html):
            add(unescape(re.sub(r"\s+", " ", m.group(1)).strip()), m.group(2))

        for m in RE_DOCUMENT_ENTRY.finditer(html):
            block = m.group(1)
            link_m = re.search(r'href="(/documents/[^"]+)"', block)
            if not link_m:
                continue
            text = unescape(re.sub(r"<[^>]+>", " ", block))
            text = re.sub(r"\s+", " ", text).strip()
            text = re.sub(r"\s*\(\s*pdf[^)]*\)\s*$", "", text, flags=re.I).strip()
            if text and not text.startswith("li class"):
                add(text, link_m.group(1))

        for m in RE_TEXT_BEFORE_DOC.finditer(html):
            title = unescape(re.sub(r"\s+", " ", m.group(1)).strip())
            if title.startswith("li class"):
                continue
            add(title, m.group(2))

        for m in RE_DOC_LINK.finditer(html):
            link = self._abs_url(m.group(1), page_url)
            key = link.split("?")[0]
            if self._is_favicon(link) or key in seen:
                continue
            name = unquote(Path(link.split("?")[0]).name.replace("+", " "))
            add(name[:500], m.group(1))
        return out

    def _collect_seed_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for title, link, src in self._extract_page_docs(html, page_url):
                blob = f"{title} {link}"
                if not RE_PROYECTO.search(blob):
                    continue
                key = link.split("?")[0]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "id": _stable_id("proy", link),
                        "municipio": MUNICIPIO,
                        "titulo": title[:500],
                        "fecha": _parse_fecha_dmy(title) or _iso_from_year(title),
                        "tipo": "plan urbano" if "plan" in title.lower() else "documento urbanismo",
                        "url": src,
                        "pdf_url": link,
                        "source": "ayuntamiento",
                        "origen": src,
                    }
                )
        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        lic_pages = [
            f"{BASE}/licencias-y-disciplina-urbanistica",
            (
                f"{BASE}/impresos-y-solicitudes/-/asset_publisher/QAJT1uxGBlsu/"
                "content/id/368979"
            ),
        ]
        seen: set[str] = set()
        for page_url in lic_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for title, link, src in self._extract_page_docs(html, page_url):
                blob = f"{title} {link}"
                if not RE_LICENCIA.search(blob):
                    continue
                key = link.split("?")[0]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "id": _stable_id("lic", link),
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title[:500],
                        "url": src,
                        "pdf_url": link,
                        "source": "ayuntamiento",
                        "nota": "Modelo/formulario de trámite; no concesión publicada",
                    }
                )
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
        return {"rows": len(rows), "status": "ok", "source": "impresos_licencias"}

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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._crawl_document_library():
            add(rec)
        for rec in self._collect_seed_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "document_library": sum(1 for r in rows if str(r.get("origen", "")).startswith("dl:")),
            "seed_pages": sum(1 for r in rows if not str(r.get("origen", "")).startswith("dl:")),
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
