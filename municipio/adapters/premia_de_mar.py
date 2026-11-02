from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records
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

WEB_BASE = "https://premiademar.cat"
SEU_E_BASE = "https://seu-e.cat/ca/web/premiademar/govern-obert-i-transparencia"
MUNICIPIO = "Premià de Mar"
ID_PREFIX = "premia-de-mar"
INE_MUN = "08172"

PLANEJAMENT_URL = (
    f"{SEU_E_BASE}/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic"
)
NORMATIVA_URL = (
    f"{SEU_E_BASE}/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme"
)
INFO_GEO_URL = (
    f"{SEU_E_BASE}/accio-de-govern-i-normativa/urbanisme/informacio-geografica-d-urbanisme"
)
URBANISME_INDEX = f"{SEU_E_BASE}/accio-de-govern-i-normativa/urbanisme"
TAULER_EDICTES = (
    f"{SEU_E_BASE}/accio-de-govern-i-normativa/accio-de-govern-i-grups-politics/"
    "tauler-d-edictes-i-anuncis"
)
TRAMITS_URBANISME = "https://seu-e.cat/ca/web/premiademar/tramits-i-gestions/-/tramits/classificacio/urbanisme"
TRAMITS_TOTS = "https://seu-e.cat/ca/web/premiademar/tramits-i-gestions/-/tramits/tots"

RPUC_MUNICI = (
    "https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    f"?reqCode=cerca&municipiSel={INE_MUN}"
)
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
CITYMAP_VISOR = (
    "https://citymap.tecnogeows.com/user/101686710051132607418/map/"
    "6rj3V3dnqKpjfnhNtxynou?tree=stage"
)
OVAC_VISOR_IT = (
    "https://www.epremia.net/ovac/catala/VisorITs/"
    "24891A1DA10F4DF6B76E636E84F11358.asp"
)

DEFAULT_WEB_SEEDS: list[str] = [
    f"{WEB_BASE}/urbanisme-espai-public",
    f"{WEB_BASE}/organisme.php?id=173",
    f"{WEB_BASE}/organisme.php?id=134",
    f"{WEB_BASE}/document.php?id=13517",
    f"{WEB_BASE}/organisme.php?id=170",
]

DEFAULT_PROYECTO_SEEDS: list[str] = [
    PLANEJAMENT_URL,
    NORMATIVA_URL,
    INFO_GEO_URL,
    URBANISME_INDEX,
    TAULER_EDICTES,
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (f"{WEB_BASE}/ovac", "OVAC — tràmits en línia (Premià de Mar)"),
    (f"{WEB_BASE}/oac", "OAC — oficines d'atenció ciutadana (urbanisme)"),
    (f"{WEB_BASE}/organisme.php?id=169", "Llicències i tràmits — regidoria d'urbanisme"),
    (NORMATIVA_URL, "Normativa d'urbanisme (seu-e)"),
]

