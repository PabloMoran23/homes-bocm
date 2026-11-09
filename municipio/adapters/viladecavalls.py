"""Selected instruments in Viladecavalls' official current-planning inventory."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://www.viladecavalls.cat/seu-electronica/normativa-municipal/'
          'normativa-urbanistica/planejament-vigent')
LIMITATIONS = [
    'Partial coverage: municipal current-planning page only, not the full RPUC or historical register.',
    'Standalone suspension map and provisional-use authorization request excluded.',
    'Dates are not stated by the inventory; document edition dates are not approval dates.',
    'No verified geometry or coordinates; publication_ready is false.',
    'No granted-licence inventory extracted.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _documents(node):
    docs = {}
    for a in node.select('a[href]'):
        url = urljoin(SOURCE + '/', a['href'])
        if not urlparse(url).path.lower().endswith('.pdf'):
            continue
        if urlparse(url).hostname not in {'www.viladecavalls.cat', 'viladecavalls.cat'}:
            raise ValueError('Unexpected document host; review inventory')
        docs.setdefault(url, {'titulo': a.get('title') or _text(a), 'url': url,
                              'source_url': SOURCE})
    return list(docs.values())


def parse_projects(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    # This inventory has no pagination. Refuse changed pagination rather than
    # returning a silently incomplete first page.
    if soup.select('a[rel~=next], .pagination, .listingBar, .batching'):
        raise ValueError('Pagination detected; traversal needs review')
    heading = soup.select_one('h1')
    content = soup.select_one('#content-core #parent-fieldname-text')
    if not heading or _text(heading) != 'Planejament vigent' or content is None:
        raise ValueError('Missing current-planning inventory')
    sections = {_text(h): h for h in content.select('h3')}
    required = {"Plànol d'Ordenació", 'Documentació escrita',
                "Projectes d'actuacions específiques i obres i usos provisionals"}
    if not required.issubset(sections):
        raise ValueError('Planning inventory sections changed')
    # The plans and written documentation are parts of ONE PGO, not projects
    # per sector/PDF. Collect both sections up to their next h3.
    plan_docs = {}
    for name in ("Plànol d'Ordenació", 'Documentació escrita'):
        for element in sections[name].next_elements:
            if getattr(element, 'name', None) == 'h3':
                break
            if getattr(element, 'name', None) == 'a':
                for doc in _documents(BeautifulSoup(str(element), 'html.parser')):
                    plan_docs.setdefault(doc['url'], doc)
    if not plan_docs or not any('normes-urbanistiques' in u for u in plan_docs):
        raise ValueError('PGO documentation missing')
    rows = [_record('pgo', "Pla general d'ordenació de Viladecavalls (PGO)",
                    'planeamiento_general', 'vigente según inventario municipal',
                    list(plan_docs.values()))]
    project_heading = sections["Projectes d'actuacions específiques i obres i usos provisionals"]
    seen = set()
    for li in project_heading.find_all_next('li'):
        if content not in li.parents:
            break
        title = _text(li)
        if title.startswith("Projecte d'urbanització"):
            kind, phase = 'proyecto_urbanizacion', None
        elif title.startswith('Aprovació definitiva dels estatuts i les bases de compensació del Pla Parcial'):
            kind, phase = 'gestion_urbanistica', 'aprobación definitiva de estatutos y bases de compensación'
        elif title.startswith('Avantprojecte '):
            kind, phase = 'anteproyecto', 'anteproyecto'
        else:
            # Requests do not establish a grant; a suspension-scope map alone
            # is not a physical works project. These are outside this adapter.
            continue
        docs = _documents(li)
        if not docs:
            raise ValueError('Supported instrument lacks documents')
        key = docs[0]['url']
        if key in seen:
            continue
        seen.add(key)
        # Keep the instrument title, without appending its attachment labels.
        title = title.split(':', 1)[0] if ':' in title else title
        rows.append(_record(key, title, kind, phase, docs))
    if len(rows) == 1:
        raise ValueError('Specific-project inventory unexpectedly empty')
    return rows


def _record(key, title, kind, phase, docs):
    return {
        'id': 'viladecavalls-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
        'municipio': 'Viladecavalls', 'provincia': 'Barcelona', 'codigo_ine': '08300',
        'titulo': title, 'tipo': kind, 'fase': phase,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': SOURCE, 'url_documento': docs[0]['url'], 'documentos': docs,
        'source': 'ayuntamiento', 'origen': 'inventario_planejament_vigent',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
    }


class ViladecavallsAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='viladecavalls', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.viladecavalls.cat')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.get(SOURCE, timeout=45, stream=True,
                          headers={'User-Agent': 'municipio-viladecavalls/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).path.rstrip('/') != urlparse(SOURCE).path:
                raise ValueError('Unexpected inventory redirect')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 4_000_000:
                    raise ValueError('Inventory exceeds response size limit')
            html = body.decode('utf-8')
        rows = parse_projects(html)
        capture = self.config.get('capture_dir')
        if capture:
            target = Path(capture)
            target.mkdir(parents=True, exist_ok=True)
            (target / 'planejament-vigent.html').write_text(html, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh of the finite inventory; no date watermark or record cap.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
