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
from municipio.geometry import record_geometry

WEB_BASE = "https://llucmajor.org"
SEDE_BASE = "https://llucmajor.sedelectronica.es"
URBANISMO_URL = f"{WEB_BASE}/ca/urbanismecadastre-pic"
TRAMITS_URBANISME_URL = f"{WEB_BASE}/ca/tramits_areas/Urbanisme"
ENLLACOS_URBANISME_URL = f"{WEB_BASE}/ca/enlla%C3%A7os/enllacos-area-urbanisme"
VISOR_IDELMA = "https://ide.idelma.cat/ide_llucmajor"
VISOR_MUIB = "https://muib.caib.es/mapurbibfront/visor_index.jsp"
VISOR_ARXURB = "https://ide.conselldemallorca.cat/visor/arxurb/"
MUNICIPIO = "Llucmajor"
ID_PREFIX = "llucmajor"

DEFAULT_SEED_PAGES: tuple[str, ...] = (
    URBANISMO_URL,
    TRAMITS_URBANISME_URL,
    ENLLACOS_URBANISME_URL,
    f"{WEB_BASE}/ca/contenidors-urbanitzacions",
    f"{WEB_BASE}/ca/anuncis",
    f"{WEB_BASE}/ca/tramits",
)

TRAMIT_SLUGS_OBRES: tuple[str, ...] = (
    "04-llicencia-dobra-major",
    "07-procediment-de-prorroga-de-llicencia-dobres",
    "08-procediment-de-prorroga-de-comunicacio-previa",
    "10-llicencia-docupacio-o-primera-utilitzacio",
    "11-declaracio-dinteres-general",
    "12-certificats-urbanistics-municipals",
    "13-declaracio-responsable-obres-i-installacions-en-sol-urba-disposicio-addicional-primera",
    "14-ocupacio-de-publica-obres-io-installacions",
    "15-comunicacio-previa-dagrupacio-de-parcelles-o-solars",
    "16-installacions-de-transport-i-distribucio-denergia-electrica-en-baixa-mitjana-i-alta",
)

