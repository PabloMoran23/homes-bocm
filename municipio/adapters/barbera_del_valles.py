from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.bdv.cat"
SEU_E_PLANEJAMENT = (
    "https://seu-e.cat/es/web/barberadelvalles/govern-obert-i-transparencia/"
    "accio-de-govern-i-normativa/urbanisme/planejament-urbanistic"
)
RPUC_MUNICI = (
    "https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08252"
)
MUC_VISOR = "https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08252&set-locale=ca"
MUNICIPIO = "Barberà del Vallès"
ID_PREFIX = "barbera-del-valles"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/planeamiento-y-gestion-urbanistica",
    f"{WEB_BASE}/es/urbanismo-y-obras",
    f"{WEB_BASE}/es/proyectos-de-obras-locales",
    SEU_E_PLANEJAMENT,
    RPUC_MUNICI,
]

RE_PATH_PROY = re.compile(
    r"(?i)^/es/(?:proyecto-(?:de-|ejecutivo|para-la|basico)|plan-de-mejora|plan-especial|"
    r"modificacion-puntual|redaccion-y-aprobacion|planeamiento-y-gestion|proyectos-de-obras-locales)"
)
RE_PATH_SKIP = re.compile(
    r"(?i)(proyecto-educativo|proyecto-literario|proyecto-en-barbera-comemos|proyecto-defensores|"
    r"proyecto-de-actuaciones-curso|modernizacion-de-la-tecnologia|ampliacion-del-archivo|"
    r"adecuacion-del-local-municipal|construccion-de-la-tarima|renovacion-del-poigono|"
    r"jardin-visitable|comemos-bien|actuaciones-curso|proyecto-de-los-arreglos-de-diferentes-espacios|"
    r"proyecto-de-arreglo-de-los-terrenos|proyecto-para-la-adecuacion-y-mejora-de-un-acceso)"
)
RE_NEWS_URBAN = re.compile(
    r"(?i)(reurbaniz|reparcel|mejora-urbana|plan-de-mejora|plan-especial|modificacion.*pgom|"
    r"aprobacion-inicial-del-proyecto-de-reurbanizacion|proyecto-de-reurbanizacion|"
    r"proyecto-de-remodelacion|inicio-de-las-obras-de-reurbanizacion|"
    r"abierto-el-proceso-participativo.*reurbaniz|se-aprueba-inicialmente-el-proyecto-de-reurbanizacion|"
    r"se-aprueba-inicialmente-el-plan-especial|informacion-publica-el-mapa-estrategico-del-ruido|"
    r"aprobacion-inicial-del-proyecto-de-reurbanizacion-de-calles)"
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:major|menor)|parcelaci[oó]n|ocupaci[oó]n temporal|"
    r"grua-torre|vado|alcantarillado|primera ocupaci[oó]n|pr[oò]rroga d.?obres)"
)
RE_PROYECTO_BODY = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgom|pgou|mejora urbana|"
    r"informaci[oó]n p[uú]blica|reparcel|modificaci[oó]n|sector|reurbaniz|imavi|"
    r"interpolar|equipamiento|ordenaci[oó]n|rpuc|muc.visor|expedient)",
)
RE_TRAMIT_HREF = re.compile(r'href="(/es/tramits/[^"]+)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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


def _fecha_from_blob(text: str, lastmod: str | None = None) -> str | None:
    d = _parse_fecha_dmy(text)
    if d:
        return d
    if lastmod:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", lastmod)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1985 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = (title or "").lower()
    if "reparcel" in n:
        return "reparcelación"
    if "plan de mejora" in n or "pmu" in n or " área de desarrollo" in n:
        return "plan de mejora urbana"
    if "plan especial" in n or "peur" in n:
        return "plan especial"
    if "modificaci" in n and ("pgom" in n or "plan general" in n):
        return "modificación PGOM"
    if "reurbaniz" in n or "remodelaci" in n:
        return "reurbanización"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "urbanizaci" in n:
        return "urbanización"
    if "rpuc" in n or "planejament" in n:
        return "planeamiento"
    return "urbanismo"


class BarberaDelVallesAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal bdv.cat (planeamiento / sitemap) + seu-e (trámites) + referencias RPUC/MUC (Gencat)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_tramites_url = str(
            self.config.get("licencia_tramites_url") or f"{self.web_base}/es/tramites/urbanismo-y-obras"
        )

    def _fetch(self, url: str, *, timeout: int = 75) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-barbera-del-valles/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

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
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>([^<]+)',
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = _strip_html(m.group(1))
                t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
                if t and len(t) > 3:
                    return t[:500]
        return fallback[:500]

    def _sitemap_proyecto_urls(self) -> list[tuple[str, str | None]]:
        out: list[tuple[str, str | None]] = []
        try:
            xml = self._fetch(f"{self.web_base}/es/sitemap.xml", timeout=90)
        except urllib.error.URLError:
            return out
        root = ET.fromstring(xml)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for url_el in root.findall("sm:url", ns):
            loc = url_el.find("sm:loc", ns)
            if loc is None or not loc.text:
                continue
            full = loc.text.strip()
            if not full.startswith(self.web_base):
                continue
            path = full.replace(self.web_base, "")
            lastmod_el = url_el.find("sm:lastmod", ns)
            lastmod = lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else None
            if RE_PATH_SKIP.search(path):
                continue
            if RE_PATH_PROY.search(path):
                out.append((full, lastmod))
                continue
            if "/noticies/" in path and RE_NEWS_URBAN.search(path):
                out.append((full, lastmod))
        return out

    def _hub_links(self) -> list[str]:
        urls: list[str] = []
        for seed in self.seed_pages:
            if not seed.startswith(self.web_base):
                continue
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for m in re.finditer(r'href="(/es/[^"]+)"', html):
                path = m.group(1)
                if RE_PATH_SKIP.search(path):
                    continue
                if RE_PATH_PROY.search(path) or (
                    "/noticies/" in path and RE_NEWS_URBAN.search(path)
                ):
                    urls.append(self._abs_url(path))
        return list(dict.fromkeys(urls))

    def _build_proyecto(self, url: str, lastmod: str | None = None) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            slug = url.rstrip("/").split("/")[-1].replace("-", " ")
            titulo = slug[:500] if slug else url
            fecha = _fecha_from_blob("", lastmod)
            return {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": fecha,
                "tipo": _proyecto_tipo(titulo),
                "url": url,
                "source": "ayuntamiento",
                "origen": "bdv_sitemap",
            }

        titulo = self._page_title(html, fallback=url.split("/")[-1].replace("-", " "))
        blob = _strip_html(html)[:4000]
        if not RE_PROYECTO_BODY.search(f"{titulo} {blob}") and not RE_PATH_PROY.search(
            url.replace(self.web_base, "")
        ):
            return None

        pdfs = []
        for pm in RE_PDF.finditer(html):
            pdfs.append(self._abs_url(pm.group(1)))
        pdfs = list(dict.fromkeys(pdfs))[:8]

        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": _fecha_from_blob(f"{titulo} {blob}", lastmod),
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": "bdv_drupal",
        }
        if pdfs:
            rec["documentos"] = [{"url": u} for u in pdfs]
            rec["pdf_url"] = pdfs[0]
        return rec

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        catalog: dict[str, str | None] = {}
        for url, lastmod in self._sitemap_proyecto_urls():
            catalog[url] = lastmod
        for url in self._hub_links():
            catalog.setdefault(url, None)

        catalog.setdefault(SEU_E_PLANEJAMENT, None)
        catalog.setdefault(RPUC_MUNICI, None)

        for url, lastmod in sorted(catalog.items()):
            if url in seen:
                continue
            rec = self._build_proyecto(url, lastmod)
            if not rec:
                continue
            seen.add(url)
            rows.append(rec)

        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        try:
            html = self._fetch(self.licencia_tramites_url)
        except urllib.error.URLError:
            html = ""

        for m in RE_TRAMIT_HREF.finditer(html):
            path = m.group(1)
            if not RE_LICENCIA.search(path.replace("-", " ")):
                continue
            url = self._abs_url(path)
            try:
                page = self._fetch(url)
                titulo = self._page_title(page, fallback=path.split("/")[-1].replace("-", " "))
            except urllib.error.URLError:
                titulo = path.split("/")[-1].replace("-", " ")
            rec_id = _stable_id("lic", url)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite urbanismo (Drupal)",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Sin tablón público de licencias concedidas; ficha informativa del trámite",
                }
            )

        seu_tramits = [
            (
                "https://seu-e.cat/es/web/barberadelvalles/tramits-i-gestions/-/tramits/classificacio/urbanisme",
                "Tràmits d'urbanisme (seu-e.cat)",
            ),
            (
                "https://seu-e.cat/es/web/barberadelvalles/tramits-i-gestions/-/tramits/tramit/14209132",
                "Sol·licitud de llicència d'ocupació temporal de la via pública per obres",
            ),
            (
                "https://bdv.eadministracio.cat",
                "Sede electrònica eAdministració (presentación telemática)",
            ),
        ]
        for url, titulo in seu_tramits:
            rec_id = _stable_id("lic", url)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia / obra",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Canal de solicitud; no publica concesiones históricas",
                }
            )

        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_drupal_seu_e"}

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
            "with_geometry": 0,
            "status": "ok",
            "source": "bdv_sitemap_drupal_rpuc_ref",
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "with_geometry": stats.get("with_geometry", 0),
            "status": "ok",
        }
