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

WEB_BASE = "https://incaciutat.com"
SEDE_BASE = "https://incaciutat.sedelectronica.es"
MUNICIPIO = "Inca"
ID_PREFIX = "inca"
WP_URBANISMO_CAT = 62

DEFAULT_SEED_PAGES = [
    f"{WEB_BASE}/pgou",
    f"{WEB_BASE}/es/ayuntamiento/arees/urbanismo",
]

DEFAULT_LICENCIA_FORMS: list[dict[str, str]] = [
    {
        "titulo": "Comunicación previa obras LUIB",
        "url": f"{WEB_BASE}/wp-content/uploads/2021/06/urbanisme-instancies-comunicacio-previa-obres-LUIB.pdf",
        "tipo": "comunicación previa obras",
    },
    {
        "titulo": "Declaración responsable obras suelo urbano",
        "url": f"{WEB_BASE}/wp-content/uploads/2020/06/urbanisme-instancies-obres-declaracio-responsable-obres-sol-urba.pdf",
        "tipo": "declaración responsable obras",
    },
    {
        "titulo": "Solicitud licencia urbanística con proyecto",
        "url": f"{WEB_BASE}/wp-content/uploads/urbanisme-instancia-solicitud-llicencia-obra-amb-projecte.pdf",
        "tipo": "licencia urbanística con proyecto",
    },
    {
        "titulo": "Solicitud licencia urbanística sin proyecto",
        "url": f"{WEB_BASE}/wp-content/uploads/urbanisme-instancia-solicitud-llicencia-obra-sense-projecte.pdf",
        "tipo": "licencia urbanística sin proyecto",
    },
    {
        "titulo": "Solicitud licencia de parcelación",
        "url": f"{WEB_BASE}/wp-content/uploads/Sol%C2%B7licitud-de-llic%C3%A8ncia-de-parcel%C2%B7laci%C3%B3.pdf",
        "tipo": "licencia de parcelación",
    },
    {
        "titulo": "Solicitud licencia ocupación o primera utilización",
        "url": f"{WEB_BASE}/wp-content/uploads/Sol%C2%B7licitud-de-llic%C3%A8ncia-docupaci%C3%B3-o-de-primera-utilitzaci%C3%B3.pdf",
        "tipo": "licencia de ocupación",
    },
    {
        "titulo": "Solicitud licencia instalación rótulos",
        "url": f"{WEB_BASE}/wp-content/uploads/2024/10/Solicitud-llicencia-instalacio-retols.pdf",
        "tipo": "licencia instalación rótulos",
    },
    {
        "titulo": "Comunicación previa placas solares",
        "url": f"{WEB_BASE}/wp-content/uploads/2023/03/urbanisme-instancies-obres-comunicacio-previa-plaques-solars.pdf",
        "tipo": "comunicación previa instalación solar",
    },
]

RE_PREVIEW = re.compile(
    r'href="((?:https://incaciutat\.sedelectronica\.es)?/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://incaciutat\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="(https://incaciutat\.com/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licen|llic[eè]ncia|obra[s]?|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"ocupaci[oó]n|parcel|rotul|instal|activitat|connexi[oó]|certificat.*urban|"
    r"primera utilizaci|primera ocupaci)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pla general|"
    r"modificaci[oó]n|unitat d.actuaci|ua-\d|mp-\d|mp\d|cataleg|cat[aà]leg|"
    r"informaci[oó]n p[uú]blica|expedient|boib|avaluaci[oó] ambient|sector|"
    r"reparcel|supressi[oó]|pmus|parc log[ií]stic|normativa urban|visor|geoportal|"
    r"obres p[uú]bliques|urbanitz)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|eleccions|elecci[oó]n|subvenc|ajudes|personal|ple de|convocat[oò]ria de ple|"
    r"soib|ocupaci[oó] per a persones|recollida.*residus|fiestes|turismo|horts urbans|"
    r"carpeta ciutadana|reclamaciones.*electores|jurats? per al bienni|edicte de reanudaci)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://incaciutat\.sedelectronica\.es)?/preview-document/[^"]+)"',
    re.I,
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
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "catàleg" in n or "catalog" in n or "cataleg" in n:
        return "modificación catálogo"
    if "unitat d.actuaci" in n or re.search(r"\bua-\d", n):
        return "unidad de actuación"
    if "supressi" in n and "ua" in n:
        return "supresión unidad de actuación"
    if "parc log" in n:
        return "proyecto urbanización / parc logístic"
    if "avaluaci" in n and "ambient" in n:
        return "evaluación ambiental"
    if "pmus" in n or "mobilitat urbana" in n:
        return "plan movilidad urbana"
    if "pgou" in n or "pla general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "obres p" in n and "blic" in n:
        return "obra pública"
    return "urbanismo"


