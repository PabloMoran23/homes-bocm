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

WEB_BASE = "https://www.vila-real.es/portal"
SEDE_BASE = "https://seuelectronica.vila-real.es"
MUNICIPIO = "Vila-real"
ID_PREFIX = "vila-real"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
PGOU_PDF_URL = (
    "https://www.vila-real.es/portal/RecursosWeb/DOCUMENTOS/1/0_43929_1.pdf"
)

DEFAULT_DOC_LIST_PAGES: list[str] = [
    f"{WEB_BASE}/p_20_contenedor1.jsp?seccion=s_ldoc_d11_v1.jsp&codbusqueda=1070&codResi=1&"
    "codMenuPN=600&codMenuSN=626&codMenuTN=949&codMenu=951&language=es",
    f"{WEB_BASE}/p_20_contenedor1.jsp?seccion=s_ldoc_d11_v1.jsp&codbusqueda=1071&codResi=1&"
    "codMenuPN=600&codMenuSN=626&codMenuTN=949&codMenu=952&language=es",
    f"{WEB_BASE}/p_20_contenedor1.jsp?seccion=s_ldoc_d11_v1.jsp&codbusqueda=1072&codResi=1&"
    "codMenuPN=600&codMenuSN=626&codMenuTN=949&codMenu=953&language=es",
    f"{WEB_BASE}/p_20_contenedor1.jsp?seccion=s_ldoc_d11_v1.jsp&codbusqueda=1073&codResi=1&"
    "codMenuPN=600&codMenuSN=626&codMenuTN=949&codMenu=954&language=es",
]

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/p_85_contenedor5.jsp?seccion=s_fdes_d4_v2.jsp&codbusqueda=625&language=es&"
    "codResi=1&codMenuPN=589&codMenu=638",
    f"{WEB_BASE}/p_20_contenedor1.jsp?seccion=s_fdes_d4_v2.jsp&codbusqueda=617&language=es&"
    "codResi=1&codMenuPN=589&codMenu=630",
    f"{WEB_BASE}/p_20_contenedor1.jsp?seccion=s_fdes_d4_v2.jsp&codbusqueda=618&language=es&"
    "codResi=1&codMenuPN=589&codMenu=631",
    PGOU_PDF_URL,
]

LICENCIA_TRAMITE_HINTS: tuple[str, ...] = (
    "licencia de obra",
    "licencia urban",
    "licencia de parcelación",
    "declaración responsable de obras",
    "comunicación previa",
    "certificado urbanístico",
    "licencia de obras singulares",
    "proyectos de urbanización",
    "primera ocupación",
    "licencia de demolición",
    "licencia de actividad",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|solicitud de licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n|"
    r"parcelaci[oó]n|demolici[oó]n|urbanizaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|modificaci[oó]n|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|reparcel|sector|homologaci[oó]n|"
    r"ordenanza|suelo|uhi[\s-]?\d|europlataforma|sedeny|industrial|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional))",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|empleo p[uú]blico|bolsa de|subvenci[oó]n deportiv|"
    r"monitor/a temps lliure|inscripci[oó]n curs|fiestas|beca|impuesto sobre|"
    r"padrones?|cobranza|grafiti|mural urbano|energ[ií]a solar)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ES = re.compile(
    r"(?i)(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo),?\s*"
    r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
)
MESES_ES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_PAGE_TITLE = re.compile(r"<title>\s*([^<|]+)", re.I)


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


