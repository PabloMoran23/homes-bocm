from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WP_BASE = "https://elmolar.org"
SEDE_BASE = "https://elmolar.sedelectronica.es"
MUNICIPIO = "El Molar"
ID_PREFIX = "el-molar"

NORMAS_URL = f"{WP_BASE}/tramites/normas-subsidiarias/"
DOCUMENTACION_URL = f"{WP_BASE}/tramites/documentacion/"
WP_API = f"{WP_BASE}/wp-json/wp/v2"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|"
    r"obra mayor|primera ocupaci[oó]n|parcelaci[oó]n|segregaci[oó]n|terrazas)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva)|sau|reurbaniz|obra[s]? (?:en|de)|"
    r"convenio|cat[aá]logo|dotacional)",
)
RE_SKIP_BOARD = re.compile(
    r"(?i)(oposici[oó]n|concurso|jurado|juez de paz|pleno ordinario|convocatoria pleno|"
    r"proceso selectivo|baremaci[oó]n|lista definitiva)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PANEL_TITLE = re.compile(
    r'vc_tta-title-text">([^<]+)</span>',
    re.I,
)
RE_PANEL_BODY = re.compile(
    r'vc_tta-panel-body">(.*?)</div>\s*</div>\s*</div>',
    re.I | re.S,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?elmolar\.org)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_LIC_BLOCK = re.compile(
    r"<p><strong>([^<]*licencia[^<]*)</strong></p>.*?href=\"([^\"]+\.pdf)\"",
    re.I | re.S,
)
RE_PREVIEW = re.compile(
    r'href="(https://elmolar\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(url) if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_url(href: str, base: str = WP_BASE) -> str:
    return urllib.parse.urljoin(base, unescape(href))


def _expediente_tipo(code: str) -> str:
    c = code.upper()
    if "NNSS" in c:
        return "normas subsidiarias"
    if "CCOND" in c or "SAU" in c:
        return "condiciones SAU"
    if "MP" in c:
        return "modificación puntual"
    if "CATALOGO" in c:
        return "catálogo"
    return "planeamiento"


def _expediente_year(code: str) -> str | None:
    m = re.search(r"(\d{4})", code)
    if m and 1980 <= int(m.group(1)) <= 2035:
        return f"{m.group(1)}-01-01"
    m = re.search(r"_(\d{4})$", code)
    if m:
        return f"{m.group(1)}-01-01"
    return None


class ElMolarAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (normas subsidiarias + trámites) + tablón eHome sede espublico."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.normas_url = str(self.config.get("normas_url") or NORMAS_URL)
        self.documentacion_url = str(self.config.get("documentacion_url") or DOCUMENTACION_URL)
        self.wp_api = str(self.config.get("wp_api") or WP_API).rstrip("/")

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-molar/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _collect_normas_expedientes(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.normas_url)
        except urllib.error.URLError:
            return []

        titles = [unescape(t.strip()) for t in RE_PANEL_TITLE.findall(html)]
        bodies = RE_PANEL_BODY.findall(html)
        rows: list[dict[str, Any]] = []

        for i, code in enumerate(titles):
            if not re.match(r"R-\d+", code):
                continue
            body = bodies[i] if i < len(bodies) else ""
            pdfs = [_abs_url(m.group(1)) for m in RE_PDF_HREF.finditer(body)]
            pdf_url = pdfs[0] if pdfs else None
            titulo = f"Expediente {code}"
            rows.append(
                {
                    "id": _stable_id("proy", code),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _expediente_year(code) or _fecha_from_url(pdf_url or ""),
                    "tipo": _expediente_tipo(code),
                    "url": self.normas_url,
                    "source": "ayuntamiento",
                    "origen": "normas_subsidiarias",
                    "expte": code,
                    **({"pdf_url": pdf_url, "pdf_count": len(pdfs)} if pdfs else {}),
                }
            )
        return rows

    def _collect_documentacion_licencias(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.documentacion_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_LIC_BLOCK.finditer(html):
            title = unescape(m.group(1).strip())
            pdf_url = _abs_url(m.group(2))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            rows.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": _fecha_from_url(pdf_url),
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": self.documentacion_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "nota": "Formulario de solicitud; no concesión publicada",
                    "origen": "documentacion_tramites",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            if url in seen:
                continue
            seen.add(url)
            local = html[max(0, m.start() - 500) : m.end() + 100]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(titulo) or _fecha_from_url(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for search in ("urbanismo", "reurbaniz", "planeamiento"):
            try:
                posts = self._fetch_json(
                    f"{self.wp_api}/posts?per_page=50&search={urllib.parse.quote(search)}"
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(posts, list):
                continue
            for post in posts:
                title = unescape(str((post.get("title") or {}).get("rendered") or "")).strip()
                link = str(post.get("link") or "").strip()
                if not title or not link:
                    continue
                if not RE_PROYECTO.search(title):
                    continue
                rows.append(
                    {
                        "id": _stable_id("proy", link),
                        "municipio": MUNICIPIO,
                        "titulo": title[:500],
                        "fecha": str(post.get("date") or "")[:10] or None,
                        "tipo": "noticia urbanismo",
                        "url": link,
                        "source": "ayuntamiento",
                        "origen": "wp_posts",
                    }
                )
        return rows

    def _board_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        if RE_SKIP_BOARD.search(titulo):
            return None
        if not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", item["url"]),
            "fecha_concesion": item.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
            **({"pdf_url": item["pdf_url"]} if item.get("pdf_url") else {}),
        }

    def _board_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        if RE_SKIP_BOARD.search(titulo):
            return None
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        if not RE_PROYECTO.search(titulo):
            return None
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": item.get("fecha"),
            "tipo": "edicto" if re.search(r"(?i)edicto|bando", titulo) else "urbanismo",
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
            **({"pdf_url": item["pdf_url"]} if item.get("pdf_url") else {}),
        }

    def _licencia_info_tablon(self) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", self.board_url),
            "fecha_concesion": None,
            "tipo": "tablón licencias urbanísticas",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": "Tablón de anuncios — licencias y urbanismo",
            "url": self.board_url,
            "source": "ayuntamiento",
            "nota": "Concesiones y exposiciones públicas en sede electrónica",
            "origen": "sede_tablon",
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_documentacion_licencias():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_licencia(item))
        add(self._licencia_info_tablon())

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
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

        for rec in self._collect_normas_expedientes():
            add(rec)
        for rec in self._collect_wp_posts():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "normas": sum(1 for r in rows if r.get("origen") == "normas_subsidiarias"),
            "wp_posts": sum(1 for r in rows if r.get("origen") == "wp_posts"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
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
