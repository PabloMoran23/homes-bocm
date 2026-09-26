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

WEB_BASE = "https://www.ajpollenca.net"
SEDE_BASE = "https://ajpollenca.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
VISOR_URL = "https://ide.idelma.cat/visormap/Visors/ide/html/visor042.html"
MUNICIPIO = "Pollença"
ID_PREFIX = "pollenca"

WFS_URL = "https://ide.idelma.cat/geoserver/M042_URBANISME/wfs"
WFS_TYPE_EXPEDIENTES = "M042_URBANISME:exp_absis"

EXPOSICION_PUBLICA_URL = f"{WEB_BASE}/ca/exposicio-publica"
PLANEAMIENTO_URL = f"{WEB_BASE}/ca/urbanisme/planejament-urbanistic"
VISOR_WEB_URL = f"{WEB_BASE}/ca/urbanisme/visor-pollenca"

TRAMITES_URBANISMO: list[dict[str, str]] = [
    {
        "url": f"{SEDE_BASE}/catalog/t/c70f211b-cab4-41cb-b33e-6f0919264ddb",
        "tipo": "aportación documentación obras",
        "titulo": "Aportación documentación expediente de obras (OBRES)",
    },
    {
        "url": f"{SEDE_BASE}/catalog/t/68f68ab1-e8df-44c7-9e5c-c0f2094103eb",
        "tipo": "aportación documentación",
        "titulo": "Aportación de documentación requerida (sede)",
    },
    {
        "url": f"{SEDE_BASE}/citizen-service/e277e1b9-3349-4412-a4e8-7b65ad84fb5a",
        "tipo": "trámites urbanismo",
        "titulo": "Obres, Urbanisme i Activitats — sede electrónica",
    },
    {
        "url": f"{WEB_BASE}/ca/urbanisme/certificats-urbanistics",
        "tipo": "certificados urbanísticos",
        "titulo": "Certificats urbanístics — web municipal",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licen|licèn|obra|comunicaci|declaraci|autoritz|autoriz|inici|connexi|"
    r"certificat|aforament|reforma|ampliaci|demolici|edificaci|instal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pla parcial|"
    r"informaci[oó] p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"sector|pol[ií]gon|unitat d.actuaci|aprovaci[oó]|boib|anunci)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvencion|subvenci[oó]|ajudes|bons 20|ocupaci[oó] p[uú]blica|ple\b|"
    r"convocat[oò]ria de.*ple)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://ajpollenca\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SKIP_WFS = re.compile(
    r"(?i)(antiguitat|subvenc|personal|ocupaci[oó]|nombrament|convocat)",
)


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


