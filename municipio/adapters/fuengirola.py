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

WEB_BASE = "https://www.fuengirola.es"
SEDE_BASE = "https://sede.fuengirola.es"
MUNICIPIO = "Fuengirola"
ID_PREFIX = "fuengirola"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
PLANEAMIENTO_DETAIL_URL = (
    f"{SEDE_BASE}/sta/Relec/CatalogDetail?action=info"
    f"&dboidProcedure=6262631033864740205304"
    f"&dboidRequest=6269031114319068205304"
)
URBANISMO_WP = f"{WEB_BASE}/concejalia/concejalia-de-urbanismo/"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n|legalizaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|"
    r"proyecto|modificaci[oó]n|reparcel|estudio (?:de detalle|ac[uú]stico)|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|sunc|api-|sector|"
    r"innovaci[oó]n|urbanizaci[oó]n|estatutos|memoria|planos|boja|edicto)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(r[eé]gimen funcionarial|convocatoria.*plaza|selecci[oó]n de personal|"
    r"ordenanza (?:fiscal|municipal reguladora del procedimiento)|plan municipal de inspecci[oó]n|"
    r"ornato p[uú]blico|arte urbano|plusval[ií]a|impuesto sobre el incremento|"
    r"taxi|ambulante|animales potencialmente peligrosos|mercado|subvenci[oó]n|"
    r"protecci[oó]n de datos|bolsa de empleo|fiestas|deportes)",
)
RE_EXCLUDE_CATALOG_LIC = re.compile(
    r"(?i)(plusval[ií]a|taxi|ambulante|animales|mercado|bonificaci[oó]n.*plusval|"
    r"transmisi[oó]n de licencia de comercio|conducci[oó]n|gr[uú]a|espect[aá]culos)",
)
RE_DOC_LINK = re.compile(r'href="(/sta/docs/GetDocumentServlet\?[^"]+)"', re.I)
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


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        y, mo, d = int(obj["year"]), int(obj["month"]), int(obj["day"])
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^:\s*", "", t)
    return t[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "estudio de detalle" in n or "estudio detalle" in n:
        return "estudio de detalle"
    if "reparcel" in n:
        return "reparcelación"
    if "convenio" in n:
        return "convenio urbanístico"
    if "innovaci" in n:
        return "innovación PGOU"
    if "urbanizaci" in n:
        return "proyecto de urbanización"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "estatutos" in n:
        return "estatutos urbanización"
    if "resumen ejecutivo" in n:
        return "resumen ejecutivo"
    if "memoria" in n:
        return "memoria planeamiento"
    return "planeamiento"


class FuengirolaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA (tablón + catálogo trámites + documentación expedientes planeamiento)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-fuengirola/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or self.sede_base in url else None
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            raw = resp.read()
            try:
                return raw.decode(charset)
            except UnicodeDecodeError:
                return raw.decode("latin-1", errors="replace")

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
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
            remitente = str(rem.get("description") or rem.get("code") or "")
            expte = str(item.get("externString") or "").strip()
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "expte": expte or None,
                    "remitente": remitente,
                    "url": self._tablon_detail_url(dboid),
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = _clean_title(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or item.get("code") or "")
            if not name or not dboid:
                continue
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _collect_planeamiento_docs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(PLANEAMIENTO_DETAIL_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_DOC_LINK.finditer(html):
            rel = m.group(1).replace("&amp;", "&")
            if rel in seen:
                continue
            seen.add(rel)
            pdf_url = urllib.parse.urljoin(self.sede_base, rel)
            idx = m.start()
            before = html[max(0, idx - 500) : idx]
            tit_candidates = re.findall(r">\s*([^<]{8,220})\s*</", before)
            titulo = _clean_title(tit_candidates[-1]) if tit_candidates else _clean_title(pdf_url)
            if titulo.lower().startswith("documentaci"):
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_text(titulo),
                    "url": PLANEAMIENTO_DETAIL_URL,
                    "pdf_url": pdf_url,
                    "origen": "catalogo_planeamiento",
                }
            )
        return rows

    def _title_to_licencia(
        self,
        title: str,
        url: str,
        fecha: str | None,
        *,
        nota: str | None = None,
        origen: str | None = None,
    ) -> dict[str, Any] | None:
        if RE_EXCLUDE.search(title):
            return None
        if not RE_LICENCIA.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha,
            "tipo": "licencia" if "comunicaci" not in title.lower() else "comunicación previa",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }
        if nota:
            rec["nota"] = nota
        if origen:
            rec["origen"] = origen
        return rec

    def _title_to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str | None,
        *,
        pdf_url: str | None = None,
        origen: str | None = None,
        expte: str | None = None,
    ) -> dict[str, Any] | None:
        blob = f"{title} {expte or ''}"
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", pdf_url or url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        if origen:
            rec["origen"] = origen
        if expte:
            rec["expte"] = expte
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(
                self._title_to_licencia(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                    origen=item.get("origen"),
                )
            )

        for item in self._collect_catalog_tramites():
            if RE_EXCLUDE_CATALOG_LIC.search(item["titulo"]):
                continue
            add(
                self._title_to_licencia(
                    item["titulo"],
                    item["url"],
                    None,
                    nota="Página informativa de trámite; no concesión publicada",
                    origen=item.get("origen"),
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_sta"}

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

        for item in self._collect_tablon():
            add(
                self._title_to_proyecto(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                    origen=item.get("origen"),
                    expte=item.get("expte"),
                )
            )

        for doc in self._collect_planeamiento_docs():
            add(
                self._title_to_proyecto(
                    doc["titulo"],
                    doc["url"],
                    doc.get("fecha"),
                    pdf_url=doc.get("pdf_url"),
                    origen=doc.get("origen"),
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": len(self._collect_tablon()),
            "planeamiento_docs": len(self._collect_planeamiento_docs()),
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
