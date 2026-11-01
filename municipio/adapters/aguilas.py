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
from municipio.geometry import record_geometry

WEB_BASE = "https://www.ayuntamientodeaguilas.org"
SEDE_BASE = "https://aguilas.sedelectronica.es"
TRANSPARENCIA_BASE = "https://transparencia.ayuntamientodeaguilas.org"
MUNICIPIO = "Águilas"
ID_PREFIX = "aguilas"

BOARD_URL = f"{SEDE_BASE}/board"
PROCEDIMIENTOS_URL = f"{WEB_BASE}/procedimientos"

DEFAULT_TRANSPARENCIA_SEEDS: tuple[str, ...] = (
    f"{TRANSPARENCIA_BASE}/obras-publicas-y-urbanismo/",
    f"{TRANSPARENCIA_BASE}/obras-publicas-y-urbanismo/plan-general-de-ordenacion-urbana/",
    f"{TRANSPARENCIA_BASE}/obras-publicas-y-urbanismo/convenios-urbanisticos/",
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|recepciones? de obra|primera ocupaci[oó]n|2ª ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmo|convenio|"
    r"informaci[oó]n p[uú]blica|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|borm|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|normativa urban|evaluaci[oó]n ambiental|"
    r"delimitaci[oó]n|urbanizaci[oó]n|ni[aá]gara|isla del fraile|pgou)",
)
RE_BOARD_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan parcial|pgou|urbaniz|sector|convenio|borm|"
    r"recepci[oó]n de obra|licencia|normativa urban|ni[aá]gara|isla del fraile)",
)
RE_CONTRATACION = re.compile(r"(?i)contrataci")
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"mesa de contrataci[oó]n|licitaci[oó]n electr[oó]nica|pleno ordinario|"
    r"decreto 2026-\d+ \[resoluci[oó]n pr/|subvenci[oó]n|empleo p[uú]blico)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://aguilas\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,6}/\d{4})")
RE_PDF_LINK = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_OBRAS_PROC = re.compile(
    r'data-ayun-category="obras"[^>]*>.*?titular-capa-interna[^>]*>([^<]+)',
    re.I | re.S,
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


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "convenio" in n:
        return "convenio urbanístico"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "urbanizaci" in n:
        return "urbanización"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "borm" in n or "aprobaci" in n:
        return "aprobación planeamiento"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


class AguilasAyuntamientoAdapter(AyuntamientoAdapter):
    """Web municipal + transparencia WP + sede espublico gestiona (tablón /board)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.procedimientos_url = str(
            self.config.get("procedimientos_url") or PROCEDIMIENTOS_URL
        )
        self.transparencia_seeds = tuple(
            self.config.get("transparencia_seeds") or DEFAULT_TRANSPARENCIA_SEEDS
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, retries: int | None = None) -> str:
        ua = self.config.get("user_agent", "poc-bocm-aguilas/1.0")
        if retries is None:
            retries = int(self.config.get("fetch_retries", 2))
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": ua, "Accept-Language": "es;q=0.9"},
            )
            try:
                with urllib.request.urlopen(
                    req,
                    timeout=int(self.config.get("fetch_timeout_s", 60)),
                    context=self._ssl_ctx,
                ) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(charset, errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_err = exc
                if attempt + 1 < retries:
                    time.sleep(1.5 * (attempt + 1))
        raise last_err or urllib.error.URLError("fetch failed")

    def _abs(self, base: str, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{base.rstrip('/')}/", href))

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

    def _collect_procedimientos_obras(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.procedimientos_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_OBRAS_PROC.finditer(html):
            titulo = _strip_html(m.group(1))
            if not titulo or len(titulo) < 8:
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": None,
                    "url": self.procedimientos_url,
                    "blob": f"{titulo} obras licencia urbanismo",
                    "origen": "procedimientos_obras",
                    "tipo_tramite": titulo,
                }
            )
        return rows

    def _collect_transparencia(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in self.transparencia_seeds:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            page_title = _strip_html(re.search(r"<title>([^<]+)", html, re.I).group(1) if re.search(r"<title>", html) else seed)
            key = f"page:{seed}"
            if key not in seen:
                seen.add(key)
                rows.append(
                    {
                        "titulo": page_title or "Transparencia urbanismo",
                        "fecha": None,
                        "url": seed,
                        "blob": f"{page_title} planeamiento urbanismo pgou convenio",
                        "origen": "transparencia",
                    }
                )
            for pm in RE_PDF_LINK.finditer(html):
                href = unescape(pm.group(1))
                if href in seen:
                    continue
                if not re.search(r"(?i)urban|pgou|plan|orden|convenio|norma", href):
                    continue
                seen.add(href)
                pdf_url = self._abs(TRANSPARENCIA_BASE, href)
                label = pdf_url.rsplit("/", 1)[-1].replace("%20", " ")[:120]
                rows.append(
                    {
                        "titulo": f"Documento urbanístico — {label}",
                        "fecha": None,
                        "url": pdf_url,
                        "blob": f"{label} pgou planeamiento urbanismo",
                        "origen": "transparencia_pdf",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios (sede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.procedimientos_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites OBRAS",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Procedimientos municipales — categoría OBRAS",
                "url": self.procedimientos_url,
                "source": "ayuntamiento",
                "nota": "Formularios informativos; sin histórico de concesiones",
                "origen": "web_procedimientos",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "trámites sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites (sede)",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc or k in cat for k in ("urban", "licencia", "actividad", "obra", "recepci")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _procedimiento_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        return {
            "id": _stable_id("lic", f"proc:{titulo}"),
            "fecha_concesion": row.get("fecha"),
            "tipo": titulo[:120],
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "procedimientos_obras",
        }

    def _generic_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        exp_m = RE_EXPTE.search(blob)
        key = exp_m.group(1) if exp_m else row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("proy", str(key)),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": exp_m.group(1) if exp_m else None,
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        proc = row.get("procedimiento") or ""
        if RE_CONTRATACION.search(proc) and not RE_BOARD_PROYECTO.search(blob):
            return None
        if not RE_BOARD_PROYECTO.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_BOARD_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_procedimientos_obras():
            rec = self._procedimiento_to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "procedimientos": sum(1 for r in rows if r.get("origen") == "procedimientos_obras"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_procedimientos")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_procedimientos_obras():
            existing[self._procedimiento_to_licencia(item)["id"]] = self._procedimiento_to_licencia(item)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
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

        for item in self._collect_transparencia():
            add(self._generic_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia": sum(1 for r in rows if (r.get("origen") or "").startswith("transparencia")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, after - before),
                    "with_geometry": result.get("with_geometry", 0),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": result.get("with_geometry", 0),
        }
