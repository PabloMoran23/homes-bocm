from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records
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
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.martorell.cat"
SEU_E_BASE = "https://seu-e.cat/ca/web/martorell"
MUNICIPIO = "Martorell"
ID_PREFIX = "martorell"
INE_MUN = "08113"

PLANEJAMENT_URL = (
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/"
    "urbanisme/planejament-urbanistic"
)
NORMATIVA_URL = (
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/"
    "urbanisme/normativa-d-urbanisme"
)
INFO_GEO_URL = (
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/"
    "urbanisme/informacio-geografica-d-urbanisme"
)
URBANISME_INDEX = (
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme"
)
TAULER_EDICTES = (
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/"
    "accio-de-govern-i-grups-politics/tauler-d-edictes-i-anuncis"
)
TRAMITS_URBANISME = f"{SEU_E_BASE}/tramits-i-gestions/-/tramits/classificacio/urbanisme"
WEB_URBANISME = f"{WEB_BASE}/ajuntament/regidories/planificacio-urbanistica.htm"
WEB_TRAMITS_OBRES = f"{WEB_BASE}/seu-electronica/tramita-amb-nosaltres.htm?fcat_221=46"
SITEMAP_URL = f"{WEB_BASE}/media/site1/sitemap.xml"
DIGITAL_SITEMAP = "https://martorelldigital.cat/sitemap.xml"

MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
RPUC_MUNICI = (
    f"https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    f"?reqCode=cerca&municipiSel={INE_MUN}"
)
WFS_BASE = "https://sig.gencat.cat/ows/PLANEJAMENT/wfs"
WFS_TYPE_SECTOR = "PLANEJAMENT:MUC_PDERIVAT_SECTOR"

DEFAULT_PROYECTO_SEEDS: list[str] = [
    PLANEJAMENT_URL,
    NORMATIVA_URL,
    INFO_GEO_URL,
    URBANISME_INDEX,
    TAULER_EDICTES,
    WEB_URBANISME,
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/"
    "urbanisme/plans-territorials-d-urbanisme",
]

DEFAULT_LICENCIA_TRAMITS: list[tuple[str, str]] = [
    (
        f"{SEU_E_BASE}/tramits-i-gestions/-/tramits/tramit/16808774",
        "Sol·licitud informe urbanístic (seu-e)",
    ),
    (
        f"{WEB_BASE}/seu-electronica/tramita-amb-nosaltres.htm?fcat_221=46",
        "Tràmits Obres i Urbanisme (web municipal iDisc)",
    ),
    (
        "https://martorell.eadministracio.cat",
        "Seu electrònica eAdministració — presentació telemàtica",
    ),
]

