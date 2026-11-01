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

BASE = "https://www.naron.gal"
SEDE_BASE = "https://sedeelectronica.naron.es"
TRANSPARENCIA_URBANISMO = (
    "https://transparencia.naron.gal/normativa-urbanistica-y-medio-ambiente/"
)
PXOM_PAGE = f"{BASE}/cat/gal/concello/pxom"
INE = "15054"
SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_URB = "https://siotuga.xunta.gal/siotuga/urb?lang=es_ES"
MUNICIPIO = "Narón"
ID_PREFIX = "naron"

SEARCH_URL = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica_search.action"
TRAMITES_CATALOGO = f"{SEDE_BASE}/opensiac/action/tramites?method=enter"
INFO_PUBLICA_OTROS = f"{SEDE_BASE}/opensiac/informacionpublica/infopublica.action?edictos=OTROS"

DEFAULT_LICENCIA_TRAMITES: list[tuple[str, str]] = [
    ("Catálogo de trámites — Concello en liña (urbanismo)", TRAMITES_CATALOGO),
    (
        "Consulta de expedientes (sede electrónica)",
        f"{SEDE_BASE}/opensiac/carpetaciudadana/consultaexpedientes_enter.action",
    ),
]

DOG_CONVENIO_2025 = (
    "https://www.xunta.gal/dog/Publicados/2025/20251002/"
    "AnuncioL154-290925-0001_es.html"
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licenz|licença|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra|edificaci[oó]n|urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|xeral|general)|pxom|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n|expediente|modificaci[oó]n|sectoriz|"
    r"ordenanza|cat[aá]logo|srau|pol[ií]gono|dotaci[oó]n|estudo|pmus|cambio de uso)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LISTING_ROW = re.compile(
    r"infopublica_ver\.action[^\"]*id=(\d+)\"[^>]*title=\"(?:Mostrar|Amosar) ([^\"]+)\"",
    re.I,
)
RE_TRAMITE_LINK = re.compile(
    r'href="(/opensiac/action/tramitesinfo[^"]+)"[^>]*>([^<]{8,200})</a>',
    re.I,
)
RE_PXOM_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.I | re.S)
RE_TRANSPARENCIA_LINK = re.compile(
    r'href="(https?://[^"]+(?:bop\.dacoruna|bop\.dicoruna|transparencia\.naron)[^"]+)"',
    re.I,
)


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


