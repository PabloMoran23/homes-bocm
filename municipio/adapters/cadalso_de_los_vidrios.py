from __future__ import annotations

import hashlib
import http.cookiejar
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
from municipio.geometry import geometry_centroid, record_geometry
from municipio.gis.sitcm import _merge_geometries

SEDE_BASE = "https://cadalsodelosvidrios.sedelectronica.es"
WEB_BASE = "http://www.cadalsodelosvidrios.es"
MUNICIPIO = "Cadalso de los Vidrios"
ID_PREFIX = "cadalso-de-los-vidrios"

URBANISMO_URL = f"{WEB_BASE}/áreas-de-gobierno/ordenacion-territorial"
NORMATIVA_URL = f"{WEB_BASE}/trámites-y-gestiones/normativa-municipal"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "CADALSO DE LOS VIDRIOS"

RE_CATALOG = re.compile(
    r'href="((?:https://cadalsodelosvidrios\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|apertura actividad|tasa.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|estudio de detalle|modificaci[oó]n|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|reparcel|sector|edicto|bocm|"
    r"actuaci[oó]n urban|cesi[oó]n.*bien|ordenanza|disposici[oó]n normativa|"
    r"\b(?:S|UA)-\d+[A-Z0-9-]*\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|iae\b|plusval[ií]a|calendario fiscal|jurado|presupuest|"
    r"selecci[oó]n de personal|funcionario|bii\b|residuos|convocatoria.*pleno|"
    r"bolsa de trabajo|socorrista|concesi[oó]n administrativa.*bar|convivencia ciudadana)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UA|S)-\d+[A-Z0-9-]*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _sector_ilike_parts(text: str) -> list[str]:
    s = text.strip()
    low = s.lower()
    for marker in (" del pgou", " pgou", " bocm", " aprob", " anuncio"):
        if marker in low:
            s = s[: low.index(marker)]
            break
    parts = [p for p in re.split(r"[\s,;/|]+", s) if len(p) >= 2]
    return parts[:6]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if re.search(r"(?i)planeamiento|pgou|plan parcial|plan especial", blob):
        return "planeamiento"
    if re.search(r"(?i)bocm", blob):
        return "publicación BOCM"
    if re.search(r"(?i)ordenanza", blob):
        return "ordenanza"
    if re.search(r"(?i)cesi[oó]n", blob):
        return "cesión patrimonial"
    if re.search(r"\bua-\w+\b", n) or re.search(r"\bs-\d+\b", n):
        return "ámbito planeamiento"
    return "urbanismo"


class CadalsoDeLosVidriosAyuntamientoAdapter(AyuntamientoAdapter):
    """BaseKit web + sede espublico tablón + WFS SITCM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency"
        )
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _parse_board_rows(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tr in re.findall(r"<tr>\s*(.*?)\s*</tr>", html, re.I | re.S):
            cells = re.findall(
                r'class="([^"]+)"[^>]*data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
                tr,
                re.I | re.S,
            )
            if not cells:
                continue
            row: dict[str, Any] = {}
            for _cls, label, val in cells:
                row[label] = _strip_html(val)
            link_m = re.search(r"preview-document/([a-f0-9-]+)", tr, re.I)
            if not link_m:
                continue
            uuid = link_m.group(1)
            if uuid in seen:
                continue
            seen.add(uuid)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else row.get("Documento", "")
            row.update(
                {
                    "titulo": titulo[:500] or row.get("Documento", "")[:500],
                    "expediente": row.get("Expediente", ""),
                    "procedimiento": row.get("Procedimiento", ""),
                    "categoria": row.get("Categoría", ""),
                    "descripcion": row.get("Descripción", ""),
                    "fecha": _parse_fecha_dmy(row.get("Fecha de Publicación", "")),
                    "url": f"{self.sede_base}/preview-document/{uuid}",
                    "pdf_url": f"{self.sede_base}/preview-document/{uuid}",
                    "origen": "tablon",
                }
            )
            rows.append(row)
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            self._fetch(f"{self.sede_base}/info.0")
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board_rows(html)

    def _collect_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in ("/dossier.0", "/dossier"):
            try:
                html = self._fetch(f"{self.sede_base}{path}")
            except urllib.error.URLError:
                continue
            for m in RE_CATALOG.finditer(html):
                href, titulo = m.group(1), unescape(m.group(2).strip())
                url = href if href.startswith("http") else f"{self.sede_base}{href}"
                if url in seen:
                    continue
                seen.add(url)
                if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                    continue
                rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _collect_web_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in (self.urbanismo_url, NORMATIVA_URL):
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                href = unescape(m.group(1))
                pdf_url = href if href.startswith("http") else urllib.parse.urljoin(f"{page}/", href)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = Path(urllib.parse.unquote(pdf_url)).stem.replace("_", " ").replace("-", " ")
                rows.append(
                    {
                        "titulo": name[:500],
                        "url": page,
                        "pdf_url": pdf_url,
                        "origen": "web_pdf",
                    }
                )
        return rows

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache.setdefault(name.upper(), f)
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache.setdefault(code_m.group(1).upper(), f)
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        if RE_EXCLUDE.search(title):
            return None

        cache = self._load_wfs_ambitos()
        candidates: list[tuple[float, str, dict[str, Any]]] = []

        for m in RE_AMBIT_CODE.finditer(title):
            code = m.group(1).upper()
            feat = cache.get(code)
            if feat:
                candidates.append((100.0, code, feat))

        parts = _sector_ilike_parts(title)
        muni = self.wfs_municipio.replace("'", "''")
        if parts:
            pattern = "%" + "%".join(p.replace("'", "''") for p in parts[:6]) + "%"
            feats = self._wfs_query(
                f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB ILIKE '{pattern}'",
                count=10,
            )
            title_low = title.lower()
            for f in feats:
                name = str((f.get("properties") or {}).get("DS_NOMB_AMB") or "")
                if not name:
                    continue
                score = sum(5 for p in parts if p.lower() in name.lower())
                if name.lower() in title_low:
                    score += 30
                candidates.append((float(score), name, f))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x[0], x[1]))
        best_score, best_name, _ = candidates[0]
        if best_score < 5:
            return None

        same_name = [
            f
            for _, name, f in candidates
            if str((f.get("properties") or {}).get("DS_NOMB_AMB") or "") == best_name
        ]
        if not same_name:
            same_name = [candidates[0][2]]

        merged = _merge_geometries(same_name)
        if not merged:
            return None

        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
            f"AND DS_NOMB_AMB='{best_name.replace(chr(39), chr(39)*2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": best_name,
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        rows: list[dict[str, Any]] = []
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([f])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39)*2)}'"
                )
                rec["geometry_source_url"] = (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                )
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(merged)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y exposiciones públicas publicadas en sede electrónica",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación Cl@ve; no hay listado público",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "formularios licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenación territorial — solicitud de licencias",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Formularios PDF (instancia, licencia obra mayor/menor)",
                "origen": "web_formularios",
            },
        ]

    def _collect_transparency_info(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", self.transparency_url),
            "municipio": MUNICIPIO,
            "titulo": "Portal transparencia sede — Urbanismo",
            "fecha": None,
            "tipo": "documentación urbanismo",
            "url": self.transparency_url,
            "source": "ayuntamiento",
            "nota": "Sección 7 urbanismo (0 documentos en sede al momento de investigación)",
            "origen": "transparencia",
        }

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_EXCLUDE.search(blob) and not re.search(
            r"(?i)exposici[oó]n p[uú]blica|informaci[oó]n p[uú]blica|bocm|cesi[oó]n", blob
        ):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() in ("urbanismo", "ordenanzas y reglamentos"):
            pass
        elif not RE_PROYECTO.search(blob):
            if row.get("categoria") != "Órganos de gobierno":
                return None
            if not re.search(r"(?i)pleno|convocatoria|acuerdo", blob):
                return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite en sede",
            "origen": row.get("origen"),
        }

    def _pdf_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if not RE_LICENCIA.search(blob) and "instancia" not in blob.lower():
            return None
        tipo = "formulario licencia"
        if re.search(r"(?i)obra mayor", blob):
            tipo = "licencia obra mayor"
        elif re.search(r"(?i)obra menor", blob):
            tipo = "licencia obra menor"
        elif re.search(r"(?i)instancia", blob):
            tipo = "instancia general"
        return {
            "id": _stable_id("lic", row.get("pdf_url") or row["url"]),
            "fecha_concesion": None,
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "nota": "Formulario/solicitud; no concesión publicada",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_licencia_info_pages():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_licencia(item))
        for item in self._collect_tramites():
            add(self._tramite_to_licencia(item))
        for item in self._collect_web_pdfs():
            add(self._pdf_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(
                1
                for r in rows
                if r.get("origen") in ("sede_tablon", "sede_tramite", "web_formularios", "catalogo_tramites", "web_pdf")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_web_pdfs():
            rec = self._pdf_to_licencia(item)
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

        add(self._collect_transparency_info())
        for rec in self._collect_sit_ambitos():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_tramites():
            if RE_PROYECTO.search(item["titulo"]):
                add(
                    {
                        "id": _stable_id("proy", item["url"]),
                        "municipio": MUNICIPIO,
                        "titulo": item["titulo"],
                        "fecha": None,
                        "tipo": "trámite urbanismo",
                        "url": item["url"],
                        "source": "ayuntamiento",
                        "origen": item.get("origen"),
                    }
                )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
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
