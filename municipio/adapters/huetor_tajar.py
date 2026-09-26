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

SEDE_BASE = "https://huetortajar.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
DOSSIER_URL = f"{SEDE_BASE}/dossier"
WEB_BASE = "https://huetortajar.org"
NORMATIVA_URL = f"{WEB_BASE}/transparencia/normativa-municipal/"
NNSS_URL = f"{WEB_BASE}/transparencia/normas-subsidiarias/"
PMVS_URL = f"{WEB_BASE}/transparencia/plan-municipal-de-vivienda-y-suelo/"
OBRAS_CITIZEN_URL = (
    f"{SEDE_BASE}/citizen-service/84d48a70-c98d-4e64-9932-c9e6f9d38a40"
)
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Huétor Tájar"
ID_PREFIX = "huetor-tajar"

DEFAULT_SEED_PAGES: list[str] = [
    NORMATIVA_URL,
    NNSS_URL,
    PMVS_URL,
    f"{WEB_BASE}/servicios/plan-municipal-de-vivienda-y-suelo/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|tasa.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|b[aá]sico|municipal)|pbom|pgou|nnss|"
    r"normas subsidiarias|convenio|informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|vivienda|"
    r"cambio de uso|ordenanza|entidades urban|edificaci[oó]n|inspecci[oó]n urban|reglamento.*urban)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|activa-t joven|polic[ií]a local|tribunal calificador|"
    r"subvenciones solicitadas)",
)
RE_URBAN_PDF = re.compile(
    r"(?i)(urban|edificaci[oó]n|licencia|planeam|nnss|subsidiari|vivienda.*suelo|"
    r"entidades urban|inspecci[oó]n urban|suelo|normativa urban|pmiu|memoria)",
)
RE_BOARD_ROW = re.compile(r'<tr[^>]*>\s*<td class="class_name".*?</tr>', re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://huetortajar\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
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
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "nnss" in b or "normas subsidiarias" in b:
        return "normas subsidiarias"
    if "plan municipal de vivienda" in b or "pmvs" in b:
        return "plan municipal de vivienda y suelo"
    if "inspecci" in b and "urban" in b:
        return "plan municipal de inspección urbanística"
    if "entidades urban" in b or "reglamento" in b and "urban" in b:
        return "normativa urbanística"
    if "ordenanza" in b and "edificaci" in b:
        return "ordenanza de edificación"
    if "memoria" in b and ("adaptaci" in b or "nnss" in b):
        return "memoria planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "licencia" in b:
        return "licencia publicada"
    if "planeamiento" in b or "situa" in b:
        return "planeamiento"
    return "urbanismo"


class HuetorTajarAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress huetortajar.org + sede espublico gestiona (tablón, dossier DIPGR)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.dossier_url = str(self.config.get("dossier_url") or DOSSIER_URL)
        self.normativa_url = str(self.config.get("normativa_url") or NORMATIVA_URL)
        self.nnss_url = str(self.config.get("nnss_url") or NNSS_URL)
        self.pmvs_url = str(self.config.get("pmvs_url") or PMVS_URL)
        self.obras_citizen_url = str(self.config.get("obras_citizen_url") or OBRAS_CITIZEN_URL)
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
        self._warmed = False

    def _request_with_retry(self, url: str, timeout: int = 90) -> bytes:
        ua = self.config.get("user_agent", "poc-bocm-huetor-tajar/1.0")
        last_err: Exception | None = None
        for attempt in range(4):
            time.sleep(self.delay_s)
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            try:
                with self._opener.open(req, timeout=timeout) as resp:
                    return resp.read()
            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch(self, url: str) -> str:
        raw = self._request_with_retry(url, timeout=120)
        return raw.decode("utf-8", errors="replace")

    def _warm_sede(self) -> None:
        if self._warmed:
            return
        try:
            self._fetch(self.board_url)
        except urllib.error.URLError:
            pass
        self._warmed = True

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

    def _is_local_href(self, href: str) -> bool:
        low = href.lower()
        return low.startswith("/") or "huetortajar.org" in low or "huetortajar.sedelectronica.es" in low

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

    def _collect_web_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            for m in re.finditer(
                r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                html,
                re.I | re.S,
            ):
                href = unescape(m.group(1))
                if not self._is_local_href(href):
                    continue
                abs_url = self._abs_web(href) if "huetortajar.org" in href or href.startswith("/") else self._abs_sede(href)
                if abs_url in seen:
                    continue
                anchor = _strip_html(m.group(2))
                blob = f"{anchor} {abs_url} {page_url}"
                if ".pdf" not in abs_url.lower() and "wp-content/uploads" not in abs_url.lower():
                    continue
                if not RE_URBAN_PDF.search(blob):
                    continue
                seen.add(abs_url)
                titulo = anchor[:500] if anchor else unescape(Path(abs_url).name.replace("-", " "))
                rows.append(
                    {
                        "url": abs_url,
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(blob),
                        "tipo": _proyecto_tipo(blob),
                        "blob": blob,
                        "origen": "web_transparencia",
                        "page_url": page_url,
                    }
                )

        return rows

    def _collect_dossier_tramites(self) -> list[dict[str, Any]]:
        self._warm_sede()
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]{5,200})</a>', html, re.I):
            href = unescape(m.group(1))
            title = _strip_html(m.group(2))
            if not title:
                continue
            blob = f"{title} {href}"
            if not RE_LICENCIA.search(blob) and not (
                "urban" in blob.lower() or "obra" in blob.lower() or "planeam" in blob.lower()
            ):
                continue
            abs_url = self._abs_sede(href)
            if abs_url in seen:
                continue
            seen.add(abs_url)
            rows.append(
                {
                    "url": abs_url,
                    "titulo": title[:500],
                    "fecha": None,
                    "tipo": "trámite urbanismo",
                    "blob": blob,
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _collect_situa(self) -> list[dict[str, Any]]:
        return [
            {
                "url": SITUA_SEARCH,
                "titulo": "Normas Subsidiarias de Planeamiento — consulta SITUA (Junta de Andalucía)",
                "fecha": "1998-02-26",
                "tipo": "normas subsidiarias",
                "blob": "NNSS Huétor Tájar planeamiento SITUA",
                "origen": "situa",
            }
        ]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Bandos y anuncios publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.obras_citizen_url),
                "fecha_concesion": None,
                "tipo": "trámites obras y urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Obras y Urbanismo — citizen-service sede",
                "url": self.obras_citizen_url,
                "source": "ayuntamiento",
                "nota": "Licencias DIPGR y trámites urbanísticos (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.normativa_url),
                "fecha_concesion": None,
                "tipo": "ordenanzas licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenanza fiscal nº 15 — tasa licencias urbanísticas",
                "url": f"{self.web_base}/wp-content/uploads/2023/03/15-ORD.-FISCAL-15-TASA-LICENCIAS-URBANISTICAS.pdf",
                "source": "ayuntamiento",
                "nota": "Normativa fiscal de licencias publicada en transparencia",
                "origen": "web_normativa",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "información pública")):
            return True
        if "ordenanza" in cat or "urban" in cat:
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
        elif re.search(r"(?i)licencias urban", blob):
            tipo = "licencia urbanística"
        elif re.search(r"(?i)obra|icio", blob):
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
        if not RE_PROYECTO.search(blob) and "información pública" not in proc and "ordenanza" not in proc:
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

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_dossier_tramites():
            if not RE_LICENCIA.search(item.get("blob") or ""):
                continue
            rec = self._tramite_to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(
                1
                for r in rows
                if r.get("origen") in ("sede_tablon", "sede_tramite", "web_normativa")
            ),
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
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
        for item in self._collect_dossier_tramites():
            if not RE_LICENCIA.search(item.get("blob") or ""):
                continue
            rec = self._tramite_to_licencia(item)
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
        for item in self._collect_web_pdfs():
            add(self._doc_to_proyecto(item))
        for item in self._collect_situa():
            add(self._doc_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web": sum(1 for r in rows if r.get("origen") == "web_transparencia"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
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
