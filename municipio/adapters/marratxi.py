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

WP_BASE = "https://www.marratxi.es"
INFO_BASE = "https://info.marratxi.es"
MUNICIPIO = "Marratxí"
ID_PREFIX = "marratxi"

NORMATIVA_URL = f"{WP_BASE}/normativa-municipal/"
URBANISME_URL = f"{WP_BASE}/urbanisme/"
IEE_URL = f"{WP_BASE}/iee/"
INFO_URBANISME_URL = f"{INFO_BASE}/urbanisme/"
NORMES_SUBSIDIARIES_URL = "http://boib.caib.es/pdf/1999154/mp16748.pdf"

DEFAULT_SEED_PAGES: list[str] = [
    NORMATIVA_URL,
    URBANISME_URL,
    IEE_URL,
    f"{WP_BASE}/bonificacio-de-libi/",
    f"{WP_BASE}/oficina-dassessorament-a-lhabitatge/",
]

DEFAULT_LICENCIA_PAGES: list[dict[str, str]] = [
    {
        "url": f"{WP_BASE}/wp-content/uploads/2026/07/OBRA-MENOR.pdf",
        "tipo": "licencia obra menor",
        "titulo": "Sol·licitud llicència d'obra menor — model municipal",
    },
    {
        "url": f"{WP_BASE}/wp-content/uploads/2024/10/OBRA-MAJOR.pdf",
        "tipo": "licencia obra mayor",
        "titulo": "Sol·licitud llicència d'obra major — model municipal",
    },
    {
        "url": f"{WP_BASE}/wp-content/uploads/2023/08/FINAL-DOBRA.pdf",
        "tipo": "licencia primera ocupación",
        "titulo": "Llicència primera ocupació / final d'obra — model municipal",
    },
    {
        "url": INFO_URBANISME_URL,
        "tipo": "trámites urbanismo",
        "titulo": "Preguntes freqüents urbanisme — portal d'ajuda",
    },
    {
        "url": IEE_URL,
        "tipo": "informe evaluación edificios",
        "titulo": "Informe d'avaluació d'edificis (IEE) — àrea d'urbanisme",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia).*(?:obra|urban|activitat|ocupaci[oó]n)|"
    r"obra (?:menor|major)|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"primera ocupaci[oó]n|final d.obra|cedula urban|tasa.*llicen|"
    r"informe d.avaluaci[oó].*edifici|instància.*edifici",
)
RE_PROYECTO = re.compile(
    r"(?i)(exposici[oóò].*p[uú]blic|informaci[oóò].*p[uú]blic|planejament|planeamiento|"
    r"normativa urban|normes subsidi|cedula urban|c[eè]dula urban|pgou|"
    r"projecte.*(?:urban|substituci|actuaci|skatepark|aparcament|via verda)|"
    r"parc fotovoltaic|edicte.*aprovaci|certificat.*acord|boib.*ordenan|"
    r"modificaci[oó].*reglament|rehabilitaci[oó].*edifici|unitat d.actuaci)",
)
RE_WP_TITLE_PROY = re.compile(
    r"(?i)(exposici[oóò].*p[uú]blic|skatepark|via verda|parc fotovoltaic|"
    r"llic[eè]ncies urban|aparcament.*pol[ií]gon|obres d.ombreig.*plaça)",
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?marratxi\.es)?/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_LINK_ANCHOR = re.compile(
    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.I | re.S,
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
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"/(\d{4})/(\d{2})/", text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    return date_str[:10]


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "exposici" in n and "p" in n and "blic" in n:
        return "información pública"
    if "normes subsidi" in n or "normativa urban" in n:
        return "normas subsidiarias"
    if "cedula" in n or "cèdula" in n:
        return "cédula urbanística"
    if "edicte" in n or "certificat" in n:
        return "aprobación normativa"
    if "skatepark" in n:
        return "actuación urbanística"
    if "via verda" in n or "aparcament" in n:
        return "obra pública"
    if "parc fotovoltaic" in n:
        return "instalación energética"
    if "llic" in n and "urban" in n:
        return "licencias urbanísticas"
    return "urbanismo"


def _licencia_tipo(title: str) -> str:
    n = title.lower()
    if "obra menor" in n:
        return "licencia obra menor"
    if "obra major" in n or "obra mayor" in n:
        return "licencia obra mayor"
    if "primera ocupaci" in n or "final d" in n and "obra" in n:
        return "licencia primera ocupación"
    if "informe" in n and "edifici" in n:
        return "informe evaluación edificios"
    if "infracci" in n:
        return "infracción urbanística"
    if "llic" in n and "urban" in n:
        return "licencia urbanística"
    return "trámite urbanismo"


class MarratxiAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Avada (marratxi.es) + portal d'ajuda + normativa municipal (PDFs). Sede espublico indeterminada."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.info_base = str(self.config.get("info_base") or INFO_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pages = [
            dict(x) for x in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        ]
        self.wp_max_pages = int(self.config.get("wp_max_pages", 35))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-marratxi/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(f"{base or self.wp_base}/", href)

    def _collect_normativa_links(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(NORMATIVA_URL)
        except urllib.error.URLError:
            return rows
        for m in RE_LINK_ANCHOR.finditer(html):
            href = self._abs_url(m.group(1))
            text = _strip_html(m.group(2))
            blob = f"{text} {href}"
            if href in seen or href.startswith("#"):
                continue
            if not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                continue
            seen.add(href)
            rows.append(
                {
                    "titulo": text[:500] or Path(urllib.parse.urlparse(href).path).name,
                    "fecha": _fecha_from_blob(href + " " + text),
                    "url": href if href.lower().endswith(".pdf") else NORMATIVA_URL,
                    "pdf_url": href if href.lower().endswith(".pdf") else None,
                    "origen": "normativa_municipal",
                    "kind": "licencia" if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) else "proyecto",
                }
            )
        rows.append(
            {
                "titulo": "Normes subsidiàries de Marratxí (BOIB)",
                "fecha": "1999-01-01",
                "url": NORMES_SUBSIDIARIES_URL,
                "pdf_url": NORMES_SUBSIDIARIES_URL,
                "origen": "boib",
                "kind": "proyecto",
            }
        )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for page in range(1, self.wp_max_pages + 1):
            url = (
                f"{self.wp_base}/wp-json/wp/v2/posts"
                f"?per_page=100&page={page}&_fields=id,date,link,title,excerpt"
            )
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(data, list) or not data:
                break
            for post in data:
                pid = int(post.get("id") or 0)
                if pid in seen:
                    continue
                seen.add(pid)
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                excerpt = _strip_html(post.get("excerpt", {}).get("rendered", ""))
                blob = f"{title} {excerpt}"
                if not RE_WP_TITLE_PROY.search(blob):
                    continue
                kind = "licencia" if re.search(r"(?i)llic[eè]ncies urban", blob) else "proyecto"
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _iso_date_wp(post.get("date") or ""),
                        "url": post.get("link") or "",
                        "pdf_url": None,
                        "origen": "wp_noticia",
                        "kind": kind,
                    }
                )
            if len(data) < 100:
                break
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_url(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                ctx_start = max(0, m.start() - 400)
                ctx = _strip_html(html[ctx_start : m.start() + 120])
                blob = f"{name} {ctx}"
                if not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": (ctx[-120:] or name)[:500],
                        "fecha": _fecha_from_blob(pdf + " " + ctx),
                        "url": page_url,
                        "pdf_url": pdf,
                        "origen": "web_seed",
                        "kind": "licencia" if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) else "proyecto",
                    }
                )
        return rows

    def _to_licencia(self, item: dict[str, Any]) -> dict[str, Any]:
        titulo = item["titulo"]
        url = item.get("pdf_url") or item.get("url") or ""
        return {
            "id": _stable_id("lic", url or titulo),
            "fecha_concesion": item.get("fecha"),
            "tipo": _licencia_tipo(titulo),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": url,
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _to_proyecto(self, item: dict[str, Any]) -> dict[str, Any]:
        titulo = item["titulo"]
        url = item.get("url") or item.get("pdf_url") or ""
        return {
            "id": _stable_id("proy", url or titulo),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

    def _collect_proyecto_info_pages(self) -> list[dict[str, Any]]:
        seeds = [
            (URBANISME_URL, "Àrea d'Urbanisme i Habitatge — web municipal"),
            (NORMATIVA_URL, "Normativa municipal — secció urbanisme"),
            (INFO_URBANISME_URL, "Urbanisme — portal d'ajuda ciutadana"),
        ]
        return [
            {
                "titulo": titulo,
                "fecha": None,
                "url": url,
                "pdf_url": None,
                "origen": "web_portal",
                "kind": "proyecto",
            }
            for url, titulo in seeds
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

        def add(item: dict[str, Any]) -> None:
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self.licencia_pages:
            add(
                {
                    "titulo": item["titulo"],
                    "fecha": None,
                    "url": item["url"],
                    "pdf_url": item["url"] if item["url"].lower().endswith(".pdf") else None,
                    "origen": "tramite_informativo",
                }
            )
        for item in self._collect_normativa_links():
            if item.get("kind") == "licencia":
                add(item)
        for item in self._collect_seed_pages():
            if item.get("kind") == "licencia":
                add(item)
        for item in self._collect_wp_posts():
            if item.get("kind") == "licencia":
                add(item)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": sum(1 for r in rows if r.get("origen") in ("tramite_informativo", "web_portal")),
            "normativa": sum(1 for r in rows if r.get("origen") == "normativa_municipal"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(item: dict[str, Any]) -> None:
            rec = self._to_proyecto(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_proyecto_info_pages():
            add(item)
        for item in self._collect_normativa_links():
            if item.get("kind") == "proyecto":
                add(item)
        for item in self._collect_seed_pages():
            if item.get("kind") == "proyecto":
                add(item)
        for item in self._collect_wp_posts():
            if item.get("kind") == "proyecto":
                add(item)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "normativa": sum(1 for r in rows if r.get("origen") == "normativa_municipal"),
            "noticias": sum(1 for r in rows if r.get("origen") == "wp_noticia"),
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