def _fecha_from_expediente(expediente: str) -> str | None:
    digits = re.sub(r"\D", "", expediente or "")
    if len(digits) >= 8:
        try:
            y, mo, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
            if 1980 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        except ValueError:
            pass
    m = re.search(r"/(\d{4})\b", expediente or "")
    if m:
        y = int(m.group(1))
        if 1980 <= y <= 2035:
            return f"{y}-01-01"
    years = [int(x.group(1)) for x in RE_YEAR.finditer(expediente or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(text: str) -> str:
    n = (text or "").lower()
    if "pla parcial" in n or "plan parcial" in n:
        return "plan parcial"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "anunci" in n and "boib" in n:
        return "anuncio BOIB"
    return "urbanismo"


def _licencia_tipo(text: str) -> str:
    n = (text or "").lower()
    if "comunicaci" in n:
        return "comunicación previa"
    if "declaraci" in n:
        return "declaración responsable"
    if "certificat" in n:
        return "certificado urbanístico"
    if "connexi" in n or "claveguer" in n:
        return "obra (conexión)"
    if "aforament" in n:
        return "licencia actividad"
    return "licencia de obra"


class PollencaAyuntamientoAdapter(AyuntamientoAdapter):
    """Plugcore CMS ajpollenca.net + sede espublico + IDELMA WFS exp_absis (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.visor_url = str(self.config.get("visor_url") or VISOR_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_URL)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE_EXPEDIENTES)
        self.wfs_max = int(geom_cfg.get("max_features") or 500)
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

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pollenca/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pollenca/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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
            geom = feat.get("geometry")
            exp_gen = str(props.get("numero_expedient_general") or "").strip()
            exp_part = str(props.get("numero_expedient_particular") or "").strip()
            expediente = exp_gen or exp_part
            descripcion = str(props.get("descripcio") or "").strip()
            promotor = str(props.get("nom_promotor") or "").strip()
            refcat = str(props.get("refcat") or "").strip()
            rows.append(
                {
                    "expediente": expediente,
                    "exp_particular": exp_part,
                    "descripcion": descripcion,
                    "promotor": promotor,
                    "refcat": refcat,
                    "geometry": geom,
                    "wfs_url": self._wfs_query_url(max_features=1),
                }
            )
        self._wfs_cache = rows
        return rows

    def _attach_wfs_geometry(self, rec: dict[str, Any], wfs_row: dict[str, Any]) -> None:
        geom = wfs_row.get("geometry")
        if not isinstance(geom, dict) or not geom.get("type"):
            return
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = self._wfs_query_url()
        rec["coord_source"] = "portal_geometry_centroid"
        cen = geometry_centroid(geom)
        if cen:
            rec["lat"], rec["lon"] = cen

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
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

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
                    "titulo": titulo[:500],
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
        if "actuacions urban" in proc or "urban" in proc:
            return True
        return bool(RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob))

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        proc = (row.get("procedimiento") or "").lower()
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and "actuacions urban" not in proc:
            return None
        if not RE_PROYECTO.search(blob) and "actuacions urban" not in proc:
            return None

        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"board:{key}"),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        return rec

    def _wfs_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        desc = row.get("descripcion") or ""
        if RE_SKIP_WFS.search(desc):
            return None
        if not RE_LICENCIA.search(desc):
            return None
        if RE_PROYECTO.search(desc) and not RE_LICENCIA.search(desc):
            return None

        expediente = row.get("expediente") or row.get("refcat") or desc[:40]
        titulo = desc
        if row.get("promotor"):
            titulo = f"{desc} — {row['promotor']}"

        rec: dict[str, Any] = {
            "id": _stable_id("lic", f"wfs:{expediente}:{desc[:60]}"),
            "fecha_concesion": _fecha_from_expediente(expediente),
            "tipo": _licencia_tipo(desc),
            "distrito": row.get("refcat") or None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "expte": expediente,
            "url": self.visor_url,
            "source": "ayuntamiento",
            "origen": "idelma_wfs",
        }
        self._attach_wfs_geometry(rec, row)
        return rec

    def _wfs_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        desc = row.get("descripcion") or ""
        if RE_SKIP_WFS.search(desc):
            return None
        if not RE_PROYECTO.search(desc):
            return None

        expediente = row.get("expediente") or row.get("refcat") or desc[:40]
        titulo = desc
        if row.get("promotor"):
            titulo = f"{desc} — {row['promotor']}"

        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"wfs:{expediente}:{desc[:60]}"),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": _fecha_from_expediente(expediente),
            "tipo": _proyecto_tipo(desc),
            "url": self.visor_url,
            "source": "ayuntamiento",
            "expte": expediente,
            "origen": "idelma_wfs",
        }
        self._attach_wfs_geometry(rec, row)
        return rec

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón anuncios urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Pollença",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Actuacions Urbanístiques y anuncios BOIB en espublico",
                "origen": "sede_tablon",
            },
        ]
        for item in TRAMITES_URBANISMO:
            rows.append(
                {
                    "id": _stable_id("lic", item["url"]),
                    "fecha_concesion": None,
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo sede espublico / web municipal",
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", EXPOSICION_PUBLICA_URL),
                "municipio": MUNICIPIO,
                "titulo": "Exposició pública — planeamiento urbanístico",
                "fecha": None,
                "tipo": "información pública",
                "url": EXPOSICION_PUBLICA_URL,
                "source": "ayuntamiento",
                "origen": "web_cms",
            },
            {
                "id": _stable_id("proy", PLANEAMIENTO_URL),
                "municipio": MUNICIPIO,
                "titulo": "Planejament urbanístic — documentación PGOU",
                "fecha": None,
                "tipo": "planeamiento",
                "url": PLANEAMIENTO_URL,
                "source": "ayuntamiento",
                "origen": "web_cms",
            },
            {
                "id": _stable_id("proy", self.visor_url),
                "municipio": MUNICIPIO,
                "titulo": "Visor IDE Pollença (IDELMA / Consell de Mallorca)",
                "fecha": None,
                "tipo": "visor GIS",
                "url": self.visor_url,
                "source": "ayuntamiento",
                "origen": "visor",
                "nota": "Capa WFS exp_absis + Projectes Municipals",
            },
            {
                "id": _stable_id("proy", VISOR_WEB_URL),
                "municipio": MUNICIPIO,
                "titulo": "Visor Pollença — enlace web municipal",
                "fecha": None,
                "tipo": "visor GIS",
                "url": VISOR_WEB_URL,
                "source": "ayuntamiento",
                "origen": "web_cms",
            },
        ]

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

        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for wfs_row in self._collect_wfs_expedientes():
            rec = self._wfs_to_licencia(wfs_row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs": sum(1 for r in rows if r.get("origen") == "idelma_wfs"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite")),
            "with_geometry": with_geom,
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_proyecto_info_pages():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for wfs_row in self._collect_wfs_expedientes():
            add(self._wfs_to_proyecto(wfs_row))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "wfs": sum(1 for r in rows if r.get("origen") == "idelma_wfs"),
            "with_geometry": with_geom,
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
