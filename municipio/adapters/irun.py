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

WEB_BASE = "https://www.irun.org"
MUNICIPIO = "Irun"
ID_PREFIX = "irun"

EXPOSICIONES_URL = (
    f"{WEB_BASE}/es/urbanismo-vivienda/exposiciones-publicas/"
    "exposiciones-publicas-de-expedientes-urbanisticos"
)
APROBADO_URL = (
    f"{WEB_BASE}/es/urbanismo-vivienda/planes-ordenacion-ejecucion-gestion/"
    "planeamiento-urbanistico-aprobado-definitivamente"
)
URBANISMO_URL = f"{WEB_BASE}/es/urbanismo-vivienda"
TABLON_URL = f"{WEB_BASE}/es/sede/tablon-de-edictos-y-anuncios/tablon-anuncios-digital"

DEFAULT_LIST_PAGES = (EXPOSICIONES_URL, APROBADO_URL)

RE_OBRA_LINK = re.compile(
    r'href="(/es/obras/[^"]+\?idob=(\d+))"[^>]*>([^<]+)</a>',
    re.I,
)
RE_BOG_PDF = re.compile(
    r"https://egoitza\.gipuzkoa\.eus/gao-bog/castell/bog/(\d{4})/(\d{2})/(\d{2})/",
    re.I,
)
RE_DETAIL_ROW = re.compile(
    r'<th[^>]*scope="row"[^>]*>([^<]+)</th>\s*<td[^>]*>(.*?)</td>',
    re.S | re.I,
)
RE_TABLON_ROW = re.compile(
    r'<tr>\s*<th scope="row"[^>]*>(.*?)</th>\s*'
    r'<td[^>]*>(\d{2}-\d{2}-\d{4})</td>\s*'
    r'<td[^>]*>(\d{2}-\d{2}-\d{4})</td>',
    re.S | re.I,
)
RE_TRAMITE = re.compile(
    r'href="(/es/tramites/[^"]+\?idt=\d+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:menor|mayor)|demolici[oó]n|"
    r"primera ocupaci[oó]n|parcelaci[oó]n|relleno)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|urbanizaci[oó]n|programa de actuaci[oó]n|expropiaci[oó]n|"
    r"ordenanza|zona de bajas|plan zonal)",
)
RE_FECHA_DMY_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY_SLASH, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if not m:
            continue
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _fecha_from_bog_url(url: str) -> str | None:
    m = RE_BOG_PDF.search(url or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _iso_from_year(text: str) -> str | None:
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2035
    ]
    return f"{max(years)}-01-01" if years else None


def _tipo_proyecto(titulo: str, instrumento: str | None = None) -> str:
    blob = f"{titulo} {instrumento or ''}".lower()
    if "plan general" in blob or "pgou" in blob:
        return "PGOU"
    if "plan especial" in blob:
        return "plan especial"
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "programa de actuaci" in blob or "pau" in blob:
        return "PAU"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "convenio" in blob:
        return "convenio"
    if "reparcel" in blob:
        return "reparcelación"
    if "urbanizaci" in blob:
        return "proyecto de urbanización"
    if "expropiaci" in blob:
        return "expropiación"
    if "ordenanza" in blob or "zona de bajas" in blob:
        return "ordenanza"
    if instrumento:
        return instrumento[:80]
    return "urbanismo"


class IrunAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla irun.org: tablas obras urbanísticas + detalle idob + tablón SAC + trámites."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.list_pages = list(self.config.get("list_pages") or DEFAULT_LIST_PAGES)
        self.enrich_details = bool(self.config.get("enrich_details", True))
        self._ua = str(self.config.get("user_agent", "poc-bocm-irun/1.0"))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua})
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return urllib.parse.urljoin(self.web_base + "/", path.lstrip("/"))

    def _collect_obras_index(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for page_url in self.list_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            origen = "exposicion" if "exposiciones" in page_url else "aprobado"
            for m in RE_OBRA_LINK.finditer(html):
                path, idob, titulo = m.group(1), m.group(2), unescape(m.group(3).strip())
                if idob in index:
                    continue
                chunk = html[m.start() : m.start() + 1200]
                bog_m = RE_BOG_PDF.search(chunk)
                index[idob] = {
                    "idob": idob,
                    "titulo": titulo[:500],
                    "url": self._abs(path),
                    "origen_lista": origen,
                    "bog_url": bog_m.group(0) if bog_m else None,
                }
        return index

    def _parse_obra_detail(self, html: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for m in RE_DETAIL_ROW.finditer(html):
            key = _strip_html(m.group(1)).lower()
            val = _strip_html(m.group(2))
            if key and val:
                fields[key] = val
        return fields

    def _obra_to_proyecto(self, row: dict[str, Any], fields: dict[str, str]) -> dict[str, Any]:
        titulo = row["titulo"]
        fecha = (
            _parse_fecha_dmy(fields.get("fecha de publicación b.o.g.", ""))
            or _parse_fecha_dmy(fields.get("fecha de tramitación", ""))
            or _fecha_from_bog_url(fields.get("url boletín", "") or row.get("bog_url") or "")
            or _fecha_from_bog_url(row.get("bog_url") or "")
            or _iso_from_year(titulo)
        )
        instrumento = fields.get("instrumento")
        url = row["url"]
        if fields.get("url boletín", "").startswith("http"):
            url = fields["url boletín"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"obra-{row['idob']}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": fecha,
            "tipo": _tipo_proyecto(titulo, instrumento),
            "url": url,
            "source": "ayuntamiento",
            "idob": row["idob"],
            "origen": row.get("origen_lista"),
        }
        if fields.get("estado tramitación"):
            rec["estado"] = fields["estado tramitación"][:200]
        if fields.get("ámbito"):
            rec["ambito"] = fields["ámbito"][:200]
        return rec

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(URBANISMO_URL)
        except urllib.error.URLError:
            return rows
        seen: set[str] = set()
        for m in RE_TRAMITE.finditer(html):
            path, label = m.group(1), unescape(m.group(2).strip())
            if not RE_LICENCIA.search(label):
                continue
            url = self._abs(path)
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": label[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramite_informativo",
                    "nota": "Página informativa; sin listado público de concesiones",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            desc = _strip_html(m.group(1))[:500]
            if not desc or not RE_LICENCIA.search(desc):
                continue
            fecha_ini = _parse_fecha_dmy(m.group(2))
            pdf_m = re.search(r'href="(https://sac\.irun\.org/[^"]+)"', m.group(1), re.I)
            url = pdf_m.group(1) if pdf_m else TABLON_URL
            rows.append(
                {
                    "descripcion": desc,
                    "fecha": fecha_ini,
                    "url": url,
                    "origen": "tablon_digital",
                }
            )
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        desc = row["descripcion"]
        return {
            "id": _stable_id("lic", f"tablon-{desc[:120]}-{row.get('fecha') or ''}"),
            "fecha_concesion": row.get("fecha"),
            "tipo": "edicto tablón",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": desc[:500],
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
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "tramite_informativo"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_digital"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats["rows"]
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        index = self._collect_obras_index()
        rows: list[dict[str, Any]] = []
        for idob, meta in sorted(index.items(), key=lambda x: x[0]):
            fields: dict[str, str] = {}
            if self.enrich_details:
                try:
                    fields = self._parse_obra_detail(self._fetch(meta["url"]))
                except urllib.error.URLError:
                    fields = {}
            rows.append(self._obra_to_proyecto(meta, fields))
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "exposicion": sum(1 for r in rows if r.get("origen") == "exposicion"),
            "aprobado": sum(1 for r in rows if r.get("origen") == "aprobado"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
