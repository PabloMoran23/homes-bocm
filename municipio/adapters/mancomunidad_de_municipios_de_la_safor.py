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

BASE = "https://www.mancomunitat-safor.es"
MUNICIPIO = "Mancomunidad de Municipios de la Safor"
ID_PREFIX = "mancomunidad-de-municipios-de-la-safor"

SEED_PAGES: list[tuple[str, str]] = [
    (f"{BASE}/pagina/disposicions-normatives", "Disposiciones normativas"),
    (f"{BASE}/pagina/consulta-audiencia-publica", "Consulta audiencia pública"),
    (f"{BASE}/pagina/tramits", "Trámites y formularios"),
    (f"{BASE}/pagina/administracio-general", "Administración general"),
]

RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.mancomunitat-safor\.es)?/sites/www\.mancomunitat-safor\.es/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_PAGE_LINK = re.compile(
    r'href="((?:https://www\.mancomunitat-safor\.es)?/pagina/[^"#?]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|llic[eè]ncia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|estrat[eè]gic)|pgou|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"agenda urbana|ordenanza|estatut|consulta p[uú]blica|aprobaci[oó]n (?:inicial|definitiva)|"
    r"reglament|aigua|residu|sequera|territori)",
)
RE_NON_URBAN = re.compile(
    r"(?i)(igualtat|joventut|serveis socials|sad\b|peis\b|carpa|teletreball|"
    r"honors|distincions|ling[uü][ií]stic|protocol|exam|visites culturals|"
    r"absentisme escolar|viol[eè]ncia de g[eè]nere|salut mental|educaci[oó] ambiental|"
    r"empadron|empleo|subvenci[oó]n|antifrau|sequera.*reglament.*comisi)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})[/_-](\d{1,2})[/_-](\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_ISO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _pdf_title(url: str, link_text: str = "") -> str:
    if link_text and len(link_text.strip()) > 5:
        return link_text.strip()
    name = urllib.parse.unquote(url.split("/")[-1])
    name = re.sub(r"\.pdf.*$", "", name, flags=re.I)
    name = name.replace("%20", " ").replace("_", " ")
    return unescape(name).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "agenda urbana" in b:
        return "agenda urbana"
    if "estatut" in b:
        return "estatutos"
    if "consulta" in b and "p" in b and "blica" in b:
        return "consulta pública"
    if "ordenanza" in b or "ordenança" in b:
        return "ordenanza"
    if "reglament" in b:
        return "reglamento"
    if "pla estrat" in b or "plan estrat" in b:
        return "plan estratégico"
    if "residu" in b:
        return "plan residuos"
    if "aigua" in b or "agua" in b:
        return "reglamento agua"
    if "sequera" in b:
        return "plan sequía"
    return "normativa / planeamiento"


def _is_urban_proyecto(blob: str) -> bool:
    if RE_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob):
        return False
    return bool(RE_PROYECTO.search(blob))


class MancomunidadDeMunicipiosDeLaSaforAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portales — normativa PDFs y consulta audiencia pública (sin expedientes urbanísticos)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or BASE).rstrip("/")
        self.seed_pages = list(self.config.get("seed_pages") or SEED_PAGES)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(self.web_base + "/", href))

    def _collect_pdf_links(self, page_url: str, page_label: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for m in re.finditer(
            r'<a[^>]+href="([^"]+\.pdf[^"]*)"[^>]*>(.*?)</a>',
            html,
            re.I | re.S,
        ):
            href = m.group(1)
            link_text = _strip_html(m.group(2))
            url = self._abs_url(href)
            if url in seen:
                continue
            seen.add(url)
            title = _pdf_title(url, link_text)
            blob = f"{title} {link_text} {page_label} {url}"
            if not _is_urban_proyecto(blob):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "url": url,
                    "fecha": _fecha_from_blob(blob),
                    "tipo": _proyecto_tipo(blob),
                    "blob": blob,
                    "origen": page_label,
                }
            )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url, page_label in self.seed_pages:
            for item in self._collect_pdf_links(page_url, page_label):
                key = item["url"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)

        # Páginas informativas sin PDF pero relevantes (Agenda Urbana context)
        info_pages = [
            (
                f"{self.web_base}/pagina/disposicions-normatives",
                "Disposiciones normativas — Agenda Urbana y estatutos",
            ),
            (
                f"{self.web_base}/pagina/consulta-audiencia-publica",
                "Consulta audiencia pública — anuncios normativos",
            ),
        ]
        for url, titulo in info_pages:
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "fecha": None,
                    "tipo": "página informativa",
                    "blob": titulo,
                    "origen": "portal_html",
                }
            )
        return rows

    def _collect_licencias_info(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", f"{self.web_base}/pagina/tramits"),
                "fecha_concesion": None,
                "tipo": "trámites y formularios",
                "distrito": "Safor",
                "lat": None,
                "lon": None,
                "titulo": "Trámites — formularios servicios mancomunitat",
                "url": f"{self.web_base}/pagina/tramits",
                "source": "ayuntamiento",
                "nota": "Sin licencias de obra; formularios de servicios sociales compartidos",
            },
            {
                "id": _stable_id("lic", "sede-indeterminada"),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": "Safor",
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica (no configurada)",
                "url": "https://mancomunitatdelasafor.sedelectronica.es/",
                "source": "ayuntamiento",
                "nota": "Sede indeterminada; sin tablón ni dossier urbanismo",
            },
        ]

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return len(rows)

    def _proyecto_rows(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in self._collect_proyectos():
            key = item["url"]
            out.append(
                {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": item["titulo"],
                    "fecha": item.get("fecha"),
                    "tipo": item.get("tipo") or "normativa",
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "origen": item.get("origen"),
                }
            )
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_info()
        n = self._write_jsonl(out_jsonl, rows)
        return {"rows": n, "source": "portal_tramites", "at": datetime.now(timezone.utc).isoformat()}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._proyecto_rows()
        n = self._write_jsonl(out_jsonl, rows)
        return {"rows": n, "source": "portal_normativa", "at": datetime.now(timezone.utc).isoformat()}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
