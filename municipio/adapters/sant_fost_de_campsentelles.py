"""Municipal POUM document inventory; deliberately partial planning coverage."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.santfost.cat/ajuntament/informacio-oficial/urbanisme/normes-urbanistiques.html'


class SantFostDeCampsentellesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.santfost.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.find('h1')
        section = soup.select_one('#page-documents')
        if not heading or heading.get_text(' ', strip=True) != 'Normes urbanístiques' or not section:
            raise ValueError('Missing municipal planning document inventory')
        # This reviewed source is a single document section, not a result listing.
        # Fail visibly if pagination appears rather than return a truncated snapshot.
        if soup.select('[rel~=next], .pagination, .paginacio, .paginator') or any(
            a.get_text(' ', strip=True).casefold() in {'següent', 'siguiente', 'next', '»', '›'}
            for a in soup.select('a[href]')
        ):
            raise ValueError('Pagination detected; inventory needs review')
        documents = {}
        title = None
        for anchor in section.select('a[href]'):
            label_node = anchor.select_one('.txt') or anchor
            label = re.sub(r'\s*\([^()]*[KMGT]?B\)\s*$', '', label_node.get_text(' ', strip=True), flags=re.I).strip()
            if not label:
                raise ValueError('Unlabelled inventory document')
            is_plan = bool(re.fullmatch(r"PLA D['’]ORDENACIÓ URBANÍSTICA MUNICIPAL SANT FOST", label, re.I))
            is_norms = bool(re.fullmatch(r'Normes text refós POUM \((CAT|CAST)\)', label, re.I))
            if not (is_plan or is_norms):
                raise ValueError(f'Unreviewed planning document; cannot silently omit: {label}')
            url = urljoin(SOURCE, anchor['href'])
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.netloc != 'www.santfost.cat' or not parsed.path.startswith('/media/repository/') or not parsed.path.lower().endswith('.pdf') or parsed.query or parsed.fragment:
                raise ValueError('Unexpected planning document URL')
            documents.setdefault(url, {'titulo': label, 'url': url, 'source_url': SOURCE})
            if is_plan:
                if title and title != label:
                    raise ValueError('Ambiguous plan title')
                title = label
        if not title or not any('Normes text refós' in d['titulo'] for d in documents.values()):
            raise ValueError('No verified POUM with normative documents')
        # Identity belongs to the instrument, not to a language/PDF rendition.
        return [{
            'id': 'sant-fost-proy-' + hashlib.sha256(SOURCE.encode()).hexdigest()[:16],
            'municipio': 'Sant Fost de Campsentelles', 'codigo_ine': '08209',
            'provincia': 'Barcelona', 'titulo': title, 'tipo': 'POUM',
            'fase': None, 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'url_documento': next(d['url'] for d in documents.values() if d['titulo'] == title),
            'documentos': list(documents.values()),
            'source': 'ayuntamiento', 'origen': 'inventario_normativa_urbanistica',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'coverage': 'Partial: municipal POUM document inventory only; not all planning dossiers or works',
            'date_notes': 'HTML inventory has no agreement/publication dates; page update and PDF filenames are not legal event dates',
        }]

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=30, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-sant-fost/1.0')
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).path != urlparse(SOURCE).path or urlparse(response.url).netloc != 'www.santfost.cat':
                raise ValueError('Unexpected inventory redirect')
            payload = bytearray()
            for chunk in response.iter_content(65536):
                payload.extend(chunk)
                if len(payload) > 2_000_000:
                    raise ValueError('Inventory exceeds reviewed response size')
            html = payload.decode('utf-8')
        rows = self.parse_projects(html)
        if self.config.get('capture_dir'):
            captures = Path(self.config['capture_dir'])
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'live-normes.html').write_text(html, encoding='utf-8')
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temporary = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        # Do not create a licence feed from application forms or planning PDFs.
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
