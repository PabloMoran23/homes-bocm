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

BASE = "https://anora.es"
DOCUMENTOS_URL = f"{BASE}/ayuntamiento/documentos/"
SEDE_BASE = "https://sede.eprinsa.es/anora"
TABLON_URL = f"{SEDE_BASE}/tablon-de-edictos"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Añora"
ID_PREFIX = "anora"

RE_ANCHOR = re.compile(
    r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.S | re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|ordenanza.*obra|situaci[oó]n jur[ií]dica.*edific)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|innovaci[oó]n|avance|ari-|normas urban|pol[ií]gono industrial|"
    r"certificaci[oó]n.*acuerdo|estructura org[aá]nica|palomares)",
)
RE_URBAN_DOC = re.compile(
    r"(?i)(pgou|planeam|urban|certificaci[oó]n.*acuerdo|modificaci[oó]n.*pgou|"
    r"ari[s]?\s*\d|normas urban|estructura org[aá]nica|plan parcial|pol[ií]gono industrial|"
    r"palomares|suelo (?:no )?urban|ordenanza.*suelo|actuaciones extraordinarias.*suelo)",
)
RE_SKIP_DOC = re.compile(
    r"(?i)^(ordenanzas fiscales|ordenanza municipal sobre tr[aá]fico|"
    r"ordenanza de pol[ií]cia|ordenanza comercio ambulante|ordenanza para implantaci[oó]n|"
    r"ordenanza reguladora de la administraci[oó]n|ordenanza registro demandantes|"
    r"ordenanza reguladora del uso.*caminos)",
)
RE_SKIP_POST = re.compile(
    r"(?i)(ayuda[- ]diputaci[oó]n|subvenci[oó]n diputaci[oó]n|bando.*incendio|"
    r"olimpiadas rurales|casetas feria|ibericfest|bonificaci[oó]n.*ibi|"
    r"paneles solares|becas mec|purines|hacienda local|incoterms|pilates|"
    r"paseo por a[nñ]ora|casa consistorial|indicadores de la ley de transparencia|"
    r"transparencia econ[oó]mico|relaciones con los ciudadanos|igualdad|"
    r"mini-olimpiadas|barra iberic)",
)
RE_BOJA_DATE = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_BOP_DATE = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _fecha_from_blob(text: str) -> str | None:
    m = RE_BOJA_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_BOP_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "plan parcial" in b or "polígono industrial" in b or "poligono industrial" in b:
        return "plan parcial"
    if "modificaci" in b and "pgou" in b:
        return "modificación PGOU"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "ordenanza" in b and "suelo" in b:
        return "ordenanza urbanística"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "certificaci" in b and "acuerdo" in b:
        return "certificación planeamiento"
    if "planos" in b or "cartograf" in b:
        return "cartografía urbanística"
    if "bop" in b or "boja" in b:
        return "publicación oficial"
    return "urbanismo"


class AnoraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (documentos PGOU) + sede eprinsa/Diputación Córdoba (tablón SPA)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.documentos_url = str(self.config.get("documentos_url") or DOCUMENTOS_URL)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-anora/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{BASE}/", href)

    def _collect_documentos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.documentos_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_ANCHOR.finditer(html):
            href = self._abs_url(m.group(1))
            titulo = _strip_html(m.group(2))[:500]
            if not titulo or len(titulo) < 8:
                continue
            if RE_SKIP_DOC.search(titulo):
                continue
            blob = f"{titulo} {href}"
            if not RE_URBAN_DOC.search(blob):
                continue
            if href in seen:
                continue
            seen.add(href)
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_blob(blob),
                    "url": href,
                    "blob": blob,
                    "origen": "web_documentos",
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for term in ("planeamiento", "pgou", "urbanismo"):
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
                blob = f"{title} {content}"
                if RE_SKIP_POST.search(blob):
                    continue
                if not RE_PROYECTO.search(title) and not (
                    RE_PROYECTO.search(content) and RE_PROYECTO.search(title)
                ):
                    if not RE_LICENCIA.search(title):
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
            {
                "id": _stable_id(
                    "lic",
                    f"{BASE}/wp-content/uploads/2022/01/05-ordenanza_procedimiento_administrativo_reconocimiento_situacion_juridica_edificaciones_en_suelo_no_urbanizable_afo.pdf",
                ),
                "fecha_concesion": None,
                "tipo": "ordenanza situación jurídica edificaciones",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenanza situación jurídica edificaciones en suelo no urbanizable",
                "url": (
                    f"{BASE}/wp-content/uploads/2022/01/"
                    "05-ordenanza_procedimiento_administrativo_reconocimiento_situacion_juridica_edificaciones_en_suelo_no_urbanizable_afo.pdf"
                ),
                "source": "ayuntamiento",
                "nota": "Modelo normativo; no concesiones publicadas",
                "origen": "web_documentos",
            },
        ]

    def _doc_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        url = item["url"]
        blob = item.get("blob") or item.get("titulo", "")
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _post_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        content = item.get("content", "") or ""
        blob = f"{titulo} {content}"
        if RE_SKIP_POST.search(blob):
            return None
        if not RE_PROYECTO.search(titulo):
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
        for item in self._collect_wp_posts():
            rec = self._post_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": 0, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_documentos():
            add(self._doc_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._post_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", SITUA_SEARCH),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Añora — consulta SITUA (Junta de Andalucía)",
                "fecha": "2022-01-01",
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
            "documentos": sum(1 for r in rows if r.get("origen") == "web_documentos"),
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
