"""Snapshot of Artà's official NS planning inventory (not a licence register)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.arta.cat/ajuntament/fitxaServeis.php?id=123'
LIMITATIONS = [
    'Partial coverage: Normes subsidiàries and linked numbered modifications only; '
    'heritage/path catalogues, reparcellation, compensation boards and public works excluded.',
    'Current published inventory snapshot, not a complete historical register or legal consolidation.',
    'Document links retained; PDFs and signature-verifier documents are not parsed for agreement dates or geometry.',
    'Index phase retained with detail headings as evidence; MP5 detail heading is stale (initial), '
    'while index and linked BOIB label indicate definitive approval.',
    'No verified granted-licence register or project geometry; publication_ready=false.',
]


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def article_url(url):
    """Canonical fetch URL; original published links remain in the output."""
    p = urlsplit(url)
    if p.hostname not in ('arta.cat', 'www.arta.cat'):
        raise ValueError('Non-municipal article')
    ids = parse_qs(p.query).get('idart', [])
    if p.path != '/ajuntament/article.php' or len(ids) != 1 or not ids[0].isdigit():
        raise ValueError('Invalid article URL')
    # The municipal inventory still publishes HTTP links and an obsolete :82 port.
    return 'https://www.arta.cat/ajuntament/article.php?idart=' + ids[0]


def no_pagination(soup):
    if soup.select('[rel~=next], .pagination, .paginacio, .paginacion'):
        raise ValueError('Pagination appeared: review traversal before extracting')


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.select_one('.titol')
    if not title or text(title) != 'Planejament i normativa urbanística':
        raise ValueError('Missing official planning inventory heading')
    no_pagination(soup)
    entries = []
    corrections = []
    for a in soup.select('a[href]'):
        label = text(a)
        if label == 'Normes subsidiàries' or re.match(r'^Modificació puntual \d+', label):
            context = text(a.find_parent('p') or a)
            phase = ('aprobación definitiva' if 'aprovat definitivament' in context.lower()
                     else 'aprobación inicial' if 'aprovat inicialment' in context.lower() else None)
            entries.append({'titulo': label, 'source_href': urljoin(SOURCE, a['href']),
                            'fase': phase, 'phase_evidence': context})
        elif label.startswith('Esmena de deficiències de l’acord de la CIOTU'):
            corrections.append(urljoin(SOURCE, a['href']))
    if len([e for e in entries if e['titulo'] == 'Normes subsidiàries']) != 1:
        raise ValueError('Expected exactly one base NS instrument')
    if len({e['source_href'] for e in entries}) != len(entries):
        raise ValueError('Duplicate instrument links')
    return entries, corrections


def parse_detail(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    no_pagination(soup)
    title, content = soup.select_one('.titol'), soup.select_one('.descripcio')
    if not title or not content or not text(title):
        raise ValueError('Missing planning detail content: ' + url)
    docs, children = [], []
    for a in content.select('a[href]'):
        target = urljoin(url, a['href'])
        p = urlsplit(target)
        if p.hostname in ('arta.cat', 'www.arta.cat') and p.path == '/ajuntament/article.php':
            children.append(article_url(target))
        elif (p.hostname in ('arta.cat', 'www.arta.cat') and p.path.startswith('/images/')) or (
            p.hostname == 'seu.arta.cat' and '/verificadorfirma.asp' in p.path.lower()
        ) or (p.hostname in ('www.caib.es', 'caib.es') and '/eboibfront/' in p.path):
            docs.append({'titulo': text(a), 'url': target, 'source_url': url})
    if not docs and not children:
        raise ValueError('No planning documents: ' + url)
    return text(title), docs, children


class ArtaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='arta', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)
        self.source_urls = []

    def _fetch(self, url, pdf=False):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-arta/1.0 (official planning inventory)'
        })
        response.raise_for_status()
        if urlsplit(response.url).hostname not in ('www.arta.cat', 'arta.cat'):
            raise ValueError('Unexpected source redirect')
        if len(response.content) > 25_000_000:
            raise ValueError('Source exceeds size limit')
        if pdf and not response.content.startswith(b'%PDF-'):
            raise ValueError('Expected real PDF for direct planning instrument')
        self.source_urls.append(url)
        if self.config.get('evidence_dir'):
            folder = Path(self.config['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            filename = hashlib.sha256(url.encode()).hexdigest()[:16] + ('.pdf' if pdf else '.html')
            (folder / filename).write_bytes(response.content)
        response.encoding = response.apparent_encoding or 'utf-8'
        return response.text if not pdf else None

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = []
        entries, corrections = parse_inventory(self._fetch(SOURCE))
        rows = []
        for entry in entries:
            published = entry['source_href']
            is_article = urlsplit(published).path == '/ajuntament/article.php'
            target = article_url(published) if is_article else published.replace('http://', 'https://', 1)
            documents, detail_pages, headings = [], [], []
            if is_article:
                pending = [target]
                if entry['titulo'] == 'Normes subsidiàries':
                    pending.extend(article_url(u) for u in corrections)
                seen = set()
                while pending:
                    page = pending.pop(0)
                    if page in seen:
                        continue
                    if len(seen) >= 100:
                        raise ValueError('Unexpected detail graph size; no partial output written')
                    seen.add(page)
                    heading, docs, children = parse_detail(self._fetch(page), page)
                    headings.append({'url': page, 'titulo': heading})
                    detail_pages.append(page)
                    documents.extend(docs)
                    pending.extend(children)
            else:
                self._fetch(target, pdf=True)
                documents.append({'titulo': entry['titulo'], 'url': published,
                                  'source_url': SOURCE, 'verified_url': target})
            unique_docs = { (d['url'], d['source_url']): d for d in documents }
            rows.append({
                'id': 'arta-plan-' + hashlib.sha256(target.encode()).hexdigest()[:16],
                'municipio': 'Artà', 'provincia': 'Illes Balears', 'codigo_ine': '07006',
                'titulo': entry['titulo'], 'tipo': 'normas subsidiarias' if entry['titulo'] == 'Normes subsidiàries'
                else 'modificación puntual de normas subsidiarias',
                'fase': entry['fase'], 'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': target, 'inventory_url': SOURCE, 'source_href': published,
                'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                'phase_evidence': entry['phase_evidence'], 'detail_headings': headings,
                'documentos': list(unique_docs.values()), 'detail_pages': detail_pages,
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'unavailable',
            })
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
