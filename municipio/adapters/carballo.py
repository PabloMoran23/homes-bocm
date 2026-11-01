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

WEB_BASE = "https://carballo.gal"
SEDE_BASE = "https://sede.carballo.gal"
MUNICIPIO = "Carballo"
ID_PREFIX = "carballo"
INE = "15019"

TABLON_INDEX = f"{SEDE_BASE}/sxc/es/informacion/tablon/index.html"
TRAMITACION_URL = f"{WEB_BASE}/urbanismo-e-axenda-urbana/documentos-en-tramitacion/"
SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_QUERY_DOC = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"
SIOTUGA_URB = "https://siotuga.xunta.gal/siotuga/urb?lang=es_ES"
PXOM_ARCHIVO = "https://arquivos.carballo.gal/pxom-carballo/"
URBANISMO_SEDE = f"{SEDE_BASE}/sxc/es/procedimientosytramites/index.html#urbanismo"

TABLON_SEARCH_QUERIES = (
    "urbanismo",
    "licencia",
    "edificacion",
    "expropiacion",
    "planeamiento",
    "plan xeral",
    "peid",
)

DEFAULT_LICENCIA_TRAMITES: list[tuple[str, str]] = [
    (
        "Solicitud de licencia de edificación",
        f"{SEDE_BASE}/sxc/es/procedimientosytramites/tramites/Solicituddelicenciadeedificacion_N",
    ),
    (
        "Comunicación previa / declaración responsable (catálogo urbanismo)",
        URBANISMO_SEDE,
    ),
    (
        "Solicitud de información urbanística",
        f"{SEDE_BASE}/sxc/es/procedimientosytramites/tramites/Solicitudinformacionurbanistica_N",
    ),
    (
        "Certificado urbanístico",
        f"{SEDE_BASE}/sxc/es/procedimientosytramites/tramites/Certificadourbanistico_N",
    ),
]

