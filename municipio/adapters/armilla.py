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

WP_BASE = "https://armilla.es"
SEDE_BASE = "https://sede.armilla.es"
MUNICIPIO = "Armilla"
ID_PREFIX = "armilla"

SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
EDICTOS_URL = f"{SEDE_BASE}/portal/noEstatica.do?opc_id=268&ent_id=1&idioma=1"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/el-ayuntamiento/concejalias/concejalia-de-urbanismo-gobernacion-y-personal/",
    f"{WP_BASE}/administracion-electronica/tramites/ordenanzas/ordenanzas-planeamiento-urbanistico/",
    f"{WP_BASE}/administracion-electronica/tramites/ordenanzas/ordenanzas-planeamiento-urbanistico/seccion-de-instrumentos-de-planeamiento-urbanistico/",
    f"{WP_BASE}/administracion-electronica/tramites/ordenanzas/ordenanzas-planeamiento-urbanistico/seccion-de-convenios-urbanisticos/",
    f"{WP_BASE}/administracion-electronica/tramites/ordenanzas/ordenanzas-planeamiento-urbanistico/bienes-y-espacios-catalogados/",
    f"{WP_BASE}/administracion-electronica/tramites/tramites-y-normativa/licencias-de-obra-y-gestiones-urbanisticas/",
    f"{WP_BASE}/administracion-electronica/tramites/directorio-de-impresos-y-solicitudes/urbanisticos/",
]

