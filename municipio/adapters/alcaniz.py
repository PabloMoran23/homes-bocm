"""Alcañiz: two municipal inventories, grouped by instrument or public work."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

URBANISMO = 'https://sede2.alcaniz.es/portal-transparencia/urbanismo'
PLANEAMIENTO = 'https://www.alcaniz.es/index.php?option=com_content&view=article&id=894&Itemid=833&lang=es'
MONTHS = dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), range(1, 13)))


def _publication(text):
    match = re.fullmatch(r'BOP Teruel (\d{1,2}) (?:de )?(\w+) de (\d{4})', text)
    if not match or match[2] not in MONTHS:
        raise ValueError('Unrecognised BOP publication label: ' + text)
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


def _no_pagination(container):
    if container.select('.pagination, .pager, a[rel~=next]'):
        raise ValueError('Inventory now paginated; review traversal before extraction')
    for link in container.select('a[href]'):
        if link.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'última', 'ultima', '»', '>'}:
            raise ValueError('Unreviewed inventory pagination')


def _documents(container, source):
    docs = {}
    for a in container.select('a[href]'):
        url = urljoin(source, a['href'])
        if urlparse(url).scheme not in {'http', 'https'}:
            raise ValueError('Unsupported document link')
        docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                              'procedencia_url': source})
    return list(docs.values())


def _record(key, title, kind, source, docs):
    return {'id': 'alcaniz-proy-' + key, 'municipio': 'Alcañiz', 'codigo_ine': '44013',
            'provincia': 'Teruel', 'titulo': title, 'tipo': kind,
            'url': source, 'source': 'ayuntamiento', 'documentos': docs,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'fase': None,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'coverage': 'Partial snapshot of municipal PGOU and transparency inventories'}


class AlcanizAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_planning(html):
        soup = BeautifulSoup(html, 'html.parser')
        _no_pagination(soup.select_one('#main') or soup)
        article = soup.select_one('div.article')
        if not article or not article.select_one('h1') or article.h1.get_text(' ', strip=True) != 'Plan General de Ordenación Urbana':
            raise ValueError('Missing municipal PGOU article')
        headings = {h.get_text(' ', strip=True) for h in article.select('h2')}
        if not {'Documentación escrita', 'Documentación gráfica - planos', 'Publicación normas urbanísticas', 'Modificaciones aprobadas'} <= headings:
            raise ValueError('PGOU inventory structure changed')
        # One list item per amendment; its BOP and annex stay on that record.
        modifications = article.select('ol > li')
        if not modifications:
            raise ValueError('Missing amendment inventory')
        rows, modification_urls = [], set()
        numbers = set()
        for li in modifications:
            docs = _documents(li, PLANEAMIENTO)
            match = re.fullmatch(r'Modificación (\d+)', docs[0]['titulo']) if docs else None
            if not match or match[1] in numbers:
                raise ValueError('Ambiguous PGOU amendment')
            numbers.add(match[1])
            publication = [d for d in docs if d['titulo'].startswith('BOP Teruel')]
            if len(publication) != 1:
                raise ValueError('Missing or ambiguous amendment publication')
            row = _record('pgou-mod-' + match[1], 'Modificación ' + match[1] + ' del PGOU de Alcañiz',
                          'planeamiento_urbanistico', PLANEAMIENTO, docs)
            row['fecha_publicacion'] = _publication(publication[0]['titulo'])
            row['estado_fuente'] = 'Incluida en Modificaciones aprobadas; alcance de aprobación no verificado en PDF'
            rows.append(row)
            modification_urls.update(d['url'] for d in docs)
        docs = [d for d in _documents(article, PLANEAMIENTO)
                if d['url'] not in modification_urls and d['titulo'] != 'Plan General de Ordenación Urbana']
        publication = [d for d in docs if d['titulo'].startswith('BOP Teruel')]
        if len(publication) != 1 or not any(d['titulo'] == 'Memoria descriptiva' for d in docs):
            raise ValueError('Missing PGOU documentation or publication')
        plan = _record('pgou', 'Plan General de Ordenación Urbana de Alcañiz',
                       'planeamiento_urbanistico', PLANEAMIENTO, docs)
        plan['fecha_publicacion'] = _publication(publication[0]['titulo'])
        return [plan] + rows

    @staticmethod
    def parse_works(html):
        soup = BeautifulSoup(html, 'html.parser')
        _no_pagination(soup)
        heading = soup.find(['h1', 'h2'], string=lambda s: s and s.strip() == 'Urbanismo')
        candidates = [d for d in soup.select('div.fw_light.m_bottom_12') if 'Puede acceder' in d.get_text()]
        if not heading or len(candidates) != 1:
            raise ValueError('Missing transparency urbanismo inventory')
        rows = {}
        for p in candidates[0].find_all('p'):
            text = p.get_text(' ', strip=True)
            if not text.casefold().startswith('proyecto '):
                continue
            # Require a named physical work and the municipality's document link.
            match = re.match(r'(Proyecto básico y de ejecución (?:de la |de )[^;]+?)(?:; descarga PDF del Proyecto en:|\. Descarga de Proyecto en:)', text, re.I)
            docs = _documents(p, URBANISMO)
            if not match or not docs or not all(urlparse(d['url']).hostname == 'www.dropbox.com' and '/scl/' in d['url'] for d in docs):
                raise ValueError('Unreviewed public-work description or document host')
            title = match[1]
            if 'alcañiz' not in title.casefold():
                raise ValueError('Public work lacks municipality identity')
            key = hashlib.sha256(title.casefold().encode()).hexdigest()[:16]
            row = rows.setdefault(key, _record(key, title, 'proyecto_obra_publica', URBANISMO, []))
            row['descripcion'] = title
            row['documentos'] = list({d['url']: d for d in row['documentos'] + docs}.values())
        if not rows:
            raise ValueError('No named public works in transparency inventory')
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = []
        for name, url, parser in [('urbanismo', URBANISMO, self.parse_works),
                                  ('planeamiento', PLANEAMIENTO, self.parse_planning)]:
            with requests.get(url, timeout=35, stream=True, headers={
                'User-Agent': self.config.get('user_agent', 'municipio-alcaniz/1.0')}) as response:
                response.raise_for_status()
                if urlparse(response.url).hostname != urlparse(url).hostname:
                    raise ValueError('Unexpected inventory redirect')
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > 3_000_000:
                        raise ValueError('Inventory response too large')
                html = content.decode('utf-8')
            if self.config.get('capture_dir'):
                capture = Path(self.config['capture_dir'])
                capture.mkdir(parents=True, exist_ok=True)
                (capture / (name + '.html')).write_text(html, encoding='utf-8')
            rows.extend(parser(html))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [URBANISMO, PLANEAMIENTO],
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Both non-paginated inventories are refreshed in full; no date cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
