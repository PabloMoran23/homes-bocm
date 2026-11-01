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

SEU_E_BASE = "https://seu-e.cat/ca/web/ripollet"
MUNICIPIO = "Ripollet"
ID_PREFIX = "ripollet"
INE_MUN = "08179"

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
TRAMITS_TOTS = f"{SEU_E_BASE}/tramits-i-gestions/-/tramits/tots"

MUC_VISOR = f"https://dtes.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
RPUC_MUNICI = (
    f"https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    f"?reqCode=cerca&municipiSel={INE_MUN}"
)
AMB_GEOPORTAL = "https://geoportalplanejament.amb.cat/AppGeoportalPlanejament2/index.html"

DEFAULT_PROYECTO_SEEDS: list[str] = [
    PLANEJAMENT_URL,
    NORMATIVA_URL,
    INFO_GEO_URL,
    URBANISME_INDEX,
    TAULER_EDICTES,
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/"
    "urbanisme/plans-territorials-d-urbanisme",
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/"
    "urbanisme/habitatge-205",
    f"{SEU_E_BASE}/govern-obert-i-transparencia/accio-de-govern-i-normativa/"
    "urbanisme/pla-local-d-habitatge-207",
]

RE_TRAMIT_ITEM = re.compile(
    r"cataleg-tramits-item.*?href=\"([^\"]+/tramit/\d+)[^\"]*\"[^>]*>\s*([^<]{8,})",
    re.I | re.S,
)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|pgou|normativa urban|edict|informaci[oó]n p[uú]blica|"
    r"expedient|habitatge|registre de planejament|mapa urban)",
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"primera ocupaci[oó]|obra|canvi d.?ús|informe urban)",
)
RE_SKIP_TEXT = re.compile(
    r"(?i)(no funciona|no se puede|error al|enlace no|link no|falta de transparencia|"
    r"geoportal no funciona|podeu consultar la informació sobre els projectes)",
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


def _title_from_path(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0].rstrip("/"))
    slug = path.split("/")[-1]
    slug = re.sub(r"-\d+$", "", slug)
    return slug.replace("-", " ").strip().title() or url


def _proyecto_tipo(text: str) -> str:
    n = (text or "").lower()
    if "habitatge" in n or "habitatge" in n:
        return "habitatge / planeamiento"
    if "edict" in n or "anunci" in n:
        return "edicto / anuncio"
    if "normativa" in n:
        return "normativa urbanística"
    if "informaci" in n and "geogr" in n:
        return "información geográfica urbanística"
    if "planej" in n or "pgou" in n or "muc" in n or "rpuc" in n or "amb" in n:
        return "planeamiento"
    return "urbanismo"


class RipolletAyuntamientoAdapter(AyuntamientoAdapter):
    """Seu-e AOC (transparència + catàleg tràmits). Web ripollet.cat 503 intermitent en cloud."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEU_E_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = str(self.config.get("user_agent", "poc-bocm-ripollet/1.0"))
        self.proyecto_seeds = [str(u) for u in (self.config.get("proyecto_seeds") or DEFAULT_PROYECTO_SEEDS)]
        self.fetch_timeout = float(self.config.get("fetch_timeout_s", 60))

    def _fetch(self, url: str) -> str | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        try:
            with urllib.request.urlopen(req, timeout=self.fetch_timeout) as resp:
                raw = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError, ValueError):
            return None
        text = raw.decode("utf-8", errors="replace")
        if "Just a moment" in text[:800]:
            return None
        return text

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
            if not RE_PROYECTO.search(text) and "Pla general" not in text:
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
            if "ripollet" not in href or "seu-e.cat" not in href:
                continue
            found.append(href.split("?")[0])
        return list(dict.fromkeys(found))

    def _static_refs(self) -> list[dict[str, Any]]:
        refs = [
            (PLANEJAMENT_URL, "Planejament urbanístic — transparència Ripollet (seu-e)"),
            (MUC_VISOR, f"Visor MUC — mapa urbanístic Catalunya (municipi {INE_MUN})"),
            (RPUC_MUNICI, f"RPUC — cerca expedients planejament (municipi {INE_MUN})"),
            (AMB_GEOPORTAL, "Geoportal planejament refós AMB (consulta classificació sòl Ripollet)"),
            (TAULER_EDICTES, "Tauler d'edictes i anuncis — seu-e Ripollet"),
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
        for url, origen in (
            (TRAMITS_URBANISME, "cataleg_urbanisme"),
            (TRAMITS_TOTS, "cataleg_tots"),
        ):
            html = self._fetch(url)
            if not html:
                continue
            for row in self._tramits_from_html(html, origen):
                by_id[row["id"]] = row

        if not by_id:
            fallback = (
                f"{SEU_E_BASE}/tramits-i-gestions/-/tramits/tramit/21039322",
                "Llicència d'obres (catàleg urbanisme seu-e)",
            )
            by_id[_stable_id("lic", fallback[0])] = {
                "id": _stable_id("lic", fallback[0]),
                "fecha_concesion": None,
                "tipo": fallback[1],
                "distrito": None,
                "lat": None,
                "lon": None,
                "url": fallback[0],
                "source": "ayuntamiento",
                "origen": "tramite_informativo",
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
