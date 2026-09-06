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

SEDE_BASE = "https://almunecar.sedelectronica.es"
TRANSPARENCY_BASE = "https://portaltransparencia.almunecar.es"
BOARD_URL = f"{SEDE_BASE}/board/"
SITUA_URL = (
    "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41236"
)
MUNICIPIO = "Almuñécar"
ID_PREFIX = "almunecar"

TRANSPARENCY_SEEDS: list[str] = [
    f"{TRANSPARENCY_BASE}/medioambiental-urbanisticay-deinfraestructuras/",
    f"{TRANSPARENCY_BASE}/informacion-publica-urbanismo-e-infraestructuras/",
    f"{TRANSPARENCY_BASE}/medioambiental-urbanisticay-deinfraestructuras/planeamiento/",
    f"{TRANSPARENCY_BASE}/medioambiental-urbanisticay-deinfraestructuras/avance-pgou/",
    f"{TRANSPARENCY_BASE}/medioambiental-urbanisticay-deinfraestructuras/tramitacion-ambiental-revision-pgou-almunecar-la-herradura/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|venta productos|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pepri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional|preliminar)|parcela|suelo|sector|"
    r"cambio de uso|snu|innovaci[oó]n|alegaciones|evaluaci[oó]n ambiental|actuaci[oó]n|"
    r"delimitaci[oó]n|atu\b|ari\b|redelimit|mp\.?\d|euc\b|normativa urban|cat[aá]logo)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"fiestas|feria|bolsa|carrera|junta de gobierno local|"
    r"planificaci[oó]n y ordenaci[oó]n de personal|provisiones de puestos|"
    r"cobranza iae|subvenci[oó]n|reglamento productividad polic[ií]a|"
    r"bando alcalde.*publicidad|concurso.*guitarra|bases.*concurso)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://almunecar\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{3,300})</a>', re.I | re.S)
RE_SKIP_LINK = re.compile(
    r"(?i)(favicon|escudo|facebook|twitter|instagram|youtube|#|javascript:|"
    r"wp-json|feed/|xmlrpc|accesibilidad|mapa-del-sitio|cookies|privacy|"
    r"plantilla-de-personal|tarjetas-de-aparcamiento|comisiones-informativas|"
    r"competencias-del-ayuntamiento|plan-anual-normativo|proyectos-de-ordenanzas)",
)
RE_DOC_EXT = re.compile(r"(?i)\.(pdf|zip|odt|docx?)(\?|$)")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_PATH = re.compile(r"/(20\d{2})/(\d{2})/")
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
    m = RE_FECHA_PATH.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
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


def _clean_title(text: str) -> str:
    return _strip_html(text)[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pgou" in n and "revisi" in n:
        return "revisión PGOU"
    if "pgou" in n:
        return "PGOU"
    if "plan parcial" in n or re.search(r"\bpp\d|mp\.?\d|mp\d", n):
        return "plan parcial"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "estudio de ordenaci" in n or "estudio de ordenacion" in n:
        return "estudio de ordenación"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "delimitaci" in n or "atu" in n:
        return "delimitación ATU"
    if "ari" in n and ("taramay" in n or "reforma interior" in n):
        return "ARI"
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual"
    if "evaluaci" in n and "ambiental" in n:
        return "evaluación ambiental"
    if "licencia" in n:
        return "licencia urbanística"
    if "planeam" in n:
        return "planeamiento"
    return "urbanismo"


class AlmunecarAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona (tablón) + portal transparencia WordPress (planeamiento/IP)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or TRANSPARENCY_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transparency_base = str(
            self.config.get("transparency_base") or TRANSPARENCY_BASE
        ).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-almunecar/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_transparency(self, href: str) -> str:
        if href.startswith("//"):
            return f"https:{href}"
        if href.startswith("/"):
            return f"{self.transparency_base}{href}"
        return href

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

    def _collect_transparency_docs(self) -> list[dict[str, Any]]:
        seeds = list(self.config.get("transparency_seeds") or TRANSPARENCY_SEEDS)
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add_row(url: str, titulo: str, blob: str, origen: str = "transparencia") -> None:
            if url in seen_urls:
                return
            if RE_SKIP_LINK.search(url):
                return
            if not RE_PROYECTO.search(blob) and not RE_DOC_EXT.search(url):
                return
            seen_urls.add(url)
            rows.append(
                {
                    "titulo": _clean_title(titulo) or Path(urllib.parse.urlparse(url).path).name,
                    "fecha": _fecha_from_blob(f"{titulo} {url}"),
                    "url": url,
                    "tipo": _proyecto_tipo(blob),
                    "origen": origen,
                    "blob": blob[:2000],
                }
            )

        for seed in seeds:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue

            add_row(
                seed,
                _proyecto_tipo(seed),
                f"{seed} planeamiento urbanismo Almuñécar",
                origen="transparencia_indice",
            )

            for m in RE_LINK.finditer(html):
                href = self._abs_transparency(m.group(1))
                text = _clean_title(m.group(2))
                if RE_SKIP_LINK.search(href):
                    continue
                blob = f"{text} {href}"

                if href.startswith(self.transparency_base) and RE_DOC_EXT.search(href):
                    add_row(href, text, blob)
                    continue

                if RE_DOC_EXT.search(href) and RE_PROYECTO.search(blob):
                    add_row(href, text, blob)
                    continue

                if (
                    href.startswith(self.transparency_base)
                    and "/medioambiental-urbanisticay-deinfraestructuras/" in href
                    and href not in seeds
                    and href not in seen_urls
                    and RE_PROYECTO.search(blob)
                ):
                    seeds.append(href)

        add_row(
            SITUA_URL,
            "PGOU Almuñécar — consulta SITUA (Junta de Andalucía)",
            "PGOU planeamiento SITUA Almuñécar",
            origen="situa",
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
                "id": _stable_id(
                    "lic",
                    f"{self.transparency_base}/medioambiental-urbanisticay-deinfraestructuras/",
                ),
                "fecha_concesion": None,
                "tipo": "información urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — urbanismo e infraestructuras",
                "url": f"{self.transparency_base}/medioambiental-urbanisticay-deinfraestructuras/",
                "source": "ayuntamiento",
                "nota": "PGOU, modificaciones puntuales, IP y documentación de planeamiento",
                "origen": "web_tramite",
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
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        if "licencias" in cat:
            return True
        urban_blob = re.sub(r"(?i)\bexpediente\b", "", blob)
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(urban_blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob) and "licencias" not in (row.get("procedimiento") or "").lower():
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra|urban", blob):
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
        proc = (row.get("procedimiento") or "").lower()
        urban_blob = re.sub(r"(?i)\bexpediente\b", "", blob)
        if not RE_PROYECTO.search(urban_blob) and "licencias" not in proc:
            return None
        if RE_LICENCIA.search(blob) and not re.search(
            r"(?i)proyecto|aprobaci[oó]n|actuaci[oó]n|informaci[oó]n p[uú]blica|edicto",
            blob,
        ):
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
        blob = row.get("blob") or row.get("titulo") or ""
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "transparencia",
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

        for item in self._collect_transparency_docs():
            add(self._doc_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(
                1 for r in rows if str(r.get("origen", "")).startswith("transparencia")
            ),
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
