from __future__ import annotations

import hashlib
import json
import re
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

BASE = "https://www.valencia.es"
NSF_BASE = "https://mhv.valencia.es"
SEDE_BASE = "https://sede.valencia.es"
MUNICIPIO = "València"
ID_PREFIX = "valencia"

NSF_TRAMITE_EN_TRAMITE = (
    f"{NSF_BASE}/ayuntamiento/urbanismo2.nsf/fTramitacionBusquedaNW?"
    "ReadForm&lang=1&titulo=Instrumentos%20en%20tr%C3%A1mite&Vista=vTramitacionWebNW"
)
NSF_TRAMITE_APROBADOS = (
    f"{NSF_BASE}/ayuntamiento/urbanismo2.nsf/fTramitacionBusquedaNW?"
    "ReadForm&Vista=vTramitacionWebNW&titulo=Instrumentos%20aprobados&lang=1&estadoFinal=1"
)

PROYECTOS_URBANOS = f"{BASE}/cas/urbanismo/proyectos-urbanos"
PARTICIPACION_PUBLICA = f"{BASE}/cas/urbanismo/planes-de-participacion-publica"
SEDE_LA = f"{SEDE_BASE}/sede/registro/indexM.xhtml?lang=1&m=LA"
SEDE_UR = f"{SEDE_BASE}/sede/registro/indexM.xhtml?lang=1&m=UR"
NSF_VIEW_XML = f"{NSF_BASE}/ayuntamiento/urbanismo2.nsf/vTramitacionWebv"

