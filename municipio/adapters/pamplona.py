from __future__ import annotations

import hashlib
import json
import re
import socket
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
from municipio.geometry import geometry_centroid

WEB_BASE = "https://www.pamplona.es"
SEDE_BASE = "https://sedeelectronica.pamplona.es"
MUNICIPIO = "Pamplona / Iruña"
ID_PREFIX = "pamplona"

PROYECTOS_COVER = (
    f"{WEB_BASE}/temas/urbanismo-vivienda-e-infraestructuras/actuaciones-urbanisticas/proyectos"
)
OBRAS_COVER = (
    f"{WEB_BASE}/temas/urbanismo-vivienda-e-infraestructuras/actuaciones-urbanisticas/obras"
)
POLIGONOS_COVER = (
    f"{WEB_BASE}/temas/urbanismo-vivienda-e-infraestructuras/actuaciones-urbanisticas/gestion-poligonos"
)
PLAN_MUNICIPAL = f"{WEB_BASE}/temas/urbanismo-vivienda-e-infraestructuras/plan-municipal"

DEFAULT_SEED_PAGES: list[str] = [
    PROYECTOS_COVER,
    OBRAS_COVER,
    POLIGONOS_COVER,
    PLAN_MUNICIPAL,
]

DEFAULT_LICENCIA_TRAMITES: list[dict[str, str]] = [
    {
        "url": f"{SEDE_BASE}/FichaTramite.aspx?id=203404TA",
        "titulo": "Ejecución de obras y/o actividades clasificadas (licencia o declaración responsable)",
        "tipo": "licencia / declaración responsable de obra",
    },
    {
        "url": f"{SEDE_BASE}/FichaTramite.aspx?id=58472TA",
        "titulo": "Obras menores — actuaciones comunicadas",
        "tipo": "comunicación de obra menor",
    },
    {
        "url": f"{SEDE_BASE}/FichaTramite.aspx?id=20-41957",
        "titulo": "Consultas urbanísticas (calificación, parcelación, régimen urbanístico)",
        "tipo": "consulta urbanística",
    },
    {
        "url": f"{SEDE_BASE}/FichaTramite.aspx?id=20-41967",
        "titulo": "Consulta urbanística (licencia de actividad, ascensores, etc.)",
        "tipo": "consulta previa urbanística",
    },
]

SIG_WFS_DEFAULT = "https://sig.pamplona.es/uxogc/wfs"
WFS_TYPE_DEFAULT = "IDEN_Pol_Municipio"

