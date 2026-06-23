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
from municipio.geometry import geometry_centroid

WP_BASE = "https://aytocubasdelasagra.es"
SEDE_BASE = "https://cubasdelasagra.sedelectronica.es"
MUNICIPIO = "Cubas de la Sagra"
ID_PREFIX = "cubas-de-la-sagra"
COD_MUNI = 28050
VISUALURB_API = "https://api-sig.visualurb.es"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|"
    r"primera ocupaci[oó]n|segregaci[oó]n|grua|gr[uú]a|placas solares|piscina)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|modificaci[oó]n|reparcel|sector|"
    r"unidad(?:es)? de ejecuci[oó]n|suelo urbanizable|ordenaci[oó]n|interpretaci[oó]n|"
    r"convocatoria.*pleno|acuerdo plenario|bienes protegidos|instrucciones particulares)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-/](\d{2})[-/]")
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?aytocubasdelasagra\.es)?/documentos/[^"]+\.(?:pdf|zip|PDF)[^"]*)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*(.*?)\s*</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(
    r'class="([^"]+)"[^>]*data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
)
RE_PREVIEW = re.compile(
    r'href="(https://cubasdelasagra\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_wp(href: str) -> str:
    return urllib.parse.urljoin(f"{WP_BASE}/", href)


def _pgou_tipo(name: str) -> str:
    n = name.lower()
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "modificaci" in n:
        return "modificación PGOU"
    if "interpretaci" in n:
        return "interpretación normativa"
    if "sector" in n and "urbaniz" in n:
        return "sector suelo urbanizable"
    if "unidad" in n and "ejecuci" in n:
        return "unidad de ejecución"
    if "planos" in n and "orden" in n:
        return "planos ordenación"
    if "bienes protegidos" in n or "catalogo" in n:
        return "catálogo patrimonio"
    if "areas" in n or "áreas" in n:
        return "áreas planeamiento incorporado"
    if "instrucciones" in n:
        return "instrucciones particulares"
    return "documento PGOU"


def _obra_tipo(name: str) -> str:
    n = name.lower()
    if "declaraci" in n and "responsable" in n:
        return "declaración responsable"
    if "primera ocupaci" in n:
        return "primera ocupación"
    if "segregaci" in n:
        return "segregación"
    if "grua" in n or "grúa" in n:
        return "instalación grúa-torre"
    if "placas solares" in n or "solar" in n:
        return "placas solares"
    if "piscina" in n:
        return "piscinas"
    if "dominio p" in n or "contenedor" in n:
        return "ocupación dominio público"
    return "trámite licencia obra"


class CubasDeLaSagraAyuntamientoAdapter(AyuntamientoAdapter):
    """Web PGOU + sede espublico tablón + visor Visualurb (geometría parcial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or f"{WP_BASE}/tramites-y-gestiones/urbanismo.php")
        self.obras_url = str(self.config.get("obras_url") or f"{WP_BASE}/tramites-y-gestiones/documentacion-obras.php")
        self.cod_muni = int(self.config.get("cod_muni") or COD_MUNI)
        self.visualurb_api = str(self.config.get("visualurb_api") or VISUALURB_API).rstrip("/")
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cubas-de-la-sagra/1.0")},
        )
        ctx = self._ssl_ctx if "sedelectronica" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-cubas-de-la-sagra/1.0"),
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60, context=self._ssl_ctx) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 404):
                return None
            raise
        except urllib.error.URLError:
            return None

    def _fetch_geometry(self, rec: dict[str, Any]) -> dict[str, Any]:
        """Intenta enriquecer con GeoJSON de Visualurb; falla silenciosamente si 401."""
        url = f"{self.visualurb_api}/MapUrbanismo/layer/suelomunicipio/{self.cod_muni}.geojson"
        data = self._fetch_json(url)
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            return rec
        features = data.get("features") or []
        if not features:
            return rec
        geom = (features[0].get("geometry") if isinstance(features[0], dict) else None) or None
        if not isinstance(geom, dict) or not geom.get("type"):
            return rec
        rec = dict(rec)
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_visor_visualurb"
        rec["geometry_source_url"] = url
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid
            rec["coord_source"] = "portal_geometry_centroid"
        return rec

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
        if not tbody_m:
            return rows
        for row_m in RE_BOARD_ROW.finditer(tbody_m.group(1)):
            row_html = row_m.group(1)
            if "emptyRow" in row_html or "display:none" in row_html:
                continue
            cells: dict[str, str] = {}
            doc_url = self.board_url
            for cm in RE_BOARD_CELL.finditer(row_html):
                cls, label, val = cm.group(1), cm.group(2), cm.group(3)
                link_m = re.search(r'href="([^"]+)"', val, re.I)
                if link_m and "class_name" in cls:
                    doc_url = urllib.parse.urljoin(f"{self.sede_base}/", link_m.group(1))
                cells[label] = _strip_html(val)
            if not cells:
                continue
            titulo = cells.get("Descripción") or cells.get("Documento") or ""
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": cells.get("Expediente", ""),
                    "procedimiento": cells.get("Procedimiento", ""),
                    "categoria": cells.get("Categoría", ""),
                    "fecha": _parse_fecha_dmy(cells.get("Fecha de Publicación", "")),
                    "url": doc_url,
                    "origen": "sede_board",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board(html)

    def _collect_page_docs(self, page_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            href = _abs_wp(m.group(1))
            if href in seen:
                continue
            seen.add(href)
            name = unescape(urllib.parse.unquote(Path(href).name))
            name = re.sub(r"\.(pdf|zip)$", "", name, flags=re.I).replace("%20", " ").replace("-", " ")
            context_m = re.search(
                rf"<h3[^>]*>\s*([^<]+).*?{re.escape(m.group(1)[:40])}",
                html,
                re.I | re.S,
            )
            section = _strip_html(context_m.group(1)) if context_m else name
            titulo = section if len(section) > 5 else name
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_url(href),
                    "url": page_url,
                    "pdf_url": href,
                    "origen": origen,
                }
            )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "expediente")
        )
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
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "expediente")
        )
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            if row.get("categoria") != "Órganos de gobierno":
                return None
            if not re.search(r"(?i)pleno|convocatoria|acuerdo", blob):
                return None
        tipo = "urbanismo"
        if re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            tipo = "información pública"
        elif re.search(r"(?i)planeamiento|pgou|nnss|sector", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)convocatoria.*pleno|acuerdo plenario", blob):
            tipo = "acuerdo plenario"
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        return rec

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("pdf_url") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": f"PGOU Cubas: {titulo}"[:500],
            "fecha": row.get("fecha"),
            "tipo": _pgou_tipo(titulo),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return self._fetch_geometry(rec)

    def _doc_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        return {
            "id": _stable_id("lic", row.get("pdf_url") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": _obra_tipo(titulo),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Documentación informativa de trámite; no concesión publicada",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_page_docs(self.obras_url, "documentacion_obras"):
            rec = self._doc_to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "obras_docs": sum(1 for r in rows if r.get("origen") == "documentacion_obras"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_page_docs(self.obras_url, "documentacion_obras"):
            existing[self._doc_to_licencia(item)["id"]] = self._doc_to_licencia(item)
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.parent.mkdir(parents=True, exist_ok=True)
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_page_docs(self.urbanismo_url, "urbanismo_pgou"):
            add(self._doc_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "pgou_docs": sum(1 for r in rows if r.get("origen") == "urbanismo_pgou"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
