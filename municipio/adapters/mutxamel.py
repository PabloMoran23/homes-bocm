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
from urllib.parse import unquote

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WP_BASE = "https://ayto.mutxamel.org"
SEDE_BASE = "https://sedeelectronica.mutxamel.org/eAdmin"
TABLON_URL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
CATALOGO_URL = f"{WP_BASE}/area/sede-electronica/catalogo-de-procedimientos/"
MUNICIPIO = "Mutxamel"
ID_PREFIX = "mutxamel"
INE_MUN = "03090"

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_TYPE = "ms:InventarioSuSuz"
GVA_PLANEAMIENTO_INDEX = (
    "https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/"
    "2%20ALICANTE/03090%20MUTXAMEL/"
)
VISOR_ICV = "https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/area/urbanismo/",
    f"{WP_BASE}/area/transparencia/obras-urbanismo-y-medio-ambiente/",
    f"{WP_BASE}/area/transparencia/normativa-y-relevancia-juridica/",
    CATALOGO_URL,
    GVA_PLANEAMIENTO_INDEX,
]

RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td[^>]*>.*?verAnuncio&id=([A-F0-9]+).*?</td>\s*<td[^>]*>\s*(.*?)\s*<br>.*?Periodo:</span>\s*([^<]+)</td>",
    re.I | re.S,
)
RE_DOC_TOKEN = re.compile(r"abrirOriginal\('([^']+)'\)")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| ambiental)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|licencia ambiental)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|nn\.?ss|normas subsidiarias|convenio|"
    r"informaci[oó]n p[uú]blica|consulta (?:p[uú]blica|previa)|expediente|proyecto|modificaci[oó]n|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|territorial)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|rio park|"
    r"cambio de uso|pri\b|pgou|eate|ovp|venta no sedentaria)",
)
RE_SKIP = re.compile(
    r"(?i)(rrhh|proceso selectivo|bolsa de|empleo p[uú]blico|podolog|bono peus|"
    r"cobranza.*voluntaria|prestaciones econ[oó]micas de urgencia|venta no sedentaria mercados)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="(https://ayto\.mutxamel\.org/wp-content/uploads/[^"]+\.pdf[^"]*)"', re.I)
RE_TRAMITE = re.compile(
    r'SE(\d{3})</span></a></div><div class="w-post-elm post_title[^"]*"[^>]*>'
    r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)',
    re.I | re.S,
)
RE_GVA_LINK = re.compile(r'href="([^"]+)"[^>]*>([^<]+)</a>', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


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
    m = re.search(r"/uploads/(\d{4})/(\d{2})/", text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and ("nnss" in n or "normas subsidiarias" in n):
        return "modificación normas subsidiarias"
    if "rio park" in n or "pri" in n:
        return "plan de reforma interior"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "consulta" in n and ("pública" in n or "previa" in n):
        return "consulta pública"
    if "licencia ambiental" in n:
        return "licencia ambiental"
    if re.search(r"\bue[\-\s]?\d+", n) or "unidad de ejecuci" in n:
        return "unidad de ejecución"
    if "sector" in n or "plan parcial" in n:
        return "sector / plan parcial"
    if "planeam" in n or "nnss" in n:
        return "planeamiento"
    return "urbanismo"


def _pdf_url(sede_base: str, token: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(token, safe='')}&tipo=doc&mode=ori"
    )


class MutxamelAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress ayto.mutxamel.org + sede eAdmin tablón + ICV InventarioSuSuz WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_type = str(geom_cfg.get("type_name") or ICV_TYPE)
        self.ine_mun = str(self.config.get("cod_ine_mun") or INE_MUN)
        self._wfs_max_scan = int(self.config.get("wfs_max_scan", 20_000))
        self._wfs_empty_streak = int(self.config.get("wfs_empty_streak", 30))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-mutxamel/1.0"),
                "Accept-Language": "es,ca;q=0.9",
            },
        )
        ctx = self._ssl_ctx if "sedeelectronica.mutxamel.org" in url else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-mutxamel/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_wp(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.wp_base}/", href))

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, period_raw = m.groups()
            title = _clean_title(_strip_html(title_raw))
            if not title or RE_SKIP.search(title):
                continue
            row_html = m.group(0)
            doc_m = RE_DOC_TOKEN.search(row_html)
            period_m = RE_PERIOD.search(period_raw or "")
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec: dict[str, Any] = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha": fecha_ini,
                "url": detail_url,
                "origen": "tablon_eadmin",
                "blob": title,
            }
            if doc_m:
                rec["pdf_url"] = _pdf_url(self.sede_base, doc_m.group(1))
            rows.append(rec)
        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_TRAMITE.finditer(html):
            code, href, title = m.group(1), m.group(2), _clean_title(m.group(3))
            titulo = f"SE{code} — {title}"
            rows.append(
                {
                    "titulo": titulo,
                    "url": href,
                    "origen": "catalogo_tramites",
                    "blob": titulo,
                }
            )
        return rows

    def _collect_web_docs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        urban_kw = (
            "urban",
            "planeam",
            "licen",
            "obra",
            "nnss",
            "rio",
            "park",
            "modific",
            "informacion",
            "edicto",
            "ambient",
            "convenio",
            "eate",
            "normas",
            "oflicurb",
            "obras",
        )
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url, timeout=90)
            except urllib.error.URLError:
                continue

            if "mediambient.gva.es" in page_url:
                for href, label in RE_GVA_LINK.findall(html):
                    label_clean = _strip_html(label)
                    if not re.search(r"(?i)plan|pdf|general|diferido|norm", label_clean + href):
                        continue
                    doc_url = urllib.parse.urljoin(page_url, href)
                    if doc_url in seen:
                        continue
                    seen.add(doc_url)
                    rows.append(
                        {
                            "titulo": f"GVA planeamiento — {label_clean or Path(doc_url).name}",
                            "fecha": _fecha_from_blob(doc_url),
                            "url": doc_url,
                            "page_url": page_url,
                            "origen": "gva_registro",
                            "blob": f"{label_clean} {doc_url}",
                        }
                    )
                continue

            for href in RE_PDF_HREF.findall(html):
                if href in seen:
                    continue
                name = unquote(Path(href).name).lower()
                if not any(k in name for k in urban_kw):
                    continue
                seen.add(href)
                titulo = _clean_title(unquote(Path(href).name).replace("_", " ").replace("-", " "))
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(href),
                        "url": href,
                        "pdf_url": href,
                        "page_url": page_url,
                        "origen": "wp_transparencia",
                        "blob": f"{titulo} {page_url}",
                    }
                )

            text_blocks = re.findall(
                r'<a[^>]+href="([^"]+)"[^>]*>([^<]{8,200})</a>',
                html,
                re.I | re.S,
            )
            for href, label in text_blocks:
                label_clean = _strip_html(label)
                blob = f"{label_clean} {href}".lower()
                if not RE_PROYECTO.search(blob):
                    continue
                url = self._abs_wp(href) if href.startswith("/") else href
                if url in seen:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": label_clean[:500],
                        "fecha": _fecha_from_blob(url),
                        "url": url,
                        "page_url": page_url,
                        "origen": "wp_link",
                        "blob": blob,
                    }
                )
        return rows

    def _wfs_feature_url(self, feature_id: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.icv_type,
                "outputFormat": "application/json; subtype=geojson",
                "srsName": "EPSG:4326",
                "count": "1",
                "featureId": feature_id,
            }
        )
        return f"{self.icv_wfs}?{params}"

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache

        rows: list[dict[str, Any]] = []
        start = 0
        empty_streak = 0
        while start < self._wfs_max_scan:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeName": self.icv_type,
                    "outputFormat": "application/json; subtype=geojson",
                    "srsName": "EPSG:4326",
                    "count": "200",
                    "STARTINDEX": str(start),
                }
            )
            url = f"{self.icv_wfs}?{params}"
            try:
                data = self._fetch_json(url, timeout=120)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            feats = data.get("features") or []
            if not feats:
                break
            page_hits = 0
            for feat in feats:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                if str(props.get("cod_ine_mun") or "") != self.ine_mun:
                    continue
                page_hits += 1
                pp = _clean_title(str(props.get("pp") or ""))
                ue = _clean_title(str(props.get("ue") or ""))
                clas = _clean_title(str(props.get("clasificacion") or ""))
                titulo = pp or ue or clas or "Ámbito planeamiento ICV"
                if ue and ue not in titulo:
                    titulo = f"{titulo} — {ue}".strip(" —")
                fecha = props.get("f_aprob") or props.get("f_public")
                fid = str(feat.get("id") or props.get("id") or f"{pp}:{ue}")
                geom = feat.get("geometry")
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", f"icv:{fid}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(f"{pp} {ue} {clas}"),
                    "url": VISOR_ICV,
                    "source": "ayuntamiento",
                    "origen": "icv_wfs",
                    "clasificacion": clas or None,
                    "pp": pp or None,
                    "ue": ue or None,
                }
                if isinstance(geom, dict) and geom.get("coordinates"):
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = self._wfs_feature_url(fid)
                    rec["coord_source"] = "portal_geometry_centroid"
                    cen = geometry_centroid(geom)
                    if cen:
                        rec["lat"], rec["lon"] = cen
                rows.append(rec)
            if page_hits == 0:
                empty_streak += 1
            else:
                empty_streak = 0
            start += len(feats)
            if len(feats) < 200:
                break
            if empty_streak >= self._wfs_empty_streak:
                break

        self._wfs_cache = rows
        return rows

    def _match_wfs_geometry(self, titulo: str) -> dict[str, Any] | None:
        norm = re.sub(r"\s+", " ", titulo.upper())
        best: tuple[float, dict[str, Any]] | None = None
        for wfs in self._collect_wfs_proyectos():
            cand = str(wfs.get("titulo") or "").upper()
            score = 0.0
            if cand and cand in norm:
                score = 100.0
            else:
                for token in re.split(r"[^A-Z0-9]+", cand):
                    if len(token) >= 5 and token in norm:
                        score += 15.0
            if score > 0 and (best is None or score > best[0]):
                best = (score, wfs)
        if best and best[0] >= 30 and best[1].get("geom_geojson"):
            return best[1]
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        match = self._match_wfs_geometry(str(rec.get("titulo") or ""))
        if not match:
            return
        for key in (
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if match.get(key) is not None:
                rec[key] = match[key]

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios (eAdmin)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Mutxamel",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios; sin listado histórico de concesiones de licencia",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.wp_base}/wp-content/uploads/2023/11/oflicurb.pdf"),
                "fecha_concesion": None,
                "tipo": "impreso licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenanza fiscal licencias urbanísticas (OF licencias)",
                "url": f"{self.wp_base}/wp-content/uploads/2023/11/oflicurb.pdf",
                "source": "ayuntamiento",
                "origen": "wp_impreso",
            },
            {
                "id": _stable_id("lic", "https://governalia.com/launch/mutxamel"),
                "fecha_concesion": None,
                "tipo": "trámites licencia (Governalia)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede Governalia — trámites urbanismo y licencias",
                "url": "https://governalia.com/launch/mutxamel",
                "source": "ayuntamiento",
                "origen": "governalia",
            },
        ]

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('blob', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("pdf_url") or row.get("ann_id") or row.get("url")
        return {
            "id": _stable_id("lic", str(key)),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / edicto",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if not re.search(r"(?i)obra|urban|licen|declar", titulo):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia / obra",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Formulario o ZIP del catálogo de procedimientos",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('blob', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("ann_id") or row.get("url")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", str(key)),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
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

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._licencia_info_pages():
            add(rec)
        for row in self._collect_tablon():
            add(self._row_to_licencia(row))
        for row in self._collect_tramites():
            add(self._tramite_to_licencia(row))
        for row in self._collect_web_docs():
            add(self._row_to_licencia(row))
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._collect_tablon():
            add(self._row_to_proyecto(row))
        for row in self._collect_web_docs():
            add(self._row_to_proyecto(row))
        for rec in self._collect_wfs_proyectos():
            add(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon_wp_tramites"}

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
        return {"rows": len(rows), "status": "ok", "source": "tablon_wp_icv_wfs"}

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
