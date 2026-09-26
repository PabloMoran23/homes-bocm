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

WP_BASE = "https://guadix.es"
SEDE_BASE = "https://guadix.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
MUNICIPIO = "Guadix"
ID_PREFIX = "guadix"

SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
SITUA_PGOU_GUADIX = (
    "https://ws132.juntadeandalucia.es/situadifusion/pages/planeamientoGeneralCompartir.jsf?"
    "bXVuaWNpcGlvc3NlbGVjY2lvbmFkb3M9MTgwODkmbXVuaWNpcGlvc1NlbGVjPUdVQURJWCZjb2RpZ29zTXVuaWNpcGlvcz0xODA4OSZ"
    "jb2RGaWd1cmE9MzkxOCZqX2lkNjpqX2lkMzU9al9pZDY6al9pZDM1JmNoZWNrQm94U2VsPWFwcm9iYWRvJmNvZEZpZ3VyYUJ1cz0z"
    "kxOCZERhdGFUYWJsZXNfVGFibGVfMF9sZW5ndGg9MTAmal9pZDY9al9pZDYmamF2YXguZmFjZXMuVmlld1N0YXRlPWpfaWQ0Jn"
    "RpdHVsb05OU1NQUD1QbGFuZWFtaWVudG8gZ2VuZXJhbCBhcHJvYmFkbyBkZSBHVUFESVgmY29kaWdvc05vbWJyZXNNdW5pY2l"
    "waW9zPVt7ImlkIjoiMTgwODkiLCJub21icmUiOiJHVUFESVgifV0="
)
VITUA_URL = (
    "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/"
)
URBANISMO_URL = f"{WP_BASE}/urbanismo-patrimonio/"
MEMORIA_PDF = f"{WP_BASE}/astythuk/2022/05/Anexo-3-Memoria.pdf"

WP_SEARCH_TERMS = (
    "plan especial casco historico",
    "pgou",
    "convenio urbanistico",
    "informacion publica urbanismo",
    "agenda urbana",
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|venta productos)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|sunp|supi|ordenanza|rectificaci[oó]n descriptiva|divisi[oó]n|segregaci[oó]n|"
    r"innovaci[oó]n|casco hist[oó]rico|agenda urbana|vitua|situa)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|padron|regantes|residuos urbanos|subasta de bienes|"
    r"contrataciones patrimoniales|resoluci[oó]n alcald[ií]a|promoci[oó]n interna|"
    r"rrhh|bolsa de trabajo|auxiliar administrativo)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://guadix\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if "plan especial" in blob or "casco hist" in blob:
        return "plan especial"
    if re.search(r"(?i)innovaci[oó]n.*pgou|modificaci[oó]n.*pgou", blob):
        return "modificación PGOU"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "convenio urban" in blob:
        return "convenio urbanístico"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "agenda urbana" in blob:
        return "agenda urbana"
    if "memoria" in blob:
        return "memoria planeamiento"
    if "licencia" in blob:
        return "licencia publicada"
    return "urbanismo"


class GuadixAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress guadix.es + sede espublico gestiona (tablón / transparencia urbanismo)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, insecure: bool | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-guadix/1.0")},
        )
        if insecure is False:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with self._opener.open(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-guadix/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []
        for term in WP_SEARCH_TERMS:
            api_url = (
                f"{self.wp_base}/wp-json/wp/v2/posts?"
                f"{urllib.parse.urlencode({'search': term, 'per_page': 20})}"
            )
            try:
                posts = self._fetch_json(api_url)
            except (urllib.error.URLError, json.JSONDecodeError, ValueError):
                continue
            if not isinstance(posts, list):
                continue
            for post in posts:
                link = str(post.get("link") or "").strip()
                title = _strip_html(str(post.get("title", {}).get("rendered") or ""))
                if not link or link in seen_urls or not title:
                    continue
                if not RE_PROYECTO.search(title) and not RE_LICENCIA.search(title):
                    continue
                seen_urls.add(link)
                fecha_raw = str(post.get("date") or "")[:10]
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha_raw if re.match(r"\d{4}-\d{2}-\d{2}", fecha_raw) else None,
                        "url": link,
                        "blob": title,
                        "origen": "web_wp",
                    }
                )
        return rows

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        static: list[tuple[str, str, str, str | None]] = [
            (SITUA_SEARCH, "PGOU Guadix — consulta SITUA (Junta de Andalucía)", "planeamiento", None),
            (
                SITUA_PGOU_GUADIX,
                "Planeamiento general aprobado de Guadix — SITUADIFusión",
                "PGOU",
                None,
            ),
            (VITUA_URL, "Visor VITUA — planeamiento urbanístico Andalucía", "planeamiento", None),
            (URBANISMO_URL, "Urbanismo y Patrimonio — web municipal", "urbanismo", None),
            (
                MEMORIA_PDF,
                "Anexo 3 Memoria — documentación urbanismo",
                "memoria planeamiento",
                "2022-05-01",
            ),
            (
                f"{self.sede_base}/transparency",
                "Portal transparencia — sección Urbanismo, Obras Públicas y Medio Ambiente (269 docs)",
                "planeamiento",
                None,
            ),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo, tipo, fecha in static:
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": fecha,
                    "tipo": tipo,
                    "url": url,
                    "blob": titulo,
                    "origen": "web_static",
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
                "nota": "Requiere identificación Cl@ve; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", URBANISMO_URL),
                "fecha_concesion": None,
                "tipo": "departamento urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo y Patrimonio — información y trámites",
                "url": URBANISMO_URL,
                "source": "ayuntamiento",
                "nota": "Web municipal WordPress; sin listado histórico de licencias concedidas",
                "origen": "web_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if cat == "urbanismo" or "planeamiento" in proc:
            return True
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        if any(k in proc for k in ("licencia", "actividad", "obra")):
            return True
        if proc == "disposiciones normativas" and RE_PROYECTO.search(blob):
            return True
        urban_blob = re.sub(r"(?i)\bexpediente\b", "", blob)
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(urban_blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
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
        cat = (row.get("categoria") or "").lower()
        urban_blob = re.sub(r"(?i)\bexpediente\b", "", blob)
        if (
            not RE_PROYECTO.search(urban_blob)
            and "planeamiento" not in proc
            and cat != "urbanismo"
            and "ordenanza" not in proc.lower()
        ):
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

    def _static_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        title = row["titulo"]
        url = row["url"]
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": row.get("fecha") or _fecha_from_blob(title, url),
            "tipo": row.get("tipo") or _proyecto_tipo(title),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web_static",
        }

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        title = row["titulo"]
        url = row["url"]
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": row.get("fecha") or _fecha_from_blob(title, url),
            "tipo": _proyecto_tipo(title),
            "url": url,
            "source": "ayuntamiento",
            "origen": "web_wp",
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
            "info": sum(
                1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")
            ),
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

        for item in self._collect_proyecto_info_pages():
            add(self._static_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._wp_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web": sum(1 for r in rows if r.get("origen") in ("web_static", "web_wp")),
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
