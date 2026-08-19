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
from municipio.geometry import geometry_centroid, record_geometry

WP_BASE = "https://aldeatejada.es"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
MUNICIPIO = "Aldeatejada"
ID_PREFIX = "aldeatejada"

WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/ows"
WFS_MUNICIPIO = "Aldeatejada"
WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/ayuntamiento/",
    f"{WP_BASE}/fichas-parcelas-resultantes/",
    f"{WP_BASE}/fichas-parcelas-aportadas/",
    f"{WP_BASE}/planos-de-reparcelacion/",
    f"{WP_BASE}/edictos/",
    f"{WP_BASE}/bandos/",
    f"{WP_BASE}/tablon-de-anuncios/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|cartel.*licencia|licencia ambiental)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|"
    r"proyecto de (?:urbaniz|actuaci)|estudio de detalle|modificaci[oó]n|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|reparcel|enajenaci[oó]n.*suelo|"
    r"unidad de (?:ejecuci[oó]n|actuaci)|sector|edicto|bando|normalizaci[oó]n|"
    r"autorizaci[oó]n de uso|suelo urbanizable|peri|bocyl|ficha.*parcela)",
)
RE_WP_EXCLUDE = re.compile(
    r"(?i)(fiestas|cine|empleo|concurso|deporte|bols[ií]n|violencia de g[eé]nero|"
    r"subvenci[oó]n deportiv|empadron|tribut|matrimonio|carnaval|navidad|piscina|"
    r"bibliob[uú]s|gripe|covid|vacunaci[oó]n|ordenanza fiscal|impuesto|plusval[ií]a|"
    r"architecto municipal|bolsa de empleo)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|proceso selectivo|pleno|"
    r"plusvalia|basura|residuos|vehiculos|igualdad|jurado|juez de paz|"
    r"selecci[oó]n de personal|tribunal|convocatoria pleno|monitor actividades|"
    r"ruidos animales|reciclaje)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|documents)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?aldeatejada\.es)?/wp-content/uploads/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"SU[-\s]?NC\.?\s*(?:N[ºo°]\.?\s*)?\d+(?:[-/]\d+)?|"
    r"SUNC[-\s]?\d+(?:[-/]\d+)?|"
    r"SUD[-\s]?\d+(?:[-/]\d+)?|"
    r"SUA[-\s]?\d+(?:[-/]\d+)?|"
    r"UU[-\s]?\d+(?:[-/]\d+)?|"
    r"UR[-\s]?\d+[A-Z]?|"
    r"AH[-\s]?\d+[A-Z]?|"
    r"SECTOR\s+[A-Z0-9.-]{1,12}|"
    r"PERI\s+acci[oó]n\s*(?:n[ºo°]\.?\s*)?\d+"
    r")\b",
)


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


