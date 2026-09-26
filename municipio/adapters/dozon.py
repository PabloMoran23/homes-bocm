from __future__ import annotations

import hashlib
import http.cookiejar
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

WEB_BASE = "https://www.dozon.gal/web"
SEDE_BASE = "https://dozon.sedelectronica.gal"
MUNICIPIO = "Dozón"
ID_PREFIX = "dozon"
INE = "36016"

DOG_PBM_URL = (
    "https://www.xunta.gal/dog/Publicados/2024/20240131/AnuncioG0691-220124-0003_es.html"
)
DOG_PBM_PDF = (
    "https://www.xunta.gal/dog/Publicados/2024/20240131/AnuncioG0691-220124-0003_es.pdf"
)
SIOTUGA_URB = "https://siotuga.xunta.gal/siotuga/urb?lang=es_ES"
PBA_VISOR = "https://mapas.xunta.gal/visores/pba/"
XUNTA_PARTICIPACION = (
    "https://cmatv.xunta.gal/seccion-tema/c/CMAOT_Territorio_e_urbanismo_Planeamento_urbanistico"
    "?content=SX_Ordenacion_Territorio_Urbanismo/Participacion_publica/seccion.html"
    "&std=Participacion_publica.html"
)

DEFAULT_URBAN_TRAMITES: list[tuple[str, str]] = [
    (
        "Solicitude de Licenza ou Autorización Urbanística",
        f"{SEDE_BASE}/catalog/t/15fabacb-83b1-47d1-b435-508245672051",
    ),
    (
        "Declaración Responsable ou Comunicación en Materia Urbanística",
        f"{SEDE_BASE}/catalog/t/5d383e20-32a5-4fcf-8725-e51c51e83e6a",
    ),
    (
        "Solicitude de Modificación ou Renuncia de Licenza Urbanística",
        f"{SEDE_BASE}/catalog/t/a3c783fb-bb19-4ea3-b40f-0072d69aebae",
    ),
    (
        "Licenza de Actividade (Modificación ou Renuncia)",
        f"{SEDE_BASE}/catalog/t/6a5af5af-b462-4ca9-8062-5ba4c95a4241",
    ),
    (
        "Licenza de Actividades e Espectáculos Públicos",
        f"{SEDE_BASE}/catalog/t/87679048-b42c-47a7-8c33-3d54d162f988",
    ),
]

RE_CATALOG_LINK = re.compile(
    r'href="(https://dozon\.sedelectronica\.gal/catalog/t/[a-f0-9-]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_BOARD_PREVIEW = re.compile(
    r'href="(https://dozon\.sedelectronica\.gal/preview-document/[^"]+)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr>\s*(.*?)\s*</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(
    r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
)
RE_URBAN = re.compile(
    r"(?i)(urban|licen|planeam|obra|territ|actividad|ocupaci|comunicaci[oó]n|declaraci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(plan (?:b[aá]sico|general)|planeam|urban|informaci[oó]n p[uú]blica|"
    r"expediente|pgou|pba|normas subsidiarias|dog)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


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


def _proyecto_tipo(titulo: str) -> str:
    n = titulo.lower()
    if "plan básico municipal" in n or "plan basico municipal" in n:
        return "plan básico municipal"
    if "plan básico autonómico" in n or "pba" in n:
        return "plan básico autonómico"
    if "información pública" in n or "informacion publica" in n:
        return "información pública"
    if "normas subsidiarias" in n:
        return "normas subsidiarias"
    return "planeamiento"


class DozonAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress corporativo + sede espublico gestiona + planeamiento Xunta (SIOTUGA/DOG)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
        )

    def _warm_sede(self) -> None:
        if getattr(self, "_sede_warmed", False):
            return
        try:
            self._fetch(f"{self.sede_base}/info.0", delay=False)
        except urllib.error.URLError:
            pass
        self._sede_warmed = True

    def _fetch(self, url: str, *, delay: bool = True) -> str:
        if delay:
            time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-dozon/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fixed_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Plan básico municipal de Dozón — información pública (DOG 2024-01-31)",
                "fecha": "2024-01-31",
                "url": DOG_PBM_URL,
                "pdf_url": DOG_PBM_PDF,
                "tipo": "plan básico municipal",
                "origen": "dog_xunta",
            },
            {
                "titulo": "Plan Básico Autonómico — Dozón (SIOTUGA, INE 36016)",
                "fecha": None,
                "url": SIOTUGA_URB,
                "tipo": "plan básico autonómico",
                "origen": "siotuga",
            },
            {
                "titulo": "Visor Plan Básico Autonómico — Xunta de Galicia",
                "fecha": None,
                "url": PBA_VISOR,
                "tipo": "visor planeamiento",
                "origen": "xunta_pba",
            },
            {
                "titulo": "Participación pública — planeamiento urbanístico (Consellería)",
                "fecha": None,
                "url": XUNTA_PARTICIPACION,
                "tipo": "información pública",
                "origen": "xunta_participacion",
            },
        ]

    def _seed_tramites(self) -> list[dict[str, Any]]:
        return [
            {"titulo": title, "url": url, "origen": "sede_tramite_seed"}
            for title, url in DEFAULT_URBAN_TRAMITES
        ]

    def _collect_dossier_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(title: str, url: str, origen: str) -> None:
            if url in seen:
                return
            seen.add(url)
            rows.append({"titulo": title, "url": url, "origen": origen})

        for item in self._seed_tramites():
            add(item["titulo"], item["url"], item["origen"])

        self._warm_sede()
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return rows
        for m in RE_CATALOG_LINK.finditer(html):
            url, title = m.group(1), unescape(m.group(2).strip())
            if not RE_URBAN.search(title):
                continue
            add(title, url, "sede_tramite")
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        self._warm_sede()
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for preview in RE_BOARD_PREVIEW.findall(html):
            rows.append(
                {
                    "titulo": "Documento tablón de anuncios",
                    "url": preview,
                    "origen": "sede_board",
                }
            )
        for row_html in RE_BOARD_ROW.findall(html):
            if "preview-document" not in row_html and "AdvertisementBoardListPanel" not in row_html:
                continue
            cells = {
                unescape(k): _strip_html(v)
                for k, v in RE_BOARD_CELL.findall(row_html)
            }
            title = cells.get("Título") or cells.get("Titulo") or cells.get("Documento") or ""
            doc_url = None
            pm = RE_BOARD_PREVIEW.search(row_html)
            if pm:
                doc_url = pm.group(1)
            blob = " ".join(cells.values())
            if not title and not doc_url:
                continue
            if title and not RE_PROYECTO.search(title) and not RE_PROYECTO.search(blob):
                continue
            fecha = _parse_fecha_dmy(blob) or _parse_fecha_dmy(cells.get("Data", ""))
            rows.append(
                {
                    "titulo": title or "Anuncio tablón urbanismo",
                    "fecha": fecha,
                    "url": doc_url or self.board_url,
                    "origen": "sede_board",
                }
            )
        return rows

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
        return {
            "id": _stable_id("proy", url + titulo),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
        return {
            "id": _stable_id("lic", url + titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": url,
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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_dossier_tramites():
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites_info"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_dossier_tramites():
            existing[self._to_licencia(item)["id"]] = self._to_licencia(item)
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, len(rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._fixed_proyectos():
            add(self._to_proyecto(item))
        for item in self._collect_board():
            add(self._to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "fixed": sum(1 for r in rows if r.get("origen", "").startswith(("dog", "siotuga", "xunta"))),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
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
