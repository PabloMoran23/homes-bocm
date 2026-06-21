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

BASE = "https://www.ssreyes.org"
SEDE = "https://sede.ssreyes.es"
TRANSP = "https://transparencia.ssreyes.org"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/normativa-urban%C3%ADstica",
    f"{BASE}/planos",
    f"{BASE}/avance-revisi%C3%B3n-plan-general",
    f"{BASE}/nuevos-desarrollos-urban%C3%ADsticos",
    f"{BASE}/plan-general-de-ordenaci%C3%B3n-urbana-p.-g.-o.-u.-2001",
    (
        f"{BASE}/aprobaci%C3%B3n-definitiva-plan-especial-de-entidades-urban%C3%ADsticas-"
        "de-conservaci%C3%B3n-en-determinados-%C3%81mbitos"
    ),
    f"{BASE}/aprobaci%C3%B3n-inicial-9%C2%AA-modificaci%C3%B3n-puntual-z.o.-59",
    f"{BASE}/acuerdos-de-la-comisi%C3%B3n-t%C3%A9cnica-de-seguimiento-del-pgou",
    f"{BASE}/gesti%C3%B3n-urban%C3%ADstica",
    f"{BASE}/planeamiento-y-gesti%C3%B3n-urban%C3%ADstica",
    f"{BASE}/es/desarrollo-urbano",
    f"{BASE}/es/sistema-de-informaci%C3%B3n-territorial-de-urbanismo",
    f"{TRANSP}/informaci%C3%93n-urban%C3%8Dstica-y-medioambiental",
]

DEFAULT_LICENCIA_URLS: list[tuple[str, str]] = [
    (f"{BASE}/es/licencias-de-actividad", "licencia de actividad"),
    (f"{BASE}/es/obras-e-infraestructuras", "licencia de obra"),
    (f"{SEDE}/sedeForms/IndexPage?metodo=LIQUI_LicenciaObra", "autoliquidación licencia de obra"),
    (f"{SEDE}/sedeForms/IndexPage?metodo=LIQUI_LicenciaActividad", "autoliquidación licencia de actividad"),
    (f"{SEDE}/sedeForms/IndexPage?metodo=LIQUI_LicenciaVeladores", "autoliquidación licencia veladores"),
    (f"{SEDE}/sedeForms/IndexPage?metodo=LIQUI_OcupacionVia", "autoliquidación ocupación vía pública"),
]

