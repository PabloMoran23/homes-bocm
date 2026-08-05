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

WP_BASE = "https://ayuntamientolahiruela.es"
SEDE_BASE = "https://lahiruela.sedelectronica.es"
MUNICIPIO = "La Hiruela"
ID_PREFIX = "la-hiruela"

AYUNTAMIENTO_URL = f"{WP_BASE}/ayuntamiento/"
DUS5000_URL = f"{WP_BASE}/dus5000/"

RE_PREVIEW = re.compile(
    r'href="(https://lahiruela\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|direccion obra|direcci[oó]n de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto (?:de |integral|de actuaci)|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva|provisional)|reparcel|"
    r"edicto|bando|embellecimiento|viario|evaluaci[oó]n de edificios|"
    r"condiciones est[eé]ticas|reglamento.*urban|dus\s*5000|"
    r"redacci[oó]n de proyecto|area recreativa|huerto del cura)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|plusvalia|basura|"
    r"residuos|vehiculos|notificaci[oó]n expediente|igualdad|"
    r"cobranza|iae|ivtm|cementerio|dominio publico|rodamiento|"
    r"incendios|riesgo de incendio|calendario fiscal|recaudaci[oó]n|"
    r"servicios turisticos|aprovechamiento dominio|abrevaderos|zarzos|"
    r"tarifas|bonificaci[oó]n.*vehiculo|imprenta|cartel|rurales|bioeconom)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?ayuntamientolahiruela\.es)?/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"BOCM[-_]?(\d{8})", url, re.I)
    if m:
        raw = m.group(1)
        try:
            return datetime(int(raw[:4]), int(raw[4:6]), int(raw[6:8])).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return _parse_fecha_dmy(Path(url).name)


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "proyecto integral" in n or "dus" in n:
        return "proyecto integral"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "planeamiento" in n or "pgou" in n or "modificaci" in n:
        return "planeamiento"
    if "embellecimiento" in n or "viario" in n:
        return "obra pública"
    if "evaluaci" in n and "edificio" in n:
        return "ordenanza urbanística"
    if "est[eé]tica" in n or "condiciones est" in n:
        return "ordenanza estética"
    if "reglamento" in n:
        return "reglamento urbanístico"
    if "informaci" in n:
        return "información pública"
    return "urbanismo"


class LaHiruelaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress ayuntamientolahiruela.es (ordenanzas PDF) + sede espublico tablón."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency"
        )
        self.ayuntamiento_url = str(self.config.get("ayuntamiento_url") or AYUNTAMIENTO_URL)
        self.dus5000_url = str(self.config.get("dus5000_url") or DUS5000_URL)
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-hiruela/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_m.group(1), re.S | re.I):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 4:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
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

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 400) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": titulo[:500],
                    "expediente": "",
                    "procedimiento": "",
                    "categoria": "",
                    "descripcion": titulo,
                    "fecha": _parse_fecha_dmy(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in ((self.board_url, "tablon"), (f"{self.sede_base}/info.0", "info_tablon")):
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_wp_pdfs(self, page_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(
            r'<a[^>]+href=["\']([^"\']+\.pdf[^"\']*)["\'][^>]*>(.*?)</a>',
            html,
            re.I | re.S,
        ):
            href, label = m.group(1), _strip_html(m.group(2))
            pdf = self._abs_wp(href)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            titulo = label or name.replace("-", " ").replace("_", " ")
            blob = f"{titulo} {name}"
            if RE_EXCLUDE.search(blob):
                continue
            if not RE_PROYECTO.search(blob):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": pdf,
                    "pdf_url": pdf,
                    "fecha": _fecha_from_url(pdf),
                    "origen": origen,
                    "page_url": page_url,
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y exposiciones públicas en sede espublico",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.transparency_url),
                "fecha_concesion": None,
                "tipo": "portal transparencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal de transparencia — sede electrónica",
                "url": self.transparency_url,
                "source": "ayuntamiento",
                "nota": "Transparencia municipal; sin catálogo urbanismo scrapeable",
                "origen": "transparencia",
            },
            {
                "id": _stable_id("lic", self.ayuntamiento_url),
                "fecha_concesion": None,
                "tipo": "ordenanzas y normativa urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ayuntamiento — ordenanzas urbanísticas (PDF)",
                "url": self.ayuntamiento_url,
                "source": "ayuntamiento",
                "nota": "NNSS, evaluación de edificios y condiciones estéticas en web municipal",
                "origen": "wp_ordenanzas",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia / obra",
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
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
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

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        pdf = row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", pdf),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha") or _fecha_from_url(pdf),
            "tipo": _proyecto_tipo(titulo),
            "url": pdf,
            "source": "ayuntamiento",
            "pdf_url": pdf,
            "origen": row.get("origen"),
        }
        if row.get("page_url"):
            rec["page_url"] = row["page_url"]
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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "transparencia", "wp_ordenanzas")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_wp_pdfs(self.ayuntamiento_url, "wp_ordenanzas"):
            add(self._pdf_to_proyecto(item))
        for item in self._collect_wp_pdfs(self.dus5000_url, "dus5000"):
            add(self._pdf_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp")),
            "dus5000": sum(1 for r in rows if r.get("origen") == "dus5000"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        def merge(rec: dict[str, Any] | None) -> None:
            if rec:
                existing[rec["id"]] = rec

        for item in self._collect_board():
            merge(self._board_to_proyecto(item))
        for item in self._collect_wp_pdfs(self.ayuntamiento_url, "wp_ordenanzas"):
            merge(self._pdf_to_proyecto(item))
        for item in self._collect_wp_pdfs(self.dus5000_url, "dus5000"):
            merge(self._pdf_to_proyecto(item))

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
