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
URBANISMO_URL = f"{WP_BASE}/concejalias/urbanismo/"
TRAMITES_URL = f"{WP_BASE}/concejalias/urbanismo/tramites-y-gestiones-de-urbanismo/"
BOARD_URL = f"{SEDE_BASE}/board/"
BOARD_URBANISMO_URL = f"{SEDE_BASE}/board/974e6d5e-f59b-11de-b600-00237da12c6a/"
NORMATIVA_DOSSIER = f"{SEDE_BASE}/transparency/c3bde2cb-3329-460a-9b0b-d02e55dc25f5/"
ORDENANZAS_DOSSIER = f"{SEDE_BASE}/transparency/ad88615a-a13d-4576-a91d-63050c8fc9f8/"
MUNICIPIO = "Quijorna"
ID_PREFIX = "quijorna"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"tramitaci[oó]n.*obra|primera ocupaci[oó]n|demolici[oó]n|piscina|pozo)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva)|parcela|suelo|ordenanza|normas subsidiarias|"
    r"nnss|segregaci[oó]n|divisi[oó]n parcelaria|bando.*parcel|tramitaci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://aytoquijorna\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="((?:https://aytoquijorna\.org)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_DOSSIER_LINK = re.compile(
    r'href="(https://aytoquijorna\.sedelectronica\.es/preview-document/[a-f0-9-]+)"'
    r'[^>]*>([^<]+)</a>',
    re.I,
)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{prefix}-{h}"


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
    m = re.search(r"BOCM[- ]?(\d{4})(\d{2})(\d{2})", text or "", re.I)
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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _doc_tipo(name: str) -> str:
    n = name.lower()
    if "normas subsidiarias" in n or "nnss" in n or "tomo ii" in n:
        return "normas subsidiarias"
    if "ordenanza" in n or n.startswith("0") and ". o." in n:
        return "ordenanza urbanística"
    if "convenio" in n:
        return "convenio urbanístico"
    if re.search(r"declaraci[oó]n responsable", n):
        return "declaración responsable"
    if "licencia" in n or "obra" in n:
        return "guía tramitación licencia"
    if "segregaci" in n or "divisi" in n or "agrupaci" in n:
        return "segregación / agrupación"
    if "bando" in n and "parcel" in n:
        return "bando urbanístico"
    return "documento urbanismo"


class QuijornaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress citygov + sede espublico eHome + transparencia NN.SS/ordenanzas."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_urls = [
            str(self.config.get("board_url") or BOARD_URL),
            str(self.config.get("board_urbanismo_url") or BOARD_URBANISMO_URL),
        ]
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.normativa_dossier = str(self.config.get("normativa_dossier") or NORMATIVA_DOSSIER)
        self.ordenanzas_dossier = str(self.config.get("ordenanzas_dossier") or ORDENANZAS_DOSSIER)
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

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{WP_BASE}/", href)

    def _collect_dossier(self, url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(url)
        except (urllib.error.URLError, OSError):
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_DOSSIER_LINK.finditer(html):
            doc_url, titulo = m.group(1), unescape(m.group(2).strip())
            if doc_url in seen:
                continue
            seen.add(doc_url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": doc_url,
                    "pdf_url": doc_url,
                    "tipo": _doc_tipo(titulo),
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for board_url in self.board_urls:
            try:
                html = self._fetch(board_url)
            except (urllib.error.URLError, OSError):
                continue

            for m in RE_BOARD_ROW.finditer(html):
                row_html = m.group(1)
                if "preview-document" not in row_html:
                    continue
                cells = [_strip_html(c) for c in RE_BOARD_CELL.findall(row_html)]
                cells = [c for c in cells if c]
                if len(cells) < 4:
                    continue
                if cells[0] in ("Documento", "Expediente"):
                    continue

                documento = cells[0] if len(cells) > 0 else ""
                expediente = cells[1] if len(cells) > 1 else ""
                procedimiento = cells[2] if len(cells) > 2 else ""
                categoria = cells[3] if len(cells) > 3 else ""
                descripcion = cells[4] if len(cells) > 4 else ""
                fecha_raw = cells[5] if len(cells) > 5 else ""

                preview_m = RE_PREVIEW_LINK.search(row_html)
                url = preview_m.group(1) if preview_m else board_url
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                titulo = descripcion or documento
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
                        "blob": f"{documento} {expediente} {procedimiento} {categoria} {descripcion}",
                        "origen": "tablon_sede",
                    }
                )
        return rows

    def _collect_wp_pdfs(self, page_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except (urllib.error.URLError, OSError):
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_WP_PDF.finditer(html):
            raw = m.group(1)
            pdf = self._abs_wp(raw) if raw.startswith("/") else raw
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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "trámite licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites y gestiones de urbanismo (guías PDF)",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Página informativa; concesiones publicadas en tablón cuando proceda",
                "origen": "urbanismo_web",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/info.2"),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — catálogo trámites urbanísticos",
                "url": f"{self.sede_base}/info.2",
                "source": "ayuntamiento",
                "nota": "Presentación electrónica de solicitudes",
                "origen": "sede_tramites",
            },
        ]
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
            "expte": row.get("expediente"),
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
            tipo = "bando urbanístico"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|publicacion bocm", blob):
            tipo = "información pública"
        elif re.search(r"(?i)plan (?:parcial|especial)|planeam", blob):
            tipo = "planeamiento"
        return {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente"),
            "origen": row.get("origen"),
        }

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or "documento urbanismo",
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _doc_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row.get("titulo") or ""
        if not RE_LICENCIA.search(titulo):
            return None
        key = row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "guía tramitación",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": row.get("url") or key,
            "pdf_url": row.get("pdf_url"),
            "source": "ayuntamiento",
            "nota": "Modelo o guía de trámite; no concesión publicada",
            "origen": row.get("origen"),
        }

    def _all_docs(self) -> list[dict[str, Any]]:
        return (
            self._collect_dossier(self.normativa_dossier, "transparencia_normativa")
            + self._collect_dossier(self.ordenanzas_dossier, "transparencia_ordenanzas")
            + self._collect_wp_pdfs(self.tramites_url, "tramites_web")
            + self._collect_wp_pdfs(self.urbanismo_url, "urbanismo_web")
        )

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
        for doc in self._all_docs():
            rec = self._doc_to_licencia(doc)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "urbanismo_tablon_transparencia"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for doc in self._all_docs():
            rec = self._doc_to_licencia(doc)
            if rec:
                existing[rec["id"]] = rec
        for row in self._collect_board():
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

        for doc in self._all_docs():
            add(self._doc_to_proyecto(doc))
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "normativa": sum(1 for r in rows if r.get("origen") == "transparencia_normativa"),
            "ordenanzas": sum(1 for r in rows if r.get("origen") == "transparencia_ordenanzas"),
            "tramites": sum(1 for r in rows if r.get("origen") == "tramites_web"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
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
