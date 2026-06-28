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

WP_BASE = "https://www.vvapardillo.org"
SEDE_BASE = "https://sede.vvapardillo.org"
MUNICIPIO = "Villanueva del Pardillo"
ID_PREFIX = "villanueva-del-pardillo"

NORMATIVA_URL = f"{WP_BASE}/normativa-urbanistica"
TRAMITES_URL = f"{WP_BASE}/tramites/urbanismo"

DEFAULT_SEED_PAGES: list[str] = [
    NORMATIVA_URL,
    f"{WP_BASE}/index.php?id=99&option=com_sppagebuilder&view=page",
    f"{WP_BASE}/suz-i-10-las-vegas",
]

RE_PREVIEW = re.compile(
    r'href="(https://sede\.vvapardillo\.org/preview-document/[^"]+)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)
RE_PDF_HREF = re.compile(
    r'href="((?:https://(?:www\.)?vvapardillo\.org)?/images/doc/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|"
    r"primera ocupaci[oó]n|segregaci[oó]n|agrupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pepri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|sector|suz|"
    r"aprobaci[oó]n (?:inicial|definitiva)|bocm|anuncio.*planeam|fotovoltaica)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _abs_url(href: str) -> str:
    return unescape(urllib.parse.urljoin(f"{WP_BASE}/", href))


def _pdf_tipo(name: str, path: str) -> str:
    blob = f"{name} {path}".lower()
    if "estudiodetalle" in blob or "estudio de detalle" in blob:
        return "estudio de detalle"
    if "modificacion" in blob or "modificación" in blob:
        return "modificación planeamiento"
    if "pepri" in blob:
        return "PEPRI"
    if re.search(r"suzl|suzll|planparcial|plan-parcial|sector", blob):
        return "plan parcial"
    if "plan especial" in blob or "bloque" in blob and "anexo" in blob:
        return "plan especial"
    if "pgou" in blob or "/normativa/" in blob:
        return "PGOU"
    if "plano" in blob:
        return "plano ordenación"
    if "normas" in blob:
        return "normas urbanísticas"
    return "documento urbanismo"


def _pdf_titulo(name: str, path: str) -> str:
    stem = unescape(urllib.parse.unquote(Path(name).stem.replace("-", " ").replace("_", " ")))
    if len(stem) > 8:
        return f"{MUNICIPIO}: {stem}"[:500]
    parts = [p for p in path.split("/") if p and p != "images" and p != "doc"]
    label = " / ".join(parts[-3:]) if parts else name
    return f"{MUNICIPIO}: {label}"[:500]


class VillanuevaDelPardilloAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla (normativa PGOU PDFs) + sede eHome (tablón anuncios)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.normativa_url = str(self.config.get("normativa_url") or NORMATIVA_URL)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-villanueva-pardillo/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.vvapardillo.org" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_sede_ssl=True)
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
            if cells[0] in ("Documento",):
                continue

            preview_m = RE_PREVIEW.search(row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            title_m = re.search(r'title="([^"]*)"', row_html, re.I)
            documento = cells[0] if cells else ""
            expediente = cells[1] if len(cells) > 1 else ""
            procedimiento = cells[2] if len(cells) > 2 else ""
            categoria = cells[3] if len(cells) > 3 else ""
            descripcion = cells[4] if len(cells) > 4 else ""
            fecha_raw = cells[5] if len(cells) > 5 else ""
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

    def _collect_normativa_pdfs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = _abs_url(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = Path(urllib.parse.urlparse(pdf).path).name
                path = urllib.parse.urlparse(pdf).path
                rows.append(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": MUNICIPIO,
                        "titulo": _pdf_titulo(name, path),
                        "fecha": _fecha_from_pdf_url(pdf),
                        "tipo": _pdf_tipo(name, path),
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": "normativa_urbanistica",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.tramites_url)
        except urllib.error.URLError:
            html = ""

        if html and RE_LICENCIA.search(html):
            rows.append(
                {
                    "id": _stable_id("lic", self.tramites_url),
                    "fecha_concesion": None,
                    "tipo": "trámites licencia y declaración responsable",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Trámites de urbanismo — licencias y declaraciones responsables",
                    "url": self.tramites_url,
                    "source": "ayuntamiento",
                    "nota": "Formularios informativos; concesiones en tablón cuando se publican",
                    "origen": "tramites_urbanismo",
                }
            )

        sede_link = f"{self.sede_base}/"
        rows.append(
            {
                "id": _stable_id("lic", sede_link),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites y tablón de anuncios",
                "url": sede_link,
                "source": "ayuntamiento",
                "nota": "Presentación telemática de solicitudes urbanísticas",
                "origen": "sede_electronica",
            }
        )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
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
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            if row.get("categoria", "").lower() != "urbanismo":
                return None
        tipo = "urbanismo"
        if re.search(r"(?i)informaci[oó]n p[uú]blica|publicaci[oó]n bocm", blob):
            tipo = "información pública"
        elif re.search(r"(?i)plan (?:parcial|especial)|planeam|suz", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)estudio de detalle", blob):
            tipo = "estudio de detalle"
        elif re.search(r"(?i)convenio", blob):
            tipo = "convenio"
        return {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente"),
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
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_tablon"}

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

        for rec in self._collect_normativa_pdfs():
            add(rec)
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        normativa_n = sum(1 for r in rows if r.get("origen") == "normativa_urbanistica")
        tablon_n = sum(1 for r in rows if r.get("origen") == "tablon_sede")
        return {
            "rows": len(rows),
            "status": "ok",
            "normativa_pdfs": normativa_n,
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
