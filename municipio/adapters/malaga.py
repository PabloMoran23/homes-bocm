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

WEB_BASE = "https://www.malaga.eu"
TABLON_URL = f"{WEB_BASE}/el-ayuntamiento/tablon-de-edictos/"
SEDE_BASE = "https://sede.malaga.eu"
URBANISMO_BASE = "https://urbanismo.malaga.eu"
MUNICIPIO = "Málaga"
ID_PREFIX = "malaga"
TABLON_PROCEDENCIA_URBANISMO = "245"

DEFAULT_SEED_PAGES: list[str] = [
    f"{URBANISMO_BASE}/normativa-y-planeamiento/informacion-pgom/",
    f"{URBANISMO_BASE}/aprobacion-proyecto-nueva-omlu/",
    f"{URBANISMO_BASE}/participacion-publica-peri-sierra-de-churriana/",
    f"{URBANISMO_BASE}/normativa-y-planeamiento/pepri-centro/",
    f"{URBANISMO_BASE}/normativa-y-planeamiento/planeamiento-de-desarrollo/",
    f"{URBANISMO_BASE}/normativa-y-planeamiento/pgou-2011/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n|parcelaci[oó]n|segregaci[oó]n|"
    r"dr de ocupaci[oó]n|declaraci[oó]n responsable)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|omlu|pepri|peri|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|expropiaci[oó]n|calificaci[oó]n|participaci[oó]n|convenio|"
    r"agente urbanizador|urbanizaci[oó]n)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(bolsa de trabajo|convocatoria.*empleo|selecci[oó]n de personal|"
    r"nombramiento|recursos humanos|subvencion|premio|orquesta)",
)
RE_ARTICLE = re.compile(r'<li class="list-element">(.*?)</li>', re.I | re.S)
RE_TITLE = re.compile(r'<h2[^>]*class="title-element[^"]*"[^>]*>(.*?)</h2>', re.I | re.S)
RE_DOC_LINK = re.compile(
    r'href="(https://www\.malaga\.eu/visorcontenido/EDIDocumentDisplayer/[^"]+)"',
    re.I,
)
RE_EXPORT_LINK = re.compile(
    r'href="((?:https://urbanismo\.malaga\.eu)?/export/[^"]+\.(?:pdf|zip)[^"]*)"',
    re.I,
)
RE_SEDE_TRAMITE = re.compile(
    r"href='(/es/tramitacion/urbanismo/detalle-del-tramite/index\.html\?id=\d+[^']*)'"
    r"[^>]*title='Trámite'[^>]*>([^<]+)",
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ES = re.compile(
    r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})",
    re.I,
)
RE_EXPDTE = re.compile(
    r"(?i)(?:\(\s*)?(?:expte\.?|expediente)\s+([A-Z]{0,6}\s*[\d/.\-]+)\)?",
)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


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


