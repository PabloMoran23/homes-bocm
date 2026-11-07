"""Ansoáin: municipal spatial plans and named PEAU participation dossiers.

Two current HTML inventories, not a licence register or an archive of approvals.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.ansoain.es'
INVENTORIES = {
    'planes': BASE + '/ayuntamiento/agenda-2030/',
    'participacion': BASE + '/procesos-participativos/',
}


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('main .contenido.content')
    if content is None:
        raise ValueError('Municipal inventory content missing')
    # These inventories are single pages. A newly paginated version needs review.
    for a in soup.select('main a[href]'):
        if a['href'] in ('', '#'):
            continue
        if ('next' in a.get('rel', []) or
                _norm(a.get_text(' ', strip=True)) in {'siguiente', 'next', 'hurrengoa', '»', '›'} or
                re.search(r'/page/\d+|[?&](?:paged|page)=\d+', a['href'])):
            raise ValueError('Paginated inventory requires traversal before extraction')
    if soup.select('main .pagination, main .page-numbers, main .nav-links'):
        raise ValueError('Pagination controls require review')
    return content


def _documents(block, source_url, role):
    docs = {}
    for a in block.select('a[href]'):
        url = urljoin(source_url, a['href'])
        if not urlparse(url).path.lower().endswith('.pdf'):
            continue
        if urlparse(url).hostname != 'www.ansoain.es' or urlparse(url).scheme != 'https':
            raise ValueError('Unexpected document host or scheme')
        docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                              'source_url': source_url, 'tipo': role})
    if not docs:
        raise ValueError('Named instrument has no PDF documents')
    return list(docs.values())


def _record(key, title, url, inventory, docs, kind, phase):
    return {
        'id': 'ansoain-plan-' + key, 'municipio': 'Ansoáin / Antsoain',
        'codigo_ine': '31016', 'provincia': 'Navarra', 'titulo': title,
        'tipo': kind, 'fase': phase, 'url': url, 'inventory_url': inventory,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_planes',
        'documentos': docs, 'geometry_status': 'unavailable',
        'publication_ready': False,
    }


def parse_inventory(html, inventory):
    """Group PDFs by their instrument, excluding generic policies and forms."""
    content = _content(html)
    rows = {}
    if inventory == INVENTORIES['planes']:
        for p in content.find_all('p', recursive=False):
            # Remove link labels (Parte 1/2) from the instrument's title.
            clone = BeautifulSoup(str(p), 'html.parser')
            for a in clone.select('a'):
                a.decompose()
            title = clone.get_text(' ', strip=True).rstrip(':').strip()
            normalized = _norm(title)
            if re.match(r'^(pmus\b|plan (?:de )?movilidad urbana sostenible\b)', normalized):
                key = 'pmus'
            elif re.match(r'^plan (?:de )?infraestructura verde\b', normalized):
                key = 'infraestructura-verde'
            else:
                continue
            docs = _documents(p, inventory, 'plan_sectorial_espacial')
            parts = [re.search(r'parte\s*(\d+)', _norm(d['titulo'])) for d in docs]
            numbers = {int(m.group(1)) for m in parts if m}
            if numbers and (len(numbers) != len(docs) or numbers != set(range(1, max(numbers) + 1)) or len(numbers) < 2):
                raise ValueError('Incomplete multipart plan')
            if key in rows:
                raise ValueError('Duplicate instrument sections require grouping review')
            rows[key] = _record(key, title, inventory, inventory, docs,
                                'plan_sectorial_espacial', 'documentacion_publicada_sin_aprobacion_verificada')
    elif inventory == INVENTORIES['participacion']:
        for block in content.select('div.bloque'):
            tab = block.select_one('a.bloque-tab[href]')
            if tab is None:
                continue
            title = tab.get_text(' ', strip=True)
            if not re.search(r'\bpeau\b|plan especial (?:de )?actuacion urbana', _norm(title)):
                continue
            fragment = tab['href']
            if not fragment.startswith('#') or not fragment[1:]:
                raise ValueError('Planning section lacks stable fragment')
            body = block.find(id=fragment[1:])
            if body is None:
                raise ValueError('Planning section body missing')
            docs = _documents(body, inventory, 'plan_participacion_previo_al_planeamiento')
            key = hashlib.sha256(fragment.encode()).hexdigest()[:16]
            if key in rows:
                raise ValueError('Duplicate planning section')
            rows[key] = _record(key, title, inventory + fragment, inventory, docs,
                                'plan_especial_actuacion_urbana', 'participacion_previa_segun_inventario')
    else:
        raise ValueError('Unknown inventory')
    if not rows:
        raise ValueError('No supported instruments; inventory needs review')
    return list(rows.values())


class AnsoainAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, pdf=False):
        response = requests.get(url, timeout=(15, 90), headers={
            'User-Agent': 'municipio-ansoain/1.0 (public municipal planning inventory)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != 'www.ansoain.es':
            raise ValueError('Unexpected source redirect')
        if pdf and not response.content.lstrip().startswith(b'%PDF-'):
            raise ValueError('Document is not a PDF: ' + url)
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16]
            (directory / (name + ('.pdf' if pdf else '.html'))).write_bytes(response.content)
        return response

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'rows': len(rows), 'count': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows = []
        for inventory in INVENTORIES.values():
            rows.extend(parse_inventory(self._fetch(inventory).text, inventory))
        # Validate every linked document before replacing a previous snapshot.
        fetched = {}
        for row in rows:
            for doc in row['documentos']:
                if doc['url'] not in fetched:
                    response = self._fetch(doc['url'], pdf=True)
                    fetched[doc['url']] = hashlib.sha256(response.content).hexdigest()
                doc['sha256'] = fetched[doc['url']]
        return {**self._write(out_jsonl, rows), 'coverage': 'current_selected_spatial_plans_and_peau_participation',
                'documents': len(fetched), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current snapshot; state_path is not an approval/change ledger.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
