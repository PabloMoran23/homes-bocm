from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records
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

WEB_BASE = "https://www.olesademontserrat.cat"
SEU_E_BASE = "https://seu-e.cat"
MUNICIPIO = "Olesa de Montserrat"
ID_PREFIX = "olesa-de-montserrat"
INE_MUN = "08154"

SEU_E_URBANISME = (
    f"{SEU_E_BASE}/ca/web/olesademontserrat/govern-obert-i-transparencia/"
    "accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme"
)
SEU_E_TAULER = (
    f"{SEU_E_BASE}/ca/web/olesademontserrat/govern-obert-i-transparencia/"
    "accio-de-govern-i-normativa/accio-de-govern-i-grups-politics/tauler-d-edictes-i-anuncis"
)
SEU_E_TRAMITS = f"{SEU_E_BASE}/ca/web/olesademontserrat/tramits-i-gestions"
GEOPORTAL_INFO = "https://geoportal.olesademontserrat.cat/info-urbanistica/inici"
RPUC_MUNICI = (
    "https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    f"?reqCode=cerca&municipiSel={INE_MUN}"
)

DEFAULT_DRUPAL_SEEDS: list[str] = [
    f"{WEB_BASE}/urbanisme",
    f"{WEB_BASE}/urbanisme/projectes",
    f"{WEB_BASE}/urbanisme/pla-dordenacio-urbanistica-municipal",
    f"{WEB_BASE}/urbanisme/cataleg-i-pla-especial-urbanistic-de-proteccio-de-patrimoni-historic-arquitectonic-i",
    f"{WEB_BASE}/urbanisme/normativa-urbanistica",
    f"{WEB_BASE}/urbanisme/orpime",
    f"{WEB_BASE}/urbanisme/pla-director-dequipaments",
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (f"{WEB_BASE}/urbanisme", "Urbanisme — tràmits i ORPIME (web municipal)"),
    (GEOPORTAL_INFO, "Assistent de tràmits urbanístics (geoportal)"),
    (SEU_E_TRAMITS, "Catàleg de tràmits (seu-e.cat)"),
    (SEU_E_TAULER, "Tauler d'edictes i anuncis (seu-e)"),
    (
        f"{SEU_E_BASE}/ca/web/olesademontserrat/govern-obert-i-transparencia/"
        "serveis-i-tramits/tramits/sol-licitud-de-llicencia-urbanistica-d-obres",
        "Sol·licitud llicència urbanística d'obres (seu-e)",
    ),
]

RE_LIFERAY_DOC = re.compile(r"/documents/\d+/[^\"'\s<>\\]+", re.I)
RE_PDF = re.compile(r'href="(/sites/default/files/[^"]+\.pdf[^"]*)"', re.I)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó]n responsable|orpime|obra (?:major|menor)|enderroc|"
    r"primera ocupaci[oó]|parcel·laci[oó])",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|poum|po[um]|pla (?:parcial|especial|director)|"
    r"informaci[oó]n p[uú]blica|exposici[oó] p[uú]blica|expedient|projecte|proyecto|"
    r"modificaci[oó]n|reparcel|normativa|memoria|planol|pe_|cat[aà]leg|patrimoni|"
    r"equipament|orpime|edict|anunci)",
)
RE_SKIP = re.compile(
    r"(?i)(eleccions|parlament europeu|subvenci[oó].*entitats|oferta p[uú]blica.*ocupaci[oó])",
)
RE_FECHA_YM = re.compile(r"/sites/default/files/(\d{4})-(\d{2})/")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    for parser in (_parse_fecha_dmy, lambda t: _fecha_from_pdf_url(url)):
        d = parser(text)
        if d:
            return d
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1985 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-06-01"
    return None


def _title_from_pdf_path(url: str) -> str:
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    name = re.sub(r"\.pdf.*$", "", name, flags=re.I)
    name = name.replace("_", " ").replace("-", " ")
    return _strip_html(name)[:500] or url[:500]


