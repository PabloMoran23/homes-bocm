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

WEB_BASE = "https://www.castellarvalles.cat"
SEU_BASE = "https://seu.castellarvalles.cat"
MUNICIPIO = "Castellar del Vallès"
ID_PREFIX = "castellar-del-valles"
INE_MUN = "08047"
ETAULER_URL = "https://tauler.seu.cat/inici.do?idens=805170005"
GEOPORTAL_URB = "http://geoportal.castellarvalles.cat/urbanisme/"
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
RPUC_POUM = (
    "https://planejamenturbanisme.territori.gencat.cat/rpucportal/#/consulta/detallExpedient/263133"
)

DEFAULT_PROYECTO_SEEDS: list[tuple[str, str]] = [
    (f"{WEB_BASE}/55033/descriptiu/", "en_tramit"),
    (f"{WEB_BASE}/55055/descriptiu/", "aprovats"),
    (f"{WEB_BASE}/31824/plaEstrategic/", "poum"),
    (f"{WEB_BASE}/46242/descriptiu/", "pe_catalog"),
    (f"{WEB_BASE}/55066/descriptiu/", "pe_nucli"),
    (f"{WEB_BASE}/55077/descriptiu/", "pe_ripoll"),
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (
        f"{SEU_BASE}/33033/tramits/?fil=eyJpZHNBbWJpdCI6IjE0LDMyLDMzIn0=",
        "Tràmits d'urbanisme (e-TRAM)",
    ),
    (ETAULER_URL, "Tauler d'edictes electrònic (e-TAULER AOC)"),
    (f"{WEB_BASE}/54912/descriptiu/", "Tipus de tràmits ORPIME"),
    (f"{WEB_BASE}/33022/descriptiu/", "Tauler d'edictes — informació"),
]

RE_EXP_LINK = re.compile(
    r'href="(?:https?://(?:www\.)?castellarvalles\.cat)?/(550(?:33|55))/descriptiu/(\d+)"'
    r'(?:\s+title="([^"]*)")?',
    re.I,
)
RE_TRAMIT = re.compile(r'href="/33033/tramit/(\d+)/"[^>]*>([^<]+)', re.I)
RE_H3 = re.compile(r'<h3[^>]*class="[^"]*sense[^"]*"[^>]*>(.*?)</h3>', re.I | re.S)
RE_DOC_LINK = re.compile(
    r'href="(/arxius/document/\d+/arxiu/[^"]+\.pdf)"[^>]*>([^<]+)',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})")
RE_FECHA_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó] previa|comunicaci[oó] pr[eè]via|"
    r"primera utilitzaci[oó]|parcel·laci[oó]|parcelaci[oó]n|obres provisionals|"
    r"1-lu\.|2-lu\.|cp\.eo|cp\.op|cp\.at)",
)
RE_PROYECTO_SKIP = re.compile(r"(?i)(ordenan[cç]a reguladora de subvencions|borsa de mediaci[oó])")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha(text: str) -> str | None:
    for rx in (RE_FECHA_DMY, RE_FECHA_SLASH):
        m = rx.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1995 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-06-01"
    return None


def _proyecto_tipo(titulo: str, section: str) -> str:
    n = (titulo or "").lower()
    if "modificaci" in n and ("poum" in n or "mppoum" in n):
        return "modificación POUM"
    if "conveni urban" in n:
        return "convenio urbanístico"
    if "reparcel" in n or "urbanitzaci" in n:
        return "urbanización / reparcelación"
    if "pla especial" in n or "pe " in n or section.startswith("pe_"):
        return "plan especial"
    if "poum" in n or section == "poum":
        return "POUM"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if section == "en_tramit":
        return "planeamiento en trámite"
    if section == "aprovats":
        return "planeamiento aprobado"
    return "urbanismo"


