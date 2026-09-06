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

WEB_BASE = "https://www.almonte.es"
SEDE_BASE = "https://almonte.sedelectronica.es"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
PGOU_DRIVE = "https://drive.google.com/open?id=0BylSYtrz3wPKVWpEam93RUFZOGs"
MUNICIPIO = "Almonte"
ID_PREFIX = "almonte"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/servicios/urbanismo/",
    f"{WEB_BASE}/es/servicios/participacion-ciudadana/consulta-publica/",
    f"{WEB_BASE}/es/ayuntamiento/PGOU/",
    f"{WEB_BASE}/es/descargas/",
    f"{WEB_BASE}/es/ayuntamiento/ordenanzas/",
    f"{WEB_BASE}/es/servicios/servicio-de-atencion-al-ciudadano/",
    f"{WEB_BASE}/es/ayuntamiento/impresos-y-modelos-administracion-electronica/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|ocupaci[oó]n|utilizaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|de etapas)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"ordenanza|innovaci[oó]n|rectificaci[oó]n|dotacional|consulta p[uú]blica|"
    r"participaci[oó]n ciudadana|normas subsidiarias|urbanizaci[oó]n)",
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
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "modificaci" in b and ("plan de etapas" in b or "plan parcial" in b):
        return "modificación plan parcial"
    if "innovaci" in b and "planeamiento" in b:
        return "innovación planeamiento"
    if "rectificaci" in b and "pgou" in b:
        return "rectificación PGOU"
    if "consulta p" in b and "blica" in b:
        return "consulta pública"
    if "participaci" in b and "ciudadana" in b:
        return "participación ciudadana"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "memoria" in b:
        return "memoria planeamiento"
    return "urbanismo"


class AlmonteAyuntamientoAdapter(AyuntamientoAdapter):
    """SAGA Diputación Huelva (consulta pública + PDFs) + sede informativa + SITUA."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.situa_url = str(self.config.get("situa_search_url") or SITUA_SEARCH)
        self.pgou_drive_url = str(self.config.get("pgou_drive_url") or PGOU_DRIVE)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", False):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-almonte/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or f"{self.web_base}/", href))

    def _collect_consulta_publica(self) -> list[dict[str, Any]]:
        url = f"{self.web_base}/es/servicios/participacion-ciudadana/consulta-publica/"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        parts = re.split(r"<h3[^>]*>", html, flags=re.I)
        for part in parts[1:]:
            title_match = re.match(r"(.*?)</h3>", part, flags=re.I | re.S)
            if not title_match:
                continue
            titulo = _strip_html(title_match.group(1))
            if not titulo or len(titulo) < 5:
                continue
            body = part[title_match.end() :]
            pdfs = re.findall(r'href="([^"]+\.pdf[^"]*)"', body, flags=re.I)
            doc_url = self._abs_web(pdfs[0], url) if pdfs else url
            key = titulo.lower()
            if key in seen:
                continue
            seen.add(key)
            blob = f"{titulo} {doc_url}"
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo, doc_url),
                    "url": doc_url,
                    "blob": blob,
                    "origen": "consulta_publica",
                }
            )
        return rows

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
                doc_url = self._abs_web(href, page_url)
                if doc_url in seen:
                    continue
                anchor = _strip_html(inner)
                titulo = anchor if anchor and len(anchor) > 3 else _title_from_pdf_url(doc_url)
                blob = f"{titulo} {doc_url}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if not any(
                        k in low
                        for k in (
                            "urbanismo",
                            "pgou",
                            "consulta-publica",
                            "documentos-consulta",
                            "ordenanzas-generales-urbanismo",
                        )
                    ):
                        continue
                seen.add(doc_url)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo, doc_url),
                        "url": doc_url,
                        "blob": blob,
                        "origen": "web_pdf",
                    }
                )

        rows.append(
            {
                "titulo": "PGOU Almonte — documentación pública (Google Drive)",
                "fecha": "2006-09-27",
                "url": self.pgou_drive_url,
                "blob": "plan general ordenacion urbanistica pgou almonte",
                "origen": "pgou_drive",
            }
        )
        rows.append(
            {
                "titulo": "PGOU Almonte — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "url": self.situa_url,
                "blob": "planeamiento general pgou situa almonte",
                "origen": "situa",
            }
        )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        urbanismo_base = (
            f"{self.web_base}/export/sites/almonte/es/ayuntamiento/"
            "impresos-y-modelos-administracion-electronica/Urbanismo"
        )
        return [
            {
                "id": _stable_id("lic", f"{urbanismo_base}/comunicacion-previa"),
                "fecha_concesion": None,
                "tipo": "comunicación previa",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Comunicación previa — formulario municipal",
                "url": f"{urbanismo_base}/COMUNICACION-PREVIA.pdf",
                "source": "ayuntamiento",
                "nota": "Modelo PDF en impresos SAC; sin listado de concesiones",
                "origen": "web_pdf",
            },
            {
                "id": _stable_id("lic", f"{urbanismo_base}/dr-obra-mayor"),
                "fecha_concesion": None,
                "tipo": "declaración responsable obra mayor/menor",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Declaración responsable licencia de obra mayor/menor",
                "url": f"{urbanismo_base}/declaracion-responsable-para-urbanismo-obra-mayor.pdf",
                "source": "ayuntamiento",
                "nota": "Trámite informativo; histórico no publicado",
                "origen": "web_pdf",
            },
            {
                "id": _stable_id("lic", f"{urbanismo_base}/dr-ocupacion"),
                "fecha_concesion": None,
                "tipo": "declaración responsable ocupación",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Declaración responsable licencia de ocupación o utilización",
                "url": (
                    f"{urbanismo_base}/declaracion-responsable-para-urbanismo-"
                    "ocupacion-y-utilizacion.pdf"
                ),
                "source": "ayuntamiento",
                "nota": "Trámite informativo; histórico no publicado",
                "origen": "web_pdf",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/urbanismo-licencias"),
                "fecha_concesion": None,
                "tipo": "portal consulta licencias (interno)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de licencias de obras — portal municipal",
                "url": f"{self.web_base}/es/servicios/urbanismo/",
                "source": "ayuntamiento",
                "nota": "Enlaces a IPs internas (195.55.65.234 / 80.28.254.234); no accesibles desde internet",
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
        path.parent.mkdir(parents=True, exist_ok=True)
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
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, len(rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_consulta_publica():
            add(self._doc_to_proyecto(item))

        for item in self._collect_pdf_docs():
            add(self._doc_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "consulta_publica": sum(1 for r in rows if r.get("origen") == "consulta_publica"),
            "pdfs": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
            "pgou_drive": sum(1 for r in rows if r.get("origen") == "pgou_drive"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
