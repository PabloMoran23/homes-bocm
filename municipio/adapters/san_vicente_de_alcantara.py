"""Municipal PGM document inventory; one instrument, many source documents."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://sanvicentedealcantara.es/plantilla.php?enlace=plangeneral'
LIMITATIONS = [
    'Only the municipal Plan General Municipal document inventory; not all later modifications or public works.',
    'Fecha de Alta is document upload metadata, not an agreement, approval or gazette publication date.',
    'No verified licence register or project geometry; no coordinates inferred from PDF plans.',
]


class SanVicenteDeAlcantaraAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('.contenidop')
        heading = main.select_one('#titulo') if main else None
        if not heading or heading.get_text(' ', strip=True) != 'Plan General Municipal':
            raise ValueError('Municipal PGM inventory missing or changed')
        # The reviewed inventory is unpaginated. Refuse a changed inventory rather
        # than quietly returning its first page. Navigation outside main is ignored.
        for a in main.select('a[href]'):
            label = ' '.join((a.get_text(' ', strip=True), a.get('title', ''),
                              a.get('aria-label', ''))).lower()
            query = parse_qs(urlparse(a['href']).query)
            if (set(a.get('rel', [])) & {'next', 'prev'}
                    or re.search(r'siguiente|anterior|next|previous|página|paginaci', label)
                    or any(k.lower() in {'page', 'pagina', 'pag', 'offset', 'start'} for k in query)
                    or a.get_text(strip=True).isdigit()):
                raise ValueError('Pagination detected: extend crawler before accepting output')
        if main.select('.pagination, .pager, [class*="pagin"], form, [data-next-page]'):
            raise ValueError('Possible pagination or dynamic inventory requires review')
        docs = {}
        blocks = [d for d in main.find_all('div', recursive=False)
                  if 'Fecha de Alta:' in d.get_text(' ', strip=True)]
        for block in blocks:
            links = block.select('a[href]')
            if len(links) != 1:
                raise ValueError('Document row must have exactly one source link')
            a = links[0]
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or parsed.hostname != 'sanvicentedealcantara.es'
                    or not re.fullmatch(r'/documentos/\d+\.pdf', parsed.path)
                    or parsed.query or parsed.fragment):
                raise ValueError('Unexpected municipal document URL')
            text = block.get_text(' ', strip=True)
            match = re.search(r'Fecha de Alta:\s*(\d{2}/\d{2}/\d{4})', text)
            title = a.get_text(' ', strip=True)
            if not match or not title or 'Descripción:' not in text:
                raise ValueError('Document metadata missing')
            doc = {
                'titulo': title, 'url': url, 'source_url': SOURCE,
                'descripcion': text.split('Descripción:', 1)[1].strip(),
                'fecha_alta': datetime.strptime(match[1], '%d/%m/%Y').date().isoformat(),
            }
            if url in docs and docs[url] != doc:
                raise ValueError('Conflicting metadata for same document')
            docs[url] = doc
        # Catch PDFs moved outside recognized document rows, including new markup.
        all_pdfs = {urljoin(SOURCE, a['href']) for a in main.select('a[href]')
                    if urlparse(a['href']).path.lower().endswith('.pdf')}
        titles = ' '.join(d['titulo'].upper() for d in docs.values())
        if set(docs) != all_pdfs or not all(x in titles for x in
                ('NORMAS URBANÍSTICAS', 'MEMORIA INFORMATIVA', 'MEMORIA JUSTIFICATIVA')):
            raise ValueError('Incomplete or unrecognized PGM document inventory')
        return [{
            'id': 'san-vicente-de-alcantara-pgm',
            'municipio': 'San Vicente de Alcántara', 'codigo_ine': '06123',
            'provincia': 'Badajoz', 'titulo': 'Plan General Municipal de San Vicente de Alcántara',
            'tipo': 'planeamiento_urbanistico', 'url': SOURCE,
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_pgm',
            'descripcion': 'Instrumento agrupado a partir del inventario municipal de normas, memorias y planos.',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'documentos': list(docs.values()), 'coverage': 'partial',
            'limitations': LIMITATIONS.copy(), 'lat': None, 'lon': None,
            'geometry': None, 'geometry_status': 'unavailable', 'publication_ready': False,
        }]

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=35, headers={
            'User-Agent': 'municipio-san-vicente-de-alcantara/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'sanvicentedealcantara.es', 'www.sanvicentedealcantara.es'}:
            raise ValueError('Unexpected redirect outside municipal website')
        response.encoding = 'utf-8'
        rows = self.parse_inventory(response.text)
        if self.config.get('evidence_dir'):
            folder = Path(self.config['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'plangeneral.html').write_bytes(response.content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': len(rows[0]['documentos']), 'limitations': LIMITATIONS.copy()}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current snapshot; stable instrument ID and URL-deduplicated docs.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
