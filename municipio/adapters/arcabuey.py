from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

SEDE_EPRINSA = "https://sede.eprinsa.es/arcabuey"
SEDE_ESPUBLICO = "https://arcabuey.sedelectronica.es"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
VITUA_URL = (
    "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/"
)
DIPU_TABLON = "https://sede.dipujaen.es/Tablon"
MUNICIPIO = "Arcabuey"
ID_PREFIX = "arcabuey"
INE_CODE = "23002"

DEFAULT_PROYECTO_SEEDS: list[dict[str, str]] = [
    {
        "titulo": "Consulta de planeamiento urbanístico — SITUADIFUSION (Junta de Andalucía)",
        "tipo": "planeamiento",
        "url": SITUA_SEARCH,
        "origen": "situa",
        "nota": "Instrumentos de planeamiento digitalizados por municipio (Jaén → Arcabuey)",
    },
    {
        "titulo": "Visor territorial VITUA — cartografía urbanística regional",
        "tipo": "cartografía urbanística",
        "url": VITUA_URL,
        "origen": "vitua",
        "nota": "Clasificación y calificación del suelo; sin enlace a expedientes del ayuntamiento",
    },
    {
        "titulo": "Tablón de anuncios — Diputación Provincial de Jaén",
        "tipo": "edicto provincial",
        "url": DIPU_TABLON,
        "origen": "dipujaen_tablon",
        "nota": "Edictos provinciales que pueden incluir anuncios de municipios pequeños",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"edicto|boja|bop|aprobaci[oó]n|parcela|suelo|sector|ordenanza)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


class ArcabueyAyuntamientoAdapter(AyuntamientoAdapter):
    """Municipio sin web operativa: sede eprinsa (stub) + espublico (indeterminada) + fuentes regionales."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_EPRINSA)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_eprinsa = str(self.config.get("sede_eprinsa") or SEDE_EPRINSA).rstrip("/")
        self.sede_espublico = str(self.config.get("sede_espublico") or SEDE_ESPUBLICO).rstrip("/")
        self.tablon_eprinsa = str(
            self.config.get("tablon_eprinsa") or f"{self.sede_eprinsa}/tablon-de-edictos"
        )
        self.situa_search = str(self.config.get("situa_search") or SITUA_SEARCH)
        self.vitua_url = str(self.config.get("vitua_url") or VITUA_URL)
        self.dipu_tablon = str(self.config.get("dipu_tablon") or DIPU_TABLON)
        self.proyecto_seeds = list(self.config.get("proyecto_seeds") or DEFAULT_PROYECTO_SEEDS)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, timeout: float = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-arcabuey/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout, context=self._ssl_ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_eprinsa),
                "fecha_concesion": None,
                "tipo": "tablón de edictos (eprinsa)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos — sede eprinsa",
                "url": self.tablon_eprinsa,
                "source": "ayuntamiento",
                "nota": "SPA Ember (wec-bulletins); entidad sin APIs públicas configuradas (404 en apisede)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_eprinsa}/tramites"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede eprinsa",
                "url": f"{self.sede_eprinsa}/tramites",
                "source": "ayuntamiento",
                "nota": "Trámites administrativos vía plataforma eprinsa (sin histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_espublico}/board/"),
                "fecha_concesion": None,
                "tipo": "tablón sede espublico",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica espublico gestiona — tablón",
                "url": f"{self.sede_espublico}/board/",
                "source": "ayuntamiento",
                "nota": "Dominio reservado pero sede no configurada («Sede Electrónica Indeterminada»)",
                "origen": "sede_espublico",
            },
            {
                "id": _stable_id("lic", f"{self.sede_eprinsa}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_eprinsa}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación Cl@ve/certificado; sin listado abierto",
                "origen": "sede_tramite",
            },
        ]

    def _collect_dipu_tablon_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dipu_tablon)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in re.finditer(
            r"<a[^>]+href=\"([^\"]+)\"[^>]*>([^<]{8,300})</a>",
            html,
            re.I,
        ):
            href = m.group(1)
            titulo = _strip_html(m.group(2))
            if not titulo:
                continue
            blob = f"{titulo} {href}"
            if "arcabuey" not in blob.lower() and not (
                RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob)
            ):
                continue
            if "arcabuey" not in blob.lower() and not RE_PROYECTO.search(blob):
                continue
            url = href if href.startswith("http") else f"https://sede.dipujaen.es{href}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": None,
                    "url": url,
                    "blob": blob,
                    "origen": "dipujaen_tablon",
                }
            )
        return rows

    def _seed_to_proyecto(self, seed: dict[str, str]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", seed["url"]),
            "municipio": MUNICIPIO,
            "titulo": seed["titulo"],
            "fecha": None,
            "tipo": seed.get("tipo") or "urbanismo",
            "url": seed["url"],
            "source": "ayuntamiento",
            "origen": seed.get("origen"),
            "nota": seed.get("nota"),
            "ine": INE_CODE,
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": "edicto urbanístico",
            "url": row["url"],
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
        rows = self._collect_licencia_info_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        for seed in self.proyecto_seeds:
            rec = self._seed_to_proyecto(seed)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_dipu_tablon_rows():
            rec = self._tablon_to_proyecto(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "seeds": sum(1 for r in rows if r.get("origen") in ("situa", "vitua", "dipujaen_tablon")),
            "tablon": sum(1 for r in rows if r.get("origen") == "dipujaen_tablon" and "edicto" in (r.get("tipo") or "")),
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
