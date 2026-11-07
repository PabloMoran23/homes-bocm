"""Live Manlleu POUM record; anonymous SEGEX access has no extractable records."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.manlleu.cat/urbanisme/poum'
MONTHS = dict(zip(('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre').split(), range(1, 13)))


class _Content(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tag = None
        self.parts = []
        self.blocks = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag in ('h2', 'p'):
            self.tag, self.parts = tag, []
        if tag == 'a':
            href = dict(attrs).get('href', '')
            if re.fullmatch(r'https://dtes\.gencat\.cat/rpucportal/#/consulta/detallExpedient/\d+', href):
                self.links.append(href)

    def handle_data(self, text):
        if self.tag:
            self.parts.append(text)

    def handle_endtag(self, tag):
        if tag == self.tag:
            self.blocks.append((tag, ' '.join(''.join(self.parts).split())))
            self.tag = None


def _date_in(text):
    match = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', text.lower())
    if not match or match[2] not in MONTHS:
        return None
    try:
        return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()
    except ValueError:
        return None


class ManlleuAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.manlleu.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        parsed = _Content()
        parsed.feed(html)
        headings = [text for tag, text in parsed.blocks if tag == 'h2' and 'ordenació urbanística municipal' in text.lower()]
        paragraphs = [text for tag, text in parsed.blocks if tag == 'p' and text]
        # A navigation link alone is not a project. Require the detailed plan and
        # its actual approval narrative, and reject redirects/changed markup.
        approved = [p for p in paragraphs if 'aprovació definitiva del nou POUM' in p]
        if not headings or not approved or not parsed.links:
            raise ValueError('Manlleu POUM source no longer exposes a verified plan record')
        plan_links = set(parsed.links)
        if len(plan_links) != 1:
            raise ValueError('Ambiguous RPUC plan identifiers in Manlleu POUM source')
        plan_url = next(iter(plan_links))
        publication = next((_date_in(p) for p in approved if 'va publicar' in p and 'DOGC' in p), None)
        approval = next((_date_in(p) for p in approved if 'va fer l’aprovació definitiva' in p), None)
        return [{
            'id': 'manlleu-proy-' + hashlib.sha256(plan_url.encode()).hexdigest()[:14],
            'municipio': 'Manlleu', 'codigo_ine': '08112',
            'titulo': headings[0] + ' de Manlleu (POUM)',
            'tipo': 'POUM', 'fase': 'aprobación definitiva',
            'fecha': None, 'fecha_publicacion': publication, 'fecha_aprob': approval,
            'url': SOURCE, 'url_documento': plan_url,
            'source': 'ayuntamiento', 'origen': 'planejament_municipal',
            'rpuc_id': plan_url.rsplit('/', 1)[-1],
            'descripcion': '\n'.join(p for p in paragraphs if 'POUM' in p or 'planejament' in p),
            'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False,
            'geometry_status': 'No verified project geometry available from this source',
        }]

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        request = Request(SOURCE, headers={'User-Agent': self.config.get('user_agent', 'homes-municipio-manlleu/1.0')})
        with urlopen(request, timeout=30) as response:
            html = response.read(2_000_001)
            if len(html) > 2_000_000:
                raise ValueError('Manlleu source exceeds bounded response size')
            rows = self.parse_projects(html.decode(response.headers.get_content_charset() or 'utf-8'))
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source': SOURCE, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # This is a single current-plan page, refreshed as a complete snapshot.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public licence register; application forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
