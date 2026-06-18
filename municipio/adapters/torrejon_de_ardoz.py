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

WP_BASE = "https://www.ayto-torrejon.es"
SEDE_BASE = "https://sede.ayto-torrejon.es"
MUNICIPIO = "Torrejón de Ardoz"
ID_PREFIX = "torrejon-de-ardoz"

TABLON_PARAMS = "opc_id=175&ent_id=1&idioma=1"
DEFAULT_TABLON_SUBSECTIONS = ("TABURB", "INFOTAB")
DEFAULT_ORDENANZAS = f"{WP_BASE}/concejalias/urbanismo/ordenanzas-y-normativa"

RE_EXP_ROW = re.compile(
    r"<tr class='Lista2Linea(?:Par|Impar)' id='exp_(\d+)'[^>]*>\s*"
    r"<td>(\d{4})</td>\s*<td>(\d+)</td>\s*<td>([^<]+)</td>"
    r"<td><a[^>]*href='([^']+)'[^>]*>([^<]+)</a></td>\s*"
    r"<td>(\d{2}/\d{2}/\d{4})</td><td>(\d{2}/\d{2}/\d{4})</td>",
    re.I | re.DOTALL,
)
RE_DOC_ROW = re.compile(
    r"id='doc_(\d+)'[^>]*>.*?<a[^>]*href='([^']+)'[^>]*>([^<]+)</a>",
    re.I | re.DOTALL,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.ayto-torrejon\.es)?/sites/default/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|calificada|inocua|declaraci[oó]n responsable|"
    r"comunicaci[oó]n previa|autorizaci[oó]n (?:previa|urban))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|edicto|reparcel|parcela|finca|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|modificaci[oó]n|"
    r"orden de ejecuci|segregaci|rectificaci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
RE_REF_CATASTRAL = re.compile(r"\bRE\s+(\d+)\b", re.I)


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


def _clean_tipo(raw: str) -> str:
    t = unescape(raw or "").strip()
    if t.upper().startswith("URB_"):
        t = t[4:].replace("_", " ").strip()
    return t[:120] or "urbanismo"


class TorrejonDeArdozAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA tablón virtual (urbanismo) + Drupal ordenanzas/planeamiento."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_subsections = tuple(
            self.config.get("tablon_subsections") or DEFAULT_TABLON_SUBSECTIONS
        )
        self.ordenanzas_url = str(self.config.get("ordenanzas_url") or DEFAULT_ORDENANZAS)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-torrejon/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "iso-8859-1"
            return raw.decode(charset, errors="replace")

    def _abs_sede(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.sede_base}/", href))

    def _abs_wp(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{WP_BASE}/", href))

    def _tablon_url(self, subseccion: str) -> str:
        return (
            f"{self.sede_base}/portal/tablonVirtual.do?"
            f"subseccion={subseccion}&{TABLON_PARAMS}"
        )

    def _parse_expedientes(self, html: str, subseccion: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_EXP_ROW.finditer(html):
            exp_id, anio, codigo, tipo_raw, href, nombre, f_crea, f_pub = m.groups()
            nombre = unescape(nombre).strip()
            tipo = _clean_tipo(tipo_raw)
            detail_url = self._abs_sede(href)
            rows.append(
                {
                    "exp_id": exp_id,
                    "anio": anio,
                    "codigo": codigo,
                    "tipo": tipo,
                    "nombre": nombre[:500],
                    "fecha_creacion": _parse_fecha_dmy(f_crea),
                    "fecha_publicacion": _parse_fecha_dmy(f_pub),
                    "url": detail_url,
                    "subseccion": subseccion,
                    "ref_catastral": (
                        RE_REF_CATASTRAL.search(nombre).group(1)
                        if RE_REF_CATASTRAL.search(nombre)
                        else None
                    ),
                }
            )
        return rows

    def _fetch_expediente_docs(self, exp: dict[str, Any]) -> list[dict[str, str]]:
        try:
            html = self._fetch(exp["url"])
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
                html = self._fetch(self._tablon_url(sub))
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
            "ref_catastral": exp.get("ref_catastral"),
        }

    def _exp_to_proyecto(self, exp: dict[str, Any], docs: list[dict[str, str]] | None = None) -> dict[str, Any] | None:
        blob = f"{exp['tipo']} {exp['nombre']}"
        if exp["subseccion"] == "INFOTAB" and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None

        tipo = "urbanismo"
        if re.search(r"(?i)edicto", blob):
            tipo = "edicto"
        elif re.search(r"(?i)plan especial|pgou|planeam", blob):
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

    def _collect_ordenanzas_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.ordenanzas_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf = self._abs_wp(m.group(1))
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))[:500]
            if not RE_PROYECTO.search(name) and "PLANO" not in name.upper():
                continue
            tipo = "documento urbanismo"
            if re.search(r"(?i)plan especial", name):
                tipo = "plan especial"
            elif re.search(r"(?i)pgou|modificaci", name):
                tipo = "PGOU"
            elif re.search(r"(?i)aprob", name):
                tipo = "aprobación planeamiento"
            rows.append(
                {
                    "id": _stable_id("proy", pdf),
                    "municipio": MUNICIPIO,
                    "titulo": name,
                    "fecha": _parse_fecha_dmy(name),
                    "tipo": tipo,
                    "url": self.ordenanzas_url,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "origen": "ordenanzas_normativa",
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
        for exp in self._collect_tablon():
            rec = self._exp_to_licencia(exp)
            if rec:
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon_TABURB"}

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
            docs = self._fetch_expediente_docs(exp) if exp["subseccion"] == "TABURB" else []
            add(self._exp_to_proyecto(exp, docs))

        for rec in self._collect_ordenanzas_pdfs():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon_")),
            "ordenanzas": sum(1 for r in rows if r.get("origen") == "ordenanzas_normativa"),
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
