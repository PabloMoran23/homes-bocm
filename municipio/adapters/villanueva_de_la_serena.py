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

WP_BASE = "https://villanuevadelaserena.es"
SEDE_BASE = "https://sede.villanuevadelaserena.es"
MUNICIPIO = "Villanueva de la Serena"
ID_PREFIX = "villanueva-de-la-serena"

TABLON_PAGE = f"{SEDE_BASE}/portal/noEstatica.do?opc_id=268&ent_id=1&idioma=1"
CATALOGO_TRAMITES = (
    f"{SEDE_BASE}/sede/catalogoTramites.do?opcion=detalle&idApl=2&ent_id=1&idioma=1"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/plan-edil/",
    f"{WP_BASE}/plan-de-actuacion-integrado/",
    f"{WP_BASE}/agenda-urbana-espanola/",
    f"{WP_BASE}/portal-de-la-transparencia/normativa/normativa-sobre-urbanismo-y-medio-ambiente/",
]

RE_CSRF = re.compile(r"value='([^']+)'\s+name='CSRFToken'", re.I)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_TRAMITE_ROW = re.compile(
    r'id="dct_(\d+)"[^>]*title="([^"]*)"[^>]*href="([^"]+)"',
    re.I,
)
RE_TRAMITE_NAME = re.compile(
    r'<i class="fa fa-angle-right[^"]*"></i>\s*([^<]{5,220})',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|c[eé]dula|parcelaci|primera ocupaci[oó]n|"
    r"obra mayor|obra menor|certificados? de urbanismo|vado)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|edil|actuaci[oó]n)|"
    r"pgou|pgom|pai|agenda urbana|convenio|informaci[oó]n p[uú]blica|expediente|"
    r"expte|reparcel|proyecto|modificaci[oó]n|aprobaci[oó]n|edil|"
    r"sector|urbanizaci[oó]n|instrumento|anuncio bop|medidas.*urban|"
    r"contrataci[oó]n urban|jgl.*urban)",
)
RE_TABLON_URBAN = re.compile(
    r"(?i)(urban|planeam|pgou|pgom|pai|plan edil|agenda urbana|"
    r"contrataci[oó]n urban|medidas.*urban|instrumento de planeamiento|"
    r"plan de acci[oó]n local|actuaci[oó]n integrad|"
    r"informaci[oó]n p[uú]blica.*(?:urban|planeam|suelo)|"
    r"exposici[oó]n p[uú]blica.*(?:urban|planeam|proyecto)|"
    r"anuncio bop.*(?:urban|planeam|mc-|expediente mc)|"
    r"jgl.*urban|ampliaci[oó]n atribuciones jgl.*urban|"
    r"revisi[oó]n precios obras sector p[uú]blico)",
)
RE_NOISE = re.compile(
    r"(?i)(cobranza|iae 20|lista definitiva|proceso selectivo|"
    r"padr[oó]n de la prestaci[oó]n patrimonial|precio p[uú]blico|"
    r"personal laboral|tribunal.*plaza|bases.*plaza|profesor|"
    r"presupuesto general|bolsa local|polic[ií]a local|"
    r"delegaci[oó]n atribuciones|reglamento condeco|"
    r"notif modificaci[oó]n tribunal|extracto bop modificaci[oó]n bases|"
    r"derogaci[oó]n bolsa|administrativo|determinaci[oó]n tribunal)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b(20\d{2})[-_](\d{2})[-_](\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(y.group(1))
        for y in RE_YEAR.finditer(text or "")
        if 1980 <= int(y.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _title_from_pdf_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).name
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    return name.replace("-", " ").replace("_", " ").strip()[:500]


def _map_tipo_proyecto(title: str) -> str:
    blob = (title or "").lower()
    if "plan edil" in blob or " pai " in blob or blob.startswith("pai"):
        return "plan actuación integrada"
    if "agenda urbana" in blob:
        return "agenda urbana"
    if "pgou" in blob or "pgom" in blob or "plan general" in blob:
        return "PGOU/PGOM"
    if "plan parcial" in blob or "plan especial" in blob:
        return "plan parcial/especial"
    if "exposici" in blob and "p" in blob and "blica" in blob:
        return "exposición pública"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "anuncio bop" in blob or "bop publicado" in blob:
        return "publicación BOP"
    if "urban" in blob or "contrataci" in blob:
        return "urbanismo"
    return "documento urbanismo"


class VillanuevaDeLaSerenaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (PAI/EDIL, normativa) + sede STA tablón JSON (CSRF) + catálogo trámites."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.catalogo_url = str(self.config.get("catalogo_tramites_url") or CATALOGO_TRAMITES)
        self.tablon_page = str(self.config.get("tablon_page") or TABLON_PAGE)
        self.tablon_opc_id = str(self.config.get("tablon_opc_id") or "268")
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        self._csrf: str | None = None
        self._tablon_warmed = False

    def _fetch(
        self,
        url: str,
        *,
        data: bytes | None = None,
        charset: str = "utf-8",
    ) -> str:
        time.sleep(self.delay_s)
        headers = {
            "User-Agent": self.config.get("user_agent", "poc-bocm-villanueva-de-la-serena/1.0"),
        }
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=60) as resp:
            raw = resp.read()
            enc = resp.headers.get_content_charset() or charset
            return raw.decode(enc, errors="replace")

    def _abs_wp(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{WP_BASE}/", href))

    def _abs_sede(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{self.sede_base}/", href.replace("&amp;", "&")))

    def _warm_tablon(self) -> None:
        if self._tablon_warmed and self._csrf:
            return
        html = self._fetch(self.tablon_page, charset="iso-8859-1")
        m = RE_CSRF.search(html)
        self._csrf = m.group(1) if m else None
        self._tablon_warmed = True

    def _tablon_post(self, subseccion: str) -> dict[str, Any]:
        self._warm_tablon()
        payload: dict[str, str] = {
            "opcion": "consultar",
            "opc_id": self.tablon_opc_id,
            "ent_id": "1",
            "subseccion": subseccion,
        }
        if self._csrf:
            payload["CSRFToken"] = self._csrf
        url = f"{self.sede_base}/sede/tablonElectronico.do"
        body = urllib.parse.urlencode(payload).encode()
        text = self._fetch(url, data=body, charset="iso-8859-1")
        if not text.lstrip().startswith("{"):
            self._tablon_warmed = False
            self._warm_tablon()
            if self._csrf:
                payload["CSRFToken"] = self._csrf
            text = self._fetch(url, data=urllib.parse.urlencode(payload).encode(), charset="iso-8859-1")
        data = json.loads(text)
        return data if isinstance(data, dict) else {}

    def _doc_url(self, doc: dict[str, Any], sub: str) -> str:
        raw = doc.get("docUrl") or ""
        if raw:
            return self._abs_sede(raw)
        code = doc.get("docCve") or ""
        if code:
            return (
                f"{self.sede_base}/portal/verificarDocumentos.do?"
                f"ent_id=1&opcion=verificar&codigo={urllib.parse.quote(str(code))}"
                f"&subseccion={sub}&idioma=1"
            )
        return self.tablon_page

    def _is_urban_blob(self, blob: str, *, tablon: bool = False) -> bool:
        if RE_NOISE.search(blob):
            return False
        if tablon:
            return bool(RE_TABLON_URBAN.search(blob) or RE_LICENCIA.search(blob))
        return bool(RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob))

    def _collect_tablon_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        subsections = ["TABLONVIRTUAL"]
        try:
            root = self._tablon_post("TABLONVIRTUAL")
            for s in root.get("listaSubsecciones") or []:
                code = str(s.get("cod") or "")
                if code and code not in subsections:
                    subsections.append(code)
        except (urllib.error.URLError, json.JSONDecodeError):
            return rows

        for sub in subsections:
            try:
                data = self._tablon_post(sub) if sub != "TABLONVIRTUAL" else root
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            for doc in data.get("listaDocumentos") or []:
                name = _strip_html(str(doc.get("docNom") or ""))
                if not name or not self._is_urban_blob(name, tablon=True):
                    continue
                key = f"doc:{doc.get('docId') or doc.get('docCve') or name}"
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": name[:500],
                        "fecha": _parse_fecha_dmy(str(doc.get("docFpu") or name)),
                        "url": self._doc_url(doc, sub),
                        "tipo": _map_tipo_proyecto(name),
                        "origen": "tablon",
                    }
                )
            for exp in data.get("listaExpedientes") or []:
                name = _strip_html(str(exp.get("nombre") or ""))
                if not name or not self._is_urban_blob(name, tablon=True):
                    continue
                exp_id = str(exp.get("idExp") or "")
                key = f"exp:{exp_id or name}"
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "titulo": name[:500],
                        "fecha": _parse_fecha_dmy(
                            str(exp.get("fechaPublicacion") or exp.get("fechaCreacion") or "")
                        ),
                        "url": self.tablon_page,
                        "tipo": _map_tipo_proyecto(name),
                        "origen": "tablon_expediente",
                    }
                )
        return rows

    def _collect_pdf_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_wp(m.group(1))
                if pdf in seen:
                    continue
                title = _title_from_pdf_url(pdf)
                blob = f"{title} {pdf}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                seen.add(pdf)
                rows.append(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": MUNICIPIO,
                        "titulo": title or "Documento urbanismo",
                        "fecha": _fecha_from_blob(f"{title} {pdf}"),
                        "tipo": _map_tipo_proyecto(title),
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": "wp_pdf",
                    }
                )
        return rows

    def _collect_catalogo_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.catalogo_url, charset="iso-8859-1")
        except urllib.error.URLError:
            return rows

        for m in RE_TRAMITE_ROW.finditer(html):
            dct_id, title_attr, href = m.groups()
            title = unescape(title_attr).strip()
            if not RE_LICENCIA.search(title):
                continue
            if dct_id in seen:
                continue
            seen.add(dct_id)
            url = self.catalogo_url if href.startswith("javascript") else self._abs_sede(href)
            rows.append(
                {
                    "id": _stable_id("lic", f"tramite-{dct_id}"),
                    "fecha_concesion": None,
                    "tipo": title[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_catalogo",
                }
            )

        if not rows:
            for m in RE_TRAMITE_NAME.finditer(html):
                title = unescape(m.group(1)).strip()
                if not RE_LICENCIA.search(title):
                    continue
                key = title.lower()
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "id": _stable_id("lic", key),
                        "fecha_concesion": None,
                        "tipo": title[:120],
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title[:500],
                        "url": self.catalogo_url,
                        "source": "ayuntamiento",
                        "origen": "sede_catalogo",
                    }
                )
        return rows

    def _tablon_to_proyectos(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in self._collect_tablon_rows():
            if RE_LICENCIA.search(row["titulo"]) and not RE_PROYECTO.search(row["titulo"]):
                continue
            key = row["url"] + row["titulo"]
            out.append(
                {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": row["titulo"],
                    "fecha": row.get("fecha"),
                    "tipo": row.get("tipo") or "urbanismo",
                    "url": row["url"],
                    "source": "ayuntamiento",
                    "origen": row.get("origen"),
                }
            )
        return out

    def _licencias_informativas(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", "info-catalogo-urbanismo"),
                "fecha_concesion": None,
                "tipo": "información trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites de urbanismo (licencias vía sede)",
                "url": self.catalogo_url,
                "source": "ayuntamiento",
                "nota": "Sin listado público de licencias concedidas.",
            }
        ]

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
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
        rows = self._collect_catalogo_licencias()
        if not rows:
            rows = self._licencias_informativas()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_catalogo"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_catalogo_licencias():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values()) if existing else self._licencias_informativas()
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        by_id: dict[str, dict[str, Any]] = {}
        for rec in self._collect_pdf_proyectos() + self._tablon_to_proyectos():
            by_id[rec["id"]] = rec
        rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

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
