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

BASE = "https://benameji.es"
DOCUMENTOS_URL = f"{BASE}/ayuntamiento/ayuntamiento-documentos/"
SEDE_BASE = "https://sede.eprinsa.es/benameji"
TABLON_URL = f"{SEDE_BASE}/tablon-de-edictos"
PGOU_DRIVE_URL = "https://drive.google.com/file/d/12r5tqom9aiJMIADEh8r8vhi5ZbbpvcDV/view?usp=share_link"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Benamejí"
ID_PREFIX = "benameji"

RE_PDF_HREF = re.compile(
    r'href=["\']((?:https://benameji\.es)?/wp-content/uploads/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_ANCHOR_LINK = re.compile(
    r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.S | re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|anexo\s+[ivx]+|parcelaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional|parcial)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza.*(?:urban|obra|suelo|ordenaci|instrumento|intervenci)|"
    r"innovaci[oó]n|avance|instrumento|registro municipal|plusvalia|plusval[ií]a|"
    r"construccion|construcci[oó]n|residuos.*construcci)",
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _fecha_from_blob(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"/(\d{4})/(\d{2})/", text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "convenio" in b:
        return "convenio urbanístico"
    if "instrumento" in b and "ordenaci" in b:
        return "instrumento de ordenación"
    if "registro municipal" in b:
        return "registro urbanístico"
    if "ordenanza" in b and ("obra" in b or "urban" in b or "suelo" in b):
        return "ordenanza urbanística"
    if "plusval" in b:
        return "plusvalía municipal"
    if "residuos" in b and "construcci" in b:
        return "ordenanza RCED"
    if "comunicaci" in b and "previa" in b:
        return "comunicación previa"
    return "urbanismo"


class BenamejiAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi eprinsa (documentos/PDFs) + sede Diputación Córdoba (tablón SPA)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.documentos_url = str(self.config.get("documentos_url") or DOCUMENTOS_URL)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_DRIVE_URL)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-benameji/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{BASE}/", href)

    def _collect_documentos_links(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.documentos_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_ANCHOR_LINK.finditer(html):
            href = m.group(1).strip()
            if not href or href.startswith("#") or href.startswith("mailto:"):
                continue
            anchor = _strip_html(m.group(2))
            if not anchor:
                continue
            abs_href = href if href.startswith("http") else self._abs_url(href)
            if abs_href in seen:
                continue
            blob = f"{anchor} {abs_href}"
            is_pdf = abs_href.lower().endswith(".pdf") or "/wp-content/uploads/" in abs_href.lower()
            is_drive = "drive.google.com" in abs_href
            if not (is_pdf or is_drive):
                continue
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            seen.add(abs_href)
            rows.append(
                {
                    "titulo": anchor[:500],
                    "fecha": _fecha_from_blob(blob),
                    "url": self.documentos_url,
                    "pdf_url": abs_href if is_pdf else None,
                    "external_url": abs_href,
                    "blob": blob,
                    "origen": "web_documentos",
                    "is_licencia": bool(RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob)),
                }
            )

        for m in RE_PDF_HREF.finditer(html):
            href = self._abs_url(m.group(1))
            if href in seen:
                continue
            name = unescape(urllib.parse.unquote(Path(href).name)).replace("_", " ").replace(".pdf", "")
            blob = f"{name} {href}"
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            seen.add(href)
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(blob),
                    "url": self.documentos_url,
                    "pdf_url": href,
                    "external_url": href,
                    "blob": blob,
                    "origen": "web_documentos",
                    "is_licencia": bool(RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob)),
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for term in ("obra", "urbanismo", "licencia", "plusvalia"):
            url = (
                f"{BASE}/wp-json/wp/v2/posts"
                f"?search={urllib.parse.quote(term)}&per_page=20"
                f"&_fields=id,date,link,title,content"
            )
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(data, list):
                continue
            for post in data:
                pid = int(post.get("id") or 0)
                if pid in seen:
                    continue
                seen.add(pid)
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                content = post.get("content", {}).get("rendered", "") or ""
                if not RE_PROYECTO.search(f"{title} {content}") and not RE_LICENCIA.search(title):
                    continue
                rows.append(
                    {
                        "id": pid,
                        "titulo": title[:500],
                        "fecha": (post.get("date") or "")[:10] or None,
                        "url": post.get("link") or "",
                        "content": content,
                        "origen": f"wp_search_{term}",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos — licencias y urbanismo",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Sede eprinsa (Diputación Córdoba); listado vía SPA Ember sin API pública",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/tramites"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/tramites",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin histórico público estructurado)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación Cl@ve/certificado; no hay listado abierto",
                "origen": "sede_tramite",
            },
        ]

    def _link_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        key = item.get("pdf_url") or item.get("external_url") or item["titulo"]
        blob = item.get("blob") or item.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", self.documentos_url),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        if item.get("external_url") and "drive.google.com" in item["external_url"]:
            rec["external_url"] = item["external_url"]
        return rec

    def _link_to_licencia(self, item: dict[str, Any]) -> dict[str, Any]:
        key = item.get("pdf_url") or item.get("external_url") or item["titulo"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": item.get("fecha"),
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"],
            "url": item.get("url", self.documentos_url),
            "source": "ayuntamiento",
            "nota": "Modelo/solicitud informativa; no concesión publicada en tablón",
            "origen": item.get("origen"),
            "pdf_url": item.get("pdf_url"),
        }

    def _post_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        blob = f"{titulo} {item.get('content', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        key = item.get("url") or titulo
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _post_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        if not RE_LICENCIA.search(titulo):
            return None
        key = item.get("url") or titulo
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": item.get("fecha"),
            "tipo": "noticia urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_documentos_links():
            if item.get("is_licencia"):
                rec = self._link_to_licencia(item)
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        for item in self._collect_wp_posts():
            rec = self._post_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_licencias(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": result["rows"],
                    "added": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": result["rows"], "added": 0, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_documentos_links():
            if not item.get("is_licencia"):
                add(self._link_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._post_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", self.pgou_url),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Benamejí — documento refundido",
                "fecha": None,
                "tipo": "PGOU",
                "url": self.pgou_url,
                "source": "ayuntamiento",
                "origen": "web_documentos",
                "external_url": self.pgou_url,
            }
        )
        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Benamejí — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": "Visor regional de planeamiento; sin geometría por expediente municipal",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pdfs": sum(1 for r in rows if r.get("pdf_url")),
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
