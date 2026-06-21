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

WP_BASE = "https://ayto-ciempozuelos.org"
SEDE_BASE = "https://sede.ayto-ciempozuelos.org/eAdmin"
MUNICIPIO = "Ciempozuelos"
ID_PREFIX = "ciempozuelos"

TABLON_LIST = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
TABLON_HOME = f"{SEDE_BASE}/Tablon.do?action=inicioTablon"
TRAMITES_URBANISMO = f"{WP_BASE}/index.php/tramites-municipales/"
URBANISMO_PAGE = f"{WP_BASE}/index.php/urbanismo/"
SEDE_TRAMITES = f"{SEDE_BASE}/Registrar.do?action=inicioPortalTramites"

DEFAULT_LICENCIA_PAGES: list[str] = [
    URBANISMO_PAGE,
    TRAMITES_URBANISMO,
    SEDE_TRAMITES,
]

RE_TABLON_ROW = re.compile(
    r'verAnuncio&id=([A-F0-9]+)"'
    r'.*?</td>\s*<td[^>]*>\s*'
    r'((?:[^<]|<br\s*/?>)+?)'
    r'\s*</td>\s*<td[^>]*>.*?Periodo:.*?(\d{2}/\d{2}/\d{4})',
    re.I | re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|vado)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan |informaci[oó]n p[uú]blica|pgou|convenio|"
    r"expediente|edicto|reparcel|pleno|ordenanza|ibi urbana|vado|"
    r"aprobaci[oó]n (?:inicial|definitiva)|modificaci[oó]n|suelo|parcela)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?ayto-ciempozuelos\.org)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_TRAMITE_LINK = re.compile(
    r'href="((?:https?://(?:www\.)?ayto-ciempozuelos\.org)?/index\.php/[^"]*(?:urbanismo|licencia|obra)[^"]*)"',
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


def _strip_html(text: str) -> str:
    t = re.sub(r"<br\s*/?>", " ", text or "", flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _norm_key(key: str) -> str:
    t = (key or "").lower()
    t = t.replace("ó", "o").replace("í", "i").replace("é", "e").replace("á", "a").replace("ú", "u")
    return t


class CiempozuelosAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede add4u tablón de edictos + web WordPress urbanismo/trámites."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.fetch_detail = bool(self.config.get("fetch_tablon_detail", True))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ciempozuelos/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", href)

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{WP_BASE}/", href)

    def _parse_tablon_listing(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TABLON_ROW.finditer(html):
            anuncio_id = m.group(1)
            if anuncio_id in seen:
                continue
            seen.add(anuncio_id)
            title = _strip_html(m.group(2))
            fecha = _parse_fecha_dmy(m.group(3))
            url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={anuncio_id}"
            rows.append(
                {
                    "anuncio_id": anuncio_id,
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": url,
                }
            )
        return rows

    def _parse_detail_fields(self, html: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for m in re.finditer(r"<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]*)", html, re.I):
            key = _norm_key(unescape(m.group(1).strip()))
            val = unescape(m.group(2).strip())
            if key:
                fields[key] = val
        return fields

    def _fetch_anuncio_detail(self, url: str) -> dict[str, str]:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return {}
        return self._parse_detail_fields(html)

    def _collect_tablon(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in (TABLON_LIST, TABLON_HOME):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for row in self._parse_tablon_listing(html):
                if row["anuncio_id"] in seen:
                    continue
                seen.add(row["anuncio_id"])
                items.append(row)
        return items

    def _enrich_tablon_item(self, item: dict[str, Any]) -> dict[str, Any]:
        if not self.fetch_detail:
            return item
        detail = self._fetch_anuncio_detail(item["url"])
        desc = detail.get("descripcion") or detail.get("descripci") or ""
        contenido = detail.get("contenido") or ""
        fecha_ini = detail.get("fecha inicio publicacion") or detail.get("fecha inicio publicaci") or ""
        titulo = desc or item["titulo"]
        fecha = _parse_fecha_dmy(fecha_ini) or item.get("fecha")
        return {
            **item,
            "titulo": titulo[:500] or item["titulo"],
            "fecha": fecha,
            "descripcion": desc,
            "contenido": contenido[:1000],
            "blob": f"{titulo} {desc} {contenido}"[:2000],
        }

    def _proyecto_tipo(self, blob: str) -> str:
        if re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            return "información pública"
        if re.search(r"(?i)pleno", blob):
            return "acuerdo plenario"
        if re.search(r"(?i)convenio", blob):
            return "convenio"
        if re.search(r"(?i)ordenanza|ibi", blob):
            return "normativa fiscal"
        if re.search(r"(?i)plan |planeam|pgou", blob):
            return "planeamiento"
        return "urbanismo"

    def _title_to_licencia(self, title: str, url: str, fecha: str | None) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
            return None
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }

    def _title_to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str | None,
        blob: str = "",
    ) -> dict[str, Any] | None:
        text = f"{title} {blob}"
        if RE_LICENCIA.search(text) and not RE_PROYECTO.search(text):
            return None
        if not RE_PROYECTO.search(text):
            return None
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha,
            "tipo": self._proyecto_tipo(text),
            "url": url,
            "source": "ayuntamiento",
        }

    def _collect_licencias_informativas(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title = "Trámites urbanismo"
            if "urbanismo" in page_url:
                title = "Urbanismo — trámites y normativa"
            elif "Registrar" in page_url:
                title = "Solicitud General Urbanismo (sede electrónica)"
            rec_id = _stable_id("lic", page_url)
            if rec_id not in seen:
                seen.add(rec_id)
                rows.append(
                    {
                        "id": rec_id,
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title,
                        "url": page_url,
                        "source": "ayuntamiento",
                        "nota": "Página informativa; no concesión publicada en tablón",
                    }
                )
            for m in RE_TRAMITE_LINK.finditer(html):
                link = self._abs_wp(m.group(1))
                if link in seen:
                    continue
                try:
                    page = self._fetch(link)
                except urllib.error.URLError:
                    continue
                pt = self._page_title(page, link.rsplit("/", 1)[-1])
                if not RE_LICENCIA.search(pt):
                    continue
                rec_id = _stable_id("lic", link)
                if rec_id in seen:
                    continue
                seen.add(rec_id)
                rows.append(
                    {
                        "id": rec_id,
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": pt[:500],
                        "url": link,
                        "source": "ayuntamiento",
                        "nota": "Trámite informativo web corporativa",
                    }
                )
        return rows

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (r"<h1[^>]*>([^<]+)", r"<title>([^<]+)"):
            m = re.search(pat, html, re.I)
            if m:
                t = unescape(m.group(1).strip())
                t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
                if t and len(t) > 3:
                    return t[:500]
        return fallback

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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            enriched = self._enrich_tablon_item(item)
            blob = enriched.get("blob") or enriched["titulo"]
            add(self._title_to_licencia(blob, enriched["url"], enriched.get("fecha")))
        for rec in self._collect_licencias_informativas():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tablon": len(self._collect_tablon())}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        tablon = self._collect_tablon()
        for item in tablon:
            enriched = self._enrich_tablon_item(item)
            blob = enriched.get("blob") or enriched["titulo"]
            add(
                self._title_to_proyecto(
                    enriched["titulo"],
                    enriched["url"],
                    enriched.get("fecha"),
                    blob=blob,
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tablon_items": len(tablon)}

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