def _parse_fecha_es(text: str) -> str | None:
    m = RE_FECHA_ES.search(text or "")
    if not m:
        return None
    month = MESES.get(m.group(2).lower())
    if not month:
        return None
    try:
        return datetime(int(m.group(3)), month, int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    for parser in (_parse_fecha_dmy, _parse_fecha_es):
        d = parser(text)
        if d:
            return d
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _extract_expte(text: str) -> str | None:
    m = RE_EXPDTE.search(text or "")
    if m:
        return _strip_html(m.group(1))
    return None


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "estudio de detalle" in b or "estudio detalle" in b:
        return "estudio de detalle"
    if "plan parcial" in b or " pp " in b:
        return "plan parcial"
    if "plan especial" in b or "pepri" in b or "peri" in b:
        return "plan especial"
    if "pgom" in b:
        return "PGOM"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "omlu" in b:
        return "ordenanza urbanística"
    if "expropiaci" in b:
        return "expropiación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "aprobaci" in b and "inicial" in b:
        return "aprobación inicial"
    if "participaci" in b:
        return "participación pública"
    if "licencia" in b:
        return "licencia publicada"
    if "urbanizaci" in b:
        return "urbanización"
    return "planeamiento"


def _abs_url(base: str, href: str) -> str:
    return urllib.parse.urljoin(f"{base.rstrip('/')}/", unescape(href))


class MalagaAyuntamientoAdapter(AyuntamientoAdapter):
    """SAGA Suite: tablón edictos malaga.eu + portal urbanismo.malaga.eu + sede.malaga.eu."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.tablon_procedencia = str(
            self.config.get("tablon_procedencia") or TABLON_PROCEDENCIA_URBANISMO
        )
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.urbanismo_base = str(self.config.get("urbanismo_base") or URBANISMO_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-malaga/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _tablon_search_url(self, *, procedencia: str | None = None, texto: str | None = None) -> str:
        params: dict[str, str] = {}
        if procedencia:
            params["procedencia"] = procedencia
        if texto:
            params["texto"] = texto
        if not params:
            return self.tablon_url
        return f"{self.tablon_url}?{urllib.parse.urlencode(params)}"

    def _parse_tablon_articles(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for article_html in RE_ARTICLE.findall(html):
            title_m = RE_TITLE.search(article_html)
            departamento = _strip_html(title_m.group(1)) if title_m else ""
            text = unescape(re.sub(r"<[^>]+>", "\n", article_html))
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

            descripcion = ""
            for i, line in enumerate(lines):
                if departamento and departamento in line and i + 1 < len(lines):
                    descripcion = lines[i + 1]
                    break
            if not descripcion:
                for line in lines:
                    if line != departamento and len(line) > 20 and "Fecha" not in line:
                        descripcion = line
                        break

            fecha_inicio = None
            for i, line in enumerate(lines):
                if line.lower().startswith("fecha de inicio") and i + 1 < len(lines):
                    fecha_inicio = _parse_fecha_es(lines[i + 1])
                    break

            docs = RE_DOC_LINK.findall(article_html)
            url = docs[0] if docs else self.tablon_url
            titulo = descripcion or departamento or "Edicto urbanismo"
            blob = f"{departamento} {descripcion} {text}"
            expte = _extract_expte(blob)

            rows.append(
                {
                    "departamento": departamento[:200],
                    "titulo": titulo[:500],
                    "fecha": fecha_inicio,
                    "url": url,
                    "expte": expte,
                    "blob": blob[:2000],
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        urls = [
            self._tablon_search_url(procedencia=self.tablon_procedencia),
            self._tablon_search_url(texto="urbanismo"),
            self._tablon_search_url(texto="planeamiento"),
        ]
        for url in urls:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            for item in self._parse_tablon_articles(html):
                key = item.get("url") or item["titulo"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)
        return rows

    def _collect_seed_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
            page_title = _strip_html(page_title_m.group(1)) if page_title_m else page_url

            for href in RE_EXPORT_LINK.findall(html):
                doc_url = _abs_url(self.urbanismo_base, href)
                if doc_url in seen:
                    continue
                seen.add(doc_url)
                filename = unescape(doc_url.rsplit("/", 1)[-1])
                titulo = f"{page_title} — {filename}"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(f"{page_title} {filename}"),
                        "url": doc_url,
                        "procedimiento": page_title,
                        "blob": titulo,
                        "folder_url": page_url,
                    }
                )

            for m in re.finditer(
                r'href="(/export/[^"]+)"[^>]*>([^<]{4,200})</a>',
                html,
                re.I,
            ):
                href, link_text = m.group(1), _strip_html(m.group(2))
                if not href.lower().endswith((".pdf", ".zip")):
                    continue
                doc_url = _abs_url(self.urbanismo_base, href)
                if doc_url in seen:
                    continue
                if not RE_PROYECTO.search(link_text) and not RE_PROYECTO.search(page_title):
                    continue
                seen.add(doc_url)
                titulo = link_text if link_text else page_title
                if page_title.lower() not in titulo.lower():
                    titulo = f"{page_title} — {link_text}"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo),
                        "url": doc_url,
                        "procedimiento": page_title,
                        "blob": titulo,
                        "folder_url": page_url,
                    }
                )
        return rows

    def _collect_sede_tramites(self, *, max_pages: int = 3) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(1, max_pages + 1):
            url = f"{self.sede_base}/es/tramitacion/urbanismo/?page={page}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            matches = RE_SEDE_TRAMITE.findall(html)
            if not matches:
                break
            for href, titulo in matches:
                tramite_url = _abs_url(self.sede_base, href)
                if tramite_url in seen:
                    continue
                seen.add(tramite_url)
                titulo_clean = _strip_html(titulo)
                rows.append(
                    {
                        "titulo": titulo_clean[:500],
                        "url": tramite_url,
                        "blob": titulo_clean,
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            (
                self._tablon_search_url(procedencia=self.tablon_procedencia),
                "tablón edictos — Vivienda y Urbanismo",
                "tablon_urbanismo",
            ),
            (
                f"{self.sede_base}/es/tramitacion/urbanismo/",
                "Catálogo trámites urbanismo — sede electrónica",
                "sede_urbanismo",
            ),
            (
                f"{self.urbanismo_base}/licencias/como-va-mi-expediente/",
                "Consulta estado expedientes (Mi Carpeta)",
                "sede_consulta",
            ),
            (
                f"{self.urbanismo_base}/tramites/",
                "Trámites Gerencia Municipal de Urbanismo",
                "urbanismo_tramites",
            ),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo, origen in pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": origen.replace("_", " "),
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": origen,
                }
            )
        return rows

    def _is_urban_tablon(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_TABLON_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob):
            return False
        dept = (row.get("departamento") or "").lower()
        if "urbanismo" in dept or "planeamiento" in dept:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._is_urban_tablon(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expte") or row.get("url") or row["titulo"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / acto urbanístico",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expte"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._is_urban_tablon(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expte") or row.get("url") or row["titulo"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expte"),
            "origen": "tablon",
        }

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        title = row["titulo"]
        key = row.get("url") or title
        return {
            "id": _stable_id("proy", f"seed:{key}"),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("blob") or title),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "urbanismo_web",
        }

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
            return None
        kind = "licencia" if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) else "proy"
        if kind == "licencia":
            return None
        return {
            "id": _stable_id("proy", f"tramite:{row['url']}"),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": "trámite informativo",
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_tramite",
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", f"tramite:{row['url']}"),
            "fecha_concesion": None,
            "tipo": _strip_html(row["titulo"])[:200],
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_tramite",
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
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_sede_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("tablon_urbanismo", "sede_urbanismo", "sede_consulta", "urbanismo_tramites")),
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
        rows = self._load_jsonl(out_jsonl)
        for rid, rec in existing.items():
            rows_dict = {r["id"]: r for r in rows}
            rows_dict[rid] = rec
        rows = list({r["id"]: r for r in rows}.values())
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
            add(self._tablon_to_proyecto(item))
        for item in self._collect_seed_documents():
            add(self._seed_to_proyecto(item))
        for item in self._collect_sede_tramites():
            add(self._tramite_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "urbanismo_web": sum(1 for r in rows if r.get("origen") == "urbanismo_web"),
            "sede_tramite": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
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
