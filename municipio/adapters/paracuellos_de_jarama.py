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

SEDE_BASE = "https://sede.paracuellosdejarama.es"
MUNICIPIO = "Paracuellos de Jarama"
ID_PREFIX = "paracuellos-de-jarama"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "PARACUELLOS DE JARAMA"

DEFAULT_TABLON_SUBSECTIONS = ("URB", "EDICTO", "BANDOS", "SECRET", "MEDIOAM")

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|druo|drupo|autorizaci[oó]n (?:previa|urban)|"
    r"legalizaci[oó]n de obras|c[eé]dula urban|calificaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|modificaci[oó]n.*plan|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|aprobaci[oó]n.*(?:plan|inicial|definitiva)|"
    r"edicto.*(?:licen|obra)|segregaci|agrupaci[oó]n.*parcel|ordenanza.*urban|"
    r"\b(?:UE|AD|AN|AI|PAU|S)-\d+\b|plan especial|plan parcial)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|responsabilidad patrimonial|\bbii\b|"
    r"funcionario|empleado|baja expediente|icio|plusvalia|basura)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UE|AD|AN|AI|PAU|S)-\d+[A-Z0-9-]*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "plan especial" in n or re.search(r"\bpe\b", n):
        return "plan especial"
    if "plan parcial" in n or re.search(r"\bpp\b", n):
        return "plan parcial"
    if "pgou" in n or "planeamiento" in n:
        return "planeamiento"
    if "informaci" in n:
        return "información pública"
    if "convenio" in n:
        return "convenio"
    if "licencia" in n or "edicto" in n:
        return "edicto urbanismo"
    return "urbanismo"


