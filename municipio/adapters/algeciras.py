from __future__ import annotations

import hashlib
import http.cookiejar
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

WEB_BASE = "https://www.algeciras.es"
SEDE_BASE = "https://algeciras.sedelectronica.es"
MUNICIPIO = "Algeciras"
ID_PREFIX = "algeciras"

TRANSP_URBANISMO = (
    f"{WEB_BASE}/es/ayuntamiento/transparencia/transparencia-en-materias-de-urbanismo-y-obras-publicas/"
)
EXPOSICION_PUBLICA = (
    f"{WEB_BASE}/es/ayuntamiento/transparencia/relaciones-con-los-ciudadanos-y-la-sociedad/"
)
DELEGACION_URBANISMO = f"{WEB_BASE}/es/temas/urbanismo-y-vivienda/delegacion-de-urbanismo/"
VISOR_ENMAPA = "https://algeciras.enmapa.com/portada"
SEDE_URBANISMO_INFO = f"{SEDE_BASE}/citizen-service/43207c42-4b23-454f-b860-8869daf9a041"

RE_PREVIEW = re.compile(
    r'href="(https://algeciras\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://algeciras\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_WEB_TRAMITE = re.compile(
    r'href="(/es/ayuntamiento/tramites/detalle-de-tramite/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|ocupaci[oó]n (?:de |en )?v[ií]a|recepci[oó]n de obra|"
    r"denuncia.*obra sin licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|"
    r"informaci[oó]n p[uú]blica|expediente|actuaci[oó]n urban|modificaci[oó]n.*planeam|"
    r"aprobaci[oó]n.*planeam|certificado.*urban|informe urban|ordenanza|bop|boja|"
    r"edicto|reparcel|sector|estudio de detalle|unidad de ejecuci[oó]n|"
    r"convenio urban|consulta p[uú]blica|exposici[oó]n|diligencia|junta de compensaci[oó]n|"
    r"recalificaci[oó]n|plan parcial|ue[\s._-]?\d)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|"
    r"notificaci[oó]n expediente|igualdad|"
    r"cobranza|iae|ivtm|cementerio|"
    r"calendario fiscal|recaudaci[oó]n|"
    r"fiestas|cine|empleo|deporte|pilates|gimnasia|"
    r"electores|bizum|caixabank|ofibus|ofimovil|horario.*l[ií]nea|"
    r"animales potencialmente peligrosos|auto-?taxi|veh[ií]culo|"
    r"saneamiento|abastecimiento|pppnt.*saneamiento|ruido estrat[eé]gico)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_FECHA_ISO_IN_NAME = re.compile(r"\b(20\d{2})[-_](\d{2})[-_](\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_ISO_IN_NAME.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _clean_link_title(text: str) -> str:
    t = unescape(text or "").strip()
    t = re.sub(r"\s*\(\d+\s*KB\)\s*", " ", t, flags=re.I)
    t = re.sub(r"\s*Formato:\s*pdf\s*", "", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


def _pdf_title_from_url(url: str) -> str:
    name = urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name)
    return name.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").strip()


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "plan parcial" in n or re.search(r"\bue\b|\due\d", n):
        return "plan parcial"
    if "modificaci" in n and ("pgou" in n or "planeam" in n):
        return "modificación PGOU"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "convenio" in n:
        return "convenio urbanístico"
    if "consulta p" in n and "blica" in n:
        return "consulta pública"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "diligencia" in n:
        return "diligencia planeamiento"
    if "junta de compensaci" in n:
        return "junta de compensación"
    if "certificado" in n or "informe urban" in n:
        return "certificado urbanístico"
    if "ordenanza" in n:
        return "ordenanza"
    return "urbanismo"


def _licencia_tipo(title: str) -> str:
    n = title.lower()
    if "obra menor" in n:
        return "licencia de obra menor"
    if "obra mayor" in n:
        return "licencia de obra mayor"
    if "declaraci" in n:
        return "declaración responsable"
    if "comunicaci" in n and "previa" in n:
        return "comunicación previa"
    if "actividad" in n:
        return "licencia de actividad"
    if "ocupaci" in n:
        return "licencia de ocupación"
    return "trámite licencia urbanística"


class AlgecirasAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona + web municipal SagaSuite (transparencia urbanismo, PGOU, consultas)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency"
        )
        self._ssl_ctx = ssl.create_default_context()
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-algeciras/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str, base: str | None = None) -> str:
        base = base or self.web_base
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return urllib.parse.urljoin(base + "/", href.lstrip("/"))

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_m.group(1), re.S | re.I):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0]) if cells else ""
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            expediente = _strip_html(cells[1]) if len(cells) > 1 else ""
            procedimiento = _strip_html(cells[2]) if len(cells) > 2 else ""
            categoria = _strip_html(cells[3]) if len(cells) > 3 else ""
            descripcion = _strip_html(cells[4]) if len(cells) > 4 else titulo
            fecha_cell = _strip_html(cells[5]) if len(cells) > 5 else ""
            url = link_m.group(1) if link_m else self.board_url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": expediente,
                    "procedimiento": procedimiento,
                    "categoria": categoria,
                    "descripcion": descripcion,
                    "fecha": _parse_fecha_dmy(fecha_cell) or _parse_fecha_dmy(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board_table(html, "tablon")

    def _collect_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            html = ""
        if html:
            for m in RE_CATALOG.finditer(html):
                href, titulo = m.group(1), unescape(m.group(2).strip())
                url = href if href.startswith("http") else f"{self.sede_base}{href}"
                if url in seen:
                    continue
                seen.add(url)
                if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                    continue
                rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})

        try:
            web_html = self._fetch(f"{self.web_base}/es/ayuntamiento/tramites/")
        except urllib.error.URLError:
            web_html = ""
        for m in RE_WEB_TRAMITE.finditer(web_html or ""):
            path = m.group(1)
            url = self._abs_web(path)
            if url in seen:
                continue
            slug = path.rstrip("/").split("/")[-1].replace("-", " ")
            titulo = slug.title()
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                if not re.search(r"(?i)urban|licen|obra|plusval", titulo):
                    continue
            seen.add(url)
            rows.append({"titulo": titulo[:500], "url": url, "origen": "web_tramites"})
        return rows

    def _collect_web_pdfs(self) -> list[dict[str, Any]]:
        seeds = [
            (TRANSP_URBANISMO, "transparencia_urbanismo"),
            (EXPOSICION_PUBLICA, "consulta_publica"),
            (DELEGACION_URBANISMO, "pgou_delegacion"),
        ]
        by_url: dict[str, dict[str, Any]] = {}
        for page_url, origen in seeds:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]+)', html, re.I):
                href, raw_title = m.group(1), m.group(2)
                if ".pdf" not in href.lower() and not re.search(r"formato:\s*pdf", raw_title, re.I):
                    continue
                url = self._abs_web(href, page_url)
                titulo = _clean_link_title(raw_title) or _pdf_title_from_url(url)
                blob = f"{titulo} {url}"
                if self._should_exclude(blob) and not RE_PROYECTO.search(blob):
                    continue
                if origen == "consulta_publica" and not RE_PROYECTO.search(blob):
                    continue
                by_url[url] = {
                    "titulo": titulo[:500],
                    "url": url,
                    "pdf_url": url,
                    "fecha": _parse_fecha_dmy(blob),
                    "blob": blob[:2000],
                    "origen": origen,
                    "page_url": page_url,
                }
        return list(by_url.values())

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios en espublico gestiona (/board)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.dossier_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites electrónicos — urbanismo y licencias",
                "url": self.dossier_url,
                "source": "ayuntamiento",
                "nota": "Catálogo sede: licencias, DR, comunicaciones previas",
                "origen": "dossier",
            },
            {
                "id": _stable_id("lic", SEDE_URBANISMO_INFO),
                "fecha_concesion": None,
                "tipo": "información trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — información general sede",
                "url": SEDE_URBANISMO_INFO,
                "source": "ayuntamiento",
                "nota": "Guía informativa licencias y actuaciones urbanísticas",
                "origen": "sede_info",
            },
            {
                "id": _stable_id("lic", VISOR_ENMAPA),
                "fecha_concesion": None,
                "tipo": "visor urbanístico municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Visor urbanístico Enmapa",
                "url": VISOR_ENMAPA,
                "source": "ayuntamiento",
                "nota": "Consulta cartográfica PGOU (sin enlace automático a expedientes)",
                "origen": "visor",
            },
        ]

    def _should_exclude(self, blob: str) -> bool:
        if RE_EXCLUDE.search(blob):
            if RE_PROYECTO.search(blob) and (
                "ordenanza" in blob.lower() or "planeam" in blob.lower() or "pgou" in blob.lower()
            ):
                return False
            return True
        return False

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if self._should_exclude(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or _licencia_tipo(blob),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if self._should_exclude(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        cat = (row.get("categoria") or "").lower()
        if cat not in ("urbanismo", "ordenanzas y reglamentos") and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _parse_fecha_dmy(row["titulo"]),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _web_pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row["titulo"]
        if self._should_exclude(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "pdf_url": row.get("pdf_url") or row["url"],
            "origen": row.get("origen"),
        }

    def _web_pdf_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row["titulo"]
        if self._should_exclude(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": _licencia_tipo(row["titulo"]),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "pdf_url": row.get("pdf_url") or row["url"],
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]) and row.get("origen") != "web_tramites":
            return None
        if self._should_exclude(row["titulo"]):
            return None
        if row.get("origen") == "web_tramites" and not re.search(
            r"(?i)licen|obra|plusval|urban", row["titulo"]
        ):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": _licencia_tipo(row["titulo"]),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite",
            "origen": row.get("origen"),
        }

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        if self._should_exclude(row["titulo"]):
            return None
        if RE_LICENCIA.search(row["titulo"]) and not re.search(
            r"(?i)planeam|urban|certificado|informe|actuaci", row["titulo"]
        ):
            return None
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite",
            "origen": row.get("origen"),
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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_web_pdfs():
            rec = self._web_pdf_to_licencia(item)
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
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "tramites": sum(
                1 for r in rows if r.get("origen") in ("catalogo_tramites", "web_tramites")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
        rows = self._load_jsonl(out_jsonl)
        for rec in rows:
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_web_pdfs():
            add(self._web_pdf_to_proyecto(item))
        for item in self._collect_tramites():
            add(self._tramite_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", VISOR_ENMAPA),
                "municipio": MUNICIPIO,
                "titulo": "Visor urbanístico municipal (Enmapa)",
                "fecha": None,
                "tipo": "visor cartográfico",
                "url": VISOR_ENMAPA,
                "source": "ayuntamiento",
                "origen": "visor",
                "nota": "PGOU y capas urbanísticas; sin API pública enlazada a expedientes",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "web_pdfs": sum(1 for r in rows if r.get("origen", "").startswith(("transparencia", "consulta", "pgou"))),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
