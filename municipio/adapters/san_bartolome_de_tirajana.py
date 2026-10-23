from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

JOOMLA_BASE = "https://www.maspalomas.com"
SEDE_BASE = "https://sede.maspalomas.com"
EADMIN_BASE = "https://eadmin.maspalomas.com"
MUNICIPIO = "San Bartolomé de Tirajana"
ID_PREFIX = "sbt"

TABLON_EXPOSICION = f"{JOOMLA_BASE}/mnutablonexposicion"

DEFAULT_SEED_PAGES: list[str] = [
    TABLON_EXPOSICION,
    f"{SEDE_BASE}/publico/contenido/PLANGRAL",
    f"{SEDE_BASE}/publico/territorio/informeurbanistico",
    f"{SEDE_BASE}/publico/territorio/cexp",
    f"{SEDE_BASE}/publico/edictos",
    f"{SEDE_BASE}/publico/tablon",
    f"{EADMIN_BASE}/publico/contenido/PGOUSBT01",
    f"{EADMIN_BASE}/publico/contenido/PGOUSBT02",
    f"{EADMIN_BASE}/publico/contenido/PGOUSBT03",
    f"{EADMIN_BASE}/publico/contenido/PGOUSBT04",
    f"{EADMIN_BASE}/publico/contenido/PGOUSBT05",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|"
    r"inicio de obra|obra (?:mayor|menor)|primera utilizaci[oó]n|ocupaci[oó]n de edific)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgo|pgou|pamu|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|planimetr|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza.*urban|exposici[oó]n p[uú]blica|"
    r"calificaci[oó]n|actuaci[oó]n en medio urbano|urbanizaci[oó]n|asentamiento rural|"
    r"n[uú]cleo poblacional|unidad de ejecuci[oó]n)",
)
RE_NOISE = re.compile(
    r"(?i)(reglamento de r[eé]gimen interno|ordenanza fiscal|impuesto sobre el incremento|"
    r"lista de candidatos a jurado|proceso selectivo|comida sobre ruedas|"
    r"promoci[oó]n publicitaria|certificado para viaje|recuperaci[oó]n posesoria.*b[uú]nker)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_TABLON_PDF = re.compile(
    r'href="(/images/stories/documents/TablonAnuncios/ExposicionPublica/[^"]+\.pdf[^"]*)"'
    r'[^>]*title="(EXPEDIENTE[^"]*)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?maspalomas\.com)?/images/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_SEDE_LINK = re.compile(
    r'href="((?:https?://(?:sede|eadmin)\.maspalomas\.com)?/publico/[^"]+)"',
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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"Expte_(\d{4})_", text or "", re.I)
    if m:
        return f"{m.group(1)}-01-01"
    digits = re.sub(r"\D", "", text or "")[:10]
    m = re.search(r"^(\d{4})\d{3,6}$", digits)
    if m:
        return f"{m.group(1)}-01-01"
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _expediente_num(title: str) -> str:
    digits = re.sub(r"\D", "", title or "")
    if len(digits) >= 7:
        return digits[:10]
    return digits or title


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pamu" in b:
        return "PAMU"
    if "plan parcial" in b or " pp " in b:
        return "plan parcial"
    if "plan especial" in b:
        return "plan especial"
    if "pgo" in b or "pgou" in b or "plan general" in b:
        return "PGOU"
    if "urbanizaci" in b:
        return "urbanización"
    if "asentamiento rural" in b:
        return "asentamiento rural"
    if "reparcel" in b:
        return "reparcelación"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "convenio" in b:
        return "convenio urbanístico"
    return "urbanismo"


class SanBartolomeDeTirajanaAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla (tablón exposición) + sede Galileo GIYS (PGOU, territorio, edictos)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or JOOMLA_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.edictos_rss = str(
            self.config.get("edictos_rss") or f"{self.sede_base}/publico/sindicacion/edictos/RSS"
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-san-bartolome-de-tirajana/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return unescape(urllib.parse.urljoin(base or JOOMLA_BASE, href))

    def _collect_tablon_exposicion(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(TABLON_EXPOSICION)
        except urllib.error.URLError:
            return rows
        seen_expte: set[str] = set()
        for m in RE_TABLON_PDF.finditer(html):
            rel_pdf, title_attr = m.group(1), m.group(2)
            expte = _expediente_num(title_attr)
            if not expte or expte in seen_expte:
                continue
            pos = m.end()
            chunk = html[pos : pos + 1200]
            desc = ""
            for desc_m in re.finditer(r"<p[^>]*>(.*?)</p>", chunk, re.S | re.I):
                raw = _strip_html(desc_m.group(1))
                if raw and not re.match(r"(?i)^EXPEDIENTE", raw):
                    desc = raw
                    break
            if not desc:
                desc = unescape(urllib.parse.unquote(Path(rel_pdf).stem.replace("_", " ")))
            blob = f"{expte} {desc} {rel_pdf}"
            if RE_NOISE.search(blob):
                continue
            if not RE_PROYECTO.search(blob):
                continue
            seen_expte.add(expte)
            pdf_url = self._abs_url(rel_pdf)
            rows.append(
                {
                    "titulo": f"EXPEDIENTE {expte}: {desc[:400]}",
                    "fecha": _fecha_from_blob(f"{expte} {rel_pdf} {desc}"),
                    "url": TABLON_EXPOSICION,
                    "pdf_url": pdf_url,
                    "blob": blob,
                    "origen": "joomla_tablon_exposicion",
                    "expediente": expte,
                }
            )
        return rows

    def _collect_edictos_rss(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            xml = self._fetch(self.edictos_rss)
        except urllib.error.URLError:
            return rows
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return rows
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            date_el = item.find("pubDate")
            if title_el is None or link_el is None:
                continue
            title = (title_el.text or "").strip()
            url = (link_el.text or "").strip()
            desc = _strip_html(desc_el.text if desc_el is not None else "")
            blob = f"{title} {desc}"
            if RE_NOISE.search(blob):
                continue
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                continue
            fecha = None
            if date_el is not None and date_el.text:
                try:
                    fecha = datetime.strptime(
                        date_el.text.strip()[:25].replace("Z", "+0000"),
                        "%a, %d %b %Y %H:%M:%S %z",
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    fecha = _fecha_from_blob(date_el.text)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": url,
                    "blob": blob,
                    "origen": "sede_edictos_rss",
                }
            )
        return rows

    def _collect_sede_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            if page_url == TABLON_EXPOSICION:
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<title>([^<]+)", html, re.I)
            title = _strip_html(title_m.group(1) if title_m else page_url.rsplit("/", 1)[-1])
            title = re.sub(r"\s*[-|:].*Sede.*$", "", title, flags=re.I).strip() or page_url
            blob = f"{title} {page_url}"
            if RE_PROYECTO.search(blob) or "PLANGRAL" in page_url or "PGOUSBT" in page_url:
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _fecha_from_blob(html[:3000]),
                        "url": page_url,
                        "blob": f"{blob} PGOU planeamiento",
                        "origen": "sede_contenido",
                    }
                )
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                pdf_blob = f"{title} {name} {pdf}"
                if not RE_PROYECTO.search(pdf_blob):
                    continue
                rows.append(
                    {
                        "titulo": f"{title}: {name}"[:500],
                        "fecha": _fecha_from_blob(f"{name} {pdf}"),
                        "url": page_url,
                        "pdf_url": pdf,
                        "blob": pdf_blob,
                        "origen": "sede_pdf",
                    }
                )
        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        tramites = [
            (f"{self.sede_base}/publico/procedimiento/CPOINST", "Comunicación previa de obras e instalaciones"),
            (
                f"{self.sede_base}/publico/procedimiento/CPPUOEE",
                "Comunicación previa primera utilización y ocupación de edificaciones",
            ),
            (f"{self.sede_base}/publico/territorio/informeurbanistico", "Informe urbanístico (visor sede)"),
            (f"{self.sede_base}/publico/edictos", "Tablón de edictos — sede electrónica"),
            (TABLON_EXPOSICION, "Exposición pública — planeamiento (Joomla)"),
        ]
        rows: list[dict[str, Any]] = []
        for url, titulo in tramites:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                }
            )
        return rows

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if row.get("origen") == "tramite_informativo":
            return row
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and "licencia" not in (row.get("titulo") or "").lower():
            return None
        key = row.get("pdf_url") or row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / edicto",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row.get("pdf_url") or row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", str(key)),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("expediente"):
            rec["expediente"] = row["expediente"]
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _dedupe(self, rows: list[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for row in rows:
            rid = row.get(key)
            if not rid or rid in seen:
                continue
            seen.add(rid)
            out.append(row)
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        raw = self._collect_licencia_tramites()
        for row in self._collect_edictos_rss():
            lic = self._to_licencia(row)
            if lic:
                raw.append(lic)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "joomla_sede_galileo"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        raw: list[dict[str, Any]] = []
        for collector in (
            self._collect_tablon_exposicion,
            self._collect_edictos_rss,
            self._collect_sede_seeds,
        ):
            for row in collector():
                proy = self._to_proyecto(row)
                if proy:
                    raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "joomla_sede_galileo"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
