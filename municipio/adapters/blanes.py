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

WEB_BASE = "https://www.blanes.cat"
SEDE_BASE = "https://seu.blanes.cat"
MUNICIPIO = "Blanes"
ID_PREFIX = "blanes"

PROJECTES_APROVATS = f"{WEB_BASE}/docweb/urbanisme.projectes.aprovats"
PLANEJAMENT_INDEX = f"{WEB_BASE}/docweb/urbanisme.planejament"
AMIC_URBANISME = f"{WEB_BASE}/docweb/amic_urbanisme"
CATALOGO_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
)
RPUC_MUNICI = (
    "https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    "?reqCode=cerca&municipiSel=17023"
)

DEFAULT_SEED_PAGES: list[str] = [
    PROJECTES_APROVATS,
    PLANEJAMENT_INDEX,
    f"{WEB_BASE}/docweb/urbanisme.novigent",
    f"{WEB_BASE}/docweb/urbanisme.delimitacio.arees",
    f"{WEB_BASE}/docweb/urbanisme.pla.moli",
    f"{WEB_BASE}/docweb/urbanisme.tecnica.pmu5",
    f"{WEB_BASE}/docweb/urbanisme.canonada.masguelo",
    f"{WEB_BASE}/docweb/urbanisme.2011-043368-G",
    f"{WEB_BASE}/docweb/urbanisme.4831.2010",
    f"{WEB_BASE}/docweb/urbanisme.0196.2014",
    f"{WEB_BASE}/docweb/urbanisme.2015-003845",
    f"{WEB_BASE}/docweb/urbanisme.pla.piscina.cbt",
    AMIC_URBANISME,
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|obra[s]?|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó] responsable|autoritzaci[oó]|enderroc|primera ocupaci[oó])",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|projecte|pla |pgou|poum|modificaci[oó]|aprovat|"
    r"exposici[oó]|informaci[oó] p[uú]blica|delimitaci|sector|pmu|canonada)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_CA = re.compile(
    r"(?i)(\d{1,2})\s+d[e']\s+"
    r"(gener|febrer|març|marzo|abril|maig|mayo|juny|junio|juliol|julio|"
    r"agost|agosto|setembre|septiembre|octubre|novembre|noviembre|desembre|diciembre)"
    r"\s+de\s+(\d{4})",
)
RE_DOCWEB_URB = re.compile(
    r'href="((?:https?://(?:www\.)?blanes\.cat)?/docweb/urbanisme[^"#?]+)"',
    re.I,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
MESES_CA = {
    "gener": 1,
    "febrer": 2,
    "març": 3,
    "marzo": 3,
    "abril": 4,
    "maig": 5,
    "mayo": 5,
    "juny": 6,
    "junio": 6,
    "juliol": 7,
    "julio": 7,
    "agost": 8,
    "agosto": 8,
    "setembre": 9,
    "septiembre": 9,
    "octubre": 10,
    "novembre": 11,
    "noviembre": 11,
    "desembre": 12,
    "diciembre": 12,
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _parse_fecha(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_CA.search(text or "")
    if m:
        mo = MESES_CA.get(m.group(2).lower())
        if mo:
            try:
                return datetime(int(m.group(3)), mo, int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    years = re.findall(r"\b(20\d{2})\b", text or "")
    if years:
        return f"{max(int(y) for y in years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pmu" in n or "pla general" in n or "poum" in n:
        return "planeamiento general"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "delimitaci" in n:
        return "delimitación"
    if "projecte executiu" in n or "projecte bàsic" in n:
        return "proyecto ejecutivo"
    if "skate" in n or "rotonda" in n or "pavell" in n:
        return "equipamiento / obra pública"
    return "planeamiento"


class BlanesAyuntamientoAdapter(AyuntamientoAdapter):
    """Lotus Domino (blanes.cat docweb) + sede STA (catálogo trámites urbanismo)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_seed_pages = int(self.config.get("max_seed_pages", 14))
        self.crawl_docweb_links = bool(self.config.get("crawl_docweb_links", False))

    def _fetch(self, url: str, *, timeout: int = 90) -> str | None:
        last_err: Exception | None = None
        for attempt in range(2):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-blanes/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    charset = resp.headers.get_content_charset() or "latin-1"
                    return resp.read().decode(charset, errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        if last_err:
            return None
        return None

    def _abs(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

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

    def _content_column(self, html: str) -> str:
        m = re.search(r'id="columna1"(.*?)id="columna2"', html, re.I | re.S)
        if m:
            return m.group(1)
        m = re.search(r'<main[^>]*>(.*)</main>', html, re.I | re.S)
        return m.group(1) if m else html

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<meta property="og:title"[^>]*content="([^"]+)"',
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = _clean(m.group(1))
                t = re.sub(r"\s*[-|].*Ajuntament.*$", "", t, flags=re.I)
                if t and t.lower() not in ("blanes.cat", "web de la vila de blanes"):
                    return t[:500]
        return fallback

    def _collect_projectes_aprovats(self) -> list[dict[str, Any]]:
        html = self._fetch(PROJECTES_APROVATS)
        if not html:
            return []
        chunk = self._content_column(html)
        rows: list[dict[str, Any]] = []
        for block in re.split(r"<h2[^>]*>", chunk, flags=re.I):
            end = block.find("</h2>")
            if end < 0:
                continue
            title = _clean(re.sub(r"<[^>]+>", " ", block[:end]))
            if len(title) < 25 or title.lower() in ("idiomes", "menú principal", "camí de tornada"):
                continue
            if not RE_PROYECTO.search(title):
                continue
            body = block[end + 5 :]
            pdf_m = RE_PDF.search(body)
            pdf = self._abs(pdf_m.group(1)) if pdf_m else None
            url = pdf or PROJECTES_APROVATS
            fecha = _parse_fecha(title) or _parse_fecha(body)
            key = title[:200] + (pdf or "")
            rows.append(
                {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(title),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "projectes_aprovats",
                    "pdf_url": pdf,
                }
            )
        return rows

    def _collect_seed_documents(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        queue: list[str] = list(self.seed_pages)
        rows: list[dict[str, Any]] = []

        while queue and len(seen_urls) < self.max_seed_pages:
            url = queue.pop(0).rstrip("/")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            html = self._fetch(url)
            if not html:
                continue
            if self.crawl_docweb_links:
                for m in RE_DOCWEB_URB.finditer(html):
                    nxt = self._abs(m.group(1)).split("#")[0].rstrip("/")
                    if nxt not in seen_urls and len(seen_urls) + len(queue) < self.max_seed_pages:
                        queue.append(nxt)

            if url == PROJECTES_APROVATS:
                continue

            title = self._page_title(html, url.rsplit("/", 1)[-1])
            chunk = self._content_column(html)
            plain = _clean(re.sub(r"<[^>]+>", " ", chunk))
            if not RE_PROYECTO.search(title + " " + plain[:2000]):
                continue

            pdfs = [self._abs(u) for u in RE_PDF.findall(chunk)]
            page_url = url
            if pdfs:
                for pdf in pdfs[:8]:
                    pdf_name = urllib.parse.unquote(Path(pdf).name)[:200]
                    titulo = f"{title}: {pdf_name}" if title else pdf_name
                    fecha = _parse_fecha(plain) or _parse_fecha(titulo)
                    rows.append(
                        {
                            "id": _stable_id("proy", pdf),
                            "municipio": MUNICIPIO,
                            "titulo": titulo[:500],
                            "fecha": fecha,
                            "tipo": _proyecto_tipo(titulo),
                            "url": pdf,
                            "source": "ayuntamiento",
                            "origen": "docweb_seed",
                            "pdf_url": pdf,
                            "seed_page": page_url,
                        }
                    )
            elif len(plain) > 80:
                fecha = _parse_fecha(plain)
                rows.append(
                    {
                        "id": _stable_id("proy", page_url),
                        "municipio": MUNICIPIO,
                        "titulo": title[:500],
                        "fecha": fecha,
                        "tipo": _proyecto_tipo(title + plain[:500]),
                        "url": page_url,
                        "source": "ayuntamiento",
                        "origen": "docweb_seed",
                        "seed_page": page_url,
                    }
                )
        return rows

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        html = self._fetch(CATALOGO_URL, timeout=120)
        rows: list[dict[str, Any]] = []
        if html:
            for item in self._extract_sta_dataset(html, "CATSERV"):
                name = _clean(str(item.get("name") or ""))
                desc = _clean(str(item.get("descriptionExt") or ""))
                blob = f"{name} {desc}"
                keywords = item.get("keywordList") or []
                is_urban = any(
                    str(k.get("code") or "").upper() == "URBANISME" for k in keywords if isinstance(k, dict)
                )
                if not is_urban and not RE_LICENCIA.search(blob):
                    continue
                if not RE_LICENCIA.search(blob) and "habitatge" in blob.lower():
                    continue
                dboid = str(item.get("dboid") or name)
                url = self._tramite_url(dboid) if item.get("dboid") else CATALOGO_URL
                rows.append(
                    {
                        "id": _stable_id("lic", dboid),
                        "fecha_concesion": None,
                        "tipo": name[:200] or "trámite urbanismo",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": name[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "nota": "Ficha catálogo sede STA; sin listado de concesiones",
                    }
                )

        amic = self._fetch(AMIC_URBANISME)
        if amic:
            rows.append(
                {
                    "id": _stable_id("lic", AMIC_URBANISME),
                    "fecha_concesion": None,
                    "tipo": "información licencias urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Llicències d'urbanisme (AMIC)",
                    "url": AMIC_URBANISME,
                    "source": "ayuntamiento",
                    "nota": "Página informativa AMIC; edictes en e-Tauler (SPA)",
                }
            )
            rows.append(
                {
                    "id": _stable_id("lic", RPUC_MUNICI),
                    "fecha_concesion": None,
                    "tipo": "consulta planeamiento RPUC",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Registre de planejament urbanístic de Catalunya — Blanes",
                    "url": RPUC_MUNICI,
                    "source": "ayuntamiento",
                    "nota": "Consulta expedientes RPUC (Angular SPA)",
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
        rows = self._collect_licencias_tramites()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sta_catalogo"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_tramites():
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

        for rec in self._collect_projectes_aprovats():
            add(rec)
        for rec in self._collect_seed_documents():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "projectes_aprovats": sum(1 for r in rows if r.get("origen") == "projectes_aprovats"),
            "docweb_seed": sum(1 for r in rows if r.get("origen") == "docweb_seed"),
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
