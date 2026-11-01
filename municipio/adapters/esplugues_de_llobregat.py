from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.esplugues.cat"
SEDE_BASE = "https://sede.esplugues.cat"
MUNICIPIO = "Esplugues de Llobregat"
ID_PREFIX = "esplugues"
INE_MUN = "08077"
URBANISME_CATEGORY_ID = 188

AMB_EXP_LAYER = (
    "https://geoportal.amb.cat/geoserveisapp/rest/services/"
    "Planejament/Expedients/MapServer/3"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/serveis/urbanisme/",
    f"{WEB_BASE}/ajuntament/ordenances-normatives-tauler-anuncis/",
    f"{WEB_BASE}/serveis/directori-serveis/servei-de-gestio-urbanistica/",
    "https://cido.diba.cat/normativa_local/6638561/planejament-urbanistic-ajuntament-desplugues-de-llobregat",
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (
        f"{SEDE_BASE}/portal/literal.do?opc_id=10047&pes_cod=8&ent_id=1&idioma=2",
        "Sede — llicències d'obra (pestanya urbanisme)",
    ),
    (
        f"{SEDE_BASE}/portal/literal.do?opc_id=10088&pes_cod=8&ent_id=1&idioma=2",
        "Sede — comunicats d'obra / obra menor",
    ),
    (
        f"{SEDE_BASE}/portal/noEstatica.do?opc_id=190&asu_mod_cod=44&asu_cod=251&asunto=11",
        "Sede — consulta prèvia d'urbanisme",
    ),
    (
        f"{SEDE_BASE}/portal/tablonVirtual.do?subseccion=TABLONVIRTUAL&opc_id=175&pes_cod=4&ent_id=1&idioma=2",
        "Sede — tabló virtual d'anuncis",
    ),
    (f"{WEB_BASE}/serveis/urbanisme/", "Web municipal — urbanisme (tràmits i enllaços)"),
    (f"{WEB_BASE}/cita-previa/", "Cita prèvia — llicències i planejament"),
]

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "llicència d'obres",
    "licencia de obras",
    "llicència d'activitat",
    "comunicació previa",
    "comunicacion previa",
    "declaració responsable",
    "obra menor",
    "obres majors",
    "obra major",
    "enderroc",
    "llicència urbanística",
    "licencia urbanística",
    "primera ocupació",
    "disciplina urbanística",
)

