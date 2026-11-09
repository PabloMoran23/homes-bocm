"""Municipal planning instruments from the official Extremadura SITEX inventory."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = "https://sitex.juntaex.es"
DISCOVERY = ROOT + "/SITEX/planeamiento"
INVENTORY = ROOT + "/SITEX/ptofiguras/listadoresultadossigcat"
MUNICIPALITY = "Arroyo de la Luz"


def _text(node):
    return node.get_text(" ", strip=True)


def _date(value):
    return datetime.strptime(value, "%d/%m/%Y").date().isoformat() if value else None


def _no_pagination(soup):
    # This source returns the complete expandable tree, without paging. Fail if
    # that contract changes rather than accepting an incomplete snapshot.
    if soup.select('.pagination, .paging, .paginator, a[rel="next"]'):
        raise ValueError("Unexpected pagination in SITEX; traversal requires review")
    for a in soup.select("a[href], a[onclick]"):
        target = a.get("href", "") + a.get("onclick", "")
        if (_text(a).casefold() in {"siguiente", "next", "última", "last", "»"}
                or re.search(r"(?:[?&]|/)page[=/:]|pagin", target, re.I)):
            raise ValueError("Unexpected pagination in SITEX")


class ArroyoDeLaLuzAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_municipality(html):
        soup = BeautifulSoup(html, "html.parser")
        options = [o for o in soup.select("#PtofiguraMunicipio option")
                   if _text(o) == MUNICIPALITY]
        if len(options) != 1 or not options[0].get("value", "").isdigit():
            raise ValueError("SITEX municipality selector missing or ambiguous")
        return options[0]["value"]

    @staticmethod
    def parse_inventory(html, municipality_id):
        soup = BeautifulSoup(html, "html.parser")
        _no_pagination(soup)
        selected = soup.select_one("#PtofiguraMunicipio option[selected][value='" + municipality_id + "']")
        if selected is None or _text(selected) != MUNICIPALITY:
            raise ValueError("SITEX inventory is not scoped to Arroyo de la Luz")
        trees = soup.select("ul.filetree")
        if not trees:
            raise ValueError("SITEX planning tree missing")
        found = {}
        for tree in trees:
            for a in tree.select("a.unenlaceafiguradeplaneamiento"):
                match = re.fullmatch(
                    r"addTab\('(/SITEX/ptofiguras/viewsigcat/(\d+))','([^']*)'\);?",
                    a.get("onclick", ""))
                if not match:
                    raise ValueError("Unrecognized SITEX instrument link")
                ident = match[2]
                # The municipal tree also lists the regional Tajo-Salor plan.
                # Exclude regional instruments, but do not impose a record cap.
                if not match[3].startswith(MUNICIPALITY + " - "):
                    if not match[3].startswith("Plan Territorial "):
                        raise ValueError("Unexpected nonmunicipal instrument")
                    continue
                found[ident] = {"sitex_id": ident, "url": ROOT + match[1]}
        if not found:
            raise ValueError("No municipal planning instruments found")
        return list(found.values())

    @staticmethod
    def parse_detail(html, item, municipality_id):
        ident = item["sitex_id"]
        soup = BeautifulSoup(html, "html.parser")
        info = soup.select_one("#infoplaneamiento" + ident)
        files = soup.select_one("#archivosplaneamiento" + ident)
        if info is None:
            raise ValueError("SITEX instrument content missing: " + ident)
        if files is None:
            if soup.select_one("#enlacearchivosplaneamiento" + ident):
                raise ValueError("SITEX documents tab present but its content missing")
            files = BeautifulSoup("", "html.parser")
        _no_pagination(info)
        _no_pagination(files)
        fields = {}
        for tr in info.select("tr"):
            th, td = tr.find("th"), tr.find("td")
            if th is not None and td is not None:
                fields[_text(th)] = _text(td)
        scope_ids = [_text(td) for td in info.select(".campoconidsdemunicipiosparamapa")]
        if fields.get("Ámbito territorial") != MUNICIPALITY or scope_ids != [municipality_id]:
            raise ValueError("Instrument scope mismatch: " + ident)
        if not all(fields.get(key) for key in ("Figura urbanística", "Referencia", "Estado")):
            raise ValueError("Incomplete SITEX instrument identity: " + ident)
        if fields["Estado"] not in {"Vigente", "No vigente", "En trámite", "En contratación"}:
            raise ValueError("Unrecognized SITEX state")
        docs = {}
        for section, kind in ((info, "publicacion_o_tramite"), (files, "documento_planeamiento")):
            for a in section.select("a[href]"):
                url = urljoin(item["url"], a["href"])
                parsed = urlparse(url)
                is_file = "/ptofiguras/downloaddocumento/" in parsed.path
                is_bulletin = parsed.hostname == "doe.juntaex.es" and parsed.path.endswith(".pdf")
                if not (is_file or is_bulletin):
                    if kind == "documento_planeamiento" and not a["href"].startswith("#"):
                        raise ValueError("Unrecognized planning document link: " + url)
                    continue
                if parsed.hostname not in {"sitex.juntaex.es", "doe.juntaex.es"}:
                    raise ValueError("Unexpected document host")
                docs.setdefault(url, {"titulo": a.get("download") or _text(a),
                                      "url": url, "tipo": kind, "source_url": item["url"]})
        procedures = []
        for tr in info.select("[id^='filatramite']"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) != 2:
                raise ValueError("Changed SITEX procedure table")
            procedures.append({"fecha": _date(_text(cells[0])), "tramite": _text(cells[1]),
                               "urls": [urljoin(item["url"], a["href"]) for a in cells[1].select("a[href]")]})
        approval = _date(fields.get("Fecha AD", ""))
        publication = _date(fields.get("Fecha de publicación AD", ""))
        return {
            "id": "arroyo-de-la-luz-sitex-" + ident,
            "municipio": MUNICIPALITY, "codigo_ine": "10021", "provincia": "Cáceres",
            "titulo": fields["Figura urbanística"], "expediente": fields["Referencia"],
            "tipo": "planeamiento urbanístico", "estado": fields["Estado"],
            "fecha_aprob": approval, "fecha_publicacion": publication,
            "fecha_deposito": _date(fields.get("Fecha de depósito", "")),
            "url": item["url"], "sitex_id": ident,
            "source": "sitex-juntaex", "origen": "registro_autonomico_planeamiento",
            "source_inventory": INVENTORY, "source_inventory_method": "POST",
            "source_inventory_params": {"municipioseleccionado": municipality_id},
            "datos_fuente": fields, "tramites": procedures, "documentos": list(docs.values()),
            "document_coverage": "linked_documents" if docs else "metadata_only",
            "lat": None, "lon": None, "geometry": None, "geometry_status": "unavailable",
            "publication_ready": False,
        }

    def _fetch(self, session, url, *, data=None):
        time.sleep(0.2)
        response = session.request("POST" if data is not None else "GET", url, data=data,
                                   timeout=40, headers={"X-Requested-With": "XMLHttpRequest"})
        response.raise_for_status()
        response.encoding = "utf-8"
        # Optional local captures for reproducible review of the live run.
        capture_dir = self.config.get("capture_dir")
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256((url + json.dumps(data, sort_keys=True)).encode()).hexdigest()[:16]
            (directory / (key + ".html")).write_text(response.text, encoding="utf-8")
            with (directory / "requests.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps({"url": url, "method": response.request.method,
                                      "data": data, "status": response.status_code,
                                      "capture": key + ".html"}) + "\n")
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-arroyo-de-la-luz/1.0"
            municipality_id = self.parse_municipality(self._fetch(session, DISCOVERY))
            items = self.parse_inventory(self._fetch(session, INVENTORY,
                data={"municipioseleccionado": municipality_id}), municipality_id)
            rows = [self.parse_detail(self._fetch(session, item["url"]), item, municipality_id)
                    for item in items]
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source": INVENTORY,
                "coverage": "municipal planning inventory; excludes regional plans, works and licences"}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot: no date cutoff or pagination truncation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
