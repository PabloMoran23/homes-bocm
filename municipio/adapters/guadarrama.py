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

WEB_BASE = "https://www.guadarrama.es"
SEDE_BASE = "https://ayuntamientodeguadarrama.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
URBANISMO_URL = f"{WEB_BASE}/contents/index3.php?id=30"
ANUNCIOS_URB_URL = f"{WEB_BASE}/contents/index3.php?id=42"
TRAMITES_URL = f"{WEB_BASE}/contents/index3.php?id=70"
MUNICIPIO = "Guadarrama"
ID_PREFIX = "guadarrama"

DEFAULT_URBANISMO_URLS = (URBANISMO_URL, ANUNCIOS_URB_URL)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|instalaci|funcionamiento|actividad)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"evaluaci[oó]n ambiental.*actividad|documentaci[oó]n licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|peri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|normas subsidiarias|"
    r"ordenanza|edtu|las cabezuelas|la mata|los fresnos|ua\d|sector|urbanizaci[oó]n|"
    r"calificaci[oó]n urban|industrial)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_ ](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_DATA_LABEL = re.compile(r'data-label="([^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://ayuntamientodeguadarrama\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_DOC_LINK = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*class="doc-link"[^>]*>(?:<[^>]+>)*\s*([^<]{3,300})',
    re.I | re.S,
)


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"BOCM[- ]?(\d{1,2})[- ](\d{1,2})[- ](\d{4})", text or "", re.I)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"BOCM[- ]?(\d{4})(\d{2})(\d{2})", text or "", re.I)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(text or "")
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


def _doc_tipo(name: str) -> str:
    n = name.lower()
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "peri" in n or "plan especial" in n:
        return "planeamiento"
    if "bocm" in n:
        return "publicación BOCM"
    if "estudio ac" in n or "acust" in n:
        return "estudio acústico"
    if "ambiental" in n:
        return "evaluación ambiental"
    if "memoria" in n:
        return "memoria planeamiento"
    if "planos" in n or "plano" in n:
        return "planos"
    if "convenio" in n:
        return "convenio urbanístico"
    if re.search(r"declaraci[oó]n responsable", n):
        return "declaración responsable"
    if "licencia" in n:
        return "modelo licencia"
    if "informacion general" in n or "información general" in n:
        return "información tramitación"
    return "documento urbanismo"


class GuadarramaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web corporativa (urbanismo/trámites PDFs) + tablón eHome espublico."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_urls = [
            str(u) for u in (self.config.get("urbanismo_urls") or DEFAULT_URBANISMO_URLS)
        ]
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-guadarrama/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str = WEB_BASE) -> str:
        return urllib.parse.urljoin(f"{base}/", href)

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(1)
            if "preview-document" not in row_html:
                continue
            cells: dict[str, str] = {}
            for label_m in RE_DATA_LABEL.finditer(row_html):
                label = label_m.group(1).strip().lower()
                cells[label] = _strip_html(label_m.group(2))
            if not cells:
                continue
            documento = cells.get("documento", "")
            if documento.lower() == "documento":
                continue

            expediente = cells.get("expediente", "")
            procedimiento = cells.get("procedimiento", "")
            categoria = cells.get("categoría", cells.get("categoria", ""))
            descripcion = cells.get("descripción", cells.get("descripcion", ""))
            fecha_raw = cells.get("fecha de publicación", cells.get("fecha de publicacion", ""))

            preview_m = RE_PREVIEW_LINK.search(row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            title_m = re.search(r'title="([^"]*)"', row_html, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or descripcion or documento
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
                    "blob": f"{documento} {expediente} {procedimiento} {categoria} {descripcion}",
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_urbanismo_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.urbanismo_urls:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                rows.append(
                    {
                        "titulo": name[:500],
                        "fecha": _fecha_from_blob(name) or _fecha_from_blob(pdf),
                        "url": page_url,
                        "pdf_url": pdf,
                        "tipo": _doc_tipo(name),
                        "origen": "urbanismo_web",
                    }
                )
        return rows

    def _collect_tramites_urbanismo(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tramites_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_DOC_LINK.finditer(html):
            href, titulo = m.group(1), _strip_html(m.group(2))
            if "/Urbanismo/" not in href and "urbanismo" not in href.lower():
                continue
            pdf = self._abs_url(href)
            if pdf in seen:
                continue
            seen.add(pdf)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo) or _fecha_from_blob(pdf),
                    "url": self.tramites_url,
                    "pdf_url": pdf,
                    "tipo": _doc_tipo(titulo),
                    "origen": "tramites_web",
                }
            )
        for m in RE_PDF_HREF.finditer(html):
            href = m.group(1)
            if "/Urbanismo/" not in href and "urbanismo" not in href.lower():
                continue
            pdf = self._abs_url(href)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(name),
                    "url": self.tramites_url,
                    "pdf_url": pdf,
                    "tipo": _doc_tipo(name),
                    "origen": "tramites_web",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", URBANISMO_URL),
                "fecha_concesion": None,
                "tipo": "urbanismo municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — normativa y planeamiento",
                "url": URBANISMO_URL,
                "source": "ayuntamiento",
                "nota": "Documentación normativa; concesiones en tablón sede",
                "origen": "urbanismo_web",
            },
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "trámites licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites — licencias y actividades urbanismo",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Modelos y documentación de trámites",
                "origen": "tramites_web",
            },
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y resoluciones publicadas",
                "origen": "tablon_sede",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — catálogo trámites urbanismo",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Presentación electrónica de solicitudes",
                "origen": "sede_tramites",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif row.get("categoria", "").lower() in {"órganos de gobierno", "organos de gobierno"}:
            if not re.search(r"(?i)pleno|convocatoria|acuerdo", blob):
                return None
        elif not RE_PROYECTO.search(blob):
            return None
        tipo = "urbanismo"
        if re.search(r"(?i)ordenanza", blob):
            tipo = "ordenanza"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|publicacion bocm|bocm", blob):
            tipo = "información pública"
        elif re.search(r"(?i)plan (?:parcial|especial)|peri|planeam", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)convenio", blob):
            tipo = "convenio"
        elif re.search(r"(?i)estudio de detalle|edtu", blob):
            tipo = "estudio de detalle"
        return {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or "documento urbanismo",
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _doc_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row.get("titulo") or ""
        if not RE_LICENCIA.search(titulo) and row.get("origen") != "tramites_web":
            return None
        if row.get("origen") == "tramites_web" and not re.search(
            r"(?i)licen|declaraci|documentaci|obra|actividad|urban|fotovoltaic|piscina|demolic|parcel|servicio|recarga",
            titulo,
        ):
            return None
        key = row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "modelo licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "nota": "Modelo o guía de trámite; no concesión publicada",
            "origen": row.get("origen"),
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
        for doc in self._collect_tramites_urbanismo():
            rec = self._doc_to_licencia(doc)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "tramites_web"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for doc in self._collect_tramites_urbanismo():
            rec = self._doc_to_licencia(doc)
            if rec:
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

        for doc in self._collect_urbanismo_pdfs():
            add(self._doc_to_proyecto(doc))
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "web": sum(1 for r in rows if r.get("origen") == "urbanismo_web"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
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
