from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import record_geometry
from municipio.onboarding_snapshot import reviewed_records

WEB_BASE = "https://www.esparreguera.cat"
SEU_BASE = "https://seu.esparreguera.cat"
# INE 08076 (prov. 08, mun. 076). Usat per MUC / RPUC (patró Sitges).
INE_MUNICIPI = "08076"
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUNICIPI}&set-locale=ca"
RPUC_MUNICI = (
    f"https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel={INE_MUNICIPI}"
)
MUNICIPIO = "Esparreguera"
ID_PREFIX = "esparreguera"

DEFAULT_CATEGORIES: list[int] = [7]
# Subcercadors sota «Instruments de planificació urbanística» (portal seu).
CERCADOR_IDS: list[int] = [35, 36, 37, 8, 32, 33, 34]

TRAMITS_INFORMATIVOS: list[tuple[str, str]] = [
    (
        f"{SEU_BASE}/urbanismeCategoriaPublic/listPublicacionsAmbCategoria?categoria.id=7",
        "Instruments de planificació urbanística — registre de publicacions (seu)",
    ),
    (f"{WEB_BASE}/urbanisme/", "Urbanisme — web municipal (enllaços i informació)"),
    (f"{SEU_BASE}/taulerAnuncisCategoriaPublic/index", "Tauler d'anuncis electrònic (catàleg, seu)"),
    ("https://tauler.seu.cat/inici.do?idens=807650006", "Tauler d'anuncis físic (Consorci AOC, idens 807650006)"),
    (MUC_VISOR, "Visor MUC — cartografia urbanística (Generalitat, municipi INE)"),
    (RPUC_MUNICI, "RPUC — cerca d'expedients de planejament urbanístic (Generalitat)"),
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó] responsable|obra major|obra menor|"
    r"projecte d['\u2019]?obres|autoritzaci[oó])",
)
RE_LICENCIA_SKIP = re.compile(
    r"(?i)(domini p[uú]blic|via p[uú]blica|aprofitament|ocupaci[oó] temporal|"
    r"fira|mercat|festa|plec)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|urbanism|planej|planeam|poum|pgou|modificaci[oó]|aprovaci[oó]|"
    r"informaci[oó] p[uú]blica|expedient|edict|conveni|pla (?:parcial|especial)|"
    r"reparcel|reparcel|estudi de detall|ordenan[cç]a|delimitaci[oó]|"
    r"gesti[oó] urban|instrument)",
)
RE_FECHA_JAVA = re.compile(
    r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\w+\s+(\d{4})$"
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_EXPEDIENT = re.compile(
    r"(?i)(?:N[uú]m(?:ero)?\.?\s*d['\u2019]?expedient|expedient|exp\.)\s*[:\s]+"
    r"([0-9]{2,}[-/][0-9]{2,}[-/A-Z0-9/]+|[0-9]{3,}/[0-9]{4})"
)
RE_URBAN_CONTEXT = re.compile(
    r"(?i)(urban|urbanism|planej|planeam|obra|viviend|edific|suelo|parcel|"
    r"pgou|poum|conveni|reparcel|instrument|ordenan)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_JAVA.search((text or "").strip())
    if m:
        try:
            y = int(m.group(1))
            # sense dia concret: usar 1 de gener com a fallback conservador
            return datetime(y, 1, 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _java_row_fecha(title_attr: str) -> str | None:
    t = (title_attr or "").strip()
    m = re.match(
        r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\s+\w+\s+(\d{4})$",
        t,
    )
    if not m:
        return None
    meses = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }
    try:
        mo = meses[m.group(1)]
        d = int(m.group(2))
        y = int(m.group(6))
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, ValueError):
        return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n:
        return "modificación urbanística"
    if "informaci" in n and "públic" in n:
        return "información pública"
    if "aprovaci" in n and "inicial" in n:
        return "aprobación inicial"
    if "aprovaci" in n and "definitiv" in n:
        return "aprobación definitiva"
    if "conveni" in n:
        return "convenio urbanístico"
    if "pla especial" in n or "plan especial" in n:
        return "plan especial"
    if "instrument" in n and "plan" in n:
        return "instrumento de planificación"
    return "planeamiento / urbanismo"


class EsparregueraAyuntamientoAdapter(AyuntamientoAdapter):
    """Seu seu.esparreguera.cat (urbanisme + registre) + web esparreguera.cat."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seu_base = str(self.config.get("seu_base") or SEU_BASE).rstrip("/")
        self.categories = [int(x) for x in (self.config.get("categories") or DEFAULT_CATEGORIES)]
        self.cercador_ids = [int(x) for x in (self.config.get("cercador_ids") or CERCADOR_IDS)]
        self.max_pages = int(self.config.get("max_pages", 12))
        self.page_size = int(self.config.get("page_size", 10))
        self.registre_pages = int(self.config.get("registre_pages", 8))

    def _fetch(self, url: str, *, timeout: int = 60) -> str | None:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-esparreguera/1.0"),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "ca,es;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError):
            return None

    def _abs_seu(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.seu_base}{path if path.startswith('/') else '/' + path}"

    def _parse_blocks(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for chunk in html.split('class="dElementPublicacioDefecte"')[1:]:
            tit_m = re.search(r'<div class="titol">([^<]+)', chunk, re.I)
            if not tit_m:
                continue
            titulo = _strip_html(tit_m.group(1))
            if not titulo:
                continue
            fecha = None
            m_date = re.search(
                r'class="data-registre-publicacions"[^>]*>.*?<span>([^<]+)</span>',
                chunk,
                re.I | re.S,
            )
            if not m_date:
                m_date = re.search(
                    r'class="dataRegistre camp"[^>]*>.*?<span>([^<]+)</span>',
                    chunk,
                    re.I | re.S,
                )
            if m_date:
                fecha = _parse_fecha(m_date.group(1))
            if not fecha:
                fecha = _parse_fecha(titulo)
            url = ""
            m_link = re.search(r'href="(/registrePublic/registrePublicacio/\d+)"', chunk)
            if m_link:
                url = self._abs_seu(m_link.group(1))
            if not url:
                m_pdf = re.search(r'href="(/documentPublic/download/\d+)"', chunk)
                if m_pdf:
                    url = self._abs_seu(m_pdf.group(1))
            expediente = ""
            m_exp = RE_EXPEDIENT.search(_strip_html(chunk))
            if m_exp:
                expediente = m_exp.group(1).strip()
            body = ""
            m_body = re.search(
                r'class="top(?: camp)?"[^>]*>(.*?)</div>\s*<div class="bottom',
                chunk,
                re.I | re.S,
            )
            if m_body:
                body = _strip_html(m_body.group(1))[:800]
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url or self.seu_base,
                    "expediente": expediente,
                    "body": body,
                    "origen": origen,
                }
            )
        return rows

    def _collect_list_pages(
        self,
        path_template: str,
        *,
        origen: str,
        extra_query: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for page in range(self.max_pages):
            offset = page * self.page_size
            q: dict[str, str] = {"offset": str(offset), "max": str(self.page_size)}
            if extra_query:
                q.update(extra_query)
            qs = urllib.parse.urlencode(q)
            url = f"{self.seu_base}{path_template}?{qs}"
            html = self._fetch(url)
            if not html:
                break
            batch = self._parse_blocks(html, origen)
            if not batch:
                break
            for row in batch:
                key = row["url"] if row["url"] != self.seu_base else f"{row['titulo']}|{row.get('fecha')}"
                by_url[key] = row
            if f"offset={offset + self.page_size}" not in html and page > 0:
                break
        return list(by_url.values())

    def _collect_cercador(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for cid in self.cercador_ids:
            rows.extend(
                self._collect_list_pages(
                    f"/urbanismeCategoriaPublic/cercadorCategoria/{cid}",
                    origen=f"seu_cercador_{cid}",
                    extra_query={},
                )
            )
        by_key = {r["url"]: r for r in rows if r.get("url")}
        return list(by_key.values())

    def _parse_registre_table(self, html: str) -> list[dict[str, Any]]:
        """Parseja la taula class=registreTable de /registrePublic/ultims."""
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
            m_pub = re.search(r'href="(/registrePublic/registrePublicacio/(\d+))"', tr)
            if not m_pub:
                continue
            path, pub_id = m_pub.group(1), m_pub.group(2)
            url = self._abs_seu(path)
            m_data = re.search(r'data-label="Data"[^>]*>\s*<a[^>]*title="([^"]*)"', tr, re.I | re.S)
            fecha = _java_row_fecha(m_data.group(1)) if m_data else None
            m_ac = re.search(
                r'data-label="Acci[oó]"[^>]*>\s*<a[^>]*>([^<]+)</a>',
                tr,
                re.I | re.S,
            )
            accio = _strip_html(m_ac.group(1)) if m_ac else ""
            m_tit = re.search(
                r'data-label="T[íi]tol"[^>]*>\s*<a[^>]*title="([^"]*)"',
                tr,
                re.I | re.S,
            )
            titulo = _strip_html(m_tit.group(1)) if m_tit else ""
            m_tip = re.search(
                r'data-label="Tipus"[^>]*>\s*<a[^>]*title="([^"]*)"',
                tr,
                re.I | re.S,
            )
            tipo = _strip_html(m_tip.group(1)) if m_tip else ""
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "expediente": "",
                    "body": tipo[:300],
                    "categoria": tipo,
                    "accio": accio,
                    "pub_id": pub_id,
                    "origen": "seu_registre_ultims",
                }
            )
        return rows

    def _collect_registre(self) -> list[dict[str, Any]]:
        """Darreres publicacions (filtrat urbanisme després)."""
        by_key: dict[str, dict[str, Any]] = {}
        for page in range(self.registre_pages):
            offset = page * self.page_size
            q = urllib.parse.urlencode({"offset": str(offset), "max": str(self.page_size)})
            url = f"{self.seu_base}/registrePublic/ultims?{q}"
            html = self._fetch(url)
            if not html:
                break
            batch = self._parse_registre_table(html)
            if not batch:
                break
            for row in batch:
                if str(row.get("accio") or "").lower() != "publicat":
                    continue
                k = f"{row.get('pub_id')}|{row.get('titulo')}"
                by_key[k] = row
        return list(by_key.values())

    def _collect_seu_categories(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for cat_id in self.categories:
            extra = {"categoria.id": str(cat_id), "esCatPrincipal": ""}
            rows.extend(
                self._collect_list_pages(
                    "/urbanismeCategoriaPublic/listPublicacionsAmbCategoria",
                    origen=f"seu_urbanisme_cat_{cat_id}",
                    extra_query=extra,
                )
            )
        by_key = {r["url"]: r for r in rows if r.get("url")}
        return list(by_key.values())

    def _catalog_stubs(self) -> list[dict[str, Any]]:
        stubs: list[dict[str, Any]] = []
        for url, titulo in TRAMITS_INFORMATIVOS:
            stubs.append(
                {
                    "titulo": titulo,
                    "fecha": None,
                    "url": url,
                    "expediente": "",
                    "body": "",
                    "origen": "catalog_stub",
                }
            )
        return stubs

    def _proyecto_record(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row.get("titulo") or ""
        tipo_cat = row.get("categoria") or ""
        blob = f"{titulo} {row.get('body') or ''} {row.get('expediente') or ''} {tipo_cat}"
        if row.get("origen") != "catalog_stub":
            if not RE_PROYECTO.search(blob):
                return None
            if row.get("origen") == "seu_registre_ultims" and not RE_URBAN_CONTEXT.search(blob):
                return None
        url = row.get("url") or WEB_BASE
        key = f"{url}|{titulo}"
        tipo = _proyecto_tipo(blob)
        if row.get("expediente"):
            tipo = f"{tipo} — {row['expediente'][:80]}"
        fecha = row.get("fecha") or "2020"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": tipo[:300],
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expediente"):
            rec["expediente"] = row["expediente"]
        if row.get("body"):
            rec["resumen"] = str(row["body"])[:500]
        return rec

    def _licencia_record(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row.get("titulo") or "Licencia / trámite"
        url = row.get("url") or self.seu_base
        return {
            "id": _stable_id("lic", f"{url}|{titulo}"),
            "fecha_concesion": row.get("fecha") or "2020",
            "tipo": titulo[:300],
            "distrito": "",
            "lat": None,
            "lon": None,
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _merge_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        sources = (
            self._collect_registre()
            + self._collect_seu_categories()
            + self._collect_cercador()
            + self._catalog_stubs()
        )
        for row in sources:
            rec = self._proyecto_record(row)
            if rec:
                by_id[rec["id"]] = rec
        return list(by_id.values())

    def _merge_licencias(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for row in self._collect_registre():
            tit = row.get("titulo") or ""
            cat = row.get("categoria") or ""
            blob = f"{tit} {cat}"
            if not RE_LICENCIA.search(blob):
                continue
            if not RE_URBAN_CONTEXT.search(blob):
                continue
            if RE_LICENCIA_SKIP.search(blob) and "obra" not in blob.lower():
                continue
            rec = self._licencia_record(row)
            by_id[rec["id"]] = rec
        return list(by_id.values())

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._merge_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "source": "ayuntamiento"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._merge_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
            "status": "ok",
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
