"""Partial snapshot of the municipal NNSS documentary inventory, not licences."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.cullarvega.com/urbanismo/'
MONTHS = dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Cobertura parcial: sección Normas Subsidiarias del inventario municipal de Urbanismo; no es un histórico completo.',
    'El PGOM anunciado como en inicio, sin documentación enlazada, no se incorpora.',
    'Enlaces documentales conservados como publicados por el ayuntamiento; no se verifica su contenido ni vigencia jurídica.',
    'El PDF NNSS devolvió HTTP 403; los enlaces BOP antiguos redirigen al buscador genérico (ver evidencia de investigación).',
    'Planos agrupados como cartografía de la sección; no se acredita su pertenencia formal a una versión del instrumento.',
    'Sin registro de licencias concedidas ni geometría verificada; fechas desconocidas y coordenadas quedan nulas.',
]


def _date(text):
    match = re.search(r'(\d{1,2})(?:\s*/\s*|\s+de\s+)(\w+)(?:\s*/\s*|\s+de\s+)(\d{4})', text.lower())
    if not match or match[2] not in MONTHS:
        return None
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


def _link(a, role):
    url = urljoin(SOURCE, a['href'])
    if urlparse(url).scheme != 'https' or urlparse(url).hostname not in {'www.cullarvega.com', 'cullarvega.com', 'bop2.dipgra.es', 'bop.dipgra.es'}:
        raise ValueError('Unexpected planning document host; review source')
    return {'titulo': a.get_text(' ', strip=True), 'url': url,
            'rol': role, 'pagina_origen': SOURCE, 'contenido_verificado': False}


class CullarVegaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.cullarvega.com')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('.post_content')
        if content is None:
            raise ValueError('Missing municipal content')
        for a in soup.select('a[href]'):
            if 'next' in a.get('rel', []) or a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'mostrar más', 'más resultados'}:
                raise ValueError('Pagination detected; extend inventory traversal before extraction')
        heading = next((h for h in content.find_all('h2') if h.get_text(' ', strip=True).upper() == 'NORMAS SUBSIDIARIAS'), None)
        if heading is None:
            raise ValueError('NNSS inventory section missing')
        blocks = []
        for sibling in heading.next_siblings:
            if getattr(sibling, 'name', None) in {'h2', 'hr'}:
                break
            blocks.append(str(sibling))
        section = BeautifulSoup(''.join(blocks), 'html.parser')
        narrative = next((p.get_text(' ', strip=True) for p in section.find_all('p') if 'Las Normas Subsidiarias de Cúllar Vega' in p.get_text()), None)
        primary = next((a for a in section.select('a[href]') if a.get_text(' ', strip=True) == 'Revisión de las Normas Subsidiarias'), None)
        if not narrative or primary is None:
            raise ValueError('No verified NNSS narrative and document link')

        def record(key, title):
            return {'id': 'cullar-vega-proy-' + key, 'municipio': 'Cúllar Vega',
                    'provincia': 'Granada', 'codigo_ine': '18057', 'titulo': title,
                    'tipo': 'planeamiento_urbanistico', 'fase': None,
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanismo',
                    'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                    'publication_ready': False, 'cobertura': 'parcial', 'limitaciones': LIMITATIONS}

        nnss = record('nnss', 'Revisión de las Normas Subsidiarias de Cúllar Vega')
        nnss['descripcion'] = narrative
        nnss['documentos'].append(_link(primary, 'documento NNSS enlazado por el ayuntamiento'))
        if 'aprobación definitiva' in narrative.lower():
            nnss['fase'] = 'aprobación definitiva'
            nnss['fecha_aprob'] = _date(narrative)
        rows = [nnss]
        for li in section.find_all('li'):
            text = li.get_text(' ', strip=True)
            if not text.startswith('Texto íntegro'):
                continue
            links = li.select('a[href]')
            if not links:
                raise ValueError('Published planning instrument lacks its document link')
            if 'Adaptación Parcial Normas Subsidiarias a la LOUA' in text:
                target = next((r for r in rows if r['id'].endswith('-adaptacion-loua')), None)
                if target is None:
                    target = record('adaptacion-loua', 'Adaptación Parcial de las Normas Subsidiarias de Cúllar Vega a la LOUA')
                    target['descripcion'] = text
                    rows.append(target)
            elif 'Texto íntegro Normas Subsidiarias:' in text:
                target = nnss
            else:
                raise ValueError('Unrecognized planning instrument; review grouping')
            published = _date(text)
            if target['fecha_publicacion'] and published != target['fecha_publicacion']:
                raise ValueError('Conflicting publication dates')
            target['fecha_publicacion'] = published
            for a in links:
                doc = _link(a, 'referencia BOP publicada por el ayuntamiento')
                doc['fecha_publicacion'] = published
                target['documentos'].append(doc)
        for a in section.select('a[href]'):
            if 'zonificacion' in a.get_text(' ', strip=True).lower():
                nnss['documentos'].append(_link(a, 'cartografía publicada en la sección NNSS; vinculación formal no verificada'))
        for row in rows:
            row['documentos'] = list({d['url']: d for d in row['documentos']}.values())
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'municipio-cullar-vega/1.0'})
        response.raise_for_status()
        if urlparse(response.url).path.rstrip('/') != '/urbanismo' or urlparse(response.url).hostname != 'www.cullarvega.com':
            raise ValueError('Unexpected inventory redirect')
        rows = self.parse_projects(response.text)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'urbanismo-live.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