PLAN_VIVIENDA_URL = "https://drive.google.com/open?id=10R6GjGSnBxAAN3kTUFx2Hn0_Vrl3LP5d"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|mod_urb)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|innovaci[oó]n|concesi[oó]n demanial|catalogad|vivienda y suelo)",
)
RE_WPDM_DOWNLOAD = re.compile(r'data-downloadurl="([^"]+)"', re.I)
RE_WPDM_TITLE = re.compile(
    r'class="package-title"[^>]*>.*?<a[^>]+href="[^"]+"[^>]*>([^<]+)</a>',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EDICTO_ROW = re.compile(
    r"(?i)(licencia|licencias|obra|urban|planeam|actividad|edicto|anuncio|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable)",
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


def _slug_to_title(slug: str) -> str:
    t = unescape(slug.replace("-", " ").replace("_", " "))
    return re.sub(r"\s+", " ", t).strip().title()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan municipal de vivienda" in b or "vivienda y suelo" in b:
        return "plan vivienda y suelo"
    if "convenio urban" in b:
        return "convenio urbanístico"
    if "estudio de detalle" in b or "estudio detalle" in b:
        return "estudio de detalle"
    if "reparcel" in b:
        return "reparcelación"
    if "innovaci" in b and "planeam" in b:
        return "innovación planeamiento"
    if "plan especial" in b:
        return "plan especial"
    if "concesi" in b and "demanial" in b:
        return "concesión demanial"
    if "catalogad" in b:
        return "bienes catalogados"
    if "licencia" in b:
        return "licencia publicada"
    return "planeamiento"


class ArmillaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (registro IOU wpdm) + sede eAdmin legacy (edictos) + SITUADIFUSION PGOU."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.edictos_url = str(self.config.get("edictos_url") or EDICTOS_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.situa_url = str(self.config.get("situa_url") or SITUA_SEARCH)
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
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "Mozilla/5.0 poc-bocm-armilla/1.0",
                ),
            },
        )
        with self._opener.open(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_wp(self, href: str) -> str:
        href = unescape(html_module.unescape(href.replace("&amp;", "&").replace("&#038;", "&")))
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _collect_wpdm_downloads(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            titles = [t.strip() for t in RE_WPDM_TITLE.findall(html) if "@" not in t]
            downloads = RE_WPDM_DOWNLOAD.findall(html)

            for idx, raw_url in enumerate(downloads):
                url = self._abs_wp(raw_url)
                if url in seen:
                    continue
                seen.add(url)

                slug = ""
                if "/download/" in url:
                    slug = url.split("/download/")[1].split("/?")[0].split("?")[0]
                title = titles[idx] if idx < len(titles) else _slug_to_title(slug)
                blob = f"{title} {slug} {url}"

                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if "urbanistic" not in page_url and "planeamiento" not in page_url:
                        continue

                rows.append(
                    {
                        "titulo": title[:500],
                        "url": url,
                        "fecha": _fecha_from_blob(blob),
                        "blob": blob,
                        "tipo": _proyecto_tipo(blob),
                        "origen": "wordpress_wpdm",
                    }
                )

            for m in re.finditer(
                r'href="(https://drive\.google\.com/[^"]+)"[^>]*>([^<]{5,200})',
                html,
                re.I,
            ):
                gurl, gtitle = m.group(1), _strip_html(m.group(2))
                if gurl in seen:
                    continue
                if not RE_PROYECTO.search(f"{gtitle} {gurl}"):
                    continue
                seen.add(gurl)
                rows.append(
                    {
                        "titulo": gtitle[:500],
                        "url": gurl,
                        "fecha": None,
                        "blob": f"{gtitle} {gurl}",
                        "tipo": _proyecto_tipo(gtitle),
                        "origen": "google_drive",
                    }
                )

        return rows

    def _collect_situa_pgou(self) -> dict[str, Any]:
        return {
            "titulo": "PGOU Armilla — consulta SITUADIFUSION (Junta de Andalucía)",
            "url": self.situa_url,
            "fecha": None,
            "blob": f"PGOU Armilla planeamiento general {self.situa_url}",
            "tipo": "PGOU",
            "origen": "situa",
        }

    def _collect_edictos_legacy(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.edictos_url)
        except urllib.error.URLError:
            return []

        if len(html) < 500 or "503" in html[:200]:
            return []

        plain = _strip_html(html)
        if not plain or len(plain) < 80:
            return []

        rows: list[dict[str, Any]] = []
        for block in re.split(r"(?i)(?=anuncio|edicto|licencia)", plain):
            if not RE_EDICTO_ROW.search(block):
                continue
            if not RE_LICENCIA.search(block) and not RE_PROYECTO.search(block):
                continue
            title = block[:500].strip()
            if len(title) < 15:
                continue
            rows.append(
                {
                    "titulo": title,
                    "fecha": _fecha_from_blob(block),
                    "url": self.edictos_url,
                    "blob": block,
                    "origen": "sede_edictos",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        licencias_url = (
            f"{self.wp_base}/administracion-electronica/tramites/"
            "tramites-y-normativa/licencias-de-obra-y-gestiones-urbanisticas/"
        )
        impresos_url = (
            f"{self.wp_base}/administracion-electronica/tramites/"
            "directorio-de-impresos-y-solicitudes/urbanisticos/"
        )
        return [
            {
                "id": _stable_id("lic", self.edictos_url),
                "fecha_concesion": None,
                "tipo": "tablón edictos y anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Edictos y anuncios municipales (sede electrónica)",
                "url": self.edictos_url,
                "source": "ayuntamiento",
                "nota": "Tablón legacy eAdmin en sede.armilla.es (opc_id=268)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", licencias_url),
                "fecha_concesion": None,
                "tipo": "trámites licencias de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias de obra y gestiones urbanísticas — impresos",
                "url": licencias_url,
                "source": "ayuntamiento",
                "nota": "Formularios mod_urb1–6; sin listado histórico de concesiones",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", impresos_url),
                "fecha_concesion": None,
                "tipo": "impresos urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Directorio de impresos urbanísticos",
                "url": impresos_url,
                "source": "ayuntamiento",
                "nota": "Solicitudes de licencias, ocupación vía pública, etc.",
                "origen": "web_tramite",
            },
        ]

    def _wpdm_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row.get("blob") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "wordpress_wpdm"),
        }

    def _edicto_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["titulo"][:120]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "edicto / licencia publicada",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_edictos",
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
        for item in self._collect_edictos_legacy():
            rec = self._edicto_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "web_tramite")),
            "edictos": sum(1 for r in rows if r.get("origen") == "sede_edictos"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_edictos_legacy():
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

        add(self._wpdm_to_proyecto(self._collect_situa_pgou()))
        for item in self._collect_wpdm_downloads():
            add(self._wpdm_to_proyecto(item))

        if not any(r.get("url") == PLAN_VIVIENDA_URL for r in rows):
            add(
                self._wpdm_to_proyecto(
                    {
                        "titulo": "Plan Municipal de Vivienda y Suelo de Armilla",
                        "url": PLAN_VIVIENDA_URL,
                        "fecha": None,
                        "blob": "Plan Municipal de Vivienda y Suelo",
                        "tipo": "plan vivienda y suelo",
                        "origen": "google_drive",
                    }
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
            "wordpress_wpdm": sum(1 for r in rows if r.get("origen") == "wordpress_wpdm"),
            "google_drive": sum(1 for r in rows if r.get("origen") == "google_drive"),
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
