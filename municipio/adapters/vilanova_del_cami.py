"""Official planning inventory snapshot; pdftotext reads the small approval notices."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.vilanovadelcami.cat'
SOURCE = BASE + '/ajuntament/normativa/urbanisme/'
MONTHS = 'gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split()
LIMITATIONS = [
    'Partial coverage: municipal Urbanisme inventory only, not all public works or RPUC dossiers.',
    'No granted-licence register extracted; forms, agreements directory and acoustic maps excluded.',
    'No verified coordinates or feature geometry; publication_ready=false.',
    'POUM amendments share one legacy RPUC URL; retained as links, not separate invented instruments.',
    'Publication dates describe municipal web pages; POUM approval and gazette dates remain unknown.',
    'PDF attachments retained as links; only small PMU approval notices downloaded and parsed.',
]


def text(node):
    return node.get_text(' ', strip=True) if node else ''


def kind(title):
    title = title.casefold()
    if title.startswith("pla d'ordenació urbanística (poum)"):
        return 'POUM'
    if title.startswith('pla de millora urbana sector pmu'):
        return 'PMU'
    return None


def official_url(href, base):
    url = urljoin(base, href)
    if urlsplit(url).scheme != 'https' or urlsplit(url).netloc != urlsplit(BASE).netloc:
        raise ValueError('Unexpected municipal source URL: ' + url)
    return url


def inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#readspeakerPage')
    if not content or text(content.select_one('h1')) != 'Urbanisme':
        raise ValueError('Missing official Urbanisme inventory')
    listings = content.select('ul.articlelist')
    if not listings:
        raise ValueError('Missing inventory rows')
    links = []
    for item in content.select('ul.articlelist li.article-item'):
        title = item.select_one('.subtitle')
        if title and kind(text(title)):
            links.append(official_url(title.find_parent('a')['href'], url))
    # Follow every pager URL, including numbered pages; cycles are deduplicated
    # by the crawler. Unknown/non-link pagination fails instead of truncating.
    pages = []
    for pager in content.select('.pager, .pagination'):
        for a in pager.select('a[href]'):
            href = a['href']
            if href and href != '#':
                pages.append(official_url(href, url))
        if pager.get_text(strip=True) and not pager.select('a[href]'):
            raise ValueError('Unrecognized pagination')
    return list(dict.fromkeys(links)), list(dict.fromkeys(pages))


def page_date(value):
    match = re.search(r'(\d{1,2})\s+d[ e’\']+([\wç]+)\s+de\s+(\d{4})', value.lower())
    if not match or match[2] not in MONTHS:
        raise ValueError('Unrecognized web publication date: ' + value)
    return date(int(match[3]), MONTHS.index(match[2]) + 1, int(match[1])).isoformat()


def parse_detail(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#readspeakerPage')
    title = text(content.select_one('h1')) if content else ''
    instrument = kind(title)
    body = content.select_one('.ddbbtext') if content else None
    if not instrument or not body:
        raise ValueError('Not a planning detail: ' + url)
    if instrument == 'PMU' and 'Aprovació definitiva' not in text(body):
        raise ValueError('PMU detail lacks approval narrative')
    docs = {}
    for a in soup.select('#page-documents a[href]') + body.select('a[href]'):
        href = urljoin(url, a['href'])
        if urlsplit(href).scheme not in ('http', 'https'):
            raise ValueError('Invalid document URL')
        label = re.sub(r'\s*\([^)]*(?:KB|MB)\)', '', text(a)).strip()
        docs.setdefault(href, {'url': href, 'titulo': label, 'source_url': url})
    if not docs:
        raise ValueError('Planning detail has no documents')
    return {
        'id': 'vilanova-del-cami-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Vilanova del Camí', 'codigo_ine': '08302', 'provincia': 'Barcelona',
        'titulo': title, 'titulo_ficha': title, 'tipo': instrument,
        'fase': 'aprobación definitiva' if instrument == 'PMU' else None,
        'fecha': None, 'fecha_publicacion': page_date(text(content.select_one('.date'))),
        'fecha_publicacion_contexto': 'Publicación de la ficha municipal, no del boletín',
        'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': url, 'url_documento': next(iter(docs)), 'documentos': list(docs.values()),
        'descripcion': text(body), 'source': 'ayuntamiento', 'origen': 'inventario_urbanisme',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'limitations': LIMITATIONS,
    }


def apply_notice(row, notice, url):
    """Read agreement dates only in their explicit sentence, never signature dates."""
    notice = ' '.join(notice.split())
    match = re.search(r'(?:Per Acord del Ple de data|Per resolució de l’Alcaldia de data) (\d{2})/(\d{2})/(\d{4})', notice)
    if not match or not re.search(r'aprovar definitivament', notice, re.I):
        raise ValueError('Approval notice changed or missing agreement date')
    agreement = date(int(match[3]), int(match[2]), int(match[1])).isoformat()
    if 'Projecte d’Urbanització del Pla de Millora Urbana' in notice:
        if not re.search(r'PMU r3\b', row['titulo_ficha'], re.I) or 'r3 Barri Bonavista' not in notice:
            raise ValueError('Notice does not match the PMU r3 detail')
        row['tipo'] = 'proyecto de urbanización'
        row['titulo'] = 'Projecte d’Urbanització del Pla de Millora Urbana r3 Barri Bonavista (Nord-oest) de Vilanova del Camí'
        row['nota_fuente'] = 'La ficha lo denomina plan PMU; el anuncio adjunto aprueba el proyecto de urbanización.'
    elif 'Pla de Millora Urbana Sector PMU r8' not in notice or not re.search(r'PMU r8\b', row['titulo_ficha'], re.I):
        raise ValueError('Unexpected approval instrument')
    row.update(fecha_acuerdo=agreement, fecha_aprob=agreement, fecha_acuerdo_source_url=url)
    exp = re.search(r'Exp\. Núm\.:\s*([A-Z]+/\d+)', notice)
    if exp:
        row['expediente'] = exp[1]
    return row


class VilanovaDelCamiAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    def _fetch(self, url, pdf=False):
        request = Request(url, headers={'User-Agent': self.config.get('user_agent', 'municipio-vilanova-del-cami/1.0')})
        limit = 4_000_000
        with urlopen(request, timeout=40) as response:
            data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError('Source exceeds response limit: ' + url)
            if pdf and not data.startswith(b'%PDF-'):
                raise ValueError('Expected PDF notice: ' + url)
            if not pdf and 'html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected HTML source: ' + url)
        self.source_urls.append(url)
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + ('.pdf' if pdf else '.html')
            (folder / name).write_bytes(data)
        return data

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        pending, seen, details = [SOURCE], set(), {}
        while pending:
            url = pending.pop(0)
            if url in seen:
                continue
            if len(seen) >= 100:
                raise ValueError('Inventory pagination safety limit; snapshot not written')
            seen.add(url)
            links, pages = inventory(self._fetch(url).decode('utf-8'), url)
            details.update(dict.fromkeys(links))
            pending.extend(p for p in pages if p not in seen)
        rows = []
        for url in details:
            row = parse_detail(self._fetch(url).decode('utf-8'), url)
            if row['tipo'] == 'PMU':
                notices = [d['url'] for d in row['documentos'] if 'anunci' in d['titulo'].casefold()]
                if len(notices) != 1:
                    raise ValueError('Missing or ambiguous PMU approval notice')
                data = self._fetch(notices[0], pdf=True)
                with tempfile.TemporaryDirectory() as directory:
                    pdf = Path(directory) / 'notice.pdf'
                    pdf.write_bytes(data)
                    result = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], check=True, capture_output=True, timeout=30)
                apply_notice(row, result.stdout.decode('utf-8'), notices[0])
            rows.append(row)
        if not rows:
            raise ValueError('No usable planning instruments; snapshot not written')
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full inventory refresh, so changes to old instruments are not missed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
