from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid

WP_BASE = "https://www.argandadelrey.es"
SEDE_BASE = "https://sedeelectronica.argandadelrey.es"
CKAN_BASE = "https://datosabiertos.ayto-arganda.es"
MUNICIPIO = "Arganda del Rey"
ID_PREFIX = "arganda-del-rey"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
PLANEAMIENTO_SEDE = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_PLANEA"
SEDE_CATALOGO = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"

URBANISMO_PAGE = f"{WP_BASE}/servicios-cpt/urbanismo/"
EXPOSICION_PUBLICA = f"{WP_BASE}/servicios-cpt/urbanismo/instrumentos-urbanisticos-en-exposicion-publica/"
PGOU_AVANCE = f"{WP_BASE}/servicios-cpt/urbanismo/avance-2023-para-nuevo-plan-general/"
PGOU_PREAVANCE = f"{WP_BASE}/servicios-cpt/urbanismo/preavance-2021/"
PGOU_VIGENTE = f"{WP_BASE}/servicios-cpt/urbanismo/plan-general/"

CONVENIOS_JSON = (
    f"{CKAN_BASE}/dataset/901cc3dd-4e47-4cca-adcf-ed7ddfdaf344/resource/"
    "1b301e37-7410-4535-83ee-3f05535041ca/download/convenios_urbanisticos.json"
)
UE_GEOJSON = (
    f"{CKAN_BASE}/dataset/eb4dcc25-84ae-4d78-8693-0c47f1805c27/resource/"
    "3c1364d9-fc47-4617-99dd-cade9cc6b415/download/map-8.geojson"
)

