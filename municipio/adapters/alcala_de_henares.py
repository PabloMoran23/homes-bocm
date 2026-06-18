from __future__ import annotations

import hashlib
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

URBANISMO_BASE = "https://urbanismo.ayto-alcaladehenares.es"
WP_API = f"{URBANISMO_BASE}/wp-json/wp/v2"

DEFAULT_PROYECTO_CATS = [128, 134, 145, 154]
DEFAULT_LICENCIA_CATS = [147, 151]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|demanial|urban))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|modificaci[oó]n|"
    r"aprobaci[oó]n|unidad de ejecuci|estudio (?:ac[uú]stico|ambiental)|"
    r"segregaci|junta de compensaci|orden de ejecuci)",
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"alcala-henares-{prefix}-{h}"


def _iso_date(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw[:10] if len(raw) >= 10 else None


class AlcalaDeHenaresAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress REST API del portal Urbanismo (planeamiento, convenios, licencias)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or URBANISMO_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_api = str(self.config.get("wp_api_base") or WP_API).rstrip("/")
        self.proyecto_cats = set(self.config.get("proyecto_category_ids") or DEFAULT_PROYECTO_CATS)
        self.licencia_cats = set(self.config.get("licencia_category_ids") or DEFAULT_LICENCIA_CATS)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-alcala-henares/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60, context=self._ssl_ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _paginate_posts(self) -> list[dict[str, Any]]:
        posts: list[dict[str, Any]] = []
        page = 1
        while page <= 20:
            url = f"{self.wp_api}/posts?per_page=100&page={page}&status=publish"
            try:
                batch = self._fetch_json(url)
            except urllib.error.URLError:
                break
            if not isinstance(batch, list) or not batch:
                break
            posts.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return posts

    @staticmethod
    def _post_title(post: dict[str, Any]) -> str:
        title = post.get("title") or {}
        return unescape(str(title.get("rendered") or "")).strip()

    @staticmethod
    def _post_categories(post: dict[str, Any]) -> set[int]:
        cats = post.get("categories") or []
        return {int(c) for c in cats if str(c).isdigit()}

    @staticmethod
    def _extract_pdfs(post: dict[str, Any]) -> list[str]:
        content = str((post.get("content") or {}).get("rendered") or "")
        pdfs: list[str] = []
        for m in RE_PDF.finditer(content):
            href = unescape(m.group(1))
            if href.startswith("http"):
                pdfs.append(href)
            else:
                pdfs.append(urllib.parse.urljoin(URBANISMO_BASE, href))
        return list(dict.fromkeys(pdfs))

    def _title_to_licencia(self, post: dict[str, Any]) -> dict[str, Any] | None:
        title = self._post_title(post)
        cats = self._post_categories(post)
        if not RE_LICENCIA.search(title) and not (cats & self.licencia_cats):
            return None
        if RE_PROYECTO.search(title) and not RE_LICENCIA.search(title):
            return None
        url = str(post.get("link") or "").strip()
        if not url:
            return None
        pdfs = self._extract_pdfs(post)
        tipo_m = re.search(r"(?i)(autorizaci[oó]n|comunicaci[oó]n previa|declaraci[oó]n responsable|licencia)", title)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": _iso_date(str(post.get("date") or "")),
            "tipo": tipo_m.group(1).lower() if tipo_m else "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }
        if pdfs:
            rec["pdf_url"] = pdfs[0]
        return rec

    def _title_to_proyecto(self, post: dict[str, Any]) -> dict[str, Any] | None:
        title = self._post_title(post)
        cats = self._post_categories(post)
        if not RE_PROYECTO.search(title) and not (cats & self.proyecto_cats):
            return None
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title) and not (cats & self.proyecto_cats):
            return None
        url = str(post.get("link") or "").strip()
        if not url:
            return None
        pdfs = self._extract_pdfs(post)
        tipo = "urbanismo"
        if re.search(r"(?i)convenio", title):
            tipo = "convenio urbanístico"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica", title):
            tipo = "información pública"
        elif re.search(r"(?i)plan (?:parcial|especial)|modificaci[oó]n|unidad de ejecuci", title):
            tipo = "planeamiento"
        elif re.search(r"(?i)aprobaci[oó]n definitiva", title):
            tipo = "aprobación definitiva"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": "Alcalá de Henares",
            "titulo": title[:500],
            "fecha": _iso_date(str(post.get("date") or "")),
            "tipo": tipo,
            "url": url,
            "source": "ayuntamiento",
        }
        if pdfs:
            rec["pdf_url"] = pdfs[0]
            if len(pdfs) > 1:
                rec["pdf_urls"] = pdfs[:30]
        return rec

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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for post in self._paginate_posts():
            rec = self._title_to_licencia(post)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "urbanismo_wp_api"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for post in self._paginate_posts():
            rec = self._title_to_licencia(post)
            if not rec:
                continue
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        posts = self._paginate_posts()
        for post in posts:
            rec = self._title_to_proyecto(post)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "wp_posts": len(posts)}

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