def _licencia_tipo(title: str) -> str:
    n = title.lower()
    if "comunicaci" in n:
        return "comunicación previa"
    if "declaraci" in n:
        return "declaración responsable"
    if "parcel" in n:
        return "licencia de parcelación"
    if "ocupaci" in n or "primera" in n:
        return "licencia de ocupación"
    if "rotul" in n:
        return "licencia de rótulos"
    if "activitat" in n or "actividad" in n:
        return "licencia de actividad"
    if "solar" in n or "placa" in n:
        return "comunicación previa instalación"
    if "projecte" in n or "proyecto" in n:
        return "licencia urbanística con proyecto"
    return "trámite licencia urbanística"


class IncaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress incaciutat.com + sede espublico gestiona + geoportal urbanístic (sin WFS expedientes)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_forms = list(self.config.get("licencia_forms") or DEFAULT_LICENCIA_FORMS)
        self.wp_categories = [int(x) for x in (self.config.get("wp_categories") or [WP_URBANISMO_CAT])]
        self.wp_max_pages = int(self.config.get("wp_max_pages", 3))
        self._ssl_ctx = ssl.create_default_context()
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-inca/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]] | dict[str, Any]:
        return json.loads(self._fetch(url))

    def _should_exclude(self, blob: str) -> bool:
        if not RE_EXCLUDE.search(blob):
            return False
        if RE_PROYECTO.search(blob) and re.search(r"(?i)pgou|modificaci|unitat|planeam|cataleg", blob):
            return False
        return True

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
            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"
            titulo = cells.get("class_description") or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            expediente = cells.get("class_folderCode", "")
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente[:120],
                    "procedimiento": cells.get("class_folderName", "")[:200],
                    "categoria": cells.get("class_boardCategory", "")[:120],
                    "descripcion": cells.get("class_description", "")[:500],
                    "fecha": _parse_fecha_dmy(cells.get("class_dateFrom", "")),
                    "url": url,
                    "pdf_url": url if "preview-document" in url else None,
                    "origen": "tablon",
                    "blob": f"{documento} {expediente} {cells.get('class_folderName', '')} "
                    f"{cells.get('class_boardCategory', '')} {titulo}",
                }
            )
        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            href, titulo = m.group(1), unescape(m.group(2).strip())
            url = href if href.startswith("http") else f"{self.sede_base}{href}"
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()

        def add_post(post: dict[str, Any], origen: str) -> None:
            pid = int(post.get("id") or 0)
            if not pid or pid in seen:
                return
            title = _strip_html(post.get("title", {}).get("rendered", ""))
            content = post.get("content", {}).get("rendered", "") or ""
            blob = f"{title} {content}"
            if self._should_exclude(blob):
                return
            if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(title):
                return
            seen.add(pid)
            pdf_m = RE_WP_PDF.search(content)
            rows.append(
                {
                    "pid": pid,
                    "titulo": title[:500],
                    "fecha": (post.get("date") or "")[:10] or None,
                    "url": post.get("link") or "",
                    "pdf_url": pdf_m.group(1) if pdf_m else None,
                    "origen": origen,
                    "blob": blob[:2000],
                }
            )

        for cat in self.wp_categories:
            for page in range(1, self.wp_max_pages + 1):
                url = (
                    f"{self.web_base}/wp-json/wp/v2/posts"
                    f"?categories={cat}&per_page=100&page={page}"
                    f"&_fields=id,date,link,title,content,slug"
                )
                try:
                    data = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(data, list) or not data:
                    break
                for post in data:
                    add_post(post, f"wp_category_{cat}")
                if len(data) < 100:
                    break

        for term in ("pgou", "modificació pgou", "unitat actuació", "planejament"):
            url = (
                f"{self.web_base}/wp-json/wp/v2/posts"
                f"?search={urllib.parse.quote(term)}&per_page=50"
                f"&_fields=id,date,link,title,content,slug"
            )
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if isinstance(data, list):
                for post in data:
                    add_post(post, f"wp_search_{term.replace(' ', '_')}")
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_WP_PDF.finditer(html):
                pdf_url = m.group(1)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = urllib.parse.unquote(pdf_url.split("/")[-1].replace(".pdf", ""))
                rows.append(
                    {
                        "titulo": name[:500],
                        "fecha": _parse_fecha_dmy(name) or _parse_fecha_dmy(pdf_url),
                        "url": pdf_url,
                        "pdf_url": pdf_url,
                        "origen": "wp_seed_pdf",
                        "blob": f"{name} {pdf_url}",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Inca",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Tablón espublico gestiona (/board)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.dossier_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites urbanismo y obras — sede electrónica",
                "url": self.dossier_url,
                "source": "ayuntamiento",
                "nota": "Catálogo /dossier espublico",
                "origen": "dossier",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/es/ayuntamiento/arees/urbanismo"),
                "fecha_concesion": None,
                "tipo": "formularios licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — formularios obras y actividades (web municipal)",
                "url": f"{self.web_base}/es/ayuntamiento/arees/urbanismo",
                "source": "ayuntamiento",
                "origen": "web_urbanismo",
            },
        ]
        for form in self.licencia_forms:
            titulo = str(form.get("titulo") or "")
            url = str(form.get("url") or "")
            if not titulo or not url:
                continue
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": _parse_fecha_dmy(url),
                    "tipo": str(form.get("tipo") or _licencia_tipo(titulo)),
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Formulario PDF área urbanismo",
                    "origen": "wp_form_pdf",
                }
            )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if self._should_exclude(row.get("blob", "")):
            return None
        if not RE_LICENCIA.search(row.get("blob", "")):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or _licencia_tipo(row["titulo"]),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expediente"):
            rec["expte"] = row["expediente"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob", "")
        if self._should_exclude(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expediente"):
            rec["expte"] = row["expediente"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo", "")
        if self._should_exclude(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = str(row.get("pid") or row["url"])
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"wp:{key}"),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo", "")
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "pdf_url": row.get("pdf_url"),
            "origen": row.get("origen"),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": _licencia_tipo(row["titulo"]),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Trámite informativo sede",
            "origen": row.get("origen"),
        }

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        if RE_LICENCIA.search(row["titulo"]) and not re.search(
            r"(?i)planeam|urban|certificat|informe|actuaci", row["titulo"]
        ):
            return None
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Trámite informativo sede",
            "origen": row.get("origen"),
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "forms": sum(1 for r in rows if r.get("origen") == "wp_form_pdf"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "rows": len(rows),
                    "added": len(rows) - before,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": len(rows) - before, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_wp_posts():
            rec = self._wp_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_seed_pdfs():
            rec = self._seed_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        geoportal = {
            "id": _stable_id("proy", "geoportal-urbanistic"),
            "municipio": MUNICIPIO,
            "titulo": "Geoportal urbanístic — mapes.incaciutat.com",
            "fecha": "2025-05-05",
            "tipo": "visor / cartografía urbanística",
            "url": "https://mapes.incaciutat.com/geoportal/",
            "source": "ayuntamiento",
            "nota": "Visor PGOU municipal (Cesium); sin API pública de expedientes",
            "origen": "geoportal",
        }
        if geoportal["id"] not in seen:
            rows.append(geoportal)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
            "seed_pdf": sum(1 for r in rows if r.get("origen") == "wp_seed_pdf"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_proyectos(out_jsonl)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), **result},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return result
