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

WEB_BASE = "https://www.elmasnou.cat"
MEDIA_BASE = "https://elmasnou.webmunicipal.diba.cat"
SEU_E_BASE = "https://seu-e.cat/ca/web/elmasnou"
MUNICIPIO = "El Masnou"
ID_PREFIX = "el-masnou"
INE_MUN = "08125"
TAULER_URL = "https://tauler.seu.cat/inici.do?idens=811890004"
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
RPUC_PORTAL = (
    f"https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?"
    f"reqCode=cerca&municipiSel={INE_MUN}"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/informacio-oficial/informacio-urbanistica",
    f"{WEB_BASE}/informacio-oficial/informacio-urbanistica/planejament-urbanistic",
    f"{WEB_BASE}/informacio-oficial/informacio-urbanistica/documents-en-exposicio-publica",
    f"{WEB_BASE}/informacio-oficial/anuncis-edictes",
    f"{WEB_BASE}/temes/urbanisme",
    f"{WEB_BASE}/temes/urbanisme/planejament-general",
    f"{WEB_BASE}/temes/urbanisme/planejament-derivat",
    f"{WEB_BASE}/temes/urbanisme/346-planejament-vigent",
    f"{WEB_BASE}/temes/urbanisme/344-documents-en-exposicio-publica",
    f"{WEB_BASE}/guia-del-municipi/geoportal",
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (f"{WEB_BASE}/temes/urbanisme", "Urbanisme i llicències d'obres"),
    (
        f"{SEU_E_BASE}/tramits-i-gestions",
        "Catàleg de tràmits (seu-e.cat)",
    ),
    (TAULER_URL, "e-TAULER — anuncis i edictes"),
    (MUC_VISOR, "Visor MUC — cartografia urbanística (08125)"),
    (
        f"{WEB_BASE}/serveis-i-tramits/tramits-i-gestions/cataleg-de-tramits",
        "Catàleg de tràmits (web municipal)",
    ),
    (
        f"{WEB_BASE}/serveis-i-tramits/tramits-i-gestions/instancia-generica",
        "Instància genèrica",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autoritzaci[oó] d.?obres|obra (?:major|menor)|suspensi[oó].*llic|"
    r"primera ocupaci[oó]|enderroc|retol|grua)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|expedient|exposici[oó]|informaci[oó] p[uú]blica|"
    r"aprovaci[oó]|modificaci[oó]|reparcel|mppgo|pgou|normativa|edicte|projecte|"
    r"rehabilitaci[oó]|facana|mitgera|coberta|esplanada|suspensi[oó])",
)
RE_EXCLUDE = re.compile(
    r"(?i)(subvenci[oó]|oferta p[uú]blica.*personal|convocat[oò]ria.*selecci[oó]|"
    r"pressupost municipal|ordenan[cç]a fiscal|cerim[oò]nia|casament|guia d.acollida|"
    r"organigrama|reactivaci[oó].*covid|normes d.us.*xarxes)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXP_CODE = re.compile(r"\b(X20\d{7,}|20\d{2}/\d{4,})\b", re.I)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_TAULER = re.compile(
    r'href="(https://tauler\.seu\.cat/pagDetall\.do[^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    d = _parse_fecha_dmy(text)
    if d:
        return d
    m = RE_EXP_CODE.search(text or "")
    if m:
        code = m.group(1)
        if code.upper().startswith("X20") and len(code) >= 5:
            year = code[1:5]
            if year.isdigit():
                return f"{year}-06-01"
    blob = f"{text} {url}"
    years = [int(y.group(1)) for y in RE_YEAR.finditer(blob) if 1985 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}"
    return None


def _proyecto_tipo(titulo: str) -> str:
    n = (titulo or "").lower()
    if "suspensi" in n and "llic" in n:
        return "suspensión de licencias"
    if "exposici" in n or "informaci" in n or "edicte" in n:
        return "información pública"
    if "mppgo" in n or "planejament general" in n or "pgou" in n:
        return "planeamiento general"
    if "aprovaci" in n and "inicial" in n:
        return "aprobación inicial"
    if "rehabilitaci" in n or "facana" in n or "mitgera" in n:
        return "proyecto de edificación"
    if "esplanada" in n or "urbanitz" in n:
        return "proyecto urbanístico"
    if "normativa" in n:
        return "normativa urbanística"
    return "planeamiento"


class ElMasnouAyuntamientoAdapter(AyuntamientoAdapter):
    """CMS webmunicipal (elmasnou.cat) + seu-e + e-TAULER (referencia); sin GIS por expediente."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.media_base = str(self.config.get("media_base") or MEDIA_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.ua = str(self.config.get("user_agent", "poc-bocm-el-masnou/1.0"))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_maybe(self, url: str) -> str | None:
        try:
            return self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError):
            return None

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or f"{self.web_base}/", unescape(href))

    def _normalize_pdf_url(self, href: str, page_url: str) -> str:
        u = self._abs_url(href, page_url)
        if u.startswith("/media/"):
            u = f"{self.media_base}{u}"
        return u.split("#")[0]

    def _is_urban_pdf(self, url: str) -> bool:
        low = url.lower()
        if not low.endswith(".pdf"):
            return False
        if "/urbanisme/" not in low and "repository/urbanisme" not in low:
            return False
        if RE_EXCLUDE.search(low):
            return False
        return bool(RE_PROYECTO.search(low))

    def _pdf_row(self, url: str, origen: str = "repository_pdf") -> dict[str, Any] | None:
        if not self._is_urban_pdf(url):
            return None
        path = urllib.parse.unquote(url.split("?")[0])
        parts = [p for p in path.split("/") if p and p.lower() != "urbanisme"]
        folder = parts[-2] if len(parts) >= 2 else ""
        fname = parts[-1].replace(".pdf", "").replace("_", " ")
        titulo = folder.replace("_", " ").replace("-", " ") if folder and len(folder) > 4 else fname
        titulo = re.sub(r"\s+", " ", titulo).strip() or url
        if RE_EXCLUDE.search(titulo):
            return None
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": _fecha_from_blob(f"{titulo} {fname}", url) or None,
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": origen,
            "documento_url": url,
        }

    def _tauler_rows(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_TAULER.finditer(html):
            url = m.group(1).split('"')[0]
            titulo = _strip_html(m.group(2))
            if not titulo or RE_EXCLUDE.search(titulo):
                continue
            if not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo, url) or None,
                    "tipo": _proyecto_tipo(titulo),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "etauler_link",
                }
            )
        for href in RE_HREF.findall(html):
            if "tauler.seu.cat/pagDetall.do" not in href:
                continue
            url = self._abs_url(href, page_url)
            if any(r.get("url") == url for r in rows):
                continue
            titulo = "Edicte e-TAULER"
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": None,
                    "tipo": "información pública",
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "etauler_link",
                }
            )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for seed in self.seed_pages:
            html = self._fetch_maybe(seed)
            if not html:
                continue
            for href in RE_HREF.findall(html):
                if href.startswith(("#", "mailto:", "javascript:")):
                    continue
                pdf_url = self._normalize_pdf_url(href, seed)
                row = self._pdf_row(pdf_url)
                if row:
                    by_id[row["id"]] = row
            for row in self._tauler_rows(html, seed):
                by_id[row["id"]] = row
        return list(by_id.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url, label in DEFAULT_LICENCIA_PAGES:
            if page_url in seen:
                continue
            seen.add(page_url)
            rows.append(
                {
                    "id": _stable_id("lic", page_url),
                    "fecha_concesion": None,
                    "tipo": label[:200],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": page_url,
                    "source": "ayuntamiento",
                    "origen": "tramites_informativos",
                }
            )
        urbanisme = self._fetch_maybe(f"{self.web_base}/temes/urbanisme")
        if urbanisme:
            for href, text in RE_LINK.findall(urbanisme):
                t = _strip_html(text)
                u = self._abs_url(href, f"{self.web_base}/temes/urbanisme")
                if u in seen or len(t) < 8:
                    continue
                if "elmasnou.cat" not in u and "tauler.seu.cat" not in u and "seu-e.cat" not in u:
                    continue
                if not (RE_LICENCIA.search(t) or RE_LICENCIA.search(u)):
                    continue
                seen.add(u)
                rows.append(
                    {
                        "id": _stable_id("lic", u),
                        "fecha_concesion": _fecha_from_blob(t, u) or None,
                        "tipo": t[:200],
                        "distrito": MUNICIPIO,
                        "lat": None,
                        "lon": None,
                        "url": u,
                        "source": "ayuntamiento",
                        "origen": "urbanisme_web",
                    }
                )
        return rows

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
        return {"rows": len(rows), "mode": "backfill"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "count": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "mode": "update"}

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "mode": "backfill"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "count": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "mode": "update"}