def _fecha_from_url(url: str) -> str | None:
    m = re.search(r"/publicado/(\d{4})/(\d{2})/(\d{2})/", url or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(url or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str, figura: str = "") -> str:
    n = f"{blob} {figura}".lower()
    if "pxom" in n or "plan xeral" in n or "pgom" in n:
        return "PXOM/PGOM"
    if "sectoriz" in n or "srau" in n:
        return "plan de sectorización"
    if "modificaci" in n:
        return "modificación PXOM"
    if "convenio" in n:
        return "convenio urbanístico"
    if "plan especial" in n or "pe " in n:
        return "plan especial"
    if "pmus" in n:
        return "PMUS"
    if "cambio de uso" in n:
        return "cambio de uso"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    return "planeamiento"


class NaronAyuntamientoAdapter(AyuntamientoAdapter):
    """Web naron.gal + transparencia WP + SIOTUGA (INE 15054); sede OpenSIAC (timeout frecuente)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.sede_timeout = float(self.config.get("sede_timeout_s", 25))
        self.max_siotuga = int(self.config.get("max_siotuga_plans", 120))
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        self._siotuga_token_cache: str | None = None

    def _fetch(self, url: str, *, data: bytes | None = None, timeout: float | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-naron/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=timeout or 90) as resp:
            enc = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(enc, errors="replace")

    def _fetch_sede(self, url: str, *, data: bytes | None = None) -> str:
        return self._fetch(url, data=data, timeout=self.sede_timeout)

    def _post_json(self, url: str, data: dict[str, str]) -> Any:
        body = urllib.parse.urlencode(data).encode()
        raw = self._fetch(url, data=body)
        if not raw.strip() or raw.startswith("tokenIncorrecto"):
            return None
        return json.loads(raw)

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", href)

    def _siotuga_token(self) -> str | None:
        if self._siotuga_token_cache:
            return self._siotuga_token_cache
        try:
            html = self._fetch(SIOTUGA_INVENTARIO)
        except urllib.error.URLError:
            return None
        m = re.search(r"id='token'[^>]+value='([^']+)'", html)
        if m:
            self._siotuga_token_cache = m.group(1)
        return self._siotuga_token_cache

    def _collect_siotuga(self) -> list[dict[str, Any]]:
        token = self._siotuga_token()
        if not token:
            return []
        rows: list[dict[str, Any]] = []
        for idclase, origen in (("13", "siotuga_desenvolvemento"), ("14", "siotuga_xeral"), ("16", "siotuga_historico")):
            try:
                data = self._post_json(
                    "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php",
                    {"id": INE, "token": token, "idclase": idclase},
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(data, list):
                continue
            for item in data:
                doc_id = str(item.get("id") or "")
                title = unescape(str(item.get("docnome") or "").strip())
                if not title or not doc_id:
                    continue
                figura = str(item.get("figura") or "")
                fecha = (
                    str(item.get("fechaaddef") or "").strip()
                    or str(item.get("fechadog") or "").strip()
                    or None
                )
                rows.append(
                    {
                        "doc_id": doc_id,
                        "titulo": f"{title} ({figura})" if figura else title,
                        "fecha": fecha,
                        "url": f"{SIOTUGA_INVENTARIO}#doc-{doc_id}",
                        "tipo": _proyecto_tipo(title, figura),
                        "origen": origen,
                    }
                )
                if len(rows) >= self.max_siotuga:
                    return rows
        return rows

    def _collect_pxom_page(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(PXOM_PAGE)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_PXOM_LI.finditer(html):
            text = _strip_html(m.group(1))
            if len(text) < 20 or not RE_PROYECTO.search(text):
                continue
            if text.lower().startswith("planeamento de desenvolvemento"):
                continue
            rows.append(
                {
                    "titulo": text[:500],
                    "fecha": _fecha_from_url(text),
                    "url": PXOM_PAGE,
                    "tipo": _proyecto_tipo(text),
                    "origen": "pxom_web",
                }
            )
        return rows

    def _collect_transparencia_docs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TRANSPARENCIA_URBANISMO)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TRANSPARENCIA_LINK.finditer(html):
            url = unescape(m.group(1)).replace("&amp;", "&")
            if url in seen:
                continue
            if not RE_PROYECTO.search(url) and "bop" not in url.lower():
                continue
            seen.add(url)
            name = url.rsplit("/", 1)[-1][:120]
            rows.append(
                {
                    "titulo": f"Documento urbanismo — {name}",
                    "fecha": _fecha_from_url(url),
                    "url": url,
                    "tipo": _proyecto_tipo(name),
                    "origen": "transparencia",
                }
            )
        return rows

    def _search_tablon(self, *, edictos: str, descripcion: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {
            "edictos": edictos,
            "descripcionTipoTablon": "Concello de Narón",
            "referencia": edictos,
        }
        if descripcion:
            params["descripcionPublicacion"] = descripcion
            params["botonBuscar"] = "Buscar"
        else:
            params["botonTodos"] = "Todos"
        data = urllib.parse.urlencode(params).encode("iso-8859-15", errors="replace")
        try:
            html = self._fetch_sede(SEARCH_URL, data=data)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_LISTING_ROW.finditer(html):
            pub_id, titulo = m.group(1), _strip_html(m.group(2))
            rows.append(
                {
                    "pub_id": pub_id,
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(titulo),
                    "url": f"{self.sede_base}/opensiac/informacionpublica/infopublica_ver.action?id={pub_id}",
                    "blob": titulo,
                    "origen": "tablon_opensiac",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        if not self.config.get("sede_tablon_enabled", True):
            return []
        merged: dict[str, dict[str, Any]] = {}
        # Una sola petición: si la sede no responde (habitual en CI), no bloquear el pipeline.
        for row in self._search_tablon(edictos="OTROS"):
            merged[row["pub_id"]] = row
        if merged:
            for row in self._search_tablon(edictos="CP"):
                merged[row["pub_id"]] = row
        return list(merged.values())

    def _collect_tramites_catalog(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch_sede(TRAMITES_CATALOGO)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_TRAMITE_LINK.finditer(html):
            href, name = m.group(1), _strip_html(m.group(2))
            if not RE_LICENCIA.search(name) and not RE_PROYECTO.search(name):
                continue
            rows.append(
                {
                    "name": name[:500],
                    "url": self._abs_sede(href),
                    "code": href,
                }
            )
        return rows

    def _fixed_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "PXOM Narón — inventario SIOTUGA (INE 15054)",
                "fecha": None,
                "url": SIOTUGA_URB,
                "tipo": "PXOM/PGOM",
                "origen": "siotuga",
            },
            {
                "titulo": (
                    "Convenio urbanístico sectorización ámbito I / exp. EDI/2020/1660 "
                    "(información pública DOG)"
                ),
                "fecha": "2025-09-18",
                "url": DOG_CONVENIO_2025,
                "tipo": "convenio urbanístico",
                "origen": "dog_xunta",
            },
        ]

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        key = item.get("doc_id") or item.get("pub_id") or item.get("url") or item["titulo"]
        return {
            "id": _stable_id("proy", str(key)),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"][:500],
            "fecha": item.get("fecha"),
            "tipo": item.get("tipo") or _proyecto_tipo(item["titulo"]),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo')} {row.get('blob', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return self._item_to_proyecto(row)

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo')} {row.get('blob', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["pub_id"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / anuncio",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _tramite_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(item["name"]):
            return None
        return {
            "id": _stable_id("lic", item["code"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["name"][:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
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

        for item in self._collect_tramites_catalog():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for title, url in DEFAULT_LICENCIA_TRAMITES:
            rec = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": "trámite informativo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": url,
                "source": "ayuntamiento",
                "nota": "Sin listado público de licencias concedidas; sede puede no responder desde CI",
                "origen": "fixed",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo"),
            "fixed": sum(1 for r in rows if r.get("origen") == "fixed"),
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

        def add(item: dict[str, Any] | None) -> None:
            if not item:
                return
            rec = self._item_to_proyecto(item) if "municipio" not in item else item
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._fixed_proyectos():
            add(self._item_to_proyecto(item))

        for item in self._collect_siotuga():
            add(item)

        for item in self._collect_pxom_page():
            add(item)

        for item in self._collect_transparencia_docs():
            add(item)

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
            "pxom": sum(1 for r in rows if r.get("origen") == "pxom_web"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_opensiac"),
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
