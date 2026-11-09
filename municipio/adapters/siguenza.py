"""Current municipal planning inventory; document availability is separate from approval."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://siguenza.es/?page_id=628'
HOSTS = {'siguenza.es', 'www.siguenza.es'}


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main .entry-content')
    if main is None:
        raise ValueError('Missing municipal content container')
    # A changed inventory must be handled explicitly, never silently truncated.
    if soup.select('[rel~=next], .pagination, .page-numbers, .nav-links'):
        raise ValueError('Pagination detected: inventory requires review')
    return main


def parse_inventory(html, source_url=SOURCE):
    main = content(html)
    if not any(normalized(h.get_text(' ', strip=True)) == 'urbanismo'
               for h in main.select('h1,h2')):
        raise ValueError('Missing Urbanismo inventory heading')
    records = {}
    for anchor in main.select('a[href]'):
        label = ' '.join(anchor.get_text(' ', strip=True).split())
        text = normalized(label)
        # These labels describe actual named planning documents, not application forms.
        match = re.fullmatch(
            r'(informacion publica: documento para aprobacion inicial|borrador para consulta previa)'
            r'\s+del\s+(plan especial\s+.+)', text)
        if not match:
            continue
        target = urljoin(source_url, anchor['href'])
        if urlparse(target).hostname not in HOSTS or urlparse(target).scheme != 'https':
            raise ValueError('Unexpected planning link host or scheme')
        title = re.split(r'\s+DEL\s+', label, maxsplit=1, flags=re.I)[1]
        identity = match[2]
        key = 'siguenza-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
        row = records.setdefault(key, {
            'id': key, 'municipio': 'Sigüenza', 'provincia': 'Guadalajara',
            'codigo_ine': '19257', 'titulo': title,
            'tipo': 'plan especial', 'url': source_url, 'inventory_url': source_url,
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanismo',
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'documents': [], 'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'current_inventory_entry; approval and validity unverified',
        })
        if not any(d['url'] == target for d in row['documents']):
            row['documents'].append({'titulo': label, 'url': target,
                                     'inventory_url': source_url,
                                     'estado_documental': match[1]})
    if not records:
        raise ValueError('No named planning documents in municipal inventory')
    return list(records.values())


def parse_documents(html, page_url):
    """Keep all attached documents together with their parent instrument."""
    main = content(html)
    documents = {}
    for anchor in main.select('a[href]'):
        target = urljoin(page_url, anchor['href'])
        if (urlparse(target).scheme == 'https' and urlparse(target).hostname in HOSTS
                and re.search(r'\.(pdf|zip|rar|7z)$', unquote(urlparse(target).path), re.I)):
            documents[target] = {'titulo': anchor.get_text(' ', strip=True),
                                 'url': target, 'inventory_url': page_url}
    return list(documents.values())


class SiguenzaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='siguenza', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def _get(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-siguenza-inventory/1.0'})
        if urlparse(response.url).hostname not in HOSTS:
            raise ValueError('Unexpected source redirect')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256(url.encode()).hexdigest()[:16]
            (path / (key + '.html')).write_bytes(response.content)
            (path / (key + '.json')).write_text(json.dumps({
                'requested_url': url, 'final_url': response.url,
                'http_status': response.status_code,
                'content_type': response.headers.get('Content-Type')}, indent=2))
        return response

    def backfill_proyectos(self, out_jsonl: Path):
        response = self._get(SOURCE)
        response.raise_for_status()
        rows = parse_inventory(response.text, response.url)
        source_urls = [response.url]
        for row in rows:
            attachments = {}
            for document in row['documents']:
                detail = self._get(document['url'])
                source_urls.append(document['url'])
                document['http_status'] = detail.status_code
                document['resolved_url'] = detail.url
                if detail.status_code in (404, 410):
                    document['availability'] = 'unavailable'
                else:
                    detail.raise_for_status()
                    document['availability'] = 'accessible'
                    for attachment in parse_documents(detail.text, detail.url):
                        attachments[attachment['url']] = attachment
            row['documents'].extend(d for u, d in attachments.items()
                                    if u not in {x['url'] for x in row['documents']})
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                          encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': source_urls,
                'publication_ready': False, 'coverage': 'current municipal planning inventory'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public grants register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
