from __future__ import annotations

import hashlib
import http.cookiejar
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
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://quatretonda.es"
SEDE_BASE = "https://quatretonda.sedelectronica.es"
MUNICIPIO = "Quatretonda"
ID_PREFIX = "quatretonda"
INE_MUN = "46214"

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER = "ms:InventarioSuSuz"

DEFAULT_SEED_PAGES: tuple[str, ...] = (
    f"{WEB_BASE}/pla-general-estructural-de-quatretonda/",
    f"{WEB_BASE}/teleadiministracio/documentacio/",
    f"{WEB_BASE}/ajuntament/tauler-danuncis/",
    f"{WEB_BASE}/informe-inundabilitat-quatretonda/",
    f"{WEB_BASE}/pla-dinundacions-i-pla-sismic-quatretonda/",
)

RE_PREVIEW = re.compile(
    r'href="(https://quatretonda\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="(https://quatretonda\.sedelectronica\.es/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_PDF = re.compile(r'href="(https://quatretonda\.es/wp-content/uploads/[^"]+\.pdf)"', re.I)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra[s]? (?:major|menor)|"
    r"primera ocupaci[oó]n|compatibilidad urban|informe urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|estructural)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"aprobaci[oó]n (?:inicial|definitiva)|sector|ue-|sd-|suz|inundabilit|s[ií]smic|"
    r"rehabilitaci[oó]n.*(?:casc|vivend)|direcci[oó]n d.obra|redacci[oó]n projecte|"
    r"camins rurals|condicionament cam[ií])",
)
RE_NOISE = re.compile(
    r"(?i)(subvenci[oó]n|ocupaci[oó] p[uú]blica|pl[aà] d.ocupaci[oó]|borsa|personal|"
    r"llibres de text|material did[aà]ctic|entitats culturals|escoles esportives|"
    r"moros i cristians|festes|empadron|ia[eé]|frau)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|PRI|PERI|SECTOR|SUZ)[\s\-]?(?:\d+|[A-Z]+)(?:[\s,\-yY/]+[\dA-Z]+)*)\b",
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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y) for y in re.findall(r"\b(20\d{2}|19\d{2})\b", text or "") if 1980 <= int(y) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = (blob or "").lower()
    if "inundabilit" in n or "inundaci" in n:
        return "planeamiento hidráulico"
    if "s[ií]smic" in n:
        return "planeamiento sísmico"
    if "plan estructural" in n or "pla general estructural" in n:
        return "plan general estructural"
    if "plan parcial" in n or re.search(r"\bpp[\s-]", n):
        return "plan parcial"
    if "estudi" in n and "detall" in n:
        return "estudio de detalle"
    if "expropi" in n:
        return "expropiación"
    if "informaci" in n:
        return "información pública"
    if re.search(r"\b(suz|su|ue|sector)\b", n):
        return "sector planeamiento"
    if "rehabilit" in n and "vivend" in n:
        return "rehabilitación urbana"
    if "cam[ií]" in n or "caminos rurales" in n:
        return "actuación vial"
    return "planeamiento"


def _sector_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for m in RE_SECTOR_TOKEN.finditer(text or ""):
        tok = _strip_html(m.group(1))
        if len(tok) >= 3:
            tokens.append(tok)
    return tokens


class QuatretondaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress quatretonda.es + sede espublico gestiona + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-quatretonda/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-quatretonda/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 4:
                continue
            link_m = re.search(
                r'href="(https://quatretonda\.sedelectronica\.es/preview-document/[^"]+)"',
                tr,
                re.I,
            )
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": _strip_html(cells[1]) if len(cells) > 1 else "",
                    "procedimiento": _strip_html(cells[2]) if len(cells) > 2 else "",
                    "categoria": _strip_html(cells[3]) if len(cells) > 3 else "",
                    "descripcion": _strip_html(cells[4]) if len(cells) > 4 else "",
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])) if len(cells) > 5 else None,
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": origen,
                }
            )
        return rows

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 400) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": titulo[:500],
                    "expediente": "",
                    "procedimiento": "",
                    "categoria": "",
                    "descripcion": titulo,
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in ((self.board_url, "tablon"), (self.info_url, "info_tablon")):
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in (self.info_url, f"{WEB_BASE}/teleadiministracio/tramits-en-linea/"):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_CATALOG.finditer(html):
                url, titulo = m.group(1), unescape(m.group(2).strip())
                if url in seen:
                    continue
                seen.add(url)
                if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                    continue
                rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _collect_wp_tramite_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(f"{WEB_BASE}/teleadiministracio/documentacio/")
        except urllib.error.URLError:
            return rows
        for href in RE_PDF.findall(html):
            name = urllib.parse.unquote(href.rsplit("/", 1)[-1]).replace(".pdf", "").replace("_", " ")
            if not RE_LICENCIA.search(name) and not RE_PROYECTO.search(name):
                continue
            rows.append(
                {
                    "titulo": name[:500],
                    "url": href,
                    "fecha": None,
                    "origen": "wp_tramite_pdf",
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = f"{WEB_BASE}/wp-json/wp/v2/posts?per_page=100&page={page}"
            try:
                posts = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not posts:
                break
            for post in posts:
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                link = str(post.get("link") or "")
                excerpt = _strip_html(post.get("excerpt", {}).get("rendered", ""))
                blob = f"{title} {excerpt}"
                if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob):
                    continue
                fecha = (post.get("date") or "")[:10] or None
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": link,
                        "fecha": fecha,
                        "tipo": _proyecto_tipo(blob),
                        "origen": "wp_noticia",
                    }
                )
            page += 1
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
            page_title = _strip_html(title_m.group(1) if title_m else seed)
            if RE_PROYECTO.search(page_title) or seed in self.seed_pages[:3]:
                rows.append(
                    {
                        "titulo": page_title[:500],
                        "url": seed,
                        "fecha": _fecha_from_blob(page_title),
                        "tipo": _proyecto_tipo(page_title),
                        "origen": "wp_pagina",
                    }
                )
            for href in RE_PDF.findall(html):
                name = urllib.parse.unquote(href.rsplit("/", 1)[-1])
                blob = f"{page_title} {name}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": f"{page_title} — {name}"[:500],
                        "url": href,
                        "fecha": _fecha_from_blob(blob),
                        "tipo": _proyecto_tipo(blob),
                        "origen": "wp_pdf",
                    }
                )
        return rows

    def _icv_wfs_url(self, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": ICV_LAYER,
                "count": "200",
                "startIndex": str(start),
                "outputFormat": "application/json; subtype=geojson",
                "srsName": "EPSG:4326",
            }
        )
        return f"{ICV_WFS}?{params}"

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        start = 0
        # El servicio ignora CQL_FILTER; hay que paginar y filtrar por cod_ine_mun (patrón picassent).
        while start < 10000:
            url = self._icv_wfs_url(start)
            try:
                data = self._fetch_json(url, timeout=120)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            feats = data.get("features") or []
            if not feats:
                break
            for feat in feats:
                props = feat.get("properties") or {}
                if str(props.get("cod_ine_mun") or "") != INE_MUN:
                    continue
                geom = feat.get("geometry")
                pp = _strip_html(str(props.get("pp") or ""))
                ue = _strip_html(str(props.get("ue") or ""))
                clas = _strip_html(str(props.get("clasificacion") or ""))
                fid = str(props.get("id") or props.get("gml_id") or "")
                titulo = pp or ue or f"Sector {fid}"
                if ue and ue not in titulo:
                    titulo = f"{pp} ({ue})" if pp else ue
                rec: dict[str, Any] = {
                    "titulo": titulo[:500],
                    "fecha": props.get("f_aprob") or None,
                    "url": url,
                    "tipo": "sector SU/SUZ" if clas else "sector planeamiento",
                    "pp": pp or None,
                    "ue": ue or None,
                    "clasificacion": clas or None,
                    "wfs_id": fid or None,
                    "origen": "icv_wfs",
                }
                if geom:
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
            start += 200
        self._wfs_cache = rows
        self._wfs_by_key = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if low:
                    self._wfs_by_key[low] = rec
            for tok in _sector_tokens(rec.get("titulo") or ""):
                self._wfs_by_key[tok.lower()] = rec
        return rows

    def _match_wfs(self, text: str) -> dict[str, Any] | None:
        if self._wfs_by_key is None:
            self._collect_icv_wfs()
        low = (text or "").lower()
        best: dict[str, Any] | None = None
        best_len = 0
        for key, rec in (self._wfs_by_key or {}).items():
            if len(key) >= 4 and key in low and len(key) > best_len:
                best = rec
                best_len = len(key)
        if best:
            return best
        for tok in _sector_tokens(text):
            hit = (self._wfs_by_key or {}).get(tok.lower())
            if hit:
                return hit
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "pp", "ue"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria", "descripcion"))
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Formulario o trámite informativo; sin concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("wfs_id") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expediente"):
            rec["expte"] = row["expediente"]
        for key in (
            "pp",
            "ue",
            "clasificacion",
            "wfs_id",
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
            "pdf_url",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria", "descripcion"))
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            cat = (row.get("categoria") or "").lower()
            if "urban" not in cat and "planeam" not in cat:
                return None
        return self._to_proyecto(row)

    def _portal_row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "icv_wfs":
            return self._to_proyecto(row)
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        return self._to_proyecto(row)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_catalog_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_wp_tramite_pdfs():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") in ("catalogo_tramites", "wp_tramite_pdf")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_catalog_tramites() + self._collect_wp_tramite_pdfs():
            rec = self._tramite_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, len(rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_icv_wfs():
            add(self._portal_row_to_proyecto(item))
        for item in self._collect_seed_pages():
            add(self._portal_row_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._portal_row_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_catalog_tramites():
            titulo = item["titulo"]
            if RE_PROYECTO.search(titulo):
                add(
                    self._to_proyecto(
                        {
                            "titulo": titulo,
                            "url": item["url"],
                            "fecha": None,
                            "origen": item.get("origen"),
                        }
                    )
                )

        self._write_jsonl(out_jsonl, rows)
        icv = sum(1 for r in rows if r.get("origen") == "icv_wfs")
        with_geom = sum(1 for r in rows if r.get("geom_geojson"))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": icv,
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
