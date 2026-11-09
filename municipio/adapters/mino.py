"""Miño: complete published POS+ works table from the provincial authority."""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://plan-unico.dacoruna.gal/mino/'


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _money(text):
    text = text.replace('\xa0', ' ').strip()
    if not re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}\s*€', text):
        raise ValueError('Unrecognized POS+ monetary value')
    return str(Decimal(text.replace('€', '').replace(' ', '').replace('.', '').replace(',', '.')))


class MinoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.find('h1')
        if not heading or _text(heading) != 'PLAN ÚNICO Miño':
            raise ValueError('Wrong municipality or changed POS+ inventory')
        selected = soup.select_one('#selector-exercicio option[selected]')
        if not selected or selected.get('value') != 'todos':
            raise ValueError('POS+ inventory is filtered; all exercises required')
        for a in soup.select('a[href], button'):
            label = ' '.join((_text(a), a.get('aria-label', ''), a.get('rel', [''])[0])).lower()
            if re.search(r'\b(next|siguiente|seguinte|próxima|load more|cargar m[aá]is)\b', label):
                raise ValueError('Unreviewed POS+ pagination; refusing partial snapshot')
        tables = soup.select('table[aria-label="Lista de obras e investimentos"]')
        if len(tables) != 1:
            raise ValueError('Missing or ambiguous works table')
        table = tables[0]
        if [_text(t) for t in table.select('thead th')] != ['Exercicio', 'Obxecto', 'Orzamento', 'Aportación']:
            raise ValueError('POS+ table schema changed')
        counters = [t for t in soup.select('li') if t.find('span', string='Obras aprobadas')]
        if len(counters) != 1:
            raise ValueError('Missing approved works count')
        count = re.fullmatch(r'Obras aprobadas\s+(\d+)', _text(counters[0]))
        if not count:
            raise ValueError('Unrecognized approved works count')
        rows = {}
        for tr in table.select('tbody tr'):
            cells = tr.find_all('td', recursive=False)
            if len(cells) != 4:
                raise ValueError('Incomplete works row')
            year, title = _text(cells[0]), _text(cells[1])
            if not re.fullmatch(r'20\d{2}', year) or not title:
                raise ValueError('Invalid exercise or empty work title')
            # The catalog has no expediente ID: this is a synthetic identity,
            # never an invented official reference. Budget edits preserve it.
            key = hashlib.sha256(f'15048|{year}|{title}'.encode()).hexdigest()[:20]
            if key in rows:
                raise ValueError('Ambiguous duplicate work identity')
            docs = {}
            for a in tr.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                if not url.startswith('https://'):
                    raise ValueError('Unexpected work document URL')
                docs[url] = {'titulo': _text(a), 'url': url, 'procedencia': SOURCE}
            rows[key] = {
                'id': 'mino-pos-' + key, 'municipio': 'Miño', 'codigo_ine': '15048',
                'provincia': 'A Coruña', 'titulo': title, 'tipo': 'obra_publica',
                'source': 'diputacion', 'origen': 'plan_unico_pos', 'url': SOURCE,
                'source_entity_type': 'actuacion', 'ejercicio': int(year),
                'presupuesto_eur': _money(_text(cells[2])),
                'aportacion_eur': _money(_text(cells[3])),
                'estado_fuente': 'Obras aprobadas',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'documentos': list(docs.values()),
                'procedencia': {'organismo': 'Deputación Provincial da Coruña',
                                'url': SOURCE, 'tabla': 'Lista de obras e investimentos'},
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            }
        if not rows or len(rows) != int(count[1]):
            raise ValueError('Incomplete POS+ snapshot: rows differ from approved works count')
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=45, headers={'User-Agent': 'municipio-mino/1.0'})
        response.raise_for_status()
        if response.url != SOURCE or len(response.content) > 5_000_000:
            raise ValueError('Unexpected redirect or oversized POS+ source')
        html = response.content.decode('utf-8')
        rows = self.parse_projects(html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'pos-live.html').write_text(html, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'coverage': 'published POS+ works only'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
