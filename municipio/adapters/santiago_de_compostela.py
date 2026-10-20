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

SEDE_BASE = "https://sede.santiagodecompostela.gal"
SIOTUGA_INVENTARIO = (
    "https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15078&lang=es_ES"
)
SIOTUGA_URB = "https://siotuga.xunta.gal/siotuga/urb?lang=es_ES"
MUNICIPIO = "Santiago de Compostela"
ID_PREFIX = "santiago-de-compostela"
INE_CONCELLO = "15078"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES"
URBANISMO_KEYWORD = "AMB_14"

DOG_PERI12_URL = (
    "https://www.xunta.gal/dog/Publicados/2025/20250421/"
    "AnuncioL178-270325-0001_es.html"
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licenz|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n previa|primera ocupaci[oó]n|"
    r"licenza de obra|licenza para)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pxom|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|peri[-\s]?\d+|"
    r"proyecto de (?:urbaniz|actuaci)|estudio de detalle|modificaci[oó]n|sunp|"
    r"aprobaci[oó]n (?:inicial|definitiva)|reparcel|actuaci[oó]n urban|equidistribuci[oó]n)",
)
RE_EXCLUDE_PROY = re.compile(
    r"(?i)(recursos humanos|proceso selectivo|lista de (?:agarda|reserva|espera)|"
    r"convocatoria.*posto|comisi[oó]n de servizos|padr[oó]n das taxas|suplemento de cr[eé]dito)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_EXPEDIENTE = re.compile(r"\b(20\d{2}/\d{5,6}[A-Z]?)\b")


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


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(
            int(obj["year"]),
            int(obj["month"]),
            int(obj["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _proyecto_tipo(section: str, title: str) -> str:
    blob = f"{section} {title}".lower()
    if "peri" in blob or "reforma interior" in blob:
        return "PERI / plan especial"
    if "pxom" in blob or "pgom" in blob or "plan xeral" in blob or "plan general" in blob:
        return "PGOM/PXOM"
    if "sunp" in blob or "sectoriz" in blob:
        return "plan parcial / sectorización"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "equidistribuci" in blob:
        return "equidistribución urbanística"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "exposici" in blob or "informaci" in blob:
        return "información pública"
    if "planeam" in blob or "urban" in blob:
        return "planeamiento"
    return section or "urbanismo"


class SantiagoDeCompostelaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA (TAO) tablón + catálogo urbanismo; planeamiento SIOTUGA (Xunta)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.siotuga_inventario = str(
            self.config.get("siotuga_inventario") or SIOTUGA_INVENTARIO
        )
        self.max_siotuga_plans = int(self.config.get("max_siotuga_plans", 400))
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-santiago-de-compostela/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _post_json(self, url: str, data: dict[str, str]) -> Any:
        time.sleep(self.delay_s)
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-santiago-de-compostela/1.0"),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with self._opener.open(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        if not raw.strip():
            return None
        if raw.startswith("tokenIncorrecto"):
            return None
        return json.loads(raw)

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        for prefix in (f"var dataset_{dataset_name} = [", f"var dataset_{dataset_name} = "):
            start = html.find(prefix)
            if start < 0:
                continue
            start += len(prefix)
            if prefix.endswith("= "):
                start -= 1
            end = html.find("];", start)
            if end < 0:
                continue
            chunk = html[start : end + 1]
            if not chunk.startswith("["):
                chunk = "[" + chunk
            try:
                data = json.loads(chunk)
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                continue
        return []

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON&lang=ES"
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            keywords = item.get("keywordList") or []
            if not any(str(k.get("code") or "") == URBANISMO_KEYWORD for k in keywords):
                continue
            name = str(item.get("name") or "").strip()
            dboid = str(item.get("dboid") or item.get("code") or name)
            if not name:
                continue
            url = (
                f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
                f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_CATSERV&lang=ES"
            )
            rows.append({"name": name, "code": dboid, "url": url})
        return rows

    def _siotuga_token(self) -> str | None:
        try:
            html = self._fetch(self.siotuga_inventario)
        except urllib.error.URLError:
            return None
        m = re.search(r"id='token'[^>]+value='([^']+)'", html)
        return m.group(1) if m else None

    def _collect_siotuga_plans(self) -> list[dict[str, Any]]:
        token = self._siotuga_token()
        if not token:
            return []
        rows: list[dict[str, Any]] = []
        for idclase, origen in (("13", "siotuga_desenvolvemento"), ("14", "siotuga_xeral")):
            data = self._post_json(
                "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php",
                {"id": INE_CONCELLO, "token": token, "idclase": idclase},
            )
            if not isinstance(data, list):
                continue
            for item in data:
                doc_id = str(item.get("id") or "")
                title = unescape(str(item.get("docnome") or "").strip())
                if not title or not doc_id:
                    continue
                fecha = (
                    str(item.get("fechaaddef") or "")
                    or str(item.get("fechadog") or "")
                    or None
                )
                figura = str(item.get("figura") or "")
                url = f"{self.siotuga_inventario}#doc-{doc_id}"
                rows.append(
                    {
                        "doc_id": doc_id,
                        "titulo": f"{title} ({figura})" if figura else title,
                        "fecha": fecha,
                        "url": url,
                        "tipo": _proyecto_tipo(figura, title),
                        "origen": origen,
                        "figura": figura,
                    }
                )
                if len(rows) >= self.max_siotuga_plans:
                    return rows
        return rows

    def _fixed_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "PXOM Santiago de Compostela — inventario SIOTUGA (INE 15078)",
                "fecha": "2007-10-03",
                "url": SIOTUGA_URB,
                "tipo": "PGOM/PXOM",
                "origen": "siotuga",
            },
            {
                "titulo": (
                    "Información pública modificación puntual PXOM PERI-12 "
                    "(antiguo colegio Manuel Peleteiro, exp. 2022/14663C)"
                ),
                "fecha": "2025-04-21",
                "url": DOG_PERI12_URL,
                "tipo": "información pública",
                "origen": "dog_xunta",
            },
        ]

    def _tablon_row(self, row: dict[str, Any]) -> tuple[str, str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        expte = str(row.get("externString") or "")
        dboid = str(row.get("dboid") or title)
        url = self._tablon_detail_url(dboid)
        return title, remitente, fecha, expte, url

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
        if not RE_LICENCIA.search(blob):
            return None
        key = expte or url
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": fecha or None,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "expte": expte or None,
            "url": url,
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _tramite_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item["name"]
        if not RE_LICENCIA.search(name):
            return None
        return {
            "id": _stable_id("lic", item["code"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": name[:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": "catalogo",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
        if RE_EXCLUDE_PROY.search(blob):
            return None
        is_urbanismo = "URBAN" in remitente.upper()
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and not is_urbanismo:
            return None
        if not is_urbanismo and not RE_PROYECTO.search(blob):
            return None
        exp_m = RE_EXPEDIENTE.search(blob)
        key = exp_m.group(1) if exp_m else (expte or url)
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha or None,
            "tipo": _proyecto_tipo(remitente, title),
            "url": url,
            "expte": exp_m.group(1) if exp_m else (expte or None),
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _siotuga_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", f"siotuga-{item['doc_id']}"),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"][:500],
            "fecha": item.get("fecha"),
            "tipo": item.get("tipo") or "planeamiento",
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen") or "siotuga",
            "siotuga_doc_id": item.get("doc_id"),
        }

    def _fixed_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"][:500],
            "fecha": item.get("fecha"),
            "tipo": item.get("tipo") or "planeamiento",
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen") or "fixed",
        }

    def _tramite_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item["name"]
        if RE_LICENCIA.search(name) and not RE_PROYECTO.search(name):
            return None
        if not RE_PROYECTO.search(name):
            return None
        return {
            "id": _stable_id("proy", item["code"]),
            "municipio": MUNICIPIO,
            "titulo": name[:500],
            "fecha": None,
            "tipo": _proyecto_tipo("trámite", name),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": "catalogo",
        }

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_catalog_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo"),
        }

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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._fixed_proyectos():
            add(self._fixed_to_proyecto(item))

        for item in self._collect_siotuga_plans():
            add(self._siotuga_to_proyecto(item))

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        for item in self._collect_catalog_tramites():
            add(self._tramite_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo"),
            "fixed": sum(1 for r in rows if r.get("origen") in ("siotuga", "dog_xunta", "fixed")),
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
