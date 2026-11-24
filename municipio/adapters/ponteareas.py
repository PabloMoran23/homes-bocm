from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

SEDE_BASE = "https://ponteareas.sedelectronica.gal"
MUNICIPIO = "Ponteareas"
ID_PREFIX = "ponteareas"
INE = "36042"

SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_URB = "https://siotuga.xunta.gal/siotuga/urb?lang=es_ES"
IDEG_VISOR = (
    "https://ideg.xunta.gal/portalsix/apps/webappviewer/index.html"
    "?find=REAL%2C+36860+Ponteareas+%28Pontevedra%29&id=a3af4fe608664fd083182874347daa26"
)
DOG_PGOM_2021 = (
    "https://www.xunta.gal/dog/Publicados/2021/20211013/AnuncioG0532-041021-0001_es.html"
)
DOG_MP01_2025 = (
    "https://www.xunta.gal/dog/Publicados/2025/20251106/AnuncioG0765-291025-0001_es.html"
)
PBA_VISOR = "https://mapas.xunta.gal/visores/pba/"

RE_CATALOG_LINK = re.compile(
    r'href="(https://ponteareas\.sedelectronica\.gal/catalog/t/[a-f0-9-]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_BOARD_PREVIEW = re.compile(
    r'href="(https://ponteareas\.sedelectronica\.gal/preview-document/[^"]+)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr>\s*(.*?)\s*</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(
    r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
)
RE_URBAN = re.compile(
    r"(?i)(urban|licen|planeam|obra|territ|actividad|ocupaci|comunicaci[oó]n|declaraci[oó]n|"
    r"certificado|autorizaci[oó]n|vaos|terraza)",
)
RE_PROYECTO = re.compile(
    r"(?i)(plan (?:xeral|general|parcial|especial)|planeam|urban|informaci[oó]n p[uú]blica|"
    r"expediente|pgom|pxom|dog|bop|modificaci[oó]n|biomasa|demanial|equipamento|"
    r"exposici[oó]n|licen|obra)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


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


def _proyecto_tipo(titulo: str, figura: str = "") -> str:
    n = f"{titulo} {figura}".lower()
    if "modificaci" in n and ("pgom" in n or "pxom" in n or "plan xeral" in n):
        return "modificación PGOM"
    if "plan xeral" in n or "pgom" in n or "pxom" in n:
        return "PGOM/PXOM"
    if "información pública" in n or "informacion publica" in n:
        return "información pública"
    if "plan especial" in n:
        return "plan especial"
    if "biomasa" in n or "ambiental" in n:
        return "medio ambiente"
    if "licen" in n or "obra" in n:
        return "licencia / obra"
    return "planeamiento"


class PonteareasAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona + SIOTUGA (INE 36042, PGOM 2021). Portal corporativo con SSL roto."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.siotuga_inventario = str(
            self.config.get("siotuga_inventario") or SIOTUGA_INVENTARIO
        )
        self.max_siotuga = int(self.config.get("max_siotuga_plans", 80))
        self._jar = http.cookiejar.CookieJar()
        self._sede_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
        )
        self._siotuga_jar = http.cookiejar.CookieJar()
        self._siotuga_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._siotuga_jar),
        )
        self._siotuga_token_cache: str | None = None

    def _ua(self) -> str:
        return str(self.config.get("user_agent", "poc-bocm-ponteareas/1.0"))

    def _warm_sede(self) -> None:
        if getattr(self, "_sede_warmed", False):
            return
        try:
            self._fetch_sede(f"{self.sede_base}/info.0", delay=False)
        except urllib.error.URLError:
            pass
        self._sede_warmed = True

    def _fetch_sede(self, url: str, *, delay: bool = True) -> str:
        if delay:
            time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        with self._sede_opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_board(self) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(self.board_url, headers={"User-Agent": self._ua()})
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_siotuga(self, url: str, *, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self._ua()}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with self._siotuga_opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _siotuga_token(self) -> str | None:
        if self._siotuga_token_cache:
            return self._siotuga_token_cache
        try:
            html = self._fetch_siotuga(self.siotuga_inventario)
        except urllib.error.URLError:
            return None
        m = re.search(r"id='token'[^>]+value='([^']+)'", html)
        if m:
            self._siotuga_token_cache = m.group(1)
        return self._siotuga_token_cache

    def _collect_siotuga(self) -> list[dict[str, Any]]:
        token = self._siotuga_token()
        if not token:
            return []
        rows: list[dict[str, Any]] = []
        for idclase, origen in (("13", "siotuga_desenvolvemento"), ("14", "siotuga_xeral"), ("16", "siotuga_historico")):
            try:
                body = urllib.parse.urlencode(
                    {"id": INE, "token": token, "idclase": idclase},
                ).encode()
                raw = self._fetch_siotuga(
                    "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php",
                    data=body,
                )
                if not raw.strip() or raw.startswith("tokenIncorrecto"):
                    continue
                data = json.loads(raw)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(data, list):
                continue
            for item in data:
                doc_id = str(item.get("id") or "")
                title = unescape(str(item.get("docnome") or "").strip())
                if not title or not doc_id:
                    continue
                figura = str(item.get("figura") or "")
                fecha = (
                    str(item.get("fechaaddef") or "").strip()
                    or str(item.get("fechadog") or "").strip()
                    or None
                )
                rows.append(
                    {
                        "titulo": f"{title} ({figura})" if figura else title,
                        "fecha": fecha,
                        "url": f"{self.siotuga_inventario}#doc-{doc_id}",
                        "tipo": _proyecto_tipo(title, figura),
                        "origen": origen,
                    }
                )
                if len(rows) >= self.max_siotuga:
                    return rows
        return rows

    def _fixed_proyectos(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "PGOM Ponteareas — aprobación definitiva (DOG 2021-10-13)",
                "fecha": "2021-09-30",
                "url": DOG_PGOM_2021,
                "tipo": "PGOM/PXOM",
                "origen": "dog_xunta",
            },
            {
                "titulo": "MP01 PGOM — equipamiento EQ DEP 21 (DOG 2025-11-06)",
                "fecha": "2025-10-28",
                "url": DOG_MP01_2025,
                "tipo": "modificación PGOM",
                "origen": "dog_xunta",
            },
            {
                "titulo": "Inventario planeamiento — SIOTUGA (INE 36042)",
                "fecha": None,
                "url": self.siotuga_inventario,
                "tipo": "PGOM/PXOM",
                "origen": "siotuga",
            },
            {
                "titulo": "Visor cartográfico IDEG — Ponteareas",
                "fecha": None,
                "url": IDEG_VISOR,
                "tipo": "visor planeamiento",
                "origen": "ideg_visor",
            },
            {
                "titulo": "Visor Plan Básico Autonómico — Xunta de Galicia",
                "fecha": None,
                "url": PBA_VISOR,
                "tipo": "visor planeamiento",
                "origen": "xunta_pba",
            },
        ]

    def _collect_dossier_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(title: str, url: str, origen: str) -> None:
            if url in seen:
                return
            seen.add(url)
            rows.append({"titulo": title, "url": url, "origen": origen})

        self._warm_sede()
        try:
            html = self._fetch_sede(self.dossier_url)
        except urllib.error.URLError:
            return rows
        for m in RE_CATALOG_LINK.finditer(html):
            url, title = m.group(1), unescape(m.group(2).strip())
            if not RE_URBAN.search(title):
                continue
            add(title, url, "sede_tramite")
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch_board()
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for row_html in RE_BOARD_ROW.findall(html):
            if "preview-document" not in row_html:
                continue
            cells = {
                unescape(k): _strip_html(v)
                for k, v in RE_BOARD_CELL.findall(row_html)
            }
            title = (
                cells.get("Documento")
                or cells.get("Título")
                or cells.get("Titulo")
                or cells.get("Descrición")
                or cells.get("Descripción")
                or ""
            )
            pm = RE_BOARD_PREVIEW.search(row_html)
            doc_url = pm.group(1) if pm else self.board_url
            blob = " ".join(cells.values())
            if not title and not pm:
                continue
            if not RE_PROYECTO.search(title) and not RE_PROYECTO.search(blob):
                continue
            fecha = _parse_fecha_dmy(blob) or _parse_fecha_dmy(
                cells.get("Data de Publicación", "") or cells.get("Data", "")
            )
            rows.append(
                {
                    "titulo": title or "Anuncio tablón urbanismo",
                    "fecha": fecha,
                    "url": doc_url,
                    "origen": "sede_board",
                    "expediente": cells.get("Expediente"),
                    "procedimiento": cells.get("Procedemento") or cells.get("Procedimiento"),
                }
            )
        return rows

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url + titulo),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expediente"):
            rec["expediente"] = row["expediente"]
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
        return {
            "id": _stable_id("lic", url + titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": url,
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
        for item in self._collect_dossier_tramites():
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tramites_info"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_dossier_tramites():
            existing[self._to_licencia(item)["id"]] = self._to_licencia(item)
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

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._fixed_proyectos():
            add(self._to_proyecto(item))
        for item in self._collect_siotuga():
            add(self._to_proyecto(item))
        for item in self._collect_board():
            add(self._to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "fixed": sum(
                1
                for r in rows
                if str(r.get("origen", "")).startswith(("dog", "siotuga", "ideg", "xunta"))
            ),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
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
