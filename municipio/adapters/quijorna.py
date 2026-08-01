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

WP_BASE = "https://aytoquijorna.org"
SEDE_BASE = "https://aytoquijorna.sedelectronica.es"
MUNICIPIO = "Quijorna"
ID_PREFIX = "quijorna"

NORMATIVA_URL = f"{WP_BASE}/concejalias/urbanismo/normativa-urbanistica/"
TRAMITES_URL = f"{WP_BASE}/concejalias/urbanismo/tramites-y-gestiones-de-urbanismo/"
CATALOGO_URL = (
    f"{WP_BASE}/concejalias/urbanismo/catalogo-de-procedimientos-y-actuaciones-urbanisticas/"
)
BOARD_URL = f"{SEDE_BASE}/board"
BOARD_URBANISMO_URL = f"{SEDE_BASE}/board/974e6d5e-f59b-11de-b600-00237da12c6a/"
TRANSP_NNSS = f"{SEDE_BASE}/transparency/07b48e79-055a-4d36-8e84-13c209f18f6b/"
TRANSP_SECTOR5 = f"{SEDE_BASE}/transparency/f3a06c71-7022-4309-8f9d-eb96272419be/"
TRANSP_COMPLEMENTARIA = (
    f"{SEDE_BASE}/transparency/ad88615a-a13d-4576-a91d-63050c8fc9f8/"
)
BOCM_NNSS_URL = (
    "https://www.bocm.es/boletin/CM_Orden_BOCM/2021/04/30/BOCM-20210430-21.PDF"
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"tramitacion.*obra|primera ocupaci[oó]n|tasa.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva)|parcela|suelo|sector|ordenanza|"
    r"normas subsidiarias|nnss|segregaci[oó]n|bando.*parcel|actuaci[oó]n)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://aytoquijorna\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_TRANSPARENCY_FOLDER = re.compile(
    r'class="gIconLink exp"[^>]*>(.*?)(?:<span class="linkExtraInfo">|$)',
    re.I | re.S,
)
RE_WP_PDF = re.compile(
    r'href="((?:https://aytoquijorna\.org)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOCM_DATE = re.compile(r"BOCM[- ]?(\d{4})(\d{2})(\d{2})", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


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
    m = RE_BOCM_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_wp(href: str) -> str:
    return urllib.parse.urljoin(f"{WP_BASE}/", unescape(href))


def _abs_sede(href: str, base: str = SEDE_BASE) -> str:
    return urllib.parse.urljoin(f"{base.rstrip('/')}/", unescape(href))


def _doc_tipo(name: str) -> str:
    n = name.lower()
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "sector" in n and ("plan" in n or "parcial" in n):
        return "plan parcial"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "modific" in n:
        return "modificación planeamiento"
    if "acuerdo" in n and "aprobaci" in n:
        return "acuerdo aprobación"
    if "plano" in n:
        return "planos ordenación"
    if "bocm" in n:
        return "publicación BOCM"
    if "tramitacion" in n or "tramitación" in n:
        return "guía tramitación"
    if "bando" in n and "parcel" in n:
        return "bando parcelas"
    return "documento urbanismo"


class QuijornaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress urbanismo + sede espublico (tablón + transparencia Wicket)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.board_urbanismo_url = str(
            self.config.get("board_urbanismo_url") or BOARD_URBANISMO_URL
        )
        self.normativa_url = str(self.config.get("normativa_url") or NORMATIVA_URL)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.transp_urls = [
            str(
                self.config.get("transparency_normativa_url")
                or TRANSP_NNSS
            ),
            str(self.config.get("transparency_sector5_url") or TRANSP_SECTOR5),
            str(
                self.config.get("transparency_complementaria_url")
                or TRANSP_COMPLEMENTARIA
            ),
        ]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-quijorna/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _collect_board(self, board_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(board_url)
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
            url = preview_m.group(1) if preview_m else board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo and expediente != "Mis Documentos":
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
                    "origen": origen,
                }
            )
        return rows

    def _collect_all_boards(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in (
            (self.board_url, "tablon_sede"),
            (self.board_urbanismo_url, "tablon_urbanismo"),
        ):
            for row in self._collect_board(url, origen):
                by_url[row["url"]] = row
        return list(by_url.values())

    def _collect_wp_pdfs(self, page_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_WP_PDF.finditer(html):
            pdf = _abs_wp(m.group(1))
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(name) or _fecha_from_blob(pdf),
                    "url": page_url,
                    "pdf_url": pdf,
                    "tipo": _doc_tipo(name),
                    "origen": origen,
                }
            )
        return rows

    def _collect_transparency(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(titulo: str, url: str, origen: str, fecha: str | None = None) -> None:
            key = f"{url}#{titulo}"
            if key in seen or len(titulo) < 5:
                return
            seen.add(key)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha or _fecha_from_blob(titulo),
                    "url": url,
                    "origen": origen,
                    "blob": titulo,
                }
            )

        for transp_url in self.transp_urls:
            try:
                html = self._fetch(transp_url)
            except urllib.error.URLError:
                continue

            dossier_label = "NNSS" if "07b48e79" in transp_url else (
                "Sector 5" if "f3a06c71" in transp_url else "ordenanzas complementarias"
            )
            for m in RE_TRANSPARENCY_FOLDER.finditer(html):
                title = _strip_html(m.group(1))
                if not title or len(title) < 8:
                    continue
                add(
                    f"{dossier_label}: {title}",
                    transp_url,
                    f"transparencia_{dossier_label.replace(' ', '_').lower()}",
                )

            for m in RE_PREVIEW_LINK.finditer(html):
                url = _abs_sede(m.group(1))
                local = html[max(0, m.start() - 500) : m.end() + 200]
                title_m = re.search(
                    r'>([^<]{5,300})</a>\s*$',
                    local[: local.rfind(url.split("/")[-1])],
                    re.I,
                )
                title = _strip_html(title_m.group(1)) if title_m else url
                add(title, url, "transparencia_preview", _fecha_from_blob(title))

        return rows

    def _collect_bocm_link(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": (
                    "Actuaciones no necesitadas de calificación urbanística por la "
                    "Comunidad de Madrid (BOCM nº102, 30 abril 2021)"
                ),
                "fecha": "2021-04-30",
                "url": self.normativa_url,
                "pdf_url": BOCM_NNSS_URL,
                "tipo": "publicación BOCM",
                "origen": "normativa_web",
            }
        ]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "trámites licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites y gestiones de urbanismo — guías PDF",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Guías informativas; concesiones en tablón cuando proceda",
                "origen": "urbanismo_web",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — catálogo trámites urbanismo y vivienda",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Presentación electrónica de solicitudes",
                "origen": "sede_tramites",
            },
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y edictos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y notificaciones publicadas en sede",
                "origen": "tablon_sede",
            },
        ]
        for doc in self._collect_wp_pdfs(self.tramites_url, "tramites_web"):
            if RE_LICENCIA.search(doc.get("titulo") or ""):
                rows.append(
                    {
                        "id": _stable_id("lic", doc.get("pdf_url") or doc["url"]),
                        "fecha_concesion": doc.get("fecha"),
                        "tipo": doc.get("tipo") or "guía tramitación",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": doc["titulo"],
                        "url": doc.get("url") or self.tramites_url,
                        "pdf_url": doc.get("pdf_url"),
                        "source": "ayuntamiento",
                        "nota": "Guía de trámite; no concesión publicada",
                        "origen": doc.get("origen"),
                    }
                )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        tipo = "urbanismo"
        if re.search(r"(?i)bando.*parcel", blob):
            tipo = "bando parcelas"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            tipo = "información pública"
        return {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }

    def _doc_to_proyecto(self, doc: dict[str, Any]) -> dict[str, Any]:
        key = doc.get("pdf_url") or doc["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": doc["titulo"][:500],
            "fecha": doc.get("fecha"),
            "tipo": doc.get("tipo") or "documento urbanismo",
            "url": doc.get("url") or key,
            "pdf_url": doc.get("pdf_url"),
            "source": "ayuntamiento",
            "origen": doc.get("origen"),
        }

    def _transparency_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", item["url"] + item["titulo"][:80]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"][:500],
            "fecha": item.get("fecha"),
            "tipo": _doc_tipo(item["titulo"]),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

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
        for row in self._collect_all_boards():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "urbanismo_tablon"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for row in self._collect_all_boards():
            rec = self._board_to_licencia(row)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for doc in (
            self._collect_wp_pdfs(self.normativa_url, "normativa_web")
            + self._collect_wp_pdfs(self.tramites_url, "tramites_web")
            + self._collect_wp_pdfs(self.catalogo_url, "catalogo_web")
            + self._collect_bocm_link()
        ):
            blob = f"{doc.get('titulo','')} {doc.get('pdf_url','')}"
            if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if RE_PROYECTO.search(blob) or doc.get("origen") == "normativa_web":
                add(self._doc_to_proyecto(doc))

        for item in self._collect_transparency():
            add(self._transparency_to_proyecto(item))

        for row in self._collect_all_boards():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia": sum(1 for r in rows if str(r.get("origen", "")).startswith("transparencia")),
            "tablon": sum(1 for r in rows if "tablon" in str(r.get("origen", ""))),
            "web": sum(1 for r in rows if str(r.get("origen", "")).endswith("_web")),
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
