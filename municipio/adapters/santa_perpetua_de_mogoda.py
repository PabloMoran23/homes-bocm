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

WEB_BASE = "https://www.staperpetua.cat"
SEDE_BASE = "https://seu.staperpetua.cat"
MUNICIPIO = "Santa Perpètua de Mogoda"
ID_PREFIX = "santa-perpetua-de-mogoda"
INE_MUN = "08260"

PIU_GEOPORTAL = "https://piu.staperpetua.cat/geoportal/"
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
RPUC_MUNICI = (
    f"https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    f"?reqCode=cerca&municipiSel={INE_MUN}"
)

DEFAULT_LIST_PAGES: tuple[str, ...] = (
    "/ajuntament/normativa/urbanisme/planejament-en-tramit",
    "/ajuntament/normativa/urbanisme/projectes-en-exposicio-publica",
    "/ajuntament/projectes-urbanistics",
    "/ajuntament/normativa/urbanisme/planejament-derivat",
    "/ajuntament/normativa/urbanisme/modificacions-puntuals-o-altres-figures-relatives-al-planejament-general",
)

DEFAULT_LICENCIA_PAGES: tuple[tuple[str, str], ...] = (
    (
        f"{WEB_BASE}/ajuntament/normativa/urbanisme/llicencies-i-comunicacions-dobres",
        "Llicències i comunicacions d'obres (llistat municipal)",
    ),
    (
        f"{WEB_BASE}/serveis-i-tramits/finestreta-unica-empresarial-fue/"
        "informe-urbanistic-associat-a-la-tramitacio-dactivitats-fue.html",
        "Informe urbanístic associat a activitats (FUE)",
    ),
    (
        f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&DETALLE="
        "6269003917446294405033&lang=CA",
        "Catàleg STA — tràmit urbanístic (sede electrònica)",
    ),
    (
        f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_CATSERV2&DETALLE="
        "6269003915230807605033&lang=CA",
        "Comunicació prèvia d'obres — instal·lacions fotovoltaiques (edictes sede)",
    ),
    (
        f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_CATSERV2&DETALLE="
        "6269003915806138005033&lang=CA",
        "Comunicació prèvia d'obres — actuacions urgents (edictes sede)",
    ),
    (
        f"{WEB_BASE}/media/repository/Com_presentar_una_comunicacio_previa_d_obres.pdf",
        "Guia: com presentar una comunicació prèvia d'obres",
    ),
    (MUC_VISOR, f"Visor MUC — cartografia urbanística (municipi {INE_MUN})"),
    (RPUC_MUNICI, f"RPUC — cerca expedients planejament (municipi {INE_MUN})"),
    (PIU_GEOPORTAL, "PIU — geoportal urbanístic municipal"),
)

RE_ARTICLE_ITEM = re.compile(r'<li class="article-item[^"]*">(.*?)</li>', re.I | re.S)
RE_SUBTITLE = re.compile(r'<p class="subtitle">(.*?)</p>', re.I | re.S)
RE_DATE = re.compile(r'<div class="date">\s*([^<]+?)\s*</div>', re.I)
RE_HREF = re.compile(r'<a[^>]+href="([^"]+)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPEDIENTE = re.compile(
    r"(?i)(?:exp(?:edient)?\.?\s*)?(\d{4}/\d{3,5}[A-Za-z]?|\d{4}-\d{4,6}-[A-Z0-9]+/\d{4})"
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó]n responsable|obra|activitat|informe urban)"
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|aprovaci[oó]|modificaci[oó]|exposici[oó]|projecte|"
    r"reparcel|pgm|mpp|pla parcial|junta de compensaci[oó]|informaci[oó] p[uú]blica)"
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_parts(text: str, date_div: str | None) -> str | None:
    d = _parse_fecha_dmy(date_div or "") or _parse_fecha_dmy(text or "")
    if d:
        return d
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1985 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-06-01"
    return None


def _proyecto_tipo(titulo: str) -> str:
    n = (titulo or "").lower()
    if "junta de compensaci" in n:
        return "junta de compensación"
    if "reparcel" in n:
        return "reparcelación"
    if "modificaci" in n and ("pgm" in n or "pgmo" in n or "mpp" in n):
        return "modificación planeamiento"
    if "pla parcial" in n or "mpppu" in n:
        return "plan parcial"
    if "avanç de pla" in n or "avanc de pla" in n:
        return "avance de plan parcial"
    if "aprovaci" in n and "inicial" in n:
        return "aprobación inicial"
    if "aprovaci" in n and ("provisional" in n or "definitiva" in n):
        return "aprobación urbanística"
    if "exposici" in n or "informaci" in n:
        return "información / exposición pública"
    if "projecte" in n or "projecte" in n:
        return "proyecto urbanístico"
    return "planeamiento"


