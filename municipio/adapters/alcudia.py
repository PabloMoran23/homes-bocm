from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records
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
from municipio.geometry import geometry_centroid

WEB_BASE = "https://alcudia.net"
URBANISME = f"{WEB_BASE}/Urbanisme/ca"
SEDE_BASE = "https://alcudia.eadministracio.cat"
BOARD_URL = f"{SEDE_BASE}/board"
VISOR_CITYMAP = (
    "https://citymap.tecnogeows.com/user/101103780093126100707/map/JvJZqsG2tuzekkreZq9d6X?tree=stage"
)
SAC_PORTADA = "http://sac.alcudia.net/ABSATLAS/NORMATIVA/PUBLICACION_WEB/PORTADA-2.PDF"
SITMUN_URL = "https://sitmun.idelma.cat/urb_alcudia"
IDELMA_VISOR = "https://ide.idelma.cat/visormap/Visors/ide/html/visor003.html"
WFS_URL = "https://ide.idelma.cat/geoserver/M003_URBANISME/wfs"
WFS_TYPE_EXP = "M003_URBANISME:exp_absis"
MUNICIPIO = "Alcúdia"
ID_PREFIX = "alcudia"

DEFAULT_SEED_PAGES: tuple[str, ...] = (
    URBANISME,
    f"{WEB_BASE}/Urbanisme/ca/tramits/",
    f"{WEB_BASE}/Urbanisme/ca/planejament-vigent/",
    f"{WEB_BASE}/Urbanisme/ca/transparencia/",
    f"{WEB_BASE}/Urbanisme/ca/documentosDeInteres/",
    f"{WEB_BASE}/Urbanisme/es/planejament-vigent/",
)

DEFAULT_LICENCIA_PAGES: list[dict[str, str]] = [
    {
        "url": f"{SEDE_BASE}/info.0",
        "titulo": "Tràmits i informació — seu electrònica Alcúdia",
        "tipo": "trámites urbanismo",
    },
    {
        "url": f"{SEDE_BASE}/citaprevia.1",
        "titulo": "Cita prèvia departament d'urbanisme",
        "tipo": "cita previa",
    },
    {
        "url": f"{WEB_BASE}/Urbanisme/ca/tramits/",
        "titulo": "Tràmits urbanisme — web municipal",
        "tipo": "trámites urbanismo",
    },
]

