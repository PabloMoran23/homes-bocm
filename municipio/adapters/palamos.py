"""Official current planning inventory, without inferred dates or geometry."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter

SETTINGS = {'slug': 'palamos', 'nombre': 'Palamós', 'ine': '17118', 'province': 'Girona', 'region': 'catalunya', 'cls': 'PalamosAyuntamientoAdapter', 'url': 'https://www.palamos.cat/POUM/index.html', 'content': 'body', 'title': 'title', 'mode': 'page', 'document_paths': ['/poum/planols/pdf/']}


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one(SETTINGS['content'])
    if content is None:
        raise ValueError('Planning inventory content selector missing')
    documents, groups = [], []
    def doc(anchor):
        target = urljoin(url, anchor.get('href', ''))
        if urlparse(target).hostname != urlparse(url).hostname:
            return None
        if not any(part in urlparse(target).path.lower() for part in SETTINGS['document_paths']):
            return None
        return {'titulo': anchor.get_text(' ', strip=True), 'url': target}
    if SETTINGS['mode'] == 'sections':
        current = None
        for node in content.find_all(['h2', 'h3', 'a']):
            if node.name in ('h2', 'h3'):
                text = node.get_text(' ', strip=True)
                if not text:
                    continue
                if node.name == 'h2' and text in ('Plans de millora', 'Plans especials', 'Pla parcial'):
                    current = None
                elif text == 'Projecte':
                    continue
                else:
                    current = [text, []]
                    groups.append(current)
            elif current is not None:
                item = doc(node)
                if item:
                    current[1].append(item)
    else:
        title = soup.select_one(SETTINGS['title'])
        if title is None:
            raise ValueError('Plan title missing')
        groups = [(title.get_text(' ', strip=True), [item for anchor in content.select('a[href]') if (item := doc(anchor))])]
    rows = []
    for title, documents in groups:
        unique = {item['url']: item for item in documents}
        if not title or not unique:
            continue
        rows.append({'id': SETTINGS['slug'] + '-plan-' + hashlib.sha256(title.encode()).hexdigest()[:16],
                     'municipio': SETTINGS['nombre'], 'codigo_ine': SETTINGS['ine'],
                     'titulo': title, 'tipo': 'instrumento de planeamiento',
                     'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                     'documentos': list(unique.values()), 'publication_ready': False,
                     'geometry_status': 'unavailable'})
    if not rows:
        raise ValueError('No named plans with supporting documents found')
    return rows


class PalamosAyuntamientoAdapter(AyuntamientoAdapter):
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
