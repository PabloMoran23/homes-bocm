from __future__ import annotations

import hashlib
import html as htmlmod
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

BASE = "https://calafell.cat"
SEU_E = "https://seu-e.cat/es/web/calafell"
MUNICIPIO = "Calafell"
ID_PREFIX = "calafell"
INE_MUN = "43037"

REGISTRE_GESTIO = f"{BASE}/temes-i-serveis/planejament/registre-gestio"
PLANEJAMENT_TRAMIT = f"{BASE}/temes-i-serveis/planejament/planejament-en-tramit"

RPUC_MUNICI = (
    "https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    f"?reqCode=cerca&municipiSel={INE_MUN}"
)
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
MAPA_INTERACTIU = (
    "https://citymap.tecnogeows.com/user/100753368952665604653/map/HnBDG6PffNgJTR7bo6JTKc"
)
SEU_URBANISME = (
    f"{SEU_E}/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme"
)

DEFAULT_SEED_PAGES: tuple[str, ...] = (
    REGISTRE_GESTIO,
    PLANEJAMENT_TRAMIT,
    f"{BASE}/temes-i-serveis/planejament/poum",
)

DEFAULT_LICENCIA_PAGES: tuple[tuple[str, str], ...] = (
    (
        "https://seu-e.cat/tramits/4303790004/comunicacio-certificat-projecte",
        "Comunicació d'inici d'activitat amb projecte tècnic (seu-e)",
    ),
    (
        "https://seu-e.cat/tramits/4303790004/comunicacio-certificat",
        "Comunicació d'inici d'activitat amb certificat tècnic (seu-e)",
    ),
    (
        "https://seu-e.cat/es/web/calafell/tramits-i-gestions",
        "Tràmits i gestions — seu electrònica Calafell",
    ),
    (
        f"{SEU_E}/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme",
        "Normativa d'urbanisme i mapa interactiu (transparència)",
    ),
)

RE_EXPAND_BLOCK = re.compile(
    r"expand-box expand-box--expandable\">(.*?)</div>\s*</div>\s*</div>",
    re.S | re.I,
)
RE_EXPAND_HEADING = re.compile(
    r'expand-box__heading">(.*?)</h2>',
    re.S | re.I,
)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/sites/default/files/(\d{4})-(\d{2})/")
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|obra|comunicaci[oó]n previa|declaraci[oó] responsable|"
    r"suspensi[oó].*llic)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    t = unescape(htmlmod.unescape(text or ""))
    return re.sub(r"\s+", " ", t).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _proyecto_tipo(titulo: str) -> str:
    n = titulo.lower()
    if "reparcel" in n:
        return "reparcelación"
    if "pla especial" in n or "plan especial" in n:
        return "plan especial"
    if "pla de millora" in n or "pmu" in n:
        return "plan de mejora urbana"
    if "pau" in n or "polígon" in n or "poligon" in n:
        return "polígono de actuación"
    if "modificaci" in n and "poum" in n:
        return "modificación POUM"
    if "suspens" in n and "llic" in n:
        return "suspensión licencias"
    if "projecte d'urban" in n or "urbanitz" in n:
        return "proyecto de urbanización"
    if "ppu" in n:
        return "plan parcial urbanístico"
    return "planeamiento"


def _pick_doc_url(links: list[str]) -> str:
    for href in links:
        if "sharepoint.com" in href.lower() or "onedrive" in href.lower():
            continue
        if href.startswith("http") and "calafell.cat" in href:
            return href
        if href.startswith("/"):
            return urllib.parse.urljoin(BASE, href)
    for href in links:
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return urllib.parse.urljoin(BASE, href)
    return REGISTRE_GESTIO


class CalafellAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal calafell.cat (registre gestió + planejament en tràmit) + seu-e tràmits."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = self.config.get("user_agent", "poc-bocm-calafell/1.0")
        self.seed_pages = tuple(self.config.get("seed_pages") or DEFAULT_SEED_PAGES)

    def _fetch(self, url: str, *, timeout: int = 90) -> str | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    def _parse_expand_boxes(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for block in RE_EXPAND_BLOCK.findall(html):
            hm = RE_EXPAND_HEADING.search(block)
            if not hm:
                continue
            heading_html = hm.group(1)
            fecha = _parse_fecha_dmy(heading_html)
            titulo = _clean(re.sub(r"<[^>]+>", " ", heading_html))
            titulo = re.sub(r"^\d{1,2}/\d{1,2}/\d{4}\s*", "", titulo).strip()
            if len(titulo) < 8:
                continue
            links = [unescape(u) for u in RE_HREF.findall(block)]
            doc_url = _pick_doc_url(links)
            pdf_urls = [
                u if u.startswith("http") else urllib.parse.urljoin(BASE, u)
                for u in links
                if ".pdf" in u.lower() and "sharepoint" not in u.lower()
            ]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"{page_url}|{titulo[:120]}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha or _fecha_from_pdf_url(doc_url),
                "tipo": _proyecto_tipo(titulo),
                "url": doc_url,
                "source": "ayuntamiento",
                "origen": page_url,
            }
            if pdf_urls:
                rec["pdf_urls"] = pdf_urls[:15]
            rows.append(rec)
        return rows

    def _static_refs(self) -> list[dict[str, Any]]:
        refs = [
            (RPUC_MUNICI, "RPUC — expedients de planejament (Calafell 43037)"),
            (MUC_VISOR, "Visor MUC — cartografia urbanística (municipi 43037)"),
            (MAPA_INTERACTIU, "Mapa interactiu del municipi (citymap.tecnogeows.com)"),
            (SEU_URBANISME, "Govern obert — normativa d'urbanisme (seu-e.cat)"),
        ]
        out: list[dict[str, Any]] = []
        for url, titulo in refs:
            out.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": None,
                    "tipo": "referencia cartográfica / planeamiento",
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "referencia_portal",
                }
            )
        return out

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for page in self.seed_pages:
            html = self._fetch(page)
            if not html:
                continue
            for row in self._parse_expand_boxes(html, page):
                by_id[row["id"]] = row
        for row in self._static_refs():
            by_id[row["id"]] = row
        return list(by_id.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo in DEFAULT_LICENCIA_PAGES:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": titulo[:200],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                }
            )
        anuncis = self._fetch(f"{BASE}/ajuntament/anuncis")
        if anuncis:
            for m in re.finditer(
                r'href="(/ajuntament/anuncis/[^"]+|/sites/default/files/[^"]+\.pdf[^"]*)"',
                anuncis,
                re.I,
            ):
                href = urllib.parse.urljoin(BASE, m.group(1))
                blob = urllib.parse.unquote(href)
                if not RE_LICENCIA.search(blob):
                    continue
                titulo = _clean(blob.rsplit("/", 1)[-1].replace("-", " "))
                rows.append(
                    {
                        "id": _stable_id("lic", href),
                        "fecha_concesion": _fecha_from_pdf_url(href),
                        "tipo": titulo[:200] or "Anunci urbanístic",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "url": href,
                        "source": "ayuntamiento",
                        "origen": "tauler_anuncis",
                    }
                )
        by_id = {r["id"]: r for r in rows}
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
