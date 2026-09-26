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

SEDE_BASE = "https://sede.huelva.es"
SEARCH_URL = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica_search.action"
TABLON_INDEX = f"{SEDE_BASE}/opensiac/action/custom?method=enter&page_index=1"
INFO_PUBLICA_OTROS = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica.action?edictos=OTROS"
INFO_PUBLICA_CP = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica?method=enter&edictos=CP"
LICENCIAS_TRAMITE = f"{SEDE_BASE}/opensiac/action/tramitesinfo?id=35&method=enter"
TRAMITES_CATALOGO = f"{SEDE_BASE}/opensiac/informacionpublica/tramites_enter.action"
PGOU_PORTAL = (
    "https://www.huelva.es/portal/plan-general-de-ordenaci%C3%B3n-urbana-y-modificaciones-puntuales-del-pgou"
)
PGOU_LEGACY = "https://www.huelva.es/portal/en/paginas/plan-general-de-ordenaci%C3%B3n-urbana"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Huelva"
ID_PREFIX = "huelva"

SEARCH_TERMS = [
    "PGOU",
    "PLAN",
    "URBAN",
    "LICENC",
    "OBRA",
    "PRI",
    "MODIFIC",
    "EXPROPI",
    "REPARCEL",
    "CAUTELAR",
    "REFORMA INTERIOR",
    "CATALOGO",
    "ORDENANZA",
    "INFORMACION PUBLICA",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|inicio de obra|obra (?:mayor|menor)|"
    r"legalizaci[oó]n|apertura.*local|actividad econ[oó]mica)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|de reforma interior)|pgou|pri|"
    r"convenio|informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|cat[aá]logo|medidas cautelares|expropiaci[oó]n|"
    r"reforma interior|cash colombino|emplazamiento.*mercadillo)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|bolsa de trabajo|banda de m[uú]sica|monitor cultural|"
    r"censo electoral|feria de oto|sal[oó]n de pintura|caseta|jurado|empleo|interino|"
    r"plantilla correctora|ejercicio te[oó]rico|tip[oó] test)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LISTING_ROW = re.compile(
    r"infopublica_ver\.action[^\"]*id=(\d+)\"[^>]*title=\"Mostrar ([^\"]+)\"",
    re.I,
)
RE_LISTING_TABLE_ROW = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(\d{2}/\d{2}/\d{4})</td>",
    re.I | re.S,
)
RE_DETAIL_FIELD = re.compile(
    r'<td class="Etiqueta">([^<]+)</td>\s*<td class="Descripcion">(.*?)</td>',
    re.I | re.S,
)
RE_PDF_LINK = re.compile(
    r'href="(/opensiac/informacionpublica/infopublica_descargar\.action[^"]+)"',
    re.I,
)


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


def _fecha_from_blob(text: str) -> str | None:
    d = _parse_fecha_dmy(text)
    if d:
        return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "reforma interior" in n or re.search(r"\bpri\b", n):
        return "plan de reforma interior"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "catalogo" in n or "catálogo" in n:
        return "catálogo PGOU"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "medidas cautelares" in n:
        return "medidas cautelares urbanísticas"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "expropiaci" in n:
        return "expropiación"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


class HuelvaAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenSIAC sede.huelva.es: tablón edictos + consultas públicas + trámites licencias."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.search_url = str(self.config.get("search_url") or SEARCH_URL)
        self.search_terms = [str(t) for t in (self.config.get("search_terms") or SEARCH_TERMS)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-huelva/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "iso-8859-15"
            return resp.read().decode(charset, errors="replace")

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href.replace("&amp;", "&")))

    def _search_publications(
        self,
        *,
        edictos: str,
        descripcion_tipo: str,
        referencia: str,
        descripcion: str | None = None,
        todos: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {
            "edictos": edictos,
            "descripcionTipoTablon": descripcion_tipo,
            "referencia": referencia,
        }
        if todos:
            params["botonTodos"] = "Todos"
        elif descripcion:
            params["descripcionPublicacion"] = descripcion
            params["botonBuscar"] = "Buscar"
        data = urllib.parse.urlencode(params).encode("iso-8859-15", errors="replace")
        try:
            html = self._fetch(self.search_url, data=data)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_LISTING_ROW.finditer(html):
            pub_id, titulo = m.group(1), _strip_html(m.group(2))
            if pub_id in seen:
                continue
            seen.add(pub_id)
            rows.append(
                {
                    "pub_id": pub_id,
                    "titulo": titulo[:500],
                    "fecha": None,
                    "url": f"{self.sede_base}/opensiac/informacionpublica/infopublica_ver.action?id={pub_id}",
                    "blob": titulo,
                    "origen": "tablon_opensiac",
                    "edictos": edictos,
                }
            )

        for m in RE_LISTING_TABLE_ROW.finditer(html):
            title_html, fecha_raw = m.group(1), m.group(2)
            if "infopublica_ver" not in title_html:
                continue
            id_m = re.search(r"id=(\d+)", title_html)
            if not id_m:
                continue
            pub_id = id_m.group(1)
            titulo = _strip_html(re.sub(r"<a[^>]*>", " ", title_html))
            for row in rows:
                if row["pub_id"] == pub_id:
                    row["fecha"] = _parse_fecha_dmy(fecha_raw)
                    if titulo:
                        row["titulo"] = titulo[:500]
                        row["blob"] = titulo
                    break
        return rows

    def _enrich_publication(self, row: dict[str, Any]) -> dict[str, Any]:
        try:
            html = self._fetch(row["url"])
        except urllib.error.URLError:
            return row

        fields: dict[str, str] = {}
        for m in RE_DETAIL_FIELD.finditer(html):
            key = _strip_html(m.group(1)).lower()
            val = _strip_html(m.group(2))
            fields[key] = val

        titulo = fields.get("título") or fields.get("titulo") or row.get("titulo")
        fecha = _parse_fecha_dmy(fields.get("fecha publicación", "")) or row.get("fecha")
        fin = fields.get("fecha prevista fin de la publicación")

        pdfs: list[str] = []
        for m in RE_PDF_LINK.finditer(html):
            pdfs.append(self._abs_sede(m.group(1)))

        ficheros: list[str] = []
        for m in re.finditer(r'class="listaFicherosDescripcion">([^<]+)', html, re.I):
            ficheros.append(_strip_html(m.group(1)))

        blob = " ".join(filter(None, [titulo, " ".join(ficheros)]))
        enriched = {
            **row,
            "titulo": (titulo or row.get("titulo", ""))[:500],
            "fecha": fecha,
            "fecha_fin": _parse_fecha_dmy(fin or ""),
            "blob": blob[:1000],
            "pdf_url": pdfs[0] if pdfs else None,
            "pdfs": pdfs,
            "ficheros": ficheros,
        }
        return enriched

    def _collect_tablon(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}

        def add_rows(rows: list[dict[str, Any]], origen: str) -> None:
            for row in rows:
                pid = row["pub_id"]
                row["origen"] = origen
                if pid in merged:
                    prev = merged[pid]
                    for k, v in row.items():
                        if v and (k not in prev or not prev[k]):
                            prev[k] = v
                else:
                    merged[pid] = dict(row)

        add_rows(
            self._search_publications(
                edictos="OTROS",
                descripcion_tipo="Ayuntamiento de Huelva",
                referencia="OTROS",
                todos=True,
            ),
            "tablon_todos",
        )
        for term in self.search_terms:
            add_rows(
                self._search_publications(
                    edictos="OTROS",
                    descripcion_tipo="Ayuntamiento de Huelva",
                    referencia="OTROS",
                    descripcion=term,
                ),
                f"tablon_busqueda_{term.lower().replace(' ', '_')}",
            )
        add_rows(
            self._search_publications(
                edictos="CP",
                descripcion_tipo="Consultas Públicas",
                referencia="CP",
                todos=True,
            ),
            "consultas_publicas",
        )

        enriched: list[dict[str, Any]] = []
        for row in merged.values():
            enriched.append(self._enrich_publication(row))
        return enriched

    def _collect_pgou_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Plan General de Ordenación Urbana y modificaciones puntuales",
                "fecha": None,
                "url": PGOU_PORTAL,
                "blob": "PGOU Huelva modificaciones puntuales plan general ordenación urbana",
                "origen": "web_pgou",
                "tipo": "PGOU",
            },
            {
                "titulo": "PGOU Huelva — documentación histórica (memorias, planos, ordenanzas)",
                "fecha": None,
                "url": PGOU_LEGACY,
                "blob": "PGOU Huelva memoria ordenación planos gestión normativa",
                "origen": "web_pgou",
                "tipo": "PGOU",
            },
            {
                "titulo": "PGOU Huelva — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "url": SITUA_SEARCH,
                "blob": "SITUA planeamiento urbanístico Huelva Andalucía",
                "origen": "situa",
                "tipo": "PGOU",
            },
        ]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", LICENCIAS_TRAMITE),
                "fecha_concesion": None,
                "tipo": "licencias urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias Urbanismo — trámites y formularios",
                "url": LICENCIAS_TRAMITE,
                "source": "ayuntamiento",
                "nota": "Obra mayor/menor, legalizaciones, comunicación previa (OpenSIAC id=35)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", TRAMITES_CATALOGO),
                "fecha_concesion": None,
                "tipo": "catálogo trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de servicios — Urbanismo y Medio Ambiente",
                "url": TRAMITES_CATALOGO,
                "source": "ayuntamiento",
                "nota": "Registro electrónico; sin histórico de concesiones",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", TABLON_INDEX),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios y edictos (OpenCERTIAC)",
                "url": TABLON_INDEX,
                "source": "ayuntamiento",
                "nota": "Edictos y resoluciones publicadas en sede electrónica",
                "origen": "tablon_index",
            },
            {
                "id": _stable_id("lic", INFO_PUBLICA_OTROS),
                "fecha_concesion": None,
                "tipo": "tablón edictos municipales",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Publicaciones tablón — Ayuntamiento de Huelva",
                "url": INFO_PUBLICA_OTROS,
                "source": "ayuntamiento",
                "nota": "Búsqueda por descripción; categoría Urbanismo con publicaciones puntuales",
                "origen": "tablon_busqueda",
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
        if "comunicaci" in low and "previa" in low:
            tipo = "comunicación previa"
        elif "legalizaci" in low:
            tipo = "legalización"
        elif "apertura" in low or "actividad" in low:
            tipo = "licencia de apertura/actividad"
        elif "obra" in low:
            tipo = "licencia de obra"
        key = row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
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
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

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
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("pub_id"):
            rec["pub_id"] = row["pub_id"]
        return rec

    def _merge_rows(self, *groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for group in groups:
            for row in group:
                key = row.get("url") or row.get("id") or row.get("titulo") or ""
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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        tablon = self._collect_tablon()
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
        tablon = self._collect_tablon()
        seeds = self._collect_pgou_seeds()
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
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "pgou": sum(1 for r in rows if str(r.get("origen", "")).startswith(("web_pgou", "situa"))),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
