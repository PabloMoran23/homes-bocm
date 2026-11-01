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

WEB_BASE = "https://www.viladesalt.cat"
SEU_E_BASE = "https://seu-e.cat/ca/web/salt"
MUNICIPIO = "Salt"
ID_PREFIX = "salt"
IDENS = "1715570005"
COD_INE_MUN = "17155"

PLANEJAMENT_ROOT = (
    f"{WEB_BASE}/ajuntament/documentacio-i-tramits-ppal/documentacio-i-tramits/planejament-urbanistic/"
)

DEFAULT_PROYECTO_PAGES: list[str] = [
    f"{PLANEJAMENT_ROOT}planejament-en-tramit/",
    f"{PLANEJAMENT_ROOT}planejament-derivat-vigent/",
    f"{PLANEJAMENT_ROOT}convenis-urbanistics/",
    f"{PLANEJAMENT_ROOT}suspensio-potestativa-de-llicencies/",
    f"{PLANEJAMENT_ROOT}instruments-de-gestio/",
    f"{PLANEJAMENT_ROOT}pla-general-dordenacio-urbana/",
    PLANEJAMENT_ROOT,
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (
        f"{WEB_BASE}/arees-serveis/area-de-territori-i-mediambient/llicencies-i-comunicats-dobres/",
        "Llicències i comunicats d'obres — formularis i tràmits",
    ),
    (
        f"{SEU_E_BASE}/tramits-i-gestions/-/tramits/classificacio/urbanisme",
        "Catàleg de tràmits — classificació urbanisme (seu-e)",
    ),
    (
        f"{SEU_E_BASE}/govern-obert-i-transparencia/serveis-i-tramits/tramits/cataleg-de-tramits-i-procediments",
        "Catàleg de tràmits i procediments",
    ),
    (
        f"https://tauler.seu.cat/inici.do?idens={IDENS}",
        "Tauler d'edictes i anuncis (e-Tauler AOC)",
    ),
]

VISOR_PLANEJAMENT = "https://mapes.salt.cat/planejament/#/home"
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={COD_INE_MUN}&set-locale=ca"

RE_H2_SECTION = re.compile(
    r'<h2 class="content-box-heading"[^>]*>(.*?)</h2>(.*?)(?=<h2 class="content-box-heading"|$)',
    re.I | re.S,
)
RE_EXP = re.compile(r"\(Exp\.\s*([^)]+)\)", re.I)
RE_LINK = re.compile(r'href="([^"]+)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_CA = re.compile(
    r"(\d{1,2})\s+d[''´`]?\s*(gener|febrer|març|marc|abril|maig|juny|juliol|agost|"
    r"setembre|octubre|novembre|desembre)\s+de\s+(\d{4})",
    re.I,
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PLANOL = re.compile(r"(?i)pl[aà]nol.*delimitaci")
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n pr[eè]via|declaraci[oó]n responsable|"
    r"comunicat d'obres|sol[\·.]?licitud.*obra|pr[oò]rroga.*llic)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|plan (?:parcial|especial|general)|pgou|modificaci[oó]n|"
    r"conveni|informaci[oó]n p[uú]blica|expedient|aprobaci[oó]n|reparcel|sector|"
    r"estudi de detall|suspensi[oó]|instrument de gesti)",
)

