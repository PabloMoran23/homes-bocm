"""Current PBOM document inventory, endorsed by the municipal website."""
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

SOURCE = 'https://nuevoplanfuentesdeandalucia.es/'
PROVENANCE = ('https://fuentesdeandalucia.org/el-ayuntamiento-presenta-a-la-ciudadania-'
              'el-documento-previo-de-diagnostico-del-nuevo-plan-basico-de-ordenacion-municipal/')
LIMITATIONS = [
    'Partial coverage: only the current new PBOM portal, not historic planning or public works.',
    'Phase indicator is reproduced literally; future phase descriptions do not establish approval.',
    'No instrument publication, agreement or approval date is established; news date is separate.',
    'No verified geometry or granted licence register; publication_ready is false.',
    'Planos is an external transfer link; availability and contents are not verified.',
]


def parse_provenance(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article')
    if article is None or not any(
        urljoin(PROVENANCE, a['href']).rstrip('/') == SOURCE.rstrip('/')
        for a in article.select('a[href]')
    ):
        raise ValueError('Municipal article no longer endorses the PBOM portal')
    if 'Plan Básico de Ordenación Municipal' not in article.get_text(' ', strip=True):
        raise ValueError('Municipal PBOM provenance missing')
    published = article.select_one('time[datetime]')
    value = published['datetime'][:10] if published else None
    if value:
        value = date.fromisoformat(value).isoformat()
    return {'url': PROVENANCE, 'tipo': 'noticia municipal de presentación del diagnóstico',
            'fecha_publicacion': value}


def parse_inventory(html: str, provenance: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    text = soup.get_text(' ', strip=True)
    if 'PBOM de Fuentes de Andalucía' not in title or 'Plan Básico de Ordenación Municipal' not in text:
        raise ValueError('PBOM inventory identity missing')
    # This is a single-page inventory. Fail explicitly if it becomes paginated.
    if soup.select('a[rel~=next], .pagination, .nav-links, .page-numbers'):
        raise ValueError('Inventory now exposes pagination; traversal must be implemented')
    documents = {}
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True)
        url = urljoin(SOURCE, a['href'])
        parsed = urlparse(url)
        if not label:
            continue  # includes an unrelated linked Peñaflor image in the template
        local_pdf = (parsed.hostname == urlparse(SOURCE).hostname
                     and parsed.path.startswith('/wp-content/uploads/')
                     and parsed.path.lower().endswith('.pdf'))
        external_plans = parsed.hostname == 'we.tl' and label.casefold() == 'planos'
        if local_pdf or external_plans:
            documents[url] = {'titulo': label, 'url': url, 'inventory_url': SOURCE,
                              'tipo': 'documento PDF' if local_pdf else 'enlace externo a planos'}
    if not any('diagnóstico' in d['titulo'].casefold() for d in documents.values()):
        raise ValueError('No published PBOM diagnostic document found')
    phase = soup.select_one('.eb-progressbar-title')
    phase_text = phase.get_text(' ', strip=True) if phase else None
    if phase_text and not re.fullmatch(r'FASE ACTUAL:\s*\d+', phase_text):
        raise ValueError('Unrecognized current phase indicator')
    return [{
        'id': 'fuentes-de-andalucia-plan-' + hashlib.sha256(SOURCE.encode()).hexdigest()[:16],
        'municipio': 'Fuentes de Andalucía', 'provincia': 'Sevilla', 'codigo_ine': '41042',
        'titulo': title, 'tipo': 'Plan Básico de Ordenación Municipal',
        'fase': phase_text, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': SOURCE, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
        'origen': 'inventario_documental_pbom', 'documentos': list(documents.values()),
        'fuentes': [provenance, {'url': SOURCE, 'tipo': 'portal del PBOM enlazado por el Ayuntamiento'}],
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False, 'limitations': LIMITATIONS,
    }]


class FuentesDeAndaluciaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='fuentes-de-andalucia', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def _fetch(self, url: str, name: str) -> str:
        with requests.get(url, timeout=45, stream=True, headers={
            'User-Agent': 'municipio-fuentes-de-andalucia/1.0'
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != urlparse(url).hostname:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Source exceeds response size limit')
                chunks.append(chunk)
            body = b''.join(chunks)
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(body)
        return body.decode('utf-8')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        provenance = parse_provenance(self._fetch(PROVENANCE, 'pbom-municipal-provenance.html'))
        rows = parse_inventory(self._fetch(SOURCE, 'pbom.html'), provenance)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE, PROVENANCE],
                'coverage': 'current_pbom_document_inventory', 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh of one unpaginated instrument, not a dated news feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
