"""Partial snapshot of the municipality's physical public-works inventory."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://www.arbucies.cat/ca/arees-i-regidories/'
          'urbanisme-territori-i-activitats/obres-i-infraestructures-municipals.html')
LIMITATIONS = [
    'Partial coverage: only the municipal public-works service page; not a historical register.',
    'Execution status is the undated municipal narrative, not independently verified current progress.',
    'No publication, agreement or approval dates supplied; storm dates and grant years are not approval dates.',
    'No verified coordinates or geometry; publication_ready is false.',
    'No technical attachments currently supplied; funding logos are not project documents.',
    'No granted-licence register extracted; planning and procurement inventories are outside this snapshot.',
]


def _norm(text):
    return ' '.join(unicodedata.normalize('NFKC', text).split())


class ArbuciesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        if slug != 'arbucies':
            raise ValueError('This adapter is specific to Arbúcies (17009)')
        super().__init__(slug, config, base_url or 'https://www.arbucies.cat')
        if str(self.config.get('ine_code', '17009')) != '17009':
            raise ValueError('Arbúcies INE must be 17009')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.select('a[href]'):
            label = a.get_text(' ', strip=True).casefold()
            if ('next' in a.get('rel', []) or label in {'següent', 'siguiente', 'next', '»', '›'}
                    or a.find_parent(class_=re.compile(r'pag(?:ination|inacio)', re.I))):
                raise ValueError('Inventory pagination detected; refusing a partial crawl')
        if soup.select('.pagination, .paginacio, [data-next-page]'):
            raise ValueError('Inventory pagination detected')
        heading = soup.find('h1', string=re.compile(r'Obres i infraestructures municipals'))
        content = heading.find_next_sibling('div', class_='text-justify') if heading else None
        if content is None:
            raise ValueError('Missing municipal works inventory content')
        sections = []
        current = None
        for block in content.find_all(['p', 'h2', 'h3'], recursive=False):
            text = _norm(block.get_text(' ', strip=True))
            bold = block.find('strong')
            is_heading = (block.name in {'h2', 'h3'} or
                          (bold is not None and _norm(bold.get_text(' ', strip=True)) == text))
            if is_heading and text:
                # This is an organisational divider, not an additional work.
                if text.startswith('Àrea de '):
                    current = None
                    continue
                current = {'titulo': text, 'blocks': []}
                sections.append(current)
            elif current is not None:
                current['blocks'].append(block)
            elif text:
                raise ValueError('Unsectioned inventory text; review changed source')
        rows = []
        seen = set()
        for section in sections:
            title = section['titulo']
            description = '\n'.join(_norm(p.get_text(' ', strip=True))
                                    for p in section['blocks'] if p.get_text(strip=True))
            narrative = description.replace('’', "'")
            if re.search(r"L'Ajuntament d'Arbúcies està duent a terme l'execució", narrative):
                phase = 'en ejecución'
            elif re.search(r"L'Ajuntament d'Arbúcies ha dut a terme (?:l'execució de )?les obres", narrative):
                phase = 'ejecutado según fuente municipal'
            else:
                raise ValueError('Section lacks explicit physical-work execution evidence: ' + title)
            key = hashlib.sha256(_norm(title).casefold().encode()).hexdigest()[:20]
            if key in seen:
                raise ValueError('Duplicate work heading; review grouping')
            seen.add(key)
            documents = {}
            for block in section['blocks']:
                for a in block.select('a[href]'):
                    url = urljoin(SOURCE, a['href'])
                    if urlparse(url).scheme in {'https', 'http'}:
                        documents.setdefault(url, {'titulo': _norm(a.get_text(' ', strip=True)),
                                                   'url': url, 'source_url': SOURCE})
            rows.append({
                'id': 'arbucies-proy-' + key, 'municipio': 'Arbúcies',
                'codigo_ine': '17009', 'provincia': 'Girona', 'titulo': title,
                'tipo': 'obra_publica', 'fase': phase, 'descripcion': description,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'url': SOURCE, 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_obras',
                'documentos': list(documents.values()),
                'provenance': {'source_url': SOURCE, 'section_heading': title,
                               'status_basis': 'municipal execution narrative',
                               'attachment_scope': 'links within this work section; funding logos excluded'},
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'coverage': 'partial_service_page_snapshot',
            })
        if not rows:
            raise ValueError('No physical works in municipal inventory')
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        request = Request(SOURCE, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-arbucies/1.0')})
        with urlopen(request, timeout=30) as response:
            if urlparse(response.url).hostname not in {'www.arbucies.cat', 'arbucies.cat'}:
                raise ValueError('Source redirected outside municipal website')
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Inventory exceeds response size limit; no output written')
            html = raw.decode(response.headers.get_content_charset() or 'utf-8')
        rows = self.parse_projects(html)
        if self.config.get('evidence_dir'):
            evidence = Path(self.config['evidence_dir'])
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / 'live-works.html').write_bytes(raw)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # The entire unpaginated page is refreshed; no date watermark is inferred.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
