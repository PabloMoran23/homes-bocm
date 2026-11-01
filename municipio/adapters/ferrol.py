from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.ferrol.gal"
SEDE_CIVIDAS = "https://www.ferrol.gal:8443/cividas-core-web-ferrol/"
MUNICIPIO = "Ferrol"
ID_PREFIX = "ferrol"
INE = "15036"
WAYBACK_PREFIX = "https://web.archive.org/web/2024/"

PLANEAMIENTO_LIST = f"{WEB_BASE}/Sede/PlaneamentoUrbanistico"
TRAMITES_LIST = f"{WEB_BASE}/Sede/Tramites"
SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_QUERY_DOC = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"
CARTOGRAFIA_SEDE = f"{WEB_BASE}/Sede"
ABS_ATLAS = "http://www.ferrol.es/absatlas/absmapas/ui/loc/ctrl_avanzado.aspx?IDIOMA=es-ES&TEMA=normal"

RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(licen|comunicaci[oó]n previa|declaraci[oó]n responsable|certificado urban|"
    r"primeira ocupaci|primeira ocupaci|obra menor|obra maior|edificaci|demolici|"
    r"licenza urban|cp-\d+)",
)
RE_SKIP_LIC = re.compile(r"(?i)(animais potencialmente perigosos|inspecci[oó]n t[eé]cnica de edificios)")
RE_PROYECTO = re.compile(
    r"(?i)(plan|planeam|pgom|pgou|peri|pol[ií]gono|sector|estudo de detalle|"
    r"modificaci[oó]n|informaci[oó]n p[uú]blica|equidistribuci|reparcel|convenio)",
)


def _wayback_url(url: str) -> str:
    return f"{WAYBACK_PREFIX}{url}"


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


def _proyecto_tipo(titulo: str, figura: str | None = None) -> str:
    blob = f"{titulo} {figura or ''}".lower()
    if "peri" in blob:
        return "PERI"
    if "plan parcial" in blob or "polígono" in blob or "poligono" in blob:
        return "plan parcial"
    if "estudo de detalle" in blob or "estudio de detalle" in blob:
        return "estudio de detalle"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "plan xeral" in blob or "pgom" in blob or "pgou" in blob:
        return "plan general"
    if "sector" in blob or "sectoriz" in blob:
        return "planeamiento de desarrollo"
    if "equidistrib" in blob:
        return "equidistribución"
    return figura or "expediente urbanístico"


