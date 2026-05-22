from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WP_BASE = "https://www.getafe.es"
SEDE_BASE = "https://sede.getafe.es"
GOBIERTO_BASE = "https://gobiernoabierto.getafe.es"

TABLON_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
INFO_PUBLICA_URL = (
    f"{GOBIERTO_BASE}/s/portal-de-transparencia/"
    "documentos-municipales-sometidos-a-informacion-publica-en-legislacion-sectorial"
)
CONVENIOS_URL = f"{GOBIERTO_BASE}/s/portal-de-transparencia/convenios-urbanisticos"
URBANISTICAS_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_URBANISTICAS"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable.*obra|autorizaci[oó]n previa)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expropi|reparcel|entidad urban|estudio de detalle|"
    r"modificaci[oó]n puntual|aprobaci[oó]n (?:inicial|definitiva)|ordenanza urban)",
)
RE_FECHA_ES = re.compile(
    r"(\d{1,2})\s+de\s+"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
    r"\s+de\s+(\d{4})",
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"getafe-{prefix}-{h}"


def _parse_fecha_es(text: str) -> str | None:
    m = RE_FECHA_ES.search(text or "")
    if m:
        try:
            d = datetime(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1)))
            return d.strftime("%Y-%m-%d")
        except (ValueError, KeyError):
            pass
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            d = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return d.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        y, mo, d = int(obj["year"]), int(obj["month"]), int(obj["day"])
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


class GetafeAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA (tablón JSON embebido) + portal Gobierto (IP y convenios)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.5))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-getafe/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.getafe.es" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
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
        html = self._fetch(TABLON_URL, use_sede_ssl=True)
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _tablon_row_to_record(self, row: dict[str, Any]) -> tuple[str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or rem.get("code") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        url = f"{TABLON_URL}#dboid={dboid}"
        return title, remitente, fecha, url

    def _fetch_gobierto_docs(self, page_url: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in re.finditer(r"/docs/(\d+)", html):
            doc_id = m.group(1)
            if doc_id in seen:
                continue
            seen.add(doc_id)
            idx = m.start()
            ctx = html[max(0, idx - 1200) : idx + 100]
            ctx_plain = re.sub(r"<[^>]+>", " ", ctx)
            ctx_plain = unescape(re.sub(r"\s+", " ", ctx_plain)).strip()
            titulo_m = re.search(
                r"((?:Convenio|Aprobación|Expediente|Modificación|Certificado|Informe)[^.]{10,200})",
                ctx_plain,
                re.I,
            )
            titulo = titulo_m.group(1).strip() if titulo_m else f"Documento portal {doc_id}"
            fecha = _parse_fecha_es(ctx_plain) or ""
            pdf_url = f"{GOBIERTO_BASE}/docs/{doc_id}"
            records.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "doc_id": doc_id,
                }
            )
        return records

    def _fetch_convenios(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CONVENIOS_URL)
        except urllib.error.URLError:
            return []
        records: list[dict[str, Any]] = []
        current_ambito = ""
        for m in re.finditer(r"<h[23][^>]*>([^<]+)</h[23]>", html, re.I):
            current_ambito = unescape(m.group(1).strip())
        # PDFs with nearby ambito from preceding h3
        parts = re.split(r"<h[23][^>]*>", html, flags=re.I)
        for part in parts[1:]:
            hm = re.match(r"([^<]+)</h[23]>", part)
            ambito = unescape(hm.group(1).strip()) if hm else ""
            for pdf_m in re.finditer(r'href="(https?://[^"]+\.pdf[^"]*)"', part, re.I):
                pdf = pdf_m.group(1)
                name = unescape(urllib.parse.unquote(Path(pdf).name))[:200]
                titulo = f"{ambito}: {name}" if ambito else name
                records.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _parse_fecha_es(part) or "",
                        "url": CONVENIOS_URL,
                        "pdf_url": pdf,
                        "tipo": "convenio urbanístico",
                    }
                )
        return records

    def _title_to_licencia(self, title: str, url: str, fecha: str, pdf_url: str | None = None) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha or None,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        return rec

    def _title_to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str,
        tipo: str = "urbanismo",
        pdf_url: str | None = None,
    ) -> dict[str, Any] | None:
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", pdf_url or url),
            "municipio": "Getafe",
            "titulo": title[:500],
            "fecha": fecha or None,
            "tipo": tipo,
            "url": url,
            "source": "ayuntamiento",
        }
        if pdf_url:
            rec["pdf_url"] = pdf_url
        return rec

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for item in self._collect_tablon():
            title, _, fecha, url = self._tablon_row_to_record(item)
            rec = self._title_to_licencia(title, url, fecha)
            if rec:
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tablon"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for item in self._collect_tablon():
            title, _, fecha, url = self._tablon_row_to_record(item)
            rec = self._title_to_licencia(title, url, fecha)
            if rec and rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            title, rem, fecha, url = self._tablon_row_to_record(item)
            blob = f"{title} {rem}"
            tipo = "acuerdo plenario" if re.search(r"(?i)pleno", blob) else "urbanismo"
            add(self._title_to_proyecto(title, url, fecha, tipo=tipo))

        for doc in self._fetch_gobierto_docs(INFO_PUBLICA_URL):
            titulo = doc["titulo"]
            if RE_PROYECTO.search(titulo) or "convenio" in titulo.lower() or "suelo" in titulo.lower():
                add(
                    self._title_to_proyecto(
                        titulo,
                        doc["url"],
                        doc["fecha"],
                        tipo="información pública",
                        pdf_url=doc["pdf_url"],
                    )
                )

        for conv in self._fetch_convenios():
            add(
                self._title_to_proyecto(
                    conv["titulo"],
                    conv["url"],
                    conv.get("fecha") or "",
                    tipo=conv.get("tipo", "convenio urbanístico"),
                    pdf_url=conv.get("pdf_url"),
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_rows": len(self._collect_tablon()),
            "gobierto_docs": len(self._fetch_gobierto_docs(INFO_PUBLICA_URL)),
            "convenios": len(self._fetch_convenios()),
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