class SantaPerpetuaDeMogodaAyuntamientoAdapter(AyuntamientoAdapter):
    """CMS staperpetua.cat (article-item urbanisme) + sede STA (referencia) + PIU/MUC/RPUC."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.ua = str(self.config.get("user_agent", "poc-bocm-santa-perpetua-de-mogoda/1.0"))
        self.list_pages = tuple(
            str(p) if str(p).startswith("http") else f"{self.web_base}{p}"
            for p in (self.config.get("list_pages") or DEFAULT_LIST_PAGES)
        )
        self.licencia_pages = tuple(
            (str(u), str(label)) for u, label in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        )
        self.fetch_timeout = float(self.config.get("fetch_timeout_s", 75))

    def _fetch(self, url: str) -> str | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        try:
            with urllib.request.urlopen(req, timeout=self.fetch_timeout) as resp:
                return resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError, ValueError):
            return None

    def _abs_url(self, href: str, base: str) -> str:
        href = unescape(href.split("#")[0])
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin(base, href)

    def _parse_article_list(self, page_url: str, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for block in RE_ARTICLE_ITEM.findall(html):
            sm = RE_SUBTITLE.search(block)
            if not sm:
                continue
            titulo = _strip_html(sm.group(1))
            if len(titulo) < 8:
                continue
            dm = RE_DATE.search(block)
            date_raw = dm.group(1).strip() if dm else None
            hm = RE_HREF.search(block)
            item_url = self._abs_url(hm.group(1), page_url) if hm else page_url
            fecha = _fecha_from_parts(titulo, date_raw)
            exp_m = RE_EXPEDIENTE.search(titulo)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": item_url,
                    "list_page": page_url,
                    "expediente": exp_m.group(1) if exp_m else None,
                }
            )
        return rows

    def _static_proyecto_refs(self) -> list[dict[str, Any]]:
        refs = [
            (f"{self.web_base}/ajuntament/normativa/urbanisme", "Normativa i planejament urbanístic"),
            (PIU_GEOPORTAL, "PIU — consulta parcel·la a parcel·la"),
            (RPUC_MUNICI, f"RPUC expedients planejament (INE {INE_MUN})"),
            (MUC_VISOR, f"Visor MUC Catalunya (municipi {INE_MUN})"),
        ]
        out: list[dict[str, Any]] = []
        for url, titulo in refs:
            out.append(
                {
                    "titulo": titulo,
                    "fecha": None,
                    "url": url,
                    "list_page": "referencia",
                    "expediente": None,
                }
            )
        return out

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        raw: list[dict[str, Any]] = []
        for page_url in self.list_pages:
            html = self._fetch(page_url)
            if html:
                raw.extend(self._parse_article_list(page_url, html))
        raw.extend(self._static_proyecto_refs())

        activitats_url = f"{self.web_base}/ajuntament/normativa/urbanisme/exposicio-publica-activitats"
        act_html = self._fetch(activitats_url)
        if act_html:
            for row in self._parse_article_list(activitats_url, act_html):
                if RE_PROYECTO.search(row["titulo"]) or RE_LICENCIA.search(row["titulo"]):
                    raw.append(row)

        for row in raw:
            titulo = row["titulo"]
            if row.get("list_page") != "referencia" and not RE_PROYECTO.search(titulo):
                continue
            url = row["url"]
            key = f"{url}|{titulo[:120]}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": row.get("fecha"),
                "tipo": _proyecto_tipo(titulo),
                "url": url,
                "source": "ayuntamiento",
                "origen": (
                    "referencia_portal"
                    if row.get("list_page") == "referencia"
                    else row.get("list_page")
                ),
            }
            if row.get("expediente"):
                rec["expediente"] = row["expediente"]
            by_id[rec["id"]] = rec
        return list(by_id.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for url, label in self.licencia_pages:
            rec = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": label[:250],
                "distrito": MUNICIPIO,
                "lat": None,
                "lon": None,
                "url": url,
                "source": "ayuntamiento",
                "origen": "guia_portal_obres",
            }
            by_id[rec["id"]] = rec

        activitats_url = f"{self.web_base}/ajuntament/normativa/urbanisme/exposicio-publica-activitats"
        act_html = self._fetch(activitats_url)
        if act_html:
            for row in self._parse_article_list(activitats_url, act_html):
                titulo = row["titulo"]
                if not RE_LICENCIA.search(titulo):
                    continue
                url = row["url"]
                rec = {
                    "id": _stable_id("lic", f"{url}|{titulo[:80]}"),
                    "fecha_concesion": row.get("fecha"),
                    "tipo": titulo[:250],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "exposicio_publica_activitats",
                }
                by_id[rec["id"]] = rec

        urbanisme_html = self._fetch(f"{self.web_base}/temes/urbanisme-i-habitatge")
        if urbanisme_html:
            for href in RE_HREF.findall(urbanisme_html):
                if "PTS_CATSERV" not in href and "CATALOGO" not in href:
                    continue
                u = self._abs_url(href.replace("&amp;", "&"), f"{self.web_base}/")
                if u in {r["url"] for r in by_id.values()}:
                    continue
                titulo = "Tràmit / edicte sede STA (enllaç des de web urbanisme)"
                rec = {
                    "id": _stable_id("lic", u),
                    "fecha_concesion": None,
                    "tipo": titulo,
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": u,
                    "source": "ayuntamiento",
                    "origen": "edicte_sede_web",
                }
                by_id[rec["id"]] = rec

        return list(by_id.values())

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "mode": "backfill", "fetched_at": datetime.now(timezone.utc).isoformat()}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        meta = self.backfill_proyectos(out_jsonl)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"updated_at": meta["fetched_at"], "count": meta["rows"]}), encoding="utf-8")
        meta["mode"] = "update"
        return meta

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "mode": "backfill", "fetched_at": datetime.now(timezone.utc).isoformat()}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        meta = self.backfill_licencias(out_jsonl)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"updated_at": meta["fetched_at"], "count": meta["rows"]}), encoding="utf-8")
        meta["mode"] = "update"
        return meta
