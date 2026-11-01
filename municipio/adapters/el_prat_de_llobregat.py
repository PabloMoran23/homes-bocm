from __future__ import annotations

import hashlib
import json
import re
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

WEB_BASE = "https://www.elprat.cat"
SEDE_BASE = "https://seu.elprat.cat"
BOARD_URL = f"{SEDE_BASE}/board"
URBANISME_SERVICE = f"{SEDE_BASE}/citizen-service/be0ce022-2e85-4954-ae47-624e1aca3ca9"
GEOPORTAL_URL = "https://mapes.elprat.cat/geoportal/"
MUNICIPIO = "El Prat de Llobregat"
ID_PREFIX = "el-prat-de-llobregat"
INE_MUN = "08169"

AMB_EXP_LAYER = (
    "https://geoportal.amb.cat/geoserveisapp/rest/services/"
    "Planejament/Expedients/MapServer/3"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/link-planejament-urbanistic",
    f"{WEB_BASE}/node/42145",
    f"{WEB_BASE}/ciutat-i-territori/urbanisme/obres-i-activitats-economiques-privades",
]

RE_LICENCIA = re.compile(
    r"(?i)(licen[cs]i[ao]|llic[eè]ncia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó]n responsable|declaraci[oó] responsable|autorizaci[oó]n (?:previa|urban)|"
    r"obra (?:major|menor)|enderroc|assabentat)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|planej|plan (?:parcial|especial|general)|pgou|pgm|mpgm|conveni|"
    r"informaci[oó]n p[uú]blica|informaci[oó] p[uú]blica|exposici[oó]n|expedient|"
    r"projecte|proyecto|modificaci[oó]n|reparcel|gesti[oó] urban|sector|àmbit|ambit|"
    r"reurbanitzaci|obres|contractaci)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(convocat[oò]ria.*(?:ple|junta)|elecci[oó]n|jurat|empleo|subvenci[oó]n|"
    r"proceso selectivo|oposici[oó]n)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://seu\.elprat\.cat)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DRUPAL_LINK = re.compile(
    r'href="((?:https://www\.elprat\.cat)?/(?:ciutat-i-territori|link-planejament)[^"#?]+)"',
    re.I,
)
RE_PDF = re.compile(
    r'href="((?:https://www\.elprat\.cat)?/sites/default/files/[^"]+\.pdf[^"]*)"',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "reurbanitz" in n or "reurbaniz" in n:
        return "reurbanización"
    if "projecte d'obres" in n or "projecte d&#039;obres" in n or "proyecto de obra" in n:
        return "proyecto de obras"
    if "plan parcial" in n or re.search(r"\bpp\b", n):
        return "plan parcial"
    if "plan especial" in n:
        return "plan especial"
    if "pgm" in n or "mpgm" in n:
        return "modificación PGM"
    if "conveni" in n:
        return "convenio urbanístico"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "contractaci" in n:
        return "contratación / obras"
    return "planeamiento"


class ElPratDeLlobregatAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal elprat.cat + sede espublico gestiona (board) + AMB Expedients GIS (PGM, INE 08169)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 12))
        geom_cfg = self.config.get("geometry") or {}
        self.amb_exp_layer = str(geom_cfg.get("arcgis_expedients_layer") or AMB_EXP_LAYER)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self._amb_cache: list[dict[str, Any]] | None = None
        self._amb_by_norm_name: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-prat-de-llobregat/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(self.web_base + "/", href)

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento",):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = unescape(title_m.group(1).strip())
            titulo = unescape(titulo)
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": unescape(
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        cat = (row.get("categoria") or "").lower()
        if cat in ("urbanisme", "edictes") and RE_PROYECTO.search(blob):
            return True
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("urban", "contractaci", "planej", "obra", "licen", "llicen")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

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
            if nom:
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
        return None

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
        nom = _strip_html(str(props.get("NOMEXP") or "Expediente urbanístico"))
        dgu = str(props.get("DGU") or "").strip()
        url = str(props.get("URL") or "").strip() or GEOPORTAL_URL
        key = dgu or nom
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"amb:{key}"),
            "municipio": MUNICIPIO,
            "titulo": nom,
            "fecha": _parse_fecha_dmy(str(props.get("DAPRDEF") or "")) or _fecha_from_blob(dgu),
            "tipo": _proyecto_tipo(nom),
            "url": url,
            "source": "ayuntamiento",
            "origen": "amb_expedients_gis",
        }
        if dgu:
            rec["expte"] = dgu
        cmb = str(props.get("CMB") or "").strip()
        if cmb:
            rec["nota"] = f"CMB AMB: {cmb}"
        self._apply_amb_geometry(rec, feat, f"{self.amb_exp_layer}/query")
        return rec

    def _collect_web_docs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        queue = list(self.seed_pages)
        rows: list[dict[str, Any]] = []
        while queue and len(seen) < self.max_crawl_pages:
            page_url = queue.pop(0)
            if page_url in seen:
                continue
            seen.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            h1 = re.search(r"<h1[^>]*>([^<]+)", html, re.I)
            page_title = _strip_html(h1.group(1)) if h1 else page_url
            for pdf in RE_PDF.findall(html):
                pdf_url = self._abs_web(pdf)
                name = Path(urllib.parse.urlparse(pdf_url).path).name
                rows.append(
                    {
                        "titulo": f"{page_title} — {name}"[:500],
                        "fecha": _fecha_from_blob(pdf_url),
                        "url": pdf_url,
                        "origen": "drupal_pdf",
                        "blob": f"{page_title} {name}",
                    }
                )
            for link in RE_DRUPAL_LINK.findall(html):
                abs_link = self._abs_web(link)
                if abs_link not in seen and abs_link not in queue:
                    queue.append(abs_link)
        return rows

    def _web_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia urbanística",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        self._enrich_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        self._enrich_geometry(rec)
        return rec

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        dossier = f"{self.sede_base}/dossier"
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos urbanismo y licencias (espublico gestiona /board)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", URBANISME_SERVICE),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanisme — trámites y información",
                "url": URBANISME_SERVICE,
                "source": "ayuntamiento",
                "nota": "Llicències d'obres, comunicacions prèvies y certificats (catálogo sede)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", dossier),
                "fecha_concesion": None,
                "tipo": "catálogo trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites municipales",
                "url": dossier,
                "source": "ayuntamiento",
                "nota": "Grupo llicències i permisos: obres (sede nueva wicket)",
                "origen": "sede_tramite",
            },
        ]

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_web_docs():
            add(self._web_to_proyecto(item))
        for feat in self._load_amb_expedients():
            add(self._amb_to_proyecto(feat))
        geoportal_seed = {
            "id": _stable_id("proy", GEOPORTAL_URL),
            "municipio": MUNICIPIO,
            "titulo": "Geoportal urbanístic municipal (mapes.elprat.cat)",
            "fecha": None,
            "tipo": "visor GIS",
            "url": GEOPORTAL_URL,
            "source": "ayuntamiento",
            "origen": "geoportal",
            "nota": "Consulta expedients, qualificacions i capes PGM (enMapa/Nexus)",
        }
        add(geoportal_seed)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencias():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": len(rows) - before},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": len(rows) - before, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "amb_gis": sum(1 for r in rows if r.get("origen") == "amb_expedients_gis"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": after, "added": max(0, after - before)},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
