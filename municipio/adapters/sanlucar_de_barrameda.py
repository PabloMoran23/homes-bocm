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

GMU_BASE = "https://www.gmusanlucar.es"
AYT_BASE = "https://www.sanlucardebarrameda.es"
SEDE_GMU_URL = "https://sede.sanlucardebarrameda.es/portal/entidades.do?ent_id=3&idioma=1"
SEDE_TRAMITES_URL = "https://sede.sanlucardebarrameda.es/sede/catalogoTramites.do?ent_id=3&idioma=1"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Sanlúcar de Barrameda"
ID_PREFIX = "sanlucar-de-barrameda"

DEFAULT_GMU_SEEDS: list[str] = [
    f"{GMU_BASE}/anuncios",
    f"{GMU_BASE}/planeamiento-vigente",
    f"{GMU_BASE}/indicepgou",
    f"{GMU_BASE}/indiceadaptacionpgou",
    f"{GMU_BASE}/avance",
    f"{GMU_BASE}/tramitaciones",
    f"{GMU_BASE}/sites/default/files/planeamientovigente/Planeamiento_de_desarrollo/index.html",
]

DEFAULT_AYT_SEEDS: list[str] = [
    f"{AYT_BASE}/es/content/urbanismo-y-suelo",
    f"{AYT_BASE}/es/anuncios",
]

