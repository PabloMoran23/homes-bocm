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
from urllib.parse import unquote, urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.benidorm.org"
CONTENT_BASE = "https://contenidos.benidorm.org"
SEDE_TABLON = "https://sede.benidorm.org/eAdmin/Tablon.do?action=verAnuncios&tipoTablon=1"
MUNICIPIO = "Benidorm"
ID_PREFIX = "benidorm"
INE_MUN = "03031"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/ayuntamiento/concejalias/urbanismo",
    f"{WEB_BASE}/es/ayuntamiento/concejalias/urbanismo/planeamiento-y-gestion/informacion-publica",
    f"{WEB_BASE}/es/ayuntamiento/concejalias/urbanismo/planeamiento-y-gestion/instrumentos-de-ordenacion",
    f"{WEB_BASE}/es/ayuntamiento/concejalias/urbanismo/planeamiento-y-gestion/instrumentos-de-gestion",
    f"{WEB_BASE}/es/ayuntamiento/concejalias/urbanismo/planeamiento-y-gestion/convenios",
    f"{WEB_BASE}/es/ayuntamiento/concejalias/urbanismo/planeamiento-y-gestion/consultas",
    f"{WEB_BASE}/es/ayuntamiento/concejalias/urbanismo/arquitectura/plan-general",
    f"{WEB_BASE}/es/ayuntamiento/concejalias/obras/ingenieria/informacion-publica-ingenieria",
    f"{WEB_BASE}/es/pagina/ordenanzas-urbanisticas",
    f"{WEB_BASE}/es/pagina/urbanismo",
    f"{WEB_BASE}/es/pagina/normativas",
]

LICENCIA_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/ayuntamiento/concejalias/urbanismo/administracion-urbanistica/solicitud-permiso-obras",
    f"{WEB_BASE}/es/ayuntamiento/concejalias/urbanismo/administracion-urbanistica/solicitud-permiso-obras/otras-instancias",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|inicio de obra|permiso de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgmo|pgou|pai|pri|paa|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"convenio|edicto|dogv|sector|urbanizaci[oó]n|estudio de detalle|"
    r"reforma interior|expropiaci[oó]n|interpretaci[oó]n)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|plaza de|empleo p[uú]blico|"
    r"subvenci[oó]n|huertos urbanos|taxi|nombramiento|bolsa)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:descargas|archivos)/(\d{4})-(\d{2})/")
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_TABLON_ROW = re.compile(r"<tr[^>]*>.*?</tr>", re.I | re.S)
RE_TABLON_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)

SKIP_HUB_TITLES = {
    "urbanismo",
    "información pública",
    "instrumentos de ordenación",
    "instrumentos de gestión",
    "convenios",
    "consultas",
    "plan general",
    "ordenanzas urbanísticas",
    "administración urbanística",
    "información pública ingeniería",
    "arquitectura",
    "planeamiento y gestión",
    "normativas",
}


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


