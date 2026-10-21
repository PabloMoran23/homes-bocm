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

WP_BASE = "https://www.aytobadajoz.es"
SEDE_BASE = "https://sede.aytobadajoz.es"
MUNICIPIO = "Badajoz"
ID_PREFIX = "badajoz"

TABLON_SUBSECTION = "ANU_ADMON"
TABLON_PARAMS = "opc_id=175&ent_id=1&idioma=1"
DEFAULT_TABLON_CAMPO_URLS = (
    f"{SEDE_BASE}/portal/tablonVirtual.do?campo=17&{TABLON_PARAMS}&subseccion={TABLON_SUBSECTION}",
    f"{SEDE_BASE}/portal/tablonVirtual.do?campo=9&{TABLON_PARAMS}&subseccion={TABLON_SUBSECTION}",
    f"{SEDE_BASE}/portal/tablonVirtual.do?{TABLON_PARAMS}&subseccion={TABLON_SUBSECTION}",
)
DEFAULT_PGM_PAGES: list[str] = [
    f"{WP_BASE}/es/ayto/pgm/planeamiento-en-tramite",
    f"{WP_BASE}/es/ayto/pgm/publicacion",
    f"{WP_BASE}/es/ayto/pgm/memorias",
    f"{WP_BASE}/es/ayto/pgm/planespecial",
    f"{WP_BASE}/es/ayto/pgm/programa",
    f"{WP_BASE}/es/ayto/pgm",
]
DEFAULT_LICENCIAS_INFO = f"{WP_BASE}/es/ayto/pgm"

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
    r'href="((?:https://www\.aytobadajoz\.es)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgm|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|edicto|reparcel|parcela|sector|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|modificaci[oó]n|"
    r"orden de ejecuci|segregaci|estudio de detalle|programa de ejecuci|"
    r"urbanizaci[oó]n|actuaci[oó]n singular)",
)
RE_FECHA_DMY = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
RE_SKIP_TIPO = re.compile(
    r"(?i)(control permanente planificable|fiscalizaci[oó]n limitada|ordenanzas municipales)",
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


def _map_tipo_proyecto(tipo_exp: str, nombre: str) -> str:
    blob = f"{tipo_exp} {nombre}"
    if re.search(r"(?i)reparcel", blob):
        return "reparcelación"
    if re.search(r"(?i)estudio de detalle", blob):
        return "estudio de detalle"
    if re.search(r"(?i)programa de ejecuci", blob):
        return "programa de ejecución"
    if re.search(r"(?i)urbanizaci", blob):
        return "proyecto de urbanización"
    if re.search(r"(?i)convenio", blob):
        return "convenio urbanístico"
    if re.search(r"(?i)plan de ordenaci", blob):
        return "planeamiento"
    return "urbanismo"


class BadajozAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA tablón virtual (ANU_ADMON) + web corporativa PGM (documentación)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_urls = [str(u) for u in (self.config.get("tablon_urls") or DEFAULT_TABLON_CAMPO_URLS)]
        self.pgm_pages = [str(u) for u in (self.config.get("pgm_pages") or DEFAULT_PGM_PAGES)]
        self.licencias_info_url = str(self.config.get("licencias_info_url") or DEFAULT_LICENCIAS_INFO)

    def _fetch(self, url: str, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-badajoz/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or ("iso-8859-1" if sede else "utf-8")
            return raw.decode(charset, errors="replace")

    def _abs_sede(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.sede_base}/", href))

    def _abs_wp(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{WP_BASE}/", href))

    def _parse_expedientes(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_EXP_ROW.finditer(html):
            exp_id, anio, codigo, tipo_raw, href, nombre, f_crea, f_pub = m.groups()
            tipo = unescape(tipo_raw).strip()
            rows.append(
                {
                    "exp_id": exp_id,
                    "anio": anio,
                    "codigo": codigo,
                    "tipo": tipo[:120],
                    "nombre": unescape(nombre).strip()[:500],
                    "fecha_creacion": _parse_fecha_dmy(f_crea),
                    "fecha_publicacion": _parse_fecha_dmy(f_pub),
                    "url": self._abs_sede(href),
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for url in self.tablon_urls:
            try:
                html = self._fetch(url, sede=True)
            except urllib.error.URLError:
                continue
            for row in self._parse_expedientes(html):
                if row["exp_id"] not in seen:
                    seen.add(row["exp_id"])
                    out.append(row)
        return out

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
        if RE_SKIP_TIPO.search(exp["tipo"]):
            return None
        blob = f"{exp['tipo']} {exp['nombre']}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None

        rec: dict[str, Any] = {
            "id": _stable_id("proy", exp["exp_id"]),
            "municipio": MUNICIPIO,
            "titulo": exp["nombre"],
            "fecha": exp.get("fecha_publicacion") or exp.get("fecha_creacion"),
            "tipo": _map_tipo_proyecto(exp["tipo"], exp["nombre"]),
            "url": exp["url"],
            "source": "ayuntamiento",
            "expte": f"{exp['anio']}/{exp['codigo']}",
            "origen": "tablon_ANU_ADMON",
            "tipo_expediente": exp["tipo"],
        }
        if docs:
            rec["documentos"] = [d["titulo"] for d in docs[:10]]
            if docs[0].get("url"):
                rec["pdf_url"] = docs[0]["url"]
        return rec

    def _collect_pgm_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.pgm_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_wp(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))[:500]
                if not RE_PROYECTO.search(name) and "PGM" not in name.upper():
                    continue
                rows.append(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": MUNICIPIO,
                        "titulo": name or "Documento PGM Badajoz",
                        "fecha": _parse_fecha_dmy(name),
                        "tipo": "documento PGM",
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": "pgm_web",
                    }
                )
        return rows

    def _licencias_informativas(self) -> list[dict[str, Any]]:
        """El tablón ANU_ADMON no publica licencias de obra; página informativa PGM."""
        return [
            {
                "id": _stable_id("lic", "info-tramites"),
                "fecha_concesion": None,
                "tipo": "información trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias y trámites urbanísticos (PGM / sede)",
                "url": self.licencias_info_url,
                "source": "ayuntamiento",
                "nota": "Sin listado público de licencias concedidas en sede; trámites vía sede electrónica.",
            }
        ]

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
        for exp in self._collect_tablon():
            rec = self._exp_to_licencia(exp)
            if rec:
                rows.append(rec)
        if not rows:
            rows = self._licencias_informativas()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon_ANU_ADMON"}

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
        rows = list(existing.values()) if existing else self._licencias_informativas()
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

        for rec in self._collect_pgm_pdfs():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_ANU_ADMON"),
            "pgm_web": sum(1 for r in rows if r.get("origen") == "pgm_web"),
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
