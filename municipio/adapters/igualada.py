from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.igualada.cat"
TRAMITS_BASE = "https://tramits.igualada.cat/Ciutadania"
MUNICIPIO = "Igualada"
ID_PREFIX = "igualada"

ARXIUS_ETALER = (
    f"{WEB_BASE}/ca/regidories/urbanisme-i-mobilitat/Urbanisme/arxius-descarregables"
)
ARXIUS_URBANITZACIO = (
    f"{WEB_BASE}/ca/regidories/urbanisme-i-mobilitat/Urbanisme/"
    "arxius-descarregables/projectes-durbanitzacio"
)
PLANEJAMENT_VIGENT = (
    f"{WEB_BASE}/ca/regidories/urbanisme-i-mobilitat/Urbanisme/planejament-vigent"
)
URBANISME_HOME = f"{WEB_BASE}/ca/regidories/urbanisme-i-mobilitat/Urbanisme"
TRAMITS_URBANISME = f"{TRAMITS_BASE}/TramitsTemes.aspx?IdTema=22"
RSS_SITE = f"{WEB_BASE}/rss.xml"
RSS_URBANISME = (
    f"{WEB_BASE}/ca/regidories/urbanisme-i-mobilitat/noticies/noticies/RSS"
)
SEU_TAULER = (
    "https://seu-e.cat/ca/web/igualada/govern-obert-i-transparencia/"
    "accio-de-govern-i-normativa/accio-de-govern-i-grups-politics/tauler-d-edictes-i-anuncis"
)
RPUC_PORTAL = (
    "https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    "?reqCode=cerca&municipiSel=08102"
)

DEFAULT_PROJECT_SEEDS: list[str] = [
    ARXIUS_ETALER,
    ARXIUS_URBANITZACIO,
    PLANEJAMENT_VIGENT,
    URBANISME_HOME,
]

