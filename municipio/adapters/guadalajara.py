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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.guadalajara.es"
SEDE_BASE = "https://sedeelectronica.guadalajara.es"
MUNICIPIO = "Guadalajara"
ID_PREFIX = "guadalajara"

TABLON_RSS = f"{WEB_BASE}/es/cargarTablonRss.do?maxResultadosIniciales=300"
PGOU_URL = (
    f"{WEB_BASE}/es/ayuntamiento/normativa/normas-urbanisticas/"
    "plan-de-ordenacion-urbana-de-guadalajara/"
)
TRAMITES_URB_URL = f"{WEB_BASE}/es/sede-electronica/tramites/tramites-gestion-urbanistica/"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|gr[uú]a|parcelaci[oó]n|segregaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pom\b|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|sector|sue-|sui-|sp-pp|programa de actuaci[oó]n|unidad de ejecuci[oó]n|"
    r"agente urbanizador|estudio de detalle|ordenanza urban|pgm|instrumento)",
)
RE_SKIP = re.compile(
    r"(?i)(oposici[oó]n|empleo|subvenci[oó]n.*cooperaci|subvenci[oó]n.*emergencia|"
    r"curso de|concurso de (?:cartel|villancico|fotograf)|mercadillo de navidad|"
    r"escuela infantil|ayudas socioecon|piscinas comunitarias|zoo\b|guadalajara card)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_FECHA_PREFIX = re.compile(r"^((?:19|20)\d{2}-\d{2}-\d{2})\.\s*", re.I)
RE_PDF_HREF = re.compile(r'href="((?:https?:)?//[^"]+\.pdf[^"]*)"', re.I)
RE_PORTAL_LINK = re.compile(
    rf'href="((?:https://www\.guadalajara\.es)?/[^"#?]+\.html)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="(https://sedeelectronica\.guadalajara\.es/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
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


def _fecha_from_title(title: str) -> str | None:
    m = RE_FECHA_PREFIX.match(title or "")
    if m:
        return m.group(1)
    return _parse_fecha_iso(title) or _parse_fecha_dmy(title)


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "informaci" in n and ("publica" in n or "pública" in n):
        return "información pública"
    if "programa de actuaci" in n:
        return "programa de actuación urbanizadora"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "plan parcial" in n or "sp-pp" in n or "sector" in n:
        return "plan parcial / sector"
    if "pgou" in n or "plan general" in n or "pom" in n:
        return "PGOU"
    if "movilidad urbana" in n:
        return "movilidad urbana"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    return "urbanismo"


def _abs_web(href: str) -> str:
    href = unescape(href).strip()
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return WEB_BASE + href
    return href


class GuadalajaraAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal municipal (RSS tablón + PGOU) + sede espublico gestiona (catálogo trámites)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.tramites_urb_url = str(self.config.get("tramites_urb_url") or TRAMITES_URB_URL)
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

    def _fetch(self, url: str, *, sede: bool = False, charset: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-guadalajara/1.0")},
        )
        opener = self._opener if sede else urllib.request.build_opener()
        with opener.open(req, timeout=90 if sede else 60) as resp:
            raw = resp.read()
            enc = charset or resp.headers.get_content_charset() or "utf-8"
            return raw.decode(enc, errors="replace")

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.tablon_rss)
        except urllib.error.URLError:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if not title or not link:
                continue
            fecha = None
            if date_el is not None and date_el.text:
                try:
                    fecha = parsedate_to_datetime(date_el.text.strip()).strftime("%Y-%m-%d")
                except (TypeError, ValueError, OverflowError):
                    fecha = None
            if not fecha:
                fecha = _fecha_from_title(title)
            rows.append(
                {
                    "titulo": title[:500],
                    "url": link,
                    "fecha": fecha,
                    "origen": "portal_tablon_rss",
                }
            )
        return rows

    def _collect_pgou(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.pgou_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(titulo: str, url: str, fecha: str | None, origen: str) -> None:
            if url in seen:
                return
            blob = f"{titulo} {url}"
            if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
                return
            if not RE_PROYECTO.search(blob):
                return
            seen.add(url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "fecha": fecha,
                    "origen": origen,
                }
            )

        for m in RE_PDF_HREF.finditer(html):
            pdf = _abs_web(m.group(1))
            name = Path(urllib.parse.unquote(pdf)).stem.replace("-", " ")
            add(name, pdf, _parse_fecha_iso(name) or _fecha_from_title(name), "pgou_pdf")

        for m in RE_PORTAL_LINK.finditer(html):
            url = _abs_web(m.group(1))
            if "guadalajara.es" not in url:
                continue
            slug = Path(urllib.parse.urlparse(url).path).stem.replace("-", " ")
            if not RE_PROYECTO.search(slug):
                continue
            add(slug, url, _fecha_from_title(slug), "pgou_html")

        add(
            "Plan de Ordenación Urbana de Guadalajara (memoria y planos)",
            self.pgou_url,
            None,
            "pgou_portal",
        )
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
                    "fecha": _fecha_from_title(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in ((self.board_url, "sede_tablon"), (self.info_url, "sede_info")):
            try:
                html = self._fetch(url, sede=True)
            except urllib.error.URLError:
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in (self.dossier_url, self.tramites_urb_url):
            try:
                html = self._fetch(page_url, sede=page_url.startswith(self.sede_base))
            except urllib.error.URLError:
                continue
            for m in RE_CATALOG.finditer(html):
                url, titulo = m.group(1), unescape(m.group(2).strip())
                if url in seen:
                    continue
                seen.add(url)
                if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": url,
                        "origen": "catalogo_tramites",
                    }
                )
        return rows

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
            "nota": "Página informativa de trámite; sin registro público de concesiones en tablón",
            "origen": row.get("origen"),
        }

    def _item_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = self._blob(row) if "procedimiento" in row else row["titulo"]
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
            "fecha": row.get("fecha") or _fecha_from_title(row["titulo"]),
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
            r"(?i)planeam|promoci[oó]n urban|subvenci[oó]n.*urban",
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
            "nota": "Trámite informativo en sede electrónica",
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
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("sede")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_tramites():
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

        for item in self._collect_tablon_rss():
            add(self._item_to_proyecto(item))
        for item in self._collect_pgou():
            add(self._item_to_proyecto(item))
        for item in self._collect_board():
            add(self._item_to_proyecto(item))
        for item in self._collect_tramites():
            add(self._tramite_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "rss": sum(1 for r in rows if r.get("origen") == "portal_tablon_rss"),
            "pgou": sum(1 for r in rows if str(r.get("origen", "")).startswith("pgou")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
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
