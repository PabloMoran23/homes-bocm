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
from municipio.gis.sitcm import WFS_BASE, _merge_geometries, resolve_ambito_geometry

ID_PREFIX = "valdaracete-brea-de-tajo-y-estremera"
SITCM_VISOR_URL = "https://www.comunidad.madrid/servicios/urbanismo-medio-ambiente/planeamiento-urbanistico-municipios"

VALDARACETE_WEB = "https://www.valdaracete.org"
VALDARACETE_SEDE = "https://sedevaldaracete.eadministracion.es"
BREA_WP = "https://breadetajo.es"
BREA_SEDE = "https://sedebreadetajo.eadministracion.es"

WFS_TYPE = "sitcm:VPLA_V_AMBITO"

VALDARACETE_VIVIENDA = f"{VALDARACETE_WEB}/index.php/vivienda"
VALDARACETE_NORMATIVA = f"{VALDARACETE_WEB}/index.php/normativa-municipal"
BREA_URBANISMO_CAT = f"{BREA_WP}/category/urbanismo/"

DEFAULT_VALDARACETE_LICENCIA_PDFS: list[dict[str, str]] = [
    {
        "path": "http://www.valdaracete.es/valdaracete/opencms/system/galleries/download/Adjuntos/omayor.pdf",
        "tipo": "licencia obra mayor",
        "titulo": "Licencia de Obra Mayor",
    },
    {
        "path": "http://www.valdaracete.es/valdaracete/opencms/system/galleries/download/Adjuntos/omenor.pdf",
        "tipo": "licencia obra menor",
        "titulo": "Licencia de Obra Menor",
    },
    {
        "path": "http://www.valdaracete.es/valdaracete/opencms/system/galleries/download/Adjuntos/primeraocup.pdf",
        "tipo": "licencia primera ocupación",
        "titulo": "Licencia de Primera Ocupación",
    },
    {
        "path": "http://www.valdaracete.es/valdaracete/opencms/system/galleries/download/Adjuntos/solgeneral.pdf",
        "tipo": "instancia general",
        "titulo": "Solicitud general (urbanismo)",
    },
    {
        "path": "http://www.valdaracete.es/valdaracete/opencms/system/galleries/download/Adjuntos/ord1.pdf",
        "tipo": "ordenanza licencias urbanísticas",
        "titulo": "Ordenanza licencias urbanísticas (Legislación del Suelo)",
    },
]

