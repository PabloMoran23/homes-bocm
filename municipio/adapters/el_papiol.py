"""El Papiol's two complete public-exhibition inventory pages, grouped by dossier."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.elpapiol.cat'
INDEX = BASE + '/ajuntament/informacio-publica-oficial/planejament-urbanistic-gestio-urbanistica-i-activitats/'
SOURCES = {
    INDEX + 'planejament-en-exposicio-publica': 'Planejament en exposició pública',
    INDEX + 'projectes-en-exposicio-publica': 'Projectes en exposició pública',
}
LIMITATIONS = [
    'Partial municipal coverage: the two public-exhibition inventories only; not the full RPUC archive or a granted-licence register.',
    'Exhibition listings may persist after their consultation period; no current execution or definitive approval is inferred.',
    'Agreement and publication dates are not extracted from PDF attachments; page update dates are separate metadata.',
    'Attachments are retained as linked documents, including administrative models within the fire-prevention dossier; they are not individual projects or granted licences.',
    'The fire-prevention FP and PM projects are retained as one jointly published dossier.',
    'No verified coordinates or geometry; publication_ready is false.',
]


def parse_inventory(html: str, source_url: str) -> list[dict[str, Any]]:
    if source_url not in SOURCES:
        raise ValueError('Unsupported inventory URL')
    soup = BeautifulSoup(html, 'html.parser')
    # Fail closed if the previously single-page inventory acquires pagination.
    for link in soup.select('a[href], link[href]'):
        label = link.get_text(' ', strip=True).lower()
        href = link['href']
        if ('next' in link.get('rel', []) or
                (href not in ('', '#') and (label in {'següent', 'següents', 'siguiente', 'next', '»', '›'} or
                 re.search(r'[?&](?:page|pagina|pag|offset|start)=', href, re.I))) or
                (href not in ('', '#') and link.find_parent(class_=re.compile(r'pagina|pager', re.I)))):
            raise ValueError('Pagination detected; extend traversal before extracting')
    article = soup.select_one('#readspeakerPage')
    heading = article.find('h1') if article else None
    if not heading or heading.get_text(' ', strip=True) != SOURCES[source_url]:
        raise ValueError('Missing municipal inventory content or unexpected page')
    updated = article.select_one('.updated')
    match = re.search(r'(\d{2}\.\d{2}\.\d{4})', updated.get_text()) if updated else None
    update_date = datetime.strptime(match[1], '%d.%m.%Y').date().isoformat() if match else None
    rows = []
    identities = set()
    for title_node in article.select('.dinamic > .subtitle'):
        title = title_node.get_text(' ', strip=True)
        if source_url.endswith('planejament-en-exposicio-publica'):
            if not re.search(r'Pla General Metropolità|Modificació puntual del PGM', title, re.I):
                raise ValueError('Unreviewed planning section: ' + title)
            kind = 'planeamiento_urbanistico'
        else:
            if not re.search(r"^(?:Instal·lació de pèrgoles|Projecte ordinari d.obres|Aprovació inicial del projecte de reducció)", title, re.I):
                raise ValueError('Unreviewed works section: ' + title)
            kind = 'proyecto_obra_publica'
        documents = {}
        for sibling in title_node.next_siblings:
            if getattr(sibling, 'get', None) and 'subtitle' in sibling.get('class', []):
                break
            if not getattr(sibling, 'select', None):
                continue
            for link in sibling.select('a[href]'):
                url = urljoin(source_url, link['href'])
                parsed = urlparse(url)
                is_pdf = (parsed.scheme == 'https' and parsed.hostname == 'www.elpapiol.cat' and
                          parsed.path.startswith('/media/repository/') and parsed.path.lower().endswith('.pdf'))
                is_notice = (parsed.scheme == 'https' and parsed.hostname == 'tauler.seu-e.cat' and
                             parsed.path == '/detall' and 'idEns=815800000' in parsed.query and 'idEdicte=' in parsed.query)
                if not (is_pdf or is_notice):
                    raise ValueError('Unreviewed dossier document URL: ' + url)
                documents.setdefault(url, {'titulo': link.get_text(' ', strip=True), 'url': url,
                                           'source_url': source_url,
                                           'tipo_enlace': 'pdf' if is_pdf else 'edicto_externo'})
        if not documents:
            raise ValueError('Dossier without linked source documents: ' + title)
        first = next(iter(documents))
        identity = first.rsplit('/', 1)[0] if urlparse(first).path.lower().endswith('.pdf') else first
        if identity in identities:
            raise ValueError('Ambiguous duplicate dossier identity')
        identities.add(identity)
        initial = bool(re.search(r'^Aprova(?:ció|r) inicial', title, re.I))
        rows.append({
            'id': 'el-papiol-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
            'municipio': 'El Papiol', 'codigo_ine': '08158', 'provincia': 'Barcelona',
            'titulo': title, 'tipo': kind,
            'fase': 'aprobación inicial' if initial else 'exposición pública',
            'fase_provenance': 'titulo' if initial else 'seccion_municipal',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'source_page_updated': update_date,
            'url': source_url, 'url_documento': first,
            'documentos': list(documents.values()), 'source_identity': identity,
            'source': 'ayuntamiento', 'origen': 'inventario_exposicion_publica',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'coverage': 'partial',
        })
    if not rows:
        raise ValueError('No documented projects found; review inventory')
    return rows


class ElPapiolAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='el-papiol', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = []
        for url in SOURCES:
            with requests.get(url, timeout=40, stream=True, headers={
                'User-Agent': self.config.get('user_agent', 'municipio-el-papiol/1.0')
            }) as response:
                response.raise_for_status()
                if response.url.rstrip('/') != url:
                    raise ValueError('Unexpected inventory redirect')
                data = bytearray()
                for chunk in response.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > 4_000_000:
                        raise ValueError('Inventory exceeds response bound')
                html = bytes(data).decode('utf-8')
            rows.extend(parse_inventory(html, url))
            if self.config.get('capture_dir'):
                capture = Path(self.config['capture_dir'])
                capture.mkdir(parents=True, exist_ok=True)
                (capture / (url.rsplit('/', 1)[-1] + '.html')).write_bytes(data)
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate dossiers across inventories')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES),
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Refresh both entire inventories; no date cursor can safely describe these pages.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