def _title_from_liferay_path(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0].rstrip("/"))
    for part in reversed(path.split("/")):
        if part and not re.fullmatch(r"[0-9a-f-]{36}", part, re.I) and not part.isdigit():
            name = part.replace("+", " ")
            if len(name) > 6:
                return _strip_html(name)[:500]
    return url[:500]


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "pe_" in n or "pla especial" in n or "catàleg" in n or "cataleg" in n:
        return "plan especial / catálogo patrimonio"
    if "poum" in n or "ordenació urbanística municipal" in n:
        return "POUM"
    if "orpime" in n:
        return "ordenanza procedimientos (ORPIME)"
    if "pla director" in n and "equipament" in n:
        return "plan director equipamientos"
    if "informaci" in n or "exposici" in n or "edict" in n:
        return "información pública"
    if "normativa" in n or "ordenan" in n:
        return "normativa urbanística"
    if "projecte" in n or "proyecto" in n:
        return "proyecto urbanístico"
    return "urbanismo"


class OlesaDeMontserratAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 10 olesademontserrat.cat + seu-e (Liferay) + geoportal Enmapa (referencia)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seu_e_base = str(self.config.get("seu_e_base") or SEU_E_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_DRUPAL_SEEDS)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _ua(self) -> str:
        return str(self.config.get("user_agent") or "poc-bocm-olesa-de-montserrat/1.0")

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
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
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

    def _collect_drupal_pdfs(self, page_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        h1 = RE_H1.search(html)
        section = _strip_html(h1.group(1)) if h1 else page_url
        if RE_SKIP.search(section):
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF.finditer(html):
            rel = m.group(1)
            pdf_url = self._abs_web(rel)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            titulo = _title_from_pdf_path(pdf_url)
            blob = f"{section} {titulo}"
            if not RE_PROYECTO.search(blob):
                continue
            rows.append(
                {
                    "titulo": f"{section}: {titulo}"[:500],
                    "fecha": _fecha_from_blob(titulo, pdf_url),
                    "url": pdf_url,
                    "page_url": page_url,
                    "origen": origen,
                    "blob": blob[:1500],
                }
            )
        if not rows and RE_PROYECTO.search(section):
            rows.append(
                {
                    "titulo": section[:500],
                    "fecha": _fecha_from_blob(html[:4000], page_url),
                    "url": page_url,
                    "page_url": page_url,
                    "origen": origen,
                    "blob": _strip_html(html[:2500])[:1500],
                }
            )
        return rows

    def _liferay_urban_pages(self) -> list[str]:
        pages = [SEU_E_URBANISME, SEU_E_TAULER]
        try:
            html = self._fetch(SEU_E_URBANISME)
        except urllib.error.URLError:
            return pages
        for m in re.finditer(
            r'href="(https://seu-e\.cat/ca/web/olesademontserrat/govern-obert-i-transparencia/'
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
                blob = f"{title} {page}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": title,
                        "fecha": _fecha_from_blob(title, url),
                        "url": url,
                        "origen": "seu_e_liferay",
                        "blob": blob[:1500],
                    }
                )
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

        for doc in self._collect_liferay_docs():
            add(self._row_to_proyecto(doc))
        for seed in self.seed_pages:
            for doc in self._collect_drupal_pdfs(seed, "drupal_pdf"):
                add(self._row_to_proyecto(doc))
        add(
            {
                "id": _stable_id("proy", RPUC_MUNICI),
                "municipio": MUNICIPIO,
                "titulo": "Registre de planejament urbanístic de Catalunya (RPUC) — Olesa",
                "fecha": None,
                "tipo": "planeamiento (referencia RPUC)",
                "url": RPUC_MUNICI,
                "source": "ayuntamiento",
                "origen": "rpuc_referencia",
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
                    "tipo": "trámite / información licencias",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": (
                        "Sin listado público de concesiones; tràmits ORPIME via geoportal/seu-e. "
                        "Edictes al tauler Liferay (càrrega dinàmica)."
                    ),
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
            "drupal_pdf": sum(1 for r in rows if r.get("origen") == "drupal_pdf"),
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
