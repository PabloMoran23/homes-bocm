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

BASE = "https://www.santboi.cat"
SEDE = "https://tramits.santboi.cat"
MUNICIPIO = "Sant Boi de Llobregat"
ID_PREFIX = "sant-boi-de-llobregat"

PLANEJAMENT_INDEX: list[tuple[str, str]] = [
    ("/planejament-urbanistic/en_tramit", "en tràmit"),
    ("/planejament-urbanistic/en_exposicio", "exposició pública"),
    ("/planejament-urbanistic/vigents", "vigent"),
    ("/planejament-urbanistic/suspesos", "suspensió llicències"),
]

GESTIO_URL = f"{BASE}/ajuntament/urbanisme/gestio-urbanistica"
CONVENIS_URL = f"{BASE}/ajuntament/urbanisme/convenis-urbanistics"
URBANISME_URL = f"{BASE}/ajuntament/Urbanisme"

DEFAULT_TRAMITE_URLS: tuple[str, ...] = (
    "https://tramits.santboi.cat/Ciutadania/DetallTramit.aspx?IdTema=1150&IdTramit=237&IdTema=1147",
    "https://tramits.santboi.cat/Ciutadania/DetallTramit.aspx?IdTema=44&IdTramit=181&IdTema=7",
    f"{SEDE}/Ciutadania/TramitsTemes.aspx?IdTema=1147",
)

RE_LIST_LINK = re.compile(
    r'<li>\s*<a href="(/planejament-urbanistic/[^"#?]+)"[^>]*>([^<]+)</a>\s*</li>',
    re.I,
)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)
RE_LI_META = re.compile(
    r"<li class='([^']+)'>([^:<]+):\s*([^<]*)</li>",
    re.I,
)
RE_DOCEXP = re.compile(r'href="([^"]*docexp/[^"]+)"', re.I)
RE_PDF = re.compile(
    r'href="((?:https?://[^"]+|/sites/default/files/[^"]+\.pdf[^"]*))"',
    re.I,
)
RE_FECHA = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_TRAMIT = re.compile(
    r'href="(https://tramits\.santboi\.cat/Ciutadania/DetallTramit\.aspx[^"]+)"',
    re.I,
)
RE_ACCORDION = re.compile(
    r'<h3 class="accordion-button">([^<]+)</h3>(.*?)(?=<h3 class="accordion-button">|$)',
    re.S | re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licen[cs]ia|obra|comunicaci[oó]n previa|declaraci[oó]n responsable)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    t = unescape(htmlmod.unescape(text or ""))
    return re.sub(r"\s+", " ", t).strip()


def _parse_fecha(text: str) -> str | None:
    m = RE_FECHA.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _best_fecha(meta: dict[str, str]) -> str | None:
    for key in (
        "dataAprovacioDefinitiva",
        "dataAprovacioInicial",
        "dataPublicacioAprovacioInicial",
        "publicacioDefinitiva",
        "publicacioSuspensio",
    ):
        v = meta.get(key, "")
        if v and v.strip() not in ("-", ""):
            f = _parse_fecha(v)
            if f:
                return f
    return None


def _proyecto_tipo(titulo: str, codi: str, estado: str) -> str:
    blob = f"{titulo} {codi} {estado}".lower()
    if "reparcel" in blob:
        return "reparcelación"
    if "conveni" in blob:
        return "convenio urbanístico"
    if "suspens" in blob:
        return "suspensión licencias"
    if "exposici" in blob or "informaci" in blob:
        return "exposición pública"
    if codi:
        return codi.upper()
    if "mpgm" in blob:
        return "modificación PGM"
    if "pmu" in blob:
        return "PMU"
    if "pe " in blob or blob.startswith("pe"):
        return "plan especial"
    return estado or "planeamiento"


class SantBoiDeLlobregatAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 10 santboi.cat (planejament + gestió) + sede tramits (obres informativos)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = self.config.get("user_agent", "poc-bocm-sant-boi-de-llobregat/1.0")

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs(self, href: str) -> str:
        return urllib.parse.urljoin(BASE, href)

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

    def _parse_planejament_detail(self, url: str, html: str, estado: str) -> dict[str, Any]:
        titulo = _clean(RE_H1.search(html).group(1)) if RE_H1.search(html) else url.rsplit("/", 1)[-1]
        meta: dict[str, str] = {}
        for m in RE_LI_META.finditer(html):
            meta[m.group(1)] = _clean(m.group(3))

        codi_exp = meta.get("codiExpedient", "").strip()
        codi_tipus = meta.get("codiTipusPlanejament", "").strip()
        docs = list(dict.fromkeys(RE_DOCEXP.findall(html)))
        pdfs = [self._abs(u) if u.startswith("/") else u for u in RE_PDF.findall(html)]
        doc_url = docs[0] if docs else (pdfs[0] if pdfs else url)
        fecha = _best_fecha(meta)

        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(titulo, codi_tipus, estado),
            "url": url,
            "source": "ayuntamiento",
            "estado_planeamiento": estado,
            "codi_expedient": codi_exp or None,
            "codi_tipus_planejament": codi_tipus or None,
            "origen": "planejament_urbanistic",
        }
        if docs:
            rec["document_urls"] = docs[:20]
        if pdfs:
            rec["pdf_urls"] = pdfs[:10]
        if meta.get("observacions"):
            rec["observaciones"] = meta["observacions"][:800]
        return rec

    def _proyecto_from_listing(
        self, detail_url: str, link_title: str, estado: str
    ) -> dict[str, Any]:
        titulo = _clean(link_title)
        codi_tipus = titulo.split(" - ", 1)[0].strip() if " - " in titulo else ""
        return {
            "id": _stable_id("proy", detail_url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": None,
            "tipo": _proyecto_tipo(titulo, codi_tipus, estado),
            "url": detail_url,
            "source": "ayuntamiento",
            "estado_planeamiento": estado,
            "origen": "planejament_urbanistic",
            "nota": "Metadatos desde índice (listado histórico grande)",
        }

    def _collect_planejament(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        # vigents tiene cientos de expedientes históricos: solo índice (sin N×ficha).
        index_only_sections = {"/planejament-urbanistic/vigents"}

        for index_path, estado in PLANEJAMENT_INDEX:
            index_url = self._abs(index_path)
            try:
                html = self._fetch(index_url)
            except urllib.error.URLError:
                continue
            for m in RE_LIST_LINK.finditer(html):
                rel = m.group(1).split("?")[0].rstrip("/")
                if rel == index_path.rstrip("/"):
                    continue
                detail_url = self._abs(rel)
                if detail_url in seen:
                    continue
                seen.add(detail_url)
                link_title = _clean(m.group(2))
                if index_path in index_only_sections:
                    rows.append(self._proyecto_from_listing(detail_url, link_title, estado))
                    continue
                try:
                    detail_html = self._fetch(detail_url)
                except urllib.error.URLError:
                    rows.append(self._proyecto_from_listing(detail_url, link_title, estado))
                    continue
                rows.append(self._parse_planejament_detail(detail_url, detail_html, estado))
        return rows

    def _collect_accordion_page(self, page_url: str, origen: str, estado: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return rows

        for m in RE_ACCORDION.finditer(html):
            titulo = _clean(m.group(1))
            if not titulo or "no hi ha cap" in titulo.lower():
                continue
            block = m.group(2)
            fechas = []
            for dm in RE_FECHA.finditer(block):
                f = _parse_fecha(dm.group(0))
                if f:
                    fechas.append(f)
            fecha = fechas[0] if fechas else None
            pdfs = []
            for href in RE_PDF.findall(block):
                pdfs.append(self._abs(href) if href.startswith("/") else href)
            pdfs = list(dict.fromkeys(pdfs))
            url = pdfs[0] if pdfs else page_url
            key = f"{origen}|{titulo}|{fecha or ''}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(titulo, "", estado),
                "url": url,
                "source": "ayuntamiento",
                "estado_planeamiento": estado,
                "origen": origen,
            }
            if pdfs:
                rec["pdf_urls"] = pdfs[:15]
            rows.append(rec)
        return rows

    def _licencia_stub(self, url: str, titulo: str) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": None,
            "tipo": "trámite licencia obra",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": url,
            "source": "ayuntamiento",
            "nota": "Ficha informativa sede; concesiones en e-Tauler (SPA, sin listado scrapeable)",
        }

    def _collect_licencias_tramits(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        urls: set[str] = set(DEFAULT_TRAMITE_URLS)
        try:
            req = urllib.request.Request(URBANISME_URL, headers={"User-Agent": self.ua})
            with urllib.request.urlopen(req, timeout=25) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            for m in RE_TRAMIT.finditer(html):
                raw = htmlmod.unescape(m.group(1))
                urls.add(raw.split('"')[0])
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

        fallback_titles = {
            DEFAULT_TRAMITE_URLS[0]: "Tràmits d'obres — llicències (sede electrònica)",
            DEFAULT_TRAMITE_URLS[1]: "Informes i certificats urbanístics (sede)",
            DEFAULT_TRAMITE_URLS[2]: "Tema obres i llicències — tramits.santboi.cat",
        }

        for url in sorted(urls):
            titulo = fallback_titles.get(url, "")
            try:
                time.sleep(self.delay_s)
                req = urllib.request.Request(url, headers={"User-Agent": self.ua})
                with urllib.request.urlopen(req, timeout=25) as resp:
                    page = resp.read().decode("utf-8", errors="replace")
                title_m = re.search(r"<title>([^<]+)</title>", page, re.I)
                if title_m:
                    titulo = _clean(title_m.group(1))
                    titulo = re.sub(r"\s*[-|].*Sant Boi.*$", "", titulo, flags=re.I).strip()
            except (urllib.error.URLError, TimeoutError, OSError):
                if not titulo:
                    titulo = "Tràmit urbanisme / obres (sede electrònica)"
            if not RE_LICENCIA.search(titulo) and "TramitsTemes" not in url:
                continue
            rows.append(self._licencia_stub(url, titulo))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_tramits()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramits_informativos"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_tramits():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_planejament():
            add(rec)
        for rec in self._collect_accordion_page(GESTIO_URL, "gestio_urbanistica", "gestió urbanística"):
            add(rec)
        for rec in self._collect_accordion_page(CONVENIS_URL, "convenis_urbanistics", "conveni urbanístic"):
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "planejament": sum(1 for r in rows if r.get("origen") == "planejament_urbanistic"),
            "gestio": sum(1 for r in rows if r.get("origen") == "gestio_urbanistica"),
            "convenis": sum(1 for r in rows if r.get("origen") == "convenis_urbanistics"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
