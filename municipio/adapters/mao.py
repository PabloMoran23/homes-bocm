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
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.ajmao.org"
SEDE_BASE = "https://www.carpetaciutadana.org/mao"
TABLON_URL = f"{WEB_BASE}/tauler/edictesx.aspx?tipo=01"
TABLON_HIST_URL = f"{WEB_BASE}/tauler/edictesx.aspx?tipo=01&HISTORIC=1"
URBANISMO_AREA = f"{WEB_BASE}/Publicacions/Area.aspx?ID=29"
PGOU_URL = f"{WEB_BASE}/Contingut.aspx?IdPub=12029"
NORMATIVA_TRAMIT = f"{WEB_BASE}/contingut.aspx?IdPub=33367"
CONSULTA_PUBLICA = f"{WEB_BASE}/contingut.aspx?IdPub=33371"
VISOR_IDE = "https://ide.cime.es/visor/"
MUNICIPIO = "Maó"
ID_PREFIX = "mao"
MUNI_INE = "07032"

WFS_URBANISME = "https://ide.cime.es/geoserver/urbanisme/wfs"
WFS_PARCEL = "https://ide.cime.es/geoserver2/base_referencia/wfs"
WFS_SOLURBA = "urbanisme:or032pgo_solurba_su"
WFS_PARCEL_TYPE = "base_referencia:ca007ins_parcela"

