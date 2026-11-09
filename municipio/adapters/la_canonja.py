"""Municipal POUM catalogue snapshot, not a register of granted licences."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.lacanonja.cat/ova_dep/urbanisme-i-territori/'
RPUC_HOST = 'planejamenturbanisme.territori.gencat.cat'
MAX_BYTES = 2_000_000
LIMITATIONS = [
    'Partial coverage: only the POUM explicitly catalogued on the municipal department page; not all amendments or public works.',
    'The RPUC application and its underlying document inventory are not extracted; the municipal dossier link is retained.',
    'No explicit agreement, approval or publication dates on the catalogue entry; all date fields remain null.',
    'No verified project geometry or coordinates; publication_ready is false.',
    'No granted-licence register extracted; application forms and procurement/news items are excluded.',
]


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    # The catalogue uses an Elementor heading widget followed by its link widget.
    # Keep links local to that entry, never borrow a dossier from navigation.
    headings = [h for h in soup.select('h4.elementor-heading-title')
                if re.fullmatch(r'POUM la Canonja\s*[-–—]\s*Aprovació Definitiva',
                                h.get_text(' ', strip=True), re.I)]
    if len(headings) != 1:
        raise ValueError('Expected one explicitly named La Canonja POUM catalogue entry')
    heading = headings[0]
    widget = heading.find_parent('div', class_='elementor-widget-heading')
    if widget is None:
        raise ValueError('POUM catalogue structure changed')
    links = {}
    for sibling in widget.find_next_siblings():
        if sibling.select_one('h1,h2,h3.elementor-heading-title,h4,h5,h6'):
            break
        if sibling.select('a[rel~="next"], .pagination, .pager, [data-next-page]'):
            raise ValueError('Unexpected pagination in the POUM entry; refusing partial output')
        for a in sibling.select('a[href]'):
            target = urljoin(source_url, a['href'])
            parsed = urlparse(target)
            match = re.fullmatch(r'/consulta/detallExpedient/(\d+)', parsed.fragment)
            if (parsed.scheme == 'https' and parsed.hostname == RPUC_HOST
                    and parsed.path == '/rpucportal/index.html' and match):
                links[target] = match[1]
    if len(set(links.values())) != 1:
        raise ValueError('Missing or ambiguous official RPUC dossier for POUM')
    # This source is a single catalogue entry. New pagination must be reviewed,
    # not silently treated as a complete snapshot.
    if widget.parent.select('a[rel~="next"], .pagination, .pager, [data-next-page]'):
        raise ValueError('Unexpected catalogue pagination')
    dossier_id = next(iter(links.values()))
    documents = [{'titulo': 'Expedient RPUC', 'url': url,
                  'tipo': 'registro_oficial', 'source_url': source_url}
                 for url in sorted(links)]
    return [{
        'id': 'la-canonja-plan-' + hashlib.sha256(('rpuc:' + dossier_id).encode()).hexdigest()[:16],
        'municipio': 'La Canonja', 'codigo_ine': '43907', 'provincia': 'Tarragona',
        'titulo': 'Pla d’ordenació urbanística municipal de la Canonja (POUM)',
        'tipo': 'POUM', 'fase': 'aprobación definitiva',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': source_url, 'url_documento': documents[0]['url'],
        'documentos': documents, 'rpuc_id': dossier_id,
        'source': 'ayuntamiento', 'origen': 'catalogo_municipal_planeamiento',
        'source_title': heading.get_text(' ', strip=True),
        'descripcion': 'POUM identificado por el catálogo municipal y su enlace al expediente RPUC. No se ha extraído el contenido documental del expediente.',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified project geometry in municipal catalogue',
        'coverage': 'single_municipal_catalogue_entry',
    }]


class LaCanonjaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.lacanonja.cat')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=30, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-la-canonja/1.0')
        }) as response:
            response.raise_for_status()
            if response.url.rstrip('/') != SOURCE.rstrip('/'):
                raise ValueError('Unexpected municipal catalogue redirect')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > MAX_BYTES:
                    raise ValueError('Municipal catalogue exceeds response size limit')
            html = content.decode('utf-8')
        rows = parse_inventory(html)
        if self.config.get('evidence_dir'):
            evidence = Path(self.config['evidence_dir'])
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / 'urbanisme-live.html').write_bytes(content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh the complete single-entry snapshot; no date-based filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
