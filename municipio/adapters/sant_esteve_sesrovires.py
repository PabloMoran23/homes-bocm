"""Municipal document inventories; one row per instrument, never per attachment."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.sesrovires.cat'
ROOT = BASE + '/temes/urbanisme/'
SOURCES = (
    ROOT + 'planejament-vigent/gestio-urbanisitca-vigent/',
    ROOT + 'planejament-en-tramit/planejament-general-en-tramit/',
    ROOT + 'planejament-en-tramit/gestio-urbanistica-en-tramit/',
)
LIMITATIONS = [
    'Partial coverage: three municipal document inventories, not all municipal projects or RPUC.',
    'Page update labels are from March 2016; listed phases are source assertions, not independently verified current legal status.',
    'Attachment URLs retained as published; PDF contents and continued availability are not verified by the scraper.',
    'No verified agreement/publication dates or project geometry in the parsed inventory; these fields remain null.',
    'No granted-licence register extracted; licence forms and allegation forms are not records.',
]


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn')


def document_url(url):
    p = urlparse(url)
    return p.scheme in {'https', 'http'} and (
        (p.hostname in {'www.seu-e.cat', 'seu-e.cat'} and p.path.startswith('/documents/'))
        or (p.hostname in {'www.seu.cat', 'seu.cat'} and p.path == '/seue-fitxer' and p.query)
        or (p.hostname == 'www.sesrovires.cat' and p.path.startswith('/media/'))
    )


class SantEsteveSesroviresAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html, source_url):
        if source_url not in SOURCES:
            raise ValueError('Unreviewed inventory URL')
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('main#main-content')
        if main is None:
            raise ValueError('Missing municipal main content')
        # These are unpaginated document inventories. Fail if that contract changes.
        if main.select('.pagination, .paginacio, .pager, [rel~=next]'):
            raise ValueError('Pagination detected; inventory coverage needs review')
        for a in main.select('a[href]'):
            if re.search(r'[?&](?:page|pagina|offset|start)=', a['href'], re.I) or normalized(a.get_text(' ', strip=True)) in {'seguent', 'seguents', 'siguiente', 'next', 'mes resultats'}:
                raise ValueError('Pagination detected; inventory coverage needs review')
        container = main.select_one('.dinamic')
        if container is None:
            raise ValueError('Missing inventory container')
        headings = container.select('.subtitle')
        if not headings:
            raise ValueError('No instruments in inventory')
        rows = {}
        used_blocks = set()
        for heading in headings:
            title = heading.get_text(' ', strip=True)
            key = normalized(title)
            if not re.search(r'\b(?:projecte|avantprojecte|modificacio puntual pgom)\b', key) or any(word in key for word in ('licitacio', 'llicencia', 'formulari', 'contractacio')):
                raise ValueError('Unrecognized instrument heading: ' + title)
            block = heading.find_next_sibling(class_=['ddbbtext', 'subtitle'])
            if block is None or 'ddbbtext' not in block.get('class', []):
                raise ValueError('Instrument lacks its own document block')
            used_blocks.add(id(block))
            docs = {}
            for a in block.select('a[href]'):
                url = urljoin(source_url, a['href'])
                if not document_url(url):
                    raise ValueError('Unrecognized inventory attachment URL: ' + url)
                label = a.get_text(' ', strip=True)
                auxiliary = 'model' in normalized(label) or 'formulari' in normalized(label)
                docs.setdefault(url, {'titulo': label, 'url': url, 'source_url': source_url,
                                      'rol': 'formulario_auxiliar' if auxiliary else 'documento_instrumento'})
            if not docs or all(d['rol'] == 'formulario_auxiliar' for d in docs.values()):
                raise ValueError('Instrument has no substantive source documents')
            identity = re.sub(r"^.*?aprovacio (?:definitiva|inicial) (?:del? |de l')?", '', key)
            identity = ' '.join(identity.split())
            record_id = 'sant-esteve-sesrovires-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
            if record_id in rows:
                raise ValueError('Duplicate instrument heading')
            phase = 'aprobación definitiva' if 'aprovacio definitiva' in key else 'aprobación inicial' if 'aprovacio inicial' in key else None
            kind = 'modificacion_planeamiento' if 'pgom' in key else 'reparcelacion' if 'reparcel' in key else 'anteproyecto_urbanizacion' if 'avantprojecte' in key else 'proyecto_urbanizacion'
            anchor = heading.get('id')
            rows[record_id] = {
                'id': record_id, 'municipio': 'Sant Esteve Sesrovires', 'codigo_ine': '08208',
                'provincia': 'Barcelona', 'titulo': title, 'tipo': kind, 'fase': phase,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': source_url + ('#' + anchor if anchor else ''), 'source_url': source_url,
                'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
                'documentos': list(docs.values()),
                'descripcion': block.get_text(' ', strip=True),
                'estado_fuente': 'vigent' if '/planejament-vigent/' in source_url else 'en tràmit',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            }
        # No newly added document section may be silently omitted.
        if used_blocks != {id(b) for b in container.select('.ddbbtext')}:
            raise ValueError('Unassociated inventory document block')
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = []
        captures = self.config.get('capture_dir')
        for source in SOURCES:
            with requests.get(source, timeout=(10, 40), stream=True,
                              headers={'User-Agent': 'municipio-sant-esteve-sesrovires/1.0'}) as response:
                response.raise_for_status()
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    raise ValueError('Inventory did not return HTML')
                data = bytearray()
                for chunk in response.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > 3_000_000:
                        raise ValueError('Inventory exceeds reviewed response size')
                html = bytes(data).decode('utf-8')
            if captures:
                directory = Path(captures)
                directory.mkdir(parents=True, exist_ok=True)
                (directory / (source.rstrip('/').rsplit('/', 1)[-1] + '.html')).write_text(html, encoding='utf-8')
            rows.extend(self.parse_inventory(html, source))
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Repeated instrument across inventories; review grouping')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES),
                'publication_ready': False, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Refresh the complete finite snapshot. No date-based filtering loses old instruments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