RE_LICENCIA = re.compile(
    r"(?i)(licen|llic[eè]ncia|obra|comunicaci|declaraci|certificat|ocupaci|"
    r"agrupaci[oó]|installaci[oó]|urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|plan (?:parcial|especial|general)|pgou|pla general|"
    r"informaci[oó] p[uú]blica|expedient|projecte|proyecto|modificaci[oó]n|"
    r"reparcel|sector|ordenan[cç]a|normativa|legalitz|epcu|catastr|visor|"
    r"arxurb|idelma|muib|document|acord)",
)
RE_NOISE = re.compile(
    r"(?i)(subvenci[oó]n|personal|empleo|convocat[oò]ria.*ple|"
    r"escoles de nadal|correfires|connecta local|oficina.*autonom)",
)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)
RE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_LLUC_HREF = re.compile(
    r'href="((?:https://llucmajor\.org)?/ca/[^"#?]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})/")
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
    m = RE_FECHA_YM.search(text or "")
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
    n = blob.lower()
    if "ordenan" in n or "ordenança" in n:
        return "ordenanza urbanística"
    if "legalitz" in n or "da7" in n:
        return "legalización urbanística"
    if "epcu" in n or "catastr" in n:
        return "catastro / EPCU"
    if "visor" in n or "idelma" in n or "muib" in n or "arxurb" in n:
        return "visor GIS"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "pgou" in n or "planej" in n:
        return "planeamiento"
    return "urbanismo"


def _licencia_tipo(blob: str) -> str:
    n = blob.lower()
    if "comunicaci" in n and "previa" in n:
        return "comunicación previa"
    if "declaraci" in n and "responsable" in n:
        return "declaración responsable"
    if "certificat" in n:
        return "certificado urbanístico"
    if "ocupaci" in n:
        return "ocupación vía pública"
    if "primera utilitzaci" in n or "primera ocupaci" in n:
        return "licencia primera ocupación"
    return "licencia de obra"


class LlucmajorAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal llucmajor.org + sede espublico (tablón no operativo) + IDELMA IDE (sin capa expedientes)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = tuple(self.config.get("seed_pages") or DEFAULT_SEED_PAGES)
        self.max_crawl_pages = int(self.config.get("max_crawl_pages") or 40)

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-llucmajor/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        if href.startswith("http"):
            return href.split("#")[0]
        return urllib.parse.urljoin(self.web_base + "/", href).split("#")[0]

    def _page_title(self, html: str, fallback: str = "") -> str:
        m = RE_H1.search(html)
        if m:
            return _strip_html(m.group(1))
        m = RE_TITLE.search(html)
        if m:
            t = _strip_html(m.group(1))
            if "|" in t:
                t = t.split("|", 1)[0].strip()
            return t
        return fallback

    def _extract_pdfs(self, html: str) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for m in RE_PDF.finditer(html):
            url = self._abs_url(urllib.parse.unquote(m.group(1)))
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def _fetch_geometry(self, _rec: dict[str, Any]) -> None:
        """IDELMA M027 no publica capa exp_absis; geometría por expediente no disponible."""

    def _collect_proyecto_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", URBANISMO_URL),
                "municipio": MUNICIPIO,
                "titulo": "Urbanisme i cadastre parcelari (PIC) — Ajuntament de Llucmajor",
                "fecha": None,
                "tipo": "urbanismo",
                "url": URBANISMO_URL,
                "source": "ayuntamiento",
                "origen": "web_drupal",
            },
            {
                "id": _stable_id("proy", VISOR_IDELMA),
                "municipio": MUNICIPIO,
                "titulo": "IDE municipal Llucmajor (IDELMA)",
                "fecha": None,
                "tipo": "visor GIS",
                "url": VISOR_IDELMA,
                "source": "ayuntamiento",
                "origen": "visor",
                "nota": "Sin WFS M027_URBANISME / exp_absis",
            },
            {
                "id": _stable_id("proy", VISOR_MUIB),
                "municipio": MUNICIPIO,
                "titulo": "Visor planeamiento MUIB (Govern Illes Balears)",
                "fecha": None,
                "tipo": "visor GIS",
                "url": f"{VISOR_MUIB}?municipi=Llucmajor",
                "source": "ayuntamiento",
                "origen": "visor",
            },
            {
                "id": _stable_id("proy", VISOR_ARXURB),
                "municipio": MUNICIPIO,
                "titulo": "Arxiu urbanístic — Consell de Mallorca",
                "fecha": None,
                "tipo": "visor documental",
                "url": VISOR_ARXURB,
                "source": "ayuntamiento",
                "origen": "visor",
            },
        ]

    def _collect_tramit_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for slug in TRAMIT_SLUGS_OBRES:
            url = f"{self.web_base}/ca/tramits/{slug}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = self._page_title(html, slug.replace("-", " "))
            blob = f"{title} {slug}"
            if not RE_LICENCIA.search(blob):
                continue
            pdfs = self._extract_pdfs(html)
            rec: dict[str, Any] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": _licencia_tipo(blob),
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": url,
                "source": "ayuntamiento",
                "nota": "Trámite informativo Drupal; no concesión publicada",
                "origen": "web_tramit",
            }
            if pdfs:
                rec["pdf_url"] = pdfs[0]
            rows.append(rec)
        return rows

    def _crawl_web_proyectos(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue: list[str] = list(self.seed_pages)
        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        while queue and len(visited) < self.max_crawl_pages:
            url = queue.pop(0).rstrip("/")
            if url in visited:
                continue
            if not url.startswith(self.web_base):
                continue
            visited.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue

            title = self._page_title(html, url.rsplit("/", 1)[-1])
            blob = f"{title} {url} {_strip_html(html)[:800]}"
            if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
                pass
            else:
                if RE_PROYECTO.search(blob) and not RE_NOISE.search(title):
                    rec_id = _stable_id("proy", url)
                    if rec_id not in seen_ids:
                        seen_ids.add(rec_id)
                        rows.append(
                            {
                                "id": rec_id,
                                "municipio": MUNICIPIO,
                                "titulo": title[:500],
                                "fecha": _fecha_from_blob(blob),
                                "tipo": _proyecto_tipo(blob),
                                "url": url,
                                "source": "ayuntamiento",
                                "origen": "web_crawl",
                            }
                        )

                for pdf in self._extract_pdfs(html):
                    pdf_blob = f"{title} {pdf}"
                    if not RE_PROYECTO.search(pdf_blob):
                        continue
                    rec_id = _stable_id("proy", pdf)
                    if rec_id in seen_ids:
                        continue
                    seen_ids.add(rec_id)
                    rows.append(
                        {
                            "id": rec_id,
                            "municipio": MUNICIPIO,
                            "titulo": (f"{title}: {Path(pdf).name}" if title else Path(pdf).name)[:500],
                            "fecha": _fecha_from_blob(pdf_blob),
                            "tipo": _proyecto_tipo(pdf_blob),
                            "url": url,
                            "pdf_url": pdf,
                            "source": "ayuntamiento",
                            "origen": "web_pdf",
                        }
                    )

            if len(visited) < self.max_crawl_pages:
                for m in RE_LLUC_HREF.finditer(html):
                    link = self._abs_url(m.group(1)).rstrip("/")
                    if link in visited or link in queue:
                        continue
                    if any(
                        skip in link
                        for skip in (
                            "/user/",
                            "/search",
                            "/form/",
                            "/avis-legal",
                            "/politica-de-cookies",
                            "/proteccio-de-dades",
                            "/benvinguda",
                            "/descobreix-llucmajor",
                            "/cultura/",
                            "/comerc",
                            "/activitats",
                        )
                    ):
                        continue
                    if (
                        "/tramits/" in link
                        or "/urbanism" in link
                        or "/enlla" in link
                        or "/anuncis" in link
                        or "/contenidors-urbanitzacions" in link
                        or "/noticies/" in link and RE_PROYECTO.search(link)
                    ):
                        queue.append(link)

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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_tramit_licencias():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": len(rows),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats["rows"]
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                self._fetch_geometry(rec)
                rows.append(rec)

        for rec in self._collect_proyecto_seeds():
            add(rec)
        for rec in self._crawl_web_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
