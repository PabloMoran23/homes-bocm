"""Municipal inventory of planning instruments, not a granted-licence register."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.canetdemar.cat/document.php?id=19781'
LIMITATIONS = [
    'Partial coverage: only the municipal Normativa aplicable inventory; not the complete RPUC or works history.',
    'The municipality reports POUM annulment and planning suspension; inclusion does not certify current legal validity.',
    'Publication dates come from municipal DOGC citations; agreement/approval dates are not inferred from edict dates.',
    'No verified project geometry or granted-licence register; coordinates remain null.',
]


def _publication(text: str) -> str | None:
    # Dates attached to a DOGC citation, including the two inverted citations.
    patterns = [r'DOGC núm\. \d+ de data (\d{2}-\d{2}-\d{4})',
                r'de (?:data )?(\d{2}-\d{2}-\d{4})\s*[, (]+DOGC núm\. \d+']
    for pattern in patterns:
        found = re.search(pattern, text)
        if found:
            day, month, year = map(int, found[1].split('-'))
            return date(year, month, day).isoformat()
    return None


class CanetDeMarAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug: str, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.canetdemar.cat')

    @staticmethod
    def parse_projects(html: str | bytes) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('#cos')
        if content is None or 'PLANEJAMENT URBANÍSTIC' not in soup.get_text(' ', strip=True):
            raise ValueError('Missing municipal planning inventory')
        for a in soup.select('a[href]'):
            if ('next' in a.get('rel', []) or a.get_text(' ', strip=True).casefold()
                    in {'següent', 'següents', 'siguiente', 'next', '»', '›'}):
                raise ValueError('Pagination detected; inventory must be reviewed before extraction')
        paragraphs = content.find_all('p', recursive=False)
        active = False
        current = None
        groups = {}
        context = []
        for p in paragraphs:
            text = p.get_text(' ', strip=True)
            if ('nul·litat del POUM' in text or 'Acord GOV/' in text
                    or 's’ha acordat iniciar els estudis' in text):
                context.append({'texto': text, 'enlaces': [
                    {'titulo': a.get_text(' ', strip=True), 'url': urljoin(SOURCE, a['href'])}
                    for a in p.select('a[href]')]})
            if text == 'Normativa aplicable i enllaços de consulta:':
                active = True
                continue
            if not active:
                continue
            if text.startswith('Per acord del Ple') or text == 'Informació relacionada:':
                active = False
                current = None
                continue
            if text.startswith('- '):
                if not text.startswith(('- Pla ', '- Delimitació de la trama urbana')):
                    raise ValueError('Unreviewed instrument type in planning inventory')
                title = re.split(r',?\s*\(?DOGC|,\s*de (?:data )?\d{2}-', text[2:])[0].rstrip(' ,(')
                key = title.casefold()
                pub = _publication(text)
                if key not in groups:
                    groups[key] = {'titulo': title, 'citation': text, 'publication': pub, 'docs': {}}
                elif groups[key]['publication'] != pub:
                    raise ValueError('Conflicting publication dates for the same instrument')
                current = groups[key]
            if current is not None:
                for a in p.select('a[href]'):
                    url = urljoin(SOURCE, a['href'])
                    parsed = urlparse(url)
                    # General RPUC link has no proven association with a single
                    # listed instrument, so it must not be attached by proximity.
                    if parsed.hostname == 'dogc.gencat.cat' and parse_qs(parsed.query).get('documentId'):
                        current['docs'][url] = {'titulo': a.get_text(' ', strip=True), 'url': url,
                                                'procedencia': SOURCE, 'tipo': 'edicto_DOGC'}
        if not groups:
            raise ValueError('No planning instruments found; navigation/forms are not projects')
        records = []
        for key, group in groups.items():
            if not group['docs']:
                raise ValueError('Planning instrument has no associated official document')
            records.append({
                'id': 'canet-de-mar-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Canet de Mar', 'codigo_ine': '08040', 'provincia': 'Barcelona',
                'titulo': group['titulo'], 'tipo': 'planeamiento_urbanistico', 'fase': None,
                'fecha': None, 'fecha_publicacion': group['publication'],
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'descripcion': group['citation'], 'url': SOURCE,
                'url_documento': next(iter(group['docs'])),
                'documentos': list(group['docs'].values()),
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
                'provenance': {'url': SOURCE, 'seccion': 'Normativa aplicable i enllaços de consulta',
                               'fecha_publicacion': group['citation']},
                'contexto_planeamiento': context,
                'vigencia_verificada': False, 'limitaciones': LIMITATIONS,
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            })
        return records

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=(10, 40), stream=True,
                          headers={'User-Agent': 'municipio-canet-de-mar/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'www.canetdemar.cat':
                raise ValueError('Unexpected municipal source redirect')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Municipal inventory exceeds response limit')
            # The official page declares ISO-8859-1; let the HTML parser
            # honor its charset rather than assuming UTF-8.
            html = bytes(data)
        rows = self.parse_projects(html)
        capture = self.config.get('capture_dir')
        if capture:
            Path(capture).mkdir(parents=True, exist_ok=True)
            (Path(capture) / 'planejament.html').write_bytes(data)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temporary = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete refresh of this unpaginated inventory; no date cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        # Deliberately do not touch output: an application form is not a grant.
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
