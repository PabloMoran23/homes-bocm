"""Canovelles official public-works inventory; complete single-page snapshot."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/canovelles/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/projectes-d-obres-i-activitats-211')


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def phase(label):
    label = label.lower()
    if 'aprovació definitiva' in label:
        return 'aprobación definitiva'
    if 'aprovació inicial' in label:
        return 'aprobación inicial'
    return None


class CanovellesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.canovelles.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        # The reviewed inventory is static HTML, without pagination. Stop if this
        # changes, instead of returning only the first page of a future inventory.
        for a in soup.select('a[href], button'):
            if ('next' in a.get('rel', []) or
                    text(a).lower() in {'següent', 'següents', 'siguiente', 'next', '›', '»'}):
                if not a.has_attr('disabled') and 'disabled' not in a.get('class', []):
                    raise ValueError('Pagination detected; inventory coverage needs review')
        if re.search(r'["\']?serverSide["\']?\s*:\s*true', html, re.I):
            raise ValueError('Server-side inventory requires pagination support')
        articles = [a for a in soup.select('.journal-content-article')
                    if a.select_one('a[href*="/documents/"]')]
        if len(articles) != 1 or not articles[0].div:
            raise ValueError('Missing or ambiguous public-works inventory')
        groups = []
        current = None
        year = None
        for node in articles[0].div.find_all(recursive=False):
            label = text(node)
            if node.name == 'h4' and label:
                match = re.fullmatch(r'ANY (\d{4})', label)
                if not match:
                    raise ValueError('Unrecognized year section')
                year = int(match[1])
                current = None
            elif node.name == 'p' and node.find(['strong', 'b']) and label:
                current = {'title': label, 'year': year, 'docs': []}
                groups.append(current)
            else:
                links = node.select('a[href]')
                if links and current is None:
                    raise ValueError('Unassigned inventory documents')
                for a in links:
                    url = urljoin(SOURCE, a['href'])
                    if (urlparse(url).hostname not in {'seu-e.cat', 'www.seu-e.cat'} or
                            not urlparse(url).path.startswith('/documents/2562153/')):
                        raise ValueError('Unexpected document provenance')
                    context = text(a.find_parent('li') or a)
                    current['docs'].append({'titulo': text(a), 'url': url,
                                            'contexto': context, 'fase': phase(context),
                                            'source_url': SOURCE})
        rows = []
        for group in groups:
            title = group['title']
            # Activity legalisation dossiers and a service cost proposal are not
            # physical works. Keep them out even though listed on the same page.
            if re.match(r"Projecte d'activitats\b|Proposta d'estructura de costos\b", title, re.I):
                continue
            if not re.match(r'Projectes?\b|Arranjament i pavimentació\b|Restauració de la façana\b', title, re.I):
                raise ValueError('Unreviewed inventory heading: ' + title)
            docs = list({d['url']: d for d in group['docs']}.values())
            technical = [d for d in docs if not re.match(r'^(Anunci|Acord|Edicte|Aprovació)\b', d['contexto'], re.I)]
            if not technical or group['year'] is None:
                raise ValueError('Works heading has no technical documents or year: ' + title)
            stages = {d['fase'] for d in docs}
            stage = ('aprobación definitiva' if 'aprobación definitiva' in stages else
                     'aprobación inicial' if 'aprobación inicial' in stages else None)
            identity = technical[0]['url'].rsplit('/', 1)[-1]
            rows.append({
                'id': 'canovelles-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
                'municipio': 'Canovelles', 'codigo_ine': '08041', 'provincia': 'Barcelona',
                'titulo': title, 'tipo': 'proyecto_obra_publica', 'fase': stage,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'anio_seccion_inventario': group['year'],
                'url': SOURCE, 'url_documento': technical[0]['url'], 'documentos': docs,
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_obras',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'Sin geometría verificada; documentos gráficos enlazados',
            })
        if not rows or len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Empty inventory or duplicate work identity')
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.get(SOURCE, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-canovelles/1.0'}) as response:
            response.raise_for_status()
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected official HTML inventory')
            chunks = []
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory exceeds response size limit')
                chunks.append(chunk)
            html = b''.join(chunks).decode('utf-8')
        rows = self.parse_projects(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'live-obras.html').write_text(html, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'Complete static works page; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