class CastellarDelVallesAyuntamientoAdapter(AyuntamientoAdapter):
    """CMS castellarvalles.cat (expedients IP/aprovats) + seu e-TRAM + e-TAULER (referencia)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seu_base = str(self.config.get("seu_base") or SEU_BASE).rstrip("/")
        self.proyecto_seeds = [
            (str(u), str(s))
            for u, s in (self.config.get("proyecto_seeds") or DEFAULT_PROYECTO_SEEDS)
        ]
        self.licencia_pages = [
            (str(u), str(t))
            for u, t in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        ]
        self.tramits_urbanisme_url = str(
            self.config.get("tramits_urbanisme_url") or DEFAULT_LICENCIA_PAGES[0][0]
        )
        self.enrich_details = bool(self.config.get("enrich_details", True))
        self.max_detail_fetches = int(self.config.get("max_detail_fetches", 120))

    def _ua(self) -> str:
        return str(self.config.get("user_agent") or "poc-bocm-castellar-del-valles/1.0")

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_seu(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.seu_base}/", unescape(href))

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
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

    def _parse_expedient_links(self, html: str, section: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for folder, num, title_attr in RE_EXP_LINK.findall(html):
            path = f"/{folder}/descriptiu/{num}"
            if path in seen:
                continue
            seen.add(path)
            titulo = _strip_html(title_attr) if title_attr else ""
            url = self._abs_web(path)
            if not titulo or len(titulo) < 6:
                titulo = f"Expedient {folder}/{num}"
            if RE_PROYECTO_SKIP.search(titulo):
                continue
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha(titulo),
                    "tipo": _proyecto_tipo(titulo, section),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": f"expedient_{section}",
                    "seccion": section,
                }
            )
        return rows

    def _parse_static_page(self, html: str, url: str, section: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        h3 = RE_H3.search(html)
        titulo = _strip_html(h3.group(1)) if h3 else section
        if titulo and len(titulo) > 5 and not RE_PROYECTO_SKIP.search(titulo):
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha(html[:8000]),
                    "tipo": _proyecto_tipo(titulo, section),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": f"pagina_{section}",
                    "seccion": section,
                }
            )
        for href, label in RE_DOC_LINK.findall(html):
            doc_url = self._abs_web(href)
            doc_title = _strip_html(label) or doc_url
            if not re.search(r"(?i)(poum|urban|planej|edicte|ctub|dogc|expedient)", doc_title):
                continue
            rows.append(
                {
                    "id": _stable_id("proy", doc_url),
                    "municipio": MUNICIPIO,
                    "titulo": doc_title[:500],
                    "fecha": _parse_fecha(doc_title),
                    "tipo": _proyecto_tipo(doc_title, section),
                    "url": doc_url,
                    "source": "ayuntamiento",
                    "origen": "document_pdf",
                    "documento_url": doc_url,
                    "seccion": section,
                }
            )
        return rows

    def _enrich_detail(self, rec: dict[str, Any]) -> dict[str, Any]:
        url = str(rec.get("url") or "")
        if not url or "/descriptiu/" not in url:
            return rec
        try:
            html = self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return rec
        h3 = RE_H3.search(html)
        if h3:
            titulo = _strip_html(h3.group(1))
            if titulo and len(titulo) > 5:
                rec["titulo"] = titulo[:500]
                rec["tipo"] = _proyecto_tipo(titulo, str(rec.get("seccion") or ""))
        docs = RE_DOC_LINK.findall(html)
        fechas: list[str] = []
        for href, label in docs:
            f = _parse_fecha(label)
            if f:
                fechas.append(f)
        if fechas:
            rec["fecha"] = max(fechas)
        if docs:
            rec["documento_url"] = self._abs_web(docs[0][0])
        return rec

    def _reference_rows(self) -> list[dict[str, Any]]:
        refs = [
            (GEOPORTAL_URB, "Geoportal municipal — planejament urbanístic (TecnoGeoWS)"),
            (MUC_VISOR, "Visor MUC Generalitat — planejament Castellar del Vallès"),
            (RPUC_POUM, "RPUC — expedient POUM Castellar del Vallès (263133)"),
        ]
        out: list[dict[str, Any]] = []
        for url, titulo in refs:
            out.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": "2016-11-30",
                    "tipo": "referencia visor / planeamiento",
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "visor_referencia",
                }
            )
        return out

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        detail_budget = self.max_detail_fetches
        for seed_url, section in self.proyecto_seeds:
            try:
                html = self._fetch(seed_url)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            if section in ("en_tramit", "aprovats"):
                batch = self._parse_expedient_links(html, section)
            else:
                batch = self._parse_static_page(html, seed_url, section)
            for rec in batch:
                if self.enrich_details and detail_budget > 0 and rec.get("origen", "").startswith(
                    "expedient_"
                ):
                    rec = self._enrich_detail(rec)
                    detail_budget -= 1
                by_id[rec["id"]] = rec
        for rec in self._reference_rows():
            by_id.setdefault(rec["id"], rec)
        return list(by_id.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.tramits_urbanisme_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            html = ""
        for _tid, inner in RE_TRAMIT.findall(html):
            titulo = _strip_html(inner)
            if not titulo or not RE_LICENCIA.search(titulo):
                continue
            url = self._abs_seu(f"/33033/tramit/{_tid}/")
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": titulo[:200],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "e_tram_cataleg",
                }
            )
        for url, label in self.licencia_pages:
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": label[:200],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "info_portal",
                }
            )
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "en_tramit": sum(1 for r in rows if r.get("seccion") == "en_tramit"),
            "aprovats": sum(1 for r in rows if r.get("seccion") == "aprovats"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": after},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {**stats, "delta": after - before}

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "e_tram": sum(1 for r in rows if r.get("origen") == "e_tram_cataleg"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": after},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {**stats, "delta": after - before}
