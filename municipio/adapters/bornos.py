from __future__ import annotations

import hashlib
import html as html_module
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

SEDE_BASE = "https://sede.bornos.es"
WEB_BASE = "https://www.bornos.es"
EDICTOS_URL = f"{SEDE_BASE}/edictos/publico?idOrgan=11"
TABLON_URL = f"{SEDE_BASE}/tablon-electronico-de-anuncios-y-edictos"
PBOM_URL = f"{WEB_BASE}/pbom-bornos"
SITUA_PLANEAMIENTO_URL = (
    "https://ws132.juntadeandalucia.es/situadifusion/pages/"
    "planeamientoGeneralCompartir.jsf?"
    "bXVuaWNpcGlvc3NlbGVjY2lvbmFkb3M9MTEwMTAmbXVuaWNpcGlvc1NlbGVjPUJPUk5PUyZ"
    "jb2RpZ29zTXVuaWNpcGlvcz0xMTAxMCZjb2RGaWd1cmE9MjE4Mzkmal9pZDY6al9pZDM1PWpfaWQ2"
    "OmpfaWQzNSZjaGVja0JveFNlbD1hcHJvYmFkbyZjb2RGaWd1cmFCdXM9MjE4MzkmRGF0YVRhYmxlc19"
    "UYWJsZV8wX2xlbmd0aD0xMCZqX2lkNj1qX2lkNiZqYXZheC5mYWNlcy5WaWV3U3RhdGU9al9pZDQm"
    "dGl0dWxvTk5TU1BQPVBsYW5lYW1pZW50byBnZW5lcmFsIGFwcHJvYmFkb2RlIEJPUk5PUyZjb2Rp"
    "Z29zTm9tYnJlc011bmljaXBpb3M9W3siaWQiOiIxMTAxMCIsIm5vbWJyZSI6IkJPUk5PUyJ9XQ=="
)
MUNICIPIO = "Bornos"
ID_PREFIX = "bornos"

