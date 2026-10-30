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

WEB_BASE = "https://www.santperederibes.cat"
SEU_E_BASE = "https://seu-e.cat/es/web/santperederibes/govern-obert-i-transparencia"
SEDE_BASE = "https://seuelectronica.santperederibes.cat/seuelectronica"
MUNICIPIO = "Sant Pere de Ribes"
ID_PREFIX = "spr"
INE_MUN = "08231"

RPUC_MUNICI = (
    "https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    f"?reqCode=cerca&municipiSel={INE_MUN}"
)
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"

DEFAULT_WEB_SEEDS: list[str] = [
    f"{WEB_BASE}/ajuntament/informaciourbanistica/gestio-urbanistica/vigents",
    f"{WEB_BASE}/ajuntament/informaciourbanistica/gestio-urbanistica/en-tramit",
    f"{WEB_BASE}/ajuntament/informaciourbanistica/projectes/vigents",
    f"{WEB_BASE}/ajuntament/informaciourbanistica/projectes/en-tramitacio",
    f"{WEB_BASE}/ajuntament/informaciourbanistica/planejament/pgou-vigent",
    f"{WEB_BASE}/ajuntament/informaciourbanistica/planejament/modificacions-puntuals-del-pgou-vigents",
    f"{WEB_BASE}/ajuntament/informaciourbanistica/planejament/modificacions-puntuals-del-pgou-en-tramit",
    f"{WEB_BASE}/ajuntament/informaciourbanistica/planejament/paum",
    f"{WEB_BASE}/ajuntament/informaciourbanistica/planejament/pladirector",
    f"{WEB_BASE}/ajuntament/informaciourbanistica/planejament/planejament-derivat-vigent",
    f"{WEB_BASE}/ajuntament/informaciourbanistica/planejament/planejament-derivat-en-tramit",
    f"{WEB_BASE}/seuelectronica/informacio-publica/gestio-i-planejament-urbanistics",
    f"{WEB_BASE}/seuelectronica/informacio-publica/tauler-d-anuncis-i-edictes",
]

