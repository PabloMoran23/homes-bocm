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

WP_BASE = "https://grinon.es"
SEDE_BASE = "https://grinon.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
URBANISMO_URL = f"{WP_BASE}/areas/urbanismo"
PLANEAMIENTO_URL = f"{WP_BASE}/areas/urbanismo/planeamiento-urbanistico"
ANUNCIOS_URL = f"{WP_BASE}/areas/urbanismo/anuncios-urbanisticos"
LICENCIAS_URL = f"{WP_BASE}/areas/urbanismo/tramites-y-servicios/licencias"
DECLARACIONES_URL = f"{WP_BASE}/areas/urbanismo/tramites-y-servicios/declaraciones-responsables"
MUNICIPIO = "Griñón"
ID_PREFIX = "grinon"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"ordenanza.*(?:edificaci|construcc|icio))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|conjunto|"
    r"ordenanza|catalogo|anexo|normas urban)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://grinon\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="(https://grinon\.es/wp-content/uploads/[^"]+\.pdf)"',
    re.I,
)
RE_ELEMENTOR_TEXT = re.compile(
    r'elementor-widget-text-editor.*?<div class="elementor-widget-container">\s*(.*?)\s*</div>\s*</div>',
    re.I | re.S,
)
HEADER_LABELS = {
    "título",
    "titulo",
    "fecha de publicación",
    "fecha de publicacion",
    "inicio plazo",
    "fin plazo",
    "periodo de participación",
    "periodo de participacion",
}


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{prefix}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(Path(url).name) if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _pgou_tipo(name: str) -> str:
    n = name.lower()
    if "convenio" in n:
        return "convenio urbanístico"
    if "memoria" in n:
        return "memoria planeamiento"
    if "planos" in n or "plano" in n:
        return "planos ordenación"
    if "orden" in n or "norma" in n:
        return "normas urbanísticas"
    if "anexo" in n:
        return "anexo planeamiento"
    if "catalogo" in n or "catálogo" in n:
        return "catálogo planeamiento"
    if "modific" in n or "m.puntual" in n:
        return "modificación puntual"
    if "estudio" in n or "est_" in n:
        return "estudio planeamiento"
    if "acuerdo" in n:
        return "acuerdo planeamiento"
    if "indice" in n or "índice" in n:
        return "índice planeamiento"
    return "planeamiento"


class GrinonAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress planeamiento + anuncios Elementor + tablón eHome (sede electrónica)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.planeamiento_url = str(self.config.get("planeamiento_url") or PLANEAMIENTO_URL)
        self.anuncios_url = str(self.config.get("anuncios_url") or ANUNCIOS_URL)
        self.licencias_url = str(self.config.get("licencias_url") or LICENCIAS_URL)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-grinon/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

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
                cls = cm.group(1)
                cells[cls] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento:
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url

            titulo = descripcion or documento
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
                    "blob": f"{documento} {expediente} {procedimiento} {categoria} {descripcion} {title_m.group(1) if title_m else ''}",
                }
            )
        return rows

    def _collect_planeamiento_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.planeamiento_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_WP_PDF.finditer(html):
            pdf = m.group(1)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            titulo = f"Planeamiento Griñón: {name}"
            rows.append(
                {
                    "id": _stable_id("proy", pdf),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_pdf_url(pdf) or "2024-03-01",
                    "tipo": _pgou_tipo(name),
                    "url": self.planeamiento_url,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "origen": "planeamiento_web",
                }
            )
        return rows

    def _collect_anuncios_urbanisticos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.anuncios_url)
        except urllib.error.URLError:
            return []

        widgets: list[str] = []
        for m in RE_ELEMENTOR_TEXT.finditer(html):
            t = _strip_html(m.group(1))
            if t and t.lower() not in HEADER_LABELS:
                widgets.append(t)

        rows: list[dict[str, Any]] = []
        for i in range(0, len(widgets), 5):
            chunk = widgets[i : i + 5]
            if not chunk:
                continue
            titulo = chunk[0]
            if len(titulo) < 10:
                continue
            fecha_pub = _parse_fecha_dmy(chunk[1]) if len(chunk) > 1 else None
            inicio = chunk[2] if len(chunk) > 2 else None
            fin = chunk[3] if len(chunk) > 3 else None
            periodo = chunk[4] if len(chunk) > 4 else None
            rows.append(
                {
                    "id": _stable_id("proy", f"anuncio:{titulo}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": fecha_pub,
                    "tipo": "información pública",
                    "url": self.anuncios_url,
                    "source": "ayuntamiento",
                    "origen": "anuncios_urbanisticos",
                    "inicio_plazo": inicio,
                    "fin_plazo": fin,
                    "periodo": periodo,
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, tipo, titulo in (
            (self.licencias_url, "trámite licencia urbanística", "Trámites de licencia (Urbanismo)"),
            (
                DECLARACIONES_URL,
                "declaración responsable",
                "Declaraciones responsables urbanísticas",
            ),
            (self.urbanismo_url, "información urbanismo", "Departamento de Urbanismo — trámites y normativa"),
            (f"{self.sede_base}/info.0", "sede electrónica urbanismo", "Sede electrónica — trámites urbanísticos"),
        ):
            try:
                self._fetch(url)
            except urllib.error.URLError:
                pass
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa; concesiones publicadas en tablón cuando proceda",
                }
            )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        cat = (row.get("categoria") or "").lower()
        if cat == "urbanismo" and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        tipo_m = re.search(r"(?i)para (?:la |el )?([^.,]+)", blob)
        return {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": (tipo_m.group(1).strip()[:120] if tipo_m else "licencia"),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "expte": row.get("expediente"),
            "url": row["url"],
            "source": "ayuntamiento",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        cat = (row.get("categoria") or "").lower()
        proc = (row.get("procedimiento") or "").lower()
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and cat != "urbanismo":
            return None
        if cat == "urbanismo" or proc == "planeamiento general":
            pass
        elif not RE_PROYECTO.search(blob):
            return None

        tipo = "urbanismo"
        if re.search(r"(?i)modificaci[oó]n puntual|m\. puntual", blob):
            tipo = "modificación puntual"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|publicacion bocm", blob):
            tipo = "información pública"
        elif re.search(r"(?i)plan (?:parcial|especial)|planeam", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)convenio", blob):
            tipo = "convenio"
        elif re.search(r"(?i)estudio de detalle", blob):
            tipo = "estudio de detalle"

        return {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente"),
            "origen": "tablon_sede",
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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "urbanismo_tablon"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
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

        for rec in self._collect_planeamiento_pdfs():
            add(rec)
        for rec in self._collect_anuncios_urbanisticos():
            add(rec)
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        planeam_n = sum(1 for r in rows if r.get("origen") == "planeamiento_web")
        anuncios_n = sum(1 for r in rows if r.get("origen") == "anuncios_urbanisticos")
        tablon_n = sum(1 for r in rows if r.get("origen") == "tablon_sede")
        return {
            "rows": len(rows),
            "status": "ok",
            "planeamiento_pdfs": planeam_n,
            "anuncios_items": anuncios_n,
            "tablon_items": tablon_n,
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
