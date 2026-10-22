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

WEB_BASE = "https://www.ceuta.es/ceuta"
SEDE_BASE = "https://sede.ceuta.es"
MUNICIPIO = "Ceuta"
ID_PREFIX = "ceuta"

TRAMITE_URL = (
    f"{SEDE_BASE}/controlador/controlador?cmd=tramite&modulo=tramites&tramite={{code}}"
)

DEFAULT_PGOU_PAGES: list[str] = [
    f"{WEB_BASE}/trpgouce",
    f"{WEB_BASE}/por-servicios/sede-electronica/152-paginas/paginas/pgou/paginas",
    (
        f"{WEB_BASE}/la-institucion/normativa/152-paginas/paginas/pgou/paginas/"
        "4863-tomo-3-2023"
    ),
]

DEFAULT_BOCCE_CATEGORIES: list[str] = [
    f"{WEB_BASE}/component/jdownloads/viewcategory/1978-julio?Itemid=0",
    f"{WEB_BASE}/component/jdownloads/viewcategory/1971-marzo?Itemid=0",
]

DEFAULT_TRAMITES: list[tuple[str, str]] = [
    ("OMAY", "licencia"),
    ("LOM", "licencia"),
    ("SLDPO", "licencia"),
    ("SPE", "proyecto"),
    ("SAMCI", "proyecto"),
    ("SADCD", "proyecto"),
    ("SGBB", "proyecto"),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n|"
    r"c[eé]dula urban|demolici[oó]n|segregaci[oó]n|parcelaci[oó]n|calificaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio|memoria|planos?|aprobaci[oó]n|revisi[oó]n|bocce|instrumento|"
    r"ordenaci[oó]n|suelo|ruina|sector|normas urban|ape_|apr_|pepch_|sup_|"
    r"cambio de uso|complejo inmobiliario|descalificaci)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proceso selectivo|empleo p[uú]blico|punto limpio|ordenanza fiscal|"
    r"padrones?|impuesto sobre|subvenci[oó]n deportiv|becas?|oposici[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_JDOWNLOAD = re.compile(
    r'href=["\']([^"\']*component/jdownloads/(?:finish|summary|download|viewfile)/[^"\']+)["\']',
    re.I,
)
RE_LINK_TEXT = re.compile(
    r'href=["\']([^"\']+)["\'][^>]*>([^<]{3,200})</a>',
    re.I,
)
RE_H1 = re.compile(r"<h1[^>]*>\s*([^<]+)", re.I)
RE_PAGE_TITLE = re.compile(r"<title>\s*([^<|]+)", re.I)
RE_INSTRUMENT_CODE = re.compile(
    r"\b((?:APE|APR|PEPCH|SUP)_[0-9]{2}_[0-9]{2,3})\b",
    re.I,
)
RE_BOCCE_ITEM = re.compile(
    r"(?m)(\d+)\.-\s*([^\n]{15,400}?)(?:\n|Pág\.|$)",
)
RE_BOCCE_FILE = re.compile(
    r'href=["\']([^"\']*component/jdownloads/finish/[^"\']*bocce[^"\']*)["\']',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                continue
    return None


def _fecha_from_text(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if re.search(r"\bape_", b):
        return "área planeamiento específico"
    if re.search(r"\bapr_", b):
        return "área planeamiento remitido"
    if re.search(r"\bpepch_", b):
        return "plan especial protección conjunto histórico"
    if re.search(r"\bsup_", b):
        return "suelo urbanizable programado"
    if "plan especial" in b:
        return "plan especial"
    if "plan parcial" in b:
        return "plan parcial"
    if "bocce" in b or "decreto" in b and "urban" in b:
        return "disposición urbanística"
    if "cambio de uso" in b:
        return "cambio de uso"
    if "complejo inmobiliario" in b:
        return "complejo inmobiliario"
    return "urbanismo"


class CeutaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal ceuta.es (Joomla/jDownloads) + sede controlador + BOCCE."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.pgou_pages = [str(u) for u in (self.config.get("pgou_pages") or DEFAULT_PGOU_PAGES)]
        self.bocce_categories = [
            str(u) for u in (self.config.get("bocce_categories") or DEFAULT_BOCCE_CATEGORIES)
        ]
        raw_tram = self.config.get("tramites") or DEFAULT_TRAMITES
        self.tramites: list[tuple[str, str]] = [
            (str(a), str(b)) for a, b in raw_tram
        ]
        self.bocce_max_issues = int(self.config.get("bocce_max_issues", 6))
        self._cache_dir: Path | None = None
        cache = self.config.get("http_cache_dir")
        if cache:
            self._cache_dir = Path(str(cache))

    def _cache_path(self, url: str) -> Path | None:
        if not self._cache_dir:
            return None
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
        return self._cache_dir / f"{key}.html"

    def _fetch(self, url: str, timeout: int = 120) -> str:
        cached = self._cache_path(url)
        if cached and cached.is_file():
            return cached.read_text(encoding="utf-8", errors="replace")

        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ceuta/1.0")},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except urllib.error.URLError:
            if cached and cached.is_file():
                return cached.read_text(encoding="utf-8", errors="replace")
            raise

        for enc in ("utf-8", "latin-1", "iso-8859-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
        if cached:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(text, encoding="utf-8")
        return text

    def _abs_url(self, href: str, page_url: str) -> str:
        return unescape(urllib.parse.urljoin(page_url, href))

    def _tramite_url(self, code: str) -> str:
        return TRAMITE_URL.format(code=code)

    def _page_heading(self, html: str, fallback: str) -> str:
        for pat in (RE_H1, RE_PAGE_TITLE):
            m = pat.search(html)
            if m:
                t = _clean_title(m.group(1))
                t = re.sub(r"^Ciudad Autónoma de Ceuta\s*-?\s*", "", t, flags=re.I).strip()
                t = re.sub(r"^Sede Electrónica.*Trámites\s*", "", t, flags=re.I).strip()
                if t and t.lower() not in {"trámites", "documentos"}:
                    return t[:200]
        return fallback

    def _collect_pgou_documents(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(title: str, url: str, pdf_url: str | None, fecha: str | None) -> None:
            key = pdf_url or url + title
            if key in seen:
                return
            seen.add(key)
            items.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": url,
                    "pdf_url": pdf_url,
                    "origen": "pgou_jdownloads",
                }
            )

        for page_url in self.pgou_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = self._page_heading(html, "PGOU Ceuta")
            fecha_page = _fecha_from_text(html) or "2023-12-28"
            for href in RE_JDOWNLOAD.findall(html):
                pdf_url = self._abs_url(href, page_url)
                title = unescape(Path(urllib.parse.urlparse(pdf_url).path).name.replace("-", " "))
                for link_href, link_text in RE_LINK_TEXT.findall(html):
                    if href in link_href or urllib.parse.unquote(href) in link_href:
                        title = _clean_title(link_text) or title
                        break
                if not title or len(title) < 3:
                    title = page_title
                add(title, page_url, pdf_url, _fecha_from_text(title) or fecha_page)

            for code in RE_INSTRUMENT_CODE.findall(html):
                add(
                    f"PGOU 2023 — instrumento {code.upper()}",
                    page_url,
                    None,
                    fecha_page,
                )

            if RE_PROYECTO.search(page_title) and "pgou" in page_title.lower():
                add(
                    "Revisión y Adaptación PGOU Ceuta 2023 (página oficial)",
                    page_url,
                    None,
                    "2023-12-28",
                )

        return items

    def _collect_bocce(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        issue_urls: list[str] = []
        seen_issues: set[str] = set()

        for cat_url in self.bocce_categories:
            try:
                html = self._fetch(cat_url)
            except urllib.error.URLError:
                continue
            for href in RE_BOCCE_FILE.findall(html):
                full = self._abs_url(href, cat_url)
                if full not in seen_issues:
                    seen_issues.add(full)
                    issue_urls.append(full)
            for href in RE_JDOWNLOAD.findall(html):
                full = self._abs_url(href, cat_url)
                if "bocce" in full.lower() and full not in seen_issues:
                    seen_issues.add(full)
                    issue_urls.append(full)

        for issue_url in issue_urls[: self.bocce_max_issues]:
            try:
                html = self._fetch(issue_url, timeout=180)
            except urllib.error.URLError:
                continue
            plain = _clean_title(html)
            fecha = _fecha_from_text(issue_url) or _fecha_from_text(plain)
            for num, body in RE_BOCCE_ITEM.findall(plain):
                blob = f"{num}.- {body}"
                if RE_EXCLUDE.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                items.append(
                    {
                        "titulo": blob[:500],
                        "fecha": fecha,
                        "url": issue_url,
                        "pdf_url": issue_url,
                        "origen": "bocce",
                    }
                )
        return items

    def _collect_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for code, kind_hint in self.tramites:
            url = self._tramite_url(code)
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = self._page_heading(html, code)
            rows.append(
                {
                    "titulo": title,
                    "url": url,
                    "code": code,
                    "kind_hint": kind_hint,
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("titulo") or ""
        if item.get("kind_hint") != "licencia" and not RE_LICENCIA.search(blob):
            return None
        if RE_EXCLUDE.search(blob):
            return None
        return {
            "id": _stable_id("lic", item["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": blob[:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str | None,
        pdf_url: str | None = None,
        origen: str | None = None,
    ) -> dict[str, Any] | None:
        blob = title or ""
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", (pdf_url or url) + title),
            "municipio": MUNICIPIO,
            "titulo": blob[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        if origen:
            rec["origen"] = origen
        return rec

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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tramites():
            if item.get("kind_hint") == "licencia":
                add(self._to_licencia(item))
        for item in self._collect_bocce():
            blob = item["titulo"]
            if RE_LICENCIA.search(blob):
                add(
                    {
                        "id": _stable_id("lic", item["url"] + blob[:80]),
                        "fecha_concesion": item.get("fecha"),
                        "tipo": "licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": blob[:500],
                        "url": item["url"],
                        "source": "ayuntamiento",
                        "origen": "bocce",
                    }
                )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
            "bocce": sum(1 for r in rows if r.get("origen") == "bocce"),
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for doc in self._collect_pgou_documents():
            add(
                self._to_proyecto(
                    doc["titulo"],
                    doc["url"],
                    doc.get("fecha"),
                    pdf_url=doc.get("pdf_url"),
                    origen=doc.get("origen"),
                )
            )

        for item in self._collect_bocce():
            add(
                self._to_proyecto(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                    pdf_url=item.get("pdf_url"),
                    origen=item.get("origen"),
                )
            )

        for item in self._collect_tramites():
            if item.get("kind_hint") == "proyecto":
                add(
                    self._to_proyecto(
                        item["titulo"],
                        item["url"],
                        None,
                        origen=item.get("origen"),
                    )
                )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pgou": sum(1 for r in rows if r.get("origen") == "pgou_jdownloads"),
            "bocce": sum(1 for r in rows if r.get("origen") == "bocce"),
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
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
