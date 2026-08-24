from __future__ import annotations

import hashlib
import html as html_module
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

WEB_BASE = "https://www.algodonales.es"
TABLON_URL = f"{WEB_BASE}/tablondeanuncios"
SEDE_BASE = "https://sede.algodonales.es"
EDICTOS_URL = f"{SEDE_BASE}/edictos/publico?idOrgan=6"
TABLON_SEDE_URL = f"{SEDE_BASE}/tablon-electronico-de-anuncios-y-edictos"
TRANSPARENCIA_URL = (
    "https://gobiernoabierto.dipucadiz.es/catalogo-de-informacion-publica?entidadId=2101"
)
POLIGONO_URL = f"{WEB_BASE}/poligono-industrial/"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Algodonales"
ID_PREFIX = "algodonales"

RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td>(\d{2}/\d{2}/\d{4})</td>\s*"
    r"<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*"
    r'<td><a[^>]+href="([^"]+)"',
    re.I | re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura|apertura de local|"
    r"informaci[oó]n p[uú]blica|calificaci[oó]n.*actividad|actividad econ[oó]mica|"
    r"construcci[oó]n de (?:nave|campamento)|planta solar|tienda de venta|"
    r"estaci[oó]n de servicio|bar con m[uú]sica|comercio de elaboraci[oó]n|"
    r"reforma para|ocupaci[oó]n de v[ií]a)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|cerros y cimas|sierra de lijar|ue-\d|"
    r"pol[ií]gono industrial|cabezadas|convenio urban)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|concurso-oposici|empleo|nombramiento|padr[oó]n|"
    r"iae|cobranza|subvencion|funcionario|interino|bolsa de trabajo|polic[ií]a local|"
    r"tribunal de selecci[oó]n|baremaci[oó]n|bases convocatoria|acta:|bando:|"
    r"recogida de (?:residuos|basura|enseres)|regulaci[oó]n de tr[aá]fico|"
    r"encargado de obras|pe[oó]n obras|feria|caseta|dni|pasaporte|"
    r"concesi[oó]n administrativa.*bar hogar|gesti[oó]n de barra|licitaci[oó]n cafeter)",
)
RE_EDICTO_NON_URBAN = RE_TABLON_NON_URBAN
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_TRAMITE_URBAN = re.compile(
    r"(?i)(declaraci[oó]n responsable.*obra|licencia|obra|urban|actividad econ[oó]mica|apertura)",
)


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


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "modificaci" in b and "puntual" in b:
        return "modificación puntual PGOU"
    if "cerros y cimas" in b:
        return "modificación puntual PGOU"
    if "sierra de lijar" in b:
        return "modificación puntual PGOU"
    if "convenio urban" in b:
        return "convenio urbanístico"
    if "reparcel" in b:
        return "reparcelación"
    if "estudio ambiental" in b:
        return "estudio ambiental estratégico"
    if "pol[ií]gono industrial" in b or "poligono industrial" in b:
        return "polígono industrial"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "planta solar" in b:
        return "instalación solar"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class AlgodonalesAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla web (tablón HTML) + sede Liferay ecadiz (EPICSA idOrgan=6 vacío) + SITUA PGOU."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.edictos_url = str(self.config.get("edictos_url") or EDICTOS_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "Mozilla/5.0 (compatible; poc-bocm-algodonales/1.0)",
                ),
            },
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        href = unescape(html_module.unescape(href.replace("&amp;", "&")))
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _abs_sede(self, href: str) -> str:
        href = unescape(html_module.unescape(href.replace("&amp;", "&")))
        return urllib.parse.urljoin(f"{self.sede_base}/", href)

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TABLON_ROW.finditer(html):
            pub, ini, fin, title, href = m.groups()
            title = _strip_html(title)
            url = self._abs_web(href)
            key = url
            if key in seen:
                continue
            seen.add(key)
            blob = f"{title} {pub} {ini} {fin}"
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _parse_fecha_dmy(pub),
                    "fecha_ini": _parse_fecha_dmy(ini) if ini.strip() else None,
                    "fecha_fin": _parse_fecha_dmy(fin) if fin.strip() else None,
                    "url": url,
                    "blob": blob,
                    "origen": "web_tablon",
                }
            )
        return rows

    def _collect_edictos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.edictos_url)
        except urllib.error.URLError:
            return []

        parts = re.split(r"publico\.action[^\"]*codigo=(\d{4}-\d+)", html)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for i in range(1, len(parts), 2):
            codigo = parts[i]
            if codigo in seen:
                continue
            seen.add(codigo)

            before = parts[i - 1][-2500:]
            chunk = unescape(re.sub(r"<[^>]+>", " ", before))
            chunk = re.sub(r"\s+", " ", chunk).strip()
            dates = re.findall(r"\d{2}/\d{2}/\d{4}", chunk)
            pub = dates[-2] if len(dates) >= 2 else (dates[-1] if dates else None)
            end = dates[-1] if len(dates) >= 2 else None
            title = chunk
            if end:
                idx = title.rfind(end)
                title = title[idx + len(end) :].strip()
            title = re.sub(r"\s*<a href.*$", "", title).strip()

            rows.append(
                {
                    "codigo": codigo,
                    "titulo": title[:500],
                    "fecha": _parse_fecha_dmy(pub or ""),
                    "url": f"{self.sede_base}/edictos/edicto/publico.action?codigo={codigo}",
                    "blob": f"{title} {codigo}",
                    "origen": "edictos_epicsa",
                }
            )
        return rows

    def _collect_tramites_urbanismo(self) -> list[dict[str, Any]]:
        url = f"{self.sede_base}/tramites-disponibles"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []

        text = html_module.unescape(html)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in re.finditer(
            r"detalle-tramite\?tramite=(\d+)[^\"]*\"[^>]*>([^<]+)",
            text,
            re.I,
        ):
            tramite_id, label = m.group(1), _strip_html(m.group(2))
            if not RE_TRAMITE_URBAN.search(label):
                continue
            tramite_url = f"{self.sede_base}/group/algodonales/detalle-tramite?tramite={tramite_id}"
            if tramite_url in seen:
                continue
            seen.add(tramite_url)
            rows.append(
                {
                    "url": tramite_url,
                    "titulo": label[:500],
                    "tipo": "trámite urbanismo",
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "url": SITUA_SEARCH,
                "titulo": "PGOU Algodonales — consulta SITUA (Junta de Andalucía)",
                "tipo": "PGOU",
                "fecha": "2003-12-23",
                "blob": "PGOU Algodonales planeamiento general ordenación urbanística SITUA",
                "origen": "situa",
            },
            {
                "url": POLIGONO_URL,
                "titulo": "Polígono Industrial de Algodonales — parcelas disponibles",
                "tipo": "polígono industrial",
                "fecha": None,
                "blob": "Polígono industrial urbanismo parcelas suelo",
                "origen": "web_poligono",
            },
            {
                "url": TRANSPARENCIA_URL,
                "titulo": "Catálogo de información pública — Diputación de Cádiz",
                "tipo": "transparencia",
                "fecha": None,
                "blob": "Transparencia urbanismo planeamiento Diputación Cádiz entidadId 2101",
                "origen": "transparencia",
            },
        ]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — Ayuntamiento de Algodonales",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Tablón Joomla rsnoticia con ~600 anuncios (PDFs locales)",
                "origen": "web_tablon",
            },
            {
                "id": _stable_id("lic", TABLON_SEDE_URL),
                "fecha_concesion": None,
                "tipo": "tablón electrónico sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico de anuncios y edictos (sede ecadiz)",
                "url": TABLON_SEDE_URL,
                "source": "ayuntamiento",
                "nota": "Redirige a EPICSA idOrgan=6 (sin edictos publicados al 2026-08)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/tramites-disponibles"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites disponibles — sede electrónica",
                "url": f"{self.sede_base}/tramites-disponibles",
                "source": "ayuntamiento",
                "nota": "Sin listado histórico de licencias concedidas",
                "origen": "sede_tramite",
            },
        ]

    def _is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_TABLON_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not re.search(
            r"(?i)informaci[oó]n p[uú]blica|licencia|actividad|construcci[oó]n|comercio|bar |estaci[oó]n|reforma|planta solar|tienda",
            blob,
        ):
            return None
        tipo = "licencia de actividad"
        if re.search(r"(?i)obra|construcci[oó]n|reforma|nave", blob):
            tipo = "licencia de obra"
        if re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            tipo = "información pública (licencia/actividad)"
        key = row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web_tablon",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if re.search(r"(?i)informaci[oó]n p[uú]blica", blob) and not re.search(
            r"(?i)modificaci[oó]n|convenio|reparcel|pgou|cerros|sierra|estudio ambiental|pol[ií]gono",
            blob,
        ):
            return None
        key = row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web_tablon",
        }

    def _edicto_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_EDICTO_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("codigo") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("codigo"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "edictos",
        }

    def _edicto_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_EDICTO_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("codigo") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("codigo"),
            "origen": "edictos",
        }

    def _static_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row.get("blob") or ""),
            "tipo": row.get("tipo") or _proyecto_tipo(row.get("blob") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "static",
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": row.get("tipo") or "trámite urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "sede_tramite",
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

        for item in self._collect_tramites_urbanismo():
            rec = self._tramite_to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_edictos():
            rec = self._edicto_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "web_tablon"),
            "edictos": sum(1 for r in rows if r.get("origen") == "edictos"),
            "info": sum(
                1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tramites_urbanismo():
            existing[self._tramite_to_licencia(item)["id"]] = self._tramite_to_licencia(item)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_edictos():
            rec = self._edicto_to_licencia(item)
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

        for item in self._collect_static_proyectos():
            add(self._static_to_proyecto(item))

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        for item in self._collect_edictos():
            add(self._edicto_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "web_tablon"),
            "static": sum(1 for r in rows if r.get("origen") in ("situa", "web_poligono", "transparencia")),
            "edictos": sum(1 for r in rows if r.get("origen") == "edictos"),
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
