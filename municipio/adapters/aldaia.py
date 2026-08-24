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

WP_BASE = "https://aldaia.es"
TRANSP_BASE = "https://transparencia.aldaia.es"
MUNICIPIO = "Aldaia"
ID_PREFIX = "aldaia"
COD_INE_MUN = "46005"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/es/urbanismo-y-medio-ambiente/",
    f"{WP_BASE}/urbanisme-i-medi-ambient/",
    f"{TRANSP_BASE}/es/transparencia/informacion-urbanistica",
    f"{TRANSP_BASE}/es/transparencia/plan-general-ordenacion-urbana",
    f"{TRANSP_BASE}/es/transparencia/modificaciones-al-plan-general-ordenacion-urbana",
    f"{TRANSP_BASE}/es/transparencia/homologaciones-modificativas",
    f"{TRANSP_BASE}/es/transparencia/ordenanzas-urbanisticas",
    f"{TRANSP_BASE}/es/general/transparencia/plrpif",
    f"{TRANSP_BASE}/es/transparencia/pla-general-dordenacio-urbana",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|obra)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|cita previa.*urban|t[ií]tulos? habilitantes?)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|plrpif|eate|date|daeate|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|homologaci[oó]n|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de paisaje|territorial)|memoria|planos|dogv|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|ordenanza|normas urban|"
    r"participaci[oó]n|puam|plano|zonificaci[oó]n|clasificaci[oó]n)",
)
RE_NOISE = re.compile(
    r"(?i)(selecci[oó]n de personal|convocatoria.*empleo|subvenci[oó]n|presupuest|"
    r"pol[ií]tica de privacidad|aviso legal|mapa del sitio|declaraci[oó]n de accesibilidad|"
    r"farmaci|festes|transport|telefons|beques|educaci)",
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*(?:title="([^"]*)")?[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPEDIENTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente|res\.?\s*alc)\s*[:.]?\s*([\w/_-]+)")


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
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "plan parcial" in b:
        return "plan parcial"
    if "homologaci" in b:
        return "homologación modificativa"
    if "modificaci" in b and ("pgou" in b or "plan general" in b):
        return "modificación PGOU"
    if "eate" in b or "daeate" in b or "date" in b:
        return "EATE / estrategia territorial"
    if "plrpif" in b:
        return "PLRPIF"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "ordenanza" in b or "or-urb" in b:
        return "ordenanza urbanística"
    if "dogv" in b or "edicto" in b:
        return "publicación / edicto"
    if "estudio" in b and ("paisaje" in b or "acust" in b or "ambiental" in b):
        return "estudio urbanístico"
    if "participaci" in b:
        return "información pública"
    if "memoria" in b or "plano" in b:
        return "documentación planeamiento"
    return "urbanismo"


class AldaiaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress aldaia.es + Drupal transparencia.aldaia.es (sin sede activa)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transp_base") or TRANSP_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.citaprevia_url = str(
            self.config.get("citaprevia_url") or "https://citaprevia.aldaia.eu/frontend.php"
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-aldaia/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or self.wp_base, href))

    def _is_doc_href(self, href: str) -> bool:
        h = href.lower()
        return bool(
            re.search(r"(?i)\.(pdf|docx?)(?:\?|$)", h)
            or "transparencia.aldaia.es/sites/default/files" in h
            or "aldaia.es/wp-content/uploads" in h
            or "aldaia.eu/wp-content/uploads" in h
        )

    def _collect_seed_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            page_title = ""
            title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
            if title_m:
                page_title = _strip_html(title_m.group(1))

            for m in RE_LINK.finditer(html):
                href = m.group(1)
                title_attr = (m.group(2) or "").strip()
                anchor = _strip_html(m.group(3))
                if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                    continue
                if "favicon" in href.lower() or RE_NOISE.search(f"{anchor} {href}"):
                    continue

                if self._is_doc_href(href):
                    doc_url = self._abs_url(href, page_url)
                    if doc_url in seen:
                        continue
                    name = unescape(urllib.parse.unquote(Path(doc_url.split("?")[0]).name))
                    titulo = title_attr or (anchor if len(anchor) > 5 else name)
                    blob = f"{titulo} {name} {doc_url} {page_url} {page_title}"
                    if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                        continue
                    seen.add(doc_url)
                    expte_m = RE_EXPEDIENTE.search(blob)
                    rows.append(
                        {
                            "titulo": titulo[:500],
                            "fecha": _fecha_from_blob(f"{name} {doc_url} {anchor} {title_attr}"),
                            "url": doc_url,
                            "page_url": page_url,
                            "blob": blob,
                            "expte": expte_m.group(1) if expte_m else None,
                            "origen": "transparencia_pdf",
                            "pdf_url": doc_url,
                        }
                    )
                elif "/transparencia/" in href or "/urbanismo" in href or "/urbanisme" in href:
                    link_url = self._abs_url(href, page_url)
                    if link_url in seen or not RE_PROYECTO.search(f"{anchor} {link_url}"):
                        continue
                    if RE_NOISE.search(anchor):
                        continue
                    seen.add(link_url)
                    rows.append(
                        {
                            "titulo": (anchor or page_title)[:500],
                            "fecha": _fecha_from_blob(anchor),
                            "url": link_url,
                            "page_url": page_url,
                            "blob": f"{anchor} {link_url} {page_title}",
                            "expte": None,
                            "origen": "transparencia_page",
                        }
                    )

        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            (
                f"{self.wp_base}/es/urbanismo-y-medio-ambiente/",
                "Urbanismo y medio ambiente — trámites e información",
                "información urbanística",
            ),
            (
                f"{self.transp_base}/es/transparencia/ordenanzas-urbanisticas",
                "Ordenanzas urbanísticas (transparencia)",
                "normativa licencias y obras",
            ),
            (
                self.citaprevia_url,
                "Cita previa — Oficina de Atención al Ciudadano",
                "cita previa trámites",
            ),
            (
                f"{self.transp_base}/es/transparencia/informacion-urbanistica",
                "Información urbanística — documentación pública",
                "documentación urbanística",
            ),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo, tipo in pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa; sede electrónica inactiva, sin tablón de licencias concedidas",
                    "origen": "tramite_info",
                }
            )
        return rows

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or ""
        titulo = row["titulo"]
        url = row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expte"):
            rec["expte"] = row["expte"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("page_url"):
            rec["seed_page"] = row["page_url"]
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
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_info"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencia_info_pages():
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
        for raw in self._collect_seed_docs():
            rec = self._doc_to_proyecto(raw)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia_pdf": sum(1 for r in rows if r.get("origen") == "transparencia_pdf"),
            "transparencia_page": sum(1 for r in rows if r.get("origen") == "transparencia_page"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for raw in self._collect_seed_docs():
            rec = self._doc_to_proyecto(raw)
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