RE_TRAMIT_LINK = re.compile(
    r'href="([^"]+/tramit/\d+)[^"]*"[^>]*class="tramit-item-link"[^>]*>([^<]{8,})',
    re.I | re.S,
)
RE_TRAMIT_ITEM = re.compile(
    r"cataleg-tramits-item.*?href=\"([^\"]+/tramit/\d+)[^\"]*\"[^>]*>\s*([^<]{8,})",
    re.I | re.S,
)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|pgou|pgo|normativa urban|edict|informaci[oó]n p[uú]blica|"
    r"expedient|habitatge|registre de planejament|mapa urban|reurbaniz|pla parcial|"
    r"modificaci[oó].*ordenaci[oó]|agenda urbana)",
)
RE_NEWS_URBAN = re.compile(
    r"(?i)(reurbaniz|reurbanitz|pla general|planificaci[oó]|planej|pgou|pgo|pla parcial|"
    r"millora urb|modificaci[oó].*ordenaci|agenda urbana|mobilitat urbana(?!.*musica))",
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"primera ocupaci[oó]|obra|canvi d.?ús|informe urban|ocupaci[oó] via p)",
)
RE_SKIP_TEXT = re.compile(
    r"(?i)(no funciona|error al|geoportal no|podeu consultar la informació sobre els projectes)",
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


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
    if "pla parcial" in n or "plan parcial" in n:
        return "plan parcial"
    if "pla general" in n or "pgou" in n or "pgo" in n:
        return "PGOU / planeamiento general"
    if "reurbaniz" in n or "reurbanitz" in n:
        return "reurbanización"
    if "millora urb" in n:
        return "plan de mejora urbana"
    if "edict" in n or "anunci" in n:
        return "edicto / anuncio"
    if "mobilitat urb" in n:
        return "movilidad urbana"
    if "habitatge" in n:
        return "habitatge / planeamiento"
    if "normativa" in n:
        return "normativa urbanística"
    if "planej" in n or "muc" in n or "rpuc" in n:
        return "planeamiento"
    return "urbanismo"


class MartorellAyuntamientoAdapter(AyuntamientoAdapter):
    """Web iDisc martorell.cat + seu-e AOC + sectores WFS MUC Generalitat (CODI_INE 08113)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEU_E_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = str(self.config.get("user_agent", "poc-bocm-martorell/1.0"))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seu_e_base = str(self.config.get("seu_e_base") or SEU_E_BASE).rstrip("/")
        self.proyecto_seeds = [str(u) for u in (self.config.get("proyecto_seeds") or DEFAULT_PROYECTO_SEEDS)]
        self.licencia_tramites = list(self.config.get("licencia_tramites") or DEFAULT_LICENCIA_TRAMITS)
        self.fetch_timeout = float(self.config.get("fetch_timeout_s", 60))
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or WFS_BASE).rstrip("/")
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE_SECTOR)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self._wfs_browser_ua = str(
            geom_cfg.get("user_agent")
            or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self._sector_features: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, user_agent: str | None = None) -> str | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": user_agent or self.ua})
        try:
            with urllib.request.urlopen(req, timeout=self.fetch_timeout) as resp:
                raw = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError, ValueError):
            return None
        text = raw.decode("utf-8", errors="replace")
        if "Just a moment" in text[:800]:
            return None
        return text

    def _fetch_json(self, url: str) -> dict[str, Any] | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._wfs_browser_ua})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
            return None

    def _sector_wfs_url(self) -> str:
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": self.wfs_type,
            "CQL_FILTER": f"CODI_INE='{self.ine_mun}'",
            "srsName": "EPSG:4326",
            "outputFormat": "application/json",
            "count": 200,
        }
        return f"{self.wfs_base}?{urllib.parse.urlencode(params)}"

    def _load_sector_features(self) -> list[dict[str, Any]]:
        if self._sector_features is not None:
            return self._sector_features
        data = self._fetch_json(self._sector_wfs_url())
        if not data:
            self._sector_features = []
            return self._sector_features
        feats = data.get("features") or []
        self._sector_features = [f for f in feats if isinstance(f, dict)]
        return self._sector_features

    def _attach_geometry(self, rec: dict[str, Any], title: str) -> None:
        """WFS MUC 08113 devuelve polígonos fuera del término municipal IGN; solo metadatos."""

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for feat in self._load_sector_features():
            props = feat.get("properties") or {}
            titulo = _strip_html(str(props.get("NOM_PLA") or ""))[:500]
            if not titulo:
                continue
            expedient = str(props.get("EXPEDIENT") or "")
            pub = str(props.get("PUB_DOGC") or "")
            fecha = _parse_fecha(pub) or (expedient[:4] if re.match(r"^\d{4}", expedient) else None)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"wfs:{expedient}:{titulo}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": fecha,
                "tipo": _proyecto_tipo(titulo),
                "url": PLANEJAMENT_URL,
                "source": "ayuntamiento",
                "expediente": expedient,
                "estado": str(props.get("ESTAT_PLANEJAMENT") or ""),
                "origen": "wfs_muc_sector",
                "geometry_source_url": self._sector_wfs_url(),
                "nota": "Metadatos MUC; polígonos WFS fuera del término IGN (no publicados)",
            }
            rows.append(rec)
        return rows

    def _tramits_from_html(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pattern in (RE_TRAMIT_LINK, RE_TRAMIT_ITEM):
            for m in pattern.finditer(html):
                url = unescape(m.group(1).split("?")[0])
                titulo = unescape(re.sub(r"\s+", " ", m.group(2))).strip()
                if not RE_LICENCIA.search(titulo):
                    continue
                rid = _stable_id("lic", url)
                if rid in seen:
                    continue
                seen.add(rid)
                rows.append(
                    {
                        "id": rid,
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
            if not RE_PROYECTO.search(text) and "Pla general" not in text:
                continue
            titulo = text[:500]
            rec = {
                "id": _stable_id("proy", f"{url}|{titulo[:120]}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": _parse_fecha(text),
                "tipo": _proyecto_tipo(titulo),
                "url": url,
                "source": "ayuntamiento",
                "origen": "seu_e_paragraph",
            }
            self._attach_geometry(rec, titulo)
            rows.append(rec)
        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if title_m:
            page_title = _strip_html(title_m.group(1)).split(" - ")[0].strip()
            if page_title and RE_PROYECTO.search(page_title) and len(page_title) > 8:
                rec = {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": page_title,
                    "fecha": None,
                    "tipo": _proyecto_tipo(page_title),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "seu_e_page",
                }
                self._attach_geometry(rec, page_title)
                rows.append(rec)
        return rows

    def _discover_urbanisme_links(self, html: str) -> list[str]:
        found: list[str] = []
        for m in RE_HREF.finditer(html):
            href = unescape(m.group(1))
            if "/urbanisme/" not in href:
                continue
            if not href.startswith("http"):
                href = urllib.parse.urljoin(self.seu_e_base, href)
            if "martorell" not in href or "seu-e.cat" not in href:
                continue
            found.append(href.split("?")[0])
        return list(dict.fromkeys(found))

    def _news_from_sitemap(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for sm_url in (SITEMAP_URL, DIGITAL_SITEMAP):
            xml = self._fetch(sm_url, user_agent=self.ua)
            if not xml:
                continue
            try:
                root = ET.fromstring(xml)
            except ET.ParseError:
                continue
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for url_el in root.findall("sm:url", ns):
                loc = url_el.find("sm:loc", ns)
                if loc is None or not loc.text:
                    continue
                full = loc.text.strip()
                if "martorelldigital.cat" not in full and "martorell.cat" not in full:
                    continue
                slug = full.rstrip("/").split("/")[-1]
                if not RE_NEWS_URBAN.search(slug.replace("-", " ")):
                    continue
                titulo = slug.replace("-", " ").title()[:500]
                rec = {
                    "id": _stable_id("proy", full),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": _parse_fecha(slug),
                    "tipo": _proyecto_tipo(titulo),
                    "url": full,
                    "source": "ayuntamiento",
                    "origen": "noticia_web",
                }
                self._attach_geometry(rec, titulo)
                rows.append(rec)
        return rows

    def _static_refs(self) -> list[dict[str, Any]]:
        refs = [
            (PLANEJAMENT_URL, "Planejament urbanístic — transparència Martorell (seu-e)"),
            (WEB_URBANISME, "Agenda urbana i planificació urbanística (web municipal)"),
            (MUC_VISOR, f"Visor MUC — mapa urbanístic Catalunya (municipi {INE_MUN})"),
            (RPUC_MUNICI, f"RPUC — cerca expedients planejament (municipi {INE_MUN})"),
            (TAULER_EDICTES, "Tauler d'edictes i anuncis — seu-e Martorell"),
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

        for row in self._collect_wfs_proyectos():
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

        for row in self._news_from_sitemap():
            by_id[row["id"]] = row

        for row in by_id.values():
            if record_geometry(row) and not row.get("coord_source"):
                cen = geometry_centroid(record_geometry(row) or {})
                if cen:
                    row["lat"], row["lon"] = cen
                    row["coord_source"] = "portal_geometry_centroid"

        return list(by_id.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        html = self._fetch(TRAMITS_URBANISME)
        if html:
            for row in self._tramits_from_html(html, "cataleg_urbanisme"):
                by_id[row["id"]] = row

        for url, label in self.licencia_tramites:
            rid = _stable_id("lic", url)
            by_id.setdefault(
                rid,
                {
                    "id": rid,
                    "fecha_concesion": None,
                    "tipo": label,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                },
            )
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
        meta["wfs_sectors"] = len(self._load_sector_features())
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
