from __future__ import annotations

import hashlib
import http.cookiejar
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

SEDE_BASE = "https://sede.vilagarcia.gal"
WEB_BASE = "https://vilagarcia.es"
MUNICIPIO = "Vilagarcía de Arousa"
ID_PREFIX = "vilagarcia-de-arousa"
INE = "36060"

BULLETIN_INDEX = f"{SEDE_BASE}/public/bulletin/bulletin-index.xhtml"
BULLETIN_DETAIL = f"{SEDE_BASE}/public/bulletin/bulletin-details.xhtml"
PLANNING_INFO = f"{SEDE_BASE}/public/dynamic/transparency/planninginfo/"
CATALOG_INDEX = f"{SEDE_BASE}/public/catalog/catalog-index.xhtml"
URBANISMO_WEB = f"{WEB_BASE}/servicios/urbanismo.asp"
SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_QUERY_DOC = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"

DEFAULT_URBAN_TRAMITES: list[tuple[str, str]] = [
    (
        "02001 Solicitude de outorgamento de licenzas urbanísticas e comunicacións previas de obras",
        f"{SEDE_BASE}/public/catalog-detail/2810946",
    ),
    (
        "02010 Solicitude de licenza urbanística",
        f"{SEDE_BASE}/public/publications/list/forms/FORMS",
    ),
    (
        "02001 Comunicación previa de obra menor",
        f"{SEDE_BASE}/public/publications/list/forms/FORMS",
    ),
    (
        "02012 Primeira ocupación — réxime de comunicación previa",
        f"{SEDE_BASE}/public/publications/list/forms/FORMS",
    ),
    (
        "02011 Presentación proxecto de execución — réxime de comunicación previa",
        f"{SEDE_BASE}/public/publications/list/forms/FORMS",
    ),
]

