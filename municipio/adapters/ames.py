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

WEB_BASE = "https://www.concellodeames.gal"
SEDE_BASE = "https://sede.concellodeames.gal/eAdmin"
MUNICIPIO = "Ames"
ID_PREFIX = "ames"
INE = "15002"

TABLON_ALL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
TRANSP_URBANISMO = f"{WEB_BASE}/es/transparencia/urbanismo-obras-publicas-e-medioambiente"
TRANSP_PXOM = f"{WEB_BASE}/es/transparencia/accion-de-goberno/pxom"
SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_QUERY_DOC = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"
PBA_VISOR = "https://mapas.xunta.gal/visores/pba/"

DEFAULT_SEARCH_TERMS = (
    "PXOM",
    "PLANEAMIENTO",
    "URBANISMO",
    "LICENZA",
    "LICENCIA",
    "SECTOR",
    "CONVENIO",
    "INFORMACION PUBLICA",
    "EXPROPIACION",
)

DEFAULT_LICENCIA_TRAMITES: list[dict[str, Any]] = [
    {"tipo_reg": 37, "nombre": "Certificado Urbanístico"},
    {"tipo_reg": 58, "nombre": "Comunicación previa de obra"},
    {"tipo_reg": 41, "nombre": "Comunicación previa de obra de adecuación de local para actividade"},
    {"tipo_reg": 43, "nombre": "Comunicación previa de primeira ocupación de edificacións"},
    {"tipo_reg": 45, "nombre": "Información urbanística"},
    {"tipo_reg": 46, "nombre": "Licenza de vaos"},
    {"tipo_reg": 47, "nombre": "Prórroga de licenza de obras"},
    {"tipo_reg": 51, "nombre": "Solicitude de licenza de obras maiores"},
    {"tipo_reg": 52, "nombre": "Solicitude de licenza de segregación e parcelación"},
    {"tipo_reg": 49, "nombre": "Solicitude de autorización para a ocupación (temporal) da vía pública (por obras)"},
]

