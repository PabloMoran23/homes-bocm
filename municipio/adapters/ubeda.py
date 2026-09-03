from __future__ import annotations

import hashlib
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

TRANSP_BASE = "https://transparencia.ayuntamientodeubeda.com"
SEDE_BASE = "https://sede.ubeda.es"
WP_BASE = "https://ubeda.es"
LEGACY_BASE = "http://ayuntamientodeubeda.com"
TRANSP_LOCAL = "https://aytoubeda.transparencialocal.gob.es"
MUNICIPIO = "Úbeda"
ID_PREFIX = "ubeda"

PLANES_URBANISTICOS = f"{TRANSP_BASE}/2023/02/02/planes-urbanisticos/"
PERFIL_CONTRATANTE = f"{SEDE_BASE}/eAdmin/PerfilContratante.do?action=verPublicaciones"
TRAMITES_URL = f"{SEDE_BASE}/eAdmin/Registrar.do?action=inicioPortalTramites"
TRANSP_LOCAL_URBANISMO = f"{TRANSP_LOCAL}/es_ES/urbanismo"

DEFAULT_SEED_PAGES: list[str] = [
    PLANES_URBANISTICOS,
    f"{TRANSP_BASE}/2026/06/10/plan-de-actuacion-integrado-ubeda-baeza/",
    f"{TRANSP_BASE}/2023/11/22/planes-anuales-normativos/",
    TRANSP_LOCAL_URBANISMO,
    f"{WP_BASE}/es/node/548",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|alineaci[oó]n|ocupaci[oó]n|parcelaci[oó]n|"
    r"primera utilizaci[oó]n|apertura de locales|cambio de titularidad)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pepch|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|viabilidad)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|cat[aá]logo|alineaci[oó]n|clasificaci[oó]n del suelo|"
    r"junta de compensaci[oó]n|actuaci[oó]n|innovaci[oó]n|consulta previa|"
    r"reforma interior|patrimonio|urbanizaci[oó]n|contrato.*obra|obra p[uú]blica)",
)
RE_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"bolsa de trabajo|tribunal calificador|orientaci[oó]n laboral|"
    r"ofertas de empleo|igualdad|recursos multimedia|entrevista de trabajo|"
    r"licencia taxi|autotaxi|mercadillo)",
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://[^"\']+|/[^"\']+))["\']',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href=["\'](https://transparencia\.ayuntamientodeubeda\.com/wp-content/uploads/[^"\']+\.pdf)["\']',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PC_IDENT = re.compile(
    r'identif=([A-F0-9]+)[^>]*>.*?'
    r'Id expediente:\s*</b>\s*([^<]+).*?'
    r'Tipo:\s*</b>\s*([^<]+)',
    re.I | re.S,
)
RE_TRAMITE_MODAL = re.compile(
    r'<h4 class="modal-title"[^>]*>([^<]+)</h4>',
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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"/(\d{4})/(\d{2})/", url or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _abs_url(href: str, base: str) -> str:
    return urllib.parse.urljoin(base, unescape(href))


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "pepch" in b or "patrimonio" in b or "centro hist" in b:
        return "PEPCH"
    if "plan parcial" in b or "sector" in b:
        return "plan parcial"
    if "junta de compensaci" in b or "reparcel" in b:
        return "reparcelación"
    if "convenio" in b:
        return "convenio urbanístico"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "consulta previa" in b:
        return "consulta previa"
    if "innovaci" in b or "modificaci" in b:
        return "modificación puntual"
    if "obra p" in b and "blica" in b or "contrato" in b:
        return "obra pública"
    if "licencia" in b:
        return "licencia publicada"
    if "estudio" in b and "viabilidad" in b:
        return "estudio de viabilidad"
    return "planeamiento"


class UbedaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress transparencia + transparencialocal Absis + sede eAdmin (tramites + perfil contratante)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or TRANSP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.planes_url = str(self.config.get("planes_urbanisticos_url") or PLANES_URBANISTICOS)
        self.perfil_url = str(self.config.get("perfil_contratante_url") or PERFIL_CONTRATANTE)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.transp_local_url = str(
            self.config.get("transparencia_local_url") or TRANSP_LOCAL_URBANISMO
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wp_max_pages = int(self.config.get("wp_max_pages", 3))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, latin1: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ubeda/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90, context=self._ssl_ctx) as resp:
            raw = resp.read()
        if latin1 or "sede.ubeda.es" in url:
            return raw.decode("latin-1", errors="replace")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _collect_planes_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.planes_url)
        except urllib.error.URLError:
            return rows

        for m in re.finditer(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>',
            html,
            re.I,
        ):
            url = _abs_url(m.group(1), self.planes_url)
            text = _strip_html(m.group(2))
            if not text and "wp-content" in url:
                text = unescape(urllib.parse.unquote(Path(url).stem.replace("-", " ")))
            blob = f"{text} {url}"
            if not (
                url.lower().endswith(".pdf")
                or "carga_archivos/urbanismo" in url
                or "transparencialocal.gob.es" in url
            ):
                continue
            if not RE_PROYECTO.search(blob) and "urbanismo" not in url.lower():
                continue
            if url in seen:
                continue
            seen.add(url)
            titulo = text[:500] if text else Path(url).stem.replace("-", " ")[:500]
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_blob(blob, url),
                    "url": self.planes_url,
                    "pdf_url": url,
                    "origen": "transparencia_planes",
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for page in range(1, self.wp_max_pages + 1):
            url = (
                f"{self.transp_base}/wp-json/wp/v2/posts"
                f"?per_page=100&page={page}&_fields=id,date,link,title,content"
            )
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(data, list) or not data:
                break
            for post in data:
                pid = int(post.get("id") or 0)
                if pid in seen:
                    continue
                seen.add(pid)
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                content = post.get("content", {}).get("rendered", "") or ""
                blob = f"{title} {content}"
                if RE_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                pdf_m = RE_WP_PDF.search(content)
                rows.append(
                    {
                        "id": pid,
                        "titulo": title[:500],
                        "fecha": (post.get("date") or "")[:10] or None,
                        "url": post.get("link") or "",
                        "pdf_url": pdf_m.group(1) if pdf_m else None,
                        "content": content,
                        "origen": "transparencia_wp",
                    }
                )
            if len(data) < 100:
                break
        return rows

    def _collect_perfil_contratante(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.perfil_url, latin1=True)
        except urllib.error.URLError:
            return rows

        chunks = html.split("identif=")
        seen: set[str] = set()
        for chunk in chunks[1:]:
            ident = chunk[:16].split('"')[0].split("&")[0]
            if ident in seen:
                continue
            exp_m = re.search(r"Id expediente:\s*</b>\s*([^<]+)", chunk)
            tipo_m = re.search(r"Tipo:\s*</b>\s*([^<]+)", chunk)
            if not exp_m:
                continue
            expediente = exp_m.group(1).strip()
            tipo = (tipo_m.group(1).strip() if tipo_m else "").lower()
            if "obra" not in tipo:
                continue
            seen.add(ident)
            detail_url = (
                f"{self.sede_base}/eAdmin/PerfilContratante.do"
                f"?action=verPublicacion&identif={ident}"
            )
            titulo = f"Contrato obras exp. {expediente}"
            desc_m = re.search(r"Descripci[oó]n[^<]*</[^>]+>\s*([^<]+)", chunk, re.I)
            ref_m = re.search(r"Referencia[^<]*</[^>]+>\s*([^<]+)", chunk, re.I)
            if ref_m and ref_m.group(1).strip():
                titulo = ref_m.group(1).strip()[:500]
            elif desc_m and desc_m.group(1).strip():
                titulo = desc_m.group(1).strip()[:500]
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_blob(expediente),
                    "url": detail_url,
                    "expte": expediente,
                    "origen": "perfil_contratante",
                }
            )
        return rows

    def _collect_sede_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.tramites_url, latin1=True)
        except urllib.error.URLError:
            return rows
        seen: set[str] = set()
        for m in RE_TRAMITE_MODAL.finditer(html):
            titulo = m.group(1).strip()
            if not RE_LICENCIA.search(titulo):
                continue
            if titulo in seen:
                continue
            seen.add(titulo)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": self.tramites_url,
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "trámites sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica Úbeda — trámites urbanismo y obras",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Formularios solicitud; sin tablón de concesiones",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", "https://portaltributario.ayuntamientodeubeda.com"),
                "fecha_concesion": None,
                "tipo": "autoliquidación tasa urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal tributario — tasa licencias urbanísticas / ICIO",
                "url": "https://portaltributario.ayuntamientodeubeda.com",
                "source": "ayuntamiento",
                "origen": "portal_tributario",
            },
            {
                "id": _stable_id("lic", self.planes_url),
                "fecha_concesion": None,
                "tipo": "información urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Planes urbanísticos — transparencia",
                "url": self.planes_url,
                "source": "ayuntamiento",
                "origen": "transparencia",
            },
        ]

    def _tramite_to_licencia(self, item: dict[str, Any]) -> dict[str, Any]:
        titulo = item["titulo"]
        return {
            "id": _stable_id("lic", titulo),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": item.get("url", self.tramites_url),
            "source": "ayuntamiento",
            "nota": "Formulario informativo; no concesión publicada",
            "origen": item.get("origen", "sede_tramite"),
        }

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item.get("titulo") or ""
        blob = f"{titulo} {item.get('content', '')} {item.get('expte', '')}"
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = item.get("pdf_url") or item.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": item.get("url", ""),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        if item.get("expte"):
            rec["expte"] = item["expte"]
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_sede_tramites():
            rec = self._tramite_to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_wp_posts():
            titulo = item.get("titulo") or ""
            if RE_LICENCIA.search(titulo) and not RE_NON_URBAN.search(titulo):
                key = item.get("pdf_url") or item.get("url") or titulo
                rec = {
                    "id": _stable_id("lic", key),
                    "fecha_concesion": item.get("fecha"),
                    "tipo": "licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": item.get("url", ""),
                    "source": "ayuntamiento",
                    "origen": "transparencia_wp",
                }
                if item.get("pdf_url"):
                    rec["pdf_url"] = item["pdf_url"]
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
            "info": sum(1 for r in rows if r.get("origen") not in ("sede_tramite", "transparencia_wp")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
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

        for item in self._collect_planes_pdfs():
            add(self._item_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._item_to_proyecto(item))
        for item in self._collect_perfil_contratante():
            add(self._item_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "planes": sum(1 for r in rows if r.get("origen") == "transparencia_planes"),
            "wp": sum(1 for r in rows if r.get("origen") == "transparencia_wp"),
            "contratacion": sum(1 for r in rows if r.get("origen") == "perfil_contratante"),
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
