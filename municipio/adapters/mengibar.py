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

WEB_BASE = "https://aytomengibar.com"
SEDE_BASE = "https://aytomengibar.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
PGOM_URL = f"{WEB_BASE}/pgom-plan-general-de-ordenacion-municipal-de-mengibar/"
SITUA_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=23061"
MUNICIPIO = "Mengíbar"
ID_PREFIX = "mengibar"
WP_URBANISMO_CAT = 97

TRANSPARENCY_SEEDS: list[str] = [
    f"{SEDE_BASE}/transparency/bd7b2e83-deab-4fb7-9e2c-dbc2be20177e/",
    f"{SEDE_BASE}/transparency",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|tasa por licencias urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|innovaci[oó]n|normas subsidiarias|actuaci[oó]n|autorizaci[oó]n previa|"
    r"delimitaci[oó]n|arroyo|dph|pol[ií]gono|licencia|reordenaci[oó]n.*tr[aá]fico|"
    r"asfaltado|transformaci[oó]n urbana)",
)
RE_WP_SKIP = re.compile(
    r"(?i)(concurso nacional de alba[nñ]iler|halloween|andaluc[ií]a activa|"
    r"carretera segura|arrendamiento vivienda|contrato de obra para la ejecuci[oó]n del proyecto|"
    r"acuerdo marco para el suministro|subvenci[oó]n del programa|mercado de abastos|"
    r"casa de la cultura|muro de contenci[oó]n)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"elecciones|censo electoral|cobranza|subvenci[oó]n|empleo p[uú]blico|"
    r"plan especial de empleo|tribunal de selecci[oó]n)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://aytomengibar\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_EXPDTE = re.compile(r"(?i)expediente\s+([\d]+(?:BIS)?/\d{4})")
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
    if "pgom" in b or "pgou" in b or "plan general" in b:
        return "PGOM"
    if "innovaci" in b or "normas subsidiarias" in b:
        return "modificación planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "plan parcial" in b or "actuaci" in b:
        return "actuación urbanística"
    if "licencia" in b:
        return "licencia publicada"
    if "reordenaci" in b and "tr[aá]fico" in b:
        return "reordenación tráfico"
    if "asfaltado" in b:
        return "obra vial"
    if "expediente" in b:
        return "expediente urbanístico"
    return "urbanismo"


class MengibarAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress aytomengibar.com + sede espublico gestiona + PGOM + SITUADIFUSION."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.pgom_url = str(self.config.get("pgom_url") or PGOM_URL)
        self.situa_url = str(self.config.get("situa_url") or SITUA_URL)
        self.transparency_seeds = list(self.config.get("transparency_seeds") or TRANSPARENCY_SEEDS)
        self.wp_urbanismo_cat = int(self.config.get("wp_urbanismo_cat") or WP_URBANISMO_CAT)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-mengibar/1.0")},
        )
        use_ssl = use_sede_ssl or "sedelectronica.es" in url
        if use_ssl:
            with self._opener.open(req, timeout=90) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", href)

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_sede_ssl=True)
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
                url = self._abs_sede(url)

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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in self.transparency_seeds:
            try:
                html = self._fetch(seed, use_sede_ssl=True)
            except urllib.error.URLError:
                continue
            for m in re.finditer(
                r'href="([^"]+)"[^>]*>([^<]{5,300})</a>',
                html,
                re.I | re.S,
            ):
                href = unescape(m.group(1))
                title = _strip_html(m.group(2))
                if not title or href.startswith("#") or "javascript:" in href:
                    continue
                if "preview-document" not in href:
                    continue
                url = self._abs_sede(href) if href.startswith("/") else href
                if url in seen:
                    continue
                blob = f"{title} {url}"
                if not RE_PROYECTO.search(blob):
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": url,
                        "blob": blob,
                        "origen": "transparencia",
                    }
                )
        return rows

    def _collect_pgom_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.pgom_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            href = self._abs_web(m.group(1))
            if href in seen:
                continue
            seen.add(href)
            name = unescape(urllib.parse.unquote(Path(href).name)).replace("_", " ").replace(".pdf", "")
            blob = f"PGOM {name} {href}"
            rows.append(
                {
                    "titulo": f"PGOM — {name}"[:500],
                    "fecha": _fecha_from_blob(blob),
                    "url": self.pgom_url,
                    "pdf_url": href,
                    "blob": blob,
                    "origen": "pgom",
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        endpoints: list[str] = [
            f"{self.web_base}/wp-json/wp/v2/posts?categories={self.wp_urbanismo_cat}&per_page=100&page={{page}}&_fields=id,date,link,title,content",
            f"{self.web_base}/wp-json/wp/v2/posts?search=expediente&per_page=100&page={{page}}&_fields=id,date,link,title,content",
            f"{self.web_base}/wp-json/wp/v2/posts?search=pgom&per_page=100&page={{page}}&_fields=id,date,link,title,content",
            f"{self.web_base}/wp-json/wp/v2/posts?search=planeamiento&per_page=100&page={{page}}&_fields=id,date,link,title,content",
        ]
        for template in endpoints:
            for page in range(1, 4):
                url = template.format(page=page)
                try:
                    data = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    continue
                if not isinstance(data, list) or not data:
                    break
                for post in data:
                    pid = int(post.get("id") or 0)
                    if pid in seen:
                        continue
                    title = _strip_html(post.get("title", {}).get("rendered", ""))
                    content = post.get("content", {}).get("rendered", "") or ""
                    blob = f"{title} {content}"
                    if RE_WP_SKIP.search(blob):
                        continue
                    if not RE_PROYECTO.search(blob) and not RE_EXPDTE.search(title):
                        continue
                    seen.add(pid)
                    expte_m = RE_EXPDTE.search(title)
                    rows.append(
                        {
                            "id": pid,
                            "titulo": title[:500],
                            "fecha": (post.get("date") or "")[:10] or None,
                            "url": post.get("link") or "",
                            "expte": expte_m.group(1) if expte_m else None,
                            "blob": blob,
                            "origen": "wp_posts",
                        }
                    )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
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
                "id": _stable_id("lic", self.pgom_url),
                "fecha_concesion": None,
                "tipo": "PGOM — trámites participación",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "PGOM — participación ciudadana y consulta pública",
                "url": self.pgom_url,
                "source": "ayuntamiento",
                "nota": "Documentación del Plan General de Ordenación Municipal en web municipal",
                "origen": "web_pgom",
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
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(
            k in proc
            for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "información pública", "actuaciones")
        ):
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
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("expte") or row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or row["titulo"]),
            "url": row.get("url") or "",
            "source": "ayuntamiento",
            "expte": row.get("expte"),
            "origen": row.get("origen"),
        }

    def _situa_metadata(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", self.situa_url),
            "municipio": MUNICIPIO,
            "titulo": "Planeamiento urbanístico — consulta SITUADIFUSION (Junta de Andalucía)",
            "fecha": None,
            "tipo": "planeamiento",
            "url": self.situa_url,
            "source": "ayuntamiento",
            "origen": "situa",
            "nota": "Visor regional de planeamiento digitalizado (INE 23061)",
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_pgom")),
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_transparency_docs():
            add(self._row_to_proyecto(item))
        for item in self._collect_pgom_pdfs():
            add(self._row_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._row_to_proyecto(item))
        add(self._situa_metadata())

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "pgom": sum(1 for r in rows if r.get("origen") == "pgom"),
            "wp_posts": sum(1 for r in rows if r.get("origen") == "wp_posts"),
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
