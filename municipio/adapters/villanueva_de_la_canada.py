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

WP_BASE = "https://www.ayto-villacanada.es"
SEDE_BASE = "https://portal.ayto-villacanada.es"
MUNICIPIO = "Villanueva de la Cañada"
ID_PREFIX = "villanueva-de-la-canada"

DEFAULT_TABLON_SUBSECTIONS = ("TV_BAN_URB", "TV_BAN")
DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/urbanismo-y-vivienda/expedientes-urbanisticos/",
    f"{WP_BASE}/urbanismo-y-vivienda/plan-general-de-ordenacion-urbana/",
    f"{WP_BASE}/urbanismo-y-vivienda/plan-parcial-sector-1/",
    f"{WP_BASE}/urbanismo-y-vivienda/plan-parcial-sector-2/",
    f"{WP_BASE}/urbanismo-y-vivienda/plan-parcial-sector-4/",
    f"{WP_BASE}/urbanismo-y-vivienda/planes-especiales/",
]
DEFAULT_LICENCIAS_URL = f"{WP_BASE}/urbanismo-y-vivienda/licencias-urbanisticas/"

RE_EXP_ROW = re.compile(
    r"<tr class='Lista2Linea(?:Par|Impar)' id='exp_(\d+)'[^>]*>\s*"
    r"<td>(\d{4})</td>\s*<td>(\d+)</td>\s*<td>([^<]+)</td>\s*"
    r"<td><a[^>]*href='([^']+)'[^>]*>([^<]+)</a></td>\s*"
    r"<td>(\d{2}/\d{2}/\d{4})</td>\s*<td>(\d{2}/\d{2}/\d{4})</td>",
    re.I | re.DOTALL,
)
RE_DOC_ROW = re.compile(
    r"id='doc_(\d+)'[^>]*>.*?<a[^>]*href='([^']+)'[^>]*>([^<]+)</a>",
    re.I | re.DOTALL,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?ayto-villacanada\.es)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|utilizaci[oó]n del dominio)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|edicto|reparcel|parcela|sector|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|modificaci[oó]n|"
    r"orden de ejecuci|segregaci|memoria|planos|ordenanza|anuncio|edar|"
    r"notificaci[oó]n|bando)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LIC_PANEL = re.compile(
    r'class="fusion-toggle-heading[^"]*"[^>]*>([^<]*[Ll]icencia[^<]{0,200})<',
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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(Path(url).name) if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (
        r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>([^<]+)',
        r"<h1[^>]*>([^<]+)",
        r"<title>([^<]+)",
    ):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Villanueva.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


class VillanuevaDeLaCanadaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA tablón virtual (TV_BAN*) + WordPress Avada (expedientes, PGOU, planes)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_ent_id = int(self.config.get("tablon_ent_id", 6))
        self.tablon_subsections = tuple(
            self.config.get("tablon_subsections") or DEFAULT_TABLON_SUBSECTIONS
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencias_url = str(self.config.get("licencias_url") or DEFAULT_LICENCIAS_URL)

    def _fetch(self, url: str, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-villanueva-canada/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or ("iso-8859-1" if sede else "utf-8")
            return raw.decode(charset, errors="replace")

    def _abs_sede(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.sede_base}/", href))

    def _abs_wp(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{WP_BASE}/", href))

    def _tablon_url(self, subseccion: str) -> str:
        return (
            f"{self.sede_base}/portal/tablonVirtual.do?"
            f"subseccion={subseccion}&opc_id=175&ent_id={self.tablon_ent_id}&idioma=1"
        )

    def _parse_expedientes(self, html: str, subseccion: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_EXP_ROW.finditer(html):
            exp_id, anio, codigo, tipo_raw, href, nombre, f_crea, f_pub = m.groups()
            rows.append(
                {
                    "exp_id": exp_id,
                    "anio": anio,
                    "codigo": codigo,
                    "tipo": unescape(tipo_raw).strip()[:120],
                    "nombre": unescape(nombre).strip()[:500],
                    "fecha_creacion": _parse_fecha_dmy(f_crea),
                    "fecha_publicacion": _parse_fecha_dmy(f_pub),
                    "url": self._abs_sede(href),
                    "subseccion": subseccion,
                }
            )
        return rows

    def _fetch_expediente_docs(self, exp: dict[str, Any]) -> list[dict[str, str]]:
        try:
            html = self._fetch(exp["url"], sede=True)
        except urllib.error.URLError:
            return []
        docs: list[dict[str, str]] = []
        for m in RE_DOC_ROW.finditer(html):
            doc_id, href, title = m.groups()
            docs.append(
                {
                    "doc_id": doc_id,
                    "url": self._abs_sede(href),
                    "titulo": unescape(title).strip()[:500],
                }
            )
        return docs

    def _collect_tablon(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sub in self.tablon_subsections:
            try:
                html = self._fetch(self._tablon_url(sub), sede=True)
            except urllib.error.URLError:
                continue
            for row in self._parse_expedientes(html, sub):
                if row["exp_id"] not in seen:
                    seen.add(row["exp_id"])
                    out.append(row)
        return out

    def _exp_to_licencia(self, exp: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{exp['tipo']} {exp['nombre']}"
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", exp["exp_id"]),
            "fecha_concesion": exp.get("fecha_publicacion"),
            "tipo": exp["tipo"],
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": exp["nombre"],
            "url": exp["url"],
            "source": "ayuntamiento",
            "expte": f"{exp['anio']}/{exp['codigo']}",
        }

    def _exp_to_proyecto(
        self, exp: dict[str, Any], docs: list[dict[str, str]] | None = None
    ) -> dict[str, Any] | None:
        blob = f"{exp['tipo']} {exp['nombre']}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if exp["subseccion"] == "TV_BAN" and not RE_PROYECTO.search(blob):
            return None

        tipo = "urbanismo"
        if re.search(r"(?i)bando|notificaci", blob):
            tipo = "bando"
        elif re.search(r"(?i)plan|pgou|planeam", blob):
            tipo = "planeamiento"
        elif RE_LICENCIA.search(blob):
            tipo = "licencia publicada"

        rec: dict[str, Any] = {
            "id": _stable_id("proy", exp["exp_id"]),
            "municipio": MUNICIPIO,
            "titulo": exp["nombre"],
            "fecha": exp.get("fecha_publicacion") or exp.get("fecha_creacion"),
            "tipo": tipo,
            "url": exp["url"],
            "source": "ayuntamiento",
            "expte": f"{exp['anio']}/{exp['codigo']}",
            "origen": f"tablon_{exp['subseccion']}",
        }
        if docs:
            rec["documentos"] = [d["titulo"] for d in docs[:10]]
            if docs[0].get("url"):
                rec["pdf_url"] = docs[0]["url"]
        return rec

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = _page_title(html, page_url.rsplit("/", 2)[-2].replace("-", " "))
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_wp(m.group(1))
                if "certificado_aenor" in pdf.lower() or "favicon" in pdf.lower():
                    continue
                if pdf in seen:
                    continue
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                blob = f"{page_title} {name} {pdf}"
                if not RE_PROYECTO.search(blob):
                    continue
                seen.add(pdf)
                tipo = "documento urbanismo"
                if re.search(r"(?i)reparcel|sector", blob):
                    tipo = "reparcelación"
                elif re.search(r"(?i)plan parcial|sector", page_url):
                    tipo = "plan parcial"
                elif re.search(r"(?i)plan especial|edar", blob):
                    tipo = "plan especial"
                elif re.search(r"(?i)pgou|ordenanza", blob):
                    tipo = "PGOU"
                elif re.search(r"(?i)informaci[oó]n p[uú]blica|anuncio", blob):
                    tipo = "información pública"
                elif re.search(r"(?i)memoria|planos", name):
                    tipo = "expediente urbanístico"
                rows.append(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": MUNICIPIO,
                        "titulo": name[:500] if len(name) > 10 else f"{page_title}: {name}"[:500],
                        "fecha": _fecha_from_url(pdf) or _parse_fecha_dmy(name),
                        "tipo": tipo,
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": "wordpress_seed",
                    }
                )
        return rows

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.licencias_url)
        except urllib.error.URLError:
            return rows
        for m in RE_LIC_PANEL.finditer(html):
            title = unescape(re.sub(r"\s+", " ", m.group(1)).strip())
            if not RE_LICENCIA.search(title) or len(title) < 8:
                continue
            rec_id = _stable_id("lic", title)
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
                    "titulo": title[:500],
                    "url": self.licencias_url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámites; no concesión publicada en tablón",
                }
            )
        if not rows:
            rec_id = _stable_id("lic", self.licencias_url)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Licencias Urbanísticas — trámites y documentación",
                    "url": self.licencias_url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámites; no concesión publicada en tablón",
                }
            )
        return rows

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
        for exp in self._collect_tablon():
            rec = self._exp_to_licencia(exp)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for rec in self._collect_licencias_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon+tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for exp in self._collect_tablon():
            rec = self._exp_to_licencia(exp)
            if not rec:
                continue
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        for rec in self._collect_licencias_tramites():
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for exp in self._collect_tablon():
            docs = self._fetch_expediente_docs(exp)
            add(self._exp_to_proyecto(exp, docs))

        for rec in self._collect_seed_pdfs():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon_")),
            "wordpress": sum(1 for r in rows if r.get("origen") == "wordpress_seed"),
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
