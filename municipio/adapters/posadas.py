"""Posadas (Córdoba): municipal planning inventory, never licence applications."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://posadas.es/ayuntamiento/normativa-y-documentos/'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
LIMITATIONS = [
    'Inventario documental municipal actual, no censo exhaustivo de expedientes ni de obras ejecutadas.',
    'Sin licencias, coordenadas ni afirmación de vigencia; las fases de anuncios son históricas.',
    'Se omiten convenios, juntas de compensación, enlaces genéricos de modificaciones y documentos antiguos 1405301 cuya identidad no se resuelve aquí.',
    'Solo se lee el contenido de anuncios BOP enlazados; los demás documentos se conservan como enlaces sin validar su contenido o disponibilidad.',
]


def _text(tag):
    return ' '.join(tag.get_text(' ', strip=True).split())


def _link(a):
    url = urljoin(SOURCE, a['href'])
    # The live municipal page has a broken attribute on Ordenación Hoja 1.
    url = url.split(' title=')[0]
    if urlparse(url).hostname != 'posadas.es' or not urlparse(url).path.lower().endswith('.pdf'):
        return None
    return {'titulo': _text(a), 'url': url, 'inventory_url': SOURCE}


def inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find('h2', string=lambda s: s and s.strip() == 'Documentos PGOU')
    if not heading or not heading.parent.select_one('.et_pb_toggle_content'):
        raise ValueError('Missing municipal PGOU inventory')
    if soup.select('a[rel~=next], .pagination, .nav-links .next, .page-links'):
        raise ValueError('Pagination detected: inventory must be researched before extraction')
    links = [d for a in heading.parent.select('a[href]') if (d := _link(a))]
    if not links:
        raise ValueError('Empty PGOU inventory')
    return soup, links


def parse_notice(text):
    """Read agreement and bulletin dates separately, not the mayor's signature."""
    text = ' '.join(text.split())
    if 'Ayuntamiento de Posadas' not in text or 'Modificación Puntual del PGOU de Posadas' not in text:
        raise ValueError('Not a Posadas planning modification notice')
    bulletin = re.search(r'\b(\d{1,2}) de (\w+) de (\d{4})', text, re.I)
    agreement = re.search(r'sesión celebrada el día (\d{1,2}) de (\w+) de (\d{4})', text, re.I)
    gex = re.search(r'GEX\s+(\d+/\d{4})', text)
    body = re.search(r'se ha acordado aprobar inicialmente (.*?) Conforme al artículo', text)
    if not all((bulletin, agreement, gex, body)):
        raise ValueError('Incomplete modification notice')
    def iso(match):
        return date(int(match[3]), MONTHS.index(match[2].lower()) + 1, int(match[1])).isoformat()
    narrative = body[1].strip().rstrip('.')
    obj = re.search(r'cuyo objeto consiste en (.*)', narrative)
    if not obj:
        obj = re.search(r', para (.*)', narrative)
    if not obj:
        raise ValueError('Missing modification object')
    return {'titulo': 'Modificación puntual del PGOU de Posadas: ' + obj[1],
            'expediente': gex[1], 'descripcion': narrative,
            'fase': 'aprobación inicial', 'fecha_acuerdo': iso(agreement),
            'fecha_publicacion': iso(bulletin)}


def _record(key, title, docs, **extra):
    return {'id': 'posadas-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Posadas', 'provincia': 'Córdoba', 'codigo_ine': '14053',
            'titulo': title, 'tipo': 'instrumento de planeamiento',
            'url': docs[0]['url'], 'inventory_url': SOURCE, 'documentos': docs,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'publication_ready': False, 'geometry_status': 'unavailable', **extra}


def parse_projects(html, notice_reader):
    soup, links = inventory(html)
    rows = []
    for i, doc in enumerate(links):
        if not re.search(r'/ANUNCIO-PUBLICADO-EN-EL-BOP-A-\d{4}-\d+\.pdf$', doc['url']):
            continue
        data = parse_notice(notice_reader(doc['url']))
        docs = [doc]
        # Each announcement is immediately followed by its technical document.
        if i + 1 >= len(links) or not re.search(r'/DOCUMENTO-(TECNICO-)?DILIGENCIADO', links[i+1]['url']):
            raise ValueError('Modification has no adjacent technical document')
        docs.append(links[i+1])
        # Repeated initial-approval documents have more descriptive filenames.
        token = {'4051/2024': 'PGOU-NORMAS-URBANISTICA',
                 '7873/2024': 'PGOU-INNOV.-PUNTUAL-CALIFIC.'}.get(data['expediente'])
        if token:
            docs.extend(d for d in links if token in d['url'])
        title = data.pop('titulo')
        rows.append(_record('gex:' + data['expediente'], title, docs, **data))
    # Maps, infrastructure drawings, norms and environmental volumes are one PGOU.
    pgou = [d for d in links if re.search(r'/1405300', d['url'], re.I)
            or re.search(r'/(boja_posadas|boja_no_11_p-94-04_posadas|cert_ads_p-94-04_posadas|pgou_hitos_de_tramitacion|normas_pgou_posadas|ordenacion_completa_hoja_\d)\.pdf$', d['url'], re.I)]
    if not pgou:
        raise ValueError('Missing PGOU documents')
    rows.append(_record('pgou', 'Plan General de Ordenación Urbanística de Posadas', pgou))
    for doc in links:
        if re.match(r'^(Estudio de detalle para|Plan Parcial del Sector)', doc['titulo'], re.I):
            rows.append(_record(doc['url'], doc['titulo'], [doc]))
    for heading in soup.select('h2.et_pb_toggle_title'):
        title = _text(heading)
        if not (title == 'Plan Municipal de Vivienda y Suelo'
                or title.startswith('Plan de movilidad urbana sostenible')
                or title.startswith('Plan Local de instalaciones y equipamientos deportivos')):
            continue
        docs = [d for a in heading.parent.select('a[href]') if (d := _link(a))]
        if not docs:
            raise ValueError('Empty named plan section: ' + title)
        rows.append(_record('section:' + title, title + ' — Posadas', docs))
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Empty or duplicate planning records')
    return rows


class PosadasAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        with requests.get(url, timeout=60, stream=True,
                          headers={'User-Agent': 'Mozilla/5.0 (compatible; PosadasPlanning/1.0)'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'posadas.es':
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 25_000_000:
                    raise ValueError('Source exceeds size limit; refusing partial extraction')
                chunks.append(chunk)
            content = b''.join(chunks)
        if self.config.get('capture_dir'):
            target = Path(self.config['capture_dir'])
            target.mkdir(parents=True, exist_ok=True)
            name = unquote(urlparse(url).path.rsplit('/', 1)[-1]) or 'index'
            if not name.endswith('.pdf'):
                name += '.html'
            (target / name).write_bytes(content)
        return content

    def _notice(self, url):
        content = self._fetch(url)
        if not content.startswith(b'%PDF-'):
            raise ValueError('Notice is not a PDF')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'notice.pdf'
            path.write_bytes(content)
            result = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                                    check=True, capture_output=True, timeout=30)
        return result.stdout.decode('utf-8')

    def backfill_proyectos(self, out_jsonl):
        rows = parse_projects(self._fetch(SOURCE).decode('utf-8'), self._notice)
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'source_urls': [SOURCE], 'limitations': LIMITATIONS,
                'coverage': 'partial_current_municipal_planning_inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
