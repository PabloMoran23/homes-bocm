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

WP_BASE = "https://merida.es"
SEDE_BASE = "https://sede.merida.es"
MUNICIPIO = "Mérida"
ID_PREFIX = "merida"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/servicios-municipales/urbanismo/planeamiento-pgou/",
    f"{WP_BASE}/servicios-municipales/urbanismo/nuevo-pgm/",
    f"{WP_BASE}/servicios-municipales/urbanismo/plan-proteccion-casco-historico/",
    f"{WP_BASE}/servicios-municipales/urbanismo/tramites/",
]
CATALOGO_TRAMITES = f"{SEDE_BASE}/sede/catalogoTramites.do?opcion=detalle&idApl=2&ent_id=2&idioma=1"
TRAMITES_URBANISMO = f"{WP_BASE}/servicios-municipales/urbanismo/tramites/"
TABLON_PAGE = f"{SEDE_BASE}/portal/noEstatica.do?opc_id=268&ent_id=2&idioma=1"

RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_TRAMITE_ROW = re.compile(
    r'id="dct_(\d+)"[^>]*title="([^"]*)"[^>]*href="([^"]+)"',
    re.I,
)
RE_TRAMITE_NAME = re.compile(
    r'<i class="fa fa-angle-right[^"]*"></i>\s*([^<]{5,220})',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|c[eé]dula|parcelaci|primera utilizaci[oó]n|"
    r"obra mayor|obra menor|certificados? de urbanismo|vado)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgm|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|proserpina|acceso|casco|"
    r"aprobaci[oó]n|modificaci[oó]n|protecci[oó]n|catalogo|normas|junta|pleno|"
    r"doe|edicto|sector|urbanizaci[oó]n|instrumento)",
)
RE_SKIP_PDF = re.compile(
    r"(?i)(politica-de-seguridad|rat_merida|modelos/urbanismo-|cartel-licencias)",
)
RE_FECHA_DMY = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b(20\d{2})[-_](\d{2})[-_](\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _title_from_pdf_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).name
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    return name.replace("-", " ").replace("_", " ").strip()[:500]


def _map_tipo_proyecto(title: str) -> str:
    blob = (title or "").lower()
    if "pgou" in blob or "pgm" in blob or "plan general" in blob:
        return "PGOU/PGM"
    if "plan especial" in blob:
        return "plan especial"
    if "casco hist" in blob or "protecci" in blob:
        return "protección patrimonial"
    if "proserpina" in blob or "acceso norte" in blob:
        return "actuación urbanística"
    if "junta" in blob or "pleno" in blob:
        return "acuerdo municipal urbanismo"
    if "doe" in blob or "gobex" in blob:
        return "publicación DOE"
    if "catalogo" in blob or "catálogo" in blob:
        return "catálogo urbanístico"
    if "normas" in blob:
        return "normativa urbanística"
    return "documento urbanismo"


class MeridaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (descargas urbanismo/PGOU) + sede STA catálogo trámites (licencias informativas)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.catalogo_url = str(self.config.get("catalogo_tramites_url") or CATALOGO_TRAMITES)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URBANISMO)

    def _fetch(self, url: str, *, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-merida/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or ("iso-8859-1" if sede else "utf-8")
            return raw.decode(charset, errors="replace")

    def _abs_wp(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{WP_BASE}/", href))

    def _abs_sede(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.sede_base}/", href.replace("&amp;", "&")))

    def _collect_pdf_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                href = m.group(1)
                pdf = self._abs_wp(href)
                if RE_SKIP_PDF.search(pdf):
                    continue
                if pdf in seen:
                    continue
                seen.add(pdf)
                title = _title_from_pdf_url(pdf)
                if not RE_PROYECTO.search(f"{title} {pdf}"):
                    continue
                rows.append(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": MUNICIPIO,
                        "titulo": title or "Documento urbanismo Mérida",
                        "fecha": _parse_fecha_dmy(pdf) or _parse_fecha_dmy(title),
                        "tipo": _map_tipo_proyecto(title),
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": "wp_pdf",
                    }
                )
        return rows

    def _collect_catalogo_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.catalogo_url, sede=True)
        except urllib.error.URLError:
            return rows

        for m in RE_TRAMITE_ROW.finditer(html):
            dct_id, title_attr, href = m.groups()
            title = unescape(title_attr).strip()
            if not RE_LICENCIA.search(title):
                continue
            if dct_id in seen:
                continue
            seen.add(dct_id)
            url = self._abs_sede(href) if not href.startswith("javascript") else self.catalogo_url
            rows.append(
                {
                    "id": _stable_id("lic", f"tramite-{dct_id}"),
                    "fecha_concesion": None,
                    "tipo": title[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_catalogo",
                }
            )

        if not rows:
            for m in RE_TRAMITE_NAME.finditer(html):
                title = unescape(m.group(1)).strip()
                if not RE_LICENCIA.search(title):
                    continue
                key = title.lower()
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "id": _stable_id("lic", key),
                        "fecha_concesion": None,
                        "tipo": title[:120],
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title[:500],
                        "url": self.catalogo_url,
                        "source": "ayuntamiento",
                        "origen": "sede_catalogo",
                    }
                )
        return rows

    def _licencias_informativas(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", "info-tramites-urbanismo"),
                "fecha_concesion": None,
                "tipo": "información trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites y modelos de licencias urbanísticas",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Sin listado público de licencias concedidas; trámites vía sede electrónica.",
            }
        ]

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
        rows = self._collect_catalogo_licencias()
        if not rows:
            rows = self._licencias_informativas()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_catalogo"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_catalogo_licencias():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values()) if existing else self._licencias_informativas()
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
        rows = self._collect_pdf_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "wp_pdf"}

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
