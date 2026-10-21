from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import record_geometry

WEB_BASE = "https://web.sabadell.cat"
SEDE_BASE = "https://seu.sabadell.cat"
PLANOL_URL = "https://planol.sabadell.cat/Planol/inici?code=urban"
IDE_RECORD_URL = (
    "https://catalegs.ide.cat/geonetwork/srv/api/records/planejament-urbanistic-sabadell"
)
MUNICIPIO = "Sabadell"
ID_PREFIX = "sabadell"
INE_COD_MUN = "08187"

SEARCH_URL = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica_search.action"
TABLON_INDEX = f"{SEDE_BASE}/opensiac/action/custom?method=enter&page_index=1"
INFO_PUBLICA_OTROS = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica.action?edictos=OTROS"
INFO_PUBLICA_CP = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica?method=enter&edictos=CP"
TRAMITES_CATALOGO = f"{SEDE_BASE}/opensiac/action/tramites?method=enter"
EPPUBLICACION = f"{SEDE_BASE}/opensiac/action/eppublicacion?method=enter&te=N"

SEARCH_TERMS = [
    "URBAN",
    "PLANEJ",
    "PGMOS",
    "LICENC",
    "OBRA",
    "MODIFIC",
    "INFORMACIO PUBLICA",
    "EXPROPI",
    "REPARCEL",
    "ORDENAN",
    "SECTOR",
    "PEPS",
]

DEFAULT_PGOU_SEEDS: list[dict[str, Any]] = [
    {
        "titulo": "Geoportal de Planejament urbanístic (Plànol municipal)",
        "fecha": "2024-01-23",
        "url": PLANOL_URL,
        "blob": "PGMOS planejament urbanístic figures vigents PEPS MPG-117 geoportal",
        "origen": "geoportal_planol",
        "tipo": "PGOU",
    },
    {
        "titulo": "Planejament urbanístic — Ajuntament de Sabadell",
        "fecha": None,
        "url": f"{WEB_BASE}/urbanisme/planejament-urbanistic",
        "blob": "planejament urbanístic PGMOS modificacions puntuals documentació",
        "origen": "web_urbanisme",
        "tipo": "planeamiento",
    },
    {
        "titulo": "Text refós del Pla General Municipal d'Ordenació de Sabadell (PGMOS)",
        "fecha": "2000-10-02",
        "url": f"{WEB_BASE}/urbanisme/planejament-urbanistic/text-refos-del-PGMOS",
        "blob": "text refós PGMOS normes urbanístiques annexos sectors àmbits",
        "origen": "web_pgmos",
        "tipo": "PGOU",
    },
    {
        "titulo": "MPG-127 — Modificació puntual PGMOS (usos recreatiu i habitatge turístic)",
        "fecha": "2023-06-15",
        "url": f"{WEB_BASE}/urbanisme/planejament-urbanistic",
        "blob": "MPG-127 modificació puntual PGMOS usos recreatiu habitatge turístic DOGC",
        "origen": "web_modificacion",
        "tipo": "modificación planeamiento",
    },
    {
        "titulo": "Cartografia i plànols — planejament urbanístic (IDE Catalunya)",
        "fecha": "2024-01-23",
        "url": IDE_RECORD_URL,
        "blob": "conjunt geogràfic planejament urbanístic Sabadell MPG-117 sèries N-0 N-1 N-2 N-3 PEPS",
        "origen": "ide_metadata",
        "tipo": "PGOU",
    },
]

