"""Muskiz's municipal planning document inventory (partial, grouped by instrument)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.muskiz.org/es-ES/Ayuntamiento/PGOU/Paginas/default.aspx'
LIMITATIONS = [
    'Partial coverage: four instruments in the municipal Urbanismo document inventory; not a complete planning register.',
    'Kobaron external Drive folder, PERI linked notice, news, procurement, forms and council appointments are outside extraction scope.',
    'Linked external folders and shortened URLs are retained as municipal references, not crawled or certified as available.',
    'Document publication dates are not agreement or approval dates. No approval dates inferred from filenames or conditional agenda titles.',
    'No verified project geometry; no coordinates or geocoding. No granted-licence inventory verified.',
]


def text(node):
    return node.get_text(' ', strip=True)


def publication_date(value):
    match = re.search(r'(?:publicado|fecha[s]? de publicaci[oó]n(?: en la web)?)\s*:?\s*(\d{2}/\d{2}/\d{4})', value, re.I)
    return datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None


def canonical_url(href):
    url = urljoin(SOURCE, href.strip())
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('Invalid document URL')
    if parsed.hostname == 'www.muskiz.org':
        url = 'https://' + parsed.netloc + parsed.path
        if parsed.query:
            url += '?' + parsed.query
        if parsed.fragment:
            url += '#' + parsed.fragment
    return quote(unquote(url), safe=":/?=&%#+,;")


class MuskizAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.select('a[href]'):
            if (text(a).lower() in {'siguiente', 'next', 'hurrengoa', '»siguiente'}
                    or 'next' in a.get('rel', [])) and a['href'] not in {'', '#'}:
                raise ValueError('Inventory pagination appeared; implement traversal before accepting output')
        if soup.select('.ms-paging, .pagination, a[title="Next Page"]'):
            raise ValueError('Unreviewed inventory pagination')
        sections = {}
        for h in soup.select('h3.ms-WPTitle'):
            name = text(h)
            body = h.parent.parent.select_one('.ms-WPBody')
            if body:
                if name in sections:
                    raise ValueError('Duplicate inventory section: ' + name)
                sections[name] = body
        specs = [
            ('nnss', 'Normas subsidiarias', 'Normas Subsidiarias de Planeamiento Municipal de Muskiz', 'normas_subsidiarias'),
            ('nnss-ies', 'Modificaciones Normas Subsidiarias', 'Modificación de las Normas Subsidiarias IES Muskiz', 'modificacion_planeamiento'),
            ('pgou', 'Plan General de Ordenación Urbana (P.G.O.U.)', 'Revisión del Plan General de Ordenación Urbana de Muskiz', 'plan_general'),
        ]
        special = [name for name in sections if name.startswith('Plan especial para la construcción de un centro de adiestramiento')]
        if len(special) != 1:
            raise ValueError('Missing or ambiguous special-plan section')
        specs.append(('plan-especial-canino-704', special[0], re.sub(r'\s*\(Publicado.*$', '', special[0]), 'plan_especial'))
        rows = []
        for key, section, title, kind in specs:
            if section not in sections:
                raise ValueError('Missing planning inventory section: ' + section)
            bodies = [sections[section]]
            if key == 'pgou':
                if 'Documentación' not in sections:
                    raise ValueError('Missing PGOU documentation section')
                bodies.append(sections['Documentación'])
            documents = {}
            for body in bodies:
                for a in body.select('a[href]'):
                    label = text(a)
                    if not label:
                        continue
                    # Administrative council appointments are not plan documents.
                    if re.search(r'vocal|representantes|consejo asesor', label, re.I):
                        continue
                    url = canonical_url(a['href'])
                    context = a.find_parent('li')
                    context_text = text(context) if context else label
                    documents.setdefault(url, {
                        'titulo': label, 'url': url, 'url_procedencia': SOURCE,
                        'descripcion_fuente': context_text,
                        'fecha_publicacion': publication_date(context_text),
                        'tipo_enlace': 'pdf_municipal' if urlparse(url).hostname == 'www.muskiz.org' and urlparse(url).path.lower().endswith('.pdf') else 'referencia_enlazada',
                    })
            if not any(d['tipo_enlace'] == 'pdf_municipal' for d in documents.values()):
                raise ValueError('Instrument lacks municipal source documents: ' + key)
            if key == 'nnss-ies' and not all('IES' in d['titulo'] or 'Boletín' in d['titulo'] for d in documents.values()):
                raise ValueError('NNSS modifications now need instrument-level grouping review')
            rows.append({
                'id': 'muskiz-proy-' + key, 'municipio': 'Muskiz', 'codigo_ine': '48071',
                'provincia': 'Bizkaia', 'titulo': title, 'tipo': kind,
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
                'url': SOURCE, 'seccion_fuente': section,
                'fecha_publicacion': publication_date(section),
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'documentos': list(documents.values()),
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'cobertura': 'parcial; instrumentos con PDF municipal en el inventario de Urbanismo',
            })
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'municipio-muskiz/1.0'})
        response.raise_for_status()
        rows = self.parse_projects(response.text)
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'inventory.html').write_text(response.text, encoding='utf-8')
            (directory / 'inventory-response.json').write_text(json.dumps({
                'requested_url': SOURCE, 'response_url': response.url, 'status_code': response.status_code,
                'retrieved_at': datetime.now().astimezone().isoformat(),
            }, indent=2), encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of this static inventory; no date-based filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