DEFAULT_BREA_LICENCIA_PDFS: list[dict[str, str]] = [
    {
        "path": "https://www.breadetajo.es/pdf/solicitud_licencia_urbanistica.pdf",
        "tipo": "solicitud licencia urbanística",
        "titulo": "Solicitud licencia urbanística",
    },
    {
        "path": "https://www.breadetajo.es/pdf/declaracion_responsable.pdf",
        "tipo": "declaración responsable urbanística",
        "titulo": "Declaración responsable urbanística",
    },
    {
        "path": "https://www.breadetajo.es/pdf/instancia_general.pdf",
        "tipo": "instancia general",
        "titulo": "Instancia general",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable|"
    r"comunicaci[oó]n previa|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|instancia general|ordenanza.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"concentraci[oó]n parcel|bando.*(?:suelo|parcela)|licencia(?:s)?(?: de)? obra|"
    r"estudio de detalle|modificaci[oó]n puntual|sector|ordenanza|"
    r"\b(?:UE|UA|SAU|S)-\d+)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|plusvalia|basura|"
    r"residuos|vehiculos|igualdad|iae\b|empleo|oposici[oó]n|navidad|carnaval|"
    r"piscina municipal|biblioteca|paddle|p[aá]del|front[oó]n|senda |ruta |"
    r"telemadrid|impuesto|tributo|cobranza de impuestos)",
)
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_WP_PDF = re.compile(
    r'href="(https://breadetajo\.es/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_AMBIT_CODE = re.compile(r"(?i)\b((?:UE|UA|SAU|S)-\d+[A-Z0-9-]*)\b")


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
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = (title or "").lower()
    if "sitcm" in n or re.search(r"\b(?:ue|ua|sau|s)-\d+", n):
        return "ámbito planeamiento"
    if "ordenanza" in n and "licencia" in n:
        return "ordenanza urbanística"
    if "informaci" in n and "p[uú]blica" in n:
        return "información pública"
    if "bando" in n:
        return "bando municipal"
    return "urbanismo"


class ValdaraceteBreaDeTajoYEstremeraAyuntamientoAdapter(AyuntamientoAdapter):
    """
    Slug compuesto BOCM: portales de Valdaracete (Joomla + eAdmin) y Brea de Tajo (WP + eAdmin).
    Estremera ya onboarded en slug `estremera`.
    """

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or VALDARACETE_WEB)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self._sitcm_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self._wp_posts: list[dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _load_sitcm_ambitos(self, wfs_municipio: str) -> dict[str, dict[str, Any]]:
        if wfs_municipio in self._sitcm_cache:
            return self._sitcm_cache[wfs_municipio]
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "50",
                "CQL_FILTER": f"DS_MUNICIPIO='{wfs_municipio}'",
            }
        )
        url = f"{WFS_BASE}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._sitcm_cache[wfs_municipio] = {}
            return self._sitcm_cache[wfs_municipio]
        cache: dict[str, dict[str, Any]] = {}
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "").strip()
            if name:
                cache[name.upper()] = feat
        self._sitcm_cache[wfs_municipio] = cache
        return cache

    def _geometry_from_ambit(self, wfs_municipio: str, ambit_name: str) -> dict[str, Any] | None:
        feat = self._load_sitcm_ambitos(wfs_municipio).get(ambit_name.upper())
        if not feat:
            return None
        merged = _merge_geometries([feat])
        if not merged:
            return None
        esc = ambit_name.replace("'", "''")
        cql = f"DS_MUNICIPIO='{wfs_municipio}' AND DS_NOMB_AMB='{esc}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "5",
                "CQL_FILTER": cql,
            }
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": f"{WFS_BASE}?{params}",
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": ambit_name,
        }

    def _fetch_geometry(self, wfs_municipio: str, title: str) -> dict[str, Any] | None:
        geom, meta = resolve_ambito_geometry(wfs_municipio, title)
        if geom:
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": WFS_BASE,
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": meta.get("ambito_name"),
            }
        title_up = (title or "").upper()
        for ambit_name in self._load_sitcm_ambitos(wfs_municipio):
            compact = ambit_name.replace("-", "").replace(" ", "")
            if ambit_name in title_up or compact in title_up.replace(" ", ""):
                return self._geometry_from_ambit(wfs_municipio, ambit_name)
        m = RE_AMBIT_CODE.search(title or "")
        if m:
            code = m.group(1).upper()
            for ambit_name in self._load_sitcm_ambitos(wfs_municipio):
                if code in ambit_name or ambit_name.startswith(code):
                    return self._geometry_from_ambit(wfs_municipio, ambit_name)
        return None

    def _enrich_geometry(self, rec: dict[str, Any], wfs_municipio: str) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(wfs_municipio, str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_sitcm_proyectos(self, municipio: str, wfs_municipio: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for ambit_name, feat in self._load_sitcm_ambitos(wfs_municipio).items():
            merged = _merge_geometries([feat])
            if not merged:
                continue
            titulo = f"Ámbito planeamiento SITCM — {ambit_name}"
            row: dict[str, Any] = {
                "id": _stable_id("proy", f"{wfs_municipio}-{ambit_name}"),
                "municipio": municipio,
                "titulo": titulo,
                "fecha": None,
                "tipo": _proyecto_tipo(titulo),
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sitcm_ambito",
            }
            geom = self._geometry_from_ambit(wfs_municipio, ambit_name)
            if geom:
                row.update(geom)
                centroid = geometry_centroid(geom["geom_geojson"])
                if centroid:
                    row["lat"], row["lon"] = centroid
            rows.append(row)
        return rows

    def _collect_valdaracete_licencia_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.config.get("valdaracete_licencia_pdfs") or DEFAULT_VALDARACETE_LICENCIA_PDFS:
            url = str(item["path"])
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": url,
                    "pdf_url": url,
                    "source": "ayuntamiento",
                    "municipio": "Valdaracete",
                    "origen": "valdaracete_vivienda",
                }
            )
        rows.append(
            {
                "id": _stable_id("lic", VALDARACETE_SEDE),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica Valdaracete (eAdmin Maggioli)",
                "url": f"{VALDARACETE_SEDE}/",
                "source": "ayuntamiento",
                "municipio": "Valdaracete",
                "origen": "sede_eadmin",
            }
        )
        return rows

    def _collect_brea_licencia_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.config.get("brea_licencia_pdfs") or DEFAULT_BREA_LICENCIA_PDFS:
            url = str(item["path"])
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": url,
                    "pdf_url": url,
                    "source": "ayuntamiento",
                    "municipio": "Brea de Tajo",
                    "origen": "brea_impresos",
                }
            )
        rows.append(
            {
                "id": _stable_id("lic", BREA_SEDE),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica Brea de Tajo (eAdmin Maggioli)",
                "url": f"{BREA_SEDE}/",
                "source": "ayuntamiento",
                "municipio": "Brea de Tajo",
                "origen": "sede_eadmin",
            }
        )
        return rows

    def _collect_valdaracete_pdfs_from_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in (VALDARACETE_VIVIENDA, VALDARACETE_NORMATIVA):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf_url = m.group(1).replace("&amp;", "&")
                if not pdf_url.lower().endswith(".pdf"):
                    continue
                titulo = Path(pdf_url).stem.replace("_", " ")
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(pdf_url),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": "valdaracete_web",
                        "municipio": "Valdaracete",
                        "wfs_municipio": "VALDARACETE",
                    }
                )
        return rows

    def _collect_brea_wp_posts(self) -> list[dict[str, Any]]:
        if self._wp_posts is not None:
            return self._wp_posts
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = f"{BREA_WP}/wp-json/wp/v2/posts?per_page=100&page={page}"
            try:
                posts = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(posts, list) or not posts:
                break
            for post in posts:
                title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                content = str((post.get("content") or {}).get("rendered") or "")
                blob = f"{title} {content[:6000]}"
                if RE_EXCLUDE.search(title) and not RE_PROYECTO.search(title):
                    continue
                if not RE_PROYECTO.search(blob):
                    continue
                link = str(post.get("link") or "")
                fecha = str(post.get("date") or "")[:10] or _fecha_from_blob(blob)
                pdfs = list(dict.fromkeys(RE_WP_PDF.findall(content)))
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": link,
                        "pdfs": pdfs,
                        "origen": "brea_wp",
                        "municipio": "Brea de Tajo",
                        "wfs_municipio": "BREA DE TAJO",
                    }
                )
            if len(posts) < 100:
                break
            page += 1
        self._wp_posts = rows
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        pdf = row.get("pdf_url") or (row.get("pdfs") or [None])[0]
        key = pdf or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": row.get("municipio") or "Valdaracete",
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if pdf:
            rec["pdf_url"] = pdf
        wfs = row.get("wfs_municipio") or "VALDARACETE"
        self._enrich_geometry(rec, wfs)
        return rec

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("pdf_url") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "municipio": row.get("municipio"),
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        wfs = row.get("wfs_municipio") or "VALDARACETE"
        self._enrich_geometry(rec, wfs)
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_valdaracete_licencia_docs() + self._collect_brea_licencia_docs():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_valdaracete_pdfs_from_pages() + self._collect_brea_wp_posts():
            rec = self._row_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_pdf"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        result = self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_sitcm_proyectos("Valdaracete", "VALDARACETE"):
            add(rec)
        for rec in self._collect_sitcm_proyectos("Brea de Tajo", "BREA DE TAJO"):
            add(rec)
        for row in self._collect_valdaracete_pdfs_from_pages():
            add(self._row_to_proyecto(row))
        for row in self._collect_brea_wp_posts():
            add(self._row_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sitcm": sum(1 for r in rows if r.get("origen") == "sitcm_ambito"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
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
