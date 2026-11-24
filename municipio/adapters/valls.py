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
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.valls.cat"
SEU_DRUPAL = "https://seu.valls.cat"
SEU_E_BASE = "https://seu-e.cat/ca/web/valls"
MUNICIPIO = "Valls"
ID_PREFIX = "valls"
INE_MUN = "43161"
IDENS = "4316130008"

TAULER_URL = f"https://tauler.seu.cat/inici.do?idens={IDENS}"
GEOPORTAL_POUM = (
    "https://geo.valls.cat/vallsgp/?center=352977.0,4572750.5&scale=50000&thematic=tematic1"
)
WFS_URL = "https://geo.valls.cat/geoserver/wfs"
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
RPUC_MUNICI = (
    f"https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    f"?reqCode=cerca&municipiSel={INE_MUN}"
)

DEFAULT_PROYECTO_SEEDS: list[str] = [
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme",
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/"
    "urbanisme/planejament-urbanistic",
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/"
    "urbanisme/informacio-geografica-d-urbanisme",
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/"
    "urbanisme/plans-territorials-d-urbanisme",
    f"{WEB_BASE}/serveis/territori-i-habitatge/planejament",
    f"{WEB_BASE}/serveis/territori-i-habitatge/urbanisme",
    f"{SEU_DRUPAL}/poum",
]

TRAMIT_ALPHA_PAGES = "CLPI"

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (TAULER_URL, "e-TAULER — edictes i anuncis (AOC)"),
    (
        f"{SEU_DRUPAL}/content/consultes-urban%C3%ADstiques",
        "Consultes urbanístiques — seu electrònica",
    ),
    (
        f"{SEU_DRUPAL}/content/pr%C3%B2rrogues-llic%C3%A8ncies-dobres-0",
        "Pròrrogues llicències d'obres",
    ),
    (
        f"{SEU_DRUPAL}/content/certificat-urban%C3%ADstic",
        "Certificat urbanístic — sol·licitud",
    ),
    (
        "https://tramits.valls.cat/impulsa/access.do?userType=citizen",
        "Tràmits en línia — llicències (Impulsa)",
    ),
]

RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_CONTENT_LINK = re.compile(r'<a href="(/content/[^"]+)">([^<]+)</a>', re.I)
RE_TRAMIT_ITEM = re.compile(
    r"cataleg-tramits-item.*?href=\"([^\"]+/tramit/\d+)[^\"]*\"[^>]*>\s*([^<]{8,})",
    re.I | re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó] (?:pr[eè]via )?d.?obres|comunicaci[oó] d.?obres|"
    r"declaraci[oó] responsable|certificat urban|consultes urban|pr[oò]rroga.*llic|"
    r"primera ocupaci[oó]|obra (?:major|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|poum|pla general|expedient|informaci[oó] p[uú]blica|"
    r"modificaci[oó]|reparcel|qualificaci[oó]|geogr[aà]fic|visor|rpuc|gencat)",
)
RE_SKIP = re.compile(r"(?i)(no trobes útil|factcheck|apiModal)")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

WFS_GEOM_LAYERS = ("valls:sect_plan_a", "valls:qual_urb_a")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


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
    if "poum" in n or "pla general" in n:
        return "POUM / planeamiento general"
    if "pla parcial" in n or "ppu" in n:
        return "plan parcial"
    if "consulta" in n and "urban" in n:
        return "consulta urbanística"
    if "informaci" in n and "geogr" in n:
        return "información geográfica"
    if "certificat" in n and "urban" in n:
        return "certificado urbanístico"
    if "revisi" in n and "poum" in n:
        return "revisión POUM"
    return "planeamiento urbanístico"


