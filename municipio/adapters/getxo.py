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

WEB_BASE = "https://www.getxo.eus"
TABLON_BASE = "https://eudala.getxo.eus/WEBTablon"
MUNICIPIO = "Getxo"
ID_PREFIX = "getxo"

TABLON_URBA = f"{TABLON_BASE}/AnunciosWEB.aspx?opt=URBA&int=1&OpcionMNU_Llamado=560&ChangeIdioma=CA"
TABLON_ALL = f"{TABLON_BASE}/AnunciosWEB.aspx?opt=TO&OpcionMNU_Llamado=574&ChangeIdioma=CA"
TRAMITES_GUIA = f"{WEB_BASE}/es/tramites/tramitesnew"
DESARROLLO_URB = f"{WEB_BASE}/es/desarrollo-urbanistico-sostenible/pgou/"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/desarrollo-urbanistico-sostenible/pgou/pgou-actualizado-modificaciones-bob1",
    f"{WEB_BASE}/es/desarrollo-urbanistico-sostenible/pgou/pgou-actualizado-publicacion-bob1",
    f"{WEB_BASE}/es/desarrollo-urbanistico-sostenible/pgou/inicial-informacion",
    DESARROLLO_URB,
]

DEFAULT_LICENCIA_TRAMITES: list[dict[str, str]] = [
    {
        "url": TRAMITES_GUIA,
        "titulo": "Obras de nueva planta, ampliación o reforma y demolición",
        "tipo": "licencia de obra",
    },
    {
        "url": TRAMITES_GUIA,
        "titulo": "Actividades clasificadas (licencias y comunicaciones previas)",
        "tipo": "licencia de actividad",
    },
    {
        "url": TRAMITES_GUIA,
        "titulo": "Licencia de parcelación (división de terrenos)",
        "tipo": "licencia de parcelación",
    },
    {
        "url": TABLON_URBA,
        "titulo": "Tablón electrónico — sección Urbanismo",
        "tipo": "tablón edictos urbanismo",
    },
]

RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', re.I)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|obra(s)?\s+(?:menor|mayor)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|edicto.*licencia|concesi[oó]n de licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|pgou|modificaci[oó]n|aprobaci[oó]n|informaci[oó]n p[uú]blica|"
    r"reparcel|convenio|ordenaci[oó]n|estudio|expediente|bob|acuerdo plenario|"
    r"licencia|obra|edicto|sondeo|parcel)",
)
RE_SKIP_PDF = re.compile(
    r"(?i)(/pgap-\d|/pgap-\d+-\d|caratula|favicon|/revision/fase_|"
    r"documentacion_grafica|\.dwg|/pgou/2026/.*\.zip|memoria\.pdf$|planos?\.pdf$)"
)
RE_URBAN_DOC = re.compile(
    r"(?i)(modificaci|acuerdo|resoluci|aprob|bob|decreto|anexo|informaci[oó]n|"
    r"edicto|licencia|convenio|reparcel|pgou|planeam|urban)"
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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(f"{text} {url}") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n:
        return "modificación puntual PGOU"
    if "pgou" in n or "plan general" in n:
        return "PGOU / planeamiento"
    if "licencia" in n:
        return "licencia urbanística"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "acuerdo" in n and "pleno" in n:
        return "acuerdo plenario"
    if re.search(r"(?i)bob", blob):
        return "publicación BOB"
    return "urbanismo"


class GetxoAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal getxo.eus (PGOU/documentación) + e-Tablón eudala (ASP.NET) + guía trámites."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tablon_base = str(self.config.get("tablon_base") or TABLON_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 12))

    def _fetch(self, url: str, timeout: float = 60, latin: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-getxo/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        if latin:
            return raw.decode("iso-8859-1", errors="replace")
        return raw.decode("utf-8", errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_tablon(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.tablon_base}/", unescape(href))

    def _parse_tablon_rows(self, html: str, list_url: str) -> list[dict[str, Any]]:
        m = re.search(r'id="DBGAnunicos"(.*?)</table>', html, re.I | re.S)
        if not m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.I | re.S)[1:]:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.I | re.S)
            if len(cells) < 4:
                continue
            fecha_ini = _strip_html(cells[0])
            agrup = _strip_html(cells[2]) if len(cells) > 2 else ""
            desc = _strip_html(cells[3]) if len(cells) > 3 else _strip_html(cells[2])
            blob = f"{agrup} {desc}"
            if not desc:
                continue
            fecha = _parse_fecha_dmy(fecha_ini) or _fecha_from_blob(blob)
            rows.append(
                {
                    "fecha": fecha,
                    "titulo": desc[:500],
                    "agrupamiento": agrup,
                    "url": list_url,
                    "blob": blob,
                }
            )
        return rows

    def _tablon_announcements(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for url in (TABLON_URBA, TABLON_ALL):
            try:
                html = self._fetch(url, latin=True)
            except (urllib.error.URLError, OSError, TimeoutError):
                continue
            for row in self._parse_tablon_rows(html, url):
                key = f"{row['titulo']}|{row.get('fecha')}"
                if key in seen:
                    continue
                seen.add(key)
                out.append(row)
        return out

    def _collect_tablon_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for ann in self._tablon_announcements():
            blob = ann["blob"]
            if "opt=TO" in ann["url"] and not RE_PROYECTO.search(blob):
                continue
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"tablon|{ann['titulo']}|{ann.get('fecha')}"),
                "municipio": MUNICIPIO,
                "titulo": ann["titulo"],
                "fecha": ann.get("fecha"),
                "tipo": _proyecto_tipo(blob),
                "url": ann["url"],
                "source": "ayuntamiento",
                "origen": "etablon",
            }
            rows.append(rec)
        return rows

    def _collect_tablon_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for ann in self._tablon_announcements():
            if not RE_LICENCIA.search(ann["blob"]):
                continue
            url = ann["url"]
            rec: dict[str, Any] = {
                "id": _stable_id("lic", f"tablon|{ann['titulo']}|{ann.get('fecha')}"),
                "fecha_concesion": ann.get("fecha"),
                "tipo": "edicto / licencia (tablón)",
                "distrito": ann.get("agrupamiento"),
                "lat": None,
                "lon": None,
                "titulo": ann["titulo"][:500],
                "url": url,
                "source": "ayuntamiento",
            }
            rows.append(rec)
        return rows

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (r"<h1[^>]*>([^<]+)", r"<h2[^>]*class=\"card-title\"[^>]*>([^<]+)", r"<title>([^<]+)"):
            m = re.search(pat, html, re.I)
            if m:
                t = _strip_html(m.group(1))
                t = re.sub(r"\s*[-|].*Getxo.*$", "", t, flags=re.I).strip()
                if len(t) > 3:
                    return t
        return fallback

    def _extract_docs_from_html(self, html: str, page_url: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for m in RE_PDF.finditer(html):
            href = m.group(1)
            if RE_SKIP_PDF.search(href):
                continue
            url = self._abs_web(href)
            titulo = ""
            for lm in RE_LINK.finditer(html):
                if lm.group(1) == href or urllib.parse.unquote(lm.group(1)) == urllib.parse.unquote(href):
                    titulo = _strip_html(lm.group(2))
                    break
            if not titulo:
                titulo = Path(urllib.parse.urlparse(url).path).name.replace("%20", " ")
            blob = f"{titulo} {url}"
            if not RE_PROYECTO.search(blob) and not RE_URBAN_DOC.search(blob):
                continue
            found.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "fecha": _fecha_from_blob(titulo, url),
                    "page_url": page_url,
                }
            )
        return found

    def _crawl_pgou_proyectos(self) -> list[dict[str, Any]]:
        queue: list[str] = list(dict.fromkeys(self.seed_pages))
        visited: set[str] = set()
        docs: dict[str, dict[str, Any]] = {}
        while queue and len(visited) < self.max_crawl_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, OSError, TimeoutError):
                continue
            for doc in self._extract_docs_from_html(html, url):
                docs.setdefault(doc["url"], doc)
        rows: list[dict[str, Any]] = []
        for url, doc in docs.items():
            titulo = doc["titulo"]
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": doc.get("fecha"),
                    "tipo": _proyecto_tipo(f"{titulo} {url}"),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "pgou_docs",
                    "pagina_origen": doc.get("page_url"),
                }
            )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for rec in self._collect_tablon_proyectos() + self._crawl_pgou_proyectos():
            merged[rec["id"]] = rec
        return list(merged.values())

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.config.get("licencia_tramites") or DEFAULT_LICENCIA_TRAMITES:
            url = str(item["url"])
            titulo = str(item.get("titulo") or url)
            rows.append(
                {
                    "id": _stable_id("lic", f"{url}|{titulo}"),
                    "fecha_concesion": None,
                    "tipo": str(item.get("tipo") or "trámite urbanismo"),
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Guía de trámites / tablón; sin listado de concesiones individuales",
                }
            )
        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for rec in self._collect_tablon_licencias() + self._collect_licencias_tramites():
            merged[rec["id"]] = rec
        return list(merged.values())

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
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "etablon_y_tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
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
            "etablon": sum(1 for r in rows if r.get("origen") == "etablon"),
            "pgou_docs": sum(1 for r in rows if r.get("origen") == "pgou_docs"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
