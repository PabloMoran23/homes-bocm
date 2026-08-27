from __future__ import annotations

import hashlib
import http.cookiejar
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

SEDE_BASE = "https://elpuertodesantamaria.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
WEB_BASE = "https://www.elpuertodesantamaria.es"
TRANSP_BASE = "https://transparencia.elpuertodesantamaria.es"
MUNICIPIO = "El Puerto de Santa María"
ID_PREFIX = "el-puerto-de-santa-maria"

DEFAULT_WEB_SEEDS: list[str] = [
    f"{WEB_BASE}/areas-municipales/urbanismo-y-patrimonio/urbanismo/info-publica-instrumentos-de-planeamiento-y-gestion/informacion-publica-instrumentos-de-planeamiento-y-gestion",
    f"{WEB_BASE}/areas-municipales/urbanismo-y-patrimonio/urbanismo/plan-general-de-ordenacion-urbana/plan-general-de-ordenacion-urbana-1",
    f"{WEB_BASE}/areas-municipales/urbanismo-y-patrimonio/urbanismo/pgom-y-pou/plan-general-de-ordenacion-municipal-pgom-y-plan-de-ordenacion-urbana-pou",
    f"{WEB_BASE}/areas-municipales/urbanismo-y-patrimonio/urbanismo/planeamiento-de-desarrollo-1/planeamiento-de-desarrollo",
    f"{WEB_BASE}/areas-municipales/urbanismo-y-patrimonio/urbanismo/consulta-publica-previa/consulta-previa",
    f"{WEB_BASE}/areas-municipales/urbanismo-y-patrimonio/urbanismo/convenios-urbanisticos-1/convenios-urbanisticos",
    f"{WEB_BASE}/contenido/815/16952/info.-publica-proyectos-de-urbanizacion",
]

DEFAULT_TRANSP_SEEDS: list[str] = [
    f"{TRANSP_BASE}/exposicion-publica",
    f"{TRANSP_BASE}/licencias-urbanisticas",
    f"{TRANSP_BASE}/calificacion-ambiental-1",
    f"{TRANSP_BASE}/proyecto-y-estudio-impacto-ambiental-1",
    f"{TRANSP_BASE}/patrimonio-1",
    f"{TRANSP_BASE}/exposicion-publica/plan-normativo-consultas-previas",
    f"{TRANSP_BASE}/exposicion-publica/plan-normativo-audiencia-e-informacion-publica",
    f"{TRANSP_BASE}/exposicion-publica/exposicion-publica-consulta-publica-previa-a-la-elaboracion-de-instrumentos-urbanisticos",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| urban[ií]stica)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|proyecto de actuaci[oó]n|enoturismo|gimnasio|centro de ocio)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|pou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bop|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|urbanizaci[oó]n|consulta p[uú]blica|calificaci[oó]n ambiental|"
    r"peprich|conjunto hist[oó]rico|gaoner|cielos|la rosa|camino del juncal|giralda)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|aspirantes|oposici[oó]n|polic[ií]a local|"
    r"nombramiento|convocatoria.*empleo|cobranza iae|padrones|decreto.*tribunal|"
    r"tribunal|oep\s*20|listado definitivo|electricista|arquitecto|t[eé]cnico superior|"
    r"presupuesto general|suspensi[oó]n cautelar.*nombramiento|bandera municipal|adopci[oó]n de bandera)",
)
RE_PREVIEW_DOC = re.compile(
    r'href="((?:https://elpuertodesantamaria\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"'
    r'[^>]*title="([^"]+)"',
    re.I,
)
RE_PREVIEW_DOC_ALT = re.compile(
    r'title="([^"]+)"[^>]*href="((?:https://elpuertodesantamaria\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPE = re.compile(
    r"(?i)(?:expte|expediente|exp\.?)\s*[:.]?\s*([\w/\-\.]+)",
)
RE_SKIP_TITLE = re.compile(
    r"(?i)^(audiencia e informaci[oó]n p[uú]blica|ordenanzas y reglamentos|"
    r"planes urban[ií]sticos y proyectos|consulta p[uú]blica previa|"
    r"presupuesto general|tabl[oó]n de edictos|proyectos estrat[eé]gicos|"
    r"urbanismo y patrimonio|urbanismo|info\.? p[uú]blica instrumentos|"
    r"licencias urbanisticas|calificaci[oó]n ambiental)$",
)


