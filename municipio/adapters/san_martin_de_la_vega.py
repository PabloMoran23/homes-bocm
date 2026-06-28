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
from urllib.parse import unquote
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WP_BASE = "https://ayto-smv.es"
SEDE_BASE = "https://sanmartindelavega.sedelectronica.es"
PGOU_BASE = "https://plangeneralsanmartindelavega.ayto-smv.es"
MUNICIPIO = "San Martín de la Vega"
ID_PREFIX = "smv"

URBANISMO_PAGE = f"{WP_BASE}/tramites/tablon-virtual/urbanismo-actividades-y-vivienda/"
WPFB_AJAX = f"{WP_BASE}/?wpfilebase_ajax=1"

PGOU_PAGES = [
    f"{PGOU_BASE}/",
    f"{PGOU_BASE}/avance-plan-general-ordenacion-urbana.html",
    f"{PGOU_BASE}/documentos.html",
    f"{PGOU_BASE}/consulta-previa.html",
]

RE_PREVIEW = re.compile(
    r'href="(https://sanmartindelavega\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="(https://sanmartindelavega\.sedelectronica\.es/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|"
    r"primera ocupaci[oó]n|segregaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|estudio de detalle|modificaci[oó]n|"
    r"aprobaci[oó]n (?:inicial|definitiva)|reparcel|expropiaci|documentaci[oó]n ambiental|"
    r"edicto|sau|sector|normas subsidiarias|nnss|callejero|denominaci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_FECHA_BOCM = re.compile(r"BOCM[- ](\d{4})-(\d{2})-(\d{2})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_WPFB_LINK = re.compile(r'href="([^"]+)"', re.I)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://[^"]+|/uploads/[^"]+)\.pdf[^"]*)"',
    re.I,
)
RE_DOWNLOAD_LIC = re.compile(
    r'href="(https://ayto-smv\.es/download/descarga_de_instanciassolicitudes/'
    r'obras_y_otras_autorizaciones/[^"]+\.pdf)"',
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
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            pass
    m = RE_FECHA_BOCM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            pass
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime(
                "%Y-%m-%d"
            )
        except ValueError:
            pass
    return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2030
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _wpfb_title(text: str) -> str:
    m = re.search(r">([^<]+)</a>", text or "")
    return unescape(m.group(1)).strip() if m else _strip_html(text)


class SanMartinDeLaVegaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress WP-Filebase + sede espublico tablón + portal PGOU Weebly."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.pgou_base = str(self.config.get("pgou_base") or PGOU_BASE).rstrip("/")
        self.wpfb_root = int(self.config.get("wpfb_root_cat", 128))
        self.wpfb_max_depth = int(self.config.get("wpfb_max_depth", 4))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, insecure: bool | None = None) -> str:
        time.sleep(self.delay_s)
        use_insecure = self.config.get("insecure_ssl", True) if insecure is None else insecure
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-san-martin-de-la-vega/1.0")}
        req = urllib.request.Request(url, headers=headers)
        if use_insecure:
            with self._opener.open(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> list[dict[str, Any]]:
        raw = self._fetch(url, insecure=False)
        return json.loads(raw)

    def _wpfb_tree(self, cat_id: int) -> list[dict[str, Any]]:
        url = f"{WPFB_AJAX}&wpfb_action=tree&base={cat_id}"
        try:
            return self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError, ValueError):
            return []

    def _crawl_wpfb(
        self,
        cat_id: int,
        depth: int = 0,
        parent_title: str = "",
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for node in self._wpfb_tree(cat_id):
            ntype = node.get("type")
            if ntype == "file":
                text = node.get("text") or ""
                title = _wpfb_title(text)
                link_m = RE_WPFB_LINK.search(text)
                file_url = link_m.group(1) if link_m else ""
                if not file_url.startswith("http"):
                    file_url = urllib.parse.urljoin(f"{WP_BASE}/", file_url)
                rows.append(
                    {
                        "titulo": title,
                        "url": file_url,
                        "carpeta": parent_title,
                        "origen": "wp_filebase",
                    }
                )
            elif ntype == "cat" and depth < self.wpfb_max_depth:
                child_id = int(node.get("cat_id") or 0)
                if child_id <= 0:
                    continue
                child_title = _wpfb_title(node.get("text") or "")
                rows.extend(self._crawl_wpfb(child_id, depth + 1, child_title))
        return rows

    def _collect_wpfb(self) -> list[dict[str, Any]]:
        return self._crawl_wpfb(self.wpfb_root)

    def _collect_pgou(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page in PGOU_PAGES:
            try:
                html = self._fetch(page, insecure=False)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                href = m.group(1)
                if not href.startswith("http"):
                    href = urllib.parse.urljoin(f"{self.pgou_base}/", href)
                if href in seen:
                    continue
                seen.add(href)
                name = unquote(href.rsplit("/", 1)[-1]).replace("_", " ").replace("-", " ")
                rows.append(
                    {
                        "titulo": f"PGOU Avance — {name[:200]}",
                        "url": href,
                        "page": page,
                        "origen": "pgou_weebly",
                    }
                )
        return rows

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r'<tbody[^>]*id="[^"]*">(.*?)</tbody>', html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 6:
                continue
            link_m = re.search(
                r'href="(https://sanmartindelavega\.sedelectronica\.es/preview-document/[^"]+)"',
                tr,
                re.I,
            )
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
                    "url": link_m.group(1) if link_m else f"{self.sede_base}/board",
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": origen,
                }
            )
        return rows

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 400) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            text_m = re.search(rf'href="{re.escape(url)}"[^>]*>([^<]+)<', local, re.I)
            titulo = ""
            if title_m:
                titulo = unescape(title_m.group(1).strip())
            elif text_m:
                titulo = unescape(text_m.group(1).strip())
            rows.append(
                {
                    "titulo": (titulo or url)[:500],
                    "doc_label": titulo[:500],
                    "expediente": "",
                    "procedimiento": "",
                    "categoria": "",
                    "descripcion": titulo,
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for path, origen in (("/board", "tablon"), ("/info.0", "info_tablon")):
            try:
                html = self._fetch(f"{self.sede_base}{path}")
            except urllib.error.URLError:
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(f"{self.sede_base}/dossier")
        except urllib.error.URLError:
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
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _collect_licencia_forms(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(URBANISMO_PAGE, insecure=False)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_DOWNLOAD_LIC.finditer(html):
            url = m.group(1)
            if url in seen:
                continue
            seen.add(url)
            name = unquote(url.rsplit("/", 1)[-1]).replace("-", " ").replace("_", " ")
            rows.append(
                {
                    "titulo": name[:500],
                    "url": url,
                    "origen": "impresos_urbanismo",
                }
            )
        return rows

    def _proyecto_tipo(self, blob: str, carpeta: str = "") -> str:
        text = f"{carpeta} {blob}".lower()
        if "informaci" in text and "pública" in text or "informacion publica" in text:
            return "información pública"
        if "estudio de detalle" in text:
            return "estudio de detalle"
        if "plan especial" in text or "plan parcial" in text:
            return "planeamiento de desarrollo"
        if "pgou" in text or "plan general" in text:
            return "PGOU"
        if "expropiaci" in text:
            return "expropiación"
        if "ambiental" in text:
            return "documentación ambiental"
        if "edicto" in text:
            return "edicto"
        if "convenio" in text:
            return "convenio"
        return "urbanismo"

    def _wpfb_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('carpeta', '')} {row['titulo']}"
        if not RE_PROYECTO.search(blob):
            return None
        key = row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": _fecha_from_blob(f"{row['titulo']} {row.get('carpeta', '')}"),
            "tipo": self._proyecto_tipo(blob, row.get("carpeta", "")),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "carpeta": row.get("carpeta"),
        }
        if row["url"].lower().endswith(".pdf"):
            rec["pdf_url"] = row["url"]
        return rec

    def _pgou_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": _fecha_from_blob(row["titulo"]),
            "tipo": "PGOU",
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "pdf_url": row["url"],
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            if row.get("categoria") != "Órganos de gobierno":
                return None
            if not re.search(r"(?i)pleno|convocatoria|acuerdo", blob):
                return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
            "tipo": self._proyecto_tipo(blob, row.get("procedimiento", "")),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        return rec

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

    def _form_to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        tipo = "trámite licencia"
        if re.search(r"(?i)declaraci[oó]n responsable", titulo):
            tipo = "declaración responsable"
        elif re.search(r"(?i)licencia", titulo):
            tipo = "licencia urbanística"
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Impreso/solicitud; no concesión publicada",
            "origen": row.get("origen"),
            "pdf_url": row["url"],
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
            "nota": "Página informativa de trámite",
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            add(self._board_to_licencia(item))
        for item in self._collect_tramites():
            add(self._tramite_to_licencia(item))
        for item in self._collect_licencia_forms():
            add(self._form_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "impresos": sum(1 for r in rows if r.get("origen") == "impresos_urbanismo"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
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

        for item in self._collect_wpfb():
            add(self._wpfb_to_proyecto(item))
        for item in self._collect_pgou():
            add(self._pgou_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_tramites():
            if RE_PROYECTO.search(item["titulo"]):
                add(
                    {
                        "id": _stable_id("proy", item["url"]),
                        "municipio": MUNICIPIO,
                        "titulo": item["titulo"],
                        "fecha": None,
                        "tipo": "trámite urbanismo",
                        "url": item["url"],
                        "source": "ayuntamiento",
                        "origen": item.get("origen"),
                    }
                )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_filebase": sum(1 for r in rows if r.get("origen") == "wp_filebase"),
            "pgou": sum(1 for r in rows if r.get("origen") == "pgou_weebly"),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
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
