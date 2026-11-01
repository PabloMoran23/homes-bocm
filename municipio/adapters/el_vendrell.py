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

WEB_BASE = "https://www.elvendrell.net"
MUNICIPIO = "El Vendrell"
ID_PREFIX = "el-vendrell"

EDICTES_URBANISME = f"{WEB_BASE}/ajuntament/edictes/urbanisme"
EDICTES_URBANISME_RSS = f"{EDICTES_URBANISME}?format=feed&type=rss"
RSS_GLOBAL = f"{WEB_BASE}/?format=feed&type=rss"
TRAMITS_OBRES = f"{WEB_BASE}/res-cerca-tramits-gestions/161-obres"
URBANISME_INFO = f"{WEB_BASE}/informacio-cid-720"
PLANEJAMENT_DERIVAT = (
    f"{WEB_BASE}/ajuntament/ordenances/ordenances-urbanistiques/planejament-derivat"
)
PLA_GENERAL = f"{WEB_BASE}/ajuntament/ordenances/ordenances-urbanistiques/pla-general"
SEU_E = "https://seu-e.cat/ca/web/elvendrell"

DEFAULT_SEED_PAGES: list[str] = [
    EDICTES_URBANISME,
    URBANISME_INFO,
    PLANEJAMENT_DERIVAT,
    PLA_GENERAL,
    TRAMITS_OBRES,
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó]n responsable|declaraci[oó] responsable|parcelaci[oó]n|"
    r"segregaci[oó]n|primera ocupaci[oó]|obra (?:major|menor)|modificaci[oó].*obres)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|plan (?:parcial|especial|general)|pgou|poum|"
    r"modificaci[oó]|informaci[oó] p[uú]blica|exposici[oó] p[uú]blica|expedient|"
    r"edict|reurban|sector|entitat urban|programa d.?actuaci|projecte d.?urban|"
    r"suspensi[oó] de llic|renaturalitz|hospital|hub sanitari|gurb)",
)
RE_EXCLUDE_NEWS = re.compile(
    r"(?i)(campionat|pesca|festa|cultura urbana|grafit|exposici[oó].*pau casals|"
    r"ple ordinari|platges|videojoc|joventut)",
)
RE_GURB = re.compile(r"\b(GURB\d{10})\b", re.I)
RE_EDICTE_LINK = re.compile(
    r'href="(/ajuntament/edictes/urbanisme/\d+-[^"]+)"',
    re.I,
)
RE_TRAMIT_LINK = re.compile(
    r'href="(/res-cerca-tramits-gestions/161-obres/\d+-[^"]+)"',
    re.I,
)
RE_LINK_TITLE = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{8,200})\s*</a>',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return _parse_fecha_dmy(text)


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    for parser in (_parse_rss_date, _parse_fecha_dmy):
        d = parser(text)
        if d:
            return d
    m = RE_GURB.search(f"{text} {url}")
    if m:
        code = m.group(1).upper()
        try:
            return datetime(int(code[4:8]), int(code[8:10]), int(code[10:12])).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            pass
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and ("puntual" in n or "pgou" in n):
        return "modificación PGOU"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "plan especial" in n:
        return "plan especial"
    if "entitat urban" in n or "ua-" in n:
        return "entidad urbanística"
    if "suspensi" in n and "llic" in n:
        return "suspensión de licencias"
    if "renaturalitz" in n or "riera" in n:
        return "proyecto de urbanización / renaturalización"
    if "pgou" in n or "pla general" in n:
        return "PGOU"
    if "informaci" in n or "aprovaci" in n:
        return "información pública"
    if "projecte executiu" in n:
        return "proyecto ejecutivo"
    return "urbanismo"


class ElVendrellAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla elvendrell.net (edictes urbanisme + notícies) + seu-e + tràmits obres."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.fetch_timeout_s = int(self.config.get("fetch_timeout_s", 90))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-vendrell/1.0")},
        )
        with urllib.request.urlopen(req, timeout=self.fetch_timeout_s) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{WEB_BASE}/", unescape(href).replace("&amp;", "&"))

    def _parse_rss(self, url: str, origen: str, *, filter_proyecto: bool = False) -> list[dict[str, Any]]:
        try:
            xml = self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return rows
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if not title or not link:
                continue
            blob = f"{title} {link}"
            if filter_proyecto and not RE_PROYECTO.search(blob):
                continue
            if filter_proyecto and RE_EXCLUDE_NEWS.search(blob):
                continue
            fecha = _parse_rss_date(date_el.text if date_el is not None else "")
            gurb = RE_GURB.search(blob)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": link,
                    "expediente": gurb.group(1).upper() if gurb else None,
                    "origen": origen,
                }
            )
        return rows

    def _collect_edictes_html(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(EDICTES_URBANISME)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_EDICTE_LINK.finditer(html):
            url = self._abs_url(m.group(1))
            slug_part = url.rstrip("/").split("/")[-1]
            titulo = slug_part.split("-", 1)[-1].replace("-", " ").strip().title()
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(slug_part, url),
                    "url": url,
                    "origen": "edictes_html",
                }
            )
        for m in RE_GURB.finditer(html):
            code = m.group(1).upper()
            rows.append(
                {
                    "titulo": f"Expedient urbanisme {code}",
                    "fecha": _fecha_from_blob(code),
                    "url": f"https://docs.elvendrell.net/docs/ajuntament/urbanisme/{code}/",
                    "expediente": code,
                    "origen": "gurb_docs",
                }
            )
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for href, raw_title in RE_LINK_TITLE.findall(html):
                if not re.search(r"\.pdf", href, re.I):
                    continue
                blob = f"{raw_title} {href}"
                if not RE_PROYECTO.search(blob):
                    continue
                url = self._abs_url(href)
                titulo = _strip_html(raw_title)[:500]
                rows.append(
                    {
                        "titulo": titulo or url.split("/")[-1],
                        "fecha": _fecha_from_blob(blob, url),
                        "url": url,
                        "origen": "pdf_seed",
                    }
                )
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = str(row.get("titulo") or "").strip()
        url = str(row.get("url") or "").strip()
        if not titulo or not url:
            return None
        blob = f"{titulo} {url}"
        if not RE_PROYECTO.search(blob):
            return None
        fecha = row.get("fecha") or _fecha_from_blob(blob, url) or "1970-01-01"
        expediente = row.get("expediente")
        key = f"{expediente or titulo}|{url}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": fecha,
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if expediente:
            rec["expediente"] = expediente
        return rec

    def _collect_licencia_tramits(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(TRAMITS_OBRES)
        except (urllib.error.URLError, TimeoutError, OSError):
            return rows
        for m in RE_TRAMIT_LINK.finditer(html):
            url = self._abs_url(m.group(1))
            slug_part = url.rstrip("/").split("/")[-1]
            titulo = slug_part.split("-", 1)[-1].replace("-", " ").strip().title()
            if not RE_LICENCIA.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "tipo": "trámite licencias de obra",
                }
            )
        rows.append(
            {
                "titulo": "Presentació telemàtica llicències (seu-e)",
                "url": f"{SEU_E}/tramits-i-gestions",
                "tipo": "seu electrònica",
            }
        )
        return rows

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = str(row.get("titulo") or "").strip()
        url = str(row.get("url") or "").strip()
        key = f"{titulo}|{url}"
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": "1970-01-01",
            "tipo": str(row.get("tipo") or titulo)[:200],
            "distrito": MUNICIPIO,
            "lat": None,
            "lon": None,
            "source": "ayuntamiento",
            "titulo": titulo,
            "url": url,
            "nota": "Tràmit informatiu; no hi ha tabló públic de concesions de llicència",
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            out.append(obj)
                    except json.JSONDecodeError:
                        pass
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = [self._row_to_licencia(r) for r in self._collect_licencia_tramits()]
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramits_obres_info"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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

        sources = [
            self._parse_rss(EDICTES_URBANISME_RSS, "rss_edictes"),
            self._parse_rss(RSS_GLOBAL, "rss_noticies", filter_proyecto=True),
            self._collect_edictes_html(),
            self._collect_seed_pdfs(),
        ]
        for src in sources:
            for raw in src:
                add(self._row_to_proyecto(raw))

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
