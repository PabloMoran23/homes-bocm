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

WP_BASE = "https://aytoleon.es"
SEDE_BASE = "https://sede.aytoleon.es/eAdmin"
MUNICIPIO = "León"
ID_PREFIX = "leon"

URBANISMO_URL = f"{WP_BASE}/es/tu-ayuntamiento/normativas/Paginas/urbanismo.aspx"
TABLON_ALL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"

DEFAULT_SEARCH_TERMS = (
    "PLANEAMIENTO",
    "PGOU",
    "SECTOR",
    "ESTUDIO DETALLE",
    "MODIFICACION PGOU",
    "INFORMACION PUBLICA",
    "EXPROPIACION",
    "URBANIZACION",
    "CONVENIO URBAN",
    "LICENCIA",
    "LICENCIA AMBIENTAL",
    "LICENCIA APERTURA",
)

DEFAULT_LICENCIA_TRAMITES: list[dict[str, Any]] = [
    {"tipo_reg": 108, "nombre": "SOLICITUD de Licencia de Obras"},
    {"tipo_reg": 192, "nombre": "SOLICITUD de Licencia Urbanística"},
    {"tipo_reg": 39, "nombre": "Declaración responsable para la EJECUCIÓN de OBRA"},
    {"tipo_reg": 188, "nombre": "Declaración responsable de PRIMERA OCUPACIÓN"},
    {"tipo_reg": 94, "nombre": "SOLICITUD de Licencia Ambiental"},
    {"tipo_reg": 107, "nombre": "Comunicación de Cambio de Titularidad de LICENCIA DE APERTURA"},
    {"tipo_reg": 109, "nombre": "Comunicación de Cambio de Titularidad de LICENCIA AMBIENTAL"},
    {"tipo_reg": 100, "nombre": "Comunicación de INICIO o PUESTA EN MARCHA de Actividad"},
    {"tipo_reg": 172, "nombre": "SOLICITUD de Cédula Urbanística"},
    {"tipo_reg": 106, "nombre": "Autorización administrativa de Agregación, Agrupación, Segregación o División"},
    {"tipo_reg": 112, "nombre": "SOLICITUD de Inscripción en el Registro de ITE"},
    {"tipo_reg": 70, "nombre": "Procesos Exposición Pública (alegaciones)"},
]

RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td[^>]*>.*?verAnuncio&id=([A-F0-9]+).*?"
    r"</td>\s*<td[^>]*>\s*(.*?)\s*<br>.*?"
    r"Periodo:</span>\s*([^<]+)</td>",
    re.I | re.S,
)
RE_DOC_TOKEN = re.compile(r"abrir(?:Original)?\('([^']+)'\)")
RE_EXPTE = re.compile(r"(?i)(?:EXP(?:EDIENTE)?\.?|EXPDTE\.?)\s*[:.]?\s*([0-9]+[/\-_][0-9]{2,4})")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|ambiental|apertura)|"
    r"declaraci[oó]n responsable.*obra|comunicaci[oó]n previa|primera ocupaci[oó]n|"
    r"cedula|c[eé]dula urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|expropi|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"modificaci[oó]n.*pgou|estudio (?:de )?detalle|proyecto de (?:urbaniz|actuaci)|"
    r"sector (?:nc|uld|pr|aa|sunc)|gesti[oó]n urban|normas urban|pepch|peca)",
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
RE_URBAN_DOC_PATH = re.compile(
    r"(?i)(PGOU|Modificaciones PGOU|Convenios Urban|Documentos Planeamiento|Documentos Gestin Urban)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"\s+", " ", text or "")).strip()
    if t.lower().startswith("ver documento"):
        t = t[len("ver documento") :].strip()
    return t[:500]


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


def _parse_expte(text: str) -> str | None:
    m = RE_EXPTE.search(text)
    return m.group(1).strip() if m else None


def _pdf_url(token: str) -> str:
    return (
        f"{SEDE_BASE}/ValidarDocumento.do?id_Documento="
        f"{urllib.parse.quote(token, safe='')}&tipo=doc&mode=ori"
    )


def _proyecto_tipo(title: str, section: str = "") -> str:
    n = f"{title} {section}".lower()
    if "convenio" in n or "reparcel" in n or "peca" in n:
        return "convenio urbanístico"
    if "plan parcial" in n or "plan especial" in n or "pgou" in n:
        return "planeamiento"
    if "estudio de detalle" in n or "estudio detalle" in n:
        return "estudio de detalle"
    if "urbaniz" in n:
        return "proyecto de urbanización"
    if "actuaci" in n:
        return "proyecto de actuación"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if re.search(r"informaci[oó]n p[uú]blica", n):
        return "información pública"
    if "expropi" in n:
        return "expropiación"
    if "normas" in n or "estatutos" in n:
        return "normativa urbanística"
    return "urbanismo"


class LeonAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede eAdmin add4u (tablón) + portal SharePoint urbanismo (PGOU, convenios, planeamiento)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.search_terms = list(self.config.get("search_terms") or DEFAULT_SEARCH_TERMS)
        self.licencia_tramites = list(
            self.config.get("licencia_tramites") or DEFAULT_LICENCIA_TRAMITES
        )

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-leon/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")

    def _parse_tablon_html(self, html: str) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, period_raw = m.groups()
            title = _clean_title(title_raw)
            if not title:
                continue
            row_html = m.group(0)
            doc_m = RE_DOC_TOKEN.search(row_html)
            doc_token = doc_m.group(1) if doc_m else None
            period_m = RE_PERIOD.search(period_raw or "")
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec: dict[str, Any] = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha_ini": fecha_ini,
                "url": detail_url,
                "doc_token": doc_token,
                "expte": _parse_expte(title),
            }
            if doc_token:
                rec["pdf_url"] = _pdf_url(doc_token)
            by_id[ann_id] = rec
        return by_id

    def _search_tablon(self, term: str) -> dict[str, dict[str, Any]]:
        body = urllib.parse.urlencode({"referenciaBusqueda": term}).encode("utf-8")
        try:
            html = self._fetch(TABLON_ALL, data=body)
        except urllib.error.URLError:
            return {}
        return self._parse_tablon_html(html)

    def _collect_tablon(self) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        try:
            html = self._fetch(TABLON_ALL)
            by_id.update(self._parse_tablon_html(html))
        except urllib.error.URLError:
            pass
        for term in self.search_terms:
            for ann_id, rec in self._search_tablon(term).items():
                by_id.setdefault(ann_id, rec)
        return by_id

    def _collect_urbanismo_docs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]*)', html, re.I):
            href, text = m.group(1), _clean_title(m.group(2))
            if not any(ext in href.lower() for ext in (".pdf", ".zip", ".7z")):
                continue
            if not RE_URBAN_DOC_PATH.search(href):
                continue
            url = href if href.startswith("http") else f"{self.wp_base}{href}"
            if url in seen:
                continue
            seen.add(url)
            title = text or unescape(urllib.parse.unquote(href.split("/")[-1]))
            section_m = RE_URBAN_DOC_PATH.search(href)
            section = section_m.group(1) if section_m else "urbanismo"
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": _parse_fecha_dmy(title),
                    "tipo": _proyecto_tipo(title, section),
                    "url": self.urbanismo_url,
                    "pdf_url": url,
                    "source": "ayuntamiento",
                    "origen": section.lower().replace(" ", "_"),
                    "expte": _parse_expte(title),
                }
            )
        return rows

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
                    "origen": "catalogo_tramites",
                    "tipo_reg": tipo_reg,
                }
            )
        return rows

    def _tablon_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if not RE_LICENCIA.search(title):
            return None
        tipo_m = re.search(r"(?i)(licencia[^,]{0,80})", title)
        out: dict[str, Any] = {
            "id": _stable_id("lic", rec.get("expte") or rec["ann_id"]),
            "fecha_concesion": rec.get("fecha_ini"),
            "tipo": (tipo_m.group(1).strip()[:120] if tipo_m else "licencia"),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "expte": rec.get("expte"),
            "url": rec["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        return out

    def _tablon_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        if re.search(r"(?i)convenio", title) and not re.search(
            r"(?i)urban|pgou|sector|parcela|reparcel|peca|urbaniz|inmueble|enajen",
            title,
        ):
            return None
        out: dict[str, Any] = {
            "id": _stable_id("proy", rec.get("expte") or rec["ann_id"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": rec.get("fecha_ini"),
            "tipo": _proyecto_tipo(title, "tablon"),
            "url": rec["url"],
            "source": "ayuntamiento",
            "expte": rec.get("expte"),
            "origen": "tablon",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        return out

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
        for rec in self._collect_tablon().values():
            lic = self._tablon_to_licencia(rec)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_licencias": sum(1 for r in rows if r.get("origen") == "tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_tablon().values():
            lic = self._tablon_to_licencia(rec)
            if lic:
                existing[lic["id"]] = lic
        for rec in self._collect_licencia_tramites():
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

        for rec in self._collect_urbanismo_docs():
            add(rec)
        for rec in self._collect_tablon().values():
            add(self._tablon_to_proyecto(rec))

        self._write_jsonl(out_jsonl, rows)
        portal = sum(1 for r in rows if r.get("origen") != "tablon")
        return {
            "rows": len(rows),
            "status": "ok",
            "portal_urbanismo": portal,
            "tablon_items": len(rows) - portal,
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
