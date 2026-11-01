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

BASE = "https://ourense.gal"
URBANISMO_URL = f"{BASE}/gl/servizos/urbanismo-licencias-y-vivienda"
SEDE_BASE = "https://sede.ourense.gob.es"
MUNICIPIO = "Ourense"
ID_PREFIX = "ou"
INE = "32054"

SIOTUGA_URB = "https://siotuga.xunta.gal/siotuga/urb?lang=es_ES"

# Publicaciones de planeamiento enlazadas desde la web (sede inaccesible desde algunos entornos).
FIXED_PLANEAMIENTO: list[dict[str, str]] = [
    {
        "titulo": "Estudo de Detalle — reordenación volumes Rúa Santo Domingo e Av. Buenos Aires",
        "url": f"{SEDE_BASE}/public/publications/list/municipalregulations/ORDE/details/69085873",
        "tipo": "estudio de detalle",
    },
    {
        "titulo": "Plan Especial de Reforma Interior do Núcleo Histórico de Ourense",
        "url": f"{SEDE_BASE}/public/publications/list/municipalregulations/ORDE/details/56129239",
        "tipo": "plan especial",
    },
    {
        "titulo": "Modificación puntual do PEPRI da Zona histórica de Ourense",
        "url": f"{SEDE_BASE}/public/publications/list/municipalregulations/ORDE/details/52142389",
        "tipo": "modificación planeamiento",
    },
    {
        "titulo": "Plan Especial de Protección — núcleo etnográfico de Seixalbo",
        "url": f"{SEDE_BASE}/public/publications/list/municipalregulations/ORDE/details/69098794",
        "tipo": "plan especial",
    },
    {
        "titulo": "Modificación puntual normativa PXOM Ourense 1986",
        "url": f"{SEDE_BASE}/public/publications/list/municipalregulations/ORDE/details/50040656",
        "tipo": "modificación PXOM",
    },
    {
        "titulo": "Planos de situación segundo PXOM 86 (A4)",
        "url": f"{SEDE_BASE}/public/publications/list/municipalregulations/ORDE/details/69103977",
        "tipo": "PXOM",
    },
    {
        "titulo": "PXOU de 16 de setembro de 1986",
        "url": f"{SEDE_BASE}/public/publications/list/municipalregulations/ORDE/details/50040533",
        "tipo": "PXOM",
    },
]

URBAN_NEWS_SEEDS: list[str] = [
    f"{BASE}/gl/actualidad/o-concello-remite-a-xunta-a-cumprimentacion-do-informe-previo-a-aprobacion-definitiva-do-plan-de-urbanismo-pxom",
    f"{BASE}/gl/actualidad/o-concello-aproba-a-modificacion-do-contrato-co-equipo-redactor-para-adaptar-o-pxom-ao-informe-da-xunta-de-galicia",
    f"{BASE}/gl/actualidad/o-concello-propon-transformar-a-antiga-prision-e-a-casa-de-banos-nun-parador-nacional-de-turismo",
]

