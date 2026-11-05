from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records
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

WEB_BASE = "https://www.amposta.cat"
SEDE_BASE = "https://seu.amposta.cat"
GEOPORTAL_URL = "https://geoportal.amposta.cat/geoportal/"
MUC_VISOR = "https://dtes.gencat.cat/muc-visor/AppJava/home.do?municipi=43009&set-locale=ca"
MUNICIPIO = "Amposta"
ID_PREFIX = "amposta"
COD_INE_MUN = "43009"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"

POUM_TABS: list[tuple[str, str]] = [
    ("poum", f"{WEB_BASE}/planejament_v1.asp?i=ca&nv1=1"),
    ("desenvolupament", f"{WEB_BASE}/planejament_v1.asp?i=ca&nv1=2"),
    ("modificacions", f"{WEB_BASE}/planejament_v1.asp?i=ca&nv1=3"),
    ("correccio", f"{WEB_BASE}/planejament_v1.asp?i=ca&nv1=4"),
]

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "llicència urbanística",
    "llicencia urbanística",
    "llicència d'obra",
    "licencia de obra",
    "comunicació prèvia",
    "comunicacion previa",
    "declaració responsable",
    "certificat urbanístic",
    "certificado urbanístico",
    "consultes urbanístiques",
    "control geomètric",
    "replanteig",
)

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó] responsable|autoritzaci[oó]|obra major|obra menor|primera ocupaci[oó])",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|poum|pgou|pgom|conveni|informaci[oó] p[uú]blica|"
    r"expedient|projecte|proyecto|modificaci[oó]|reparcel|sector|reurbanitz|"
    r"aprobaci[oó]|aprovaci[oó]|peu|ppu|pmu|bopt|pol[ií]gon|exposici[oó])",
)
RE_NOISE = re.compile(
    r"(?i)(proc[eé]s selectiu|oferta p[uú]blica|subvenci[oó]|pressupost|pce-psc|"
    r"empresa municipal|junta de govern)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOPT = re.compile(r"\bbopt\s+(\d{1,2})\.(\d{1,2})\.(\d{4})", re.I)
RE_PDF = re.compile(r'href=[\'"]([^\'"]+\.pdf[^\'"]*)[\'"]', re.I)
RE_EXPEDIENTE = re.compile(
    r"(?i)(?:PEU|PPU|PMU|POUM)[\s\-_/]*([A-Z0-9][A-Z0-9_\-\s]{2,40})|"
    r"(\d{1,4}/\d{4}[A-Z]?)|"
    r"(PCE-PSC\s*\d+/\d{4})",
)
RE_TABLON_PROY = re.compile(
    r"(?i)(reurbanitz|reurbaniz|planej|urban[ií]stic|poum|peu|ppu|pmu|"
    r"modificaci[oó].*poum|bopt|pol[ií]gon|sector\s|actuaci[oó].*urban)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_BOPT.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _fecha_from_pub_date(pub: dict[str, Any] | None) -> str | None:
    if not isinstance(pub, dict):
        return None
    try:
        return datetime(
            int(pub["year"]),
            int(pub["month"]),
            int(pub["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _proyecto_tipo(section: str, titulo: str, estado: str) -> str:
    blob = f"{section} {titulo} {estado}".lower()
    if "pla parcial" in blob or "ppu" in blob:
        return "plan parcial"
    if "pla especial" in blob or " peu" in blob or blob.startswith("peu"):
        return "plan especial"
    if "modificaci" in blob or "pmu" in blob:
        return "modificación POUM"
    if "reurbanitz" in blob or "reurbaniz" in blob:
        return "reurbanización"
    if "desenvolupament" in blob or "desarrollo" in blob:
        return "desarrollo POUM"
    if "correcci" in blob:
        return "corrección erratas POUM"
    if "poum" in blob or "ordenació" in blob:
        return "POUM"
    if "informaci" in blob:
        return "información pública"
    return "planeamiento"


class AmpostaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web amposta.cat (POUM) + sede STA (tablón/catálogo) + geoportal Nexus/enMapa (sin API bulk)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.geoportal_url = str(self.config.get("geoportal_url") or GEOPORTAL_URL)
        self.muc_visor = str(self.config.get("muc_visor") or MUC_VISOR)
        self.poum_tabs = [tuple(x) for x in (self.config.get("poum_tabs") or POUM_TABS)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_sede_ssl: bool = False, timeout: float = 90) -> str:
        time.sleep(self.delay_s)
        ctx = self._ssl_ctx if use_sede_ssl or self.sede_base in url else None
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-amposta/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO"
        )

    def _tablon_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL, use_sede_ssl=True, timeout=120)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_html(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_pub_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "extern": str(item.get("externString") or ""),
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _catalog_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL, use_sede_ssl=True, timeout=120)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            dboid = str(item.get("dboid") or "")
            name = _clean_html(str(item.get("name") or ""))
            if not name or not dboid:
                continue
            rows.append(
                {
                    "titulo": name[:500],
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    @staticmethod
    def _parse_poum_table(html: str) -> list[tuple[str, str, str]]:
        if "<tbody>" in html:
            chunk = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        else:
            chunk = html
        rows: list[tuple[str, str, str]] = []
        for part in re.split(r"<tr><td>", chunk, flags=re.I)[1:]:
            cells = re.split(r"</td><td>", part, maxsplit=2, flags=re.I)
            if len(cells) < 2:
                continue
            titulo = _clean_html(cells[0])
            estado = _clean_html(re.split(r"</td>", cells[1], maxsplit=1, flags=re.I)[0])
            docs = cells[2] if len(cells) > 2 else ""
            if titulo and len(titulo) >= 8:
                rows.append((titulo, estado, docs))
        return rows

    @staticmethod
    def _expediente_from_text(*parts: str) -> str | None:
        blob = " ".join(p for p in parts if p)
        m = RE_EXPEDIENTE.search(blob)
        if not m:
            return None
        for g in m.groups():
            if g and re.search(r"\d", g):
                return re.sub(r"\s+", " ", g.strip())[:80]
        return None

    def _collect_poum_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for section, page_url in self.poum_tabs:
            try:
                html = self._fetch(page_url, timeout=60)
            except urllib.error.URLError:
                continue
            for titulo, estado, docs_raw in self._parse_poum_table(html):
                if re.match(r"^\d{2,3}\.\s", titulo):
                    continue
                if not re.search(
                    r"(?i)(resolt|tràmit|tramit|refòs|refos|provisional|definitiva|en curs)",
                    estado,
                ):
                    continue
                if len(titulo) < 12:
                    continue
                pdfs = RE_PDF.findall(docs_raw)
                pdf_url = pdfs[0] if pdfs else None
                if pdf_url and pdf_url.startswith("/"):
                    pdf_url = urllib.parse.urljoin(f"{self.web_base}/", pdf_url)
                elif pdf_url and not pdf_url.startswith("http"):
                    pdf_url = urllib.parse.urljoin(page_url, pdf_url)
                fecha = None
                for pdf in pdfs:
                    fecha = _parse_fecha_dmy(_clean_html(pdf)) or _parse_fecha_dmy(pdf)
                    if fecha:
                        break
                key = f"{section}|{titulo}|{estado}"
                expte = self._expediente_from_text(titulo, estado) or f"POUM-{section}-{titulo[:40]}"
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": f"{titulo} — {estado}"[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(section, titulo, estado),
                    "url": pdf_url or page_url,
                    "source": "ayuntamiento",
                    "origen": "poum_web",
                    "estado": estado[:200],
                    "expediente": expte,
                    "seccion_poum": section,
                    "geoportal_url": self.geoportal_url,
                }
                if pdf_url:
                    rec["pdf_url"] = pdf_url
                rows.append(rec)
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('extern', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("dboid") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / anuncio obra",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        low = titulo.lower()
        if not any(p in low for p in LICENCIA_TRAMITE_PATTERNS) and not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia urbanística",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Tràmit informatiu del catàleg SEU; sense llistat de concessions",
            "origen": row.get("origen"),
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('extern', '')}"
        if not RE_TABLON_PROY.search(blob):
            return None
        if RE_NOISE.search(blob) and not RE_TABLON_PROY.search(blob):
            return None
        expte = self._expediente_from_text(titulo) or f"TAB-{row.get('dboid', '')}"
        return {
            "id": _stable_id("proy", row.get("dboid") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo("", titulo, ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_sta",
            "expediente": expte,
            "geoportal_url": self.geoportal_url,
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
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
        info = {
            "id": _stable_id("lic", TABLON_URL),
            "fecha_concesion": None,
            "tipo": "tablón edictos",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": "Tauler d'anuncis i edictes — SEU Amposta",
            "url": TABLON_URL,
            "source": "ayuntamiento",
            "nota": "Anuncis STA; consulta d'expedients privada requereix VÀLid",
            "origen": "sede_tablon",
        }
        rows.append(info)
        seen.add(info["id"])
        for item in self._tablon_rows():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._catalog_rows():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats["rows"]
        state_path.parent.mkdir(parents=True, exist_ok=True)
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

        for rec in self._collect_poum_rows():
            add(rec)
        for item in self._tablon_rows():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "poum": sum(1 for r in rows if r.get("origen") == "poum_web"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "cod_ine_mun": COD_INE_MUN,
            "geoportal": self.geoportal_url,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
