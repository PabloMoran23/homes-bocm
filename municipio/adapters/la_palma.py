from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

CABILDO_BASE = "https://www.cabildodelapalma.es"
PIOLP_BASE = "https://www.piolp.es"
SEDE_BASE = "https://sedeelectronica.cabildodelapalma.es"
TRANSPARENCIA_BASE = "https://transparencia.cabildodelapalma.es"
MUNICIPIO = "La Palma"
ID_PREFIX = "lapalma"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
)
PLANEAMIENTO_TRANSPARENCIA = (
    f"{TRANSPARENCIA_BASE}/ordenacion-del-territorio/plan-de-ordenacion/"
)

PIOLP_SEED_PAGES: list[str] = [
    f"{PIOLP_BASE}/index.php/plan-insular-de-ordenacion/",
    f"{PIOLP_BASE}/index.php/planes-territoriales-especiales/",
    f"{PIOLP_BASE}/index.php/planes-territoriales-parciales/",
    f"{PIOLP_BASE}/index.php/planes-normas-espacios-naturales-protegidos/",
    (
        f"{PIOLP_BASE}/index.php/planes-de-gestion-de-las-zonas-especiales-de-conservacion-"
        "zec-terrestres-integrantes-de-la-red-natura-2000-en-construccion/"
    ),
    f"{PIOLP_BASE}/index.php/ordenanzas/",
    f"{PIOLP_BASE}/index.php/otros/",
    f"{PIOLP_BASE}/index.php/noticias/",
]

