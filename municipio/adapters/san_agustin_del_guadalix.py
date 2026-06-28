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

WP_BASE = "https://sanagustindelguadalix.net"
SEDE_BASE = "https://sanagustindelguadalix.sedelectronica.es"
MUNICIPIO = "San Agustín del Guadalix"
ID_PREFIX = "san-agustin-del-guadalix"

URBANISMO_ROOT = f"{WP_BASE}/portal-transparencia/normativa-urbanismo/"
URBANISMO_PAGE_ID = 25892
FORMULARIOS_URL = f"{WP_BASE}/formularios-solicitudes/"
BOARD_URL = f"{SEDE_BASE}/board/"
DOSSIER_URL = f"{SEDE_BASE}/dossier"

RE_PREVIEW = re.compile(
    r'href="(https://sanagustindelguadalix\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="(https://sanagustindelguadalix\.sedelectronica\.es/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|obra)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|"
    r"ocupaci[oó]n (?:de |en )?v[ií]a p[uú]blica|primera ocupaci[oó]n|"
    r"licencia de actividad|licencia funcionamiento)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|peri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva)|parcela|suelo|urbanizaci|"
    r"normas subsidiarias|ordenanza|carretera|corredor|industrial)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-/](\d{2})[-/]")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(
    r"href=['\"]((?:https://sanagustindelguadalix\.net)?/[^'\"]+\.pdf[^'\"]*)['\"]",
    re.I,
)
RE_LICENCIA_LINK = re.compile(
    r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*>([^<]*(?:licencia|declaraci[oó]n responsable|ocupaci[oó]n)[^<]*)</a>",
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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(Path(url).name) if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _pdf_tipo(name: str) -> str:
    n = name.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "peri" in n:
        return "PERI"
    if "convenio" in n:
        return "convenio urbanístico"
    if "memoria" in n:
        return "memoria"
    if "plano" in n:
        return "plano"
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "ordenanza" in n:
        return "ordenanza"
    if "estudio" in n:
        return "estudio"
    if "bocm" in n:
        return "información pública BOCM"
    return "documento urbanismo"


class SanAgustinDelGuadalixAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (portal transparencia urbanismo) + tablón espublico sede."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.dossier_url = str(self.config.get("dossier_url") or DOSSIER_URL)
        self.formularios_url = str(self.config.get("formularios_url") or FORMULARIOS_URL)
        self.urbanismo_root = str(self.config.get("urbanismo_root") or URBANISMO_ROOT)
        self.urbanismo_page_id = int(self.config.get("urbanismo_page_id") or URBANISMO_PAGE_ID)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-san-agustin-del-guadalix/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{WP_BASE}/", href)

    def _collect_urbanismo_pages(self) -> list[dict[str, Any]]:
        queue = [self.urbanismo_page_id]
        seen_ids: set[int] = set()
        pages: list[dict[str, Any]] = []
        while queue:
            pid = queue.pop(0)
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            try:
                page = self._fetch_json(f"{WP_BASE}/wp-json/wp/v2/pages/{pid}")
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            pages.append(page)
            try:
                children = self._fetch_json(
                    f"{WP_BASE}/wp-json/wp/v2/pages?parent={pid}&per_page=100"
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if isinstance(children, list):
                for child in children:
                    cid = child.get("id")
                    if isinstance(cid, int):
                        queue.append(cid)
        return pages

    def _page_to_proyectos(self, page: dict[str, Any]) -> list[dict[str, Any]]:
        title = _strip_html(str((page.get("title") or {}).get("rendered") or ""))
        link = str(page.get("link") or "").strip()
        fecha = _iso_date_wp(str(page.get("modified") or page.get("date") or ""))
        content = str((page.get("content") or {}).get("rendered") or "")
        rows: list[dict[str, Any]] = []

        if title and link and RE_PROYECTO.search(title):
            rows.append(
                {
                    "id": _stable_id("proy", link),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": fecha,
                    "tipo": _pdf_tipo(title),
                    "url": link,
                    "source": "ayuntamiento",
                    "origen": "wp_urbanismo_page",
                }
            )

        seen_pdfs: set[str] = set()
        for href in RE_PDF_HREF.findall(content):
            pdf = self._abs_wp(href)
            if pdf in seen_pdfs or "favicon" in pdf.lower():
                continue
            seen_pdfs.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            pdf_title = f"{title}: {name}" if title else name
            rows.append(
                {
                    "id": _stable_id("proy", pdf),
                    "municipio": MUNICIPIO,
                    "titulo": pdf_title[:500],
                    "fecha": _fecha_from_url(pdf) or fecha,
                    "tipo": _pdf_tipo(name),
                    "url": link or pdf,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "origen": "wp_urbanismo_pdf",
                }
            )
        return rows

    def _collect_wp_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for page in self._collect_urbanismo_pages():
            for rec in self._page_to_proyectos(page):
                by_id[rec["id"]] = rec
        return list(by_id.values())

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        body = tbody_m.group(1) if tbody_m else html
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S | re.I):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 6:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": _strip_html(cells[1]),
                    "procedimiento": _strip_html(cells[2]),
                    "categoria": _strip_html(cells[3]),
                    "descripcion": _strip_html(cells[4]),
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])),
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board_table(html, "tablon_sede")

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.formularios_url)
        except urllib.error.URLError:
            html = ""
        seen: set[str] = set()
        if html:
            for m in RE_LICENCIA_LINK.finditer(html):
                href, label = m.group(1), unescape(_strip_html(m.group(2)))
                url = self._abs_wp(href)
                if url in seen:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": _fecha_from_url(url),
                        "tipo": label[:120] or "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": label[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "formularios_urbanismo",
                    }
                )
        rows.append(
            {
                "id": _stable_id("lic", self.urbanismo_root),
                "fecha_concesion": None,
                "tipo": "normativa y planeamiento",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — normativa urbanismo",
                "url": self.urbanismo_root,
                "source": "ayuntamiento",
                "origen": "urbanismo_transparencia",
            }
        )
        rows.append(
            {
                "id": _stable_id("lic", f"{self.sede_base}/"),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanísticos",
                "url": f"{self.sede_base}/",
                "source": "ayuntamiento",
                "origen": "sede_electronica",
            }
        )
        return rows

    def _board_blob(self, row: dict[str, Any]) -> str:
        return " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = self._board_blob(row)
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = self._board_blob(row)
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        tipo = "urbanismo"
        if re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            tipo = "información pública"
        elif re.search(r"(?i)planeamiento|pgou|peri|plan (?:parcial|especial|general)", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)convenio", blob):
            tipo = "convenio"
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row.get("titulo") or ""):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": row["titulo"][:120],
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row["url"],
            "source": "ayuntamiento",
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
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_tramites():
            rec = self._tramite_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "formularios_tablon_sede"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec:
                existing[rec["id"]] = rec
        for row in self._collect_tramites():
            rec = self._tramite_to_licencia(row)
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

        for rec in self._collect_wp_proyectos():
            add(rec)
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        wp_n = sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_"))
        tablon_n = sum(1 for r in rows if r.get("origen") == "tablon_sede")
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_items": wp_n,
            "tablon_items": tablon_n,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
