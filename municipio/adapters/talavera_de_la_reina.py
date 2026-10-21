from __future__ import annotations

import codecs
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

WP_URB = "https://urbanismo.talavera.es"
WEB_BASE = "https://talavera.es"
SEDE_BASE = "https://sede.talavera.org"
MUNICIPIO = "Talavera de la Reina"
ID_PREFIX = "talavera-de-la-reina"
ENTIDAD = "45165"

TABLON_POST_URL = f"{SEDE_BASE}/web/tablonEdictos.do?entidad={ENTIDAD}&idioma=1"
CATALOGO_LICENCIAS = (
    f"{SEDE_BASE}/web/catalogoAsuntos.do?opcion=5&palabrasBusqueda=licencia+obra"
    f"&lineasPagina=100&pagina=1&entidad={ENTIDAD}&idioma=1"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_URB}/tramites-en-informacion-publica/planeamiento-y-gestion/",
    f"{WP_URB}/planeamiento/",
    f"{WP_URB}/ordenanzas-y-reglamentos/",
    f"{WP_URB}/planes-y-programas-en-ejecucion/",
    f"{WP_URB}/visor/",
]

IMPRESOS_LICENCIAS = f"{WP_URB}/impresos-documentacion-y-solicitudes/"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|parcelaci[oó]n|apertura de (?:actividad|local))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pom|pgou|perim|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|exp\.|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|memoria|planos|edicto|aprobaci[oó]n (?:inicial|definitiva)|"
    r"sector|unidad urbana|eatim|palomarejos|gamonal|suspensi[oó]n.*licencia)",
)
RE_TABLON_NOISE = re.compile(
    r"(?i)(proceso selectivo|empleo p[uú]blico|subvenci[oó]n|padrones|padr[oó]n ite|"
    r"inspecci[oó]n t[eé]cnica de edificios|festejos|polic[ií]a local.*vmp|"
    r"dominio p[uú]blico|escuela infantil|veh[ií]culos de movilidad)",
)
RE_DOWNLOAD = re.compile(
    r'href="((?:https://(?:urbanismo\.)?talavera\.es)?/download/[^"]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPEDIENTE = re.compile(
    r"(?i)(?:exp(?:ediente)?\.?|exp-)\s*([0-9]{3,6}[/\-][0-9]{2,4}[/\-]?(?:urb|URB)?)",
)
RE_LISTA_JS = re.compile(r"listaJS\[j\]\s*=\s*\[(.*?)\];", re.S)
RE_QUOTED = re.compile(r"'((?:\\'|[^'])*)'")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _decode_js_string(s: str) -> str:
    s = s.replace("\\/", "/")
    try:
        s = codecs.decode(s, "unicode_escape")
    except (UnicodeDecodeError, ValueError):
        pass
    return unescape(s)


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "perim" in b or "reforma interior" in b:
        return "PERIM"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "convenio urban" in b:
        return "convenio urbanístico"
    if "pom" in b or "plan de ordenaci" in b or "pgou" in b:
        return "planeamiento general"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "modificaci" in b and "puntual" in b:
        return "modificación puntual"
    if "suspensi" in b and "licencia" in b:
        return "suspensión licencias"
    if "plan parcial" in b or "sector" in b:
        return "plan parcial"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    return "urbanismo"


class TalaveraDeLaReinaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress urbanismo (WP File Download) + sede SIAL tablón edictos + formularios licencias."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_URB)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_urb = str(self.config.get("wp_urb") or WP_URB).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.impresos_url = str(self.config.get("impresos_url") or IMPRESOS_LICENCIAS)
        self.tablon_post_url = str(self.config.get("tablon_post_url") or TABLON_POST_URL)
        self.catalogo_licencias = str(self.config.get("catalogo_licencias") or CATALOGO_LICENCIAS)

    def _fetch(self, url: str, *, post_data: bytes | None = None, latin1: bool = False) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")}
        req = urllib.request.Request(url, data=post_data, headers=headers, method="POST" if post_data else "GET")
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
        enc = "iso-8859-15" if latin1 or "sede.talavera" in url else "utf-8"
        return raw.decode(enc, errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(f"{(base or self.wp_urb)}/", unescape(href).replace("&amp;", "&"))

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

    def _extract_wp_downloads(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_DOWNLOAD.finditer(html):
            pdf = self._abs_url(m.group(1), page_url)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf.split("?")[0]).name))
            titulo = name.replace("-", " ").replace("_", " ")
            rows.append(
                {
                    "pdf_url": pdf,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(f"{name} {pdf}"),
                    "page_url": page_url,
                }
            )
        return rows

    def _collect_wp_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for rec in self._extract_wp_downloads(html, page_url):
                blob = f"{rec['titulo']} {rec['pdf_url']}"
                if not RE_PROYECTO.search(blob) and "planeamiento" not in page_url:
                    if "/visor/" in page_url:
                        continue
                pdf_id = _stable_id("proy", rec["pdf_url"])
                if pdf_id in seen:
                    continue
                seen.add(pdf_id)
                rows.append(
                    {
                        "id": pdf_id,
                        "municipio": MUNICIPIO,
                        "titulo": rec["titulo"],
                        "fecha": rec["fecha"],
                        "tipo": _proyecto_tipo(blob),
                        "url": rec["pdf_url"],
                        "pdf_url": rec["pdf_url"],
                        "source": "ayuntamiento",
                        "origen": "wpfd",
                        "seed_page": page_url,
                    }
                )
        return rows

    def _parse_tablon_entries(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_post_url, post_data=b"opcion=5&procedencia=&tip_pub=", latin1=True)
        except urllib.error.URLError:
            return []
        items: list[dict[str, Any]] = []
        for block in RE_LISTA_JS.findall(html):
            parts = [_decode_js_string(p) for p in RE_QUOTED.findall(block)]
            if len(parts) < 10:
                continue
            eid, codigo, titulo, desc, fecha_pub, dept = (
                parts[0],
                parts[1],
                parts[4],
                _strip_html(parts[5]),
                parts[6],
                parts[9],
            )
            bop_url = parts[12] if len(parts) > 12 else ""
            items.append(
                {
                    "eid": eid,
                    "codigo": codigo,
                    "titulo": titulo[:500],
                    "descripcion": desc[:1000],
                    "fecha": _parse_fecha_dmy(fecha_pub),
                    "dept": dept,
                    "bop_url": bop_url,
                    "blob": f"{titulo} {desc} {dept} {codigo}",
                    "url": f"{self.sede_base}/web/tablonEdictos.do?opcion=0&entidad={ENTIDAD}&idioma=1",
                }
            )
        return items

    def _tablon_is_urban(self, item: dict[str, Any]) -> bool:
        blob = item.get("blob") or ""
        dept = (item.get("dept") or "").lower()
        if RE_TABLON_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return False
        if "obras y urbanismo" in dept:
            return True
        return bool(RE_PROYECTO.search(blob))

    def _tablon_is_licencia(self, item: dict[str, Any]) -> bool:
        return bool(RE_LICENCIA.search(item.get("blob") or ""))

    def _tablon_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(item):
            return None
        url = item.get("bop_url") or item["url"]
        if url.startswith("https://"):
            doc_url = url.split("|")[0]
        else:
            doc_url = item["url"]
        titulo = item["titulo"] or item.get("codigo") or "Edicto tablón"
        exp_m = RE_EXPEDIENTE.search(item.get("blob") or "")
        return {
            "id": _stable_id("proy", f"tablon-{item['eid']}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(item.get("blob") or titulo),
            "url": doc_url,
            "source": "ayuntamiento",
            "origen": "tablon",
            "expediente": exp_m.group(1) if exp_m else None,
        }

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.impresos_url)
        except urllib.error.URLError:
            html = ""
        for m in RE_DOWNLOAD.finditer(html or ""):
            pdf = self._abs_url(m.group(1), self.web_base)
            if "licencias" not in pdf and "urbanismo" not in pdf:
                continue
            lic_id = _stable_id("lic", pdf)
            if lic_id in seen:
                continue
            seen.add(lic_id)
            name = Path(pdf).name.replace("-", " ")
            rows.append(
                {
                    "id": lic_id,
                    "fecha_concesion": _fecha_from_blob(pdf),
                    "tipo": "formulario / trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": name[:500],
                    "url": pdf,
                    "source": "ayuntamiento",
                    "origen": "formulario",
                }
            )
        rows.append(
            {
                "id": _stable_id("lic", self.catalogo_licencias),
                "fecha_concesion": None,
                "tipo": "catálogo trámites sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo sede — licencia de obra (SIAL)",
                "url": self.catalogo_licencias,
                "source": "ayuntamiento",
                "origen": "catalogo_info",
                "nota": "Tramitación electrónica sede.talavera.org",
            }
        )
        rows.append(
            {
                "id": _stable_id("lic", self.tablon_post_url),
                "fecha_concesion": None,
                "tipo": "tablón edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos — sede electrónica",
                "url": f"{self.sede_base}/web/tablonEdictos.do?opcion=0&entidad={ENTIDAD}&idioma=1",
                "source": "ayuntamiento",
                "origen": "tablon_info",
            }
        )
        return rows

    def _tablon_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_licencia(item):
            return None
        url = item.get("bop_url") or item["url"]
        if "|" in url:
            url = url.split("|")[0]
        return {
            "id": _stable_id("lic", f"tablon-{item['eid']}"),
            "fecha_concesion": item.get("fecha"),
            "tipo": "edicto / licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item.get("titulo") or item.get("codigo") or "Edicto",
            "url": url if url.startswith("http") else item["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._parse_tablon_entries():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "formularios": sum(1 for r in rows if r.get("origen") == "formulario"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        new_rows = 0
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                new_rows += 1
        for item in self._parse_tablon_entries():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in existing:
                existing[rec["id"]] = rec
                new_rows += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "new": new_rows, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_wp_proyectos():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._parse_tablon_entries():
            rec = self._tablon_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wpfd": sum(1 for r in rows if r.get("origen") == "wpfd"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        new_rows = 0
        for rec in self._collect_wp_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                new_rows += 1
        for item in self._parse_tablon_entries():
            rec = self._tablon_to_proyecto(item)
            if rec and rec["id"] not in existing:
                existing[rec["id"]] = rec
                new_rows += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "new": new_rows, "status": "ok"}
