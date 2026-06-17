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

SEDE_BASE = "https://sede.ayto-torrejon.es"
WEB_BASE = "https://www.ayto-torrejon.es"

TABLON_URB = (
    f"{SEDE_BASE}/portal/tablonVirtual.do?subseccion=TABURB&opc_id=175&ent_id=1&idioma=1"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/concejalias/urbanismo",
    f"{WEB_BASE}/tramites/licencias-y-gestiones-urbanisticas",
]

RE_EXP_ROW = re.compile(
    r"<tr class='Lista2Linea(?:Par|Impar)' id='exp_(\d+)'[^>]*>(.*?)</tr>",
    re.I | re.S,
)
RE_DOC_ROW = re.compile(
    r"id='doc_(\d+)'[^>]*>.*?href='([^']+)'>([^<]+)",
    re.I | re.S,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.ayto-torrejon\.es)?/sites/default/files/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|calificada|inocua|edicto|declaraci[oó]n responsable|"
    r"comunicaci[oó]n previa)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plano|pgou|pgom|convenio|informaci[oó]n p[uú]blica|"
    r"expediente|edicto|normativ|ordenanz|rehabilitaci[oó]n|subvenci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/sites/default/files/(\d{4})-(\d{2})/")


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"torrejon-{prefix}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _cell_text(html: str) -> str:
    t = re.sub(r"<[^>]+>", " ", html)
    return unescape(re.sub(r"\s+", " ", t).strip())


def _licencia_tipo(raw: str) -> str:
    t = (raw or "").strip()
    if re.search(r"(?i)INOCUA", t):
        return "licencia actividad inocua"
    if re.search(r"(?i)CALIFICAD", t):
        return "licencia actividad calificada"
    if re.search(r"(?i)LICENCIA", t):
        return "licencia urbanística"
    return t[:120] or "licencia"


class TorrejonDeArdozAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede Tablón Virtual (TABURB) + PDFs Drupal urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tablon_urb_url = str(self.config.get("tablon_urb_url") or TABLON_URB)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.fetch_details = bool(self.config.get("fetch_expediente_details", True))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.ua = self.config.get("user_agent", "poc-bocm-torrejon/1.0")

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(self.sede_base + "/", href)

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(self.web_base + "/", href)

    def _parse_expediente_row(self, exp_id: str, row_html: str) -> dict[str, Any]:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.I | re.S)
        cells = [_cell_text(td) for td in tds]
        while len(cells) < 7:
            cells.append("")
        anio, codigo, tipo_raw, nombre, fecha_creacion, fecha_publicacion, estado = cells[:7]
        detail_url = (
            f"{self.sede_base}/portal/tablonVirtual.do?"
            f"expId={exp_id}&subseccion=TABURB&opc_id=175&ent_id=1&idioma=1"
        )
        return {
            "exp_id": exp_id,
            "anio": anio,
            "codigo": codigo,
            "tipo_raw": tipo_raw,
            "nombre": nombre[:500],
            "fecha_creacion": _parse_fecha_dmy(fecha_creacion),
            "fecha_publicacion": _parse_fecha_dmy(fecha_publicacion),
            "estado": estado,
            "detail_url": detail_url,
        }

    def _collect_tablon_expedientes(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_urb_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_EXP_ROW.finditer(html):
            rows.append(self._parse_expediente_row(m.group(1), m.group(2)))
        return rows

    def _fetch_expediente_docs(self, detail_url: str) -> list[dict[str, str]]:
        try:
            html = self._fetch(detail_url)
        except urllib.error.URLError:
            return []
        docs: list[dict[str, str]] = []
        for m in RE_DOC_ROW.finditer(html):
            doc_id = m.group(1)
            href = unescape(self._abs_sede(m.group(2)))
            titulo = _cell_text(m.group(3))
            docs.append({"doc_id": doc_id, "url": href, "titulo": titulo})
        return docs

    def _expediente_to_licencia(self, exp: dict[str, Any]) -> dict[str, Any]:
        key = f"{exp['exp_id']}|{exp['codigo']}|{exp['nombre']}"
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": exp.get("fecha_publicacion"),
            "tipo": _licencia_tipo(exp.get("tipo_raw", "")),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": exp.get("nombre"),
            "url": exp.get("detail_url"),
            "source": "ayuntamiento",
            "expte": f"{exp.get('anio')}/{exp.get('codigo')}",
            "origen": "tablon_urb",
        }
        return rec

    def _doc_to_proyecto(self, exp: dict[str, Any], doc: dict[str, str]) -> dict[str, Any]:
        titulo = doc.get("titulo") or exp.get("nombre") or "Documento urbanismo"
        fecha = exp.get("fecha_publicacion") or exp.get("fecha_creacion")
        tipo = "edicto" if re.search(r"(?i)edicto", titulo) else "documento urbanismo"
        return {
            "id": _stable_id("proy", doc.get("doc_id") or doc.get("url", "")),
            "municipio": "Torrejón de Ardoz",
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": tipo,
            "url": exp.get("detail_url"),
            "pdf_url": doc.get("url"),
            "source": "ayuntamiento",
            "expte": f"{exp.get('anio')}/{exp.get('codigo')}",
            "origen": "tablon_urb_detalle",
        }

    def _expediente_to_proyecto(self, exp: dict[str, Any]) -> dict[str, Any]:
        key = f"exp-{exp['exp_id']}"
        return {
            "id": _stable_id("proy", key),
            "municipio": "Torrejón de Ardoz",
            "titulo": exp.get("nombre"),
            "fecha": exp.get("fecha_publicacion") or exp.get("fecha_creacion"),
            "tipo": "expediente urbanismo",
            "url": exp.get("detail_url"),
            "source": "ayuntamiento",
            "expte": f"{exp.get('anio')}/{exp.get('codigo')}",
            "origen": "tablon_urb",
        }

    def _collect_drupal_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_web(m.group(1))
                if pdf in seen:
                    continue
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                blob = f"{name} {pdf}"
                if not RE_PROYECTO.search(blob):
                    continue
                seen.add(pdf)
                rec_id = _stable_id("proy", pdf)
                tipo = "plano oficial" if re.search(r"(?i)plano", name) else "documento urbanismo"
                rows.append(
                    {
                        "id": rec_id,
                        "municipio": "Torrejón de Ardoz",
                        "titulo": name[:500],
                        "fecha": _fecha_from_pdf_url(pdf),
                        "tipo": tipo,
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": page_url,
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
        rows = [self._expediente_to_licencia(exp) for exp in self._collect_tablon_expedientes()]
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon_urb"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in [self._expediente_to_licencia(exp) for exp in self._collect_tablon_expedientes()]:
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

        expedientes = self._collect_tablon_expedientes()
        for exp in expedientes:
            add(self._expediente_to_proyecto(exp))
            if self.fetch_details:
                for doc in self._fetch_expediente_docs(exp["detail_url"]):
                    add(self._doc_to_proyecto(exp, doc))

        for rec in self._collect_drupal_pdfs():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_expedientes": len(expedientes),
            "drupal_pdfs": sum(1 for r in rows if r.get("origen", "").startswith("http://www") or "ayto-torrejon" in str(r.get("origen", ""))),
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
