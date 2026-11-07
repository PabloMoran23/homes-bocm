"""Anonymous municipal urban-planning inventory; complete snapshot of this section."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.corberadellobregat.cat'
INVENTORY = BASE + '/ajuntament/urbanisme-i-territori'
MONTHS = 'gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split()
LIMITATIONS = [
    'Partial municipal coverage: only the current Urbanisme i territori section, not a historical register or all municipal works.',
    'No granted-licence register. Application forms and procurement/news are excluded.',
    'PDF links retained as municipal document provenance; PDF contents and project geometry are not parsed.',
    'Page update dates are not publication or agreement dates. Missing dates remain null.',
    'La Servera is retained as the combined reparcellation/urbanisation dossier presented by the municipality.',
]


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    article = soup.select_one('#readspeakerPage')
    if main is None or article is None or article.select_one('h1') is None:
        raise ValueError('Missing municipal article; possible error/login/markup change')
    # Fail visibly if the reviewed single-page inventories acquire pagination.
    if main.select('.pager a[href], .pagination a[href], a[rel~=next], [data-next-page]'):
        raise ValueError('Pagination detected; refusing an incomplete snapshot')
    return main, article


def inventory_links(html, url, selector):
    _, article = content(html)
    links = {}
    for a in article.select(selector):
        target = urljoin(url, a['href'])
        parsed = urlsplit(target)
        if (parsed.netloc != urlsplit(BASE).netloc or parsed.query or parsed.fragment
                or not parsed.path.startswith(urlsplit(url).path.rstrip('/') + '/')):
            raise ValueError('Unexpected inventory target: ' + target)
        links[target] = a.get_text(' ', strip=True)
    if not links:
        raise ValueError('Empty municipal inventory')
    return list(links)


def documents(node, url):
    result = {}
    for a in node.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlsplit(target)
        if (parsed.netloc == urlsplit(BASE).netloc and parsed.path.startswith('/media/')
                and parsed.path.lower().endswith('.pdf')):
            label = re.sub(r'\s*\([\d.,]+\s*(?:MB|KB)\)\s*$', '', a.get_text(' ', strip=True))
            result[target] = {'titulo': label, 'url': target, 'pagina_origen': url}
    if not result:
        raise ValueError('Project has no municipal source documents: ' + url)
    return list(result.values())


def record(title, url, docs, key, kind, phase=None, phase_source=None, agreement=None, updated=None):
    return {
        'id': 'corbera-proy-' + hashlib.sha256(key.encode()).hexdigest()[:20],
        'municipio': 'Corbera de Llobregat', 'codigo_ine': '08072', 'provincia': 'Barcelona',
        'titulo': title, 'tipo': kind, 'fase': phase, 'fase_fuente': phase_source,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': agreement,
        'fecha_aprob': agreement, 'fecha_actualizacion_pagina': updated,
        'url': url, 'url_documento': docs[0]['url'], 'documentos': docs,
        'source': 'ayuntamiento', 'origen': 'urbanisme_i_territori',
        'source_inventory': INVENTORY, 'source_entity_type': 'actuacion',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'coverage': 'partial_current_section',
    }


def updated_date(article):
    el = article.select_one('.updated')
    match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', el.get_text() if el else '')
    return date(int(match[3]), int(match[2]), int(match[1])).isoformat() if match else None


class CorberaDeLlobregatAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_dossier(html, url):
        main, article = content(html)
        title = article.select_one('h1').get_text(' ', strip=True)
        if not title.lower().startswith('projecte de reparcel·lació'):
            raise ValueError('Unsupported dossier title: ' + title)
        docs = documents(main.select_one('.documents') or article, url)
        agreement = None
        match = re.search(r'Junta de Govern Local de (\d{1,2}) de (\w+) de (\d{4})', title)
        if match:
            agreement = date(int(match[3]), MONTHS.index(match[2]) + 1, int(match[1])).isoformat()
        evidence = next((d['titulo'] for d in docs if 'aprovació definitiva' in d['titulo'].lower()), None)
        phase_source = title if 'aprovat definitivament' in title.lower() else evidence
        return [record(title, url, docs, url, 'reparcelacion_urbanizacion',
                       'aprobación definitiva' if phase_source else None,
                       phase_source, agreement, updated_date(article))]

    @staticmethod
    def parse_fire_projects(html, url, parent_url, parent_title):
        _, article = content(html)
        location = article.select_one('h1').get_text(' ', strip=True)
        body = article.select_one('.ddbbtext')
        if body is None or not body.select('h2'):
            raise ValueError('No technical project sections: ' + url)
        rows = []
        for heading in body.select('h2'):
            title = heading.get_text(' ', strip=True)
            if not title:
                continue  # The live CMS includes trailing empty layout headings.
            if not title.startswith('Projecte de reducció'):
                raise ValueError('Unreviewed technical project heading: ' + title)
            group = BeautifulSoup('<div></div>', 'html.parser').div
            for sibling in heading.next_siblings:
                if getattr(sibling, 'name', None) == 'h2':
                    break
                group.append(BeautifulSoup(str(sibling), 'html.parser'))
            docs = documents(group, url)
            # A memory, budget, specifications and drawings are one project.
            key = url + '#' + title
            row = record(title + ' — ' + location, url, docs, key, 'proyecto_prevencion_incendios',
                         'aprobación inicial', parent_title, updated=updated_date(article))
            row['fase_url'] = parent_url
            row['ambito'] = location
            rows.append(row)
        if not rows or {d['url'] for d in documents(body, url)} != {
                d['url'] for row in rows for d in row['documentos']}:
            raise ValueError('Ungrouped technical documents: ' + url)
        return rows

    def _fetch(self, url):
        with requests.get(url, timeout=(10, 45), stream=True,
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-corbera/1.0')}) as response:
            response.raise_for_status()
            if urlsplit(response.url).netloc != urlsplit(BASE).netloc:
                raise ValueError('Unexpected off-site redirect')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected HTML inventory/detail')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Municipal HTML exceeds response size limit')
            html = data.decode('utf-8')
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir'])
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        source_urls = [INVENTORY]
        rows = []
        for url in inventory_links(self._fetch(INVENTORY), INVENTORY, '.widgetMenu a[href]'):
            source_urls.append(url)
            html = self._fetch(url)
            _, article = content(html)
            title = article.select_one('h1').get_text(' ', strip=True)
            if title.startswith('Projecte de reparcel·lació'):
                rows.extend(self.parse_dossier(html, url))
            elif title.startswith('Aprovació inicial dels projectes executius del Pla de prevenció'):
                for child in inventory_links(html, url, '.card-title a[href]'):
                    source_urls.append(child)
                    rows.extend(self.parse_fire_projects(self._fetch(child), child, url, title))
            else:
                raise ValueError('Unreviewed inventory entry: ' + title)
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate project identity')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full current-section refresh; state is not a historic completeness claim.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
