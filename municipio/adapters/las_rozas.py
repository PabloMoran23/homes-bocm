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

WP_BASE = "https://www.lasrozas.es"
TRANSP_BASE = "https://transparencia.lasrozas.es"

PGOU_URL = f"{WP_BASE}/urbanismo-conservacion-y-medio-ambiente/urbanismo/PGOU"
PORTAL_URBANISMO = f"{WP_BASE}/gestiones-y-tramites/PortaldelCiudadano/Urbanismo"
CONVENIOS_URL = f"{TRANSP_BASE}/contratos-convenios-concesiones-y-subvenciones/convenios/"

DEFAULT_TRANSPARENCIA_PAGES: list[str] = [
    f"{TRANSP_BASE}/ordenacion-del-territorio-y-obras/",
    f"{TRANSP_BASE}/ordenacion-del-territorio-y-obras/planes-parciales/",
    f"{TRANSP_BASE}/ordenacion-del-territorio-y-obras/mapas-y-planos-pgou/",
    f"{TRANSP_BASE}/obras-publicas-y-urbanismo/modificaciones/",
    f"{TRANSP_BASE}/obras-publicas-y-urbanismo/normas-pgou/",
    f"{TRANSP_BASE}/actas/comisiones-de-obras/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|inicio de obras)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|npgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental)|memoria|planos|bocm|acta|alegacion|"
    r"aprobacion|segregaci|parcela|suelo)",
)
RE_CONVENIO_URBAN = re.compile(
    r"(?i)(urban|suelo|planeam|consorcio urban|pgou|colaboraci[oó]n.*comunidad de madrid.*suelo)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_WP_PDF = re.compile(
    r'href="(https://transparencia\.lasrozas\.es/wp-content/uploads/[^"]+\.pdf)"',
    re.I,
)
RE_DRUPAL_PDF = re.compile(
    r'href="((?:https://www\.lasrozas\.es)?/(?:sites/[^"]+\.pdf|sites/default/files/[^"]+\.pdf))"',
    re.I,
)
RE_CONVENIO_LINK = re.compile(
    r'<a href="(https://transparencia\.lasrozas\.es/convenio/[^"]+)"[^>]*>\s*([^<]{10,300})\s*</a>',
    re.I | re.S,
)
RE_PANEL_LICENCIA = re.compile(
    r'class="panel-title"[^>]*>\s*<a[^>]*>([^<]*[Ll]icencia[^<]{0,200})</a>',
    re.I,
)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"las-rozas-{prefix}-{h}"


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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(Path(url).name) if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>([^<]+)',
        r"<h1[^>]*>([^<]+)",
        r"<title>([^<]+)",
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


class LasRozasAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 10 + transparencia WordPress: PGOU, planes, modificaciones, trámites licencia."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.transp_pages = [str(u) for u in (self.config.get("transparencia_pages") or DEFAULT_TRANSPARENCIA_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-las-rozas/1.0")},
        )
        ctx = self._ssl_ctx if "sede.lasrozas.es" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str = WP_BASE) -> str:
        return urllib.parse.urljoin(base, href)

    def _collect_transparencia_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.transp_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = _page_title(html, page_url.rsplit("/", 2)[-2].replace("-", " "))
            for m in RE_WP_PDF.finditer(html):
                pdf = m.group(1)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                blob = f"{page_title} {name} {pdf}"
                if not RE_PROYECTO.search(blob):
                    continue
                rec_id = _stable_id("proy", pdf)
                if rec_id in seen:
                    continue
                seen.add(rec_id)
                tipo = "planeamiento"
                if re.search(r"(?i)modificaci[oó]n", blob):
                    tipo = "modificación PGOU"
                elif re.search(r"(?i)plan parcial|bocm", blob):
                    tipo = "plan parcial"
                elif re.search(r"(?i)acta", blob):
                    tipo = "acta comisión obras"
                rows.append(
                    {
                        "id": rec_id,
                        "municipio": "Las Rozas de Madrid",
                        "titulo": name[:500] if len(name) > 10 else f"{page_title}: {name}"[:500],
                        "fecha": _fecha_from_url(pdf),
                        "tipo": tipo,
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": "transparencia",
                    }
                )
        return rows

    def _collect_drupal_pgou(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(PGOU_URL)
        except urllib.error.URLError:
            return rows
        title = _page_title(html, "PGOU Las Rozas")
        for m in RE_DRUPAL_PDF.finditer(html):
            pdf = self._abs_url(m.group(1))
            if "AnverTurismo" in pdf:
                continue
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            rec_id = _stable_id("proy", pdf)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "municipio": "Las Rozas de Madrid",
                    "titulo": f"{title}: {name}"[:500],
                    "fecha": _fecha_from_url(pdf),
                    "tipo": "PGOU/NPGOU",
                    "url": PGOU_URL,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "origen": "drupal_pgou",
                }
            )
        return rows

    def _collect_convenios_urbanisticos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(CONVENIOS_URL)
        except urllib.error.URLError:
            return rows
        for m in RE_CONVENIO_LINK.finditer(html):
            url = m.group(1)
            title = unescape(re.sub(r"\s+", " ", m.group(2)).strip())
            if not RE_CONVENIO_URBAN.search(title):
                continue
            rec_id = _stable_id("proy", url)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "municipio": "Las Rozas de Madrid",
                    "titulo": title[:500],
                    "fecha": _parse_fecha_dmy(title) or _fecha_from_url(title),
                    "tipo": "convenio",
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "convenios",
                }
            )
        return rows

    def _collect_licencias_portal(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(PORTAL_URBANISMO)
        except urllib.error.URLError:
            return rows
        seen: set[str] = set()
        for m in RE_PANEL_LICENCIA.finditer(html):
            title = unescape(re.sub(r"\s+", " ", m.group(1)).strip())
            if not RE_LICENCIA.search(title):
                continue
            rec_id = _stable_id("lic", title)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": PORTAL_URBANISMO,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo Portal del Ciudadano; no concesión publicada",
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
        rows = self._collect_licencias_portal()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "portal_ciudadano"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_portal():
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

        for rec in self._collect_transparencia_pdfs():
            add(rec)
        for rec in self._collect_drupal_pgou():
            add(rec)
        for rec in self._collect_convenios_urbanisticos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "drupal_pgou": sum(1 for r in rows if r.get("origen") == "drupal_pgou"),
            "convenios": sum(1 for r in rows if r.get("origen") == "convenios"),
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