RE_DOC_TOKEN = re.compile(r"abrir(?:Original)?\('([^']+)'\)")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_EXPTE = re.compile(r"(?i)(?:EXP(?:EDIENTE)?\.?|EXPDTE\.?)\s*[:.]?\s*([0-9]+[/\-_][0-9]{2,4})")
RE_LICENCIA = re.compile(
    r"(?i)(licen[cs]|licenza|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"primeira ocupaci[oó]n|certificado urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(pxom|pgom|planeam|urban|sector|convenio|reparcel|modificaci[oó]n|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|plan especial|"
    r"plan parcial|sunp|expropi|instrumento|normas urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(elecci[oó]n|obradoiro de emprego|proceso selectivo|estabilizaci|"
    r"consello sectorial da xuventude|recursos humanos|xardiner)",
)
RE_URBAN_FILE = re.compile(
    r"(?i)(pxom|planeam|urban|sector|convenio|reforma.?interior|pb3|modificaci|"
    r"certificaci|plan.?especial|instrumento|normas)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"\s+", " ", text or "")).strip()
    return t[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_expte(text: str) -> str | None:
    m = RE_EXPTE.search(text)
    return m.group(1).strip() if m else None


def _pdf_url(token: str) -> str:
    return (
        f"{SEDE_BASE}/ValidarDocumento.do?id_Documento="
        f"{urllib.parse.quote(token, safe='')}&tipo=doc&mode=ori"
    )


def _proyecto_tipo(title: str, figura: str | None = None) -> str:
    blob = f"{title} {figura or ''}".lower()
    if "pxom" in blob or "pgom" in blob or "plan xeral" in blob:
        return "PXOM/PGOM"
    if "sector" in blob or "sunp" in blob:
        return "planeamiento de desarrollo"
    if "modificaci" in blob:
        return "modificación PXOM"
    if "convenio" in blob or "reparcel" in blob:
        return "convenio urbanístico"
    if "plan especial" in blob or "reforma interior" in blob or "pb3" in blob:
        return "plan especial"
    if re.search(r"informaci[oó]n p[uú]blica", blob):
        return "información pública"
    if "expropi" in blob:
        return "expropiación"
    return "planeamiento"


class AmesAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal concellodeames.gal + sede eAdmin tablón/trámites + inventario SIOTUGA (INE 15002)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.search_terms = list(self.config.get("search_terms") or DEFAULT_SEARCH_TERMS)
        self.licencia_tramites = list(
            self.config.get("licencia_tramites") or DEFAULT_LICENCIA_TRAMITES
        )
        self.max_siotuga_des = int(self.config.get("max_siotuga_desarrollo", 60))
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
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-ames/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=90) as resp:
            enc = charset or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(enc, errors="replace")

    def _parse_tablon_html(self, html: str) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for chunk in html.split("<tr>")[1:]:
            if "verAnuncio&id=" not in chunk:
                continue
            id_m = re.search(r"verAnuncio&id=([A-F0-9]+)", chunk, re.I)
            if not id_m:
                continue
            tds = re.findall(r"<td[^>]*>(.*?)</td>", chunk, re.S)
            if len(tds) < 3:
                continue
            title = _clean_title(re.sub(r"<[^>]+>", " ", tds[1]))
            if not title or RE_EXCLUDE.search(title):
                continue
            period_raw = re.sub(r"<[^>]+>", " ", tds[2])
            period_m = RE_PERIOD.search(period_raw)
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            doc_m = RE_DOC_TOKEN.search(chunk)
            ann_id = id_m.group(1).upper()
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec: dict[str, Any] = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha_ini": fecha_ini,
                "url": detail_url,
                "expte": _parse_expte(title),
                "origen": "sede_tablon",
            }
            if doc_m:
                rec["pdf_url"] = _pdf_url(doc_m.group(1))
            by_id[ann_id] = rec
        return by_id

    def _search_tablon(self, term: str) -> dict[str, dict[str, Any]]:
        body = urllib.parse.urlencode({"referenciaBusqueda": term}).encode("utf-8")
        try:
            html = self._fetch(TABLON_ALL, data=body, charset="utf-8")
        except urllib.error.URLError:
            return {}
        return self._parse_tablon_html(html)

    def _collect_tablon(self) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        try:
            html = self._fetch(TABLON_ALL, charset="utf-8")
            by_id.update(self._parse_tablon_html(html))
        except urllib.error.URLError:
            pass
        for term in self.search_terms:
            by_id.update(self._search_tablon(term))
        return by_id

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
        data = urllib.parse.urlencode({"id": INE, "token": token, "idclase": idclase}).encode()
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

    def _collect_transparencia_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in (TRANSP_URBANISMO, TRANSP_PXOM):
            try:
                html = self._fetch(page_url, charset="utf-8")
            except urllib.error.URLError:
                continue
            for href, text in re.findall(r'href="([^"]+)"[^>]*>([^<]*)', html, re.I):
                if not re.search(r"\.(?:pdf|zip|7z)(?:\?|$)", href, re.I):
                    continue
                if not RE_URBAN_FILE.search(href) and not RE_URBAN_FILE.search(text):
                    continue
                url = href if href.startswith("http") else f"{self.web_base}{href}"
                if url in seen:
                    continue
                seen.add(url)
                title = _clean_title(text) or unescape(urllib.parse.unquote(href.split("/")[-1]))
                rows.append(
                    {
                        "titulo": title,
                        "fecha": _parse_fecha_dmy(title) or _parse_fecha_dmy(href),
                        "url": page_url,
                        "pdf_url": url,
                        "tipo": _proyecto_tipo(title),
                        "origen": "drupal_transparencia",
                    }
                )
        return rows

    def _fixed_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Inventario planeamento municipal — SIOTUGA (INE 15002)",
                "fecha": None,
                "url": SIOTUGA_INVENTARIO,
                "tipo": "inventario planeamiento",
                "origen": "siotuga_inventario",
            },
            {
                "titulo": "Visor Plan Básico Autonómico / planeamiento Xunta",
                "fecha": None,
                "url": PBA_VISOR,
                "tipo": "visor planeamiento",
                "origen": "xunta_pba",
            },
            {
                "titulo": "Transparencia — urbanismo, obras públicas e medio ambiente",
                "fecha": None,
                "url": TRANSP_URBANISMO,
                "tipo": "transparencia urbanismo",
                "origen": "web_transparencia",
            },
            {
                "titulo": "PXOM — transparencia acción de goberno",
                "fecha": None,
                "url": TRANSP_PXOM,
                "tipo": "PXOM",
                "origen": "web_pxom",
            },
        ]

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tram in self.licencia_tramites:
            tipo_reg = int(tram["tipo_reg"])
            nombre = str(tram.get("nombre") or f"Trámite {tipo_reg}")
            url = f"{self.sede_base}/Registrar.do?action=infoTramite&tipoReg={tipo_reg}"
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": nombre[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": nombre[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámite; no concesión publicada en tablón",
                    "origen": "catalogo_tramites",
                    "tipo_reg": tipo_reg,
                }
            )
        return rows

    def _tablon_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        out: dict[str, Any] = {
            "id": _stable_id("proy", rec.get("expte") or rec["ann_id"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": rec.get("fecha_ini"),
            "tipo": _proyecto_tipo(title),
            "url": rec["url"],
            "source": "ayuntamiento",
            "expte": rec.get("expte"),
            "origen": rec.get("origen"),
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        return out

    def _tablon_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if not RE_LICENCIA.search(title):
            return None
        tipo_m = re.search(r"(?i)(licen[cs][^,]{0,80}|comunicaci[oó]n previa[^,]{0,80})", title)
        out: dict[str, Any] = {
            "id": _stable_id("lic", rec.get("expte") or rec["ann_id"]),
            "fecha_concesion": rec.get("fecha_ini"),
            "tipo": (tipo_m.group(1).strip()[:120] if tipo_m else "licencia"),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "expte": rec.get("expte"),
            "url": rec["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        return out

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
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("siotuga_id"):
            rec["siotuga_doc_id"] = row["siotuga_id"]
        return rec

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
        rows.extend(self._collect_transparencia_docs())
        for rec in self._collect_tablon().values():
            if RE_PROYECTO.search(rec["titulo"]) and not RE_EXCLUDE.search(rec["titulo"]):
                rows.append(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_tablon().values():
            lic = self._tablon_to_licencia(rec)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_licencias": sum(1 for r in rows if r.get("origen") == "tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_tablon().values():
            lic = self._tablon_to_licencia(rec)
            if lic:
                existing[lic["id"]] = lic
        for rec in self._collect_licencia_tramites():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_proyecto_sources():
            if "ann_id" in item:
                rec = self._tablon_to_proyecto(item)
            else:
                rec = self._to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_proyecto_sources():
            if "ann_id" in item:
                rec = self._tablon_to_proyecto(item)
            else:
                rec = self._to_proyecto(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}
