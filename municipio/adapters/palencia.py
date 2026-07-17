from __future__ import annotations

import hashlib
import html as htmlmod
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, unquote

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.aytopalencia.es"
SEDE_BASE = "https://sede.aytopalencia.es"
MUNICIPIO = "Palencia"
ID_PREFIX = "palencia"

TABLON_URL = (
    f"{SEDE_BASE}/castellano/Externos/ASP/enlacesPortada/"
    "EnlacesPortadaSede.asp?enlacePortada=tablon"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/area/urbanismo-e-infraestructura/documentos-en-tramite",
    f"{WEB_BASE}/area/urbanismo-e-infraestructura/pgou-y-modificaciones",
    f"{WEB_BASE}/area/urbanismo-e-infraestructura/archivo-urbanistico",
    f"{WEB_BASE}/area/urbanismo-e-infraestructura/convenios-urbanisticos",
    f"{WEB_BASE}/area/urbanismo-e-infraestructura/planeamiento-y-gestion-urbanistica",
    "https://pgou.aytopalencia.es/",
    f"{WEB_BASE}/tramite/tramites-de-informacion-publica",
]

DEFAULT_TRAMITE_SLUGS: tuple[str, ...] = (
    "acceso-garajes-en-zona-peatonal",
    "andamios",
    "autorizacion-de-comienzo-de-obra",
    "autorizacion-de-modificacion-del-regimen-juridico-de-division-horizontal-division",
    "tramites-de-informacion-publica",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|de comienzo)|"
    r"obra mayor|andamio|garaje|vado|demolici[oó]n|instalaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|"
    r"reparcel|estudio de detalle|sector|urpi|uzpi|sunc-|suelo urban|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|avance de la revisi[oó]n|"
    r"documento inicial estrat[eé]gico|archivo urban)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|plaza de|empleo p[uú]blico|"
    r"presupuest|subvenci[oó]n deportiv|empadron|tribut|matrimonio civil|"
    r"impuesto sobre actividades econ[oó]micas|cobranza relativo|censo electoral|"
    r"concurso de fotograf|padrones listas)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_TIME = re.compile(r"(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}:\d{2})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,4}/\d{4}[^/\s]*)")
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)
RE_TABLON_NUMUINT = re.compile(
    r"numuint=([A-F0-9]+)'",
    re.I,
)


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