DEFAULT_PBOM_PAGES: list[str] = [
    PBOM_URL,
    f"{WEB_BASE}/pbom-bornos/7-memoria",
    f"{WEB_BASE}/pbom-bornos/8-normativa-urbanistica",
    f"{WEB_BASE}/pbom-bornos/6-cartografia",
    f"{WEB_BASE}/pbom-bornos/5-anexos",
    f"{WEB_BASE}/pbom-bornos/9-resumen-ejecutivo",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|punto limpio|calificaci[oó]n.*actividad)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|b[aá]sico)|pbom|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|normativa urban|ordenanza|certificado.*eae|cacoa)",
)
RE_EDICTO_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|concurso-oposici|empleo|nombramiento|padr[oó]n|"
    r"iae|cobranza|subvencion|funcionario|interino|bolsa de trabajo|auxiliar administrativo|"
    r"intervenci[oó]n en el ayuntamiento|activa-t joven|programa activa|feria de bornos|"
    r"certamen de poes[ií]a|jurado|censo electoral|colonia felina|caseta)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PBOM_DOWNLOAD = re.compile(
    r'href="((?:https://www\.bornos\.es)?/pbom-bornos\?download=\d+:[^"]+)"',
    re.I,
)
RE_PBOM_PATH = re.compile(
    r'href="((?:https://www\.bornos\.es)?/pbom-bornos(?:/[^"?]+)?)"',
    re.I,
)
RE_TRAMITE_URBAN = re.compile(
    r"(?i)(declaraci[oó]n responsable.*obra|licencia|obra|urban|actividad econ[oó]mica|apertura)",
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
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pbom" in b or "plan básico" in b or "plan basico" in b:
        return "PBOM"
    if "normativa urban" in b:
        return "normativa urbanística"
    if "memoria" in b:
        return "memoria planeamiento"
    if "cartograf" in b:
        return "cartografía urbanística"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "calificaci" in b and "actividad" in b:
        return "calificación ambiental"
    if "licencia" in b:
        return "licencia publicada"
    if "planeamiento general" in b:
        return "planeamiento"
    return "urbanismo"


class BornosAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay sede ecadiz (EPICSA edictos) + Joomla web (PBOM Phoca Download)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.edictos_url = str(self.config.get("edictos_url") or EDICTOS_URL)
        self.pbom_pages = [str(u) for u in (self.config.get("pbom_pages") or DEFAULT_PBOM_PAGES)]
        self.situa_url = str(self.config.get("situa_planeamiento_url") or SITUA_PLANEAMIENTO_URL)
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-bornos/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        href = unescape(html_module.unescape(href.replace("&amp;", "&")))
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _abs_sede(self, href: str) -> str:
        href = unescape(html_module.unescape(href.replace("&amp;", "&")))
        return urllib.parse.urljoin(f"{self.sede_base}/", href)

    def _collect_edictos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.edictos_url)
        except urllib.error.URLError:
            return []

        parts = re.split(r"publico\.action[^\"]*codigo=(\d{4}-\d+)", html)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for i in range(1, len(parts), 2):
            codigo = parts[i]
            if codigo in seen:
                continue
            seen.add(codigo)

            before = parts[i - 1][-2500:]
            chunk = unescape(re.sub(r"<[^>]+>", " ", before))
            chunk = re.sub(r"\s+", " ", chunk).strip()
            dates = re.findall(r"\d{2}/\d{2}/\d{4}", chunk)
            pub = dates[-2] if len(dates) >= 2 else (dates[-1] if dates else None)
            end = dates[-1] if len(dates) >= 2 else None
            title = chunk
            if end:
                idx = title.rfind(end)
                title = title[idx + len(end) :].strip()
            title = re.sub(r"\s*<a href.*$", "", title).strip()

            rows.append(
                {
                    "codigo": codigo,
                    "titulo": title[:500],
                    "fecha": _parse_fecha_dmy(pub or ""),
                    "url": f"{self.sede_base}/edictos/edicto/publico.action?codigo={codigo}",
                    "blob": f"{title} {codigo}",
                    "origen": "edictos_epicsa",
                }
            )
        return rows

    def _collect_pbom(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(url: str, titulo: str, tipo: str = "PBOM", fecha: str | None = None) -> None:
            abs_url = self._abs_web(url)
            if abs_url in seen_urls:
                return
            seen_urls.add(abs_url)
            rows.append(
                {
                    "url": abs_url,
                    "titulo": titulo[:500],
                    "tipo": tipo,
                    "fecha": fecha,
                    "blob": f"{titulo} PBOM Bornos planeamiento",
                    "origen": "web_pbom",
                }
            )

        add(PBOM_URL, "Plan Básico de Ordenación Municipal (PBOM) — aprobación inicial", "PBOM", "2025-11-04")
        add(self.situa_url, "Planeamiento general aprobado — SituaDIFusión Junta de Andalucía", "planeamiento")

        for page_url in self.pbom_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            page_plain = _strip_html(html)
            page_title = page_plain[:120] if page_plain else page_url

            for m in RE_PBOM_DOWNLOAD.finditer(html):
                href = m.group(1)
                slug_part = href.split("download=")[-1] if "download=" in href else href
                titulo = slug_part.replace("-", " ").replace(":", " ").strip()
                add(href, f"PBOM Bornos — {titulo}", _proyecto_tipo(titulo))

            if page_url not in seen_urls and "/pbom-bornos/" in page_url:
                section = page_url.rsplit("/", 1)[-1].replace("-", " ")
                add(page_url, f"PBOM Bornos — {section}", _proyecto_tipo(section))

        return rows

    def _collect_tramites_urbanismo(self) -> list[dict[str, Any]]:
        url = f"{self.sede_base}/tramites-disponibles"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []

        text = html_module.unescape(html)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in re.finditer(
            r"detalle-tramite\?tramite=(\d+)[^\"]*\"[^>]*>([^<]+)",
            text,
            re.I,
        ):
            tramite_id, label = m.group(1), _strip_html(m.group(2))
            if not RE_TRAMITE_URBAN.search(label):
                continue
            tramite_url = f"{self.sede_base}/group/bornos/detalle-tramite?tramite={tramite_id}"
            if tramite_url in seen:
                continue
            seen.add(tramite_url)
            rows.append(
                {
                    "url": tramite_url,
                    "titulo": label[:500],
                    "tipo": "trámite urbanismo",
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", EDICTOS_URL),
                "fecha_concesion": None,
                "tipo": "tablón edictos urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico de anuncios y edictos (EPICSA)",
                "url": EDICTOS_URL,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en sede Liferay ecadiz (idOrgan=11)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", TABLON_URL),
                "fecha_concesion": None,
                "tipo": "tablón electrónico municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico de anuncios y edictos",
                "url": TABLON_URL,
                "source": "ayuntamiento",
                "nota": "Portal Liferay redirige al tablón EPICSA",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/tramites-disponibles"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites disponibles — declaración responsable obras",
                "url": f"{self.sede_base}/tramites-disponibles",
                "source": "ayuntamiento",
                "nota": "Incluye declaración responsable ejecución de obras (tramite 5540)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/catalogo-de-procedimientos"),
                "fecha_concesion": None,
                "tipo": "catálogo de procedimientos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de procedimientos administrativos",
                "url": f"{self.sede_base}/catalogo-de-procedimientos",
                "source": "ayuntamiento",
                "nota": "Sin listado histórico de licencias concedidas",
                "origen": "sede_tramite",
            },
        ]

    def _edicto_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_EDICTO_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _edicto_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._edicto_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        tipo = "licencia de actividad"
        if re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("codigo") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("codigo"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "edictos",
        }

    def _edicto_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._edicto_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("codigo") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("codigo"),
            "origen": "edictos",
        }

    def _pbom_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row.get("blob") or ""),
            "tipo": row.get("tipo") or _proyecto_tipo(row.get("blob") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "web_pbom",
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": row.get("tipo") or "trámite urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen") or "sede_tramite",
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

        for item in self._collect_tramites_urbanismo():
            rec = self._tramite_to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_edictos():
            rec = self._edicto_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "edictos": sum(1 for r in rows if r.get("origen") == "edictos"),
            "info": sum(
                1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tramites_urbanismo():
            existing[self._tramite_to_licencia(item)["id"]] = self._tramite_to_licencia(item)
        for item in self._collect_edictos():
            rec = self._edicto_to_licencia(item)
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

        for item in self._collect_pbom():
            add(self._pbom_to_proyecto(item))

        for item in self._collect_edictos():
            add(self._edicto_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pbom": sum(1 for r in rows if r.get("origen") == "web_pbom"),
            "edictos": sum(1 for r in rows if r.get("origen") == "edictos"),
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