def _sector_ilike_parts(text: str) -> list[str]:
    s = text.strip()
    low = s.lower()
    for marker in (" del pgou", " pgou", " bocm", " aprob", " anuncio"):
        if marker in low:
            low = low.split(marker, 1)[0]
    parts = [p for p in re.split(r"[\s,;/|()]+", low) if len(p) >= 3]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        k = p.lower()
        if k not in seen and not re.fullmatch(r"\d{4}", p):
            seen.add(k)
            out.append(p)
    return out[:10]


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class ParacuellosDeJaramaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede Insuit: tablón JSON + catálogo trámites urbanismo + WFS SIT (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_opc_id = str(self.config.get("tablon_opc_id") or "268")
        self.catalog_id_apl = str(self.config.get("catalog_id_apl") or "1")
        self.tablon_subsections = tuple(
            self.config.get("tablon_subsections") or DEFAULT_TABLON_SUBSECTIONS
        )
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(
        self,
        url: str,
        *,
        data: bytes | None = None,
        charset: str = "latin-1",
    ) -> str:
        time.sleep(self.delay_s)
        headers = {
            "User-Agent": self.config.get("user_agent", "poc-bocm-paracuellos-de-jarama/1.0"),
        }
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            enc = resp.headers.get_content_charset() or charset
            return raw.decode(enc, errors="replace")

    def _fetch_json(self, url: str, *, data: bytes | None = None) -> Any:
        text = self._fetch(url, data=data)
        return json.loads(text)

    def _abs_sede(self, href: str) -> str:
        href = unescape(href).replace("&amp;", "&")
        return urllib.parse.urljoin(f"{self.sede_base}/", href)

    def _tablon_post(self, subseccion: str) -> dict[str, Any]:
        url = f"{self.sede_base}/sede/tablonElectronico.do"
        payload = urllib.parse.urlencode(
            {
                "opcion": "consultar",
                "opc_id": self.tablon_opc_id,
                "ent_id": "1",
                "subseccion": subseccion,
            }
        ).encode()
        data = self._fetch_json(url, data=payload)
        return data if isinstance(data, dict) else {}

    def _doc_url(self, doc: dict[str, Any]) -> str:
        raw = doc.get("docUrl") or ""
        if raw:
            return self._abs_sede(raw)
        code = doc.get("docCve") or ""
        sub = doc.get("_sub") or "TABLONVIRTUAL"
        if code:
            return (
                f"{self.sede_base}/portal/verificarDocumentos.do?"
                f"ent_id=1&opcion=verificar&codigo={urllib.parse.quote(str(code))}"
                f"&subseccion={sub}&idioma=1"
            )
        return f"{self.sede_base}/portal/noEstatica.do?opc_id={self.tablon_opc_id}&ent_id=1&idioma=1"

    def _collect_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        subsections = list(self.tablon_subsections)
        try:
            root = self._tablon_post("TABLONVIRTUAL")
            for s in root.get("listaSubsecciones") or []:
                code = str(s.get("cod") or "")
                if code and code not in subsections:
                    subsections.append(code)
        except urllib.error.URLError:
            pass

        for sub in subsections:
            try:
                data = self._tablon_post(sub)
            except urllib.error.URLError:
                continue
            for doc in data.get("listaDocumentos") or []:
                name = _clean_title(str(doc.get("docNom") or ""))
                if not name:
                    continue
                key = f"doc:{doc.get('docId') or name}"
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": name,
                        "fecha": _parse_fecha_dmy(str(doc.get("docFpu") or name)),
                        "url": self._doc_url({**doc, "_sub": sub}),
                        "subseccion": sub,
                        "origen": "tablon",
                        "doc_cve": doc.get("docCve"),
                    }
                )
            for exp in data.get("listaExpedientes") or []:
                name = _clean_title(str(exp.get("nombre") or ""))
                if not name:
                    continue
                code = f"{exp.get('anno')}/{exp.get('codigo')}"
                key = f"exp:{exp.get('idExp') or code}"
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": name,
                        "fecha": _parse_fecha_dmy(
                            str(exp.get("fechaPublicacion") or exp.get("fechaCreacion") or "")
                        ),
                        "url": f"{self.sede_base}/portal/noEstatica.do?opc_id={self.tablon_opc_id}&ent_id=1&idioma=1",
                        "subseccion": sub,
                        "origen": "tablon_expediente",
                        "expte": code,
                    }
                )
        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        url = (
            f"{self.sede_base}/sede/catalogoTramites.do?"
            f"opcion=detalle&idApl={self.catalog_id_apl}&ent_id=1&idioma=1"
        )
        try:
            html = self._fetch(url, charset="iso-8859-1")
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        block_m = re.search(
            r'id="collapse32".*?</ul>\s*</div>\s*</div>\s*</div>',
            html,
            re.S,
        )
        block = block_m.group(0) if block_m else html

        for m in re.finditer(
            r'title="([^"]+)"[^>]*href="javascript: abrirLogin\([^)]*asu_cod=(\d+)[^)]*\)"',
            block,
        ):
            title = _clean_title(m.group(1))
            asu = m.group(2)
            if not title:
                continue
            ficha_m = re.search(
                rf"asu_cod={asu}&asu_mod_cod=1&codVerif=([A-F0-9]+)&tra_cod=([^\"&]+)",
                block,
            )
            if ficha_m:
                ficha_url = (
                    f"{self.sede_base}/sede/fichaInformativa.do?"
                    f"asu_cod={asu}&asu_mod_cod=1&codVerif={ficha_m.group(1)}&tra_cod={ficha_m.group(2)}"
                )
            else:
                ficha_url = (
                    f"{self.sede_base}/sede/catalogoTramites.do?"
                    f"opcion=detalle&idApl={self.catalog_id_apl}&ent_id=1&idioma=1"
                )
            if ficha_url in seen:
                continue
            seen.add(ficha_url)
            rows.append(
                {
                    "titulo": title,
                    "url": ficha_url,
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _wfs_query(self, cql: str, count: int = 20) -> list[dict[str, Any]]:
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
        if parts:
            pattern = "%" + "%".join(p.replace("'", "''") for p in parts[:6]) + "%"
            muni = self.wfs_municipio.replace("'", "''")
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
            "geometry_source_url": f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}",
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

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo')} {row.get('subseccion')}"
        if RE_EXCLUDE.search(blob):
            return None
        if row.get("subseccion") == "URB":
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        key = row.get("doc_cve") or row.get("expte") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", str(key)),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "subseccion": row.get("subseccion"),
            "origen": row.get("origen"),
        }
        if row.get("expte"):
            rec["expte"] = row["expte"]
        self._enrich_geometry(rec)
        return rec

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row.get("titulo") or ""):
            return None
        if RE_EXCLUDE.search(row.get("titulo") or ""):
            return None
        key = row.get("doc_cve") or row.get("expte") or row["url"]
        return {
            "id": _stable_id("lic", str(key)),
            "fecha_concesion": row.get("fecha"),
            "tipo": "edicto licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row.get("titulo") or ""):
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
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title = row.get("titulo") or ""
        if title.strip().lower() != "planeamiento":
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": f"Trámite: {title}",
            "fecha": None,
            "tipo": "planeamiento",
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
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
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": len(rows) - before, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_tablon():
            rec = self._tablon_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_tablon():
            rec = self._tablon_to_proyecto(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_tramites():
            rec = self._tramite_to_proyecto(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "rows": len(rows),
                    "with_geometry": sum(1 for r in rows if record_geometry(r)),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "rows": len(rows),
            "added": len(rows) - before,
            "status": "ok",
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }
