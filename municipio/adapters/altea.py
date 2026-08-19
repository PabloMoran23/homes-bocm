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

BASE = "https://altea.es"
API_BASE = "https://api.digitalvalue.es/contents/altea/collections"
SEDE_BASE = "https://altea.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
MUNICIPIO = "Altea"
ID_PREFIX = "altea"

TRAMITES_ARTICLE_ID = "68133cb60c2bd4518f7f5af8"

HUB_SLUGS = {
    "documentos-de-planeamiento",
    "proyectos-en-desarrollo",
    "informacion-de-interes",
    "tramites",
    "urbanisme",
    "ordenanzas",
    "legislacion-urbanistica-valenciana",
    "altea-urban-project",
    "informacion-playas",
    "informacion-general",
}

RE_LICENCIA = re.compile(
    r"(?i)(licencia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|primera ocupaci[oó]n|parcelaci[oó]n|segregaci[oó]n|"
    r"certificado.*urban|urbanizaci[oó]n|demolici[oó]n|edificaci[oó]n|gr[uú]a)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pge|pai|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|sector|ordenanza|vivienda.*tur|urbanitz|sanejament|"
    r"rehabilitaci[oó]n.*costera|lsmt|dotacional)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvencion|padrones|bop\b|boe\b|dogv\b|pleno|jgl|empleo|bolsa de trabajo)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://altea\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _localized(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("es", "und", "va", "ca"):
            if value.get(key):
                return str(value[key])
        for v in value.values():
            if v:
                return str(v)
        return ""
    return str(value or "")


def _slug(item: dict[str, Any]) -> str:
    data = item.get("data") or {}
    slug = data.get("slug") or item.get("slug") or ""
    return _localized(slug).strip("/")


def _title(item: dict[str, Any]) -> str:
    return _strip_html(_localized(item.get("title")))


def _article_url(item: dict[str, Any]) -> str:
    data = item.get("data") or {}
    original = data.get("original")
    if original:
        return str(original).rstrip("/")
    slug = _slug(item)
    if slug:
        return f"{BASE}/articulos/{slug}"
    return f"{BASE}/articulos/{item.get('_id', '')}"


def _article_fecha(item: dict[str, Any]) -> str | None:
    for key in ("date", "modified", "updated", "created"):
        raw = item.get(key)
        if not raw:
            continue
        text = str(raw)
        if "T" in text:
            return text.split("T", 1)[0]
        parsed = _parse_fecha_dmy(text)
        if parsed:
            return parsed
    return _fecha_from_blob(_title(item))


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "sector" in b:
        return "plan parcial"
    if "plan general" in b or "pge" in b or "pgou" in b:
        return "PGOU/PGE"
    if "modificaci" in b and ("pgou" in b or "ordenanza" in b):
        return "modificación PGOU"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "reparcel" in b:
        return "reparcelación"
    if "vivienda" in b and "tur" in b:
        return "ordenanza VUT"
    if "urbanitz" in b or "urbanizaci" in b:
        return "proyecto urbanización"
    if "pai" in b:
        return "programa actuación integrada"
    return "planeamiento"


class AlteaAyuntamientoAdapter(AyuntamientoAdapter):
    """Digital Value API (altea.es) + sede electrónica espublico gestiona."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.api_base = str(self.config.get("api_base") or API_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.tramites_article_id = str(
            self.config.get("tramites_article_id") or TRAMITES_ARTICLE_ID
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-altea/1.0")},
        )
        ctx = self._ssl_ctx if url.startswith("https://") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _fetch_all_articulos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        limit = 200
        while True:
            url = f"{self.api_base}/articulos?limit={limit}&offset={offset}"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            batch = data.get("items", []) if isinstance(data, dict) else data
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return rows

    def _fetch_article(self, article_id: str) -> dict[str, Any] | None:
        try:
            data = self._fetch_json(f"{self.api_base}/articulos/{article_id}")
        except (urllib.error.URLError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _is_proyecto_article(self, item: dict[str, Any]) -> bool:
        slug = _slug(item).lower()
        if slug in HUB_SLUGS:
            return False
        title = _title(item)
        cats = [str(c).lower() for c in (item.get("categories") or [])]
        blob = f"{title} {slug} {' '.join(cats)}"
        if RE_PROYECTO.search(blob):
            return True
        if item.get("filesGroup") and (
            "urbanismo" in cats
            or slug.startswith("sector-")
            or "informacio-publica" in slug
            or "informacion-publica" in slug
        ):
            return True
        return False

    def _article_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        title = _title(item)
        url = _article_url(item)
        blob = title
        files: list[str] = []
        for group in item.get("filesGroup") or []:
            for f in group.get("files") or []:
                ft = str(f.get("title") or "")
                if ft:
                    files.append(ft)
                    blob = f"{blob} {ft}"
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": _article_fecha(item),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "slug": _slug(item),
            "documentos": files[:20] if files else None,
        }

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._fetch_all_articulos():
            if not self._is_proyecto_article(item):
                continue
            rec = self._article_to_proyecto(item)
            if rec["id"] in seen:
                continue
            seen.add(rec["id"])
            rows.append(rec)
        return rows

    def _collect_tramites_licencias(self) -> list[dict[str, Any]]:
        article = self._fetch_article(self.tramites_article_id)
        if not article:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for group in article.get("tablesGroup") or []:
            for table in group.get("tables") or []:
                for row in table.get("data") or []:
                    if not row:
                        continue
                    title = _strip_html(str(row[0]))
                    url = str(row[2] if len(row) > 2 else row[-1]).strip()
                    if not title or not RE_LICENCIA.search(title):
                        continue
                    if not url.startswith("http"):
                        url = f"{self.sede_base}/catalog"
                    rec_id = _stable_id("lic", url if url.startswith("http") else title)
                    if rec_id in seen:
                        continue
                    seen.add(rec_id)
                    rows.append(
                        {
                            "id": rec_id,
                            "fecha_concesion": None,
                            "tipo": "trámite licencia",
                            "distrito": None,
                            "lat": None,
                            "lon": None,
                            "titulo": title,
                            "url": url,
                            "source": "ayuntamiento",
                            "nota": "Ficha procedimental sede; no hay registro público de concesiones",
                            "origen": "urbanismo_tramites",
                        }
                    )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento",):
                continue

            blob = f"{documento} {expediente} {procedimiento} {categoria} {descripcion}"
            if RE_BOARD_NON_URBAN.search(blob):
                continue
            if not (RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob)):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": blob,
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                clean = {k: v for k, v in row.items() if v is not None}
                f.write(json.dumps(clean, ensure_ascii=False) + "\n")

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
        rows = self._collect_tramites_licencias()
        seen = {r["id"] for r in rows}
        for item in self._collect_board():
            blob = item.get("blob") or item["titulo"]
            if not RE_LICENCIA.search(blob):
                continue
            rec = {
                "id": _stable_id("lic", item["url"]),
                "fecha_concesion": item.get("fecha"),
                "tipo": "edicto tablón",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": item["titulo"],
                "url": item["url"],
                "source": "ayuntamiento",
                "nota": "Edicto sede electrónica Altea",
                "origen": "sede_tablon",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "api_tramites_sede_tablon"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
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
        rows = self._collect_proyectos()
        board_rows = self._collect_board()
        seen = {r["id"] for r in rows}
        for item in board_rows:
            if not RE_PROYECTO.search(item.get("blob") or item["titulo"]):
                continue
            rec = {
                "id": _stable_id("proy", item["url"]),
                "municipio": MUNICIPIO,
                "titulo": item["titulo"],
                "fecha": item.get("fecha"),
                "tipo": _proyecto_tipo(item.get("blob") or item["titulo"]),
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "digitalvalue_api_sede"}

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
