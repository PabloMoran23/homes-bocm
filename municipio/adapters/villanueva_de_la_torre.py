"""Complete municipal POM document-folder snapshot; not a licence register."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'villanuevadelatorre.sedelectronica.es'
INDEX = f'https://{HOST}/transparency/ba147749-25db-4fbb-8010-2bf088e84d4b/'
POM = f'https://{HOST}/transparency/87e10476-50d2-4db1-ba55-0aab0fa8548b/'
LIMITATIONS = [
    'Cobertura parcial: carpeta POM y sus modificaciones; excluye PAUS, PEIS, sectores antiguos y expedientes en tramitación.',
    'Inventario documental publicado actualmente; no acredita vigencia legal ni estado de ejecución.',
    'Sin fechas de acuerdo, aprobación o publicación verificadas; creación del archivo no equivale a aprobación.',
    'Sin geometría ni coordenadas verificadas; publication_ready=false.',
    'No se extraen licencias concedidas, formularios ni anuncios de contratación.',
]


def checked_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != HOST:
        raise ValueError('Unexpected municipal source URL')
    return url


def action_url(element, base: str) -> str:
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing pagination/folder action')
    return checked_url(urljoin(base, match[1]))


def folder_count(html: str) -> int:
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.select_one('table.TransparencyListPanel'):
        raise ValueError('Missing planning inventory')
    matches = []
    for a in soup.select('table a.exp'):
        m = re.fullmatch(r'POM\s*\(\s*(\d+)\s*\)', a.get_text(' ', strip=True))
        if m:
            matches.append(int(m[1]))
    if len(matches) != 1 or matches[0] < 1:
        raise ValueError('Missing or ambiguous POM folder count')
    return matches[0]


def parse_page(text: str, base: str, *, initial: bool = False):
    """Parse full HTML or Wicket CDATA components without executing JavaScript."""
    if initial:
        soup = BeautifulSoup(text, 'html.parser')
        if not soup.select_one('table.TransparencyListPanel') or not re.search(
            r'7\.1\. PLANEAMIENTO URBANÍSTICO\s*/\s*POM', soup.get_text(' ', strip=True)
        ):
            raise ValueError('Missing POM inventory context')
        content = soup.select_one('table.TransparencyListPanel')
    else:
        root = ElementTree.fromstring(text)
        if root.tag != 'ajax-response':
            raise ValueError('Unexpected pagination response')
        components = root.findall('component')
        if not components:
            raise ValueError('Pagination contains no components')
        soup = BeautifulSoup('\n'.join(c.text or '' for c in components), 'html.parser')
        content = soup
    docs = []
    for a in content.select('a[href]'):
        href = a['href']
        if '/preview-document/' not in href:
            continue
        target = checked_url(urljoin(base, href))
        if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path):
            raise ValueError('Unexpected document identifier')
        title = a.get_text(' ', strip=True)
        if not title:
            raise ValueError('Untitled POM document')
        docs.append({'titulo': title, 'url': target, 'inventory_url': POM})
    buttons = [b for b in soup.select('.more_results button') if 'Mostrar más' in b.get_text(' ', strip=True)]
    if len(buttons) > 1:
        raise ValueError('Ambiguous pagination')
    more = action_url(buttons[0], base) if buttons else None
    folders = []
    for a in content.select('a.exp'):
        match = re.fullmatch(r'(.+?)\s*\(\s*(\d+)\s*\)', a.get_text(' ', strip=True))
        if not match or not match[1].startswith('MODIFICACI'):
            raise ValueError('Unexpected POM subfolder')
        folders.append({'titulo': match[1], 'count': int(match[2]), 'action': action_url(a, base)})
    if not docs and not folders:
        raise ValueError('No POM documents in source page')
    return docs, more, folders


def build_record(documents: list[dict[str, str]], expected: int, title: str | None = None, source_url: str = POM) -> dict[str, Any]:
    unique = {d['url']: d for d in documents}
    if len(unique) != expected or len(documents) != expected:
        raise ValueError(f'Incomplete or repeated POM inventory: {len(unique)}/{expected}')
    titles = [d['titulo'].upper() for d in documents]
    if not title and (not any('MEMORIA' in t for t in titles) or not any('NORMATIVA' in t for t in titles)):
        raise ValueError('POM lacks memory or planning regulations')
    return {
        'id': 'villanueva-de-la-torre-pom-' + hashlib.sha256(source_url.encode()).hexdigest()[:16],
        'municipio': 'Villanueva de la Torre', 'provincia': 'Guadalajara', 'codigo_ine': '19319',
        'titulo': title or 'Plan de Ordenación Municipal de Villanueva de la Torre (POM)',
        'tipo': 'Modificación del POM' if title else 'Plan de Ordenación Municipal', 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': source_url, 'inventory_url': INDEX, 'source': 'ayuntamiento',
        'origen': 'inventario_municipal_planeamiento',
        'descripcion': 'Documentos agrupados por su carpeta del inventario municipal POM. No se infiere aprobación, vigencia jurídica ni estado de ejecución.',
        'documentos': sorted(unique.values(), key=lambda d: d['url']),
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False, 'limitations': LIMITATIONS,
    }


class VillanuevaDeLaTorreAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or f'https://{HOST}')

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        captures = self.config.get('capture_dir')
        capture_dir = Path(captures) if captures else None
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-villanueva-de-la-torre/1.0'

            def fetch(url, name):
                checked_url(url)
                response = session.get(url, timeout=40)
                response.raise_for_status()
                checked_url(response.url)
                if len(response.content) > 5_000_000:
                    raise ValueError('Source exceeds response size limit')
                if capture_dir:
                    capture_dir.mkdir(parents=True, exist_ok=True)
                    (capture_dir / name).write_bytes(response.content)
                source_urls.append(response.url)
                return response.text, response.url

            index, _ = fetch(INDEX, 'live-index.html')
            expected = folder_count(index)
            total_pages = 0

            def collect(url, count, label=None, depth=0):
                nonlocal total_pages
                if depth > 2:
                    raise ValueError('Unexpected folder depth')
                text, base = fetch(url, f'live-folder-{total_pages}.html')
                folder_url = base
                docs, more, folders = parse_page(text, base, initial=True)
                total_pages += 1
                page = 0
                while more:
                    page += 1
                    if page > count:
                        raise ValueError('Non-terminating POM pagination')
                    text, base = fetch(more, f'live-page-{total_pages}.xml')
                    batch, more, children = parse_page(text, base)
                    total_pages += 1
                    if {d['url'] for d in docs} & {d['url'] for d in batch}:
                        raise ValueError('Repeated document in pagination')
                    docs.extend(batch)
                    folders.extend(children)
                direct_count = count - sum(f['count'] for f in folders)
                for d in docs:
                    d['inventory_url'] = folder_url
                rows = [build_record(docs, direct_count, label, folder_url)]
                for f in folders:
                    rows.extend(collect(f['action'], f['count'], f['titulo'], depth + 1))
                return rows

            records = collect(POM, expected)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
        return {'status': 'ok', 'rows': len(records), 'documents': sum(len(r['documentos']) for r in records), 'pages': total_pages,
                'source_urls': source_urls, 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
