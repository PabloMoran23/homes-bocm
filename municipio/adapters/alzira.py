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

WEB_BASE = "https://alzira.es"
SEDE_BASE = "https://sedeelectronica.alzira.es/PortalCiudadano"
TABLON_URL = f"{SEDE_BASE}/tablonEdictos.do?formAction=btShowInfoTablonEdictos"
VISOR_GVSIG = "https://alzira.gvsigonline.com/gvsigonline/core/load/planeamiento/"
GVA_PG_INDEX = (
    "https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/"
    "4%20VALENCIA/46017%20ALZIRA/"
)
MUNICIPIO = "Alzira"
ID_PREFIX = "alzira"
COD_INE_MUN = "46017"

WP_CATEGORY_URBANISME = 1632
WP_CATEGORY_PLANEJAMENT = 1635

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/serveis-municipals/urbanisme-i-infraestructures/",
    f"{WEB_BASE}/serveis-municipals/urbanisme-i-infraestructures/planejament-i-informacio-urbanistica/",
    f"{WEB_BASE}/serveis-municipals/urbanisme-i-infraestructures/estudis-i-projectes/",
    f"{WEB_BASE}/serveis-municipals/urbanisme-i-infraestructures/registre-municipal-de-programes-i-aiu/",
    f"{WEB_BASE}/serveis-municipals/urbanisme-i-infraestructures/ordenances/",
    f"{WEB_BASE}/serveis-municipals/urbanisme-i-infraestructures/nous-tramits-amb-sense-ecuv/",
    GVA_PG_INDEX,
]

DEFAULT_SEDE_TRAMITES: list[dict[str, str]] = [
    {
        "titulo": "Tablón de anuncios y edictos — sede electrónica",
        "url": TABLON_URL,
    },
    {
        "titulo": "Declaración responsable — quemas restos vegetales núcleo urbano",
        "url": f"{SEDE_BASE}/tramites/tramite.do?formAction=btShow&t=3317",
    },
    {
        "titulo": "Catálogo de trámites — sección Urbanismo",
        "url": f"{SEDE_BASE}/tramites/tramite.do?formAction=btLista&seccion=27",
    },
    {
        "titulo": "Catálogo de trámites — Licencias, permisos y actividades",
        "url": f"{SEDE_BASE}/tramites/tramite.do?formAction=btLista&seccion=46",
    },
]

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER_SU = "ms:InventarioSuSuz"
ICV_LAYER_ZON = "Planeamiento.Zonificacion"
ICV_OFFSETS = list(range(0, 20000, 500))

