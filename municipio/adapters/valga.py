"""Valga planning instruments in Xunta's live AAE running-plan inventory.

This is a complete snapshot of the matching inventory rows, not a municipal
licence register or a history of all planning approvals.
"""
from __future__ import annotations

import json
import re
import ssl
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://medioambiente.xunta.gal/en-curso"
ISSUER = "https://secure.globalsign.com/cacert/gsrsaovsslca2018.crt"
PORTLET = "_aaeRunning_WAR_aae_"


def _text(node):
    return node.get_text(" ", strip=True)


def _date(value):
    return datetime.strptime(value, "%d/%m/%Y").date().isoformat() if value else None


def _official(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc != "medioambiente.xunta.gal":
        raise ValueError("Unexpected AAE source host")
    return url


def _content(html):
    soup = BeautifulSoup(html, "html.parser")
    block = soup.select_one("#aae")
    if block is None:
        raise ValueError("Missing AAE content; possible login/error page")
    # The reviewed inventory is one complete table. Fail explicitly if the
    # provider adds paging; never emit just the first page as a full snapshot.
    if soup.select('[rel~=next], .pagination, .paginacion, .paginador, .taglib-page-iterator'):
        raise ValueError("Pagination detected; crawler requires review")
    for a in block.select("a[href]"):
        if re.search(r"seguinte|siguiente|next|anterior|últim|primeir", _text(a), re.I):
            raise ValueError("Pagination detected; crawler requires review")
        if re.search(r"(?:[?&])(?:[^=&]*(?:page|cur|start))=\d+", a["href"], re.I):
            raise ValueError("Pagination detected; crawler requires review")
    return block


class ValgaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug="valga", config=None, base_url=""):
        super().__init__(slug, config, base_url or "https://www.valga.gal")

    @staticmethod
    def parse_inventory(html: str) -> list[dict[str, str]]:
        block = _content(html)
        heading = block.select_one("h2")
        if not heading or _text(heading) != "Plans en tramitación":
            raise ValueError("Unexpected running-plan inventory")
        table = block.select_one("table")
        if table is None or [_text(th) for th in table.select("th")][:2] != ["Código", "Plan ou programa"]:
            raise ValueError("Unexpected AAE inventory columns")
        found = {}
        for tr in table.select("tr"):
            cells = tr.find_all("td", recursive=False)
            if not cells:
                continue
            if len(cells) != 5:
                raise ValueError("Unexpected inventory row shape")
            title = _text(cells[1])
            if not re.search(r"\bValga\b", title, re.I):
                continue
            if not re.search(r"\b(?:plan|PXOM|planeamento)\b", title, re.I):
                raise ValueError("Unreviewed Valga instrument type")
            code = _text(cells[0])
            if not re.fullmatch(r"\d+/\d{4}", code):
                raise ValueError("Invalid AAE code")
            links = [a for a in cells[3].select("a[href]") if _text(a) == "Ver proxecto"]
            if len(links) != 1:
                raise ValueError("Missing or ambiguous instrument detail")
            url = _official(urljoin(SOURCE, links[0]["href"]))
            ids = parse_qs(urlsplit(url).query).get(PORTLET + "id", [])
            if ids != [str(int(code.split("/")[0]))]:
                raise ValueError("Detail identifier differs from inventory code")
            row = {"codigo_aae": code, "titulo": title, "url": url, "tipo_fuente": _text(cells[2])}
            if code in found and found[code] != row:
                raise ValueError("Conflicting duplicate instrument")
            found[code] = row
        if not found:
            raise ValueError("No Valga plans in current inventory; review coverage")
        return list(found.values())

    @staticmethod
    def parse_detail(html: str, item: dict[str, str]) -> dict[str, Any]:
        block = _content(html)
        fields = {}
        for p in block.select(".infoContido > p"):
            label = p.find("strong", recursive=False)
            if label:
                key = _text(label).rstrip(": ")
                label.extract()
                fields[key] = _text(p)
        if fields.get("Nome") != item["titulo"] or fields.get("Código") != item["codigo_aae"]:
            raise ValueError("Detail does not match the Valga inventory instrument")
        expediente = fields.get("Expediente", "")
        if not re.fullmatch(r"\d{4}AAE\d+", expediente):
            raise ValueError("Missing AAE expediente")
        if fields.get("Órgano promotor") not in ("", "Concello de Valga"):
            raise ValueError("Unexpected instrument promoter")
        if fields.get("Estado") != "En curso":
            raise ValueError("Instrument no longer in reviewed running state")
        docs = {}
        for a in block.select(".anexos a[href]"):
            label = _text(a)
            match = re.search(r"\s+(\d{2}/\d{2}/\d{4})$", label)
            url = _official(urljoin(item["url"], a["href"]))
            query = parse_qs(urlsplit(url).query)
            resource = query.get(PORTLET + "idCodigo")
            linked_id = query.get(PORTLET + "id")
            plan_id = str(int(item["codigo_aae"].split("/")[0]))
            if resource:
                if linked_id != [plan_id] or query.get(PORTLET + "accion") != ["descarga"]:
                    raise ValueError("Document linked to a different instrument")
            elif not urlsplit(url).path.startswith("/aaedescargas/documentos_AAE/" + plan_id + "/"):
                raise ValueError("Unexpected source document URL")
            docs[url] = {
                "titulo": label[:match.start()].strip() if match else label,
                "url": url, "url_ficha": item["url"],
                "fecha_fuente": _date(match[1]) if match else None,
                "fecha_semantica": "fecha mostrada junto al documento; no implica aprobación del plan",
            }
        if not docs:
            raise ValueError("Instrument lacks source documents")
        return {
            "id": "valga-proy-" + expediente.lower(),
            "municipio": "Valga", "provincia": "Pontevedra", "codigo_ine": "36056",
            "titulo": item["titulo"], "tipo": "planeamiento_urbanistico",
            "tipo_fuente": fields.get("Tipoloxías"), "expediente": expediente,
            "codigo_aae": item["codigo_aae"], "estado_fuente": fields["Estado"],
            "organo_promotor": fields.get("Órgano promotor") or None,
            "fase": "evaluación ambiental estratégica en tramitación",
            "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
            "fecha_inicio_consulta": _date(fields.get("Data de inicio do período de consulta")),
            "fecha_fin_consulta": _date(fields.get("Data de remate do período de consulta")),
            "url": item["url"], "url_inventario": SOURCE,
            "source": "xunta", "origen": "xunta_aae_plans_en_tramitacion",
            "documentos": list(docs.values()),
            "lat": None, "lon": None, "geometry": None, "publication_ready": False,
            "geometry_status": "No se ha extraído geometría verificada de los documentos",
        }

    def _fetch(self, url, context, capture):
        request = Request(url, headers={"User-Agent": "municipio-valga/1.0"})
        with urlopen(request, timeout=40, context=context) as response:
            if url == ISSUER:
                if response.url != ISSUER:
                    raise ValueError("Unexpected certificate issuer redirect")
            else:
                _official(response.url)
            data = response.read(5_000_001)
            if len(data) > 5_000_000:
                raise ValueError("Source exceeds response limit; snapshot aborted")
        if self.config.get("evidence_dir"):
            path = Path(self.config["evidence_dir"])
            path.mkdir(parents=True, exist_ok=True)
            (path / capture).write_bytes(data)
        return data

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        context = ssl.create_default_context()
        # Xunta omits its intermediate certificate. Fetch that public CA
        # certificate over verified HTTPS and keep root/hostname validation on.
        issuer = self._fetch(ISSUER, context, "gsrsaovsslca2018.crt")
        context.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(issuer))
        inventory = self._fetch(SOURCE, context, "en-curso.html").decode("utf-8")
        items = self.parse_inventory(inventory)
        rows = []
        for item in items:
            capture = "plan-" + item["codigo_aae"].split("/")[0] + ".html"
            html = self._fetch(item["url"], context, capture).decode("utf-8")
            rows.append(self.parse_detail(html, item))
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "publication_ready": False,
                "source_urls": [SOURCE] + [item["url"] for item in items]}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0, "reason": "No verified public register of granted licences"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
