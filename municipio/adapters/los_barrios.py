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

WP_BASE = "https://losbarrios.es"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
SEDE_BASE = "https://losbarrios.sedelectronica.es"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Los Barrios"
ID_PREFIX = "los-barrios"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/portal-de-transparencia/urbanismo/",
    f"{WP_BASE}/portal-de-transparencia/proyectos-de-urbanismo/",
    f"{WP_BASE}/portal-de-transparencia/planeamiento-estudio-de-detalles/",
    f"{WP_BASE}/portal-de-transparencia/otros-tramites-en-informacion-publica/",
    f"{WP_BASE}/portal-de-transparencia/urbanismo-obras-publicas-y-medio-ambiental/plan-general-de-ordenacion-urbana-pgou/",
    f"{WP_BASE}/portal-de-transparencia/urbanismo-obras-publicas-y-medio-ambiental/",
    f"{WP_BASE}/el-consistorio/servicios-publicos-basicos/urbanismo/",
    f"{WP_BASE}/el-consistorio/servicios-publicos-basicos/urbanismo/proyectos-de-urbanismo/",
    f"{WP_BASE}/el-consistorio/servicios-publicos-basicos/urbanismo/plan-general-de-ordenacion-urbanistica-de-los-barrios/",
    f"{WP_BASE}/el-consistorio/servicios-publicos-basicos/urbanismo/tramitacion-de-la-delegacion-de-urbanismo/",
]

