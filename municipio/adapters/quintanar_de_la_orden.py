"""Municipal NNSS document inventory, not a licence or procurement feed."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.quintanardelaorden.es/reglamento-urbanistico/'
HOST = 'www.quintanardelaorden.es'
LIMITATIONS = [
    'Cobertura parcial: colección municipal de Normas Subsidiarias; no es un registro exhaustivo de expedientes ni de obras.',
    'Incluye planos rotulados MP1 y modificación NNSS1985 en la colección; no se atribuyen acuerdos independientes sin evidencia.',
    'Fechas de publicación, acuerdo, aprobación y vigencia jurídica no acreditadas por el índice; las rutas de subida no son fechas de aprobación.',
    'Planos PDF conservados como documentos: sin geometría vectorial verificada ni coordenadas.',
    'Licencias deshabilitadas; formularios y anuncios de contratación excluidos.',
]


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article')
    title = article.select_one('h1') if article else None
    content = article.select_one('.entry-content') if article else None
    if not title or title.get_text(' ', strip=True) != 'Normas Urbanísticas' or not content:
        raise ValueError('Municipal planning inventory missing or markup changed')
    # This is a single document index. Refuse newly introduced pagination rather
    # than emitting the first page as if it were complete.
    if soup.select('.pagination, .nav-links, .page-links, a[rel~=next], link[rel~=next]'):
        raise ValueError('Inventory pagination requires review')
    for a in content.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if label in {'siguiente', 'next', 'más', 'ver más', 'cargar más'}:
            raise ValueError('Inventory continuation requires review')
    documents = {}
    section = None
    sections = set()
    for element in content.find_all(['h2', 'div']):
        if element.name == 'h2':
            heading = element.get_text(' ', strip=True).upper()
            section = ('textos' if 'CONSULTA Y DESCARGA DE TEXTOS' in heading else
                       'planos' if 'CONSULTA Y DESCARGA DE PLANOS' in heading else None)
            if section:
                sections.add(section)
            continue
        if 'wp-block-file' not in element.get('class', []):
            continue
        anchors = element.select('a[href]')
        if not section or not anchors:
            raise ValueError('Unclassified or empty document block')
        urls = {urljoin(SOURCE, a['href']) for a in anchors}
        if len(urls) != 1:
            raise ValueError('Document label and download point to different URLs')
        url = urls.pop()
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != HOST or
                not parsed.path.startswith('/wp-content/uploads/') or
                not parsed.path.lower().endswith('.pdf')):
            raise ValueError('Unexpected planning document URL')
        label = anchors[0].get_text(' ', strip=True)
        if not label or label.casefold() == 'descarga':
            raise ValueError('Document title missing')
        documents.setdefault(url, {'titulo': label, 'url': url, 'seccion': section,
                                   'source_url': SOURCE})
    docs = list(documents.values())
    if sections != {'textos', 'planos'} or not all(any(d['seccion'] == s for d in docs) for s in sections):
        raise ValueError('Incomplete text/map inventory')
    labels = ' '.join(d['titulo'].upper() for d in docs)
    if not all(term in labels for term in ('DOCUMENTO COMPLETO', 'MEMORIA INFORMATIVA', 'NNSS')):
        raise ValueError('NNSS collection identity not established')
    # Never turn individual map sheets, or download-button duplicates, into works.
    return [{
        'id': 'quintanar-de-la-orden-nnss',
        'municipio': 'Quintanar de la Orden', 'codigo_ine': '45142',
        'provincia': 'Toledo',
        'titulo': 'Normas Subsidiarias de Quintanar de la Orden — colección municipal de textos y planos',
        'tipo': 'planeamiento_urbanistico', 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
        'descripcion': 'Colección de Normas Urbanísticas publicada por el Ayuntamiento; incluye documentación NNSS y planos con referencias a modificaciones.',
        'documentos': docs, 'coverage': 'partial', 'limitations': list(LIMITATIONS),
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False,
    }]


class QuintanarDeLaOrdenAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=(10, 40), stream=True,
                          headers={'User-Agent': 'municipio-quintanar-de-la-orden/1.0'}) as response:
            response.raise_for_status()
            if urlsplit(response.url).netloc != HOST:
                raise ValueError('Unexpected inventory redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory exceeds response bound; refusing truncated output')
                chunks.append(chunk)
            body = b''.join(chunks)
        rows = parse_inventory(body.decode('utf-8'))
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'reglamento-urbanistico.html').write_bytes(body)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': len(rows[0]['documentos']), 'limitations': list(LIMITATIONS)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh of one unpaginated collection; state is deliberately unused.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
