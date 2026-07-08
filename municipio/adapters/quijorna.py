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

WP_BASE = "https://aytoquijorna.org"
SEDE_BASE = "https://aytoquijorna.sedelectronica.es"
MUNICIPIO = "Quijorna"
ID_PREFIX = "quijorna"

URBANISMO_URL = f"{WP_BASE}/concejalias/urbanismo/"
TRAMITES_URL = f"{WP_BASE}/concejalias/urbanismo/tramites-y-gestiones-de-urbanismo/"
NORMATIVA_URL = f"{WP_BASE}/concejalias/urbanismo/normativa-urbanistica/"
NORMATIVA_DOSSIER = f"{SEDE_BASE}/transparency/c3bde2cb-3329-460a-9b0b-d02e55dc25f5/"
BOARD_URL = f"{SEDE_BASE}/board/"
BOARD_URBANISMO = f"{SEDE_BASE}/board/974e6d5e-f59b-11de-b600-00237da12c6a/"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    TRAMITES_URL,
    NORMATIVA_URL,
    f"{WP_BASE}/concejalias/urbanismo/licencias-urbanisticas/",
    f"{WP_BASE}/concejalias/urbanismo/zonas-de-ordenanza/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"tramitaci[oó]n.*obra|primera ocupaci[oó]n|segregaci[oó]n|demolici[oó]n|"
    r"replanteo|piscina|fotovoltaic)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva)|parcela|suelo|ordenanza|normas subsidiarias|"
    r"nn\.?ss|inspecci[oó]n urban|regimen del suelo|normas particulares)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://aytoquijorna\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="((?:https://aytoquijorna\.org)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_EXT_PDF = re.compile(
    r'href="(https?://[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_DOSSIER_LINK = re.compile(
    r'href="(https://aytoquijorna\.sedelectronica\.es/preview-document/[a-f0-9-]+)"'
    r'[^>]*>([^<]+)</a>',
    re.I,
)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{prefix}-{h}"


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
    m = re.search(r"BOCM[- ]?(\d{4})(\d{2})(\d{2})", text or "", re.I)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _doc_tipo(name: str) -> str:
    n = name.lower()
    if "normas subsidiarias" in n or "nnss" in n or "nn.ss" in n:
        return "normas subsidiarias"
    if "ordenanza" in n or "regimen del suelo" in n:
        return "ordenanza urbanística"
    if "convenio" in n:
        return "convenio urbanístico"
    if re.search(r"declaraci[oó]n responsable", n):
        return "declaración responsable"
    if "licencia" in n or "obra" in n:
        return "guía tramitación licencia"
    if "bocm" in n:
        return "publicación BOCM"
    return "documento urbanismo"


class QuijornaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress citygov + sede espublico (eHome) + transparencia normativa."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.board_urbanismo_url = str(
            self.config.get("board_urbanismo_url") or BOARD_URBANISMO
        )
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.normativa_dossier = str(
            self.config.get("normativa_dossier") or NORMATIVA_DOSSIER
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-quijorna/1.0")},
        )
        ctx = self._ssl_ctx if url.startswith("https://aytoquijorna.sedelectronica") else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{WP_BASE}/", href)

    def _collect_board(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for board_url in (self.board_url, self.board_urbanismo_url):
            try:
                html = self._fetch(board_url)
            except urllib.error.URLError:
                continue
            for m in RE_BOARD_ROW.finditer(html):
                row_html = m.group(1)
                if "preview-document" not in row_html:
                    continue
                cells = [_strip_html(c) for c in RE_BOARD_CELL.findall(row_html)]
                cells = [c for c in cells if c]
                if len(cells) < 4 or cells[0] in ("Documento", "Expediente"):
                    continue

                documento = cells[0] if len(cells) > 0 else ""
                expediente = cells[1] if len(cells) > 1 else ""
                procedimiento = cells[2] if len(cells) > 2 else ""
                categoria = cells[3] if len(cells) > 3 else ""
                descripcion = cells[4] if len(cells) > 4 else ""
                fecha_raw = cells[5] if len(cells) > 5 else ""

                preview_m = RE_PREVIEW_LINK.search(row_html)
                url = preview_m.group(1) if preview_m else board_url
                titulo = descripcion or documento
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
                        "blob": f"{documento} {expediente} {procedimiento} {categoria} {descripcion}",
                        "origen": "tablon_sede",
                    }
                )
        return rows

    def _collect_normativa_dossier(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.normativa_dossier)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_DOSSIER_LINK.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo) or "2021-04-30",
                    "url": url,
                    "pdf_url": url,
                    "tipo": _doc_tipo(titulo),
                    "origen": "transparencia_normativa",
                }
            )
        return rows

    def _collect_wp_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for pat in (RE_WP_PDF, RE_EXT_PDF):
                for m in pat.finditer(html):
                    raw = m.group(1)
                    pdf = self._abs_wp(raw) if raw.startswith("/") else raw
                    if pdf in seen:
                        continue
                    if "bocm.es" not in pdf and "aytoquijorna.org" not in pdf:
                        continue
                    seen.add(pdf)
                    name = unescape(urllib.parse.unquote(Path(pdf).name))
                    rows.append(
                        {
                            "titulo": name[:500],
                            "fecha": _fecha_from_blob(name) or _fecha_from_blob(pdf),
                            "url": page_url,
                            "pdf_url": pdf,
                            "tipo": _doc_tipo(name),
                            "origen": "urbanismo_web",
                        }
                    )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "trámite licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites y gestiones de urbanismo (guías PDF)",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Guías de tramitación; concesiones publicadas en tablón cuando proceda",
                "origen": "urbanismo_web",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — solicitud de licencia urbanística",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Presentación electrónica de solicitudes (URB-001A)",
                "origen": "sede_tramites",
            },
            {
                "id": _stable_id("lic", self.board_urbanismo_url),
                "fecha_concesion": None,
                "tipo": "tablón urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — categoría Urbanismo",
                "url": self.board_urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Categoría dedicada; actualmente sin anuncios vigentes",
                "origen": "tablon_sede",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "expte": row.get("expediente"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        tipo = "urbanismo"
        if re.search(r"(?i)ordenanza|normas subsidiarias", blob):
            tipo = "normas subsidiarias"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|publicacion bocm", blob):
            tipo = "información pública"
        elif re.search(r"(?i)plan (?:parcial|especial)|planeam", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)convenio", blob):
            tipo = "convenio"
        return {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente"),
            "origen": row.get("origen"),
        }

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or "documento urbanismo",
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _doc_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row.get("titulo") or ""
        if not RE_LICENCIA.search(titulo):
            return None
        key = row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "guía tramitación licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "nota": "Modelo o guía de trámite; no concesión publicada",
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
        for doc in self._collect_wp_pdfs():
            rec = self._doc_to_licencia(doc)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "urbanismo_tablon_transparencia"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for doc in self._collect_wp_pdfs():
            rec = self._doc_to_licencia(doc)
            if rec:
                existing[rec["id"]] = rec
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
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

        for doc in self._collect_normativa_dossier() + self._collect_wp_pdfs():
            add(self._doc_to_proyecto(doc))
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        trans = sum(1 for r in rows if r.get("origen") == "transparencia_normativa")
        web = sum(1 for r in rows if r.get("origen") == "urbanismo_web")
        tablon = sum(1 for r in rows if r.get("origen") == "tablon_sede")
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia_docs": trans,
            "web_pdfs": web,
            "tablon_items": tablon,
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
