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

WEB_BASE = "https://www.burjassot.org"
SEDE_BASE = "https://sede.burjassot.org"
TRANSP_BASE = "https://transparencia.burjassot.org"
MUNICIPIO = "Burjassot"
ID_PREFIX = "burjassot"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
URBANISMO_URL = f"{WEB_BASE}/urbanismo/"
TRAMITES_URBANISMO_URL = f"{WEB_BASE}/tramites/urbanisme/"
TRANSP_EXPEDIENTES_URL = (
    f"{TRANSP_BASE}/urbanismo-y-medioambiente/2-desarrollo-y-gestion-delplan/"
)
TRANSP_PGOU_URL = (
    f"{TRANSP_BASE}/urbanismo-y-medioambiente/plan-general-de-ordenacion-urbana/"
    "pgou-aprovat-definitivament/"
)

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    TRANSP_EXPEDIENTES_URL,
    TRANSP_PGOU_URL,
    f"{TRANSP_BASE}/urbanismo-y-medioambiente/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|inicio de obra|zanja|vado)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|modificaci[oó]n|"
    r"estudio de detalle|unidad de ejecuci|programa de actuaci|sector|reparcel|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|ordenanza urban|"
    r"integraci[oó]n paisaj|actuaci[oó]n integrada|precisi[oó]n geom[eé]trica)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|bolsa de empleo|subvenci[oó]n|convocatoria.*pleno|"
    r"junta de gobierno|baremaci[oó]n|oposici[oó]n|empleo temporal|bicicleta|"
    r"padr[oó]n fiscal|tasa de basura|mercado municipal|mercado extraordinario|"
    r"reglamento del consell|joventut|fiestas|impuesto|tribut|cobranza|"
    r"brigada de obras|brigada de obra)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_EXPEDIENTE = re.compile(
    r"(?i)expediente[-/](\d{4})[-/]([a-z0-9]+)",
)
RE_TRANSP_EXP = re.compile(
    r'href="((?:https://transparencia\.burjassot\.org)?/urbanismo-y-medioambiente/[^"]*(?:expediente|unidad-de-ejecucion)[^"]*)"',
    re.I,
)
RE_PDF = re.compile(r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"', re.I)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                pass
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(int(obj["year"]), int(obj["month"]), int(obj["day"])).strftime(
            "%Y-%m-%d"
        )
    except (KeyError, TypeError, ValueError):
        return None


def _proyecto_tipo(title: str) -> str:
    n = (title or "").lower()
    if "modificaci" in n and ("plan general" in n or "pgou" in n):
        return "modificación PGOU"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "programa de actuaci" in n or "actuaci" in n and "integrada" in n:
        return "programa de actuación integrada"
    if "unidad de ejecuci" in n:
        return "unidad de ejecución"
    if "plan general" in n or "pgou" in n:
        return "PGOU"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


class BurjassotAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress + sede STA (tablón JSON) + portal transparencia (expedientes PGOU)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transp_base") or TRANSP_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._tablon_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-burjassot/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.burjassot.org" in url else None
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or self.web_base, unescape(href))

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

    def _collect_tablon(self) -> list[dict[str, Any]]:
        if self._tablon_cache is not None:
            return self._tablon_cache
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except (urllib.error.URLError, OSError):
            return self._tablon_cache or []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            title = str(item.get("descriptionProc") or item.get("externString") or "").strip()
            rem = item.get("remitent") or {}
            remitente = str(rem.get("description") or rem.get("code") or "")
            fecha = _xml_date(item.get("pubDateIni")) or ""
            dboid = str(item.get("dboid") or title)
            url = f"{TABLON_URL}#dboid={dboid}"
            rows.append(
                {
                    "titulo": title[:500],
                    "remitente": remitente,
                    "fecha": fecha,
                    "url": url,
                    "origen": "sede_tablon",
                }
            )
        if rows:
            self._tablon_cache = rows
        return rows

    def _is_noise(self, blob: str) -> bool:
        if RE_NOISE.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return True
        return False

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", TABLON_URL),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios y edictos — sede electrónica",
                "url": TABLON_URL,
                "source": "ayuntamiento",
                "nota": "Dataset PTS2_TABLON embebido en sede STA",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", CATALOGO_URL),
                "fecha_concesion": None,
                "tipo": "catálogo trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — urbanismo y vivienda",
                "url": CATALOGO_URL,
                "source": "ayuntamiento",
                "nota": "Licencias de obra, ocupación vía pública, etc. (STA)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", URBANISMO_URL),
                "fecha_concesion": None,
                "tipo": "urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — web municipal",
                "url": URBANISMO_URL,
                "source": "ayuntamiento",
                "nota": "Documentación PGOU, encuestas paisaje, planos",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", TRAMITES_URBANISMO_URL),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de urbanismo — web municipal",
                "url": TRAMITES_URBANISMO_URL,
                "source": "ayuntamiento",
                "nota": "Información presencial/telemática licencias",
                "origen": "web_tramite",
            },
        ]

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo') or ''} {row.get('remitente') or ''}"
        if self._is_noise(blob) or not RE_LICENCIA.search(blob):
            return None
        key = row.get("url") or blob
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha") or None,
            "tipo": "licencia / edicto",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo') or ''} {row.get('remitente') or ''}"
        if self._is_noise(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or blob
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or None,
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _page_title(self, html: str, fallback: str = "") -> str:
        m = RE_H1.search(html)
        if m:
            t = unescape(m.group(1).strip())
            if t:
                return t[:500]
        return fallback[:500]

    def _collect_transparencia_expedientes(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in (TRANSP_EXPEDIENTES_URL, TRANSP_PGOU_URL):
            try:
                html = self._fetch(seed)
            except (urllib.error.URLError, OSError):
                continue
            for m in RE_TRANSP_EXP.finditer(html):
                href = self._abs_url(m.group(1), self.transp_base)
                if href in seen:
                    continue
                seen.add(href)
                try:
                    page_html = self._fetch(href)
                except (urllib.error.URLError, OSError):
                    continue
                slug = href.rstrip("/").split("/")[-1]
                exp_m = RE_EXPEDIENTE.search(slug)
                expte = f"{exp_m.group(1)}-{exp_m.group(2)}" if exp_m else None
                titulo = self._page_title(page_html, slug.replace("-", " "))
                fecha = _parse_fecha_dmy(page_html) or _parse_fecha_dmy(slug)
                pdf_url = None
                for pdf_m in RE_PDF.finditer(page_html):
                    pdf = self._abs_url(pdf_m.group(1), self.transp_base)
                    if "transparencia.burjassot.org" in pdf or "archivo.burjassot.org" in pdf:
                        pdf_url = pdf
                        break
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", href),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(titulo),
                    "url": href,
                    "source": "ayuntamiento",
                    "origen": "transparencia",
                }
                if expte:
                    rec["expte"] = expte
                if pdf_url:
                    rec["pdf_url"] = pdf_url
                rows.append(rec)
        return rows

    def _collect_wordpress_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            if not page_url.startswith(self.web_base) and not page_url.startswith(self.transp_base):
                continue
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, OSError):
                continue
            page_title = self._page_title(html, page_url)
            for pdf_m in RE_PDF.finditer(html):
                pdf = self._abs_url(pdf_m.group(1), page_url)
                if pdf in seen:
                    continue
                if "administracionelectronica.gob.es" in pdf:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))[:200]
                ctx_start = max(0, pdf_m.start() - 800)
                ctx = unescape(re.sub(r"<[^>]+>", " ", html[ctx_start : pdf_m.start()]))
                ctx = re.sub(r"\s+", " ", ctx).strip()
                titulo = name
                for heading in re.finditer(r"(?:Plan General|Modificaci[oó]n|Encuesta|Plano|Urbanizaci[oó]n)[^.]{5,120}", ctx, re.I):
                    titulo = heading.group(0).strip()[:500]
                    break
                if not RE_PROYECTO.search(titulo) and not RE_PROYECTO.search(name):
                    if "urban" not in page_url.lower() and "pgou" not in name.lower():
                        continue
                rows.append(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": MUNICIPIO,
                        "titulo": titulo,
                        "fecha": _parse_fecha_dmy(name) or _parse_fecha_dmy(ctx),
                        "tipo": _proyecto_tipo(titulo),
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": "web_pdf",
                        "contexto": page_title,
                    }
                )
        return rows

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
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
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
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
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

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for rec in self._collect_transparencia_expedientes():
            add(rec)
        for rec in self._collect_wordpress_seeds():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "web_pdf": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "with_geometry": 0,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        stats = self.backfill_proyectos(out_jsonl)
        merged = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        for rid, rec in existing.items():
            merged.setdefault(rid, rec)
        rows = list(merged.values())
        self._write_jsonl(out_jsonl, rows)
        after = len(rows)
        stats = {**stats, "rows": after}
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": stats.get("with_geometry", 0),
        }