def _parse_fecha_es(text: str) -> str | None:
    m = RE_FECHA_ES.search(text or "")
    if not m:
        return None
    mes = MESES_ES.get(m.group(2).lower())
    if not mes:
        return None
    try:
        return datetime(int(m.group(3)), mes, int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_pub_date(pub: dict[str, Any] | None) -> str | None:
    if not isinstance(pub, dict):
        return None
    try:
        return datetime(
            int(pub["year"]),
            int(pub["month"]),
            int(pub["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _clean(text: str) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()


def _proyecto_tipo(blob: str) -> str:
    b = (blob or "").lower()
    if "pgou" in b or "plan general" in b or "normas urban" in b:
        return "PGOU"
    if "plan parcial" in b or "sector" in b or "uhi" in b:
        return "plan parcial"
    if "homologaci" in b:
        return "homologación planeamiento"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "informaci" in b and "p[uú]blica" in b:
        return "información pública"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "proyecto de obra" in b:
        return "proyecto de obras"
    return "urbanismo"


class VilaRealAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal eAdmin (vila-real.es) + sede STA (tablón/catálogo TAO)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.doc_list_pages = [
            str(u) for u in (self.config.get("doc_list_pages") or DEFAULT_DOC_LIST_PAGES)
        ]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._tablon_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-vila-real/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or self.sede_base in url else None
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            raw = resp.read()
        for enc in ("utf-8", "latin-1", "iso-8859-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _abs_url(self, href: str, page_url: str) -> str:
        return unescape(urllib.parse.urljoin(page_url, href))

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

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
        if self._tablon_cache is not None:
            return self._tablon_cache
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except (urllib.error.URLError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            title = str(item.get("descriptionProc") or item.get("externString") or "").strip()
            rem = item.get("remitent") or {}
            remitente = str(rem.get("description") or rem.get("code") or "")
            fecha = _fecha_from_pub_date(item.get("pubDateIni")) or ""
            dboid = str(item.get("dboid") or title)
            url = f"{TABLON_URL}#dboid={dboid}"
            rows.append(
                {
                    "titulo": title[:500],
                    "remitente": remitente,
                    "fecha": fecha,
                    "url": url,
                    "origen": "tablon_sta",
                }
            )
        self._tablon_cache = rows
        return rows

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True)
        except (urllib.error.URLError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = _clean(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or item.get("code") or "")
            if not name or not dboid:
                continue
            blob = name + " " + _clean(str(item.get("descriptionExt") or ""))
            if not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if RE_NOISE.search(blob) and not RE_LICENCIA.search(blob):
                continue
            rows.append(
                {
                    "titulo": name[:500],
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                    "licencia": any(h in name.lower() for h in LICENCIA_TRAMITE_HINTS)
                    or bool(RE_LICENCIA.search(blob)),
                }
            )
        return rows

    def _collect_doc_tables(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.doc_list_pages:
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, OSError):
                continue
            page_title = self._page_title(html, page_url)
            for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
                row_html = m.group(1)
                if "href" not in row_html.lower():
                    continue
                cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.I | re.S)
                if len(cells) < 2:
                    continue
                titulo = _clean(cells[0])
                if len(titulo) < 4:
                    continue
                fecha_raw = _clean(cells[1])
                fecha = _parse_fecha_es(fecha_raw) or _parse_fecha_dmy(fecha_raw)
                link_m = re.search(r'href="([^"]+)"', row_html, re.I)
                if not link_m:
                    continue
                doc_url = self._abs_url(link_m.group(1), page_url)
                key = doc_url + titulo
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": fecha,
                        "url": doc_url,
                        "page_title": page_title,
                        "origen": "portal_doc_list",
                    }
                )
        return rows

    def _page_title(self, html: str, fallback: str) -> str:
        m = RE_PAGE_TITLE.search(html)
        if m:
            t = _clean(m.group(1))
            t = re.sub(r"\s*-\s*Ayuntamiento de Vila-real.*$", "", t, flags=re.I).strip()
            if t:
                return t[:200]
        return fallback[:200]

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            if page_url.lower().endswith(".pdf"):
                titulo = "Normas urbanísticas PGOU Vila-real (texto consolidado)"
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": "2022-08-01",
                        "url": page_url,
                        "pdf_url": page_url,
                        "origen": "portal_pdf",
                    }
                )
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
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))[:200]
                ctx_start = max(0, pdf_m.start() - 400)
                ctx = _clean(html[ctx_start : pdf_m.start()])
                titulo = name if len(name) > 8 else page_title
                if RE_PROYECTO.search(ctx):
                    titulo = ctx[-120:] if len(ctx) > 20 else titulo
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _parse_fecha_dmy(name) or _parse_fecha_dmy(ctx),
                        "url": page_url,
                        "pdf_url": pdf,
                        "page_title": page_title,
                        "origen": "portal_pdf",
                    }
                )
        return rows

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", TABLON_URL),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios y edictos electrónicos",
                "url": TABLON_URL,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", CATALOGO_URL),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — licencias y urbanismo (STA)",
                "url": CATALOGO_URL,
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
        ]

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo') or ''} {row.get('remitente') or ''}"
        if RE_NOISE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha") or None,
            "tipo": "licencia / edicto",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _catalog_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if not item.get("licencia"):
            return None
        return {
            "id": _stable_id("lic", item["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"],
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _to_proyecto(
        self,
        titulo: str,
        url: str,
        fecha: str | None,
        *,
        pdf_url: str | None = None,
        origen: str | None = None,
    ) -> dict[str, Any] | None:
        blob = titulo or ""
        if RE_NOISE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", pdf_url or url + titulo),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": origen,
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo') or ''} {row.get('remitente') or ''}"
        if RE_NOISE.search(blob):
            return None
        return self._to_proyecto(
            row["titulo"],
            row["url"],
            row.get("fecha") or None,
            origen=row.get("origen"),
        )

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
        for rec in self._licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_catalog_tramites():
            rec = self._catalog_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        stats = self.backfill_licencias(out_jsonl)
        merged = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        for rid, rec in existing.items():
            merged.setdefault(rid, rec)
        rows = list(merged.values())
        self._write_jsonl(out_jsonl, rows)
        after = len(rows)
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}

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
            if not item.get("licencia"):
                add(
                    self._to_proyecto(
                        item["titulo"],
                        item["url"],
                        None,
                        origen=item.get("origen"),
                    )
                )
        for item in self._collect_doc_tables():
            add(
                self._to_proyecto(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                    origen=item.get("origen"),
                )
            )
        for item in self._collect_seed_pdfs():
            add(
                self._to_proyecto(
                    item["titulo"],
                    item.get("pdf_url") or item["url"],
                    item.get("fecha"),
                    pdf_url=item.get("pdf_url"),
                    origen=item.get("origen"),
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "doc_list": sum(1 for r in rows if r.get("origen") == "portal_doc_list"),
            "portal_pdf": sum(1 for r in rows if r.get("origen") == "portal_pdf"),
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
