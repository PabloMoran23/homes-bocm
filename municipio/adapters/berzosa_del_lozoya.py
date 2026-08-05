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

WP_BASE = "https://www.berzosadelozoya.com"
SEDE_EADMIN = "https://sedeberzosadellozoya.eadministracion.es"
TABLON_URL = f"{SEDE_EADMIN}/PortalCiudadano/Tablon/wfrTablon.aspx"
TRANSPARENCIA_URL = "https://transparenciaberzosadellozoya.eadministracion.es/portal"
DESCARGAS_PAGE = f"{WP_BASE}/ayuntamiento/descarga-de-documentos/"
MUNICIPIO = "Berzosa del Lozoya"
ID_PREFIX = "berzosa-del-lozoya"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|titulo habilitante)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"ordenanza.*urban|servicios urban|limpieza de solares|residuos.*construc|"
    r"informaci[oó]n p[uú]blica|expediente|bocm|suelo|parcela|"
    r"ocupaci[oó]n.*v[ií]a p[uú]blica|terrenos.*naturaleza urbana)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(empadronamiento|certificado|bonificaci[oó]n ibi|fianza.*residuos|"
    r"recaudaci[oó]n|domiciliaci[oó]n|veh[ií]culos|animales|ap[ií]colas|"
    r"uniones civiles|carruajes|cementerio|front[oó]n|talleres|cine)",
)
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_LINK_LABEL = re.compile(
    r'href="([^"]+\.pdf[^"]*)"[^>]*>([^<]{3,})</a>',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "ordenanza" in n and "urban" in n:
        return "ordenanza urbanística"
    if "limpieza" in n and "solar" in n:
        return "ordenanza urbanística"
    if "residuos" in n and "construc" in n:
        return "normativa construcción"
    if "ocupaci" in n and "vía" in n:
        return "ordenanza urbanística"
    if "terrenos" in n and "urbana" in n:
        return "ordenanza fiscal urbanística"
    if "servicios urban" in n:
        return "ordenanza fiscal urbanística"
    return "normativa urbanística"


def _licencia_tipo(title: str) -> str:
    n = title.lower()
    if "obra mayor" in n:
        return "licencia de obra mayor"
    if "actividad" in n:
        return "licencia de actividad"
    if "comunicaci" in n and "previa" in n:
        return "comunicación previa"
    if "declaraci" in n and "responsable" in n:
        return "declaración responsable"
    return "trámite licencia urbanística"


class BerzosaDelLozoyaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (formularios/ordenanzas) + sede eAdmin Maggioli (SPA, sin listado scrapeable)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_eadmin = str(self.config.get("sede_eadmin") or SEDE_EADMIN).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.transparencia_url = str(self.config.get("transparencia_url") or TRANSPARENCIA_URL)
        self.descargas_page = str(self.config.get("descargas_page") or DESCARGAS_PAGE)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60, context=self._ssl_ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _parse_descargas_page(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.descargas_page)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_LINK_LABEL.finditer(html):
            pdf_url = self._abs_wp(m.group(1))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            label = _strip_html(m.group(2)) or Path(urllib.parse.urlparse(pdf_url).path).name
            rows.append(
                {
                    "titulo": label[:500],
                    "fecha": _fecha_from_url(pdf_url),
                    "url": self.descargas_page,
                    "pdf_url": pdf_url,
                    "origen": "wp_descargas",
                }
            )
        return rows

    def _collect_wp_media(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            try:
                data = self._fetch_json(
                    f"{self.wp_base}/wp-json/wp/v2/media?per_page=100&page={page}"
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(data, list) or not data:
                break
            for item in data:
                if not isinstance(item, dict):
                    continue
                title = str((item.get("title") or {}).get("rendered") or "").strip()
                pdf_url = str(item.get("source_url") or "")
                if not pdf_url.lower().endswith(".pdf"):
                    continue
                blob = f"{title} {pdf_url}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                if RE_EXCLUDE.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _fecha_from_url(pdf_url),
                        "url": self.descargas_page,
                        "pdf_url": pdf_url,
                        "origen": "wp_media",
                    }
                )
            page += 1
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.sede_eadmin),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica eAdmin — trámites urbanísticos",
                "url": self.sede_eadmin,
                "source": "ayuntamiento",
                "nota": "Presentación electrónica de solicitudes (Maggioli SPA)",
                "origen": "sede_eadmin",
            },
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y exposiciones públicas (eAdmin, requiere JS)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.transparencia_url),
                "fecha_concesion": None,
                "tipo": "portal transparencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal de transparencia municipal",
                "url": self.transparencia_url,
                "source": "ayuntamiento",
                "nota": "Transparencia eAdmin (Maggioli)",
                "origen": "transparencia",
            },
            {
                "id": _stable_id("lic", self.descargas_page),
                "fecha_concesion": None,
                "tipo": "formularios urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Descarga de documentos — formularios urbanísticos",
                "url": self.descargas_page,
                "source": "ayuntamiento",
                "nota": "Formularios de licencias y declaraciones responsables",
                "origen": "wp_tramite",
            },
        ]

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("pdf_url") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": _licencia_tipo(row.get("titulo") or ""),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row.get("titulo") or ""),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
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

    def _collect_source_rows(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for rec in self._parse_descargas_page():
            key = rec.get("pdf_url") or rec["url"]
            by_key[key] = rec
        for rec in self._collect_wp_media():
            key = rec.get("pdf_url") or rec["url"]
            by_key.setdefault(key, rec)
        return list(by_key.values())

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_source_rows():
            rec = self._row_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": sum(1 for r in rows if str(r.get("origen", "")).startswith(("sede_", "transparencia", "wp_tramite"))),
            "forms": sum(1 for r in rows if r.get("origen") in ("wp_descargas", "wp_media")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_source_rows():
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
        for item in self._collect_source_rows():
            rec = self._row_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_descargas": sum(1 for r in rows if r.get("origen") == "wp_descargas"),
            "wp_media": sum(1 for r in rows if r.get("origen") == "wp_media"),
            "with_geometry": 0,
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