DEFAULT_LICENCIA_TRAMITES: list[dict[str, str]] = [
    {
        "url": f"{SEDE_BASE}/opensiac/action/tramitesinfo?id=36&method=enter",
        "titulo": "Llicència de parcel·lació urbanística",
        "tipo": "licencia parcelación",
    },
    {
        "url": f"{SEDE_BASE}/opensiac/action/tramitesinfo?id=35&method=enter",
        "titulo": "Llicència d'obres (informació tràmit)",
        "tipo": "licencia de obra",
    },
    {
        "url": f"{WEB_BASE}/urbanisme/planol",
        "titulo": "Plànol d'emplaçament per sol·licitud de llicències (E 1:500)",
        "tipo": "documentación licencia",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(lic[eè]n[cç]ia|llic[eè]ncia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autoritzaci[oó]|autorizaci[oó]n (?:previa|urban)|inici d'obra|inicio de obra|"
    r"obra (?:major|menor)|primera ocupaci[oó]n|parcel·laci[oó]|parcelaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|plan (?:parcial|especial|general)|pgmou|pgmos|pgou|"
    r"informaci[oó]n p[uú]blica|expedient|expediente|projecte|proyecto|modificaci[oó]n|"
    r"reparcel|estudi(?:o)? (?:ac[uú]stic|ambiental|de detall)|mem[oò]ria|pl[aà]nol|"
    r"aprobaci[oó]n|sector|àmbit|ambit|peps|mpg-|ordenan|edicto|expropiaci[oó]n)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|oferta p[uú]blica d'ocupaci[oó]|bolsa de treball|"
    r"nombramiento|convocatoria.*empleo|subvenci[oó]n|festa major|bandes de m[uú]sica)",
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
RE_ARCGIS = re.compile(
    r"https?://[^\"'\\s]+(?:MapServer|FeatureServer|ImageServer)[^\"'\\s]*",
    re.I,
)

_GMD_NS = {"gmd": "http://www.isotc211.org/2005/gmd", "gco": "http://www.isotc211.org/2005/gco"}


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
    if "mpg-" in n or "modificaci" in n:
        return "modificación planeamiento"
    if "peps" in n:
        return "plan especial patrimonio"
    if "pgmos" in n or "pgou" in n or "pla general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "sector" in n or "àmbit" in n or "ambit" in n:
        return "sector / ámbito"
    if "licencia" in n or "llic" in n:
        return "licencia publicada"
    return "urbanismo"


class SabadellAyuntamientoAdapter(AyuntamientoAdapter):
    """OpenSIAC (seu.sabadell.cat) + web PGMOS + metadades IDE + Plànol municipal."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.planol_url = str(self.config.get("planol_url") or PLANOL_URL)
        self.ide_record_url = str(self.config.get("ide_record_url") or IDE_RECORD_URL)
        self.search_url = str(self.config.get("search_url") or SEARCH_URL)
        self.search_terms = [str(t) for t in (self.config.get("search_terms") or SEARCH_TERMS)]
        self.pgou_seeds = list(self.config.get("pgou_seeds") or DEFAULT_PGOU_SEEDS)
        self.licencia_tramites = list(self.config.get("licencia_tramites") or DEFAULT_LICENCIA_TRAMITES)
        self.ine_cod_mun = str(self.config.get("cod_ine_mun") or INE_COD_MUN)
        self._sede_unreachable = False
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, data: bytes | None = None, timeout: int = 20) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-sabadell/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=timeout) as resp:
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
        if self._sede_unreachable:
            return []
        try:
            html = self._fetch(self.search_url, data=data, timeout=12)
        except (urllib.error.URLError, TimeoutError, OSError):
            self._sede_unreachable = True
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
        except (urllib.error.URLError, TimeoutError, OSError):
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
        return {
            **row,
            "titulo": (titulo or row.get("titulo", ""))[:500],
            "fecha": fecha,
            "fecha_fin": _parse_fecha_dmy(fin or ""),
            "blob": blob[:1000],
            "pdf_url": pdfs[0] if pdfs else None,
            "pdfs": pdfs,
            "ficheros": ficheros,
        }

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

        for tipo_tablon in ("Ajuntament de Sabadell", "Ayuntamiento de Sabadell"):
            add_rows(
                self._search_publications(
                    edictos="OTROS",
                    descripcion_tipo=tipo_tablon,
                    referencia="OTROS",
                    todos=True,
                ),
                "tablon_todos",
            )
            if self._sede_unreachable:
                break
            for term in self.search_terms[:4]:
                add_rows(
                    self._search_publications(
                        edictos="OTROS",
                        descripcion_tipo=tipo_tablon,
                        referencia="OTROS",
                        descripcion=term,
                    ),
                    f"tablon_busqueda_{term.lower().replace(' ', '_')}",
                )
                if self._sede_unreachable:
                    break

        if not self._sede_unreachable:
            add_rows(
                self._search_publications(
                    edictos="CP",
                    descripcion_tipo="Consultes Públiques",
                    referencia="CP",
                    todos=True,
                ),
                "consultas_publicas",
            )

        return [self._enrich_publication(row) for row in merged.values()]

    def _collect_pgou_seeds(self) -> list[dict[str, Any]]:
        seeds = [dict(s) for s in self.pgou_seeds]
        try:
            raw = self._fetch(self.ide_record_url, timeout=45)
            root = ET.fromstring(raw)
            abstract = root.find(".//gmd:abstract/gmd:CharacterString", _GMD_NS)
            if abstract is not None and abstract.text:
                seeds.append(
                    {
                        "titulo": "Planejament urbanístic de Sabadell (resum metadades IDE)",
                        "fecha": "2024-01-23",
                        "url": self.ide_record_url,
                        "blob": abstract.text[:900],
                        "origen": "ide_abstract",
                        "tipo": "PGOU",
                    }
                )
        except (urllib.error.URLError, ET.ParseError, TimeoutError, OSError):
            pass
        return seeds

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        static_pages = [
            (TRAMITES_CATALOGO, "Catálogo de trámites — Urbanisme i llicències", "catálogo trámites"),
            (EPPUBLICACION, "Publicaciones electrónicas (tablón edictos)", "tablón edictos"),
            (INFO_PUBLICA_OTROS, "Tablón de anuncios — edictos municipales", "tablón edictos"),
            (INFO_PUBLICA_CP, "Consultas / información pública urbanística", "información pública"),
            (TABLON_INDEX, "Índice tablón OpenSIAC", "tablón index"),
            (
                "https://seua.sabadell.cat/sedelectronica/p/TramitsCarpeta_esp.asp",
                "Carpeta ciudadana — consulta expedientes de obra (autenticación)",
                "consulta expedientes",
            ),
        ]
        for url, titulo, tipo in static_pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_info",
                }
            )
        for item in self.licencia_tramites:
            url = item["url"]
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": item.get("tipo") or "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item.get("titulo") or "Trámite licencias urbanísticas",
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_tramite",
                    "nota": "Tramitación electrónica; sin histórico público de concesiones",
                }
            )
        return rows

    def _try_planol_arcgis_hint(self, rec: dict[str, Any]) -> dict[str, Any]:
        if record_geometry(rec):
            return rec
        try:
            html = self._fetch(self.planol_url, timeout=25)
        except (urllib.error.URLError, TimeoutError, OSError):
            return rec
        for m in RE_ARCGIS.finditer(html):
            service_url = m.group(0).split("?")[0]
            rec.setdefault("nota_geometry", f"Servicio detectado en HTML Plànol: {service_url[:120]}")
            break
        return rec

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
        elif "parcel" in low:
            tipo = "licencia de parcelación"
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
            "fecha": row.get("fecha") or _fecha_from_blob(blob),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "cod_ine_mun": self.ine_cod_mun,
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("pub_id"):
            rec["pub_id"] = row["pub_id"]
        return self._try_planol_arcgis_hint(rec)

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
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "tablon+pgou+ide",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "pgou": sum(
                1
                for r in rows
                if str(r.get("origen", "")).startswith(
                    ("web_", "geoportal_", "ide_", "web_modificacion")
                )
            ),
            "with_geometry": with_geom,
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
