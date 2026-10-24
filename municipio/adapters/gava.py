from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.gavaciutat.cat"
SEDE_BASE = "https://eseu.gava.cat"
MUNICIPIO = "Gavà"
ID_PREFIX = "gava"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/planejament-i-projectes-en-exposicio-publica",
    f"{WEB_BASE}/planejament-aprovat",
    f"{WEB_BASE}/ciutat/urbanisme-i-obres/plans-parcials",
    f"{WEB_BASE}/ciutat/urbanisme-i-obres/plans-especials",
    f"{WEB_BASE}/ciutat/urbanisme-i-obres/estudis-de-detall",
    f"{WEB_BASE}/ciutat/urbanisme-i-obres/modificacions-del-pgm",
    f"{WEB_BASE}/aprovacio-inicial-del-pla-especial-urbanistic-a-l-ambit-de-la-masia-de-can-mas",
    f"{WEB_BASE}/modificacio-puntual-del-pla-parcial-del-sector-pla-de-ponent-",
    f"{WEB_BASE}/plans-de-millora-urbana",
    f"{WEB_BASE}/ciutat-urbanisme-i-obres-programes-d-actuacio-urbanistica",
]

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "llicència d'obres",
    "licencia de obras",
    "llicencia d'obres",
    "comunicació previa",
    "comunicacion previa",
    "declaració responsable",
    "obra menor",
    "obres majors",
    "enderroc",
    "llicència urbanística",
    "licencia urbanística",
    "compatibilitat urbanística",
    "disciplina urbanística",
)

