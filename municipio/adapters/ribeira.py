from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records
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

WEB_BASE = "https://www.ribeira.gal"
SEDE_BASE = "https://sede.ribeira.gal"
MUNICIPIO = "Ribeira"
ID_PREFIX = "ribeira"
INE = "15057"

SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_QUERY_DOC = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"
SIOTUGA_URB = "https://siotuga.xunta.gal/siotuga/urb?lang=es_ES"

SEED_PAGES: tuple[str, ...] = (
    f"{WEB_BASE}/planeamento-urbanistico",
    f"{WEB_BASE}/exposicions-publicas",
    f"{WEB_BASE}/anuncios",
    f"{WEB_BASE}/plan-especial-de-reforma-interior-del-pol%C3%8Dgono-8-del-plan-general-de-ordenaci%C3%93n-municipal.",
    f"{WEB_BASE}/pire-plan-especial-de-reforma-interior-do-pol%C3%ADgono-27-",
)

DEFAULT_LICENCIA_TRAMITES: list[tuple[str, str]] = [
    ("Comunicación previa de obra menor", f"{SEDE_BASE}/Editors/DlgTramiteSede.aspx"),
    ("Información urbanística", f"{SEDE_BASE}/Editors/DlgTramiteSede.aspx"),
    ("Licencia de segregación", f"{SEDE_BASE}/Editors/DlgTramiteSede.aspx"),
    (
        "Proyecto de ejecución / comunicación previa",
        f"{SEDE_BASE}/Editors/DlgTramiteSede.aspx",
    ),
    ("Catálogo de trámites — sede electrónica", f"{SEDE_BASE}/"),
]

