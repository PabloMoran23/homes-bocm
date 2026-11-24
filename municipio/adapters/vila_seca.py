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

WEB_BASE = "https://vila-seca.cat"
SEDE_BASE = "https://vila-seca.eadministracio.cat"
BOARD_URL = f"{SEDE_BASE}/board"
URBANISMO_URL = f"{WEB_BASE}/es/urbanismo"
URBANISME_URL = f"{WEB_BASE}/ca/urbanisme"
GEOPORTAL_URL = "https://geoportal.vila-seca.cat/urbanisme/"
GEOPORTAL_INFO = f"{WEB_BASE}/es/geoportal-urbanistico"
RPUC_MUNICI = (
    "https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=43177"
)
MUNICIPIO = "Vila-seca"
ID_PREFIX = "vila-seca"

DEFAULT_LICENCIA_PAGES: list[dict[str, str]] = [
    {
        "url": f"{WEB_BASE}/es/tramits-urbanisme/comunicacion-de-obras",
        "tipo": "comunicación previa",
        "titulo": "Comunicación de obras (pequeñas obras, grandes reformas, fachadas, etc.)",
    },
    {
        "url": f"{WEB_BASE}/es/tramits-urbanisme/licencia-plan-de-actuacion-especifica-pae",
        "tipo": "PAE",
        "titulo": "Licencia Plan de Actuación Específica (PAE)",
    },
    {
        "url": f"{WEB_BASE}/es/tramits-urbanisme/llicencia-urbanistica-obra-nova-reformes-rehabilitacio-i-ampliacio-enderrocs-grua-torre-bastides-2m-obres-sol-rustic",
        "tipo": "licencia urbanística",
        "titulo": "Llicència urbanística (obra nova, reformes, enderrocs, grua torre, etc.)",
    },
    {
        "url": f"{WEB_BASE}/es/tramits-urbanisme/solicitud-de-documentacion-urbanistica",
        "tipo": "documentación urbanística",
        "titulo": "Solicitud de documentación urbanística",
    },
    {
        "url": f"{WEB_BASE}/es/tramits-urbanisme/solicitud-de-informes-y-certificados-urbanisticos",
        "tipo": "certificado urbanístico",
        "titulo": "Solicitud de certificados urbanísticos",
    },
    {
        "url": f"{WEB_BASE}/es/urbanismo",
        "tipo": "trámites urbanismo",
        "titulo": "Urbanismo — sede electrónica Vila-seca (trámites telemáticos)",
    },
]

