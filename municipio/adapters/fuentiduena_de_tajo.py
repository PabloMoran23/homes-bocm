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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WP_BASE = "https://www.fuentiduenadetajo.org"
SEDE_BASE = "https://fuentiduenadetajo.sedelectronica.es"
MUNICIPIO = "Fuentidueña de Tajo"
ID_PREFIX = "fuentiduena-de-tajo"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "FUENTIDUEÑA DE TAJO"

AVISOS_SITEMAP = f"{WP_BASE}/lsvrnotice-sitemap.xml"
DOCUMENTS_FEED = f"{WP_BASE}/documentos/feed/"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|edicto.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|proyecto|"
    r"modificaci[oó]n|aprobaci[oó]n|reparcel|sector|edicto|bocm|"
    r"parcela|concentraci[oó]n parcelaria|entorno urban|bando.*parcel|"
    r"ordenanza.*urban|\b(?:UA|S)-[\d\.]+[A-Z0-9-]*\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|iae\b|plusval[ií]a|calendario fiscal|jurado|presupuest|"
    r"selecci[oó]n de personal|funcionario|campamento urban|milla urbana|"
    r"corresponsables|empleo.formaci|premios acad|donaci[oó]n de sangre|"
    r"fiestas patronales|programa p[uú]blico de empleo|hereder|abintestato|"
    r"contrataci[oó]n personal|precios p[uú]blicos|actividades culturales|"
    r"campamentos urban|summer camp|club de vacaciones)",
)
RE_AMBIT_CODE = re.compile(r"(?i)\b((?:UA|S)-[\d\.]+[A-Z0-9-]*)\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://[^"\']+|/[^"\']+)\.(?:pdf|PDF)(?:[^"\']*)?)["\']',
    re.I,
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


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return None


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


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
    return None


def _sector_ilike_parts(text: str) -> list[str]:
    s = text.strip()
    low = s.lower()
    for marker in (" del pgou", " pgou", " bocm", " aprob", " anuncio", " bando"):
        if marker in low:
            s = s[: low.index(marker)]
            break
    parts = [p for p in re.split(r"[\s,;/|()\"«»]+", s) if len(p) >= 3]
    return parts[:6]


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "concentraci" in n and "parcel" in n:
        return "concentración parcelaria"
    if "bando" in n and "parcel" in n:
        return "bando urbanístico"
    if "entorno urban" in n or "mejora del entorno" in n:
        return "actuación urbanística"
    if re.search(r"(?i)planeamiento|pgou|plan parcial|plan especial", blob):
        return "planeamiento"
    if re.search(r"(?i)convenio", blob):
        return "convenio"
    if re.search(r"(?i)bocm", blob):
        return "publicación BOCM"
    return "urbanismo"


class FuentiduenaDeTajoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress ayuntamiento + sede espublico gestiona + WFS SITCM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency/"
        )
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", unescape(href))

    def _extract_pdfs(self, html: str) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_wp(m.group(1))
            if "favicon" in u.lower():
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def _parse_board_rows(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tr in re.findall(r"<tr>\s*(.*?)\s*</tr>", html, re.I | re.S):
            cells = re.findall(
                r'class="([^"]+)"[^>]*data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
                tr,
                re.I | re.S,
            )
            if not cells:
                continue
            row: dict[str, Any] = {}
            for _cls, label, val in cells:
                row[label] = _strip_html(val)
            link_m = re.search(r"preview-document/([a-f0-9-]+)", tr, re.I)
            if not link_m:
                continue
            uuid = link_m.group(1)
            if uuid in seen:
                continue
            seen.add(uuid)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else row.get("Documento", "")
            row.update(
                {
                    "titulo": titulo[:500] or row.get("Documento", "")[:500],
                    "expediente": row.get("Expediente", ""),
                    "procedimiento": row.get("Procedimiento", ""),
                    "categoria": row.get("Categoría", ""),
                    "descripcion": row.get("Descripción", ""),
                    "fecha": _parse_fecha_dmy(row.get("Fecha de Publicación", "")),
                    "url": f"{self.sede_base}/preview-document/{uuid}",
                    "pdf_url": f"{self.sede_base}/preview-document/{uuid}",
                    "origen": "tablon",
                }
            )
            rows.append(row)
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board_rows(html)

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for query in (
            "urbanismo",
            "urbanistico",
            "planeamiento",
            "reparcel",
            "parcela",
            "bando",
            "entorno urban",
        ):
            try:
                posts = self._fetch_json(
                    f"{self.wp_base}/wp-json/wp/v2/posts?search={urllib.parse.quote(query)}&per_page=50"
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(posts, list):
                continue
            for post in posts:
                link = str(post.get("link") or "").strip()
                if not link or link in seen:
                    continue
                seen.add(link)
                title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                content = str((post.get("content") or {}).get("rendered") or "")
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _iso_date_wp(str(post.get("date") or "")),
                        "url": link,
                        "pdfs": self._extract_pdfs(content),
                        "origen": "wordpress_post",
                    }
                )
        return rows

    def _collect_avisos_sitemap(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            xml_text = self._fetch(AVISOS_SITEMAP)
            root = ET.fromstring(xml_text)
        except (urllib.error.URLError, ET.ParseError):
            return rows
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for url_el in root.findall("sm:url", ns):
            loc = url_el.findtext("sm:loc", default="", namespaces=ns)
            lastmod = url_el.findtext("sm:lastmod", default="", namespaces=ns)
            if not loc or loc.rstrip("/").endswith("/avisos"):
                continue
            slug = loc.rstrip("/").rsplit("/", 1)[-1]
            title = unescape(slug.replace("-", " "))
            if not RE_PROYECTO.search(title) or RE_EXCLUDE.search(title):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _iso_date_wp(lastmod) if lastmod else None,
                    "url": loc,
                    "origen": "avisos_web",
                }
            )
        return rows

    def _collect_documents_feed(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            xml_text = self._fetch(DOCUMENTS_FEED)
        except urllib.error.URLError:
            return rows
        for block in re.findall(r"<item>(.*?)</item>", xml_text, re.I | re.S):
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.I | re.S)
            link_m = re.search(r"<link>(.*?)</link>", block, re.I | re.S)
            pub_m = re.search(r"<pubDate>(.*?)</pubDate>", block, re.I | re.S)
            if not title_m or not link_m:
                continue
            title = unescape(_strip_html(title_m.group(1)))
            link = unescape(link_m.group(1).strip())
            pub = pub_m.group(1).strip() if pub_m else ""
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": _parse_rss_date(pub),
                    "url": link,
                    "origen": "documentos_web",
                }
            )
        return rows

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache.setdefault(name.upper(), f)
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache.setdefault(code_m.group(1).upper(), f)
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        if RE_EXCLUDE.search(title):
            return None

        cache = self._load_wfs_ambitos()
        candidates: list[tuple[float, str, dict[str, Any]]] = []

        for m in RE_AMBIT_CODE.finditer(title):
            code = m.group(1).upper()
            feat = cache.get(code)
            if feat:
                candidates.append((100.0, code, feat))

        parts = _sector_ilike_parts(title)
        muni = self.wfs_municipio.replace("'", "''")
        if parts:
            pattern = "%" + "%".join(p.replace("'", "''") for p in parts[:6]) + "%"
            feats = self._wfs_query(
                f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB ILIKE '{pattern}'",
                count=10,
            )
            title_low = title.lower()
            for f in feats:
                name = str((f.get("properties") or {}).get("DS_NOMB_AMB") or "")
                if not name:
                    continue
                score = sum(5 for p in parts if p.lower() in name.lower())
                if name.lower() in title_low:
                    score += 30
                candidates.append((float(score), name, f))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x[0], x[1]))
        best_score, best_name, _ = candidates[0]
        if best_score < 5:
            return None

        same_name = [
            f
            for _, name, f in candidates
            if str((f.get("properties") or {}).get("DS_NOMB_AMB") or "") == best_name
        ]
        if not same_name:
            same_name = [candidates[0][2]]

        merged = _merge_geometries(same_name)
        if not merged:
            return None

        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
            f"AND DS_NOMB_AMB='{best_name.replace(chr(39), chr(39) * 2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": best_name,
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y exposiciones públicas publicadas en sede electrónica",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación Cl@ve; no hay listado público",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/info.0"),
                "fecha_concesion": None,
                "tipo": "trámite licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites urbanísticos en sede electrónica",
                "url": f"{self.sede_base}/info.0",
                "source": "ayuntamiento",
                "nota": "Página informativa de trámite; concesiones en tablón cuando proceda",
                "origen": "sede_tramite_info",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
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
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('descripcion', '')}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or self.board_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("expediente"):
            rec["expte"] = row["expediente"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("pdfs"):
            rec["pdf_url"] = row["pdfs"][0]
        self._enrich_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_EXCLUDE.search(blob) and not re.search(
            r"(?i)exposici[oó]n p[uú]blica|informaci[oó]n p[uú]blica", blob
        ):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        cat = (row.get("categoria") or "").lower()
        if cat == "urbanismo":
            pass
        elif cat in ("ordenanzas y reglamentos", "anuncios") and not re.search(
            r"(?i)urban|licen|planeam|obra|informaci[oó]n p[uú]blica|exposici[oó]n", blob
        ):
            return None
        elif not RE_PROYECTO.search(blob):
            return None
        return self._row_to_proyecto(row)

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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(
                1
                for r in rows
                if r.get("origen") in ("sede_tablon", "sede_tramite", "sede_tramite_info")
            ),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._row_to_proyecto(item))
        for item in self._collect_avisos_sitemap():
            add(self._row_to_proyecto(item))
        for item in self._collect_documents_feed():
            add(self._row_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "wordpress_post": sum(1 for r in rows if r.get("origen") == "wordpress_post"),
            "avisos_web": sum(1 for r in rows if r.get("origen") == "avisos_web"),
            "documentos_web": sum(1 for r in rows if r.get("origen") == "documentos_web"),
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
