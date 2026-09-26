from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

SEDE_BASE = "https://humesdemadrid.sedelectronica.es"
CANONICAL_SEDE = "https://humanes.sedelectronica.es"
CANONICAL_WEB = "https://ayto-humanesdemadrid.es"
MUNICIPIO = "Humes de Madrid"
CANONICAL_MUNICIPIO = "Humanes de Madrid"
ID_PREFIX = "humes-de-madrid"

DEFAULT_STATIC_PROYECTOS: list[dict[str, str]] = [
    {
        "url": CANONICAL_SEDE + "/board/",
        "titulo": (
            "Alias BOCM — portal urbanístico en Humanes de Madrid "
            "(sede espublico gestiona)"
        ),
        "fecha": None,
        "tipo": "nota alias municipio",
        "origen": "alias_canonical",
    },
    {
        "url": CANONICAL_WEB + "/menu-concejalias/urbanismo-concejalia/",
        "titulo": "Urbanismo — Ayuntamiento de Humanes de Madrid (municipio INE canónico)",
        "fecha": None,
        "tipo": "urbanismo",
        "origen": "alias_canonical",
    },
]

DEFAULT_LICENCIA_PAGES: list[dict[str, str]] = [
    {
        "url": CANONICAL_WEB + "/menu-concejalias/urbanismo-concejalia/licencias-y-solicitudes/",
        "titulo": "Licencias y solicitudes urbanísticas — Humanes de Madrid",
        "tipo": "trámite informativo",
    },
]


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


class HumesDeMadridAyuntamientoAdapter(AyuntamientoAdapter):
    """
    Alias BOCM sin municipio INE propio. Sede humesdemadrid.sedelectronica.es no operativa.
    Emite referencias estáticas al portal canónico Humanes de Madrid.
    """

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.canonical_sede = str(self.config.get("canonical_sede") or CANONICAL_SEDE).rstrip("/")
        self.canonical_web = str(self.config.get("canonical_web") or CANONICAL_WEB).rstrip("/")
        self.static_proyectos = list(self.config.get("static_proyectos") or DEFAULT_STATIC_PROYECTOS)
        self.licencia_pages = list(self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=30, context=self._ssl_ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _sede_operativa(self) -> bool:
        try:
            html = self._fetch(f"{self.sede_base}/board")
        except urllib.error.URLError:
            return False
        return "indeterminada" not in html.lower()

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.static_proyectos:
            url = str(item.get("url") or self.canonical_sede)
            titulo = str(item.get("titulo") or url)
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": item.get("fecha"),
                    "tipo": item.get("tipo") or "urbanismo",
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": item.get("origen") or "alias_canonical",
                    "nota": f"Municipio canónico INE: {CANONICAL_MUNICIPIO} (slug humanes-de-madrid)",
                    "canonical_municipio": CANONICAL_MUNICIPIO,
                    "canonical_slug": str(self.config.get("canonical_slug") or "humanes-de-madrid"),
                }
            )
        if not self._sede_operativa():
            rows.append(
                {
                    "id": _stable_id("proy", f"{self.sede_base}/unconfigured"),
                    "municipio": MUNICIPIO,
                    "titulo": (
                        "Sede espublico humesdemadrid.sedelectronica.es no configurada "
                        "(Sede Electrónica Indeterminada)"
                    ),
                    "fecha": None,
                    "tipo": "bloqueo portal",
                    "url": f"{self.sede_base}/board",
                    "source": "ayuntamiento",
                    "origen": "sede_indeterminada",
                    "nota": "Subdominio espublico sin entidad vinculada",
                }
            )
        return rows

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.licencia_pages:
            url = str(item.get("url") or self.canonical_web)
            titulo = str(item.get("titulo") or url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": item.get("tipo") or "trámite informativo",
                    "distrito": CANONICAL_MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "alias_canonical",
                    "nota": "Página informativa del municipio canónico; no concesión publicada",
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
        rows = self._collect_licencia_info()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "alias": True}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
        after = result["rows"]
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, after - before),
                    "alias": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_static_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "alias": True,
            "with_geometry": 0,
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
                    "alias": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