RE_LIST_ITEM = re.compile(
    r'class="field--item"[^>]*>\s*<a href="([^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.pamplona\.es)?/sites/default/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|municipal)|proyecto|obra|"
    r"reparcel|liquidaci[oó]n|gesti[oó]n|pol[ií]gono|ars-|arz-|u\.i\.|"
    r"unidad de ejecuci[oó]n|derribo|urbanizaci[oó]n|hidraul|parque)",
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|obra menor|declaraci[oó]n responsable|comunicaci[oó]n|"
    r"ejecuci[oó]n de obra|consulta urban)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/sites/default/files/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_CODE = re.compile(
    r"(?i)\b("
    r"ARS[-\s]?\d+|ARZ[-\s]?\d+|"
    r"U\.?\s*I\.?\s*[IVXLC\d]+|"
    r"UE[-\s]?[A-Z0-9]+|"
    r"ZN[-\s]?\d+|ZNO[-\s]?\d+"
    r")\b",
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
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(url or text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(f"{text} {url}") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "reparcel" in n or "liquidaci" in n:
        return "reparcelación"
    if "plan parcial" in n or "polígono" in n or "poligono" in n:
        return "plan parcial"
    if "proyecto de ejecuci" in n or "obra" in n:
        return "obra / proyecto"
    if "urbaniz" in n:
        return "urbanización"
    if "plan municipal" in n:
        return "plan municipal"
    if "derribo" in n:
        return "derribo"
    return "urbanismo"


def _norm_token(s: str) -> str:
    t = unescape(s or "").lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


class PamplonaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 10 actuaciones urbanísticas + sede (trámites licencia) + GeoPamplona WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom = self.config.get("geometry") or {}
        self.wfs_url = str(geom.get("wfs_url") or SIG_WFS_DEFAULT).rstrip("/")
        self.wfs_type = str(geom.get("type_name") or WFS_TYPE_DEFAULT)
        self.wfs_timeout = float(geom.get("timeout_s") or 12)
        self._wfs_features: list[dict[str, Any]] | None = None
        self._wfs_failed = False

    def _fetch(self, url: str, timeout: float = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pamplona/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, timeout: float) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pamplona/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (r"<h1[^>]*>([^<]+)", r"<title>([^<]+)"):
            m = re.search(pat, html, re.I)
            if m:
                t = _strip_html(m.group(1))
                t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
                if t and len(t) > 3:
                    return t[:500]
        return fallback

    def _extract_pdfs(self, html: str) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            out.append(self._abs_url(m.group(1)))
        return list(dict.fromkeys(out))

    def _collect_cover_links(self, cover_url: str) -> list[tuple[str, str]]:
        try:
            html = self._fetch(cover_url)
        except (urllib.error.URLError, OSError, TimeoutError):
            return []
        items: list[tuple[str, str]] = []
        for href, title in RE_LIST_ITEM.findall(html):
            url = self._abs_url(href)
            if not url.startswith(self.web_base):
                continue
            if "/temas/" in url and url.rstrip("/") in {
                PROYECTOS_COVER.rstrip("/"),
                OBRAS_COVER.rstrip("/"),
                POLIGONOS_COVER.rstrip("/"),
            }:
                continue
            tit = _strip_html(title)
            if tit:
                items.append((url, tit))
        return items

    def _collect_poligono_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(POLIGONOS_COVER)
        except (urllib.error.URLError, OSError, TimeoutError):
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_PDF_HREF.finditer(html):
            pdf = self._abs_url(m.group(1))
            # title from filename
            name = urllib.parse.unquote(pdf.rsplit("/", 1)[-1])
            titulo = re.sub(r"[_-]+", " ", name.replace(".pdf", "")).strip().title()
            if not RE_PROYECTO.search(titulo):
                continue
            fecha = _fecha_from_blob("", pdf)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", pdf),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": _proyecto_tipo(titulo),
                "url": pdf,
                "source": "ayuntamiento",
                "origen": "gestion_poligonos_pdf",
            }
            rows.append(rec)
        return rows

    def _detail_proyecto(self, url: str, titulo: str, origen: str) -> dict[str, Any]:
        fecha = _fecha_from_blob(titulo, url)
        pdfs: list[str] = []
        try:
            html = self._fetch(url)
            if not fecha:
                fecha = _fecha_from_blob(_strip_html(html), url)
            tit = self._page_title(html, titulo)
            if tit:
                titulo = tit
            pdfs = self._extract_pdfs(html)
            if not fecha and pdfs:
                fechas = [_fecha_from_blob("", p) for p in pdfs]
                fechas = [f for f in fechas if f]
                if fechas:
                    fecha = max(fechas)
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": origen,
        }
        if pdfs:
            rec["documentos"] = pdfs[:20]
        return rec

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] in seen:
                return
            blob = f"{rec.get('titulo', '')} {rec.get('url', '')}"
            if not RE_PROYECTO.search(blob):
                return
            seen.add(rec["id"])
            self._enrich_geometry(rec)
            rows.append(rec)

        for cover, origen in (
            (PROYECTOS_COVER, "proyectos_cover"),
            (OBRAS_COVER, "obras_cover"),
        ):
            for url, titulo in self._collect_cover_links(cover):
                add(self._detail_proyecto(url, titulo, origen))

        for rec in self._collect_poligono_pdfs():
            add(rec)

        # PDFs del plan municipal (documentación de referencia)
        try:
            plan_html = self._fetch(PLAN_MUNICIPAL)
            for pdf in self._extract_pdfs(plan_html):
                name = urllib.parse.unquote(pdf.rsplit("/", 1)[-1])
                titulo = f"Plan Municipal — {name.replace('.pdf', '').replace('_', ' ')}"
                add(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": MUNICIPIO,
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob("", pdf),
                        "tipo": "plan municipal",
                        "url": pdf,
                        "source": "ayuntamiento",
                        "origen": "plan_municipal_pdf",
                    }
                )
        except (urllib.error.URLError, OSError, TimeoutError):
            pass

        return rows

    def _wfs_query_url(self, count: int = 800) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
            }
        )
        return f"{self.wfs_url}?{params}"

    def _load_wfs_features(self) -> list[dict[str, Any]]:
        if self._wfs_features is not None:
            return self._wfs_features
        if self._wfs_failed:
            return []
        url = self._wfs_query_url()
        try:
            data = self._fetch_json(url, timeout=self.wfs_timeout)
            feats = [f for f in (data.get("features") or []) if isinstance(f, dict)]
            self._wfs_features = feats
            return feats
        except (urllib.error.URLError, OSError, TimeoutError, socket.timeout, json.JSONDecodeError, ssl.SSLError):
            self._wfs_failed = True
            self._wfs_features = []
            return []

    @staticmethod
    def _feature_label(props: dict[str, Any]) -> str:
        parts: list[str] = []
        for key in sorted(props.keys()):
            val = props.get(key)
            if val is None:
                continue
            s = str(val).strip()
            if s and len(s) < 120:
                parts.append(s)
        return _norm_token(" ".join(parts))

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        titulo = str(rec.get("titulo") or "")
        codes = [re.sub(r"\s+", "", c.upper()) for c in RE_CODE.findall(titulo)]
        tokens = set(_norm_token(titulo).split())
        best: tuple[int, dict[str, Any]] | None = None
        for feat in self._load_wfs_features():
            props = feat.get("properties") or {}
            label = self._feature_label(props)
            if not label:
                continue
            score = 0
            for code in codes:
                if code.replace(".", "").replace(" ", "") in label.replace(".", "").replace(" ", ""):
                    score += 5
            for tok in tokens:
                if len(tok) > 4 and tok in label:
                    score += 1
            if score > 0 and (best is None or score > best[0]):
                best = (score, feat)
        if not best:
            return
        geom = best[1].get("geometry")
        if not isinstance(geom, dict) or not geom.get("type"):
            return
        url = self._wfs_query_url()
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = url
        rec["coord_source"] = "portal_geometry_centroid"
        rec["geometry_crs"] = "EPSG:4326"
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.config.get("licencia_tramites") or DEFAULT_LICENCIA_TRAMITES:
            url = str(item["url"])
            titulo = str(item.get("titulo") or url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": str(item.get("tipo") or "trámite licencia"),
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo sede; no concesión publicada en tablón",
                }
            )
        return rows

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_tramites()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_tramites():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "proyectos_cover": sum(1 for r in rows if r.get("origen") == "proyectos_cover"),
            "obras_cover": sum(1 for r in rows if r.get("origen") == "obras_cover"),
            "poligonos_pdf": sum(1 for r in rows if r.get("origen") == "gestion_poligonos_pdf"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