RE_TRAMIT_TITOL = re.compile(
    r"<a class=\"Titol\" href='([^']+)'>([^<]+)</a>",
    re.I,
)
RE_H3_BLOCK = re.compile(r"<h3[^>]*>(.*?)</h3>(.*?)(?=<h3[^>]*>|$)", re.I | re.S)
RE_PDF = re.compile(
    r'href="(https://www\.igualada\.cat/fitxers/regidories/urbanisme[^"]+\.pdf)"',
    re.I,
)
RE_PLONE_PDF = re.compile(
    r'href="(https://www\.igualada\.cat/[^"]+\.pdf(?:/view)?)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autoritzaci[oó].*obres|obra (?:major|menor)|fiances? d'obra|qualificaci[oó] "
    r"urban|expedients? administratius- obres|pr[oò]rroga de llic)",
)
RE_PROYECTO = re.compile(
    r"(?i)(projecte|pla (?:de|local|general)|modificaci[oó] puntual|reparcel|"
    r"pgo|pgou|urbanitzaci[oó]|informaci[oó] p[uú]blica|exposici[oó] p[uú]blica|"
    r"planejament|arranjament|rehabilitaci[oó]|enderroc|pmu|pmus)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_FILE_YYMMDD = re.compile(r"(?:^|/)(\d{2})(\d{2})(\d{2})[_-]")


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


def _parse_iso_date(text: str) -> str | None:
    m = RE_ISO_DATE.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_filename(url: str) -> str | None:
    m = RE_FILE_YYMMDD.search(urllib.parse.unquote(url))
    if not m:
        return None
    yy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year = 2000 + yy if yy < 70 else 1900 + yy
    try:
        return datetime(year, mm, dd).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    for parser in (_parse_iso_date, _parse_fecha_dmy, lambda t: _fecha_from_filename(url)):
        d = parser(text)
        if d:
            return d
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return _parse_iso_date(text.replace("/", "-"))


def _proyecto_tipo(titulo: str) -> str:
    n = (titulo or "").lower()
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual"
    if "reparcel" in n:
        return "reparcelación"
    if "pla general" in n or "pgo" in n or "pgou" in n:
        return "planeamiento general"
    if "pla de mobilitat" in n or "pmus" in n:
        return "plan de movilidad"
    if "pla local" in n and "habitatge" in n:
        return "plan local de vivienda"
    if "urbanitzaci" in n or "arranjament" in n:
        return "urbanización"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "projecte" in n or "proyecto" in n:
        return "proyecto urbanístico"
    return "urbanismo"


class IgualadaAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone igualada.cat (e-tauler arxius PDF) + e-Tràmits urbanisme; seu-e tauler informativo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.project_seeds = [str(u) for u in (self.config.get("project_seeds") or DEFAULT_PROJECT_SEEDS)]
        self.tramits_url = str(self.config.get("tramits_urbanisme_url") or TRAMITS_URBANISME)
        self.rss_urls = [str(u) for u in (self.config.get("rss_urls") or [RSS_URBANISME, RSS_SITE])]
        self.fetch_timeout_s = int(self.config.get("fetch_timeout_s", 90))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-igualada/1.0")},
        )
        with urllib.request.urlopen(req, timeout=self.fetch_timeout_s) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_tramit(self, href: str) -> str:
        return urllib.parse.urljoin(f"{TRAMITS_BASE}/", href.replace("&amp;", "&"))

    def _collect_etaueler_projects(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_H3_BLOCK.finditer(html):
            titulo = _strip_html(m.group(1))
            if len(titulo) < 12:
                continue
            block = m.group(2)
            pdfs = RE_PDF.findall(block)
            if not pdfs and not RE_PROYECTO.search(titulo):
                continue
            doc = pdfs[0] if pdfs else page_url
            url = doc if pdfs else page_url
            key = f"{titulo}|{doc}"
            fecha = _fecha_from_blob(titulo, doc) or _fecha_from_blob("", page_url) or "1970-01-01"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(titulo),
                "url": url,
                "source": "ayuntamiento",
                "origen": "e_tauler_arxius",
            }
            if pdfs:
                rec["documento_url"] = pdfs[0]
                if len(pdfs) > 1:
                    rec["documentos_extra"] = pdfs[1:5]
            rows.append(rec)
        return rows

    def _collect_planejament_links(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href in RE_PLONE_PDF.findall(html):
            u = href.split("/view")[0]
            if u in seen:
                continue
            seen.add(u)
            slug = urllib.parse.unquote(u.rsplit("/", 1)[-1])
            titulo = slug.replace(".pdf", "").replace("_", " ").replace("%20", " ")[:500]
            if not RE_PROYECTO.search(titulo) and "NORMES" not in titulo.upper():
                continue
            rows.append(
                {
                    "id": _stable_id("proy", u),
                    "municipio": MUNICIPIO,
                    "titulo": titulo or "Document urbanístic",
                    "fecha": _fecha_from_blob(titulo, u) or "1970-01-01",
                    "tipo": _proyecto_tipo(titulo),
                    "url": u,
                    "source": "ayuntamiento",
                    "origen": "planejament_vigent",
                    "documento_url": u,
                }
            )
        return rows

    def _collect_rss(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rss_url in self.rss_urls:
            try:
                raw = self._fetch(rss_url)
            except urllib.error.URLError:
                continue
            try:
                root = ET.fromstring(raw)
            except ET.ParseError:
                continue
            ns = {"rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}
            items = root.findall(".//item") or root.findall(".//{http://purl.org/rss/1.0/}item")
            if not items:
                channel = root.find("{http://purl.org/rss/1.0/}channel")
                if channel is not None:
                    for li in channel.findall(".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li"):
                        link = li.get(f"{{{ns['rdf']}}}resource") or li.get("resource")
                        if link:
                            items.append(li)
            for item in items:
                if item.tag.endswith("li"):
                    link = item.get(f"{{{ns['rdf']}}}resource") or ""
                    title = ""
                else:
                    link = (item.findtext("link") or "").strip()
                    title = (item.findtext("title") or "").strip()
                date_raw = ""
                if item.tag.endswith("li"):
                    date_raw = ""
                else:
                    date_raw = item.findtext("date") or item.findtext("pubDate") or ""
                    if not title:
                        title = link.rsplit("/", 1)[-1].replace("-", " ")
                blob = f"{title} {link}"
                if not RE_PROYECTO.search(blob):
                    continue
                out.append(
                    {
                        "titulo": title[:500],
                        "url": link,
                        "fecha": _parse_rss_date(date_raw),
                        "origen": "rss",
                    }
                )
        return out

    def _rss_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        url = str(row["url"])
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"], url) or "1970-01-01",
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen", "rss"),
        }

    def _collect_tramits_licencias(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tramits_url)
        except urllib.error.URLError:
            html = ""
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in RE_TRAMIT_TITOL.findall(html):
            t = unescape(title).strip()
            if not RE_LICENCIA.search(t):
                continue
            u = self._abs_tramit(href)
            if u in seen:
                continue
            seen.add(u)
            rows.append(
                {
                    "id": _stable_id("lic", u),
                    "fecha_concesion": _fecha_from_blob(t, u) or "1970-01-01",
                    "tipo": t[:200],
                    "distrito": "Igualada",
                    "lat": None,
                    "lon": None,
                    "url": u,
                    "source": "ayuntamiento",
                    "origen": "e_tramits",
                }
            )
        info_pages = [
            (TRAMITS_URBANISME, "Tràmits urbanisme — comunicacions i llicències"),
            (SEU_TAULER, "Tauler d'edictes i anuncis (seu-e.cat)"),
            (RPUC_PORTAL, "RPUC — cerca expedients planejament (Generalitat)"),
            (
                f"{WEB_BASE}/ca/regidories/urbanisme-i-mobilitat/Urbanisme",
                "Secció Urbanisme — arxius e-tauler",
            ),
        ]
        for url, label in info_pages:
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": "1970-01-01",
                    "tipo": label[:200],
                    "distrito": "Igualada",
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "informativo",
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        by_id: dict[str, dict[str, Any]] = {}
        for seed in self.project_seeds:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            if "arxius-descarregables" in seed:
                for rec in self._collect_etaueler_projects(html, seed):
                    by_id[rec["id"]] = rec
            else:
                for rec in self._collect_planejament_links(html, seed):
                    by_id[rec["id"]] = rec
        for item in self._collect_rss():
            rec = self._rss_to_proyecto(item)
            by_id[rec["id"]] = rec
        rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "e_tauler": sum(1 for r in rows if r.get("origen") == "e_tauler_arxius"),
            "rss": sum(1 for r in rows if r.get("origen") == "rss"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": after},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {**stats, "delta": after - before}

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_tramits_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": after},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "status": "ok", "delta": after - before}
