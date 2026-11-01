from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.tomelloso.es"
ETABLON_BASE = "https://etablon.dipucr.es:4443/eTablon"
ETABLON_ENTIDAD = "037"
MUNICIPIO = "Tomelloso"
ID_PREFIX = "tomelloso"

INFO_URBANISTICA = f"{BASE}/urbanismo-y-obras/informacion-urbanistica"
INFO_JURIDICA = f"{BASE}/ayuntamiento/gobierno-abierto/informacion-de-relevancia-juridica"
TABLON_URL = f"{ETABLON_BASE}/tablon.jsf?entidad={ETABLON_ENTIDAD}"
TRAMITES_URBANISMO = f"{BASE}/sede/catalogo/tramites-de-urbanismo-y-obras"

DEFAULT_SEED_PAGES: list[str] = [
    INFO_URBANISTICA,
    INFO_JURIDICA,
]

DEFAULT_LICENCIA_PATHS: list[str] = [
    "/sede/catalogo-de-tramites/licencia-de-obra-mayor",
    "/sede/catalogo-de-tramites/licencia-de-obra-menor",
    "/sede/catalogo-de-tramites/comunicacion-previa-de-obras",
    "/sede/catalogo-de-tramites/licencias-de-parcelacion",
    (
        "/sede/catalogo-de-tramites/expedientes-de-solicitud-de-licencia-para-actividades-"
        "y-en-su-caso-para-realizacion-de-obras-de-edificacion-o-adecuacion-del-establecimiento"
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|parcelaci[oó]n|obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pau|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|memoria|planos|ordenanza|sector|pol[ií]gono|peri|"
    r"programa de actuaci[oó]n|unidad de (?:ejecuci[oó]n|actuaci[oó]n)|alternativa t[eé]cnica)",
)
RE_TABLON_NOISE = re.compile(
    r"(?i)(proceso selectivo|empleo p[uú]blico|subvenci[oó]n|padrones?|padr[oó]n|"
    r"escuela (?:infantil|matinal)|concurso de escaparatismo|festejos|navidad)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD_IN_NAME = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DYN_ITEM = re.compile(r'<div role="listitem" class="w-dyn-item">(.*?)</div>\s*</div>\s*</div>', re.S)
RE_VISIBLE_LINK = re.compile(
    r'<a href="([^"]+)"[^>]*class="link-tramite-verde w-inline-block"(?! w-condition-invisible)',
    re.I,
)
RE_H6_TITLE = re.compile(r'<h6 class="paragraph grow-if-possible">([^<]+)</h6>')
RE_PAGE_H2 = re.compile(r'<h1 class="heading h2">([^<]+)</h1>', re.I)
RE_TRAMITE_LINK = re.compile(
    r'href="(/sede/catalogo-de-tramites/[^"#?]+)"',
    re.I,
)


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YMD_IN_NAME.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1990 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "convenio urban" in b:
        return "convenio urbanístico"
    if "programa de actuaci" in b or "pau" in b:
        return "programa de actuación urbanizadora"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "modificaci" in b and ("puntual" in b or "pgou" in b):
        return "modificación puntual PGOU"
    if "pgou" in b or "plan general" in b:
        return "planeamiento general"
    if "ordenanza" in b or "peri" in b:
        return "ordenanza / PERI"
    if "plan parcial" in b or "polígono industrial" in b:
        return "plan parcial"
    return "urbanismo"


class TomellosoAyuntamientoAdapter(AyuntamientoAdapter):
    """Webflow municipal (CMS) + tablón Diputación Ciudad Real (eTablon JSF)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_paths = [str(p) for p in (self.config.get("licencia_paths") or DEFAULT_LICENCIA_PATHS)]
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.etablon_base = str(self.config.get("etablon_base") or ETABLON_BASE).rstrip("/")
        self.etablon_entidad = str(self.config.get("etablon_entidad") or ETABLON_ENTIDAD)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        opener = self._opener if sede or self.config.get("insecure_ssl", True) else urllib.request.build_opener()
        with opener.open(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{BASE}/", unescape(href).replace("&amp;", "&"))

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

    def _parse_webflow_cards(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for block in RE_DYN_ITEM.findall(html):
            for m in RE_VISIBLE_LINK.finditer(block):
                url = self._abs_url(m.group(1))
                if url.rstrip("/") == page_url.rstrip("/"):
                    continue
                local = block[m.start() : m.end() + 600]
                tm = RE_H6_TITLE.search(local)
                if not tm:
                    continue
                titulo = unescape(re.sub(r"\s+", " ", tm.group(1)).strip())
                key = f"{titulo}|{url}"
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": url,
                        "fecha": _fecha_from_blob(f"{titulo} {url}"),
                        "page_url": page_url,
                        "origen": "webflow",
                    }
                )
        return rows

    def _parse_etablon(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row_html in re.findall(r'<tr class="rich-table-row[^"]*">(.*?)</tr>', html, re.S):
            titulo_m = re.search(r'class="publicacion"><span[^>]*>([^<]+)', row_html)
            archivo_m = re.search(r"'nombreArchivo':'([^']+)'", row_html)
            desc_m = re.search(r'tabla_publicaciones:\d+:j_id73[^>]*>([^<]+)', row_html)
            if not titulo_m:
                continue
            titulo = _strip_html(titulo_m.group(1))
            descripcion = _strip_html(desc_m.group(1)) if desc_m else titulo
            blob = f"{titulo} {descripcion}"
            pdf_url = None
            if archivo_m:
                pdf_url = f"{self.etablon_base}/documentos/{self.etablon_entidad}/{archivo_m.group(1)}"
            url = pdf_url or self.tablon_url
            rows.append(
                {
                    "titulo": (descripcion if len(descripcion) > len(titulo) else titulo)[:500],
                    "url": url,
                    "pdf_url": pdf_url,
                    "fecha": _fecha_from_blob(blob),
                    "page_url": self.tablon_url,
                    "origen": "etablon",
                    "categoria": _strip_html(
                        re.search(r'tabla_publicaciones:\d+:j_id81[^>]*>([^<]+)', row_html).group(1)
                        if re.search(r'tabla_publicaciones:\d+:j_id81[^>]*>([^<]+)', row_html)
                        else ""
                    ),
                }
            )
        return rows

    def _collect_proyectos_raw(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for rec in self._parse_webflow_cards(html, page_url):
                by_key[f"wf|{rec['titulo']}|{rec['url']}"] = rec
        try:
            tablon_html = self._fetch(self.tablon_url, sede=True)
            for rec in self._parse_etablon(tablon_html):
                if RE_TABLON_NOISE.search(rec["titulo"]):
                    continue
                if not RE_PROYECTO.search(rec["titulo"]) and not RE_PROYECTO.search(
                    rec.get("categoria", "")
                ):
                    continue
                by_key[f"et|{rec['titulo']}|{rec['url']}"] = rec
        except urllib.error.URLError:
            pass
        return list(by_key.values())

    def _to_proyecto_row(self, rec: dict[str, Any]) -> dict[str, Any]:
        blob = f"{rec['titulo']} {rec.get('categoria', '')}"
        url = rec["url"]
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": rec["titulo"],
            "fecha": rec.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "pdf_url": rec.get("pdf_url") or (url if url.lower().endswith(".pdf") else None),
            "source": "ayuntamiento",
            "origen": rec.get("origen"),
            "seed_page": rec.get("page_url"),
        }

    def _collect_licencias_pages(self) -> list[dict[str, Any]]:
        urls: set[str] = {self._abs_url(p) for p in self.licencia_paths}
        try:
            html = self._fetch(TRAMITES_URBANISMO)
            for m in RE_TRAMITE_LINK.finditer(html):
                link = self._abs_url(m.group(1))
                if RE_LICENCIA.search(link):
                    urls.add(link)
        except urllib.error.URLError:
            pass

        rows: list[dict[str, Any]] = []
        for url in sorted(urls):
            try:
                page = self._fetch(url)
            except urllib.error.URLError:
                continue
            tm = RE_PAGE_H2.search(page)
            title = unescape(tm.group(1).strip()) if tm else url.rsplit("/", 1)[-1].replace("-", " ")
            if not RE_LICENCIA.search(title) and not RE_LICENCIA.search(url):
                continue
            pdfs = re.findall(
                r'href="(https://cdn\.prod\.website-files\.com/[^"]+\.pdf)"',
                page,
                re.I,
            )
            rec: dict[str, Any] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": url,
                "source": "ayuntamiento",
                "nota": "Página informativa de trámites; no hay listado público de concesiones",
            }
            if pdfs:
                rec["pdf_url"] = unescape(pdfs[0])
            rows.append(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_catalogo"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_pages():
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
        rows = [self._to_proyecto_row(r) for r in self._collect_proyectos_raw()]
        rows = [r for r in rows if RE_PROYECTO.search(r["titulo"]) or r.get("origen") == "webflow"]
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos_raw():
            row = self._to_proyecto_row(rec)
            if not RE_PROYECTO.search(row["titulo"]) and row.get("origen") != "webflow":
                continue
            if row["id"] not in existing:
                added += 1
            existing[row["id"]] = row
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