RE_LICENCIA = re.compile(
    r"(?i)(licencia|llic[eè]ncia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|obra[s]? (?:mayor|menor)|primera ocupaci[oó]n|"
    r"impost.*construcc|taxa.*construcc|fotovoltaic|ecuv)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|normes urban|normativa urban|"
    r"informaci[oó]n p[uú]blica|expedient|projecte|expropi|modificaci[oó]n|reparcel|"
    r"estudi(?:s)? (?:de )?detall|sector|ue-|pp[i\-\s]|suz|minimitz|impacte territorial|"
    r"ordenan[cç]a|edict|conveni|registre.*aiu|programa.*aiu|visor|planejament)",
)
RE_NOISE = re.compile(
    r"(?i)(subvenci[oó]n|ivace|festa|m[uú]sica|cultural|empadron|empleo p[uú]blico|"
    r"pol[ií]gon industrial.*millora|obres de recuperaci[oó]|pla[cç]a d.alacant|"
    r"neteja de solars|farmac|bibliotec|arbre|economia|aigues potables|c[aà]ncer|"
    r"fotovoltaic.*centre de la ciutat)",
)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|PP[I]?|SD|SECTOR|PAI)[\s\-]?[\dA-ZÁÉÍÓÚ'._/\-]+)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_LINK = re.compile(r'href="([^"]+)"[^>]*>([^<]{6,300})</a>', re.I | re.S)
RE_GVA_LINK = re.compile(r'href="([^"]+)"[^>]*>([^<]+)</a>', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "expropi" in n:
        return "expropiación"
    if "minimitz" in n or "impacte territorial" in n:
        return "minimització impacte territorial"
    if "normes urban" in n or "normativa urban" in n:
        return "normas urbanísticas"
    if "ordenan" in n:
        return "ordenanza urbanística"
    if "plan parcial" in n or re.search(r"\bpp[\s\-]", n):
        return "plan parcial"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "registre" in n and "aiu" in n:
        return "registro AIU"
    if "visor" in n or "gvsig" in n:
        return "visor GIS"
    if "licencia" in n or "llic" in n:
        return "licencia / trámite"
    return "planeamiento"


def _sector_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for m in RE_SECTOR_TOKEN.finditer(text or ""):
        tok = _clean(m.group(1))
        if len(tok) >= 3:
            tokens.append(tok)
    return tokens


class AlziraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress alzira.es + sede inDenova + ICV WFS InventarioSuSuz (partial) + gvSIG visor."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.visor_url = str(self.config.get("visor_url") or VISOR_GVSIG)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.sede_tramites: list[dict[str, str]] = list(
            self.config.get("sede_tramites") or DEFAULT_SEDE_TRAMITES
        )
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer_su = str(geom_cfg.get("type_name_su") or ICV_LAYER_SU)
        self.icv_layer_zon = str(geom_cfg.get("type_name_zon") or ICV_LAYER_ZON)
        self.icv_offsets = list(geom_cfg.get("offsets") or ICV_OFFSETS)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or COD_INE_MUN)
        self._icv_cache: list[dict[str, Any]] | None = None
        self._icv_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90, retries: int = 3) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.config.get("user_agent", "poc-bocm-alzira/1.0"),
                    "Accept-Language": "ca,es;q=0.9",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, ConnectionResetError, TimeoutError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch_json(self, url: str, *, timeout: int = 120) -> Any:
        return json.loads(self._fetch(url, timeout=timeout))

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

    def _abs_web(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.web_base}{href if href.startswith('/') else '/' + href}"

    def _collect_wp_category(self, category_id: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = (
                f"{self.web_base}/wp-json/wp/v2/posts?"
                f"categories={category_id}&per_page=100&page={page}"
            )
            try:
                posts = self._fetch_json(url, timeout=60)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not posts:
                break
            for post in posts:
                title = _clean(post.get("title", {}).get("rendered") or "")
                link = (post.get("link") or "").strip()
                fecha = (post.get("date") or "")[:10] or None
                excerpt = _clean(post.get("excerpt", {}).get("rendered") or "")
                if not title or not link:
                    continue
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": link,
                        "fecha": fecha,
                        "origen": "wp_rest",
                        "blob": f"{title} {excerpt}",
                    }
                )
            page += 1
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url, timeout=90)
            except urllib.error.URLError:
                continue

            if "mediambient.gva.es" in page_url:
                for href, label in RE_GVA_LINK.findall(html):
                    label_clean = _clean(label)
                    blob = f"{label_clean} {href}".lower()
                    if not re.search(r"(?i)plan|pdf|general|diferido|norm", blob):
                        continue
                    doc_url = urllib.parse.urljoin(page_url, href)
                    if doc_url in seen:
                        continue
                    seen.add(doc_url)
                    rows.append(
                        {
                            "titulo": f"GVA planeamiento — {label_clean or Path(doc_url).name}",
                            "fecha": _parse_fecha_dmy(doc_url),
                            "url": doc_url,
                            "origen": "gva_registro",
                            "blob": blob,
                        }
                    )
                continue

            for href in RE_PDF.findall(html):
                pdf_url = self._abs_web(href)
                if pdf_url in seen:
                    continue
                name = urllib.parse.unquote(Path(pdf_url).name).lower()
                blob = f"{name} {page_url}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                seen.add(pdf_url)
                rows.append(
                    {
                        "titulo": _clean(name.replace("_", " ").replace("-", " "))[:500],
                        "fecha": _parse_fecha_dmy(pdf_url),
                        "url": pdf_url,
                        "origen": "wp_pdf",
                        "blob": blob,
                    }
                )

            for href, label in RE_LINK.findall(html):
                label_clean = _clean(label)
                if len(label_clean) < 8:
                    continue
                url = self._abs_web(href)
                if url in seen:
                    continue
                blob = f"{label_clean} {url}".lower()
                if not RE_PROYECTO.search(blob) and "gvsigonline" not in url:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": label_clean[:500],
                        "fecha": _parse_fecha_dmy(blob),
                        "url": url,
                        "origen": "wp_link",
                        "blob": blob,
                    }
                )
        return rows

    def _icv_wfs_url(self, type_name: str, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": type_name,
                "outputFormat": "application/json; subtype=geojson",
                "srsName": "EPSG:4326",
                "count": "500",
                "startIndex": str(start),
            }
        )
        return f"{self.icv_wfs_url}?{params}"

    def _feature_to_icv_row(self, feat: dict[str, Any], *, layer: str) -> dict[str, Any] | None:
        props = feat.get("properties") or {}
        if str(props.get("cod_ine_mun") or "") != self.cod_ine_mun:
            return None
        fid = str(props.get("id") or props.get("fid") or "")
        pp = _clean(str(props.get("pp") or ""))
        ue = _clean(str(props.get("ue") or ""))
        denom = _clean(str(props.get("denominaci") or props.get("denominaci_val") or ""))
        clas = _clean(str(props.get("clasificacion") or ""))
        f_aprob = props.get("f_aprob") or props.get("f_public")
        titulo = denom or pp or ue
        if ue and ue not in titulo:
            titulo = f"{titulo} ({ue})" if titulo else ue
        if not titulo:
            titulo = f"Sector {fid}"
        geom = feat.get("geometry")
        rec: dict[str, Any] = {
            "titulo": titulo[:500],
            "fecha": str(f_aprob)[:10] if f_aprob else None,
            "url": self.visor_url,
            "tipo": "sector SU/SUZ" if clas else "zonificación",
            "pp": pp or None,
            "ue": ue or None,
            "wfs_id": f"{layer}:{fid}",
            "origen": "icv_wfs",
            "blob": titulo,
        }
        if isinstance(geom, dict) and geom.get("coordinates"):
            rec["geom_geojson"] = geom
            rec["geometry_crs"] = "EPSG:4326"
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = self._icv_wfs_url(
                self.icv_layer_su if layer == "su" else self.icv_layer_zon,
                0,
            )
            rec["coord_source"] = "portal_geometry_centroid"
            cen = geometry_centroid(geom)
            if cen:
                rec["lat"], rec["lon"] = cen
        return rec

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._icv_cache is not None:
            return self._icv_cache
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for type_name, layer in ((self.icv_layer_su, "su"), (self.icv_layer_zon, "zon")):
            empty_pages = 0
            for start in self.icv_offsets:
                url = self._icv_wfs_url(type_name, start)
                try:
                    data = self._fetch_json(url, timeout=120)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                batch = data.get("features") or []
                if not batch:
                    break
                page_hits = 0
                for feat in batch:
                    rec = self._feature_to_icv_row(feat, layer=layer)
                    if rec and rec["wfs_id"] not in seen:
                        seen.add(rec["wfs_id"])
                        rows.append(rec)
                        page_hits += 1
                if page_hits == 0:
                    empty_pages += 1
                    if empty_pages >= 8:
                        break
                else:
                    empty_pages = 0
        self._icv_cache = rows
        self._icv_by_key = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if low:
                    self._icv_by_key[low] = rec
            for tok in _sector_tokens(rec.get("titulo") or ""):
                self._icv_by_key[tok.lower()] = rec
        return rows

    def _match_icv(self, text: str) -> dict[str, Any] | None:
        if self._icv_by_key is None:
            self._collect_icv_wfs()
        low = (text or "").lower()
        best: dict[str, Any] | None = None
        best_len = 0
        for key, rec in (self._icv_by_key or {}).items():
            if len(key) >= 4 and key in low and len(key) > best_len:
                best = rec
                best_len = len(key)
        if best:
            return best
        for tok in _sector_tokens(text):
            hit = (self._icv_by_key or {}).get(tok.lower())
            if hit:
                return hit
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "pp", "ue", "blob"))
        hit = self._match_icv(blob)
        if not hit:
            return
        for key in (
            "geom_geojson",
            "geometry_crs",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _sede_tramite_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": item["titulo"],
                "url": item["url"],
                "origen": "sede_tramite",
                "blob": item["titulo"],
            }
            for item in self.sede_tramites
        ]

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row.get("blob") or row.get("titulo") or ""):
            if row.get("origen") != "sede_tramite":
                return None
            if "tablón" not in (row.get("titulo") or "").lower():
                return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "trámite / edicto sede",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Páginas informativas sede inDenova; tablón sin listado HTML estático",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _wp_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_NOISE.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "noticia / normativa licencias",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("wfs_id") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        for key in (
            "pp",
            "ue",
            "wfs_id",
            "geom_geojson",
            "geometry_crs",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "wp_rest" and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "sede_tramite":
            return None
        if not RE_PROYECTO.search(blob) and row.get("origen") != "icv_wfs":
            return None
        return self._to_proyecto(row)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._sede_tramite_rows():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_wp_category(WP_CATEGORY_URBANISME):
            rec = self._wp_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_seed_pages():
            rec = self._wp_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_wp"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_icv_wfs():
            add(self._to_proyecto(item))
        for item in self._collect_wp_category(WP_CATEGORY_PLANEJAMENT):
            add(self._row_to_proyecto(item))
        for item in self._collect_wp_category(WP_CATEGORY_URBANISME):
            add(self._row_to_proyecto(item))
        for item in self._collect_seed_pages():
            add(self._row_to_proyecto(item))
        add(
            {
                "id": _stable_id("proy", self.visor_url),
                "municipio": MUNICIPIO,
                "titulo": "Visor cartográfico de planeamiento — gvSIG Online Alzira",
                "fecha": None,
                "tipo": "visor GIS",
                "url": self.visor_url,
                "source": "ayuntamiento",
                "origen": "visor",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "wp_rest": sum(1 for r in rows if r.get("origen") == "wp_rest"),
            "with_geometry": with_geom,
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **result}
