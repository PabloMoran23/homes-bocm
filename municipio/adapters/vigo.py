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

SEDE_BASE = "https://sede.vigo.org"
TABOLEIRO = f"{SEDE_BASE}/expedientes/taboleiro"
TRAMITES_SEARCH = f"{SEDE_BASE}/expedientes/tramites/tramitesbusqueda.jsp"
MUNICIPIO = "Vigo"
ID_PREFIX = "vigo"

EXPOSICION_ENTS: list[tuple[int, str]] = [
    (0, "convenio urbanístico"),
    (1, "operación jurídica complementaria"),
    (2, "ordenanza urbanística"),
    (5, "expediente urbanístico"),
    (6, "planeamiento"),
]

DEFAULT_LICENCIA_QUERIES: list[str] = [
    "obra",
    "licencia obra",
    "comunicación previa",
]

RE_TRAMITE_LINK = re.compile(
    r'<a href="tramite\.jsp\?id_tramite=(\d+)&amp;lang=es"\s*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA_TRAMITE = re.compile(
    r"(?i)(licencia|licenza|permiso de obra|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"primera ocupaci[oó]n|fuera de ordenaci[oó]n|parcelamiento|infracci[oó]n urban)",
)
RE_SKIP_TRAMITE = re.compile(
    r"(?i)(representante|autoliquidaci[oó]n|dominio p[uú]blico|gran cala|canalizaciones|aver[ií]as)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|convenio|expropi|ordenanza|pxou|pgou|parcel|reparcel|modificaci[oó]n|"
    r"revisi[oó]n|estatuto|pol[ií]gono|zona \d)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).replace("\xa0", " ").strip()


def _proyecto_tipo(titulo: str, categoria: str) -> str:
    blob = f"{titulo} {categoria}".lower()
    if "convenio" in blob:
        return "convenio urbanístico"
    if "expropi" in blob:
        return "expropiación"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "pxou" in blob or "pgou" in blob or "plan general" in blob:
        return "plan general"
    if "parcel" in blob or "reparcel" in blob:
        return "parcelación"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "operaci" in blob and "jur" in blob:
        return "operación jurídica complementaria"
    return categoria or "expediente urbanístico"


class VigoAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede Vigo (taboleiro exposición pública Xerencia Urbanismo) + trámites OB/CP."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.licencia_queries = [str(q) for q in (self.config.get("licencia_queries") or DEFAULT_LICENCIA_QUERIES)]
        self._cj = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cj))

    def _fetch(self, url: str, *, encoding: str = "latin-1") -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-vigo/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            return resp.read().decode(encoding, errors="replace")

    def _warm_taboleiro(self) -> None:
        self._fetch(f"{TABOLEIRO}/exposicion.jsp?id=1&lang=es")

    def _parse_exposicion_rows(self, html: str, categoria: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
            if "fichero_exposicion" not in row:
                continue
            links = re.findall(
                r'fichero_exposicion\.jsp\?id_archivo=(\d+)[^>]*>([^<]+)',
                row,
                re.I,
            )
            if not links:
                continue
            id_archivo = links[0][0]
            expediente = _clean(links[0][1])
            titulo = _clean(links[1][1]) if len(links) > 1 else expediente
            distrito = _clean(links[2][1]) if len(links) > 2 else None
            if not RE_PROYECTO.search(f"{titulo} {categoria}") and categoria == "expediente urbanístico":
                if not RE_PROYECTO.search(titulo):
                    continue
            url = f"{TABOLEIRO}/fichero_exposicion.jsp?id_archivo={id_archivo}&lang=es"
            key = f"exp:{id_archivo}:{expediente}"
            out.append(
                {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": None,
                    "tipo": _proyecto_tipo(titulo, categoria),
                    "url": url,
                    "source": "ayuntamiento",
                    "expediente": expediente,
                    "distrito": distrito,
                    "categoria_taboleiro": categoria,
                    "id_archivo": id_archivo,
                }
            )
        return out

    def _collect_exposicion_proyectos(self) -> list[dict[str, Any]]:
        self._warm_taboleiro()
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for ent, categoria in EXPOSICION_ENTS:
            url = f"{TABOLEIRO}/exposicion_listado.jsp?epi=1&ent={ent}&id=1&lang=es"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            for rec in self._parse_exposicion_rows(html, categoria):
                if rec["id"] in seen:
                    continue
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_tramite_licencias(self) -> list[dict[str, Any]]:
        seen_ids: set[str] = set()
        tramites: dict[str, str] = {}
        for query in self.licencia_queries:
            qs = urllib.parse.urlencode({"q": query, "buscar": "SI", "lang": "es"})
            try:
                html = self._fetch(f"{TRAMITES_SEARCH}?{qs}")
            except urllib.error.URLError:
                continue
            for m in RE_TRAMITE_LINK.finditer(html):
                tid, title = m.group(1), _clean(m.group(2))
                if RE_SKIP_TRAMITE.search(title):
                    continue
                if not RE_LICENCIA_TRAMITE.search(title):
                    continue
                tramites[tid] = title
        rows: list[dict[str, Any]] = []
        for tid, title in sorted(tramites.items(), key=lambda x: int(x[0])):
            url = f"{SEDE_BASE}/expedientes/tramites/tramite.jsp?id_tramite={tid}&lang=es"
            rec_id = _stable_id("lic", url)
            if rec_id in seen_ids:
                continue
            seen_ids.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "tramite_id": tid,
                    "nota": "Procedimiento informativo; sin listado público de concesiones",
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_exposicion_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok" if rows else "empty"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_exposicion_proyectos():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "added": len(rows) - before},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": len(rows) - before, "status": "ok"}

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_tramite_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_tramite_licencias():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "added": len(rows) - before},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": len(rows) - before, "status": "ok"}