RE_TABLON_LINK = re.compile(
    r'href="(/sxc/es/informacion/tablon/\d+/ANUNCIO[^"]+\.html)"',
    re.I,
)
RE_TABLON_HEADER = re.compile(
    r"<h2>([^<]+)</h2>\s*<div>(\d{2}/\d{2}/\d{4})</div>.*?<p class=\"top40\">([^<]+)</p>",
    re.I | re.S,
)
RE_CONTENIDO = re.compile(r"<contenido>(.*?)</contenido>", re.I | re.S)
RE_EXPEDIENTE = re.compile(r"\bEXP[:\s]*([\d]{4}/[A-Z0-9/]+)\b", re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/uploads/(\d{4})/(\d{2})/")
RE_LICENCIA = re.compile(
    r"(?i)(licen|comunicaci[oó]n previa|declaraci[oó]n responsable|autorizaci[oó]n|"
    r"edificaci[oó]n|primera ocupaci)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan xeral|pxom|peid|expropi|modificaci[oó]n puntual|"
    r"informaci[oó]n p[uú]blica|aprobaci[oó]n|reparcel|sector|convenio)",
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


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _proyecto_tipo(section: str, titulo: str, figura: str | None = None) -> str:
    blob = f"{section} {titulo} {figura or ''}".lower()
    if "peid" in blob or "plan especial" in blob:
        return "plan especial / PEID"
    if "expropi" in blob:
        return "expropiación"
    if "modificaci" in blob and "puntual" in blob:
        return "modificación puntual PXOM"
    if "pxom" in blob or "plan xeral" in blob:
        return "PXOM"
    if "informaci" in blob or "exposici" in blob:
        return "información pública"
    if "aprobaci" in blob:
        return "aprobación planeamiento"
    if section.strip().upper() == "URBANISMO":
        return "urbanismo"
    return "planeamiento"


class CarballoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress corporativo + sede SXC (Diputación A Coruña) tablón + SIOTUGA (INE 15019)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
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
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-carballo/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=90) as resp:
            enc = charset or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(enc, errors="replace")

    def _tablon_search_links(self, query: str) -> list[str]:
        body = urllib.parse.urlencode({"query": query, "search": "search"}).encode()
        try:
            html = self._fetch(TABLON_INDEX, data=body)
        except urllib.error.URLError:
            return []
        links = RE_TABLON_LINK.findall(html)
        out: list[str] = []
        seen: set[str] = set()
        for link in links:
            if link not in seen:
                seen.add(link)
                out.append(link)
        return out

    def _parse_tablon_detail(self, path: str) -> dict[str, Any] | None:
        url = f"{self.sede_base}{path}"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None
        m = RE_TABLON_HEADER.search(html)
        if not m:
            return None
        section, fecha_raw, titulo = m.group(1).strip(), m.group(2), _strip_html(m.group(3))
        contenido_m = RE_CONTENIDO.search(html)
        extra = _strip_html(contenido_m.group(1)) if contenido_m else ""
        blob = f"{titulo} {extra}"
        exp = None
        em = RE_EXPEDIENTE.search(blob)
        if em:
            exp = em.group(1)
        pdf_m = re.search(
            r'href="(/sxc/export/sites/carballo/recursos/downloads/Tablon/[^"]+\.pdf)"',
            html,
            re.I,
        )
        pdf_url = f"{self.sede_base}{pdf_m.group(1)}" if pdf_m else url
        return {
            "titulo": titulo[:500],
            "fecha": _parse_fecha_dmy(fecha_raw),
            "url": pdf_url,
            "detalle_url": url,
            "section": section,
            "codigo": exp,
            "origen": "sede_tablon",
        }

    def _collect_tablon(self) -> list[dict[str, Any]]:
        paths: list[str] = []
        seen_paths: set[str] = set()
        for q in TABLON_SEARCH_QUERIES:
            for path in self._tablon_search_links(q):
                if path not in seen_paths:
                    seen_paths.add(path)
                    paths.append(path)
        rows: list[dict[str, Any]] = []
        for path in paths:
            detail = self._parse_tablon_detail(path)
            if detail:
                rows.append(detail)
        return rows

    def _collect_wp_tramitacion(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TRAMITACION_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for part in re.split(r'(?=<div class="elementor-widget-container">)', html):
            pdfs = re.findall(
                r'href="(https://carballo\.gal/wp-content/uploads/[^"]+\.pdf)"',
                part,
                re.I,
            )
            if not pdfs:
                continue
            primary = pdfs[0]
            if primary in seen:
                continue
            seen.add(primary)
            text = _strip_html(part)
            title = text[:240] if text else primary.rsplit("/", 1)[-1]
            rows.append(
                {
                    "titulo": title,
                    "fecha": _fecha_from_pdf_url(primary),
                    "url": primary,
                    "tipo": _proyecto_tipo("", title),
                    "origen": "web_tramitacion_pdf",
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
                    "fecha": doc.get("fechaaddef"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo("", nome, str(doc.get("figura") or "")),
                    "origen": "siotuga_pg",
                    "siotuga_id": doc.get("id"),
                    "figura": doc.get("figura"),
                }
            )
        for doc in self._siotuga_query(13)[: self.max_siotuga_des]:
            nome = str(doc.get("docnome") or "Instrumento de planeamiento")
            rows.append(
                {
                    "titulo": nome,
                    "fecha": doc.get("fechaaddef"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo("", nome, str(doc.get("figura") or "")),
                    "origen": "siotuga_des",
                    "siotuga_id": doc.get("id"),
                    "figura": doc.get("figura"),
                }
            )
        return rows

    def _fixed_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Documentos en tramitación — Urbanismo (web municipal)",
                "fecha": None,
                "url": TRAMITACION_URL,
                "tipo": "información pública",
                "origen": "web_tramitacion",
            },
            {
                "titulo": "Archivo PXOM Carballo",
                "fecha": None,
                "url": PXOM_ARCHIVO,
                "tipo": "PXOM",
                "origen": "pxom_archivo",
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
            {
                "titulo": "Catálogo trámites — Urbanismo (sede SXC)",
                "fecha": None,
                "url": URBANISMO_SEDE,
                "tipo": "trámites urbanismo",
                "origen": "sede_catalogo",
            },
        ]

    def _licencia_tramites(self) -> list[dict[str, Any]]:
        return [
            {"titulo": title, "url": url, "origen": "sede_tramite_info"}
            for title, url in DEFAULT_LICENCIA_TRAMITES
        ]

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.web_base
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{url}|{titulo}|{row.get('codigo','')}"),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo")
            or _proyecto_tipo(str(row.get("section") or ""), titulo, row.get("figura")),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("codigo"):
            rec["expediente_codigo"] = row["codigo"]
        if row.get("detalle_url"):
            rec["detalle_url"] = row["detalle_url"]
        if row.get("siotuga_id"):
            rec["siotuga_doc_id"] = row["siotuga_id"]
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
        return {
            "id": _stable_id("lic", url + titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite / anuncio urbanismo",
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

    def _is_proyecto_row(self, row: dict[str, Any]) -> bool:
        titulo = row.get("titulo") or ""
        section = str(row.get("section") or "")
        if section.strip().upper() == "URBANISMO":
            return True
        if row.get("origen", "").startswith("siotuga"):
            return True
        if row.get("origen", "").startswith("web_tramitacion"):
            return True
        if row.get("origen", "").startswith("web_tramitacion_pdf"):
            return True
        if row.get("origen") in {"pxom_archivo", "siotuga_inventario", "siotuga_urb", "web_tramitacion", "sede_catalogo"}:
            return True
        return bool(RE_PROYECTO.search(titulo))

    def _collect_proyecto_sources(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._fixed_seeds())
        rows.extend(self._collect_siotuga())
        rows.extend(self._collect_wp_tramitacion())
        tablon = self._collect_tablon()
        for item in tablon:
            if self._is_proyecto_row(item):
                rows.append(item)
        return rows

    def _collect_licencia_sources(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._licencia_tramites())
        for item in self._collect_tablon():
            if RE_LICENCIA.search(item.get("titulo") or ""):
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
        return {"rows": len(rows), "status": "ok", "source": "sede_sxc_info_tablon"}

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
            "web_tramitacion": sum(
                1 for r in rows if "tramitacion" in str(r.get("origen", ""))
            ),
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
