from __future__ import annotations

import gzip
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

BASE = "https://www.alcobendas.org"

TABLON_EDICTOS = f"{BASE}/es/tramites/tablon-edictos"
ACUERDOS_IP = (
    f"{BASE}/es/ayuntamiento/informacion-administrativa/"
    "acuerdos-informacion-publica?buscar=&field_departamento_target_id=2466"
)
CONVENIOS_URB = (
    f"{BASE}/es/ayuntamiento/informacion-administrativa/convenios?"
    "buscar=&field_firmante_convenio_ayto_target_id=All"
    "&field_inicio_vi_value=&field_f_value=&field_area_tematica_target_id=1110"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/es/temas/ciudad-sostenible/urbanismo/PGOU",
    f"{BASE}/es/temas/ciudad-sostenible/urbanismo/planes-especiales",
    f"{BASE}/es/temas/ciudad-sostenible/urbanismo/modificaciones-aprobadas",
    f"{BASE}/es/temas/ciudad-sostenible/urbanismo/estudios-de-detalle",
    f"{BASE}/es/temas/ciudad-sostenible/urbanismo/desarrollos-en-ejecucion",
    f"{BASE}/es/temas/ciudad-sostenible/urbanismo/nuevos-desarrollos",
    f"{BASE}/es/transparencia/ordenacion-territorio-y-obras-publicas",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|instalaci)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|autorizaci[oó]n (?:previa|ambiental))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|aprobaci[oó]n|disoluci[oó]n|"
    r"entidad de conservaci[oó]n|cerramiento|desarrollo urban)",
)
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_FECHA_DMY_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/sites/default/files/(\d{4})-(\d{2})/")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{3,5}(?:/\d{4})?)")


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"alcobendas-{prefix}-{h}"


def _parse_fecha_dmy_dash(text: str) -> str | None:
    m = RE_FECHA_DMY_DASH.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_dmy_slash(text: str) -> str | None:
    m = RE_FECHA_DMY_SLASH.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_pdf_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _iso_from_year(text: str) -> str | None:
    years = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", text) if 1980 <= int(y) <= 2030]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _parse_expte(text: str) -> str | None:
    m = RE_EXPTE.search(text)
    return m.group(1).strip() if m else None


def _clean_title(text: str) -> str:
    t = unescape(text or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:500]


class AlcobendasAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal: tablón edictos + acuerdos IP + convenios + páginas PGOU/planeamiento."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.8))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 40))

    def _fetch(self, url: str) -> str:
        ua = self.config.get("user_agent", "Mozilla/5.0 (compatible; poc-bocm-alcobendas/1.0)")
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "es-ES,es;q=0.9",
            "Connection": "close",
        }
        last_err: Exception | None = None
        for attempt in range(5):
            time.sleep(self.delay_s + attempt * 0.5)
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    return raw.decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 403 and attempt < 4:
                    continue
                raise
            except urllib.error.URLError as e:
                last_err = e
                if attempt < 4:
                    continue
                raise
        if last_err:
            raise last_err
        raise RuntimeError(f"fetch failed: {url}")

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(BASE, href)

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

    def _parse_accordion_sections(self, html: str, page_url: str, default_tipo: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        triggers = re.findall(
            r'data-target="(#ps-id-\d+)"[^>]*>.*?<div class="titulo">([^<]+)</div>',
            html,
            re.S | re.I,
        )
        for target, raw_titulo in triggers:
            sid = target.lstrip("#")
            m = re.search(
                rf'id="{re.escape(sid)}"[^>]*>(.*?)(?=<div class="title_container"|$)',
                html,
                re.S | re.I,
            )
            body = m.group(1) if m else ""
            titulo = _clean_title(raw_titulo)
            pdfs = [
                self._abs_url(p)
                for p in re.findall(r'href="(/sites/default/files/[^"]+\.pdf)"', body, re.I)
            ]
            expte = _parse_expte(titulo)
            fecha = _parse_fecha_dmy_slash(titulo) or _iso_from_year(titulo)
            if pdfs:
                fecha = fecha or _fecha_from_pdf_url(pdfs[0])
            key = expte or pdfs[0] if pdfs else f"{page_url}#{sid}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": "Alcobendas",
                "titulo": titulo,
                "fecha": fecha,
                "tipo": default_tipo,
                "url": page_url,
                "source": "ayuntamiento",
                "origen": page_url,
            }
            if expte:
                rec["expte"] = expte
            if pdfs:
                rec["pdf_url"] = pdfs[0]
                if len(pdfs) > 1:
                    rec["pdf_urls"] = pdfs[:30]
            rows.append(rec)
        return rows

    def _parse_tablon_edictos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_EDICTOS)
        except (urllib.error.HTTPError, urllib.error.URLError):
            return []

        rows: list[dict[str, Any]] = []
        for m in re.finditer(
            r'<div class="views-row">(.*?)(?=<div class="views-row">|</div>\s*</div>\s*</div>\s*</div>)',
            html,
            re.S,
        ):
            block = m.group(1)
            if "field--name-name" not in block:
                continue
            name_m = re.search(r"field--name-name.*?field__item\">([^<]+)", block, re.S)
            if not name_m:
                continue
            titulo = _clean_title(name_m.group(1))
            pdf_m = re.search(r'href="(/sites/default/files/[^"]+\.pdf)"', block, re.I)
            fecha_m = re.search(r"Fecha inicio:\s*([0-9-]+)", block)
            fecha = _parse_fecha_dmy_dash(fecha_m.group(1)) if fecha_m else None
            pdf_url = self._abs_url(pdf_m.group(1)) if pdf_m else TABLON_EDICTOS
            if fecha_m and not fecha:
                fecha = _parse_fecha_dmy_dash(fecha_m.group(0))
            expte = _parse_expte(titulo)
            key = expte or pdf_url or titulo
            rows.append(
                {
                    "id": _stable_id("proy", f"tablon:{key}"),
                    "municipio": "Alcobendas",
                    "titulo": titulo,
                    "fecha": fecha or _fecha_from_pdf_url(pdf_url),
                    "tipo": "edicto",
                    "url": TABLON_EDICTOS,
                    "source": "ayuntamiento",
                    "origen": "tablon_edictos",
                    "expte": expte,
                    "pdf_url": pdf_url if pdf_m else None,
                }
            )
        return rows

    def _collect_acuerdos_y_convenios(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, tipo in (
            (ACUERDOS_IP, "información pública"),
            (CONVENIOS_URB, "convenio urbanístico"),
        ):
            try:
                html = self._fetch(url)
            except (urllib.error.HTTPError, urllib.error.URLError):
                continue
            rows.extend(self._parse_accordion_sections(html, url, tipo))
        return rows

    def _crawl_seed_pdfs(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue = list(self.seed_pages)
        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        while queue and len(visited) < self.max_crawl_pages:
            url = queue.pop(0).rstrip("/")
            if url in visited:
                continue
            visited.add(url)
            try:
                html = self._fetch(url)
            except (urllib.error.HTTPError, urllib.error.URLError):
                continue

            page_name = url.rsplit("/", 1)[-1] or "urbanismo"
            for href, label in re.findall(
                r'<a href="(/sites/default/files/[^"]+\.pdf)"[^>]*>([^<]*)</a>',
                html,
                re.I,
            ):
                pdf = self._abs_url(href)
                blob = f"{_clean_title(label)} {pdf} {page_name}"
                if not RE_PROYECTO.search(blob) and "pgou" not in url.lower():
                    continue
                titulo = _clean_title(label) or Path(pdf).name
                if len(titulo) < 4:
                    titulo = f"{page_name}: {Path(pdf).name}"
                rec_id = _stable_id("proy", pdf)
                if rec_id in seen_ids:
                    continue
                seen_ids.add(rec_id)
                rows.append(
                    {
                        "id": rec_id,
                        "municipio": "Alcobendas",
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_pdf_url(pdf),
                        "tipo": "documento urbanismo",
                        "url": url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": url,
                    }
                )

            if len(visited) < self.max_crawl_pages:
                for link in re.findall(r'href="(/es/temas/ciudad-sostenible/urbanismo/[^"#?]+)"', html):
                    full = self._abs_url(link).rstrip("/")
                    if full not in visited and full not in queue:
                        queue.append(full)

        return rows

    def _tablon_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        titulo = str(rec.get("titulo") or "")
        if not RE_LICENCIA.search(titulo) and "edicto" not in titulo.lower():
            return None
        expte = rec.get("expte") or _parse_expte(titulo)
        return {
            "id": _stable_id("lic", expte or rec.get("pdf_url") or titulo),
            "fecha_concesion": rec.get("fecha"),
            "tipo": "licencia/edicto",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "expte": expte,
            "url": rec.get("url") or TABLON_EDICTOS,
            "source": "ayuntamiento",
            "pdf_url": rec.get("pdf_url"),
        }

    def _merge_proyecto_rows(self, *groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for group in groups:
            for rec in group:
                rid = rec["id"]
                if rid not in seen:
                    seen.add(rid)
                    out.append(rec)
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for rec in self._parse_tablon_edictos():
            lic = self._tablon_to_licencia(rec)
            if lic:
                rows.append(lic)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tablon_edictos"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._parse_tablon_edictos():
            lic = self._tablon_to_licencia(rec)
            if not lic:
                continue
            if lic["id"] not in existing:
                added += 1
            existing[lic["id"]] = lic
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
        tablon = self._parse_tablon_edictos()
        proyectos_tablon = [r for r in tablon if RE_PROYECTO.search(str(r.get("titulo", "")))]
        rows = self._merge_proyecto_rows(
            proyectos_tablon,
            self._collect_acuerdos_y_convenios(),
            self._crawl_seed_pdfs(),
        )
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": len(proyectos_tablon),
            "acuerdos_convenios": sum(
                1 for r in rows if r.get("origen") in (ACUERDOS_IP, CONVENIOS_URB)
            ),
            "seed_crawl": sum(
                1 for r in rows if str(r.get("origen", "")).startswith(f"{BASE}/es/temas/ciudad-sostenible")
            ),
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
