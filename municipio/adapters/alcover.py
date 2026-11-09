"""Alcover's municipal planning inventory, one record per named instrument."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/alcover/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/planejament-urbanistic')
BASE_TITLE = "PLA D'ORDENACIÓ URBANÍSTICA MUNICIPAL"
MODIFICATION = re.compile(r'MODIFICACIÓ PUNTUAL NÚM\.\s*(\d+)\s+DEL POUM')
LIMITATIONS = [
    'Partial coverage: only the POUM and numbered modifications section; special plans, specific-action projects, works and urban management are outside this adapter.',
    'RPUC links are dossier references, not downloaded dossier contents; municipal PDF links are retained without parsing their contents.',
    'No agreement, approval or publication dates verified in this inventory; page update dates are excluded.',
    'No verified geometry or coordinates; publication_ready is false. No granted licences extracted.',
]


def _clean(value: str) -> str:
    return ' '.join(value.split())


def _fold(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                   if unicodedata.category(c) != 'Mn')


def _document_kind(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.scheme != 'https':
        return None
    if (parsed.hostname in {'dtes.gencat.cat', 'planejamenturbanisme.territori.gencat.cat'}
            and re.fullmatch(r'/consulta/(?:detallExpedient|fitxaExpedient)/\d+(?:/documents)?',
                             parsed.fragment)):
        return 'rpuc_dossier'
    if parsed.hostname == 'seu-e.cat' and parsed.path.startswith('/documents/'):
        return 'municipal_document'
    if parsed.hostname == 'dtes.gencat.cat' and parsed.path.startswith('/muc-visor/'):
        return 'map_viewer'
    return None


class AlcoverAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug: str, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.alcover.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        candidates = [block for block in soup.select('.journal-content-article')
                      if any(_clean(str(t)) == BASE_TITLE for t in block.find_all(string=True))]
        if len(candidates) != 1:
            raise ValueError('Missing or ambiguous Alcover planning inventory')
        content = candidates[0]
        # This inventory is an unpaginated HTML list. Refuse a changed paginated
        # source instead of returning an apparently complete first page.
        if content.select('[rel~=next], .pagination, .lfr-pagination, .taglib-page-iterator'):
            raise ValueError('Planning inventory now exposes pagination; traversal must be reviewed')
        expected_modifications = len(content.find_all(string=lambda t: bool(MODIFICATION.fullmatch(_clean(str(t))))))
        sections = [block for block in content.select('.md-htmlblock')
                    if any(_clean(str(t)) == BASE_TITLE for t in block.find_all(string=True))
                    and expected_modifications > 0
                    and sum(bool(MODIFICATION.fullmatch(_clean(str(t))))
                            for t in block.find_all(string=True)) == expected_modifications]
        if not sections:
            raise ValueError('Missing POUM/modifications section boundary')
        content = min(sections, key=lambda block: len(str(block)))
        groups = []
        current = None
        for node in content.descendants:
            if isinstance(node, NavigableString):
                if node.find_parent(['a', 'script', 'style']):
                    continue
                text = _clean(str(node))
                match = MODIFICATION.fullmatch(text)
                if text == BASE_TITLE or match:
                    key = 'mp-' + match[1] if match else 'poum'
                    current = {'key': key, 'title': text, 'parts': [], 'documents': []}
                    groups.append(current)
                elif current and text and not text.startswith('MODIFICACIONS PUNTUALS'):
                    current['parts'].append(text)
            elif isinstance(node, Tag) and node.name == 'a' and current:
                url = urljoin(SOURCE, node.get('href', ''))
                kind = _document_kind(url)
                if kind and not any(d['url'] == url for d in current['documents']):
                    current['documents'].append({'titulo': node.get_text(' ', strip=True),
                                                 'url': url, 'tipo': kind, 'source_url': SOURCE})
        keys = [g['key'] for g in groups]
        if not groups or keys[0] != 'poum' or len(keys) != len(set(keys)):
            raise ValueError('Missing base POUM or duplicate planning instrument headings')
        rows = []
        for group in groups:
            docs = group['documents']
            primary = [d for d in docs if d['tipo'] != 'map_viewer']
            if not primary:
                raise ValueError('Instrument has no official dossier/document: ' + group['title'])
            # Approval stage only where stated, never inferred from RPUC presence.
            narrative = _clean(' '.join(group['parts']))
            stage_text = _fold(narrative + ' ' + ' '.join(d['titulo'] for d in docs))
            stages = [stage for marker, stage in (
                ('aprovacio definitiva', 'aprobación definitiva'),
                ('aprovacio provisional', 'aprobación provisional'),
                ('aprovat inicialment', 'aprobación inicial'),
                ('aprovacio inicial', 'aprobación inicial'),
                ('aprovacio inical', 'aprobación inicial'),  # source spelling
            ) if marker in stage_text]
            stages = set(stages)
            if len(stages) > 1:
                raise ValueError('Conflicting approval stages: ' + group['title'])
            rows.append({
                'id': 'alcover-proy-' + group['key'],
                'municipio': 'Alcover', 'provincia': 'Tarragona', 'codigo_ine': '43005',
                'titulo': group['title'],
                'tipo': 'POUM' if group['key'] == 'poum' else 'modificación puntual del POUM',
                'fase': next(iter(stages), None),
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'descripcion': narrative, 'url': SOURCE, 'url_documento': primary[0]['url'],
                'documentos': docs, 'source': 'ayuntamiento', 'origen': 'planejament_municipal',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'No verified instrument geometry from the inventory',
            })
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=(15, 45), stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-alcover/1.0')
        }) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Alcover inventory exceeds 4 MB; refusing truncation')
                chunks.append(chunk)
            raw = b''.join(chunks)
            html = raw.decode('utf-8')
        rows = self.parse_projects(html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            target = Path(capture_dir)
            target.mkdir(parents=True, exist_ok=True)
            (target / 'planejament.html').write_bytes(raw)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                             encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'Complete POUM/numbered-modifications section; partial municipal coverage',
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
