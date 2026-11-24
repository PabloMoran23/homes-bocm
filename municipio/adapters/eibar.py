from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.eibar.eus"
DUE_API = (
    "https://w390w.gipuzkoa.net/WAS/CORP/DUERegistroPlaneamientoWEB/api/record/"
    "?municipality=eibar"
)
TRAMITES_SERVICIOS = f"{BASE}/es/tramites/tramites-servicios"
PLANEAMIENTO_PAGE = f"{BASE}/es/ayuntamiento/planeamiento"
TABLON_PROVINCIAL = "https://erakunde.egoitza.gipuzkoa.eus?De=03015"
MUNICIPIO = "Eibar"
ID_PREFIX = "eibar"

RE_PLONE_URBANISMO = re.compile(
    r'href="(https://www\.eibar\.eus/es/tramites/tramites-servicios/urbanismo/[^"]+)"'
    r"[^>]*>([^<]+)</a>",
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(obra|lizent|licen|jarduera.*obra|erabiler|eraikuntza|urban|actividad|"
    r"ocupaci[oó]n|comunicaci[oó]n|permiso|ite\b|andamio)",
)
RE_PROYECTO_TIPO = (
    (re.compile(r"(?i)xehetasun|detalle"), "estudio de detalle"),
    (re.compile(r"(?i)plan berezi|plan especial"), "plan especial"),
    (re.compile(r"(?i)aldaketa|modificaci"), "modificación puntual"),
    (re.compile(r"(?i)hiri antolamendu|planeamiento"), "planeamiento urbanístico"),
    (re.compile(r"(?i)hap\b|plan nagusi|pgou|plan orokorra"), "PGOU/HAP"),
    (re.compile(r"(?i)plan partzial|plan parcial"), "plan parcial"),
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()[:10]
    if re.match(r"\d{4}-\d{2}-\d{2}", v):
        return v
    return None


def _classify_tipo(title: str) -> str:
    for pat, label in RE_PROYECTO_TIPO:
        if pat.search(title):
            return label
    return "expediente planeamiento"


class EibarAyuntamientoAdapter(AyuntamientoAdapter):
    """Eibar: registro DUE Gipuzkoa (JSON) + trámites Plone de urbanismo (licencias informativas)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.due_api = str(self.config.get("due_api") or DUE_API)

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-eibar/1.0"),
                "Accept": "text/html,application/json,*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        charset = "utf-8"
        if b"charset=iso-8859-1" in raw[:800].lower() or b"charset=latin-1" in raw[:800].lower():
            charset = "latin-1"
        return raw.decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
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

    def _collect_due_proyectos(self) -> list[dict[str, Any]]:
        try:
            payload = self._fetch_json(self.due_api)
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"DUE API no disponible: {exc}") from exc

        items = payload.get("resultadoBusqueda") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return []

        rows: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            reg = str(item.get("registration_number") or "").strip()
            title = unescape(str(item.get("title") or "").strip())
            link = str(item.get("links") or "").strip()
            if not title:
                continue
            ghe = f"GHE-{reg}" if reg else str(item.get("id") or title)
            url = link or PLANEAMIENTO_PAGE
            fecha = _normalize_date(
                str(item.get("checkin_date") or item.get("inscription_date") or "")
            )
            key = link or f"{ghe}:{title}"
            rows.append(
                {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": f"{title} ({ghe})"[:500],
                    "fecha": fecha,
                    "tipo": _classify_tipo(title),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "due_gipuzkoa_api",
                    "codigo_expediente": ghe,
                    "area": item.get("area"),
                }
            )
        return rows

    def _collect_plone_licencias(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TRAMITES_SERVICIOS)
        except urllib.error.URLError:
            return []

        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for m in RE_PLONE_URBANISMO.finditer(html):
            url = m.group(1).split("#")[0].rstrip("/")
            title = unescape(re.sub(r"\s+", " ", m.group(2)).strip())
            if not title or not RE_LICENCIA.search(f"{title} {url}"):
                continue
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia/obras",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "plone_tramite_informativo",
                    "nota": "Página informativa Plone; no listado de concesiones en tablón",
                }
            )

        rows.append(
            {
                "id": _stable_id("lic", TABLON_PROVINCIAL),
                "fecha_concesion": None,
                "tipo": "tablón provincial Gipuzkoa",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios / iragarki taula (Diputación Gipuzkoa)",
                "url": TABLON_PROVINCIAL,
                "source": "ayuntamiento",
                "origen": "tablon_provincial_enlace",
                "nota": "Anuncios de licencias pueden publicarse en sede provincial (De=03015)",
            }
        )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_plone_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "plone_tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_plone_licencias():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_due_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "due_api": sum(1 for r in rows if r.get("origen") == "due_gipuzkoa_api"),
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
