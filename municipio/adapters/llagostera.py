"""Snapshot of Llagostera's official municipal works project inventory."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/llagostera/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/projectes-d-obra-municipal-227')
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def _agreement_date(text):
    # Dates only from certificate labels, never from filenames or page updates.
    match = re.search(r"(?:de data|local de)\s+(\d{1,2})\s+(?:de\s+|d['’])(\w+)\s+de\s+(\d{4})", text.lower())
    if not match:
        return None
    if match[2] not in MONTHS:
        raise ValueError('Unknown Catalan month in agreement date')
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


class LlagosteraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.llagostera.cat')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.select('a[href]'):
            label = _norm(a.get_text(' ', strip=True))
            if ('next' in a.get('rel', []) or label in {'seguent', 'siguiente', 'next', 'següent', '›', '»'}
                    or re.search(r'[?&](?:pag|page|start|cur)=', a['href'], re.I)):
                if a['href'] not in {'', '#'}:
                    raise ValueError('Pagination detected; inventory must be reviewed before extraction')
        articles = [a for a in soup.select('.journal-content-article')
                    if any(_norm(p.get_text(' ', strip=True)).startswith('aprovacio del projecte')
                           for p in a.select('p'))]
        if len(articles) != 1:
            raise ValueError('Expected one municipal project inventory')
        article = articles[0]
        headings = [p for p in article.select('p')
                    if _norm(p.get_text(' ', strip=True)).startswith('aprovacio del projecte')]
        groups = []
        assigned = set()
        for heading in headings:
            title = heading.get_text(' ', strip=True)
            docs = {}
            for sibling in heading.next_siblings:
                if getattr(sibling, 'name', None) == 'p' and _norm(sibling.get_text(' ', strip=True)).startswith('aprovacio del projecte'):
                    break
                if not getattr(sibling, 'select', None):
                    continue
                for a in sibling.select('a[href]'):
                    url = urljoin(SOURCE, a['href'])
                    parts = urlparse(url)
                    if parts.hostname not in {'seu-e.cat', 'www.seu-e.cat'} or not parts.path.startswith('/documents/27933/'):
                        raise ValueError('Unexpected project document provenance')
                    label = a.get_text(' ', strip=True)
                    docs.setdefault(url, {'titulo': label, 'url': url, 'url_fuente': SOURCE})
                    assigned.add(url)
            if not docs or not any(re.search(r'projecte|memoria', _norm(d['titulo'])) for d in docs.values()):
                raise ValueError('Project lacks a project/memorandum document')
            expediente = re.search(r'\(exp\.?\s*(\d{4}/\d+)\)', title, re.I)
            folders = {urlparse(d['url']).path.split('/')[3] for d in docs.values()}
            if len(folders) != 1:
                raise ValueError('Ambiguous document dossier grouping')
            dossier = next(iter(folders))
            key = expediente[1].replace('/', '-') if expediente else 'docs-' + dossier
            events = []
            for doc in docs.values():
                label = _norm(doc['titulo'])
                if label.startswith('certificat'):
                    stage = 'aprobación definitiva' if 'definitiva' in label else 'aprobación inicial' if re.search('inicial|inical|incial', label) else None
                    if stage:
                        events.append({'fase': stage, 'fecha_acuerdo': _agreement_date(doc['titulo']), 'url_documento': doc['url']})
            if not events:
                raise ValueError('Project lacks an explicit approval certificate')
            definitive = [e for e in events if e['fase'] == 'aprobación definitiva']
            current = definitive or events
            dates = {e['fecha_acuerdo'] for e in current if e['fecha_acuerdo']}
            if len(dates) > 1:
                raise ValueError('Conflicting current approval dates')
            groups.append({
                'id': 'llagostera-proy-' + key, 'municipio': 'Llagostera',
                'codigo_ine': '17089', 'provincia': 'Girona', 'titulo': title,
                'expediente': expediente[1] if expediente else None,
                'source_dossier_id': dossier, 'tipo': 'proyecto de obra municipal',
                'fase': current[0]['fase'], 'fecha': None,
                'fecha_acuerdo': next(iter(dates), None), 'fecha_publicacion': None,
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_obras_municipales',
                'documentos': list(docs.values()), 'eventos': events,
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'No verified project geometry extracted',
            })
        all_documents = {urljoin(SOURCE, a['href']) for a in article.select('a[href]') if '/documents/' in a['href']}
        if assigned != all_documents:
            raise ValueError('Unassigned inventory documents; review changed section markup')
        if not groups or len({r['id'] for r in groups}) != len(groups):
            raise ValueError('Empty or duplicate project inventory')
        return groups

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.get(SOURCE, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-llagostera/1.0'}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Source exceeds reviewed response limit')
                chunks.append(chunk)
            html = b''.join(chunks).decode('utf-8')
        rows = self.parse_projects(html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'live-projectes-obra-municipal.html').write_text(html, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register in this adapter'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
