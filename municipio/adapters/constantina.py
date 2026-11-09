"""Constantina's municipal PBOM document inventory, one record per instrument."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ENTRY = "https://www.constantina.org/es/ayuntamiento/pgou"
HOME = "https://constantina.nuevoplan.es/"
DOCUMENTS = HOME + "documentos/"
LIMITATIONS = [
    "Cobertura parcial municipal: solo el inventario documental del nuevo PBOM; "
    "no incluye el PGOU histórico, otros instrumentos, obras ni licencias.",
    "Las fases del portal no acreditan aprobación; fechas de publicación, "
    "acuerdo y aprobación no verificadas. Los nombres DEF y las carpetas "
    "de carga no se interpretan como aprobación ni fecha administrativa.",
    "Se conservan enlaces documentales; no se extraen geometrías de los PDF "
    "ni se comprueba exhaustivamente su contenido o vigencia jurídica.",
]


def _no_pagination(soup):
    for a in soup.select("a[href]"):
        href = a["href"]
        if href in ("", "#"):
            continue
        text = a.get_text(" ", strip=True).casefold()
        if ("next" in a.get("rel", []) or text in {"next", "siguiente", "última"}
                or re.search(r"[?&](?:page\w*|paged)=\d+", href, re.I)
                or re.search(r"/page/\d+", href)
                or a.find_parent(class_=re.compile(r"pagination|page-numbers"))):
            raise ValueError("PBOM inventory is paginated; review crawler before extraction")


def parse_documents(html: str, source_url: str = DOCUMENTS) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if not re.search(r"DOCUMENTOS\s*[–—-]\s*PBOM\s+CONSTANTINA", title, re.I):
        raise ValueError("Not the Constantina PBOM document inventory")
    main = soup.select_one("main")
    if main is None:
        raise ValueError("Missing PBOM inventory content")
    _no_pagination(main)
    documents = {}
    primary = False
    for a in main.select("a[href]"):
        url = urljoin(source_url, a["href"])
        parts = urlsplit(url)
        if not parts.path.lower().endswith(".pdf"):
            continue
        filename = unquote(parts.path.rsplit("/", 1)[-1])
        if re.search(r"cuestionario|formulario|solicitud|alegaciones", filename, re.I):
            continue
        local_plan = (parts.hostname == "constantina.nuevoplan.es"
                      and parts.path.startswith("/wp-content/uploads/")
                      and re.match(r"P07-F\d+_", filename, re.I))
        municipal_plan = (parts.hostname == "www.constantina.org"
                          and parts.path.startswith("/export/sites/constantina/")
                          and "PBOM-CONSTANTINA" in filename.upper())
        if parts.scheme != "https" or not (local_plan or municipal_plan):
            # The homepage contains copied links to Los Molares. Never attach
            # another municipality's files or generic forms to this instrument.
            continue
        primary |= bool(re.match(r"P07-F3_(MEMORIA|PLANOS)", filename, re.I))
        label = a.get_text(" ", strip=True) or a.get("title") or filename
        documents.setdefault(url, {
            "titulo": label, "url": url, "inventory_url": source_url,
            "nombre_archivo": filename,
        })
    if not primary:
        raise ValueError("No substantive PBOM plan documents; forms alone are not a plan")
    return {
        "id": "constantina-pbom", "municipio": "Constantina",
        "codigo_ine": "41033", "provincia": "Sevilla",
        "titulo": "Plan Básico de Ordenación Municipal de Constantina (PBOM)",
        "tipo": "PBOM", "source": "ayuntamiento",
        "origen": "inventario_documental_pbom", "url": source_url,
        "url_fuente_municipal": ENTRY,
        "documentos": list(documents.values()),
        "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
        "lat": None, "lon": None, "geometry": None,
        "geometry_status": "unavailable", "publication_ready": False,
        "coverage": "inventario_documental_pbom", "limitations": LIMITATIONS,
    }


class ConstantinaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug="constantina", config=None, base_url=""):
        super().__init__(slug, config, base_url or ENTRY)

    def _fetch(self, url, capture_name, expected_url):
        response = requests.get(url, timeout=40, headers={
            "User-Agent": "municipio-constantina/1.0 (public planning inventory)",
        })
        response.raise_for_status()
        if response.url.rstrip("/") != expected_url.rstrip("/"):
            raise ValueError(f"Unexpected municipal source redirect: {response.url}")
        if "html" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("Expected an HTML planning inventory")
        # Use bytes so the declared UTF-8 HTML meta tag wins over a server's
        # default ISO-8859-1 response encoding.
        html = response.content.decode("utf-8")
        if self.config.get("capture_dir"):
            directory = Path(self.config["capture_dir"])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture_name).write_text(html, encoding="utf-8")
        return html

    def backfill_proyectos(self, out_jsonl: Path):
        home_html = self._fetch(ENTRY, "municipal-entry.html", HOME)
        home = BeautifulSoup(home_html, "html.parser")
        if not home.title or "PBOM CONSTANTINA" not in home.title.get_text().upper():
            raise ValueError("Municipal entry no longer identifies the Constantina PBOM")
        if not any(urljoin(HOME, a["href"]).rstrip("/") == DOCUMENTS.rstrip("/")
                   for a in home.select("a[href]")):
            raise ValueError("Municipally endorsed PBOM no longer links its document inventory")
        row = parse_documents(self._fetch(DOCUMENTS, "documents.html", DOCUMENTS))
        # Preserve the literal portal stage without asserting a legal phase.
        stages = re.findall(r"Actualmente nos encontramos en la Fase\s+\d+",
                            home.get_text(" ", strip=True), re.I)
        if stages:
            row["etapas_publicadas"] = list(dict.fromkeys(stages))
            row["etapas_source_url"] = HOME
        rows = [row]
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                             encoding="utf-8")
        temporary.replace(output)
        return {"status": "ok", "count": len(rows), "written": len(rows),
                "documents": len(row["documentos"]),
                "source_urls": [ENTRY, HOME, DOCUMENTS], "limitations": LIMITATIONS,
                "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        """Refresh the entire current document inventory; no date cursor."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        raise NotImplementedError("Licencias disabled: no verified register of granted licences")

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