RE_DOC_LINK = re.compile(
    r'href="((?:https://(?:www\.)?ssreyes\.org)?/documents/[^"]+)"[^>]*title="([^"]*)"',
    re.I,
)
RE_SUBPAGE = re.compile(
    r'href="(https://(?:www\.)?ssreyes\.org/[^"#?]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|ocupaci[oó]n.*v[ií]a|velador)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental)|memoria|planos|norma|ordenanza|anexo|"
    r"aprobaci[oó]n|acuerdo|comisi[oó]n|desarrollo|suelo|gesti[oó]n urban)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"ssreyes-{prefix}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_url(url: str) -> str | None:
    m = re.search(r"[?&]t=(\d{13})", url)
    if m:
        try:
            ts = int(m.group(1)) / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(url) if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>([^<]+)',
        r"<h1[^>]*>([^<]+)",
        r"<title>([^<]+)",
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*ssreyes.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3 and "verificando" not in t.lower():
                return t[:500]
    return fallback


class SanSebastianDeLosReyesAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay: documentos PGOU/planeamiento + trámites informativos de licencia en sede."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.4))
        self.browser_cookie = str(self.config.get("browser_cookie", "browser_verified=1"))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        raw_lic = self.config.get("licencia_urls")
        if raw_lic:
            self.licencia_urls = [(p["url"], p.get("tipo", "licencia")) for p in raw_lic]
        else:
            self.licencia_urls = list(DEFAULT_LICENCIA_URLS)
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 60))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-ssreyes/1.0"),
                "Cookie": self.browser_cookie,
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, page_url: str = BASE) -> str:
        if href.startswith("http"):
            return href
        base = SEDE if page_url.startswith(SEDE) else (TRANSP if "transparencia" in page_url else BASE)
        return urllib.parse.urljoin(base, href)

    def _extract_documents(self, html: str, page_url: str) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for m in RE_DOC_LINK.finditer(html):
            href = self._abs_url(m.group(1), page_url)
            if "intranet.ssreyes" in href:
                continue
            title = unescape(m.group(2).strip())
            if not title:
                title = unescape(Path(urllib.parse.unquote(href)).name)[:200]
            if not title or href in seen:
                continue
            if not re.search(r"document-pdf|\.pdf", html[max(0, m.start() - 80) : m.end() + 80], re.I):
                if ".pdf" not in href.lower() and not title.lower().endswith(".pdf"):
                    continue
            seen.add(href)
            out.append({"titulo": title[:500], "url": page_url, "pdf_url": href})
        return out

    def _discover_subpages(self, html: str) -> list[str]:
        found: list[str] = []
        for m in RE_SUBPAGE.finditer(html):
            u = m.group(1).rstrip("/")
            if any(
                k in u.lower()
                for k in (
                    "urban",
                    "plan",
                    "pgou",
                    "desarrollo",
                    "normativa",
                    "obra",
                    "modific",
                    "aprob",
                    "gesti",
                    "plano",
                    "comisi",
                )
            ):
                if u not in found and u not in self.seed_pages:
                    found.append(u)
        return found

    def _crawl_proyecto_documents(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue: list[str] = list(self.seed_pages)
        docs: list[dict[str, Any]] = []
        seen_pdf: set[str] = set()

        while queue and len(visited) < self.max_crawl_pages:
            page_url = queue.pop(0).rstrip("/")
            if page_url in visited:
                continue
            visited.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            if "verificando navegador" in html.lower():
                continue

            for sub in self._discover_subpages(html):
                if sub not in visited and sub not in queue:
                    queue.append(sub)

            for doc in self._extract_documents(html, page_url):
                pdf = doc["pdf_url"]
                if pdf in seen_pdf:
                    continue
                titulo = doc["titulo"]
                blob = f"{titulo} {page_url}"
                if not RE_PROYECTO.search(blob) and page_url not in self.seed_pages:
                    continue
                seen_pdf.add(pdf)
                tipo = "planeamiento"
                if re.search(r"(?i)modificaci[oó]n", blob):
                    tipo = "modificación puntual"
                elif re.search(r"(?i)plan especial", blob):
                    tipo = "plan especial"
                elif re.search(r"(?i)acuerdo|comisi[oó]n", blob):
                    tipo = "acuerdo comisión PGOU"
                elif re.search(r"(?i)normativa|normas", blob):
                    tipo = "normativa PGOU"
                docs.append(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": "San Sebastián de los Reyes",
                        "titulo": titulo,
                        "fecha": _fecha_from_url(pdf) or _parse_fecha_dmy(titulo),
                        "tipo": tipo,
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": page_url,
                    }
                )

        return docs

    def _collect_licencias_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, tipo_default in self.licencia_urls:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = _page_title(html, tipo_default)
            if "verificando navegador" in html.lower():
                continue
            rec: dict[str, Any] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": tipo_default,
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": url,
                "source": "ayuntamiento",
                "nota": "Trámite informativo; no concesión publicada en tablón",
            }
            rows.append(rec)

            for doc in self._extract_documents(html, url):
                if not RE_LICENCIA.search(doc["titulo"]):
                    continue
                rows.append(
                    {
                        "id": _stable_id("lic", doc["pdf_url"]),
                        "fecha_concesion": _fecha_from_url(doc["pdf_url"]),
                        "tipo": "licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": doc["titulo"][:500],
                        "url": url,
                        "pdf_url": doc["pdf_url"],
                        "source": "ayuntamiento",
                    }
                )
        return rows

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
        rows = self._collect_licencias_info()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_informativos"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_info():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
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
        rows = self._crawl_proyecto_documents()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "seed_pages": len(self.seed_pages)}

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
