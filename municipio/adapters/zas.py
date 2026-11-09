"""Zas physical works in the official Deputación POS+ inventory.

Full current snapshot, not a procurement feed or a licence register.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://plan-unico.dacoruna.gal/zas/"
LIMITATIONS = [
    "Only physical works listed in the Deputación POS+ Zas inventory; not all municipal projects.",
    "Fiscal years are not publication, agreement or approval dates; these dates remain null.",
    "Approval is the inventory's Obras aprobadas classification, not evidence of completion or a licence grant.",
    "No verified project geometry, administrative file numbers or individual project documents in this inventory.",
    "Municipal urbanismo page returned HTTP 403 to direct requests; its planning documents are not covered.",
]


def _norm(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _money(text):
    value = text.replace("\xa0", " ").strip()
    if not re.fullmatch(r"(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}\s*€", value):
        raise ValueError(f"Invalid POS amount: {text!r}")
    return float(value.replace(".", "").replace(",", ".").replace("€", "").strip())


class ZasAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.select_one("h1")
        if not heading or heading.get_text(" ", strip=True) != "PLAN ÚNICO Zas":
            raise ValueError("Not the Zas POS+ inventory")
        # The reviewed source renders every fiscal year in one table. Fail if
        # pagination appears rather than silently accepting its first page.
        for a in soup.select("a[href], button"):
            label = _norm(a.get_text(" ", strip=True) + " " + a.get("aria-label", ""))
            if ("next" in a.get("rel", []) or
                    re.search(r"\b(?:seguinte|siguiente|next|mais|cargar|load more)\b", label) or
                    re.search(r"[?&](?:page|pagina|offset)=|/page/", a.get("href", ""))):
                raise ValueError("Pagination requires review before extracting")
        tables = soup.select('table[aria-label="Lista de obras e investimentos"]')
        if len(tables) != 1:
            raise ValueError("Missing or ambiguous works table")
        table = tables[0]
        headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
        if headers != ["Exercicio", "Obxecto", "Orzamento", "Aportación"]:
            raise ValueError("POS+ table schema changed")
        totals = [li for li in soup.select("li")
                  if li.find("span", string="Obras aprobadas")]
        if len(totals) != 1:
            raise ValueError("Missing official total")
        count_text = totals[0].get_text(" ", strip=True)
        match = re.fullmatch(r"Obras aprobadas\s+(\d+)", count_text)
        raw_rows = table.select("tbody tr")
        if not match or not raw_rows or int(match[1]) != len(raw_rows):
            raise ValueError("Incomplete inventory: row count differs from official total")
        rows, excluded, seen = [], [], set()
        for tr in raw_rows:
            cells = tr.find_all("td", recursive=False)
            if len(cells) != 4:
                raise ValueError("Malformed POS+ row")
            year, title, budget, contribution = [c.get_text(" ", strip=True) for c in cells]
            if not re.fullmatch(r"20\d{2}", year) or not title:
                raise ValueError("Missing fiscal year or work title")
            budget, contribution = _money(budget), _money(contribution)
            key = year + ":" + _norm(title)
            if key in seen:
                raise ValueError("Ambiguous duplicate work identity")
            seen.add(key)
            norm = _norm(title)
            if norm.startswith("subministracion "):
                excluded.append({"ejercicio": int(year), "titulo": title, "reason": "equipment_supply"})
                continue
            if not re.match(r"^(?:mell|mcr\b|substitucion cespede|reforzo |aglomerado |"
                            r"aglom\.|rehabilitacion |rehab\.|instalacion de estacion depuradora |"
                            r"ensanche |capa de rodadura |acond|adec\.|rede |reparac|"
                            r"ampliacion da ponte |acceso |term acond|subs\. cespede)", norm):
                raise ValueError(f"Unreviewed inventory category: {title}")
            docs = {urljoin(SOURCE, a["href"]): a.get_text(" ", strip=True)
                    for a in cells[1].select("a[href]")}
            rows.append({
                "id": "zas-pos-" + hashlib.sha256(key.encode()).hexdigest()[:20],
                "municipio": "Zas", "codigo_ine": "15093", "provincia": "A Coruña",
                "titulo": title, "tipo": "obra_publica", "ejercicio": int(year),
                "estado_fuente": "Obras aprobadas", "presupuesto_eur": budget,
                "aportacion_diputacion_eur": contribution,
                "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None,
                "fecha_aprob": None, "url": SOURCE, "source": "diputacion",
                "organismo_fuente": "Deputación da Coruña", "origen": "inventario_pos",
                "documentos": [{"titulo": title, "url": url} for url, title in docs.items()],
                "lat": None, "lon": None, "geometry": None,
                "geometry_status": "unavailable", "publication_ready": False,
            })
        if not rows:
            raise ValueError("No usable physical works in inventory")
        return rows, {"inventory_rows": len(raw_rows), "excluded": excluded}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=40, headers={"User-Agent": "municipio-zas/1.0"})
        response.raise_for_status()
        rows, report = self.parse_inventory(response.text)
        capture = self.config.get("capture_dir")
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "pos-zas.html").write_bytes(response.content)
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": [SOURCE],
                "limitations": LIMITATIONS, **report}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh; no date-based incremental assumption.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
