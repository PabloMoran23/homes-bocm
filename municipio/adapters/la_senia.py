"""Reviewed public-works families in La Sénia's official WordPress inventory.

A complete paginated search snapshot, not a licence register or all municipal works.
Each instrument retains its notices, revisions and linked documents separately.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://lasenia.cat/web/wp-json/wp/v2/posts'
AFTER = '2025-08-01T00:00:00'
MONTHS = dict(zip('gener febrer marc abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
# Source-backed identity aliases, not output records. The two northern street
# sections and different storm years must never collapse into a single work.
FAMILIES = {
    'casa-cultura': ('casa de cultura',),
    'coberta-poliesportiu': ('doblat', 'coberta', 'poliesportiu'),
    'renovacio-fibrociment': ('renovacio', 'canonades de fibrociment'),
    'sortida-nord-santander-t1040': ('sortida nord', 'santander', 't-1040'),
    'sortida-nord-osca-santander': ('sortida nord', 'osca-santander'),
    'collector-barranquet': ('reparacio', 'barranquet'),
    'camins-aiguats-novembre-2024': ('camins municipals', 'novembre 2024'),
    'carrers-placa-montsia': ('urbanitzacio', 'carrers adjacents', 'montsia'),
    'digitalitzacio-aigua': ('digitalitzacio', 'xarxa', 'aigua potable'),
}
LIMITATIONS = [
    'Partial coverage: nine reviewed public-works families; notices published since 2025-08-01 only.',
    'Search projecte is not a complete municipal planning or works register; other wording and families are excluded.',
    'PDF contents are linked, not parsed: agreement dates found only in PDFs remain null.',
    'fecha_publicacion is the municipal WordPress publication date, not BOPT publication or agreement date.',
    'Revisions share an instrument but retain separate notices; latest notice is not proof of final approval.',
    'No verified geometry, coordinates or granted-licence inventory; publication_ready is false.',
]


def norm(value):
    return unicodedata.normalize('NFKD', value.replace('’', "'")).encode('ascii', 'ignore').decode().lower().replace('col.lector', 'collector')


def text(html):
    return BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)


def agreement_date(body):
    """Only an explicit agreement/resolution date, never a signature or crawl date."""
    normalized = norm(body)
    prefix = r'(?:acord de ple|resolucio de l.alcaldia)[^;]{0,90}?de data\s+'
    match = re.search(prefix + r'(\d{1,2})/(\d{1,2})/(\d{4})', normalized)
    if match:
        return date(int(match[3]), int(match[2]), int(match[1])).isoformat()
    match = re.search(prefix + r"(\d{1,2})\s+d(?:e\s+|['’])([a-z]+)\s+de\s+(\d{4})", normalized)
    if match and match[2] in MONTHS:
        return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()
    return None


class LaSeniaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://lasenia.cat/web/')

    @staticmethod
    def parse_projects(posts):
        groups = {}
        for post in posts:
            title = text(post['title']['rendered'])
            title_norm = norm(title)
            # Formal approval/correction of a named physical project only.
            if 'projecte' not in title_norm or not any(word in title_norm for word in ('aprovacio', 'rectificacio')):
                continue
            if any(word in title_norm for word in ('licitacio', 'adjudicacio', 'contractacio', 'subvencio', 'ordenanca')):
                continue
            families = [key for key, tokens in FAMILIES.items() if all(token in title_norm for token in tokens)]
            if not families:
                continue
            if len(families) != 1:
                raise ValueError('Ambiguous public-works identity')
            key = families[0]
            url = post['link']
            if urlparse(url).hostname not in ('lasenia.cat', 'www.lasenia.cat'):
                raise ValueError('Non-municipal post URL')
            publication = datetime.fromisoformat(post['date']).date().isoformat()
            html = post['content']['rendered']
            if post['content'].get('protected'):
                raise ValueError('Protected project content')
            soup = BeautifulSoup(html, 'html.parser')
            documents = {}
            for anchor in soup.select('a[href]'):
                doc_url = urljoin(url, anchor['href'])
                parsed = urlparse(doc_url)
                if parsed.scheme == 'https' and parsed.hostname in ('lasenia.cat', 'www.lasenia.cat') and '/wp-content/uploads/' in parsed.path and parsed.path.lower().endswith(('.pdf', '.zip')):
                    documents.setdefault(doc_url, {'titulo': anchor.get_text(' ', strip=True), 'url': doc_url, 'url_origen': url})
            body = soup.get_text(' ', strip=True)
            if not documents and not re.search(r'aprova(?:t|r|cio)', norm(body)):
                raise ValueError('Project notice lacks documents or an approval narrative')
            phase = ('aprobación definitiva' if 'definitiva' in title_norm else
                     'aprobación inicial' if 'inicial' in title_norm or 'inical' in title_norm else
                     'rectificación')
            notice = {'wp_id': post['id'], 'titulo': title, 'url': url,
                      'url_api': SOURCE + '/' + str(post['id']),
                      'fecha_publicacion': publication, 'fecha_acuerdo': agreement_date(body),
                      'fase': phase, 'descripcion': body, 'documentos': list(documents.values())}
            groups.setdefault(key, []).append(notice)
        rows = []
        for key, notices in sorted(groups.items()):
            notices.sort(key=lambda n: (n['fecha_publicacion'], n['wp_id']))
            latest = notices[-1]
            rows.append({
                'id': 'la-senia-proy-' + key, 'municipio': 'La Sénia',
                'codigo_ine': '43044', 'provincia': 'Tarragona',
                'titulo': latest['titulo'], 'tipo': 'proyecto_obra_publica',
                'fase': latest['fase'], 'fecha': None,
                'fecha_publicacion': latest['fecha_publicacion'],
                'fecha_acuerdo': latest['fecha_acuerdo'], 'fecha_aprob': None,
                'url': latest['url'], 'source': 'ayuntamiento',
                'origen': 'anuncios_municipales_obras', 'descripcion': latest['descripcion'],
                'anuncios': notices,
                'documentos': list({d['url']: d for n in notices for d in n['documentos']}.values()),
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'No verified project geometry in the parsed inventory',
            })
        if not rows:
            raise ValueError('No usable reviewed public-works notices in inventory')
        return rows

    def backfill_proyectos(self, out_jsonl: Path):
        posts, source_urls, seen = [], [], set()
        totals = None
        page = 1
        capture = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        if capture:
            capture.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            while True:
                response = session.get(SOURCE, params={
                    'search': 'projecte', 'after': AFTER, 'per_page': 20, 'page': page,
                    'orderby': 'id', 'order': 'asc',
                    '_fields': 'id,date,link,title,content',
                }, timeout=40, headers={'User-Agent': 'municipio-la-senia/1.0'})
                response.raise_for_status()
                current = (int(response.headers['X-WP-Total']), int(response.headers['X-WP-TotalPages']))
                if totals is None:
                    totals = current
                if current != totals:
                    raise ValueError('Inventory changed during pagination; retry snapshot')
                batch = response.json()
                if not isinstance(batch, list) or not batch:
                    raise ValueError('Missing inventory page')
                for post in batch:
                    if post['id'] in seen:
                        raise ValueError('Repeated post during pagination')
                    seen.add(post['id'])
                posts.extend(batch)
                source_urls.append(response.url)
                if capture:
                    (capture / f'inventory-{page}.json').write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding='utf-8')
                if page >= totals[1]:
                    break
                page += 1
        if len(posts) != totals[0]:
            raise ValueError('Incomplete inventory: count does not match X-WP-Total')
        rows = self.parse_projects(posts)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_posts': len(posts),
                'pages': page, 'source_urls': source_urls, 'limitations': LIMITATIONS,
                'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        # Complete scoped snapshot; never an append of duplicate notices.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
