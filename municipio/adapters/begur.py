"""Current Begur municipal works inventory and POUM document inventories."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://begur.cat/serveis/urbanisme/'
WORKS = BASE + 'projectes-municipals-en-execucio/'
DRAFT = BASE + 'poum-en-tramit/'
OFFICIAL = BASE + 'normativa/poum/poum-begur/'


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.select_one('.centerpad:has(h1)')
    if root is None:
        raise ValueError('Begur content container missing')
    # These are unpaginated inventories today. A future pager must not result
    # in a successful but truncated snapshot (including WordPress multipages).
    if soup.select('[rel~=next], .pagination, .nav-links, .page-links, a.next'):
        raise ValueError('Uncovered pagination in Begur source')
    return root


def documents(root, source):
    result = {}
    for a in root.select('a[href]'):
        url = urljoin(source, a['href'])
        if urlsplit(url).scheme not in ('http', 'https'):
            continue
        result.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                                'source_url': source})
    return list(result.values())


def record(url, title, kind, description, docs, phase=None):
    return {
        'id': 'begur-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Begur', 'provincia': 'Girona', 'codigo_ine': '17013',
        'titulo': title, 'tipo': kind, 'fase': phase,
        'descripcion': description, 'url': url,
        'url_documento': docs[0]['url'] if docs else None, 'documentos': docs,
        'source': 'ayuntamiento', 'origen': 'urbanisme_municipal',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class BegurAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://begur.cat')
        self.source_urls = []

    @staticmethod
    def parse_inventory(html, source=WORKS):
        root = content(html)
        if root.h1.get_text(' ', strip=True) != 'Projectes municipals en execució':
            raise ValueError('Unexpected Begur works inventory')
        links = {}
        for a in root.select('.sub-servei-list a[href]'):
            url = urljoin(source, a['href'])
            if not url.startswith(WORKS) or url == WORKS:
                raise ValueError('Unexpected work detail link')
            links[url] = a.get_text(' ', strip=True)
        if not links:
            raise ValueError('Empty works inventory requires review')
        return list(links)

    @staticmethod
    def parse_work(html, url):
        root = content(html)
        body = root.select_one('.content-postTitle')
        text = body.get_text(' ', strip=True) if body else ''
        if 'projecte' not in text.lower() or 'obres' not in text.lower():
            raise ValueError('Work detail lacks a physical project narrative')
        docs = documents(body, url)
        if not docs:
            raise ValueError('Work detail lacks project document links')
        # Preserve the full seasonal suspension narrative, with no inferred year.
        phase = "en execució (segons la pàgina municipal)" if "fase d'execució" in text else None
        return record(url, root.h1.get_text(' ', strip=True), 'obra pública', text, docs, phase)

    @staticmethod
    def parse_draft(html):
        root = content(html)
        body = root.select_one('.content-postTitle')
        text = body.get_text(' ', strip=True) if body else ''
        if root.h1.get_text(' ', strip=True) != 'POUM en tràmit' or 'redacció i tramitació' not in text:
            raise ValueError('Draft POUM narrative missing')
        docs = []
        for section in root.select('.accordion_in'):
            head = section.select_one('.acc_head')
            for doc in documents(section, DRAFT):
                doc['seccion'] = head.get_text(' ', strip=True) if head else None
                docs.append(doc)
        if not docs:
            raise ValueError('Draft POUM documents missing')
        # Empty later-stage headings are a roadmap, not evidence of approval.
        return record(DRAFT, 'Nou POUM de Begur', 'POUM', text, docs, 'en redacció i tramitació')

    @staticmethod
    def parse_official(html):
        root = content(html)
        body = root.select_one('.content-postTitle')
        if root.h1.get_text(' ', strip=True) != 'POUM-oficial' or body is None:
            raise ValueError('Official POUM inventory missing')
        docs = documents(body, OFFICIAL)
        if not any('/rpucportal/#/consulta/detallExpedient/' in d['url'] for d in docs):
            raise ValueError('Official POUM registry reference missing')
        return record(OFFICIAL, 'Pla d’ordenació urbanística municipal de Begur — oficial',
                      'POUM', body.get_text(' ', strip=True), docs)

    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-begur/1.0')})
        response.raise_for_status()
        if len(response.content) > 5_000_000:
            raise ValueError('Begur source exceeds response limit')
        response.encoding = 'utf-8'
        self.source_urls.append(url)
        if self.config.get('evidence_dir'):
            folder = Path(self.config['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = []
        urls = self.parse_inventory(self._fetch(WORKS))
        rows = [self.parse_work(self._fetch(url), url) for url in urls]
        rows.extend([self.parse_draft(self._fetch(DRAFT)), self.parse_official(self._fetch(OFFICIAL))])
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'publication_ready': False, 'coverage': 'partial municipal works and POUM inventories'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete current snapshot; no date filter or guessed incremental cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