FOOTER_NODE_IDS = frozenset({260, 262, 263})

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia apertura|actuaci[oó]n para implantaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|sup-|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|manzana|"
    r"cambio de uso|calificaci[oó]n ambiental|adaptaci[oó]n|nnss|normativa urban|"
    r"delimitaci[oó]n|unidad de suministro|taller de chapa)",
)
RE_SKIP = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"bolsa de|limpiador|administrativo|pleno|junta de gobierno|sesi[oó]n ordinaria|"
    r"elicode|caza en coto|permuta de d[ií]as|fiestas|turismo|protecci[oó]n de datos|"
    r"aviso legal|resoluci[oó]n tribunal|aspirantes|baremaci[oó]n)",
)
RE_BODY = re.compile(
    r'class="[^"]*field--name-body[^"]*"[^>]*>(.*?)</div>',
    re.I | re.S,
)
RE_GMU_NODE = re.compile(r'href="(/node/(\d+))"[^>]*(?:hreflang="es")?>([^<]+)', re.I)
RE_AYT_NODE = re.compile(
    r'href="(/es/node/(\d+))"[^>]*(?:hreflang="es")?>([^<]+)',
    re.I,
)
RE_PDF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?(?:gmusanlucar|sanlucardebarrameda)\.es)?'
    r'(?:/system/files|/sites/default/files)[^"\']+\.(?:pdf|PDF)[^"\']*)["\']',
    re.I,
)
RE_PDF_QUERY = re.compile(
    r'href=["\']((?:https?://www\.gmusanlucar\.es)?/system/files\?file=[^"\']+)["\']',
    re.I,
)
RE_TITLE = re.compile(r"<title>([^<|]+)", re.I)
RE_TIME = re.compile(r'<time[^>]+datetime="([^"]+)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:ediente)?\.?|expte\.?)\s*(?:n[ºo°.]?\s*)?(\d+[-/]\d+)")


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


def _fecha_from_iso(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return _parse_fecha_dmy(iso)


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _pdf_title(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[-1] if "file=" in url else url.split("?")[0])
    name = Path(path).stem.replace("_", " ").replace("%20", " ")
    if "file=" in url:
        name = urllib.parse.unquote(url.split("file=", 1)[-1].split("&")[0])
        name = Path(name).stem.replace("_", " ")
    return re.sub(r"\s+", " ", name).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "modificaci" in b and "pgou" in b:
        return "modificación PGOU"
    if "plan parcial" in b or " sup-" in b:
        return "plan parcial"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "calificaci" in b and "ambiental" in b:
        return "calificación ambiental"
    if "adaptaci" in b:
        return "adaptación planeamiento"
    if "memoria" in b:
        return "memoria planeamiento"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class SanlucarDeBarramedaAyuntamientoAdapter(AyuntamientoAdapter):
    """GMU Drupal 10 (tablón + planeamiento) + ayuntamiento Drupal 11 (tablón virtual) + sede GMU."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or GMU_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.gmu_base = str(self.config.get("gmu_base") or GMU_BASE).rstrip("/")
        self.ayt_base = str(self.config.get("ayt_base") or AYT_BASE).rstrip("/")
        self.sede_tramites_url = str(self.config.get("sede_tramites_url") or SEDE_TRAMITES_URL)
        self.sede_gmu_url = str(self.config.get("sede_gmu_url") or SEDE_GMU_URL)
        self.situa_url = str(self.config.get("situa_search_url") or SITUA_SEARCH)
        self.gmu_seeds = [str(u) for u in (self.config.get("gmu_seed_pages") or DEFAULT_GMU_SEEDS)]
        self.ayt_seeds = [str(u) for u in (self.config.get("ayt_seed_pages") or DEFAULT_AYT_SEEDS)]
        self.max_anuncios_pages = int(self.config.get("max_anuncios_pages", 12))
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 35))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-sanlucar-de-barrameda/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs(self, href: str, base: str) -> str:
        href = unescape(href).replace("&amp;", "&")
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return urllib.parse.urljoin(f"{base.rstrip('/')}/", href.lstrip("/"))

    def _parse_node_html(
        self, html: str, url: str, origen: str, listing_title: str | None = None
    ) -> dict[str, Any]:
        title_m = RE_TITLE.search(html)
        titulo = (listing_title or (title_m.group(1).strip() if title_m else "")).strip()
        if "|" in titulo:
            titulo = titulo.split("|", 1)[0].strip()
        time_m = RE_TIME.search(html)
        fecha = _fecha_from_iso(time_m.group(1) if time_m else None)
        body_m = RE_BODY.search(html)
        body = _strip_html(body_m.group(1) if body_m else "")[:2500]
        blob = f"{titulo} {body}".strip()
        expte_m = RE_EXPTE.search(blob)
        return {
            "titulo": titulo[:500],
            "url": url,
            "fecha": fecha or _fecha_from_blob(blob),
            "blob": blob,
            "expte": expte_m.group(1) if expte_m else None,
            "origen": origen,
        }

    def _collect_gmu_nodes(self) -> list[dict[str, Any]]:
        seen_nodes: set[int] = set()
        queue: list[tuple[str, str | None]] = []
        for seed in self.gmu_seeds:
            queue.append((seed, None))

        rows: list[dict[str, Any]] = []
        visited: set[str] = set()

        while queue and len(visited) < self.max_crawl_pages:
            page_url, list_title = queue.pop(0)
            if page_url in visited:
                continue
            visited.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            for m in RE_GMU_NODE.finditer(html):
                node_id = int(m.group(2))
                if node_id in FOOTER_NODE_IDS or node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                node_url = self._abs(m.group(1), self.gmu_base)
                queue.append((node_url, _strip_html(m.group(3))))

            if "/node/" in page_url:
                node_id = int(page_url.rstrip("/").split("/")[-1])
                if node_id not in FOOTER_NODE_IDS:
                    rows.append(self._parse_node_html(html, page_url, "gmu_node", list_title))

        return rows

    def _collect_ayto_anuncios(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for page in range(self.max_anuncios_pages):
            suffix = f"?page={page}" if page else ""
            list_url = f"{self.ayt_base}/es/anuncios{suffix}"
            try:
                html = self._fetch(list_url)
            except urllib.error.URLError:
                break
            found = 0
            for m in RE_AYT_NODE.finditer(html):
                node_id = int(m.group(2))
                if node_id in seen:
                    continue
                list_title = _strip_html(m.group(3))
                if RE_SKIP.search(list_title):
                    continue
                if not RE_PROYECTO.search(list_title) and not RE_LICENCIA.search(list_title):
                    continue
                seen.add(node_id)
                node_url = self._abs(m.group(1), self.ayt_base)
                try:
                    node_html = self._fetch(node_url)
                except urllib.error.URLError:
                    continue
                rows.append(self._parse_node_html(node_html, node_url, "ayto_anuncio", list_title))
                found += 1
            if found == 0 and page > 0:
                break
        return rows

    def _collect_pdfs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for seed in self.gmu_seeds + self.ayt_seeds:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for pat in (RE_PDF, RE_PDF_QUERY):
                for m in pat.finditer(html):
                    pdf_url = self._abs(m.group(1), self.gmu_base)
                    if pdf_url in seen:
                        continue
                    title = _pdf_title(pdf_url)
                    blob = f"{title} {pdf_url}"
                    if not RE_PROYECTO.search(blob) and "planeam" not in title.lower():
                        continue
                    seen.add(pdf_url)
                    rows.append(
                        {
                            "titulo": title[:500],
                            "url": pdf_url,
                            "fecha": _fecha_from_blob(blob),
                            "blob": blob,
                            "origen": "pdf",
                        }
                    )
        return rows

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.sede_tramites_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites GMU (sede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — Gerencia Municipal de Urbanismo",
                "url": self.sede_tramites_url,
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (registro obligatorio PJ)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.gmu_base}/tramitaciones"),
                "fecha_concesion": None,
                "tipo": "guía tramitaciones GMU",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tramitaciones urbanísticas — GMU (tabla orientativa)",
                "url": f"{self.gmu_base}/tramitaciones",
                "source": "ayuntamiento",
                "origen": "gmu_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.gmu_base}/anuncios"),
                "fecha_concesion": None,
                "tipo": "tablón anuncios GMU (45 días)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — Gerencia Municipal de Urbanismo",
                "url": f"{self.gmu_base}/anuncios",
                "source": "ayuntamiento",
                "origen": "gmu_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.ayt_base}/es/anuncios"),
                "fecha_concesion": None,
                "tipo": "tablón virtual ayuntamiento",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón virtual — Ayuntamiento de Sanlúcar de Barrameda",
                "url": f"{self.ayt_base}/es/anuncios",
                "source": "ayuntamiento",
                "origen": "ayto_tablon",
            },
        ]

    def _is_urban_row(self, row: dict[str, Any]) -> bool:
        titulo = row.get("titulo") or ""
        if RE_SKIP.search(titulo):
            return False
        blob = f"{titulo} {row.get('blob') or ''}"
        if RE_SKIP.search(blob) and not RE_PROYECTO.search(titulo) and not RE_LICENCIA.search(titulo):
            return False
        return bool(RE_PROYECTO.search(titulo) or RE_LICENCIA.search(titulo) or RE_PROYECTO.search(blob))

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_SKIP.search(blob) and not RE_LICENCIA.search(blob):
            return None
        key = row.get("expte") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / actuación publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expte"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._is_urban_row(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expte") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expte"),
            "origen": row.get("origen"),
        }

    def _situa_row(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", self.situa_url),
            "municipio": MUNICIPIO,
            "titulo": "Planeamiento general — consulta SITUA (Junta de Andalucía, INE 11032)",
            "fecha": None,
            "tipo": "planeamiento",
            "url": self.situa_url,
            "source": "ayuntamiento",
            "origen": "situa",
            "nota": "Visor regional SituaDIFusión; sin API por expediente municipal",
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

    def _collect_all_rows(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        raw: list[dict[str, Any]] = []
        raw.extend(self._collect_gmu_nodes())
        raw.extend(self._collect_ayto_anuncios())
        raw.extend(self._collect_pdfs())

        licencias: list[dict[str, Any]] = list(self._licencia_info_pages())
        proyectos: list[dict[str, Any]] = [self._situa_row()]
        seen_lic: set[str] = {r["id"] for r in licencias}
        seen_proy: set[str] = {r["id"] for r in proyectos}

        for row in raw:
            lic = self._to_licencia(row)
            if lic and lic["id"] not in seen_lic:
                seen_lic.add(lic["id"])
                licencias.append(lic)
            proy = self._to_proyecto(row)
            if proy and proy["id"] not in seen_proy:
                seen_proy.add(proy["id"])
                proyectos.append(proy)

        return licencias, proyectos

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        licencias, _ = self._collect_all_rows()
        self._write_jsonl(out_jsonl, licencias)
        return {
            "rows": len(licencias),
            "status": "ok",
            "info": sum(1 for r in licencias if r.get("origen", "").endswith("tramite") or "tablon" in r.get("origen", "")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        licencias, _ = self._collect_all_rows()
        for rec in licencias:
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": len(rows) - len(existing), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        _, proyectos = self._collect_all_rows()
        self._write_jsonl(out_jsonl, proyectos)
        return {
            "rows": len(proyectos),
            "status": "ok",
            "gmu": sum(1 for r in proyectos if r.get("origen") == "gmu_node"),
            "ayto": sum(1 for r in proyectos if r.get("origen") == "ayto_anuncio"),
            "pdf": sum(1 for r in proyectos if r.get("origen") == "pdf"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        _, proyectos = self._collect_all_rows()
        for rec in proyectos:
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "rows": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": len(rows) - len(existing), "status": "ok"}
