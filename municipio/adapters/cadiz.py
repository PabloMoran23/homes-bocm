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

BASE = "https://institucional.cadiz.es"
TABLON_LIST = f"{BASE}/area/Tabl%C3%B3n-de-anuncios-Ayto.-C%C3%A1diz/646"
MUNICIPIO = "Cádiz"
ID_PREFIX = "cadiz"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/area/Plan-General-de-Ordenaci%C3%B3n-Urban%C3%ADstica-(PGOU)/677",
    f"{BASE}/area/Modificaciones-del-PGOU-(en-tr%C3%A1mite)/2443",
    f"{BASE}/area/Modificaciones-aprobadas-del-PGOU./2038",
    f"{BASE}/area/Modificaci%C3%B3n%20PGOU%20%22Hospedaje%20y%20Equipamiento%22/2446",
    f"{BASE}/area/Convenios-urban%C3%ADsticos/806",
    f"{BASE}/area/Trabajos-en-curso/2013",
    f"{BASE}/area/Solicitudes/595",
    f"{BASE}/area/Normativa-vigente-en-materia-de-Gesti%C3%B3n-Urban%C3%ADstica/2037",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|inicio de obra|obra (?:mayor|menor)|"
    r"calificaci[oó]n ambiental|actividad(?:es)? calificad)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"unidad de ejecuci[oó]n|\bue\b|expropiaci[oó]n|ordenanza|reparcelaci[oó]n)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|padr[oó]n|bolsa de empleo|subvenci[oó]n deportiv|"
    r"estad[ií]stica|tributaria|recaudaci[oó]n)",
)
RE_FECHA_TABLON = re.compile(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_UPLOAD = re.compile(r"subido el (\d{2})-(\d{2})-(\d{4})")
RE_TABLON_LIST_ROW = re.compile(
    r'href="(/[^"]+)"[^>]*><span class="titulo">([^<]+)</span>',
    re.I,
)
RE_TABLON_RESUMEN = re.compile(r"<b>Resumen: </b>(.*?)</p>", re.I | re.S)
RE_TABLON_FECHA = re.compile(r"<b>Fecha de publicaci[oó]n: </b>([^<]+)", re.I)
RE_TABLON_DESC = re.compile(r"<b>Descripci[oó]n: </b>(.*?)(?:</p>|<p><b>)", re.I | re.S)
RE_PDF_HREF = re.compile(
    r"href=['\"]((?:https://institucional\.cadiz\.es)?/[^'\"]+\.pdf[^'\"]*)['\"]",
    re.I,
)
RE_LINK_HREF = re.compile(
    r'href=["\']((?:https://institucional\.cadiz\.es)?/[^"\']+)["\']',
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

MESES = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
    "jan": 1,
    "apr": 4,
    "aug": 8,
    "dec": 12,
}


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


def _parse_fecha_tablon(text: str) -> str | None:
    m = RE_FECHA_TABLON.search(text or "")
    if not m:
        return _parse_fecha_dmy(text)
    month = MESES.get(m.group(2).lower()[:3])
    if not month:
        return None
    try:
        return datetime(int(m.group(3)), month, int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    d = _parse_fecha_tablon(text)
    if d:
        return d
    m = RE_FECHA_UPLOAD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "reparcelaci" in n or "unidad de ejecuci" in n or re.search(r"\bue\b", n):
        return "reparcelación / UE"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "plan especial" in n:
        return "plan especial"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "calificaci" in n and "ambiental" in n:
        return "calificación ambiental"
    if "convenio" in n:
        return "convenio urbanístico"
    if "expropiaci" in n:
        return "expropiación"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


class CadizAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal institucional.cadiz.es: tablón urbanismo-N + PGOU/modificaciones + trámites."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.tablon_list_url = str(self.config.get("tablon_list_url") or TABLON_LIST)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_tablon_scan = int(self.config.get("max_tablon_scan", 400))
        self.tablon_stop_misses = int(self.config.get("tablon_stop_misses", 20))
        self.incremental_tail = int(self.config.get("incremental_tail", 40))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{BASE}/", unescape(href))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cadiz/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _parse_tablon_detail(self, html: str, url: str) -> dict[str, Any] | None:
        if not RE_TABLON_RESUMEN.search(html):
            return None
        resumen = _strip_html(RE_TABLON_RESUMEN.search(html).group(1))
        fecha_raw = RE_TABLON_FECHA.search(html)
        fecha = _parse_fecha_tablon(fecha_raw.group(1)) if fecha_raw else None
        desc_m = RE_TABLON_DESC.search(html)
        descripcion = _strip_html(desc_m.group(1)) if desc_m else ""
        pdfs = [self._abs_url(m.group(1)) for m in RE_PDF_HREF.finditer(html)]
        titulo = resumen or descripcion or url.rsplit("/", 1)[-1]
        blob = f"{titulo} {descripcion} {resumen}"
        return {
            "titulo": titulo[:500],
            "fecha": fecha,
            "descripcion": descripcion[:1000],
            "url": url,
            "pdf_url": pdfs[0] if pdfs else None,
            "pdfs": pdfs,
            "blob": blob,
            "origen": "tablon_detalle",
        }

    def _collect_tablon_urbanismo_scan(self, *, start: int = 1, end: int | None = None) -> list[dict[str, Any]]:
        end = end or self.max_tablon_scan
        rows: list[dict[str, Any]] = []
        misses = 0
        for n in range(start, end + 1):
            url = f"{BASE}/urbanismo-{n}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                misses += 1
                if misses >= self.tablon_stop_misses and n > 30:
                    break
                continue
            item = self._parse_tablon_detail(html, url)
            if not item:
                misses += 1
                if misses >= self.tablon_stop_misses and n > 30:
                    break
                continue
            misses = 0
            item["tablon_id"] = n
            item["origen"] = "tablon_urbanismo"
            rows.append(item)
        return rows

    def _collect_tablon_listing(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_list_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_LIST_ROW.finditer(html):
            path, titulo = m.group(1), _strip_html(m.group(2))
            url = self._abs_url(path)
            upload_dates = [
                _fecha_from_blob(cm.group(0))
                for cm in re.finditer(
                    rf'href="{re.escape(path)}"[\s\S]*?subido el (\d{{2}}-\d{{2}}-\d{{4}})',
                    html,
                    re.I,
                )
            ]
            fecha = next((d for d in upload_dates if d), None)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "blob": titulo,
                    "origen": "tablon_listado",
                }
            )
        return rows

    def _enrich_tablon_listing(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for item in items:
            path = urllib.parse.urlparse(item["url"]).path.lower()
            if path.startswith("/urbanismo-"):
                try:
                    html = self._fetch(item["url"])
                    detail = self._parse_tablon_detail(html, item["url"])
                    if detail:
                        enriched.append({**item, **detail, "origen": "tablon_urbanismo"})
                        continue
                except urllib.error.URLError:
                    pass
            try:
                html = self._fetch(item["url"])
            except urllib.error.URLError:
                continue
            detail = self._parse_tablon_detail(html, item["url"])
            if detail:
                enriched.append({**item, **detail})
            elif RE_PROYECTO.search(item.get("blob", "")) or RE_LICENCIA.search(item.get("blob", "")):
                enriched.append(item)
        return enriched

    def _crawl_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
            section = _strip_html(title_m.group(1)) if title_m else seed.rsplit("/", 1)[-1]
            for m in RE_PDF_HREF.finditer(html):
                href = self._abs_url(m.group(1))
                if href in seen:
                    continue
                seen.add(href)
                fname = unescape(urllib.parse.unquote(href.rsplit("/", 1)[-1]))
                titulo = re.sub(r"[_\-]+", " ", fname.rsplit(".", 1)[0]).strip()
                if len(titulo) < 8:
                    titulo = f"{section} — {fname}"
                blob = f"{section} {titulo} {fname}"
                if not (RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob)):
                    if "pgou" not in seed.lower() and "urban" not in seed.lower():
                        continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(fname),
                        "url": href,
                        "pdf_url": href,
                        "blob": blob,
                        "origen": "pgou_semilla",
                        "seccion": section,
                    }
                )
            for m in RE_LINK_HREF.finditer(html):
                href = self._abs_url(m.group(1))
                if href in seen or href == seed:
                    continue
                if not href.startswith(BASE):
                    continue
                if "/area/" not in href or href.count("/area/") != 1:
                    continue
                low = href.lower()
                if not any(k in low for k in ("pgou", "modific", "convenio", "urban", "planeam")):
                    continue
                seen.add(href)
                label = unescape(urllib.parse.unquote(href.rsplit("/", 1)[-1])).replace("-", " ")
                rows.append(
                    {
                        "titulo": label[:500],
                        "fecha": None,
                        "url": href,
                        "blob": f"{section} {label}",
                        "origen": "pgou_enlace",
                        "seccion": section,
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", f"{BASE}/area/Solicitudes/595"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Solicitudes y trámites de urbanismo",
                "url": f"{BASE}/area/Solicitudes/595",
                "source": "ayuntamiento",
                "nota": "Formularios licencias obra, apertura y actividad (Drupal)",
                "origen": "tramite_info",
            },
            {
                "id": _stable_id("lic", f"{BASE}/area/Licencias-de-obras/410"),
                "fecha_concesion": None,
                "tipo": "licencias de obras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias de obras — documentación",
                "url": f"{BASE}/area/Licencias-de-obras/410",
                "source": "ayuntamiento",
                "nota": "Trámites informativos; concesiones en tablón virtual",
                "origen": "tramite_info",
            },
            {
                "id": _stable_id("lic", self.tablon_list_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios Ayuntamiento de Cádiz",
                "url": self.tablon_list_url,
                "source": "ayuntamiento",
                "nota": "Edictos y resoluciones de licencias/urbanismo",
                "origen": "tablon_listado",
            },
            {
                "id": _stable_id(
                    "lic",
                    "https://portaldelcontribuyente.cadiz.es/portalCiudadano/sede/catalogoTramites.do",
                ),
                "fecha_concesion": None,
                "tipo": "sede electrónica trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — Portal del Contribuyente",
                "url": "https://portaldelcontribuyente.cadiz.es/portalCiudadano/sede/catalogoTramites.do?opcion=buscar&ent_id=1&idioma=1&texto=urbanismo",
                "source": "ayuntamiento",
                "nota": "Sede municipal; sin listado histórico de concesiones",
                "origen": "sede_tramite",
            },
        ]

    def _is_urban(self, blob: str) -> bool:
        if RE_TABLON_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not self._is_urban(blob) or not RE_LICENCIA.search(blob):
            return None
        tipo = "licencia"
        low = blob.lower()
        if "calificaci" in low and "ambiental" in low:
            tipo = "calificación ambiental"
        elif "apertura" in low or "actividad" in low:
            tipo = "licencia de apertura/actividad"
        elif "obra" in low:
            tipo = "licencia de obra"
        key = row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row.get("titulo"),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not self._is_urban(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row.get("titulo"),
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("descripcion"):
            rec["descripcion"] = row["descripcion"]
        return rec

    def _merge_rows(self, *groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for group in groups:
            for row in group:
                key = row.get("url") or row.get("titulo") or ""
                if not key:
                    continue
                if key in by_key:
                    prev = by_key[key]
                    for k, v in row.items():
                        if v is not None and (k not in prev or prev[k] in (None, "")):
                            prev[k] = v
                else:
                    by_key[key] = dict(row)
        return list(by_key.values())

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def _collect_tablon_all(self) -> list[dict[str, Any]]:
        scan = self._collect_tablon_urbanismo_scan()
        listing = self._collect_tablon_listing()
        listing_detail = self._enrich_tablon_listing(listing)
        return self._merge_rows(scan, listing_detail)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        tablon = self._collect_tablon_all()
        rows = self._collect_licencia_info_pages()
        seen = {r["id"] for r in rows}
        for item in tablon:
            lic = self._to_licencia(item)
            if lic and lic["id"] not in seen:
                rows.append(lic)
                seen.add(lic["id"])
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "tablon+tramites",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        tablon = self._collect_tablon_all()
        seeds = self._crawl_seed_pages()
        merged = self._merge_rows(tablon, seeds)
        rows: list[dict[str, Any]] = []
        for item in merged:
            proy = self._to_proyecto(item)
            if proy:
                rows.append(proy)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "tablon+pgou",
            "tablon_urbanismo": sum(1 for r in rows if r.get("origen") == "tablon_urbanismo"),
            "pgou": sum(1 for r in rows if str(r.get("origen", "")).startswith("pgou")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        state: dict[str, Any] = {}
        if state_path.is_file():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = {}
        last_id = int(state.get("last_tablon_id") or 0)
        start = max(1, last_id - self.incremental_tail)
        scan = self._collect_tablon_urbanismo_scan(start=start, end=self.max_tablon_scan)
        listing = self._enrich_tablon_listing(self._collect_tablon_listing())
        seeds = self._crawl_seed_pages()
        merged = self._merge_rows(scan, listing, seeds)
        new_rows: list[dict[str, Any]] = []
        for item in merged:
            proy = self._to_proyecto(item)
            if proy:
                new_rows.append(proy)
        existing = self._load_jsonl(out_jsonl)
        combined = self._merge_rows(existing, new_rows)
        proy_rows = [r for r in combined if r.get("municipio")]
        self._write_jsonl(out_jsonl, proy_rows)
        max_id = max((int(r.get("tablon_id") or 0) for r in scan), default=last_id)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "last_tablon_id": max_id,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "rows": len(proy_rows),
            "status": "ok",
            "source": "incremental",
            "new_scan": len(scan),
        }
