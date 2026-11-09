"""Municipal planning document inventory, grouped by instrument (not map sheet)."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://elpoblenoudebenitatxell.com/va/arees/urbanisme-i-obres/'
HOST = 'elpoblenoudebenitatxell.com'
LIMITATIONS = [
    'Partial coverage: municipal planning downloads only; not a complete historical planning or works register.',
    'The consolidated text is a documentary consolidation, not a new planning approval.',
    'Publication dates are unknown; website update and upload paths are not agreement dates.',
    'PDF and Drive map links retained; no geometry or coordinates extracted. Drive targets not downloaded.',
    'Licence application forms, procurement and general news excluded; licences disabled.',
    'PDF text verification requires the preinstalled pdftotext executable.',
]


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    groups = {'normas': {}, 'criterio': {}}
    for a in soup.select('.jet-listing-grid__item a[href]'):
        title = a.get_text(' ', strip=True)
        match = re.match(r'^(OE-\d+|OP-\d+|1\.[123])(?:\b|[- .])', title)
        if not match:
            continue
        grid = a.find_parent(class_='jet-listing-grid__items')
        nav = json.loads(grid.get('data-nav', '{}')) if grid else {}
        if (nav.get('enabled') is not False or
                nav.get('query', {}).get('posts_per_page') != -1):
            raise ValueError('Planning inventory pagination changed; refuse incomplete snapshot')
        url = urljoin(SOURCE, a['href'])
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in {HOST, 'drive.google.com'}:
            raise ValueError('Unexpected planning document origin')
        group = 'criterio' if match[1] == '1.3' else 'normas'
        groups[group].setdefault(url, {'titulo': title, 'url': url, 'url_origen': SOURCE})
    docs = {key: list(value.values()) for key, value in groups.items()}
    for prefix in ('1.1', '1.2', 'OE-', 'OP-'):
        if not any(d['titulo'].startswith(prefix) for d in docs['normas']):
            raise ValueError('Missing consolidated planning documents: ' + prefix)
    if len(docs['criterio']) != 1:
        raise ValueError('Missing or ambiguous interpretative instrument')
    return docs


def parse_records(docs, synthesis_text, norms_text, criterion_text):
    if not all('NORMAS SUBSIDIARIAS' in text.upper() for text in (synthesis_text, norms_text)):
        raise ValueError('Downloaded documents do not verify consolidated Normas Subsidiarias')
    normalized = ' '.join(criterion_text.split())
    certificate = re.search(
        r'EXPEDIENTE Nº ÓRGANO COLEGIADO FECHA DE LA SESIÓN (\d+/\d{4}) El Pleno (\d{2}/\d{2}/\d{4})',
        normalized)
    if not certificate or 'CRITERIO INTERPRETATIVO' not in normalized or 'OLIVOS PUEBLO' not in normalized:
        raise ValueError('Interpretative instrument no longer has a verified plenary certificate')
    agreement = datetime.strptime(certificate[2], '%d/%m/%Y').date().isoformat()
    common = dict(municipio='el Poble Nou de Benitatxell / Benitachell', codigo_ine='03042',
                  provincia='Alicante', source='ayuntamiento', origen='inventario_documentos_planeamiento',
                  url=SOURCE, fecha=None, fecha_publicacion=None, fecha_aprob=None,
                  lat=None, lon=None, geometry=None, publication_ready=False,
                  geometry_status='No verified instrument geometry extracted', cobertura='parcial')
    primary = next(d['url'] for d in docs['normas'] if d['titulo'].startswith('1.2'))
    return [
        {**common, 'id': '03042-normas-subsidiarias-texto-consolidado',
         'titulo': 'Normas Subsidiarias de El Poble Nou de Benitatxell — texto consolidado',
         'tipo': 'planeamiento_urbanistico', 'fase': None, 'fecha_acuerdo': None,
         'descripcion': 'Texto consolidado, documento de síntesis y planos de ordenación publicados por el Ayuntamiento. La consolidación no constituye una nueva aprobación.',
         'url_documento': primary, 'documentos': docs['normas']},
        {**common, 'id': '03042-criterio-interpretativo-' + certificate[1].replace('/', '-'),
         'titulo': 'Criterio interpretativo del Plan Parcial Cumbre del Sol — usos terciarios en Olivos–Pueblo del Mar',
         'tipo': 'criterio_interpretativo_planeamiento', 'fase': 'acuerdo plenario',
         'expediente': certificate[1], 'fecha_acuerdo': agreement,
         'fecha_acuerdo_fuente': {'url': docs['criterio'][0]['url'], 'pagina': 1, 'campo': 'FECHA DE LA SESIÓN'},
         'descripcion': 'Criterio interpretativo de la normativa del Plan Parcial; no es una licencia ni una nueva obra. Certificado del acuerdo plenario y documentación adjunta.',
         'url_documento': docs['criterio'][0]['url'], 'documentos': docs['criterio']},
    ]


class ElPobleNouDeBenitatxellAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://' + HOST)

    def _fetch(self, url, name, pdf=False):
        with requests.get(url, timeout=(15, 60), stream=True,
                          headers={'User-Agent': 'municipio-03042/1.0'}) as response:
            response.raise_for_status()
            parts, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 25_000_000:
                    raise ValueError('Source response exceeds safety bound; extraction aborted')
                parts.append(chunk)
            content = b''.join(parts)
        if pdf and not content.startswith(b'%PDF-'):
            raise ValueError('Expected PDF at ' + url)
        if self.config.get('evidence_dir'):
            path = Path(self.config['evidence_dir'])
            path.mkdir(parents=True, exist_ok=True)
            (path / name).write_bytes(content)
        return content

    @staticmethod
    def _pdf_text(content):
        with tempfile.TemporaryDirectory(prefix='benitatxell-') as directory:
            path = Path(directory) / 'document.pdf'
            path.write_bytes(content)
            return subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True,
                                  capture_output=True, text=True, timeout=30).stdout

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        docs = parse_inventory(self._fetch(SOURCE, 'urbanisme.html').decode('utf-8'))
        selected = [next(d for d in docs['normas'] if d['titulo'].startswith(prefix))
                    for prefix in ('1.1', '1.2')] + docs['criterio']
        texts = [self._pdf_text(self._fetch(d['url'], f'document-{i}.pdf', pdf=True))
                 for i, d in enumerate(selected, 1)]
        rows = parse_records(docs, *texts)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [d['url'] for d in selected],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Entire nonpaginated inventory is refreshed; no date watermark can drop records.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
