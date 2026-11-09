"""Castelló (Valencia, INE 46257): public detailed-plan document inventory."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://castello.sedelectronica.es'
PARENT = BASE + '/transparency/47001e76-9560-4fb3-991e-da5e553aefed/'
SOURCE = BASE + '/transparency/1fd32726-d72d-4838-8d29-9a0217fbe2ce/'
PLAN = "PLA D'ORDENACIÓ DETALLADA"


def parse_inventory(html: str, expected_documents: int | None = None) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    if '6.1.2. NORMATIVA URBANÍSTICA' not in text:
        raise ValueError('Missing Castelló planning inventory heading')
    # This small public folder has no paginator today. Fail visibly if it grows
    # a continuation control instead of publishing a silently truncated snapshot.
    for a in soup.select('a[href], a[onclick], button'):
        label = ' '.join([a.get_text(' ', strip=True), a.get('title', ''), a.get('aria-label', '')]).lower()
        if (any(t in label for t in ("veure'n més", 'ver más', 'següent', 'siguiente', 'next'))
                or 'next' in a.get('rel', [])):
            if not a.has_attr('disabled') and a.get('aria-disabled') != 'true':
                raise ValueError('Inventory pagination requires explicit handling')
    links = {}
    for a in soup.select('table tbody a[href]'):
        url = urljoin(SOURCE, a['href'])
        if urlparse(url).path.startswith('/preview-document/'):
            if urlparse(url).netloc != urlparse(BASE).netloc or urlparse(url).scheme != 'https':
                raise ValueError('Unexpected document host')
            links[url] = a
    if expected_documents is not None and len(links) != expected_documents:
        raise ValueError('Document count differs from parent inventory; possible pagination')
    documents = []
    for url, a in links.items():
        title = a.get_text(' ', strip=True)
        # Deliberately limited to the detailed plan, not forms or announcements.
        if not title.upper().startswith(PLAN):
            raise ValueError('Unreviewed document added to detailed-plan inventory')
        documents.append({'titulo': title, 'url': url, 'descripcion_fuente': a.get('title') or None})
    if not documents:
        raise ValueError('No detailed-plan documents found')
    documents.sort(key=lambda d: d['url'])
    phases = {d['descripcion_fuente'] for d in documents}
    return [{
        'id': 'castello-plan-' + hashlib.sha256((SOURCE + '#' + PLAN).encode()).hexdigest()[:16],
        'municipio': 'Castelló', 'provincia': 'Valencia', 'codigo_ine': '46257',
        'titulo': "Pla d'Ordenació Detallada de Castelló",
        'tipo': 'plan de ordenación detallada',
        'fase': 'aprobación definitiva' if phases == {"Aprovació definitiva del Pla d'Ordenació Detallada"} else None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': SOURCE, 'url_documento': documents[0]['url'], 'documentos': documents,
        'source': 'ayuntamiento', 'origen': 'inventario_normativa_urbanistica',
        'descripcion': 'Instrumento publicado en la carpeta municipal de normativa urbanística. Las fechas del acuerdo y de publicación no constan en el inventario.',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No project geometry extracted; no municipal centroid substituted',
    }]


class CastelloAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='castello', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, session, url, capture_name):
        response = session.get(url, timeout=30, stream=True)
        response.raise_for_status()
        if urlparse(response.url).netloc != urlparse(BASE).netloc:
            raise ValueError('Unexpected redirect outside municipal seat')
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > 2_000_000:
                raise ValueError('Municipal HTML exceeds 2 MB')
        html = data.decode('utf-8')
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / capture_name).write_bytes(data)
        return html

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-castello/1.0 (public planning inventory)'
            parent = self._fetch(session, PARENT, 'live-parent.html')
            text = BeautifulSoup(parent, 'html.parser').get_text(' ', strip=True)
            match = re.search(r'6\.1\.2\. NORMATIVA URBANÍSTICA\s*\(\s*(\d+)\s*\)', text)
            if not match:
                raise ValueError('Missing parent inventory count')
            html = self._fetch(session, SOURCE, 'live-inventory.html')
            rows = parse_inventory(html, int(match[1]))
            for doc in rows[0]['documentos']:
                preview = self._fetch(session, doc['url'], 'live-document-' + doc['url'].rsplit('/', 1)[-1] + '.html')
                soup = BeautifulSoup(preview, 'html.parser')
                if doc['titulo'] not in soup.get_text(' ', strip=True) or not soup.select_one('iframe[src*="/preview/pdf/"]'):
                    raise ValueError('Document preview no longer exposes the plan PDF')
                # Archive metadata is retained as source text, never an approval.
                text = soup.get_text(' ', strip=True)
                match = re.search(r'Data de creació\s+(.+?)\s+Tipus de document', text)
                doc['fecha_creacion_documento_texto'] = match[1] if match else None
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [PARENT, SOURCE] + [d['url'] for d in rows[0]['documentos']],
                'coverage': 'Complete current detailed-plan folder; partial municipality coverage', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register; application forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
