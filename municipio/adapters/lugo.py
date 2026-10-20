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

SEDE_BASE = "https://www.lugo.gal"
WEB_BASE = "https://concellodelugo.gal"
MUNICIPIO = "Lugo"
ID_PREFIX = "lugo"
INE = "27028"

TABLON_GRUPO = "TipoPublicarEn.TablonElectronico"
SIOTUGA_INVENTARIO = f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
SIOTUGA_QUERY_DOC = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"
URBANISMO_EN_REDE = "http://urbanismoenred.lugo.es/Visor/"
DATOS_ABIERTOS_PGOU = (
    "https://datosabertos.lugo.gal/es/e-transparencia-en-materias-de-urbanismo-obras-p%C3%BAblicas-y-medio-ambiente/"
    "e1-planes-de-ordenaci%C3%B3n-urbana-y-convenios-urban%C3%ADsticos"
)
PLANEAMIENTO_WEB = f"{WEB_BASE}/es/actuaciones/planeamiento-gestion-y-disciplina-urbanistica"
URBANISMO_REDE_INFO = f"{WEB_BASE}/gl/actuacions/urbanismo-en-rede"

DEFAULT_LICENCIA_TRAMITES: list[tuple[str, str]] = [
    (
        "Catálogo de procedementos — Urbanismo (sede electrónica)",
        f"{SEDE_BASE}/portal/tramites",
    ),
    (
        "Tramitación telemática procedimientos urbanísticos (noticia 2021)",
        f"{WEB_BASE}/es/noticias/la-sede-electronica-doelconcello-lugo-permitira-desde-manana-la-tramitacion-directa-y",
    ),
]

