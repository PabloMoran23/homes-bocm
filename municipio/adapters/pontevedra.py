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

WEB_BASE = "https://pontevedra.gal"
SEDE_BASE = "https://sede.pontevedra.gal"
MUNICIPIO = "Pontevedra"
ID_PREFIX = "pontevedra"
INE = "36038"

SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_QUERY_DOC = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"
CATAFIS = "https://catafis.pontevedra.gal/"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/areas/urbanismo-e-territorio/",
    f"{WEB_BASE}/areas/urbanismo-e-territorio/planeamento-urbanistico/",
    f"{WEB_BASE}/areas/urbanismo-e-territorio/planeamento-urbanistico/planeamento-de-desenvolvemento/",
    f"{WEB_BASE}/areas/urbanismo-e-territorio/planeamento-urbanistico/planeamento-en-tramitacion/",
    f"{WEB_BASE}/areas/urbanismo-e-territorio/planeamento-urbanistico/pxou-e-modificacions-realizadas/",
    f"{WEB_BASE}/areas/urbanismo-e-territorio/o-futuro-pxom/",
    f"{WEB_BASE}/areas/urbanismo-e-territorio/tramites-urbanisticos/",
    f"{WEB_BASE}/concello/observatorio-urbano/",
]

DEFAULT_LICENCIA_SEEDS: list[tuple[str, str]] = [
    (
        "Trámites urbanísticos — Concello de Pontevedra",
        f"{WEB_BASE}/areas/urbanismo-e-territorio/tramites-urbanisticos/",
    ),
    (
        "Comunicacións previas (documentación informativa 2017)",
        "https://www.pontevedra.gal/URBANISMO-docs/2017-06-26_Comunicacions-previas.pdf",
    ),
    (
        "Licenzas urbanísticas (documentación informativa 2017)",
        "https://www.pontevedra.gal/URBANISMO-docs/2017-06-26_Licenzas.pdf",
    ),
    (
        "Sede electrónica — publicacións e transparencia",
        f"{SEDE_BASE}/public/dynamic/publications/",
    ),
    (
        "Convenios urbanísticos (sede)",
        f"{SEDE_BASE}/public/convenio/convenio-index.xhtml",
    ),
]

RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_PDF = re.compile(r"\.pdf(?:\?|#|$)", re.I)
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_URBAN = re.compile(
    r"(?i)(urban|licen|planeam|pxou|pxom|obra|territ|convenio|sector|reparcel|"
    r"exposici[oó]n|informaci[oó]n p[uú]blica|modificaci[oó]n|ordenanza)",
)
RE_LICENCIA = re.compile(
    r"(?i)(licen|comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n|"
    r"primeira ocupaci|titul)",
)
RE_PROYECTO = re.compile(
    r"(?i)(plan|planeam|pxou|pxom|sector|convenio|urban|exposici[oó]n|"
    r"informaci[oó]n p[uú]blica|modificaci[oó]n|reparcel|catalogo|instrumento)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_url(base_page: str, href: str) -> str:
    href = unescape(href.strip())
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return WEB_BASE.rstrip("/") + href
    return urllib.parse.urljoin(base_page, href)


def _parse_fecha(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _proyecto_tipo(titulo: str, figura: str | None = None) -> str:
    blob = f"{titulo} {figura or ''}".lower()
    if "pxou" in blob or "plan xeral" in blob or "plan general" in blob:
        return "plan general"
    if "pxom" in blob:
        return "plan municipal"
    if "sector" in blob or "sectorización" in blob or "sectorizacion" in blob:
        return "planeamiento de desarrollo"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "catalogo" in blob or "catálogo" in blob:
        return "catálogo urbanístico"
    if "exposici" in blob or "información pública" in blob or "informacion publica" in blob:
        return "información pública"
    if "modificaci" in blob:
        return "modificación planeamiento"
    return "planeamiento"


class PontevedraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress pontevedra.gal + inventario SIOTUGA (INE 36038); sede JSF sin tablón scrapeable."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_siotuga_des = int(self.config.get("max_siotuga_desarrollo", 60))
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        self._siotuga_token: str | None = None

    def _fetch(self, url: str, *, data: bytes | None = None, charset: str | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-pontevedra/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=90) as resp:
            enc = charset or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(enc, errors="replace")

    def _get_siotuga_token(self) -> str:
        if self._siotuga_token:
            return self._siotuga_token
        html = self._fetch(SIOTUGA_INVENTARIO, charset="utf-8")
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

    def _fixed_proyecto_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Catafis — portal de mapas e datos xeoreferenciados (SIG municipal)",
                "fecha": None,
                "url": CATAFIS,
                "tipo": "visor SIG",
                "origen": "catafis",
            },
            {
                "titulo": "Planeamento urbanístico — área municipal",
                "fecha": None,
                "url": f"{self.web_base}/areas/urbanismo-e-territorio/planeamento-urbanistico/",
                "tipo": "información planeamiento",
                "origen": "web_planeamiento",
            },
            {
                "titulo": "O futuro PXOM — proceso participativo",
                "fecha": None,
                "url": f"{self.web_base}/areas/urbanismo-e-territorio/o-futuro-pxom/",
                "tipo": "plan municipal",
                "origen": "web_pxom",
            },
            {
                "titulo": "Inventario planeamento — SIOTUGA (INE 36038)",
                "fecha": None,
                "url": SIOTUGA_INVENTARIO,
                "tipo": "inventario planeamiento",
                "origen": "siotuga_inventario",
            },
            {
                "titulo": "Observatorio urbano — Concello de Pontevedra",
                "fecha": None,
                "url": f"{self.web_base}/concello/observatorio-urbano/",
                "tipo": "información urbanismo",
                "origen": "web_observatorio",
            },
        ]

    def _collect_wp_assets(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(titulo: str, url: str, origen: str, fecha: str | None = None) -> None:
            if url in seen:
                return
            if not RE_URBAN.search(f"{titulo} {url}"):
                return
            seen.add(url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "tipo": _proyecto_tipo(titulo),
                    "origen": origen,
                }
            )

        for page in self.seed_pages:
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                continue
            for href in RE_HREF.findall(html):
                url = _abs_url(page, href)
                if "pontevedra.gal" not in url and "pontevedra.eu" not in url and "boppo.depo.gal" not in url:
                    continue
                if RE_PDF.search(url):
                    name = urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace(".pdf", "").replace("-", " ")
                    add(name or "Documento PDF", url, "wp_pdf", _parse_fecha(url))
                    continue
                if "/PXOU/" in url or "/URBANISMO-docs/" in url:
                    slug_part = url.rsplit("/", 1)[-1].replace("-", " ")
                    add(slug_part, url, "wp_link")
                    continue
                if "/areas/urbanismo" in url and RE_PROYECTO.search(url):
                    if url.rstrip("/") in {p.rstrip("/") for p in self.seed_pages}:
                        continue
                    if url.rstrip("/") == page.rstrip("/"):
                        continue
                    slug_part = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
                    add(slug_part, url, "wp_link")

        return rows

    def _licencia_seeds(self) -> list[dict[str, Any]]:
        return [
            {"titulo": title, "url": url, "origen": "tramite_info", "tipo": "información trámite"}
            for title, url in DEFAULT_LICENCIA_SEEDS
        ]

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.web_base
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{url}|{titulo}|{row.get('siotuga_id', '')}"),
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
        url = row.get("url") or self.web_base
        return {
            "id": _stable_id("lic", url + titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite / información licencias",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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
        for item in self._licencia_seeds():
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_info"}

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

        def add(item: dict[str, Any]) -> None:
            rec = self._to_proyecto(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._fixed_proyecto_seeds():
            add(item)
        for item in self._collect_siotuga():
            add(item)
        for item in self._collect_wp_assets():
            add(item)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
            "fixed": sum(1 for r in rows if r.get("origen") in ("catafis", "web_planeamiento", "web_pxom", "web_observatorio")),
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
