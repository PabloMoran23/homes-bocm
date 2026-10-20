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
from municipio.geometry import geometry_centroid, record_geometry

BASE = "https://www.reus.cat"
SEU = "https://seu.reus.cat"
GEO_SEARCH = (
    "https://geoportal.reus.cat/apps/giscube-admin/plugins/mapiareus_search/search/"
)
ID_PREFIX = "reus"
MUNICIPIO = "Reus"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/serveis/planejament-urbanistic",
    f"{BASE}/serveis-tecnics-darquitectura-i-urbanisme-0",
    f"{BASE}/ajuntament/registre-de-planejament-urbanistic-de-catalunya",
    f"{BASE}/serveis/tramits-i-llicencies",
    "https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/267316",
]

SEU_URBANISME_LISTS: list[tuple[int, str]] = [
    (1981, "Planejament — documents vigents PGOU"),
    (1982, "Planejament — informació pública"),
    (1983, "Planejament — aprovacions"),
    (1986, "Planejament — plans parcials i especials"),
    (1987, "Planejament — modificacions puntuals"),
]

SEU_TRAMIT_LINKS: list[tuple[str, str]] = [
    (
        f"{SEU}/seu/carpetaCiutadana/perTemes/1474?root=1426",
        "Tràmits d'Arquitectura i Urbanisme",
    ),
    (
        f"{SEU}/seu/carpetaCiutadana/tramit/6654?lang=es",
        "Sol·licitud tramitació planejament urbanístic",
    ),
    (f"{SEU}/seu/carpetaCiutadana/perTemes", "Catàleg de tràmits (sede)"),
]

