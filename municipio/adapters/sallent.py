"""Sallent's municipal Actuacions inventory; one record per detail page."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.sallent.cat'
SOURCE = BASE + '/temes/207-urbanisme'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
DATE = r"\d{1,2}\s+(?:de\s+|d['’])(?:gener|febrer|març|abril|maig|juny|juliol|agost|setembre|octubre|novembre|desembre)\s+(?:de\s+)?\d{4}"
SUPPORTED = re.compile(r"^(?:projecte\b|memòria valorada per a la reparació\b|\d+a modificació puntual\b|modificació puntual\b|document de l'avanç de la modificació puntual\b|pla especial\b|poum\b)", re.I)


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split()) if node else ''


def _url(base, href):
    parts = urlsplit(urljoin(base, href))
    return urlunsplit((parts.scheme, parts.netloc, re.sub('/+', '/', parts.path), parts.query, parts.fragment))


def _iso(value):
    match = re.fullmatch(r"(\d{1,2})\s+(?:de\s+|d['’])(\w+)\s+(?:de\s+)?(\d{4})", value)
    if not match:
        return None
    try:
        return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()
    except (ValueError, KeyError):
        return None


def _dates(text):
    """Only explicit narrative events; page update time is never an event date."""
    text = text.lower().replace('’', "'")
    approval = None
    patterns = [
        rf"(?:celebrat el dia|celebrada el dia|sessió de|sessió celebrada en data|en data)\s+({DATE})\s*,?\s*(?:es va acordar |va prendre l'acord d'\s*|va acordar )?(?:va )?aprovar\s+(?:inicialment|definitivament|el document de l'avanç)",
        rf"va ser aprova(?:t|da)(?: definitivament)?\s+[^.;]{{0,150}}?(?:en sessió de|en data)\s+({DATE})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            approval = _iso(match[1])
            break
    # A dated publication of an approval is NOT the agreement date.
    publication_patterns = [
        rf"en data\s+({DATE}),?\s+es (?:va publicar|publica)",
        rf"publica(?:t|da|r)?\b[^;]{{0,150}}?\bdogc\b[^;]{{0,45}}?\b(?:de|del dia)\s+({DATE})",
    ]
    publication = None
    for pattern in publication_patterns:
        match = re.search(pattern, text)
        if match:
            publication = _iso(match[1])
            break
    return approval, publication


def _check_pagination(soup):
    for a in soup.select('a[href]'):
        label = _text(a).lower()
        rel = a.get('rel', [])
        if ('next' in rel or label in {'següent', 'següents', 'siguiente', 'next', '›', '»'}
                or a.find_parent(class_=re.compile(r'pagin', re.I))):
            if a['href'] not in {'', '#'}:
                raise ValueError('Inventory is paginated; refusing an incomplete snapshot')


class SallentAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        if slug != 'sallent' or str(self.config.get('ine_code', '08191')) != '08191':
            raise ValueError('This adapter is exclusively for Sallent, INE 08191')

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        _check_pagination(soup)
        blocks = [b for b in soup.select('.bloc_servei') if _text(b.find('h3')) == 'Actuacions']
        if len(blocks) != 1:
            raise ValueError('Missing or ambiguous municipal Actuacions inventory')
        entries = {}
        for a in blocks[0].select('a[href]'):
            title = _text(a)
            if not SUPPORTED.match(title):
                continue
            url = _url(SOURCE, a['href'])
            if urlsplit(url).hostname != 'www.sallent.cat' or urlsplit(url).query:
                raise ValueError('Unexpected instrument URL in municipal inventory')
            entries[url] = title
        if not entries:
            raise ValueError('No supported planning instruments or works in inventory')
        return entries

    @staticmethod
    def parse_detail(html, url, expected_title):
        soup = BeautifulSoup(html, 'html.parser')
        # The source nests two divs with id=contingut. Use the innermost one.
        nodes = soup.select('#contingut')
        if not nodes:
            raise ValueError('Missing municipal detail content: ' + url)
        content = nodes[-1]
        title = _text(content.find('h1'))
        if title != expected_title:
            raise ValueError('Inventory/detail title mismatch: ' + url)
        narrative = content.select_one('.info_contingut')
        description = _text(narrative)
        documents = {}
        for a in content.select('.espai_documents a[href], .info_contingut a[href]'):
            link = _url(url, a['href'])
            parts = urlsplit(link)
            is_file = parts.hostname == 'www.sallent.cat' and parts.path.startswith('/media/repository/')
            is_register = parts.hostname in {'dtes.gencat.cat', 'ptop.gencat.cat'} and '/rpucportal/' in parts.path
            if is_file or is_register:
                documents.setdefault(link, {'titulo': _text(a), 'url': link,
                    'tipo': 'registro_planeamiento' if is_register else 'documento',
                    'source_url': url})
        if not documents:
            raise ValueError('Instrument without supporting documents/register link: ' + url)
        approval, publication = _dates(description)
        lowered = (title + ' ' + description).lower().replace('’', "'")
        phase = None
        if 'aprovar definitivament' in lowered or 'aprovada definitivament' in lowered or "acord d'aprovació definitiva" in lowered:
            phase = 'aprobación definitiva'
        elif 'aprovar inicialment' in lowered or 'aprovació inicial' in lowered:
            phase = 'aprobación inicial'
        elif "document de l'avanç" in lowered or 'aprovació avanç' in lowered:
            phase = 'avance de planeamiento'
        planning = 'poum' in title.lower() or 'pla especial' in title.lower()
        updated = _text(content.select_one('.info_actualitzacio .data')) or None
        return {
            'id': 'sallent-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': 'Sallent', 'provincia': 'Barcelona', 'codigo_ine': '08191',
            'titulo': title, 'tipo': 'planeamiento_urbanistico' if planning else 'proyecto_obras',
            'fase': phase, 'fecha': None, 'fecha_acuerdo': approval,
            'fecha_aprob': approval, 'fecha_publicacion': publication,
            'source': 'ayuntamiento', 'origen': 'inventario_actuacions_urbanisme',
            'url': url, 'source_url': SOURCE, 'url_documento': next(iter(documents)),
            'documentos': list(documents.values()), 'descripcion': description or None,
            'source_updated_at_text': updated,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'coverage_note': 'Published municipal inventory snapshot; phase as described, not independently verified current legal status. Linked PDF/register contents and geometry not parsed.',
        }

    def _fetch(self, url):
        with requests.get(url, timeout=(10, 40), stream=True,
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-sallent/1.0')}) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != 'www.sallent.cat':
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Municipal HTML exceeds reviewed size; refusing truncation')
                chunks.append(chunk)
            body = b''.join(chunks)
            if self.config.get('capture_dir'):
                directory = Path(self.config['capture_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                name = hashlib.sha256(url.encode()).hexdigest() + '.html'
                (directory / name).write_bytes(body)
            return body.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        entries = self.parse_inventory(self._fetch(SOURCE))
        rows = [self.parse_detail(self._fetch(url), url, title) for url, title in entries.items()]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, *entries], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete public inventory refresh; no date cursor can hide undated records.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory; forms excluded'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
