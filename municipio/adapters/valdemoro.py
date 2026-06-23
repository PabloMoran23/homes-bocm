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
from urllib.parse import urljoin, unquote

from municipio.adapters.portal import AyuntamientoAdapter

SEDE_BASE = "https://sede.valdemoro.es"
MUNICIPIO = "Valdemoro"
ID_PREFIX = "valdemoro"

TABLON_BASE = (
    f"{SEDE_BASE}/tablon-electronico?"
    "p_p_id=101_INSTANCE_5eNJAxVOlRs5&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view"
    "&_101_INSTANCE_5eNJAxVOlRs5_delta=25"
)

DEFAULT_DOC_PAGES: list[str] = [
    f"{SEDE_BASE}/plan-general-de-valdemoro",
    f"{SEDE_BASE}/tomo-v-planos",
    f"{SEDE_BASE}/planos",
    f"{SEDE_BASE}/fichero-del-catalogo-de-bienes-protegidos",
    f"{SEDE_BASE}/planes-parciales",
    f"{SEDE_BASE}/consulta-publica",
]

DEFAULT_TRAMITES_URL = f"{SEDE_BASE}/tramites-vivienda-urbanismo"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|vado|obra (?:mayor|menor)|primera ocupaci[oó]n|"
    r"segregaci[oó]n|agrupaci[oó]n|calas|terraz)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio urban|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|edicto|"
    r"reparcel|modificaci[oó]n.{0,30}(?:pgou|urban|cat[aá]logo)|normas urban|"
    r"cat[aá]logo|plano|tomo|casco hist[oó]rico|ordenanza.{0,20}tasa|"
    r"prestaci[oó]n de servicios urban)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|plaza de|empleo p[uú]blico|bolsa de trabajo|"
    r"examen|convocatoria del (?:primer|segundo|tercer)|jurado|ciberataque|"
    r"suspensi[oó]n de plazos|estabilizaci[oó]n de empleo|polic[ií]a local|"
    r"t[eé]cnico.{0,25}jur[ií]dico|participaci[oó]n ciudadana|guardia civil|"
    r"presupuesto municipal|padr[oó]n del impuesto|ivtm|recaudador|conserje|"
    r"oficial 1|emergencias|inform[aá]tica|residencia|arquitecto|libre designaci[oó]n|"
    r"herederos|abintestato|notoriedad)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_ASSET_BLOCK = re.compile(
    r'<div class="asset-full-content[^"]*">(.*?)</div>\s*<div class="asset-metadata">',
    re.S | re.I,
)
RE_H1 = re.compile(r"<h1>([^<]+)</h1>", re.I)
RE_LINK = re.compile(r'<a href="([^"]+)"[^>]*>([^<]*)</a>', re.I)
RE_DOC_HREF = re.compile(r'href="(/documents/[^"]+)"', re.I)
RE_CONTENT_LINK = re.compile(
    r'href="(https://sede\.valdemoro\.es/[^"]+/content/[^"]+)"',
    re.I,
)
RE_TRAMITE_LINK = re.compile(
    r'href="(https://sede\.valdemoro\.es/tramites-vivienda-urbanismo/-/asset_publisher/[^"]+/content/[^"]+)"[^>]*>\s*([^<]{3,120})',
    re.I,
)
RE_DOC_ENTRY = re.compile(
    r"([^<\n]{5,120})\s*\(\s*[^)]*-\s*([^)]+\.pdf)\)",
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _clean_title(raw: str) -> str:
    t = unescape(re.sub(r"\s+", " ", raw or "")).strip()
    return t[:500]


def _abs_sede(href: str) -> str:
    return urljoin(f"{SEDE_BASE}/", unescape(href))


def _title_from_doc_url(url: str) -> str:
    path = unquote(url.split("?")[0])
    parts = [p for p in path.split("/") if p]
    for part in reversed(parts):
        if part.lower().endswith(".pdf"):
            name = part[:-4].replace("+", " ").replace("%20", " ")
            return _clean_title(name)
    name = Path(path).name
    if re.fullmatch(r"[0-9a-f-]{36}", name, re.I):
        if len(parts) >= 2:
            return _title_from_doc_url("/".join(parts[:-1]))
    name = name.replace("+", " ").replace("%20", " ")
    return _clean_title(name) or url


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "convenio urban" in n:
        return "convenio urbanístico"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "catálogo" in n or "catalogo" in n:
        return "catálogo patrimonio"
    if "plano" in n or "tomo" in n or "pgou" in n or "plan general" in n:
        return "planeamiento"
    if "ordenanza" in n or "tasa" in n:
        return "normativa fiscal"
    if "edicto" in n:
        return "edicto"
    return "urbanismo"


class ValdemoroAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede Liferay: tablón, PGOU PDF, consulta pública y trámites urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.tablon_max_pages = int(self.config.get("tablon_max_pages", 16))
        self.doc_pages = [str(u) for u in (self.config.get("doc_pages") or DEFAULT_DOC_PAGES)]
        self.tramites_url = str(self.config.get("tramites_url") or DEFAULT_TRAMITES_URL)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-valdemoro/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _parse_liferay_assets(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for block in RE_ASSET_BLOCK.findall(html):
            h1 = RE_H1.search(block)
            if not h1:
                continue
            title = _clean_title(h1.group(1))
            fecha = _parse_fecha_dmy(block)
            doc_links = [
                _abs_sede(h) for h in RE_DOC_HREF.findall(block) if ".pdf" in h.lower()
            ]
            content_links = [
                h if h.startswith("http") else _abs_sede(h)
                for h in RE_CONTENT_LINK.findall(block)
            ]
            web_links = []
            for href, text in RE_LINK.findall(block):
                if "bocm.es" in href:
                    web_links.append(href)
            url = doc_links[0] if doc_links else (content_links[0] if content_links else "")
            if not url:
                url = f"{self.sede_base}/tablon-electronico"
            rows.append(
                {
                    "titulo": title,
                    "fecha": fecha,
                    "url": url,
                    "blob": f"{title} {block[:500]}",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(1, self.tablon_max_pages + 1):
            url = f"{TABLON_BASE}&_101_INSTANCE_5eNJAxVOlRs5_cur={page}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            page_items = self._parse_liferay_assets(html)
            if not page_items and page > 1:
                break
            for row in page_items:
                key = row["titulo"].lower()
                if key in seen:
                    continue
                seen.add(key)
                items.append(row)
        return items

    def _collect_document_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(titulo: str, url: str, fecha: str | None = None, tipo: str = "planeamiento") -> None:
            titulo = _clean_title(titulo)
            if not titulo or url in seen:
                return
            seen.add(url)
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "fecha": fecha,
                    "tipo": tipo,
                    "blob": titulo,
                }
            )

        for page_url in self.doc_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            if "consulta-publica" in page_url:
                for link in RE_CONTENT_LINK.findall(html):
                    link = link.split(";jsessionid")[0]
                    slug_part = link.rsplit("/content/", 1)[-1].split("?")[0]
                    title = slug_part.replace("-", " ").strip()[:500]
                    add(title, link, tipo="información pública")
                for asset in self._parse_liferay_assets(html):
                    add(asset["titulo"], asset["url"], asset.get("fecha"), "información pública")
                continue

            if page_url.endswith("plan-general-de-valdemoro"):
                add("Plan General de Valdemoro (revisión 2004)", page_url, "2004-05-06")
                continue

            if page_url.endswith("planes-parciales"):
                add("Planes Parciales de Valdemoro — índice", page_url)
                continue

            for href in RE_DOC_HREF.findall(html):
                doc_url = _abs_sede(href)
                if doc_url in seen:
                    continue
                title = _title_from_doc_url(doc_url)
                add(title, doc_url)

            for m in RE_DOC_ENTRY.finditer(html):
                title = _clean_title(m.group(1))
                # siguiente enlace document cerca
                idx = m.end()
                chunk = html[idx : idx + 400]
                dm = RE_DOC_HREF.search(chunk)
                if dm:
                    add(title, _abs_sede(dm.group(1)))

            for href, text in RE_LINK.findall(html):
                if "/documents/" not in href or ".pdf" not in href.lower():
                    continue
                doc_url = _abs_sede(href)
                title = _clean_title(text) if text.strip() else _title_from_doc_url(doc_url)
                if title.lower().endswith(".pdf"):
                    title = _title_from_doc_url(doc_url)
                add(title, doc_url)

        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tramites_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in RE_TRAMITE_LINK.findall(html):
            href = href.split(";jsessionid")[0]
            title = _clean_title(title)
            if not RE_LICENCIA.search(title):
                continue
            rec_id = _stable_id("lic", href)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title,
                    "url": href,
                    "source": "ayuntamiento",
                    "nota": "Ficha procedimental sede; no concesión publicada",
                }
            )
        return rows

    def _tablon_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item["titulo"]
        if RE_NOISE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not re.search(r"(?i)vado|licencia", blob):
            return None
        return {
            "id": _stable_id("lic", item["url"]),
            "fecha_concesion": item.get("fecha"),
            "tipo": "licencia" if "licencia" in blob.lower() else "vado/urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"],
            "url": item["url"],
            "source": "ayuntamiento",
        }

    def _tablon_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item["titulo"]
        if RE_NOISE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(
            re.sub(r"(?i)licencia", "", blob)
        ):
            return None
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item["url"],
            "source": "ayuntamiento",
        }

    def _doc_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": item.get("tipo") or _proyecto_tipo(item.get("blob", "")),
            "url": item["url"],
            "source": "ayuntamiento",
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        tramites = self._collect_tramites()
        for item in self._collect_tablon():
            add(self._tablon_to_licencia(item))
        for rec in tramites:
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tramites": len(tramites)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        tablon = self._collect_tablon()
        for item in tablon:
            add(self._tablon_to_proyecto(item))
        for item in self._collect_document_pages():
            add(self._doc_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tablon_items": len(tablon)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
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
