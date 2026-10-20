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
from municipio.geometry import geometry_centroid

WP_BASE = "https://www.ayto-caceres.es"
SEDE_BASE = "https://sede.caceres.es"
SIG_BASE = "https://sig.caceres.es"
MUNICIPIO = "Cáceres"
ID_PREFIX = "caceres"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
CPO_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_CPO"
)
URBANISMO_KEYWORD = "PTS_PC_012"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/ayuntamiento/plan-general-municipal/",
    f"{WP_BASE}/transparencia/urbanismo-y-obras-publicas/",
    f"{WP_BASE}/ayuntamiento/tablon-de-anuncios-y-edictos-electronicos/",
]

SIG_PLANEAMIENTO_TIPOS: list[str] = ["30", "31", "40", "41", "50"]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|primera ocupaci[oó]n|"
    r"licencia (?:de )?obra|permiso de obra|inicio de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgm|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|"
    r"proyecto|modificaci[oó]n|reparcel|estudio de detalle|aprobaci[oó]n|"
    r"actuaci[oó]n urban|ape\b|api\b|uzi\b|instrumento|ordenaci[oó]n|"
    r"utilidad p[uú]blica|fotovoltaica|instalaci[oó]n)",
)
RE_EXCLUDE_PROY = re.compile(
    r"(?i)(cobranza|i\.?a\.?e\.?|impuesto|subvenci[oó]n|proceso selectivo|"
    r"concurso-oposici|empleo|bolsa de|presupuesto|bando de|"
    r"resultados definitivos de la fase de concurso|calificaci[oó]n definitiva)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_WP_PDF = re.compile(
    r'href="((?:https?://(?:www\.)?ayto-caceres\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_SIG_PDF = re.compile(
    r'href="(https?://sig\.caceres\.es[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_SIG_INSTR = re.compile(
    r"Ámbito PGM10\s*</td>\s*<td><strong>([^<]+)</strong>.*?"
    r"Expediente\s*</td>\s*<td[^>]*>\s*<strong>([^<]+)</strong>.*?"
    r"Denominación\s*</td>\s*<td>([^<]+)</td>.*?"
    r"Situación\s*</td>\s*<td>([^<]+)</td>(.*?)(?=Ámbito PGM10|$)",
    re.S | re.I,
)
RE_SIG_MAP = re.compile(
    r"serweb/planea/\?cx=([-\d.]+)&cy=([-\d.]+)&iden=(\d+)",
    re.I,
)
RE_AMBITO_CODE = re.compile(
    r"(?i)\b((?:API|UZI|APE|PP|PLA)-[\w\s./-]+?)(?:\s{2,}|$)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _iso_from_year(text: str) -> str | None:
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2035
    ]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(
            int(obj["year"]),
            int(obj["month"]),
            int(obj["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _proyecto_tipo(section: str, title: str) -> str:
    blob = f"{section} {title}".lower()
    if "plan parcial" in blob or re.search(r"\bpp-", blob):
        return "plan parcial"
    if "modificaci" in blob and "pgm" in blob:
        return "modificación PGM"
    if "pgm" in blob or "pgou" in blob or "plan general" in blob:
        return "PGM"
    if "exposici" in blob or "informaci" in blob:
        return "información pública"
    if "utilidad p" in blob and "blica" in blob:
        return "utilidad pública"
    if "licencia" in blob:
        return "licencia urbanística"
    if "anuncio" in blob or "edicto" in blob:
        return "anuncio"
    return section or "urbanismo"


class CaceresAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress ayto-caceres.es + sede STA (tablón/catálogo) + SIG planeamiento; geometría parcial IDE WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.sig_base = str(self.config.get("sig_base") or SIG_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.sig_tipos = [str(t) for t in (self.config.get("sig_planeamiento_tipos") or SIG_PLANEAMIENTO_TIPOS)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(
            geom_cfg.get("wfs_url") or "https://ide.caceres.es/geoserver/PGM2010/ows"
        ).rstrip("/")
        self.wfs_layer = str(geom_cfg.get("type_name") or "PGM2010:alteraciones_plan")
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sig_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._geom_cache: dict[str, dict[str, Any] | None] = {}
        self._wfs_disabled = False
        self._wfs_timeout_s = float(geom_cfg.get("timeout_s", 4))

    def _fetch(self, url: str, *, use_insecure: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-caceres/1.0")},
        )
        ctx = self._ssl_ctx if use_insecure or "sig.caceres.es" in url or "ide.caceres.es" in url else None
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            keywords = item.get("keywordList") or []
            if not any(str(k.get("code") or "") == URBANISMO_KEYWORD for k in keywords):
                continue
            name = str(item.get("name") or "").strip()
            code = str(item.get("code") or item.get("dboid") or name)
            if not name:
                continue
            url = f"{CATALOGO_URL}#tramite={code}"
            rows.append({"name": name, "code": code, "url": url})
        return rows

    def _collect_sig_instruments(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tipo in self.sig_tipos:
            url = f"{self.sig_base}/planea/planeamiento_actual.php?tipo={tipo}"
            try:
                html = self._fetch(url, use_insecure=True)
            except urllib.error.URLError:
                continue
            for m in RE_SIG_INSTR.finditer(html):
                ambito = unescape(m.group(1).strip())
                expediente = unescape(m.group(2).strip())
                denominacion = unescape(m.group(3).strip())
                situacion = unescape(m.group(4).strip())
                tail = m.group(5)
                key = expediente or ambito
                if key in seen:
                    continue
                seen.add(key)
                map_hit = RE_SIG_MAP.search(tail)
                pdf_m = RE_SIG_PDF.search(tail)
                titulo = f"{denominacion} — {situacion} ({expediente})"
                out.append(
                    {
                        "ambito": ambito,
                        "expediente": expediente,
                        "titulo": titulo[:500],
                        "fecha": _iso_from_year(expediente),
                        "url": url,
                        "pdf_url": pdf_m.group(1) if pdf_m else None,
                        "iden": map_hit.group(3) if map_hit else None,
                        "origen": "sig_planeamiento",
                    }
                )
        return out

    def _collect_wp_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for pat in (RE_WP_PDF, RE_SIG_PDF):
                for href in pat.findall(html):
                    pdf_url = href if href.startswith("http") else urllib.parse.urljoin(WP_BASE, href)
                    if pdf_url in seen:
                        continue
                    seen.add(pdf_url)
                    name = unescape(urllib.parse.unquote(pdf_url.split("/")[-1].split("?")[0]))
                    rows.append(
                        {
                            "titulo": name[:500],
                            "fecha": _iso_from_year(name) or _parse_fecha_dmy(name),
                            "url": page_url,
                            "pdf_url": pdf_url,
                            "origen": "web_pgm",
                        }
                    )
        return rows

    def _wfs_geometry(self, id_tabla_p: str) -> dict[str, Any] | None:
        if self._wfs_disabled:
            return None
        if id_tabla_p in self._geom_cache:
            return self._geom_cache[id_tabla_p]
        qs = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.wfs_layer,
                "count": "1",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "CQL_FILTER": f"id_tabla_p={id_tabla_p}",
            }
        )
        url = f"{self.wfs_base}?{qs}"
        hit: dict[str, Any] | None = None
        try:
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-caceres/1.0")},
            )
            with urllib.request.urlopen(
                req, timeout=self._wfs_timeout_s, context=self._ssl_ctx
            ) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            feats = data.get("features") or []
            if feats and isinstance(feats[0], dict):
                geom = feats[0].get("geometry")
                if isinstance(geom, dict) and geom.get("type"):
                    hit = {
                        "geom_geojson": geom,
                        "geometry_source": "portal_wfs",
                        "geometry_source_url": url,
                        "coord_source": "portal_geometry_centroid",
                    }
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
            hit = None
            self._wfs_disabled = True
        self._geom_cache[id_tabla_p] = hit
        return hit

    def _attach_geometry(self, rec: dict[str, Any], iden: str | None = None) -> None:
        if iden:
            geom = self._wfs_geometry(iden)
            if geom:
                rec.update(geom)
                centroid = geometry_centroid(geom["geom_geojson"])
                if centroid:
                    rec["lat"], rec["lon"] = centroid
                return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "expediente", "ambito"))
        for code in RE_AMBITO_CODE.findall(blob):
            rec.setdefault("ambito_code", code.strip())

    def _tablon_row(self, row: dict[str, Any]) -> tuple[str, str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        expte = str(row.get("externString") or "")
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, remitente, fecha, expte, url

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
        if not RE_LICENCIA.search(blob):
            return None
        key = expte or url
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": fecha or None,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "expte": expte or None,
            "url": url,
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _tramite_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item["name"]
        if not RE_LICENCIA.search(name):
            return None
        return {
            "id": _stable_id("lic", item["code"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": name[:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "nota": "Trámite en sede; no concesión publicada en tablón",
            "origen": "catalogo",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
        if RE_EXCLUDE_PROY.search(blob):
            return None
        is_urbanismo = "URBANISMO" in remitente.upper()
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and not is_urbanismo:
            return None
        if not is_urbanismo and not RE_PROYECTO.search(blob):
            return None
        key = expte or url
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha or None,
            "tipo": _proyecto_tipo(remitente, title),
            "url": url,
            "expte": expte or None,
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        self._attach_geometry(rec)
        return rec

    def _tramite_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item["name"]
        if RE_LICENCIA.search(name) and not RE_PROYECTO.search(name):
            return None
        if not RE_PROYECTO.search(name):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", item["code"]),
            "municipio": MUNICIPIO,
            "titulo": name[:500],
            "fecha": None,
            "tipo": _proyecto_tipo("trámite", name),
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": "catalogo",
        }
        return rec

    def _sig_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        key = item.get("expediente") or item.get("ambito") or item["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(item.get("ambito", ""), item["titulo"]),
            "url": item.get("pdf_url") or item["url"],
            "expediente": item.get("expediente"),
            "ambito": item.get("ambito"),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        self._attach_geometry(rec, iden=item.get("iden"))
        return rec

    def _pdf_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        titulo = item["titulo"]
        if not RE_PROYECTO.search(titulo):
            return None
        key = item.get("pdf_url") or item["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo("PGM", titulo),
            "url": item.get("pdf_url") or item["url"],
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_catalog_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        if not rows:
            rows.append(
                {
                    "id": _stable_id("lic", CPO_URL),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Comunicación previa de obras (sede electrónica)",
                    "url": CPO_URL,
                    "source": "ayuntamiento",
                    "origen": "tramite_sede",
                }
            )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo"),
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_catalog_tramites():
            add(self._tramite_to_proyecto(item))
        for item in self._collect_sig_instruments():
            add(self._sig_to_proyecto(item))
        for item in self._collect_wp_pdfs():
            add(self._pdf_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "sig": sum(1 for r in rows if r.get("origen") == "sig_planeamiento"),
            "web": sum(1 for r in rows if r.get("origen") == "web_pgm"),
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
