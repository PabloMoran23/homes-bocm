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

WEB_BASE = "https://www.nerja.es"
SEDE_BASE = "https://sedeelectronica.nerja.es"
TABLON_PAGE = f"{SEDE_BASE}/portal/noEstatica.do?opc_id=268&ent_id=1&idioma=1"
SITUA_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=29901"
MUNICIPIO = "Nerja"
ID_PREFIX = "nerja"

DEFAULT_TABLON_SUBSECTIONS = ("dep.urb", "DEP.AP", "DEP.TRAF")

WEB_SEEDS: list[str] = [
    f"{WEB_BASE}/urbanismo/",
    f"{WEB_BASE}/urbanismo/pgom/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura| de ocupaci[oó]n)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|ocupaci[oó]n.*v[ií]a p[uú]blica|ovp\b|quiosco|apertura)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|municipal)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|actuaci[oó]n|rehabilitaci[oó]n.*vivienda|vivienda vpo|programa municipal)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(proceso selectivo|personal laboral|convocatoria.*empleo|"
    r"subvenci[oó]n|fiestas|permiso de caza|taxi|carnet taxi)",
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{3,300})</a>', re.I | re.S)
RE_SKIP_LINK = re.compile(
    r"(?i)(favicon|facebook|twitter|instagram|youtube|#|javascript:|"
    r"wp-json|feed/|xmlrpc|accesibilidad|cookies|privacy|mailto:|gtranslate)",
)
RE_DOC_EXT = re.compile(r"(?i)\.(pdf|zip)(\?|$)")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_PATH = re.compile(r"/(20\d{2})/(\d{2})/")
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
    m = RE_FECHA_PATH.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _clean_title(text: str) -> str:
    return _strip_html(text)[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pgom" in n or "pgou" in n:
        return "PGOM"
    if "reparcel" in n:
        return "reparcelación"
    if "programa" in n and "rehabilitaci" in n:
        return "rehabilitación de viviendas"
    if "vivienda" in n and "vpo" in n:
        return "vivienda protegida"
    if "licencia" in n:
        return "licencia publicada"
    if "ocupaci" in n and "p" in n and "blica" in n:
        return "ocupación vía pública"
    if "planeam" in n or "urban" in n:
        return "planeamiento"
    return "urbanismo"


class NerjaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (urbanismo/PGOM) + sede Insuit tablón electrónico JSON + SITUA."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_page = str(self.config.get("tablon_page") or TABLON_PAGE)
        self.tablon_opc_id = str(self.config.get("tablon_opc_id") or "268")
        self.tablon_subsections = tuple(
            self.config.get("tablon_subsections") or DEFAULT_TABLON_SUBSECTIONS
        )
        self.situa_url = str(self.config.get("situa_url") or SITUA_URL)
        self.web_seeds = [str(u) for u in (self.config.get("web_seeds") or WEB_SEEDS)]

    def _fetch(self, url: str, *, data: bytes | None = None, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-nerja/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or ("iso-8859-1" if sede else "utf-8")
            return raw.decode(charset, errors="replace")

    def _fetch_json(self, payload: dict[str, str]) -> dict[str, Any]:
        url = f"{self.sede_base}/sede/tablonElectronico.do"
        body = urllib.parse.urlencode(payload).encode()
        text = self._fetch(url, sede=True, data=body)
        data = json.loads(text)
        return data if isinstance(data, dict) else {}

    def _abs_web(self, href: str) -> str:
        if href.startswith("//"):
            return f"https:{href}"
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _abs_sede(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        return urllib.parse.urljoin(f"{self.sede_base}/", href.lstrip("/"))

    def _tablon_consultar(self, subseccion: str) -> dict[str, Any]:
        return self._fetch_json(
            {
                "opcion": "consultar",
                "opc_id": self.tablon_opc_id,
                "ent_id": "1",
                "subseccion": subseccion,
            }
        )

    def _tablon_detalle(self, subseccion: str, exp_id: str) -> dict[str, Any]:
        return self._fetch_json(
            {
                "opcion": "verDetalleExpediente",
                "opc_id": self.tablon_opc_id,
                "ent_id": "1",
                "subseccion": subseccion,
                "expId": exp_id,
            }
        )

    def _exp_url(self, exp: dict[str, Any], docs: list[dict[str, Any]] | None = None) -> str:
        if docs:
            doc_url = str(docs[0].get("docUrl") or "")
            if doc_url:
                return self._abs_sede(doc_url)
        return self.tablon_page

    def _collect_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sub in self.tablon_subsections:
            try:
                obj = self._tablon_consultar(sub)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            for doc in obj.get("listaDocumentos") or []:
                name = _clean_title(str(doc.get("docNom") or ""))
                if not name:
                    continue
                key = f"doc:{doc.get('docId') or name}"
                if key in seen:
                    continue
                seen.add(key)
                url = self._abs_sede(str(doc.get("docUrl") or "")) if doc.get("docUrl") else self.tablon_page
                rows.append(
                    {
                        "titulo": name,
                        "fecha": _parse_fecha_dmy(str(doc.get("docFpu") or name)),
                        "url": url,
                        "subseccion": sub,
                        "origen": "tablon_doc",
                        "blob": name,
                        "tipo_des": "",
                    }
                )
            for exp in obj.get("listaExpedientes") or []:
                exp_id = str(exp.get("idExp") or "")
                if not exp_id or exp_id in seen:
                    continue
                seen.add(exp_id)
                item = dict(exp)
                item["subseccion"] = sub
                rows.append(item)
        return rows

    def _is_urban_blob(self, blob: str) -> bool:
        if RE_BOARD_NON_URBAN.search(blob):
            if not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _collect_web_docs(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add_row(url: str, titulo: str, blob: str, origen: str) -> None:
            if url in seen_urls or RE_SKIP_LINK.search(url):
                return
            if not RE_PROYECTO.search(blob) and not RE_DOC_EXT.search(url):
                return
            seen_urls.add(url)
            rows.append(
                {
                    "titulo": _clean_title(titulo) or Path(urllib.parse.urlparse(url).path).name,
                    "fecha": _fecha_from_blob(f"{titulo} {url}"),
                    "url": url,
                    "tipo": _proyecto_tipo(blob),
                    "origen": origen,
                    "blob": blob[:2000],
                }
            )

        for seed in self.web_seeds:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            add_row(seed, Path(seed.rstrip("/")).name.replace("-", " "), f"{seed} urbanismo Nerja", "web_indice")
            for m in RE_LINK.finditer(html):
                href = self._abs_web(m.group(1))
                text = _clean_title(m.group(2))
                if RE_SKIP_LINK.search(href):
                    continue
                blob = f"{text} {href}"
                if href.startswith(self.web_base) and RE_DOC_EXT.search(href):
                    add_row(href, text, blob, "web_pdf")
                elif RE_DOC_EXT.search(href) and RE_PROYECTO.search(blob):
                    add_row(href, text, blob, "web_pdf")

        add_row(
            self.situa_url,
            "PGOM Nerja — consulta SITUA (Junta de Andalucía)",
            "PGOM planeamiento SITUA Nerja",
            "situa",
        )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_page),
                "fecha_concesion": None,
                "tipo": "tablón virtual — urbanismo y licencias",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón virtual — sede electrónica",
                "url": self.tablon_page,
                "source": "ayuntamiento",
                "nota": "Subsecciones dep.urb, DEP.AP, DEP.TRAF",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/urbanismo/"),
                "fecha_concesion": None,
                "tipo": "información trámites urbanísticos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo y vivienda — trámites y licencias",
                "url": f"{self.web_base}/urbanismo/",
                "source": "ayuntamiento",
                "nota": "Licencias de obra, apertura, DR y calificación ambiental (informativo)",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/sede/catalogoTramites.do?ent_id=1&idioma=1"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites electrónicos",
                "url": f"{self.sede_base}/sede/catalogoTramites.do?ent_id=1&idioma=1",
                "source": "ayuntamiento",
                "nota": "Trámites presenciales/electrónicos; urbanismo mayoritariamente presencial",
                "origen": "sede_tramite",
            },
        ]

    def _tablon_row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if "idExp" not in row:
            blob = row.get("blob") or row.get("titulo") or ""
            if not self._is_urban_blob(blob) or not RE_LICENCIA.search(blob):
                return None
            return {
                "id": _stable_id("lic", row.get("url") or blob),
                "fecha_concesion": row.get("fecha"),
                "tipo": "anuncio tablón",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": row.get("titulo"),
                "url": row.get("url") or self.tablon_page,
                "source": "ayuntamiento",
                "origen": row.get("origen"),
            }

        blob = f"{row.get('tipoDes', '')} {row.get('nombre', '')}"
        if not self._is_urban_blob(blob):
            return None
        if not RE_LICENCIA.search(blob) and (row.get("subseccion") or "") not in ("DEP.AP", "DEP.TRAF"):
            return None
        title = str(row.get("nombre") or "").strip()[:500]
        fecha = _parse_fecha_dmy(str(row.get("fechaPublicacion") or "")) or _parse_fecha_dmy(
            str(row.get("fechaCreacion") or "")
        )
        docs: list[dict[str, Any]] = []
        try:
            det = self._tablon_detalle(str(row.get("subseccion")), str(row.get("idExp")))
            docs = det.get("listaDocumentos") or []
        except (urllib.error.URLError, json.JSONDecodeError):
            pass
        return {
            "id": _stable_id("lic", str(row.get("idExp"))),
            "fecha_concesion": fecha,
            "tipo": str(row.get("tipoDes") or "licencia")[:120],
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "url": self._exp_url(row, docs),
            "source": "ayuntamiento",
            "expte": f"{row.get('anno')}/{row.get('codigo')}",
            "origen": f"tablon_{row.get('subseccion')}",
        }

    def _tablon_row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if "idExp" not in row:
            blob = row.get("blob") or row.get("titulo") or ""
            if not self._is_urban_blob(blob):
                return None
            if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                return None
            return {
                "id": _stable_id("proy", row.get("url") or blob),
                "municipio": MUNICIPIO,
                "titulo": row.get("titulo"),
                "fecha": row.get("fecha"),
                "tipo": _proyecto_tipo(blob),
                "url": row.get("url") or self.tablon_page,
                "source": "ayuntamiento",
                "origen": row.get("origen"),
            }

        blob = f"{row.get('tipoDes', '')} {row.get('nombre', '')}"
        if not self._is_urban_blob(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            if (row.get("subseccion") or "") != "dep.urb":
                return None
        title = str(row.get("nombre") or "").strip()[:500]
        fecha = _parse_fecha_dmy(str(row.get("fechaPublicacion") or "")) or _parse_fecha_dmy(
            str(row.get("fechaCreacion") or "")
        )
        docs: list[dict[str, Any]] = []
        try:
            det = self._tablon_detalle(str(row.get("subseccion")), str(row.get("idExp")))
            docs = det.get("listaDocumentos") or []
        except (urllib.error.URLError, json.JSONDecodeError):
            pass
        return {
            "id": _stable_id("proy", str(row.get("idExp"))),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": fecha,
            "tipo": _proyecto_tipo(blob),
            "url": self._exp_url(row, docs),
            "source": "ayuntamiento",
            "expte": f"{row.get('anno')}/{row.get('codigo')}",
            "origen": f"tablon_{row.get('subseccion')}",
        }

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row.get("titulo") or ""
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web",
        }

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

    def _merge_by_id(self, *groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for group in groups:
            for row in group:
                rid = str(row.get("id") or "")
                if rid:
                    out[rid] = row
        return list(out.values())

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._merge_by_id(
            self._collect_licencia_info_pages(),
            [r for item in self._collect_tablon() for r in [self._tablon_row_to_licencia(item)] if r],
        )
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon_")),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        result = self.backfill_licencias(out_jsonl)
        after = result["rows"]
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
        proy: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                proy.append(rec)

        for item in self._collect_web_docs():
            add(self._doc_to_proyecto(item))
        for item in self._collect_tablon():
            add(self._tablon_row_to_proyecto(item))

        self._write_jsonl(out_jsonl, proy)
        return {
            "rows": len(proy),
            "status": "ok",
            "tablon": sum(1 for r in proy if str(r.get("origen", "")).startswith("tablon_")),
            "web": sum(1 for r in proy if str(r.get("origen", "")).startswith("web")),
            "situa": sum(1 for r in proy if r.get("origen") == "situa"),
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
