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
from municipio.geometry import record_geometry

WEB_BASE = "https://www.santjosep.org"
SEDE_BASE = "https://santjosep.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
URBANISME_URL = f"{WEB_BASE}/el-teu-municipi/urbanisme/"
TRAMITS_URL = f"{WEB_BASE}/tramits-gestions/urbanisme/"
MUIB_URL = "http://muib.caib.es/mapurbibfront/visor_index.jsp"
MUNICIPIO = "Sant Josep de sa Talaia"
ID_PREFIX = "sant-josep-de-sa-talaia"

RE_BOARD_ROW = re.compile(r"<tr>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://santjosep\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licen|llic[eè]ncia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó]n responsable|obra major|obra menor|demolici|enderroc|"
    r"segregaci|certificat|qualificaci[oó] urban|final d.obra|autoritzaci)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|planej|nnss|normes subsidi|modificaci[oó]n puntual|"
    r"modificaci[oó] puntual|informaci[oó] p[uú]blica|expedient|proyecto|"
    r"aprovaci[oó]|boib|anunci|pl[aà]nol|determinaci|ordenaci[oó]|"
    r"actuaci[oó]n urban|plan territorial|muib|ordenan)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(padr[oó]n|junta de govern|ple\b|convocat[oò]ria.*ple|"
    r"selecci[oó]n de personal|subvencion|subvenci[oó]|taxi|cer/cere|"
    r"reclamaciones estimadas|listado de exposici)",
)
RE_URBAN_SIGNAL = re.compile(
    r"(?i)(urban|obra[s]?|planeam|planej|licen|llic[eè]ncia|nnss|"
    r"modificaci[oó]n|informaci[oó] p[uú]blica|actuaci[oó]n urban|"
    r"aprovaci[oó]|boib|segregaci|demolici|ordenaci[oó])",
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?santjosep\.org)?/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_TRAMIT_BLOCK = re.compile(
    r"<h2>([^<]+)</h2>\s*<p>(.*?)</p>\s*<div>\s*<a href=\"([^\"]+)\"",
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "modificaci" in n and "puntual" in n:
        return "modificación puntual NNSS"
    if "nnss" in n or "normes subsidi" in n:
        return "NNSS"
    if "plà" in n or "plano" in n or "determinaci" in n:
        return "plano determinaciones"
    if "plan territorial" in n or "pti" in n:
        return "plan territorial"
    if "ordenan" in n:
        return "ordenanza"
    if "boib" in n:
        return "publicación BOIB"
    return "urbanismo"


def _licencia_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "comunicaci" in n:
        return "comunicación previa"
    if "segregaci" in n:
        return "licencia segregación"
    if "demolici" in n or "enderroc" in n:
        return "licencia demolición"
    if "certificat" in n:
        return "certificado urbanístico"
    if "obra major" in n:
        return "licencia obra mayor"
    return "trámite urbanismo"


class SantJosepDeSaTalaiaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress santjosep.org + sede espublico gestiona (Illes Balears / Eivissa)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.urbanisme_page_id = int(self.config.get("urbanisme_page_id") or 1467)
        self.tramits_page_id = int(self.config.get("tramits_page_id") or 2602)
        self.muib_url = str(self.config.get("muib_url") or MUIB_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            if not documento or documento in ("Document", "Documento"):
                continue

            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if "urban" in proc or "obra" in proc:
            return True
        return bool(RE_URBAN_SIGNAL.search(blob) or RE_LICENCIA.search(blob))

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_URBAN_SIGNAL.search(blob):
            return None
        if not RE_URBAN_SIGNAL.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", f"board:{key}"),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", f"board:{key}"),
            "fecha_concesion": row.get("fecha"),
            "tipo": _licencia_tipo(blob),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _collect_wp_page_content(self, page_id: int) -> str:
        try:
            page = self._fetch_json(f"{self.web_base}/wp-json/wp/v2/pages/{page_id}")
        except (urllib.error.URLError, json.JSONDecodeError):
            return ""
        return str((page.get("content") or {}).get("rendered") or "")

    def _pdfs_from_html(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href in RE_PDF_HREF.findall(html or ""):
            url = self._abs_web(href)
            if url in seen:
                continue
            seen.add(url)
            name = unescape(urllib.parse.unquote(Path(url).name.replace("+", " ")))
            blob = f"{name} {url}"
            on_urbanisme = "urbanisme" in page_url or "urbanismo" in page_url
            if not on_urbanisme and not RE_PROYECTO.search(blob) and "ordenan" not in name.lower():
                if not ("/uploads/" in url and re.search(r"(?i)\.pdf$", url)):
                    continue
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(name),
                    "tipo": _proyecto_tipo(blob),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "web_pdf",
                    "pagina": page_url,
                }
            )
        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        html = self._collect_wp_page_content(self.tramits_page_id)
        if not html:
            return []
        rows: list[dict[str, Any]] = []
        for title, body, href in RE_TRAMIT_BLOCK.findall(html):
            titulo = _strip_html(title)
            url = self._abs_web(href)
            if not url.startswith("http"):
                url = urllib.parse.urljoin(f"{TRAMITS_URL.rstrip('/')}/", href)
            blob = f"{titulo} {_strip_html(body)}"
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": _licencia_tipo(blob),
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": _strip_html(body)[:400],
                    "origen": "web_tramite",
                }
            )
        return rows

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tauler d'anuncis — sede electrónica Sant Josep",
                "url": self.board_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", TRAMITS_URL),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tràmits i gestions — Urbanisme",
                "url": TRAMITS_URL,
                "source": "ayuntamiento",
                "origen": "web_tramite",
            },
        ]

    def _collect_proyecto_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("proy", URBANISME_URL),
                "municipio": MUNICIPIO,
                "titulo": "Urbanisme — NNSS, modificacions i plànols",
                "fecha": None,
                "tipo": "planeamiento",
                "url": URBANISME_URL,
                "source": "ayuntamiento",
                "origen": "web_cms",
            },
            {
                "id": _stable_id("proy", self.muib_url),
                "municipio": MUNICIPIO,
                "titulo": "MUIB — Mapa Urbanístic de les Illes Balears",
                "fecha": None,
                "tipo": "visor cartográfico",
                "url": self.muib_url,
                "source": "ayuntamiento",
                "origen": "visor",
                "nota": "Consulta cartográfica insular; geometría no automatizable (IDEIB 403)",
            },
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_licencia_info():
            add(rec)
        for rec in self._collect_tramites():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") == "web_tramite"),
            "with_geometry": with_geom,
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_proyecto_seeds():
            add(rec)

        urbanisme_html = self._collect_wp_page_content(self.urbanisme_page_id)
        for rec in self._pdfs_from_html(urbanisme_html, URBANISME_URL):
            add(rec)

        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "pdfs": sum(1 for r in rows if r.get("origen") == "web_pdf"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "with_geometry": with_geom,
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
