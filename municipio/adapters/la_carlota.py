from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://lacarlota.es"
PGOU_URL = f"{BASE}/pgou-de-la-carlota/"
SEDE_BASE = "https://sede.eprinsa.es/carlota"
TABLON_URL = f"{SEDE_BASE}/tablon-de-edictos"
MUNICIPIO = "La Carlota"
ID_PREFIX = "la-carlota"

RE_BOJA_DATE = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_CSV = re.compile(r"CSV\s+([A-Z0-9 ]+)", re.I)
RE_SKIP_LINE = re.compile(
    r"(?i)^(pgou de la carlota|accesibilidad|pol[ií]tica de|mapa web|avda\.)",
)
RE_URBAN_LINE = re.compile(
    r"(?i)(pgou|plan parcial|boja|sector|ordenaci[oó]n|ordenanza|cat[aá]logo|"
    r"planos|n[uú]cleo principal|subs|subo|habitat|fuencubierta|pinedas|garabato|"
    r"quintana|rinconcillo|arrecife|monte alto|la paz|txref)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _fecha_from_boja(text: str) -> str | None:
    m = RE_BOJA_DATE.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _proyecto_tipo(title: str) -> str:
    blob = (title or "").lower()
    if "plan parcial" in blob:
        return "plan parcial"
    if "boja" in blob and "pgou" in blob:
        return "PGOU"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "catálogo" in blob or "catalogo" in blob:
        return "planeamiento"
    if "planos" in blob or "ordenación" in blob or "ordenacion" in blob:
        return "planeamiento"
    if "sector" in blob or "subs" in blob or "subo" in blob:
        return "modificación planeamiento"
    if "pgou" in blob:
        return "PGOU"
    return "urbanismo"


def _proyecto_url(title: str) -> str:
    if re.search(r"(?i)\bboja\b", title):
        return "https://www.juntadeandalucia.es/boja/"
    if RE_CSV.search(title):
        return f"{SEDE_BASE}/validacion-de-documentos"
    return PGOU_URL


class LaCarlotaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (PGOU estático) + sede eprinsa/Diputación Córdoba (tablón SPA)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-carlota/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _collect_pgou_lines(self) -> list[str]:
        try:
            html = self._fetch(self.pgou_url)
        except urllib.error.URLError:
            return []

        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "\n", text)
        text = unescape(text)
        lines: list[str] = []
        seen: set[str] = set()
        for raw in text.split("\n"):
            line = re.sub(r"\s+", " ", raw).strip()
            if len(line) < 12 or line in seen:
                continue
            if RE_SKIP_LINE.search(line):
                continue
            if not RE_URBAN_LINE.search(line):
                continue
            seen.add(line)
            lines.append(line)
        return lines

    def _pgou_to_proyecto(self, line: str) -> dict[str, Any]:
        csv_m = RE_CSV.search(line)
        return {
            "id": _stable_id("proy", line),
            "municipio": MUNICIPIO,
            "titulo": line[:500],
            "fecha": _fecha_from_boja(line),
            "tipo": _proyecto_tipo(line),
            "url": _proyecto_url(line),
            "source": "ayuntamiento",
            "origen": "web_pgou",
            "csv": csv_m.group(1).strip() if csv_m else None,
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos — licencias y urbanismo",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Sede eprinsa (Diputación Córdoba); listado vía web component con token de sesión",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/tramites"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/tramites",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin histórico público estructurado)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación Cl@ve/certificado; no hay listado abierto",
                "origen": "sede_tramite",
            },
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
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": len(rows),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": 0, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = [self._pgou_to_proyecto(line) for line in self._collect_pgou_lines()]
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pgou": len(rows),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
