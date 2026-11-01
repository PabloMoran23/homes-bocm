from __future__ import annotations

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
from urllib.parse import urljoin, unquote

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.vilanova.cat"
SEDE_STA = "https://tramitacio.vilanova.cat"
SEDE_WEB = "https://seuelectronica.vilanova.cat"
MUNICIPIO = "Vilanova i la Geltrú"
ID_PREFIX = "vilanova-i-la-geltru"

CATALOGO_URL = f"{SEDE_STA}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES"
TABLON_URL = (
    f"{SEDE_STA}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES"
)

DEFAULT_SEED_PAGES: list[tuple[str, str]] = [
    ("urbanisme", f"{WEB_BASE}/espai_public/urbanisme.html"),
    ("planejament general (tràmit)", f"{WEB_BASE}/espai_public/planejament_general_en_tramit.html"),
    ("planejament general (vigent)", f"{WEB_BASE}/espai_public/planejament_general_vigent.html"),
    ("planejament derivat (tràmit)", f"{WEB_BASE}/espai_public/planejament_derivat_en_tramit.html"),
    ("planejament derivat (vigent)", f"{WEB_BASE}/espai_public/planejament_derivat_vigent.html"),
    ("projectes d'urbanització", f"{WEB_BASE}/espai_public/projectes_urbanitzacio.html"),
    ("convenis urbanístics", f"{WEB_BASE}/espai_public/convenis_urbanistics.html"),
    ("altres instruments gestió", f"{WEB_BASE}/espai_public/altres_instruments_gestio_urbanistica.html"),
    ("plans parcials", f"{WEB_BASE}/espai_public/plans_parcials_dordenacio.html"),
    ("estudis de detall", f"{WEB_BASE}/espai_public/estudis_de_detall.html"),
    ("plans especials", f"{WEB_BASE}/espai_public/plans_especials.html"),
    ("plans de millora urbana", f"{WEB_BASE}/espai_public/plans_de_millora_urbana.html"),
]

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "llicència",
    "llicencia",
    "licencia",
    "obra",
    "obres",
    "comunicació prèvia",
    "comunicacion previa",
    "declaració responsable",
    "declaracion responsable",
    "primera ocupació",
    "primera ocupacion",
    "parcel·lació",
    "parcelacion",
    "compatibilitat urban",
    "compatibilidad urban",
    "informe urban",
    "enderroc",
    "enderro",
    "certificat de llic",
    "certificado de licencia",
)

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|licències|licencias|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|declaraci[oó] responsable|obra (?:major|menor)|"
    r"primera ocupaci[oó]n|informe urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|plan (?:parcial|especial|general)|pgou|poum|"
    r"informaci[oó]n p[uú]blica|exposici[oó] p[uú]blica|expedient|edict|"
    r"reparcel|estudi de detall|modificaci[oó]|projecte d'urban|proyecto de urban|"
    r"conveni urban|certificat|document t[eè]cnic|mem[oò]ria|bop|dogc|avan[cç])",
)
RE_EXCLUDE = re.compile(
    r"(?i)(subvenci[oó]n|huertos urbanos|huertos ecol[oó]gic|proc[eé]s selectiu|"
    r"oferta p[uú]blica d'ocupaci[oó]|festa major|tribut|impost)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DOC_LINK = re.compile(r'href="(/doc/[^"]+)"', re.I)


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


def _fecha_from_blob(text: str) -> str | None:
    d = _parse_fecha_dmy(text)
    if d:
        return d
    years = [int(m.group(1)) for m in RE_YEAR.finditer(text or "") if 1980 <= int(m.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(
            int(obj["year"]),
            int(obj["month"]),
            int(obj["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _proyecto_tipo(blob: str, section: str = "") -> str:
    n = f"{blob} {section}".lower()
    if "avanç" in n or "avanc" in n or "poum" in n:
        return "avance POUM"
    if "conveni" in n:
        return "convenio urbanístico"
    if "projecte d'urban" in n or "urbanitz" in n:
        return "proyecto de urbanización"
    if "plan parcial" in n or "parcial" in n:
        return "plan parcial"
    if "estudi de detall" in n:
        return "estudio de detalle"
    if "plan especial" in n:
        return "plan especial"
    if "informaci" in n and ("públic" in n or "public" in n):
        return "información pública"
    if "pla general" in n or "pgou" in n:
        return "planeamiento general"
    if "licencia" in n or "llic" in n:
        return "licencia publicada"
    return section or "urbanismo"


class VilanovaILaGeltruAyuntamientoAdapter(AyuntamientoAdapter):
    """Web municipal (wetown) + sede STA TAO (catálogo trámites; tablón vía AJAX)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_sta = str(self.config.get("sede_sta") or SEDE_STA).rstrip("/")
        self.seed_pages = [
            tuple(pair) for pair in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)
        ]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _needs_insecure(self, url: str) -> bool:
        return any(host in url for host in ("vilanova.cat", "tramitacio.vilanova.cat"))

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-vilanova-i-la-geltru/1.0")},
        )
        ctx = self._ssl_ctx if self._needs_insecure(url) else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

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
            f"{self.sede_sta}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO&lang=ES"
        )

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_sta}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON&lang=ES"
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, timeout=120)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _strip_html(str(item.get("descriptionProc") or item.get("externString") or ""))[:500]
            if not titulo or not dboid:
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "extern": str(item.get("externString") or ""),
                    "seccion": "tablón edictos",
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _collect_web_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for section, page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for m in RE_DOC_LINK.finditer(html):
                href = m.group(1)
                pdf_url = urljoin(self.web_base, href)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                start = max(0, m.start() - 400)
                chunk = html[start : m.end() + 200]
                title_m = re.search(
                    r'<a[^>]+href="' + re.escape(href) + r'"[^>]*>(.*?)</a>',
                    chunk,
                    re.I | re.S,
                )
                link_title = _strip_html(title_m.group(1) if title_m else "") or unquote(
                    Path(href).name
                )
                titulo = f"{section}: {link_title}" if section else link_title
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "seccion": section,
                        "origen": "web_planejament_pdf",
                    }
                )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, timeout=120)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = _strip_html(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or "")
            if not name or not dboid:
                continue
            low = name.lower()
            if not any(p in low for p in LICENCIA_TRAMITE_PATTERNS):
                continue
            if RE_EXCLUDE.search(name):
                continue
            url = self._tramite_url(dboid)
            if url in seen:
                continue
            seen.add(url)
            rows.append({"titulo": name, "url": url, "origen": "catalogo_tramites"})
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
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            rows.append(obj)
                    except json.JSONDecodeError:
                        pass
        return rows

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = str(row.get("titulo") or "")
        if not RE_LICENCIA.search(blob) and row.get("origen") != "catalogo_tramites":
            return None
        url = str(row.get("url") or SEDE_WEB)
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": row.get("fecha"),
            "tipo": "trámite informativo" if row.get("origen") == "catalogo_tramites" else "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row.get("titulo"),
            "url": url,
            "source": "ayuntamiento",
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('extern', '')} {row.get('seccion', '')}"
        if row.get("origen") == "web_planejament_pdf":
            if RE_EXCLUDE.search(blob):
                return None
        elif not RE_PROYECTO.search(blob):
            return None
        url = str(row.get("pdf_url") or row.get("url") or self.web_base)
        section = str(row.get("seccion") or "")
        key = url + str(row.get("titulo", ""))
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row.get("titulo"),
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob, section),
            "url": url,
            "source": "ayuntamiento",
        }

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._collect_tablon():
            add(self._row_to_licencia(row))

        for tram in self._collect_licencia_tramites():
            add(
                {
                    "id": _stable_id("lic", tram["url"]),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": tram["titulo"],
                    "url": tram["url"],
                    "source": "ayuntamiento",
                }
            )

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_sta_catalogo"}

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

        tablon = self._collect_tablon()
        for row in tablon:
            add(self._row_to_proyecto(row))

        web_docs = self._collect_web_documents()
        for row in web_docs:
            add(self._row_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": len(tablon),
            "web_docs": len(web_docs),
        }

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