LICENCIA_TRAMITES: list[dict[str, str]] = [
    {
        "titulo": "Licencia de obras del Cabildo Insular de La Palma",
        "url": (
            f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?"
            "APP_CODE=STA&PAGE_CODE=CATALOGO&SEARCH=licencia+obra"
        ),
    },
    {
        "titulo": "Autorización de actividad clasificada (Cabildo)",
        "url": (
            f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?"
            "APP_CODE=STA&PAGE_CODE=CATALOGO&SEARCH=actividad+clasificada"
        ),
    },
    {
        "titulo": "Información pública de planeamiento insular (PIOLP)",
        "url": f"{PIOLP_BASE}/index.php/plan-insular-de-ordenacion/",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|"
    r"certificado urban|cedula urban|c[eé]dula urban|segregaci[oó]n|parcelaci[oó]n|"
    r"pr[oó]rroga de licencia|inicio de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|insular|territorial)|"
    r"pio|piolp|pte|ptp|pgou|pgo|convenio|informaci[oó]n p[uú]blica|expediente|"
    r"proyecto|modificaci[oó]n|reparcel|estudio (?:de detalle|ac[uú]stico|ambiental)|"
    r"memoria|planos|aprobaci[oó]n (?:inicial|definitiva|provisional)|sector|suelo|"
    r"ordenanza(?:s)?|evaluaci[oó]n ambiental|iae|consulta previa|exposici[oó]n p[uú]blica|"
    r"paisaje protegido|zona especial de conservaci[oó]n|zec|red natura|"
    r"instrumento(?:s)? de planificaci[oó]n|ordenaci[oó]n del territorio)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proceso selectivo|empleo p[uú]blico|tribunal calificador|baremaci[oó]n|"
    r"subvenci[oó]n|becas?|bonos? de transporte|convocatoria de pleno|sesi[oó]n plenaria|"
    r"nombramiento|retribuciones|contrato menor|factura electr[oó]nica|"
    r"protecci[oó]n de datos|accesibilidad web|plan de emergencia)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-_/](\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_MEDIA_HREF = re.compile(r'href="(/media/[^"]+\.(?:pdf|odt|docx?)[^"]*)"', re.I)
RE_PLAN_LINE = re.compile(r'Plan:\s*[“"]([^”"\n]+)[”"]', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_title(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


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
    m = re.search(r"(\d{6})-", Path(url or text).name)
    if m:
        s = m.group(1)
        try:
            return datetime(int("20" + s[:2]), int(s[2:4]), int(s[4:6])).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(url or text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(f"{text} {url}") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _xml_date(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    try:
        return datetime(
            int(raw.get("year", 0)),
            int(raw.get("month", 1)),
            int(raw.get("day", 1)),
        ).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _pdf_title(url: str) -> str:
    name = urllib.parse.unquote(Path(url.split("?")[0]).name)
    name = re.sub(r"\.[a-z0-9]+$", "", name, flags=re.I)
    name = name.replace("_", " ").replace("-", " ").replace("%20", " ")
    return re.sub(r"\s+", " ", name).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "plan insular" in b or "piolp" in b or "pio" in b:
        return "plan insular"
    if "plan territorial especial" in b or " pte " in f" {b} ":
        return "plan territorial especial"
    if "plan territorial parcial" in b or " ptp " in f" {b} ":
        return "plan territorial parcial"
    if "plan especial" in b:
        return "plan especial"
    if "modificaci" in b and ("menor" in b or "puntual" in b):
        return "modificación planeamiento"
    if "evaluaci" in b and "ambiental" in b:
        return "evaluación ambiental"
    if "consulta previa" in b:
        return "consulta previa"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b:
        return "ordenanza"
    if "memoria" in b:
        return "memoria planeamiento"
    if re.search(r"planos?|plano", b):
        return "planos planeamiento"
    if "licencia" in b:
        return "licencia publicada"
    return "planeamiento insular"


class LaPalmaAyuntamientoAdapter(AyuntamientoAdapter):
    """Cabildo Insular: piolp.es + transparencia + sede STA tablón (Canarias)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or CABILDO_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.piolp_base = str(self.config.get("piolp_base") or PIOLP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transparencia_base = str(self.config.get("transparencia_base") or TRANSPARENCIA_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or PIOLP_SEED_PAGES)]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-palma/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _collect_piolp_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in self.seed_pages:
            try:
                html = self._fetch(page)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for href in RE_PDF_HREF.findall(html):
                url = href if href.startswith("http") else urllib.parse.urljoin(self.piolp_base, href)
                if url in seen:
                    continue
                seen.add(url)
                titulo = _pdf_title(url)
                rows.append(
                    {
                        "titulo": titulo,
                        "fecha": _fecha_from_blob(titulo, url),
                        "url": url,
                        "origen": "piolp_pdf",
                    }
                )
        return rows

    def _collect_transparencia_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(PLANEAMIENTO_TRANSPARENCIA)
        except (urllib.error.URLError, TimeoutError, OSError):
            return rows
        for href in RE_MEDIA_HREF.findall(html):
            url = urllib.parse.urljoin(self.transparencia_base, href)
            if url in seen:
                continue
            seen.add(url)
            titulo = _pdf_title(url)
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_blob(titulo, url),
                    "url": url,
                    "origen": "transparencia_pdf",
                }
            )
        return rows

    def _tablon_to_record(self, row: dict[str, Any]) -> tuple[str, str, str]:
        desc = str(row.get("descriptionProc") or "").strip()
        extern = str(row.get("externString") or "").strip()
        plan_m = RE_PLAN_LINE.search(desc)
        if plan_m:
            title = plan_m.group(1).strip()
            if extern:
                title = f"{extern}: {title}"
        else:
            title = desc or extern
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        url = f"{self.tablon_url}#dboid={dboid}"
        return title[:500], fecha, url

    def _to_licencia_tramite(self, row: dict[str, str]) -> dict[str, Any]:
        url = row["url"]
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": None,
            "tipo": "trámite informativo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": "sede_tramite",
        }

    def _to_licencia_tablon(self, title: str, fecha: str, url: str) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
            return None
        if RE_EXCLUDE.search(title):
            return None
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha or None,
            "tipo": "licencia / anuncio",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": "sta_tablon",
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = str(row.get("titulo") or "").strip()
        blob = f"{titulo} {row.get('origen', '')}"
        if not titulo or RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or titulo
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
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
        raw: list[dict[str, Any]] = [
            self._to_licencia_tramite(row) for row in LICENCIA_TRAMITES
        ]
        for item in self._collect_tablon():
            title, fecha, url = self._tablon_to_record(item)
            lic = self._to_licencia_tablon(title, fecha, url)
            if lic:
                raw.append(lic)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_piolp"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": result["rows"],
                    "added": max(0, result["rows"] - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        raw: list[dict[str, Any]] = []
        for collector in (
            self._collect_piolp_pdfs,
            self._collect_transparencia_docs,
        ):
            for row in collector():
                proy = self._to_proyecto(row)
                if proy:
                    raw.append(proy)
        for item in self._collect_tablon():
            title, fecha, url = self._tablon_to_record(item)
            proy = self._to_proyecto(
                {"titulo": title, "fecha": fecha or None, "url": url, "origen": "sta_tablon"}
            )
            if proy:
                raw.append(proy)
        rows = self._dedupe(raw)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "piolp_transparencia_sta"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": result["rows"],
                    "added": max(0, result["rows"] - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result
