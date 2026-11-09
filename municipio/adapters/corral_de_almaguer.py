"""Corral de Almaguer planning instruments in the official JCCM agreement index."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'urbanismo.castillalamancha.es'
SOURCE = f'https://{HOST}/acuerdos-expedientes?title=Corral+de+Almaguer'
LIMITATIONS = [
    'Partial coverage: JCCM agreements whose titles contain Corral de Almaguer; not the complete municipal planning register.',
    'Only planning instruments are included; urban qualifications and provisional authorisations are excluded.',
    'Agreement dates are retained per document, not interpreted as publication or approval dates.',
    'No licence grants, current legal validity, execution status or coordinates are inferred.',
]


def official_url(base, href, prefix):
    url = urljoin(base, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != HOST or not parsed.path.startswith(prefix):
        raise ValueError(f'Unexpected official source URL: {url}')
    return url


def parse_page(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    count = re.search(r'Mostrando\s+(\d+)\s*-\s*(\d+)\s+de\s+(\d+)\s+expediente/s', text)
    if not count:
        raise ValueError('Missing inventory result count; cannot establish coverage')
    start, end, total = map(int, count.groups())
    articles = soup.select('article.node--type-acuerdo-expediente-urbanistico')
    if len(articles) != end - start + 1:
        raise ValueError('Inventory count does not match article count')
    selected = []
    for article in articles:
        title_el = article.select_one('h3.article__title')
        population = article.select_one('.field--name-field-poblacion')
        if not title_el or not population:
            raise ValueError('Missing title or municipality')
        title = ' '.join(title_el.get_text(' ', strip=True).split())
        # Exact municipality field, not a substring such as Almagro.
        if population.get_text(' ', strip=True) != 'Corral de Almaguer':
            continue
        if not re.search(r'\b(?:POM|NNSS|PAU|Plan de Ordenaci[oó]n Municipal|Modificaci[oó]n Puntual)\b', title, re.I):
            continue
        if re.match(r'^(?:Calificaci[oó]n|Autorizaci[oó]n|Modelo|Licitaci[oó]n)', title, re.I):
            continue
        detail = official_url(url, article.get('about', ''), '/urbanismo/acuerdos/')
        date_el = article.select_one('.field--name-field-expediente-fecha')
        if not date_el:
            raise ValueError('Missing explicitly labelled agreement date')
        date = datetime.strptime(date_el.get_text(strip=True), '%d/%m/%Y').date().isoformat()
        docs = []
        for link in article.select('.field--name-field-expediente-fichero a[href]'):
            target = official_url(url, link['href'], '/sites/default/files/expedientes/')
            label = link.select_one('.file--title')
            docs.append({'titulo': label.get_text(' ', strip=True) if label else link.get_text(' ', strip=True),
                         'url': target, 'fecha_acuerdo': date, 'agreement_title': title,
                         'source_url': detail, 'inventory_url': url})
        if not docs:
            raise ValueError('Planning agreement without documents')
        selected.append({'titulo': title, 'url': detail, 'documentos': docs})
    next_links = soup.select('li.pager__item--next a[href], a[rel~=next][href]')
    next_urls = {official_url(url, a['href'], '/acuerdos-expedientes') for a in next_links}
    if len(next_urls) > 1:
        raise ValueError('Ambiguous next page')
    next_url = next(iter(next_urls), None)
    if next_url and parse_qs(urlparse(next_url).query).get('title') != ['Corral de Almaguer']:
        raise ValueError('Pagination lost municipal title filter')
    return selected, (start, end, total), next_url


def group_instruments(entries):
    grouped = {}
    for entry in entries:
        title = entry['titulo']
        # Both reviewed certificates name the same NNSS industrial-sector PAU.
        industrial_pau = re.search(r'\bPAU\s+Sector\s+(?:["“]?Pol[ií]gono Industrial["”]?|P\.I\.)\s+de las NNSS', title, re.I)
        identity = 'pau-sector-poligono-industrial-nnss' if industrial_pau else entry['url']
        if identity not in grouped:
            grouped[identity] = {
                'id': 'corral-de-almaguer-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
                'municipio': 'Corral de Almaguer', 'codigo_ine': '45054', 'provincia': 'Toledo',
                'titulo': 'PAU Sector Polígono Industrial de las NNSS de Corral de Almaguer' if industrial_pau else title,
                'tipo': 'planeamiento_urbanistico', 'url': entry['url'], 'inventory_url': SOURCE,
                'source': 'jccm', 'origen': 'inventario_acuerdos_urbanismo',
                'documentos': [], 'source_urls': [], 'publication_ready': False,
                'geometry_status': 'unavailable', 'limitations': LIMITATIONS,
            }
        row = grouped[identity]
        if entry['url'] not in row['source_urls']:
            row['source_urls'].append(entry['url'])
        known = {(d['url'], d['source_url']) for d in row['documentos']}
        row['documentos'].extend(d for d in entry['documentos'] if (d['url'], d['source_url']) not in known)
    if not grouped:
        raise ValueError('No usable planning instruments in live inventory')
    return list(grouped.values())


class CorralDeAlmaguerAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        url, seen, entries, pages = SOURCE, set(), [], []
        expected_start, expected_total = 1, None
        capture_dir = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'MunicipalPlanningInventory/1.0'
            while url:
                if url in seen:
                    raise ValueError('Pagination cycle')
                seen.add(url)
                response = session.get(url, timeout=45)
                response.raise_for_status()
                official_url(url, response.url, '/acuerdos-expedientes')
                if parse_qs(urlparse(response.url).query).get('title') != ['Corral de Almaguer']:
                    raise ValueError('Inventory redirect lost municipal filter')
                selected, (start, end, total), next_url = parse_page(response.text, response.url)
                if start != expected_start or (expected_total is not None and total != expected_total):
                    raise ValueError('Inventory changed or pagination skipped results')
                if end > total or end < start or (end < total and not next_url) or (end == total and next_url):
                    raise ValueError('Incomplete or inconsistent pagination')
                expected_start, expected_total = end + 1, total
                entries.extend(selected)
                pages.append(response.url)
                if capture_dir:
                    folder = Path(capture_dir)
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f'inventory-{len(pages)}.html').write_text(response.text, encoding='utf-8')
                url = next_url
        rows = group_instruments(entries)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(output)
        return {'count': len(rows), 'live_records': len(rows), 'inventory_entries': expected_total,
                'selected_agreements': len(entries), 'pages': len(pages),
                'source_urls': list(dict.fromkeys(pages + [u for r in rows for u in r['source_urls']] +
                                                [d['url'] for r in rows for d in r['documentos']])),
                'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full current inventory refresh; the state file is not a date watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        raise NotImplementedError('Licences disabled: no verified register of grants')

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