_MES_CA = {
    "gener": 1,
    "febrer": 2,
    "març": 3,
    "marc": 3,
    "abril": 4,
    "maig": 5,
    "juny": 6,
    "juliol": 7,
    "agost": 8,
    "setembre": 9,
    "octubre": 10,
    "novembre": 11,
    "desembre": 12,
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_ca(text: str) -> str | None:
    m = RE_FECHA_CA.search(text or "")
    if not m:
        return None
    mes = _MES_CA.get(m.group(2).lower().replace("ç", "c"))
    if not mes:
        return None
    try:
        return datetime(int(m.group(3)), mes, int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str, expediente: str = "") -> str | None:
    for parser in (_parse_fecha_ca, _parse_fecha_dmy):
        d = parser(text)
        if d:
            return d
    digits = re.sub(r"\D", "", expediente or "")
    if len(digits) >= 4:
        y = int(digits[:4])
        if 1980 <= y <= 2035:
            return f"{y}-01-01"
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(titulo: str, blob: str) -> str:
    n = f"{titulo} {blob}".lower()
    if "pgou" in n or "pla general" in n:
        return "PGOU"
    if "plan especial" in n or "pe " in f" {n} ":
        return "plan especial"
    if "plan parcial" in n or "subsector" in n:
        return "plan parcial"
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual PGOU"
    if "conveni" in n:
        return "convenio urbanístico"
    if "suspensi" in n:
        return "suspensión licencias"
    if "instrument" in n and "gesti" in n:
        return "instrumento de gestión"
    return "planeamiento urbanístico"


def _abs_url(base: str, href: str) -> str:
    return unescape(urllib.parse.urljoin(f"{base.rstrip('/')}/", href))


class SaltAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Avada (viladesalt.cat) + seu-e / BPM + e-Tauler; visor mapes.salt.cat (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.proyecto_pages = [str(u) for u in (self.config.get("proyecto_pages") or DEFAULT_PROYECTO_PAGES)]
        self.licencia_pages = [
            tuple(x) for x in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        ]
        self.visor_url = str(self.config.get("visor_planejament") or VISOR_PLANEJAMENT)
        self.fetch_timeout = int(self.config.get("fetch_timeout_s", 45))
        self.ua = str(self.config.get("user_agent", "poc-bocm-salt/1.0"))

    def _fetch(self, url: str, *, timeout: int | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=timeout or self.fetch_timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return {"rows": len(rows), "path": str(path)}

    def _pick_doc_url(self, section_html: str, page_url: str) -> str:
        candidates: list[str] = []
        for href in RE_LINK.findall(section_html):
            u = _abs_url(self.web_base, href)
            if "bpm.salt.cat" in u or u.lower().endswith(".pdf"):
                candidates.append(u)
            elif "tauler.seu" in u:
                candidates.append(u.replace("&#038;", "&"))
        if candidates:
            for u in candidates:
                if RE_PLANOL.search(section_html) and "download" in u.lower():
                    return u
            return candidates[0]
        return page_url

    def _parse_avada_sections(self, page_url: str, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_H2_SECTION.finditer(html):
            titulo = _strip_html(m.group(1))[:500]
            if len(titulo) < 8:
                continue
            body = m.group(2)
            blob = _strip_html(body)
            if not RE_PROYECTO.search(f"{titulo} {blob}"):
                continue
            exp_m = RE_EXP.search(blob)
            expediente = exp_m.group(1).strip() if exp_m else ""
            doc_url = self._pick_doc_url(body, page_url)
            key = f"{expediente}:{titulo}:{page_url}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": _fecha_from_blob(blob, expediente),
                "tipo": _proyecto_tipo(titulo, blob),
                "url": doc_url,
                "source": "ayuntamiento",
                "origen": "viladesalt_avada",
                "page_url": page_url,
            }
            if expediente:
                rec["expediente"] = expediente
            if RE_PLANOL.search(blob):
                rec["geometry_note"] = "plànol_delimitacio_pdf"
                rec["geometry_source_url"] = doc_url
            rows.append(rec)
        return rows

    def _static_proyecto_refs(self) -> list[dict[str, Any]]:
        refs = [
            (self.visor_url, "Visor de planejament urbanístic (mapes.salt.cat)"),
            (MUC_VISOR, "Visor MUC — cartografia urbanística (Gencat)"),
        ]
        out: list[dict[str, Any]] = []
        for url, titulo in refs:
            out.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": None,
                    "tipo": "referencia cartográfica",
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "visor_ref",
                }
            )
        return out

    def _try_visor_reachable(self) -> bool:
        try:
            req = urllib.request.Request(self.visor_url.split("#")[0], headers={"User-Agent": self.ua})
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for page in self.proyecto_pages:
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                continue
            for rec in self._parse_avada_sections(page, html):
                by_id[rec["id"]] = rec
        for rec in self._static_proyecto_refs():
            by_id.setdefault(rec["id"], rec)
        return list(by_id.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url, label in self.licencia_pages:
            rows.append(
                {
                    "id": _stable_id("lic", page_url),
                    "fecha_concesion": None,
                    "tipo": label[:200],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "url": page_url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                }
            )
        try:
            html = self._fetch(
                f"{self.web_base}/arees-serveis/area-de-territori-i-mediambient/llicencies-i-comunicats-dobres/"
            )
        except urllib.error.URLError:
            html = ""
        for href in RE_LINK.findall(html):
            u = _abs_url(self.web_base, href)
            host = urllib.parse.urlparse(u).netloc.lower()
            if "seu-e.cat" not in host or "/documents/" not in u:
                continue
            titulo = unescape(
                urllib.parse.unquote(Path(u).parent.name.replace("+", " "))
            )[:200]
            if not titulo or titulo.isdigit():
                titulo = unescape(urllib.parse.unquote(u.split("/documents/")[-1][:200]))
            if not RE_LICENCIA.search(titulo) and not re.search(r"\bOB\d", titulo):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", u),
                    "fecha_concesion": None,
                    "tipo": titulo or "Formulari llicència/comunicació d'obres",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "url": u,
                    "source": "ayuntamiento",
                    "origen": "formulari_seu_e",
                }
            )
        try:
            tram_html = self._fetch(f"{SEU_E_BASE}/tramits-i-gestions/-/tramits/classificacio/urbanisme")
            for tid in sorted(set(re.findall(r"tramits/tramit/(\d+)", tram_html))):
                url = f"{SEU_E_BASE}/tramits-i-gestions/-/tramits/tramit/{tid}"
                rows.append(
                    {
                        "id": _stable_id("lic", url),
                        "fecha_concesion": None,
                        "tipo": "Tràmit urbanisme (catàleg seu-e)",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "seu_e_tramit",
                    }
                )
        except urllib.error.URLError:
            pass
        by_id = {r["id"]: r for r in rows}
        return list(by_id.values())

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        meta = self._write_jsonl(out_jsonl, rows)
        meta["visor_reachable"] = self._try_visor_reachable()
        meta["fetched_at"] = datetime.now(timezone.utc).isoformat()
        meta["status"] = "ok" if rows else "empty"
        return meta

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        meta = self._write_jsonl(out_jsonl, rows)
        meta["fetched_at"] = datetime.now(timezone.utc).isoformat()
        meta["status"] = "ok" if rows else "empty"
        return meta

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