def _norm_match(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


class VallsAyuntamientoAdapter(AyuntamientoAdapter):
    """Seu-e transparència + seu Drupal (tràmits) + GeoValls WFS (POUM); e-TAULER React (referència)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = str(self.config.get("user_agent", "poc-bocm-valls/1.0"))
        self.seu_e = str(self.config.get("seu_e_base") or SEU_E_BASE).rstrip("/")
        self.seu_drupal = str(self.config.get("seu_drupal_base") or SEU_DRUPAL).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.proyecto_seeds = [str(u) for u in (self.config.get("proyecto_seeds") or DEFAULT_PROYECTO_SEEDS)]
        self.licencia_pages = [
            tuple(x) for x in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        ]
        self.wfs_url = str(self.config.get("wfs_url") or WFS_URL)
        self.fetch_timeout = float(self.config.get("fetch_timeout_s", 60))
        self._wfs_index: list[dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        try:
            with urllib.request.urlopen(req, timeout=self.fetch_timeout) as resp:
                raw = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError, ValueError):
            return None
        text = raw.decode("utf-8", errors="replace")
        if "Just a moment" in text[:900]:
            return None
        return text

    def _fetch_json(self, url: str) -> dict[str, Any] | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        try:
            with urllib.request.urlopen(req, timeout=self.fetch_timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError, ValueError, json.JSONDecodeError):
            return None

    def _abs_seu_e(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.seu_e}/", unescape(href))

    def _abs_drupal(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.seu_drupal}/", unescape(href))

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
        rows = reviewed_records(path, rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return {"rows": len(rows), "path": str(path)}

    def _load_wfs_index(self) -> list[dict[str, Any]]:
        if self._wfs_index is not None:
            return self._wfs_index
        index: list[dict[str, Any]] = []
        for type_name in WFS_GEOM_LAYERS:
            q = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeNames": type_name,
                    "outputFormat": "application/json",
                    "srsName": "EPSG:4326",
                    "count": "200",
                }
            )
            data = self._fetch_json(f"{self.wfs_url}?{q}")
            if not data:
                continue
            for feat in data.get("features") or []:
                geom = feat.get("geometry")
                if not isinstance(geom, dict):
                    continue
                props = feat.get("properties") or {}
                label = " ".join(
                    str(props.get(k) or "")
                    for k in ("codi_ajt", "desc_ajt", "doc", "nom")
                ).strip()
                if not label:
                    continue
                index.append(
                    {
                        "label": label,
                        "norm": _norm_match(label),
                        "geom": geom,
                        "layer": type_name,
                        "doc": props.get("doc"),
                    }
                )
        self._wfs_index = index
        return index

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        norm_title = _norm_match(titulo)
        if len(norm_title) < 4:
            return None
        best: tuple[int, dict[str, Any]] | None = None
        for entry in self._load_wfs_index():
            norm = entry["norm"]
            if not norm:
                continue
            score = 0
            for token in norm.split():
                if len(token) >= 4 and token in norm_title:
                    score += len(token)
            if "ppu" in norm_title and "ppu" in norm:
                score += 8
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, entry)
        if not best or best[0] < 6:
            return None
        entry = best[1]
        q = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": entry["layer"],
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "1",
                "CQL_FILTER": f"doc='{entry.get('doc')}'" if entry.get("doc") else None,
            },
            quote_via=urllib.parse.quote,
        )
        q = re.sub(r"CQL_FILTER=None&?", "", q)
        url = f"{self.wfs_url}?{q}"
        return {
            "geom_geojson": entry["geom"],
            "geometry_crs": "EPSG:4326",
            "geometry_source": "portal_wfs",
            "geometry_source_url": url,
            "coord_source": "portal_geometry_centroid",
        }

    def _attach_geom(self, rec: dict[str, Any], geom: dict[str, Any], source_url: str, **extra: Any) -> dict[str, Any]:
        out = {
            **rec,
            "geom_geojson": geom,
            "geometry_crs": "EPSG:4326",
            "geometry_source": "portal_wfs",
            "geometry_source_url": source_url,
            "coord_source": "portal_geometry_centroid",
            **extra,
        }
        cen = geometry_centroid(geom)
        if cen:
            out.setdefault("lat", cen[0])
            out.setdefault("lon", cen[1])
        return out

    def _enrich_geometry(self, rec: dict[str, Any]) -> dict[str, Any]:
        if record_geometry(rec):
            rec.setdefault("geometry_crs", "EPSG:4326")
            return rec
        titulo = rec.get("titulo") or ""
        if re.search(r"(?i)poum|pla general|geoportal|geo\.valls", titulo):
            idx = self._load_wfs_index()
            if idx:
                return self._attach_geom(
                    rec,
                    idx[0]["geom"],
                    (
                        f"{self.wfs_url}?service=WFS&version=2.0.0&request=GetFeature"
                        f"&typeNames={idx[0]['layer']}&outputFormat=application/json&srsName=EPSG:4326&count=1"
                    ),
                    geometry_note="sector_planejament_sample",
                )
        geom_fields = self._fetch_geometry(titulo)
        if geom_fields:
            return self._attach_geom(
                rec,
                geom_fields["geom_geojson"],
                geom_fields["geometry_source_url"],
            )
        return rec

    def _paragraph_proyectos(self, url: str, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in re.finditer(r"<p>(.*?)</p>", html, re.I | re.S):
            inner = m.group(1)
            if RE_SKIP.search(inner):
                continue
            text = _strip_html(inner)
            if len(text) < 30:
                continue
            link_m = RE_HREF.search(inner)
            link = self._abs_seu_e(link_m.group(1)) if link_m else url
            if "geo.valls.cat" in link or RE_PROYECTO.search(text) or RE_PROYECTO.search(link):
                titulo = text[:500] if len(text) <= 500 else text[:497] + "..."
                if "Enllaç a Gencat" in text:
                    titulo = "Registre planejament urbanístic — enllaç RPUC (Gencat)"
                    link = RPUC_MUNICI
                if "Revisió del Poum" in text or "POUM.png" in inner:
                    titulo = "Geoportal urbanístic POUM — GeoValls"
                    link = GEOPORTAL_POUM
                rows.append(
                    {
                        "id": _stable_id("proy", f"{link}|{titulo[:80]}"),
                        "municipio": MUNICIPIO,
                        "titulo": titulo,
                        "fecha": _parse_fecha(text) or "2021-08-11",
                        "tipo": _proyecto_tipo(titulo),
                        "url": link,
                        "source": "ayuntamiento",
                        "origen": "seu_e_paragraph",
                    }
                )
        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if title_m:
            page_title = _strip_html(title_m.group(1)).split(" - ")[0].strip()
            if page_title and RE_PROYECTO.search(page_title) and "Ajuntament" not in page_title:
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
                href = self._abs_seu_e(href)
            if "valls" not in href or "seu-e.cat" not in href:
                continue
            found.append(href.split("?")[0])
        return list(dict.fromkeys(found))

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        seeds = list(dict.fromkeys(self.proyecto_seeds))
        index_html = self._fetch(f"{self.seu_e}/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme")
        if index_html:
            seeds.extend(self._discover_urbanisme_links(index_html))
        for url in seeds:
            html = self._fetch(url)
            if not html:
                continue
            for row in self._paragraph_proyectos(url, html):
                by_id[row["id"]] = self._enrich_geometry(row)
        return list(by_id.values())

    def _tramits_from_drupal_alpha(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for letter in TRAMIT_ALPHA_PAGES:
            html = self._fetch(f"{self.seu_drupal}/tramits-per-ordre-alfabetic/{letter}?page=1")
            if not html:
                continue
            for href, titulo_raw in RE_CONTENT_LINK.findall(html):
                titulo = _strip_html(titulo_raw)
                if not RE_LICENCIA.search(titulo):
                    continue
                url = self._abs_drupal(href)
                if url in seen:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": None,
                        "tipo": titulo[:250],
                        "distrito": MUNICIPIO,
                        "lat": None,
                        "lon": None,
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "seu_drupal_tramit",
                    }
                )
        return rows

    def _tramits_from_seu_e(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in (
            "/tramits-i-gestions/-/tramits/classificacio/urbanisme",
            "/tramits-i-gestions/-/tramits/tots",
        ):
            html = self._fetch(f"{self.seu_e}{path}")
            if not html:
                continue
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
                        "distrito": MUNICIPIO,
                        "lat": None,
                        "lon": None,
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "seu_e_cataleg",
                    }
                )
        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        """Tràmits informatius; reviewed_records descarta filas sense concessió publicada."""
        by_id: dict[str, dict[str, Any]] = {}
        for row in self._tramits_from_drupal_alpha() + self._tramits_from_seu_e():
            by_id[row["id"]] = row
        return list(by_id.values())

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        meta = self._write_jsonl(out_jsonl, rows)
        meta["with_geometry"] = sum(1 for r in rows if record_geometry(r))
        meta["fetched_at"] = datetime.now(timezone.utc).isoformat()
        meta["status"] = "ok"
        return meta

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        meta = self._write_jsonl(out_jsonl, rows)
        meta["fetched_at"] = datetime.now(timezone.utc).isoformat()
        meta["status"] = "ok"
        return meta

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
