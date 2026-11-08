"""Reviewed official planning inventories; no licence or geometry inference."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Comment

from municipio.adapters.portal import AyuntamientoAdapter

TRANSPARENCIA = ('https://transparencia.palomaresdelrio.es/es/transparencia/'
                 'indicadores-de-transparencia/indicador/'
                 'Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00031/')
PGOM = 'https://www.palomaresdelrio.es/es/pgom/documentacion/'
TITLES = {
    'casa-alegre-atu': 'Actuación de Transformación Urbanística ARI-1 Casa Alegre',
    'casa-alegre-ficha-10': 'Modificación de la Ficha 10 del Catálogo — Casa Alegre',
    'innovacion-10': 'Innovación décima del PGOU — usos de gasolineras y servicios auxiliares',
    'villarejo': 'Estudio de detalle de las parcelas 19, 20 y 21 del sector SUZ-PP-07 El Villarejo',
    'zorrero': 'Modificación del Plan Parcial del sector SUZ-PP-08 El Zorrero',
    'pgom': 'Plan General de Ordenación Municipal de Palomares del Río',
}


def normalize(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def documents(block, source):
    result = {}
    for a in block.select('a[href]'):
        url = urljoin(source, a['href'])
        parsed = urlparse(url)
        if (parsed.hostname != urlparse(source).hostname
                or not parsed.path.startswith('/export/sites/palomaresdelrio/')
                or not parsed.path.lower().endswith('.pdf')):
            continue
        result[url] = {'titulo': a.get_text(' ', strip=True), 'url': url}
    return list(result.values())


def check_complete(soup, source):
    # OpenCMS collectors expose their total even when only one page is rendered.
    for gallery in soup.select('.sg-download-gallery, table'):
        comments = ' '.join(str(c) for c in gallery.find_all(
            string=lambda x: isinstance(x, Comment)))
        totals = re.findall(r'(?:resultSize|listResultSize)\s*:\s*(\d+)', comments)
        if totals and int(totals[-1]) != len(documents(gallery, source)):
            raise ValueError('Incomplete document collector; pagination requires review')
    for a in soup.select('a[href]'):
        label = normalize(a.get_text(' ', strip=True))
        if (a.get('href') not in {'', '#'} and
                ('next' in a.get('rel', []) or label in {'siguiente', 'next'}
                 or re.search(r'[?&]page[^=]*=', a['href']))):
            raise ValueError('Paginated inventory requires review; refusing partial output')


def parse_inventory(html, source=TRANSPARENCIA):
    soup = BeautifulSoup(html, 'html.parser')
    check_complete(soup, source)
    records = {}

    def add(key, docs, section):
        if not docs:
            raise ValueError('Named planning section has no official PDF documents')
        row = records.setdefault(key, {
            'id': 'palomares-del-rio-' + key, 'municipio': 'Palomares del Río',
            'codigo_ine': '41070', 'provincia': 'Sevilla', 'titulo': TITLES[key],
            'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
            'origen': 'inventario_documental_planeamiento', 'url': source,
            'inventory_url': source, 'documentos': [], 'source_sections': [],
            'publication_ready': False, 'geometry_status': 'unavailable',
        })
        if section not in row['source_sections']:
            row['source_sections'].append(section)
        known = {d['url'] for d in row['documentos']}
        row['documentos'].extend(d for d in docs if d['url'] not in known)

    if source == PGOM:
        for table in soup.select('table'):
            docs = documents(table, source)
            if docs and all('/documentos-pgom/' in d['url'] for d in docs):
                add('pgom', docs, 'Documentación PGOM')
    elif source == TRANSPARENCIA:
        for block in soup.select('.contentblock'):
            heading = block.find('h3', recursive=False)
            if not heading:
                continue
            title = heading.get_text(' ', strip=True)
            text = normalize(title)
            if 'registro de entidades urbanisticas' in text:
                continue  # A regulation, not a physical/planning project.
            docs = documents(block, source)
            if not docs:
                raise ValueError('Inventory section without documents: ' + title)
            if 'casa alegre' in text or 'modificacion ficha 10' in text:
                if 'consulta' in text:
                    add('casa-alegre-atu', docs, title)
                else:
                    # The shared announcement/certificate concerns both instruments.
                    add('casa-alegre-atu', [d for d in docs if 'MODF._FICHA' not in d['url']], title)
                    add('casa-alegre-ficha-10', [d for d in docs if '_ATU_' not in d['url']], title)
            elif 'decima' in text or 'modificacion n' in text and '10' in text:
                add('innovacion-10', docs, title)
            elif 'villarejo' in text:
                add('villarejo', docs, title)
            elif 'modificacion planes parciales' in text:
                if 'el zorrero' not in normalize(block.get_text(' ', strip=True)):
                    raise ValueError('Unreviewed partial-plan scope')
                add('zorrero', docs, title)
            else:
                raise ValueError('Unreviewed planning section: ' + title)
    else:
        raise ValueError('Unsupported inventory URL')
    if not records:
        raise ValueError('No usable planning instruments found')
    return list(records.values())


class PalomaresDelRioAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        rows = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipal-planning-inventory/1.0'
            for source in (TRANSPARENCIA, PGOM):
                response = session.get(source, timeout=40)
                response.raise_for_status()
                if response.url != source:
                    raise ValueError('Unexpected inventory redirect: ' + response.url)
                rows.extend(parse_inventory(response.text, source))
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(output)
        return {'count': len(rows), 'source_urls': [TRANSPARENCIA, PGOM],
                'coverage': 'current official document inventories; partial municipal coverage'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
