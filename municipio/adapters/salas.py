"""One PGO instrument from Salas' official, unpaginated document inventory."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://www.ayto-salas.es/pgo"


def parse_projects(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    # This reviewed source is a single document package, not a results feed.
    # Fail visibly if the publisher introduces pagination; never emit page one.
    for a in soup.select("a[href]"):
        label = a.get_text(" ", strip=True).casefold()
        query = parse_qs(urlparse(a["href"]).query)
        if ("next" in a.get("rel", []) or label in {"siguiente", "next", "siguiente página"}
                or any(re.search(r"(?:^|_)(?:cur|page|start)$", k, re.I) for k in query)):
            raise ValueError("PGO inventory has pagination; crawler review required")
    if soup.select(".pagination, .lfr-pagination, .taglib-page-iterator"):
        raise ValueError("PGO inventory has pagination controls; crawler review required")

    packages = [node for node in soup.select(".journal-content-article .detalle")
                if "Plan General de Ordenación Urbana (PGOU)" in node.get_text(" ", strip=True)]
    if len(packages) != 1:
        raise ValueError("Expected one municipal PGO document package")
    package = packages[0]
    docs = {}
    for a in package.select("a[href]"):
        url = urljoin(SOURCE, a["href"])
        parsed = urlparse(url)
        if parsed.path != "/c/document_library/get_file":
            continue
        query = parse_qs(parsed.query)
        uuid = query.get("uuid", [""])[0]
        title = a.get_text(" ", strip=True)
        if (parsed.scheme != "https" or parsed.netloc != "www.ayto-salas.es"
                or not re.fullmatch(r"[0-9a-fA-F-]{36}", uuid)
                or query.get("groupId") != ["1902209"] or not title):
            raise ValueError("Invalid municipal PGO document link")
        docs.setdefault(uuid, {"titulo": title, "url": url, "source_url": SOURCE})
    if not {"Memoria", "Normativa"}.issubset({d["titulo"] for d in docs.values()}):
        raise ValueError("PGO package lacks its memory or regulations")
    return [{
        "id": "salas-proy-pgo", "municipio": "Salas", "codigo_ine": "33059",
        "provincia": "Asturias", "titulo": "Plan General de Ordenación Urbana (PGOU) de Salas",
        "tipo": "planeamiento_urbanistico", "url": SOURCE,
        "source": "ayuntamiento", "origen": "inventario_documental_pgo",
        "documentos": list(docs.values()),
        # The page dates neither the package nor the instrument's agreement.
        "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None,
        "fecha_aprob": None, "fase": None,
        "lat": None, "lon": None, "geometry": None,
        "publication_ready": False, "geometry_status": "unavailable",
        "coverage": "Paquete PGO municipal; sin acreditar vigencia ni otras modificaciones o proyectos",
    }]


class SalasAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug="salas", config=None, base_url=""):
        super().__init__(slug, config, base_url or "https://www.ayto-salas.es")

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=45, headers={"User-Agent": "municipio-salas/1.0"})
        response.raise_for_status()
        if urlparse(response.url).netloc != "www.ayto-salas.es":
            raise ValueError("PGO source redirected outside municipal host")
        rows = parse_projects(response.text)
        if self.config.get("capture_dir"):
            capture = Path(self.config["capture_dir"])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "pgo.html").write_text(response.text, encoding="utf-8")
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": [SOURCE], "publication_ready": False}

    def update_proyectos(self, out_jsonl, state_path):
        """Refresh the whole package; no dated incremental feed is available."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
