"""Snapshot of Matadepera's official ordinary public-works dossier inventory."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/matadepera/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/projectes-d-obra-municipal-204')
MARKER = "projectes locals d'obra ordinària"
LIMITATIONS = [
    'Only the currently published ordinary municipal public-works inventory; not all municipal planning or works history.',
    'One record per published dossier heading, including headings covering several technical projects.',
    'Document associations are those published by the municipality; attachments are linked, not interpreted as independently verified decisions.',
    'No per-project publication dates or verified geometry; page update timestamp is not a project date.',
    'Approval phases describe the published dossier, not verified present execution status. Licences disabled.',
    'Shared entity policy may quarantine records without an explicit municipal expediente; document folder IDs are not expediente numbers.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _agreement(text):
    # Only explicit approval narrative, never a filename, crawl time or page update.
    match = re.search(r"(?:ha aprovat inicialment|s'ha aprovat inicialment).*?"
                      r'(\d{1,2})[/.](\d{1,2})[/.](\d{4})', text, re.I)
    if match:
        return date(int(match[3]), int(match[2]), int(match[1])).isoformat()
    # In these paragraphs the agreement date precedes the approval predicate.
    match = re.search(r'en data (\d{1,2})[/.](\d{1,2})[/.](\d{4}) ha aprovat inicialment', text, re.I)
    return date(int(match[3]), int(match[2]), int(match[1])).isoformat() if match else None


class MatadeperaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.select('a[href]'):
            if ('next' in (a.get('rel') or []) or
                re.fullmatch(r'(següent|siguiente|next|[»›])', _text(a), re.I)) and a['href'] not in ('', '#'):
                raise ValueError('Inventory pagination detected; refusing a partial snapshot')
        articles = [c for c in soup.select('.journal-content-article') if MARKER in _text(c)]
        if len(articles) != 1:
            raise ValueError('Expected one official public-works inventory article')
        content = articles[0]
        headings = []
        for tag in content.find_all(['ul', 'p']):
            title = _text(tag)
            if tag.find('a'):
                continue
            if ((tag.name == 'ul' and len(tag.find_all('li')) == 1) or
                (tag.name == 'p' and tag.find('strong') and title.startswith('Projecte'))):
                if not re.match(r'^(Expedient d.aprovació|Aprovació|Memòria valorada|Projecte)\b', title):
                    raise ValueError('Unrecognized dossier heading: ' + title)
                headings.append(tag)
        if not headings:
            raise ValueError('No dossier headings')
        heading_ids = {id(h) for h in headings}
        groups = []
        current = None
        for node in content.descendants:
            if isinstance(node, Tag) and id(node) in heading_ids:
                current = {'title': _text(node), 'docs': {}, 'narrative': []}
                groups.append(current)
            if isinstance(node, Tag) and node.name == 'a' and '/documents/' in node.get('href', ''):
                if current is None:
                    raise ValueError('Ungrouped source document')
                url = urljoin(SOURCE, node['href'])
                if urlparse(url).hostname != 'seu-e.cat' or not urlparse(url).path.startswith('/documents/1686281/'):
                    raise ValueError('Unexpected document provenance: ' + url)
                doc = current['docs'].setdefault(url, {'url': url, 'titulos': [], 'source_url': SOURCE})
                label = _text(node)
                if label and label not in doc['titulos']:
                    doc['titulos'].append(label)
            if isinstance(node, NavigableString) and current is not None and not node.find_parent('a'):
                current['narrative'].append(str(node))
        rows = []
        for group in groups:
            title, docs = group['title'], list(group['docs'].values())
            if not docs or not any(re.search(r'projecte|memòria', ' '.join(d['titulos']), re.I) for d in docs):
                raise ValueError('Dossier lacks technical project or memoir: ' + title)
            narrative = ' '.join(' '.join(group['narrative']).split())
            agreement = _agreement(narrative)
            phase = 'aprobación inicial' if 'inicial' in narrative.lower() else None
            folders = sorted({urlparse(d['url']).path.split('/')[3] for d in docs})
            rows.append({
                'id': 'matadepera-proy-' + hashlib.sha256(title.encode()).hexdigest()[:16],
                'municipio': 'Matadepera', 'provincia': 'Barcelona', 'codigo_ine': '08120',
                'titulo': title, 'tipo': 'proyecto de obra municipal', 'fase': phase,
                'expediente': next(iter(re.findall(r'\bX\d{10}\b', title)), None),
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': agreement,
                'fecha_aprob': agreement, 'fecha_acuerdo_texto': narrative if agreement else None,
                'descripcion': narrative, 'url': SOURCE, 'source': 'ayuntamiento',
                'origen': 'inventario_proyectos_obra_municipal', 'documentos': docs,
                'document_folder_ids': folders,
                'document_provenance': 'Grouped under the same municipal inventory heading; links retained as published.',
                'document_warning': 'Multiple document folders in source grouping; associations not independently verified.' if len(folders) > 1 else None,
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': 'Current published inventory snapshot; bundled projects remain one dossier.',
            })
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate dossier headings require identity review')
        return rows

    @staticmethod
    def _write(path: Path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        response = requests.get(SOURCE, timeout=40, stream=True,
                                headers={'User-Agent': 'municipio-matadepera/1.0'})
        with response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory exceeds reviewed response size')
                chunks.append(chunk)
            payload = b''.join(chunks)
        html = payload.decode('utf-8')
        rows = self.parse_projects(html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'live-public-works.html').write_bytes(payload)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete snapshot; no high-water mark can hide amended old dossiers.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
