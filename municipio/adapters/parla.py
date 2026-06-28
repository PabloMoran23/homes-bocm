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

SEDE_BASE = "https://sede.ayuntamientoparla.es"
TRANSP_BASE = "https://transparencia.ayuntamientoparla.es"
MUNICIPIO = "Parla"
ID_PREFIX = "parla"

CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
LICENCIAS_PDF_URL = (
    f"{TRANSP_BASE}/obras-publicas-y-urbanismo/expedientes-de-licencias-de-obras/"
)
LICENCIAS_LISTADO_PDF = (
    f"{TRANSP_BASE}/wp-content/uploads/2021/02/EXPEDIENTES-LICENCIAS-OBRA-2020.pdf"
)

DEFAULT_TRANSPARENCIA_PAGES: list[tuple[str, str]] = [
    (
        f"{TRANSP_BASE}/obras-publicas-y-urbanismo/planeamiento-general/",
        "planeamiento general",
    ),
    (
        f"{TRANSP_BASE}/obras-publicas-y-urbanismo/planeamiento-de-desarrollo/",
        "planeamiento de desarrollo",
    ),
    (
        f"{TRANSP_BASE}/obras-publicas-y-urbanismo/planeamiento-de-desarrollo-2/",
        "planeamiento en exposición",
    ),
    (
        f"{TRANSP_BASE}/obras-publicas-y-urbanismo/plan-general-de-ordenacion-urbana/",
        "PGOU",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|certificado.*obra|"
    r"primera ocupaci[oó]n|placa de vado|cambio de uso)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|modificaci[oó]n|aprobaci[oó]n|"
    r"memoria|planos|normas urban|estudio|bocm|sectoriz|reparcel|suelo)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|documents)/(\d{4})/(\d{2})/")
RE_TRANSP_PDF = re.compile(
    r'href="(https?://transparencia\.ayuntamientoparla\.es/wp-content/uploads/[^"]+\.pdf)"',
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


def _proyecto_tipo(section: str, title: str) -> str:
    blob = f"{section} {title}".lower()
    if "convenio" in blob:
        return "convenio urbanístico"
    if "plan parcial" in blob or "plan especial" in blob:
        return "plan parcial"
    if "modificaci" in blob:
        return "modificación PGOU"
    if "exposici" in blob or "informaci" in blob:
        return "información pública"
    if "pgou" in blob or "ordenaci" in blob:
        return "planeamiento"
    return section or "documento urbanismo"


class ParlaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal transparencia (oGov/WordPress) + sede STA catálogo de trámites urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or TRANSP_BASE)
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-parla/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.ayuntamientoparla.es" in url else None
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

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            keywords = item.get("keywordList") or []
            if not any(str(k.get("code") or "") == "URB" for k in keywords):
                continue
            name = str(item.get("name") or "").strip()
            code = str(item.get("code") or item.get("dboid") or name)
            if not name:
                continue
            url = f"{CATALOGO_URL}#tramite={code}"
            rows.append(
                {
                    "id": _stable_id("lic", code),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": name[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite del catálogo sede; no concesión publicada",
                    "tramite_code": code,
                }
            )
        return rows

    def _collect_licencias_publicadas(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.append(
            {
                "id": _stable_id("lic", LICENCIAS_LISTADO_PDF),
                "fecha_concesion": "2020-01-01",
                "tipo": "listado licencias",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Expedientes de licencias de obra 2020 (listado PDF)",
                "url": LICENCIAS_PDF_URL,
                "pdf_url": LICENCIAS_LISTADO_PDF,
                "source": "ayuntamiento",
                "nota": "Único listado publicado en transparencia; sin actualización reciente",
            }
        )
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
            idx = m.start()
            ctx = html[max(0, idx - 900) : idx + 200]
            ctx_plain = unescape(re.sub(r"<[^>]+>", " ", ctx))
            ctx_plain = re.sub(r"\s+", " ", ctx_plain).strip()
            anchor_m = re.search(r">([^<]{8,200})</a>\s*$", ctx_plain[-220:])
            titulo = anchor_m.group(1).strip()[:500] if anchor_m else _title_from_url(doc_url)
            records.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_url(doc_url) or _parse_fecha_dmy(ctx_plain) or "",
                    "url": page_url,
                    "pdf_url": doc_url,
                    "tipo": _proyecto_tipo(default_tipo, titulo),
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
                        "tipo": doc["tipo"],
                        "url": doc["url"],
                        "pdf_url": doc["pdf_url"],
                        "source": "ayuntamiento",
                        "origen": page_url,
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
        for rec in self._collect_catalog_tramites() + self._collect_licencias_publicadas():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "catalogo_tramites_y_listado_pdf",
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
        rows = self._collect_transparencia_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia_pages": len(self.transparencia_pages),
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