RE_BULLETIN_BLOCK = re.compile(
    r'<h4 style="display: block;">\s*'
    r'<a href="([^"]+idtaskdata=(\d+))"[^>]*>([^<]+)</a>',
    re.I,
)
RE_BULLETIN_DEPT = re.compile(
    r'width:65%">([^<]+)</span>',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_PUB = re.compile(
    r"(?i)(?:data de publicaci[oó]n|fecha de publicaci[oó]n)\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan |pxom|pgom|proyecto|proxecto|estudo de detalle|peri|"
    r"reparcel|convenio|exposici[oó]n p[uú]blica|aprobaci[oó]n|entidade urban|"
    r"ru[ií]na|subasta de finca|cambio de uso|urbanizaci[oó]n|vial|informaci[oó]n p[uú]blic)",
)
RE_EXCLUDE_PROY = re.compile(
    r"(?i)(ibi|padr[oó]n|imposto|biomassa|tarefas de xesti|axudas para estudantes|"
    r"campamento urbano|contaminaci[oó]n ac[uú]stica|ruido)",
)
RE_LICENCIA = re.compile(
    r"(?i)(licen|licenz|comunicaci[oó]n previa|declaraci[oó]n responsable|obra menor|"
    r"primeira ocupaci[oó]n|outorgamento)",
)
URBANISMO_DEPT = "XERENCIA DE URBANISMO"


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


def _normalize_bulletin_path(href: str) -> str:
    path = href.split(";")[0]
    if path.startswith("http"):
        return path
    return f"{SEDE_BASE}{path}"


def _proyecto_tipo(titulo: str, figura: str | None = None) -> str:
    blob = f"{titulo} {figura or ''}".lower()
    if "estudo de detalle" in blob:
        return "estudio de detalle"
    if "proxecto de urbaniz" in blob or "proyecto de urbaniz" in blob:
        return "proyecto de urbanización"
    if "entidade urban" in blob:
        return "entidad urbanística de conservación"
    if "plan xeral" in blob or "pxom" in blob or "pgom" in blob:
        return "PGOM/PXOM"
    if "plan parcial" in blob or "peri" in blob:
        return "plan parcial / PERI"
    if "informaci" in blob and ("public" in blob or "públic" in blob):
        return "información pública"
    if "aprobaci" in blob:
        return "aprobación planeamiento"
    if "cambio de uso" in blob:
        return "cambio de uso"
    return "planeamiento"


class VilagarciaDeArousaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede Cividas (tablón + transparencia planeamiento) + SIOTUGA (INE 36060)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.max_siotuga_des = int(self.config.get("max_siotuga_desarrollo", 45))
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        self._siotuga_token_cache: str | None = None
        self._detail_fecha_cache: dict[str, str | None] = {}

    def _fetch(self, url: str, data: bytes | None = None, charset: str | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-vilagarcia-de-arousa/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        else:
            req = urllib.request.Request(url, headers=headers)
        with self._opener.open(req, timeout=90) as resp:
            enc = charset or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(enc, errors="replace")

    def _bulletin_fecha(self, task_id: str) -> str | None:
        if task_id in self._detail_fecha_cache:
            return self._detail_fecha_cache[task_id]
        url = f"{BULLETIN_DETAIL}?idtaskdata={task_id}"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            self._detail_fecha_cache[task_id] = None
            return None
        m = RE_FECHA_PUB.search(_strip_html(html))
        fecha = _parse_fecha_dmy(m.group(1)) if m else _parse_fecha_dmy(html)
        self._detail_fecha_cache[task_id] = fecha
        return fecha

    def _collect_bulletin(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(BULLETIN_INDEX)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_BULLETIN_BLOCK.finditer(html):
            href, task_id, title_raw = m.group(1), m.group(2), unescape(m.group(3)).strip()
            tail = html[m.end() : m.end() + 1200]
            dept_m = RE_BULLETIN_DEPT.search(tail)
            dept = (dept_m.group(1) if dept_m else "").strip()
            if dept != URBANISMO_DEPT:
                continue
            if RE_EXCLUDE_PROY.search(title_raw):
                continue
            if not RE_PROYECTO.search(title_raw):
                continue
            url = _normalize_bulletin_path(href)
            rows.append(
                {
                    "titulo": title_raw[:500],
                    "fecha": self._bulletin_fecha(task_id),
                    "url": url,
                    "task_id": task_id,
                    "origen": "sede_tablon_urb",
                }
            )
        return rows

    def _get_siotuga_token(self) -> str:
        if self._siotuga_token_cache:
            return self._siotuga_token_cache
        html = self._fetch(SIOTUGA_INVENTARIO, charset="utf-8")
        m = re.search(r"id=['\"]token['\"][^>]*value=['\"]([^'\"]+)['\"]", html, re.I)
        if not m:
            m = re.search(r"name=['\"]token['\"][^>]*value=['\"]([^'\"]+)['\"]", html, re.I)
        if not m:
            raise RuntimeError("SIOTUGA: no se encontró token de sesión")
        self._siotuga_token_cache = m.group(1)
        return self._siotuga_token_cache

    def _siotuga_query(self, idclase: int) -> list[dict[str, Any]]:
        token = self._get_siotuga_token()
        body = urllib.parse.urlencode({"id": INE, "token": token, "idclase": str(idclase)}).encode()
        raw = self._fetch(SIOTUGA_QUERY_DOC, data=body, charset="utf-8")
        if not raw.strip() or raw.startswith("tokenIncorrecto"):
            return []
        try:
            docs = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return docs if isinstance(docs, list) else []

    def _collect_siotuga(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for doc in self._siotuga_query(14):
            nombre = str(doc.get("docnome") or "Plan xeral")
            rows.append(
                {
                    "titulo": nombre,
                    "fecha": doc.get("fechaaddef") or doc.get("fechabop"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo(nombre, str(doc.get("figura") or "")),
                    "origen": "siotuga_pg",
                    "siotuga_id": doc.get("id"),
                    "figura": doc.get("figura"),
                }
            )
        for doc in self._siotuga_query(13)[: self.max_siotuga_des]:
            nombre = str(doc.get("docnome") or "Planeamento desenvolvemento")
            rows.append(
                {
                    "titulo": nombre,
                    "fecha": doc.get("fechaaddef") or doc.get("fechabop"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo(nombre, str(doc.get("figura") or "")),
                    "origen": "siotuga_des",
                    "siotuga_id": doc.get("id"),
                    "figura": doc.get("figura"),
                }
            )
        return rows

    def _fixed_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Información de planificación — transparencia sede",
                "fecha": None,
                "url": PLANNING_INFO,
                "tipo": "transparencia planeamiento",
                "origen": "sede_planninginfo",
            },
            {
                "titulo": "Taboleiro de anuncios electrónico — Xerencia de Urbanismo",
                "fecha": None,
                "url": BULLETIN_INDEX,
                "tipo": "tablón anuncios",
                "origen": "sede_tablon_index",
            },
            {
                "titulo": "Catálogo de procedementos — Xerencia de Urbanismo",
                "fecha": None,
                "url": CATALOG_INDEX,
                "tipo": "trámites urbanismo",
                "origen": "sede_catalogo",
            },
            {
                "titulo": "Xerencia de Urbanismo — web municipal",
                "fecha": None,
                "url": URBANISMO_WEB,
                "tipo": "información urbanismo",
                "origen": "web_urbanismo",
            },
            {
                "titulo": f"Inventario planeamento municipal — SIOTUGA (INE {INE})",
                "fecha": None,
                "url": SIOTUGA_INVENTARIO,
                "tipo": "inventario planeamiento",
                "origen": "siotuga_inventario",
            },
        ]

    def _tramite_licencias(self) -> list[dict[str, Any]]:
        return [
            {"titulo": title, "url": url, "origen": "sede_tramite_info"}
            for title, url in DEFAULT_URBAN_TRAMITES
        ]

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{url}|{titulo}|{row.get('task_id','')}|{row.get('siotuga_id','')}"),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(titulo, row.get("figura")),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("task_id"):
            rec["tablon_task_id"] = row["task_id"]
        if row.get("siotuga_id"):
            rec["siotuga_doc_id"] = row["siotuga_id"]
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
        return {
            "id": _stable_id("lic", url + titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite / información urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def _collect_proyecto_sources(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._fixed_seeds())
        rows.extend(self._collect_siotuga())
        rows.extend(self._collect_bulletin())
        return rows

    def _collect_licencia_sources(self) -> list[dict[str, Any]]:
        rows = self._tramite_licencias()
        for item in self._collect_bulletin():
            if RE_LICENCIA.search(item["titulo"]):
                rows.append({**item, "origen": "sede_tablon_licencia"})
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_licencia_sources():
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites_info"}

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
        for item in self._collect_proyecto_sources():
            rec = self._to_proyecto(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if "tablon" in str(r.get("origen", ""))),
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
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
