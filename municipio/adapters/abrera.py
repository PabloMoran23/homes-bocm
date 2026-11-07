"""Snapshot of Abrera's official public-consultation document inventory."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://www.ajuntamentabrera.cat/serveis/'
          'obres-i-serveis-parcs-i-jardins-urbanisme-i-mobilitat/'
          'urbanisme-documentacio-per-a-consulta-publica')
LIMITATIONS = [
    'Partial coverage: current single-page public-consultation inventory only; not a historical register.',
    'Linked PDFs are retained as documentary provenance, not parsed for dates, legal effect or geometry.',
    'Publication/agreement/approval dates are unknown; filenames and related-news dates are not dates of these records.',
    'No granted-licence register or verified coordinates; publication_ready=false.',
    'Some source links are malformed and one roof notice has conflicting visible/attribute labels; inspect extraction warnings.',
]


def clean(value: str) -> str:
    return ' '.join(value.split())


def project_title(value: str) -> bool:
    return value.lower().startswith(('projecte ', 'projecte\u00a0', 'plànol de delimitació'))


def parse_inventory(html: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    soup = BeautifulSoup(html, 'html.parser')
    headings = [h for h in soup.select('main h2')
                if clean(h.get_text()).lower() == 'urbanisme - documentació a exposició pública']
    if len(headings) != 1:
        raise ValueError('Missing or ambiguous Abrera public-consultation inventory')
    content = headings[0].parent
    if content.name != 'div' or 'element-rotador' not in content.get('class', []):
        raise ValueError('Abrera inventory structure changed')
    if soup.select('link[rel~=next], a[rel~=next]') or content.select(
            '.pagination, .paginacio, [class*=paginador]'):
        raise ValueError('Pagination detected: refusing an incomplete snapshot')
    groups: dict[str, dict[str, Any]] = {}
    warnings: list[dict[str, Any]] = []
    current = None
    roofs = False

    def group(title: str):
        return groups.setdefault(title, {'titulo': title, 'documentos': []})

    # Walk in document order: Can Pous's heading is nested inside the previous
    # list, and roof safety has several distinct equipment projects in one list.
    for el in content.descendants:
        if not getattr(el, 'name', None):
            continue
        text = clean(el.get_text(' ', strip=True)) if el.name in ('p', 'strong', 'a') else ''
        if el.name == 'p' and text.lower().startswith('projectes '):
            if 'línies de vida' not in text.lower():
                raise ValueError('Unrecognized plural project group')
            roofs, current = True, None
        elif (el.name == 'p' or (el.name == 'strong' and not el.find_parent('p'))) and project_title(text) and not el.find('a'):
            current, roofs = group(text), False
        elif el.name == 'a':
            href = el.get('href', '')
            if not text:  # duplicate image-only anchors do not add documents
                continue
            if roofs:
                equipment = next((name for name in (
                    'Casa de la Cultura (Biblioteca)', 'Centre Polivalent',
                    'Escola Bressol Municipal Món Petit', 'Camp Municipal de Futbol',
                    "Escola Ernest Lluch") if name.casefold() in text.casefold()), None)
                if equipment is None:
                    raise ValueError(f'Unknown roof project: {text}')
                current = group('Projecte d’obres per a la instal·lació de línies de vida '
                                'i elements de seguretat a la coberta: ' + equipment)
            if current is None:
                raise ValueError(f'Document without an instrument heading: {text}')
            url = urljoin(SOURCE, href)
            if (urlsplit(url).hostname != 'www.ajuntamentabrera.cat'
                    or not urlsplit(url).path.startswith('/files/')
                    or not urlsplit(url).path.lower().endswith('.pdf')):
                warnings.append({'titulo': current['titulo'], 'href': href,
                                 'reason': 'Malformed or unsupported document link; excluded'})
                continue
            doc = {'titulo': text, 'url': url, 'source_url': SOURCE}
            if el.get('title'):
                doc['titulo_atributo'] = clean(el['title'])
                if ('inicial' in text.lower() and 'definitiva' in el['title'].lower()):
                    warnings.append({'url': url, 'reason': 'Visible initial-approval label conflicts with definitive-approval attribute; phase unknown'})
            if not any(d.get('url') == url for d in current['documentos']):
                current['documentos'].append(doc)
        elif el.name == 'img' and el.get('src', '').startswith('data:application/pdf;base64,'):
            if current is None:
                raise ValueError('Embedded document without an instrument')
            payload = base64.b64decode(el['src'].split(',', 1)[1], validate=True)
            if not payload.startswith(b'%PDF-'):
                raise ValueError('Invalid embedded PDF')
            digest = hashlib.sha256(payload).hexdigest()
            if any(d.get('embedded_sha256') == digest for d in current['documentos']):
                continue
            current['documentos'].append({
                'titulo': 'PDF incrustado sin etiqueta independiente', 'url': SOURCE,
                'source_url': SOURCE, 'embedded_sha256': digest,
                'source_locator': 'img[src="data:application/pdf;base64,..."]',
                'mime_type': 'application/pdf',
            })

    rows = []
    for title, item in groups.items():
        docs = item['documentos']
        if not docs:
            warnings.append({'titulo': title, 'reason': 'No usable document; instrument excluded'})
            continue
        rows.append({
            'id': 'abrera-proy-' + hashlib.sha256(title.casefold().encode()).hexdigest()[:16],
            'municipio': 'Abrera', 'provincia': 'Barcelona', 'codigo_ine': '08001',
            'titulo': title, 'tipo': 'planeamiento' if title.lower().startswith('plànol') else 'proyecto de obras',
            'fase': None, 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'url_documento': next((d['url'] for d in docs if 'embedded_sha256' not in d), SOURCE),
            'documentos': docs, 'source': 'ayuntamiento',
            'origen': 'inventario_municipal_exposicion_publica',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'No verified geometry extracted',
        })
    if not rows:
        raise ValueError('No usable Abrera instruments found')
    return rows, warnings


class AbreraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='abrera', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.ajuntamentabrera.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        return parse_inventory(html)[0]

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=(15, 60), stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-abrera/1.0'),
        }) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != 'www.ajuntamentabrera.cat':
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 10_000_000:
                    raise ValueError('Inventory exceeds 10 MB; refusing truncation')
                chunks.append(chunk)
            raw = b''.join(chunks)
            html = raw.decode('utf-8')
        rows, warnings = parse_inventory(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanisme.html').write_bytes(raw)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'source_sha256': hashlib.sha256(raw).hexdigest(),
                'warnings': warnings, 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # This inventory has no chronology/cursor: updates are full snapshots.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        Path(out_jsonl).parent.mkdir(parents=True, exist_ok=True)
        Path(out_jsonl).write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
