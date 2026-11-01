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

LIFERAY_BASE = "https://www.huesca.es"
SEDE_BASE = "https://sedeelectronica.huesca.es/eAdmin"
TABLON_URL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios&tipoTablon=1"
CATALOGO_URBANISMO = (
    f"{LIFERAY_BASE}/ayuntamiento/tramites-y-gestiones/catalogo-de-tramites/urbanismo"
)
MUNICIPIO = "Huesca"
ID_PREFIX = "huesca"
WAYBACK_SNAPSHOT = "20250422193846"

DEFAULT_SEED_PAGES: list[str] = [
    f"{LIFERAY_BASE}/areas/urbanismo/inicio",
    f"{LIFERAY_BASE}/areas/urbanismo/planeamiento-urbanistico",
    (
        f"{LIFERAY_BASE}/areas/urbanismo/planeamiento-urbanistico/"
        "modificaciones-aisladas-al-texto-refundido-del-pgou"
    ),
    (
        f"{LIFERAY_BASE}/areas/urbanismo/planeamiento-urbanistico/"
        "disposiciones-sectoriales-con-incidencias-en-el-planeamiento"
    ),
    f"{LIFERAY_BASE}/areas/urbanismo/planeamiento-urbanistico/plan-general-de-ordenacion-urbana",
    f"{LIFERAY_BASE}/areas/urbanismo/geoinfohuesca",
    CATALOGO_URBANISMO,
]

RE_TABLON_ROW = re.compile(
    r"verAnuncio(?:&amp;|&)id=([A-F0-9]+).*?"
    r"</td>\s*<td[^>]*>\s*(.*?)\s*<br>.*?"
    r"Periodo:</span>\s*([^<]+)</td>",
    re.I | re.S,
)
RE_DOC_TOKEN = re.compile(r"abrirOriginal\('([^']+)'\)")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| ambiental)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de (?:obra|actividad)|"
    r"obra (?:mayor|menor)|t[ií]tulo habilitante|licencia de funcionamiento)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|modificaci[oó]n|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|reparcel|reurbaniz|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|disposici[oó]n sectorial|arru|"
    r"licitaci[oó]n.*(?:obra|proyecto)|actuaci[oó]n urban)",
)
RE_SKIP = re.compile(
    r"(?i)(proceso selectivo|empleo p[uú]blico|bolsa de|subvenci[oó]n deportiv|"
    r"presupuesto|tribut|empadron|punto limpio|reglamento de organizaci[oó]n|"
    r"biblioteca|halloween|fiestas|cita previa|zona de bajas emisiones)",
)
RE_LIFERAY_DOC = re.compile(r'href="(/documents/[^"]+)"', re.I)
RE_LIFERAY_W = re.compile(r'href="(/w/[^"?]+)"', re.I)
RE_TRAMITE_LINK = re.compile(
    r'href="(https://www\.huesca\.es/-/[^"]+|/-/[^"]+)"[^>]*>([^<]{5,200})</a>',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "convenio" in n or "reurbaniz" in n:
        return "reurbanización / convenio"
    if "disposici" in n and "sectorial" in n:
        return "disposición sectorial"
    if "arru" in n:
        return "ARRU"
    if "licitaci" in n:
        return "licitación obra"
    if "licencia ambiental" in n:
        return "licencia ambiental"
    return "urbanismo"


def _pdf_url(sede_base: str, token: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(token, safe='')}&tipo=doc&mode=ori"
    )


def _wayback_url(url: str, snapshot: str) -> str:
    return f"https://web.archive.org/web/{snapshot}/{url}"


class HuescaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay huesca.es + sede eAdmin tablón (Wayback fallback) + catálogo trámites."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or LIFERAY_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.liferay_base = str(self.config.get("liferay_base") or LIFERAY_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_urbanismo_url") or CATALOGO_URBANISMO)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wayback_snapshot = str(self.config.get("wayback_snapshot") or WAYBACK_SNAPSHOT)
        self.wayback_fallback = bool(self.config.get("wayback_fallback", True))
        self.sede_timeout = int(self.config.get("sede_fetch_timeout_s", 20))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(
        self,
        url: str,
        *,
        sede: bool = False,
        timeout: int | None = None,
    ) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-huesca/1.0"),
                "Accept-Language": "es;q=0.9",
            },
        )
        ctx = self._ssl_ctx if sede or "sedeelectronica.huesca.es" in url else None
        with urllib.request.urlopen(req, timeout=timeout or (self.sede_timeout if sede else 60), context=ctx) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            if sede or "Tablon.do" in url:
                charset = "iso-8859-1"
            return raw.decode(charset, errors="replace")

    def _fetch_sede_html(self, url: str) -> str:
        try:
            return self._fetch(url, sede=True)
        except (urllib.error.URLError, TimeoutError, OSError):
            if not self.wayback_fallback:
                raise
            return self._fetch(_wayback_url(url, self.wayback_snapshot), sede=False, timeout=90)

    def _abs_liferay(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.liferay_base}/", href))

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            rows.append(obj)
                    except json.JSONDecodeError:
                        continue
        return rows

    def _parse_tablon(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, period_raw = m.groups()
            title = _clean_title(_strip_html(title_raw))
            if not title or RE_SKIP.search(title):
                continue
            row_html = m.group(0)
            doc_m = RE_DOC_TOKEN.search(row_html)
            period_m = RE_PERIOD.search(period_raw or "")
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec: dict[str, Any] = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha": fecha_ini,
                "url": detail_url,
                "origen": "tablon_eadmin",
                "blob": title,
            }
            if doc_m:
                rec["pdf_url"] = _pdf_url(self.sede_base, doc_m.group(1))
            rows.append(rec)
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch_sede_html(self.tablon_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        return self._parse_tablon(html)

    def _collect_liferay_docs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        urban_doc = re.compile(
            r"(?i)(modificaci|pgou|planeam|urban|memoria|plano|disposici|sectorial|pgou|arru)",
        )
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_LIFERAY_DOC.finditer(html):
                path = unescape(m.group(1))
                if not urban_doc.search(path):
                    continue
                url = self._abs_liferay(path)
                if url in seen:
                    continue
                seen.add(url)
                name = Path(urllib.parse.urlparse(url).path).name.replace("+", " ")
                titulo = _clean_title(name) or url
                rows.append(
                    {
                        "titulo": titulo,
                        "url": url,
                        "fecha": _fecha_from_blob(titulo + " " + url),
                        "origen": "liferay_document",
                        "blob": f"{titulo} {url}",
                    }
                )
            for m in RE_LIFERAY_W.finditer(html):
                path = m.group(1)
                url = self._abs_liferay(path)
                if url in seen:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": _clean_title(path.rsplit("/", 1)[-1].replace("-", " ")),
                        "url": url,
                        "fecha": None,
                        "origen": "liferay_news",
                        "blob": url,
                    }
                )
        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, label in RE_TRAMITE_LINK.findall(html):
            url = self._abs_liferay(href)
            if url in seen:
                continue
            seen.add(url)
            titulo = _clean_title(label)
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "origen": "catalogo_tramite",
                    "blob": titulo,
                }
            )
        return rows

    def _licencia_info_rows(self) -> list[dict[str, Any]]:
        info = [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios (eAdmin)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Huesca",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y edictos (licencias e IP) publicados en sede",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.catalogo_url),
                "fecha_concesion": None,
                "tipo": "catálogo de trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — Urbanismo",
                "url": self.catalogo_url,
                "source": "ayuntamiento",
                "origen": "catalogo",
            },
        ]
        for rec in self._collect_tramites():
            blob = rec.get("blob") or rec.get("titulo") or ""
            if not RE_LICENCIA.search(blob):
                continue
            url = str(rec.get("url") or self.catalogo_url)
            info.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": _clean_title(rec.get("titulo") or "trámite licencia")[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": rec.get("titulo"),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": rec.get("origen"),
                }
            )
        return info

    def _tablon_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for rec in self._collect_tablon():
            blob = rec.get("blob") or rec.get("titulo") or ""
            if not RE_LICENCIA.search(blob):
                continue
            url = str(rec.get("url") or self.tablon_url)
            rows.append(
                {
                    "id": _stable_id("lic", rec.get("ann_id") or url),
                    "fecha_concesion": rec.get("fecha"),
                    "tipo": "anuncio tablón",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": rec.get("titulo"),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tablon_eadmin",
                }
            )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        by_id: dict[str, dict[str, Any]] = {}
        for row in self._licencia_info_rows() + self._tablon_licencias():
            by_id[row["id"]] = row
        rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_eadmin"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": after},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {**result, "delta": after - before}

    def _build_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add_proyecto(
            titulo: str,
            url: str,
            fecha: str | None,
            origen: str,
            blob: str,
        ) -> None:
            if not titulo or not url:
                return
            if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
                return
            key = url
            if key in seen:
                return
            seen.add(key)
            rows.append(
                {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(blob),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": origen,
                }
            )

        for rec in self._collect_liferay_docs():
            blob = rec.get("blob") or rec.get("titulo") or ""
            if not RE_PROYECTO.search(blob) and rec.get("origen") != "liferay_document":
                continue
            add_proyecto(
                str(rec.get("titulo") or ""),
                str(rec.get("url") or ""),
                rec.get("fecha"),
                str(rec.get("origen") or "liferay"),
                blob,
            )

        for rec in self._collect_tablon():
            blob = rec.get("blob") or rec.get("titulo") or ""
            if not RE_PROYECTO.search(blob):
                continue
            url = str(rec.get("url") or self.tablon_url)
            add_proyecto(
                str(rec.get("titulo") or ""),
                url,
                rec.get("fecha"),
                "tablon_eadmin",
                blob,
            )

        for rec in self._collect_tramites():
            blob = rec.get("blob") or ""
            if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if not RE_PROYECTO.search(blob):
                continue
            add_proyecto(
                str(rec.get("titulo") or ""),
                str(rec.get("url") or ""),
                None,
                "catalogo_tramite",
                blob,
            )

        if not rows:
            add_proyecto(
                "Área de Urbanismo — planeamiento y documentación",
                f"{self.liferay_base}/areas/urbanismo/planeamiento-urbanistico",
                None,
                "semilla",
                "planeamiento urbanistico huesca",
            )
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._build_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "liferay": sum(1 for r in rows if str(r.get("origen", "")).startswith("liferay")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_eadmin"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": after},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {**result, "delta": after - before}
