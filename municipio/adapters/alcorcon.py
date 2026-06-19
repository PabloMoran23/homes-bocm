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

BASE = "https://www.ayto-alcorcon.es"
SEDE = "https://portalciudadano.ayto-alcorcon.es"

CONCEJALIA_URB = (
    f"{BASE}/es/ayuntamiento/concejalias/"
    "concejalia-de-agenda-urbana-planificacion-desarrollo-y-mantenimiento"
)
TRANSP_ORDENACION = (
    f"{BASE}/es/transparencia/publicidad-activa/"
    "informacion-en-materia-de-ordenacion-del-territorio-y-obras-publicas"
)
TRANSP_NORMATIVA = (
    f"{BASE}/es/transparencia/publicidad-activa/"
    "informacion-en-materia-normativa-de-planificacion-y-programacion-y-de-servicios-y-procedimientos"
)
SEDE_ANUNCIOS = f"{SEDE}/portal/contenedor.do?det_cod=37&pes_cod=-2&ent_id=1&idioma=1"
SEDE_MAPA = f"{SEDE}/portal/mapaWeb.do?ent_id=1&opc_id=218&pes_cod=-2"
SEDE_URBANISMO = (
    f"{SEDE}/sede/catalogoTramites.do?opcion=detalle&idApl=4&ent_id=1&idioma=1"
)

DEFAULT_SEED_PAGES = [
    TRANSP_ORDENACION,
    TRANSP_NORMATIVA,
    CONCEJALIA_URB,
    SEDE_URBANISMO,
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|dyc-10[124]|dyc-20[1-6]|tramite.*obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"agrupaci[oó]n|viabilidad urban|ordenanza|instrucci[oó]n|normativa|"
    r"memoria|anexo|nnuu|retamar|parcelaci[oó]n|segregaci)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/sites/default/files/(\d{4})-(\d{2})/")
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.ayto-alcorcon\.es)?/sites/default/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_PARAGRAPH_BLOCK = re.compile(
    r'<div class="paragraph-text">(.*?)</div>\s*</div>\s*</div>',
    re.S | re.I,
)
RE_NODE_LINK = re.compile(
    r'href="((?:https://www\.ayto-alcorcon\.es)?/es/node/\d+)"',
    re.I,
)
RE_SEDE_TRAMITE = re.compile(
    r'title="([^"]+)"[^>]*href="(https://portalciudadano\.ayto-alcorcon\.es/sede/[^"]+)"',
    re.I,
)
RE_SEDE_TRAMITE_ALT = re.compile(
    r'href="(https://portalciudadano\.ayto-alcorcon\.es/sede/[^"]+)"[^>]*title="([^"]+)"',
    re.I,
)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"alcorcon-{prefix}-{h}"


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


def _iso_from_year(text: str) -> str | None:
    years = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", text) if 1980 <= int(y) <= 2030]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _clean_title(text: str) -> str:
    t = unescape(text or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:500]


def _page_title(html: str, fallback: str = "") -> str:
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


class AlcorconAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 10 (transparencia + concejalía DYC) + sede portalciudadano."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.sede_base = str(self.config.get("sede_base") or SEDE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alcorcon/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or BASE, href)

    def _extract_pdfs(self, html: str, base: str | None = None) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_url(m.group(1), base)
            if "favicon" in u.lower():
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def _collect_transparencia_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in (TRANSP_ORDENACION, TRANSP_NORMATIVA):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for pdf in self._extract_pdfs(html):
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                titulo = name
                tipo = "documento urbanismo"
                if "pgou" in name.lower() or "pgou" in pdf.lower():
                    tipo = "PGOU"
                elif "conv" in name.lower() and "urb" in name.lower():
                    tipo = "convenio urbanístico"
                elif "carta_servicios_urbanismo" in name.lower():
                    tipo = "carta de servicios"
                rows.append(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": "Alcorcón",
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_pdf_url(pdf) or _iso_from_year(name),
                        "tipo": tipo,
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": "transparencia",
                    }
                )
        return rows

    def _parse_concejalia_paragraphs(self) -> list[tuple[str, str]]:
        try:
            html = self._fetch(CONCEJALIA_URB)
        except urllib.error.URLError:
            return []
        items: list[tuple[str, str]] = []
        for block in RE_PARAGRAPH_BLOCK.findall(html):
            title_m = re.search(
                r'field-paragraph-long-text[^>]*>.*?<(?:h[234]|p)[^>]*>(.*?)</(?:h[234]|p)>',
                block,
                re.S | re.I,
            )
            title = _clean_title(re.sub(r"<[^>]+>", " ", title_m.group(1))) if title_m else ""
            link_m = re.search(
                r'paragraph-text-button[^>]*href="([^"]+)"',
                block,
                re.I,
            )
            if not link_m:
                continue
            url = self._abs_url(link_m.group(1))
            if title:
                items.append((title, url))
        return items

    def _collect_concejalia_nodes(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        lic_rows: list[dict[str, Any]] = []
        proy_rows: list[dict[str, Any]] = []
        seen_nodes: set[str] = set()

        for title, url in self._parse_concejalia_paragraphs():
            if "/es/node/" not in url:
                continue
            if url in seen_nodes:
                continue
            seen_nodes.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            page_title = _page_title(html, title)
            pdfs = self._extract_pdfs(html)
            fecha = _fecha_from_pdf_url(pdfs[0]) if pdfs else _parse_fecha_dmy(html) or _iso_from_year(page_title)

            base_rec = {
                "titulo": page_title[:500],
                "fecha_concesion": fecha,
                "tipo": "trámite licencia" if RE_LICENCIA.search(page_title) else "documento urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "url": url,
                "source": "ayuntamiento",
                "origen": "concejalia_urbana",
            }
            if pdfs:
                base_rec["pdf_url"] = pdfs[0]

            if RE_LICENCIA.search(page_title):
                lic_rows.append(
                    {
                        **base_rec,
                        "id": _stable_id("lic", url),
                        "nota": "Impreso/trámite informativo; no concesión publicada",
                    }
                )

            if RE_PROYECTO.search(page_title) or RE_LICENCIA.search(page_title):
                tipo = "licencia" if RE_LICENCIA.search(page_title) and not RE_PROYECTO.search(page_title) else "urbanismo"
                if "ordenanza" in page_title.lower():
                    tipo = "normativa"
                elif "instrucci" in page_title.lower():
                    tipo = "instrucción"
                elif "convenio" in page_title.lower():
                    tipo = "convenio"
                proy_rows.append(
                    {
                        "id": _stable_id("proy", url),
                        "municipio": "Alcorcón",
                        "titulo": page_title[:500],
                        "fecha": fecha,
                        "tipo": tipo,
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "concejalia_urbana",
                        **({"pdf_url": pdfs[0]} if pdfs else {}),
                    }
                )
        return lic_rows, proy_rows

    def _collect_sede_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in (SEDE_MAPA, SEDE_URBANISMO):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            pairs: list[tuple[str, str]] = []
            for m in RE_SEDE_TRAMITE.finditer(html):
                pairs.append((unescape(m.group(1).strip()), m.group(2)))
            for m in RE_SEDE_TRAMITE_ALT.finditer(html):
                pairs.append((unescape(m.group(2).strip()), m.group(1)))
            for title, href in pairs:
                if not RE_LICENCIA.search(title):
                    continue
                rows.append(
                    {
                        "id": _stable_id("lic", href),
                        "fecha_concesion": None,
                        "tipo": title[:120],
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title[:500],
                        "url": href,
                        "source": "ayuntamiento",
                        "origen": "sede_tramite",
                        "nota": "Trámite sede electrónica; no concesión publicada",
                    }
                )
        return rows

    def _collect_sede_anuncios(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(SEDE_ANUNCIOS)
        except urllib.error.URLError:
            return rows
        for m in re.finditer(r'<section><a href="([^"]+)">([^<]+)</a></section>', html, re.I):
            href, title = m.group(1), unescape(m.group(2).strip())
            blob = f"{title} {href}"
            if not (RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob)):
                continue
            fecha = _fecha_from_pdf_url(href) or _parse_fecha_dmy(title)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", href),
                "municipio": "Alcorcón",
                "titulo": title[:500],
                "fecha": fecha,
                "tipo": "anuncio sede",
                "url": SEDE_ANUNCIOS,
                "source": "ayuntamiento",
                "origen": "sede_anuncios",
            }
            if href.lower().endswith(".pdf"):
                rec["pdf_url"] = href
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

    def _merge_unique(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            by_id[row["id"]] = row
        return list(by_id.values())

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        lic_conc, _ = self._collect_concejalia_nodes()
        rows = self._merge_unique(lic_conc + self._collect_sede_tramites())
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "concejalia": len(lic_conc),
            "sede_tramites": len(rows) - len(lic_conc),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        lic_conc, _ = self._collect_concejalia_nodes()
        added = 0
        for rec in lic_conc + self._collect_sede_tramites():
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
        _, proy_conc = self._collect_concejalia_nodes()
        rows = self._merge_unique(
            self._collect_transparencia_pdfs() + proy_conc + self._collect_sede_anuncios()
        )
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "concejalia": sum(1 for r in rows if r.get("origen") == "concejalia_urbana"),
            "sede_anuncios": sum(1 for r in rows if r.get("origen") == "sede_anuncios"),
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
