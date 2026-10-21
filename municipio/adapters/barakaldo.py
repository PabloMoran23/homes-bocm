from __future__ import annotations

import hashlib
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

PORTAL_BASE = "https://www.barakaldo.eus"
SEDE_BASE = f"{PORTAL_BASE}/OficinaVirtualBarakaldo"
INFO_PUBLICA = f"{PORTAL_BASE}/portal/es/web/planeamiento-y-gestion/informacion-publica"
TABLON_BUSCAR = f"{SEDE_BASE}/buscarTablonAnuncios.do"
MUNICIPIO = "Barakaldo"
ID_PREFIX = "barakaldo"

DEFAULT_LICENCIA_TRAMITES: list[tuple[str, str]] = [
    ("143", "Liquidación de Licencias de Obras"),
    ("1178", "Licencia de Obra Menor Abreviada"),
    ("497", "Licencia de Obra Menor (ordinario)"),
    ("1181", "Licencia de Obra Mayor (general)"),
    ("21", "Licencia de Obra Mayor: ascensor"),
    ("23", "Licencia de Obra Mayor: local a vivienda"),
]

TABLON_TEMAS = ("24", "10")  # Urbanismo, Licencias urbanísticas

RE_LICENCIA = re.compile(
    r"(?i)(licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:menor|mayor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|integral)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|urbanizaci[oó]n|peri|gesti[oó]n urban|ascensor|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional))",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_TABLON_ITEM = re.compile(
    r'verDetalleAnuncio\((\d+)\)[^<]*<font[^>]*>([^<]+)</font>.*?'
    r"Fecha de publicaci[oó]n:</span>&nbsp;(\d{2}/\d{2}/\d{4})",
    re.S | re.I,
)
RE_LIFERAY_NEWS = re.compile(
    r'class="fecha">(\d{2}/\d{2}/\d{4})\s*</span><span class="h2ListadoNoticias">'
    r'<a href="([^"]+)"[^>]*>([^<]+)</a>',
    re.S,
)
RE_EXPEDIENTE = re.compile(
    r"(?i)\b(?:expte\.?|expediente)\s*[:.]?\s*([0-9]+/[0-9]{4}|[A-Z0-9./-]+)",
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


def _iso_from_year(text: str) -> str | None:
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2030
    ]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (r"<h1[^>]*>([^<]+)", r"<title>([^<]+)"):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*SIBAE.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _tipo_proyecto(titulo: str) -> str:
    blob = titulo.lower()
    if "plan integral" in blob or "plan general" in blob or "pgou" in blob:
        return "PGOU"
    if "plan especial" in blob:
        return "plan especial"
    if "plan parcial" in blob:
        return "plan parcial"
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "modificaci" in blob and "puntual" in blob:
        return "modificación puntual"
    if "convenio" in blob:
        return "convenio"
    if "reparcel" in blob:
        return "reparcelación"
    if "informaci" in blob and "pública" in blob:
        return "información pública"
    if "aprobaci" in blob:
        return "aprobación"
    return "urbanismo"


class BarakaldoAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay noticias planeamiento + SIBAE tablón (AJAX JSON); licencias vía trámites sede."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or PORTAL_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.info_publica_url = str(self.config.get("info_publica_url") or INFO_PUBLICA)
        raw_tram = self.config.get("licencia_tramites")
        if raw_tram:
            self.licencia_tramites = [(str(t["id"]), t["titulo"]) for t in raw_tram]
        else:
            self.licencia_tramites = list(DEFAULT_LICENCIA_TRAMITES)
        self.tablon_temas = list(self.config.get("tablon_temas") or TABLON_TEMAS)

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-barakaldo/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_portal(self, path: str) -> str:
        if path.startswith("http"):
            return path.split(";jsessionid=")[0]
        return urllib.parse.urljoin(PORTAL_BASE, path)

    def _abs_sede(self, path: str) -> str:
        if path.startswith("http"):
            return path.split(";jsessionid=")[0]
        return urllib.parse.urljoin(self.sede_base + "/", path.lstrip("/"))

    def _tablon_page(self, tema: str, pagina: int, page_size: int = 50) -> dict[str, Any]:
        payload = urllib.parse.urlencode(
            {
                "textoLibre": "",
                "origenNoMunicipal": "",
                "codTemaAnuncio": tema,
                "estadoAnuncio": "1",
                "entorno": "1",
                "languageEus": "true",
                "tipoBusqueda": "1",
                "paginaActual": str(pagina),
                "registrosPagina": str(page_size),
                "avanzarRetroceder": "0",
            }
        ).encode("utf-8")
        raw = self._fetch(TABLON_BUSCAR, data=payload)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"html": raw, "regTotal": "0", "paginaActual": pagina}

    def _collect_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tema in self.tablon_temas:
            pagina = 1
            total = None
            while True:
                data = self._tablon_page(tema, pagina)
                html = data.get("html") or ""
                if total is None:
                    try:
                        total = int(data.get("regTotal") or 0)
                    except (TypeError, ValueError):
                        total = 0
                for m in RE_TABLON_ITEM.finditer(html):
                    cod, titulo, fecha_raw = m.group(1), unescape(m.group(2).strip()), m.group(3)
                    if cod in seen:
                        continue
                    seen.add(cod)
                    url = self._abs_sede(f"detalleAnuncio.do?codAnuncio={cod}")
                    rows.append(
                        {
                            "cod_anuncio": cod,
                            "titulo": titulo[:500],
                            "fecha": _parse_fecha_dmy(fecha_raw),
                            "url": url,
                            "tema": tema,
                            "origen": "sede_tablon",
                        }
                    )
                if not html or pagina * 50 >= (total or 0):
                    break
                pagina += 1
        return rows

    def _collect_liferay_news(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.info_publica_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_LIFERAY_NEWS.finditer(html):
            fecha_raw, url, titulo = m.group(1), m.group(2), unescape(m.group(3).strip())
            article_m = re.search(r"articleId=(\d+)", url)
            rows.append(
                {
                    "article_id": article_m.group(1) if article_m else None,
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": self._abs_portal(url),
                    "origen": "liferay_noticias",
                }
            )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tram_id, label in self.licencia_tramites:
            url = self._abs_sede(f"tramites/acceso.do?id={tram_id}")
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = _page_title(html, label)
            rec: dict[str, Any] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": url,
                "source": "ayuntamiento",
                "nota": "Página informativa SIBAE; sin listado público de concesiones",
            }
            rows.append(rec)
        return rows

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        if not RE_PROYECTO.search(titulo):
            return None
        url = row["url"]
        fecha = row.get("fecha") or _iso_from_year(titulo)
        return {
            "id": _stable_id("proy", f"tablon-{row['cod_anuncio']}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": fecha,
            "tipo": _tipo_proyecto(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "cod_anuncio": row.get("cod_anuncio"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", f"tablon-{row['cod_anuncio']}"),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia urbanística",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _news_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if not RE_PROYECTO.search(titulo):
            return None
        key = row.get("article_id") or row["url"]
        return {
            "id": _stable_id("proy", f"news-{key}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha") or _iso_from_year(titulo),
            "tipo": _tipo_proyecto(titulo),
            "url": row["url"],
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
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_tramites():
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
            "tramites": sum(1 for r in rows if r.get("nota")),
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_tablon"),
        }

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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_liferay_news():
            add(self._news_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_tablon"),
            "liferay": sum(1 for r in rows if r.get("origen") == "liferay_noticias"),
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
