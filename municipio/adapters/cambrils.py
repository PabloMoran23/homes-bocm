from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.cambrils.cat"
TRAMITS_BASE = "https://tramits.cambrils.cat"
MUNICIPIO = "Cambrils"
ID_PREFIX = "cambrils"

INFO_PUBLICA = f"{WEB_BASE}/ca/serveis/urbanisme/informacio-publica"
TRAMITS_LIC = f"{WEB_BASE}/ca/serveis/urbanisme/tramits-i-llicencies"
POUM = f"{WEB_BASE}/ca/serveis/urbanisme/poum-21"
URBANISME_HUB = f"{WEB_BASE}/ca/serveis/urbanisme"
TAULER = f"{WEB_BASE}/ca/seu-electronica/tauler-danuncis"
SEU_TRAMITS = f"{WEB_BASE}/ca/seu-electronica/tramits-i-gestions"

DEFAULT_SEED_PAGES: list[str] = [
    INFO_PUBLICA,
    TRAMITS_LIC,
    POUM,
    URBANISME_HUB,
    f"{WEB_BASE}/ca/serveis/urbanisme/informacio-dinteres",
]

RE_INFO_PUBLICA_LINK = re.compile(
    r'href="(https://www\.cambrils\.cat/ca/serveis/urbanisme/informacio-publica/[^"?#]+)"',
    re.I,
)
RE_LINK = re.compile(r'href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|comunicaci[oó] previa|"
    r"declaraci[oó]n responsable|declaraci[oó] responsable|enderroc|grua|piscina|"
    r"primera ocupaci[oó]|obra[s]? (?:major|menor)|parcel\.?laci[oó]|divisi[oó] horitzontal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|poum|pla parcial|pol[ií]gon|reparcel|modificaci[oó]|"
    r"informaci[oó] p[uú]blica|projecte d.?urban|us provisional|mutaci[oó] demanial|"
    r"aprovaci[oó] (?:inicial|definitiva)|sector|horts)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_OG_TITLE = re.compile(r'property="og:title" content="([^"]+)"', re.I)
RE_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    for parser in (_parse_fecha_iso, _parse_fecha_dmy):
        d = parser(text)
        if d:
            return d
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(titulo: str) -> str:
    n = (titulo or "").lower()
    if "informaci" in n and "públic" in n or "informaci" in n and "public" in n:
        return "información pública"
    if "reparcel" in n:
        return "reparcelación"
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual POUM"
    if "projecte d'urban" in n or "projecte d2019urban" in n:
        return "proyecto de urbanización"
    if "pla parcial" in n or re.search(r"\bpa[- ]?\d+", n):
        return "plan parcial"
    if "poum" in n:
        return "POUM"
    if "us provisional" in n:
        return "uso provisional del suelo"
    if "mutaci" in n and "demanial" in n:
        return "mutación demanial"
    return "planeamiento"


class CambrilsAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone cambrils.cat (informació pública urbanisme) + tràmits OAC (tramits.cambrils.cat)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tramits_base = str(self.config.get("tramits_base") or TRAMITS_BASE).rstrip("/")
        self.fetch_timeout_s = int(self.config.get("fetch_timeout_s", 90))
        self.tramits_timeout_s = int(self.config.get("tramits_timeout_s", 12))

    def _fetch(self, url: str, *, timeout: int | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cambrils/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout or self.fetch_timeout_s) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_optional(self, url: str, *, timeout: int | None = None) -> str | None:
        try:
            return self._fetch(url, timeout=timeout or self.tramits_timeout_s)
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    def _abs(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or f"{self.web_base}/", unescape(href))

    def _collect_info_publica_urls(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        start = 0
        while start < 400:
            url = INFO_PUBLICA if start == 0 else f"{INFO_PUBLICA}?b_start:int={start}"
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, TimeoutError, OSError):
                break
            found = RE_INFO_PUBLICA_LINK.findall(html)
            new = 0
            for u in found:
                u = u.split("#")[0].rstrip("/")
                if u.endswith("/informacio-publica"):
                    continue
                if u not in seen:
                    seen.add(u)
                    out.append(u)
                    new += 1
            if start > 0 and new == 0:
                break
            start += 20
        return sorted(out)

    def _page_title(self, html: str, fallback: str = "") -> str:
        m = RE_OG_TITLE.search(html)
        if m:
            t = _strip_html(m.group(1))
            t = re.sub(r"\s*-\s*Ajuntament de Cambrils\s*$", "", t, flags=re.I)
            if t:
                return t
        m = RE_H1.search(html)
        if m:
            t = _strip_html(m.group(1))
            if t:
                return t
        return fallback

    def _page_fecha(self, html: str, titulo: str, url: str) -> str | None:
        for pat in (
            r'property="article:modified_time" content="([^"]+)"',
            r'name="DC\.date\.modified" content="([^"]+)"',
            r'class="documentModified"[^>]*>.*?(\d{1,2}/\d{1,2}/\d{4})',
        ):
            m = re.search(pat, html, re.I | re.S)
            if m:
                d = _parse_fecha_iso(m.group(1)[:10]) or _parse_fecha_dmy(m.group(1))
                if d:
                    return d
        return _fecha_from_blob(titulo, url)

    def _parse_info_publica_page(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
        slug = url.rstrip("/").split("/")[-1]
        titulo = self._page_title(html, slug.replace("-", " ").title())
        if not titulo:
            return None
        fecha = self._page_fecha(html, titulo, url) or "1970-01-01"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": "plone_info_publica",
        }
        pdfs = RE_PDF.findall(html)
        if pdfs:
            rec["documento_url"] = self._abs(pdfs[0], url)
        return rec

    def _collect_poum_docs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(POUM)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for href in RE_PDF.findall(html):
            pdf_url = self._abs(href, POUM)
            titulo = urllib.parse.unquote(pdf_url.split("/")[-1]).replace(".pdf", "").replace("_", " ")
            if len(titulo) < 6:
                titulo = "Document POUM Cambrils"
            rows.append(
                {
                    "id": _stable_id("proy", pdf_url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo, pdf_url) or "1970-01-01",
                    "tipo": "POUM",
                    "url": POUM,
                    "documento_url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "poum_pdf",
                }
            )
        return rows

    def _collect_licencia_tramits(self) -> list[dict[str, Any]]:
        pages = [TRAMITS_LIC, SEU_TRAMITS, TAULER]
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(url: str, titulo: str, origen: str) -> None:
            u = url.split("#")[0]
            if u in seen or len(titulo) < 5:
                return
            if not RE_LICENCIA.search(titulo) and "tramit" not in titulo.lower():
                return
            seen.add(u)
            rows.append(
                {
                    "id": _stable_id("lic", u),
                    "fecha_concesion": _fecha_from_blob(titulo, u) or "1970-01-01",
                    "tipo": titulo[:200],
                    "distrito": "Cambrils",
                    "lat": None,
                    "lon": None,
                    "url": u,
                    "source": "ayuntamiento",
                    "origen": origen,
                }
            )

        for page in pages:
            try:
                html = self._fetch(page)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for href, text in RE_LINK.findall(html):
                if href.startswith(("mailto:", "javascript:", "#")):
                    continue
                titulo = _strip_html(text)
                u = self._abs(href, page)
                if "cambrils.cat" in u and "/tramits-i-llicencies/" in u:
                    add(u, titulo or u.split("/")[-1].replace("-", " "), "plone_tramit")
                elif "tramits.cambrils.cat" in u and "CdT.jsp" in u:
                    add(u, titulo or f"Tràmit OAC {u}", "oac_cdt")
                elif "cambrils.cat" in u and RE_LICENCIA.search(titulo):
                    add(u, titulo, "plone_tramit")

        static_oac = [
            (f"{self.tramits_base}/OAC/CdT.jsp?tramit=105", "Tràmit OAC — llicències (catàleg)"),
            (f"{self.tramits_base}/OAC/CdT.jsp?tramit=63", "Tràmit OAC — urbanisme"),
            (f"{self.tramits_base}/OAC/CdT.jsp?tramit=228", "Tràmit OAC — obres"),
            (f"{self.tramits_base}/OAC/SegExpStandalone.jsp?idioma=ca&_UNITREE=CCIU", "Consulta expedients (OAC)"),
        ]
        for u, titulo in static_oac:
            add(u, titulo, "oac_seed")

        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        by_id: dict[str, dict[str, Any]] = {}
        for url in self._collect_info_publica_urls():
            rec = self._parse_info_publica_page(url)
            if rec:
                by_id[rec["id"]] = rec
        for rec in self._collect_poum_docs():
            by_id[rec["id"]] = rec
        rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info_publica": sum(1 for r in rows if r.get("origen") == "plone_info_publica"),
            "poum_pdf": sum(1 for r in rows if r.get("origen") == "poum_pdf"),
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
        rows = self._collect_licencia_tramits()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": after},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "status": "ok", "delta": after - before}
