from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records

import hashlib
import http.cookiejar
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

WEB_BASE = "https://www.concellodemarin.es"
SEDE_BASE = "https://sede.concellodemarin.es"
MUNICIPIO = "Marín"
ID_PREFIX = "marin"
INE = "36037"

WP_URBANISMO_CAT = 10
WP_POSTS_API = f"{WEB_BASE}/wp-json/wp/v2/posts"

URBANISMO_WEB = f"{WEB_BASE}/urbanismo/"
PXOM_WEB = f"{WEB_BASE}/urbanismo/pxom/"
EDICTOS_WEB = f"{WEB_BASE}/edictos/"
IMPRESOS_WEB = f"{WEB_BASE}/impresos-oficiais/"
OFICINA_ARI = f"{WEB_BASE}/urbanismo/oficina-ari/"

SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_QUERY_DOC = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"
SIOTUGA_URB = "https://siotuga.xunta.gal/siotuga/urb?lang=es_ES"
SIOTUGA_VISOR = "https://siotuga.xunta.gal/siotuga/visor"

DEFAULT_LICENCIA_TRAMITES: list[tuple[str, str]] = [
    ("Solicitude licenza urbanística — impresos oficiais", IMPRESOS_WEB),
    ("Comunicación previa de obras — impresos oficiais", IMPRESOS_WEB),
    ("Solicitude licenza primeira ocupación — impresos oficiais", IMPRESOS_WEB),
    ("Tasas urbanismo (impreso PDF)", f"{WEB_BASE}/wp-content/uploads/2015/12/IMPRESO-TASAS-URBANISMO.pdf"),
    ("Sede electrónica — trámites con certificado / Cl@ve", SEDE_BASE),
    ("Oficina ARI — documentación obras menores e axudas", OFICINA_ARI),
]

RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_PROYECTO = re.compile(
    r"(?i)(pxom|plan especial|planeam|proxecto de urban|peid|peri|reparcel|"
    r"exposici[oó]n|informaci[oó]n p[uú]blica|aprobaci|modificaci[oó]n puntual|"
    r"casco|pmus|estudo de detalle|solo urban|entidade urban|ari\b|instrumento)",
)
RE_EXCLUDE_PROY = re.compile(
    r"(?i)(orzamento|axuda|rehabilit|pavillon|rua |estrada|incendio|monte|"
    r"xornada|sede electr|administraci[oó]n dixital|luminaria|led|vial de|"
    r"repint|marcas viarias|pavimentaci[oó]n|demolici[oó]n mercado|torre do reloxo|"
    r"canota|instalaci[oó]n deportiva|participaci[oó]n pública sin plan)",
)
RE_LICENCIA = re.compile(
    r"(?i)(licen|licenz|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"primeira ocupaci|obra menor)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(titulo: str, figura: str | None = None) -> str:
    blob = f"{titulo} {figura or ''}".lower()
    if "plan especial" in blob or "pep" in blob:
        return "plan especial"
    if "pmus" in blob:
        return "PMUS"
    if "estudo de detalle" in blob or "estudio de detalle" in blob:
        return "estudio de detalle"
    if "pxom" in blob or "plan xeral" in blob:
        return "PXOM"
    if "plan parcial" in blob or "peri" in blob:
        return "plan parcial"
    if "modificaci" in blob and "puntual" in blob:
        return "modificación puntual PXOM"
    if "informaci" in blob or "exposici" in blob or "participaci" in blob:
        return "información pública"
    if "aprobaci" in blob:
        return "aprobación planeamiento"
    if "solo " in blob:
        return "clasificación / solo"
    return "planeamiento"


class MarinAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress concellodemarin.es + sede ASP.NET + inventario SIOTUGA (INE 36037)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.max_wp_pages = int(self.config.get("max_wp_pages", 4))
        self.max_siotuga_des = int(self.config.get("max_siotuga_desarrollo", 80))
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
        self._siotuga_token_cache: str | None = None

    def _fetch(
        self,
        url: str,
        *,
        data: bytes | None = None,
        charset: str | None = None,
        timeout: float = 90,
    ) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-marin/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            req = urllib.request.Request(url, data=data, headers=headers)
        else:
            req = urllib.request.Request(url, headers=headers)
        with self._opener.open(req, timeout=timeout) as resp:
            enc = charset or resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(enc, errors="replace")

    def _collect_wp_urbanismo(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in range(1, self.max_wp_pages + 1):
            q = urllib.parse.urlencode(
                {
                    "categories": str(WP_URBANISMO_CAT),
                    "per_page": "100",
                    "page": str(page),
                    "_fields": "date,link,title",
                }
            )
            url = f"{WP_POSTS_API}?{q}"
            try:
                raw = self._fetch(url, timeout=60)
            except urllib.error.URLError:
                break
            try:
                posts = json.loads(raw)
            except json.JSONDecodeError:
                break
            if not isinstance(posts, list) or not posts:
                break
            for post in posts:
                titulo = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                if not titulo or RE_EXCLUDE_PROY.search(titulo):
                    continue
                if not RE_PROYECTO.search(titulo):
                    continue
                fecha = str(post.get("date") or "")[:10] or None
                link = str(post.get("link") or self.web_base)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": fecha,
                        "url": link,
                        "tipo": _proyecto_tipo(titulo),
                        "origen": "web_wp_urbanismo",
                        "wp_post": True,
                    }
                )
            if len(posts) < 100:
                break
        return rows

    def _get_siotuga_token(self) -> str:
        if self._siotuga_token_cache:
            return self._siotuga_token_cache
        html = self._fetch(SIOTUGA_INVENTARIO, charset="utf-8")
        m = re.search(r"name=['\"]token['\"][^>]*value=['\"]([^'\"]+)['\"]", html, re.I)
        if not m:
            m = re.search(r"id=['\"]token['\"][^>]*value=['\"]([^'\"]+)['\"]", html, re.I)
        if not m:
            raise RuntimeError("SIOTUGA: no se encontró token de sesión")
        self._siotuga_token_cache = m.group(1)
        return self._siotuga_token_cache

    def _siotuga_query(self, idclase: int) -> list[dict[str, Any]]:
        token = self._get_siotuga_token()
        data = f"id={INE}&token={token}&idclase={idclase}".encode()
        raw = self._fetch(SIOTUGA_QUERY_DOC, data=data, charset="utf-8")
        if raw.strip().startswith("tokenIncorrecto"):
            self._siotuga_token_cache = None
            return []
        try:
            docs = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return docs if isinstance(docs, list) else []

    def _collect_siotuga(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for doc in self._siotuga_query(14):
            nome = str(doc.get("docnome") or "Plan xeral")
            rows.append(
                {
                    "titulo": nome,
                    "fecha": doc.get("fechaaddef"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo(nome, str(doc.get("figura") or "")),
                    "origen": "siotuga_pg",
                    "siotuga_id": doc.get("id"),
                    "figura": doc.get("figura"),
                }
            )
        for doc in self._siotuga_query(13)[: self.max_siotuga_des]:
            nome = str(doc.get("docnome") or "Instrumento de planeamiento")
            rows.append(
                {
                    "titulo": nome,
                    "fecha": doc.get("fechaaddef"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo(nome, str(doc.get("figura") or "")),
                    "origen": "siotuga_des",
                    "siotuga_id": doc.get("id"),
                    "figura": doc.get("figura"),
                }
            )
        return rows

    def _fixed_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Urbanismo — Concello de Marín",
                "fecha": None,
                "url": URBANISMO_WEB,
                "tipo": "información urbanismo",
                "origen": "web_urbanismo",
            },
            {
                "titulo": "PXOM — Concello de Marín",
                "fecha": "2012-11-02",
                "url": PXOM_WEB,
                "tipo": "PXOM",
                "origen": "web_pxom",
            },
            {
                "titulo": "Edictos municipais",
                "fecha": None,
                "url": EDICTOS_WEB,
                "tipo": "edictos",
                "origen": "web_edictos",
            },
            {
                "titulo": f"Inventario planeamento — SIOTUGA (INE {INE})",
                "fecha": None,
                "url": SIOTUGA_INVENTARIO,
                "tipo": "inventario planeamiento",
                "origen": "siotuga_inventario",
            },
            {
                "titulo": "Estado planeamento municipal — SIOTUGA / Xunta",
                "fecha": None,
                "url": SIOTUGA_URB,
                "tipo": "planeamiento vigente",
                "origen": "siotuga_urb",
            },
            {
                "titulo": "Visor cartográfico SIOTUGA",
                "fecha": None,
                "url": SIOTUGA_VISOR,
                "tipo": "visor planeamiento",
                "origen": "siotuga_visor",
            },
            {
                "titulo": "Sede electrónica — rexistro e trámites",
                "fecha": None,
                "url": self.sede_base,
                "tipo": "sede electrónica",
                "origen": "sede_portal",
            },
        ]

    def _licencia_tramites(self) -> list[dict[str, Any]]:
        return [
            {"titulo": title, "url": url, "origen": "web_tramite_info"}
            for title, url in DEFAULT_LICENCIA_TRAMITES
        ]

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.web_base
        rec: dict[str, Any] = {
            "id": _stable_id(
                "proy",
                f"{url}|{titulo}|{row.get('siotuga_id','')}|{row.get('fecha','')}",
            ),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(titulo, row.get("figura")),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("siotuga_id"):
            rec["siotuga_doc_id"] = row["siotuga_id"]
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.web_base
        return {
            "id": _stable_id("lic", url + titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite / información urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def _collect_proyecto_sources(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._fixed_seeds())
        rows.extend(self._collect_siotuga())
        rows.extend(self._collect_wp_urbanismo())
        return rows

    def _collect_licencia_sources(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._licencia_tramites())
        for item in self._collect_wp_urbanismo():
            if RE_LICENCIA.search(item.get("titulo") or ""):
                rows.append({**item, "origen": "web_wp_licencia"})
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._collect_licencia_sources():
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "web_impresos_sede_info"}

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
        for item in self._collect_proyecto_sources():
            rec = self._to_proyecto(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
            "web_wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("web_wp")),
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
