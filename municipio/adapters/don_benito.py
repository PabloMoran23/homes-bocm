from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.donbenito.es"
SEDE_BASE = "https://sede.donbenito.es"
MUNICIPIO = "Don Benito"
ID_PREFIX = "dbenito"

DEFAULT_SEED_PAGES: list[str] = [
    f"{SEDE_BASE}/publico/tablon",
    f"{SEDE_BASE}/publico/edictos",
    f"{SEDE_BASE}/publico/procedimientos",
    f"{SEDE_BASE}/publico/territorio/informeurbanistico",
    f"{SEDE_BASE}/publico/mapa",
    f"{WEB_BASE}/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|licencia apertura|segregaci[oó]n|parcelaci[oó]n|vado|"
    r"primera ocupaci[oó]n|legalizaci[oó]n de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|pou|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n.*(?:pgou|pgom|plan)|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|planimetr|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza.*urban|rectificaci[oó]n|exposici[oó]n p[uú]blica|"
    r"calificaci[oó]n|supletorio|actuaci[oó]n en medio urbano|cementerio|nichos|"
    r"informe urban|territorio urban)",
)
RE_NOISE = re.compile(
    r"(?i)(modificaci[oó]n de cr[eé]dito|modificaci[oó]n presupuestaria|lista cobratoria|"
    r"impuesto de actividades|iae 20\d\d|proceso selectivo|polic[ií]a local|padr[oó]n de habitantes|"
    r"precio p[uú]blico|tasa por el servicio|fusión.*villanueva|moci[oó]n.*fusión|"
    r"subvenci[oó]n deportiv|bando pam|riesgo de inundaciones)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EDICTO_LINK = re.compile(r'href="(?:https?://[^"]+)?/publico/edictos/(\d+)"', re.I)
RE_EDICTO_EXPD = re.compile(
    r"N[uú]mero de expediente:\s*<[^>]*>(\d+)",
    re.I,
)
RE_PROCEDENCIA = re.compile(
    r"Procedencia:</strong>\s*<[^>]*>([^<]+)",
    re.I,
)
RE_FECHA_PUB = re.compile(
    r"Fecha de publicaci[oó]n:\s*[^<]*</[^>]+>\s*([^<\n]+)",
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="([^"]+\.pdf[^"]*)"',
    re.I,
)
RE_ORDENANZA_URBAN = re.compile(
    r"(?i)(ordenanza.*(?:urban|planeam|suelo|edificaci|circulaci|tr[aá]fico)|"
    r"plan (?:general|parcial|especial)|pgou|pgom)",
)
RE_ORDENANZA_EXCLUDE = re.compile(
    r"(?i)(ordenanza fiscal|tasa por|precio p[uú]blico|reglamento.*escuela|"
    r"consejo local de infancia|ayuda a domicilio|estaciones de recarga|"
    r"impuesto sobre construcciones|seguridad y convivencia)",
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
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgom" in b or "plan general" in b:
        return "PGOM"
    if "pgou" in b:
        return "PGOU"
    if "plan parcial" in b:
        return "plan parcial"
    if "exposici" in b and "p" in b and "blica" in b:
        return "exposición pública"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b:
        return "ordenanza"
    if "informe urban" in b or "informeurbanistico" in b:
        return "información urbanística"
    if "licencia" in b:
        return "licencia publicada"
    if "proyecto" in b:
        return "proyecto"
    return "urbanismo"


class DonBenitoAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede electrónica Galileo GIYS (edictos RSS/HTML, trámites urbanismo, informe urbanístico)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.edictos_rss = str(
            self.config.get("edictos_rss") or f"{self.sede_base}/publico/sindicacion/edictos/RSS"
        )
        self.ordenanzas_rss = str(
            self.config.get("ordenanzas_rss") or f"{self.sede_base}/publico/sindicacion/ordenanzas/RSS"
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-don-benito/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or self.sede_base, href))

    def _parse_rss_items(self, xml: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return rows
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            date_el = item.find("pubDate")
            if title_el is None or link_el is None:
                continue
            title = (title_el.text or "").strip()
            url = (link_el.text or "").strip().replace("//publico", "/publico")
            desc = _strip_html(desc_el.text if desc_el is not None else "")
            blob = f"{title} {desc}"
            fecha = None
            if date_el is not None and date_el.text:
                try:
                    fecha = datetime.strptime(
                        date_el.text.strip()[:25].replace("Z", "+0000"),
                        "%a, %d %b %Y %H:%M:%S %z",
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    fecha = _fecha_from_blob(date_el.text)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": url,
                    "blob": blob,
                }
            )
        return rows

    def _enrich_edicto(self, url: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return out
        m = RE_EDICTO_EXPD.search(html)
        if m:
            out["expte"] = m.group(1)
        m = RE_PROCEDENCIA.search(html)
        if m:
            out["procedencia"] = _strip_html(m.group(1))
        m = RE_FECHA_PUB.search(html)
        if m:
            out["fecha"] = _fecha_from_blob(m.group(1))
        pdfs = []
        for pm in RE_PDF_HREF.finditer(html):
            pdf = self._abs_url(pm.group(1), url)
            if pdf not in pdfs:
                pdfs.append(pdf)
        if pdfs:
            out["pdf_urls"] = pdfs
        resumen = re.search(
            r"Resumen:</h4>\s*<[^>]+>\s*([^<]+)",
            html,
            re.I,
        )
        if resumen:
            out["resumen"] = _strip_html(resumen.group(1))
        return out

    def _collect_edictos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        try:
            xml = self._fetch(self.edictos_rss)
            for row in self._parse_rss_items(xml):
                row["origen"] = "sede_edictos_rss"
                rows.append(row)
                seen_urls.add(row["url"])
        except urllib.error.URLError:
            pass

        for page in (f"{self.sede_base}/publico/tablon", f"{self.sede_base}/publico/edictos"):
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                continue
            for edicto_id in RE_EDICTO_LINK.findall(html):
                url = f"{self.sede_base}/publico/edictos/{edicto_id}"
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                rows.append(
                    {
                        "titulo": f"Edicto {edicto_id}",
                        "fecha": None,
                        "url": url,
                        "blob": f"edicto {edicto_id}",
                        "origen": "sede_tablon_html",
                    }
                )

        for row in rows:
            if not row.get("titulo") or row["titulo"].startswith("Edicto "):
                detail = self._enrich_edicto(row["url"])
                if detail.get("resumen"):
                    row["titulo"] = detail["resumen"][:500]
                    row["blob"] = f"{row['titulo']} {detail.get('procedencia') or ''}"
                if detail.get("fecha"):
                    row["fecha"] = detail["fecha"]
                if detail.get("expte"):
                    row["expte"] = detail["expte"]
                if detail.get("procedencia"):
                    row["procedencia"] = detail["procedencia"]
                if detail.get("pdf_urls"):
                    row["pdf_urls"] = detail["pdf_urls"]
        return rows

    def _collect_ordenanzas(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            xml = self._fetch(self.ordenanzas_rss)
        except urllib.error.URLError:
            return rows
        for row in self._parse_rss_items(xml):
            blob = row["blob"]
            if RE_ORDENANZA_EXCLUDE.search(blob) or RE_NOISE.search(blob):
                continue
            if not RE_ORDENANZA_URBAN.search(blob):
                continue
            row["origen"] = "sede_ordenanzas_rss"
            rows.append(row)
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<title>\s*([^<]+)", html, re.I)
            title = _strip_html(title_m.group(1) if title_m else page_url)
            title = re.sub(r"\s*[-|].*Sede.*$", "", title, flags=re.I).strip()
            blob = f"{title} {page_url}"
            if RE_NOISE.search(blob):
                continue
            if not RE_PROYECTO.search(blob) and "informeurbanistico" not in page_url:
                continue
            rows.append(
                {
                    "titulo": title[:500] or "Información urbanística",
                    "fecha": _fecha_from_blob(html[:3000]),
                    "url": page_url,
                    "blob": blob,
                    "origen": "sede_seed_page",
                }
            )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        info = [
            (
                f"{self.sede_base}/publico/procedimientos",
                "Catálogo de procedimientos — materia URBANISMO (17 trámites)",
            ),
            (
                f"{self.sede_base}/publico/tablon",
                "Tablón de edictos y anuncios",
            ),
            (
                f"{self.sede_base}/publico/territorio/informeurbanistico",
                "Información territorial y urbanística",
            ),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo in info:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                }
            )
        return rows

    def _is_urban(self, blob: str, procedencia: str | None = None) -> bool:
        if RE_NOISE.search(blob):
            return False
        if procedencia and "urbanismo" in procedencia.lower():
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if row.get("origen") == "tramite_informativo":
            return row
        blob = row.get("blob") or ""
        procedencia = row.get("procedencia")
        if not self._is_urban(blob, procedencia):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(row.get("titulo", "")):
            return None
        key = row.get("expte") or (row.get("pdf_urls") or [None])[0] or row.get("url") or row["titulo"]
        return {
            "id": _stable_id("lic", str(key)),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia publicada" if row.get("origen") == "sede_edictos_rss" else "licencia / trámite",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": (row.get("pdf_urls") or [row["url"]])[0],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        procedencia = row.get("procedencia")
        if not self._is_urban(blob, procedencia):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expte") or row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", str(key)),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expte"):
            rec["expediente"] = row["expte"]
        pdfs = row.get("pdf_urls") or []
        if pdfs:
            rec["pdf_url"] = pdfs[0]
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _dedupe(self, rows: list[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            rid = row.get(key)
            if not rid or rid in seen:
                continue
            seen.add(rid)
            out.append(row)
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        raw = self._collect_licencia_tramites()
        for row in self._collect_edictos():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_galileo_giys"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        raw: list[dict[str, Any]] = []
        for row in self._collect_edictos():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        for row in self._collect_ordenanzas():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        for row in self._collect_seed_pages():
            proy = self._to_proyecto(row)
            if proy:
                raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_galileo_giys"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