DEFAULT_SEU_E_SEEDS: list[str] = [
    f"{SEU_E_BASE}/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme",
    f"{SEU_E_BASE}/accio-de-govern-i-normativa/urbanisme/estudis-d-impacte-ambiental-i-paisatgistic",
    f"{SEU_E_BASE}/accio-de-govern-i-normativa/normativa-plans-i-programes/memories-i-documents-dels-projectes-normatius-en-curs",
    f"{SEU_E_BASE}/accio-de-govern-i-normativa/accio-de-govern-i-grups-politics/tauler-d-edictes-i-anuncis",
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (
        f"{WEB_BASE}/ajuntament/informaciourbanistica/informacio-general/cita-previa-tecnics-urbanisme",
        "Cita prèvia tècnics d'urbanisme (llicències / consultes)",
    ),
    (
        f"{SEDE_BASE}/tramits/sol-licitud-cita-tecnics-urbanisme",
        "Sol·licitud cita tècnics urbanisme (sede)",
    ),
    (
        f"{SEDE_BASE}/tramits/instancia-generica",
        "Instància genèrica (sede electrònica)",
    ),
    (
        f"{WEB_BASE}/municipi/espaipublic/obres",
        "Espai públic — obres (informació)",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|obra[s]?|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autoritzaci[oó]|edict.*obra|edict.*llic)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|pgou|paum|modificaci[oó]|reparcel|informaci[oó]n p[uú]blica|"
    r"expedient|projecte|proyecto|sector|àmbit|ambit|edict|estudi|impacte|normatiu|gesti[oó] urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(beques|llibres|covid|subvenci[oó]|festa major|ocupaci[oó].*laboral|"
    r"proc[eé]s selectiu|mercat)",
)
RE_DOC_HREF = re.compile(
    r'href="((?:https://www\.santperederibes\.cat)?/documents/[^"]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b(20\d{2})[-_](\d{2})[-_](\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _parse_fecha(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1995 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-06-01"
    return None


def _title_from_doc_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    parts = [p for p in path.rstrip("/").split("/") if p]
    for part in reversed(parts):
        if part.endswith(".pdf") or "+" in part or "%" in part:
            name = part.replace("+", " ").replace("%20", " ")
            if not re.fullmatch(r"[0-9a-f-]{36}", name, re.I):
                return _clean(name)[:500]
    return _clean(parts[-1] if parts else url)[:500]


def _doc_folder_key(url: str) -> str | None:
    path = urllib.parse.unquote(url)
    m = re.search(r"/documents/\d+/(\d+)/", path)
    return m.group(1) if m else None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pgou" in n or "pla general" in n:
        return "PGOU"
    if "paum" in n:
        return "PAUM"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "reparcel" in n:
        return "reparcelación"
    if "impacte" in n or "ambient" in n:
        return "estudio ambiental / paisaje"
    if "edict" in n:
        return "edicto"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    return "urbanismo"


class SantPereDeRibesAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay santperederibes.cat (gestió urbanística) + seu-e AOC + referencias RPUC/MUC."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = str(self.config.get("user_agent", "poc-bocm-sant-pere-de-ribes/1.0"))
        self.web_seeds = [str(u) for u in (self.config.get("web_seeds") or DEFAULT_WEB_SEEDS)]
        self.seu_e_seeds = [str(u) for u in (self.config.get("seu_e_seeds") or DEFAULT_SEU_E_SEEDS)]
        self.licencia_pages = list(self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        self.max_doc_rows_per_page = int(self.config.get("max_doc_rows_per_page", 40))
        self.fetch_timeout = float(self.config.get("fetch_timeout_s", 45))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: float | None = None) -> str | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        try:
            with self._opener.open(req, timeout=timeout or self.fetch_timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError):
            return None

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{WEB_BASE}/", unescape(href.strip()))

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>([^<]+)',
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = _clean(m.group(1))
                t = re.sub(r"\s*-\s*Ajuntament de Sant Pere de Ribes\s*$", "", t, flags=re.I)
                if t:
                    return t[:500]
        return fallback[:500]

    def _extract_document_urls(self, html: str) -> list[str]:
        text = unescape(html or "")
        out: list[str] = []
        for m in RE_DOC_HREF.finditer(text):
            out.append(self._abs_web(m.group(1)))
        for m in re.finditer(
            r"https://www\.santperederibes\.cat/documents/[^\s\"<>]+",
            text,
            re.I,
        ):
            out.append(m.group(0).rstrip(".,;)"))
        return list(dict.fromkeys(out))

    def _rows_from_html_page(self, page_url: str, html: str, *, origen: str) -> list[dict[str, Any]]:
        page_title = self._page_title(html, fallback=page_url.rstrip("/").split("/")[-1])
        blob = f"{page_title} {page_url}"
        if RE_EXCLUDE.search(blob):
            return []
        rows: list[dict[str, Any]] = []
        if RE_PROYECTO.search(blob):
            rows.append(
                {
                    "id": _stable_id("proy", page_url),
                    "municipio": MUNICIPIO,
                    "titulo": page_title,
                    "fecha": _parse_fecha(html),
                    "tipo": _proyecto_tipo(page_title),
                    "url": page_url,
                    "source": "ayuntamiento",
                    "origen": origen,
                }
            )
        seen_folders: set[str] = set()
        doc_count = 0
        for doc_url in self._extract_document_urls(html):
            if doc_count >= self.max_doc_rows_per_page:
                break
            titulo_doc = _title_from_doc_url(doc_url)
            blob_doc = f"{titulo_doc} {doc_url} {page_title}"
            if RE_EXCLUDE.search(blob_doc):
                continue
            if not RE_PROYECTO.search(blob_doc):
                continue
            folder = _doc_folder_key(doc_url) or doc_url
            if folder in seen_folders:
                continue
            seen_folders.add(folder)
            doc_count += 1
            titulo = titulo_doc if len(titulo_doc) > 8 else f"{page_title} — documentació"
            rows.append(
                {
                    "id": _stable_id("proy", f"{page_url}|{folder}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha(f"{titulo_doc} {doc_url}"),
                    "tipo": _proyecto_tipo(blob_doc),
                    "url": doc_url,
                    "source": "ayuntamiento",
                    "origen": f"{origen}_document",
                    "page_url": page_url,
                }
            )
        return rows

    def _static_planeamiento_refs(self) -> list[dict[str, Any]]:
        refs = [
            (RPUC_MUNICI, "RPUC — expedients de planejament (08231)"),
            (MUC_VISOR, "Visor MUC — cartografia urbanística (08231)"),
            (f"{WEB_BASE}/ajuntament/informaciourbanistica", "Informació urbanística — índex"),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo in refs:
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": None,
                    "tipo": "planeamiento",
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "referencia_portal",
                }
            )
        return rows

    def _sitemap_urban_pages(self) -> list[str]:
        sm_url = f"{WEB_BASE}/sitemap.xml"
        xml = self._fetch(sm_url, timeout=60)
        if not xml:
            return []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return []
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        out: list[str] = []
        for loc in root.findall(".//sm:loc", ns):
            u = (loc.text or "").strip()
            if not u or "/en/" in u:
                continue
            if not re.search(
                r"informaciourbanistica|gestio-urbanistica|planejament|projectes|edict|urbanistic",
                u,
                re.I,
            ):
                continue
            if u not in out:
                out.append(u)
        return out[:25]

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        seeds = list(dict.fromkeys(self.web_seeds + self.seu_e_seeds + self._sitemap_urban_pages()))
        for url in seeds:
            html = self._fetch(url)
            if not html:
                continue
            origen = "seu_e" if "seu-e.cat" in url else "web_liferay"
            for row in self._rows_from_html_page(url, html, origen=origen):
                by_id[row["id"]] = row
        for row in self._static_planeamiento_refs():
            by_id[row["id"]] = row
        return list(by_id.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for url, titulo in self.licencia_pages:
            by_id[_stable_id("lic", url)] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": titulo,
                "distrito": None,
                "lat": None,
                "lon": None,
                "url": url,
                "source": "ayuntamiento",
                "origen": "tramite_informativo",
            }
        for page_url in self.web_seeds[:6]:
            html = self._fetch(page_url)
            if not html:
                continue
            for doc_url in self._extract_document_urls(html):
                titulo = _title_from_doc_url(doc_url)
                if not RE_LICENCIA.search(f"{titulo} {doc_url}"):
                    continue
                rid = _stable_id("lic", doc_url)
                by_id[rid] = {
                    "id": rid,
                    "fecha_concesion": _parse_fecha(f"{titulo} {doc_url}"),
                    "tipo": titulo[:200] or "Edicto / llicència (document)",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "url": doc_url,
                    "source": "ayuntamiento",
                    "origen": "document_edicto",
                }
        return list(by_id.values())

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return {"rows": len(rows), "path": str(path)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        meta = self._write_jsonl(out_jsonl, rows)
        meta["fetched_at"] = datetime.now(timezone.utc).isoformat()
        return meta

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        meta = self._write_jsonl(out_jsonl, rows)
        meta["fetched_at"] = datetime.now(timezone.utc).isoformat()
        return meta

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