def _is_nav_noise(title: str) -> bool:
    words = title.split()
    if len(words) >= 4 and len(words) % 2 == 0:
        half = len(words) // 2
        if [w.lower() for w in words[:half]] == [w.lower() for w in words[half:]]:
            return True
    return bool(RE_SKIP_TITLE.match(title.strip()))


RE_SKIP_LINK = re.compile(
    r"(?i)(facebook|twitter|whatsapp|aviso-legal|mapa-del-web|contacta-con|"
    r"sharer\.php|index\.php\?art_id=)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        m = RE_FECHA_DASH.search(text or "")
        if not m:
            return None
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"/(\d{4})/", url)
    if m:
        return f"{m.group(1)}-01-01"
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _extract_expte(text: str) -> str | None:
    m = RE_EXPE.search(text or "")
    return m.group(1)[:120] if m else None


def _normalize_url(url: str) -> str:
    return (
        url.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
        .replace("\u00ad", "")
    )


def _abs_url(href: str, base: str) -> str:
    return _normalize_url(urllib.parse.urljoin(f"{base.rstrip('/')}/", unescape(href)))


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if "estudio de detalle" in blob or "estudio detalle" in blob:
        return "estudio de detalle"
    if "urbanizaci" in blob:
        return "urbanización"
    if "plan parcial" in blob:
        return "plan parcial"
    if "plan especial" in blob or "peprich" in blob:
        return "plan especial"
    if "pgom" in blob or "pou" in blob:
        return "PGOM/POU"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "calificaci" in blob and "ambiental" in blob:
        return "calificación ambiental"
    if "proyecto de actuaci" in blob:
        return "proyecto de actuación"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "consulta" in blob and ("previa" in blob or "pública" in blob):
        return "consulta pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "licencia" in blob:
        return "licencia publicada"
    return "urbanismo"


class ElPuertoDeSantaMariaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico ehome + portal transparencia + web municipal urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.web_seeds = [str(u) for u in (self.config.get("web_seeds") or DEFAULT_WEB_SEEDS)]
        self.transp_seeds = [str(u) for u in (self.config.get("transp_seeds") or DEFAULT_TRANSP_SEEDS)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        url = _normalize_url(url)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-puerto-de-santa-maria/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for pattern in (RE_PREVIEW_DOC, RE_PREVIEW_DOC_ALT):
            for m in pattern.finditer(html):
                if pattern is RE_PREVIEW_DOC:
                    url, titulo = m.group(1), m.group(2)
                else:
                    titulo, url = m.group(1), m.group(2)
                if url.startswith("/"):
                    url = f"{self.sede_base}{url}"
                if url in seen:
                    continue
                seen.add(url)
                titulo = _strip_html(titulo)
                expte = _extract_expte(titulo)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "expediente": expte,
                        "procedimiento": "",
                        "fecha": _fecha_from_blob(titulo),
                        "url": url,
                        "blob": titulo,
                        "origen": "tablon",
                    }
                )
        return rows

    def _collect_page_links(
        self,
        page_url: str,
        *,
        base: str,
        origen: str,
        urban_only: bool = True,
    ) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, inner in RE_LINK.findall(html):
            if RE_SKIP_LINK.search(href):
                continue
            title = _strip_html(inner)
            if not title or len(title) < 8:
                continue
            if _is_nav_noise(title):
                continue
            if title.lower() in ("leer más", "leer mas", "más información", "ver documentos"):
                continue
            url = _abs_url(href, base)
            if url in seen:
                continue
            blob = f"{title} {url}"
            if urban_only and not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _fecha_from_blob(title, url),
                    "url": url,
                    "procedimiento": origen,
                    "blob": blob,
                    "origen": origen,
                    "expediente": _extract_expte(title),
                }
            )
        return rows

    def _collect_transparencia(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for seed in self.transp_seeds:
            for item in self._collect_page_links(
                seed, base=self.transp_base, origen="transparencia", urban_only=True
            ):
                if item["url"] in seen_urls:
                    continue
                seen_urls.add(item["url"])
                rows.append(item)
                if (
                    item["url"].startswith(self.transp_base)
                    and "/exposicion-publica" in item["url"]
                    and item["url"] not in self.transp_seeds
                    and not item["url"].endswith(".pdf")
                ):
                    for sub in self._collect_page_links(
                        item["url"],
                        base=self.transp_base,
                        origen="transparencia_detalle",
                        urban_only=False,
                    ):
                        if sub["url"] in seen_urls:
                            continue
                        blob = sub.get("blob") or ""
                        if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                            if ".pdf" not in sub["url"].lower():
                                continue
                        seen_urls.add(sub["url"])
                        sub["origen"] = "transparencia_detalle"
                        rows.append(sub)
        return rows

    def _collect_web_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in self.web_seeds:
            for item in self._collect_page_links(
                seed, base=self.web_base, origen="web_urbanismo", urban_only=False
            ):
                url = item["url"].lower()
                blob = item.get("blob") or ""
                if ".pdf" not in url and "/uploads/" not in url:
                    continue
                if not RE_PROYECTO.search(blob):
                    continue
                if item["url"] in seen:
                    continue
                seen.add(item["url"])
                rows.append(item)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias de obra y actividad",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y edictos publicados en sede electrónica espublico",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.transp_base}/licencias-urbanisticas"),
                "fecha_concesion": None,
                "tipo": "licencias urbanísticas en exposición",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal transparencia — licencias urbanísticas",
                "url": f"{self.transp_base}/licencias-urbanisticas",
                "source": "ayuntamiento",
                "nota": "Proyectos de actuación y licencias en periodo de exposición pública",
                "origen": "transparencia",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
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
                "nota": "Requiere identificación; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
        ]

    def _is_urban_blob(self, blob: str) -> bool:
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not self._is_urban_blob(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        tipo = row.get("procedimiento") or "licencia"
        if re.search(r"(?i)actuaci[oó]n|enoturismo", blob):
            tipo = "proyecto de actuación"
        elif re.search(r"(?i)licencia urban", blob):
            tipo = "licencia urbanística"
        elif re.search(r"(?i)obra|icio", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "tablon"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not self._is_urban_blob(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row.get("url") or row.get("titulo", "")
        titulo = row["titulo"]
        expte = row.get("expediente")
        if expte and expte not in titulo:
            titulo = f"{titulo} (exp. {expte})"
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": expte,
            "origen": row.get("origen", "web"),
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
        for source in (
            self._collect_board(),
            self._collect_transparencia(),
            self._collect_web_documents(),
        ):
            for item in source:
                rec = self._row_to_licencia(item)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(
                1
                for r in rows
                if r.get("origen") in ("sede_tablon", "sede_tramite", "transparencia")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for source in (
            self._collect_board(),
            self._collect_transparencia(),
            self._collect_web_documents(),
        ):
            for item in source:
                rec = self._row_to_licencia(item)
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

        for source in (
            self._collect_board(),
            self._collect_transparencia(),
            self._collect_web_documents(),
        ):
            for item in source:
                add(self._row_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(
                1 for r in rows if str(r.get("origen", "")).startswith("transparencia")
            ),
            "web": sum(1 for r in rows if r.get("origen") == "web_urbanismo"),
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
