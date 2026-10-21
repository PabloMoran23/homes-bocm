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

WEB_BASE = "https://www.doshermanas.es"
SEDE_BASE = "https://sede.doshermanas.es"
MUNICIPIO = "Dos Hermanas"
ID_PREFIX = "dos-hermanas"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
)
SITUA_SEARCH_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41038"

DEFAULT_URBANISMO_PAGES: list[tuple[str, str]] = [
    (f"{WEB_BASE}/concejalias/urbanismo/", "urbanismo"),
    (
        f"{WEB_BASE}/concejalias/urbanismo/Instrumentos-Ordenacion-Urbanistica/",
        "instrumentos ordenación",
    ),
    (
        f"{WEB_BASE}/concejalias/urbanismo/Instrumentos-Ordenacion-Urbanistica/pgou/",
        "PGOU",
    ),
    (
        f"{WEB_BASE}/concejalias/urbanismo/Instrumentos-Ordenacion-Urbanistica/"
        "Planes-Parciales-Ordenacion/",
        "plan parcial",
    ),
    (
        f"{WEB_BASE}/concejalias/urbanismo/Instrumentos-Ordenacion-Urbanistica/"
        "Planes-Reforma-Interior/",
        "reforma interior",
    ),
    (
        f"{WEB_BASE}/concejalias/urbanismo/Instrumentos-Ordenacion-Urbanistica/"
        "Estudios-Detalle/",
        "estudio de detalle",
    ),
    (f"{WEB_BASE}/concejalias/urbanismo/convenios-urbanisticos/", "convenio urbanístico"),
    (
        f"{WEB_BASE}/transparencia/transparencia-en-materias-de-urbanismo-obras-publicas-y-medioambiente/",
        "transparencia urbanismo",
    ),
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{WEB_BASE}/concejalias/urbanismo/licencias-urbanisticas/",
    f"{WEB_BASE}/concejalias/urbanismo/Comunicaciones-previas/",
    f"{WEB_BASE}/concejalias/urbanismo/Declaraciones-Responsables/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|edicto.*licencia|"
    r"inicio de obra|primera ocupaci[oó]n|parcelaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|innovaci[oó]n|"
    r"modificaci[oó]n|estudio de detalle|reforma interior|aprobaci[oó]n|"
    r"memoria|planos|sector|suelo|ordenanza|bop|boja|edicto|actuaci[oó]n)",
)
RE_EXCLUDE_TABLON = re.compile(
    r"(?i)(subvenci[oó]n|selecci[oó]n de personal|proceso selectivo|"
    r"modificaci[oó]n presupuestaria|padr[oó]n|convocatoria de pleno|"
    r"impuesto|tributo|cobranza|empleo p[uú]blico)",
)
RE_SAGA_PDF = re.compile(
    r'href="((?:https?://(?:www\.)?doshermanas\.es)?/export/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_SAGA_LINK = re.compile(
    r'href="((?:https?://(?:www\.)?doshermanas\.es)?/concejalias/urbanismo[^"#?]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOP_BOJA = re.compile(r"(?i)BOP\s+N[ÚU]M\.?\s*\d+\s+DE\s+\d{1,2}/\d{1,2}/(\d{4})")


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
    m = RE_BOP_BOJA.search(text or "")
    if m:
        return f"{m.group(1)}-01-01"
    ym = re.search(r"/(\d{4})[-_/](\d{2})/", url or "")
    if ym:
        try:
            return datetime(int(ym.group(1)), int(ym.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        y, mo, d = int(obj["year"]), int(obj["month"]), int(obj["day"])
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _title_from_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).name
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    name = name.replace("_", " ").replace("-", " ")
    return name[:500] if name else url


def _proyecto_tipo(blob: str, default: str = "urbanismo") -> str:
    b = blob.lower()
    if "convenio" in b:
        return "convenio urbanístico"
    if "plan parcial" in b or " sen-" in b or " snp-" in b:
        return "plan parcial"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "reforma interior" in b:
        return "reforma interior"
    if "innovaci" in b and "pgou" in b:
        return "innovación PGOU"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "informaci" in b or "exposici" in b:
        return "información pública"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    return default


class DosHermanasAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal SagaSuite (urbanismo/PGOU) + sede STA tablón PTS2_TABLON."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.fetch_timeout_s = float(self.config.get("fetch_timeout_s", 180))
        raw_pages = self.config.get("urbanismo_pages")
        if raw_pages:
            self.urbanismo_pages = [(p["url"], p.get("tipo", "documento")) for p in raw_pages]
        else:
            self.urbanismo_pages = list(DEFAULT_URBANISMO_PAGES)
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-dos-hermanas/1.0")},
        )
        timeout = self.fetch_timeout_s if "PTS2_TABLON" in url else min(self.fetch_timeout_s, 90)
        ctx = self._ssl_ctx if use_sede_ssl or "sede.doshermanas.es" in url else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

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
        try:
            html = self._fetch(self.tablon_url, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _tablon_row(self, row: dict[str, Any]) -> tuple[str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or rem.get("code") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        expte = str(row.get("externString") or "")
        dboid = str(row.get("dboid") or title)
        url = f"{self.tablon_url}#dboid={dboid}"
        return title, remitente, fecha, expte, url

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or self.web_base, unescape(href))

    def _extract_page_documents(self, page_url: str, default_tipo: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        records: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_SAGA_PDF.finditer(html):
            doc_href = m.group(1)
            doc_url = self._abs_url(doc_href)
            if doc_url in seen:
                continue
            seen.add(doc_url)
            idx = m.start()
            ctx = html[max(0, idx - 600) : idx + 120]
            anchor_m = re.search(
                r'<a[^>]+href="[^"]+\.pdf[^"]*"[^>]*>([^<]{4,300})</a>',
                ctx,
                re.I | re.S,
            )
            titulo = unescape(anchor_m.group(1).strip()) if anchor_m else _title_from_url(doc_url)
            titulo = re.sub(r"\s+", " ", titulo).strip()[:500]
            ctx_plain = unescape(re.sub(r"<[^>]+>", " ", ctx))
            fecha = _fecha_from_blob(ctx_plain, doc_url) or ""
            records.append(
                {
                    "titulo": titulo,
                    "fecha": fecha,
                    "url": page_url,
                    "pdf_url": doc_url,
                    "tipo": _proyecto_tipo(f"{titulo} {default_tipo}", default_tipo),
                }
            )

        for m in re.finditer(
            r'<a[^>]+href="([^"]+)"[^>]*>([^<]{8,250})</a>',
            html,
            re.I | re.S,
        ):
            href, label = m.group(1), unescape(m.group(2).strip())
            label = re.sub(r"\s+", " ", label).strip()
            if not RE_PROYECTO.search(label):
                continue
            if "javascript:" in href.lower():
                continue
            link = self._abs_url(href, page_url)
            if link in seen or ".pdf" in link.lower():
                continue
            seen.add(link)
            records.append(
                {
                    "titulo": label[:500],
                    "fecha": _fecha_from_blob(label, link) or "",
                    "url": link,
                    "pdf_url": None,
                    "tipo": _proyecto_tipo(label, default_tipo),
                }
            )
        return records

    def _collect_web_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url, section_tipo in self.urbanismo_pages:
            for doc in self._extract_page_documents(page_url, section_tipo):
                key = doc.get("pdf_url") or doc["url"]
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": doc["titulo"],
                    "fecha": doc["fecha"] or None,
                    "tipo": doc["tipo"],
                    "url": doc["url"],
                    "source": "ayuntamiento",
                    "origen": "portal_web",
                }
                if doc.get("pdf_url"):
                    rec["pdf_url"] = doc["pdf_url"]
                rows.append(rec)
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        visited: set[str] = set(self.licencia_pages)

        for url in list(visited):
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue

            title_m = re.search(r"<h1[^>]*>\s*([^<]+)", html, re.I)
            if not title_m:
                title_m = re.search(r"<title>([^<]+)", html, re.I)
            title = unescape(title_m.group(1).strip()) if title_m else _title_from_url(url)
            title = re.sub(r"\s*[-|].*Dos Hermanas.*$", "", title, flags=re.I).strip()

            if RE_LICENCIA.search(title) or "licencia" in url.lower() or "comunicacion" in url.lower():
                rows.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "nota": "Página informativa de trámite; no concesión publicada en listado",
                        "origen": "portal_web",
                    }
                )

            for m in RE_SAGA_LINK.finditer(html):
                link = self._abs_url(m.group(1))
                if link not in visited and (
                    "licencia" in link.lower()
                    or "comunicacion" in link.lower()
                    or "declaracion" in link.lower()
                ):
                    visited.add(link)

        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
        if RE_EXCLUDE_TABLON.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = expte or url
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": fecha or None,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "expte": expte or None,
            "url": url,
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
        if RE_EXCLUDE_TABLON.search(blob):
            return None
        is_urbanismo = "URBANISMO" in remitente.upper()
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and not is_urbanismo:
            return None
        if not is_urbanismo and not RE_PROYECTO.search(blob):
            return None
        key = expte or url
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha or None,
            "tipo": _proyecto_tipo(blob, "información pública" if is_urbanismo else "urbanismo"),
            "url": url,
            "expte": expte or None,
            "source": "ayuntamiento",
            "origen": "tablon",
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

        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_licencia_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon_y_tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for rec in self._collect_licencia_tramites():
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
        for rec in self._collect_web_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        for item in self._collect_tablon():
            rec = self._tablon_to_proyecto(item)
            if rec:
                existing[rec["id"]] = rec
        for rec in self._collect_web_proyectos():
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
