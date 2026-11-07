"""Official current planning inventory, without inferred dates or geometry."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter

SETTINGS = {'slug': 'caldes-de-montbui', 'nombre': 'Caldes de Montbui', 'ine': '08033', 'province': 'Barcelona', 'region': 'catalunya', 'cls': 'CaldesDeMontbuiAyuntamientoAdapter', 'url': 'https://seu-e.cat/ca/web/caldesdemontbui/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic', 'mode': 'table'}


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    groups = []
    if SETTINGS['mode'] == 'links':
        content = soup.select_one('main')
        if content is None:
            raise ValueError('Inventory selector missing')
        for a in content.select('a[href]'):
            target = urljoin(url, a['href'])
            if urlparse(target).hostname == 'dtes.gencat.cat' and re.search(r'/detallExpedient/\d+', target):
                groups.append((a.get_text(' ', strip=True), target, []))
    elif SETTINGS['mode'] == 'documents':
        for a in soup.select('a[href]'):
            target = urljoin(url, a['href'])
            title = a.get_text(' ', strip=True)
            if urlparse(target).hostname == urlparse(url).hostname and '/documents/' in urlparse(target).path and re.match(r'plan (?:director|de movilidad)', title, re.I):
                groups.append((title.removesuffix('.pdf'), target, [{'titulo': title, 'url': target}]))
    else:
        for table in soup.select('table'):
            headers = [th.get_text(' ', strip=True) for th in table.select('thead th')]
            if 'Número expedient' not in headers or 'Tema' not in headers:
                continue
            for tr in table.select('tbody tr'):
                cells = tr.find_all('td', recursive=False)
                if len(cells) != len(headers):
                    raise ValueError('Unexpected planning table layout')
                fields = dict(zip(headers, cells))
                title = fields['Tema'].get_text(' ', strip=True)
                links = fields['Enllaç'].select('a[href]')
                if not title or not links:
                    continue
                target = urljoin(url, links[0]['href'])
                if urlparse(target).hostname != 'dtes.gencat.cat' or '/detallExpedient/' not in target:
                    continue
                documents = [{'titulo': a.get_text(' ', strip=True), 'url': urljoin(url, a['href'])} for a in fields['Documents'].select('a[href]') if urlparse(urljoin(url, a['href'])).hostname == urlparse(url).hostname]
                groups.append((title, target, documents))
    records = {}
    for title, target, documents in groups:
        if not title:
            continue
        key = SETTINGS['slug'] + '-plan-' + hashlib.sha256(target.encode()).hexdigest()[:16]
        records[key] = {'id': key, 'municipio': SETTINGS['nombre'], 'codigo_ine': SETTINGS['ine'],
                        'titulo': title, 'tipo': 'instrumento de planeamiento', 'url': target,
                        'inventory_url': url, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                        'documentos': documents, 'publication_ready': False, 'geometry_status': 'unavailable'}
    if not records:
        raise ValueError('No named planning entries found')
    return list(records.values())


class CaldesDeMontbuiAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        response = requests.get(SETTINGS['url'], timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(SETTINGS['url']).hostname:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'publication_ready': False, 'coverage': 'current_document_inventory'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
