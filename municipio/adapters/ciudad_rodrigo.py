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
MUNICIPIO = "Ciudad Rodrigo"
ID_PREFIX = "ciudad-rodrigo"

WP_API = f"{WP_BASE}/wp-json/wp/v2"
WP_CATEGORIES_PROYECTOS = (152, 154, 153, 155)
WP_CATEGORY_LICENCIAS = 151

PGOU_URL = f"{WP_BASE}/plan-general-de-ordenacion-urbana-municipal/"
INFORMES_URL = f"{WP_BASE}/informes-seguimiento-actividad-urbanistica/"
TRAMITES_URL = f"{WP_BASE}/tramites-y-gestiones-impresos/"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|de uso)|inicio de obra|"
    r"obra (?:mayor|menor)|uso excepcional|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocyl|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|sunp|supi|ordenanza|informe.*urban)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"subvenci[oó]n|licitaci[oó]n.*barra|carnaval|premio de investigaci[oó]n)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://ciudadrodrigo\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_WP_PDF = re.compile(
    r'href="(https?://www\.ciudadrodrigo\.es/ayuntamiento/wp-content/uploads/[^"]+\.pdf)"',
    re.I,
)


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


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(Path(url).name)
        if 1980 <= int(x.group(1)) <= 2030
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _wp_tipo_proyecto(title: str) -> str:
    t = title.lower()
    if "estudio de detalle" in t:
        return "estudio de detalle"
    if "modificaci" in t and "pgou" in t:
        return "modificación PGOU"
    if "plan especial" in t or "pech" in t:
        return "plan especial"
    if "proyecto de actuaci" in t or "urbanizaci" in t:
        return "proyecto de actuación"
    if "informe" in t and "urban" in t:
        return "informe actividad urbanística"
    if "pgou" in t or "planeam" in t:
        return "planeamiento"
    return "urbanismo"


class CiudadRodrigoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress REST (normativa urbanística) + PGOU/informes PDF + tablón espublico gestiona."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.wp_api = f"{self.wp_base}/wp-json/wp/v2"
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ciudad-rodrigo/1.0")},
        )
        if use_sede_ssl or "sedelectronica" in url:
            with self._opener.open(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        raw = self._fetch(url)
        data = json.loads(raw)
        return data

    def _collect_wp_posts(self, category_ids: tuple[int, ...]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for cat_id in category_ids:
            try:
                posts = self._fetch_json(
                    f"{self.wp_api}/posts?categories={cat_id}&per_page=100&_fields=id,title,date,link"
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(posts, list):
                continue
            for post in posts:
                pid = int(post.get("id") or 0)
                if pid in seen:
                    continue
                seen.add(pid)
                title_obj = post.get("title") or {}
                title = _strip_html(str(title_obj.get("rendered") or ""))
                if not title:
                    continue
                fecha = str(post.get("date") or "")[:10] or None
                link = str(post.get("link") or "")
                rows.append(
                    {
                        "id": pid,
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": link,
                        "categoria_id": cat_id,
                    }
                )
        return rows

    def _collect_pgou_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(PGOU_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_WP_PDF.finditer(html):
            pdf = m.group(1)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            rows.append(
                {
                    "titulo": f"PGOU Ciudad Rodrigo: {name}"[:500],
                    "fecha": _fecha_from_pdf_url(pdf),
                    "url": PGOU_URL,
                    "pdf_url": pdf,
                    "key": pdf,
                }
            )
        return rows

    def _collect_informes(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(INFORMES_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(
            r'href="([^"]+\.pdf)"[^>]*>([^<]*Informe[^<]*)',
            html,
            re.I,
        ):
            pdf = m.group(1)
            if pdf.startswith("/"):
                pdf = f"{self.wp_base}{pdf}"
            if pdf in seen:
                continue
            seen.add(pdf)
            label = _strip_html(m.group(2))
            rows.append(
                {
                    "titulo": label[:500] or "Informe actividad urbanística",
                    "fecha": _fecha_from_pdf_url(pdf),
                    "url": INFORMES_URL,
                    "pdf_url": pdf,
                    "key": pdf,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_sede_ssl=True)
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
                "tipo": "tablón licencias y urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios de licencias y planeamiento publicados en sede",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", TRAMITES_URL),
                "fecha_concesion": None,
                "tipo": "trámites licencias de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites y gestiones — licencias urbanísticas",
                "url": TRAMITES_URL,
                "source": "ayuntamiento",
                "nota": "Formularios: licencia obra, declaración responsable, 1ª ocupación",
                "origen": "web_tramites",
            },
            {
                "id": _stable_id("lic", INFORMES_URL),
                "fecha_concesion": None,
                "tipo": "informes anuales licencias",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Informes seguimiento actividad urbanística",
                "url": INFORMES_URL,
                "source": "ayuntamiento",
                "nota": "Estadísticas anuales de licencias concedidas (PDF)",
                "origen": "informes",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _wp_post_to_licencia(self, post: dict[str, Any]) -> dict[str, Any]:
        key = str(post.get("id") or post.get("url"))
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": post.get("fecha"),
            "tipo": "autorización uso excepcional",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": post["titulo"],
            "url": post["url"],
            "source": "ayuntamiento",
            "origen": "wp_uso_excepcional",
        }

    def _wp_post_to_proyecto(self, post: dict[str, Any]) -> dict[str, Any]:
        key = str(post.get("id") or post.get("url"))
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": post["titulo"],
            "fecha": post.get("fecha"),
            "tipo": _wp_tipo_proyecto(post["titulo"]),
            "url": post["url"],
            "source": "ayuntamiento",
            "origen": "wp_normativa",
        }

    def _pdf_to_proyecto(self, item: dict[str, Any], origen: str) -> dict[str, Any]:
        key = item.get("key") or item.get("pdf_url") or item["titulo"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _wp_tipo_proyecto(item["titulo"]),
            "url": item.get("url") or item.get("pdf_url"),
            "pdf_url": item.get("pdf_url"),
            "source": "ayuntamiento",
            "origen": origen,
        }

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _wp_tipo_proyecto(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
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

        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for post in self._collect_wp_posts((WP_CATEGORY_LICENCIAS,)):
            rec = self._wp_post_to_licencia(post)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_uso_excepcional": sum(1 for r in rows if r.get("origen") == "wp_uso_excepcional"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "web_tramites", "informes")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for post in self._collect_wp_posts((WP_CATEGORY_LICENCIAS,)):
            rec = self._wp_post_to_licencia(post)
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
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

        for post in self._collect_wp_posts(WP_CATEGORIES_PROYECTOS):
            add(self._wp_post_to_proyecto(post))

        for item in self._collect_pgou_pdfs():
            add(self._pdf_to_proyecto(item, "pgou"))

        for item in self._collect_informes():
            rec = self._pdf_to_proyecto(item, "informes")
            rec["tipo"] = "informe actividad urbanística"
            add(rec)

        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_normativa": sum(1 for r in rows if r.get("origen") == "wp_normativa"),
            "pgou": sum(1 for r in rows if r.get("origen") == "pgou"),
            "informes": sum(1 for r in rows if r.get("origen") == "informes"),
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
