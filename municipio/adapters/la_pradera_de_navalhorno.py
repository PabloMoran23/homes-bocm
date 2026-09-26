from __future__ import annotations

import hashlib
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
from municipio.geometry import record_geometry

PLAI_BASE = "https://servicios.jcyl.es/PlanPublica"
MUNICIPIO = "La Pradera de Navalhorno"
MUNICIPIO_MATRIZ = "Real Sitio de San Ildefonso"
ID_PREFIX = "la-pradera-de-navalhorno"
PLAI_PROVINCIA = 40
PLAI_MUNICIPIO = 181

DEFAULT_SEED_PAGES: list[tuple[str, str]] = [
    (
        f"{PLAI_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia={PLAI_PROVINCIA}&municipio={PLAI_MUNICIPIO:03d}",
        "Archivo planeamiento urbanístico — Real Sitio de San Ildefonso (JCyL)",
    ),
    (
        f"{PLAI_BASE}/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia={PLAI_PROVINCIA}&municipio={PLAI_MUNICIPIO:03d}",
        "Planeamiento en información pública — Real Sitio de San Ildefonso (JCyL)",
    ),
]

RE_LOCALITY = re.compile(r"(?i)pradera|navalhorno")
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|"
    r"informaci[oó]n p[uú]blica|expediente|modificaci[oó]n|aprobaci[oó]n|"
    r"ordenanza|parcela|suelo|sector|normas urban)",
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


def _proyecto_tipo(title: str, instrumento: str = "") -> str:
    blob = f"{title} {instrumento}".lower()
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "informaci" in blob:
        return "información pública"
    return "planeamiento"


class LaPraderaDeNavalhornoAyuntamientoAdapter(AyuntamientoAdapter):
    """Localidad en Real Sitio de San Ildefonso — PlanPublica JCyL filtrado."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or PLAI_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.plai_provincia = int(self.config.get("plai_provincia") or PLAI_PROVINCIA)
        self.plai_municipio = int(self.config.get("plai_municipio") or PLAI_MUNICIPIO)
        self.plai_max_pages = int(self.config.get("plai_max_pages", 8))
        self.plai_page_size = int(self.config.get("plai_page_size", 15))
        self.municipio_matriz = str(self.config.get("municipio_matriz") or MUNICIPIO_MATRIZ)
        locality_pat = str(self.config.get("locality_filter") or "pradera|navalhorno")
        self.locality_re = re.compile(locality_pat, re.I)
        raw_seeds = self.config.get("seed_pages") or DEFAULT_SEED_PAGES
        self.seed_pages: list[tuple[str, str]] = []
        for item in raw_seeds:
            if isinstance(item, dict):
                self.seed_pages.append((str(item["url"]), str(item.get("titulo") or item["url"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                self.seed_pages.append((str(item[0]), str(item[1])))
            else:
                self.seed_pages.append((str(item), str(item)))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-la-pradera-de-navalhorno/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _plai_page_url(self, offset: int, *, info_publica: bool = False) -> str:
        action = "searchVPubDocMuniPlai.do" if info_publica else "searchVPubDocMuniPlau.do"
        params = {
            "pager.size": str(self.plai_page_size),
            "pager.reload": "no",
            "municipio": f"{self.plai_municipio:03d}",
            "provincia": str(self.plai_provincia),
            "urlResults": action,
            "pager.offset": str(offset),
        }
        if info_publica:
            params["bInfoPublica"] = "S"
        else:
            params["bInfoPublica"] = "N"
        return f"{PLAI_BASE}/{action}?{urllib.parse.urlencode(params)}"

    @staticmethod
    def _parse_plai_rows(html: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            cells = [
                _strip_html(c)
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            ]
            cells = [c for c in cells if c]
            if len(cells) < 5 or cells[0] in {"Libro", "Tipo"}:
                continue
            titulo = cells[4] if len(cells) > 4 else cells[-1]
            if not titulo or re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", titulo):
                continue
            fecha_pub = cells[2]
            doc_m = re.search(r"doOpen\('(\d+)'", tr) or re.search(r"doOpenDocumento\((\d+)\)", tr)
            boletin_m = re.search(r"doGoBoletin\('(\d+)'", tr)
            doc_id = doc_m.group(1) if doc_m else (boletin_m.group(1) if boletin_m else None)
            if doc_id and doc_m:
                url = f"{PLAI_BASE}/openDocumento.do?cDocId={doc_id}"
            elif boletin_m:
                url = f"{PLAI_BASE}/openBoletin.do?cDocId={boletin_m.group(1)}"
            else:
                url = (
                    f"{PLAI_BASE}/searchVPubDocMuniPlau.do?"
                    f"provincia={PLAI_PROVINCIA}&municipio={PLAI_MUNICIPIO:03d}"
                )
            rows.append(
                {
                    "title": titulo,
                    "url": url,
                    "fecha": fecha_pub,
                    "instrumento": cells[1] if len(cells) > 1 else "",
                    "origen": "plai_jcyl",
                    "doc_id": doc_id or "",
                }
            )
        return rows

    def _matches_locality(self, text: str) -> bool:
        return bool(self.locality_re.search(text or ""))

    def _collect_plai(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for info_publica in (False, True):
            for page in range(self.plai_max_pages):
                offset = page * self.plai_page_size
                try:
                    html = self._fetch(self._plai_page_url(offset, info_publica=info_publica))
                except urllib.error.URLError:
                    break
                parsed = self._parse_plai_rows(html)
                if not parsed:
                    break
                for item in parsed:
                    if not self._matches_locality(item["title"]):
                        continue
                    key = item["url"] + item["title"]
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "titulo": item["title"][:500],
                            "fecha": _parse_fecha_dmy(item.get("fecha") or ""),
                            "url": item["url"],
                            "instrumento": item.get("instrumento") or "",
                            "origen": "plai_jcyl",
                            "municipio_matriz": self.municipio_matriz,
                        }
                    )
                if len(parsed) < self.plai_page_size:
                    break
        return rows

    def _plai_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row.get("instrumento", "")),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "municipio_matriz": self.municipio_matriz,
            "instrumento": row.get("instrumento") or None,
        }

    def _seed_to_proyecto(self, url: str, titulo: str) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": None,
            "tipo": "planeamiento",
            "url": url,
            "source": "ayuntamiento",
            "origen": "plai_semilla",
            "municipio_matriz": self.municipio_matriz,
            "nota": "Índice PlanPublica del municipio matriz (Real Sitio de San Ildefonso)",
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
        self._write_jsonl(out_jsonl, [])
        return {"rows": 0, "status": "ok", "nota": "Sin sede activa ni tablón de licencias"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        stats = self.backfill_licencias(out_jsonl)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": 0, "added": 0},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return stats

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_plai():
            add(self._plai_to_proyecto(item))
        for url, titulo in self.seed_pages:
            add(self._seed_to_proyecto(url, titulo))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "plai_jcyl": sum(1 for r in rows if r.get("origen") == "plai_jcyl"),
            "semillas": sum(1 for r in rows if r.get("origen") == "plai_semilla"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