WP_SEARCH_TERMS: tuple[str, ...] = (
    "planeamiento",
    "pgou",
    "urbanismo",
    "estudio de detalle",
    "informacion publica",
    "reparcelacion",
    "licencia apertura",
    "modificacion puntual",
    "plan parcial",
    "actuacion extraordinaria",
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|lap\s*\d|licencia de apertura)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|innovaci[oó]n|avance|revisi[oó]n|"
    r"\b(?:API|SUS|SUNS|MRC)-[\w\d-]+\b|guadacorte|pmvs|plan municipal de vivienda|"
    r"delimitaci[oó]n del [áa]mbito|junta de compensaci[oó]n|entidad urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|padr[oó]n|bolsa de trabajo|subvenci[oó]n deportiv|"
    r"proceso selectivo|proyecto los barrios emplea|proyecto plan activa|"
    r"proyecto los barrios avanz|proyecto los barrios insert|acoso laboral|"
    r"elecci[oó]n de juez|ordenanza.*playa|piscina cubierta|ayudas escolares|"
    r"fiestas|navidad|mercadillo|consulta popular|encuesta)",
)
RE_PDF_HREF = re.compile(
    r'href=["\']([^"\']+\.(?:pdf|PDF|odt|ODT)[^"\']*)["\']',
    re.I,
)
RE_LINK_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)


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


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


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
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan parcial" in b or re.search(r"\bsus[-\s]?\d", b):
        return "plan parcial"
    if "estudio de detalle" in b or re.search(r"\bapi[-\s]?\d", b):
        return "estudio de detalle"
    if "reparcel" in b:
        return "reparcelación"
    if "modificaci" in b or "innovaci" in b:
        return "modificación planeamiento"
    if "plan municipal de vivienda" in b or "pmvs" in b:
        return "plan municipal vivienda y suelo"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "junta de compensaci" in b or "entidad urban" in b:
        return "entidad urbanística"
    if "actuaci" in b and "extraordinaria" in b:
        return "actuación extraordinaria"
    if "delimitaci" in b and "mbito" in b:
        return "delimitación ámbito"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class LosBarriosAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress transparencia (REST API + crawl semillas) + SITUA referencia PGOU."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.wp_api = str(self.config.get("wp_api") or WP_API).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-los-barrios/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.wp_base}/", href))

    def _is_urban_blob(self, blob: str) -> bool:
        if RE_EXCLUDE.search(blob):
            return False
        return bool(RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob))

    def _collect_wp_pages_search(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        for term in WP_SEARCH_TERMS:
            url = (
                f"{self.wp_api}/pages"
                f"?search={urllib.parse.quote(term)}&per_page=100"
                f"&_fields=id,date,link,title,content,slug"
            )
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(data, list):
                continue
            for page in data:
                pid = int(page.get("id") or 0)
                if pid in seen_ids:
                    continue
                title = _strip_html((page.get("title") or {}).get("rendered", ""))
                content = (page.get("content") or {}).get("rendered", "") or ""
                slug = str(page.get("slug") or "")
                blob = f"{title} {slug} {content}"
                if not self._is_urban_blob(blob):
                    continue
                seen_ids.add(pid)
                rows.append(
                    {
                        "page_id": pid,
                        "titulo": title[:500],
                        "fecha": _iso_date_wp(str(page.get("date") or "")),
                        "url": str(page.get("link") or ""),
                        "content": content,
                        "slug": slug,
                        "blob": blob,
                        "origen": f"wp_search_{term.replace(' ', '_')}",
                    }
                )
        return rows

    def _parse_page_content(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        content = item.get("content") or ""
        page_url = item.get("url") or ""
        title = item.get("titulo") or ""
        fecha = item.get("fecha")

        seen_urls: set[str] = set()
        for m in RE_PDF_HREF.finditer(content):
            href = self._abs_url(m.group(1))
            if href in seen_urls:
                continue
            seen_urls.add(href)
            name = unescape(Path(urllib.parse.urlparse(href).path).name)
            blob = f"{title} {name} {href}"
            if RE_EXCLUDE.search(blob):
                continue
            if not self._is_urban_blob(blob) and not RE_PROYECTO.search(title):
                continue
            rows.append(
                {
                    "titulo": f"{title} — {name}"[:500] if name else title[:500],
                    "fecha": fecha or _fecha_from_blob(href),
                    "url": page_url,
                    "pdf_url": href,
                    "blob": blob,
                    "origen": item.get("origen", "wp_page"),
                }
            )

        for m in RE_LINK_HREF.finditer(content):
            href = m.group(1)
            if "drive.google.com" not in href and "dropbox.com" not in href:
                continue
            abs_href = href if href.startswith("http") else self._abs_url(href)
            if abs_href in seen_urls:
                continue
            seen_urls.add(abs_href)
            blob = f"{title} {abs_href}"
            if not self._is_urban_blob(blob):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": page_url,
                    "doc_url": abs_href,
                    "blob": blob,
                    "origen": item.get("origen", "wp_page"),
                }
            )

        if not rows and self._is_urban_blob(f"{title} {item.get('slug', '')}"):
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": page_url,
                    "blob": f"{title} {item.get('slug', '')}",
                    "origen": item.get("origen", "wp_page"),
                }
            )
        return rows

    def _collect_seed_links(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for m in RE_LINK_HREF.finditer(html):
                href = m.group(1)
                if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                    continue
                abs_url = self._abs_url(href)
                if abs_url in seen:
                    continue
                if "losbarrios.es" not in abs_url:
                    continue
                if not any(
                    k in abs_url.lower()
                    for k in (
                        "transparencia",
                        "urbanismo",
                        "planeamiento",
                        "pgou",
                        "aprobacion",
                        "estudio",
                        "reparcel",
                        "licencia",
                        "informacion-publica",
                    )
                ):
                    continue
                seen.add(abs_url)
                rows.append({"url": abs_url, "origen": "seed_link"})

            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(Path(urllib.parse.urlparse(pdf).path).name)
                blob = f"{name} {pdf} {seed}"
                if RE_EXCLUDE.search(blob):
                    continue
                if not self._is_urban_blob(blob):
                    continue
                rows.append(
                    {
                        "titulo": name[:500],
                        "fecha": _fecha_from_blob(pdf),
                        "url": seed,
                        "pdf_url": pdf,
                        "blob": blob,
                        "origen": "seed_pdf",
                    }
                )
        return rows

    def _resolve_seed_pages(self, links: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for link in links:
            if link.get("pdf_url") or link.get("titulo"):
                rows.append(link)
                continue
            page_url = link.get("url") or ""
            if not page_url:
                continue
            slug = urllib.parse.urlparse(page_url).path.strip("/").split("/")[-1]
            api_url = f"{self.wp_api}/pages?slug={urllib.parse.quote(slug)}&_fields=id,date,link,title,content,slug"
            try:
                data = self._fetch_json(api_url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(data, list) or not data:
                continue
            page = data[0]
            title = _strip_html((page.get("title") or {}).get("rendered", ""))
            content = (page.get("content") or {}).get("rendered", "") or ""
            blob = f"{title} {slug} {content}"
            if not self._is_urban_blob(blob):
                continue
            item = {
                "titulo": title[:500],
                "fecha": _iso_date_wp(str(page.get("date") or "")),
                "url": str(page.get("link") or page_url),
                "content": content,
                "slug": slug,
                "blob": blob,
                "origen": link.get("origen", "seed_resolved"),
            }
            rows.extend(self._parse_page_content(item))
            if not any(r.get("url") == item["url"] for r in rows):
                rows.append(item)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", f"{self.wp_base}/el-consistorio/servicios-publicos-basicos/urbanismo/tramitacion-de-la-delegacion-de-urbanismo/"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tramitación de la delegación de Urbanismo",
                "url": f"{self.wp_base}/el-consistorio/servicios-publicos-basicos/urbanismo/tramitacion-de-la-delegacion-de-urbanismo/",
                "source": "ayuntamiento",
                "nota": "Información trámites licencias; sin listado histórico de concesiones",
                "origen": "web_tramites",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/"),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — licencias y comunicaciones previas",
                "url": f"{self.sede_base}/",
                "source": "ayuntamiento",
                "nota": "Sede espublico no operativa (página indeterminada); trámites solo presenciales/ventanilla",
                "origen": "sede_inactiva",
            },
            {
                "id": _stable_id("lic", f"{self.wp_base}/ventanilla-unica/"),
                "fecha_concesion": None,
                "tipo": "ventanilla única",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ventanilla única — trámites urbanismo",
                "url": f"{self.wp_base}/ventanilla-unica/",
                "source": "ayuntamiento",
                "nota": "Punto de atención presencial; sin dataset de licencias publicadas",
                "origen": "web_ventanilla",
            },
        ]

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not self._is_urban_blob(blob) and not RE_PROYECTO.search(item.get("titulo") or ""):
            return None
        key = item.get("pdf_url") or item.get("doc_url") or item.get("url") or item.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        if item.get("doc_url"):
            rec["doc_url"] = item["doc_url"]
        return rec

    def _item_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_EXCLUDE.search(blob):
            return None
        key = item.get("pdf_url") or item.get("url") or item.get("titulo", "")
        tipo = "licencia de apertura"
        if re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        if re.search(r"(?i)actividad", blob):
            tipo = "licencia de actividad"
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": item.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"],
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
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

        raw_items: list[dict[str, Any]] = []
        for page in self._collect_wp_pages_search():
            raw_items.extend(self._parse_page_content(page))
            raw_items.append(page)
        raw_items.extend(self._resolve_seed_pages(self._collect_seed_links()))

        for item in raw_items:
            rec = self._item_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": sum(1 for r in rows if r.get("origen", "").startswith(("web_", "sede_")))}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        raw_items: list[dict[str, Any]] = []
        for page in self._collect_wp_pages_search():
            raw_items.extend(self._parse_page_content(page))
            raw_items.append(page)
        raw_items.extend(self._resolve_seed_pages(self._collect_seed_links()))

        for item in raw_items:
            add(self._item_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Los Barrios — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": "Visor regional de planeamiento digitalizado; sin geometría por expediente municipal",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_pages": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
            "pdfs": sum(1 for r in rows if r.get("pdf_url")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
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
