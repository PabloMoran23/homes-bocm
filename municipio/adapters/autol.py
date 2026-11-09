"""Autol's published Urbanismo document inventory; no licence inference."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://aytoautol.larioja.org/ayuntamiento/urbanismo'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
LIMITATIONS = [
    'Inventario documental de Urbanismo, no registro exhaustivo ni garantía de vigencia.',
    'No cubre proyectos de las páginas separadas Pasarela río Cidacos y Auditorio municipal, ni sede, actas o BOR completo.',
    'Documentos enlazados conservados; no se extrae el contenido de PDF/DWG ni se verifica cada descarga.',
    'Fechas de publicación son del BOR según el texto municipal; no son fechas de publicación web ni de aprobación definitiva.',
    'Sin licencias concedidas, coordenadas ni geometría; sin inferir ejecución o vigencia.',
]


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def spanish_date(text):
    match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', normalize(text))
    if not match:
        return None
    day, month, year = match.groups()
    return date(int(year), MONTHS.index(month) + 1, int(day)).isoformat()


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('[itemprop="articleBody"]')
    if body is None:
        raise ValueError('Urbanismo article body missing')
    if soup.select('a[rel~="next"], .pagination a[href], .pagenav a[href], .article-index a[href]'):
        raise ValueError('Pagination appeared: review crawler before extracting partial inventory')
    sections = []
    current = None
    for node in body.descendants:
        if getattr(node, 'name', None) == 'h1':
            title = node.get_text(' ', strip=True)
            current = None
            if re.match(r'^(proyecto de |modificacion |plan general |plan parcial )', normalize(title)):
                current = {'title': title, 'strings': [], 'docs': {}}
                sections.append(current)
        if current is None:
            continue
        if isinstance(node, NavigableString) and node.strip():
            current['strings'].append(str(node).strip())
        if getattr(node, 'name', None) == 'a' and node.get('href'):
            target = urljoin(url, node['href'])
            parsed = urlparse(target)
            local = parsed.hostname in {'aytoautol.larioja.org', 'www.aytoautol.larioja.org'}
            bor = parsed.hostname == 'ias1.larioja.org' and parsed.path.startswith('/boletin/')
            if (local and parsed.path.lower().endswith(('.pdf', '.dwg'))) or bor:
                if local:
                    target = parsed._replace(scheme='https', netloc='aytoautol.larioja.org').geturl()
                current['docs'].setdefault(target, {
                    'titulo': node.get_text(' ', strip=True), 'url': target,
                    'source_url': url, 'procedencia': 'enlace en inventario municipal',
                })
    rows = {}
    for section in sections:
        if not section['docs']:
            raise ValueError('Instrument without documents: ' + section['title'])
        title = section['title']
        text = ' '.join(section['strings'])
        key = 'autol-proy-' + hashlib.sha256(normalize(title).strip(' .').encode()).hexdigest()[:16]
        if key in rows:
            raise ValueError('Duplicate instrument heading')
        row = {
            'id': key, 'municipio': 'Autol', 'codigo_ine': '26021', 'provincia': 'La Rioja',
            'titulo': title, 'tipo': 'obra_publica' if normalize(title).startswith('proyecto de ') else 'planeamiento_urbanistico',
            'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
            'descripcion': text, 'documentos': list(section['docs'].values()),
            'publication_ready': False, 'geometry_status': 'unavailable',
        }
        # Only explicit BOR publication expressions, bounded to this instrument.
        publication = re.search(
            r'(?:publicad[oa]|anuncio) en el b\.o\.r\..*?(\d{1,2} de \w+ de \d{4})',
            normalize(text), re.S,
        )
        if publication:
            row['fecha_publicacion'] = spanish_date(publication.group(1))
            row['fecha_publicacion_fuente'] = 'BOR, fecha indicada en inventario municipal'
        agreement = re.search(
            r'aprobado inicialmente por el pleno.*?(\d{1,2} de \w+ de \d{4})', normalize(text), re.S,
        )
        if agreement:
            row['fecha_acuerdo'] = spanish_date(agreement.group(1))
            row['fase'] = 'aprobacion_inicial'
            row['fase_fuente'] = 'Texto municipal; hito histórico, no estado actual verificado'
        rows[key] = row
    if not rows:
        raise ValueError('No supported instruments; review source')
    return list(rows.values())


class AutolAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=35, headers={'User-Agent': 'municipio-autol/1.0'})
        response.raise_for_status()
        if response.url != SOURCE:
            raise ValueError('Unexpected inventory redirect: ' + response.url)
        rows = parse_inventory(response.content, response.url)
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_bytes(response.content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'live_records': len(rows), 'source_urls': [SOURCE],
                'documents': sum(len(r['documentos']) for r in rows), 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
