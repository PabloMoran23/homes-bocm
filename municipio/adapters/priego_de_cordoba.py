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

WP_BASE = "https://priegodecordoba.es"
SEDE_BASE = "https://sede.eprinsa.es/priego"
MUNICIPIO = "Priego de Córdoba"
ID_PREFIX = "priego-de-cordoba"

URBANISMO_CATEGORY_ID = 71
DEFAULT_SEED_PAGES = [
    f"{WP_BASE}/temas/urbanismo-suelo-y-vivienda/normativa-municipal-de-urbanismo/",
    f"{WP_BASE}/temas/urbanismo-suelo-y-vivienda/documentacion-y-modelos-de-solicitud-del-area-de-urbanismo/",
    f"{SEDE_BASE}/tramites/procedimiento/12652/certificado-de-empadronamiento-automatizado",
]
DEFAULT_LICENCIA_PAGES = [
    f"{WP_BASE}/temas/urbanismo-suelo-y-vivienda/documentacion-y-modelos-de-solicitud-del-area-de-urbanismo/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|cambio de uso|concesi[oó]n de licencia|licencia de urbanizaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|innovaci[oó]n|avance|expropiaci[oó]n|bando|"
    r"reforma interior|ari-|aa-|pepricch|calificaci[oó]n|actuaci[oó]n)",
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://priegodecordoba\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_WP_PDF_LINK = re.compile(
    r'href="(https://priegodecordoba\.es/wp-content/uploads/[^"]+\.pdf)"',
    re.I,
)
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
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
    m = RE_FECHA_ISO.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"/(\d{4})/(\d{2})/", text or "")
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
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "pepricch" in b or "plan especial" in b:
        return "plan especial"
    if "reforma interior" in b or re.search(r"\bari-\d+", b):
        return "reforma interior"
    if "expropiaci" in b:
        return "expropiación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "avance" in b:
        return "avance de planeamiento"
    if "innovaci" in b:
        return "innovación normativa"
    if "calificaci" in b and "ambiental" in b:
        return "calificación ambiental"
    if "cambio de uso" in b:
        return "cambio de uso"
    if "licencia" in b:
        return "licencia publicada"
    if "bando" in b:
        return "bando urbanístico"
    if "actuaci" in b or "proyecto de actuaci" in b:
        return "actuación urbanística"
    return "urbanismo"


class PriegoDeCordobaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (categoría urbanismo) + normativa PDFs + sede eprinsa (trámites informativos)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.wp_categories = [int(x) for x in (self.config.get("wp_categories") or [URBANISMO_CATEGORY_ID])]
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.wp_max_pages = int(self.config.get("wp_max_pages", 5))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-priego-de-cordoba/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60, context=self._ssl_ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        text = self._fetch(url)
        return json.loads(text)

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for cat in self.wp_categories:
            for page in range(1, self.wp_max_pages + 1):
                url = (
                    f"{self.wp_base}/wp-json/wp/v2/posts"
                    f"?categories={cat}&per_page=100&page={page}&_fields=id,date,link,title,content"
                )
                try:
                    data = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(data, list) or not data:
                    break
                for post in data:
                    pid = int(post.get("id") or 0)
                    if pid in seen:
                        continue
                    seen.add(pid)
                    title = _strip_html(post.get("title", {}).get("rendered", ""))
                    content = post.get("content", {}).get("rendered", "") or ""
                    pdf_m = RE_WP_PDF_LINK.search(content)
                    pdf_url = pdf_m.group(1) if pdf_m else None
                    rows.append(
                        {
                            "id": pid,
                            "titulo": title[:500],
                            "fecha": (post.get("date") or "")[:10] or None,
                            "url": post.get("link") or "",
                            "pdf_url": pdf_url,
                            "content": content,
                            "origen": f"wp_category_{cat}",
                        }
                    )
                if len(data) < 100:
                    break
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                ctx_start = max(0, m.start() - 600)
                ctx = _strip_html(html[ctx_start : m.start() + 200])
                titulo = name[:500]
                link_m = re.search(
                    r"((?:Plan|Aprobaci[oó]n|Modificaci[oó]n|modelo|solicitud|declaraci[oó]n)[^.]{8,180})",
                    ctx,
                    re.I,
                )
                if link_m:
                    titulo = link_m.group(1).strip()[:500]
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(pdf + " " + ctx),
                        "url": page_url,
                        "pdf_url": pdf,
                        "origen": page_url,
                    }
                )
        return rows

    def _collect_licencia_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self.licencia_pages:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            pdfs = [self._abs_url(m.group(1)) for m in RE_PDF_HREF.finditer(html)]
            lic_pdfs = [
                p
                for p in pdfs
                if re.search(r"(?i)licencia|obra|declaracion|solicitud|espectaculo|ocupacion", p)
            ]
            if not lic_pdfs:
                lic_pdfs = pdfs[:3]
            for pdf in lic_pdfs:
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                rows.append(
                    {
                        "id": _stable_id("lic", pdf),
                        "fecha_concesion": _fecha_from_blob(pdf),
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": name[:500],
                        "url": url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "nota": "Modelo/solicitud informativa; no concesión publicada en tablón",
                    }
                )
        return rows

    def _post_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        if not RE_LICENCIA.search(titulo):
            return None
        key = item.get("pdf_url") or item.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": item.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": item.get("url", ""),
            "source": "ayuntamiento",
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        return rec

    def _post_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        blob = f"{titulo} {item.get('content', '')}"
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = item.get("pdf_url") or item.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        return rec

    def _pdf_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        pdf = item.get("pdf_url") or item["url"]
        blob = f"{item.get('titulo', '')} {pdf}"
        return {
            "id": _stable_id("proy", pdf),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "pdf_url": item.get("pdf_url"),
            "origen": item.get("origen"),
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
        for rec in self._collect_licencia_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_wp_posts():
            rec = self._post_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_pages():
            existing[rec["id"]] = rec
        for item in self._collect_wp_posts():
            rec = self._post_to_licencia(item)
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

        for item in self._collect_wp_posts():
            add(self._post_to_proyecto(item))
        for item in self._collect_seed_pdfs():
            add(self._pdf_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_categories": self.wp_categories,
            "seed_pages": len(self.seed_pages),
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
