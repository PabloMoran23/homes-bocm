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

WEB_BASE = "https://www.eivissa.es"
SEDE_BASE = "https://eivissa.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
TRANSPARENCY_URBANISMO = (
    f"{SEDE_BASE}/transparency/c43909b2-2063-4114-bcec-56c8a94fd737/"
)
PGOU_URL = f"{WEB_BASE}/pla-general-de-ordenacio-urbana-2023"
MUNICIPIO = "Eivissa"
ID_PREFIX = "eivissa"

BANS_ASSET_PUBLISHER = (
    f"{WEB_BASE}/bans?p_p_id=com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet"
    "_INSTANCE_pjGXd4w7WchG&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view"
    "&_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_pjGXd4w7WchG_delta=50"
    "&p_r_p_resetCur=false"
    "&_com_liferay_asset_publisher_web_portlet_AssetPublisherPortlet_INSTANCE_pjGXd4w7WchG_cur="
)

RE_PREVIEW = re.compile(
    r'href="((?:https://eivissa\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_EXT_URL = re.compile(
    r'<a href="(https://www\.caib\.es/eboibfront[^"]+)"[^>]*class="extUrl"[^>]*>([^<]+)</a>',
    re.I | re.S,
)
RE_EXT_URL_ALT = re.compile(
    r'<a href="(https://www\.caib\.es/eboibfront[^"]+)"[^>]*target="_blank"[^>]*>([^<]+)</a>',
    re.I | re.S,
)
RE_PDF_HREF = re.compile(r'href="(/documents/[^"]+\.pdf[^"]*)"', re.I)
RE_BAN_BLOCK = re.compile(
    r'<a href="(https://www\.eivissa\.es/w/[^"]+)" class="card-title[^"]*" title="([^"]*)"[^>]*>'
    r"([^<]+)</a>.*?<span class=\"date pubish-date[^\"]*>([^<]+)</span>"
    r".*?<span class=\"category[^\"]*>([^<]+)</span>",
    re.I | re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|licència|comunicaci[oó]n previa|comunicaci[oó] "
    r"pr[eè]via|declaraci[oó] responsable|obra[s]?|autoritzaci[oó]|autorizaci[oó]|"
    r"ocupaci[oó]|primera ocupaci[oó])",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|planej|plan (?:parcial|especial|general)|pgou|pla general|"
    r"informaci[oó] p[uú]blica|expedient|projecte|proyecto|modificaci[oó]n|reparcel|"
    r"estudi de detall|estudio de detalle|sector|boib|ban[s]? d.urban|exposici[oó]|"
    r"aprovaci[oó]|ordenaci[oó] urbana|normes urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(selecci[oó]n de personal|ocupaci[oó] p[uú]blica|convocat[oò]ria.*ple|"
    r"subvenci[oó]n|personal funcionari|monitor/a escola|treballador/a social|"
    r"mercat de nadal|parades al mercat|eleccions)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

_CAT_MONTHS = {
    "gen": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "maig": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "oct": 10,
    "nov": 11,
    "des": 12,
}


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
    m = re.search(
        r"(\d{1,2})\s+d[''']?\s*(\w+)\.?\s+(\d{4})|(\d{1,2})\s+de\s+(\w+)\.?\s+(\d{4})",
        text or "",
        re.I,
    )
    if m:
        groups = m.groups()
        if groups[0]:
            day, mon_raw, year = int(groups[0]), groups[1], int(groups[2])
        else:
            day, mon_raw, year = int(groups[3]), groups[4], int(groups[5])
        mon_key = (mon_raw or "")[:3].lower()
        month = _CAT_MONTHS.get(mon_key)
        if month:
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except ValueError:
                pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "estudi de detall" in n or "estudio de detalle" in n:
        return "estudio de detalle"
    if "modificaci" in n and ("pgou" in n or "pla general" in n):
        return "modificación PGOU"
    if "pgou" in n or "pla general" in n or "plan general" in n:
        return "PGOU"
    if "ban" in n and "obr" in n:
        return "bando obras"
    if "boib" in n:
        return "anuncio BOIB"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    return "planeamiento"


def _licencia_tipo(blob: str) -> str:
    n = blob.lower()
    if "ocupaci" in n:
        return "licencia de ocupación"
    if "comunicaci" in n:
        return "comunicación previa"
    if "declaraci" in n:
        return "declaración responsable"
    if "obra" in n:
        return "licencia / obra"
    return "trámite urbanístico"


class EivissaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay eivissa.es + sede espublico gestiona (tablón, transparencia PGOU/BOIB, bans urbanismo)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparency_urbanismo_url = str(
            self.config.get("transparency_urbanismo_url") or TRANSPARENCY_URBANISMO
        )
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.bans_max_pages = int(self.config.get("bans_max_pages") or 4)
        self._ssl_ctx = ssl.create_default_context()
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-eivissa/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.web_base}{path if path.startswith('/') else '/' + path}"

    def _abs_sede(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.sede_base}{path if path.startswith('/') else '/' + path}"

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_m.group(1), re.S | re.I):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0]) if cells else ""
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            expediente = _strip_html(cells[1]) if len(cells) > 1 else ""
            procedimiento = _strip_html(cells[2]) if len(cells) > 2 else ""
            categoria = _strip_html(cells[3]) if len(cells) > 3 else ""
            descripcion = _strip_html(cells[4]) if len(cells) > 4 else titulo
            fecha_cell = _strip_html(cells[5]) if len(cells) > 5 else ""
            url = link_m.group(1) if link_m else self.board_url
            if url.startswith("/"):
                url = self._abs_sede(url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente,
                    "procedimiento": procedimiento,
                    "categoria": categoria,
                    "descripcion": descripcion,
                    "fecha": _parse_fecha_dmy(fecha_cell) or _parse_fecha_dmy(titulo),
                    "url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            return self._parse_board_table(self._fetch(self.board_url), "tablon")
        except (urllib.error.URLError, TimeoutError):
            return []

    def _collect_bans_urbans(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in range(1, self.bans_max_pages + 1):
            url = f"{BANS_ASSET_PUBLISHER}{page}"
            try:
                html = self._fetch(url, timeout=45)
            except (urllib.error.URLError, TimeoutError):
                break
            found = 0
            for m in RE_BAN_BLOCK.finditer(html):
                ban_url, title_attr, title_text, fecha_raw, categoria = m.groups()
                categoria = unescape(categoria).strip()
                if "urbanisme" not in categoria.lower() and not RE_PROYECTO.search(title_attr):
                    continue
                titulo = unescape(title_attr or title_text).strip()
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _parse_fecha_dmy(fecha_raw) or _parse_fecha_dmy(titulo),
                        "url": ban_url,
                        "categoria": categoria,
                        "origen": "liferay_bans",
                    }
                )
                found += 1
            if found == 0 and page > 1:
                break
        return rows

    def _collect_transparency_boib(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_urbanismo_url, timeout=45)
        except (urllib.error.URLError, TimeoutError):
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pat in (RE_EXT_URL, RE_EXT_URL_ALT):
            for m in pat.finditer(html):
                url, title = m.group(1), _strip_html(m.group(2))
                if url in seen:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _parse_fecha_dmy(title),
                        "url": url,
                        "origen": "transparencia_boib",
                    }
                )
        return rows

    def _collect_pgou_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "titulo": "Pla General d'Ordenació Urbana 2023 — Ajuntament d'Eivissa",
                "fecha": "2023-09-19",
                "url": self.pgou_url,
                "origen": "liferay_pgou",
            }
        ]
        try:
            html = self._fetch(self.pgou_url, timeout=45)
        except (urllib.error.URLError, TimeoutError):
            return rows
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            path = m.group(1)
            if path in seen:
                continue
            seen.add(path)
            name = unescape(urllib.parse.unquote(path.split("/")[-2].replace("+", " ")))
            rows.append(
                {
                    "titulo": name[:500] or "Document PGOU Eivissa",
                    "fecha": _parse_fecha_dmy(name) or "2023-01-01",
                    "url": self._abs_web(path),
                    "origen": "liferay_pgou_pdf",
                }
            )
        return rows

    def _blob(self, row: dict[str, Any]) -> str:
        return " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria", "descripcion"))

    def _should_exclude(self, blob: str) -> bool:
        return bool(RE_EXCLUDE.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = self._blob(row)
        if self._should_exclude(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or _licencia_tipo(blob),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = self._blob(row)
        if self._should_exclude(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }

    def _generic_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if self._should_exclude(blob):
            return None
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
            "origen": row.get("origen"),
        }

    def _ban_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if not RE_LICENCIA.search(blob) and "obr" not in blob.lower():
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": _licencia_tipo(blob),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón anuncios urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tauler d'anuncis — sede electrónica Eivissa",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y licencias publicados en espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tràmits — seu electrònica (obres i urbanisme)",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Catálogo espublico; /dossier puede responder lento (>60s)",
                "origen": "sede_tramite",
            },
        ]

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
        for item in self._collect_bans_urbans():
            rec = self._ban_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_bans_urbans():
            rec = self._ban_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, len(rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_bans_urbans():
            add(self._generic_to_proyecto(item))
        for item in self._collect_transparency_boib():
            add(self._generic_to_proyecto(item))
        for item in self._collect_pgou_documents():
            add(self._generic_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "boib": sum(1 for r in rows if r.get("origen") == "transparencia_boib"),
            "pgou": sum(1 for r in rows if str(r.get("origen", "")).startswith("liferay_pgou")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
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
        return {**result, "added": max(0, after - before)}
