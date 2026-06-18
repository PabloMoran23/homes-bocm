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

BASE = "https://www.rivasciudad.es"
TABLON_DEFAULT = "https://inscripciones.rivasciudad.es/tablon-inicio/"
PGOU_NORMATIVA = f"{BASE}/geoportal/normativa-urbanistica-vigente/"
PGOU_AVANCE = f"{BASE}/geoportal/avance-pgou/"

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{BASE}/servicio/urbanismo-y-vivienda/2019/12/18/licencias-en-viviendas/862600112947/",
    f"{BASE}/servicio/urbanismo-y-vivienda/2019/12/18/licencias-implantacion-de-actividades-economicas/862600112949/",
    f"{BASE}/tramite/solicitud-de-licencia-de-actividad-autorizacion-previa/",
    (
        f"{BASE}/tramite/licencia-de-obras-en-viviendas-y-otros-usos-no-incluidos-en-dru-de-nueva-planta-o-"
        "que-alteren-el-volumen-edificado-y-obras-en-via-publica/"
    ),
    f"{BASE}/tramite/comunicacion-previa-de-obras/",
    f"{BASE}/tramite/declaracion-responsable-de-obras/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|disciplina urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|estudio (?:ac[uú]stico|ambiental)|"
    r"edicto|modificaci[oó]n puntual|aprobaci[oó]n (?:inicial|definitiva)|"
    r"acuerdo (?:plenario|junta)|orden de ejecuci|segregaci|pgom)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[./-](\d{2})[./-]")
RE_PDF_HREF = re.compile(r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"', re.I)
RE_TABLON_ROW = re.compile(
    r'<tr style="font-size: 10px;" class="([^"]+)">(.*?)</tr>',
    re.I | re.S,
)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"rivas-{prefix}-{h}"


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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _pgou_tipo(name: str) -> str:
    n = name.lower()
    if "informacion" in n or "info" in n:
        return "información pública"
    if "convenio" in n:
        return "convenio urbanístico"
    if "plan" in n or "pgou" in n:
        return "planeamiento"
    if "estudio" in n or "ambiental" in n or "acustic" in n:
        return "estudio ambiental"
    return "documento PGOU"


class RivasVaciamadridAyuntamientoAdapter(AyuntamientoAdapter):
    """Tablón HTML (inscripciones) + PGOU geoportal + trámites informativos."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_DEFAULT)
        self.pgou_pages = [
            str(self.config.get("pgou_normativa_url") or PGOU_NORMATIVA),
            str(self.config.get("pgou_avance_url") or PGOU_AVANCE),
        ]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-rivas/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(BASE, href)

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r"<h1[^>]*>([^<]+)",
            r'<h2[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)',
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = unescape(m.group(1).strip())
                t = re.sub(r"\s*[-|].*Rivas.*$", "", t, flags=re.I).strip()
                if t and len(t) > 3:
                    return t[:500]
        return fallback

    def _extract_pdfs(self, html: str) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_url(m.group(1))
            if "favicon" in u.lower():
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            section = m.group(1).strip()
            body = m.group(2)
            cells = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)
            if len(cells) < 5:
                continue

            title_html = cells[1]
            title_m = re.search(r"<b>\s*([^<]+)", title_html, re.I)
            titulo = _strip_html(title_m.group(1) if title_m else title_html)
            subt = _strip_html(re.sub(r"<b>.*?</b>", "", title_html, flags=re.S))
            if subt and subt not in titulo:
                titulo = f"{titulo}: {subt}"[:500]

            expediente = _strip_html(cells[2])
            procedimiento = _strip_html(cells[3])
            categoria = _strip_html(cells[4]) if len(cells) > 4 else ""
            fecha_raw = _strip_html(cells[5]) if len(cells) > 5 else ""
            fecha = _parse_fecha_dmy(fecha_raw)

            link_m = re.search(r'data-link="([^"]+)"', body)
            doc_url = unescape(link_m.group(1)) if link_m else self.tablon_url

            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente,
                    "procedimiento": procedimiento,
                    "categoria": categoria,
                    "fecha": fecha,
                    "url": doc_url,
                    "section": section,
                    "origen": "tablon",
                }
            )
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row['procedimiento']} {row['categoria']}"
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row['procedimiento']} {row['categoria']}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            if row.get("section") != "Organos-de-gobierno":
                return None
            if not re.search(r"(?i)pleno|junta|acuerdo|urban", blob):
                return None
        tipo = "urbanismo"
        if re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            tipo = "información pública"
        elif re.search(r"(?i)plan (?:parcial|especial)|planeam|pgou", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)acuerdo (?:plenario|junta)", blob):
            tipo = "acuerdo plenario"
        elif re.search(r"(?i)convenio", blob):
            tipo = "convenio"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": "Rivas-Vaciamadrid",
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente"),
            "origen": row.get("origen"),
        }

    def _collect_pgou_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.pgou_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for pdf in self._extract_pdfs(html):
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                rows.append(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": "Rivas-Vaciamadrid",
                        "titulo": name[:500],
                        "fecha": _fecha_from_pdf_url(pdf),
                        "tipo": _pgou_tipo(name),
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": page_url,
                    }
                )
        return rows

    def _collect_licencias_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self.licencia_pages:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            title = self._page_title(html, url.rsplit("/", 2)[-2].replace("-", " "))
            if not RE_LICENCIA.search(title):
                continue
            pdfs = self._extract_pdfs(html)
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
                "nota": "Página informativa de trámite; no concesión publicada en tablón",
                "origen": "tramite_info",
            }
            if pdfs:
                rec["pdf_url"] = pdfs[0]
            rows.append(rec)
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencias_pages():
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
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "tramite_info": sum(1 for r in rows if r.get("origen") == "tramite_info"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencias_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for rec in self._collect_pgou_pdfs():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "pgou": sum(1 for r in rows if "geoportal" in str(r.get("origen", ""))),
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