RE_SITEMAP_PROY = re.compile(
    r"(?i)(modificaci[oó].*urban|transformaci[oó].*urban|reurbanitz|"
    r"planejament-urban|tramitaci[oó].*urban|exposici[oó].*p[uú]blica|"
    r"poligon-industrial|ptoteccio-zones-no-urbanitzables|horts-urbans)",
)
RE_NOISE = re.compile(
    r"(?i)(guardia.?urbana|pellicul|cinema|tecnoparc|subvenc|menjador|"
    r"mercat-del-carrilet|gaudi|fets-urbans-guia)",
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|obra[s]?|comunicaci[oó]n previa|"
    r"declaraci[oó] responsable|primera ocupaci[oó])",
)
RE_PROYECTO_BODY = re.compile(
    r"(?i)(urban|planej|pgou|modificaci[oó]|reurban|transformaci[oó]|"
    r"pol[ií]gon|equipament|expropi|informaci[oó] p[uú]blica|sector|"
    r"patrimoni.*urban|arquitectura)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_PARCEL = re.compile(r"\b(\d{5,7}CF\d{4}[A-Z]?)\b", re.I)
RE_REFPLA = re.compile(r"\b(CF\d{4}[A-Z]?)\b", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _parse_fecha(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            pass
    m = RE_FECHA_ISO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            pass
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n:
        return "modificación urbanística"
    if "transformaci" in n and "urban" in n:
        return "transformación urbanística"
    if "reurbanitz" in n or "reurbaniz" in n:
        return "reurbanización"
    if "informaci" in n and ("public" in n or "pública" in n or "pública" in n):
        return "información pública"
    if "pgou" in n or "pla general" in n:
        return "plan general"
    if "poligon" in n:
        return "polígono industrial / sector"
    if "hort" in n and "urban" in n:
        return "horts urbans"
    return "planeamiento"


class ReusAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal reus.cat + sede seu.reus.cat (urbanisme) + geoportal Mapia (parcelas)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_sitemap_pages = int(self.config.get("max_sitemap_pages", 60))
        self.seu_timeout_s = int(self.config.get("seu_timeout_s", 18))
        self._sitemap_cache: list[tuple[str, str | None]] | None = None
        self._parcel_geom_cache: dict[str, dict[str, Any]] = {}

    def _fetch(
        self, url: str, *, timeout: int = 60, retries: int = 2
    ) -> str | None:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-reus/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
                last_err = exc
                time.sleep(0.4 * (attempt + 1))
        if last_err:
            return None
        return None

    def _abs(self, href: str) -> str:
        return urllib.parse.urljoin(f"{BASE}/", href)

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<meta property="og:title" content="([^"]+)"',
            r"<h1[^>]*class=\"[^\"]*page-title[^\"]*\"[^>]*>([^<]+)",
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = _clean(m.group(1))
                t = re.sub(r"\s*\|\s*Ajuntament de Reus\s*$", "", t, flags=re.I)
                if t:
                    return t
        return fallback

    def _page_fecha(self, html: str) -> str | None:
        for pat in (
            r'class="date-display-single"[^>]*>([^<]+)',
            r'property="article:published_time" content="([^"]+)"',
            r'field-convocatoria-fecha-inicio[^>]*>.*?date-display-single[^>]*>([^<]+)',
        ):
            m = re.search(pat, html, re.I | re.S)
            if m:
                f = _parse_fecha(m.group(1))
                if f:
                    return f
        return _parse_fecha(html)

    def _page_body_text(self, html: str) -> str:
        chunk = html
        m = re.search(
            r'field-name-body[^>]*>.*?field-item[^>]*>(.*?)</div>',
            html,
            re.I | re.S,
        )
        if m:
            chunk = m.group(1)
        return _clean(re.sub(r"<[^>]+>", " ", chunk))

    def _sitemap_urls(self) -> list[tuple[str, str | None]]:
        if self._sitemap_cache is not None:
            return self._sitemap_cache
        out: list[tuple[str, str | None]] = []
        for page in (1, 2):
            xml = self._fetch(f"{BASE}/sitemap.xml?page={page}", timeout=45)
            if not xml:
                continue
            try:
                root = ET.fromstring(xml)
            except ET.ParseError:
                continue
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for url_el in root.findall(".//sm:url", ns) or root.findall(".//url"):
                loc = url_el.findtext("sm:loc", default=None, namespaces=ns) or url_el.findtext(
                    "loc"
                )
                if not loc:
                    continue
                lastmod = url_el.findtext("sm:lastmod", default=None, namespaces=ns) or url_el.findtext(
                    "lastmod"
                )
                out.append((loc, lastmod))
        self._sitemap_cache = out
        return out

    def _discover_proyecto_urls(self) -> list[str]:
        urls: list[str] = []
        for loc, _ in self._sitemap_urls():
            if RE_NOISE.search(loc):
                continue
            if "/convocatoria/" in loc or "/noticia/" in loc:
                if RE_SITEMAP_PROY.search(loc):
                    urls.append(loc)
        return list(dict.fromkeys(urls))[: self.max_sitemap_pages]

    def _fetch_parcel_geometry(self, ref: str) -> tuple[dict[str, Any] | None, str | None]:
        key = ref.upper()
        if key in self._parcel_geom_cache:
            cached = self._parcel_geom_cache[key]
            return cached.get("geom"), cached.get("url")
        q = urllib.parse.quote(key)
        url = f"{GEO_SEARCH}?q={q}&e=parcella"
        raw = self._fetch(url, timeout=30, retries=1)
        geom: dict[str, Any] | None = None
        if raw:
            try:
                data = json.loads(raw)
                items = (data.get("resultat") or {}).get("parcella") or []
                if items and isinstance(items[0], dict):
                    geom = items[0].get("geom")
            except json.JSONDecodeError:
                pass
        self._parcel_geom_cache[key] = {"geom": geom, "url": url if geom else None}
        return geom, url if geom else None

    def _attach_geometry(self, rec: dict[str, Any], blob: str) -> None:
        refs: list[str] = []
        for m in RE_PARCEL.finditer(blob):
            refs.append(m.group(1).upper())
        if not refs:
            for m in RE_REFPLA.finditer(blob):
                refs.append(m.group(1).upper())
        for ref in refs:
            geom, gurl = self._fetch_parcel_geometry(ref)
            if not geom:
                continue
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_geojson"
            rec["geometry_source_url"] = gurl
            rec["coord_source"] = "portal_geometry_centroid"
            cen = geometry_centroid(geom)
            if cen:
                rec["lat"], rec["lon"] = cen
            break

    def _proyecto_from_url(self, url: str, lastmod: str | None = None) -> dict[str, Any] | None:
        html = self._fetch(url, timeout=45)
        if not html:
            return None
        title = self._page_title(html, fallback=url.rsplit("/", 1)[-1])
        body = self._page_body_text(html)
        blob = f"{title} {body}"
        if not RE_PROYECTO_BODY.search(blob) and not RE_SITEMAP_PROY.search(url):
            return None
        fecha = self._page_fecha(html) or _parse_fecha(lastmod or "") or "2020-01-01"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": fecha,
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": "drupal_web",
        }
        if body:
            rec["resumen"] = body[:500]
        self._attach_geometry(rec, blob)
        return rec

    def _proyecto_stub(self, url: str, titulo: str, tipo: str = "planeamiento") -> dict[str, Any]:
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": "2020-01-01",
            "tipo": tipo,
            "url": url,
            "source": "ayuntamiento",
            "origen": "catalog_stub",
        }

    def _collect_seu_publications(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for cat_id, label in SEU_URBANISME_LISTS:
            list_url = (
                f"{SEU}/seu/urbanismeCategoriaPublic/listPublicacionsAmbCategoria"
                f"?categoria.id={cat_id}&multiseu="
            )
            html = self._fetch(list_url, timeout=self.seu_timeout_s, retries=1)
            if not html:
                rows.append(self._proyecto_stub(list_url, label, "catálogo sede urbanisme"))
                continue
            for m in re.finditer(
                r'href="([^"]*mostrarPublicacion[^"]*|[^"]*urbanisme[^"]*)"', html, re.I
            ):
                href = unescape(m.group(1))
                if "listPublicacions" in href:
                    continue
                url = urllib.parse.urljoin(f"{SEU}/", href)
                tit = _clean(m.group(0))
                tit_m = re.search(r">([^<]{8,200})<", m.group(0))
                if tit_m:
                    tit = _clean(tit_m.group(1))
                else:
                    tit = f"{label} — publicación"
                rec = self._proyecto_stub(url, tit, "publicación urbanismo")
                rec["origen"] = "seu_urbanisme"
                fecha = _parse_fecha(html)
                if fecha:
                    rec["fecha"] = fecha
                rows.append(rec)
            if not any(r.get("origen") == "seu_urbanisme" for r in rows):
                rows.append(self._proyecto_stub(list_url, label, "catálogo sede urbanisme"))
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if not rec or rec["id"] in seen:
                return
            seen.add(rec["id"])
            rows.append(rec)

        for url in self.seed_pages:
            if "rpucportal" in url:
                add(
                    self._proyecto_stub(
                        url,
                        "PGOU Reus — Registre de Planejament Urbanístic de Catalunya (exp. 267316)",
                        "plan general",
                    )
                )
                continue
            add(self._proyecto_from_url(url))

        lastmod_by_url = {u: lm for u, lm in self._sitemap_urls()}
        for url in self._discover_proyecto_urls():
            add(self._proyecto_from_url(url, lastmod_by_url.get(url)))

        for rec in self._collect_seu_publications():
            add(rec)

        # PDFs de planejament enlazados en la página semilla
        planej = self._fetch(f"{BASE}/serveis/planejament-urbanistic", timeout=45)
        if planej:
            for pdf in re.findall(r'href="([^"]+\.pdf[^"]*)"', planej, re.I):
                purl = self._abs(pdf)
                add(
                    {
                        "id": _stable_id("proy", purl),
                        "municipio": MUNICIPIO,
                        "titulo": f"Document PDF planejament — {purl.rsplit('/', 1)[-1][:60]}",
                        "fecha": _parse_fecha(purl) or "2020-01-01",
                        "tipo": "documentación planeamiento",
                        "url": purl,
                        "source": "ayuntamiento",
                        "origen": "drupal_pdf",
                    }
                )

        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo in SEU_TRAMIT_LINKS:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": "2020-01-01",
                    "tipo": titulo,
                    "distrito": "",
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "seu_tramit_info",
                }
            )
        tramits_html = self._fetch(f"{BASE}/serveis/tramits-i-llicencies", timeout=45)
        if tramits_html:
            for m in re.finditer(r'href="(https://seu\.reus\.cat[^"]+)"[^>]*>([^<]+)', tramits_html):
                url, tit = m.group(1), _clean(m.group(2))
                if not RE_LICENCIA.search(f"{tit} {url}") and "Arquitectura" not in tit:
                    continue
                rows.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": "2020-01-01",
                        "tipo": tit or "Tràmit urbanisme",
                        "distrito": "",
                        "lat": None,
                        "lon": None,
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "drupal_tramits",
                    }
                )
        dedup = {r["id"]: r for r in rows}
        return list(dedup.values())

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
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "seu_tramits_info"}

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
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
