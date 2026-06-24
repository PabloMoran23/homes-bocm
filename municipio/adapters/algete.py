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

BASE = "https://www.aytoalgete.es"
SEDE_BASE = "https://algete.sedelectronica.es"
URBANISMO_URL = (
    f"{BASE}/index.php?Itemid=519&id=111&option=com_content&view=article"
)
PLANEAMIENTO_URL = (
    f"{BASE}/index.php?Itemid=654&id=192&option=com_content&view=article"
)
MUNICIPIO = "Algete"
ID_PREFIX = "algete"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra mayor|obra menor)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|de sector)|pgou|"
    r"informaci[oó]n p[uú]blica|expediente urban|proyecto de (?:actuaci|exprop)|"
    r"modificaci[oó]n puntual|reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|"
    r"memoria|planos|bocm|edicto|aprobaci[oó]n (?:inicial|definitiva|urgente)|"
    r"parcela|suelo|sector|exprop|avance de planeam|espino|algete norte|locales comerciales)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(ayudas y subvenciones|empleo p[uú]blico|personal|deporte|"
    r"planificaci[oó]n y ordenaci[oó]n de personal)",
)
RE_SKIP_PDF = re.compile(
    r"(?i)(formulario|consideraciones|explicacion|instrucciones|cuenta_para|"
    r"ocupacion.via|certificado_punto_limpio|sitcm_manual|manual_ayuda|"
    r"transferencia_de_fianzas|/nuevos_2023/)",
)
RE_PUBLICATION_PATH = re.compile(
    r"(?i)(/urbanismo/|/algetenorte/|/documentacion/2026/|"
    r"edicto|exprop|bocm|planeam|espino|pe_algete|au_algete|mp1|decreto)",
)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?aytoalgete\.es)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)
RE_PREVIEW = re.compile(
    r'href="((?:https://algete\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:DOCUMENTACION|Urbanismo)/(?:[^/]+/)?(\d{4})(\d{2})")
RE_FECHA_YM_SLASH = re.compile(r"/DOCUMENTACION/(\d{4})/")
RE_BOCM_DATE = re.compile(r"BOCM-(\d{4})(\d{2})(\d{2})")
RE_FILENAME_DATE = re.compile(r"(\d{4})(\d{2})(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
MESES_ABBR = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}


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


def _fecha_from_url_or_name(url: str, title: str = "") -> str | None:
    blob = f"{url} {title}"
    m = RE_BOCM_DATE.search(blob)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FILENAME_DATE.search(Path(url).name)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM_SLASH.search(url)
    if m:
        return f"{m.group(1)}-01-01"
    m = re.search(r"(\d{1,2})(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)(\d{4})", blob, re.I)
    if m:
        try:
            return datetime(int(m.group(3)), MESES_ABBR[m.group(2).lower()], int(m.group(1))).strftime(
                "%Y-%m-%d"
            )
        except (ValueError, KeyError):
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(blob) if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_url(href: str) -> str:
    return urllib.parse.urljoin(BASE, unescape(href))


def _proyecto_tipo(title: str, url: str) -> str:
    blob = f"{title} {url}".lower()
    if "exprop" in blob:
        return "expropiación"
    if "informaci" in blob and "p" in blob:
        return "información pública"
    if "plan especial" in blob or "pe_" in blob or "pe " in blob:
        return "plan especial"
    if "avance" in blob or "sector" in blob or "algete norte" in blob:
        return "planeamiento"
    if "bocm" in blob:
        return "publicación BOCM"
    if "decreto" in blob or "edicto" in blob:
        return "edicto/decreto"
    if "modificaci" in blob or "mp1" in blob or "au_" in blob:
        return "modificación puntual"
    return "urbanismo"


class AlgeteAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla (PDFs urbanismo) + tablón espublico sede electrónica."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.planeamiento_url = str(self.config.get("planeamiento_url") or PLANEAMIENTO_URL)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-algete/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _collect_pdf_links(self, url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf = _abs_url(m.group(1))
            if pdf in seen:
                continue
            seen.add(pdf)
            anchor_m = re.search(
                rf'href="{re.escape(m.group(1))}"[^>]*>(.*?)</a>',
                html[m.start() : m.start() + 1200],
                re.I | re.S,
            )
            label = _strip_html(anchor_m.group(1)) if anchor_m else ""
            label = re.sub(r"\s*NUEVO\s*$", "", label, flags=re.I).strip()
            if not label or label in ("\u00a0", "&nbsp;"):
                label = unescape(Path(urllib.parse.unquote(pdf)).stem.replace("_", " "))
            rows.append(
                {
                    "titulo": label[:500],
                    "url": url,
                    "pdf_url": pdf,
                    "fecha": _fecha_from_url_or_name(pdf, label),
                    "origen": origen,
                    "blob": f"{label} {pdf}",
                }
            )
        return rows

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
            cells = [_strip_html(c) for c in RE_BOARD_CELL.findall(row_html)]
            cells = [c for c in cells if c]
            if len(cells) < 4:
                continue
            if cells[0] in ("Documento", "Expediente"):
                continue

            documento = cells[0] if len(cells) > 0 else ""
            expediente = cells[1] if len(cells) > 1 else ""
            procedimiento = cells[2] if len(cells) > 2 else ""
            categoria = cells[3] if len(cells) > 3 else ""
            descripcion = cells[4] if len(cells) > 4 else ""
            fecha_raw = cells[5] if len(cells) > 5 else ""

            preview_m = RE_PREVIEW.search(row_html)
            doc_url = preview_m.group(1) if preview_m else self.board_url
            if doc_url.startswith("/"):
                doc_url = f"{self.sede_base}{doc_url}"

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
                    "url": doc_url,
                    "blob": f"{documento} {expediente} {procedimiento} {categoria} {descripcion}",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "trámites licencia / declaración responsable",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de licencia y declaración responsable (Urbanismo)",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Formularios PDF; concesiones en tablón cuando se publiquen",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanísticos",
                "url": f"{self.sede_base}/",
                "source": "ayuntamiento",
                "nota": "Presentación digital de solicitudes (requiere identificación)",
            },
        ]
        return rows

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        pdf = row.get("pdf_url") or ""
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_SKIP_PDF.search(pdf) or RE_SKIP_PDF.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and not RE_PUBLICATION_PATH.search(pdf):
            return None
        if not RE_PROYECTO.search(blob) and not RE_PUBLICATION_PATH.search(pdf):
            return None
        key = pdf or row.get("titulo") or ""
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], pdf),
            "url": row.get("url") or self.urbanismo_url,
            "pdf_url": pdf or None,
            "source": "ayuntamiento",
            "origen": row.get("origen", "urbanismo_pdf"),
        }

    def _pdf_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        pdf = row.get("pdf_url") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not re.search(r"(?i)licencia|declaraci", blob):
            return None
        tipo = "declaración responsable / trámite licencia"
        if re.search(r"(?i)obra mayor", blob):
            tipo = "licencia obra mayor"
        elif re.search(r"(?i)declaraci", blob):
            tipo = "declaración responsable"
        return {
            "id": _stable_id("lic", pdf or blob),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row.get("pdf_url") or self.urbanismo_url,
            "source": "ayuntamiento",
            "origen": "urbanismo_formulario",
        }

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        meta = f"{row.get('categoria', '')} {row.get('procedimiento', '')}"
        if RE_BOARD_NON_URBAN.search(meta):
            return False
        return True

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
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
            "origen": "tablon_sede",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row.get("url") or ""),
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
        for page_url in (self.urbanismo_url,):
            for row in self._collect_pdf_links(page_url, "urbanismo_formulario"):
                rec = self._pdf_to_licencia(row)
                if rec and rec["id"] not in seen:
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
        for page_url in (self.urbanismo_url,):
            for row in self._collect_pdf_links(page_url, "urbanismo_formulario"):
                rec = self._pdf_to_licencia(row)
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

        for page_url, origen in (
            (self.urbanismo_url, "urbanismo_pdf"),
            (self.planeamiento_url, "planeamiento_pdf"),
        ):
            for row in self._collect_pdf_links(page_url, origen):
                add(self._pdf_to_proyecto(row))
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        pdf_n = sum(1 for r in rows if r.get("origen", "").endswith("_pdf"))
        tablon_n = sum(1 for r in rows if r.get("origen") == "tablon_sede")
        return {
            "rows": len(rows),
            "status": "ok",
            "pdf_items": pdf_n,
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
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