RE_LICENCIA = re.compile(
    r"(?i)(licen[cs]i[ao]|llicen[cs]i[ao]|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:major|menor)|enderroc|segregaci|comunicat d.?obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|planej|plan (?:parcial|especial|general)|pgou|pgm|mpgm|conveni|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n|expedient|reparcel|modificaci[oó]n|"
    r"delimitaci|gesti[oó] urban|sector|àmbit|ambit|reurbanitz|peatge|ref[oò]s|"
    r"pe\b|pp\b|ordenan[cç]a|visor|geoportal|cido|tabl[oó])",
)
RE_WP_NOISE = re.compile(
    r"(?i)(protocol de col|signen un protocol|policia local|piscina|festa major|"
    r"subvenci[oó]|eleccions|empadronament)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_EXPTE = re.compile(
    r"(?i)(?:exp(?:te)?\.?|expedient|n[uú]m(?:ero)?\.?\s*exp(?:edient)?)\s*[:\.]?\s*"
    r"(\d{1,4}/[A-Z0-9-]+(?:\s+\d{4}/\d+[A-Z]?)?|\d{4}/\d+[A-Z]?)",
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_WP_PDF = re.compile(
    r'href="(https://www\.esplugues\.cat/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _strip_html(text: str) -> str:
    return _clean_title(re.sub(r"<[^>]+>", " ", text or ""))


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    m = RE_FECHA_ISO.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "mpgm" in n or "pgm" in n or "pla general metropolit" in n:
        return "modificación PGM"
    if "plan parcial" in n or "pla parcial" in n or re.search(r"\bpp\b", n):
        return "plan parcial"
    if "plan especial" in n or "pla especial" in n or re.search(r"\bpe\b", n):
        return "plan especial"
    if "reparcel" in n:
        return "reparcelación"
    if "reurbanitz" in n:
        return "reurbanización"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "consulta pr" in n:
        return "consulta previa"
    if "refós" in n or "refos" in n:
        return "refós planeamiento"
    return "planeamiento"


class EspluguesDeLlobregatAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress esplugues.cat + sede Indenova (STA) + AMB ArcGIS expedients."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pages = [
            tuple(x) for x in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        ]
        self.wp_categories = [int(x) for x in (self.config.get("wp_categories") or [URBANISME_CATEGORY_ID])]
        self.wp_max_pages = int(self.config.get("wp_max_pages", 3))
        self.catalogo_url = str(
            self.config.get("catalogo_url")
            or f"{self.sede_base}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_CATSERV&lang=CA"
        )
        geom_cfg = self.config.get("geometry") or {}
        self.amb_exp_layer = str(geom_cfg.get("arcgis_expedients_layer") or AMB_EXP_LAYER)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._amb_cache: list[dict[str, Any]] | None = None
        self._amb_by_norm_name: dict[str, dict[str, Any]] | None = None

    def _ua(self) -> str:
        return str(self.config.get("user_agent") or "poc-bocm-esplugues-de-llobregat/1.0")

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        with urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_CATSERV&lang=CA"
        )

    def _catalog_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url, timeout=45)
        except urllib.error.URLError:
            return []
        if not html.strip():
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            dboid = str(item.get("dboid") or "")
            name = _clean_title(str(item.get("name") or ""))
            if not name or not dboid:
                continue
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites_sta",
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for cat in self.wp_categories:
            for page in range(1, self.wp_max_pages + 1):
                url = (
                    f"{self.web_base}/wp-json/wp/v2/posts"
                    f"?categories={cat}&per_page=100&page={page}"
                    f"&_fields=id,date,link,title,content,excerpt"
                )
                try:
                    data = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(data, list) or not data:
                    break
                for post in data:
                    pid = int(post.get("id") or 0)
                    if pid in seen:
                        continue
                    seen.add(pid)
                    title = _strip_html(post.get("title", {}).get("rendered", ""))
                    content = post.get("content", {}).get("rendered", "") or ""
                    excerpt = post.get("excerpt", {}).get("rendered", "") or ""
                    pdf_m = RE_WP_PDF.search(content)
                    rows.append(
                        {
                            "titulo": title[:500],
                            "fecha": (post.get("date") or "")[:10] or None,
                            "url": post.get("link") or "",
                            "pdf_url": pdf_m.group(1) if pdf_m else None,
                            "nota": _strip_html(excerpt)[:400],
                            "origen": f"wp_category_{cat}",
                        }
                    )
                if len(data) < 100:
                    break
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url, timeout=60)
            except urllib.error.URLError:
                continue
            page_title = _strip_html(re.search(r"<title>([^<]+)", html, re.I).group(1)) if re.search(
                r"<title>([^<]+)", html, re.I
            ) else page_url
            for pdf in RE_PDF.findall(html):
                pdf_url = self._abs_web(pdf)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = Path(urllib.parse.urlparse(pdf_url).path).name
                rows.append(
                    {
                        "titulo": f"{page_title} — {name}"[:500],
                        "fecha": _parse_fecha_dmy(pdf_url) or _parse_fecha_dmy(html[:8000]),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": "wp_seed_pdf",
                    }
                )
        return rows

    def _load_amb_expedients(self) -> list[dict[str, Any]]:
        if self._amb_cache is not None:
            return self._amb_cache
        features: list[dict[str, Any]] = []
        offset = 0
        page_size = 100
        base_query = (
            f"{self.amb_exp_layer}/query?"
            f"where=CODI_INE%3D%27{self.ine_mun}%27"
            "&outFields=NOMEXP%2CDGU%2CCMB%2CURL%2CDAPRDEF%2CVIGENT"
            "&returnGeometry=true&outSR=4326&f=geojson"
        )
        while True:
            url = f"{base_query}&resultOffset={offset}&resultRecordCount={page_size}"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            batch = data.get("features") or []
            if not batch:
                break
            features.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        self._amb_cache = features
        by_name: dict[str, dict[str, Any]] = {}
        for feat in features:
            props = feat.get("properties") or {}
            nom = str(props.get("NOMEXP") or "").strip()
            if not nom:
                continue
            by_name[_norm_text(nom)] = feat
        self._amb_by_norm_name = by_name
        return features

    def _amb_hit_for_blob(self, blob: str) -> dict[str, Any] | None:
        self._load_amb_expedients()
        by_name = self._amb_by_norm_name or {}
        norm_blob = _norm_text(blob)
        for nom_norm, feat in by_name.items():
            if len(nom_norm) >= 8 and nom_norm in norm_blob:
                return feat
        tokens = [t for t in re.split(r"[\s,;/|()]+", norm_blob) if len(t) >= 5]
        best: dict[str, Any] | None = None
        best_score = 0
        for nom_norm, feat in by_name.items():
            nom_tokens = [t for t in re.split(r"[\s,;/|()]+", nom_norm) if len(t) >= 4]
            score = sum(1 for t in nom_tokens if t in norm_blob)
            if score > best_score and score >= 2:
                best_score = score
                best = feat
        return best

    def _apply_amb_geometry(self, rec: dict[str, Any], feat: dict[str, Any], query_url: str) -> None:
        geom = feat.get("geometry")
        if not isinstance(geom, dict) or geom.get("type") not in {"Polygon", "MultiPolygon"}:
            return
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_axis_order"] = "xy"
        rec["geometry_source"] = "portal_visor_arcgis"
        rec["geometry_source_url"] = query_url
        rec["coord_source"] = "portal_geometry_centroid"
        cent = geometry_centroid(geom)
        if cent:
            rec["lat"], rec["lon"] = cent

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = f"{rec.get('titulo', '')} {rec.get('nota', '')} {rec.get('expte', '')}"
        feat = self._amb_hit_for_blob(blob)
        if feat:
            self._apply_amb_geometry(rec, feat, f"{self.amb_exp_layer}/query")

    def _amb_to_proyecto(self, feat: dict[str, Any]) -> dict[str, Any]:
        props = feat.get("properties") or {}
        nom = _clean_title(str(props.get("NOMEXP") or "Expediente urbanístico"))
        dgu = str(props.get("DGU") or "").strip()
        url = str(props.get("URL") or "").strip() or f"{self.web_base}/serveis/urbanisme/"
        key = dgu or nom
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"amb:{key}"),
            "municipio": MUNICIPIO,
            "titulo": nom,
            "fecha": _parse_fecha_dmy(str(props.get("DAPRDEF") or "")),
            "tipo": _proyecto_tipo(nom),
            "url": url,
            "source": "ayuntamiento",
            "origen": "amb_expedients_gis",
        }
        if dgu:
            rec["expte"] = dgu
        vigent = str(props.get("VIGENT") or "").strip()
        if vigent:
            rec["estado"] = vigent
        self._apply_amb_geometry(rec, feat, f"{self.amb_exp_layer}/query")
        return rec

    def _collect_amb_proyectos(self) -> list[dict[str, Any]]:
        return [self._amb_to_proyecto(f) for f in self._load_amb_expedients()]

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('nota', '')}"
        if RE_WP_NOISE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("nota"):
            rec["nota"] = row["nota"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        m = RE_EXPTE.search(blob)
        if m:
            rec["expte"] = m.group(1).strip()
        self._enrich_geometry(rec)
        return rec

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        lower = titulo.lower()
        if not any(p in lower for p in LICENCIA_TRAMITE_PATTERNS) and not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Catálogo STA sede.esplugues.cat",
            "origen": row.get("origen"),
        }

    def _informative_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo in self.licencia_pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Sin listado público de licencias concedidas; enlace sede/web",
                    "origen": "pagina_informativa",
                }
            )
        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for row in self._catalog_rows():
            rec = self._tramite_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        if not rows:
            for rec in self._informative_licencias():
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_amb_proyectos():
            add(rec)
        for row in self._collect_wp_posts():
            add(self._row_to_proyecto(row))
        for row in self._collect_seed_pdfs():
            add(self._row_to_proyecto(row))
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
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
