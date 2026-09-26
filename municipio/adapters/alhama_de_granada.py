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

SEDE_BASE = "https://alhamadegranada.sedelectronica.es"
WP_BASE = "https://news.alhamadegranada.info"
BOARD_URL = f"{SEDE_BASE}/board/"
MUNICIPIO = "Alhama de Granada"
ID_PREFIX = "alhama-de-granada"

WP_STATIC_SEEDS: list[tuple[str, str]] = [
    ("informacion-urbanistica", "Información Urbanística"),
    ("pgou", "PGOU"),
    ("pgou-2014", "PGOU 2014"),
]

WP_POST_SEARCHES: list[str] = [
    "planeamiento",
    "pgou",
    "innovacion",
    "snu",
    "pepri",
    "licencia urban",
    "proyecto actuacion",
    "alegaciones pgou",
    "evaluacion ambiental",
    "variante alhama",
    "informacion publica planeamiento",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|venta productos)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pepri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional|preliminar)|parcela|suelo|sector|"
    r"cambio de uso|snu|innovaci[oó]n|alegaciones|evaluaci[oó]n ambiental|actuaci[oó]n|variante)",
)
RE_WP_PROY_TITLE = re.compile(
    r"(?i)(pgou|planeam(?:iento)?|pepri|snu\b|innovaci[oó]n al planeam|informaci[oó]n p[uú]blica|"
    r"alegaciones.*(?:pgou|innovaci[oó]n)|evaluaci[oó]n ambiental|reuni[oó]n informativa.*(?:pgou|planeam|innovaci[oó]n)|"
    r"variante de alhama|proyecto de actuaci[oó]n|actuaci[oó]n protegida|licencia urban|"
    r"exposici[oó]n p[uú]blica.*proyecto|edicto.*licencia|"
    r"aprobaci[oó]n (?:inicial|definitiva|preliminar).*(?:pgou|planeam|proyecto|innovaci[oó]n)|"
    r"intervenci[oó]n-consolidaci[oó]n|memoria de participaci[oó]n ciudadana.*(?:evaluaci[oó]n|innovaci[oó]n)|"
    r"cuestionario.*(?:innovaci[oó]n|planeam|pepri)|anuncio innovaci[oó]n|periodo de alegaciones.*pgou|"
    r"documento inicial estrat[eé]gico|delimitaci[oó]n del plan especial|bic conjunto|"
    r"actualizaci[oó]n del proyecto de trazado)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"fiestas|feria|bolsa|carrera|junta de gobierno local|"
    r"planificaci[oó]n y ordenaci[oó]n de personal|provisiones de puestos|"
    r"datos de la v[ií]a p[uú]blica|cambio denominaci[oó]n calle|"
    r"bop num \d+ correcion bases|bases.*carrera|decreto.*fiestas)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://alhamadegranada\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_STATIC_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{3,200})</a>', re.I)
RE_STATIC_DOC = re.compile(
    r"(?i)(pgou|planeam|innovaci[oó]n|snu|pepri|proyecto|actuaci[oó]n|estudio|memoria|planos|"
    r"bop|boja|ordenaci[oó]n|urban|licencia|variante|alegaciones|evaluaci[oó]n)",
)
RE_SKIP_STATIC = re.compile(
    r"(?i)(favicon|escudo|dir3|factura|ruta_aljibes|triptico_interfase|codigos_dir3)",
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


def _fecha_from_text(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
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
    if "variante" in n and "alhama" in n:
        return "infraestructura viaria"
    if "innovaci" in n and "pgou" in n:
        return "innovación PGOU"
    if "pepri" in n or "bic conjunto" in n:
        return "PEPRI"
    if "pgou" in n:
        return "PGOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "alegaciones" in n:
        return "alegaciones planeamiento"
    if "evaluaci" in n and "ambiental" in n:
        return "evaluación ambiental"
    if "licencia" in n:
        return "licencia urbanística"
    if "proyecto de actuaci" in n or "actuaci" in n and "proteg" in n:
        return "proyecto de actuación"
    if "planeam" in n:
        return "planeamiento"
    return "urbanismo"


class AlhamaDeGranadaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress news.alhamadegranada.info + sede espublico gestiona (tablón/transparencia)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alhama-de-granada/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        raw = self._fetch(url)
        return json.loads(raw)

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

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        seen_ids: set[int] = set()
        posts: list[dict[str, Any]] = []
        for term in WP_POST_SEARCHES:
            q = urllib.parse.quote(term)
            url = f"{self.wp_base}/wp-json/wp/v2/posts?per_page=100&search={q}"
            try:
                batch = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(batch, list):
                continue
            for post in batch:
                pid = post.get("id")
                if not isinstance(pid, int) or pid in seen_ids:
                    continue
                title = _clean_title(post.get("title", {}).get("rendered", ""))
                if not RE_WP_PROY_TITLE.search(title):
                    continue
                seen_ids.add(pid)
                posts.append(
                    {
                        "titulo": title,
                        "fecha": (post.get("date") or "")[:10] or None,
                        "url": post.get("link") or f"{self.wp_base}/",
                        "blob": title,
                    }
                )
        return posts

    def _collect_static_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for slug, label in WP_STATIC_SEEDS:
            page_url = f"{self.wp_base}/{slug}/"
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            rows.append(
                {
                    "titulo": label,
                    "fecha": None,
                    "url": page_url,
                    "tipo": "planeamiento" if "pgou" in slug else "urbanismo",
                    "origen": "web_static",
                    "blob": label,
                }
            )

            for m in RE_STATIC_LINK.finditer(html):
                href, text = m.group(1), _clean_title(m.group(2))
                if href.startswith("/"):
                    href = f"{self.wp_base}{href}"
                if not href.startswith(("http://", "https://")):
                    continue
                if RE_SKIP_STATIC.search(href):
                    continue
                blob = f"{text} {href}"
                if not RE_STATIC_DOC.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": text or href.split("/")[-1][:120],
                        "fecha": _fecha_from_text(href + " " + text),
                        "url": href,
                        "tipo": _proyecto_tipo(blob),
                        "origen": "web_documento",
                        "blob": blob,
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
                "id": _stable_id("lic", f"{self.wp_base}/informacion-urbanistica/"),
                "fecha_concesion": None,
                "tipo": "información urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Información urbanística — documentación PGOU/SNU",
                "url": f"{self.wp_base}/informacion-urbanistica/",
                "source": "ayuntamiento",
                "nota": "Documentos de planeamiento e innovación al PGOU en web municipal",
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
        if "licencias urban" in cat:
            return True
        urban_blob = re.sub(r"(?i)\bexpediente\b", "", blob)
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(urban_blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob) and "licencias urban" not in (row.get("categoria") or "").lower():
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
        if not RE_PROYECTO.search(urban_blob) and "licencias urban" not in (row.get("categoria") or "").lower():
            return None
        if RE_LICENCIA.search(blob) and not re.search(r"(?i)proyecto|aprobaci[oó]n|actuaci[oó]n|informaci[oó]n p[uú]blica", blob):
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

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row.get("titulo") or ""
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web_noticia",
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

        for item in self._collect_static_pages():
            add(self._wp_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._wp_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web_")),
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
