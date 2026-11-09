"""Los Silos: municipal planning document inventory, grouped by instrument."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.lossilos.es/plan-urbanistico-3/'


def parse_sections(html: str, page_url: str) -> list[dict]:
    """Read Divi document sections; fail if pagination or markup needs review."""
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('a[rel~=next], .pagination a[href], .page-numbers[href], .wp-pagenavi a[href]'):
        raise ValueError('Paginated planning inventory requires traversal before extraction')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', '»', '›'} and a['href'] not in {'', '#'}:
            raise ValueError('Unexpected next-page link')
    sections = []
    for block in soup.select('.et_pb_accordion_item'):
        heading = block.select_one('.et_pb_toggle_title')
        content = block.select_one('.et_pb_toggle_content')
        if heading is None or content is None:
            raise ValueError('Incomplete planning section')
        title = heading.get_text(' ', strip=True)
        links = []
        for a in content.select('a[href]'):
            target = urljoin(page_url, a['href'])
            parsed = urlparse(target)
            if parsed.scheme != 'https' or parsed.hostname != 'www.lossilos.es':
                raise ValueError(f'Unexpected planning link: {target}')
            suffix = Path(unquote(parsed.path)).suffix.lower()
            if suffix == '.pdf':
                kind = 'documento'
            elif suffix in {'.png', '.jpg', '.jpeg', '.gif'}:
                kind = 'imagen_no_documental'
            elif not suffix and not parsed.query and not parsed.fragment:
                kind = 'indice'
            else:
                raise ValueError(f'Unsupported planning link: {target}')
            links.append({'titulo': a.get_text(' ', strip=True) or title,
                          'url': target, 'tipo_enlace': kind,
                          'pagina_fuente': page_url, 'seccion_fuente': title})
        if not links:
            raise ValueError(f'Planning section without links: {title}')
        sections.append({'titulo': title, 'enlaces': links})
    if not sections:
        raise ValueError('No planning document sections found')
    return sections


def extract_inventory(fetch) -> list[dict]:
    rows = []
    for section in parse_sections(fetch(SOURCE), SOURCE):
        title = section['titulo']
        if not re.match(r'^Plan (General|Especial)\b', title, re.I):
            raise ValueError(f'Unreviewed instrument type: {title}')
        documents, indexes, issues = {}, {}, []
        visited = {SOURCE}

        def walk(links):
            for link in links:
                target = link['url']
                if link['tipo_enlace'] == 'documento':
                    provenance = {k: link[k] for k in ('pagina_fuente', 'seccion_fuente')}
                    doc = documents.setdefault(target, {'titulo': link['titulo'], 'url': target,
                                                       'procedencia': []})
                    if provenance not in doc['procedencia']:
                        doc['procedencia'].append(provenance)
                elif link['tipo_enlace'] == 'imagen_no_documental':
                    if link not in issues:
                        issues.append(link)
                elif target not in visited:
                    if len(visited) >= 40:
                        raise ValueError('Planning inventory exceeds traversal safety bound')
                    visited.add(target)
                    indexes[target] = link
                    for child in parse_sections(fetch(target), target):
                        walk(child['enlaces'])
        walk(section['enlaces'])
        if not documents:
            raise ValueError(f'No documents for instrument: {title}')
        rows.append({
            'id': 'los-silos-plan-' + hashlib.sha256(title.casefold().encode()).hexdigest()[:16],
            'municipio': 'Los Silos', 'codigo_ine': '38042',
            'provincia': 'Santa Cruz de Tenerife', 'titulo': title,
            'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
            'origen': 'inventario_municipal_planeamiento', 'url': SOURCE,
            'inventory_url': SOURCE, 'documentos': list(documents.values()),
            'indices_documentales': list(indexes.values()), 'incidencias_fuente': issues,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'cobertura': 'Inventario documental municipal; no acredita vigencia jurídica ni reúne todas las modificaciones.',
        })
    return rows


class LosSilosAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('capture_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-los-silos/1.0 (public planning inventory)'

            def fetch(url):
                response = session.get(url, timeout=35)
                response.raise_for_status()
                if urlparse(response.url).hostname != 'www.lossilos.es':
                    raise ValueError('Unexpected inventory redirect')
                if 'html' not in response.headers.get('Content-Type', '').lower():
                    raise ValueError('Expected HTML planning inventory')
                source_urls.append(url)
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
                    (directory / name).write_text(response.text, encoding='utf-8')
                return response.text

            rows = extract_inventory(fetch)
        return {**self._write(out_jsonl, rows), 'source_urls': source_urls,
                'coverage': 'municipal_planning_document_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot: the site supplies no reliable incremental date or cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
