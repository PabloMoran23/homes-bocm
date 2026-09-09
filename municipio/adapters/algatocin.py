from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

SEDE_BASE = "https://algatocin.sedelectronica.es"
WEB_BASE = "https://www.algatocin.es"
BOARD_URL = f"{SEDE_BASE}/board/"
DIP_PGOU_URL = "https://www.malaga.es/delegacionfomento/planeamiento/ficha.asp?mun=29006&cod=736"
MUNICIPIO = "Algatocín"
ID_PREFIX = "algatocin"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura| de ocupaci[oó]n)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|uso com[uú]n especial)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bopma|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n descriptiva|dafo|"
    r"regularizaci[oó]n|asimilado|fuera de orden|no urbanizable|consulta p[uú]blica)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"empleo p[uú]blico|oferta empleo|cobranza iae|padrones|censo electoral|"
    r"pe[oó]n (?:construcci|forestal|limpieza)|acreedores por fallecimiento)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://algatocin\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_TRANSPARENCY_FOLDER = re.compile(
    r'class="gIconLink exp"[^>]*>(.*?)(?:<span class="linkExtraInfo">|$)',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if "dafo" in blob or "regularizaci" in blob or "no urbanizable" in blob:
        return "ordenanza urbanística"
    if "plan especial" in blob or "pe_" in blob:
        return "plan especial"
    if "estudio de detalle" in blob or "estudio detalle" in blob:
        return "estudio de detalle"
    if "plan parcial" in blob:
        return "plan parcial"
    if "pgom" in blob or "avance" in blob:
        return "planeamiento"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "consulta p" in blob and "blica" in blob:
        return "consulta pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "licencia" in blob:
        return "licencia publicada"
    return "urbanismo"


class AlgatocinAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona + web Diputación Málaga: tablón y transparencia urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparency_folders: list[dict[str, str]] = list(
            self.config.get("transparency_folders") or []
        )
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-algatocin/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

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

    def _collect_transparency_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        preview_re = re.compile(
            r'href="((?:https://algatocin\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"'
            r'[^>]*>([^<]+)',
            re.I,
        )
        for folder in self.transparency_folders:
            url = str(folder.get("url") or "").strip()
            if not url:
                continue
            folder_title = str(folder.get("titulo") or "").strip()
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue

            seen_urls: set[str] = set()
            for m in preview_re.finditer(html):
                doc_url = m.group(1)
                if doc_url.startswith("/"):
                    doc_url = f"{self.sede_base}{doc_url}"
                if doc_url in seen_urls:
                    continue
                seen_urls.add(doc_url)
                doc_title = _strip_html(m.group(2))
                if not doc_title or len(doc_title) < 4:
                    continue
                titulo = doc_title
                if folder_title and folder_title.lower() not in titulo.lower():
                    titulo = f"{folder_title} — {doc_title}"
                if not RE_PROYECTO.search(titulo) and not RE_PROYECTO.search(folder_title):
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(f"{folder_title} {doc_title}"),
                        "url": doc_url,
                        "procedimiento": folder_title or "planeamiento urbanístico",
                        "blob": f"{folder_title} {doc_title}",
                        "folder_url": url,
                    }
                )

            for m in RE_TRANSPARENCY_FOLDER.finditer(html):
                sub_title = _strip_html(m.group(1))
                if not sub_title or len(sub_title) < 8:
                    continue
                if not RE_PROYECTO.search(sub_title) and not RE_PROYECTO.search(folder_title):
                    continue
                combined = f"{folder_title} — {sub_title}" if folder_title else sub_title
                rows.append(
                    {
                        "titulo": combined[:500],
                        "fecha": _fecha_from_blob(combined),
                        "url": url,
                        "procedimiento": folder_title or "planeamiento urbanístico",
                        "blob": combined,
                        "folder_url": url,
                    }
                )

            if folder_title and RE_PROYECTO.search(folder_title) and not seen_urls:
                rows.append(
                    {
                        "titulo": folder_title[:500],
                        "fecha": _fecha_from_blob(folder_title),
                        "url": url,
                        "procedimiento": "planeamiento urbanístico",
                        "blob": folder_title,
                        "folder_url": url,
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
                "titulo": "Tablón de anuncios — licencias de obra y actividad",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y edictos publicados en sede electrónica espublico",
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
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/10900/punto-informacion-catastral"),
                "fecha_concesion": None,
                "tipo": "punto información catastral",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Punto de Información Catastral (P.I.C.)",
                "url": f"{self.web_base}/10900/punto-informacion-catastral",
                "source": "ayuntamiento",
                "nota": "Certificaciones catastrales en sede del ayuntamiento (c/ Fuente 2)",
                "origen": "web_tramite",
            },
        ]

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", DIP_PGOU_URL),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Algatocín — documentos de avance (Diputación Málaga)",
                "fecha": None,
                "tipo": "PGOU",
                "url": DIP_PGOU_URL,
                "source": "ayuntamiento",
                "origen": "diputacion_planeamiento",
            },
            {
                "id": _stable_id(
                    "proy",
                    f"{self.web_base}/6873/ordenanza-del-registro-publico-municipal-de-demandantes-de-viviendas-protegidas-de-algatocin",
                ),
                "municipio": MUNICIPIO,
                "titulo": "Ordenanza registro público demandantes viviendas protegidas",
                "fecha": None,
                "tipo": "ordenanza urbanística",
                "url": (
                    f"{self.web_base}/6873/"
                    "ordenanza-del-registro-publico-municipal-de-demandantes-de-viviendas-protegidas-de-algatocin"
                ),
                "source": "ayuntamiento",
                "origen": "web_normativa",
            },
            {
                "id": _stable_id(
                    "proy",
                    "https://algatocin.sedelectronica.es/transparency/74eefec2-abd4-4c14-be2f-20f83913f444/",
                ),
                "municipio": MUNICIPIO,
                "titulo": "Normas en período de Consulta Pública previa",
                "fecha": None,
                "tipo": "consulta pública",
                "url": "https://algatocin.sedelectronica.es/transparency/74eefec2-abd4-4c14-be2f-20f83913f444/",
                "source": "ayuntamiento",
                "origen": "transparencia",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "ocupaci")):
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
        if "ocupaci" in proc:
            tipo = "licencia de ocupación"
        elif "actividad" in proc:
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
        if RE_BOARD_NON_URBAN.search(blob):
            return None
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
            "tipo": _proyecto_tipo(row["titulo"], row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _transparency_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        title = row["titulo"]
        key = row.get("url") or title
        return {
            "id": _stable_id("proy", f"transparency:{key}"),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(title, row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "transparencia",
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
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
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

        for rec in self._collect_proyecto_info_pages():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_transparency_documents():
            add(self._transparency_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "static": sum(
                1
                for r in rows
                if r.get("origen") in ("diputacion_planeamiento", "web_normativa")
            ),
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
