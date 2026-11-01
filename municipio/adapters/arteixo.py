from __future__ import annotations

import hashlib
import http.cookiejar
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

SEDE_BASE = "https://sede.arteixo.org"
WEB_BASE = "https://arteixo.org"
MUNICIPIO = "Arteixo"
ID_PREFIX = "arteixo"
INE_CONCELLO = "15005"

TABLON_INDEX = f"{SEDE_BASE}/sxc/es/informacion/tablon/index.html"
TRAMITES_URL = f"{SEDE_BASE}/sxc/es/procedimientosytramites/"
SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE_CONCELLO}&lang=es_ES"
)
SIOTUGA_QUERY = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"
SIOTUGA_URB = "https://siotuga.xunta.gal/siotuga/urb?lang=es_ES"
URBANISMO_WEB = f"{WEB_BASE}/servizos/urbanismo/"

RE_TABLON_ITEM = re.compile(
    r'<div class="noticia top40">.*?'
    r'<a href="([^"]+)"\s*\n\s*title="Ver noticia">\s*([^<]+?)\s*</a>.*?'
    r'<p class="fecha">(\d{2}/\d{2}/\d{4})</p>\s*<p>([^<]+)</p>',
    re.I | re.S,
)
RE_PDF_ANEXO = re.compile(
    r'href="(/sxc/export/sites/arteixo/recursos/downloads/Tablon/[^"]+\.pdf)"',
    re.I,
)
RE_TRAMITE_LINK = re.compile(
    r'href="(/sxc/es/procedimientosytramites/tramites/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licen|comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n|"
    r"primera ocupaci|certificado urban|edificaci[oó]n|demolici[oó]n|obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pxom|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n|expediente|proyecto|modificaci[oó]n|"
    r"reparcel|equidistribuci[oó]n|urbanizaci[oó]n|sector|sunp|unidad de actuaci|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|rehabilitaci[oó]n integral)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proceso selectivo|convocatoria.*plaza|personal y rr\.?hh|persoal e rr\.?hh|"
    r"oficial de polic|capataz|animador|coordinador)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _abs_url(path: str) -> str:
    if path.startswith("http"):
        return path
    return urllib.parse.urljoin(SEDE_BASE, path)


def _proyecto_tipo(section: str, titulo: str, figura: str | None = None) -> str:
    blob = f"{section} {titulo} {figura or ''}".lower()
    if "plan especial" in blob or "peid" in blob:
        return "plan especial"
    if "equidistribuci" in blob:
        return "equidistribución urbanística"
    if "urbanizaci" in blob:
        return "proyecto de urbanización"
    if "convenio" in blob or "concerto" in blob or "compensaci" in blob:
        return "convenio / sistema de actuación"
    if "rehabilitaci" in blob and "integral" in blob:
        return "área de rehabilitación integral"
    if "normas subsidiarias" in blob:
        return "normas subsidiarias"
    if "exposici" in blob or "informaci" in blob:
        return "información pública"
    if "planeam" in blob or "urban" in blob:
        return "planeamiento"
    return section or "urbanismo"


class ArteixoAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede Diputación A Coruña (SXC) tablón + trámites urbanismo; inventario SIOTUGA (INE 15005)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.max_tablon_pages = int(self.config.get("max_tablon_pages", 30))
        self.max_siotuga_docs = int(self.config.get("max_siotuga_docs", 80))
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        self._siotuga_token_cache: str | None = None

    def _fetch(
        self,
        url: str,
        *,
        data: bytes | None = None,
        delay: bool = True,
    ) -> str:
        if delay:
            time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-arteixo/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=90) as resp:
            enc = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(enc, errors="replace")

    def _post_json(self, url: str, fields: dict[str, str]) -> Any:
        body = urllib.parse.urlencode(fields).encode()
        raw = self._fetch(url, data=body)
        if not raw.strip() or raw.startswith("tokenIncorrecto"):
            return None
        return json.loads(raw)

    def _parse_tablon_html(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for href, section, fecha_raw, summary in RE_TABLON_ITEM.findall(html):
            section_clean = _strip_html(section)
            summary_clean = _strip_html(summary)[:500]
            if RE_EXCLUDE.search(f"{section_clean} {summary_clean}"):
                continue
            if not RE_PROYECTO.search(f"{section_clean} {summary_clean}") and not RE_LICENCIA.search(
                summary_clean
            ):
                if "urbanismo" not in section_clean.lower():
                    continue
            url = _abs_url(href)
            rows.append(
                {
                    "section": section_clean,
                    "titulo": summary_clean or section_clean,
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "origen": "sede_tablon",
                }
            )
        return rows

    def _collect_tablon_pages(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        out: list[dict[str, Any]] = []
        for page in range(1, self.max_tablon_pages + 1):
            suffix = f"?page={page}" if page > 1 else ""
            try:
                html = self._fetch(f"{TABLON_INDEX}{suffix}")
            except urllib.error.URLError:
                break
            batch = self._parse_tablon_html(html)
            if not batch:
                break
            new = 0
            for item in batch:
                if item["url"] in seen_urls:
                    continue
                seen_urls.add(item["url"])
                out.append(item)
                new += 1
            if new == 0:
                break
        return out

    def _collect_tablon_search(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for query in ("Urbanismo", "planeamiento", "licencia obra"):
            try:
                html = self._fetch(
                    TABLON_INDEX,
                    data=urllib.parse.urlencode({"query": query, "search": "search"}).encode(),
                )
            except urllib.error.URLError:
                continue
            rows.extend(self._parse_tablon_html(html))
        return rows

    def _enrich_pdf_url(self, item: dict[str, Any]) -> None:
        if item.get("pdf_url"):
            return
        try:
            detail = self._fetch(item["url"])
        except urllib.error.URLError:
            return
        m = RE_PDF_ANEXO.search(detail)
        if m:
            item["pdf_url"] = _abs_url(m.group(1))

    def _get_siotuga_token(self) -> str | None:
        if self._siotuga_token_cache:
            return self._siotuga_token_cache
        try:
            html = self._fetch(SIOTUGA_INVENTARIO)
        except urllib.error.URLError:
            return None
        m = re.search(r"id='token'[^>]+value='([^']+)'", html)
        if not m:
            return None
        self._siotuga_token_cache = m.group(1)
        return self._siotuga_token_cache

    def _collect_siotuga(self) -> list[dict[str, Any]]:
        token = self._get_siotuga_token()
        if not token:
            return []
        rows: list[dict[str, Any]] = []
        for idclase, origen in (("14", "siotuga_xeral"), ("13", "siotuga_desenvolvemento")):
            data = self._post_json(
                SIOTUGA_QUERY,
                {"id": INE_CONCELLO, "token": token, "idclase": idclase},
            )
            if not isinstance(data, list):
                continue
            for doc in data[: self.max_siotuga_docs]:
                doc_id = str(doc.get("id") or "")
                title = unescape(str(doc.get("docnome") or "").strip())
                if not doc_id or not title:
                    continue
                figura = str(doc.get("figura") or "")
                fecha = str(doc.get("fechaaddef") or doc.get("fechadog") or "") or None
                rows.append(
                    {
                        "titulo": f"{title} ({figura})" if figura else title,
                        "fecha": fecha,
                        "url": f"{SIOTUGA_INVENTARIO}#doc-{doc_id}",
                        "figura": figura,
                        "origen": origen,
                        "siotuga_id": doc_id,
                    }
                )
        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TRAMITES_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in RE_TRAMITE_LINK.findall(html):
            title_clean = _strip_html(title)
            if not RE_LICENCIA.search(title_clean):
                continue
            url = _abs_url(href)
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": title_clean,
                    "url": url,
                    "fecha": None,
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _fixed_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Urbanismo — web corporativa Concello de Arteixo",
                "fecha": None,
                "url": URBANISMO_WEB,
                "tipo": "información urbanismo",
                "origen": "web_urbanismo",
            },
            {
                "titulo": "Inventario planeamento municipal — SIOTUGA (INE 15005)",
                "fecha": None,
                "url": SIOTUGA_INVENTARIO,
                "tipo": "inventario planeamiento",
                "origen": "siotuga_inventario",
            },
            {
                "titulo": "Planeamento urbanístico — SIOTUGA Xunta (tabla municipios)",
                "fecha": None,
                "url": SIOTUGA_URB,
                "tipo": "planeamiento autonómico",
                "origen": "siotuga_urb",
            },
        ]

    def _merge_tablon(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for item in self._collect_tablon_pages() + self._collect_tablon_search():
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            merged.append(item)
        return merged

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("pdf_url") or row.get("url") or self.sede_base
        section = row.get("section") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{url}|{titulo}|{row.get('siotuga_id','')}"),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(section, titulo, row.get("figura")),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("siotuga_id"):
            rec["siotuga_doc_id"] = row["siotuga_id"]
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
        return {
            "id": _stable_id("lic", url + titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite / anuncio urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def _collect_proyecto_sources(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._fixed_seeds())
        rows.extend(self._collect_siotuga())
        tablon = self._merge_tablon()
        for item in tablon:
            section = (item.get("section") or "").lower()
            blob = f"{item.get('section','')} {item['titulo']}"
            if "planeamiento" in section or RE_PROYECTO.search(blob):
                if not RE_EXCLUDE.search(blob):
                    self._enrich_pdf_url(item)
                    rows.append(item)
        return rows

    def _collect_licencia_sources(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._collect_tramites())
        for item in self._merge_tablon():
            blob = f"{item.get('section','')} {item['titulo']}"
            if RE_LICENCIA.search(blob) and not RE_EXCLUDE.search(blob):
                rows.append({**item, "origen": "sede_tablon_licencia"})
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_licencia_sources():
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
        }

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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_proyecto_sources():
            rec = self._to_proyecto(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if "tablon" in str(r.get("origen", ""))),
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
        }

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
