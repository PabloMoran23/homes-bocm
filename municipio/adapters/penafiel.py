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

WEB_BASE = "https://www.penafiel.es"
SEDE_BASE = "https://penafiel.sedelectronica.es"
MUNICIPIO = "Peñafiel"
ID_PREFIX = "penafiel"

URBANISMO_PAGE = f"{WEB_BASE}/urbanismo.php"

DEFAULT_SEED_URLS: list[tuple[str, str]] = [
    (
        "https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=147",
        "Planeamiento en información pública (Junta CYL)",
    ),
    (
        "https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=147",
        "Archivo planeamiento urbanístico aprobado (Junta CYL)",
    ),
]

RE_PREVIEW = re.compile(
    r'href="(https://penafiel\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="(https://penafiel\.sedelectronica\.es/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_CARPETA = re.compile(
    r"<div class='carpeta'><p>([^<]+)</p><ul>(.*?)</ul></div>",
    re.S | re.I,
)
RE_PDF_LINK = re.compile(
    r"<a href='([^']+\.pdf)'[^>]*>([^<]*)</a>",
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|impuesto de construcciones)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pech|conjunto hist[oó]rico|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|"
    r"edicto|bando.*parcel|actuaci[oó]n urban|ruina|rehabilitaci[oó]n de edificios|"
    r"ordenaci[oó]n urbana|aru\b|errp)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(cuenta general|cr[eé]dito extraordinario|ordenanza fiscal|tasa escuela|"
    r"fiestas locales|subvenci[oó]n.*m[uú]sica|ayudas escuela)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
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
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "ruina" in n:
        return "declaración de ruina"
    if "pech" in n or "conjunto hist" in n:
        return "plan especial conjunto histórico"
    if "plan general" in n or "pgou" in n or "ordenaci" in n:
        return "planeamiento"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "aprobaci" in n:
        return "aprobación"
    if "rehabilit" in n:
        return "rehabilitación edificios"
    return "urbanismo"


class PenafielAyuntamientoAdapter(AyuntamientoAdapter):
    """Web PHP penafiel.es (PGOU/PECH PDFs) + sede espublico tablón/catálogo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.urbanismo_page = str(self.config.get("urbanismo_page") or URBANISMO_PAGE)
        raw_seeds = self.config.get("seed_urls") or DEFAULT_SEED_URLS
        self.seed_urls: list[tuple[str, str]] = []
        for item in raw_seeds:
            if isinstance(item, dict):
                self.seed_urls.append((str(item["url"]), str(item.get("titulo") or item["url"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                self.seed_urls.append((str(item[0]), str(item[1])))
            else:
                self.seed_urls.append((str(item), str(item)))
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-penafiel/1.0")},
        )
        opener = self._opener if sede else urllib.request.build_opener()
        with opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _warm_sede(self) -> None:
        try:
            self._fetch(self.info_url, sede=True)
        except (urllib.error.URLError, OSError, ConnectionError):
            pass

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 6:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": _strip_html(cells[1]),
                    "procedimiento": _strip_html(cells[2]),
                    "categoria": _strip_html(cells[3]),
                    "descripcion": _strip_html(cells[4]),
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])),
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": origen,
                }
            )
        return rows

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 500) : m.end() + 400]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            text_m = re.search(rf'href="{re.escape(url)}"[^>]*>([^<]+)<', local, re.I)
            titulo = ""
            if title_m:
                titulo = unescape(title_m.group(1).strip())
            elif text_m:
                titulo = unescape(text_m.group(1).strip())
            spans = [_strip_html(s) for s in re.findall(r"<span>([^<]+)</span>", local)]
            categoria = procedimiento = descripcion = ""
            fecha = None
            for s in spans:
                if RE_FECHA_DMY.search(s):
                    fecha = _parse_fecha_dmy(s)
            if len(spans) >= 3:
                useful = [s for s in spans if s not in ("Categoría", "Descripción", "Fecha de Publicación")]
                if useful:
                    categoria = useful[0] if len(useful) > 2 else ""
                    procedimiento = useful[1] if len(useful) > 2 else useful[0]
                    descripcion = useful[-2] if len(useful) > 2 else useful[-1]
                    if not fecha:
                        fecha = _parse_fecha_dmy(useful[-1])
            rows.append(
                {
                    "titulo": (titulo or descripcion or url)[:500],
                    "doc_label": titulo[:500],
                    "expediente": "",
                    "procedimiento": procedimiento,
                    "categoria": categoria,
                    "descripcion": descripcion or titulo,
                    "fecha": fecha or _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in ((self.board_url, "tablon"), (self.info_url, "info_tablon")):
            try:
                html = self._fetch(url, sede=True)
            except (urllib.error.URLError, OSError, ConnectionError):
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_tramites(self) -> list[dict[str, Any]]:
        self._warm_sede()
        try:
            html = self._fetch(self.dossier_url, sede=True)
        except (urllib.error.URLError, OSError, ConnectionError):
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _collect_urbanismo_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_page)
        except (urllib.error.URLError, OSError, ConnectionError):
            return []
        rows: list[dict[str, Any]] = []
        for carpeta_m in RE_CARPETA.finditer(html):
            section = unescape(carpeta_m.group(1).strip())
            body = carpeta_m.group(2)
            for pdf_m in RE_PDF_LINK.finditer(body):
                href = pdf_m.group(1)
                label = unescape(pdf_m.group(2).strip()) or Path(href).name
                pdf_url = urllib.parse.urljoin(f"{self.web_base}/", href)
                titulo = f"{section} — {label}" if label.lower() not in section.lower() else section
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(f"{label} {href}"),
                        "url": self.urbanismo_page,
                        "pdf_url": pdf_url,
                        "section": section,
                        "origen": "web_urbanismo_pdf",
                    }
                )
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, fallback_title in self.seed_urls:
            titulo = fallback_title
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "origen": "jcyl_planeamiento",
                }
            )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if not RE_LICENCIA.search(blob):
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
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() in ("urbanismo", "declaraciones de ruina"):
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('section', '')} {row['titulo']}"
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        if RE_LICENCIA.search(row["titulo"]) and not re.search(
            r"(?i)planeam|actuaci[oó]n urban|modificaci[oó]n del planeamiento|ruina",
            row["titulo"],
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
            "origen": row.get("origen"),
        }

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": "planeamiento",
            "url": row["url"],
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
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
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
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
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
        added = len(rows) - before
        state_path.parent.mkdir(parents=True, exist_ok=True)
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_urbanismo_pdfs():
            add(self._pdf_to_proyecto(item))
        for item in self._collect_tramites():
            add(self._tramite_to_proyecto(item))
        for item in self._collect_seed_pages():
            add(self._seed_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "web_pdfs": sum(1 for r in rows if r.get("origen") == "web_urbanismo_pdf"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "jcyl": sum(1 for r in rows if r.get("origen") == "jcyl_planeamiento"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
