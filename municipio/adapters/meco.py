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

WP_BASE = "https://www.ayto-meco.es"
SEDE_BASE = "https://sede.ayto-meco.es/eAdmin"
TRANSP_BASE = "http://transparencia.ayto-meco.es"

DEFAULT_TRANSPARENCIA_PAGES: list[dict[str, Any]] = [
    {"page_id": 185, "section": "planeamiento", "tipo": "planeamiento"},
    {"page_id": 528, "section": "planeamiento_desarrollo", "tipo": "planeamiento"},
    {"page_id": 530, "section": "instrumentos", "tipo": "convenio"},
]

DEFAULT_LICENCIA_TRAMITES: list[dict[str, Any]] = [
    {"tipo_reg": 57, "nombre": "Cédula urbanística"},
    {"tipo_reg": 58, "nombre": "Segregación urbanística"},
    {"tipo_reg": 59, "nombre": "Obra mayor"},
    {"tipo_reg": 60, "nombre": "Obra menor"},
    {"tipo_reg": 61, "nombre": "Calas o zanjas"},
    {"tipo_reg": 62, "nombre": "Declaración responsable obras"},
    {"tipo_reg": 63, "nombre": "Declaración responsable 1ª ocupación"},
]

RE_READING_BOX = re.compile(
    r'<div class="reading-box"[^>]*>(.*?)</div>\s*</div>',
    re.I | re.S,
)
RE_ABRIR_CODE = re.compile(r"abrir\('([^']+)'\)")
RE_ABRIR_TITLE = re.compile(
    r"abrir\('([^']+)'\)[^>]*>([^<]+)</a>",
    re.I,
)
RE_H2_TITLE = re.compile(
    r"<h2[^>]*>(?:<[^>]+>)*\s*([^<]{3,500})",
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|cedula|c[eé]dula)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|alma)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|segregaci|modificaci[oó]n|"
    r"aprobaci[oó]n|normas urban|instrumento|sectoriz|zonificaci)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_FECHA_ES = re.compile(
    r"(\d{1,2})\s+de\s+"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
    r"\s+de\s+(\d{4})",
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
MESES = {
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


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"meco-{prefix}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_DMY_DASH.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_ES.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1))).strftime(
                "%Y-%m-%d"
            )
        except (ValueError, KeyError):
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _doc_url(sede_base: str, code: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(code, safe='')}&tipo=doc"
    )


def _clean_title(raw: str) -> str:
    t = unescape(re.sub(r"\s+", " ", raw or "")).strip()
    if t.lower().startswith("ver documento"):
        t = t[len("ver documento") :].strip()
    return t[:500]


def _proyecto_tipo(title: str, default: str = "urbanismo") -> str:
    n = title.lower()
    if "convenio" in n or "reparcel" in n:
        return "convenio urbanístico"
    if "plan parcial" in n or "plan especial" in n or "pgou" in n or "plan alma" in n:
        return "planeamiento"
    if "modificaci" in n:
        return "modificación PGOU"
    if "normas" in n or "instrucci" in n:
        return "normativa urbanística"
    if "informaci" in n:
        return "información pública"
    return default


class MecoAyuntamientoAdapter(AyuntamientoAdapter):
    """eAdmin sede (tablón + trámites) + transparencia WordPress (PGOU, planes, convenios)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.transp_pages = list(self.config.get("transparencia_pages") or DEFAULT_TRANSPARENCIA_PAGES)
        self.licencia_tramites = list(
            self.config.get("licencia_tramites") or DEFAULT_LICENCIA_TRAMITES
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("transparencia_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_transp_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-meco/1.0")},
        )
        ctx = self._ssl_ctx if use_transp_ssl or url.startswith("http://transparencia.") else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "iso-8859-1"
            return raw.decode(charset, errors="replace")

    def _fetch_transparencia_page(self, page_id: int) -> str:
        url = f"{self.transp_base}/?page_id={page_id}"
        return self._fetch(url, use_transp_ssl=True)

    def _extract_transparencia_docs(self, html: str) -> list[tuple[str, str]]:
        by_code: dict[str, str] = {}

        for box in RE_READING_BOX.findall(html):
            codes = RE_ABRIR_CODE.findall(box)
            if not codes:
                continue
            code = codes[0]
            h2 = RE_H2_TITLE.search(box)
            title = _clean_title(h2.group(1)) if h2 else ""
            if not title:
                continue
            by_code[code] = title

        for code, anchor_title in RE_ABRIR_TITLE.findall(html):
            title = _clean_title(anchor_title)
            if title and title.lower() != "ver documento" and code not in by_code:
                by_code[code] = title

        return [(title, code) for code, title in by_code.items()]

    def _collect_transparencia_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in self.transp_pages:
            page_id = int(page["page_id"])
            section = str(page.get("section") or page_id)
            default_tipo = str(page.get("tipo") or "urbanismo")
            page_url = f"{self.transp_base}/?page_id={page_id}"
            try:
                html = self._fetch_transparencia_page(page_id)
            except urllib.error.URLError:
                continue
            for title, code in self._extract_transparencia_docs(html):
                pdf_url = _doc_url(self.sede_base, code)
                rows.append(
                    {
                        "id": _stable_id("proy", code),
                        "municipio": "Meco",
                        "titulo": title,
                        "fecha": _parse_fecha_dmy(title),
                        "tipo": _proyecto_tipo(title, default_tipo),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "source": "ayuntamiento",
                        "origen": section,
                        "doc_code": code,
                    }
                )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        index_url = f"{self.sede_base}/Tablon.do?action=inicioTablon"
        try:
            html = self._fetch(index_url)
        except urllib.error.URLError:
            return []

        ids = re.findall(r"verAnuncio&id=([A-F0-9]+)", html, re.I)
        titles = [
            _clean_title(unescape(re.sub(r"<[^>]+>", " ", cell)))
            for cell in re.findall(r'<td[^>]*width="40%"[^>]*>(.*?)</td>', html, re.I | re.S)
        ]
        date_spans = re.findall(
            r"Periodo:\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})",
            html,
            re.I,
        )
        fechas_ini = [d[0] for d in date_spans]

        rows: list[dict[str, Any]] = []
        for i, aid in enumerate(ids):
            title = titles[i] if i < len(titles) else ""
            if not title:
                continue
            fecha = _parse_fecha_dmy(fechas_ini[i]) if i < len(fechas_ini) else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={aid}"
            rows.append(
                {
                    "anuncio_id": aid,
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": detail_url,
                }
            )
        return rows

    def _tablon_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        title = item["titulo"]
        if not RE_PROYECTO.search(title):
            return None
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(
            re.sub(r"(?i)licencia", "", title)
        ):
            return None
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": "Meco",
            "titulo": title,
            "fecha": item.get("fecha"),
            "tipo": "edicto tablón",
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
            "anuncio_id": item.get("anuncio_id"),
        }

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tram in self.licencia_tramites:
            tipo_reg = int(tram["tipo_reg"])
            nombre = str(tram.get("nombre") or f"Trámite {tipo_reg}")
            url = f"{self.sede_base}/Registrar.do?action=infoTramite&tipoReg={tipo_reg}"
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": nombre[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": nombre[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámite; no concesión publicada en tablón",
                    "tipo_reg": tipo_reg,
                }
            )
        return rows

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
        rows = self._collect_licencia_tramites()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites_info"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in existing:
                added += 1
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

        for rec in self._collect_transparencia_proyectos():
            add(rec)
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        transp = sum(1 for r in rows if r.get("origen") != "tablon")
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia_docs": transp,
            "tablon_items": len(rows) - transp,
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
