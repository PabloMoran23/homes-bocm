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
from municipio.gis.sitcm import resolve_ambito_geometry, resolve_municipio_wfs

WP_BASE = "https://www.villarejodesalvanes.es"
URBANISMO_URL = f"{WP_BASE}/areas-municipales/urbanismo-y-vivienda/"
TRAMITES_URL = f"{WP_BASE}/tramites-administrativos/tramites-sin-certificado-digital/"
NUEVOS_TRAMITES_URL = f"{WP_BASE}/nuevos-tramites-urbanismo/"
MUNICIPIO = "Villarejo de Salvanés"
ID_PREFIX = "villarejo-de-salvanes"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    TRAMITES_URL,
    NUEVOS_TRAMITES_URL,
    f"{WP_BASE}/urbanismo-obra-y-vivienda1245/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|modificaci[oó]n|aprobaci[oó]n|"
    r"convenio|ordenaci[oó]n|memoria urban|planos|anexo|sau-|ue-|suelo|patrimonio|"
    r"infra|vertido|clasificaci[oó]n|estructura general|catalogo)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|bolsa|familia numerosa|ivtm|"
    r"estacionamiento|terrazas|actividad|asociaciones|cere|multa)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[./-](\d{2})[./-]")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://[^"\']+|/[^"\']+)\.(?:pdf|PDF)(?:[^"\']*)?)["\']',
    re.I,
)
RE_AMBIT_CODE = re.compile(r"(?i)\b((?:UE|SAU)-\d+[A-Z0-9-]*)\b")


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(m.group(1)) for m in RE_YEAR.finditer(text or "") if 1980 <= int(m.group(1)) <= 2035]
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


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "reparcel" in n:
        return "reparcelación"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "convenio" in n:
        return "convenio urbanístico"
    if "memoria" in n:
        return "memoria urbanística"
    if re.search(r"\bor\s*0?\d", n) or "ordenaci" in n or "clasificaci" in n:
        return "planos de ordenación"
    if "anexo" in n:
        return "anexo normativa"
    if re.search(r"\bsau-\d", n):
        return "suelo urbanizable"
    if re.search(r"\bue-\d", n):
        return "unidad de ejecución"
    if "patrimonio" in n or "arqueol" in n:
        return "patrimonio"
    return "planeamiento"


class VillarejoDeSalvanesAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress PDFs urbanismo + formularios licencia + WFS SITCM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or "https://idem.comunidad.madrid/geoserver3/ows")
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or MUNICIPIO)
        self._municipio_wfs: str | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-villarejo-de-salvanes/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", unescape(href))

    def _extract_pdfs(self, html: str) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_url(m.group(1))
            if "favicon" in u.lower():
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def _resolve_municipio_wfs(self) -> str | None:
        if self._municipio_wfs:
            return self._municipio_wfs
        resolved = resolve_municipio_wfs(self.wfs_municipio) or resolve_municipio_wfs(MUNICIPIO)
        self._municipio_wfs = resolved
        return resolved

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        muni_wfs = self._resolve_municipio_wfs()
        if not muni_wfs:
            return
        title = rec.get("titulo") or ""
        if not RE_AMBIT_CODE.search(title):
            return
        geom, meta = resolve_ambito_geometry(muni_wfs, title)
        if not geom:
            return
        cql = (
            f"DS_MUNICIPIO='{muni_wfs.replace(chr(39), chr(39) * 2)}' "
            f"AND DS_NOMB_AMB ILIKE '%{meta.get('ambito_name', '').replace(chr(39), chr(39) * 2)}%'"
        )
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = (
            f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
        )
        rec["coord_source"] = "portal_geometry_centroid"
        if meta.get("ambito_name"):
            rec["ambito_sit"] = meta["ambito_name"]
        cen = geometry_centroid(geom)
        if cen:
            rec.setdefault("lat", cen[0])
            rec.setdefault("lon", cen[1])

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for query in ("urbanismo", "reparcel", "convenio", "planeamiento"):
            try:
                posts = self._fetch_json(
                    f"{self.wp_base}/wp-json/wp/v2/posts?search={urllib.parse.quote(query)}&per_page=50"
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(posts, list):
                continue
            for post in posts:
                link = str(post.get("link") or "").strip()
                if not link or link in seen:
                    continue
                seen.add(link)
                title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                content = str((post.get("content") or {}).get("rendered") or "")
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _iso_date_wp(str(post.get("date") or "")),
                        "url": link,
                        "pdfs": self._extract_pdfs(content),
                        "origen": "wordpress_post",
                    }
                )
        return rows

    def _collect_page_pdfs(self, page_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for pdf in self._extract_pdfs(html):
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_url(pdf) or _fecha_from_blob(name),
                    "url": page_url,
                    "pdf_url": pdf,
                    "origen": origen,
                }
            )
        return rows

    def _licencia_info_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "trámite licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Formularios de licencia y comunicación previa (sin certificado)",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Formularios informativos; no listado de concesiones",
                "origen": "tramites_web",
            },
            {
                "id": _stable_id("lic", NUEVOS_TRAMITES_URL),
                "fecha_concesion": None,
                "tipo": "trámite licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Nuevos trámites en urbanismo — procedimiento licencia",
                "url": NUEVOS_TRAMITES_URL,
                "source": "ayuntamiento",
                "nota": "Información de presentación; sin tablón de concesiones",
                "origen": "tramites_web",
            },
        ]

    def _pdf_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if RE_EXCLUDE.search(row["titulo"]):
            return None
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["pdf_url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "formulario licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "pdf_url": row["pdf_url"],
            "source": "ayuntamiento",
            "nota": "Formulario informativo; no concesión publicada",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('pdf_url', '')}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row.get("url") or self.urbanismo_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("pdfs"):
            rec["pdf_url"] = row["pdfs"][0]
            if len(row["pdfs"]) > 1:
                rec["pdf_urls"] = row["pdfs"][:20]
        self._enrich_geometry(rec)
        return rec

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        return self._row_to_proyecto(row)

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return len(rows)

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def _build_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._licencia_info_rows():
            add(rec)
        for page_url in (self.tramites_url, NUEVOS_TRAMITES_URL):
            for pdf_row in self._collect_page_pdfs(page_url, "tramites_pdf"):
                add(self._pdf_to_licencia(pdf_row))

        return rows

    def _build_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for page_url in self.seed_pages:
            origen = "urbanismo_pdf" if "urbanismo" in page_url else "seed_pdf"
            for pdf_row in self._collect_page_pdfs(page_url, origen):
                add(self._row_to_proyecto(pdf_row))
        for wp_row in self._collect_wp_posts():
            add(self._wp_to_proyecto(wp_row))

        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._build_licencias()
        n = self._write_jsonl(out_jsonl, rows)
        return {
            "ok": True,
            "rows": n,
            "source": "ayuntamiento",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
        for rec in self._load_jsonl(out_jsonl):
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
        rows = self._build_proyectos()
        n = self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "ok": True,
            "rows": n,
            "with_geometry": with_geom,
            "source": "ayuntamiento",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
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
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
