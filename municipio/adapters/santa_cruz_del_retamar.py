"""Municipal POM document inventory; not a licence or public-works register."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://santacruzdelretamar.es/Urbanismo/Urbanismo.html"
LIMITATIONS = [
    "Cobertura parcial: solo el bloque documental del POM de Urbanismo; no histórico municipal completo.",
    "Se excluyen modelos de licencia, bases reguladoras DOT1, contratación y noticias.",
    "Sin fechas estructuradas: el HTML no fecha el inventario; no se analizan automáticamente los PDF.",
    "Sin geometría ni afirmación de vigencia actual; archivos comprobados por firma, no íntegramente analizados.",
]


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).upper().split())


def official_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in {
        "santacruzdelretamar.es", "www.santacruzdelretamar.es"
    }


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    if not official_url(source_url):
        raise ValueError("Unexpected inventory origin")
    soup = BeautifulSoup(html, "html.parser")
    section = next((s for s in soup.select("section")
                    if s.find(["h1", "h2"], string=re.compile(r"^\s*Urbanismo\s*$", re.I))), None)
    if section is None:
        raise ValueError("Urbanismo inventory section missing")
    for a in section.select("a[href]"):
        label = normalized(a.get_text(" ", strip=True))
        rel = a.get("rel", [])
        if ("next" in rel or label in {"SIGUIENTE", "NEXT", "SIGUIENTE PAGINA", ">", "»"}
                or re.search(r"(?:[?&](?:page|pagina|paged|offset)=|/page/)", a["href"], re.I)):
            raise ValueError("Inventory pagination detected; review crawler before extraction")

    heading = next((p for p in section.find_all("p")
                    if normalized(p.get_text(" ", strip=True)) == "PLAN DE ORDENACION MUNICIPAL"), None)
    if heading is None:
        raise ValueError("POM heading missing")
    docs = {}
    ended = False
    # Traverse in document order: the legacy page contains improperly nested <p>s.
    for node in heading.next_elements:
        if node is not section and section not in node.parents:
            break
        if getattr(node, "name", None) == "p" and normalized(node.get_text(" ", strip=True)) == "NOTAS:":
            ended = True
            break
        if getattr(node, "name", None) != "a" or not node.get("href"):
            continue
        title = node.get_text(" ", strip=True)
        url = urldefrag(urljoin(source_url, node["href"]))[0]
        if (not official_url(url) or not urlparse(url).path.startswith("/Urbanismo/")
                or not urlparse(url).path.lower().endswith((".pdf", ".rar"))):
            raise ValueError("Unexpected POM document link")
        if not title:
            raise ValueError("POM document has no label")
        docs.setdefault(url, {"titulo": title, "url": url, "inventory_url": source_url})
    if not ended:
        raise ValueError("POM end marker missing; refusing to absorb unrelated documents")
    labels = [normalized(d["titulo"]) for d in docs.values()]
    if not (any("EDICTO" in t and "P.O.M." in t for t in labels)
            and any("NORMAS" in t for t in labels)
            and any("PLANOS" in t for t in labels)):
        raise ValueError("Incomplete POM inventory: expected edict, norms and plans")
    return [{
        "id": "santa-cruz-del-retamar-pom",
        "municipio": "Santa Cruz del Retamar", "provincia": "Toledo", "codigo_ine": "45157",
        "titulo": heading.get_text(" ", strip=True), "tipo": "planeamiento_urbanistico",
        "url": source_url, "inventory_url": source_url,
        "source": "ayuntamiento", "origen": "inventario_documental_pom",
        "documentos": list(docs.values()), "publication_ready": False,
        "geometry_status": "unavailable", "limitaciones": LIMITATIONS,
    }]


class SantaCruzDelRetamarAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = Path(self.config["evidence_dir"]) if self.config.get("evidence_dir") else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        checks = []
        with requests.Session() as session:
            session.headers.update({"User-Agent": "municipio-santa-cruz-del-retamar/1.0"})
            response = session.get(SOURCE, timeout=40)
            response.raise_for_status()
            rows = parse_inventory(response.content.decode("utf-8"), response.url)
            if captures:
                (captures / "urbanismo.html").write_bytes(response.content)
            # Check every retained link without downloading the large plan archive.
            for index, doc in enumerate(rows[0]["documentos"]):
                with session.get(doc["url"], timeout=40, stream=True) as result:
                    result.raise_for_status()
                    if not official_url(result.url):
                        raise ValueError("Unexpected document redirect")
                    prefix = next(result.iter_content(chunk_size=512), b"")
                    is_rar = urlparse(doc["url"]).path.lower().endswith(".rar")
                    signature = b"Rar!\x1a\x07" if is_rar else b"%PDF-"
                    if not prefix.startswith(signature):
                        raise ValueError(f"Invalid document signature: {doc['url']}")
                    checks.append({"url": doc["url"], "final_url": result.url,
                                   "status": result.status_code, "signature_valid": True,
                                   "content_type": result.headers.get("Content-Type"),
                                   "captured_bytes": len(prefix)})
                    if captures:
                        (captures / f"document-{index + 1:02d}.prefix").write_bytes(prefix)
        if captures:
            (captures / "document_checks.json").write_text(
                json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._write(out_jsonl, rows)
        return {"count": len(rows), "written": len(rows), "documents_checked": len(checks),
                "coverage": "current_pom_document_inventory", "limitations": LIMITATIONS,
                "source_urls": [SOURCE] + [d["url"] for d in rows[0]["documentos"]]}

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # This is a complete replacement snapshot of the same scoped inventory.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True, "reason": "No verified register of granted licences"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
