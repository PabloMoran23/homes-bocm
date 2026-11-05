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

WEB_BASE = "https://www.guixols.cat"
SEU_BASE = "https://ciutadania.guixols.cat"
MUNICIPIO = "Sant Feliu de Guíxols"
ID_PREFIX = "sant-feliu-de-guixols"
INE_MUN = "17160"
IDENS = "1716090004"

EXPEDIENTS_API = f"{SEU_BASE}/administrar/pagina/agafar_expedients"
TRAMITS_PAGE = f"{SEU_BASE}/tramits"
POUM_INDEX = f"{SEU_BASE}/poum"
POUM_VIGENT = f"{SEU_BASE}/poum/vigent"
ETAULER_URL = f"https://tauler.seu.cat/inici.do?idens={IDENS}"
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
RPUC_MUNICI = (
    f"https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    f"?reqCode=cerca&municipiSel={INE_MUN}"
)

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia d.?obres|comunicaci[oó] pr[eè]via.*obra|obra[s]?(?:\s|$)|"
    r"autoritzaci[oó].*via p[uú]blica.*obra|primera utilitzaci[oó]|enderroc|"
    r"disciplina urban[ií]stica|parcel·laci[oó])",
)
RE_LICENCIA_SKIP = re.compile(
    r"(?i)(circulaci[oó]|conducci[oó]|veh[ií]cul|mercat|activitat econ[oò]mica|"
    r"subvenci[oó]|bonificaci[oó].*impost)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|poum|pgou|projecte.*urban|urbanitz|endegament|reparcel|"
    r"sector|taxaci[oó]|gesti[oó] urban|informaci[oó] p[uú]blica|exposici[oó]|"
    r"modificaci[oó].*poum|pla parcial|instrument.*gesti)",
)
RE_EXPEDIENT_EXCLUDE = re.compile(
    r"(?i)(subvenci[oó]|pressupost|jurat popular|adhesi[oó].*consorci|"
    r"campanya del pla|mobilitat el[eè]ctrica|llumin[aà]ries|platges|"
    r"programa d.incentius|plagues urbanes|basses per fauna|lleres trams)",
)
RE_TRAMIT_PATH = re.compile(r"/tramit/([^\"'\s<>]+)", re.I)
RE_NOTICIA_PATH = re.compile(r'href="(/noticies/[^"#?]+)"', re.I)
RE_NOTICIA_URBAN = re.compile(
    r"(?i)(poum|urban|planej|riera|sector|taxaci|urbanitz|gesti[oó]\s+urban|"
    r"endegament|cobriment.*riera|modificaci[oó].*poum|ordenaci[oó]\s+urban)",
)
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "poum" in n or "pla d'ordenaci" in n:
        return "POUM"
    if "taxaci" in n and "sector" in n:
        return "taxación conjunta / gestión urbanística"
    if "urbanitz" in n or "endegament" in n:
        return "urbanización / obra pública"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "projecte" in n and ("monestir" in n or "pavell" in n):
        return "proyecto de equipamiento"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    return "planeamiento urbanístico"


class SantFeliuDeGuixolsAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla guixols.cat + seu ciutadania (API expedients/tràmits) + e-TAULER AOC."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seu_base = str(self.config.get("seu_base") or SEU_BASE).rstrip("/")
        self.max_expedient_pages = int(self.config.get("max_expedient_pages", 25))
        self.ua = str(self.config.get("user_agent") or "poc-bocm-sant-feliu-de-guixols/1.0")

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_maybe(self, url: str) -> str | None:
        try:
            return self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError):
            return None

    def _post_json(self, url: str, data: dict[str, str]) -> Any:
        time.sleep(self.delay_s)
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "User-Agent": self.ua,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="replace").strip()
        if not raw:
            return {}
        return json.loads(raw)

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _expedient_row(self, item: dict[str, Any]) -> dict[str, Any] | None:
        nom = _clean(str(item.get("NOM") or ""))
        if len(nom) < 12:
            return None
        if RE_EXPEDIENT_EXCLUDE.search(nom):
            return None
        if not (RE_PROYECTO.search(nom) or re.search(r"(?i)projecte d.?obres|separata del projecte", nom)):
            return None
        exp_id = str(item.get("ID") or "")
        num = str(item.get("NUM_EXPEDIENT") or "").strip()
        url = f"{self.seu_base}/expedient/{exp_id}" if exp_id else f"{self.seu_base}/expedients"
        fecha = str(item.get("DATA_INICIAL") or item.get("DATA_FINAL") or "")[:10] or None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{exp_id}:{num}:{nom}"),
            "municipio": MUNICIPIO,
            "titulo": nom[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(nom),
            "url": url,
            "source": "ayuntamiento",
            "origen": "ciutadania_expedients_api",
        }
        if num:
            rec["expediente"] = num
        return rec

    def _collect_expedients_api(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        total_pages = self.max_expedient_pages
        for pag in range(1, total_pages + 1):
            payload = self._post_json(EXPEDIENTS_API, {"pag_num": str(pag)})
            if not isinstance(payload, dict) or not payload:
                break
            meta = payload.get("999")
            if isinstance(meta, list) and meta and pag == 1:
                try:
                    total_pages = min(int(meta[0]), self.max_expedient_pages)
                except (TypeError, ValueError):
                    pass
            for key, val in payload.items():
                if key == "999" or not isinstance(val, dict):
                    continue
                rec = self._expedient_row(val)
                if not rec or rec["id"] in seen:
                    continue
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _static_proyecto_refs(self) -> list[dict[str, Any]]:
        refs: list[tuple[str, str, str]] = [
            (POUM_VIGENT, "POUM vigent — documentació i normativa", "POUM"),
            (POUM_INDEX, "Pla d'Ordenació Urbanística Municipal (índex)", "POUM"),
            (RPUC_MUNICI, "RPUC — Registre de planejament urbanístic de Catalunya", "referencia cartográfica"),
            (MUC_VISOR, "Visor MUC cartografia urbanística (Generalitat)", "referencia cartográfica"),
            (ETAULER_URL, "Tauler d'edictes electrònic (e-TAULER AOC)", "información pública"),
        ]
        out: list[dict[str, Any]] = []
        for url, titulo, tipo in refs:
            out.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": None,
                    "tipo": tipo,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "referencia_portal",
                }
            )
        return out

    def _collect_joomla_noticies(self) -> list[dict[str, Any]]:
        html = self._fetch_maybe(f"{self.web_base}/noticies")
        if not html:
            html = self._fetch_maybe(self.web_base)
        if not html:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in RE_NOTICIA_PATH.findall(html):
            if path in seen:
                continue
            blob = path.replace("-", " ")
            if not RE_NOTICIA_URBAN.search(blob):
                continue
            seen.add(path)
            url = urllib.parse.urljoin(f"{self.web_base}/", path)
            titulo = _clean(path.split("/")[-1].replace("-", " "))
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": None,
                    "tipo": _proyecto_tipo(titulo),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "guixols_joomla_noticia",
                }
            )
        return rows

    def _merge_proyectos(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            rid = row.get("id") or _stable_id("proy", row.get("url", ""))
            by_id[rid] = row
        return list(by_id.values())

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._collect_expedients_api())
        rows.extend(self._static_proyecto_refs())
        rows.extend(self._collect_joomla_noticies())
        return self._merge_proyectos(rows)

    def _tramit_title_from_path(self, path: str) -> str:
        slug = path.rsplit("_", 1)[0] if "_" in path else path
        return _clean(slug.replace("-", " ").replace("_", " "))

    def _collect_licencias(self) -> list[dict[str, Any]]:
        html = self._fetch_maybe(TRAMITS_PAGE)
        if not html:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in RE_TRAMIT_PATH.findall(html):
            full = f"{self.seu_base}/tramit/{path}"
            if full in seen:
                continue
            titulo = self._tramit_title_from_path(path)
            if RE_LICENCIA_SKIP.search(titulo):
                continue
            if not RE_LICENCIA.search(titulo):
                continue
            seen.add(full)
            rows.append(
                {
                    "id": _stable_id("lic", full),
                    "fecha_concesion": None,
                    "tipo": titulo[:200],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": full,
                    "source": "ayuntamiento",
                    "origen": "ciutadania_tramits_catalog",
                }
            )
        if not rows:
            rows.append(
                {
                    "id": _stable_id("lic", TRAMITS_PAGE),
                    "fecha_concesion": None,
                    "tipo": "Catàleg de tràmits — Urbanisme (seu ciutadania)",
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": TRAMITS_PAGE,
                    "source": "ayuntamiento",
                    "origen": "tramites_informativos",
                }
            )
        return rows

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