def _fecha_from_text(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_iso(text)


def _clean_title(text: str) -> str:
    t = unescape(htmlmod.unescape(text or ""))
    return re.sub(r"\s+", " ", t).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "convenio urban" in n:
        return "convenio urbanístico"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "avance" in n and "pgou" in n:
        return "avance PGOU"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "plan parcial" in n or "urpi" in n or "uzpi" in n:
        return "plan parcial"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "archivo urban" in n:
        return "archivo urbanístico"
    if "pgou" in n or "planeam" in n:
        return "planeamiento"
    return "urbanismo"


class PalenciaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 9 (urbanismo) + sede Absis (tablón) + trámites informativos."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.tramite_slugs = tuple(self.config.get("tramite_slugs") or DEFAULT_TRAMITE_SLUGS)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-palencia/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str, base: str | None = None) -> str:
        return unescape(urljoin(base or f"{self.web_base}/", href))

    def _tablon_detail_url(self, numuint: str) -> str:
        return (
            f"{self.sede_base}/castellano/Externos/ASP/dlg/TablonAnuncios/"
            f"dlgVerDetalleAnuncio.aspx?numuint={numuint}"
        )

    def _parse_tablon_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.config.get("tablon_url") or TABLON_URL)
        except urllib.error.URLError:
            return []

        html = htmlmod.unescape(html)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_FECHA_DMY_TIME.finditer(html):
            chunk = html[m.start() : m.start() + 2500]
            texts = [
                t.strip()
                for t in re.findall(r">([^<]{3,400})<", chunk)
                if t.strip() and not t.startswith("&")
            ]
            if len(texts) < 2:
                continue
            titulo = texts[0]
            unidad = texts[1] if len(texts) > 1 else ""
            tipo_doc = texts[2] if len(texts) > 2 else ""
            numuint_m = RE_TABLON_NUMUINT.search(chunk)
            numuint = numuint_m.group(1) if numuint_m else _stable_id("tab", titulo + m.group(1))
            if numuint in seen:
                continue
            seen.add(numuint)
            rows.append(
                {
                    "titulo": _clean_title(titulo),
                    "fecha": _parse_fecha_dmy(m.group(1)),
                    "unidad": _clean_title(unidad),
                    "tipo_doc": _clean_title(tipo_doc),
                    "url": self._tablon_detail_url(numuint) if numuint_m else TABLON_URL,
                    "numuint": numuint,
                    "origen": "tablon_absis",
                }
            )
        return rows

    def _parse_html_tables(self, html: str, page_url: str, default_tipo: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            cells = [
                _clean_title(re.sub(r"<[^>]+>", " ", c))
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            ]
            cells = [c for c in cells if c]
            if len(cells) < 2:
                continue
            titulo = cells[0]
            blob = " ".join(cells)
            if not RE_PROYECTO.search(blob) and default_tipo != "convenio urbanístico":
                if "convenio" not in blob.lower():
                    continue
            fecha = None
            for cell in cells[1:5]:
                fecha = fecha or _fecha_from_text(cell)
            pdf_url = None
            pdf_m = RE_PDF.search(tr)
            if pdf_m:
                pdf_url = self._abs_web(pdf_m.group(1), page_url)
            key = titulo + (pdf_url or "")
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": fecha,
                    "tipo": default_tipo,
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "origen": "drupal_tabla",
                    "key": key,
                }
            )
        return rows

    def _collect_drupal_proyectos(self) -> list[dict[str, Any]]:
        page_specs = (
            (f"{self.web_base}/area/urbanismo-e-infraestructura/documentos-en-tramite", "información pública"),
            (f"{self.web_base}/area/urbanismo-e-infraestructura/pgou-y-modificaciones", "planeamiento"),
            (f"{self.web_base}/area/urbanismo-e-infraestructura/archivo-urbanistico", "archivo urbanístico"),
            (f"{self.web_base}/area/urbanismo-e-infraestructura/convenios-urbanisticos", "convenio urbanístico"),
        )
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url, default_tipo in page_specs:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for item in self._parse_html_tables(html, page_url, default_tipo):
                if item["key"] in seen:
                    continue
                seen.add(item["key"])
                rows.append(item)

            for href in RE_PDF.findall(html):
                pdf = self._abs_web(href, page_url)
                blob = f"{pdf} {page_url}"
                if not RE_PROYECTO.search(blob) and "Urbanismo" not in pdf:
                    continue
                name = _clean_title(unquote(Path(pdf).name))
                key = pdf
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": name,
                        "fecha": _fecha_from_text(name) or _fecha_from_text(pdf),
                        "tipo": default_tipo,
                        "url": page_url,
                        "pdf_url": pdf,
                        "origen": "drupal_pdf",
                        "key": key,
                    }
                )

        for page_url in self.seed_pages:
            if page_url in {s[0] for s in page_specs}:
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            h1 = RE_H1.search(html)
            titulo = _clean_title(h1.group(1)) if h1 else page_url
            if RE_PROYECTO.search(titulo) or RE_PROYECTO.search(page_url):
                key = page_url
                if key not in seen:
                    seen.add(key)
                    rows.append(
                        {
                            "titulo": titulo,
                            "fecha": _fecha_from_text(html[:6000]),
                            "tipo": _proyecto_tipo(titulo),
                            "url": page_url,
                            "origen": "drupal_pagina",
                            "key": key,
                        }
                    )
        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for slug in self.tramite_slugs:
            url = f"{self.web_base}/tramite/{slug}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            h1 = RE_H1.search(html)
            titulo = _clean_title(h1.group(1)) if h1 else slug.replace("-", " ").title()
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "origen": "tramite_informativo",
                }
            )
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('unidad', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        if RE_NOISE.search(blob) and not RE_LICENCIA.search(blob):
            return None
        key = row.get("numuint") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"expte": m.group(1)} if (m := RE_EXPTE.search(row["titulo"])) else {}),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('unidad', '')} {row.get('tipo', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "tablon_absis":
            if not RE_PROYECTO.search(blob):
                return None
            if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
                return None
            if "gesti" in row.get("unidad", "").lower() and "urban" in row.get("unidad", "").lower():
                pass
            elif not RE_PROYECTO.search(blob):
                return None
        elif not RE_PROYECTO.search(blob):
            return None
        key = row.get("numuint") or row.get("pdf_url") or row.get("key") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if m := RE_EXPTE.search(titulo):
            rec["expte"] = m.group(1)
        return rec

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
        for item in self._parse_tablon_rows():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_absis"),
            "tramites": sum(1 for r in rows if r.get("origen") == "tramite_informativo"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats["rows"]
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._parse_tablon_rows():
            add(self._row_to_proyecto(item))
        for item in self._collect_drupal_proyectos():
            add(self._row_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_absis"),
            "drupal": sum(1 for r in rows if str(r.get("origen", "")).startswith("drupal")),
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