RE_NSF_ITEM = re.compile(
    r'<li><a href="([^"]+)"[^>]*>\s*([^<]+)</a></li>',
    re.I,
)
RE_PROYECTO_CARD = re.compile(
    r'href="(/cas/urbanismo/proyectos-urbanos/-/content/[^"]+)"[^>]*>'
    r'.*?<span class="enlace-title">\s*([^<]+)',
    re.S | re.I,
)
RE_PARTICIPACION_LINK = re.compile(
    r'href="(/cas/urbanismo/planes-de-participacion-publica/-/content/[^"]+)"',
    re.I,
)
RE_SEDE_PROC = re.compile(
    r'href="(/sede/registro/procedimiento/[^"]+)"[^>]*>\s*([^<]+)',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_EDICTO_ITEM = re.compile(
    r'class="rotuloAnuncio"[^>]*>\s*<a href="([^"]+)"[^>]*>([^<]+)</a>\s*\((\d{1,2}/\d{1,2}/\d{4})\)',
    re.I | re.S,
)
RE_FECHA_DOCV = re.compile(
    r"Fecha publicaci[oó]n en el DOCV[^<]*</strong>\s*(?:&nbsp;)*\s*([^<\n]+)",
    re.I,
)
RE_BLOQUE_TITULO = re.compile(r'class="bloque_titulo"[^>]*>([^<]+)', re.I)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|primera ocupaci[oó]n|parcelaci[oó]n|segregaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pai|pe-|p\.e\.|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|modificaci[oó]n|estudio de detalle|"
    r"reurbaniz|supermanzana|superilla|proyecto urban)",
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


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _abs_nsf(href: str) -> str:
    return urllib.parse.urljoin(f"{NSF_BASE}/", unescape(href))


def _abs_web(href: str) -> str:
    return urllib.parse.urljoin(f"{BASE}/", unescape(href))


def _abs_sede(href: str) -> str:
    return urllib.parse.urljoin(f"{SEDE_BASE}/", unescape(href))


def _split_nsf_label(label: str) -> tuple[str | None, str]:
    label = _clean(label)
    m = re.match(r"^([\d/.\-\s]+)\s*-\s*(.+)$", label)
    if m:
        return _clean(m.group(1)), _clean(m.group(2))
    return None, label


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "plan especial" in n or "p.e." in n or "pe-" in n:
        return "plan especial"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "estudio de detalle" in n or "e.d." in n:
        return "estudio de detalle"
    if "pai" in n:
        return "programa actuación integrada"
    if "reparcel" in n:
        return "reparcelación"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "modificaci" in n and "catálogo" in n:
        return "modificación catálogo"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "reurbaniz" in n or "supermanzana" in n or "superilla" in n:
        return "proyecto urbano"
    if "participaci" in n:
        return "participación pública"
    return "planeamiento"


class ValenciaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay urbanismo + NSF tramitación (mhv) + sede electrónica JSF."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.fetch_detail_dates = bool(self.config.get("fetch_detail_dates", True))
        self.sede_timeout_s = int(self.config.get("sede_timeout_s", 120))

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-valencia/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _parse_nsf_list(self, html: str, *, estado: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, label in RE_NSF_ITEM.findall(html):
            expediente, titulo = _split_nsf_label(_clean(label))
            url = _abs_nsf(href)
            key = expediente or titulo
            if key.lower() in seen:
                continue
            seen.add(key.lower())
            rows.append(
                {
                    "expediente": expediente,
                    "titulo": titulo,
                    "url": url,
                    "estado": estado,
                    "blob": label,
                }
            )
        return rows

    def _parse_nsf_detail_fecha(self, url: str) -> str | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None
        m = RE_FECHA_DOCV.search(html)
        if m:
            return _parse_fecha_dmy(m.group(1))
        return _parse_fecha_dmy(html)

    def _parse_nsf_viewentries(self, navigate: str, *, estado: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        start = 1
        while True:
            url = (
                f"{NSF_VIEW_XML}?ReadViewEntries&Start={start}&Count=200"
                f"&Navigate={navigate}"
            )
            try:
                raw = self._fetch(url)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            viewentries = root.findall("viewentry")
            if not viewentries:
                break
            for ve in viewentries:
                texts = [unescape(t.text or "") for t in ve.findall(".//text") if t.text]
                link = title = ""
                for text in texts:
                    if "OpenDocument" in text:
                        link = text.split('"')[0].replace("&amp;", "&")
                    elif "<strong>" in text:
                        title = _clean(re.sub(r"<[^>]+>", "", text))
                if not link or not title:
                    continue
                url_doc = _abs_nsf(link)
                expediente, titulo = _split_nsf_label(title)
                rows.append(
                    {
                        "expediente": expediente,
                        "titulo": titulo,
                        "url": url_doc,
                        "estado": estado,
                        "blob": title,
                    }
                )
            if len(viewentries) < 200:
                break
            start += 200
        return rows

    def _collect_nsf_tramitacion(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(item: dict[str, Any], *, fetch_date: bool) -> None:
            key = (item.get("expediente") or item["titulo"]).lower()
            if key in seen:
                return
            seen.add(key)
            if fetch_date and self.fetch_detail_dates:
                item["fecha"] = self._parse_nsf_detail_fecha(item["url"])
            rows.append(item)

        for navigate, estado in (("1.1", "en trámite"), ("4.1", "aprobado")):
            for item in self._parse_nsf_viewentries(navigate, estado=estado):
                add(item, fetch_date=False)

        for page_url, estado in (
            (NSF_TRAMITE_EN_TRAMITE, "en trámite"),
            (NSF_TRAMITE_APROBADOS, "aprobado"),
        ):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for item in self._parse_nsf_list(html, estado=estado):
                add(item, fetch_date=True)
        return rows

    def _collect_edictos(self, materia: str) -> list[dict[str, Any]]:
        url = f"{SEDE_BASE}/sede/edictos/index/materia/{materia}"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for href, title, fecha_raw in RE_EDICTO_ITEM.findall(html):
            rows.append(
                {
                    "titulo": _clean(title),
                    "url": _abs_sede(href),
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "materia": materia,
                    "blob": title,
                }
            )
        return rows

    def _collect_proyectos_urbanos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(f"{PROYECTOS_URBANOS}")
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in RE_PROYECTO_CARD.findall(html):
            url = _abs_web(href)
            title = _clean(title)
            if title.lower() in seen:
                continue
            seen.add(title.lower())
            rows.append({"titulo": title, "url": url, "tipo": "proyecto urbano"})
        return rows

    def _collect_participacion(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(PARTICIPACION_PUBLICA)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href in RE_PARTICIPACION_LINK.findall(html):
            url = _abs_web(href.split(";")[0])
            if url in seen:
                continue
            seen.add(url)
            titulo = ""
            try:
                page = self._fetch(url)
                m = RE_BLOQUE_TITULO.search(page)
                if m:
                    titulo = _clean(m.group(1))
            except urllib.error.URLError:
                pass
            if not titulo:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                uid = (qs.get("uid") or [""])[0]
                titulo = f"Participación pública {uid[:8]}" if uid else url.rsplit("/", 1)[-1]
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "tipo": "participación pública",
                }
            )
        return rows

    def _collect_sede_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for catalog_url in (SEDE_LA, SEDE_UR):
            try:
                html = self._fetch(catalog_url, timeout=self.sede_timeout_s)
            except urllib.error.URLError:
                continue
            for href, title in RE_SEDE_PROC.findall(html):
                code = href.rsplit("/", 1)[-1]
                if not (code.startswith("LA.") or code.startswith("UR.LC.")):
                    continue
                title = _clean(title)
                if not RE_LICENCIA.search(title):
                    continue
                url = _abs_sede(href)
                rec_id = _stable_id("lic", url)
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
                    }
                )
        return rows

    def _nsf_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        blob = f"{item.get('expediente') or ''} {item['titulo']} {item.get('estado') or ''}"
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item["url"],
            "source": "ayuntamiento",
            "expediente": item.get("expediente"),
            "estado_tramitacion": item.get("estado"),
        }

    def _simple_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": item.get("tipo") or _proyecto_tipo(item["titulo"]),
            "url": item["url"],
            "source": "ayuntamiento",
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
        rows = self._collect_sede_licencias()
        seen = {r["id"] for r in rows}
        for item in self._collect_edictos("LA"):
            blob = item.get("blob") or item["titulo"]
            if not RE_LICENCIA.search(blob) and "informaci" not in blob.lower():
                continue
            rec = {
                "id": _stable_id("lic", item["url"]),
                "fecha_concesion": item.get("fecha"),
                "tipo": "edicto información pública",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": item["titulo"],
                "url": item["url"],
                "source": "ayuntamiento",
                "nota": "Edicto sede materia LA (obras/actividades)",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites_edictos"}

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

    def _edicto_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        blob = item.get("blob") or item["titulo"]
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": f"edictos_{item.get('materia', 'UR')}",
        }

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        nsf_items = self._collect_nsf_tramitacion()
        for item in nsf_items:
            add(self._nsf_to_proyecto(item))
        for item in self._collect_proyectos_urbanos():
            add(self._simple_to_proyecto(item))
        for item in self._collect_participacion():
            add(self._simple_to_proyecto(item))
        for item in self._collect_edictos("UR"):
            if RE_PROYECTO.search(item.get("blob") or item["titulo"]):
                add(self._edicto_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "nsf": len(nsf_items),
            "source": "nsf_liferay_edictos",
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
