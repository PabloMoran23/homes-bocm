"""Complete snapshot of the municipal Planejament general inventory (category 368)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://arenysdemar.cat'
SOURCE = BASE + '/fitxes.php?categoria=368'
LIMITATIONS = [
    'Only the municipal Planejament general inventory; not all planning or public works.',
    'Municipal inventory may lag the official register; no claim of current legal validity.',
    'DOGC publication dates are municipal transcriptions, not agreement/approval dates.',
    'Agreement and approval dates remain null; original narratives and document labels retained.',
    'PDF contents and RPUC dossiers are linked, not parsed or independently validated.',
    'Source inconsistencies retained: POUM narrative calls 2013-11-06 a plenary approval '
    'but attachment labels it CTUB conformity; PAU 15 publication precedes narrated approval.',
    'No verified geometry or coordinates; publication_ready is false. Licences disabled.',
]


def _text(node):
    return node.get_text(' ', strip=True) if node else ''


def _publication(text):
    match = re.fullmatch(r'Publicat al DOGC el (\d{2}/\d{2}/\d{4})', text)
    if not match:
        raise ValueError('Missing or changed explicit DOGC publication label')
    return datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()


def _detail_url(href):
    url = urljoin(SOURCE, href)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if (parsed.scheme != 'https' or parsed.netloc != 'arenysdemar.cat'
            or parsed.path != '/fitxa.php' or set(query) != {'id'}
            or len(query['id']) != 1 or not query['id'][0].isdigit()):
        raise ValueError('Unexpected planning detail URL')
    return BASE + '/fitxa.php?id=' + query['id'][0]


def _no_pagination(soup):
    # This reviewed inventory is unpaginated. Fail closed on new pagination;
    # never quietly output just the first page.
    if soup.select('[class*="pagin"], [id*="PAGIN"], [id*="pagin"], a[rel~="next"]'):
        raise ValueError('Pagination detected; crawler requires review')
    for a in soup.select('a[href]'):
        query = parse_qs(urlparse(a['href']).query)
        if (set(query) & {'pagina', 'page', 'pag', 'offset', 'start', 'inici'}
                or _text(a).lower() in {'següent', 'següents', 'siguiente', 'next', '»', '›'}):
            raise ValueError('Pagination detected; crawler requires review')


class ArenysDeMarAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        _no_pagination(soup)
        if 'Planejament general' not in soup.get_text(' ', strip=True):
            raise ValueError('Not the general planning inventory')
        rows = {}
        items = soup.select('li.fitxes')
        if not items:
            raise ValueError('Empty planning inventory')
        for item in items:
            a = item.select_one('a.eltitol[href]')
            title = _text(a)
            if not a or not re.match(r'^I\.\d+\. .*(?:POUM|ordenació municipal)', title):
                raise ValueError('Unexpected instrument in general planning inventory')
            url = _detail_url(a['href'])
            row = {'url': url, 'titulo': title,
                   'fecha_publicacion': _publication(_text(item.select_one('.sotstitol')))}
            if url in rows and rows[url] != row:
                raise ValueError('Conflicting duplicate planning entries')
            rows[url] = row
        return list(rows.values())

    @staticmethod
    def parse_detail(html: str, entry: dict[str, Any]) -> dict[str, Any]:
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('.fitxes_bloc_cos')
        titles = [_text(n) for n in soup.select('.titol .eltitol')]
        if content is None or entry['titulo'] not in titles:
            raise ValueError('Planning detail title/content mismatch')
        # Check both inventory and detail publication assertions.
        labels = re.findall(r'Publicat al DOGC el \d{2}/\d{2}/\d{4}', soup.get_text(' ', strip=True))
        if not labels or any(_publication(x) != entry['fecha_publicacion'] for x in labels):
            raise ValueError('Missing or conflicting detail publication date')
        narrative = '\n'.join(_text(n) for n in content.select('.fcamp119 .cos_fitxa'))
        dossiers = sorted({a['href'] for a in content.select('a[href]') if re.fullmatch(
            r'https://dtes\.gencat\.cat/rpucportal/#/consulta/detallExpedient/\d+', a['href'])})
        if len(dossiers) != 1:
            raise ValueError('Expected one official register dossier per instrument')
        docs = {}
        for block in content.select('.div_pdf'):
            a = block.select_one('a.linkpdf[href]')
            if not a:
                raise ValueError('Document block without a PDF link')
            url = urljoin(entry['url'], a['href'])
            if urlparse(url).netloc != 'arenysdemar.cat' or not urlparse(url).path.lower().endswith('.pdf'):
                raise ValueError('Unexpected document URL')
            docs.setdefault(url, {'titulo': _text(block.select_one('.descri_pdf')) or _text(a),
                                  'url': url, 'source_url': entry['url'],
                                  'provenance': 'municipal_detail_attachment'})
        if not docs:
            raise ValueError('Instrument has no documents')
        return {
            **entry, 'id': 'arenys-de-mar-proy-' + entry['url'].split('=')[-1],
            'municipio': 'Arenys de Mar', 'provincia': 'Barcelona', 'codigo_ine': '08006',
            'tipo': 'modificacion_poum' if 'Modificació' in entry['titulo'] else 'POUM',
            'fase': None, 'fecha': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'fecha_publicacion_fuente': 'DOGC, según inventario municipal',
            'descripcion': narrative, 'descripcion_fuente': 'municipal_detail_fcamp119',
            'source': 'ayuntamiento', 'origen': 'planejament_general', 'source_url': SOURCE,
            'url_documento': dossiers[0], 'rpuc_id': dossiers[0].rsplit('/', 1)[-1],
            'documentos': list(docs.values()), 'coverage': 'partial_municipal_planning',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'limitations': LIMITATIONS,
        }

    def _fetch(self, session, url):
        with session.get(url, timeout=40, stream=True) as response:
            response.raise_for_status()
            if urlparse(response.url).netloc != 'arenysdemar.cat':
                raise ValueError('Unexpected source redirect')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Source response exceeds 4 MB; nothing truncated')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected HTML source')
            html = data.decode(response.encoding or 'utf-8', errors='strict')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = 'general-inventory' if url == SOURCE else 'fitxa-' + url.split('=')[-1]
            (directory / (name + '.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = self.config.get('user_agent', 'municipio-arenys-de-mar/1.0')
            entries = self.parse_inventory(self._fetch(session, SOURCE))
            rows = [self.parse_detail(self._fetch(session, entry['url']), entry) for entry in entries]
        # Write only after the entire inventory and every detail succeeded.
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                'source_urls': [SOURCE] + [r['url'] for r in rows],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