class FerrolAyuntamientoAdapter(AyuntamientoAdapter):
    """Ferrol: tabla Sede/PlaneamentoUrbanistico + SIOTUGA (15036) + trámites informativos."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.max_siotuga_des = int(self.config.get("max_siotuga_desarrollo", 80))
        self._prefer_wayback = bool(self.config.get("prefer_wayback", False))
        self._direct_blocked = self._prefer_wayback
        self._direct_timeout_s = float(self.config.get("direct_timeout_s", 12))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        self._siotuga_token: str | None = None

    def _fetch(self, url: str, *, data: bytes | None = None, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-ferrol/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        candidates: list[str] = []
        if not self._direct_blocked:
            candidates.append(url)
        if self.config.get("wayback_fallback", True):
            candidates.append(_wayback_url(url))
        last_err: urllib.error.URLError | None = None
        for attempt_url in candidates:
            timeout = self._direct_timeout_s if attempt_url == url else 75.0
            ctx = self._ssl_ctx if (use_sede_ssl or ":8443" in attempt_url) else None
            req = urllib.request.Request(attempt_url, data=data, headers=headers)
            try:
                if ctx is not None:
                    resp_cm = urllib.request.urlopen(req, timeout=timeout, context=ctx)
                else:
                    resp_cm = self._opener.open(req, timeout=timeout)
                with resp_cm as resp:
                    enc = resp.headers.get_content_charset() or "utf-8"
                    return resp.read().decode(enc, errors="replace")
            except urllib.error.URLError as exc:
                last_err = exc
                if attempt_url == url:
                    self._direct_blocked = True
                continue
        raise last_err or urllib.error.URLError("fetch failed")

    def _get_siotuga_token(self) -> str:
        if self._siotuga_token:
            return self._siotuga_token
        html = self._fetch(SIOTUGA_INVENTARIO)
        m = re.search(r"name=['\"]token['\"][^>]*value=['\"]([^'\"]+)['\"]", html, re.I)
        if not m:
            m = re.search(r"id=['\"]token['\"][^>]*value=['\"]([^'\"]+)['\"]", html, re.I)
        if not m:
            raise RuntimeError("SIOTUGA: no se encontró token de sesión")
        self._siotuga_token = m.group(1)
        return self._siotuga_token

    def _siotuga_query(self, idclase: int) -> list[dict[str, Any]]:
        token = self._get_siotuga_token()
        data = f"id={INE}&token={token}&idclase={idclase}".encode()
        raw = self._fetch(SIOTUGA_QUERY_DOC, data=data)
        try:
            docs = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return docs if isinstance(docs, list) else []

    def _collect_siotuga(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for doc in self._siotuga_query(14):
            rows.append(
                {
                    "titulo": doc.get("docnome") or "Plan xeral",
                    "fecha": doc.get("fechaaddef"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo(str(doc.get("docnome") or ""), str(doc.get("figura") or "")),
                    "origen": "siotuga_pg",
                    "siotuga_id": doc.get("id"),
                    "figura": doc.get("figura"),
                }
            )
        for doc in self._siotuga_query(13)[: self.max_siotuga_des]:
            rows.append(
                {
                    "titulo": doc.get("docnome") or "Planeamento desenvolvemento",
                    "fecha": doc.get("fechaaddef"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo(str(doc.get("docnome") or ""), str(doc.get("figura") or "")),
                    "origen": "siotuga_des",
                    "siotuga_id": doc.get("id"),
                    "figura": doc.get("figura"),
                }
            )
        return rows

    def _collect_planeamiento_sede(self) -> list[dict[str, Any]]:
        html = self._fetch(PLANEAMIENTO_LIST)
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
            if "PlaneamentoUrbanisticoAmpliar" not in tr:
                continue
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.I | re.S)
            if len(tds) < 3:
                continue
            cells = [_strip_html(td) for td in tds]
            fecha = _parse_fecha_dmy(cells[0]) if cells else None
            figura = cells[1] if len(cells) > 1 else ""
            titulo = cells[2] if len(cells) > 2 else ""
            if not titulo:
                continue
            am = re.search(r"PlaneamentoUrbanisticoAmpliar/(\d+)", tr)
            detail = (
                f"{self.web_base}/Sede/PlaneamentoUrbanisticoAmpliar/{am.group(1)}"
                if am
                else PLANEAMIENTO_LIST
            )
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": detail,
                    "tipo": _proyecto_tipo(titulo, figura),
                    "origen": "sede_planeamiento",
                    "figura": figura or None,
                    "planeamiento_id": am.group(1) if am else None,
                }
            )
        return rows

    def _collect_tramites_licencias(self) -> list[dict[str, Any]]:
        html = self._fetch(TRAMITES_LIST)
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
            blob = _strip_html(tr)
            if not RE_LICENCIA.search(blob):
                continue
            if RE_SKIP_LIC.search(blob):
                continue
            am = re.search(r"TramitesAmpliar/(\d+)", tr)
            if not am:
                continue
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.I | re.S)
            titulo = _strip_html(tds[0]) if tds else blob[:200]
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": None,
                    "url": f"{self.web_base}/Sede/TramitesAmpliar/{am.group(1)}",
                    "tipo": "trámite licencias urbanísticas",
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _fixed_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Inventario municipal planeamiento — SIOTUGA (INE 15036)",
                "fecha": None,
                "url": SIOTUGA_INVENTARIO,
                "tipo": "inventario planeamiento",
                "origen": "siotuga_inventario",
            },
            {
                "titulo": "Cartografía dixital — Sede electrónica Ferrol",
                "fecha": None,
                "url": CARTOGRAFIA_SEDE,
                "tipo": "cartografía municipal",
                "origen": "sede_cartografia",
            },
            {
                "titulo": "Visor cartográfico municipal (AbsAtlas)",
                "fecha": None,
                "url": ABS_ATLAS,
                "tipo": "visor cartografía",
                "origen": "abs_atlas",
            },
            {
                "titulo": "Sede electrónica Cividas — trámites telemáticos",
                "fecha": None,
                "url": SEDE_CIVIDAS,
                "tipo": "sede telemática",
                "origen": "cividas_sede",
            },
        ]

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.web_base
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{url}|{titulo}|{row.get('planeamiento_id','')}|{row.get('siotuga_id','')}"),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(titulo, row.get("figura")),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("siotuga_id"):
            rec["siotuga_doc_id"] = row["siotuga_id"]
        if row.get("planeamiento_id"):
            rec["planeamiento_id"] = row["planeamiento_id"]
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.web_base
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
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_tramites_licencias():
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites_info"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        sources.extend(self._fixed_seeds())
        sources.extend(self._collect_siotuga())
        sources.extend(self._collect_planeamiento_sede())
        for item in sources:
            if item.get("origen") == "sede_planeamiento" and not RE_PROYECTO.search(item.get("titulo", "")):
                continue
            rec = self._to_proyecto(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
            "sede_planeamiento": sum(1 for r in rows if r.get("origen") == "sede_planeamiento"),
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