RE_FECHA_GAL_ES = re.compile(
    r"(\d{1,2})\s+de\s+"
    r"(xaneiro|febreiro|marzo|abril|maio|xu[nñ]o|xullo|agosto|setembro|outubro|novembro|decembro|"
    r"enero|febrero|junio|julio|septiembre|octubre|noviembre|diciembre)"
    r"\s+de\s+(\d{4})",
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_BARE = re.compile(
    r"(\d{1,2})\s+"
    r"(xaneiro|febreiro|marzo|abril|maio|xu[nñ]o|xullo|agosto|setembro|outubro|novembro|decembro|"
    r"enero|febrero|junio|julio|septiembre|octubre|noviembre|diciembre)"
    r"\s+(\d{4})",
    re.I,
)
MESES = {
    "xaneiro": 1,
    "febreiro": 2,
    "marzo": 3,
    "abril": 4,
    "maio": 5,
    "xuno": 6,
    "xuño": 6,
    "xunho": 6,
    "xullo": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "decembro": 12,
    "enero": 1,
    "febrero": 2,
    "junio": 6,
    "julio": 7,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
RE_LICENCIA = re.compile(
    r"(?i)(licen|comunicaci[oó]n previa|declaraci[oó]n responsable|segregaci|obra menor|"
    r"informaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan xeral|pgom|pxom|peri|pire|reforma interior|exposici|"
    r"informaci[oó]n p[uú]blica|ordenaci|normas subsidiarias|instrumento|modificaci|"
    r"convenio|expropi|sector|pol[ií]gono)",
)
RE_PATH_PROYECTO = re.compile(
    r"(?i)(plan-|/pire-|peri|planeam|expos|reforma-interior|pgom|pxom|urban)",
)
RE_DOC_HREF = re.compile(
    r'href="(/documents/\d+/\d+/[^"]+\.pdf[^"]*|https://www\.ribeira\.gal/documents/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_SKIP_TITLE = re.compile(r"(?i)^(ver m[aá]is|leer m[aá]is|plan antifraude|plan .nico de concellos)$")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _web_url(path_or_url: str) -> str:
    if path_or_url.startswith("http"):
        return path_or_url
    if not path_or_url.startswith("/"):
        path_or_url = "/" + path_or_url
    return "https://www.ribeira.gal" + urllib.parse.quote(path_or_url, safe="/:?&=%")


def _parse_fecha(text: str) -> str | None:
    for regex in (RE_FECHA_GAL_ES, RE_FECHA_BARE, RE_FECHA_DMY):
        m = regex.search(text or "")
        if not m:
            continue
        try:
            if regex is RE_FECHA_DMY:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                    "%Y-%m-%d"
                )
            month = MESES.get(m.group(2).lower().replace("ñ", "n"))
            if not month:
                continue
            return datetime(int(m.group(3)), month, int(m.group(1))).strftime("%Y-%m-%d")
        except (ValueError, KeyError):
            continue
    ym = re.search(r"\b((?:19|20)\d{2})\b", text or "")
    return f"{ym.group(1)}" if ym else None


def _page_title(html: str, fallback: str = "") -> str:
    m = re.search(r"<title>([^<]+)</title>", html, re.I)
    if m:
        title = m.group(1).split(" - Concello")[0].strip()
        if title and title.lower() not in {"inicio", "home"}:
            return title
    for m in re.finditer(r"<h1[^>]*>([^<]{5,})", html, re.I):
        t = _strip_html(m.group(1))
        if t and not RE_SKIP_TITLE.search(t):
            return t
    return fallback


def _proyecto_tipo(titulo: str, figura: str | None = None) -> str:
    blob = f"{titulo} {figura or ''}".lower()
    if "peri" in blob or "pire" in blob or "reforma interior" in blob:
        return "PERI / plan especial"
    if "normas subsidiarias" in blob:
        return "normas subsidiarias"
    if "pgom" in blob or "plan xeral" in blob or "pxom" in blob:
        return "plan general"
    if "exposici" in blob:
        return "exposición pública"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "convenio" in blob:
        return "convenio urbanístico"
    return "planeamiento"


class RibeiraAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Liferay (planeamento, exposiciones) + sede + inventario SIOTUGA (INE 15057)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.max_siotuga_des = int(self.config.get("max_siotuga_desarrollo", 80))
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        self._siotuga_token_cache: str | None = None

    def _fetch(
        self,
        url: str,
        *,
        data: bytes | None = None,
        charset: str | None = None,
    ) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-ribeira/1.0")}
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
            self._siotuga_token_cache = None
            return []
        try:
            docs = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return docs if isinstance(docs, list) else []

    def _collect_siotuga(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for doc in self._siotuga_query(14):
            nome = str(doc.get("docnome") or "Plan xeral")
            rows.append(
                {
                    "titulo": nome,
                    "fecha": doc.get("fechaaddef") or doc.get("fechabop"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo(nome, str(doc.get("figura") or "")),
                    "origen": "siotuga_pg",
                    "siotuga_id": doc.get("id"),
                }
            )
        for doc in self._siotuga_query(13)[: self.max_siotuga_des]:
            nome = str(doc.get("docnome") or "Instrumento de planeamiento")
            rows.append(
                {
                    "titulo": nome,
                    "fecha": doc.get("fechaaddef") or doc.get("fechabop"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo(nome, str(doc.get("figura") or "")),
                    "origen": "siotuga_des",
                    "siotuga_id": doc.get("id"),
                }
            )
        return rows

    def _fixed_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Planeamento urbanístico — Concello de Ribeira",
                "fecha": None,
                "url": f"{self.web_base}/planeamento-urbanistico",
                "tipo": "planeamiento",
                "origen": "web_planeamento",
            },
            {
                "titulo": "Exposicións públicas",
                "fecha": None,
                "url": f"{self.web_base}/exposicions-publicas",
                "tipo": "exposición pública",
                "origen": "web_exposiciones",
            },
            {
                "titulo": f"Inventario planeamento — SIOTUGA (INE {INE})",
                "fecha": None,
                "url": SIOTUGA_INVENTARIO,
                "tipo": "inventario planeamiento",
                "origen": "siotuga_inventario",
            },
            {
                "titulo": "Estado planeamento municipal — SIOTUGA / Xunta",
                "fecha": None,
                "url": SIOTUGA_URB,
                "tipo": "planeamiento vigente",
                "origen": "siotuga_urb",
            },
        ]

    def _parse_liferay_page(self, url: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []
        titulo = _page_title(html, url.rsplit("/", 1)[-1])
        if not RE_PROYECTO.search(titulo) and not RE_PATH_PROYECTO.search(url):
            return []
        fecha = _parse_fecha(html)
        rows: list[dict[str, Any]] = [
            {
                "titulo": titulo[:500],
                "fecha": fecha,
                "url": url.split("?")[0],
                "tipo": _proyecto_tipo(titulo),
                "origen": "liferay_page",
            }
        ]
        seen_pdfs: set[str] = set()
        for href in RE_DOC_HREF.findall(html):
            pdf = _web_url(href)
            key = pdf.split("?")[0]
            if key in seen_pdfs:
                continue
            seen_pdfs.add(key)
            pdf_title = unescape(key.rsplit("/", 1)[-1].replace("+", " "))
            rows.append(
                {
                    "titulo": f"{titulo[:200]} — {pdf_title[:120]}",
                    "fecha": fecha,
                    "url": pdf,
                    "tipo": _proyecto_tipo(titulo),
                    "origen": "liferay_pdf",
                    "page_url": url.split("?")[0],
                }
            )
        return rows

    def _discover_page_urls(self) -> list[str]:
        found: set[str] = set()
        for seed in SEED_PAGES:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for href in re.findall(r'href="(https://www\.ribeira\.gal/[^"#?]+|/[^"#?]+)"', html):
                link = _web_url(href).split("?")[0]
                if RE_PATH_PROYECTO.search(link) and "plan-antifraude" not in link.lower():
                    found.add(link)
        return sorted(found)

    def _collect_liferay(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for url in self._discover_page_urls():
            if url in seen_urls:
                continue
            seen_urls.add(url)
            rows.extend(self._parse_liferay_page(url))
        return rows

    def _licencia_tramites(self) -> list[dict[str, Any]]:
        return [
            {"titulo": title, "url": url, "origen": "sede_tramite_info"}
            for title, url in DEFAULT_LICENCIA_TRAMITES
        ]

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
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
        if row.get("page_url"):
            rec["detalle_url"] = row["page_url"]
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
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
        rows = reviewed_records(path, rows)
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
        rows.extend(self._collect_liferay())
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._licencia_tramites():
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
            "liferay": sum(1 for r in rows if "liferay" in str(r.get("origen", ""))),
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
