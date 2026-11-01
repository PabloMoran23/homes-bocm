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
from municipio.geometry import record_geometry

WEB_BASE = "https://www.salou.cat"
SEDE_BASE = "https://seu.salou.cat/siac"
MUNICIPIO = "Salou"
ID_PREFIX = "salou"
INE_MUN = "43148"

TABLON_URL = f"{SEDE_BASE}/Tablon.aspx"
PUBLICACIONES_ET = f"{SEDE_BASE}/Publicaciones.aspx?t=ET&viewall=Y"
PROCEDIMIENTOS_URL = f"{SEDE_BASE}/Procedimientos.aspx"

DEFAULT_PLONE_ROOTS: list[str] = [
    f"{WEB_BASE}/ca/la-ciutat-per-temes/urbanisme-i-planejament/planejament",
    f"{WEB_BASE}/ca/la-ciutat-per-temes/urbanisme-i-planejament/convenis-urbanistics",
    f"{WEB_BASE}/ca/la-ciutat-per-temes/urbanisme-i-planejament/projectes-en-desenvolupament",
    f"{WEB_BASE}/ca/la-ciutat-per-temes/urbanisme-i-planejament/projectes-finalitzats",
]

DEFAULT_LICENCIA_PROC_KEYWORDS: tuple[str, ...] = (
    "obras mayores",
    "obras menores",
    "comunicación previa",
    "comunicacio previa",
    "primera ocupación",
    "primera ocupacio",
    "licencia",
    "llicència",
    "llicencia",
    "declaración responsable",
    "declaracio responsable",
    "informe urban",
    "informes i certificacions urban",
    "devolución de fianza en materia urbanística",
)

RE_LICENCIA = re.compile(
    r"(?i)(llicen[cs]ia|licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"obra[s]? (?:major|menor|mayores|menores)|primera ocupaci[oó]|informe[s]? urban|"
    r"fianza en materia urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|poum|pgou|modificaci[oó]|plan (?:parcial|especial|millora)|"
    r"informaci[oó] p[uú]blica|exposici[oó]|expedient|conveni urban|peu\b|peu-|"
    r"projecte|gesti[oó] urban|dogc|edict|sector|reurban|drenatge|rambla|crt\b|"
    r"trama urbana|ordenan[cç]a urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(cr[eè]dit[s]? pressupost|modificaci[oó] cr[eè]dit|sindicatura de comptes|"
    r"preus p[uú]blics|jurat per als propers anys|permute agent|subvenci[oó]|"
    r"proc[eé]s selectiu|borsa de treball|establiments alimentaris|espectacle|"
    r"actividades recreativ|piscines de uso p[uú]blico|quema restos)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_TABLON_ROW = re.compile(
    r'<tr class="GridViewRow">\s*<td[^>]*>\s*(.*?)\s*</td>\s*'
    r'<td[^>]*>\s*(\d{1,2}/\d{1,2}/\d{4})\s*</td>.*?'
    r'href="([^"]*DetalleTablon\.aspx\?id=\d+)"',
    re.S | re.I,
)
RE_PROC_ROW = re.compile(
    r'<tr class="GridViewRow">\s*<td[^>]*>\s*(.*?)\s*</td>.*?'
    r'href="(ProcedimientoTabs\.aspx\?[^"]+)"',
    re.S | re.I,
)
RE_PLONE_LINK = re.compile(
    r'href="(https://www\.salou\.cat/ca/la-ciutat-per-temes/urbanisme-i-planejament/[^"#?]+)"',
    re.I,
)
RE_H1 = re.compile(r'<h1[^>]*class="documentFirstHeading"[^>]*>([^<]+)', re.I)
RE_META_MOD = re.compile(
    r'name="DC\.date\.modified" content="([^"]+)"',
    re.I,
)
RE_EXPEDIENTE = re.compile(r"(?i)Exp\.?\s*(\d+/\d+)")


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


def _parse_iso_date(text: str) -> str | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text or "")
    if not m:
        return None
    try:
        datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return m.group(0)


def _tipo_proyecto(titulo: str) -> str:
    blob = titulo.lower()
    if "modificaci" in blob and "poum" in blob:
        return "modificación POUM"
    if "plan especial" in blob or re.search(r"\bpeu\b", blob):
        return "plan especial urbanístico"
    if "plan parcial" in blob or "plans parcials" in blob:
        return "plan parcial"
    if "conveni" in blob:
        return "convenio urbanístico"
    if "informaci" in blob or "exposici" in blob or "edict" in blob or "dogc" in blob:
        return "información pública / edicto"
    if "projecte" in blob or "obra" in blob:
        return "proyecto / obra urbanística"
    if "poum" in blob or "planejament" in blob:
        return "planeamiento"
    return "urbanismo"


class SalouAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone salou.cat (minisite urbanisme) + seu SIAC (Tablon, tràmits). Geometría: sin capa ICV para INE 43148."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.plone_roots = [str(u) for u in (self.config.get("plone_roots") or DEFAULT_PLONE_ROOTS)]
        self.max_plone_pages = int(self.config.get("max_plone_pages", 90))
        self.enrich_tablon = bool(self.config.get("enrich_tablon", False))

    def _fetch(self, url: str, *, timeout: int = 90, retries: int = 2) -> str:
        last_err: Exception | None = None
        for attempt in range(retries):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-salou/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError, ConnectionResetError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        if last_err:
            raise last_err
        raise urllib.error.URLError("fetch failed")

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

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
                    rows.append(json.loads(line))
        return rows

    def _parse_tablon(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            titulo = _strip_html(m.group(1))
            fecha = _parse_fecha_dmy(m.group(2))
            detail_url = self._abs_sede(m.group(3))
            if not titulo or RE_EXCLUDE.search(titulo):
                continue
            if not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "id": _stable_id("proy", detail_url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": _tipo_proyecto(titulo),
                    "url": detail_url,
                    "source": "ayuntamiento",
                    "origen": "sede_tablon",
                }
            )
        return rows

    def _enrich_tablon_detail(self, rec: dict[str, Any]) -> None:
        url = str(rec.get("url") or "")
        if not url:
            return
        try:
            html = self._fetch(url, timeout=60)
        except urllib.error.URLError:
            return
        desc_m = re.search(
            r'id="ctl00_Content_LDescripcionPub"[^>]*>[^<]*</span>\s*'
            r'<span class="LitDetalle">(.*?)</span>',
            html,
            re.S,
        )
        if desc_m:
            desc = _strip_html(desc_m.group(1))
            if desc and len(desc) > len(str(rec.get("titulo") or "")):
                rec["titulo"] = desc[:500]
        exp_m = RE_EXPEDIENTE.search(html)
        if exp_m:
            rec["expediente"] = exp_m.group(1)

    def _collect_plone_documents(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue = [u.rstrip("/") for u in self.plone_roots]
        doc_urls: set[str] = set()

        while queue and len(visited) < self.max_plone_pages:
            url = queue.pop(0).rstrip("/")
            if url in visited:
                continue
            visited.add(url)
            try:
                html = self._fetch(url, timeout=60)
            except urllib.error.URLError:
                continue
            if "portaltype-document" in html or "documentFirstHeading" in html:
                doc_urls.add(url)
            for m in RE_PLONE_LINK.finditer(html):
                link = m.group(1).rstrip("/")
                if link in visited or link in queue:
                    continue
                if any(x in link for x in ("/noticies", "/agenda", "/sitemap", "/el-cadastre")):
                    continue
                queue.append(link)

        rows: list[dict[str, Any]] = []
        for url in sorted(doc_urls):
            try:
                html = self._fetch(url, timeout=60)
            except urllib.error.URLError:
                continue
            h1_m = RE_H1.search(html)
            titulo = _strip_html(h1_m.group(1)) if h1_m else url.rsplit("/", 1)[-1].replace("-", " ")
            if len(titulo) < 4 or RE_EXCLUDE.search(titulo):
                continue
            if not RE_PROYECTO.search(titulo) and "planejament" not in url:
                continue
            fecha = _parse_iso_date(RE_META_MOD.search(html).group(1) if RE_META_MOD.search(html) else "")
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": _tipo_proyecto(titulo),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "plone_urbanisme",
                }
            )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        try:
            tablon_html = self._fetch(self.tablon_url)
            for rec in self._parse_tablon(tablon_html):
                if self.enrich_tablon:
                    self._enrich_tablon_detail(rec)
                merged[rec["id"]] = rec
        except urllib.error.URLError:
            pass

        for rec in self._collect_plone_documents():
            merged[rec["id"]] = rec

        # Semilla informativa del listado de expedientes en tramitación (sede).
        pub_id = _stable_id("proy", PUBLICACIONES_ET)
        if pub_id not in merged:
            merged[pub_id] = {
                "id": pub_id,
                "municipio": MUNICIPIO,
                "titulo": "Expedientes en tramitación — publicaciones sede electrónica",
                "fecha": None,
                "tipo": "índice expedientes",
                "url": PUBLICACIONES_ET,
                "source": "ayuntamiento",
                "origen": "sede_publicaciones_et",
            }

        return list(merged.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        try:
            tablon_html = self._fetch(self.tablon_url)
            for rec in self._parse_tablon(tablon_html):
                if not RE_LICENCIA.search(rec["titulo"]):
                    continue
                lic = {
                    "id": _stable_id("lic", rec["url"]),
                    "fecha_concesion": rec.get("fecha"),
                    "tipo": "anuncio tablón",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": rec["titulo"],
                    "url": rec["url"],
                    "source": "ayuntamiento",
                    "origen": "sede_tablon",
                }
                if lic["id"] not in seen:
                    seen.add(lic["id"])
                    rows.append(lic)
        except urllib.error.URLError:
            pass

        try:
            proc_html = self._fetch(PROCEDIMIENTOS_URL)
            for m in RE_PROC_ROW.finditer(proc_html):
                titulo = _strip_html(m.group(1))
                titulo = re.sub(r"\s*(Información|Tramitar)\s*$", "", titulo, flags=re.I).strip()
                blob = titulo.lower()
                if not any(k in blob for k in DEFAULT_LICENCIA_PROC_KEYWORDS):
                    continue
                if not RE_LICENCIA.search(titulo) and "obra" not in blob:
                    continue
                url = self._abs_sede(m.group(2))
                rec_id = _stable_id("lic", url)
                if rec_id in seen:
                    continue
                seen.add(rec_id)
                rows.append(
                    {
                        "id": rec_id,
                        "fecha_concesion": None,
                        "tipo": "trámite licencia / comunicación obra",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": titulo[:500],
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "sede_procedimientos",
                        "nota": "Sin listado público de concesiones; trámite telemático SIAC",
                    }
                )
        except urllib.error.URLError:
            pass

        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tablon_y_tramites"}

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
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "source": "plone_urbanisme_y_sede_tablon",
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "with_geometry": stats.get("with_geometry", 0),
            "status": "ok",
        }
