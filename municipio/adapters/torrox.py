from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records

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

WEB_BASE = "http://www.torrox.es"
MUNICIPIO = "Torrox"
ID_PREFIX = "torrox"

# Fragmentos AJAX del portal (urbanismo)
SAC_SEEDS: list[tuple[str, str]] = [
    ("urba_servicio", f"{WEB_BASE}/sac/urba_servicio"),
    ("urba_pgou", f"{WEB_BASE}/sac/urba_pgou"),
    ("urba_loua", f"{WEB_BASE}/sac/urba_loua"),
    ("plan_playas", f"{WEB_BASE}/sac/plan_playas"),
]

RE_PDF = re.compile(
    r'<a[^>]+href=["\']([^"\']*(?:resources/files/[^"\']+\.pdf)[^"\']*)["\'][^>]*>([^<]{3,500})</a>',
    re.I | re.S,
)
RE_BOP_FECHA = re.compile(
    r"(?i)BOP\s*(?:n|nr|º|o)?\.?\s*[\d\s\-/]*\s*(?:de\s+)?(?:[A-Za-záéíóúñ]+\s+)?(?:de\s+)?(\d{1,2})[/-](\d{1,2})[/-](\d{4})"
)
RE_ANY_DMY = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _abs_url(href: str) -> str:
    href = unescape(href.strip())
    return urllib.parse.urljoin(f"{WEB_BASE}/", href)


def _parse_fecha(text: str) -> str | None:
    m = RE_BOP_FECHA.search(text or "")
    if not m:
        m = RE_ANY_DMY.search(text or "")
    if not m:
        return None
    try:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _titulo_tipo(title: str) -> str:
    n = (title or "").lower()
    if "playa" in n or "costa" in n:
        return "Plan playas"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "loua" in n or "adaptación" in n or "adaptacion" in n:
        return "adaptación LOUA"
    if "ordenanza" in n or "declaración responsable" in n or "declaracion responsable" in n:
        return "normativa urbanística"
    if "plano" in n or "clasificación" in n or "calificación" in n or "alineac" in n:
        return "plano urbanístico"
    if "memoria" in n or "anexo" in n:
        return "documentación planeamiento"
    return "urbanismo"


class TorroxAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal propio Torrox (SAC): PDFs de planeamiento; sede electrónica inaccesible."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seeds: list[tuple[str, str]] = [
            (str(a[0]), str(a[1]))
            for a in (self.config.get("sac_seeds") or SAC_SEEDS)
        ]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        ua = str(self.config.get("user_agent") or "poc-bocm-torrox/1.0")
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
            enc = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(enc, errors="replace")

    def _pdf_rows_from_html(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PDF.finditer(html or ""):
            href = _abs_url(m.group(1))
            titulo = unescape(re.sub(r"\s+", " ", m.group(2)).strip())
            if len(titulo) < 3:
                continue
            key = href
            fecha = _parse_fecha(titulo)
            if not fecha:
                ym = RE_YEAR.search(titulo)
                fecha = f"{ym.group(1)}-01-01" if ym else None
            rows.append(
                {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": _titulo_tipo(titulo),
                    "url": href,
                    "source": "ayuntamiento",
                    "entity_type": "document",
                    "origen": f"sac_pdf_{origen}",
                }
            )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for key, url in self.seeds:
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for row in self._pdf_rows_from_html(html, key):
                out[row["id"]] = row
        return list(out.values())

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
        self._write_jsonl(out_jsonl, [])
        return {"rows": 0, "status": "ok", "note": "sin listado público de licencias concedidas en portal consultado"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self.backfill_licencias(out_jsonl)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": 0,
                    "added": 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "sources": [s[0] for s in self.seeds]}

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
