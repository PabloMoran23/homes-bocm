from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records
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

WEB_BASE = "https://molinsderei.cat"
SEDE_BASE = "https://www.molinsderei.net"
MUNICIPIO = "Molins de Rei"
ID_PREFIX = "molins-de-rei"
INE_MUN = "08130"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
RPUC_MUNICI = (
    f"https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    f"?reqCode=cerca&municipiSel={INE_MUN}"
)
RPUC_PGOU_DOC = (
    "https://ptop.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    "?reqCode=veureDocument&codintExp=277777&fromPage=load"
)
AMB_GEOPORTAL = "https://geoportalplanejament.amb.cat/AppGeoportalPlanejament2/index.html"
PEPHA_VISOR = "https://patrimoni.molinsderei.cat/"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/urbanisme/",
    f"{WEB_BASE}/urbanitzacio-del-sector-industrial-de-les-llicorelles/",
    f"{WEB_BASE}/pla-especial-de-patrimoni-historic-i-arquitectonic-de-molins-de-rei/",
    f"{WEB_BASE}/ambits/obres-i-rehabilitacions-i-urbanisme/",
    f"{WEB_BASE}/quines-obres-requereixen-llicencia/",
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|obra[s]?|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó] responsable|autoritzaci[oó]|enderroc|primera ocupaci[oó]|"
    r"certificat.*urban|informe urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|projecte|pla |pgou|pgm|modificaci[oó]|aprovaci[oó]|"
    r"exposici[oó]|informaci[oó] p[uú]blica|sector|urbanitz|ordenan[cç]a|"
    r"patrimoni|llicorel|pepha|rpuc|muc|geoportal)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(autob[uú]s|molins bus|manifest|jutge|viol[eè]ncia|inf[aà]ncia|whatsapp|cookie)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_WP_LINK = re.compile(r'href="(https?://(?:www\.)?molinsderei\.cat/[^"#?]+/?)"', re.I)
RE_JSONLD_DATE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
RE_JSONLD_DESC = re.compile(r'"description"\s*:\s*"([^"]+)"')


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
    m = RE_JSONLD_DATE.search(text or "")
    if m:
        raw = m.group(1)
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1985 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-06-01"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(int(obj["year"]), int(obj["month"]), int(obj["day"])).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "llicorel" in n or "sector industrial" in n:
        return "plan parcial / urbanización sector"
    if "pepha" in n or "patrimoni" in n:
        return "plan especial patrimonio"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "ordenan" in n:
        return "ordenanza urbanística"
    if "urbanitz" in n:
        return "proyecto de urbanización"
    if "rpuc" in n or "muc" in n:
        return "consulta planeamiento (RPUC/MUC)"
    return "planeamiento"


class MolinsDeReiAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress molinsderei.cat + sede STA T-Systems (tablón + catálogo). Geometría: partial (MUC/RPUC)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)

    def _fetch(self, url: str, *, timeout: int = 90) -> str | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-molins-de-rei/1.0")},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError):
            return None

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

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON&lang=ES"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

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
                if t and "molins" not in t.lower()[:8]:
                    return t[:500]
                if t:
                    return t[:500]
        return fallback

    def _collect_tablon(self) -> list[dict[str, Any]]:
        html = self._fetch(self.tablon_url)
        if not html:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            extern = _clean(str(item.get("externString") or ""))
            proc = _clean(str(item.get("descriptionProc") or ""))
            titulo = proc or extern
            if extern and extern not in titulo:
                titulo = f"{extern} — {proc}" if proc else extern
            if not titulo or not dboid or RE_EXCLUDE.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _collect_wordpress_seeds(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        queue = list(dict.fromkeys(self.seed_pages))
        rows: list[dict[str, Any]] = []

        for url in queue:
            if url in seen:
                continue
            seen.add(url)
            html = self._fetch(url)
            if not html:
                continue
            for m in RE_WP_LINK.finditer(html):
                nxt = m.group(1).split("#")[0].rstrip("/") + "/"
                if nxt not in seen and "/wp-content/" not in nxt and len(queue) < 12:
                    if RE_PROYECTO.search(nxt):
                        queue.append(nxt)
                        seen.add(nxt)

            title = self._page_title(html, url)
            meta_desc = _clean(RE_JSONLD_DESC.search(html).group(1)) if RE_JSONLD_DESC.search(html) else ""
            plain = _clean(re.sub(r"<[^>]+>", " ", html))
            blob = f"{title} {meta_desc} {plain[:2500]}"
            if RE_EXCLUDE.search(blob) or not RE_PROYECTO.search(blob):
                continue
            fecha = _parse_fecha(html) or _parse_fecha(blob)
            pdfs = list(dict.fromkeys(RE_PDF.findall(html)))[:6]
            if pdfs:
                for pdf in pdfs:
                    pdf_url = urllib.parse.urljoin(url, pdf)
                    name = urllib.parse.unquote(Path(pdf_url).name)[:200]
                    titulo = f"{title}: {name}" if title else name
                    rows.append(
                        {
                            "id": _stable_id("proy", pdf_url),
                            "municipio": MUNICIPIO,
                            "titulo": titulo[:500],
                            "fecha": fecha,
                            "tipo": _proyecto_tipo(titulo),
                            "url": pdf_url,
                            "source": "ayuntamiento",
                            "origen": "wordpress_pdf",
                            "pdf_url": pdf_url,
                            "seed_page": url,
                        }
                    )
            else:
                rows.append(
                    {
                        "id": _stable_id("proy", url),
                        "municipio": MUNICIPIO,
                        "titulo": (meta_desc or title)[:500],
                        "fecha": fecha,
                        "tipo": _proyecto_tipo(blob),
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "wordpress_page",
                        "seed_page": url,
                    }
                )
        return rows

    def _static_proyecto_refs(self) -> list[dict[str, Any]]:
        refs = [
            (RPUC_PGOU_DOC, "PGOU Molins de Rei — document RPUC (exp. 277777)"),
            (RPUC_MUNICI, f"RPUC — cerca expedients planejament (municipi {INE_MUN})"),
            (MUC_VISOR, f"Visor MUC — mapa urbanístic Catalunya (municipi {INE_MUN})"),
            (AMB_GEOPORTAL, "Geoportal planejament refós AMB (consulta classificació sòl)"),
            (PEPHA_VISOR, "Visor patrimoni històric-arquitectònic (PEPHA)"),
        ]
        out: list[dict[str, Any]] = []
        for url, titulo in refs:
            out.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": None,
                    "tipo": _proyecto_tipo(titulo),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "referencia_portal",
                }
            )
        return out

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]) and "ordenan" not in row["titulo"].lower():
            return None
        return {
            "id": _stable_id("proy", row["dboid"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["dboid"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row["titulo"][:200],
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_sta",
        }

    def _collect_catalog(self) -> list[dict[str, Any]]:
        html = self._fetch(self.catalogo_url, timeout=120)
        if not html:
            return []
        out: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = _clean(str(item.get("name") or ""))
            desc = _clean(str(item.get("descriptionExt") or ""))
            blob = f"{name} {desc}"
            keywords = item.get("keywordList") or []
            is_urban = any(
                "URBANISME" in str(k.get("code") or "").upper()
                for k in keywords
                if isinstance(k, dict)
            )
            if not is_urban and not RE_LICENCIA.search(blob):
                continue
            if not RE_LICENCIA.search(blob):
                continue
            dboid = str(item.get("dboid") or name)
            out.append(
                {
                    "dboid": dboid,
                    "titulo": name[:500],
                    "tipo": name[:200],
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_sta",
                }
            )
        return out

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            (f"{self.web_base}/quines-obres-requereixen-llicencia/", "Quines obres requereixen llicència"),
            (f"{self.sede_base}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME", "Seu electrònica STA"),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo in pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "información trámites licencias de obra",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "pagina_informativa",
                    "nota": "Sin listado público de concesiones; trámites vía EACAT/STA",
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        if "licencias" not in path.name:
            rows = reviewed_records(path, rows)
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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_catalog():
            rec = {
                "id": _stable_id("lic", item["dboid"]),
                "fecha_concesion": None,
                "tipo": item["tipo"],
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": item["titulo"],
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": item["origen"],
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for rec in self._collect_wordpress_seeds():
            add(rec)
        for rec in self._static_proyecto_refs():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "wordpress": sum(1 for r in rows if str(r.get("origen", "")).startswith("wordpress")),
            "referencias": sum(1 for r in rows if r.get("origen") == "referencia_portal"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
