"""Artés: public urban-project inventory and initial-approval POUM dossier."""
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

INVENTORY = 'https://seu-e.cat/ca/web/artes/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/projectes-i-estudis-urbanistics-213'
POUM = 'https://participa.artes.cat/poum/aprovacio-inicial-del-poum'
DOCUMENTS = POUM + '/documentacio'
MONTHS = 'gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split()
LIMITATIONS = [
    'Partial snapshot: municipal project/study inventory and initial-approval POUM only; not all works or RPUC history.',
    'POUM phase describes the linked initial-approval dossier, not a claim of current definitive approval.',
    'No granted-licence register; forms, procurement and unrelated news excluded.',
    'No verified geometry; coordinates remain null and publication_ready is false.',
    'PDF and SharePoint links retained as published; linked file contents and folder descendants are not parsed.',
    'Inventory update date is not a project publication or approval date.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # Fail instead of quietly dropping additional inventory pages.
    for a in soup.select('a[href]'):
        href = a['href']
        if (set(a.get('rel', [])) & {'next', 'prev'}
                or a.get_text(' ', strip=True).lower() in {'següent', 'siguiente', 'next', '›', '»'}
                or re.search(r'[?&](?:page|cur|start|.*_cur)=', href, re.I)):
            if href not in {'', '#'}:
                raise ValueError('Pagination detected; review crawler before extracting')
    return soup


def _record(key, title, kind, source, docs):
    return {
        'id': 'artes-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
        'municipio': 'Artés', 'codigo_ine': '08010', 'provincia': 'Barcelona',
        'titulo': title, 'tipo': kind, 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': source, 'url_documento': docs[0]['url'], 'documentos': docs,
        'source': 'ayuntamiento', 'origen': 'inventario_urbanismo_municipal',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
    }


def _doc(a, source):
    return {'titulo': a.get_text(' ', strip=True), 'url': urljoin(source, a['href']),
            'source_url': source, 'provenance': 'enlace publicado por el ayuntamiento'}


class ArtesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='artes', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.artes.cat')

    @staticmethod
    def parse_inventory(html):
        soup = _soup(html)
        if 'Projectes i estudis urbanístics' not in soup.get_text(' ', strip=True):
            raise ValueError('Missing Artés project inventory heading')
        rows = {}
        for li in soup.select('.journal-content-article li'):
            links = [a for a in li.select('a[href]')
                     if urlparse(urljoin(INVENTORY, a['href'])).hostname == 'seu-e.cat'
                     and urlparse(urljoin(INVENTORY, a['href'])).path.startswith('/documents/949642/')]
            if not links:
                continue
            title = links[0].get_text(' ', strip=True)
            if not re.match(r'^(Projecte|Estudi)\b', title):
                raise ValueError('Unrecognised municipal inventory item')
            docs = list({d['url']: d for d in (_doc(a, INVENTORY) for a in links)}.values())
            # One instrument per list item, with all its supporting documents.
            key = re.sub(r'\s+', ' ', title).casefold()
            if key in rows:
                known = {d['url'] for d in rows[key]['documentos']}
                rows[key]['documentos'].extend(d for d in docs if d['url'] not in known)
                continue
            row = _record(key, title, 'proyecto_urbanistico' if title.startswith('Projecte') else 'estudio_urbanistico', INVENTORY, docs)
            block = li.find_parent(class_='journal-content-article')
            updated = re.search(r'Actualització:\s*(\d{2})/(\d{2})/(\d{4})', block.get_text(' ', strip=True))
            row['fecha_actualizacion_fuente'] = date(int(updated[3]), int(updated[2]), int(updated[1])).isoformat() if updated else None
            rows[key] = row
        if not rows:
            raise ValueError('No actual municipal project documents found')
        return list(rows.values())

    @staticmethod
    def parse_poum(html, documents_html):
        soup, listing = _soup(html), _soup(documents_html)
        body = soup.select_one('article .field-name-body')
        doc_body = listing.select_one('article .field-name-body')
        if body is None or doc_body is None:
            raise ValueError('Missing POUM dossier content')
        text = body.get_text(' ', strip=True)
        agreement = re.search(r'va aprovar pel Ple en data (\d{1,2}) de (\w+) de (\d{4}) el document per a l\x27aprovació inicial del POUM', text)
        if not agreement or agreement[2] not in MONTHS:
            raise ValueError('Missing explicit POUM initial-approval agreement')
        if 'Documentació del POUM aprovat inicialment' not in listing.get_text(' ', strip=True):
            raise ValueError('Wrong POUM document inventory')
        docs = []
        for content, source in [(body, POUM), (doc_body, DOCUMENTS)]:
            for a in content.select('a[href]'):
                url = urljoin(source, a['href'])
                if ((urlparse(url).hostname == 'participa.artes.cat' and urlparse(url).path.endswith('.pdf'))
                        or urlparse(url).hostname == 'ajartes-my.sharepoint.com'):
                    docs.append(_doc(a, source))
        docs = list({d['url']: d for d in docs}.values())
        if not any(urlparse(d['url']).hostname == 'ajartes-my.sharepoint.com' for d in docs):
            raise ValueError('POUM supporting document links missing')
        row = _record(POUM, "Pla d’ordenació urbanística municipal d’Artés (POUM) — aprovació inicial", 'POUM', POUM, docs)
        row.update(fase='aprobación inicial', descripcion=text,
                   fecha_acuerdo=date(int(agreement[3]), MONTHS.index(agreement[2]) + 1, int(agreement[1])).isoformat(),
                   origen='planejament_municipal', source_urls=[POUM, DOCUMENTS])
        row['fecha_aprob'] = row['fecha_acuerdo']
        return row

    def _fetch(self, url, name):
        response = requests.get(url, timeout=(10, 45), stream=True,
                                headers={'User-Agent': 'municipio-artes/1.0'})
        with response:
            response.raise_for_status()
            if urlparse(response.url).hostname != urlparse(url).hostname:
                raise ValueError('Unexpected cross-host source redirect')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected municipal HTML inventory')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 5_000_000:
                    raise ValueError('Municipal source exceeds response limit')
            if self.config.get('evidence_dir'):
                directory = Path(self.config['evidence_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                (directory / name).write_bytes(data)
            return data.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = self.parse_inventory(self._fetch(INVENTORY, 'live_inventory.html'))
        rows.append(self.parse_poum(self._fetch(POUM, 'live_poum.html'), self._fetch(DOCUMENTS, 'live_poum_documents.html')))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [INVENTORY, POUM, DOCUMENTS],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refreshed snapshot; no date filtering or pagination truncation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