RE_TRAMIT_ITEM = re.compile(
    r"cataleg-tramits-item.*?href=\"([^\"]+/tramit/\d+)[^\"]*\"[^>]*>\s*([^<]{8,})",
    re.I | re.S,
)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_AMPLE_DOC = re.compile(
    r"href=['\"]document\.php\?id=(\d+)['\"][^>]*>(.*?)</a>",
    re.I | re.S,
)
RE_AMPLE_PDF = re.compile(
    r"href=['\"](ARXIUS[^'\"]+\.pdf)['\"][^>]*>(.*?)</a>",
    re.I | re.S,
)
RE_GENERIC_DOC_TITLE = re.compile(
    r"(?i)^(avisos i anuncis vigents|notes de premsa|ajuntament|regidoria|"
    r"ple municipal|error 404)",
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"primera ocupaci[oó]|obra|canvi d.?ús|informe urban|declaraci[oó] responsable)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|pgou|poum|normativa urban|edict|informaci[oó]n p[uú]blica|"
    r"expedient|habitatge|projecte|proyecto|aprovaci[oó]|avantprojecte|modificaci[oó]|"
    r"gesti[oó] urban|reurban|illa de vianants|aparcament|comissaria|visor|muc|rpuc)",
)
RE_SKIP_TEXT = re.compile(
    r"(?i)(protecci[oó] de dades|e-fact|factures electr|pol[ií]tica de protecci|"
    r"procediment d.inscripci[oó].*entitat|cr[eè]dits|subvenci[oó])",
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_TITOL_INTERIOR = re.compile(r"id=['\"]titol_interior['\"][^>]*><span>([^<]+)", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1995 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-06-01"
    return None


def _proyecto_tipo(text: str) -> str:
    n = (text or "").lower()
    if "avantprojecte" in n or "avantproyecto" in n:
        return "avantproyecto / proyecto"
    if "aprovaci" in n and "definitiva" in n:
        return "aprobación definitiva"
    if "edict" in n or "anunci" in n:
        return "edicto / anuncio"
    if "normativa" in n:
        return "normativa urbanística"
    if "illa" in n and "vianant" in n:
        return "ordenación vial / urbanismo"
    if "planej" in n or "poum" in n or "pgou" in n or "muc" in n or "rpuc" in n:
        return "planeamiento"
    return "urbanismo"


class PremiaDeMarAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Ample24 (premiademar.cat) + seu-e AOC + referencias MUC/RPUC/TecnoGeoWS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = str(self.config.get("user_agent", "poc-bocm-premia-de-mar/1.0"))
        self.web_seeds = [str(u) for u in (self.config.get("web_seeds") or DEFAULT_WEB_SEEDS)]
        self.proyecto_seeds = [str(u) for u in (self.config.get("proyecto_seeds") or DEFAULT_PROYECTO_SEEDS)]
        self.licencia_pages = list(self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        self.fetch_timeout = float(self.config.get("fetch_timeout_s", 60))
        self.enrich_documents = bool(self.config.get("enrich_documents", True))

    def _fetch(self, url: str, *, encoding: str | None = None) -> str | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        try:
            with urllib.request.urlopen(req, timeout=self.fetch_timeout) as resp:
                raw = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError, ValueError):
            return None
        if encoding:
            return raw.decode(encoding, errors="replace")
        try:
            return raw.decode("utf-8", errors="replace")
        except ValueError:
            return raw.decode("iso-8859-1", errors="replace")

    def _fetch_web(self, url: str) -> str | None:
        return self._fetch(url, encoding="iso-8859-1")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{WEB_BASE}/", unescape(href))

    def _document_title(self, doc_id: str, fallback: str) -> str:
        titulo = _strip_html(fallback)
        if titulo and not RE_GENERIC_DOC_TITLE.match(titulo):
            return titulo[:500]
        if not self.enrich_documents:
            return titulo[:500] or f"Document {doc_id}"
        html = self._fetch_web(f"{WEB_BASE}/document.php?id={doc_id}")
        if not html:
            return titulo[:500] or f"Document {doc_id}"
        m = RE_TITOL_INTERIOR.search(html)
        if m:
            enriched = _strip_html(m.group(1))
            if enriched and not RE_GENERIC_DOC_TITLE.match(enriched):
                return enriched[:500]
        return titulo[:500] or f"Document {doc_id}"

    def _parse_ample24_page(self, page_url: str, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_AMPLE_DOC.finditer(html):
            doc_id = m.group(1)
            if doc_id in seen:
                continue
            seen.add(doc_id)
            link_text = _strip_html(m.group(2))
            if RE_SKIP_TEXT.search(link_text):
                continue
            if not RE_PROYECTO.search(link_text):
                continue
            titulo = self._document_title(doc_id, link_text)
            if RE_SKIP_TEXT.search(titulo):
                continue
            url = f"{WEB_BASE}/document.php?id={doc_id}"
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": _parse_fecha(f"{link_text} {titulo}"),
                    "tipo": _proyecto_tipo(titulo),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "ample24_web",
                }
            )

        for m in RE_AMPLE_PDF.finditer(html):
            href = unescape(m.group(1))
            link_text = _strip_html(m.group(2))
            if RE_SKIP_TEXT.search(link_text):
                continue
            if not RE_PROYECTO.search(link_text):
                continue
            url = self._abs_web(href)
            titulo = link_text[:500]
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": _parse_fecha(titulo),
                    "tipo": _proyecto_tipo(titulo),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "ample24_pdf",
                }
            )
        return rows

    def _tramits_from_html(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_TRAMIT_ITEM.finditer(html):
            url = unescape(m.group(1).split("?")[0])
            titulo = unescape(re.sub(r"\s+", " ", m.group(2))).strip()
            if not RE_LICENCIA.search(titulo):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": titulo[:250],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": origen,
                }
            )
        return rows

    def _paragraph_proyectos(self, url: str, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in re.finditer(r"<p>(.*?)</p>", html, re.I | re.S):
            text = _strip_html(m.group(1))
            if len(text) < 35 or RE_SKIP_TEXT.search(text):
                continue
            if text.startswith("http") and " " not in text.strip():
                continue
            if not RE_PROYECTO.search(text) and "Pla general" not in text and "Pla d'Ordenació" not in text:
                continue
            titulo = text[:500]
            rows.append(
                {
                    "id": _stable_id("proy", f"{url}|{titulo[:120]}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": _parse_fecha(text),
                    "tipo": _proyecto_tipo(titulo),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "seu_e_paragraph",
                }
            )
        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if title_m:
            page_title = _strip_html(title_m.group(1)).split(" - ")[0].strip()
            if page_title and RE_PROYECTO.search(page_title) and len(page_title) > 8:
                rows.append(
                    {
                        "id": _stable_id("proy", url),
                        "municipio": MUNICIPIO,
                        "titulo": page_title,
                        "fecha": None,
                        "tipo": _proyecto_tipo(page_title),
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "seu_e_page",
                    }
                )
        return rows

    def _discover_urbanisme_links(self, html: str) -> list[str]:
        found: list[str] = []
        for m in RE_HREF.finditer(html):
            href = unescape(m.group(1))
            if "/urbanisme/" not in href:
                continue
            if not href.startswith("http"):
                href = urllib.parse.urljoin(SEU_E_BASE, href)
            if "premiademar" not in href or "seu-e.cat" not in href:
                continue
            found.append(href.split("?")[0])
        return list(dict.fromkeys(found))

    def _static_refs(self) -> list[dict[str, Any]]:
        refs = [
            (PLANEJAMENT_URL, "Planejament urbanístic — transparència Premià de Mar (seu-e)"),
            (MUC_VISOR, f"Visor MUC — mapa urbanístic Catalunya (municipi {INE_MUN})"),
            (RPUC_MUNICI, f"RPUC — cerca expedients planejament (municipi {INE_MUN})"),
            (CITYMAP_VISOR, "Mapa interactiu urbanístic municipal (TecnoGeoWS citymap)"),
            (OVAC_VISOR_IT, "Visor d'informació territorial (OVAC / epremia.net)"),
            (TAULER_EDICTES, "Tauler d'edictes i anuncis — seu-e Premià de Mar"),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo in refs:
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": None,
                    "tipo": _proyecto_tipo(titulo),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "referencia_portal",
                }
            )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}

        for page in self.web_seeds:
            html = self._fetch_web(page)
            if not html:
                continue
            for row in self._parse_ample24_page(page, html):
                by_id[row["id"]] = row

        seeds = list(dict.fromkeys(self.proyecto_seeds))
        index_html = self._fetch(URBANISME_INDEX)
        if index_html:
            seeds.extend(self._discover_urbanisme_links(index_html))

        for url in seeds:
            html = self._fetch(url)
            if not html:
                continue
            for row in self._paragraph_proyectos(url, html):
                by_id[row["id"]] = row

        for row in self._static_refs():
            by_id[row["id"]] = row

        return list(by_id.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}

        for url, titulo in self.licencia_pages:
            by_id[_stable_id("lic", url)] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": titulo[:250],
                "distrito": None,
                "lat": None,
                "lon": None,
                "url": url,
                "source": "ayuntamiento",
                "origen": "tramite_informativo",
            }

        for url, origen in (
            (TRAMITS_URBANISME, "cataleg_urbanisme"),
            (TRAMITS_TOTS, "cataleg_tots"),
        ):
            html = self._fetch(url)
            if not html:
                continue
            for row in self._tramits_from_html(html, origen):
                by_id[row["id"]] = row

        html = self._fetch_web(f"{WEB_BASE}/urbanisme-espai-public")
        if html:
            for m in RE_AMPLE_DOC.finditer(html):
                link_text = _strip_html(m.group(2))
                if not RE_LICENCIA.search(link_text):
                    continue
                doc_id = m.group(1)
                url = f"{WEB_BASE}/document.php?id={doc_id}"
                by_id[_stable_id("lic", url)] = {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": _parse_fecha(link_text),
                    "tipo": self._document_title(doc_id, link_text)[:250],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "ample24_anunci",
                }

        return list(by_id.values())

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
        rows = reviewed_records(path, rows)
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
