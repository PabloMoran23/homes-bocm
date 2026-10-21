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

WEB_BASE = "https://www.tarragona.cat"
SEDE_BASE = "https://seu.tarragona.cat"
MUNICIPIO = "Tarragona"
ID_PREFIX = "tarragona"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES"
PLANEJAMENT_ATRAMIT_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_PLANEJAMENT_ATRAMIT&lang=ES"
)
OBRES_INFO_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_SOL_OBRES&lang=ES"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/lajuntament/territori/territori",
    f"{WEB_BASE}/poum",
    "https://cis.tarragona.cat/cataleg/procediments/planejament-urbanistic_71",
    OBRES_INFO_URL,
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó] responsable|autoritzaci[oó]|obra[s]?|enderroc|parcel|"
    r"primera ocupaci[oó]|innecessarietat de llic[eè]ncia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|poum|pgou|pla (?:especial|parcial|director)|"
    r"conveni|informaci[oó]n p[uú]blica|exposici[oó]n|expedient|projecte|"
    r"modificaci[oó]|millora urbana|reparcel|estudi|mem[oò]ria|aprobaci[oó]|"
    r"revisi[oó]n|instrument|ordenaci[oó]|suspensi[oó].*llic|sector|bopt|"
    r"avan[cç] de poum|urbanitzaci[oó])",
)
RE_EXCLUDE = re.compile(
    r"(?i)(taxi|armes|espectacle|plusval[ií]a|subvenci[oó]n|empleo|selecci[oó]n|"
    r"ordenan[cç]a fiscal|mercat|animals|padron|impost|festa|esport|"
    r"protecci[oó] de dades|targeta|establiment.*espectacle)",
)
RE_EXCLUDE_CATALOG_LIC = re.compile(
    r"(?i)(taxi|armes|espectacle|targeta|establiment.*espectacle|animals|mercat|"
    r"plusval[ií]a|transmisi[oó] de llic[eè]ncia de comer[cç])",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_LINK = re.compile(r'<a[^>]+href="([^"]+\.pdf[^"]*)"[^>]*>([^<]+)</a>', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_text(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        y, mo, d = int(obj["year"]), int(obj["month"]), int(obj["day"])
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "avan" in n and "poum" in n:
        return "avance POUM"
    if "poum" in n or "pgou" in n or "pla general" in n:
        return "POUM"
    if "pla especial" in n or "plan especial" in n:
        return "plan especial"
    if "millora urbana" in n or "pmu" in n:
        return "plan de mejora urbana"
    if "pla parcial" in n or "plan parcial" in n:
        return "plan parcial"
    if "modificaci" in n:
        return "modificación urbanística"
    if "conveni" in n or "convenio" in n:
        return "convenio urbanístico"
    if "urbanitzaci" in n or "urbanizaci" in n:
        return "proyecto de urbanización"
    return "planeamiento"


class TarragonaAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone tarragona.cat + sede STA (planejament a tràmit, tablón, catálogo obres/urbanisme)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_timeout_s = int(self.config.get("tablon_timeout_s", 180))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._tablon_cache: list[dict[str, Any]] | None = None
        self._planejament_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-tarragona/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            raw = resp.read()
            try:
                return raw.decode(charset)
            except UnicodeDecodeError:
                return raw.decode("latin-1", errors="replace")

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

    def _planejament_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_PLANEJAMENT_ATRAMIT&lang=ES"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO&lang=ES"
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
        if self._tablon_cache is not None:
            return self._tablon_cache
        try:
            html = self._fetch(TABLON_URL, timeout=self.tablon_timeout_s)
        except urllib.error.URLError:
            self._tablon_cache = []
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_title(
                str(item.get("descriptionProc") or item.get("externString") or "")
            )
            if not titulo or not dboid:
                continue
            rem = item.get("remitent") or {}
            remitente = str(rem.get("description") or rem.get("code") or "")
            expte = str(item.get("externString") or "").strip()
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "expte": expte or None,
                    "remitente": remitente,
                    "url": self._tablon_detail_url(dboid),
                    "origen": "tablon_sta",
                }
            )
        self._tablon_cache = rows
        return rows

    def _collect_planejament_atramit(self) -> list[dict[str, Any]]:
        if self._planejament_cache is not None:
            return self._planejament_cache
        try:
            html = self._fetch(PLANEJAMENT_ATRAMIT_URL, timeout=90)
        except urllib.error.URLError:
            self._planejament_cache = []
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_PLANEJAMENT_ATRAMIT"):
            dboid = str(item.get("dboid") or "")
            extern = _clean_title(str(item.get("externString") or ""))
            desc = _clean_title(str(item.get("descriptionProc") or extern))
            if not desc or not dboid:
                continue
            titulo = desc if len(desc) > len(extern) else f"{extern}: {desc}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "expte": extern or None,
                    "url": self._planejament_detail_url(dboid),
                    "origen": "planejament_atramit",
                }
            )
        self._planejament_cache = rows
        return rows

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, timeout=90)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = _clean_title(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or item.get("code") or "")
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

    def _collect_web_pdfs(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            if not page_url.startswith(self.web_base) and "tarragona.cat" not in page_url:
                continue
            try:
                html = self._fetch(page_url, timeout=45)
            except urllib.error.URLError:
                continue
            context = page_url
            for href, raw_title in RE_PDF_LINK.findall(html):
                pdf_url = urllib.parse.urljoin(page_url, unescape(href))
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                title = _clean_title(raw_title)
                blob = f"{title} {context}"
                if not RE_PROYECTO.search(blob):
                    continue
                records.append(
                    {
                        "titulo": title or pdf_url,
                        "fecha": _fecha_from_text(title),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": "web_pdf",
                    }
                )
        return records

    def _title_to_licencia(
        self,
        title: str,
        url: str,
        fecha: str | None,
        *,
        nota: str | None = None,
        origen: str | None = None,
    ) -> dict[str, Any] | None:
        if RE_EXCLUDE.search(title):
            return None
        if not RE_LICENCIA.search(title):
            return None
        tipo = "licencia"
        low = title.lower()
        if "comunicaci" in low or "comunicaci" in low:
            tipo = "comunicación previa"
        elif "declaraci" in low and "respons" in low:
            tipo = "declaración responsable"
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha,
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }
        if nota:
            rec["nota"] = nota
        if origen:
            rec["origen"] = origen
        return rec

    def _title_to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str | None,
        *,
        pdf_url: str | None = None,
        origen: str | None = None,
        expte: str | None = None,
    ) -> dict[str, Any] | None:
        blob = f"{title} {expte or ''}"
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", pdf_url or url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        if origen:
            rec["origen"] = origen
        if expte:
            rec["expte"] = expte
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

        for item in self._collect_tablon():
            add(
                self._title_to_licencia(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                    origen=item.get("origen"),
                )
            )

        for item in self._collect_catalog_tramites():
            if RE_EXCLUDE_CATALOG_LIC.search(item["titulo"]):
                continue
            add(
                self._title_to_licencia(
                    item["titulo"],
                    item["url"],
                    None,
                    nota="Página informativa de trámite; no concesión publicada",
                    origen=item.get("origen"),
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_sta"}

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

        for item in self._collect_planejament_atramit():
            add(
                self._title_to_proyecto(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                    origen=item.get("origen"),
                    expte=item.get("expte"),
                )
            )

        for item in self._collect_tablon():
            add(
                self._title_to_proyecto(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                    origen=item.get("origen"),
                    expte=item.get("expte"),
                )
            )

        for doc in self._collect_web_pdfs():
            add(
                self._title_to_proyecto(
                    doc["titulo"],
                    doc["url"],
                    doc.get("fecha"),
                    pdf_url=doc.get("pdf_url"),
                    origen=doc.get("origen"),
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "planejament_atramit": len(self._collect_planejament_atramit()),
            "tablon": len(self._collect_tablon()),
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