DEFAULT_PROYECTO_SEEDS: list[dict[str, str]] = [
    {
        "url": VISOR_CITYMAP,
        "titulo": "Visor urbanístic Citymap (Tecnogeo) — Ajuntament d'Alcúdia",
        "tipo": "visor GIS",
    },
    {
        "url": SAC_PORTADA,
        "titulo": "ABS-Atlas — normativa urbanística publicada (SAC Alcúdia)",
        "tipo": "PGOU",
    },
    {
        "url": SITMUN_URL,
        "titulo": "SITMUN — informació urbanística Alcúdia (IDELMA)",
        "tipo": "visor GIS",
    },
    {
        "url": IDELMA_VISOR,
        "titulo": "Visor IDE Consell de Mallorca (INE M003)",
        "tipo": "visor GIS",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licen|llic[eè]ncia|obra|comunicaci|declaraci|certificat|ocupaci|"
    r"urban|tramit|activitat|instal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|plan (?:parcial|especial|general)|pgou|pla general|"
    r"modificaci[oó]n|modificaci|informaci[oó] p[uú]blica|expedient|projecte|proyecto|"
    r"reparcel|sector|normativa|nnss|mp\d|ficha|visor|atlas|sac\.|boib|instrument)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocat[oò]ria.*empleo|"
    r"subvencion|subvenci[oó]|ajudes|ple\b|policia|festes)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://alcudia\.eadministracio\.cat)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_PDF = re.compile(r'\.pdf(?:\?|"|$)', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_MODI = re.compile(r"(?i)modi|ficha_modificacion|nnss|mp\d|est_de_t")
RE_SKIP_WFS = re.compile(r"(?i)(subvenc|personal|ocupaci[oó]|nombrament)")


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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "modificaci" in n or "modi_" in n or "ficha_modificacion" in n:
        return "modificación planeamiento"
    if "nnss" in n or "mp2" in n or "normes" in n:
        return "normativa / planeamiento"
    if "pgou" in n or "pla general" in n or "atlas" in n:
        return "PGOU"
    if "visor" in n or "citymap" in n or "sitmun" in n or "idelma" in n:
        return "visor GIS"
    if "informaci" in n and "p" in n:
        return "información pública"
    return "urbanismo"


def _licencia_tipo(text: str) -> str:
    n = (text or "").lower()
    if "comunicaci" in n:
        return "comunicación previa"
    if "declaraci" in n:
        return "declaración responsable"
    if "certificat" in n:
        return "certificado urbanístico"
    if "cita" in n:
        return "cita previa urbanismo"
    return "trámite urbanismo"


class AlcudiaAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenCms alcudia.net (Urbanisme) + sede eadministracio.cat + Citymap/TecnoGeo + IDELMA WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        geom = self.config.get("geometry") or {}
        self.wfs_url = str(geom.get("wfs_url") or WFS_URL)
        self.wfs_type = str(geom.get("type_name") or WFS_TYPE_EXP)
        self.wfs_max = int(geom.get("max_features") or 500)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alcudia/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 120) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alcudia/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_url(self, href: str) -> str:
        href = unescape(href).strip()
        if href.startswith("//"):
            href = "https:" + href
        if href.startswith("http"):
            return href.split("#")[0]
        if href.startswith("/"):
            return urllib.parse.urljoin(f"{self.web_base}/", href).split("#")[0]
        return urllib.parse.urljoin(f"{self.web_base}/", href).split("#")[0]

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href)).split("#")[0]

    def _wfs_query_url(self, *, max_features: int | None = None) -> str:
        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": self.wfs_type,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "maxFeatures": str(max_features or self.wfs_max),
        }
        return f"{self.wfs_url}?{urllib.parse.urlencode(params)}"

    def _collect_wfs_expedientes(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        try:
            data = self._fetch_json(self._wfs_query_url())
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            self._wfs_cache = []
            return self._wfs_cache
        feats = data.get("features") if isinstance(data, dict) else []
        rows: list[dict[str, Any]] = []
        for feat in feats or []:
            props = feat.get("properties") or {}
            expediente = str(
                props.get("numero_expedient_general")
                or props.get("numero_expedient_particular")
                or ""
            ).strip()
            descripcion = str(props.get("descripcio") or "").strip()
            rows.append(
                {
                    "expediente": expediente,
                    "descripcion": descripcion,
                    "refcat": str(props.get("refcat") or "").strip(),
                    "geometry": feat.get("geometry"),
                }
            )
        self._wfs_cache = rows
        return rows

    def _attach_geometry(self, rec: dict[str, Any], geom: dict[str, Any] | None) -> None:
        if not isinstance(geom, dict) or not geom.get("type"):
            return
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs_idelma"
        rec["geometry_source_url"] = self._wfs_query_url(max_features=1)
        rec["coord_source"] = "portal_geometry_centroid"
        cen = geometry_centroid(geom)
        if cen:
            rec["lat"], rec["lon"] = cen

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, timeout=45)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            if not documento or documento in ("Document", "Documento"):
                continue

            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            url = self._abs_sede(url)

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if "urban" in proc or "obra" in proc:
            return True
        return bool(RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not re.search(
            r"(?i)(llic[eè]ncia|comunicaci|decret|resoluci)", blob
        ):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", f"board:{key}"),
            "fecha_concesion": row.get("fecha"),
            "tipo": _licencia_tipo(blob),
            "distrito": MUNICIPIO,
            "lat": None,
            "lon": None,
            "source": "ayuntamiento",
            "titulo": (row.get("titulo") or row.get("documento", ""))[:500],
            "url": row.get("url"),
            "origen": "tablon",
            "expte": row.get("expediente"),
        }
        if re.search(r"(?i)decret|resoluci", blob):
            rec["tipo"] = "resolución / licencia urbanística"
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        proc = (row.get("procedimiento") or "").lower()
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and "urban" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", f"board:{key}"),
            "municipio": MUNICIPIO,
            "titulo": row.get("titulo", row.get("documento", ""))[:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _crawl_urbanisme(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []

        for page in DEFAULT_SEED_PAGES:
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                continue
            for m in RE_HREF.finditer(html):
                href = m.group(1)
                if href.startswith("#") or "javascript:" in href.lower():
                    continue
                url = self._abs_url(href)
                low = url.lower()
                if not (
                    "alcudia.net/urbanisme" in low
                    or "sac.alcudia.net" in low
                    or "/export/sites/default/urbanisme" in low
                ):
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                if RE_PDF.search(url) or RE_MODI.search(url):
                    blob = urllib.parse.unquote(url.split("/")[-1])
                    if not RE_PROYECTO.search(blob) and not RE_MODI.search(blob):
                        continue
                    rows.append(
                        {
                            "titulo": blob.replace("_", " ").replace("%20", " ")[:500],
                            "fecha": _fecha_from_blob(blob),
                            "url": url,
                            "blob": blob,
                            "origen": "pdf_web",
                        }
                    )
                    continue

                if "/Urbanisme/" in url and url.rstrip("/") != page.rstrip("/"):
                    title = url.rsplit("/", 1)[-1].replace("-", " ")
                    rows.append(
                        {
                            "titulo": title[:500],
                            "fecha": None,
                            "url": url,
                            "blob": title,
                            "origen": "web_crawl",
                        }
                    )
        return rows

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        url = item.get("url") or URBANISME
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": (item.get("titulo") or blob)[:500],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": item.get("origen"),
            "expte": item.get("expediente"),
        }
        return rec

    def _wfs_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        desc = row.get("descripcion") or ""
        exp = row.get("expediente") or row.get("refcat") or ""
        blob = f"{desc} {exp}"
        if RE_SKIP_WFS.search(blob):
            return None
        if not blob.strip():
            return None
        titulo = desc or f"Expedient {exp}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"wfs:{exp or desc[:40]}"),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": _fecha_from_blob(exp),
            "tipo": _proyecto_tipo(blob) if RE_PROYECTO.search(blob) else "expediente urbanístico",
            "url": self._wfs_query_url(max_features=1),
            "source": "ayuntamiento",
            "expte": exp or None,
            "origen": "idelma_wfs",
        }
        if RE_LICENCIA.search(desc) and not RE_PROYECTO.search(desc):
            rec["tipo"] = _licencia_tipo(desc)
        self._attach_geometry(rec, row.get("geometry"))
        return rec

    def _wfs_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        desc = row.get("descripcion") or ""
        if not RE_LICENCIA.search(desc) or RE_SKIP_WFS.search(desc):
            return None
        exp = row.get("expediente") or row.get("refcat") or desc[:40]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", f"wfs:{exp}"),
            "fecha_concesion": _fecha_from_blob(exp),
            "tipo": _licencia_tipo(desc),
            "distrito": MUNICIPIO,
            "lat": None,
            "lon": None,
            "source": "ayuntamiento",
            "titulo": desc[:500],
            "url": self._wfs_query_url(max_features=1),
            "expte": row.get("expediente"),
            "origen": "idelma_wfs",
        }
        self._attach_geometry(rec, row.get("geometry"))
        return rec

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in DEFAULT_LICENCIA_PAGES:
            rows.append(
                {
                    "id": _stable_id("lic", seed["url"]),
                    "fecha_concesion": None,
                    "tipo": seed.get("tipo") or _licencia_tipo(seed["titulo"]),
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "source": "ayuntamiento",
                    "titulo": seed["titulo"],
                    "url": seed["url"],
                    "origen": "sede_portal",
                }
            )
        return rows

    def _collect_proyecto_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", s["url"]),
                "municipio": MUNICIPIO,
                "titulo": s["titulo"],
                "fecha": None,
                "tipo": s.get("tipo") or _proyecto_tipo(s["titulo"]),
                "url": s["url"],
                "source": "ayuntamiento",
                "origen": "semilla",
            }
            for s in DEFAULT_PROYECTO_SEEDS
        ]

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_licencia_info():
            add(rec)
        for item in self._collect_board():
            lic = self._board_to_licencia(item)
            if lic:
                add(lic)
        for w in self._collect_wfs_expedientes():
            lic = self._wfs_to_licencia(w)
            if lic:
                add(lic)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs": sum(1 for r in rows if r.get("origen") == "idelma_wfs"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before_rows = self._load_jsonl(out_jsonl)
        before = len(before_rows)
        stats = self.backfill_licencias(out_jsonl)
        after_rows = self._load_jsonl(out_jsonl)
        if not after_rows and before_rows:
            self._write_jsonl(out_jsonl, before_rows)
            after_rows = before_rows
            stats = {**stats, "rows": len(after_rows), "preserved_previous": True}
        after = len(after_rows)
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

        for rec in self._collect_proyecto_seeds():
            add(rec)
        for item in self._crawl_urbanisme():
            add(self._item_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for w in self._collect_wfs_expedientes():
            add(self._wfs_to_proyecto(w))

        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "pdf_web": sum(1 for r in rows if r.get("origen") == "pdf_web"),
            "idelma_wfs": sum(1 for r in rows if r.get("origen") == "idelma_wfs"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before_rows = self._load_jsonl(out_jsonl)
        before = len(before_rows)
        stats = self.backfill_proyectos(out_jsonl)
        after_rows = self._load_jsonl(out_jsonl)
        if len(after_rows) < before and before_rows:
            seen = {r["id"] for r in after_rows}
            merged = after_rows + [r for r in before_rows if r["id"] not in seen]
            if len(merged) > len(after_rows):
                self._write_jsonl(out_jsonl, merged)
                after_rows = merged
                stats = {**stats, "rows": len(merged), "merged_previous": True}
        after = len(after_rows)
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
        return stats | {"added": max(0, after - before)}