DEFAULT_PROYECTO_SEEDS: list[dict[str, str]] = [
    {
        "url": GEOPORTAL_URL,
        "titulo": "Geoportal Urbanístic de Vila-seca (PGOU, sectores, parcelas)",
        "tipo": "visor GIS",
    },
    {
        "url": GEOPORTAL_INFO,
        "titulo": "Geoportal urbanístico — información municipal",
        "tipo": "visor GIS",
    },
    {
        "url": RPUC_MUNICI,
        "titulo": "RPUC Generalitat — cerca d'expedients urbanístics (INE 43177)",
        "tipo": "planeamiento",
    },
    {
        "url": "https://geoportal.vila-seca.cat/urbanisme/assets/doc/PGOU_ANNEXOS_2023.pdf",
        "titulo": "PGOU Vila-seca — normes urbanístiques (refós 2023)",
        "tipo": "PGOU",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licen|licèn|llic[eè]ncia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autoritz|autoriz|obra[s]? (?:major|menor)|certificat|planol)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|planej|plan (?:parcial|especial|general)|pgou|pla general|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|projecte|modificaci[oó]n|reparcel|"
    r"sector|pol[ií]gon|unitat d.actuaci|obres?|ampliaci[oó]|urbanitz|visor|geoportal|"
    r"ordenan|normes urban|pae\b|actuaci[oó] espec|suspensi[oó].*llic|planejament general)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]ns? de personal|nombramiento|convocat[oò]ria de personal|"
    r"subvencion|subvenci[oó]|prestaci[oó]n econ[oò]mica|serveis socials|eleccions|"
    r"padr[oó] fiscal|ocupaci[oó] p[uú]blica|policia|jurado|mercadet|concessi[oó] de subvencions)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://vila-seca\.eadministracio\.cat)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_TRAMIT_LINK = re.compile(
    r'href="(/es/tramits-urbanisme/[^"]+)"[^>]*>([^<]{8,})',
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
        return f"{max(years)}"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "pgou" in n or "pla general" in n or "planejament general" in n:
        return "PGOU"
    if "plan parcial" in n or "pla parcial" in n:
        return "plan parcial"
    if "pae" in n or "actuació específica" in n or "actuacion especifica" in n:
        return "PAE"
    if "polígon" in n or "poligon" in n or "sector" in n:
        return "desarrollo urbanístico"
    if "visor" in n or "geoportal" in n:
        return "visor GIS"
    if "rpuc" in n:
        return "planeamiento"
    if "suspensi" in n and "llic" in n:
        return "suspensión licencias / planeamiento"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    return "urbanismo"


def _licencia_tipo(text: str) -> str:
    n = (text or "").lower()
    if "comunicaci" in n:
        return "comunicación previa"
    if "pae" in n:
        return "PAE"
    if "llic" in n or "licen" in n:
        return "licencia urbanística"
    if "certificat" in n:
        return "certificado urbanístico"
    return "trámite urbanismo"


class VilaSecaAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla vila-seca.cat + sede espublico (eadministracio.cat) + geoportal EnMapa/Nexus."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-vila-seca/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

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
            url = self._abs_sede(url)

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
        if "urban" in proc or "planejament" in proc or "obra" in proc:
            return True
        return bool(RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob))

    def _collect_urbanismo_page(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in (URBANISMO_URL, URBANISME_URL):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_TRAMIT_LINK.finditer(html):
                url = self._abs_web(m.group(1))
                titulo = _strip_html(m.group(2))
                if len(titulo) < 8:
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _parse_fecha_dmy(titulo),
                        "url": url,
                        "origen": "web_tramite",
                        "blob": titulo,
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in DEFAULT_LICENCIA_PAGES:
            rows.append(
                {
                    "id": _stable_id("lic", seed["url"]),
                    "fecha_concesion": None,
                    "tipo": seed.get("tipo") or _licencia_tipo(seed["titulo"]),
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "source": "ayuntamiento",
                    "titulo": seed["titulo"],
                    "url": seed["url"],
                    "origen": "portal_urbanismo",
                }
            )
        return rows

    def _collect_proyecto_seeds(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in DEFAULT_PROYECTO_SEEDS:
            rows.append(
                {
                    "id": _stable_id("proy", seed["url"]),
                    "municipio": MUNICIPIO,
                    "titulo": seed["titulo"],
                    "fecha": None,
                    "tipo": seed.get("tipo") or _proyecto_tipo(seed["titulo"]),
                    "url": seed["url"],
                    "source": "ayuntamiento",
                    "origen": "semilla",
                }
            )
        return rows

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = item.get("blob") or item.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        url = item.get("url") or URBANISMO_URL
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": item.get("titulo") or blob[:200],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": item.get("origen"),
            "expte": item.get("expediente"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        proc = (row.get("procedimiento") or "").lower()
        if (
            RE_LICENCIA.search(blob)
            and "llicències urbanístiques" in proc
            and not RE_PROYECTO.search(blob)
        ):
            return None
        return self._item_to_proyecto(
            {
                "titulo": row.get("documento") or blob[:200],
                "fecha": row.get("fecha"),
                "url": row.get("url"),
                "blob": blob,
                "origen": "tablon",
                "expediente": row.get("expediente"),
            }
        )

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        proc = (row.get("procedimiento") or "").lower()
        blob = row.get("blob") or ""
        if "llicències urbanístiques" not in proc and not (
            RE_LICENCIA.search(blob) and "urban" in proc
        ):
            return None
        url = row.get("url") or self.board_url
        titulo = row.get("documento") or blob[:200]
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": row.get("fecha"),
            "tipo": _licencia_tipo(blob),
            "distrito": MUNICIPIO,
            "lat": None,
            "lon": None,
            "source": "ayuntamiento",
            "titulo": titulo,
            "url": url,
            "origen": "tablon",
            "expte": row.get("expediente"),
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
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        tablon = sum(1 for r in rows if r.get("origen") == "tablon")
        return {"rows": len(rows), "status": "ok", "info": len(rows) - tablon, "tablon": tablon}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats["rows"]
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
        for item in self._collect_urbanismo_page():
            add(self._item_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "with_geometry": 0,
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
