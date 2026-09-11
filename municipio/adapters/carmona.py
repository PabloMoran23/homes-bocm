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

WEB_BASE = "https://www.carmona.org"
SEDE_BASE = "https://sede.carmona.org"
TABLON_URL = f"{WEB_BASE}/actualidad/tablon.php"
PLANEAMIENTO_URL = f"{WEB_BASE}/planeamiento/"
NORMAS_URL = f"{WEB_BASE}/planeamiento/plan_normas_subsidiarias_mpales.php"
MUNICIPIO = "Carmona"
ID_PREFIX = "carmona"

DEFAULT_PLANEAMIENTO_PAGES = [
    PLANEAMIENTO_URL,
    NORMAS_URL,
    f"{WEB_BASE}/planeamiento/plan_publ8.php",
    f"{WEB_BASE}/planeamiento/plan_publ26.php",
    f"{WEB_BASE}/planeamiento/ficha_catalogo.php",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|actividades municipales)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nn\.?ss|normas subsidiarias|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|reforma interior|atu|transformaci[oó]n urban|"
    r"cat[aá]logo|ficha del cat[aá]logo|pepp|parque log[ií]stico|instrucci[oó]n municipal)",
)
RE_TABLON_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|proceso selectivo|bolsa de trabajo|empleo|nombramiento|"
    r"subvencion(?:es)? deportiv|clubes deportivos|talleres culturales|escuela municipal de m[uú]sica|"
    r"plan de formaci[oó]n y empleo|pai carmona|fisioterapeuta|monitor/a|educador/a social|"
    r"auxiliar de enfermer[ií]a|administrativo|conserje|tag\b|comisi[oó]n de servicios|"
    r"bando de ampliaci[oó]n del horario|fiestas patronales|virus del nilo|recomendaciones)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DOC_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?carmona\.org)?/[^"]+\.(?:pdf|php)[^"]*)"',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


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
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1960 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "normas subsidiarias" in b or "nn.ss" in b or "nnss" in b:
        return "normas subsidiarias"
    if "plan especial" in b or "pepp" in b:
        return "plan especial"
    if "plan parcial" in b:
        return "plan parcial"
    if "reforma interior" in b or "peri" in b:
        return "reforma interior"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "instrucci" in b and "atu" in b:
        return "instrucción ATU"
    if "ficha" in b and "cat[aá]logo" in b:
        return "modificación catálogo"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "licencia" in b:
        return "licencia publicada"
    if "planeamiento general" in b or "pgou" in b:
        return "planeamiento general"
    return "urbanismo"


class CarmonaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web municipal PHP (tablón + planeamiento PDFs) + sede propia carmona.org."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.planeamiento_pages = [
            str(u) for u in (self.config.get("planeamiento_pages") or DEFAULT_PLANEAMIENTO_PAGES)
        ]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-carmona/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        pattern = (
            r"<a href='publicacion\.php\?pub=([a-f0-9]+)'[^>]*>([^<]+)</a></div>"
            r"<div class='one_quarter'[^>]*><b>FECHA</b></div><div class='one_quarter'[^>]*>"
            r"(\d{2}/\d{2}/\d{4})</div>"
        )
        for pub_id, title, fecha_raw in re.findall(pattern, html, re.I):
            title = _strip_html(title)
            url = f"{self.web_base}/actualidad/publicacion.php?pub={pub_id}"
            rows.append(
                {
                    "pub_id": pub_id,
                    "titulo": title[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": title,
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_planeamiento_docs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(url: str, titulo: str, origen: str = "planeamiento") -> None:
            abs_url = self._abs_web(url)
            if abs_url in seen:
                return
            if "carmona.org" not in abs_url:
                return
            if not re.search(r"(?i)planeamiento|ordenanzas", abs_url):
                return
            seen.add(abs_url)
            name = titulo or abs_url.rsplit("/", 1)[-1]
            rows.append(
                {
                    "url": abs_url,
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(name + " " + abs_url),
                    "blob": f"{name} {abs_url}",
                    "origen": origen,
                }
            )

        for page_url in self.planeamiento_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            page_title = _strip_html(re.search(r"<title>([^<]+)</title>", html, re.I).group(1))
            if page_url.endswith(".php") and "plan_normas" not in page_url:
                add(page_url, page_title or "Documento urbanístico")

            for m in RE_DOC_HREF.finditer(html):
                href = m.group(1)
                basename = urllib.parse.unquote(href.rsplit("/", 1)[-1])
                titulo = re.sub(r"[_\-]+", " ", basename.rsplit(".", 1)[0])
                add(href, titulo)

            for m in re.finditer(
                r'<a[^>]+href="([^"]+)"[^>]*>(?:\s*<img[^>]*>\s*)?([^<]{8,300})</a>',
                html,
                re.I,
            ):
                href, text = m.group(1), _strip_html(m.group(2))
                if not text or text.lower() in {"volver arriba", "inicio"}:
                    continue
                if re.search(r"(?i)modificaci|plan |normas|ordenanza|aprob|parcial|especial|pepp|atu|ficha", text):
                    add(href, text)

        add(PLANEAMIENTO_URL, "Documentos urbanísticos — índice planeamiento")
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios municipal",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Publicaciones diarias con edictos urbanísticos y licencias",
                "origen": "web_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/tramites"),
                "fecha_concesion": None,
                "tipo": "trámites licencias de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias de Obras — sede electrónica",
                "url": f"{self.sede_base}/tramites",
                "source": "ayuntamiento",
                "nota": "Trámite online sin listado histórico de concesiones",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/tramites#actividades"),
                "fecha_concesion": None,
                "tipo": "inscripción actividades municipales",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Inscripciones y consulta de actividades municipales",
                "url": f"{self.sede_base}/tramites",
                "source": "ayuntamiento",
                "nota": "Licencias de actividad vía sede propia",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/ordenanzas/obras_me.pdf"),
                "fecha_concesion": None,
                "tipo": "ordenanza licencias obras menores",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenanza reguladora de licencias urbanísticas de obras menores",
                "url": f"{self.web_base}/ordenanzas/obras_me.pdf",
                "source": "ayuntamiento",
                "nota": "Normativa publicada en web municipal",
                "origen": "web_ordenanzas",
            },
        ]

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_TABLON_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        tipo = "licencia urbanística"
        if re.search(r"(?i)actividad|hosteler", blob):
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("pub_id") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._tablon_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("pub_id") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row["url"]
        blob = row.get("blob") or row["titulo"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "planeamiento",
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

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("web_tablon", "sede_tramite", "web_ordenanzas")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
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

        for item in self._collect_planeamiento_docs():
            add(self._doc_to_proyecto(item))

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "planeamiento": sum(1 for r in rows if r.get("origen") == "planeamiento"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
