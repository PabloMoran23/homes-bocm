from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.cornella.cat"
GOVERN_OPEN = "http://governobert.cornella.cat"
SEU_E_URBANISME = (
    "https://seu-e.cat/es/web/cornella/govern-obert-i-transparencia/"
    "accio-de-govern-i-normativa/urbanisme"
)
RPUC_MUNICI = "https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08073"
MUC_VISOR = "https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08073&set-locale=ca"
SITEMAP_GZ = f"{WEB_BASE}/sitemap.xml.gz"
MUNICIPIO = "Cornellà de Llobregat"
ID_PREFIX = "cornella"
INE_MUN = "08073"

DEFAULT_PLONE_ROOTS: list[str] = [
    f"{WEB_BASE}/files/contenidos/Urbanisme",
    f"{WEB_BASE}/files/contenidos/InfoPublica",
]

DEFAULT_GOVERN_SEEDS: list[str] = [
    f"{GOVERN_OPEN}/normativa-municipal-en-tramit",
    f"{GOVERN_OPEN}/altres",
    f"{GOVERN_OPEN}/normativa-municipal",
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (f"{WEB_BASE}/ca/tramits/seu-electronica", "Seu electrònica — tràmits telemàtics"),
    (f"{WEB_BASE}/es/tramites/sede-electronica", "Sede electrónica — trámites telemáticos"),
    (
        f"{WEB_BASE}/files/contenidos/Normativa/Normativa%20General/Ordenances/"
        "Ordenan-a%20Proceciment%20Autoritzacions%20Obres%20Menors%202014.pdf/view",
        "Ordenança procediment autoritzacions obres menors",
    ),
    (
        "https://seuelectronica.cornella.cat/portal/inicio.do?ent_id=1&idioma=1",
        "Seu electrònica Cornellà (carpeta ciutadana)",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|obra menor|obra major|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autoritzaci[oó] d.?obres|autorizaci[oó]n de obra|"
    r"procediment.*obres|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|plan (?:parcial|especial|general)|pgou|pgm|"
    r"informaci[oó]n p[uú]blica|exposici[oó] p[uú]blica|expedient|edict|"
    r"modificaci[oó]n|reparcel|ordenan[cç]a.*(?:circul|zbe|qualitat|aire|vehicle)|"
    r"consulta pr[eè]via|aprovaci[oó]n (?:inicial|provisional|definitiva)|"
    r"ref[oò]s|pasi|pl[aà] central|fontsanta|sant ildefons|ascensor|zbe|"
    r"circulaci[oó]|motius|esborrany|rpuc|muc.visor)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(expedient sancionador|gos potencialment perillosos|espectacles p[uú]blics|"
    r"oferta p[uú]blica.*(?:funcionari|laboral|guardia urbana|educador|cuinera|"
    r"psic[oò]leg|biblioteca|administratiu)|mercat.*no sedent|parades.*castanyes|"
    r"subvenci[oó].*ascensor|bases reguladores.*ascensor)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_WORDS = re.compile(
    r"(?i)(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre|gener|febrer|març|abril|maig|juny|"
    r"juliol|agost|setembre|octubre|novembre|desembre)\s+de\s+(\d{4})"
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PLONE_FOLDER = re.compile(
    r'href="(https://www\.cornella\.cat/files/contenidos/[^"?#]+)"',
    re.I,
)
RE_PLONE_FILE = re.compile(
    r'href="(https://www\.cornella\.cat/files/[^"?#]+\.(?:pdf|PDF)(?:/view)?)"',
    re.I,
)
RE_GOVERN_BLOCK = re.compile(
    r"(?is)(consulta pr[eè]via|informaci[oó]n p[uú]blica|aprovaci[oó]n (?:inicial|"
    r"provisional|definitiva)|modificaci[oó]n|ordenan[cç]a)[^<]{20,800}",
)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _month_num(name: str) -> int | None:
    m = name.lower()[:3]
    table = {
        "ene": 1,
        "feb": 2,
        "mar": 3,
        "abr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dic": 12,
        "gen": 1,
        "febr": 2,
        "març": 3,
        "maig": 5,
        "juny": 6,
        "juliol": 7,
        "agost": 8,
        "set": 9,
        "octu": 10,
        "nov": 11,
        "des": 12,
    }
    for k, v in table.items():
        if m.startswith(k[:3]):
            return v
    return None


def _parse_fecha(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_DMY_WORDS.search(text or "")
    if m:
        mo = _month_num(m.group(2))
        if mo:
            try:
                return datetime(int(m.group(3)), mo, int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1995 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-06-01"
    return None


def _fecha_from_url(url: str) -> str | None:
    for part in urllib.parse.unquote(url).split("/"):
        if re.fullmatch(r"20\d{2}", part):
            return f"{part}-06-01"
    return None


def _title_from_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0].rstrip("/"))
    if path.endswith("/view"):
        path = path[:-5]
    name = Path(path).name
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    name = name.replace("%20", " ").replace("_", " ").replace("-", " ")
    return _strip_html(name)[:500] or url


def _proyecto_tipo(title: str) -> str:
    n = (title or "").lower()
    if "consulta" in n and "prèvia" in n or "consulta previa" in n:
        return "consulta previa"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "aprovaci" in n:
        return "aprobación normativa"
    if "ordenan" in n or "zbe" in n or "circulaci" in n:
        return "ordenanza urbanística"
    if "plan parcial" in n or "pasi" in n or "pla " in n:
        return "plan parcial / actuación"
    if "pgou" in n or "planej" in n or "refós" in n:
        return "planeamiento"
    if "edict" in n:
        return "edicto"
    return "urbanismo"


class CornelladeLlobregatAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone cornella.cat (Urbanisme/InfoPublica) + govern obert + seu-e (referencias)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = str(self.config.get("user_agent", "poc-bocm-cornella-de-llobregat/1.0"))
        self.plone_roots = [str(u) for u in (self.config.get("plone_roots") or DEFAULT_PLONE_ROOTS)]
        self.govern_seeds = [str(u) for u in (self.config.get("govern_seeds") or DEFAULT_GOVERN_SEEDS)]
        self.max_plone_pages = int(self.config.get("max_plone_pages", 120))
        self.fetch_timeout = float(self.config.get("fetch_timeout_s", 45))
        self.govern_timeout = float(self.config.get("govern_timeout_s", 12))

    def _fetch(self, url: str, *, timeout: float | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=timeout or self.fetch_timeout) as resp:
            raw = resp.read()
        return raw.decode("utf-8", errors="replace")

    def _normalize_url(self, url: str) -> str | None:
        url = unescape((url or "").strip())
        if not url or " " in url or "\n" in url:
            parts = urllib.parse.urlsplit(url)
            if " " in parts.path:
                path = urllib.parse.quote(parts.path, safe="/%:@&=+$,;~")
                url = urllib.parse.urlunsplit(
                    (parts.scheme, parts.netloc, path, parts.query, parts.fragment)
                )
        try:
            urllib.parse.urlparse(url)
        except ValueError:
            return None
        if " " in url:
            return None
        return url

    def _fetch_maybe(self, url: str, *, timeout: float | None = None) -> str | None:
        url = self._normalize_url(url) or ""
        if not url:
            return None
        try:
            return self._fetch(url, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, urllib.error.HTTPError):
            return None

    def _sitemap_urban_urls(self) -> list[str]:
        out: list[str] = []
        try:
            req = urllib.request.Request(SITEMAP_GZ, headers={"User-Agent": self.ua})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = gzip.decompress(resp.read())
            text = data.decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError, gzip.BadGzipFile):
            return out
        for m in re.finditer(r"<loc>([^<]+)</loc>", text):
            url = m.group(1).strip()
            if "cornella.cat" not in url:
                continue
            blob = urllib.parse.unquote(url)
            if not RE_PROYECTO.search(blob):
                continue
            if RE_EXCLUDE.search(blob):
                continue
            if "/files/contenidos/" in url or "_urbanismo.pdf" in url.lower():
                out.append(url)
        return list(dict.fromkeys(out))

    def _plone_bfs_documents(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue = list(self.plone_roots)
        file_urls: set[str] = set()

        while queue and len(visited) < self.max_plone_pages:
            url = queue.pop(0).rstrip("/")
            if url in visited:
                continue
            visited.add(url)
            html = self._fetch_maybe(url)
            if not html:
                continue
            for m in RE_PLONE_FILE.finditer(html):
                nu = self._normalize_url(m.group(1).rstrip("/"))
                if nu:
                    file_urls.add(nu)
            for m in RE_PLONE_FOLDER.finditer(html):
                link = self._normalize_url(m.group(1).rstrip("/")) or ""
                if link in visited or link in queue:
                    continue
                if any(x in link.lower() for x in ("/rss", "/atom", "set_language")):
                    continue
                if link and link.startswith(f"{WEB_BASE}/files/contenidos/"):
                    if "/@@download/" in link:
                        continue
                    queue.append(link)

        rows: list[dict[str, Any]] = []
        for furl in sorted(file_urls):
            blob = urllib.parse.unquote(furl)
            if not RE_PROYECTO.search(blob) and "Urbanisme" not in blob and "InfoPublica" not in blob:
                continue
            if RE_EXCLUDE.search(blob):
                continue
            titulo = _title_from_url(furl)
            if len(titulo) < 4:
                continue
            rows.append(
                {
                    "id": _stable_id("proy", furl),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": _fecha_from_url(furl),
                    "tipo": _proyecto_tipo(titulo),
                    "url": furl,
                    "source": "ayuntamiento",
                    "origen": "plone_files",
                }
            )
        return rows

    def _govern_obert_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in self.govern_seeds:
            html = self._fetch_maybe(seed, timeout=self.govern_timeout)
            if not html:
                continue
            plain = _strip_html(html)
            for block in RE_GOVERN_BLOCK.findall(html):
                text = _strip_html(block)
                if len(text) < 25 or RE_EXCLUDE.search(text):
                    continue
                if not RE_PROYECTO.search(text):
                    continue
                titulo = text[:500]
                rec_id = _stable_id("proy", f"{seed}|{titulo[:120]}")
                rows.append(
                    {
                        "id": rec_id,
                        "municipio": MUNICIPIO,
                        "titulo": titulo,
                        "fecha": _parse_fecha(text),
                        "tipo": _proyecto_tipo(titulo),
                        "url": seed,
                        "source": "ayuntamiento",
                        "origen": "governobert",
                    }
                )
            for m in RE_HREF.finditer(html):
                href = unescape(m.group(1))
                if not href or href.startswith("#") or href.startswith("javascript"):
                    continue
                abs_u = urllib.parse.urljoin(seed, href)
                if "cornella.cat/files" not in abs_u and ".pdf" not in abs_u.lower():
                    continue
                titulo = _title_from_url(abs_u)
                if not RE_PROYECTO.search(f"{titulo} {abs_u}"):
                    continue
                rows.append(
                    {
                        "id": _stable_id("proy", abs_u),
                        "municipio": MUNICIPIO,
                        "titulo": titulo,
                        "fecha": _parse_fecha(plain),
                        "tipo": _proyecto_tipo(titulo),
                        "url": abs_u,
                        "source": "ayuntamiento",
                        "origen": "governobert_link",
                    }
                )
        return rows

    def _static_planeamiento_refs(self) -> list[dict[str, Any]]:
        refs = [
            (RPUC_MUNICI, "RPUC — expedients de planejament (Cornellà 08073)"),
            (MUC_VISOR, "Visor MUC — cartografia urbanística (municipi 08073)"),
            (SEU_E_URBANISME, "Govern obert — secció urbanisme (seu-e.cat)"),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo in refs:
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": None,
                    "tipo": "planeamiento",
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "referencia_portal",
                }
            )
        return rows

    def _merge_proyectos(self, chunks: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            for row in chunk:
                rid = row.get("id") or _stable_id("proy", row.get("url", ""))
                if rid not in by_id:
                    by_id[rid] = row
        return list(by_id.values())

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        chunks = [
            self._sitemap_urban_urls_as_rows(),
            self._plone_bfs_documents(),
            self._govern_obert_proyectos(),
            self._static_planeamiento_refs(),
        ]
        return self._merge_proyectos(chunks)

    def _sitemap_urban_urls_as_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self._sitemap_urban_urls():
            titulo = _title_from_url(url)
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": _fecha_from_url(url),
                    "tipo": _proyecto_tipo(titulo),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sitemap",
                }
            )
        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo in DEFAULT_LICENCIA_PAGES:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": titulo[:200],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                }
            )
        for seed in (f"{GOVERN_OPEN}/altres",):
            html = self._fetch_maybe(seed, timeout=self.govern_timeout)
            if not html:
                continue
            plain = _strip_html(html)
            for line in re.split(r"\.\s+", plain):
                if not RE_LICENCIA.search(line):
                    continue
                if RE_EXCLUDE.search(line):
                    continue
                if len(line) < 20:
                    continue
                rows.append(
                    {
                        "id": _stable_id("lic", line[:200]),
                        "fecha_concesion": _parse_fecha(line),
                        "tipo": line[:200],
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "url": seed,
                        "source": "ayuntamiento",
                        "origen": "governobert_anunci",
                    }
                )
        by_id = {r["id"]: r for r in rows}
        return list(by_id.values())

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return {"rows": len(rows), "path": str(path)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        meta = self._write_jsonl(out_jsonl, rows)
        meta["fetched_at"] = datetime.utcnow().isoformat() + "Z"
        return meta

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        meta = self._write_jsonl(out_jsonl, rows)
        meta["fetched_at"] = datetime.utcnow().isoformat() + "Z"
        return meta

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