LICENCIA_TRAMITES: list[tuple[str, str]] = [
    (
        "Guía informativa licencias urbanísticas",
        "https://www.ourense.gal/media/filer_public/cf/ca/cfca477d-e3fc-4add-8540-52d7a6dcc407/galego_guia_informativa_licencias_urbanisticas.pdf",
    ),
    (
        "Guía informativa licencias de actividade",
        "https://www.ourense.gal/media/filer_public/b4/24/b424e2e3-7fb7-40a0-a5d6-59d6009d7793/galego_guia_informativa_licencias_actividad.pdf",
    ),
    (
        "Fichas técnicas da edificación (sede)",
        f"{SEDE_BASE}/public/publications/list/forms/FORMS/details/50046014",
    ),
    (
        "Ordenanza deber de conservación e ITE",
        f"{SEDE_BASE}/public/publications/list/municipalregulations/ORDE/details/50040741",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(licen|gu[ií]a informativa|ficha[s]? t[eé]cnic|ordenanza.*ite|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|pxom|pxou|pepri|plan especial|estudo de detalle|"
    r"modificaci[oó]n|convenio|anuncio|expedient|expte|taboleiro|informaci[oó]n p[uú]blica|"
    r"parador|prisi[oó]n|ite listado|normativa)",
)
RE_ITE_ONLY = re.compile(
    r"(?i)^ite\s*20\d{2}\.\s*listado de edificios",
)
RE_EXPEDIENTE = re.compile(r"(?i)(?:expte\.?|expediente)\s*[.\s]*(\d{10,})")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_NEWS = re.compile(
    r"(?i)(\d{1,2})\s+(?:Xan|Feb|Mar|Abr|Mai|Xu[nñ]|Xul|Ago|Set|Out|Nov|Dec|"
    r"Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic),?\s*(\d{4})",
)
RE_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_UPLOAD_DATE = re.compile(r"/media/uploads/(\d{4})/(\d{2})/(\d{2})/")


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_UPLOAD_DATE.search(url or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _proyecto_tipo(titulo: str) -> str:
    n = titulo.lower()
    if "pxom" in n or "pxou" in n:
        return "PXOM"
    if "pepri" in n or "plan especial" in n:
        return "plan especial"
    if "estudo de detalle" in n:
        return "estudio de detalle"
    if "convenio" in n:
        return "convenio urbanístico"
    if "anuncio" in n or "decreto" in n:
        return "anuncio expediente"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "parador" in n or "prisi" in n:
        return "actuación urbanística"
    return "urbanismo"


class OurenseAyuntamientoAdapter(AyuntamientoAdapter):
    """Web ourense.gal (CMS propio) + sede.ourense.gob.es (publicaciones ORDE; sede a veces inaccesible)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._sede_timeout = float(self.config.get("sede_timeout_s", 20))

    def _fetch(self, url: str, *, use_sede_ssl: bool = False, timeout: float = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-ourense/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(self.web_base + "/", href))

    def _try_sede_fetch(self, url: str) -> str | None:
        try:
            return self._fetch(url, use_sede_ssl=True, timeout=self._sede_timeout)
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    def _collect_urb_page_rows(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        html = self._fetch(self.urbanismo_url)
        proyectos: list[dict[str, Any]] = []
        licencias: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_proy(title: str, url: str, origen: str, fecha: str | None = None) -> None:
            if not title or url in seen:
                return
            if RE_ITE_ONLY.search(title):
                return
            if not RE_PROYECTO.search(title) and not RE_PROYECTO.search(url):
                return
            seen.add(url)
            proyectos.append(
                {
                    "titulo": title[:500],
                    "url": url,
                    "fecha": fecha or _fecha_from_url(url),
                    "tipo": _proyecto_tipo(title),
                    "origen": origen,
                }
            )

        def add_lic(title: str, url: str, origen: str) -> None:
            if url in seen:
                return
            if not RE_LICENCIA.search(title):
                return
            seen.add(url)
            licencias.append(
                {
                    "titulo": title[:500],
                    "url": url,
                    "fecha": _fecha_from_url(url),
                    "tipo": "licencia / trámite",
                    "origen": origen,
                }
            )

        for m in RE_LINK.finditer(html):
            href, raw_title = m.group(1), _strip_html(m.group(2))
            if not raw_title or raw_title.startswith("#"):
                continue
            url = self._abs_url(href) if not href.startswith("http") else href
            if "ourense" not in url and "sede.ourense" not in url:
                continue
            add_lic(raw_title, url, "urbanismo_hub")
            add_proy(raw_title, url, "urbanismo_hub")

        for pdf in RE_PDF.findall(html):
            url = self._abs_url(pdf) if not pdf.startswith("http") else pdf
            name = unescape(urllib.parse.unquote(url.split("/")[-1]))
            add_proy(name.replace("_", " "), url, "urbanismo_pdf")

        return proyectos, licencias

    def _collect_news(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in URBAN_NEWS_SEEDS:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            h1 = _strip_html(RE_H1.search(html).group(1)) if RE_H1.search(html) else ""
            if not h1:
                continue
            fecha = _parse_fecha_dmy(html)
            rows.append(
                {
                    "titulo": h1[:500],
                    "url": url,
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(h1),
                    "origen": "noticia",
                }
            )
        return rows

    def _fixed_rows(self) -> list[dict[str, Any]]:
        rows = [
            {
                "titulo": f"SIOTUGA — inventario planeamento Ourense (INE {INE})",
                "url": SIOTUGA_URB,
                "fecha": None,
                "tipo": "inventario planeamiento",
                "origen": "siotuga",
            },
        ]
        for item in FIXED_PLANEAMIENTO:
            rows.append({**item, "origen": "sede_ORDE_seed"})
        return rows

    def _collect_sede_board(self) -> list[dict[str, Any]]:
        html = self._try_sede_fetch(f"{self.sede_base}/board")
        if not html:
            return []
        rows: list[dict[str, Any]] = []
        for m in re.finditer(
            r'href="(https://sede\.ourense\.gob\.es/preview-document/[^"]+)"',
            html,
            re.I,
        ):
            rows.append(
                {
                    "titulo": "Documento tablón de anuncios (sede)",
                    "url": m.group(1),
                    "fecha": None,
                    "tipo": "anuncio",
                    "origen": "sede_board",
                }
            )
        return rows

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.web_base
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url + titulo),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        ex = RE_EXPEDIENTE.search(titulo)
        if ex:
            rec["expediente"] = ex.group(1)
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.web_base
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._fixed_rows():
            add(self._to_proyecto(item))
        for item in self._collect_news():
            add(self._to_proyecto(item))
        proys, _ = self._collect_urb_page_rows()
        for item in proys:
            add(self._to_proyecto(item))
        for item in self._collect_sede_board():
            add(self._to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "fixed": sum(1 for r in rows if str(r.get("origen", "")).startswith(("siotuga", "sede_"))),
            "news": sum(1 for r in rows if r.get("origen") == "noticia"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        _, lics = self._collect_urb_page_rows()
        for title, url in LICENCIA_TRAMITES:
            lics.append(
                {
                    "titulo": title,
                    "url": url,
                    "fecha": _fecha_from_url(url),
                    "tipo": "trámite informativo",
                    "origen": "seed",
                }
            )
        for item in lics:
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

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
