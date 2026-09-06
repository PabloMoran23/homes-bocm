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

WEB_BASE = "https://www.aljaraque.es"
SEDE_BASE = "https://aljaraque.sedelectronica.es"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Aljaraque"
ID_PREFIX = "aljaraque"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/areas-tematicas/urbanismo/",
    f"{WEB_BASE}/es/areas-tematicas/urbanismo/el-planeamiento/",
    f"{WEB_BASE}/es/areas-tematicas/urbanismo/el-planeamiento/modificaciones-puntuales-pgou/",
    f"{WEB_BASE}/es/areas-tematicas/urbanismo/el-planeamiento/planes-parciales/",
    f"{WEB_BASE}/es/areas-tematicas/urbanismo/el-planeamiento/normas-subsidiarias/",
    f"{WEB_BASE}/es/areas-tematicas/urbanismo/el-planeamiento/innovaciones-a-las-normas-subsidiarias/",
    f"{WEB_BASE}/es/areas-tematicas/urbanismo/el-planeamiento/adaptacion-a-la-loua/",
    f"{WEB_BASE}/es/areas-tematicas/urbanismo/el-planeamiento/estudio-de-detalle/",
    f"{WEB_BASE}/es/areas-tematicas/urbanismo/como-hacer-una-obra-en-casa/",
    f"{WEB_BASE}/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/Se-publican-y-se-mantienen-publicados-las-modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados.-00002/",
    f"{WEB_BASE}/es/ayuntamiento/publicaciones-oficiales/Bandos",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|ppr|ppt|ppi|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|normas subsidiarias|loua|adaptaci[oó]n|dotacional|ficha urban)",
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"(20\d{2})(\d{2})(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


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
    m = RE_FECHA_YMD.search(url or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
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


def _title_from_pdf_url(url: str) -> str:
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    name = re.sub(r"[_-]+", " ", name).strip()
    return name[:500] if name else url


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "estudio de detalle" in b or re.search(r"\bed\b", b):
        return "estudio de detalle"
    if "modificaci" in b and "pgou" in b:
        return "modificación PGOU"
    if re.search(r"\bppr\d+", b) or "plan parcial" in b:
        return "plan parcial"
    if re.search(r"\bppt", b):
        return "plan parcial de transformación"
    if "adaptaci" in b and "loua" in b:
        return "adaptación LOUA"
    if "normas subsidiarias" in b or "normasppr" in b.replace(" ", ""):
        return "normas subsidiarias"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "ficha urban" in b:
        return "ficha urbanística"
    if "memoria" in b:
        return "memoria planeamiento"
    return "urbanismo"


class AljaraqueAyuntamientoAdapter(AyuntamientoAdapter):
    """SAGA Diputación Huelva (PDFs urbanismo) + sede propia (informativa) + SITUA."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.situa_url = str(self.config.get("situa_search_url") or SITUA_SEARCH)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-aljaraque/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or f"{self.web_base}/", href))

    def _collect_pdf_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            for href, inner in RE_LINK.findall(html):
                low = href.lower()
                if ".pdf" not in low:
                    continue
                url = self._abs_web(href, page_url)
                if url in seen:
                    continue
                seen.add(url)
                anchor = _strip_html(inner)
                titulo = anchor if anchor and len(anchor) > 3 else _title_from_pdf_url(url)
                blob = f"{titulo} {url}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if "/urbanismo/" not in url.lower() and "pgou" not in url.lower():
                        continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo, url),
                        "url": url,
                        "blob": blob,
                        "origen": "web_pdf",
                    }
                )

        rows.append(
            {
                "titulo": "PGOU Aljaraque — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "url": self.situa_url,
                "blob": "planeamiento general pgou situa aljaraque",
                "origen": "situa",
            }
        )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", f"{self.web_base}/obra-en-casa"),
                "fecha_concesion": None,
                "tipo": "guía licencia de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Cómo hacer una obra en casa — guía municipal",
                "url": f"{self.web_base}/es/areas-tematicas/urbanismo/como-hacer-una-obra-en-casa/",
                "source": "ayuntamiento",
                "nota": "Procedimiento y documentación para licencias de obra",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/faq-licencias"),
                "fecha_concesion": None,
                "tipo": "preguntas frecuentes licencias",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Preguntas frecuentes — licencia de obras",
                "url": (
                    f"{self.web_base}/es/areas-tematicas/urbanismo/preguntas-frecuentes/"
                    "preguntas-frecuentes-licencia-de-obras/"
                ),
                "source": "ayuntamiento",
                "nota": "Información informativa; sin listado de concesiones",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/info"),
                "fecha_concesion": None,
                "tipo": "sede electrónica — trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — oficina virtual",
                "url": f"{self.sede_base}/info.0",
                "source": "ayuntamiento",
                "nota": "Trámites de licencias vía sede; sin histórico público scrapeable",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/obra_en_casa.pdf"),
                "fecha_concesion": None,
                "tipo": "guía PDF licencia de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Guía PDF — obra en casa",
                "url": (
                    f"{self.web_base}/export/sites/aljaraque/es/.galleries/"
                    "areas-tematicas/Urbanismo/pdf/obras-en-casa/obra_en_casa.pdf"
                ),
                "source": "ayuntamiento",
                "nota": "Documento informativo publicado en web municipal",
                "origen": "web_pdf",
            },
        ]

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row["titulo"]
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "web_pdf"),
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
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - len(existing)), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_pdf_docs():
            rec = self._doc_to_proyecto(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pdfs": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_pdf_docs():
            rec = self._doc_to_proyecto(item)
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}
