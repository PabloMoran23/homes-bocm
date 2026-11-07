"""Municipal POUM inventory, not a comprehensive register of current planning."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.santjoanvilatorrada.cat'
SOURCE = BASE + '/ca/ajuntament-nou/normativa-municipal/pla-dordenacio-urbanistica-municipal-poum'
LIMITATIONS = [
    'Partial municipal POUM page snapshot; listed dated amendments end in 2021, not a complete current RPUC inventory.',
    'Municipal download copies are expressly for consultation and have no official legal character; RPUC is the authoritative register.',
    'Document contents and currency are not independently verified; links retained as published.',
    'No publication dates or verified geometry supplied; no geocoding or granted licences extracted.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _key(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def _record(title, narrative, approval=None, phase=None):
    return {
        'id': 'sant-joan-de-vilatorrada-proy-' + hashlib.sha256(_key(title).encode()).hexdigest()[:20],
        'municipio': 'Sant Joan de Vilatorrada', 'provincia': 'Barcelona', 'codigo_ine': '08218',
        'titulo': title, 'descripcion': narrative,
        'tipo': 'planeamiento urbanístico', 'fase': phase,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': approval,
        'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'planejament_municipal',
        'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'coverage': 'partial',
        'geometry_status': 'No verified geometry extracted',
    }


class SantJoanDeVilatorradaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        core = soup.select_one('#content-core')
        if core is None:
            raise ValueError('Missing municipal planning content')
        if core.select('a[rel~="next"], .pagination, .batching, .listingBar'):
            raise ValueError('Unexpected pagination: inventory requires review before extraction')
        intro = next((p for p in core.find_all('p') if
                      "El Pla d'Ordenació Urbanística de Sant Joan de Vilatorrada" in _text(p)
                      and 'aprovar definitivament' in _text(p)), None)
        inventory = core.find('ol')
        if intro is None or inventory is None or 'següents modificacions' not in _text(intro):
            raise ValueError('Missing POUM approval narrative or instrument inventory')
        m = re.search(r'el dia (\d{1,2}) de juny de (\d{4})', _text(intro))
        if not m:
            raise ValueError('Unrecognized POUM approval date')
        rows = [_record("Pla d'Ordenació Urbanística Municipal de Sant Joan de Vilatorrada (POUM)",
                        _text(intro), date(int(m[2]), 6, int(m[1])).isoformat(), 'aprobación definitiva')]
        for li in inventory.find_all('li', recursive=False):
            narrative = _text(li)
            if not re.match(r'(Modificació|Pla Especial|Pla Director)', narrative, re.I):
                raise ValueError('Unexpected item in planning inventory: ' + narrative[:100])
            approval_match = re.search(r'\baprova[dt]a?\b', narrative, re.I)
            title = narrative[:approval_match.start()].rstrip(' ,.') if approval_match else narrative.rstrip('.')
            dates = re.findall(r'\b(\d{2})/(\d{2})/(\d{4})\b', narrative)
            if len(dates) > 1:
                raise ValueError('Ambiguous approval dates')
            approval = date(int(dates[0][2]), int(dates[0][1]), int(dates[0][0])).isoformat() if dates else None
            phase = ('aprobación definitiva' if 'definitivament' in narrative else 'aprobación') if approval_match else None
            rows.append(_record(title, narrative, approval, phase))
        masies = [r for r in rows if r['titulo'].lower().startswith('pla especial urbanístic de catàleg de masies')]
        if len(masies) != 1:
            raise ValueError('Missing or ambiguous masies instrument for grouped documents')
        seen = set()
        for a in core.find_all('a', href=True):
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            if parsed.scheme != 'https' or not (
                (parsed.netloc == 'seu-e.cat' and parsed.path.startswith('/documents/')) or
                (parsed.netloc == 'www.santjoanvilatorrada.cat' and parsed.path.endswith('.pdf'))
            ):
                continue
            if url in seen:
                continue
            seen.add(url)
            label = _text(a)
            target = masies[0] if label.startswith('Pla especial de masies.') else rows[0]
            target['documentos'].append({'titulo': label, 'url': url, 'source_url': SOURCE,
                                        'caracter': 'copia municipal de consulta; no oficial'})
        if not rows[0]['documentos'] or not masies[0]['documentos']:
            raise ValueError('Planning document groups missing')
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate instrument identities')
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        response = requests.get(SOURCE, timeout=(10, 45), stream=True,
                                headers={'User-Agent': self.config.get('user_agent', 'municipio-sant-joan-de-vilatorrada/1.0')})
        with response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Source exceeds 4 MB; refusing truncated inventory')
                chunks.append(chunk)
            body = b''.join(chunks)
        if urlparse(response.url).netloc != urlparse(BASE).netloc:
            raise ValueError('Unexpected source redirect')
        rows = self.parse_projects(body.decode('utf-8'))
        if self.config.get('capture_dir'):
            capture_dir = Path(self.config['capture_dir'])
            capture_dir.mkdir(parents=True, exist_ok=True)
            (capture_dir / 'poum.html').write_bytes(body)
            (capture_dir / 'poum-response.json').write_text(json.dumps({
                'source_url': SOURCE, 'final_url': response.url, 'http_status': response.status_code,
                'sha256': hashlib.sha256(body).hexdigest(), 'bytes': size,
            }, indent=2), encoding='utf-8')
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # The source is an unpaginated inventory: updates replace the full snapshot.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
