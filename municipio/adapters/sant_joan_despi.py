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

BASE = "https://sjdespi.cat"
SEU = "https://seu-e.cat"
MUNICIPIO = "Sant Joan Despí"
ID_PREFIX = "sant-joan-despi"

PROYECTOS_IP_ES = (
    f"{BASE}/es/la-ciudad-por-temas/urbanismo-y-publica/informacion-publica-de-proyectos"
)
SEU_PLANEJAMENT = (
    f"{SEU}/es/web/santjoandespi/govern-obert-i-transparencia/"
    "accio-de-govern-i-normativa/urbanisme/planejament-urbanistic"
)

LICENCIA_PAGES: list[tuple[str, str]] = [
    (f"{BASE}/es/ayuntamiento/licencias-obras/licencia-urbanistica", "Licencia urbanística"),
    (f"{SEU}/es/web/santjoandespi/seu-electronica", "Sede electrónica — trámites"),
    (
        f"{BASE}/es/la-ciudad-por-temas/urbanismo-y-publica/expedientes-en-tramite",
        "Expedientes urbanismo en trámite (seu-e)",
    ),
]

RE_FILE_LINK = re.compile(
    r'<div class="file-link">\s*<a[^>]+href="([^"]+)"[^>]*>\s*(?:<img[^>]*>)?\s*([^<]+)\s*</a>',
    re.I | re.S,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://sjdespi\.cat)?/sites/default/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_YM = re.compile(r"/sites/default/files/(20\d{2})-(\d{2})/")
RE_SEU_DOC = re.compile(
    r'href="(/documents/27745/\d+/([^"/?]+)/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|obra|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"urban[ií]stic|tramit)",
)
RE_PROYECTO = re.compile(
    r"(?i)(projecte|proyecto|aprovaci[oó]|urban|planej|reurban|modificaci[oó]|"
    r"informaci[oó] p[uú]blica|expedient|pgm|gpu|pmu)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _title_from_pdf_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).name
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    return _clean(name.replace("_", " ").replace("-", " "))[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "aprovaci" in n and "definitiva" in n:
        return "aprobación definitiva"
    if "aprovaci" in n and "inicial" in n:
        return "aprobación inicial"
    if "informaci" in n or "anunci" in n:
        return "información pública"
    if "reurban" in n:
        return "reurbanización"
    if "gpu" in n:
        return "gestión urbanística (GPU)"
    if "pgm" in n or "pmu" in n:
        return "planeamiento (PGM/PMU)"
    if "ppe" in n:
        return "plan parcial (PPE)"
    if "projecte" in n or "proyecto" in n:
        return "proyecto técnico"
    return "urbanismo"


def _folder_title(name: str) -> str:
    t = urllib.parse.unquote(name).replace("+", " ").replace("_", " ")
    return _clean(t)[:500]


class SantJoanDespiAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal sjdespi.cat (IP proyectos) + seu-e AOC (planejament en tràmit)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = str(self.config.get("user_agent", "poc-bocm-sant-joan-despi/1.0"))

    def _fetch(self, url: str, *, timeout: float = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_maybe(self, url: str, *, timeout: float = 90) -> str | None:
        try:
            return self._fetch(url, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError):
            return None

    def _abs_sjd(self, href: str) -> str:
        return urllib.parse.urljoin(BASE, href)

    def _abs_seu(self, href: str) -> str:
        return urllib.parse.urljoin(SEU, href)

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

    def _collect_ip_proyectos(self) -> list[dict[str, Any]]:
        html = self._fetch_maybe(PROYECTOS_IP_ES)
        if not html:
            return []
        html = unescape(html)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_FILE_LINK.finditer(html):
            pdf_url = self._abs_sjd(m.group(1))
            title = _clean(m.group(2))
            if not title or pdf_url in seen:
                continue
            seen.add(pdf_url)
            rows.append(
                {
                    "id": _stable_id("proy", pdf_url),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": _fecha_from_pdf_url(pdf_url),
                    "tipo": _proyecto_tipo(title),
                    "url": PROYECTOS_IP_ES,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "drupal_informacio_publica",
                }
            )

        for m in RE_PDF_HREF.finditer(html):
            pdf_url = self._abs_sjd(m.group(1))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            title = _title_from_pdf_url(pdf_url)
            if not RE_PROYECTO.search(title):
                continue
            rows.append(
                {
                    "id": _stable_id("proy", pdf_url),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": _fecha_from_pdf_url(pdf_url),
                    "tipo": _proyecto_tipo(title),
                    "url": PROYECTOS_IP_ES,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "drupal_pdf",
                }
            )
        return rows

    def _collect_seu_planejament(self) -> list[dict[str, Any]]:
        html = self._fetch_maybe(SEU_PLANEJAMENT, timeout=120)
        if not html:
            return []
        html = unescape(html)
        by_folder: dict[str, str] = {}
        for m in RE_SEU_DOC.finditer(html):
            path, folder = m.group(1), m.group(2)
            key = folder.upper()
            if key not in by_folder:
                by_folder[key] = path

        rows: list[dict[str, Any]] = []
        for folder, path in sorted(by_folder.items()):
            title = _folder_title(folder)
            doc_url = self._abs_seu(path)
            rows.append(
                {
                    "id": _stable_id("proy", doc_url),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": None,
                    "tipo": _proyecto_tipo(title),
                    "url": SEU_PLANEJAMENT,
                    "document_url": doc_url,
                    "source": "ayuntamiento",
                    "origen": "seu_e_planejament",
                    "codi_expedient_carpeta": folder,
                }
            )
        return rows

    def _collect_licencias_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, label in LICENCIA_PAGES:
            html = self._fetch_maybe(url)
            if html is None:
                continue
            title = label
            m = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
            if m:
                title = _clean(m.group(1))[:500]
            pdfs = [
                self._abs_sjd(u) if u.startswith("/") else u
                for u in RE_PDF_HREF.findall(unescape(html))
            ]
            rec: dict[str, Any] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": "trámite licencia / urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title,
                "url": url,
                "source": "ayuntamiento",
                "nota": "Página informativa; no listado de concesiones en tablón",
            }
            if pdfs:
                rec["pdf_url"] = pdfs[0]
            rows.append(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_informativos"}

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

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_ip_proyectos():
            add(rec)
        for rec in self._collect_seu_planejament():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "drupal_ip": sum(1 for r in rows if str(r.get("origen", "")).startswith("drupal")),
            "seu_e": sum(1 for r in rows if r.get("origen") == "seu_e_planejament"),
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
