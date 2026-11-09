"""Partial municipal inventory: modern sections of Vilafant's planning page."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.vilafant.cat/per-temes/urbanisme/planejament-en-tramit'
LIMITATIONS = [
    'Partial snapshot: municipal 2024-onwards complementary documents and supported works/planning entries throughout the 2020-23 section; 2013-19 archive excluded.',
    'Since 2024 the municipality directs readers to e-Tauler; its JavaScript application is not an extracted notice inventory.',
    'Other municipal general/derived planning and urban management inventories are not harvested.',
    'Linked documents are retained, not downloaded or independently interpreted; labels may contain source errors.',
    'No granted licences, verified geometry or current execution status; publication_ready is false.',
]
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def publication_date(label):
    """Only a labelled bulletin publication date, never an exposure deadline."""
    if not re.search(r'\b(?:BOP|DOGC)\b', label, re.I):
        return None
    numeric = re.search(r'\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b', label)
    words = re.search(r"\b(\d{1,2})\s+(?:d[’']|de\s+)?(\w+)(?:\s+de[l]?)?[,]?\s+(\d{4})\b", label.lower())
    try:
        if numeric:
            return date(int(numeric[3]), int(numeric[2]), int(numeric[1])).isoformat()
        if words and words[2] in MONTHS:
            return date(int(words[3]), MONTHS[words[2]], int(words[1])).isoformat()
    except ValueError:
        pass
    return None


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


class VilafantAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='vilafant', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.vilafant.cat')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('#content-core #parent-fieldname-text')
        if content is None:
            raise ValueError('Municipal inventory content missing')
        for a in soup.select('a[href]'):
            if ('next' in a.get('rel', []) or
                _text(a).lower() in {'següent', 'seguent', 'siguiente', 'next', '»'} or
                'b_start' in a['href']):
                raise ValueError('Pagination detected; refusing incomplete snapshot')
        sections = [_text(h) for h in content.select('h2')]
        expected = ['2024 endavant', 'Projectes i planejament en tràmit vigents 2020-23',
                    'Projectes i planejament en tràmit anteriors 2013-19']
        if sections != expected:
            raise ValueError('Inventory sections changed; review coverage before extraction')
        rows = {}

        def add(title, nodes, section):
            fragment = BeautifulSoup(''.join(str(n) for n in nodes), 'html.parser')
            description = _text(fragment)
            documents = {}
            for a in fragment.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                if urlparse(url).scheme not in {'http', 'https'}:
                    continue
                context = a.find_parent('li') or a.find_parent('p') or a
                label = _text(context)
                documents.setdefault(url, {'titulo': _text(a), 'url': url,
                    'contexto': label, 'fecha_publicacion': publication_date(_text(a)),
                    'provenance_url': SOURCE})
            if not documents:
                raise ValueError('Project lacks documentary links: ' + title)
            matches = set(re.findall(r'\bX\d{10}\b', title + ' ' + description))
            if len(matches) > 1:
                raise ValueError('Multiple expedientes in one project block')
            expediente = next(iter(matches), None)
            key = expediente or re.sub(r'\W+', ' ', title.casefold()).strip()
            row = rows.setdefault(key, {
                'id': 'vilafant-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Vilafant', 'provincia': 'Girona', 'codigo_ine': '17221',
                'titulo': title, 'expediente': expediente,
                'tipo': 'planeamiento_urbanistico' if re.search(r'pla especial|reparcel|trama urbana', title, re.I) else 'proyecto de obras',
                'fase': None, 'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal',
                'seccion_fuente': section, 'descripcion': description, 'documentos': [],
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            })
            known = {d['url'] for d in row['documentos']}
            row['documentos'].extend(d for u, d in documents.items() if u not in known)

        section = None
        for node in content.children:
            if getattr(node, 'name', None) == 'h2':
                section = _text(node)
            if section == expected[0] and getattr(node, 'name', None) == 'ul':
                for li in node.find_all('li', recursive=False):
                    strong = li.find('strong', recursive=False)
                    if strong and re.match(r'Reurbanització\b', _text(strong), re.I):
                        add(_text(strong), [li], section)
            if section != expected[1] or getattr(node, 'name', None) != 'h4':
                continue
            title = _text(node)
            if not re.match(r'^(?:projecte\b|aprovació del projecte\b|memòria valorada obra\b|supressió d.esglaons\b|obra de\b|exposició pública obra\b|pla especial\b)', title, re.I):
                continue
            nodes = [node]
            for sibling in node.next_siblings:
                if getattr(sibling, 'name', None) in {'h2', 'h3', 'h4'}:
                    break
                nodes.append(sibling)
            add(title, nodes, section)
        if not rows:
            raise ValueError('No supported municipal projects')
        return list(rows.values())

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=(10, 45), stream=True,
            headers={'User-Agent': self.config.get('user_agent', 'municipio-vilafant/1.0')})
        with response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Inventory response exceeds size bound')
                chunks.append(chunk)
            payload = b''.join(chunks)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory.html').write_bytes(payload)
        rows = self.parse_projects(payload.decode('utf-8'))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of the explicitly scoped inventory, not a date cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
