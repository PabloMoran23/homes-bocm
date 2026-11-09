"""Municipal planning inventory snapshot; not a licence or works register."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://www.seu-e.cat/web/ulldecona/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme')
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Partial coverage: one static municipal planning inventory, last updated 24/05/2024; not the complete RPUC register.',
    'UA4 public-exposure link from the municipal urbanism page returned HTTP 404 during research.',
    'No granted-licence register or exhaustive public-works inventory extracted.',
    'Documents are linked as published; PDF contents and current legal validity are not independently certified.',
    'No verified geometry; coordinates remain null and publication_ready is false.',
    'Multiple agreement/publication dates remain arrays with source narratives; ambiguous singular dates are null.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _dates(text):
    pattern = r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})|(\d{1,2})\s+d[’e']\s*(gener|febrer|març|abril|maig|juny|juliol|agost|setembre|octubre|novembre|desembre)\s+de\s+(\d{4})"
    result = []
    for m in re.finditer(pattern, text.lower()):
        day, month, year = (int(m[1]), int(m[2]), int(m[3])) if m[1] else (int(m[4]), MONTHS[m[5]], int(m[6]))
        result.append(date(year, month, day).isoformat())
    return list(dict.fromkeys(result))


class UlldeconaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://ulldecona.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        # The header repeats a stale inventory inside an access-direct widget.
        articles = [a for a in soup.select('.journal-content-article')
                    if not a.select('.accessdirecte_element')
                    and 'TEXT NORMES SUBSIDIÀRIES' in _text(a)]
        if len(articles) != 1:
            raise ValueError('Missing or ambiguous municipal planning article')
        article = articles[0]
        if article.select('a[rel~=next], .pagination a, a.next'):
            raise ValueError('Inventory now paginated; traversal must be implemented')
        content = article.find('div', recursive=False)
        if content is None:
            raise ValueError('Missing inventory content')
        sections, current = [], None
        for block in content.find_all(['p', 'ul'], recursive=False):
            text = _text(block)
            if block.name == 'p' and re.match(r'^[–-]\s*\S', text):
                current = {'title': text.lstrip('–- ').strip(), 'texts': [], 'docs': []}
                sections.append(current)
            elif current and text:
                if not block.find('a'):
                    current['texts'].append(text)
            if current:
                for a in block.select('a[href]'):
                    url = urljoin(SOURCE, a['href'])
                    if urlsplit(url).hostname not in ('ulldecona.cat', 'www.ulldecona.cat') or not urlsplit(url).path.lower().endswith('.pdf'):
                        raise ValueError('Unexpected non-municipal/non-PDF inventory document')
                    doc = {'titulo': _text(a), 'url': url, 'source_url': SOURCE}
                    if doc not in current['docs']:
                        current['docs'].append(doc)
        # First five sections are chapters/maps of the SAME Normes Subsidiàries.
        boundary = next((i for i, s in enumerate(sections) if s['title'].startswith('Pla Parcial')), None)
        if boundary is None or boundary != 5:
            raise ValueError('NSU chapter layout changed; review grouping')
        nsu = {'title': 'Normes Subsidiàries de Planejament d’Ulldecona',
               'texts': [t for s in sections[:boundary] for t in s['texts']],
               'docs': [d for s in sections[:boundary] for d in s['docs']]}
        instruments = [nsu] + sections[boundary:]
        rows = []
        for section in instruments:
            title = section['title']
            # Environmental noise regulation is not a physical project/urban plan.
            if title.startswith('Mapa de Capacitat Acústica'):
                continue
            if not title.startswith(('Normes Subsidiàries', 'Pla Parcial', 'Pla Especial', 'Pla Millora', 'Unitat d’Actuació', 'Delimitació Trama')):
                raise ValueError('Unclassified inventory section: ' + title)
            if not section['docs'] or not section['texts']:
                raise ValueError('Instrument lacks narrative or documents: ' + title)
            agreements, publications, evidence = [], [], []
            if section is not nsu:
                for narrative in section['texts']:
                    # Parenthesized DOGC references are publications, not agreements.
                    gazettes = re.findall(r'\(DOGC[^)]*\)', narrative)
                    agreement_text = re.sub(r'\(DOGC[^)]*\)', '', narrative)
                    if re.search(r'aprovat|aprovada', agreement_text, re.I):
                        agreements.extend(_dates(agreement_text))
                    for gazette in gazettes:
                        publications.extend(_dates(gazette))
                    evidence.append({'texto': narrative, 'source_url': SOURCE})
            agreements = sorted(set(agreements))
            publications = sorted(set(publications))
            rows.append({
                'id': 'ulldecona-proy-' + hashlib.sha256(title.casefold().encode()).hexdigest()[:16],
                'municipio': 'Ulldecona', 'provincia': 'Tarragona', 'codigo_ine': '43156',
                'titulo': title, 'tipo': 'instrumento de planeamiento urbanístico',
                'fase': None, 'fecha': None,
                'fecha_acuerdo': agreements[0] if len(agreements) == 1 else None,
                'fecha_publicacion': publications[0] if len(publications) == 1 else None,
                'fechas_acuerdo': agreements, 'fechas_publicacion_dogc': publications,
                'evidencia_fechas': evidence,
                'descripcion': '\n'.join(section['texts']),
                'url': SOURCE, 'url_documento': section['docs'][0]['url'],
                'documentos': section['docs'], 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_planeamiento',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'limitations': LIMITATIONS,
            })
        if not rows:
            raise ValueError('No verified planning instruments')
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=45, stream=True,
                          headers={'User-Agent': 'municipio-ulldecona/1.0'}) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 3_000_000:
                    raise ValueError('Inventory exceeds response size limit')
            html = data.decode('utf-8-sig')
        rows = self.parse_projects(html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory_live.html').write_text(html, encoding='utf-8')
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
