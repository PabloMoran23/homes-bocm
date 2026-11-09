"""Pechina's public planning document inventory (Domino/XPages)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.pechina.es/Servicios/cmsdipro/index.nsf/tablon_view.xsp?p=Pechina'
HOST = 'www.pechina.es'

# Reviewed members of one adaptation package, not output records. Discovery and
# retrieval remain live; additions require provenance review before grouping.
REVIEWED_DOCUMENT_IDS = frozenset({
    '0F76A55EB51CFA85C12577EA004922A9',
    '10322DDD20AE0E7FC12577EA004C83B5',
    '136FC8CA09FC9934C12577EA0047ED61',
    '1FC7E364097AA4CEC12577EA0039AC2A',
    '217837F4F7793111C12577EA00498BD1',
    '22A5DA6BDA3E1F17C12577EA003119DA',
    '238A20A9C3BBDF95C12577EA0048CA0C',
    '275BCF722900E12DC12577EA004CCE1A',
    '2E0D449F2EC7B9C0C12577EA00400C50',
    '46B407F0A58434F3C12577EA003E431F',
    '49DF80504C83E7BFC12577EA0045901D',
    '5AC4822B5D5A0CEDC12577EA003AA67F',
    '7A0D243A94318CE5C12577EA0040A917',
    '7CD973DF349925B6C12577EA00304257',
    '808121DEE470CAFCC12577EA004D0744',
    '8488945C6D92E394C12577EA004A1C7A',
    '87774322CD3E4778C12577EA004C35B1',
    '9B889475FF59DEF0C12577EA0049F286',
    'B15DE189AAAB26DCC12577EA003D7B36',
    'B1995C861192B023C12577EA002D5464',
    'C02AC27E39F56AFAC12577EA003F847E',
})


def soup(html):
    return BeautifulSoup(html, 'html.parser')


def document_links(html):
    result = {}
    for a in soup(html).select('a[href]'):
        url = urljoin(SOURCE, a['href'])
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if parsed.hostname == HOST and parsed.path.endswith('/tablon.xsp'):
            if query.get('p') != ['Pechina']:
                raise ValueError('Foreign municipality in planning inventory')
            uid = query.get('documentId', [''])[0]
            if not re.fullmatch('[0-9A-Fa-f]{32}', uid):
                raise ValueError('Invalid document identifier')
            result[uid.upper()] = url
    return result


def parse_detail(html, url):
    page = soup(html)
    heading = page.select_one('#doc-dipalme-titulo h1')
    if not heading:
        raise ValueError('Missing municipal document heading')
    text = page.get_text(' ', strip=True)
    # Municipality selector/footer alone is insufficient proof of ownership.
    if not page.find('h2', string='Ayuntamiento de Pechina') or 'Territorio - Planeamiento Urbanístico' not in text:
        raise ValueError('Document is not Pechina planning material')
    date = re.search(r'Publicado:\s*(\d{2}/\d{2}/\d{4})', text)
    return {'titulo': heading.get_text(' ', strip=True), 'url': url,
            'fecha_publicacion': datetime.strptime(date[1], '%d/%m/%Y').date().isoformat() if date else None}


def parse_attachments(html, uid):
    page = soup(html)
    if 'Ayuntamiento de Pechina' not in page.get_text(' ', strip=True):
        raise ValueError('Foreign original document')
    docs = {}
    for a in page.select('a[href]'):
        target = urljoin(SOURCE, a['href'])
        path = urlparse(target).path
        if urlparse(target).hostname == HOST and re.search('/' + uid + r'/\$FILE/', path, re.I):
            docs[target] = {'titulo': a.get_text(' ', strip=True), 'url': target}
    if not docs:
        raise ValueError('Document has no original attachments')
    return list(docs.values())


class PechinaAyuntamientoAdapter(AyuntamientoAdapter):
    """Full refresh of the reviewed Territorio branch; licences are disabled."""

    def _request(self, session, url, data=None):
        response = session.get(url, timeout=40) if data is None else session.post(url, data=data, timeout=40)
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Unexpected source redirect')
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            self._capture_number += 1
            (directory / f'capture-{self._capture_number:04d}.html').write_text(response.text, encoding='utf-8')
        return response.text

    def _post(self, session, html, event):
        data = {a['name']: a.get('value', '') for a in soup(html).select('input[name]')}
        if not data.get('$$viewid'):
            raise ValueError('Missing XPages state')
        data.update({'$$xspsubmitid': event, '$$xspexecid': 'view:_id6:viewPanel1',
                     '$$xspsubmitvalue': '', '$$xspsubmitscroll': '0|0'})
        return self._request(session, SOURCE, data)

    def _pages(self, session, html):
        seen = set()
        for _ in range(200):
            page = soup(html)
            panel = page.find(id='view:_id6:viewPanel1')
            if panel is None:
                raise ValueError('Missing inventory table')
            signature = str(panel)
            if signature in seen:
                raise ValueError('Pagination loop')
            seen.add(signature)
            yield html
            next_link = page.select_one('a[id*="__Next__lnk"]')
            if not next_link:
                return
            html = self._post(session, html, next_link['id'].removesuffix('__lnk'))
        raise ValueError('Pagination safety limit reached; no output written')

    def _open_branch(self, session, labels):
        html = self._request(session, SOURCE)
        position = None
        for label in labels:
            found = None
            for candidate in self._pages(session, html):
                for a in soup(candidate).select('a[id*="__expand:"]'):
                    if a.get_text(' ', strip=True) == label:
                        found = (candidate, a['id'])
                        break
                if found:
                    break
            if not found:
                raise ValueError(f'Missing inventory branch: {label}')
            html, control = found
            position = control.split('__expand:')[1].removesuffix('link')
            html = self._post(session, html, control.removesuffix('link'))
        return html, position

    def _inventory(self, session, labels=('Territorio',)):
        html, position = self._open_branch(session, labels)
        links, children = {}, {}
        for page in self._pages(session, html):
            links.update(document_links(page))
            for a in soup(page).select('a[id*="__expand:"]'):
                child = a['id'].split('__expand:')[1].removesuffix('link')
                if child.startswith(position + '.'):
                    if child.count('.') != position.count('.') + 1:
                        raise ValueError('Unexpected tree depth')
                    children[child] = a.get_text(' ', strip=True)
        for label in children.values():
            links.update(self._inventory(session, (*labels, label)))
        return links

    def backfill_proyectos(self, out_jsonl):
        self._capture_number = 0
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipal-planning-inventory/1.0'
            inventory = self._inventory(session)
            if not inventory:
                raise ValueError('Empty planning inventory')
            documents = []
            for uid, url in sorted(inventory.items()):
                document = parse_detail(self._request(session, url), url)
                original = f'https://{HOST}/Servicios/Tablon/Tablon.nsf/0/{uid}?OpenDocument'
                document['original_url'] = original
                document['adjuntos'] = parse_attachments(self._request(session, original), uid)
                documents.append(document)
        rows = group_documents(documents)
        result = self._write(out_jsonl, rows)
        return {**result, 'coverage': 'reviewed_current_territorio_inventory', 'documents': len(documents),
                'source_urls': [SOURCE, *inventory.values()]}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)


def group_documents(documents):
    # The current branch is a disaggregated package. Fail on unreviewed additions
    # rather than assigning a new instrument to the existing package.
    identifiers = {parse_qs(urlparse(d['url']).query).get('documentId', [''])[0].upper() for d in documents}
    if not identifiers <= REVIEWED_DOCUMENT_IDS:
        raise ValueError('Unreviewed planning documents; grouping requires review')
    if not documents or not any('ADPATACION NN.SS.' in d['titulo'].upper() for d in documents):
        raise ValueError('Missing adaptation memory; grouping requires review')
    return [{'id': 'pechina-pgou-adaptacion-parcial-nnss-loua', 'municipio': 'Pechina',
             'codigo_ine': '04074', 'provincia': 'Almería',
             'titulo': 'PGOU de Pechina. Adaptación parcial de las NN.SS. a la LOUA',
             'tipo': 'planeamiento_urbanistico', 'url': SOURCE, 'source': 'ayuntamiento',
             'origen': 'inventario_documental_planeamiento', 'documentos': documents,
             'publication_ready': False, 'geometry_status': 'unavailable'}]
