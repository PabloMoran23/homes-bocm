"""Municipal-linked POUM snapshot, backed by the public Generalitat RPUC API."""
from __future__ import annotations

import json
import re
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPIO = 'Santa Margarida i els Monjos'
SOURCE = ('https://seu-e.cat/ca/web/santamargaridaielsmonjos/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme')
API = 'https://planejamenturbanisme.territori.gencat.cat/RPUC-portal/rest/consulta/'
VIEWER = 'https://planejamenturbanisme.territori.gencat.cat/rpucportal/#/consulta/detallExpedient/'
LIMITATIONS = [
    'Partial coverage: only the POUM dossier linked by municipal Normativa d’urbanisme; '
    'other instruments, related dossiers, works and licences are outside this snapshot.',
    'Municipal page update date is not an approval date. RPUC dates retain their source semantics.',
    'No assertion of current legal validity: public tree includes judicial resolutions; contents not interpreted.',
    'Document links cover the complete public arbre tree, not historical assentament trees or all internal dossier metadata.',
    'No verified geometry; coordinates remain null and publication_ready is false.',
]


def dossier_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    if not any(re.search("Normativa d.urbanisme", h.get_text(' ', strip=True))
               for h in soup.select('h1,h2')):
        raise ValueError('Municipal planning source heading missing')
    if "Consulta el Pla d'Ordenació Urbanísrtica Municipal" not in soup.get_text(' ', strip=True):
        raise ValueError('Municipal POUM narrative missing')
    links = {}
    for a in soup.select('a[href]'):
        u = urlparse(a['href'])
        if u.hostname not in {'ptop.gencat.net', 'dtes.gencat.cat'}:
            continue
        q = parse_qs(u.query)
        ids = q.get('codintExp', [])
        if q.get('reqCode') == ['veureDocument'] and len(ids) == 1 and ids[0].isdigit():
            links[ids[0]] = a['href']
    if len(links) != 1:
        raise ValueError('Expected exactly one municipally linked POUM dossier')
    return next(iter(links.items()))


def _date(value):
    if value is None or value == '':
        return None
    return date.fromisoformat(value).isoformat()


def parse_project(detail, tree, dossier, municipal_link):
    if (not isinstance(detail, dict) or str(detail.get('codintExp')) != dossier
            or detail.get('municipi') != MUNICIPIO
            or detail.get('tipologiaCA', '').strip() != "Pla d'ordenació urbanística municipal"):
        raise ValueError('RPUC identity or instrument mismatch')
    if not isinstance(tree, list) or not tree:
        raise ValueError('Missing complete public document tree')
    docs = {}

    def walk(nodes, parents=()):
        for node in nodes:
            path = (*parents, unescape(node['label']))
            for doc in node.get('data') or []:
                doc_id = doc['idDocument']
                if not isinstance(doc_id, int) or not doc.get('nomDocument'):
                    raise ValueError('Invalid public document identity')
                if doc_id not in docs:
                    docs[doc_id] = {
                        'id_documento': doc_id, 'titulo': doc['nomDocument'],
                        'url': API + 'documents?' + urlencode({
                            'documentId': doc_id, 'downloadType': 'inline', 'idioma': 'ca'}),
                        'categorias': [],
                        'source_metadata': {k: doc.get(k) for k in ('portal', 'afectat', 'baixa', 'recurs')},
                    }
                if list(path) not in docs[doc_id]['categorias']:
                    docs[doc_id]['categorias'].append(list(path))
            walk(node.get('children') or [], path)
    walk(tree)
    if not docs:
        raise ValueError('POUM public tree contains no documents')
    params = urlencode({'codiExpedient': dossier, 'idioma': 'ca', 'cercaPublic': 'false'})
    return {
        'id': 'santa-margarida-i-els-monjos-proy-rpuc-' + dossier,
        'municipio': MUNICIPIO, 'codigo_ine': '08251', 'provincia': 'Barcelona',
        'titulo': detail['tema'].strip() + ' — ' + MUNICIPIO,
        'tipo': 'POUM', 'fase': None, 'fecha': None,
        'fecha_aprob': _date(detail.get('dataAprovacio')),
        'fecha_acuerdo': None,
        'fecha_publicacion': _date(detail.get('dataPublicacio')),
        'expediente': detail.get('numComplet'), 'rpuc_id': dossier,
        'url': VIEWER + dossier, 'url_fuente_municipal': SOURCE,
        'enlace_municipal_original': municipal_link,
        'source': 'ayuntamiento', 'origen': 'rpuc_enlazado_por_ayuntamiento',
        'source_urls': [SOURCE, API + 'detall?' + params, API + 'arbre?' + params],
        'documentos': sorted(docs.values(), key=lambda d: d['id_documento']),
        'expedientes_relacionados_fuente': detail.get('expedientsRelacionats', []),
        'vigencia_fuente': detail.get('vigencia'),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'limitations': LIMITATIONS,
    }


class SantaMargaridaIElsMonjosAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.santamargaridaielsmonjos.cat')

    def _fetch(self, url, capture_name):
        with requests.get(url, timeout=40, stream=True, headers={
                'User-Agent': self.config.get('user_agent', 'municipio-santa-margarida-i-els-monjos/1.0')}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 5_000_000:
                    raise ValueError('Source exceeds reviewed size; no partial extraction')
                chunks.append(chunk)
            body = b''.join(chunks)
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir']) / capture_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        return body.decode('utf-8')

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        dossier, link = dossier_from_html(self._fetch(SOURCE, 'municipal-normativa.html'))
        params = urlencode({'codiExpedient': dossier, 'idioma': 'ca', 'cercaPublic': 'false'})
        detail = json.loads(self._fetch(API + 'detall?' + params, 'rpuc-detail.json'))
        tree = json.loads(self._fetch(API + 'arbre?' + params, 'rpuc-tree.json'))
        row = parse_project(detail, tree, dossier, link)
        self._write(out_jsonl, [row])
        return {'status': 'ok', 'rows': 1, 'source_urls': row['source_urls'],
                'documents': len(row['documentos']), 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of one linked instrument; no paginated search is used.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