DEFAULT_URBANISMO_PAGES: list[str] = [
    URBANISMO_PAGE,
    EXPOSICION_PUBLICA,
    PGOU_AVANCE,
    PGOU_PREAVANCE,
    PGOU_VIGENTE,
    f"{PGOU_AVANCE}documento-informativo/",
    f"{PGOU_AVANCE}documento-normativo/",
    f"{PGOU_AVANCE}documento-ambiental/",
    f"{PGOU_AVANCE}instancias/",
    f"{WP_BASE}/servicios-cpt/urbanismo/pe-ue024-plan-especial-equipamientos/",
    f"{WP_BASE}/servicios-cpt/urbanismo/ed-ue107-estudio-de-detalle-manzana-16/",
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{WP_BASE}/servicios-cpt/urbanismo/ordenanzas/",
    f"{WP_BASE}/servicios-cpt/urbanismo/inspeccion-tecnica-edificios/",
    SEDE_CATALOGO,
    URBANISMO_PAGE,
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|certificaci[oó]n urban|"
    r"inspecci[oó]n t[eé]cnica de edificios|ite\b)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|modificaci[oó]n|"
    r"aprobaci[oó]n (?:inicial|definitiva)|estudio (?:ac[uú]stico|ambiental|de detalle)|"
    r"edicto|acuerdo|pleno|orden de ejecuci|segregaci|ue[-\.\d]|pe\.ue|ed\.ue|"
    r"instrumento urban|documento normativo|documento informativo|documento ambiental)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_PIPE = re.compile(r"(\d{1,2})\|(\d{1,2})\|(\d{4})")
RE_FECHA_YM = re.compile(r"/wp-content/uploads/(\d{4})/(\d{2})/")
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.argandadelrey\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_UE_CODE = re.compile(r"(?:PE\.|ED\.|UE[-\. ]?)(?:UE)?(\d{1,4})", re.I)
RE_SEDE_TRAMITE = re.compile(
    r'href="((?:https://sedeelectronica\.argandadelrey\.es)?/sta/[^"]*(?:licencia|obra|urban)[^"]*)"',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_PIPE):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(int(obj["year"]), int(obj["month"]), int(obj["day"])).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>([^<]+)',
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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _ue_codes(text: str) -> list[str]:
    out: list[str] = []
    for m in RE_UE_CODE.finditer(text or ""):
        num = int(m.group(1))
        out.append(f"UE-{num}")
    return list(dict.fromkeys(out))


def _pgou_tipo(name: str) -> str:
    n = name.lower()
    if "informacion" in n or "informativo" in n:
        return "documento informativo"
    if "normativo" in n:
        return "documento normativo"
    if "ambiental" in n:
        return "estudio ambiental"
    if "convenio" in n:
        return "convenio urbanístico"
    if "plan especial" in n or "pe.ue" in n or "pe-" in n:
        return "plan especial"
    if "estudio de detalle" in n or "ed.ue" in n:
        return "estudio de detalle"
    if "exposici" in n or "informaci" in n:
        return "información pública"
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    return "documento urbanismo"


class ArgandaDelReyAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress urbanismo + datos abiertos CKAN + sede STA (tablón/planeamiento)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.urbanismo_pages = [
            str(u) for u in (self.config.get("urbanismo_pages") or DEFAULT_URBANISMO_PAGES)
        ]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.ue_geojson_url = str(self.config.get("ue_geojson_url") or UE_GEOJSON)
        self.convenios_json_url = str(self.config.get("convenios_json_url") or CONVENIOS_JSON)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._ue_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-arganda-del-rey/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sedeelectronica.argandadelrey.es" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, use_sede_ssl: bool = False) -> Any:
        raw = self._fetch(url, use_sede_ssl=use_sede_ssl)
        return json.loads(raw)

    def _abs_url(self, href: str, base: str = WP_BASE) -> str:
        return urllib.parse.urljoin(base, href)

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _discover_urbanismo_pages(self) -> list[str]:
        pages = list(self.urbanismo_pages)
        try:
            data = self._fetch_json(f"{WP_BASE}/wp-json/wp/v2/pages?parent=3568&per_page=100")
            if isinstance(data, list):
                for page in data:
                    link = str(page.get("link") or "")
                    if link:
                        pages.append(link)
                    page_id = page.get("id")
                    if not page_id:
                        continue
                    children = self._fetch_json(
                        f"{WP_BASE}/wp-json/wp/v2/pages?parent={page_id}&per_page=50"
                    )
                    if isinstance(children, list):
                        for child in children:
                            clink = str(child.get("link") or "")
                            if clink:
                                pages.append(clink)
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            pass
        return list(dict.fromkeys(pages))

    def _load_ue_index(self) -> dict[str, dict[str, Any]]:
        if self._ue_index is not None:
            return self._ue_index
        index: dict[str, dict[str, Any]] = {}
        try:
            data = self._fetch_json(self.ue_geojson_url)
            features = data.get("features") if isinstance(data, dict) else []
            for feat in features or []:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                ue = str(props.get("UE") or props.get("NOMBRE") or "").strip()
                if ue and isinstance(geom, dict):
                    index[ue.upper()] = geom
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            pass
        self._ue_index = index
        return index

    def _fetch_geometry(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(rec.get(k) or "")
            for k in ("titulo", "tipo", "url", "pdf_url", "origen")
        )
        ue_index = self._load_ue_index()
        for code in _ue_codes(blob):
            geom = ue_index.get(code.upper())
            if geom:
                return {
                    "geom_geojson": geom,
                    "geometry_source": "portal_geojson",
                    "geometry_source_url": self.ue_geojson_url,
                    "coord_source": "portal_geometry_centroid",
                }
        return None

    def _apply_geometry(self, rec: dict[str, Any]) -> dict[str, Any]:
        geom_fields = self._fetch_geometry(rec)
        if geom_fields:
            rec.update(geom_fields)
            centroid = geometry_centroid(rec["geom_geojson"])
            if centroid:
                rec["lat"], rec["lon"] = centroid
        return rec

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except (urllib.error.URLError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            title = str(item.get("descriptionProc") or item.get("externString") or "").strip()
            rem = item.get("remitent") or {}
            remitente = str(rem.get("description") or rem.get("code") or "")
            fecha = _xml_date(item.get("pubDateIni")) or ""
            dboid = str(item.get("dboid") or title)
            url = f"{TABLON_URL}#dboid={dboid}"
            rows.append(
                {
                    "titulo": title[:500],
                    "remitente": remitente,
                    "fecha": fecha,
                    "url": url,
                    "origen": "sede_tablon",
                }
            )
        return rows

    def _collect_sede_planeamiento(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(PLANEAMIENTO_SEDE, use_sede_ssl=True)
        except (urllib.error.URLError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_PLANEA"):
            title = str(item.get("descriptionProc") or item.get("externString") or "").strip()
            fecha = _xml_date(item.get("pubDateIni")) or ""
            dboid = str(item.get("dboid") or title)
            url = f"{PLANEAMIENTO_SEDE}#dboid={dboid}"
            if title:
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": url,
                        "origen": "sede_planeamiento",
                    }
                )
        return rows

    def _collect_wordpress(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_pages: set[str] = set()
        seen_pdfs: set[str] = set()
        for page_url in self._discover_urbanismo_pages():
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, OSError):
                continue
            title = _page_title(html, page_url.rsplit("/", 2)[-2].replace("-", " "))
            page_blob = f"{title} {page_url}"
            if RE_PROYECTO.search(page_blob):
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _parse_fecha_dmy(html) or _fecha_from_pdf_url(page_url),
                        "url": page_url,
                        "tipo": _pgou_tipo(title),
                        "origen": page_url,
                    }
                )
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                if pdf in seen_pdfs or "favicon" in pdf.lower():
                    continue
                seen_pdfs.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                blob = f"{title} {name} {pdf}"
                if not RE_PROYECTO.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": f"{title}: {name}"[:500] if title else name[:500],
                        "fecha": _fecha_from_pdf_url(pdf) or _parse_fecha_dmy(html),
                        "url": page_url,
                        "pdf_url": pdf,
                        "tipo": _pgou_tipo(f"{title} {name}"),
                        "origen": page_url,
                    }
                )
        return rows

    def _collect_convenios(self) -> list[dict[str, Any]]:
        try:
            data = self._fetch_json(self.convenios_json_url)
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            return []
        if not isinstance(data, list):
            return []
        rows: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            titulo = str(item.get("Objeto") or "").strip()
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(str(item.get("Fecha") or "")),
                    "url": CONVENIOS_JSON,
                    "pdf_url": str(item.get("Pdf") or "") or None,
                    "tipo": "convenio urbanístico",
                    "origen": "datos_abiertos_convenios",
                }
            )
        return rows

    def _collect_licencia_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url, use_sede_ssl="sedeelectronica" in page_url)
            except (urllib.error.URLError, OSError):
                continue
            if "sedeelectronica" in page_url:
                for m in RE_SEDE_TRAMITE.finditer(html):
                    href = self._abs_url(m.group(1), SEDE_BASE)
                    ctx = html[max(0, m.start() - 400) : m.end() + 200]
                    label = _strip_html(ctx)[:300]
                    if not RE_LICENCIA.search(label):
                        continue
                    key = href
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "id": _stable_id("lic", href),
                            "fecha_concesion": None,
                            "tipo": "trámite informativo",
                            "distrito": None,
                            "lat": None,
                            "lon": None,
                            "titulo": label[:500] or "Trámite urbanismo sede",
                            "url": href,
                            "source": "ayuntamiento",
                        }
                    )
                continue
            title = _page_title(html, page_url.rsplit("/", 2)[-2].replace("-", " "))
            if not RE_LICENCIA.search(f"{title} {page_url}"):
                continue
            rec = {
                "id": _stable_id("lic", page_url),
                "fecha_concesion": None,
                "tipo": "trámite informativo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": page_url,
                "source": "ayuntamiento",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _tablon_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item["titulo"]
        if not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", item["url"]),
            "fecha_concesion": item.get("fecha") or None,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": item["url"],
            "source": "ayuntamiento",
        }

    def _tablon_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item["titulo"]
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        if not RE_PROYECTO.search(titulo):
            return None
        tipo = "urbanismo"
        if re.search(r"(?i)convenio", titulo):
            tipo = "convenio urbanístico"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|exposici", titulo):
            tipo = "información pública"
        elif re.search(r"(?i)pleno|acuerdo", titulo):
            tipo = "acuerdo plenario"
        return self._apply_geometry(
            {
                "id": _stable_id("proy", item["url"]),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": item.get("fecha") or None,
                "tipo": tipo,
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": item.get("origen"),
            }
        )

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        pdf = item.get("pdf_url") or item["url"]
        rec = {
            "id": _stable_id("proy", pdf),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha") or None,
            "tipo": item.get("tipo", "documento urbanismo"),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        return self._apply_geometry(rec)

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
        for rec in self._collect_licencia_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, len(rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_sede_planeamiento():
            add(self._item_to_proyecto(item))
        for item in self._collect_wordpress():
            add(self._item_to_proyecto(item))
        for item in self._collect_convenios():
            add(self._item_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "wordpress_pages": len(self._discover_urbanismo_pages()),
            "convenios": len(self._collect_convenios()),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, after - before),
                    "with_geometry": result.get("with_geometry", 0),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