DEFAULT_TRAMITES: list[dict[str, str]] = [
    {
        "url": f"{WEB_BASE}/gesserveis/gestion.aspx?idgestion=58",
        "titulo": "Llicència d'obres amb projecte",
        "tipo": "licencia de obra",
    },
    {
        "url": f"{WEB_BASE}/gesserveis/gestion.aspx?idgestion=277",
        "titulo": "Certificat de disciplina urbanística i/o històric",
        "tipo": "certificado urbanístico",
    },
    {
        "url": f"{WEB_BASE}/gesserveis/gestion.aspx?idgestion=22",
        "titulo": "Consulta registre d'entrades i sortides (carpeta ciutadana)",
        "tipo": "consulta expediente",
    },
    {
        "url": SEDE_BASE + "/Portal.aspx",
        "titulo": "Seu electrònica / Carpeta ciutadana — tràmits urbanisme",
        "tipo": "sede electrónica",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|licen|obra[s]? (?:amb|con)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|primera ocupaci|legalitz|piscin|autoritzaci[oó])",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|planej|plan (?:parcial|especial|general)|pgou|pla general|"
    r"informaci[oó]n p[uú]blica|expedient|exp\.|proyecto|projecte|modificaci[oó]n|"
    r"reparcel|estudi de detall|sector|pol[ií]gon|unitat d.actuaci|aprovaci[oó]|"
    r"anunci|exposici[oó] p[uú]blica|disciplina|ordenan|consulta p[uú]blica)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(subvenci[oó]n|subvenci|ajud|personal|empleo|ocupaci[oó]|convocat[oò]ria.*ple|"
    r"menjador|escolar|ludoteca|festes|flors|escultura|tribunal|jurado|jurat|"
    r"contracte menor(?!.*urban)|mostrador|bieni|concurs de)",
)
RE_EDICTE = re.compile(
    r'<a class="dxeHyperlink_Moderno" href="([^"]+)"[^>]*>(.*?)</a></td>\s*'
    r'<td class="textCenter[^"]*"[^>]*>(\d{1,2}/\d{1,2}/\d{4})',
    re.I | re.S,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_CATASTRO = re.compile(
    r"(?i)REFER[EÈ]NCIA CADASTRAL\s+([0-9A-Z]{10,20})",
)
RE_EXP_CODE = re.compile(
    r"(?i)\bEXP\.?\s*([A-Z]{1,4}\d{3,4}-\d{4}-\d+)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


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


def _abs_url(href: str) -> str:
    return urllib.parse.urljoin(f"{WEB_BASE}/", unescape(href).replace("&amp;", "&"))


def _proyecto_tipo(title: str) -> str:
    n = (title or "").lower()
    if "estudi de detall" in n:
        return "estudio de detalle"
    if "plan parcial" in n or "pla parcial" in n:
        return "plan parcial"
    if "pgou" in n or "plan general" in n or "pla general" in n:
        return "PGOU"
    if "polígon industrial" in n or "poligon industrial" in n:
        return "planeamiento sectorial"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "consulta p" in n and "blica" in n:
        return "consulta pública"
    if "llicen" in n or "licen" in n:
        return "licencia / trámite obra"
    if "sòl urb" in n or "sol urb" in n:
        return "ámbito PGOU"
    return "urbanismo"


def _normalize_catastro(raw: str) -> str:
    ref = (raw or "").strip().upper()
    if len(ref) > 14 and re.match(r"^\d{7}[A-Z0-9]{7,}", ref):
        return ref[:14]
    return ref


def _apply_geom_fields(rec: dict[str, Any], geom: dict[str, Any], meta: dict[str, Any]) -> None:
    rec.update(meta)
    rec["geom_geojson"] = geom
    rec["geometry_crs"] = "EPSG:4326"
    rec["source_crs"] = "EPSG:4326"
    rec["coordinates_crs"] = "EPSG:4326"
    cen = geometry_centroid(geom)
    if cen:
        rec.setdefault("lat", cen[0])
        rec.setdefault("lon", cen[1])


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        t, coords = g.get("type"), g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class MaoAyuntamientoAdapter(AyuntamientoAdapter):
    """CMS ajmao.org (DevExpress tablón) + gesserveis trámites + IDE Menorca WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_urbanisme = str(geom_cfg.get("wfs_urbanisme_url") or WFS_URBANISME)
        self.wfs_parcel = str(geom_cfg.get("wfs_parcel_url") or WFS_PARCEL)
        self.wfs_solurba = str(geom_cfg.get("solurba_type") or WFS_SOLURBA)
        self.wfs_parcel_type = str(geom_cfg.get("parcel_type") or WFS_PARCEL_TYPE)
        self.muni_ine = str(geom_cfg.get("municipio_ine") or MUNI_INE)
        self._ssl_ctx = ssl.create_default_context()
        self._solurba_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-mao/1.0")},
        )
        with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _wfs_features(
        self,
        base: str,
        type_name: str,
        *,
        cql: str | None = None,
        count: int = 50,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": type_name,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "count": str(count),
        }
        if cql:
            params["CQL_FILTER"] = cql
        url = f"{base}?{urllib.parse.urlencode(params)}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _load_solurba(self) -> list[dict[str, Any]]:
        if self._solurba_cache is not None:
            return self._solurba_cache
        self._solurba_cache = self._wfs_features(
            self.wfs_urbanisme, self.wfs_solurba, count=200
        )
        return self._solurba_cache

    def _fetch_geometry_catastro(self, title: str) -> dict[str, Any] | None:
        m = RE_CATASTRO.search(title or "")
        if not m:
            return None
        ref = _normalize_catastro(m.group(1))
        ref_esc = ref.replace("'", "''")
        cql = f"nationalcadastralreference='{ref_esc}' AND idmun='{self.muni_ine}'"
        feats = self._wfs_features(self.wfs_parcel, self.wfs_parcel_type, cql=cql, count=5)
        merged = _merge_geometries(feats)
        if not merged:
            return None
        return {
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_parcel}?service=WFS&request=GetFeature&typeNames={self.wfs_parcel_type}"
                f"&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
            "coord_source": "portal_geometry_centroid",
            "ref_catastral": ref,
            "_geom": merged,
        }

    def _fetch_geometry_ambito(self, title: str) -> dict[str, Any] | None:
        low = (title or "").lower()
        best: tuple[int, dict[str, Any]] | None = None
        for feat in self._load_solurba():
            props = feat.get("properties") or {}
            nom = str(props.get("nom") or "").strip()
            if not nom or len(nom) < 4:
                continue
            nlow = nom.lower()
            if nlow in low or low in nlow:
                score = len(nom)
            elif nlow in low.replace("·", "").replace("'", " "):
                score = len(nom) - 1
            else:
                parts = [p for p in re.split(r"[\s,;/]+", nlow) if len(p) >= 5]
                score = sum(len(p) for p in parts if p in low)
                if score <= 0:
                    continue
            if best is None or score > best[0]:
                best = (score, feat)
        if not best:
            return None
        feat = best[1]
        props = feat.get("properties") or {}
        nom = str(props.get("nom") or "")
        merged = _merge_geometries([feat])
        if not merged:
            return None
        cql = f"nom='{nom.replace(chr(39), chr(39) * 2)}'"
        return {
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_urbanisme}?service=WFS&request=GetFeature&typeNames={self.wfs_solurba}"
                f"&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
            "coord_source": "portal_geometry_centroid",
            "ambito_pgou": nom,
            "_geom": merged,
        }

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        geom = self._fetch_geometry_catastro(title)
        if geom:
            return geom
        return self._fetch_geometry_ambito(title)

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom_pack = self._fetch_geometry(rec.get("titulo") or "")
        if geom_pack:
            merged = geom_pack.pop("_geom", None)
            if merged:
                _apply_geom_fields(rec, merged, geom_pack)

    def _collect_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tablon_url in (TABLON_URL, TABLON_HIST_URL):
            try:
                html = self._fetch(tablon_url)
            except urllib.error.URLError:
                continue
            for m in RE_EDICTE.finditer(html):
                href, title_raw, fecha_raw = m.group(1), m.group(2), m.group(3)
                titulo = _strip_html(title_raw)
                if not titulo or titulo in seen:
                    continue
                seen.add(titulo)
                url = _abs_url(href) if not href.startswith("http") else href
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _parse_fecha_dmy(fecha_raw),
                        "url": url,
                        "origen": "tablon_edictes",
                        "blob": titulo,
                        "tablon": tablon_url,
                    }
                )
        return rows

    def _collect_pgou_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in (PGOU_URL, URBANISMO_AREA, NORMATIVA_TRAMIT, CONSULTA_PUBLICA):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for href in RE_PDF.findall(html):
                pdf_url = _abs_url(href)
                if pdf_url in seen:
                    continue
                name = Path(unescape(href)).name
                if not RE_PROYECTO.search(name) and "urban" not in name.lower():
                    continue
                seen.add(pdf_url)
                titulo = name.replace("-", " ").replace("_", " ")[:500]
                rows.append(
                    {
                        "titulo": f"PGOU / urbanisme — {titulo}",
                        "fecha": _parse_fecha_dmy(name),
                        "tipo": _proyecto_tipo(name),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": "pgou_web",
                    }
                )
                if len(rows) >= 35:
                    return rows
        return rows

    def _collect_pgou_ambitos(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for feat in self._load_solurba():
            props = feat.get("properties") or {}
            nom = str(props.get("nom") or "").strip()
            if not nom:
                continue
            dsg = str(props.get("dsgestio") or "Sòl urbà")
            merged = _merge_geometries([feat])
            titulo = f"PGOU Maó — {dsg}: {nom}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"pgou:{nom}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": "2012-01-30",
                "tipo": "ámbito PGOU",
                "url": VISOR_IDE,
                "source": "ayuntamiento",
                "origen": "ide_cime_wfs",
                "ambito_pgou": nom,
            }
            if merged:
                cql = f"nom='{nom.replace(chr(39), chr(39) * 2)}'"
                _apply_geom_fields(
                    rec,
                    merged,
                    {
                        "geometry_source": "portal_wfs",
                        "geometry_source_url": (
                            f"{self.wfs_urbanisme}?service=WFS&request=GetFeature&typeNames={self.wfs_solurba}"
                            f"&CQL_FILTER={urllib.parse.quote(cql)}"
                        ),
                        "coord_source": "portal_geometry_centroid",
                    },
                )
            out.append(rec)
        return out

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob.replace("llicen", "")):
            pass
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["titulo"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        exp = RE_EXP_CODE.search(blob)
        if exp:
            rec["expediente"] = exp.group(1)
        self._enrich_geometry(rec)
        return rec

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["titulo"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / edicto urbanístico",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("pdf_url") or row["titulo"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row["titulo"]),
            "url": row.get("url") or self.web_base,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.append(
            {
                "id": _stable_id("lic", TABLON_URL),
                "fecha_concesion": None,
                "tipo": "tablón de edictes",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tauler d'edictes i exposició pública (tipo 01)",
                "url": TABLON_URL,
                "source": "ayuntamiento",
                "origen": "tablon_edictes",
            }
        )
        for t in DEFAULT_TRAMITES:
            rows.append(
                {
                    "id": _stable_id("lic", t["url"]),
                    "fecha_concesion": None,
                    "tipo": t["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": t["titulo"],
                    "url": t["url"],
                    "source": "ayuntamiento",
                    "origen": "gesserveis",
                }
            )
        return rows

    def _build_proyectos(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec in self._collect_pgou_ambitos():
            if rec["id"] in seen:
                continue
            seen.add(rec["id"])
            out.append(rec)
        for row in self._collect_pgou_pdfs():
            rec = self._doc_to_proyecto(row)
            if rec["id"] in seen:
                continue
            seen.add(rec["id"])
            out.append(rec)
        for row in self._collect_tablon():
            rec = self._tablon_to_proyecto(row)
            if not rec or rec["id"] in seen:
                continue
            seen.add(rec["id"])
            out.append(rec)
        return out

    def _build_licencias(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec in self._collect_licencia_info():
            if rec["id"] in seen:
                continue
            seen.add(rec["id"])
            out.append(rec)
        for row in self._collect_tablon():
            rec = self._tablon_to_licencia(row)
            if not rec or rec["id"] in seen:
                continue
            seen.add(rec["id"])
            out.append(rec)
        return out

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return len(rows)

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
        return self.backfill_licencias(out_jsonl)

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
        return self.backfill_proyectos(out_jsonl)
