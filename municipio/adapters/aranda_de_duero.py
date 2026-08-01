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

WP_BASE = "https://www.arandadeduero.es"
SEDE_BASE = "https://sede.arandadeduero.es"
TRANSP_BASE = "https://transparencia.arandadeduero.es"
MUNICIPIO = "Aranda de Duero"
ID_PREFIX = "aranda-de-duero"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"

DEFAULT_TRANSPARENCIA_PAGES: list[tuple[str, str]] = [
    (
        f"{TRANSP_BASE}/obras-publicas-y-urbanismo/plan-general-de-ordenacion-urbana/",
        "PGOU",
    ),
    (
        f"{TRANSP_BASE}/obras-publicas-y-urbanismo/convenios-urbanisticos/",
        "convenio urbanístico",
    ),
]

URBANISMO_KEYWORD = "PTS_PC_012"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|primera ocupaci[oó]n|"
    r"certificado.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|"
    r"proyecto de (?:urbaniz|actuaci)|estudio de detalle|modificaci[oó]n|"
    r"aprobaci[oó]n (?:inicial|definitiva)|reparcel|enajenaci[oó]n.*suelo|"
    r"unidad de (?:ejecuci[oó]n|actuaci)|ue\s*\d|actuaci[oó]n urban)",
)
RE_EXCLUDE_PROY = re.compile(
    r"(?i)(cuenta general|padr[oó]n ibi|huertos urbanos|agenda urbana|"
    r"bolsa de empleo|tribunal calificador|subvenci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|documents)/(\d{4})/(\d{2})/")
RE_TRANSP_PDF = re.compile(
    r'href="(https?://transparencia\.arandadeduero\.es/wp-content/uploads/[^"]+\.pdf)"',
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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = re.findall(r"\b((?:19|20)\d{2})\b", Path(url).name)
    valid = [int(y) for y in years if 1980 <= int(y) <= 2035]
    if valid:
        return f"{max(valid)}-01-01"
    return None


def _title_from_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).name
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    name = name.replace("+", " ").replace("%20", " ").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name[:500] if name else url


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        y, mo, d = int(obj["year"]), int(obj["month"]), int(obj["day"])
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _proyecto_tipo(section: str, title: str) -> str:
    blob = f"{section} {title}".lower()
    if "convenio" in blob:
        return "convenio urbanístico"
    if "exposici" in blob or "informaci" in blob:
        return "información pública"
    if "pgou" in blob or "ordenaci" in blob or "planeam" in blob:
        return "planeamiento"
    if "enajenaci" in blob:
        return "enajenación suelo"
    if "urbaniz" in blob or "ue " in blob:
        return "proyecto urbanización"
    return section or "urbanismo"


class ArandaDeDueroAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA (tablón + catálogo urbanismo) + transparencia PGOU/convenios."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        raw_pages = self.config.get("transparencia_pages")
        if raw_pages:
            self.transparencia_pages = [(p["url"], p.get("tipo", "documento")) for p in raw_pages]
        else:
            self.transparencia_pages = list(DEFAULT_TRANSPARENCIA_PAGES)

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-aranda-de-duero/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.arandadeduero.es" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
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

    def _tablon_row(self, row: dict[str, Any]) -> tuple[str, str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        expte = str(row.get("externString") or "")
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, remitente, fecha, expte, url

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            keywords = item.get("keywordList") or []
            if not any(str(k.get("code") or "") == URBANISMO_KEYWORD for k in keywords):
                continue
            name = str(item.get("name") or "").strip()
            code = str(item.get("code") or item.get("dboid") or name)
            if not name:
                continue
            url = f"{CATALOGO_URL}#tramite={code}"
            rows.append({"name": name, "code": code, "url": url})
        return rows

    def _extract_page_documents(self, page_url: str, default_tipo: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TRANSP_PDF.finditer(html):
            doc_url = m.group(1)
            if doc_url in seen:
                continue
            seen.add(doc_url)
            titulo = _title_from_url(doc_url)
            idx = m.start()
            ctx = html[max(0, idx - 600) : idx + 200]
            ctx_plain = unescape(re.sub(r"<[^>]+>", " ", ctx))
            ctx_plain = re.sub(r"\s+", " ", ctx_plain).strip()
            anchor_m = re.search(r">([^<]{8,200})</a>\s*$", ctx_plain[-200:])
            if anchor_m:
                titulo = anchor_m.group(1).strip()[:500]
            records.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_url(doc_url) or _parse_fecha_dmy(ctx_plain) or "",
                    "url": page_url,
                    "pdf_url": doc_url,
                    "tipo": default_tipo,
                }
            )
        return records

    def _collect_transparencia_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url, tipo in self.transparencia_pages:
            for doc in self._extract_page_documents(page_url, tipo):
                rows.append(
                    {
                        "id": _stable_id("proy", doc["pdf_url"]),
                        "municipio": MUNICIPIO,
                        "titulo": doc["titulo"],
                        "fecha": doc["fecha"] or None,
                        "tipo": _proyecto_tipo(tipo, doc["titulo"]),
                        "url": doc["url"],
                        "pdf_url": doc["pdf_url"],
                        "source": "ayuntamiento",
                        "origen": "transparencia",
                    }
                )
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
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

    def _tramite_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item["name"]
        if not RE_LICENCIA.search(name):
            return None
        return {
            "id": _stable_id("lic", item["code"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": name[:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": "catalogo",
        }

    def _tramite_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item["name"]
        if RE_LICENCIA.search(name) and not RE_PROYECTO.search(name):
            return None
        if not RE_PROYECTO.search(name):
            return None
        return {
            "id": _stable_id("proy", item["code"]),
            "municipio": MUNICIPIO,
            "titulo": name[:500],
            "fecha": None,
            "tipo": _proyecto_tipo("trámite", name),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": "catalogo",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
        if RE_EXCLUDE_PROY.search(blob):
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
            "tipo": _proyecto_tipo(remitente, title),
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

        for item in self._collect_catalog_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_catalog_tramites():
            rec = self._tramite_to_licencia(item)
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
        for item in self._collect_catalog_tramites():
            add(self._tramite_to_proyecto(item))
        for rec in self._collect_transparencia_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
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
