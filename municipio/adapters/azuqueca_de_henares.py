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

WEB_BASE = "https://www.azuqueca.es"
SEDE_BASE = "https://azuqueca.sedelectronica.es"
MUNICIPIO = "Azuqueca de Henares"
ID_PREFIX = "azuqueca"

DEFAULT_SEED_URLS: list[str] = [
    f"{WEB_BASE}/servicios/urbanismo/planeamiento",
    f"{WEB_BASE}/servicios/urbanismo/gestion-y-ejecucion",
    f"{WEB_BASE}/servicios/urbanismo/informacion-de-interes",
]
LICENCIAS_PAGE = f"{WEB_BASE}/servicios/urbanismo/licencias-declaraciones-y-comunicaciones"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|parcelaci[oó]n|segregaci[oó]n|cedula urban|c[eé]dula urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pom\b|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|sector|estudio de detalle|sue-|sui-|sur[-\s]?r|plan parcial|"
    r"instrumento|unidad de ejecuci|agente urbanizador|edicto|normas urban|"
    r"miralcampo|pau sur|pol[ií]gono)",
)
RE_SKIP = re.compile(
    r"(?i)(oposici[oó]n|empleo|elecci[oó]n|jurado|baja en el padr[oó]n|"
    r"subvenci[oó]n.*cultural|mercadillo|piscina comunitaria|protecci[oó]n de datos)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_LIFERAY_PDF = re.compile(
    r'href="((?:https?://(?:www\.)?azuqueca\.es)?/documents/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_TRAMITE_SLUG = re.compile(
    r'href="(https://www\.azuqueca\.es/-/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    rf'href="({re.escape(SEDE_BASE)}/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    return _parse_fecha_iso(text) or _parse_fecha_dmy(text)


def _abs_web(href: str) -> str:
    href = unescape(href).strip()
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return WEB_BASE + href
    return href


def _pdf_label(url: str) -> str:
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    name = Path(path).name
    name = re.sub(r"\.pdf.*$", "", name, flags=re.I)
    name = name.replace("+", " ").replace("_", " ").replace("-", " ")
    return name[:500] or url


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "estudio de detalle" in n or re.search(r"\bed\b", n):
        return "estudio de detalle"
    if "plan parcial" in n or re.search(r"sur[-\s]?r", n) or "pau sur" in n:
        return "plan parcial"
    if "plan especial" in n or "miralcampo" in n:
        return "plan especial"
    if "modificaci" in n:
        return "modificación POM"
    if "pom" in n or "plan de ordenaci" in n:
        return "POM"
    if "informaci" in n and "públic" in n:
        return "información pública"
    return "urbanismo"


class AzuquecaDeHenaresAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal Liferay (POM/planes PDF) + sede espublico gestiona (tablón /board)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.seed_urls = list(self.config.get("seed_urls") or DEFAULT_SEED_URLS)
        self.licencias_page = str(self.config.get("licencias_page") or LICENCIAS_PAGE)
        self._preview_re = re.compile(
            rf'href="({re.escape(self.sede_base)}/preview-document/[^"]+)"',
            re.I,
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-azuqueca/1.0")},
        )
        opener = self._opener if sede else urllib.request.build_opener()
        with opener.open(req, timeout=90 if sede else 60) as resp:
            return resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace")

    def _collect_liferay_pdfs(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for seed in self.seed_urls:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for m in RE_LIFERAY_PDF.finditer(html):
                pdf = _abs_web(m.group(1))
                titulo = _pdf_label(pdf)
                blob = f"{titulo} {pdf}"
                if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob):
                    continue
                by_url[pdf] = {
                    "titulo": titulo,
                    "url": pdf,
                    "pdf_url": pdf,
                    "fecha": _fecha_from_blob(titulo),
                    "origen": "liferay_pdf",
                }
        return list(by_url.values())

    def _collect_portal_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in (self.licencias_page, f"{self.web_base}/servicios/atencion-a-la-ciudadania/catalogo-de-tramites"):
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                continue
            for m in RE_TRAMITE_SLUG.finditer(html):
                url = m.group(1)
                if url in seen:
                    continue
                seen.add(url)
                slug = urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace("-", " ")
                if not RE_LICENCIA.search(slug) and not RE_PROYECTO.search(slug):
                    continue
                rows.append(
                    {
                        "titulo": slug[:500],
                        "url": url,
                        "origen": "liferay_tramite",
                    }
                )
        return rows

    def _collect_catalog(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.dossier_url, sede=True)
        except urllib.error.URLError:
            return rows
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_sede"})
        return rows

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 4:
                continue
            link_m = self._preview_re.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or _strip_html(cells[0])
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": _strip_html(cells[1]) if len(cells) > 1 else "",
                    "procedimiento": _strip_html(cells[2]) if len(cells) > 2 else "",
                    "categoria": _strip_html(cells[3]) if len(cells) > 3 else "",
                    "descripcion": _strip_html(cells[4]) if len(cells) > 4 else "",
                    "fecha": _parse_fecha_dmy(_strip_html(cells[-1])),
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": origen,
                }
            )
        return rows

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in self._preview_re.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 500) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": "",
                    "procedimiento": "",
                    "categoria": "",
                    "descripcion": titulo,
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        try:
            html = self._fetch(self.board_url, sede=True)
        except urllib.error.URLError:
            return []
        items = self._parse_board_table(html, "sede_tablon")
        if not items:
            items = self._parse_board_links(html, "sede_tablon")
        for rec in items:
            by_url[rec["url"]] = rec
        return list(by_url.values())

    def _blob(self, row: dict[str, Any]) -> str:
        return " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "expediente")
        )

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = self._blob(row)
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
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
            "nota": "Página informativa; sin registro público de concesiones",
            "origen": row.get("origen"),
        }

    def _item_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = self._blob(row) if "procedimiento" in row else f"{row['titulo']} {row.get('url', '')}"
        if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        if RE_LICENCIA.search(row["titulo"]) and not re.search(
            r"(?i)planeam|informaci[oó]n urban|cedula|c[eé]dula",
            row["titulo"],
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
            "origen": row.get("origen"),
            "nota": "Trámite informativo en portal municipal",
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_portal_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_catalog():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") != "sede_tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_portal_tramites():
            rec = self._tramite_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_catalog():
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

        for item in self._collect_liferay_pdfs():
            add(self._item_to_proyecto(item))
        for item in self._collect_board():
            add(self._item_to_proyecto(item))
        for item in self._collect_portal_tramites():
            add(self._tramite_to_proyecto(item))
        for item in self._collect_catalog():
            add(self._tramite_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "liferay_pdf": sum(1 for r in rows if r.get("origen") == "liferay_pdf"),
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_tablon"),
            "tramites": sum(
                1 for r in rows if str(r.get("origen", "")).startswith(("liferay_tramite", "catalogo"))
            ),
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
