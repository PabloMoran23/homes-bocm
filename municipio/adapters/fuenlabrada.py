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

from municipio.adapters.portal import AyuntamientoAdapter

WP_BASE = "https://www.ayto-fuenlabrada.es"
SEDE_BASE = "https://sede.fuenlabrada.es"
TRANSP_BASE = "https://transparencia.ayto-fuenlabrada.es"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"

DEFAULT_TRANSPARENCIA_PAGES: list[tuple[str, str]] = [
    (
        f"{TRANSP_BASE}/ordenacion-del-territorio-y-obras/plan-general-de-ordenacion-urbana-pgou/",
        "planeamiento",
    ),
    (
        f"{TRANSP_BASE}/ordenacion-del-territorio-y-obras/modificaciones-plan-general-ordenacion-urbana/",
        "modificación PGOU",
    ),
    (
        f"{TRANSP_BASE}/ordenacion-del-territorio-y-obras/convenios-urbanisticos/",
        "convenio urbanístico",
    ),
    (
        f"{TRANSP_BASE}/ordenacion-del-territorio-y-obras/revision-del-pgouf/",
        "revisión PGOU",
    ),
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{WP_BASE}/web/portal/tramites/urbanismo",
    f"{WP_BASE}/web/portal/w/licencias-de-obra-menor-en-suelo-publico",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable.*obra|autorizaci[oó]n previa|edicto.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgouf|convenio|"
    r"informaci[oó]n p[uú]blica|expropi|reparcel|entidad urban|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|certificado|memoria|planos)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|documents)/(\d{4})/(\d{2})/")
RE_DOC_LINK = re.compile(
    r'href="((?:https?://(?:www\.)?ayto-fuenlabrada\.es)?/documents/[^"]+|'
    r"https?://transparencia\.ayto-fuenlabrada\.es/wp-content/uploads/[^\"]+\.pdf)\"",
    re.I,
)
RE_TRANSP_PDF = re.compile(
    r'href="(https?://transparencia\.ayto-fuenlabrada\.es/wp-content/uploads/[^"]+\.pdf)"',
    re.I,
)
RE_TRAMITE_LINK = re.compile(
    r'href="((?:https://www\.ayto-fuenlabrada\.es)?/web/portal/[^"]*licencia[^"]*)"',
    re.I,
)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"fuenlabrada-{prefix}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"[?&]t=(\d{13})", url)
    if m:
        try:
            ts = int(m.group(1)) / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            pass
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        y, mo, d = int(obj["year"]), int(obj["month"]), int(obj["day"])
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _title_from_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).name
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    name = name.replace("+", " ").replace("%20", " ")
    return name[:500] if name else url


class FuenlabradaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA tablón + transparencia ordenación del territorio + trámites urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE)
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.4))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        raw_pages = self.config.get("transparencia_pages")
        if raw_pages:
            self.transparencia_pages = [(p["url"], p.get("tipo", "documento")) for p in raw_pages]
        else:
            self.transparencia_pages = list(DEFAULT_TRANSPARENCIA_PAGES)
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-fuenlabrada/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.fuenlabrada.es" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _tablon_row_to_record(self, row: dict[str, Any]) -> tuple[str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, fecha, url

    def _extract_page_documents(self, page_url: str, default_tipo: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        records: list[dict[str, Any]] = []
        seen: set[str] = set()

        for pat in (RE_TRANSP_PDF, RE_DOC_LINK):
            for m in pat.finditer(html):
                doc_url = m.group(1)
                if doc_url in seen:
                    continue
                seen.add(doc_url)
                titulo = _title_from_url(doc_url)
                idx = m.start()
                ctx = html[max(0, idx - 800) : idx + 200]
                ctx_plain = unescape(re.sub(r"<[^>]+>", " ", ctx))
                ctx_plain = re.sub(r"\s+", " ", ctx_plain).strip()
                anchor_m = re.search(
                    r">([^<]{8,200})</a>\s*$",
                    ctx_plain[-200:],
                )
                if anchor_m:
                    titulo = anchor_m.group(1).strip()[:500]
                records.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_url(doc_url) or _parse_fecha_dmy(ctx_plain) or "",
                        "url": page_url,
                        "pdf_url": doc_url,
                        "tipo": default_tipo,
                    }
                )
        return records

    def _collect_transparencia_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url, tipo in self.transparencia_pages:
            for doc in self._extract_page_documents(page_url, tipo):
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", doc["pdf_url"]),
                    "municipio": "Fuenlabrada",
                    "titulo": doc["titulo"],
                    "fecha": doc["fecha"] or None,
                    "tipo": doc["tipo"],
                    "url": doc["url"],
                    "pdf_url": doc["pdf_url"],
                    "source": "ayuntamiento",
                    "origen": page_url,
                }
                rows.append(rec)
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        visited: set[str] = set(self.licencia_pages)

        for url in list(visited):
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue

            title_m = re.search(r'<h1[^>]*class="title"[^>]*>\s*([^<]+)', html, re.I)
            if not title_m:
                title_m = re.search(r"<title>([^<]+)", html, re.I)
            title = unescape(title_m.group(1).strip()) if title_m else _title_from_url(url)
            title = re.sub(r"\s*[-|].*Fuenlabrada.*$", "", title, flags=re.I).strip()

            if RE_LICENCIA.search(title) or "urbanismo" in url.lower():
                rec: dict[str, Any] = {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámite; no concesión publicada",
                }
                rows.append(rec)

            for m in RE_TRAMITE_LINK.finditer(html):
                link = m.group(1)
                if link.startswith("/"):
                    link = urllib.parse.urljoin(WP_BASE, link)
                if link not in visited:
                    visited.add(link)

        return rows

    def _title_to_licencia(self, title: str, url: str, fecha: str) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
            return None
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha or None,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }

    def _title_to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str,
        tipo: str = "urbanismo",
    ) -> dict[str, Any] | None:
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        return {
            "id": _stable_id("proy", url),
            "municipio": "Fuenlabrada",
            "titulo": title[:500],
            "fecha": fecha or None,
            "tipo": tipo,
            "url": url,
            "source": "ayuntamiento",
        }

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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in self._collect_tablon():
            title, fecha, url = self._tablon_row_to_record(item)
            rec = self._title_to_licencia(title, url, fecha)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_licencia_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon_y_tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        for item in self._collect_tablon():
            title, fecha, url = self._tablon_row_to_record(item)
            rec = self._title_to_licencia(title, url, fecha)
            if rec:
                existing[rec["id"]] = rec

        for rec in self._collect_licencia_tramites():
            existing[rec["id"]] = rec

        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            title, fecha, url = self._tablon_row_to_record(item)
            blob = title
            tipo = "información pública" if re.search(r"(?i)informaci[oó]n", blob) else "urbanismo"
            add(self._title_to_proyecto(title, url, fecha, tipo=tipo))

        for rec in self._collect_transparencia_proyectos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_rows": len(self._collect_tablon()),
            "transparencia_pages": len(self.transparencia_pages),
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
