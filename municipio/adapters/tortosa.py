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

WEB_BASE = "https://www2.tortosa.cat"
URBANISME_INDEX = f"{WEB_BASE}/urbanisme/index.php"
TRAMITS_INDEX = f"{WEB_BASE}/tramits/"
SEU_E = "https://seu-e.cat/es/web/tortosa"
MUC_VISOR = "https://dtes.gencat.cat/muc-visor/AppJava/home.do?municipi=43155&set-locale=ca"
MUNICIPIO = "Tortosa"
ID_PREFIX = "tortosa"

RE_SLUG = re.compile(r"\?slug=([a-z0-9-]+)", re.I)
RE_TITLE_PARENT = re.compile(r"id=['\"]title_page_parent['\"]>([^<]+)", re.I)
RE_TITLE_PAGE = re.compile(r"id=['\"]title_page['\"]>([^<]+)", re.I)
RE_ELEMENT_BLOCK = re.compile(
    r"class=['\"]element_container['\"][^>]*>(.*?)(?=class=['\"]element_container['\"]|<!-- FOOTER|$)",
    re.I | re.S,
)
RE_TITLE_ELEMENT = re.compile(r"class=['\"]title_element['\"]>([^<]+)", re.I)
RE_PDF_LINK = re.compile(
    r"<a href=['\"]([^'\"]+\.pdf[^'\"]*)['\"][^>]*>([^<]*)",
    re.I,
)
RE_TRAMIT_URBAN = re.compile(
    r"(?i)(llic[eè]ncia.*obra|obra (?:major|menor|civil)|autoliquidaci[oó].*obr|"
    r"parcel|planejament|urban|compatibilitat urban|aprofitament urban|"
    r"comunicaci[oó].*obr|primera ocupaci|urbanitzaci[oó]|certificat.*(?:obra|habitabilitat|innecessarietat))",
)
RE_TRAMIT_EXCLUDE = re.compile(
    r"(?i)(empadronament|veinatge|gos|aigua|cadastr|assist[eè]ncia|inscripci[oó]|"
    r"compte bancari|creditors)",
)
RE_URBANISME_H3 = re.compile(
    r'<h3[^>]*>\s*Urbanisme\s*</h3>',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_TRAMIT_LINK = re.compile(
    r'<a href="/tramits\?codi=(\d+)"[^>]*>\s*<li class="listElement">\s*([^<]+?)\s*</li>',
    re.I | re.S,
)


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


def _proyecto_tipo(parent: str, page: str, title: str) -> str:
    blob = f"{parent} {page} {title}".lower()
    if "modificaci" in blob and "puntual" in blob:
        return "modificación puntual POUM"
    if "pla parcial" in blob or "plan parcial" in blob:
        return "plan parcial"
    if "pla especial" in blob or "plan especial" in blob:
        return "plan especial"
    if "pla de millora" in blob or "plan de mejora" in blob:
        return "plan de mejora"
    if "projecte d'urbanitzaci" in blob or "projecte d'urbanització" in blob:
        return "proyecto de urbanización"
    if "conveni" in blob:
        return "convenio urbanístico"
    if "reparcel" in blob:
        return "reparcelación"
    if "poum" in blob or "ordenació urbanística" in blob or "ordenacion urbanistica" in blob:
        return "POUM"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "aprovaci" in blob:
        return "aprobación planeamiento"
    return "planeamiento"


class TortosaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web municipal www2.tortosa.cat (urbanisme per slug) + tràmits informatius + seu-e."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.urbanisme_index = str(self.config.get("urbanisme_index") or URBANISME_INDEX)
        self.tramits_index = str(self.config.get("tramits_index") or TRAMITS_INDEX)
        self.muc_visor = str(self.config.get("muc_visor") or MUC_VISOR)

    def _fetch(self, url: str, *, timeout: int = 90) -> str | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-tortosa/1.0")},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    def _urbanisme_slugs(self) -> list[str]:
        html = self._fetch(self.urbanisme_index)
        if not html:
            return []
        return sorted(set(RE_SLUG.findall(html)))

    def _parse_slug_page(self, slug: str) -> list[dict[str, Any]]:
        url = f"{WEB_BASE}/urbanisme/?slug={urllib.parse.quote(slug)}"
        html = self._fetch(url)
        if not html:
            return []

        parent_m = RE_TITLE_PARENT.search(html)
        page_m = RE_TITLE_PAGE.search(html)
        parent = _strip_html(parent_m.group(1)) if parent_m else ""
        page_title = _strip_html(page_m.group(1)) if page_m else slug.replace("-", " ").title()

        rows: list[dict[str, Any]] = []
        blocks = list(RE_ELEMENT_BLOCK.finditer(html))
        if not blocks:
            rows.append(
                self._proyecto_row(
                    slug=slug,
                    parent=parent,
                    page_title=page_title,
                    milestone=page_title,
                    fecha=None,
                    url=url,
                    pdf_url=None,
                )
            )
            return rows

        for block_m in blocks:
            block = block_m.group(1)
            te = RE_TITLE_ELEMENT.search(block)
            if not te:
                continue
            milestone = _strip_html(te.group(1))
            fecha = _parse_fecha_dmy(milestone)
            pdfs = RE_PDF_LINK.findall(block)
            pdf_url = pdfs[0][0] if pdfs else None
            if pdf_url and pdf_url.startswith("/"):
                pdf_url = urllib.parse.urljoin(f"{WEB_BASE}/", pdf_url)
            rows.append(
                self._proyecto_row(
                    slug=slug,
                    parent=parent,
                    page_title=page_title,
                    milestone=milestone,
                    fecha=fecha,
                    url=pdf_url or url,
                    pdf_url=pdf_url,
                )
            )
        return rows

    def _proyecto_row(
        self,
        *,
        slug: str,
        parent: str,
        page_title: str,
        milestone: str,
        fecha: str | None,
        url: str,
        pdf_url: str | None,
    ) -> dict[str, Any]:
        titulo = milestone if len(milestone) > 10 else f"{page_title} — {milestone}"
        if parent and parent.lower() not in titulo.lower():
            titulo = f"{parent}: {titulo}"
        key = f"{slug}|{milestone}|{fecha or ''}|{url}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(parent, page_title, milestone),
            "url": url,
            "source": "ayuntamiento",
            "slug_urbanisme": slug,
            "planeamiento_seccion": page_title[:300],
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        return rec

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for slug in self._urbanisme_slugs():
            for rec in self._parse_slug_page(slug):
                if rec["id"] in seen:
                    continue
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _tramits_urbanisme_chunk(self, html: str) -> str:
        m = RE_URBANISME_H3.search(html)
        if not m:
            return html
        tail = html[m.end() :]
        nxt = re.search(r"<h3[^>]*>", tail, re.I)
        return tail[: nxt.start()] if nxt else tail

    def _collect_licencias_tramits(self) -> list[dict[str, Any]]:
        html = self._fetch(self.tramits_index)
        if not html:
            return []
        chunk = self._tramits_urbanisme_chunk(html)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for codi, title_raw in RE_TRAMIT_LINK.findall(chunk):
            title = _strip_html(title_raw)
            if not title or RE_TRAMIT_EXCLUDE.search(title):
                continue
            if not RE_TRAMIT_URBAN.search(title):
                continue
            url = f"{WEB_BASE}/tramits/?codi={codi}"
            rid = _stable_id("lic", url)
            if rid in seen:
                continue
            seen.add(rid)
            rows.append(
                {
                    "id": rid,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia / urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Tràmit informatiu (www2.tortosa.cat); no concesión publicada en tablón",
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
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

    def _merge_update(
        self, out_jsonl: Path, state_path: Path, rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in rows:
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        merged = list(existing.values())
        self._write_jsonl(out_jsonl, merged)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(merged),
                    "added": added,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"rows": len(merged), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "urbanisme_slug_pages",
            "muc_visor": self.muc_visor,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self._merge_update(out_jsonl, state_path, self._collect_proyectos())
        result["source"] = "urbanisme_slug_pages"
        return result

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_tramits()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramits_informatius"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        result = self._merge_update(out_jsonl, state_path, self._collect_licencias_tramits())
        result["source"] = "tramits_informatius"
        return result
