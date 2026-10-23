from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "http://www.cerdanyola.cat"
SEU_E_BASE = "https://seu-e.cat"
SEDE_BASE = "https://seu.cerdanyola.cat"
ETAULER_URL = "https://tauler.seu.cat/inici.do?idens=826650006"
SIG_VISOR_ALIN = (
    "http://sig.cerdanyola.cat/enmapa/visor/alin?"
    "centre=426101.0,4592549.0&capes=T5248,T5251,T5254&escala=40000"
)
MUNICIPIO = "Cerdanyola del Vallès"
ID_PREFIX = "cerdanyola"
INE_MUN = "08074"

SEU_E_URBANISME = (
    f"{SEU_E_BASE}/ca/web/cerdanyoladelvalles/govern-obert-i-transparencia/"
    "accio-de-govern-i-normativa/urbanisme"
)

DEFAULT_DRUPAL_SEEDS: list[str] = [
    f"{WEB_BASE}/urbanisme",
    f"{WEB_BASE}/urbanisme/actualitat",
    f"{WEB_BASE}/urbanisme/projectes-aprovats",
    f"{WEB_BASE}/urbanisme/informacio-urbanistica",
    f"{WEB_BASE}/la-ciutat/guia/punt-dinformacio-geografica",
    f"{WEB_BASE}/descarrega-de-cartografia",
    f"{WEB_BASE}/servituds-aeronautiques",
    f"{WEB_BASE}/xarxa-geodesica-local",
    (
        f"{WEB_BASE}/actualitat/el-tsjc-avala-el-desenvolupament-del-parc-de-lalba-"
        "i-en-mante-vigent-el-planejament"
    ),
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (SEDE_BASE, "Seu electrònica — tràmits i carpeta ciutadana"),
    (ETAULER_URL, "e-Tauler d'anuncis (Consorci Administració Oberta de Catalunya)"),
    (
        f"{SEU_E_BASE}/ca/web/cerdanyoladelvalles/govern-obert-i-transparencia/"
        "serveis-i-tramits/tramits",
        "Catàleg de tràmits (seu-e.cat)",
    ),
    (
        f"{SEU_E_URBANISME}/normativa-d-urbanisme",
        "Normativa d'urbanisme (transparència)",
    ),
    (SIG_VISOR_ALIN, "Visor SIG — alineacions urbanístiques (plànol no normatiu)"),
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autoritzaci[oó] d.?obres|autorizaci[oó]n de obra|obra (?:major|menor)|"
    r"primera ocupaci[oó]|parcel·laci[oó]|parcelaci[oó]n|enderroc)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|plan (?:parcial|especial|general)|pgou|pgm|"
    r"informaci[oó]n p[uú]blica|exposici[oó] p[uú]blica|expedient|projecte|proyecto|"
    r"modificaci[oó]n|reparcel|consulta pr[eè]via|aprovaci[oó]|parc de l.?alba|"
    r"alba|sector|ordenan[cç]a|cartograf|geod[eè]s|servitud|amiant|cens|sig|visor|"
    r"alineaci|desenvolupament|normativa|document|memoria|estudi)",
)
RE_SKIP = re.compile(
    r"(?i)(corretapes|halloween|castanyes|selecci[oó] de personal|hub textil|"
    r"jornades d.arxius|teatre ateneu|mobles i voluminosos)",
)
RE_LIFERAY_DOC = re.compile(r"/documents/\d+/[^\"'\s<>\\]+", re.I)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)
RE_DATE_META = re.compile(
    r'class="date-display-single"[^>]*content="(\d{4}-\d{2}-\d{2})"',
    re.I,
)
RE_ACTUALITAT_LINK = re.compile(
    r'views-field-title[^>]*>.*?<a href="(/actualitat/[^"]+)"[^>]*>([^<]+)</a>',
    re.S | re.I,
)
RE_SLUG_URBAN = re.compile(
    r"(?i)(urban|planej|parc|alba|llic|licen|obra|pgou|tsjc|norma|amiant|cens|"
    r"consulta|informaci|desenvolupament|cartograf|servitud|geod|sig|visor)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_ISO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1995 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-06-01"
    return None


def _title_from_liferay_path(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0].rstrip("/"))
    parts = path.split("/")
    for part in reversed(parts):
        if part and not re.fullmatch(r"[0-9a-f-]{36}", part, re.I) and part.isdigit() is False:
            name = part.replace("+", " ")
            if len(name) > 8:
                return _strip_html(name)[:500]
    return url[:500]


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "consulta pr" in n:
        return "consulta previa"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "ordenan" in n:
        return "ordenanza urbanística"
    if "parc" in n and "alba" in n:
        return "planeamiento / Parc de l'Alba"
    if "cartograf" in n or "geod" in n or "sig" in n or "visor" in n:
        return "información geográfica urbanística"
    if "cens" in n and "amiant" in n:
        return "cens municipal instalaciones"
    if "servitud" in n:
        return "servidumbre aeronáutica"
    if "pgou" in n or "planej" in n or "avanç" in n:
        return "planeamiento"
    if "aprovaci" in n:
        return "aprobación normativa"
    return "urbanismo"


class CerdanyolaDelVallesAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 7 cerdanyola.cat + seu-e (Liferay) + seu STA (referencia) + e-Tauler."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seu_e_base = str(self.config.get("seu_e_base") or SEU_E_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_DRUPAL_SEEDS)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _ua(self) -> str:
        return str(self.config.get("user_agent") or "poc-bocm-cerdanyola/1.0")

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        if url.startswith("https://"):
            with urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

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

    def _page_title_fecha(self, html: str, url: str) -> tuple[str, str | None]:
        h1 = RE_H1.search(html)
        title = _strip_html(h1.group(1)) if h1 else _title_from_liferay_path(url)
        fecha = None
        dm = RE_DATE_META.search(html)
        if dm:
            fecha = dm.group(1)
        if not fecha:
            fecha = _parse_fecha_dmy(html[:8000]) or _parse_fecha_dmy(url)
        return title[:500], fecha

    def _drupal_row_from_page(self, url: str, origen: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
        title, fecha = self._page_title_fecha(html, url)
        blob = f"{title} {_strip_html(html[:12000])}"
        if RE_SKIP.search(blob):
            return None
        pdf = None
        for m in RE_PDF.findall(html):
            pdf = self._abs_web(m)
            break
        return {
            "titulo": title,
            "fecha": fecha,
            "url": pdf or url,
            "page_url": url,
            "origen": origen,
            "blob": blob[:2000],
        }

    def _collect_rss(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            raw = self._fetch(f"{self.web_base}/rss.xml", timeout=60)
            root = ET.fromstring(raw)
        except (urllib.error.URLError, ET.ParseError, TimeoutError, OSError):
            return rows
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "")[:25]
            blob = f"{title} {item.findtext('description') or ''}"
            if not link or not RE_PROYECTO.search(blob):
                continue
            fecha = _parse_fecha_dmy(pub) if pub else None
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": link,
                    "origen": "drupal_rss",
                    "blob": _strip_html(blob)[:1500],
                }
            )
        return rows

    def _collect_actualitat(self, max_pages: int = 12) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(max_pages):
            try:
                html = self._fetch(f"{self.web_base}/actualitat?page={page}", timeout=45)
            except (urllib.error.URLError, TimeoutError, OSError):
                break
            matches = RE_ACTUALITAT_LINK.findall(html)
            if not matches:
                break
            for path, title in matches:
                title = _strip_html(title)
                if path in seen:
                    continue
                if not RE_SLUG_URBAN.search(path) and not RE_PROYECTO.search(title):
                    continue
                seen.add(path)
                url = self._abs_web(path)
                row = self._drupal_row_from_page(url, "drupal_actualitat")
                if row:
                    rows.append(row)
        return rows

    def _liferay_urban_pages(self) -> list[str]:
        pages = [SEU_E_URBANISME]
        try:
            html = self._fetch(SEU_E_URBANISME)
        except urllib.error.URLError:
            return pages
        for m in re.finditer(
            r'href="(https://seu-e\.cat/ca/web/cerdanyoladelvalles/govern-obert-i-transparencia/'
            r'accio-de-govern-i-normativa/urbanisme/[^"]+)"',
            html,
        ):
            pages.append(unescape(m.group(1)))
        return list(dict.fromkeys(pages))

    def _collect_liferay_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in self._liferay_urban_pages():
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                continue
            for m in RE_LIFERAY_DOC.finditer(html):
                path = unescape(m.group(0).split('"')[0].split("'")[0])
                url = f"{self.seu_e_base}{path}"
                if url in seen:
                    continue
                seen.add(url)
                title = _title_from_liferay_path(url)
                rows.append(
                    {
                        "titulo": title,
                        "fecha": _parse_fecha_dmy(title) or _parse_fecha_dmy(url),
                        "url": url,
                        "origen": "seu_e_liferay",
                        "blob": f"{title} {page}",
                    }
                )
        return rows

    def _collect_drupal_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self.seed_pages:
            row = self._drupal_row_from_page(url, "drupal_semilla")
            if row:
                rows.append(row)
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('blob', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or row.get("page_url") or row.get("titulo", "")
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or row.get("page_url") or self.web_base,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for source in (
            self._collect_liferay_docs(),
            self._collect_rss(),
            self._collect_drupal_seeds(),
            self._collect_actualitat(),
        ):
            for row in source:
                add(self._row_to_proyecto(row))
        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo in DEFAULT_LICENCIA_PAGES:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite / información licencias",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": (
                        "Sin tablón STA descargable en cloud; anuncios en e-Tauler (idens 826650006). "
                        "Catálogo de trámites en seu.cerdanyola.cat / seu-e."
                    ),
                    "origen": "pagina_informativa",
                }
            )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "paginas_tramite"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "drupal_seu_e_rss",
            "liferay": sum(1 for r in rows if r.get("origen") == "seu_e_liferay"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