def _parse_fecha_iso(text: str) -> str | None:
    m = re.search(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b", text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    iso = _parse_fecha_iso(text)
    if iso:
        return iso
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


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _normalize_sector_code(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", " ", code)
    code = code.replace("SU NC", "SU-NC")
    code = re.sub(r"SU-NC\.?\s*N[ºO°]\.?\s*", "SU-NC.", code)
    code = re.sub(r"SUNC\s*", "SUNC-", code)
    code = re.sub(r"SUD\s*", "SUD-", code)
    code = re.sub(r"SUA\s*", "SUA-", code)
    code = re.sub(r"UU\s*", "UU-", code)
    code = re.sub(r"UR\s*", "UR-", code)
    code = re.sub(r"AH\s*", "AH-", code)
    return code.strip()


def _sector_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_SECTOR_CODE.finditer(text or ""):
        code = _normalize_sector_code(m.group(1))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "plan parcial" in n or "plan-parcial" in n:
        return "plan parcial"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "proyecto de actuaci" in n or "proyecto de actuación" in n:
        return "proyecto de actuación"
    if "normalizaci" in n:
        return "normalización sector"
    if "informaci" in n and "p" in n:
        return "información pública"
    if "licencia" in n:
        return "licencia"
    if "autorizaci" in n and "uso" in n:
        return "autorización de uso"
    if "reparcel" in n or "ficha" in n and "parcela" in n:
        return "reparcelación"
    if "modificaci" in n:
        return "modificación puntual"
    if "sector" in n:
        return "sector"
    return "urbanismo"


class AldeatejadaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (urbanismo en /ayuntamiento/#urbanismo) + IDECyL WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.wp_api = str(self.config.get("wp_api") or f"{self.wp_base}/wp-json/wp/v2")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or WFS_MUNICIPIO)
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_sector_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-aldeatejada/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _wfs_query_url(self, layer: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "120",
                "CQL_FILTER": f"n_mun = '{self.wfs_municipio}'",
            }
        )
        return f"{self.wfs_base}?{params}"

    def _build_wfs_sector_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_sector_index is not None:
            return self._wfs_sector_index
        index: dict[str, dict[str, Any]] = {}
        for rec in self._collect_wfs_proyectos():
            for token in (
                str(rec.get("sector_code") or ""),
                str(rec.get("titulo") or ""),
            ):
                for code in _sector_codes_from_text(token):
                    index.setdefault(code, rec)
        self._wfs_sector_index = index
        return index

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        for layer, default_tipo in WFS_LAYERS:
            url = self._wfs_query_url(layer)
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            for feat in data.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                titulo = _strip_html(str(props.get("n_titulo") or ""))
                sector = str(props.get("n_sector") or "").strip()
                num = str(props.get("n_num_sect") or "").strip()
                if not titulo:
                    titulo = f"{sector} ({num})" if sector else num
                if not titulo:
                    titulo = str(props.get("c_id_sect") or props.get("c_plan") or layer)
                instrum = str(props.get("n_instrum") or props.get("c_instrum") or "")
                blob = f"{titulo} {instrum}"
                fecha = _parse_fecha_iso(str(props.get("f_bocyl") or "")) or _parse_fecha_iso(
                    str(props.get("f_aprob") or "")
                )
                doc_url = str(props.get("url_doc_info") or "").strip() or url
                key = str(props.get("c_id_sect") or props.get("c_plan") or props.get("fid") or titulo)
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", f"wfs:{layer}:{key}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(blob) if blob.strip() else default_tipo,
                    "url": doc_url,
                    "source": "ayuntamiento",
                    "origen": "idecyl_wfs",
                    "wfs_layer": layer,
                    "sector_id": props.get("c_id_sect"),
                    "sector_code": num or None,
                    "instrumento": instrum or None,
                }
                if isinstance(geom, dict) and geom.get("type"):
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
        self._wfs_cache = rows
        return rows

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "expte", "url", "pdf_url"))
        index = self._build_wfs_sector_index()
        for code in _sector_codes_from_text(blob):
            hit = index.get(code)
            if not hit:
                continue
            for key in (
                "geom_geojson",
                "geometry_source",
                "geometry_source_url",
                "coord_source",
                "lat",
                "lon",
                "sector_code",
            ):
                if hit.get(key) is not None:
                    rec[key] = hit[key]
            return

    def _collect_urbanismo_groups(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(f"{self.wp_base}/ayuntamiento/")
        except urllib.error.URLError:
            return []
        m = re.search(r'id="urbanismo".*?(?=id="precio-publico"|id="eventos"|<footer)', html, re.S | re.I)
        if not m:
            return []
        block = m.group(0)
        rows: list[dict[str, Any]] = []
        for strong_m in re.finditer(r"<strong>([^<]+)</strong>", block, re.I):
            title = _strip_html(strong_m.group(1))
            if not title or len(title) < 8:
                continue
            if title.lower().startswith(("documento", "memoria", "plano", "edicto:", "publicaci")):
                continue
            if not RE_PROYECTO.search(title) and not RE_LICENCIA.search(title):
                continue
            chunk = block[strong_m.start() : strong_m.start() + 2500]
            pdf_m = RE_PDF_HREF.search(chunk)
            pdf_url = self._abs_wp(pdf_m.group(1)) if pdf_m else None
            rows.append(
                {
                    "titulo": title[:500],
                    "url": f"{self.wp_base}/ayuntamiento/#urbanismo",
                    "pdf_url": pdf_url,
                    "fecha": _fecha_from_blob(title + " " + (pdf_url or "")),
                    "origen": "wp_urbanismo_group",
                }
            )
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = ""
            m = re.search(r"<title>([^<]+)", html, re.I)
            if m:
                page_title = _strip_html(m.group(1))
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_wp(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
                link_text = ""
                ctx = html[max(0, m.start() - 200) : m.end() + 50]
                text_m = re.search(r">([^<]{3,120})</a>", ctx)
                if text_m:
                    link_text = _strip_html(text_m.group(1))
                titulo = link_text or name
                blob = f"{page_title} {titulo} {pdf}"
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if "urbanismo" not in page_url and "parcela" not in page_url and "reparcel" not in page_url:
                        continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": page_url,
                        "pdf_url": pdf,
                        "fecha": _fecha_from_blob(pdf + " " + titulo),
                        "origen": "wp_pdf",
                        "page_title": page_title,
                    }
                )
        return rows

    def _paginate_wp(self, endpoint: str, max_pages: int = 8) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page_num in range(1, max_pages + 1):
            url = f"{self.wp_api}/{endpoint}?per_page=100&page={page_num}&status=publish"
            try:
                batch = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(batch, list) or not batch:
                break
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    def _wp_item_to_proyecto(self, item: dict[str, Any], origen: str) -> dict[str, Any] | None:
        title = _strip_html(str((item.get("title") or {}).get("rendered") or ""))
        if not title or RE_WP_EXCLUDE.search(title):
            return None
        content = str((item.get("content") or {}).get("rendered") or "")
        blob = f"{title} {_strip_html(content)}"
        if not RE_PROYECTO.search(blob):
            return None
        url = str(item.get("link") or "").strip()
        if not url:
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": _iso_date_wp(str(item.get("date") or item.get("modified") or "")),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": origen,
        }
        pdfs = [self._abs_wp(m.group(1)) for m in RE_PDF_HREF.finditer(content)]
        if pdfs:
            rec["pdf_url"] = pdfs[0]
        self._attach_geometry(rec)
        return rec

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')} {row.get('page_title', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or row.get("pdf_url") or f"{self.wp_base}/ayuntamiento/#urbanismo",
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            (f"{self.wp_base}/ayuntamiento/#urbanismo", "urbanismo — documentación y trámites"),
            (
                f"{self.wp_base}/wp-content/uploads/2025/02/ORDENANZA-LICENCIAS-URBANISTICAS.pdf",
                "ordenanza tasa licencias urbanísticas",
            ),
            (
                f"{self.wp_base}/wp-content/uploads/2025/03/ORDENANZA-LICENCIA-APERTURA-ESTABLECIMIENTOS.pdf",
                "ordenanza licencia apertura establecimientos",
            ),
            (f"{self.wp_base}/tablon-de-anuncios/", "tablón de anuncios municipal"),
        ]
        rows: list[dict[str, Any]] = []
        for url, tipo in pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": tipo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámite o publicación",
                    "origen": "wp_tramite",
                }
            )
        return rows

    def _wp_item_to_licencia(self, item: dict[str, Any], origen: str) -> dict[str, Any] | None:
        title = _strip_html(str((item.get("title") or {}).get("rendered") or ""))
        if not title or RE_WP_EXCLUDE.search(title):
            return None
        content = str((item.get("content") or {}).get("rendered") or "")
        blob = f"{title} {_strip_html(content)}"
        if not RE_LICENCIA.search(blob):
            return None
        url = str(item.get("link") or "").strip()
        if not url:
            return None
        pdfs = [self._abs_wp(m.group(1)) for m in RE_PDF_HREF.finditer(content)]
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": _iso_date_wp(str(item.get("date") or "")),
            "tipo": "licencia / autorización",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": origen,
            **({"pdf_url": pdfs[0]} if pdfs else {}),
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for post in self._paginate_wp("posts", max_pages=10):
            rec = self._wp_item_to_licencia(post, "wp_posts")
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "wp_tramite"),
            "wp_posts": sum(1 for r in rows if r.get("origen") == "wp_posts"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for post in self._paginate_wp("posts", max_pages=10):
            rec = self._wp_item_to_licencia(post, "wp_posts")
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for page in self._paginate_wp("pages"):
            add(self._wp_item_to_proyecto(page, "wp_pages"))
        for post in self._paginate_wp("posts", max_pages=10):
            add(self._wp_item_to_proyecto(post, "wp_posts"))
        for item in self._collect_urbanismo_groups():
            add(self._row_to_proyecto(item))
        for item in self._collect_seed_pdfs():
            add(self._row_to_proyecto(item))
        for rec in self._collect_wfs_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_pages": sum(1 for r in rows if r.get("origen") == "wp_pages"),
            "wp_posts": sum(1 for r in rows if r.get("origen") == "wp_posts"),
            "wp_urbanismo_group": sum(1 for r in rows if r.get("origen") == "wp_urbanismo_group"),
            "wp_pdf": sum(1 for r in rows if r.get("origen") == "wp_pdf"),
            "idecyl_wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "with_geometry": with_geom,
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
