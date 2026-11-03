from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records

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

WEB_BASE = "https://cangas.gal"
SEDE_BASE = "https://cangas.sedelectronica.gal"
MUNICIPIO = "Cangas"
ID_PREFIX = "cangas"
INE = "36008"

SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_QUERY_DOC = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"
SIOTUGA_URB = "https://siotuga.xunta.gal/siotuga/urb?lang=es_ES"
SIOTUGA_WMS_CAP = f"https://siotuga.xunta.gal/siotuga/ws?codine={INE}&SERVICE=WMS&REQUEST=GetCapabilities"

URBANISMO_URL = f"{WEB_BASE}/es/areas/urbanismo"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    f"{WEB_BASE}/es/areas/urbanismo/inventario",
    f"{WEB_BASE}/es/areas/urbanismo/pxom",
    f"{WEB_BASE}/es/areas/urbanismo/pepri",
    f"{WEB_BASE}/es/areas/urbanismo/normativa",
    f"{WEB_BASE}/es/areas/urbanismo/plan-basico-autonomico",
    f"{WEB_BASE}/es/transparencia",
]

DEFAULT_LICENCIA_SEEDS: list[tuple[str, str]] = [
    ("Taboleiro de anuncios — sede electrónica", f"{SEDE_BASE}/board"),
    (
        "Catálogo trámites urbanismo (comunicación previa, licencia obras, primera ocupación)",
        f"{SEDE_BASE}/dossier",
    ),
    ("Urbanismo — trámites y normativa municipal", URBANISMO_URL),
]

RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_PDF = re.compile(r"\.pdf(?:\?|#|$)", re.I)
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_URBAN = re.compile(
    r"(?i)(urban|licen|planeam|pxom|pepri|obra|territ|convenio|sector|reparcel|"
    r"exposici[oó]n|informaci[oó]n p[uú]blica|modificaci[oó]n|ordenanza|edusi|"
    r"arqueol|normativa|instrumento)",
)
RE_LICENCIA = re.compile(
    r"(?i)(licen|licenza|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n|primeira ocupaci|primera ocupaci|obra maior|obra mayor|"
    r"licencia urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(plan|planeam|pxom|pepri|sector|convenio|urban|exposici[oó]n|"
    r"informaci[oó]n p[uú]blica|modificaci[oó]n|reparcel|ordenanza|instrumento|"
    r"normas subsidi|edusi|arqueol)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|subvenci[oó]n|padron|padr[oó]n|"
    r"ple municipal|contractaci|ocupaci[oó] p[uú]blica|mercado|iae|domiciliaci)",
)
RE_BOARD_ROW = re.compile(r'<tr[^>]*>\s*<td class="class_name".*?</tr>', re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://cangas\.sedelectronica\.gal)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_TRANSPARENCY_ROW = re.compile(r"<tr[^>]*>.*?</tr>", re.I | re.S)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_web(base_page: str, href: str) -> str:
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
    if "pxom" in blob or "plan xeral" in blob or "plan general" in blob:
        return "PXOM/PGOM"
    if "pepri" in blob:
        return "PEPRI"
    if "normas subsidi" in blob:
        return "normas subsidiarias"
    if "sector" in blob or "saur" in blob or "cho" in blob:
        return "planeamiento de desarrollo"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "exposici" in blob or "información pública" in blob or "informacion publica" in blob:
        return "información pública"
    if "arqueol" in blob:
        return "patrimonio / planeamiento"
    if "modificaci" in blob:
        return "modificación planeamiento"
    return figura or "planeamiento"


class CangasAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal cangas.gal + sede espublico gestiona (/board) + SIOTUGA (INE 36008)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_siotuga_des = int(self.config.get("max_siotuga_desarrollo", 80))
        self.sede_timeout = float(self.config.get("sede_timeout_s", 45))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._siotuga_token: str | None = None
        self._transparency_urls: list[str] | None = None

    def _fetch(self, url: str, *, data: bytes | None = None, timeout: float | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-cangas/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._opener.open(req, timeout=timeout or 90) as resp:
            enc = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(enc, errors="replace")

    def _fetch_sede(self, url: str) -> str:
        return self._fetch(url, timeout=self.sede_timeout)

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

    def _get_siotuga_token(self) -> str:
        if self._siotuga_token:
            return self._siotuga_token
        html = self._fetch(SIOTUGA_INVENTARIO)
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
        raw = self._fetch(SIOTUGA_QUERY_DOC, data=data)
        if not raw.strip() or raw.startswith("tokenIncorrecto"):
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

    def _transparency_seed_urls(self) -> list[str]:
        if self._transparency_urls is not None:
            return self._transparency_urls
        urls: list[str] = []
        try:
            html = self._fetch(URBANISMO_URL)
        except urllib.error.URLError:
            self._transparency_urls = urls
            return urls
        for href in RE_HREF.findall(html):
            if "/transparency/" not in href:
                continue
            urls.append(self._abs_sede(href))
        self._transparency_urls = list(dict.fromkeys(urls))
        return self._transparency_urls

    def _collect_transparency(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self._transparency_seed_urls():
            try:
                html = self._fetch_sede(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_TRANSPARENCY_ROW.finditer(html):
                row_html = m.group(0)
                if "preview-document" not in row_html:
                    continue
                preview_m = RE_PREVIEW_LINK.search(row_html)
                if not preview_m:
                    continue
                url = self._abs_sede(preview_m.group(1))
                if url in seen:
                    continue
                seen.add(url)
                titulo = _strip_html(row_html)
                title_m = re.search(r'title="([^"]+)"', row_html)
                if title_m and len(title_m.group(1).strip()) > 8:
                    titulo = title_m.group(1).strip()
                if not RE_URBAN.search(titulo):
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _parse_fecha(titulo),
                        "url": url,
                        "tipo": _proyecto_tipo(titulo),
                        "origen": "sede_transparencia",
                    }
                )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch_sede(self.board_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))
            documento = cells.get("class_name", "")
            if not documento or documento in ("Documento",):
                continue
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")
            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            url = self._abs_sede(url)
            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"
            blob = (
                f"{documento} {expediente} {procedimiento} {categoria} "
                f"{descripcion} {title_m.group(1) if title_m else ''}"
            )
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "fecha": _parse_fecha(fecha_raw),
                    "url": url,
                    "blob": blob,
                    "origen": "sede_tablon",
                }
            )
        return rows

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
                url = _abs_web(page, href)
                if "cangas.gal" not in url and "cangas.sedelectronica.gal" not in url:
                    continue
                if RE_PDF.search(url):
                    name = urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace(".pdf", "").replace("_", " ")
                    add(name or "Documento PDF", url, "drupal_pdf", _parse_fecha(url))
                elif "/areas/urbanismo" in url and url.rstrip("/") != page.rstrip("/"):
                    slug_part = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
                    if RE_URBAN.search(slug_part):
                        add(slug_part, url, "drupal_link")
        return rows

    def _fixed_proyecto_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Inventario planeamento — SIOTUGA (INE 36008)",
                "fecha": None,
                "url": SIOTUGA_INVENTARIO,
                "tipo": "inventario planeamiento",
                "origen": "siotuga_inventario",
            },
            {
                "titulo": "Taboa planeamento urbanístico — SIOTUGA Galicia",
                "fecha": None,
                "url": SIOTUGA_URB,
                "tipo": "planeamiento",
                "origen": "siotuga_urb",
            },
            {
                "titulo": "PXOM — documentación municipal",
                "fecha": None,
                "url": f"{self.web_base}/es/areas/urbanismo/pxom",
                "tipo": "PXOM/PGOM",
                "origen": "web_pxom",
            },
            {
                "titulo": "PEPRI — Plan Especial Protección Ría de Vigo",
                "fecha": None,
                "url": f"{self.web_base}/es/areas/urbanismo/pepri",
                "tipo": "PEPRI",
                "origen": "web_pepri",
            },
        ]

    def _licencia_seeds(self) -> list[dict[str, Any]]:
        return [
            {"titulo": title, "url": url, "origen": "tramite_info", "tipo": "información trámite"}
            for title, url in DEFAULT_LICENCIA_SEEDS
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo')} {row.get('blob', '')} {row.get('procedimiento', '')}"
        if RE_BOARD_NON_URBAN.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row.get("url") or row.get("expediente") or row["titulo"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia / anuncio urbanístico",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row.get("url") or self.board_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo')} {row.get('blob', '')} {row.get('procedimiento', '')}"
        if RE_BOARD_NON_URBAN.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "url": row.get("url") or self.board_url,
            "tipo": _proyecto_tipo(row["titulo"], row.get("procedimiento")),
            "origen": row.get("origen"),
            "expediente": row.get("expediente"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.web_base
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{url}|{titulo}|{row.get('siotuga_id', '')}|{row.get('expediente', '')}"),
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
        if row.get("expediente"):
            rec["expediente"] = row["expediente"]
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
        rows = reviewed_records(path, rows)
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
        for board_row in self._collect_board():
            rec = self._board_to_licencia(board_row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon_y_tramites"}

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
        for item in self._collect_transparency():
            add(item)
        for board_row in self._collect_board():
            mapped = self._board_to_proyecto(board_row)
            if mapped:
                add(mapped)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_tablon"),
            "drupal": sum(1 for r in rows if str(r.get("origen", "")).startswith("drupal_")),
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
