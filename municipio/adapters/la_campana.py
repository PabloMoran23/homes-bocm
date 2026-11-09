"""Physical street works explicitly described in La Campana's public archive."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.lacampana.es/inicio/obras-servicios'


def _source_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'www.lacampana.es'
            or parsed.path != '/inicio/obras-servicios' or parsed.fragment
            or (parsed.query and not re.fullmatch(r'start=\d+', parsed.query))):
        raise ValueError('Unexpected archive URL: ' + url)
    return url


def parse_page(html: str, url: str):
    """Return qualifying works and explicit pagination; no inferred agreements."""
    _source_url(url)
    soup = BeautifulSoup(html, 'html.parser')
    blog = soup.select_one('div.blog')
    if blog is None or not blog.select('[itemprop="blogPost"]'):
        raise ValueError('Missing municipal works archive')
    counter = blog.select_one('.pagination .counter')
    match = re.fullmatch(r'Página\s+(\d+)\s+de\s+(\d+)', counter.get_text(' ', strip=True)) if counter else None
    if not match:
        raise ValueError('Missing archive pagination counter')
    page, total = map(int, match.groups())
    if not 1 <= page <= total:
        raise ValueError('Invalid pagination counter')
    following = blog.select_one('.pagination-next a[href]')
    next_url = _source_url(urljoin(url, following['href'])) if following else None
    if (page < total) != bool(next_url):
        raise ValueError('Incomplete pagination: missing or unexpected next page')
    rows = []
    for article in blog.select('[itemprop="blogPost"]'):
        paragraphs = [p.get_text(' ', strip=True) for p in article.select('p')]
        # A traffic restriction, tender meeting or licence form is insufficient.
        descriptions = [p for p in paragraphs if re.search(
            r'(?:comienzo de las obras|darán comienzo las obras)', p, re.I)
            and re.search(r'\b(?:calle|calles|plaza)\b', p, re.I)]
        if not descriptions:
            continue
        documents = []
        for a in article.select('a[href]'):
            target = urljoin(url, a['href'])
            parsed = urlparse(target)
            if (parsed.netloc == 'www.lacampana.es' and parsed.scheme == 'https'
                    and parsed.path.startswith('/images/Anuncios/OBRAS-SERVICIOS/Avisos_Obras/')):
                if target not in [d['url'] for d in documents]:
                    documents.append({'url': target, 'tipo': 'aviso municipal de obra',
                                      'titulo': a.get_text(' ', strip=True) or
                                      (a.img.get('alt', '') if a.img else '')})
        if not documents:
            raise ValueError('Named commencement lacks its municipal notice')
        publication = None
        if paragraphs and re.fullmatch(r'\d{2}/\d{2}/\d{4}', paragraphs[0]):
            publication = datetime.strptime(paragraphs[0], '%d/%m/%Y').date().isoformat()
        description = '\n'.join(descriptions)
        title = re.split(r'\s+(?:el próximo|Disculpen|Se ruega)', description, maxsplit=1, flags=re.I)[0].rstrip('.')
        notice_url = documents[0]['url']
        rows.append({
            'id': 'la-campana-obra-' + hashlib.sha256(notice_url.encode()).hexdigest()[:16],
            'municipio': 'La Campana', 'codigo_ine': '41022', 'provincia': 'Sevilla',
            'titulo': title, 'descripcion': description, 'tipo': 'obra pública viaria',
            'fase': 'comienzo de obras anunciado',
            'fecha_publicacion': publication, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': notice_url, 'url_documento': notice_url, 'source_urls': [url],
            'documentos': documents, 'source': 'ayuntamiento',
            'origen': 'archivo_municipal_obras_servicios',
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    return rows, next_url, page, total


class LaCampanaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='la-campana', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path):
        url, seen, records, expected_total = SOURCE, set(), {}, None
        while url:
            if url in seen:
                raise ValueError('Pagination cycle')
            response = requests.get(url, timeout=(10, 30), headers={
                'User-Agent': 'municipio-la-campana/1.0 (public municipal archive)'})
            response.raise_for_status()
            _source_url(response.url)
            rows, next_url, page, total = parse_page(response.text, url)
            if page != len(seen) + 1 or (expected_total is not None and total != expected_total):
                raise ValueError('Skipped page or changed pagination total')
            expected_total = total
            seen.add(url)
            if self.config.get('evidence_dir'):
                capture = Path(self.config['evidence_dir']) / f'archive-{page}.html'
                capture.parent.mkdir(parents=True, exist_ok=True)
                capture.write_bytes(response.content)
            for row in rows:
                previous = records.get(row['id'])
                if previous:
                    previous['source_urls'] = sorted(set(previous['source_urls'] + row['source_urls']))
                    for document in row['documentos']:
                        if document not in previous['documentos']:
                            previous['documentos'].append(document)
                else:
                    records[row['id']] = row
            url = next_url
        if not records or len(seen) != expected_total:
            raise ValueError('Empty or incomplete works archive')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                  for row in records.values()), encoding='utf-8')
        return {'count': len(records), 'written': len(records), 'pages': len(seen),
                'source_urls': sorted(seen), 'coverage': 'partial_historical_street_works',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full archive refresh; a state watermark would miss unordered old entries.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
