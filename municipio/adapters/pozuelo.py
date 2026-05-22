from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.pozuelodealarcon.org"

EXPEDIENTES_IP = (
    f"{BASE}/urbanismo-y-obras/expedientes-urbanisticos-en-informacion-publica"
)

DEFAULT_SEED_PAGES: list[str] = [
    EXPEDIENTES_IP,
    f"{BASE}/urbanismo-y-obras/plan-general-de-ordenacion-urbana/convenios-pgou",
    f"{BASE}/urbanismo-y-obras/plan-general-de-ordenacion-urbana/planos-pgou",
    f"{BASE}/urbanismo-y-obras/plan-general-de-ordenacion-urbana",
    f"{BASE}/urbanismo-y-obras/planeamiento-de-desarrollo",
    f"{BASE}/urbanismo-y-obras/planeamiento-de-desarrollo/planes-especiales",
    f"{BASE}/urbanismo-y-obras/obras/licencias",
    f"{BASE}/portal-de-transparencia/urbanismo-obras-publicas-y-medioambiente",
    (
        f"{BASE}/tu-ayuntamiento/portal-de-transparencia/"
        "urbanismo-obras-publicas-y-medioambiente/ordenacion-del-territorio-y-urbanismo"
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental)|memoria|planos|palacio|hotel|obra)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/sites/default/files/(\d{4})-(\d{2})/")
RE_EXP_DOC_TAIL = re.compile(
    r"-(?:memoria|planos(?:-\d+)?|anexo(?:-[^/]+)?|estudio(?:-[^/]+)?|"
    r"expediente(?:-[^/]+)?|certificado(?:-[^/]+)?|indice(?:-[^/]+)?|"
    r"mediciones(?:-[^/]+)?|documentacion(?:-[^/]+)?|archivos(?:-[^/]+)?)$",
    re.I,
)
RE_EXPEDIENTE_LINK = re.compile(
    r'href="((?:https://www\.pozuelodealarcon\.org)?'
    r"/urbanismo-y-obras/expedientes-urbanisticos-en-informacion-publica/[^\"#?]+)\"",
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.pozuelodealarcon\.org)?/sites/default/files/[^"]+\.pdf)"',
    re.I,
)
RE_URBAN_LINK = re.compile(
    r'href="((?:https://www\.pozuelodealarcon\.org)?/(?:urbanismo|portal-de-transparencia)[^\"#?]+)"',
    re.I,
)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"pozuelo-{prefix}-{h}"


def _slug_to_title(slug: str) -> str:
    t = slug.replace("-", " ").strip()
    return t[:1].upper() + t[1:] if t else slug


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _expediente_project_slug(page_slug: str) -> str:
    s = page_slug.strip("/")
    if "-proyecto-basico" in s:
        return s.split("-proyecto-basico", 1)[0] + "-proyecto-basico"
    while True:
        m = RE_EXP_DOC_TAIL.search(s)
        if not m:
            break
        s = s[: m.start()]
    return s or page_slug


class PozueloAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal: expedientes en información pública + páginas PGOU/planeamiento."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.25))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 80))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pozuelo/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(BASE, href)

    def _extract_pdfs(self, html: str) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_url(m.group(1))
            if "nogestionados" in u or "favicon" in u.lower():
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>([^<]+)',
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = unescape(m.group(1).strip())
                t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
                if t and len(t) > 3:
                    return t[:500]
        return fallback

    def _collect_expedientes_ip(self) -> list[dict[str, Any]]:
        try:
            index_html = self._fetch(EXPEDIENTES_IP)
        except urllib.error.URLError:
            return []

        child_urls: list[str] = []
        for m in RE_EXPEDIENTE_LINK.finditer(index_html):
            u = self._abs_url(m.group(1)).rstrip("/")
            if u.rstrip("/") != EXPEDIENTES_IP.rstrip("/"):
                child_urls.append(u)
        child_urls = sorted(set(child_urls))

        by_project: dict[str, dict[str, Any]] = {}
        for url in child_urls:
            page_slug = url.replace(EXPEDIENTES_IP + "/", "").split("/")[0]
            proj_slug = _expediente_project_slug(page_slug)
            if len(proj_slug) < 40:
                continue
            bucket = by_project.setdefault(
                proj_slug,
                {
                    "pages": [],
                    "pdfs": [],
                    "titles": [],
                },
            )
            bucket["pages"].append(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = self._page_title(html, _slug_to_title(page_slug))
            if title:
                bucket["titles"].append(title)
            for pdf in self._extract_pdfs(html):
                if pdf not in bucket["pdfs"]:
                    bucket["pdfs"].append(pdf)

        rows: list[dict[str, Any]] = []
        for proj_slug, data in by_project.items():
            titulo = _slug_to_title(proj_slug)
            if data["titles"]:
                # Prefer shortest distinctive title containing project keywords
                candidates = sorted(data["titles"], key=len)
                for c in candidates:
                    if len(c) > 20 and not c.lower().startswith("planos"):
                        titulo = c
                        break

            fechas = [_fecha_from_pdf_url(p) for p in data["pdfs"]]
            fechas = [f for f in fechas if f]
            fecha = max(fechas) if fechas else None
            landing = data["pages"][0] if data["pages"] else EXPEDIENTES_IP

            rec: dict[str, Any] = {
                "id": _stable_id("proy", proj_slug),
                "municipio": "Pozuelo de Alarcón",
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": "información pública",
                "url": landing,
                "source": "ayuntamiento",
                "origen": "expedientes_ip",
                "slug": proj_slug,
            }
            if data["pdfs"]:
                rec["pdf_url"] = data["pdfs"][0]
                if len(data["pdfs"]) > 1:
                    rec["pdf_urls"] = data["pdfs"][:50]
            rows.append(rec)
        return rows

    def _crawl_seed_documents(self) -> list[dict[str, Any]]:
        """Páginas semilla y un nivel de enlaces urbanismo con PDF o texto relevante."""
        visited: set[str] = set()
        queue: list[str] = list(self.seed_pages)
        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        while queue and len(visited) < self.max_crawl_pages:
            url = queue.pop(0).rstrip("/")
            if url in visited:
                continue
            visited.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue

            if EXPEDIENTES_IP.rstrip("/") in url:
                continue

            title = self._page_title(html, _slug_to_title(url.rsplit("/", 1)[-1]))
            pdfs = self._extract_pdfs(html)
            blob = f"{title} {url}"

            if pdfs and (RE_PROYECTO.search(blob) or "pgou" in url.lower() or "convenio" in url.lower()):
                for pdf in pdfs:
                    pdf_title = f"{title}: {Path(pdf).name}" if title else Path(pdf).name
                    rec_id = _stable_id("proy", pdf)
                    if rec_id in seen_ids:
                        continue
                    seen_ids.add(rec_id)
                    rows.append(
                        {
                            "id": rec_id,
                            "municipio": "Pozuelo de Alarcón",
                            "titulo": pdf_title[:500],
                            "fecha": _fecha_from_pdf_url(pdf) or _parse_fecha_dmy(html),
                            "tipo": "convenio" if "convenio" in blob.lower() else "documento urbanismo",
                            "url": url,
                            "pdf_url": pdf,
                            "source": "ayuntamiento",
                            "origen": url,
                        }
                    )
            if len(visited) < self.max_crawl_pages:
                for m in RE_URBAN_LINK.finditer(html):
                    link = self._abs_url(m.group(1)).rstrip("/")
                    if link in visited or link in queue:
                        continue
                    if any(
                        x in link
                        for x in (
                            "licencias-de-actividad",
                            "licencias-de-obra",
                            "tramites-frecuentes",
                            "/tu-ayuntamiento/organizacion",
                            "normativa-urbanistica/ordenanza",
                        )
                    ):
                        continue
                    if "/urbanismo" in link or (
                        "/portal-de-transparencia/" in link and "urbanismo" in link
                    ):
                        queue.append(link)

        return rows

    def _collect_licencias_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        lic_root = f"{BASE}/urbanismo-y-obras/obras/licencias"
        try:
            html = self._fetch(lic_root)
        except urllib.error.URLError:
            return rows

        urls = {lic_root}
        for m in re.finditer(
            r'href="((?:https://www\.pozuelodealarcon\.org)?/urbanismo-y-obras/obras/licencias/[^"]+)"',
            html,
            re.I,
        ):
            urls.add(self._abs_url(m.group(1)).rstrip("/"))

        for url in sorted(urls):
            try:
                page = self._fetch(url) if url != lic_root else html
            except urllib.error.URLError:
                continue
            title = self._page_title(page, _slug_to_title(url.rsplit("/", 1)[-1]))
            if not RE_LICENCIA.search(title):
                continue
            pdfs = self._extract_pdfs(page)
            rec: dict[str, Any] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": url,
                "source": "ayuntamiento",
                "nota": "Página informativa de trámites; no concesión publicada en tablón",
            }
            if pdfs:
                rec["pdf_url"] = pdfs[0]
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
        rows = self._collect_licencias_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "obras_licencias_info"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_pages():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
            else:
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

        for rec in self._collect_expedientes_ip():
            add(rec)
        for rec in self._crawl_seed_documents():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "expedientes_ip": sum(1 for r in rows if r.get("origen") == "expedientes_ip"),
            "seed_crawl": sum(1 for r in rows if r.get("origen") != "expedientes_ip"),
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