def _fecha_from_path(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "reforma interior" in n or " pri " in f" {n} ":
        return "plan de reforma interior"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "plan parcial" in n or "sector" in n or " pp-" in n:
        return "plan parcial"
    if "modificaci" in n and ("pgmo" in n or "pgou" in n):
        return "modificación PGMO"
    if "pgmo" in n or "plan general" in n:
        return "PGMO"
    if "convenio" in n:
        return "convenio urbanístico"
    if "informaci" in n or "dogv" in n:
        return "información pública"
    if "expropiaci" in n:
        return "expropiación"
    if "urbanizaci" in n:
        return "urbanización"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.split() if x.strip()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lng = nums[i], nums[i + 1]
        ring.append([lng, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


class BenidormAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 11 benidorm.org + archivos contenidos.benidorm.org + sede tablón + ICV WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.content_base = str(self.config.get("content_base") or CONTENT_BASE).rstrip("/")
        self.sede_tablon = str(self.config.get("sede_tablon") or SEDE_TABLON)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or LICENCIA_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 220))
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or "https://terramapas.icv.gva.es/0702_Planeamiento").rstrip("/")
        self.wfs_type = str(geom_cfg.get("type_name") or "InventarioSuSuz")
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-benidorm/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-benidorm/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def _abs_url(self, href: str, page_url: str = "") -> str:
        href = unescape(href.strip())
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if href.startswith("/"):
            return urljoin(self.web_base + "/", href)
        return urljoin(page_url or self.web_base + "/", href)

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r"<h1[^>]*class=['\"][^'\"]*pagina-title[^'\"]*['\"][^>]*>([^<]+)",
            r"<h1[^>]*class=['\"][^'\"]*page-title[^'\"]*['\"][^>]*>([^<]+)",
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = unescape(m.group(1).strip())
                t = re.sub(r"\s*[-|].*Benidorm.*$", "", t, flags=re.I).strip()
                if t and len(t) > 3:
                    return t[:500]
        return fallback

    def _is_urban_path(self, url: str) -> bool:
        path = urllib.parse.urlparse(url).path.lower()
        if "/ayuntamiento/concejalias/urbanismo" in path:
            return True
        if "/ayuntamiento/concejalias/obras" in path and any(
            k in path for k in ("informacion-publica", "proyecto", "urbaniz", "ingenieria")
        ):
            return True
        if path.endswith("/pagina/ordenanzas-urbanisticas") or path.endswith("/pagina/urbanismo"):
            return True
        return False

    def _extract_pdfs(self, html: str, page_url: str) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for m in RE_PDF.finditer(html):
            u = self._abs_url(m.group(1), page_url)
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
        return out

    def _crawl_proyectos(self) -> list[dict[str, Any]]:
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

            title = self._page_title(html, url.rsplit("/", 1)[-1].replace("-", " ").title())
            pdfs = self._extract_pdfs(html, url)
            blob = f"{title} {url}"

            if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
                pass
            elif RE_PROYECTO.search(blob) or self._is_urban_path(url):
                rec_id = _stable_id("proy", url)
                if title.strip().lower() in SKIP_HUB_TITLES and not pdfs:
                    pass
                elif rec_id not in seen_ids and title and len(title) > 5:
                    seen_ids.add(rec_id)
                    fechas = [_fecha_from_path(p) for p in pdfs] + [_parse_fecha_dmy(blob)]
                    fechas = [f for f in fechas if f]
                    rec: dict[str, Any] = {
                        "id": rec_id,
                        "municipio": MUNICIPIO,
                        "titulo": title,
                        "fecha": max(fechas) if fechas else None,
                        "tipo": _proyecto_tipo(blob),
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "drupal_urbanismo",
                    }
                    if pdfs:
                        rec["pdf_url"] = pdfs[0]
                        if len(pdfs) > 1:
                            rec["pdf_urls"] = pdfs[:40]
                    rows.append(rec)

                for pdf in pdfs:
                    pdf_name = unquote(Path(pdf).name)
                    if not RE_PROYECTO.search(pdf_name) and not RE_PROYECTO.search(blob):
                        continue
                    pdf_id = _stable_id("proy", pdf)
                    if pdf_id in seen_ids:
                        continue
                    seen_ids.add(pdf_id)
                    pdf_title = f"{title}: {pdf_name}" if title else pdf_name
                    rows.append(
                        {
                            "id": pdf_id,
                            "municipio": MUNICIPIO,
                            "titulo": pdf_title[:500],
                            "fecha": _fecha_from_path(pdf) or _parse_fecha_dmy(pdf_name),
                            "tipo": _proyecto_tipo(pdf_title),
                            "url": url,
                            "pdf_url": pdf,
                            "source": "ayuntamiento",
                            "origen": "contenidos_pdf",
                        }
                    )

            if len(visited) < self.max_crawl_pages:
                for m in RE_HREF.finditer(html):
                    href = m.group(1)
                    if not href or href.startswith("#") or href.startswith("mailto:"):
                        continue
                    link = self._abs_url(href, url).rstrip("/")
                    if link in visited or link in queue:
                        continue
                    if "pro.benidorm.org" in link:
                        continue
                    if self._is_urban_path(link):
                        queue.append(link)

        return rows

    def _parse_wfs_feature(self, feat_el: ET.Element) -> dict[str, Any] | None:
        props: dict[str, Any] = {}
        geom: dict[str, Any] | None = None
        for child in feat_el:
            tag = child.tag.split("}", 1)[-1]
            if tag == "msGeometry":
                for gchild in child.iter():
                    gtag = gchild.tag.split("}", 1)[-1]
                    if gtag == "posList" and gchild.text:
                        geom = _gml_poslist_to_polygon(gchild.text)
            elif child.text and tag not in {"boundedBy", "msGeometry"}:
                props[tag] = child.text.strip()
        if props.get("cod_ine_mun") != self.ine_mun:
            return None
        titulo = _strip_html(str(props.get("pp") or props.get("ue") or props.get("clasificacion") or ""))
        if not titulo:
            return None
        fecha = None
        for key in ("f_aprob", "f_public"):
            raw = str(props.get(key) or "")
            if raw and re.match(r"\d{4}-\d{2}-\d{2}", raw):
                fecha = raw[:10]
                break
        key = str(props.get("id") or titulo)
        wfs_url = (
            f"{self.wfs_base}?service=WFS&version=2.0.0&request=GetFeature"
            f"&typename={self.wfs_type}&outputFormat=GML3&srsName=EPSG:4326"
            f"&count=1&STARTINDEX=0"
        )
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"wfs:{key}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": fecha,
            "tipo": _proyecto_tipo(f"{titulo} {props.get('clasificacion', '')}"),
            "url": f"{self.web_base}/es/ayuntamiento/concejalias/urbanismo",
            "source": "ayuntamiento",
            "origen": "icv_wfs",
            "clasificacion": props.get("clasificacion"),
            "uso": props.get("uso"),
        }
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = wfs_url
            rec["coord_source"] = "portal_geometry_centroid"
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
        return rec

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        start = 0
        step = 500
        while True:
            url = (
                f"{self.wfs_base}?service=WFS&version=2.0.0&request=GetFeature"
                f"&typename={self.wfs_type}&outputFormat=GML3&srsName=EPSG:4326"
                f"&count={step}&STARTINDEX={start}"
            )
            try:
                raw = self._fetch_bytes(url)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = [el for el in root if el.tag.endswith("member")]
            if not members:
                break
            for member in members:
                feat_el = member[0]
                rec = self._parse_wfs_feature(feat_el)
                if rec:
                    rows.append(rec)
            start += step
            if len(members) < step:
                break
        self._wfs_cache = rows
        return rows

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        titulo = str(rec.get("titulo") or "").lower()
        if not titulo:
            return
        best: dict[str, Any] | None = None
        best_score = 0
        for wfs_rec in self._collect_wfs_proyectos():
            wfs_title = str(wfs_rec.get("titulo") or "").lower()
            if not wfs_title:
                continue
            score = 0
            if titulo in wfs_title or wfs_title in titulo:
                score = min(len(titulo), len(wfs_title))
            else:
                tokens = [t for t in re.split(r"[\s/_-]+", titulo) if len(t) > 3]
                score = sum(1 for t in tokens if t in wfs_title)
            if score > best_score and wfs_rec.get("geom_geojson"):
                best_score = score
                best = wfs_rec
        if best and best_score >= 2:
            for key in (
                "geom_geojson",
                "geometry_source",
                "geometry_source_url",
                "coord_source",
                "lat",
                "lon",
            ):
                if best.get(key) is not None:
                    rec[key] = best[key]

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.sede_tablon, timeout=15)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            row_html = m.group(0)
            cells = [_strip_html(c) for c in RE_TABLON_CELL.findall(row_html)]
            if len(cells) < 2:
                continue
            titulo = cells[0] if len(cells[0]) > 10 else " ".join(cells)
            blob = " ".join(cells)
            if not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
                continue
            fecha = _parse_fecha_dmy(blob)
            kind = "lic" if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) else "proy"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": self.sede_tablon,
                    "blob": blob,
                    "origen": "sede_tablon",
                    "kind": kind,
                }
            )
        return rows

    def _collect_licencias_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title = self._page_title(html, "Solicitud permiso de obras")
            rows.append(
                {
                    "id": _stable_id("lic", page_url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title,
                    "url": page_url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámites; no concesión publicada en tablón",
                    "origen": "drupal_tramites",
                }
            )
            for pdf in self._extract_pdfs(html, page_url):
                pdf_name = unquote(Path(pdf).name)
                if not RE_LICENCIA.search(pdf_name):
                    continue
                rows.append(
                    {
                        "id": _stable_id("lic", pdf),
                        "fecha_concesion": _fecha_from_path(pdf),
                        "tipo": "formulario licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": pdf_name[:500],
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "nota": "Formulario/instrucciones; no concesión publicada",
                        "origen": "contenidos_pdf",
                    }
                )
        if not rows:
            rows.append(
                {
                    "id": _stable_id("lic", self.sede_tablon),
                    "fecha_concesion": None,
                    "tipo": "tablón licencias (sede)",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Tablón de anuncios — sede.benidorm.org",
                    "url": self.sede_tablon,
                    "source": "ayuntamiento",
                    "nota": "Sede inaccesible desde CI; enlace de referencia",
                    "origen": "sede_tablon_ref",
                }
            )
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", row["titulo"] + str(row.get("fecha") or "")),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["titulo"] + str(row.get("fecha") or "")),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
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
        rows = self._collect_licencias_info()
        tablon = self._collect_tablon()
        for row in tablon:
            if row.get("kind") == "lic":
                rows.append(self._tablon_to_licencia(row))
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tablon": len(tablon)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_info():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        for row in self._collect_tablon():
            if row.get("kind") == "lic":
                rec = self._tablon_to_licencia(row)
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
                self._enrich_geometry(rec)
                rows.append(rec)

        for rec in self._crawl_proyectos():
            add(rec)
        for rec in self._collect_wfs_proyectos():
            add(rec)
        for row in self._collect_tablon():
            if row.get("kind") == "proy":
                add(self._tablon_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "drupal": sum(1 for r in rows if r.get("origen", "").startswith("drupal")),
            "wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
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
