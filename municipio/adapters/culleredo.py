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

WEB_BASE = "https://www.culleredo.es"
SEDE_OPENSIAC = "https://sedeelectronica.culleredo.es"
SEDE_CATALOG = "https://sede.culleredo.es"
MUNICIPIO = "Culleredo"
ID_PREFIX = "culleredo"
INE = "15031"

SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_VISOR = "https://siotuga.xunta.gal/siotuga/visor"
SIOTUGA_QUERY_DOC = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"
URBANISMO_WEB = f"{WEB_BASE}/es/urbanredes"
CATALOGO_URBANISMO = f"{SEDE_CATALOG}/catalogoservicios.aspx?ambito=2&area=1821"

URBAN_DRUPAL_NODES = ("8162", "8163", "8164")

RE_CATALOG_TRAMITE = re.compile(
    r'href="(https://sede\.culleredo\.es/carpetaciudadana/tramite\.aspx\?idtramite=\d+)"[^>]*>'
    r"([^<]+)</a>",
    re.I,
)
RE_DRUPAL_LINK = re.compile(
    r'href="(https?://[^"]+|/[^"]+)"[^>]*>([^<]{4,300})',
    re.I,
)
RE_URBAN = re.compile(
    r"(?i)(urban|licen|planeam|pgou|pxou|peri|sunp|anuncio|ordenaci|convenio|"
    r"reforma interior|modificaci|expropi|informaci[oó]n p[uú]blica|documentos/urbanismo)",
)
RE_LICENCIA = re.compile(
    r"(?i)(licen|comunicaci[oó]n previa|declaraci[oó]n responsable|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|URB\.)",
)
RE_PROYECTO = re.compile(
    r"(?i)(plan|planeam|pgou|pxou|peri|sunp|anuncio|convenio|modificaci|"
    r"informaci[oó]n p[uú]blica|ordenaci|reforma interior|documentos/urbanismo|"
    r"peid|ed_|instrumento|normas subsidiarias)",
)
RE_SKIP_LINK = re.compile(
    r"(?i)(twitter|facebook|menu|principal|galego|castellano|regresar|"
    r"urbanismo y planeamento|criterios de interpretaci|ordenaciones urban)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_url(href: str, base: str = WEB_BASE) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return f"{base.rstrip('/')}/{href}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    d = _parse_fecha_dmy(text)
    if d:
        return d
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    return f"{max(years)}" if years else None


def _proyecto_tipo(titulo: str, figura: str | None = None) -> str:
    blob = f"{titulo} {figura or ''}".lower()
    if "peri" in blob or "reforma interior" in blob:
        return "PERI / plan especial"
    if "sunp" in blob or "sectoriz" in blob:
        return "planeamiento de desarrollo"
    if "pgou" in blob or "plan xeral" in blob or "pxou" in blob:
        return "plan general"
    if "normas subsidiarias" in blob:
        return "normas subsidiarias"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "inspecci" in blob:
        return "disciplina urbanística"
    return "planeamiento"


class CulleredoAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal corporativo + sede Sedipualba/OpenSIAC + inventario SIOTUGA (INE 15031)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_OPENSIAC)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_catalog = str(self.config.get("sede_catalog") or SEDE_CATALOG).rstrip("/")
        self.sede_opensiac = str(self.config.get("sede_opensiac") or SEDE_OPENSIAC).rstrip("/")
        self.max_siotuga_des = int(self.config.get("max_siotuga_desarrollo", 120))
        self._jar = http.cookiejar.CookieJar()
        self._opener = self._build_opener()
        self._siotuga_token_cache: str | None = None

    def _build_opener(self) -> urllib.request.OpenerDirector:
        handlers: list[Any] = [urllib.request.HTTPCookieProcessor(self._jar)]
        if self.config.get("insecure_ssl", True):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            handlers.append(urllib.request.HTTPSHandler(context=ctx))
        return urllib.request.build_opener(*handlers)

    def _fetch(
        self,
        url: str,
        *,
        data: bytes | None = None,
        delay: bool = True,
        charset: str | None = None,
    ) -> str:
        if delay:
            time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-culleredo/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=90) as resp:
            enc = charset or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(enc, errors="replace")

    def _get_siotuga_token(self) -> str:
        if self._siotuga_token_cache:
            return self._siotuga_token_cache
        html = self._fetch(SIOTUGA_INVENTARIO, charset="utf-8")
        m = re.search(r"name=['\"]token['\"][^>]*value=['\"]([^'\"]+)['\"]", html, re.I)
        if not m:
            m = re.search(r"id=['\"]token['\"][^>]*value=['\"]([^'\"]+)['\"]", html, re.I)
        if not m:
            raise RuntimeError("SIOTUGA: no se encontró token de sesión")
        self._siotuga_token_cache = m.group(1)
        return self._siotuga_token_cache

    def _siotuga_query(self, idclase: int) -> list[dict[str, Any]]:
        token = self._get_siotuga_token()
        data = f"id={INE}&token={token}&idclase={idclase}".encode()
        raw = self._fetch(SIOTUGA_QUERY_DOC, data=data, charset="utf-8")
        if raw.strip().startswith("tokenIncorrecto"):
            return []
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
                    "fecha": doc.get("fechaaddef") or doc.get("fechabop"),
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
                    "fecha": doc.get("fechaaddef") or doc.get("fechabop"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo(str(doc.get("docnome") or ""), str(doc.get("figura") or "")),
                    "origen": "siotuga_des",
                    "siotuga_id": doc.get("id"),
                    "figura": doc.get("figura"),
                }
            )
        return rows

    def _collect_drupal_urban(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for nid in URBAN_DRUPAL_NODES:
            try:
                html = self._fetch(f"{self.web_base}/es/node/{nid}", charset="utf-8")
            except urllib.error.URLError:
                continue
            for href, raw_title in RE_DRUPAL_LINK.findall(html):
                titulo = _strip_html(raw_title)
                url = _abs_url(href.replace("&amp;", "&"), self.web_base)
                if url in seen:
                    continue
                if RE_SKIP_LINK.search(titulo) or RE_SKIP_LINK.search(url):
                    continue
                if not RE_URBAN.search(f"{titulo} {url}"):
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(titulo + " " + url),
                        "url": url,
                        "origen": f"drupal_node_{nid}",
                    }
                )
        return rows

    def _collect_catalog_licencias(self) -> list[dict[str, Any]]:
        url = f"{self.sede_catalog}/catalogoservicios.aspx?ambito=2&area=1821"
        try:
            html = self._fetch(url, charset="utf-8")
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tram_url, title in RE_CATALOG_TRAMITE.findall(html):
            titulo = _strip_html(title)
            if not RE_LICENCIA.search(titulo):
                continue
            if tram_url in seen:
                continue
            seen.add(tram_url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": tram_url.replace("&amp;", "&"),
                    "origen": "sede_catalogo_urb",
                    "tipo": "trámite licencia",
                }
            )
        return rows

    def _fixed_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Consulta del planeamento urbanístico — SIOTUGA (Culleredo 15031)",
                "fecha": None,
                "url": SIOTUGA_VISOR,
                "tipo": "visor planeamiento",
                "origen": "siotuga_visor",
            },
            {
                "titulo": "Inventario planeamento municipal — SIOTUGA",
                "fecha": None,
                "url": SIOTUGA_INVENTARIO,
                "tipo": "inventario planeamiento",
                "origen": "siotuga_inventario",
            },
            {
                "titulo": "Urbanismo y planeamento — web municipal",
                "fecha": None,
                "url": URBANISMO_WEB,
                "tipo": "información urbanismo",
                "origen": "web_urbanismo",
            },
            {
                "titulo": "Documentos sometidos a información pública (tablón sede)",
                "fecha": None,
                "url": f"{self.sede_catalog}/tablondeanuncios",
                "tipo": "información pública",
                "origen": "sede_tablon_info",
            },
        ]

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        if not RE_PROYECTO.search(titulo) and row.get("origen", "").startswith("drupal"):
            if not RE_PROYECTO.search(row.get("url", "")):
                return None
        url = row.get("url") or self.web_base
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{url}|{titulo}|{row.get('siotuga_id','')}"),
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
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_catalog
        return {
            "id": _stable_id("lic", url + titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "nota": row.get("nota")
            or "Procedimiento informativo Sedipualba; sin listado público de concesiones",
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

    def _collect_proyecto_sources(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._fixed_seeds())
        rows.extend(self._collect_siotuga())
        rows.extend(self._collect_drupal_urban())
        return rows

    def _collect_licencia_sources(self) -> list[dict[str, Any]]:
        return self._collect_catalog_licencias()

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_licencia_sources():
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_catalogo_urb"}

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
        for item in self._collect_proyecto_sources():
            rec = self._to_proyecto(item)
            if rec is None:
                continue
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
            "drupal": sum(1 for r in rows if str(r.get("origen", "")).startswith("drupal")),
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
