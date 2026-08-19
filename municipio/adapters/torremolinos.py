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

WP_BASE = "https://www.torremolinos.es"
SEDE_BASE = "https://torremolinos.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
TRANSPARENCY_URL = "https://transparencia.torremolinos.es/obras-publicas/"
PLANEA_URL = "https://planea.torremolinos.es/documentacion/"
MUNICIPIO = "Torremolinos"
ID_PREFIX = "torremolinos"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/ayuntamiento/urbanismo-infraestructuras/",
    TRANSPARENCY_URL,
    PLANEA_URL,
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura|apertura de local)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|pou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|atu|delimitaci[oó]n|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n|expropiaci[oó]n|avance|"
    r"calificaci[oó]n|divisi[oó]n en fases|uer|diligencia|acuerdo jgl|regeneraci[oó]n)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|bopma.*orientador|auxiliar administrativo|"
    r"polic[ií]a local|aparcamiento|abono|f[ií]sicas|oferta complementaria oep|"
    r"pe[oó]n|herrero|alba[nñ]il|jardinero|museo)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://torremolinos\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPEDIENTE = re.compile(r"(?i)(?:expediente|expte\.?|exp\.)\s*([0-9]+[/\-][0-9]+)")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
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


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "atu" in b or "delimitaci" in b and "actuaci" in b:
        return "ATU / delimitación"
    if "plan parcial" in b or " sup " in b or "sup-" in b or "me sup" in b:
        return "plan parcial"
    if "plan especial" in b or " sunp " in b:
        return "plan especial"
    if "pgom" in b or "pou" in b:
        return "planeamiento municipal"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "estudio de ordenaci" in b or "estudio ordenaci" in b:
        return "estudio de ordenación"
    if "reparcel" in b:
        return "reparcelación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "expropiaci" in b:
        return "expropiación"
    if "estudio de detalle" in b or "estudio detalle" in b:
        return "estudio de detalle"
    if "convenio" in b:
        return "convenio urbanístico"
    if "licencia" in b:
        return "licencia publicada"
    if "acuerdo jgl" in b or "diligencia" in b:
        return "acuerdo plenario"
    if "avance" in b:
        return "planeamiento"
    if "modificaci" in b:
        return "modificación puntual PGOU"
    return "urbanismo"


class TorremolinosAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Arthemia + transparencia + Planea Torremolinos + tablón espublico gestiona."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-torremolinos/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or WP_BASE, href))

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

    def _is_doc_href(self, href: str) -> bool:
        h = href.lower()
        return bool(
            re.search(r"(?i)\.(pdf|zip)(?:\?|$)", h)
            or "drive.google.com/file" in h
            or "transparencia.torremolinos.es" in h and ".pdf" in h
            or "torremolinos.es/wpsystem/wp-content/uploads" in h
            or "planea.torremolinos.es/wp-content/uploads" in h
        )

    def _collect_seed_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            page_title = ""
            title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
            if title_m:
                page_title = _strip_html(title_m.group(1))

            for m in RE_LINK.finditer(html):
                href = m.group(1)
                anchor = _strip_html(m.group(2))
                if href.startswith("#") or "favicon" in href.lower():
                    continue
                if not self._is_doc_href(href):
                    continue
                doc_url = self._abs_url(href, page_url)
                if doc_url in seen:
                    continue
                name = unescape(urllib.parse.unquote(Path(doc_url.split("?")[0]).name))
                titulo = anchor if len(anchor) > 5 else name
                blob = f"{titulo} {name} {doc_url} {page_url} {page_title}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                seen.add(doc_url)
                expte_m = RE_EXPEDIENTE.search(blob)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(f"{name} {doc_url} {anchor}"),
                        "url": page_url,
                        "doc_url": doc_url,
                        "blob": blob,
                        "expte": expte_m.group(1) if expte_m else None,
                        "origen": "seed",
                        "seed_page": page_url,
                    }
                )

            for m in re.finditer(
                r"<p[^>]*>\s*<strong[^>]*>(.*?)</strong>\s*</p>(.*?)(?=<p|<h[1-6]|$)",
                html,
                re.I | re.S,
            ):
                heading = _strip_html(m.group(1))
                block = m.group(2)
                if not RE_PROYECTO.search(heading):
                    continue
                expte_m = RE_EXPEDIENTE.search(heading)
                for lm in RE_LINK.finditer(block):
                    href = lm.group(1)
                    if not self._is_doc_href(href):
                        continue
                    doc_url = self._abs_url(href, page_url)
                    if doc_url in seen:
                        continue
                    anchor = _strip_html(lm.group(2))
                    titulo = heading
                    if anchor and len(anchor) > 3:
                        titulo = f"{heading} — {anchor}"[:500]
                    blob = f"{heading} {anchor} {doc_url}"
                    seen.add(doc_url)
                    rows.append(
                        {
                            "titulo": titulo[:500],
                            "fecha": _fecha_from_blob(blob),
                            "url": page_url,
                            "doc_url": doc_url,
                            "blob": blob,
                            "expte": expte_m.group(1) if expte_m else None,
                            "origen": "transparencia_expediente",
                            "seed_page": page_url,
                        }
                    )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y edictos publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{WP_BASE}/ayuntamiento/urbanismo-infraestructuras/"),
                "fecha_concesion": None,
                "tipo": "información urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — PGOU y modificaciones (web municipal)",
                "url": f"{WP_BASE}/ayuntamiento/urbanismo-infraestructuras/",
                "source": "ayuntamiento",
                "nota": "Sin listado tabular de licencias concedidas; solo documentación PGOU",
                "origen": "wp_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "regeneraci")):
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

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
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

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        doc_url = row["doc_url"]
        origen = row.get("origen", "seed")
        if "transparencia" in (row.get("seed_page") or ""):
            origen = "transparencia"
        elif "planea" in (row.get("seed_page") or ""):
            origen = "planea"
        elif "torremolinos.es" in (row.get("seed_page") or ""):
            origen = "wordpress"
        return {
            "id": _stable_id("proy", doc_url),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "pdf_url": doc_url,
            "source": "ayuntamiento",
            "expte": row.get("expte"),
            "origen": origen,
        }

    def _seed_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(row.get("titulo", "")):
            return None
        doc_url = row["doc_url"]
        return {
            "id": _stable_id("lic", doc_url),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "pdf_url": doc_url,
            "source": "ayuntamiento",
            "origen": row.get("origen", "seed"),
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_seed_docs():
            rec = self._seed_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "wp_tramite")),
            "seed": sum(1 for r in rows if r.get("origen") in ("seed", "transparencia_expediente")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_seed_docs():
            rec = self._seed_to_licencia(item)
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_seed_docs():
            add(self._seed_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "wordpress": sum(1 for r in rows if r.get("origen") == "wordpress"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "planea": sum(1 for r in rows if r.get("origen") == "planea"),
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
