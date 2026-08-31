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

WP_BASE = "https://navarredondaysanmames.org"
SEDE_EADMIN = "https://sedenavarredondaysanmames.eadministracion.es"
TABLON_URL = f"{SEDE_EADMIN}/PortalCiudadano/Tablon/wfrTablon.aspx"
DESCARGAS_PAGE = f"{WP_BASE}/descarga-de-documentos/"
URBANISMO_URL = f"{WP_BASE}/urbanismo/"
MUNICIPIO = "Navarredonda y San Mamés"
ID_PREFIX = "navarredonda-y-san-mames"

DEFAULT_STATIC_PROYECTOS: list[dict[str, str]] = [
    {
        "url": f"{WP_BASE}/pgou-plan-general-de-ordenacion-urbanistica-de-navarredonda-y-san-mames/",
        "titulo": "PGOU — Plan General de Ordenación Urbanística de Navarredonda y San Mamés",
        "fecha": "2025-03-17",
        "tipo": "PGOU",
        "origen": "pgou_seed",
    },
    {
        "url": f"{WP_BASE}/avance-del-plan-general-de-ordenacion-urbana-de-navarredonda-y-san-mames/",
        "titulo": "Avance del Plan General de Ordenación Urbana — exposición pública",
        "fecha": "2025-03-14",
        "tipo": "información pública",
        "origen": "pgou_seed",
    },
    {
        "url": f"{WP_BASE}/informacion-del-pgou-dudas-y-consultas/",
        "titulo": "Información del PGOU — dudas y consultas",
        "fecha": "2025-04-02",
        "tipo": "información pública",
        "origen": "pgou_seed",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|instancia general|tasa.*obra|druo)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|bocm|ordenanza.*urban|servicios urban|"
    r"licitaci[oó]n.*obra|obra (?:mayor|urbaniz)|urbanizaci[oó]n|"
    r"tramitaci[oó]n licencia|licencia (?:de )?actividad)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(empadronamiento|bonificaci[oó]n ibi|recaudaci[oó]n|domiciliaci[oó]n|"
    r"veh[ií]culos|animales|cementerio|cine|ola de calor|inclemencias|incendio|"
    r"inuncam|meteorol|nieve|tormenta|lluvia|fr[ií]o|ozono|ganader|ayudas a ganader|"
    r"transporte (?:p[uú]blico|urbano)|l[ií]neas urbanas|plantotum|cuidame|imidra|"
    r"juez de paz|perros|m[eé]todos de pago|plantones hort|influencia aviar|"
    r"leña|fiestas|programa de apoyo a mujeres|bandomovil|ibi urbana)",
)
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_LINK_LABEL = re.compile(
    r'href=["\']([^"\']+\.pdf[^"\']*)["\'][^>]*>([^<]{3,})</a>',
    re.I,
)
RE_BOCM_FILE = re.compile(r"BOCM-(\d{8})", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_BOCM_FILE.search(url or "")
    if m:
        raw = m.group(1)
        try:
            return datetime(int(raw[:4]), int(raw[4:6]), int(raw[6:8])).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "avance" in n and "plan" in n:
        return "información pública"
    if "licitaci" in n or "obra mayor" in n:
        return "licitación obra"
    if "urbanizaci" in n:
        return "proyecto urbanístico"
    if "licencia" in n and "actividad" in n:
        return "licencia de actividad"
    if "bocm" in n:
        return "publicación BOCM"
    return "urbanismo"


def _licencia_tipo(title: str) -> str:
    n = title.lower()
    if "obra mayor" in n:
        return "licencia de obra mayor"
    if "actividad" in n:
        return "licencia de actividad"
    if "instancia general" in n:
        return "instancia general"
    if "druo" in n or "declaraci" in n:
        return "declaración responsable"
    return "trámite licencia urbanística"


class NavarredondaYSanMamesAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (Avada) + sede eAdmin Maggioli (SPA, sin listado scrapeable)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_eadmin = str(self.config.get("sede_eadmin") or SEDE_EADMIN).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.descargas_page = str(self.config.get("descargas_page") or DESCARGAS_PAGE)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.static_proyectos = list(self.config.get("static_proyectos") or DEFAULT_STATIC_PROYECTOS)
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

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 12:
            url = (
                f"{self.wp_base}/wp-json/wp/v2/posts"
                f"?per_page=100&page={page}&_fields=id,link,title,date,content"
            )
            try:
                posts = self._fetch_json(url)
            except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(posts, list) or not posts:
                break
            for p in posts:
                if not isinstance(p, dict):
                    continue
                title = str((p.get("title") or {}).get("rendered") or "").strip()
                link = str(p.get("link") or "").strip()
                fecha = _iso_date_wp(str(p.get("date") or ""))
                content = str((p.get("content") or {}).get("rendered") or "")
                blob = f"{title} {content}"
                if RE_EXCLUDE.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                pdfs = [self._abs_wp(m.group(1)) for m in RE_PDF_HREF.finditer(content)]
                if pdfs:
                    for pdf_url in pdfs:
                        rows.append(
                            {
                                "titulo": title[:500],
                                "fecha": fecha or _fecha_from_url(pdf_url),
                                "url": link,
                                "pdf_url": pdf_url,
                                "origen": "wp_post",
                            }
                        )
                else:
                    rows.append(
                        {
                            "titulo": title[:500],
                            "fecha": fecha,
                            "url": link,
                            "origen": "wp_post",
                        }
                    )
            if len(posts) < 100:
                break
            page += 1
        return rows

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in self.static_proyectos:
            rows.append(
                {
                    "titulo": seed["titulo"][:500],
                    "fecha": seed.get("fecha"),
                    "url": seed["url"],
                    "origen": seed.get("origen", "static_seed"),
                    "tipo_hint": seed.get("tipo"),
                }
            )
            try:
                html = self._fetch(seed["url"])
            except urllib.error.URLError:
                continue
            seen: set[str] = set()
            for m in RE_PDF_HREF.finditer(html):
                pdf_url = self._abs_wp(m.group(1))
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                rows.append(
                    {
                        "titulo": f"{seed['titulo']} — {Path(urllib.parse.urlparse(pdf_url).path).name}",
                        "fecha": seed.get("fecha") or _fecha_from_url(pdf_url),
                        "url": seed["url"],
                        "pdf_url": pdf_url,
                        "origen": "wp_seed_pdf",
                    }
                )
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
                "id": _stable_id("lic", self.descargas_page),
                "fecha_concesion": None,
                "tipo": "formularios urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Descarga de documentos — formularios urbanísticos",
                "url": self.descargas_page,
                "source": "ayuntamiento",
                "nota": "Licencia de obras, DRUO e instancia general",
                "origen": "wp_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "urbanismo municipal",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — arquitecto técnico municipal",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Atención presencial viernes 10:00–14:00",
                "origen": "wp_urbanismo",
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
            "tipo": row.get("tipo_hint") or _proyecto_tipo(row.get("titulo") or ""),
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
        for rec in self._collect_static_proyectos():
            key = rec.get("pdf_url") or rec["url"]
            by_key[key] = rec
        for rec in self._parse_descargas_page():
            key = rec.get("pdf_url") or rec["url"]
            by_key.setdefault(key, rec)
        for rec in self._collect_wp_media():
            key = rec.get("pdf_url") or rec["url"]
            by_key.setdefault(key, rec)
        for rec in self._collect_wp_posts():
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
            "info": sum(1 for r in rows if str(r.get("origen", "")).startswith(("sede_", "wp_"))),
            "forms": sum(1 for r in rows if r.get("origen") in ("wp_descargas", "wp_media", "wp_post")),
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
            "wp_posts": sum(1 for r in rows if r.get("origen") in ("wp_post", "wp_seed_pdf")),
            "static": sum(1 for r in rows if str(r.get("origen", "")).startswith(("pgou", "static"))),
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
