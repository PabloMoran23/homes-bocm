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

WEB_BASE = "https://www.alicante.es"
SEDE_BASE = "https://sedeelectronica.alicante.es"
PGMOA_BASE = "https://w3.alicante.es/urbanismo/pgmoa-1987"
MUNICIPIO = "Alicante"
ID_PREFIX = "alicante"

PGMOA_TIPOS_URL = f"{PGMOA_BASE}/vista_tipos.php"
SEDE_EDICTOS_URL = f"{SEDE_BASE}/edictos.php"
SEDE_RSS_URL = f"{SEDE_BASE}/rss/rss20/edictos.rss"
TRAMITES_URBANISMO_URL = f"{WEB_BASE}/es/tramites/urbanismo-y-vivienda"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/contenidos/modificaciones-del-planeamiento-tramitacion",
    f"{WEB_BASE}/es/contenidos/sometimiento-informacion-publica-mp-no-52-nueva-regulacion-alojamiento-turistico",
    f"{WEB_BASE}/es/contenidos/modificacion-puntual-no-53-del-pgmo-1987-cambio-calificacion-terrenos-ampliacion",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|inicio de obra|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|parcelaci[oó]n|segregaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmo|pgmoa|convenio|"
    r"informaci[oó]n p[uú]blica|consulta p[uú]blica|exposici[oó]n p[uú]blica|"
    r"expediente|proyecto|modificaci[oó]n|reparcel|estudio (?:de detalle|ac[uú]stico)|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|sometimiento|sector|"
    r"unidad de actuaci[oó]n|\bua\b|\bpai\b|\bpp\b|adaptaci[oó]n|agente urbanizador)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(liquidaciones tributarias|impuesto de veh[ií]culos|impuesto de actividades|"
    r"impuesto de bienes inmuebles|pruebas selectivas|junta de gobierno local|"
    r"sesi[oó]n (?:ordinaria|extraordinaria)|mercadillo|mercados|tasa por prestaci[oó]n|"
    r"anuncio de cobranza|padrones|nombramiento|convocatoria.*empleo)",
)
RE_PGMOA_ITEM = re.compile(
    r'<strong><a href="consulta\.php\?codigo=([^"]+)">([^<]+)</a></strong>\s*</dt>\s*<dd>([^<]*)</dd>',
    re.I | re.S,
)
RE_PGMOA_CATEGORY = re.compile(r"<summary>([^<]+)</summary>", re.I)
RE_EDICTO_ITEM = re.compile(
    r'<a href="documento_edicto\.php\?guid=([^"]+)"[^>]*>\s*(.*?)\s*</a>',
    re.I | re.S,
)
RE_EDICTO_PERIODO = re.compile(
    r"Per[ií]odo exposici[oó]n:\s*(\d{1,2}/\d{1,2}/\d{4})\s*al\s*(\d{1,2}/\d{1,2}/\d{4})",
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_RSS = re.compile(
    r"<pubDate>(\w{3}),\s*(\d{1,2})\s+(\w{3})\s+(\d{4})",
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_TRAMITE_LINK = re.compile(
    r'href="(/es/tramites/[^"]+)"[^>]*>([^<]{8,200})</a>',
    re.I,
)
RE_PAGE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)

RSS_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_text(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str, categoria: str = "") -> str:
    n = f"{blob} {categoria}".lower()
    if "plan parcial" in n or re.search(r"\bpp\b", n):
        return "plan parcial"
    if "adaptaci" in n and "pgmo" in n:
        return "adaptación PGMOU"
    if "unidad de actuaci" in n or re.search(r"\bua\b", n):
        return "unidad de actuación"
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual"
    if "pgmo" in n or "pgou" in n:
        return "PGMOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "reparcel" in n:
        return "reparcelación"
    if "estudio" in n and "detalle" in n:
        return "estudio de detalle"
    if "convenio" in n:
        return "convenio urbanístico"
    return "planeamiento"


class AlicanteAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal ayto + PGMOA w3 + tablón edictos sede + Guía Urbana WMS (sin geometría por expediente)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.pgmoa_base = str(self.config.get("pgmoa_base") or PGMOA_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_edicto_pages = int(self.config.get("max_edicto_pages", 8))

    def _fetch(self, url: str, *, encoding: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alicante/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = encoding or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", href)

    def _abs_pgmoa(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.pgmoa_base}/", href)

    def _collect_pgmoa(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(f"{self.pgmoa_base}/vista_tipos.php")
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        categoria = ""
        for block in html.split("<details"):
            cat_m = RE_PGMOA_CATEGORY.search(block)
            if cat_m:
                categoria = _clean(cat_m.group(1))
            for codigo, titulo, desc in RE_PGMOA_ITEM.findall(block):
                title = _clean(titulo)
                description = _clean(desc)
                if not title:
                    continue
                url = self._abs_pgmoa(f"consulta.php?codigo={urllib.parse.quote(codigo, safe='')}")
                blob = f"{title} {description} {categoria}"
                rec_id = _stable_id("proy", f"pgmoa:{codigo}")
                rows.append(
                    {
                        "id": rec_id,
                        "municipio": MUNICIPIO,
                        "titulo": title[:500],
                        "fecha": _fecha_from_text(blob),
                        "tipo": _proyecto_tipo(blob, categoria),
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "pgmoa_w3",
                        "codigo_pgmoa": codigo,
                        "categoria": categoria or None,
                        "descripcion": description[:500] or None,
                    }
                )
        return rows

    def _parse_edicto_block(self, guid: str, title: str, context: str) -> dict[str, Any] | None:
        titulo = _clean(title)
        if not titulo or RE_EXCLUDE.search(titulo):
            return None
        url = self._abs_sede(f"documento_edicto.php?guid={guid}")
        periodo = RE_EDICTO_PERIODO.search(context)
        fecha = _parse_fecha_dmy(periodo.group(1)) if periodo else None
        blob = titulo
        return {
            "titulo": titulo,
            "fecha": fecha,
            "url": url,
            "guid": guid,
            "blob": blob,
        }

    def _collect_edictos_html(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(1, self.max_edicto_pages + 1):
            url = f"{self.sede_base}/edictos.php" + (f"?pagina={page}" if page > 1 else "")
            try:
                html = self._fetch(url, encoding="iso-8859-1")
            except urllib.error.URLError:
                break
            found = 0
            for m in RE_EDICTO_ITEM.finditer(html):
                guid = m.group(1)
                if guid in seen:
                    continue
                seen.add(guid)
                start = max(0, m.start() - 200)
                end = min(len(html), m.end() + 400)
                ctx = html[start:end]
                parsed = self._parse_edicto_block(guid, m.group(2), ctx)
                if parsed:
                    rows.append(parsed)
                    found += 1
            if page > 1 and found == 0:
                break
        return rows

    def _collect_edictos_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(f"{self.sede_base}/rss/rss20/edictos.rss", encoding="iso-8859-1")
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return rows
        channel = root.find("channel")
        if channel is None:
            return rows
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            pub = item.findtext("pubDate") or ""
            guid_el = item.find("guid")
            guid = ""
            if guid_el is not None and guid_el.text:
                m = re.search(r"guid=([^&]+)", guid_el.text)
                guid = m.group(1) if m else guid_el.text
            if not title or RE_EXCLUDE.search(title):
                continue
            fecha = _parse_fecha_dmy(desc) or _parse_fecha_dmy(pub)
            if not fecha:
                rm = RE_FECHA_RSS.search(pub)
                if rm:
                    mo = RSS_MONTHS.get(rm.group(3).lower()[:3])
                    if mo:
                        try:
                            fecha = datetime(int(rm.group(4)), mo, int(rm.group(2))).strftime("%Y-%m-%d")
                        except ValueError:
                            pass
            rows.append(
                {
                    "titulo": _clean(title),
                    "fecha": fecha,
                    "url": link or self._abs_sede(f"documento_edicto.php?guid={guid}"),
                    "guid": guid,
                    "blob": f"{title} {desc}",
                }
            )
        return rows

    def _collect_edictos(self) -> list[dict[str, Any]]:
        by_guid: dict[str, dict[str, Any]] = {}
        for rec in self._collect_edictos_rss() + self._collect_edictos_html():
            key = rec.get("guid") or rec["url"]
            by_guid[key] = rec
        return list(by_guid.values())

    def _edicto_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        blob = rec.get("blob") or rec["titulo"]
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", f"edicto:{rec.get('guid') or rec['url']}"),
            "municipio": MUNICIPIO,
            "titulo": rec["titulo"][:500],
            "fecha": rec.get("fecha") or _fecha_from_text(blob),
            "tipo": _proyecto_tipo(blob),
            "url": rec["url"],
            "source": "ayuntamiento",
            "origen": "sede_edictos",
        }

    def _edicto_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        blob = rec.get("blob") or rec["titulo"]
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", f"edicto:{rec.get('guid') or rec['url']}"),
            "fecha_concesion": rec.get("fecha"),
            "tipo": "edicto licencia/obra",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": rec["titulo"][:500],
            "url": rec["url"],
            "source": "ayuntamiento",
            "origen": "sede_edictos",
        }

    def _collect_drupal_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self.seed_pages:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = ""
            for pat in (RE_H1, RE_PAGE_TITLE):
                m = pat.search(html)
                if m:
                    title = _clean(m.group(1)).split("|")[0].strip()
                    break
            if not title:
                title = url.rsplit("/", 1)[-1].replace("-", " ")
            if not RE_PROYECTO.search(title):
                continue
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": _fecha_from_text(html) or _fecha_from_text(title),
                    "tipo": _proyecto_tipo(title),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "drupal_seed",
                }
            )
        return rows

    def _collect_tramites_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(TRAMITES_URBANISMO_URL)
        except urllib.error.URLError:
            return rows
        seen: set[str] = set()
        for href, text in RE_TRAMITE_LINK.findall(html):
            titulo = _clean(text)
            if not RE_LICENCIA.search(titulo):
                continue
            url = self._abs_web(href)
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "drupal_tramites",
                    "nota": "Página informativa; no concesión publicada en tablón",
                }
            )
        return rows

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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_edictos():
            lic = self._edicto_to_licencia(rec)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        for rec in self._collect_tramites_licencias():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "edictos": sum(1 for r in rows if r.get("origen") == "sede_edictos"),
            "tramites": sum(1 for r in rows if r.get("origen") == "drupal_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats["rows"]
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_pgmoa():
            add(rec)
        for raw in self._collect_edictos():
            proy = self._edicto_to_proyecto(raw)
            if proy:
                add(proy)
        for rec in self._collect_drupal_seeds():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pgmoa": sum(1 for r in rows if r.get("origen") == "pgmoa_w3"),
            "edictos": sum(1 for r in rows if r.get("origen") == "sede_edictos"),
            "drupal": sum(1 for r in rows if r.get("origen") == "drupal_seed"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
