"""Sariñena's public SIUa planning archive, grouped by official expediente.

The regional archive is a partial documentary inventory, not a licence register
or a statement that every historical instrument is currently in force.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ARCHIVE = "https://idearagon.aragon.es/archivoSIUa/"
SOURCE = ARCHIVE + "?CMUNIINE=22213"
LIMITATIONS = [
    "Partial SIUa documentary archive; not all municipal works or current planning are covered.",
    "Historical resolutions, including suspensions and withdrawals, are retained; presence does not establish current validity.",
    "Document links and repository identifiers are retained; PDF contents and geometries are not extracted.",
    "No verified granted-licence inventory; no coordinates or inferred dates.",
]
DATE_FIELDS = {
    "FAPRINI": "fecha_aprobacion_inicial",
    "FAPRINIPUB": "fecha_publicacion_inicial",
    "FAPRPROV": "fecha_aprobacion_provisional",
    "FACUERDO": "fecha_acuerdo",
    "FPUBACUERDO": "fecha_publicacion",
    "FAPRDEF": "fecha_aprobacion_definitiva_municipal",
    "FAPRWEB": "fecha_publicacion_aprobacion_municipal",
    "FPUBNU": "fecha_publicacion_normas",
    "FPUB_N_U": "fecha_publicacion_normas",
}


def _date(text):
    if not text:
        return None
    return datetime.strptime(text, "%d/%m/%Y").date().isoformat()


def _check_pagination(soup):
    # This archive renders the entire municipal inventory in one response.
    # Fail visibly if it ever starts advertising additional result pages.
    for link in soup.select("a[href], link[href]"):
        label = link.get_text(" ", strip=True).lower()
        href = link["href"]
        if ("next" in link.get("rel", []) or
                re.search(r"(?:siguiente|next|página\s+\d)", label) or
                re.search(r"[?&](?:page|pagina|offset|start)=", href, re.I)):
            raise ValueError("SIUa pagination changed; refusing an incomplete snapshot")


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    _check_pagination(soup)
    if not re.search(r"cmuniineSolicitado\s*=\s*'22213'", html):
        raise ValueError("SIUa response does not identify INE 22213")
    if not re.search(r"MUNICIPIO\s+SARIÑENA", soup.get_text(" ", strip=True), re.I):
        raise ValueError("SIUa response does not identify Sariñena")
    records = {}
    for td in soup.select("td[id]"):
        if not re.fullmatch(r"(?:PG|TPG|MPG|TMPG|PD|TPD|MPD|TMPD|DSU)_Exp\d+", td["id"]):
            continue
        anchor = td.find("a", href=True)
        if not anchor:
            raise ValueError("Missing expediente link")
        url = urljoin(ARCHIVE, anchor["href"])
        query = parse_qs(urlsplit(url).query)
        code = query.get("CODEXP", [""])[0]
        if urlsplit(url).netloc != urlsplit(ARCHIVE).netloc or not re.fullmatch(r"(?:CPU|COT)-22/\d{4}/\d+", code):
            raise ValueError("Unexpected official expediente identifier")
        title = anchor.get_text(" ", strip=True)
        if not title:
            raise ValueError("Missing planning title")
        record = records.setdefault(code, {
            "id": "sarinena-plan-" + hashlib.sha256(code.encode()).hexdigest()[:16],
            "municipio": "Sariñena", "provincia": "Huesca", "codigo_ine": "22213",
            "expediente": code, "titulo": title, "tipo": "instrumento de planeamiento urbanístico",
            "source": "Gobierno de Aragón - SIUa", "origen": "archivo_planeamiento",
            "url": url, "inventory_url": SOURCE, "tramitacion": [], "documentos": [],
            "lat": None, "lon": None, "geometry": None,
            "publication_ready": False, "geometry_status": "unavailable",
        })
        event = {"titulo_fuente": title, "source_row": td["id"], "url": url}
        for cell in td.parent.find_all("td", recursive=False)[1:]:
            field = cell.get("id", "").removeprefix(td["id"] + "_")
            text = cell.get_text(" ", strip=True)
            if field in DATE_FIELDS:
                event[DATE_FIELDS[field]] = _date(text)
            elif field == "ACUERDO":
                event["resolucion"] = text or None
            elif text:
                raise ValueError(f"Unknown nonempty SIUa field: {field}")
            for a in cell.select("a[href]"):
                document = {"url": urljoin(ARCHIVE, a["href"]), "campo_fuente": field,
                            "source_row": td["id"], "inventory_url": SOURCE}
                record["documentos"].append(document)
        record["tramitacion"].append(event)
    if not records:
        raise ValueError("No planning dossiers in Sariñena inventory")
    for record in records.values():
        events = record["tramitacion"]
        latest = max(events, key=lambda e: e.get("fecha_acuerdo") or "")
        municipal = [e for e in events if e.get("fecha_aprobacion_definitiva_municipal")]
        record.update({
            "fecha": None,
            "fecha_acuerdo": latest.get("fecha_acuerdo"),
            "fecha_publicacion": latest.get("fecha_publicacion"),
            "fase": latest.get("resolucion"),
            "fecha_aprob": max(e["fecha_aprobacion_definitiva_municipal"] for e in municipal) if municipal else (
                latest.get("fecha_acuerdo") if (latest.get("resolucion") or "").startswith("Aprobar definitivamente") else None),
            "descripcion": "Inventario documental histórico SIUa; consultar tramitación y documentos para cada resolución. La inclusión no acredita vigencia actual.",
        })
    return list(records.values())


def parse_documents(html: str, code: str, detail_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    _check_pagination(soup)
    if f"codExpSolicitadoFicha = '{code}'" not in html or "hayDatosMunicipio=true" not in html:
        raise ValueError(f"Unrecognized SIUa detail response for {code}")
    documents = {}
    # Read data literals only; never execute the website's JavaScript.
    quoted = r"'((?:\\.|[^'\\])*)'"
    pattern = re.compile(r"\s*,\s*".join([quoted] * 7 + ["codExpSolicitado", quoted]))
    for call in re.findall(r"\baddDoc\((.*?)\);", html, re.S):
        match = pattern.fullmatch(call.strip())
        if not match:
            raise ValueError("SIUa document declaration format changed")
        values = [v.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\") for v in match.groups()]
        _, docid, jpg, mini, world, metadata, title, category = values
        if not re.fullmatch(r"[0-9a-f]{16}", docid):
            raise ValueError("Invalid SIUa repository document identifier")
        documents[docid] = {
            "repository_id": docid, "titulo": title, "categoria": category,
            "url": detail_url, "provenance": "SIUa addDoc declaration",
            "related_repository_ids": {k: v for k, v in {
                "jpg": jpg, "thumbnail": mini, "world_file": world, "metadata": metadata}.items() if v},
        }
    return list(documents.values())


class SarinenaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug="sarinena", config=None, base_url=""):
        super().__init__(slug, config, base_url or SOURCE)

    def _fetch(self, url, capture_name):
        response = requests.get(url, timeout=40, headers={
            "User-Agent": "municipio-sarinena/1.0 (public planning inventory)"})
        response.raise_for_status()
        if urlsplit(response.url).hostname != urlsplit(ARCHIVE).hostname:
            raise ValueError("Unexpected SIUa redirect")
        if len(response.content) > 5_000_000:
            raise ValueError("SIUa response exceeds 5 MB; snapshot refused")
        if self.config.get("capture_dir"):
            folder = Path(self.config["capture_dir"])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / capture_name).write_bytes(response.content)
        return response.content.decode("utf-8-sig")

    def backfill_proyectos(self, out_jsonl: Path):
        rows = parse_inventory(self._fetch(SOURCE, "inventory.html"))
        sources = [SOURCE]
        for row in rows:
            url = row["url"]
            html = self._fetch(url, "detail-" + row["expediente"].replace("/", "-") + ".html")
            docs = parse_documents(html, row["expediente"], url)
            row["documentos"].extend(docs)
            row["repository_document_count"] = len(docs)
            sources.append(url)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return {"status": "ok", "rows": len(rows), "source_urls": sources,
                "limitations": LIMITATIONS, "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {"status": "disabled", "rows": 0,
                "reason": "No verified granted-licence register; application forms excluded"}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
