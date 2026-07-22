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

WP_BASE = "https://www.ciudadrodrigo.es/ayuntamiento"
SEDE_BASE = "https://ciudadrodrigo.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
PGOU_URL = f"{WP_BASE}/plan-general-de-ordenacion-urbana-municipal/"
TRAMITES_URL = f"{WP_BASE}/tramites-y-gestiones-impresos/"
MUNICIPIO = "Ciudad Rodrigo"
ID_PREFIX = "ciudad-rodrigo"

DEFAULT_WP_CATEGORIES = (152, 154, 151, 153)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|de uso)|"
    r"autorizaci[oó]n de uso excepcional|uso excepcional|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n|segregaci[oó]n|parcelaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|memoria|planos|edicto|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"parcela|suelo|sector|unidad(?:es)? de ejecuci[oó]n|\b(?:UE|AD|AN|AI|PAU|S|PAS)-[\d.]+\b|"
    r"cambio de ordenaci[oó]n|actuaci[oó]n|autorizaci[oó]n de uso)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvenci[oó]n|premio|certamen|licitaci[oó]n.*bar|feria del caballo|"
    r"auto taxi|bolsa de empleo|recurso de alzada.*ejercicio)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://ciudadrodrigo\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_PDF_HREF = re.compile(r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"', re.I)


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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _proyecto_tipo(title: str) -> str:
    t = title.lower()
    if "estudio de detalle" in t or "estudio detalle" in t:
        return "estudio de detalle"
    if re.search(r"\bue[\s.-]?\d", t) or "unidad de ejecuci" in t:
        return "unidad de ejecución"
    if "modificaci" in t and "pgou" in t:
        return "modificación PGOU"
    if "pgou" in t or "plan general" in t:
        return "PGOU"
    if "autorizaci" in t and "uso excepcional" in t:
        return "autorización uso excepcional"
    if "informaci" in t and "p" in t and "blica" in t:
        return "información pública"
    if "proyecto de actuaci" in t or "actuaci" in t:
        return "proyecto de actuación"
    if "planeamiento" in t:
        return "planeamiento"
    return "urbanismo"


class CiudadRodrigoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress REST (urbanismo) + sede espublico tablón + PDFs PGOU/trámites."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        raw_cats = self.config.get("wp_category_ids") or list(DEFAULT_WP_CATEGORIES)
        self.wp_category_ids = [int(c) for c in raw_cats]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ciudad-rodrigo/1.0")},
        )
        opener = self._opener if sede else urllib.request.build_opener()
        with opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or self.wp_base, href)

    def _extract_pdfs(self, html: str, base: str | None = None) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_url(m.group(1), base or self.wp_base)
            if "favicon" in u.lower():
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        for cat_id in self.wp_category_ids:
            page = 1
            while page <= 10:
                url = (
                    f"{self.wp_base}/wp-json/wp/v2/posts"
                    f"?categories={cat_id}&per_page=100&page={page}"
                )
                try:
                    posts = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(posts, list) or not posts:
                    break
                for post in posts:
                    link = str(post.get("link") or "").strip()
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)
                    title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                    content = str((post.get("content") or {}).get("rendered") or "")
                    fecha = _iso_date_wp(str(post.get("date") or ""))
                    pdfs = self._extract_pdfs(content, link)
                    rows.append(
                        {
                            "titulo": title[:500],
                            "fecha": fecha,
                            "url": link,
                            "pdfs": pdfs,
                            "origen": f"wp_cat_{cat_id}",
                        }
                    )
                if len(posts) < 100:
                    break
                page += 1
        return rows

    def _collect_pgou_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.pgou_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for pdf in self._extract_pdfs(html):
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            rows.append(
                {
                    "titulo": f"PGOU — {name}"[:500],
                    "fecha": None,
                    "url": self.pgou_url,
                    "pdf_url": pdf,
                    "origen": "pgou",
                }
            )
        return rows

    def _collect_tramite_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tramites_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for pdf in self._extract_pdfs(html):
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            blob = name.lower()
            if not RE_LICENCIA.search(blob) and "urban" not in blob:
                continue
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": None,
                    "url": self.tramites_url,
                    "pdf_url": pdf,
                    "origen": "tramites_impresos",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, sede=True)
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
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios de urbanismo y licencias en sede espublico",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "formularios licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites e impresos — licencias urbanísticas",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Solicitudes informativas; sin listado histórico de concesiones",
                "origen": "tramites_impresos",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "obra")):
            return True
        if "urbanismo" in cat:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _wp_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "autorización uso excepcional" if "uso excepcional" in row["titulo"].lower() else "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdfs"):
            rec["pdf_url"] = row["pdfs"][0]
        return rec

    def _pdf_row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["pdf_url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "pdf_url": row["pdf_url"],
            "source": "ayuntamiento",
            "nota": "Formulario informativo; no concesión publicada",
            "origen": row.get("origen"),
        }

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        if not RE_LICENCIA.search(row.get("blob") or ""):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdfs"):
            rec["pdf_url"] = row["pdfs"][0]
            if len(row["pdfs"]) > 1:
                rec["pdf_urls"] = row["pdfs"][:20]
        return rec

    def _pdf_row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('pdf_url', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", row["pdf_url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": "documento PGOU" if row.get("origen") == "pgou" else "documento urbanismo",
            "url": row["url"],
            "pdf_url": row["pdf_url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and "planeamiento" not in (row.get("procedimiento") or "").lower():
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "expte": row.get("expediente") or None,
            "source": "ayuntamiento",
            "origen": "tablon",
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_licencia_info_pages():
            add(rec)
        for wp in self._collect_wp_posts():
            add(self._wp_to_licencia(wp))
        for pdf_row in self._collect_tramite_pdfs():
            add(self._pdf_row_to_licencia(pdf_row))
        for board in self._collect_board():
            add(self._board_to_licencia(board))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_licencias": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "tramites_impresos")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for wp in self._collect_wp_posts():
            rec = self._wp_to_licencia(wp)
            if rec:
                existing[rec["id"]] = rec
        for pdf_row in self._collect_tramite_pdfs():
            rec = self._pdf_row_to_licencia(pdf_row)
            if rec:
                existing[rec["id"]] = rec
        for board in self._collect_board():
            rec = self._board_to_licencia(board)
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

        for wp in self._collect_wp_posts():
            add(self._wp_to_proyecto(wp))
        for pdf_row in self._collect_pgou_pdfs():
            add(self._pdf_row_to_proyecto(pdf_row))
        for board in self._collect_board():
            add(self._board_to_proyecto(board))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_posts": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
            "pgou_pdfs": sum(1 for r in rows if r.get("origen") == "pgou"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