RE_LICENCIA = re.compile(
    r"(?i)(licen[cs]i[ao]|llicen[cs]i[ao]|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:major|menor)|enderroc|reparcel)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|planej|plan (?:parcial|especial|general)|pgm|pgou|mpgm|conveni|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n|expedient|reparcel|modificaci[oó]n|"
    r"delimitaci|gesti[oó] urban|sector|àmbit|ambit|estudi de detall|millora urbana|"
    r"projectes? d.?urbanitzaci|ordenances reguladores|pla parcial|pla especial)",
)
RE_NOISE = re.compile(
    r"(?i)(ordenança fiscal|impost sobre|taxa per serveis urbanístics|iiivtnu|"
    r"proceso selectivo|oposici[oó]n|empleo p[uú]blico)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_HREF = re.compile(r'href="(https://www\.gavaciutat\.cat/[^"#?]+)"', re.I)
RE_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "mpgm" in n or "pgm" in n or "pla general metropolit" in n:
        return "modificación PGM"
    if "pla parcial" in n or "plan parcial" in n or re.search(r"\bpp\b", n):
        return "plan parcial"
    if "pla especial" in n or "plan especial" in n:
        return "plan especial"
    if "estudi de detall" in n:
        return "estudio de detalle"
    if "reparcel" in n:
        return "reparcelación"
    if "conveni" in n:
        return "convenio urbanístico"
    if "millora urbana" in n:
        return "mejora urbana"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "projecte d'urbanitzaci" in n or "projectes d'urbanitzaci" in n:
        return "proyecto de urbanización"
    return "planeamiento"


def _is_urban_url(url: str) -> bool:
    low = url.lower()
    if "gavaciutat.cat" not in low:
        return False
    if low.endswith(".pdf") or "/documents/" in low and ".pdf" in low:
        return False
    keys = (
        "urbanisme",
        "planejament",
        "planeamiento",
        "modificaci",
        "aprovaci",
        "plans-",
        "pla-de-",
        "pla-parcial",
        "masia-de-can",
        "ponent",
        "millora-urbana",
        "actuacio-urbanistica",
        "projectes-de-ciutat",
    )
    return any(k in low for k in keys)


def _noise_pdf(url: str) -> bool:
    low = url.lower()
    return "fulleto+web" in low or "favicon" in low or "apple-touch" in low


class GavaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay (gavaciutat.cat) planejament + sede STA TAO (eseu.gava.cat, catálogo CATSERV)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.catalogo_url = str(
            self.config.get("catalogo_url")
            or f"{self.sede_base}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_CATSERV&lang=CA"
        )
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _ua(self) -> str:
        return str(self.config.get("user_agent") or "poc-bocm-gava/1.0")

    def _fetch(self, url: str, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        url = self._quote_url(url)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        ctx = self._ssl_ctx if sede or self.sede_base.split("//")[-1] in url else None
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _quote_url(self, url: str) -> str:
        parts = urllib.parse.urlsplit(url)
        path = urllib.parse.quote(parts.path, safe="/%:@+&=")
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_CATSERV&lang=CA"
        )

    def _catalog_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url, sede=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            dboid = str(item.get("dboid") or "")
            name = _clean_title(str(item.get("name") or ""))
            if not name or not dboid:
                continue
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _page_title(self, html: str, page_url: str) -> str:
        m = RE_TITLE.search(html)
        if m:
            title = _clean_title(m.group(1))
            title = re.sub(r"\s*-\s*Gavà.*$", "", title, flags=re.I)
            if title and title.lower() != "navegació":
                return title
        slug = page_url.rstrip("/").split("/")[-1]
        return slug.replace("-", " ").title()[:500]

    def _parse_page(self, html: str, page_url: str) -> list[dict[str, Any]]:
        title = self._page_title(html, page_url)
        blob = f"{title} {unescape(re.sub(r'<[^>]+>', ' ', html[:12000]))}"
        rows: list[dict[str, Any]] = []
        pdfs: list[str] = []
        seen_pdf: set[str] = set()
        for pdf in RE_PDF.findall(html):
            pdf_url = self._quote_url(self._abs_web(pdf))
            if _noise_pdf(pdf_url) or pdf_url in seen_pdf:
                continue
            seen_pdf.add(pdf_url)
            pdfs.append(pdf_url)

        if RE_PROYECTO.search(blob) and not RE_NOISE.search(title):
            rows.append(
                {
                    "titulo": title,
                    "fecha": _parse_fecha_dmy(blob),
                    "url": page_url,
                    "pdf_url": pdfs[0] if pdfs else None,
                    "nota": blob[:400],
                    "origen": "liferay_page",
                }
            )

        for pdf_url in pdfs[1:6]:
            name = Path(urllib.parse.urlparse(pdf_url).path).name
            rows.append(
                {
                    "titulo": f"{title} — {name}"[:500],
                    "fecha": _parse_fecha_dmy(blob),
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "origen": "liferay_pdf",
                }
            )
        return rows

    def _collect_web_docs(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        queue: list[str] = list(self.seed_pages)
        rows: list[dict[str, Any]] = []
        max_pages = int(self.config.get("max_crawl_pages", 45))

        while queue and len(seen_urls) < max_pages:
            page_url = queue.pop(0)
            if page_url in seen_urls:
                continue
            seen_urls.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            rows.extend(self._parse_page(html, page_url))
            for link in RE_HREF.findall(html):
                abs_link = self._quote_url(link)
                if not _is_urban_url(abs_link):
                    continue
                if abs_link not in seen_urls and abs_link not in queue:
                    queue.append(abs_link)
        return rows

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        lower = titulo.lower()
        if not any(p in lower for p in LICENCIA_TRAMITE_PATTERNS) and not RE_LICENCIA.search(titulo):
            return None
        if RE_NOISE.search(titulo) and "llicen" not in lower and "licen" not in lower:
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Trámite catálogo sede STA (eseu.gava.cat); sin listado público de concesiones",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('nota', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_NOISE.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        key = row.get("pdf_url") or row.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("nota"):
            rec["nota"] = row["nota"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
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

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for row in self._catalog_rows():
            rec = self._tramite_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._collect_web_docs():
            add(self._row_to_proyecto(row))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_catalogo"}

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
        return {"rows": len(rows), "status": "ok", "source": "liferay_web"}

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
