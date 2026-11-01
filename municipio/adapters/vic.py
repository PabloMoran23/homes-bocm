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

WEB_BASE = "https://www.vic.cat"
SEDE_BASE = "https://seuelectronica.vic.cat"
MUNICIPIO = "Vic"
ID_PREFIX = "vic"

PLANEJAMENT_VIGENT_RSS = (
    f"{WEB_BASE}/serveis/territori/urbanisme/prova/"
    "planejament-i-gestio-urbanistica-vigent-1/"
    "planejament-i-gestio-urbanistica-vigent/rss.xml"
)
PLANEJAMENT_EN_TRAMIT = (
    f"{WEB_BASE}/serveis/territori/urbanisme/prova/"
    "planejament-i-gestio-urbanistica-en-tramit"
)
RPUC_MUNICI = "https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08298"
PIU_URL = "http://informaciourbanistica.vic.cat/vicgp/?center=437933.0,4641643.0&scale=50000&thematic=tematic1"

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "llicència d'obres",
    "llicencia de obras",
    "comunicació prèvia",
    "comunicacion previa",
    "comunicació prèvia d'obres",
    "declaració responsable",
    "declaracion responsable",
    "ocupació de la via pública",
    "ocupacion de la via publica",
    "primera ocupació",
    "primera ocupacion",
    "certificat d'obra",
    "certificado de obra",
    "actuació urbanística",
    "actuacion urbanistica",
)

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|licències|licencias|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|declaraci[oó] responsable|obra[s]? (?:major|menor)|"
    r"ocupaci[oó] de la via|enderroc|primera ocupaci[oó]|recepci[oó] d'obra|"
    r"actuaci[oó] urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|poum|pgou|pau\b|pmu\b|pe\b|modificaci[oó]|"
    r"reparcel|projecte d'urban|expropiaci|conveni urban|informaci[oó] p[uú]blica|"
    r"pla especial|pla de millora|ordenan[cç]a|gesti[oó] urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(proc[eé]s selectiu|oposici[oó]n|subvenci[oó]n|padr[oó]n|empadron|"
    r"festa|agenda cultural|guardia urbana.*informe|xarxa de serveis)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://seuelectronica\.vic\.cat)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://seuelectronica\.vic\.cat)?/catalog/t/[a-f0-9-]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_TABLE_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_TABLE_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.I | re.S)
RE_LINK = re.compile(r'href="(https://www\.vic\.cat[^"]+)"', re.I)


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


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and "poum" in n:
        return "modificación POUM"
    if "reparcel" in n:
        return "reparcelación"
    if "projecte d'urban" in n or "proyecto de urbaniz" in n:
        return "proyecto de urbanización"
    if "expropiaci" in n:
        return "expropiación"
    if "pla especial" in n or "plan especial" in n:
        return "plan especial"
    if "pla de millora" in n or "pmu" in n:
        return "plan de mejora urbana"
    if "pau" in n:
        return "polígono de actuación"
    if "conveni" in n:
        return "convenio urbanístico"
    if "poum" in n or "pla d'ordenaci" in n:
        return "POUM"
    if "ordenan" in n:
        return "ordenanza urbanística"
    if "informaci" in n and "públic" in n:
        return "información pública"
    return "planeamiento"


class VicAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone vic.cat (taules planejament RSS/HTML) + sede espublico (board + dossier)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier.0")
        self._ssl_ctx = ssl.create_default_context()
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _ua(self) -> str:
        return str(self.config.get("user_agent") or "poc-bocm-vic/1.0")

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_plain(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _parse_planejament_tables(self, html: str, source_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in RE_TABLE_ROW.findall(html):
            cells = [_strip_html(c) for c in RE_TABLE_CELL.findall(tr)]
            if len(cells) < 3:
                continue
            if cells[0].lower() in ("any", "año"):
                continue
            title = cells[1] if len(cells) > 1 else cells[0]
            if len(title) < 5:
                continue
            exp = cells[-1] if cells[-1] not in ("-", "") else None
            fecha = None
            for cell in reversed(cells):
                if RE_FECHA_DMY.search(cell):
                    fecha = _parse_fecha_dmy(cell)
                    break
            link_m = RE_LINK.search(tr)
            url = link_m.group(1) if link_m else source_url
            if url.endswith(".pdf"):
                titulo = f"{title} — {Path(urllib.parse.urlparse(url).path).name}"
            else:
                titulo = title
            key = f"{exp or ''}|{titulo}|{url}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "expediente": exp,
                    "url": url,
                    "origen": "planejament_taula",
                    "key": key,
                }
            )
        return rows

    def _collect_planejament(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        sources = (
            (self._fetch_plain(PLANEJAMENT_VIGENT_RSS), PLANEJAMENT_VIGENT_RSS, True),
            (self._fetch_plain(PLANEJAMENT_EN_TRAMIT), PLANEJAMENT_EN_TRAMIT, False),
        )
        for raw, src_url, is_rss in sources:
            html = raw
            if is_rss:
                cdata = re.findall(r"<!\[CDATA\[(.*?)\]\]>", raw, re.S)
                html = "\n".join(cdata) if cdata else raw
            for row in self._parse_planejament_tables(html, src_url):
                by_key[row["key"]] = row
        ref = {
            "titulo": "Registre de planejament urbanístic de Catalunya (RPUC) — Vic (08298)",
            "fecha": None,
            "expediente": None,
            "url": RPUC_MUNICI,
            "origen": "referencia_rpuc",
            "key": RPUC_MUNICI,
        }
        by_key[ref["key"]] = ref
        return list(by_key.values())

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
            if not documento or documento in ("Documento",):
                continue
            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"
            titulo = (title_m.group(1).strip() if title_m else "") or cells.get("class_description", "") or documento
            expediente = cells.get("class_folderCode", "")
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(cells.get("class_dateFrom", "")),
                    "expediente": expediente,
                    "procedimiento": cells.get("class_folderName", ""),
                    "categoria": cells.get("class_boardCategory", ""),
                    "url": url,
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_dossier_tramites(self) -> list[dict[str, Any]]:
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
            low = titulo.lower()
            if not any(p in low for p in LICENCIA_TRAMITE_PATTERNS):
                if not RE_LICENCIA.search(titulo):
                    continue
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            out.append(obj)
                    except json.JSONDecodeError:
                        pass
        return out

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('expediente', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") != "referencia_rpuc" and not RE_PROYECTO.search(blob):
            return None
        url = str(row.get("url") or self.web_base)
        exp = row.get("expediente")
        rec_id = _stable_id("proy", f"{exp or ''}|{row.get('titulo', '')}|{url}")
        return {
            "id": rec_id,
            "municipio": MUNICIPIO,
            "titulo": row.get("titulo"),
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "expediente": exp,
            "origen": row.get("origen"),
        }

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "expediente")
        )
        if RE_EXCLUDE.search(blob) and not RE_LICENCIA.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        url = str(row.get("url") or self.sede_base)
        key = row.get("expediente") or url
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia / urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row.get("titulo"),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for raw in self._collect_planejament():
            rec = self._row_to_proyecto(raw)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "plone_planejament"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats.get("rows", before)
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
        return stats

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._collect_board():
            add(self._row_to_licencia(row))

        for tram in self._collect_dossier_tramites():
            add(
                {
                    "id": _stable_id("lic", tram["url"]),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": tram["titulo"],
                    "url": tram["url"],
                    "source": "ayuntamiento",
                    "origen": tram.get("origen"),
                }
            )

        if not rows:
            add(
                {
                    "id": _stable_id("lic", self.board_url),
                    "fecha_concesion": None,
                    "tipo": "tablón de anuncios",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Tauler d'anuncis — sede electrónica Vic",
                    "url": self.board_url,
                    "source": "ayuntamiento",
                    "origen": "sede_tablon",
                }
            )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "sede_espublico",
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats.get("rows", before)
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
        return stats
