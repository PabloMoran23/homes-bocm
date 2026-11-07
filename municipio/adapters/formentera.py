"""Curated Consell urbanism planning inventory (not the historical notice board)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.consellinsulardeformentera.cat'
SOURCE = BASE + '/index.php?option=com_content&view=category&id=110&Itemid=525&lang=ca&layout=default'
MONTHS = dict(zip('gener febrer marc abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def article_url(href):
    url = urlparse(urljoin(BASE, href))
    q = parse_qs(url.query)
    if url.hostname != urlparse(BASE).hostname or q.get('view') != ['article'] or q.get('option') != ['com_content']:
        return None
    ident = q.get('id', [''])[0].split(':')[0]
    if not ident.isdigit():
        return None
    return BASE + '/index.php?' + urlencode(dict(option='com_content', view='article', id=ident, lang='ca'))


def instrument_key(title):
    text = norm(title)
    m = re.search(r'modificacio\s+(?:puntual\s+)?num\.?\s*(\d+)', text)
    if m and any(t in text for t in ('formentera', 'nnss', 'pti')):
        return 'mod-' + m[1]
    # The 2013 consolidated page explicitly identifies amendment 1 in its body.
    if 'text refos i planimetria nnss 2013' in text:
        return 'mod-1'
    if 'revisio' in text and 'nnss' in text and '2010' in text:
        return 'nnss-2010'
    return None


def publication_date(text):
    m = re.search(r"(\d{1,2})\s+(?:de\s+|d['’])(\w+)\s+de\s+(\d{4})", norm(text))
    if not m or m[2] not in MONTHS:
        raise ValueError('Unrecognized municipal publication date: ' + text)
    return date(int(m[3]), MONTHS[m[2]], int(m[1])).isoformat()


def phase(title):
    text = norm(title)
    return next(('aprobación ' + es for ca, es in [('definitiva', 'definitiva'), ('inicial', 'inicial')]
                 if 'aprovacio ' + ca in text), None)


class FormenteraAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        menus = [menu for menu in soup.select('ul.menu')
                 if any('Text refós i planimetria NNSS 2013' in a.get_text(' ', strip=True)
                        for a in menu.select('a[href]'))]
        if len(menus) != 1:
            raise ValueError('Missing or ambiguous curated urbanism menu')
        menu = menus[0]
        if menu.select('.pagination, a[rel=next]'):
            raise ValueError('Curated planning inventory has unsupported pagination')
        groups = {}
        for a in menu.select('a[href]'):
            title = a.get_text(' ', strip=True)
            url = article_url(a['href'])
            if not url:
                continue  # category links (news/notice archive) are outside this inventory
            key = instrument_key(title)
            if not key:
                if norm(title) == 'cadastre':
                    continue
                raise ValueError('Unrecognized curated inventory entry: ' + title)
            group = groups.setdefault(key, {'titulo': title, 'url': url, 'pages': {}})
            group['pages'].setdefault(url, title)
            # Prefer the definitive-stage title over an earlier stage.
            if phase(title) == 'aprobación definitiva' and phase(group['titulo']) != 'aprobación definitiva':
                group.update(titulo=title, url=url)
        if not groups:
            raise ValueError('Empty planning inventory requires review')
        return groups

    @staticmethod
    def parse_detail(html, url):
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.select_one('.rt-article')
        if not body or not body.select_one('h1.rt-article-title'):
            raise ValueError('Missing planning article at ' + url)
        if body.select('.pagination, a[rel=next], .pagenavcounter'):
            raise ValueError('Planning article has unsupported pagination: ' + url)
        title = body.select_one('h1.rt-article-title').get_text(' ', strip=True)
        posted = body.select_one('.rt-date-posted')
        published = publication_date(posted.get_text(' ', strip=True)) if posted else None
        docs, children = {}, {}
        for a in body.select('a[href]'):
            # Joomla print, email and generated PDF controls are not source documents.
            if a.find_parent(class_='rt-article-icons'):
                continue
            target = urljoin(url, a['href'])
            parsed = urlparse(target)
            label = a.get_text(' ', strip=True) or a.get('title') or parsed.path.rsplit('/', 1)[-1]
            child = article_url(target)
            if child:
                children[child] = label
            elif (parsed.hostname == urlparse(BASE).hostname and parsed.path.startswith('/images/')) or (
                parsed.hostname in {'www.caib.es', 'caib.es', 'www.boe.es'} and
                ('/eboibfront/pdf/' in parsed.path or parsed.path.lower().endswith('.pdf'))
            ):
                docs[target] = {'titulo': label, 'url': target, 'source_urls': [url]}
        return {'url': url, 'titulo': title, 'fecha_publicacion': published, 'fase': phase(title),
                'descripcion': body.get_text(' ', strip=True)}, list(docs.values()), children

    def _fetch(self, session, url):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        if len(response.content) > 5_000_000:
            raise ValueError('Unexpectedly large planning page: ' + url)
        response.encoding = 'utf-8'
        html = response.text
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (directory / name).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Municipio-Formentera/1.0 (public planning inventory)'
            groups = self.parse_inventory(self._fetch(session, SOURCE))
            for key, group in groups.items():
                queue = dict(group['pages'])
                pages, docs = {}, {}
                while queue:
                    url = next(iter(queue))
                    queue.pop(url)
                    if url in pages:
                        continue
                    page, attachments, children = self.parse_detail(self._fetch(session, url), url)
                    # Consolidated 2013 page proves the alias rather than trusting the menu alone.
                    if 'text refos i planimetria nnss 2013' in norm(page['titulo']):
                        if instrument_key(page['descripcion']) != 'mod-1':
                            raise ValueError('2013 consolidated plan no longer identifies amendment 1')
                    elif key != 'nnss-2010' and instrument_key(page['titulo']) != key:
                        raise ValueError('Detail does not match its planning instrument: ' + url)
                    elif key == 'nnss-2010' and not ('revisio' in norm(page['titulo']) and 'nnss' in norm(page['titulo'])):
                        raise ValueError('Missing NNSS revision detail')
                    pages[url] = page
                    for doc in attachments:
                        if doc['url'] in docs:
                            if url not in docs[doc['url']]['source_urls']:
                                docs[doc['url']]['source_urls'].append(url)
                        else:
                            docs[doc['url']] = doc
                    for child, title in children.items():
                        if child == url or child in pages:
                            continue
                        if instrument_key(title) != key:
                            raise ValueError('Unexpected linked planning article: ' + title)
                        queue[child] = title
                if not docs:
                    raise ValueError('Instrument has no supporting documents: ' + key)
                primary = pages[group['url']]
                rows.append({
                    'id': 'formentera-proy-' + key, 'municipio': 'Formentera', 'codigo_ine': '07024',
                    'provincia': 'Illes Balears', 'titulo': group['titulo'],
                    'tipo': 'planeamiento_urbanistico', 'fase': phase(group['titulo']),
                    'fecha': None, 'fecha_publicacion': primary['fecha_publicacion'],
                    'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': group['url'], 'source': 'ayuntamiento', 'origen': 'inventario_urbanismo',
                    'source_inventory_url': SOURCE, 'paginas_fuente': list(pages.values()),
                    'documentos': list(docs.values()),
                    'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                    'publication_ready': False,
                    'date_notes': 'Publication dates are municipal article dates only. Agreement/approval dates not extracted from linked documents.',
                })
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [SOURCE] + [p['url'] for r in rows for p in r['paginas_fuente']],
                'coverage': 'Curated urbanism menu only; historical notice categories excluded'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
