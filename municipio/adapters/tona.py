"""Tona's complete single-page municipal public-works inventory (not licences)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://tona.cat/ajuntament/informacio-oficial/projectes-dobres-municipals/'
MAX_BYTES = 4_000_000


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def _date(value):
    if not value:
        return None
    if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', value):
        raise ValueError(f'Unexpected milestone date: {value!r}')
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


class TonaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='tona', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://tona.cat')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.find('h1')
        content = soup.select_one('.entry-content')
        if not title or _norm(title.get_text(' ', strip=True)) != 'projectes d’obres municipals' or content is None:
            raise ValueError('Missing Tona public-works inventory')
        # This reviewed source is one static page. Refuse partial output if it
        # becomes paginated; never impose an arbitrary number of project rows.
        if soup.select('[rel~=next], .pagination, .wp-block-query-pagination, .page-links'):
            raise ValueError('Pagination appeared; crawler must be extended')
        for a in content.select('a[href]'):
            if _norm(a.get_text(' ', strip=True)) in {'seguent', 'seguents', 'next', 'siguiente', 'mes', 'carrega mes'}:
                raise ValueError('Pagination appeared; crawler must be extended')
        rows = {}
        year = None
        for node in content.find_all(['h2', 'h3'], recursive=False):
            if node.name == 'h2':
                match = re.fullmatch(r'Any (\d{4})', node.get_text(' ', strip=True))
                year = int(match[1]) if match else None
                continue
            if year is None:
                raise ValueError('Project outside a recognised inventory year')
            heading = node.get_text(' ', strip=True)
            block = node.find_next_sibling()
            if block is None or block.name != 'ul':
                raise ValueError(f'Project lacks structured fields: {heading}')
            fields, docs = [], {}
            for item in block.find_all('li', recursive=False):
                label_node = item.find('strong')
                if label_node is None:
                    raise ValueError('Unlabelled project field')
                label = label_node.get_text(' ', strip=True)
                full = item.get_text(' ', strip=True)
                value = full[len(label):].lstrip(' :').strip()
                fields.append({'campo': label, 'valor': value})
                if _norm(label) in {'projecte', 'memoria tecnica valorada'}:
                    for a in item.select('a[href]'):
                        url = urljoin(SOURCE, a['href'])
                        if urlparse(url).scheme != 'https' or urlparse(url).hostname not in {'tona.cat', 'www.tona.cat', 'seuelectronica.tona.cat'}:
                            raise ValueError('Unexpected project document host')
                        docs[url] = {'titulo': a.get_text(' ', strip=True), 'url': url,
                                     'campo_fuente': label, 'source_url': SOURCE}
            dossier = [f['valor'] for f in fields if _norm(f['campo']) == 'expedient']
            if len(dossier) != 1 or not re.fullmatch(r'[A-Z]+/\d{4}/\d+', dossier[0]) or not docs:
                raise ValueError('Project requires one real expediente and technical documents')
            milestones = []
            for f in fields:
                key = _norm(f['campo'])
                if key.startswith(('aprovacio', 'inici ', 'finalitzacio', 'adjudicacio', 'adhesio')):
                    milestones.append({'tipo': f['campo'], 'fecha': _date(f['valor']), 'valor_fuente': f['valor']})
            def approval(prefix):
                return next((m['fecha'] for m in milestones if _norm(m['tipo']).startswith(prefix) and m['fecha']), None)
            initial = approval('aprovacio inicial')
            definitive = approval('aprovacio definitiva')
            memoir = approval('aprovacio memoria')
            row = {
                'id': 'tona-proy-' + hashlib.sha256(dossier[0].encode()).hexdigest()[:16],
                'municipio': 'Tona', 'provincia': 'Barcelona', 'codigo_ine': '08283',
                'titulo': heading, 'expediente': dossier[0], 'tipo': 'obra_publica',
                'fase': 'aprobación definitiva' if definitive else ('aprobación inicial' if initial else ('aprobación memoria técnica' if memoir else None)),
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': definitive or initial or memoir,
                'fecha_aprobacion_inicial': initial, 'fecha_aprobacion_definitiva': definitive,
                'fecha_aprobacion_memoria': memoir,
                'url': SOURCE, 'url_documento': next(iter(docs)), 'documentos': list(docs.values()),
                'source': 'ayuntamiento', 'origen': 'inventario_obras_municipales',
                'inventory_year': year, 'campos_fuente': fields, 'hitos': milestones,
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            }
            if dossier[0] in rows:
                previous = rows[dossier[0]]
                if previous['titulo'] != heading or previous['campos_fuente'] != fields:
                    raise ValueError('Conflicting duplicate expediente; review source')
                previous['documentos'] = list({d['url']: d for d in previous['documentos'] + row['documentos']}.values())
            else:
                rows[dossier[0]] = row
        if not rows:
            raise ValueError('No public works found; source changed')
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.get(SOURCE, timeout=(10, 40), stream=True,
                          headers={'User-Agent': 'municipio-tona/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname not in {'tona.cat', 'www.tona.cat'}:
                raise ValueError('Unexpected inventory redirect')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ValueError('Inventory exceeds bounded response size')
            html = bytes(data).decode('utf-8')
        rows = self.parse_projects(html)
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'obres.html').write_text(html, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot refresh, including changed milestones on existing works.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
