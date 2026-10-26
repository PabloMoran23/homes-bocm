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

WEB_BASE = "https://www.plasencia.es/web"
SEDE_BASE = "https://sede.plasencia.es"
MUNICIPIO = "Plasencia"
ID_PREFIX = "plasencia"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"

PGOU_URL = (
    f"{WEB_BASE}/portal-de-transparencia/materias-de-urbanismo-y-obras-publicas/"
    "plan-general-de-ordenacion-urbana"
)
NORMATIVA_URL = (
    f"{WEB_BASE}/portal-de-transparencia/materias-de-urbanismo-y-obras-publicas/"
    "normativa-urbanistica"
)
PLAN_MURALLA_URL = (
    f"{WEB_BASE}/portal-de-transparencia/materias-de-urbanismo-y-obras-publicas/"
    "plan-director-muralla-de-plasencia"
)
PLAN_INTRAMUROS_URL = (
    f"{WEB_BASE}/portal-de-transparencia/materias-de-urbanismo-y-obras-publicas/"
    "plan-especial-de-proteccion-del-recinto-intramuros"
)

DEFAULT_SEED_PAGES: list[str] = [
    PGOU_URL,
    NORMATIVA_URL,
    PLAN_MURALLA_URL,
    PLAN_INTRAMUROS_URL,
]

URBANISMO_REMITENTE = re.compile(r"(?i)urbanismo")
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"primera ocupaci[oó]n|proyecto de urbanizaci[oó]n|segregaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|director)|pgm|pgou|"
    r"informaci[oó]n p[uú]blica|expediente|modificaci[oó]n|reparcel|estudio de detalle|"
    r"aprobaci[oó]n|sector|infracci[oó]n urban|sancionador|ordenanza urban|"
    r"anuncio.*obra|ocupaci[oó]n terrenos)",
)
RE_NOISE = re.compile(
    r"(?i)(jurado|candidatos|canon|tarifa.*agua|bando desbroce|mercadillo|"
    r"ludoteca|empleo|personal eventual|subvenci[oó]n covid|fondos europeos)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_EXPEDIENTE_YEAR = re.compile(r"\b(\d{1,6})/(\d{4})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?plasencia\.es)?/web/images/documentos/doc-urbanismo[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_CATALOG_LIC = re.compile(
    r"(?i)(licencia|comunicaci[oó]n previa|primera ocupaci[oó]n|proyecto de urbanizaci[oó]n|"
    r"segregaci[oó]n|compatibilidad urban)",
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


def _fecha_from_expediente(text: str) -> str | None:
    m = RE_EXPEDIENTE_YEAR.search(text or "")
    if m:
        try:
            return datetime(int(m.group(2)), 1, 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(int(obj["year"]), int(obj["month"]), int(obj["day"])).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str) -> str:
    blob = title.lower()
    if "modificaci" in blob and ("pgm" in blob or "plan general" in blob):
        return "modificación PGM"
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "reparcel" in blob:
        return "reparcelación"
    if "informaci" in blob or "exposici" in blob:
        return "información pública"
    if "aprobaci" in blob:
        return "aprobación"
    if "infracci" in blob or "sancion" in blob:
        return "disciplina urbanística"
    if "plan director" in blob or "muralla" in blob:
        return "plan director"
    if "plan especial" in blob or "intramuros" in blob:
        return "plan especial"
    if "pgm" in blob or "pgou" in blob or "plan general" in blob:
        return "PGM"
    if "licencia" in blob:
        return "licencia urbanística"
    return "urbanismo"


class PlasenciaAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla (transparencia/PGM) + sede STA (tablón JSON + catálogo trámites)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or f"{WEB_BASE}/")
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-plasencia/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.plasencia.es" in url else None
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
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
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON"
        )

    def _tablon_row_to_record(self, row: dict[str, Any]) -> tuple[str, str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or rem.get("code") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        url = self._tablon_detail_url(dboid)
        return title, remitente, fecha, url, dboid

    def _collect_catalog_licencias(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = str(item.get("name") or "").strip()
            if not name or not RE_CATALOG_LIC.search(name):
                continue
            code = str(item.get("code") or item.get("dboid") or name)
            rows.append(
                {
                    "id": _stable_id("lic", code),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": name[:500],
                    "url": f"{CATALOGO_URL}#tramite={code}",
                    "source": "ayuntamiento",
                    "nota": "Trámite catálogo sede STA; no concesión publicada",
                }
            )
        return rows

    def _collect_tablon_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._collect_tablon():
            title, rem, fecha, url, _ = self._tablon_row_to_record(item)
            blob = f"{title} {rem}"
            if not RE_LICENCIA.search(blob):
                continue
            if RE_NOISE.search(blob):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": fecha or None,
                    "tipo": "licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                }
            )
        return rows

    def _collect_pgou_pdfs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                href = unescape(m.group(1).replace("&amp;", "&"))
                if href.startswith("/"):
                    pdf_url = urllib.parse.urljoin(f"{WEB_BASE}/", href)
                else:
                    pdf_url = href
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = unescape(urllib.parse.unquote(Path(pdf_url).name))[:200]
                titulo = f"Documentación PGM: {name}"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_expediente(name) or _parse_fecha_dmy(name),
                        "tipo": _proyecto_tipo(name),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": "transparencia_pgou",
                    }
                )
        return rows

    def _collect_tablon_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._collect_tablon():
            title, rem, fecha, url, dboid = self._tablon_row_to_record(item)
            blob = f"{title} {rem}"
            if RE_NOISE.search(blob):
                continue
            if not (URBANISMO_REMITENTE.search(rem) or RE_PROYECTO.search(blob)):
                continue
            if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha or _fecha_from_expediente(title) or _parse_fecha_dmy(title),
                    "tipo": _proyecto_tipo(title),
                    "url": url,
                    "origen": "sede_tablon",
                    "expediente": str(item.get("externString") or ""),
                    "dboid": dboid,
                }
            )
        return rows

    def _to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any]:
        key = rec.get("pdf_url") or rec.get("url") or rec.get("titulo", "")
        out: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": rec["titulo"],
            "fecha": rec.get("fecha") or None,
            "tipo": rec.get("tipo") or "urbanismo",
            "url": rec["url"],
            "source": "ayuntamiento",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        if rec.get("expediente"):
            out["expediente"] = rec["expediente"]
        return out

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        catalog = self._collect_catalog_licencias()
        tablon = self._collect_tablon_licencias()
        for rec in catalog + tablon:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "catalog_tramites": len(catalog),
            "tablon_licencias": len(tablon),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for raw in self._collect_tablon_proyectos():
            add(self._to_proyecto(raw))
        for raw in self._collect_pgou_pdfs():
            add(self._to_proyecto(raw))

        self._write_jsonl(out_jsonl, rows)
        tablon_n = len(self._collect_tablon_proyectos())
        pdf_n = len(self._collect_pgou_pdfs())
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_proyectos": tablon_n,
            "pgou_pdfs": pdf_n,
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