RE_TABLON_ITEM = re.compile(
    r"verDetalleAnuncio\('([^']+)'\).*?<time>.*?<span>(\d{2}/\d{2}/\d{4})</span>.*?"
    r"<p><strong>([^<]+)</strong></p>",
    re.I | re.S,
)
RE_TABLON_TITLE = re.compile(r"imc-anuncios-titulo.*?<p><strong>([^<]+)</strong>", re.I | re.S)
RE_PDF_LINK = re.compile(r"location\.href='(https://www\.lugo\.gal/publicacions/[^']+\.pdf)'", re.I)
RE_NOTICIA = re.compile(
    r'href="(https://concellodelugo\.gal/(?:es|gl)/noticias/[^"]+)"[^>]*>([^<]{10,200})</a>',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_URBAN = re.compile(
    r"(?i)(urban|licen|planeam|pgou|pgom|exposici[oó]n p[uú]blica|expropi|reparcel|"
    r"convenio urban|disciplina|ruina|ordenanza|sector|sunp|obra)",
)
RE_LICENCIA = re.compile(
    r"(?i)(licen|comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n|"
    r"primera ocupaci|titulos habilitantes|edificaci)",
)
RE_PROYECTO = re.compile(
    r"(?i)(plan|planeam|pgou|pgom|exposici[oó]n|expropi|reparcel|convenio|sector|"
    r"sunp|disciplina|informaci[oó]n p[uú]blica|expropiaci)",
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


def _proyecto_tipo(titulo: str, figura: str | None = None) -> str:
    blob = f"{titulo} {figura or ''}".lower()
    if "plan xeral" in blob or "pgou" in blob or "pgom" in blob:
        return "plan general"
    if "sector" in blob or "sunp" in blob:
        return "planeamiento de desarrollo"
    if "expropi" in blob:
        return "expropiación"
    if "exposici" in blob:
        return "información pública"
    if "convenio" in blob:
        return "convenio urbanístico"
    return "planeamiento"


class LugoAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede IMC (lugo.gal) + Drupal concellodelugo + inventario SIOTUGA (INE 27028)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.max_tablon_pages = int(self.config.get("max_tablon_pages", 20))
        self.max_siotuga_des = int(self.config.get("max_siotuga_desarrollo", 40))
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        self._siotuga_token_cache: str | None = None

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
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-lugo/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=90) as resp:
            enc = charset or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(enc, errors="replace")

    def _post_publicaciones(self, fields: dict[str, str]) -> str:
        body = urllib.parse.urlencode(fields).encode()
        return self._fetch(f"{self.sede_base}/portal/publicaciones", data=body)

    def _warm_tablon(self) -> None:
        if getattr(self, "_tablon_warmed", False):
            return
        try:
            self._fetch(
                f"{self.sede_base}/portal/publicaciones/TipoPublicarEn.TablonElectronico?noMenu=S",
                delay=False,
            )
        except urllib.error.URLError:
            pass
        self._tablon_warmed = True

    def _collect_tablon(self) -> list[dict[str, Any]]:
        self._warm_tablon()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pax in range(1, self.max_tablon_pages + 1):
            html = self._post_publicaciones(
                {
                    "grupo": TABLON_GRUPO,
                    "text": "",
                    "fecDesde": "",
                    "fecHasta": "",
                    "pax": str(pax),
                    "codigo": "",
                }
            )
            items = RE_TABLON_ITEM.findall(html)
            if not items:
                break
            for codigo, fecha_raw, titulo in items:
                titulo_clean = _strip_html(titulo)
                if codigo in seen:
                    continue
                if not RE_URBAN.search(titulo_clean):
                    continue
                seen.add(codigo)
                detail = self._post_publicaciones(
                    {
                        "grupo": TABLON_GRUPO,
                        "codigo": codigo,
                        "fecDesde": "",
                        "fecHasta": "",
                        "text": "",
                        "pax": "1",
                    }
                )
                pdf_m = RE_PDF_LINK.search(detail)
                title_m = RE_TABLON_TITLE.search(detail)
                rows.append(
                    {
                        "titulo": (title_m.group(1) if title_m else titulo_clean)[:500],
                        "fecha": _parse_fecha_dmy(fecha_raw),
                        "url": pdf_m.group(1) if pdf_m else f"{self.sede_base}/portal/tablonanuncios",
                        "codigo": codigo,
                        "origen": "sede_tablon",
                    }
                )
        return rows

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

    def _collect_noticias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for keys in ("urbanismo", "licencia obra", "planeamiento"):
            url = f"{self.web_base}/es/search/node/urbanismo?keys={urllib.parse.quote(keys)}"
            try:
                html = self._fetch(url, charset="utf-8")
            except urllib.error.URLError:
                continue
            for link, title in RE_NOTICIA.findall(html):
                if link in seen:
                    continue
                if not RE_URBAN.search(title):
                    continue
                seen.add(link)
                rows.append(
                    {
                        "titulo": _strip_html(title)[:500],
                        "fecha": None,
                        "url": link,
                        "origen": "drupal_noticia",
                    }
                )
        return rows

    def _fixed_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Urbanismo en Red — visor municipal",
                "fecha": None,
                "url": URBANISMO_EN_REDE,
                "tipo": "visor planeamiento",
                "origen": "visor_urbanismo_en_rede",
            },
            {
                "titulo": "Planeamento, xestión e disciplina urbanística",
                "fecha": None,
                "url": PLANEAMIENTO_WEB,
                "tipo": "información urbanismo",
                "origen": "web_planeamiento",
            },
            {
                "titulo": "Datos abertos — plans de ordenación e convenios urbanísticos",
                "fecha": None,
                "url": DATOS_ABIERTOS_PGOU,
                "tipo": "transparencia planeamiento",
                "origen": "datos_abertos",
            },
            {
                "titulo": "Inventario planeamento municipal — SIOTUGA (INE 27028)",
                "fecha": None,
                "url": SIOTUGA_INVENTARIO,
                "tipo": "inventario planeamiento",
                "origen": "siotuga_inventario",
            },
            {
                "titulo": "Urbanismo en Rede — información",
                "fecha": None,
                "url": URBANISMO_REDE_INFO,
                "tipo": "visor planeamiento",
                "origen": "web_urbanismo_rede",
            },
        ]

    def _licencia_tramites(self) -> list[dict[str, Any]]:
        return [
            {"titulo": title, "url": url, "origen": "sede_tramite_info"}
            for title, url in DEFAULT_LICENCIA_TRAMITES
        ]

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{url}|{titulo}|{row.get('codigo','')}"),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(titulo, row.get("figura")),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("codigo"):
            rec["expediente_codigo"] = row["codigo"]
        if row.get("siotuga_id"):
            rec["siotuga_doc_id"] = row["siotuga_id"]
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
        return {
            "id": _stable_id("lic", url + titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite / información urbanismo",
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

    def _collect_proyecto_sources(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._fixed_seeds())
        rows.extend(self._collect_siotuga())
        rows.extend(self._collect_tablon())
        rows.extend(self._collect_noticias())
        return rows

    def _collect_licencia_sources(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._licencia_tramites())
        for item in self._collect_noticias():
            if RE_LICENCIA.search(item["titulo"]):
                rows.append({**item, "origen": "drupal_noticia_licencia"})
        for item in self._collect_tablon():
            if RE_LICENCIA.search(item["titulo"]):
                rows.append({**item, "origen": "sede_tablon_licencia"})
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_licencia_sources():
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_web_siotuga_info"}

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
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
            "tablon": sum(1 for r in rows if "tablon" in str(r.get("origen", ""))),
            "noticias": sum(1 for r in rows if "noticia" in str(r.get("origen", ""))),
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
