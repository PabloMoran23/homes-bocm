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

BASE = "https://villalbilla.es"
SEDE_BASE = "https://aytovillalbilla.sedelectronica.es"
BOARD_DEFAULT = f"{SEDE_BASE}/board"
URBANISMO_AREA = f"{BASE}/areas/vivienda-y-urbanismo/"
MUNICIPIO = "Villalbilla"
ID_PREFIX = "villalbilla"

DEFAULT_WP_CATEGORIES = (3316, 4842)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|concesi[oó]n de licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|edicto|reparcel|aprobaci[oó]n|"
    r"modificaci[oó]n|obra|pleno|vivienda|construcci|nave|industrial|"
    r"declaraci[oó]n de utilidad|proyecto|promoci[oó]n|normas subsidiarias|bocm)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[./-](\d{2})[./-]")
RE_PDF_HREF = re.compile(r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"', re.I)
RE_BOARD_ROW = re.compile(r"<tr>\s*(.*?)\s*</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(
    r'class="([^"]+)"[^>]*data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
)
RE_MAINTENANCE = re.compile(r"(?i)en mantenimiento|under maintenance|mantenimiento")


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
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _proyecto_tipo(title: str) -> str:
    t = title.lower()
    if "pleno" in t or "plenario" in t:
        return "acuerdo plenario"
    if "planeamiento" in t or "normas subsidiarias" in t:
        return "planeamiento"
    if "licencia" in t:
        return "licencia publicada"
    if "vivienda" in t or "construcci" in t or "promoci" in t:
        return "promoción inmobiliaria"
    if "utilidad pública" in t or "fotovoltaic" in t or "solar" in t:
        return "proyecto energético"
    if "nave" in t or "industrial" in t:
        return "obra industrial"
    return "urbanismo"


class VillalbillaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress REST (urbanismo) + tablón espublico sede + PDFs área urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_DEFAULT)
        self.urbanismo_area_url = str(self.config.get("urbanismo_area_url") or URBANISMO_AREA)
        raw_cats = self.config.get("wp_category_ids") or list(DEFAULT_WP_CATEGORIES)
        self.wp_category_ids = [int(c) for c in raw_cats]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-villalbilla/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        raw = self._fetch(url)
        return json.loads(raw)

    def _abs_url(self, href: str, base: str = BASE) -> str:
        return urllib.parse.urljoin(base, href)

    def _extract_pdfs(self, html: str) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_url(m.group(1))
            if "favicon" in u.lower():
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def _is_maintenance(self, html: str) -> bool:
        return bool(RE_MAINTENANCE.search(html))

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        for cat_id in self.wp_category_ids:
            page = 1
            while page <= 5:
                url = (
                    f"{BASE}/wp-json/wp/v2/posts"
                    f"?categories={cat_id}&per_page=100&page={page}"
                )
                try:
                    posts = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(posts, list) or not posts:
                    break
                for post in posts:
                    link = str(post.get("link") or "").strip()
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)
                    title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                    content = str((post.get("content") or {}).get("rendered") or "")
                    fecha = _iso_date_wp(str(post.get("date") or ""))
                    pdfs = self._extract_pdfs(content)
                    rows.append(
                        {
                            "titulo": title[:500],
                            "fecha": fecha,
                            "url": link,
                            "pdfs": pdfs,
                            "origen": f"wp_cat_{cat_id}",
                        }
                    )
                if len(posts) < 100:
                    break
                page += 1
        return rows

    def _collect_urbanismo_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_area_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for pdf in self._extract_pdfs(html):
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_url(pdf),
                    "url": self.urbanismo_area_url,
                    "pdf_url": pdf,
                    "origen": "urbanismo_area",
                }
            )
        return rows

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        if self._is_maintenance(html):
            return []
        rows: list[dict[str, Any]] = []
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
        if not tbody_m:
            return rows
        for row_m in RE_BOARD_ROW.finditer(tbody_m.group(1)):
            row_html = row_m.group(1)
            if "emptyRow" in row_html or "display:none" in row_html:
                continue
            cells: dict[str, str] = {}
            doc_url = self.board_url
            for cm in RE_BOARD_CELL.finditer(row_html):
                cls, label, val = cm.group(1), cm.group(2), cm.group(3)
                link_m = re.search(r'href="([^"]+)"', val, re.I)
                if link_m and "class_name" in cls:
                    doc_url = self._abs_url(link_m.group(1), self.sede_base)
                cells[label] = _strip_html(val)
            if not cells:
                continue
            titulo = cells.get("Descripción") or cells.get("Documento") or ""
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": cells.get("Expediente", ""),
                    "procedimiento": cells.get("Procedimiento", ""),
                    "categoria": cells.get("Categoría", ""),
                    "fecha": _parse_fecha_dmy(cells.get("Fecha de Publicación", "")),
                    "url": doc_url,
                    "origen": "sede_board",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board(html)

    def _wp_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia de obras",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdfs"):
            rec["pdf_url"] = row["pdfs"][0]
        return rec

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('procedimiento', '')} {row.get('categoria', '')}"
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
            "expte": row.get("expediente"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_board",
        }

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdfs"):
            rec["pdf_url"] = row["pdfs"][0]
            if len(row["pdfs"]) > 1:
                rec["pdf_urls"] = row["pdfs"][:20]
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('procedimiento', '')} {row.get('categoria', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        tipo = "urbanismo"
        if re.search(r"(?i)planeamiento", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|bocm", blob):
            tipo = "información pública"
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "expte": row.get("expediente"),
            "source": "ayuntamiento",
            "origen": "sede_board",
        }

    def _pdf_row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('pdf_url', '')}"
        if not RE_PROYECTO.search(blob) and "tramite" not in blob.lower():
            return None
        return {
            "id": _stable_id("proy", row["pdf_url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": "trámite urbanismo" if "tramite" in blob.lower() else "documento urbanismo",
            "url": row["url"],
            "pdf_url": row["pdf_url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _pdf_row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["pdf_url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "pdf_url": row["pdf_url"],
            "source": "ayuntamiento",
            "nota": "Formulario informativo; no concesión publicada",
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for wp in self._collect_wp_posts():
            add(self._wp_to_licencia(wp))
        for pdf_row in self._collect_urbanismo_pdfs():
            add(self._pdf_row_to_licencia(pdf_row))
        for board in self._collect_board():
            add(self._board_to_licencia(board))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_posts": len(self._collect_wp_posts()),
            "board_available": len(self._collect_board()) > 0,
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
        after_rows = self._load_jsonl(out_jsonl)
        added = max(0, len(after_rows) - before)
        for rec in after_rows:
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for wp in self._collect_wp_posts():
            add(self._wp_to_proyecto(wp))
        for pdf_row in self._collect_urbanismo_pdfs():
            add(self._pdf_row_to_proyecto(pdf_row))
        for board in self._collect_board():
            add(self._board_to_proyecto(board))

        self._write_jsonl(out_jsonl, rows)
        wp_count = len(self._collect_wp_posts())
        board_count = len(self._collect_board())
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_posts": wp_count,
            "board_rows": board_count,
            "board_available": board_count > 0,
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
