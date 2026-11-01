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
from urllib.parse import unquote, urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.onboarding_snapshot import reviewed_records

WEB_BASE = "https://www.villajoyosa.com"
SEDE_BASE = "https://sede.villajoyosa.com"
MUNICIPIO = "la Vila Joiosa / Villajoyosa"
ID_PREFIX = "la-vila-joiosa"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
GVA_PG_ROOT = (
    "https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/"
    "2%20ALICANTE/03139%20LA%20VILA%20JOIOSA/"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/departamento/urbanismo/",
    f"{WEB_BASE}/tablon-de-anuncios/",
    f"{WEB_BASE}/guia-urbana/",
    f"{WEB_BASE}/buscador-de-tramites/",
    GVA_PG_ROOT,
]

WP_CATEGORY_PAGES: list[str] = [
    f"{WEB_BASE}/category/urbanismo-e-infraestructuras/",
] + [
    f"{WEB_BASE}/category/urbanismo-e-infraestructuras/page/{n}/"
    for n in range(2, 6)
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|tasa.*urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|proyecto|"
    r"modificaci[oó]n|reparcel|estudio de detalle|sector|unidad de ejecuci|"
    r"audiencia|ordenanza.*urban|catalogo|compatibilidad urban|canon de urba|"
    r"ue[\s-]?\d|pp[\s-]?\d|montiboli|montesol)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|subvenci[oó]n.*empleo|asfaltado de calles|"
    r"puente sobre|rotonda|ascensor|puesta en marcha|primera piedra|"
    r"plan estrat[eé]gico de turismo|plan estrat[eé]gico de ciudad)",
)
RE_WP_POST_PATH = re.compile(
    r"/(?:anuncio|informacion-publica|licencia|reparcel|audiencia|tramite|"
    r"expediente|sector|pgou|ordenanza|planeam|urbaniz|compatibilidad|"
    r"suspension-cautelar)[^/]*/$",
    re.I,
)
RE_HREF = re.compile(r'href="(https://www\.villajoyosa\.com/[^"#?]+/?)"', re.I)
RE_INDEX_HREF = re.compile(r'href="([^"?#]+\/?)"', re.I)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_META_DATE = re.compile(
    r'property="article:published_time"\s+content="([^"]+)"', re.I
)
RE_OG_TITLE = re.compile(r'property="og:title"\s+content="([^"]+)"', re.I)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_pub_date(pub: Any) -> str | None:
    if not isinstance(pub, dict):
        return None
    try:
        return datetime(
            int(pub["year"]),
            int(pub["month"]),
            int(pub["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _clean_title(text: str) -> str:
    t = unescape(text or "")
    return re.sub(r"\s+", " ", t).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "reparcel" in n or "audiencia" in n:
        return "reparcelación / audiencia"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "plan parcial" in n or "sector" in n or "urbaniz" in n:
        return "actuación urbanística"
    if "pgou" in n or "catalogo" in n:
        return "planeamiento"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


class LaVilaJoiosaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress villajoyosa.com + sede STA (T-Systems tablón); registro planeamiento GVA."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wp_category_pages = list(self.config.get("wp_category_pages") or WP_CATEGORY_PAGES)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-la-vila-joiosa/1.0"),
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        ctx = self._ssl_ctx if (use_sede_ssl or "sede.villajoyosa.com" in url) else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON&lang=ES"
        )

    def _tablon_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_title(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rem = item.get("remitent") or {}
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_pub_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "extern": str(item.get("externString") or ""),
                    "remitente": str(rem.get("description") or ""),
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _discover_wp_post_urls(self) -> list[str]:
        seen: set[str] = set()
        urls: list[str] = []
        for page_url in self.wp_category_pages + self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for href in RE_HREF.findall(html):
                if not RE_WP_POST_PATH.search(href):
                    continue
                if href in seen:
                    continue
                seen.add(href)
                urls.append(href)
        return urls

    def _parse_wp_post(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None
        title_m = RE_OG_TITLE.search(html) or RE_H1.search(html)
        titulo = _clean_title(title_m.group(1) if title_m else "")
        if not titulo:
            slug = url.rstrip("/").rsplit("/", 1)[-1]
            titulo = _clean_title(slug.replace("-", " "))
        fecha = None
        meta_m = RE_META_DATE.search(html)
        if meta_m:
            fecha = _parse_fecha_iso(meta_m.group(1)[:10])
        if not fecha:
            fecha = _parse_fecha_dmy(titulo) or _parse_fecha_dmy(html[:4000])
        pdf_url = None
        for m in RE_PDF.finditer(html):
            pdf = urljoin(url, m.group(1))
            if "wp-content/uploads" in pdf:
                pdf_url = pdf
                break
        return {
            "titulo": titulo,
            "fecha": fecha,
            "url": url,
            "pdf_url": pdf_url,
            "origen": "wordpress_noticia",
        }

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self._discover_wp_post_urls():
            row = self._parse_wp_post(url)
            if row:
                rows.append(row)
        return rows

    def _collect_gva_planeamiento_docs(self) -> list[dict[str, Any]]:
        seen_dirs: set[str] = set()
        seen_pdfs: set[str] = set()
        rows: list[dict[str, Any]] = []

        def walk(url: str, depth: int) -> None:
            if depth <= 0 or url in seen_dirs:
                return
            seen_dirs.add(url)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                return
            for href in RE_INDEX_HREF.findall(html):
                if href.startswith("?"):
                    continue
                target = urljoin(url, unescape(href))
                if not target.startswith("https://mediambient.gva.es/"):
                    continue
                low = target.lower()
                if low.endswith(".pdf"):
                    if target in seen_pdfs:
                        continue
                    seen_pdfs.add(target)
                    name = _clean_title(unquote(Path(target).name))
                    rows.append(
                        {
                            "titulo": name or "Documento planeamiento GVA",
                            "fecha": _parse_fecha_dmy(name),
                            "url": url,
                            "pdf_url": target,
                            "origen": "gva_registro",
                        }
                    )
                elif low.endswith("/") and "03139" in target.upper():
                    walk(target, depth - 1)

        walk(GVA_PG_ROOT, 4)
        return rows

    def _collect_web_pdfs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            if page_url.startswith("https://mediambient.gva.es"):
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF.finditer(html):
                pdf = urljoin(page_url, m.group(1))
                if pdf in seen or "wp-content/uploads" not in pdf:
                    continue
                low = pdf.lower()
                if not any(
                    k in low
                    for k in (
                        "urban",
                        "urb_",
                        "licen",
                        "llicen",
                        "obra",
                        "declaracion",
                        "solicitud",
                        "pgou",
                        "planeam",
                    )
                ):
                    continue
                seen.add(pdf)
                name = _clean_title(unquote(Path(pdf).name))
                rows.append(
                    {
                        "titulo": name,
                        "fecha": _parse_fecha_dmy(name),
                        "url": page_url,
                        "pdf_url": pdf,
                        "origen": "web_pdf",
                    }
                )
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('remitente', '')} {row.get('extern', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("dboid") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("extern"):
            rec["expte"] = row["extern"]
        return rec

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('extern', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("pdf_url") or row.get("dboid") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / trámite obra",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._tablon_rows():
            add(self._row_to_licencia(row))
        for row in self._collect_web_pdfs():
            add(self._row_to_licencia(row))
        for row in self._collect_wp_posts():
            if RE_LICENCIA.search(row["titulo"]):
                add(self._row_to_licencia(row))

        info_pages = [
            {
                "id": _stable_id("lic", TABLON_URL),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios y edictos — sede electrónica (STA)",
                "url": TABLON_URL,
                "source": "ayuntamiento",
                "nota": "Dataset PTS2_TABLON; sin listado de concesiones de obra",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/buscador-de-tramites/"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Buscador de trámites — licencias y autorizaciones",
                "url": f"{self.web_base}/buscador-de-tramites/",
                "source": "ayuntamiento",
                "nota": "Catálogo STA (CATSERV) vacío en sede; trámites vía web",
                "origen": "web_tramites",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/departamento/urbanismo/"),
                "fecha_concesion": None,
                "tipo": "formularios licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo y Vivienda — solicitudes y tasas",
                "url": f"{self.web_base}/departamento/urbanismo/",
                "source": "ayuntamiento",
                "nota": "PDFs de solicitud/declaración responsable; no registro de concesiones",
                "origen": "web_urbanismo",
            },
        ]
        for rec in info_pages:
            add(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._tablon_rows():
            add(self._row_to_proyecto(row))
        for row in self._collect_wp_posts():
            add(self._row_to_proyecto(row))
        for row in self._collect_gva_planeamiento_docs():
            add(self._row_to_proyecto(row))
        for row in self._collect_web_pdfs():
            add(self._row_to_proyecto(row))

        add(
            {
                "id": _stable_id("proy", "gva-pg-root"),
                "municipio": MUNICIPIO,
                "titulo": "Registro de planeamiento aprobado — Generalitat Valenciana (03139)",
                "fecha": None,
                "tipo": "planeamiento",
                "url": GVA_PG_ROOT,
                "source": "ayuntamiento",
                "origen": "gva_registro",
            }
        )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_web"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon_wp_gva"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
